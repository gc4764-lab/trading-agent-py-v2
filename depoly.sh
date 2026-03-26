#!/bin/bash
# deploy.sh - Production Deployment Script

set -e

echo "🚀 Trading Agent Production Deployment"
echo "========================================"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required" >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "⚠️  kubectl not found, using Docker Compose" >&2; USE_K8S=false; }

# Load environment
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
fi

# Run database migrations
echo "📊 Running database migrations..."
python -m alembic upgrade head

# Build Docker image
echo "🐳 Building Docker image..."
docker build -t trading-agent:production -f Dockerfile.prod .

if [ "$USE_K8S" != "false" ]; then
    echo "☸️  Deploying to Kubernetes..."
    
    # Create namespace
    kubectl create namespace trading-production --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply secrets
    kubectl create secret generic trading-secrets \
        --from-literal=database-password=$POSTGRES_PASSWORD \
        --from-literal=binance-api-key=$BINANCE_API_KEY \
        --from-literal=binance-api-secret=$BINANCE_API_SECRET \
        --namespace trading-production \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply configurations
    kubectl apply -f kubernetes/deployment.yaml -n trading-production
    kubectl apply -f kubernetes/service.yaml -n trading-production
    
    # Wait for rollout
    kubectl rollout status deployment/trading-agent -n trading-production
    
    # Get service endpoint
    SERVICE_IP=$(kubectl get service trading-agent-service -n trading-production -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    echo "✅ Deployment complete! Service IP: $SERVICE_IP"
    
else
    echo "🐳 Deploying with Docker Compose..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services
    sleep 10
    
    # Health check
    curl -f http://localhost:8080/health || { echo "❌ Health check failed"; exit 1; }
    
    echo "✅ Deployment complete!"
    echo "   API: http://localhost:8000"
    echo "   Dashboard: http://localhost:8500"
    echo "   Metrics: http://localhost:9090"
fi

# Create initial backup
echo "💾 Creating initial backup..."
python -m trading_agent.cli backup

echo "========================================"
echo "🎉 Production deployment successful!"
