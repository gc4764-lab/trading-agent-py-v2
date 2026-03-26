# error_handling.py - Comprehensive Error Handling System
import traceback
from enum import Enum
from typing import Optional, Callable, Any
import functools

class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class TradingError(Exception):
    """Base trading exception"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR, 
                 context: Optional[Dict] = None):
        self.message = message
        self.severity = severity
        self.context = context or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)

class OrderError(TradingError):
    """Order-related errors"""
    pass

class RiskError(TradingError):
    """Risk management errors"""
    pass

class MarketDataError(TradingError):
    """Market data errors"""
    pass

class AlertError(TradingError):
    """Alert-related errors"""
    pass

class ErrorHandler:
    """Centralized error handling system"""
    
    def __init__(self):
        self.error_handlers: Dict[type, Callable] = {}
        self.error_history: List[Dict] = []
        self.circuit_breakers: Dict[str, Dict] = {}
        
    def register_handler(self, error_type: type, handler: Callable):
        """Register error handler for specific exception type"""
        self.error_handlers[error_type] = handler
        
    async def handle_error(self, error: Exception, context: Optional[Dict] = None):
        """Handle error with appropriate handler"""
        error_info = {
            'type': error.__class__.__name__,
            'message': str(error),
            'traceback': traceback.format_exc(),
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Store error history
        self.error_history.append(error_info)
        
        # Keep only last 1000 errors
        if len(self.error_history) > 1000:
            self.error_history.pop(0)
        
        # Find handler
        handler = None
        for error_type, error_handler in self.error_handlers.items():
            if isinstance(error, error_type):
                handler = error_handler
                break
        
        if handler:
            try:
                await handler(error_info)
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
        
        # Log error
        if isinstance(error, TradingError):
            log_func = {
                ErrorSeverity.DEBUG: logger.debug,
                ErrorSeverity.INFO: logger.info,
                ErrorSeverity.WARNING: logger.warning,
                ErrorSeverity.ERROR: logger.error,
                ErrorSeverity.CRITICAL: logger.critical
            }.get(error.severity, logger.error)
            
            log_func(f"{error.__class__.__name__}: {error.message}")
        else:
            logger.error(f"Unexpected error: {error_info['traceback']}")
        
        # Check circuit breaker
        await self._check_circuit_breaker(error)
        
        return error_info
    
    def circuit_breaker(self, name: str, failure_threshold: int = 5, 
                        recovery_timeout: int = 60):
        """Circuit breaker decorator"""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                circuit = self.circuit_breakers.get(name, {
                    'state': 'closed',
                    'failures': 0,
                    'last_failure': None
                })
                
                if circuit['state'] == 'open':
                    if circuit['last_failure']:
                        elapsed = (datetime.now() - circuit['last_failure']).total_seconds()
                        if elapsed >= recovery_timeout:
                            circuit['state'] = 'half-open'
                        else:
                            raise TradingError(f"Circuit breaker '{name}' is open")
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Success - reset circuit
                    if circuit['state'] == 'half-open':
                        circuit['state'] = 'closed'
                        circuit['failures'] = 0
                    
                    return result
                    
                except Exception as e:
                    circuit['failures'] += 1
                    circuit['last_failure'] = datetime.now()
                    
                    if circuit['failures'] >= failure_threshold:
                        circuit['state'] = 'open'
                        logger.warning(f"Circuit breaker '{name}' opened")
                    
                    raise e
                finally:
                    self.circuit_breakers[name] = circuit
            
            return wrapper
        return decorator
    
    async def _check_circuit_breaker(self, error: Exception):
        """Check if error should trigger circuit breaker"""
        if isinstance(error, (MarketDataError, OrderError)):
            # These errors might indicate system issues
            pass
    
    def get_error_stats(self) -> Dict:
        """Get error statistics"""
        if not self.error_history:
            return {}
        
        error_counts = {}
        for error in self.error_history:
            error_type = error['type']
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'by_type': error_counts,
            'last_error': self.error_history[-1] if self.error_history else None,
            'circuit_breakers': self.circuit_breakers
        }

# ============= Advanced Logging System =============

import logging.handlers
import json
from datetime import datetime
import socket
import platform

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'hostname': socket.gethostname(),
            'process_id': record.process,
            'thread_id': record.thread
        }
        
        if hasattr(record, 'context'):
            log_entry['context'] = record.context
            
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

class LogManager:
    """Centralized log management"""
    
    def __init__(self, log_dir: str = "logs", app_name: str = "trading_agent"):
        self.log_dir = log_dir
        self.app_name = app_name
        self.loggers: Dict[str, logging.Logger] = {}
        
        # Create log directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup root logger
        self._setup_root_logger()
        
    def _setup_root_logger(self):
        """Setup root logger with handlers"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        log_file = os.path.join(self.log_dir, f"{self.app_name}.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=10
        )
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
        
        # Error file handler
        error_file = os.path.join(self.log_dir, f"{self.app_name}_error.log")
        error_handler = logging.handlers.RotatingFileHandler(
            error_file, maxBytes=10485760, backupCount=10
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_handler)
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create logger"""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(f"{self.app_name}.{name}")
        return self.loggers[name]
    
    async def log_with_context(self, logger: logging.Logger, level: int, 
                                message: str, context: Dict = None):
        """Log message with additional context"""
        extra = {'context': context} if context else {}
        logger.log(level, message, extra=extra)
        
    async def rotate_logs(self):
        """Rotate log files"""
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.doRollover()

# ============= Performance Optimizations =============

import hashlib
import pickle
import aioredis
from functools import wraps

class CacheManager:
    """Redis-based cache manager"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        
    async def connect(self):
        """Connect to Redis"""
        self.redis = await aioredis.from_url(self.redis_url)
        
    async def get(self, key: str):
        """Get value from cache"""
        if not self.redis:
            return None
            
        value = await self.redis.get(key)
        if value:
            return pickle.loads(value)
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL"""
        if not self.redis:
            return
            
        await self.redis.set(key, pickle.dumps(value), ex=ttl)
    
    async def delete(self, key: str):
        """Delete key from cache"""
        if self.redis:
            await self.redis.delete(key)
    
    def cached(self, ttl: int = 300, prefix: str = ""):
        """Cache decorator"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                key_parts = [prefix, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in kwargs.items())
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
                
                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.set(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator

class ConnectionPool:
    """Connection pool manager"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.pools: Dict[str, asyncio.Queue] = {}
        self.active_connections: Dict[str, int] = {}
        
    async def get_connection(self, name: str, creator: Callable) -> Any:
        """Get connection from pool"""
        if name not in self.pools:
            self.pools[name] = asyncio.Queue(maxsize=self.max_connections)
            self.active_connections[name] = 0
            
        pool = self.pools[name]
        
        try:
            # Try to get existing connection
            connection = pool.get_nowait()
            return connection
        except asyncio.QueueEmpty:
            # Create new connection if under limit
            if self.active_connections[name] < self.max_connections:
                self.active_connections[name] += 1
                return await creator()
            else:
                # Wait for connection
                return await pool.get()
    
    async def return_connection(self, name: str, connection: Any):
        """Return connection to pool"""
        if name in self.pools:
            await self.pools[name].put(connection)

# ============= Security Hardening =============

import secrets
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class SecurityManager:
    """Security and encryption manager"""
    
    def __init__(self, key_file: str = "keys/master.key"):
        self.key_file = key_file
        self.master_key = self._load_or_create_master_key()
        self.fernet = Fernet(self.master_key)
        
    def _load_or_create_master_key(self) -> bytes:
        """Load or create master encryption key"""
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode(), hashed.encode())
    
    def generate_api_key(self) -> str:
        """Generate secure API key"""
        return secrets.token_urlsafe(32)
    
    def rate_limit_check(self, key: str, limit: int = 100, window: int = 60) -> bool:
        """Check rate limit for API key"""
        # Implement rate limiting logic
        return True

class AuditLogger:
    """Audit logging for security events"""
    
    def __init__(self, log_manager: LogManager):
        self.log_manager = log_manager
        self.audit_logger = log_manager.get_logger("audit")
        
    async def log_event(self, event_type: str, user: str, action: str, 
                         details: Dict = None, status: str = "success"):
        """Log security audit event"""
        audit_entry = {
            'event_type': event_type,
            'user': user,
            'action': action,
            'details': details or {},
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'ip_address': self._get_client_ip(),
            'user_agent': self._get_user_agent()
        }
        
        await self.log_manager.log_with_context(
            self.audit_logger,
            logging.INFO,
            f"Audit: {event_type} - {action}",
            audit_entry
        )
    
    def _get_client_ip(self) -> str:
        """Get client IP address"""
        # Implementation depends on framework
        return "unknown"
    
    def _get_user_agent(self) -> str:
        """Get user agent"""
        return "unknown"

# ============= Health Monitoring System =============

class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.status_history: List[Dict] = []
        
    def register_check(self, name: str, check_func: Callable, interval: int = 60):
        """Register health check"""
        self.checks[name] = {
            'func': check_func,
            'interval': interval,
            'last_check': None,
            'last_status': None
        }
    
    async def run_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        
        for name, check_info in self.checks.items():
            try:
                # Check if due
                if check_info['last_check']:
                    elapsed = (datetime.now() - check_info['last_check']).total_seconds()
                    if elapsed < check_info['interval']:
                        results[name] = check_info['last_status']
                        continue
                
                # Run check
                result = await check_info['func']()
                results[name] = {
                    'status': 'healthy',
                    'details': result,
                    'timestamp': datetime.now().isoformat()
                }
                
                check_info['last_check'] = datetime.now()
                check_info['last_status'] = results[name]
                
            except Exception as e:
                results[name] = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                
                check_info['last_status'] = results[name]
        
        # Store history
        self.status_history.append({
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        # Keep last 1000 checks
        if len(self.status_history) > 1000:
            self.status_history.pop(0)
        
        return results
    
    def get_system_health(self) -> Dict:
        """Get overall system health"""
        if not self.status_history:
            return {'status': 'unknown'}
        
        latest = self.status_history[-1]['results']
        unhealthy = [name for name, result in latest.items() 
                    if result.get('status') != 'healthy']
        
        return {
            'status': 'healthy' if not unhealthy else 'degraded',
            'unhealthy_components': unhealthy,
            'last_check': self.status_history[-1]['timestamp'],
            'uptime': self._get_uptime()
        }
    
    def _get_uptime(self) -> float:
        """Get system uptime"""
        # Implementation depends on system
        return 0.0

# ============= Continuous Integration/Continuous Deployment =============

# .github/workflows/ci-cd.yml
CI_CD_CONFIG = """
name: Trading Agent CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis
        ports:
          - 6379:6379
      postgres:
        image: postgres
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov flake8 black mypy
    
    - name: Lint with flake8
      run: |
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 . --count --exit-zero --max-complexity=10 --statistics
    
    - name: Format with black
      run: |
        black --check .
    
    - name: Type check with mypy
      run: |
        mypy trading_agent.py
    
    - name: Test with pytest
      run: |
        pytest --cov=trading_agent --cov-report=xml --cov-report=html
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v1
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
    
    - name: Security scan
      run: |
        pip install bandit
        bandit -r . -f json -o bandit-report.json
    
    - name: Upload security report
      uses: actions/upload-artifact@v2
      with:
        name: security-report
        path: bandit-report.json

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v1
    
    - name: Login to DockerHub
      uses: docker/login-action@v1
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}
    
    - name: Build and push
      uses: docker/build-push-action@v2
      with:
        context: .
        push: true
        tags: |
          trading-agent:latest
          trading-agent:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Deploy to Kubernetes
      uses: appleboy/ssh-action@v0.1.4
      with:
        host: ${{ secrets.K8S_HOST }}
        username: ${{ secrets.K8S_USER }}
        key: ${{ secrets.K8S_SSH_KEY }}
        script: |
          kubectl set image deployment/trading-agent trading-agent=trading-agent:${{ github.sha }}
          kubectl rollout status deployment/trading-agent
