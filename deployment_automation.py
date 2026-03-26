# deployment_automation.py - Automated Deployment Scripts
import subprocess
import sys
import os
import yaml
from pathlib import Path

class DeploymentAutomation:
    """Automated deployment management"""
    
    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """Load deployment configuration"""
        config_file = f"config/{self.environment}.yaml"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            'docker': {
                'image': 'trading-agent:latest',
                'container_name': f'trading-agent-{self.environment}',
                'ports': ['8000:8000', '8500:8500', '9090:9090'],
                'volumes': ['./data:/app/data', './logs:/app/logs']
            },
            'kubernetes': {
                'namespace': f'trading-{self.environment}',
                'replicas': 1 if self.environment == 'development' else 3,
                'resources': {
                    'requests': {'memory': '512Mi', 'cpu': '500m'},
                    'limits': {'memory': '1Gi', 'cpu': '1000m'}
                }
            }
        }
    
    def deploy_docker(self):
        """Deploy with Docker Compose"""
        print(f"🚀 Deploying to {self.environment} with Docker...")
        
        # Build image
        subprocess.run(["docker", "build", "-t", "trading-agent:latest", "."])
        
        # Run container
        compose_file = f"docker-compose.{self.environment}.yml"
        subprocess.run(["docker-compose", "-f", compose_file, "up", "-d"])
        
        print("✅ Deployment complete!")
        print(f"   API: http://localhost:8000")
        print(f"   Dashboard: http://localhost:8500")
        print(f"   Metrics: http://localhost:9090")
    
    def deploy_kubernetes(self):
        """Deploy to Kubernetes"""
        print(f"☸️ Deploying to Kubernetes ({self.environment})...")
        
        # Apply namespace
        subprocess.run([
            "kubectl", "create", "namespace", 
            self.config['kubernetes']['namespace'], "--dry-run=client", "-o", "yaml"
        ], capture_output=True)
        
        # Apply deployments
        subprocess.run([
            "kubectl", "apply", "-f", "kubernetes/deployment.yaml",
            "-n", self.config['kubernetes']['namespace']
        ])
        
        # Wait for rollout
        subprocess.run([
            "kubectl", "rollout", "status", 
            f"deployment/trading-agent", 
            "-n", self.config['kubernetes']['namespace']
        ])
        
        print("✅ Kubernetes deployment complete!")
    
    def rollback(self, version: str):
        """Rollback to previous version"""
        print(f"🔄 Rolling back to version {version}...")
        
        if self.environment == "kubernetes":
            subprocess.run([
                "kubectl", "rollout", "undo", 
                f"deployment/trading-agent", 
                "--to-revision", version,
                "-n", self.config['kubernetes']['namespace']
            ])
        else:
            # Docker rollback
            subprocess.run([
                "docker", "stop", self.config['docker']['container_name']
            ])
            subprocess.run([
                "docker", "run", "-d", 
                "--name", self.config['docker']['container_name'],
                f"trading-agent:{version}"
            ])
        
        print("✅ Rollback complete!")
    
    def health_check(self):
        """Check deployment health"""
        print("🏥 Running health checks...")
        
        import requests
        
        endpoints = [
            "http://localhost:8000/health",
            "http://localhost:8080/health",
            "http://localhost:9090/metrics"
        ]
        
        all_healthy = True
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    print(f"  ✓ {endpoint} - OK")
                else:
                    print(f"  ✗ {endpoint} - Failed ({response.status_code})")
                    all_healthy = False
            except Exception as e:
                print(f"  ✗ {endpoint} - Error: {e}")
                all_healthy = False
        
        if all_healthy:
            print("✅ All health checks passed!")
        else:
            print("❌ Some health checks failed!")

# ============= Monitoring Dashboard Generator =============

class GrafanaDashboardGenerator:
    """Generate Grafana dashboards automatically"""
    
    def __init__(self):
        self.dashboard = {
            "dashboard": {
                "title": "Trading Agent Dashboard",
                "panels": [],
                "time": {"from": "now-6h", "to": "now"},
                "schemaVersion": 16,
                "version": 0
            },
            "overwrite": True
        }
    
    def add_panel(self, title: str, query: str, panel_type: str = "graph"):
        """Add panel to dashboard"""
        panel = {
            "title": title,
            "type": panel_type,
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "targets": [{
                "expr": query,
                "legendFormat": "{{symbol}}",
                "refId": "A"
            }]
        }
        self.dashboard["dashboard"]["panels"].append(panel)
    
    def generate(self):
        """Generate complete dashboard"""
        # Add P&L panel
        self.add_panel(
            "Trading P&L Over Time",
            "trading_pnl{symbol!=''}"
        )
        
        # Add positions panel
        self.add_panel(
            "Current Positions",
            "trading_position_size{symbol!=''}"
        )
        
        # Add risk metrics panel
        self.add_panel(
            "Risk Metrics",
            "trading_risk_exposure"
        )
        
        # Add order volume panel
        self.add_panel(
            "Order Volume",
            "rate(trading_orders_total[5m])",
            "stat"
        )
        
        # Save dashboard
        with open("grafana/dashboards/trading_dashboard.json", "w") as f:
            json.dump(self.dashboard, f, indent=2)
        
        print("✅ Grafana dashboard generated!")

# ============= Main Deployment Script =============

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Trading Agent Deployment")
    parser.add_argument("command", choices=["deploy", "rollback", "health", "dashboard"],
                       help="Deployment command")
    parser.add_argument("--env", default="development",
                       choices=["development", "staging", "production"],
                       help="Deployment environment")
    parser.add_argument("--version", help="Version for rollback")
    
    args = parser.parse_args()
    
    deployer = DeploymentAutomation(args.env)
    
    if args.command == "deploy":
        deployer.deploy_docker() if args.env != "kubernetes" else deployer.deploy_kubernetes()
    elif args.command == "rollback":
        deployer.rollback(args.version)
    elif args.command == "health":
        deployer.health_check()
    elif args.command == "dashboard":
        generator = GrafanaDashboardGenerator()
        generator.generate()
        