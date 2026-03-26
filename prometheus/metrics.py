# prometheus/metrics.py
from prometheus_client import Counter, Gauge, Histogram, generate_latest
import prometheus_client

class MetricsCollector:
    """Prometheus metrics collector"""
    
    def __init__(self):
        # Define metrics
        self.orders_total = Counter('trading_orders_total', 'Total orders placed', 
                                     ['symbol', 'side', 'status'])
        self.trades_total = Counter('trading_trades_total', 'Total trades executed',
                                     ['symbol', 'side'])
        self.pnl_gauge = Gauge('trading_pnl', 'Current P&L', ['symbol'])
        self.position_gauge = Gauge('trading_position_size', 'Current position size', 
                                     ['symbol'])
        self.order_duration = Histogram('trading_order_duration_seconds', 
                                         'Order execution duration')
        self.risk_exposure = Gauge('trading_risk_exposure', 'Current risk exposure')
        
    def record_order(self, symbol: str, side: str, status: str):
        """Record order metric"""
        self.orders_total.labels(symbol=symbol, side=side, status=status).inc()
        
    def record_trade(self, symbol: str, side: str, pnl: float):
        """Record trade metric"""
        self.trades_total.labels(symbol=symbol, side=side).inc()
        self.pnl_gauge.labels(symbol=symbol).set(pnl)
        
    def update_position(self, symbol: str, quantity: float, price: float):
        """Update position metric"""
        value = quantity * price
        self.position_gauge.labels(symbol=symbol).set(value)
        
    def update_risk(self, exposure: float):
        """Update risk metric"""
        self.risk_exposure.set(exposure)
        
    def get_metrics(self):
        """Get Prometheus metrics"""
        return generate_latest()

# ============= Configuration Manager =============

class ConfigurationManager:
    """Dynamic configuration management"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.watchers = []
        
    def load_config(self) -> Dict:
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            'risk_management': {
                'max_position_size': 100000,
                'max_daily_loss': 10000,
                'risk_per_trade': 0.02,
                'stop_loss_default': 0.02,
                'take_profit_default': 0.04
            },
            'trading': {
                'default_order_type': 'market',
                'default_time_in_force': 'GTC',
                'min_volume_threshold': 1000
            },
            'alerts': {
                'default_check_interval': 5,
                'webhook_timeout': 10,
                'max_alerts_per_symbol': 10
            },
            'ai': {
                'model': 'llama2',
                'analysis_interval': 3600,
                'confidence_threshold': 70
            },
            'monitoring': {
                'performance_report_interval': 86400,
                'health_check_interval': 60,
                'metrics_port': 9090
            }
        }
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
        
        # Notify watchers
        for watcher in self.watchers:
            watcher(key, value)
    
    def watch(self, callback: Callable):
        """Watch for configuration changes"""
        self.watchers.append(callback)

# ============= Health Check Server =============

class HealthCheckServer:
    """Health check endpoint for monitoring"""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.components = {}
        self.start_time = datetime.now()
        
    def register_component(self, name: str, check_function: Callable):
        """Register component health check"""
        self.components[name] = check_function
    
    async def start(self):
        """Start health check server"""
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get('/health', self.health_check)
        app.router.add_get('/ready', self.readiness_check)
        app.router.add_get('/metrics', self.metrics_endpoint)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        
        print(f"Health check server running on port {self.port}")
    
    async def health_check(self, request):
        """Health check endpoint"""
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'uptime': (datetime.now() - self.start_time).total_seconds(),
            'components': {}
        }
        
        overall_healthy = True
        
        for name, check_func in self.components.items():
            try:
                result = await check_func()
                status['components'][name] = {'status': 'healthy', 'details': result}
            except Exception as e:
                status['components'][name] = {'status': 'unhealthy', 'error': str(e)}
                overall_healthy = False
        
        if not overall_healthy:
            status['status'] = 'unhealthy'
            
        return web.json_response(status, status=200 if overall_healthy else 503)
    
    async def readiness_check(self, request):
        """Readiness check endpoint"""
        # Check if agent is ready to accept orders
        is_ready = True
        # Add your readiness logic here
        
        return web.json_response({
            'ready': is_ready,
            'timestamp': datetime.now().isoformat()
        }, status=200 if is_ready else 503)
    
    async def metrics_endpoint(self, request):
        """Prometheus metrics endpoint"""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        
        metrics = generate_latest()
        return web.Response(body=metrics, content_type=CONTENT_TYPE_LATEST)

# ============= Main Application with All Features =============

class CompleteTradingAgent(TradingAgentApplication):
    """Complete trading agent with all features"""
    
    async def initialize(self):
        """Initialize all components"""
        await super().initialize()
        
        # Initialize additional components
        self.config_manager = ConfigurationManager()
        self.dashboard = RealtimeDashboard()
        self.portfolio_manager = MultiAssetPortfolioManager(self.db)
        self.enhanced_alert_manager = EnhancedAlertManager(self.db, self.order_manager)
        self.metrics_collector = MetricsCollector()
        self.health_check = HealthCheckServer()
        
        # Register health checks
        self.health_check.register_component('database', self.check_database)
        self.health_check.register_component('order_manager', self.check_order_manager)
        self.health_check.register_component('risk_manager', self.check_risk_manager)
        
        # Start background tasks
        asyncio.create_task(self.dashboard.start())
        asyncio.create_task(self.health_check.start())
        
        print("All components initialized with advanced features")
    
    async def check_database(self):
        """Check database health"""
        try:
            self.db.get_orders(limit=1)
            return {'connected': True}
        except Exception as e:
            raise Exception(f"Database error: {e}")
    
    async def check_order_manager(self):
        """Check order manager health"""
        return {
            'pending_orders': len(self.order_manager.orders),
            'active': True
        }
    
    async def check_risk_manager(self):
        """Check risk manager health"""
        return {
            'daily_pnl': self.risk_manager.daily_pnl,
            'active_trades': len(self.risk_manager.daily_trades)
        }

# ============= Run Complete Application =============

if __name__ == "__main__":
    # Create required directories
    os.makedirs("reports", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    
    # Run application
    app = CompleteTradingAgent()
    
    try:
        asyncio.run(app.initialize())
        asyncio.run(app.start())
    except KeyboardInterrupt:
        asyncio.run(app.shutdown())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        asyncio.run(app.shutdown())
        