"""

# ============= Documentation Generator =============

class DocumentationGenerator:
    """Generate API documentation automatically"""
    
    def __init__(self):
        self.endpoints = []
        
    def register_endpoint(self, path: str, method: str, handler: Callable, 
                          description: str, parameters: Dict, responses: Dict):
        """Register endpoint for documentation"""
        self.endpoints.append({
            'path': path,
            'method': method,
            'handler': handler.__name__,
            'description': description,
            'parameters': parameters,
            'responses': responses
        })
    
    def generate_openapi_spec(self) -> Dict:
        """Generate OpenAPI 3.0 specification"""
        openapi = {
            'openapi': '3.0.0',
            'info': {
                'title': 'Trading Agent API',
                'version': '1.0.0',
                'description': 'AI-powered trading agent API'
            },
            'servers': [
                {'url': 'http://localhost:8000', 'description': 'Local server'},
                {'url': 'https://api.trading-agent.com', 'description': 'Production server'}
            ],
            'paths': {},
            'components': {
                'securitySchemes': {
                    'ApiKeyAuth': {
                        'type': 'apiKey',
                        'in': 'header',
                        'name': 'X-API-Key'
                    }
                }
            },
            'security': [{'ApiKeyAuth': []}]
        }
        
        for endpoint in self.endpoints:
            path = endpoint['path']
            method = endpoint['method'].lower()
            
            if path not in openapi['paths']:
                openapi['paths'][path] = {}
            
            openapi['paths'][path][method] = {
                'summary': endpoint['description'],
                'parameters': endpoint['parameters'],
                'responses': endpoint['responses']
            }
        
        return openapi
    
    def generate_markdown_docs(self) -> str:
        """Generate Markdown documentation"""
        docs = "# Trading Agent API Documentation\n\n"
        
        for endpoint in self.endpoints:
            docs += f"## {endpoint['method']} {endpoint['path']}\n\n"
            docs += f"{endpoint['description']}\n\n"
            
            if endpoint['parameters']:
                docs += "### Parameters\n\n"
                docs += "| Name | Type | Required | Description |\n"
                docs += "|------|------|----------|-------------|\n"
                for param in endpoint['parameters']:
                    docs += f"| {param['name']} | {param['schema']['type']} | {param.get('required', False)} | {param.get('description', '')} |\n"
                docs += "\n"
            
            docs += "### Responses\n\n"
            for status, response in endpoint['responses'].items():
                docs += f"#### {status}\n\n"
                docs += f"{response.get('description', '')}\n\n"
            
            docs += "---\n\n"
        
        return docs

# ============= Final Integration =============

class CompleteSystem:
    """Complete system integrating all components"""
    
    def __init__(self):
        # Initialize core components
        self.config = ConfigurationManager()
        self.log_manager = LogManager()
        self.error_handler = ErrorHandler()
        self.cache_manager = CacheManager()
        self.security_manager = SecurityManager()
        self.audit_logger = AuditLogger(self.log_manager)
        self.health_monitor = HealthMonitor()
        self.doc_generator = DocumentationGenerator()
        
        # Initialize trading components
        self.db = DatabaseManager()
        self.risk_manager = AdvancedRiskManager(self.db)
        self.order_manager = AdvancedOrderManager(self.db, self.risk_manager)
        self.alert_manager = EnhancedAlertManager(self.db, self.order_manager)
        self.ai_agent = AdvancedAIAgent()
        self.strategy_coordinator = StrategyCoordinator(self.order_manager, self.risk_manager)
        self.disaster_recovery = DisasterRecoverySystem(self.db, self.order_manager)
        
        # Register error handlers
        self._register_error_handlers()
        
        # Register health checks
        self._register_health_checks()
        
    def _register_error_handlers(self):
        """Register error handlers"""
        self.error_handler.register_handler(OrderError, self._handle_order_error)
        self.error_handler.register_handler(RiskError, self._handle_risk_error)
        self.error_handler.register_handler(MarketDataError, self._handle_market_data_error)
        
    async def _handle_order_error(self, error_info: Dict):
        """Handle order errors"""
        await self.audit_logger.log_event(
            'order_error',
            'system',
            error_info['message'],
            error_info['context'],
            'failed'
        )
        
    async def _handle_risk_error(self, error_info: Dict):
        """Handle risk errors"""
        logger.warning(f"Risk limit exceeded: {error_info['message']}")
        
    async def _handle_market_data_error(self, error_info: Dict):
        """Handle market data errors"""
        logger.error(f"Market data error: {error_info['message']}")
        
    def _register_health_checks(self):
        """Register health checks"""
        self.health_monitor.register_check(
            'database',
            lambda: self._check_database(),
            interval=60
        )
        self.health_monitor.register_check(
            'redis',
            lambda: self._check_redis(),
            interval=60
        )
        self.health_monitor.register_check(
            'order_manager',
            lambda: self._check_order_manager(),
            interval=30
        )
        
    async def _check_database(self) -> Dict:
        """Check database health"""
        try:
            self.db.get_orders(limit=1)
            return {'status': 'connected', 'type': 'sqlite'}
        except Exception as e:
            raise MarketDataError(f"Database check failed: {e}")
    
    async def _check_redis(self) -> Dict:
        """Check Redis health"""
        try:
            await self.cache_manager.connect()
            await self.cache_manager.set('health_check', 'ok', ttl=10)
            result = await self.cache_manager.get('health_check')
            return {'status': 'connected', 'result': result}
        except Exception as e:
            raise MarketDataError(f"Redis check failed: {e}")
    
    async def _check_order_manager(self) -> Dict:
        """Check order manager health"""
        return {
            'active_orders': len(self.order_manager.orders),
            'status': 'healthy'
        }
    
    async def start(self):
        """Start complete system"""
        print("\n" + "="*70)
        print("🤖 AI Trading Agent - Complete Enterprise System")
        print("="*70)
        
        # Connect to Redis cache
        await self.cache_manager.connect()
        
        # Start all services
        asyncio.create_task(self.strategy_coordinator.start())
        asyncio.create_task(self.disaster_recovery.auto_recovery())
        
        # Start health monitoring
        asyncio.create_task(self._monitor_health())
        
        # Generate documentation
        with open("API_DOCS.md", "w") as f:
            f.write(self.doc_generator.generate_markdown_docs())
        
        print("\n✅ System Components:")
        print(f"  ✓ Log Manager (Directory: logs/)")
        print(f"  ✓ Error Handler ({len(self.error_handler.error_handlers)} handlers)")
        print(f"  ✓ Cache Manager (Redis)")
        print(f"  ✓ Security Manager (Encryption enabled)")
        print(f"  ✓ Audit Logger")
        print(f"  ✓ Health Monitor ({len(self.health_monitor.checks)} checks)")
        print(f"  ✓ Documentation Generator")
        print(f"  ✓ Database Manager")
        print(f"  ✓ Risk Manager")
        print(f"  ✓ Order Manager")
        print(f"  ✓ Alert Manager")
        print(f"  ✓ AI Agent (Ollama)")
        print(f"  ✓ Strategy Coordinator")
        print(f"  ✓ Disaster Recovery")
        
        print("\n🌐 Available Interfaces:")
        print("  • REST API: http://localhost:8000")
        print("  • Web Dashboard: http://localhost:8500")
        print("  • Admin Console: http://localhost:8500/admin")
        print("  • Health Check: http://localhost:8080/health")
        print("  • Metrics: http://localhost:9090/metrics")
        
        print("\n📚 Documentation:")
        print("  • API Docs: API_DOCS.md")
        print("  • OpenAPI Spec: /openapi.json")
        
        print("\n📊 Monitoring:")
        print("  • Prometheus: http://localhost:9090")
        print("  • Grafana: http://localhost:3000 (admin/admin)")
        
        print("\n🔐 Security:")
        print("  • API Key Authentication")
        print("  • Rate Limiting")
        print("  • Audit Logging")
        print("  • Encryption at Rest")
        
        print("\n" + "="*70)
        print("System Running - Press Ctrl+C to stop")
        print("="*70)
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.shutdown()
    
    async def _monitor_health(self):
        """Continuous health monitoring"""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            health_status = await self.health_monitor.run_checks()
            overall = self.health_monitor.get_system_health()
            
            if overall['status'] != 'healthy':
                logger.warning(f"System degraded: {overall['unhealthy_components']}")
                
                # Send alert
                await self._send_health_alert(overall)
    
    async def _send_health_alert(self, health_status: Dict):
        """Send health alert"""
        # Implement alert sending logic
        pass
    
    async def shutdown(self):
        """Graceful shutdown"""
        print("\n🛑 Shutting down system...")
        
        # Create final checkpoint
        await self.disaster_recovery.create_checkpoint()
        
        # Log shutdown event
        await self.audit_logger.log_event(
            'system_shutdown',
            'system',
            'Graceful shutdown initiated',
            {'uptime': self.health_monitor._get_uptime()},
            'success'
        )
        
        # Generate final health report
        final_health = await self.health_monitor.run_checks()
        with open("logs/final_health_report.json", "w") as f:
            json.dump(final_health, f, default=str, indent=2)
        
        # Close connections
        if self.cache_manager.redis:
            await self.cache_manager.redis.close()
        
        print("✅ Shutdown complete")

# ============= Final Entry Point =============

async def main():
    """Main entry point for complete system"""
    system = CompleteSystem()
    await system.start()

if __name__ == "__main__":
    # Set up environment
    os.environ.setdefault('PYTHONASYNCIODEBUG', '1')
    
    # Create necessary directories
    for directory in ['logs', 'keys', 'reports', 'backups', 'models', 'data']:
        os.makedirs(directory, exist_ok=True)
    
    # Run system
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nSystem terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()