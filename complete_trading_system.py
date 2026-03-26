class CompleteTradingSystem:
  """complete trading system with all features integrated"""
  def __init__(self):
    self.config = ConfigurationManager()
    self.db = DatabaseManager(self.config.get('database.path', 'trading_agent.db'))
    self.risk_profile = RiskProfile()
    self.risk_manager = AdvancedRiskManager(self.db, self.risk_profile)
    self.order_manager = AdvancedOrderManager(self.db, self.risk_manager)
    self.market_data = MarketDataProvider()
    self.ai_agent = AdvancedAIAgent()
    self.sentiment_analyzer = SentimentAnalyzer()
    self.portfolio_optimizer = PortfolioOptimizer(self.market_data)
    self.risk_monitor = RealTimeRiskMonitor(self.risk_manager)
    self.automated_strategies = AutomatedStrategies(self.order_manager, self.ai_agent)
    self.performance_analytics = PerformanceAnalytics(self.db)
    self.web_interface = WebAdminInterface(self, port=8500)
    self.metrics_collector = MetricsCollector()
    
  async def start(self):
    """Start all components"""
    print("="*60)
    print("🚀 Complete Trading System v2.0")
    print("="*60)
    
    # Start background tasks
    asyncio.create_task(self.risk_monitor.start_monitoring())
    asyncio.create_task(self.web_interface.start())
    asyncio.create_task(self.background_strategy_execution())
    
    # Print system info
    await self.print_system_info()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await self.shutdown()

  async def background_strategy_execution(self):
    """Execute automated strategies in background"""
    symbols = ['BTCUSD', 'ETHUSD', 'AAPL', 'GOOGL']
    
    while True:
        try:
            for symbol in symbols:
                # Run momentum strategy
                momentum_result = await self.automated_strategies.momentum_strategy(symbol)
                
                # Run mean reversion strategy
                mean_reversion_result = await self.automated_strategies.mean_reversion_strategy(symbol)
                
                # Log results
                if momentum_result.get('action') != 'hold':
                    logger.info(f"Momentum strategy: {momentum_result}")
                
                if mean_reversion_result.get('action') != 'hold':
                    logger.info(f"Mean reversion strategy: {mean_reversion_result}")
            
            await asyncio.sleep(300)  # Run every 5 minutes
            
        except Exception as e:
            logger.error(f"Error in background strategy execution: {e}")
            await asyncio.sleep(60)

  async def print_system_info(self):
    """Print system information"""
    print("\n📊 System Information:")
    print(f"  Database: {self.config.get('database.path')}")
    print(f"  Risk Profile: Max Position ${self.risk_profile.max_position_size:,.0f}")
    print(f"  AI Model: {self.config.get('ai.model')}")
    print(f"  Active Strategies: Momentum, Mean Reversion")
    print(f"\n🌐 Web Interface: http://localhost:8500")
    print(f"📈 API Documentation: http://localhost:8500/docs")
    print(f"📊 Metrics: http://localhost:9090/metrics")
    print(f"❤️ Health Check: http://localhost:8080/health")
    print("\n✅ System ready!")

  async def shutdown(self):
    """Graceful shutdown"""
    print("\n🛑 Shutting down...")
    self.risk_monitor.monitoring_active = False
    await self.web_interface.app.shutdown()
    print("✅ Shutdown complete")
    
    
#  ============= Main Entry Point =============

async def main():
  """Main entry point"""
  system = CompleteTradingSystem()
  await system.start()

  if name == "main":
  # Setup logging
  logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  handlers=[
  logging.FileHandler('trading_system.log'),
  logging.StreamHandler()
  ]
  )

# Run system
asyncio.run(main())

