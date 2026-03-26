# advanced_trading_agent.py - Additional advanced features
import asyncio
import json
import signal
import sys
from typing import Optional, Callable
from decimal import Decimal, ROUND_DOWN
import time
from collections import deque
import statistics

# ============= Advanced Order Types =============

class AdvancedOrderManager(OrderManager):
    """Extended order manager with advanced order types"""
    
    async def place_trailing_stop_order(self, symbol: str, side: str, 
                                        quantity: float, trail_amount: float) -> Dict[str, Any]:
        """Place a trailing stop order"""
        current_price = await self.market_data.get_current_price(symbol)
        
        if side == 'sell':
            stop_price = current_price - trail_amount
        else:
            stop_price = current_price + trail_amount
            
        order = Order(
            symbol=symbol,
            side=side,
            order_type='trailing_stop',
            quantity=quantity,
            stop_price=stop_price,
            price=None
        )
        
        order.trail_amount = trail_amount
        order.highest_price = current_price
        order.lowest_price = current_price
        
        return await self.place_order(order)
    
    async def place_bracket_order(self, symbol: str, side: str, quantity: float,
                                   entry_price: float, stop_loss: float, 
                                   take_profit: float) -> Dict[str, Any]:
        """Place a bracket order (entry with attached stop loss and take profit)"""
        # Place entry order
        entry_order = Order(
            symbol=symbol,
            side=side,
            order_type='limit',
            quantity=quantity,
            price=entry_price
        )
        
        result = await self.place_order(entry_order)
        
        if result['success']:
            # Create stop loss order
            stop_side = 'sell' if side == 'buy' else 'buy'
            stop_order = Order(
                symbol=symbol,
                side=stop_side,
                order_type='stop',
                quantity=quantity,
                stop_price=stop_loss
            )
            
            # Create take profit order
            tp_order = Order(
                symbol=symbol,
                side=stop_side,
                order_type='limit',
                quantity=quantity,
                price=take_profit
            )
            
            # Store bracket orders for monitoring
            self.bracket_orders[entry_order.order_id] = {
                'stop': stop_order,
                'take_profit': tp_order,
                'parent_order': entry_order
            }
            
            result['bracket_orders'] = {
                'stop_loss': stop_order,
                'take_profit': tp_order
            }
        
        return result
    
    async def _monitor_trailing_stop(self, order: Order):
        """Monitor and adjust trailing stop"""
        while order.status == 'pending':
            current_price = await self.market_data.get_current_price(order.symbol)
            
            if order.side == 'sell':
                # Update highest price for sell trailing stop
                if current_price > order.highest_price:
                    order.highest_price = current_price
                    # Adjust stop price upward
                    new_stop = order.highest_price - order.trail_amount
                    if new_stop > order.stop_price:
                        order.stop_price = new_stop
                        logger.info(f"Trailing stop adjusted to {order.stop_price}")
            else:
                # Update lowest price for buy trailing stop
                if current_price < order.lowest_price:
                    order.lowest_price = current_price
                    # Adjust stop price downward
                    new_stop = order.lowest_price + order.trail_amount
                    if new_stop < order.stop_price:
                        order.stop_price = new_stop
                        logger.info(f"Trailing stop adjusted to {order.stop_price}")
            
            # Check if stop triggered
            if (order.side == 'sell' and current_price <= order.stop_price) or \
               (order.side == 'buy' and current_price >= order.stop_price):
                await self._execute_market_order(order, current_price)
                break
            
            await asyncio.sleep(1)

# ============= Advanced Risk Manager =============

class AdvancedRiskManager(RiskManager):
    """Enhanced risk management with advanced metrics"""
    
    def __init__(self, db: DatabaseManager, profile: RiskProfile = None):
        super().__init__(db, profile)
        self.var_confidence = 0.95  # Value at Risk confidence level
        self.correlation_matrix = {}
        self.portfolio_values = deque(maxlen=1000)
        
    async def calculate_var(self, positions: List[Position]) -> float:
        """Calculate Value at Risk (VaR)"""
        if not positions:
            return 0.0
            
        # Get historical returns for positions
        returns = []
        for position in positions:
            historical_data = await self.market_data.get_historical_data(
                position.symbol, period='1mo'
            )
            position_returns = historical_data['price'].pct_change().dropna()
            returns.append(position_returns * position.quantity)
        
        if returns:
            # Calculate portfolio returns
            portfolio_returns = sum(returns)
            var = np.percentile(portfolio_returns, (1 - self.var_confidence) * 100)
            return abs(var) * self.portfolio_values[-1] if self.portfolio_values else 0
        
        return 0.0
    
    async def calculate_sharpe_ratio(self, period_days: int = 30) -> float:
        """Calculate Sharpe ratio for the portfolio"""
        if len(self.daily_trades) < period_days:
            return 0.0
            
        recent_trades = self.daily_trades[-period_days:]
        returns = [t['pnl'] for t in recent_trades]
        
        if not returns:
            return 0.0
            
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 1
        
        if std_return == 0:
            return 0.0
            
        risk_free_rate = 0.02  # Assume 2% risk-free rate
        sharpe = (avg_return - risk_free_rate / 365) / std_return
        
        return sharpe
    
    async def validate_order_advanced(self, order: Order, current_price: float) -> tuple[bool, str]:
        """Advanced order validation with more risk checks"""
        
        # Basic validation
        is_valid, message = await self.validate_order(order, current_price)
        if not is_valid:
            return False, message
        
        # Get current positions
        positions = self.db.get_positions()
        
        # Check concentration risk
        if positions:
            position_value = order.quantity * current_price
            total_portfolio = sum(p['quantity'] * p['current_price'] for p in positions) + position_value
            
            concentration = position_value / total_portfolio if total_portfolio > 0 else 1
            if concentration > 0.25:  # Max 25% in any single position
                return False, f"Position concentration {concentration:.2%} exceeds 25% limit"
        
        # Check correlation risk
        if len(positions) > 1:
            for pos in positions:
                if pos['symbol'] != order.symbol:
                    correlation = await self._get_correlation(order.symbol, pos['symbol'])
                    if correlation > 0.8:  # Highly correlated
                        return False, f"High correlation ({correlation:.2f}) with existing position {pos['symbol']}"
        
        # Check VaR
        portfolio_value = sum(p['quantity'] * p['current_price'] for p in positions)
        var = await self.calculate_var(positions + [order])
        if var > portfolio_value * 0.05:  # VaR > 5% of portfolio
            return False, f"VaR {var:.2f} exceeds 5% of portfolio"
        
        return True, "Order validated"
    
    async def _get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate correlation between two symbols"""
        if (symbol1, symbol2) in self.correlation_matrix:
            return self.correlation_matrix[(symbol1, symbol2)]
        
        # Get historical data
        data1 = await self.market_data.get_historical_data(symbol1, period='1mo')
        data2 = await self.market_data.get_historical_data(symbol2, period='1mo')
        
        # Calculate correlation
        merged = pd.merge(data1, data2, left_index=True, right_index=True, suffixes=('_1', '_2'))
        correlation = merged['price_1'].corr(merged['price_2'])
        
        self.correlation_matrix[(symbol1, symbol2)] = correlation
        self.correlation_matrix[(symbol2, symbol1)] = correlation
        
        return correlation

# ============= Performance Monitor =============

class PerformanceMonitor:
    """Monitor and track trading performance"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'peak_portfolio': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0
        }
        self.daily_snapshots = []
        
    async def update_performance(self, trade_result: Dict[str, Any]):
        """Update performance metrics with new trade"""
        pnl = trade_result.get('pnl', 0)
        
        self.metrics['total_trades'] += 1
        self.metrics['total_pnl'] += pnl
        
        if pnl > 0:
            self.metrics['winning_trades'] += 1
            self.metrics['avg_win'] = (self.metrics['avg_win'] * (self.metrics['winning_trades'] - 1) + pnl) / self.metrics['winning_trades']
        else:
            self.metrics['losing_trades'] += 1
            self.metrics['avg_loss'] = (self.metrics['avg_loss'] * (self.metrics['losing_trades'] - 1) + pnl) / self.metrics['losing_trades']
        
        # Calculate win rate
        if self.metrics['total_trades'] > 0:
            self.metrics['win_rate'] = self.metrics['winning_trades'] / self.metrics['total_trades']
        
        # Calculate profit factor
        total_wins = self.metrics['winning_trades'] * self.metrics['avg_win']
        total_losses = abs(self.metrics['losing_trades'] * self.metrics['avg_loss'])
        self.metrics['profit_factor'] = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Update drawdown
        current_portfolio = await self._get_current_portfolio_value()
        if current_portfolio > self.metrics['peak_portfolio']:
            self.metrics['peak_portfolio'] = current_portfolio
        
        drawdown = (self.metrics['peak_portfolio'] - current_portfolio) / self.metrics['peak_portfolio'] if self.metrics['peak_portfolio'] > 0 else 0
        if drawdown > self.metrics['max_drawdown']:
            self.metrics['max_drawdown'] = drawdown
        
        # Save daily snapshot
        self._save_daily_snapshot(current_portfolio)
        
    async def _get_current_portfolio_value(self) -> float:
        """Calculate current portfolio value"""
        positions = self.db.get_positions()
        total = 0
        for pos in positions:
            price = await self.market_data.get_current_price(pos['symbol'])
            total += pos['quantity'] * price
        return total
    
    def _save_daily_snapshot(self, portfolio_value: float):
        """Save daily performance snapshot"""
        today = datetime.now().date()
        self.daily_snapshots.append({
            'date': today,
            'portfolio_value': portfolio_value,
            'metrics': self.metrics.copy(),
            'timestamp': datetime.now()
        })
        
        # Keep only last 365 days
        if len(self.daily_snapshots) > 365:
            self.daily_snapshots.pop(0)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        return {
            'overall': self.metrics,
            'daily_snapshots': self.daily_snapshots[-30:],  # Last 30 days
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'calmar_ratio': self._calculate_calmar_ratio(),
            'recovery_factor': self._calculate_recovery_factor()
        }
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from daily snapshots"""
        if len(self.daily_snapshots) < 2:
            return 0.0
            
        returns = []
        for i in range(1, len(self.daily_snapshots)):
            ret = (self.daily_snapshots[i]['portfolio_value'] - 
                   self.daily_snapshots[i-1]['portfolio_value']) / self.daily_snapshots[i-1]['portfolio_value']
            returns.append(ret)
        
        if not returns:
            return 0.0
            
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return 0.0
            
        risk_free_rate = 0.02 / 365  # Daily risk-free rate
        return (avg_return - risk_free_rate) / std_return * (252 ** 0.5)  # Annualized
    
    def _calculate_calmar_ratio(self) -> float:
        """Calculate Calmar ratio (annualized return / max drawdown)"""
        if self.metrics['max_drawdown'] == 0:
            return 0.0
            
        annualized_return = self.metrics['total_pnl'] / 365  # Simplified
        return annualized_return / self.metrics['max_drawdown']
    
    def _calculate_recovery_factor(self) -> float:
        """Calculate recovery factor (total P&L / max drawdown)"""
        if self.metrics['max_drawdown'] == 0:
            return 0.0
        return self.metrics['total_pnl'] / self.metrics['max_drawdown']

# ============= Enhanced Webhook System =============

class EnhancedWebhookSender(WebhookSender):
    """Webhook sender with retry logic and authentication"""
    
    def __init__(self, max_retries: int = 3, retry_delay: int = 1):
        super().__init__()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    async def send_webhook_with_retry(self, url: str, data: Dict, 
                                       method: str = 'POST', 
                                       headers: Optional[Dict] = None) -> Dict:
        """Send webhook with retry logic"""
        for attempt in range(self.max_retries):
            try:
                result = await self.send_webhook(url, data, method, headers)
                if result:
                    return {'success': True, 'data': result, 'attempts': attempt + 1}
                else:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    else:
                        return {'success': False, 'error': 'Max retries exceeded', 'attempts': attempt + 1}
            except Exception as e:
                logger.error(f"Webhook attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    return {'success': False, 'error': str(e), 'attempts': attempt + 1}
                await asyncio.sleep(self.retry_delay)
        
        return {'success': False, 'error': 'Unknown error'}
    
    async def send_signed_webhook(self, url: str, data: Dict, secret: str) -> Dict:
        """Send webhook with HMAC signature"""
        # Create signature
        payload = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-Signature': signature,
            'Content-Type': 'application/json'
        }
        
        return await self.send_webhook_with_retry(url, data, 'POST', headers)

# ============= Advanced AI Agent =============

class AdvancedAIAgent(AIAgent):
    """Enhanced AI agent with multiple model support and context memory"""
    
    def __init__(self, model_name: str = "llama2", context_window: int = 10):
        super().__init__(model_name)
        self.context_window = context_window
        self.trade_history = deque(maxlen=context_window)
        self.sentiment_history = deque(maxlen=context_window)
        
    async def analyze_with_context(self, symbol: str, 
                                    recent_trades: List[Dict]) -> Dict[str, Any]:
        """Analyze market with recent trade context"""
        # Get market data
        current_price = await self.market_data.get_current_price(symbol)
        historical_data = await self.market_data.get_historical_data(symbol)
        
        # Calculate technical indicators
        sma_20 = historical_data['price'].tail(20).mean()
        sma_50 = historical_data['price'].tail(50).mean()
        rsi = self._calculate_rsi(historical_data['price'])
        
        # Prepare trade context
        trade_context = ""
        if recent_trades:
            recent_pnl = sum(t.get('pnl', 0) for t in recent_trades[-5:])
            win_rate = len([t for t in recent_trades if t.get('pnl', 0) > 0]) / len(recent_trades)
            trade_context = f"""
            Recent Trading Performance:
            - Last 5 trades P&L: ${recent_pnl:.2f}
            - Win Rate: {win_rate:.2%}
            - Total Trades: {len(recent_trades)}
            """
        
        # Enhanced prompt with context
        prompt = f"""
        Analyze market conditions for {symbol}:
        
        Current Price: ${current_price:.2f}
        Technical Indicators:
        - SMA 20: ${sma_20:.2f}
        - SMA 50: ${sma_50:.2f}
        - RSI: {rsi:.2f}
        
        {trade_context}
        
        Provide a comprehensive analysis including:
        1. Market sentiment and momentum
        2. Key support and resistance levels
        3. Recommended action (buy/sell/hold) with confidence level
        4. Risk assessment
        5. Suggested position sizing based on recent performance
        
        Format your response as a structured analysis.
        """
        
        response = ollama.chat(
            model=self.model_name,
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        analysis = response['message']['content']
        
        # Parse sentiment and recommendation
        sentiment = self._parse_sentiment(analysis)
        recommendation = self._parse_recommendation(analysis)
        confidence = self._parse_confidence(analysis)
        
        # Store in history
        self.sentiment_history.append(sentiment)
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'analysis': analysis,
            'sentiment': sentiment,
            'recommendation': recommendation,
            'confidence': confidence,
            'technical_indicators': {
                'sma_20': sma_20,
                'sma_50': sma_50,
                'rsi': rsi
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not rsi.empty else 50
    
    def _parse_sentiment(self, analysis: str) -> str:
        """Parse sentiment from analysis text"""
        analysis_lower = analysis.lower()
        if 'bullish' in analysis_lower:
            return 'bullish'
        elif 'bearish' in analysis_lower:
            return 'bearish'
        return 'neutral'
    
    def _parse_recommendation(self, analysis: str) -> str:
        """Parse recommendation from analysis text"""
        analysis_lower = analysis.lower()
        if 'buy' in analysis_lower:
            return 'buy'
        elif 'sell' in analysis_lower:
            return 'sell'
        return 'hold'
    
    def _parse_confidence(self, analysis: str) -> int:
        """Parse confidence level from analysis text"""
        # Look for percentages in text
        import re
        percentages = re.findall(r'(\d+)%', analysis)
        if percentages:
            return int(percentages[0])
        return 50

# ============= Example Client =============

class TradingAgentClient:
    """Example client demonstrating how to use the trading agent"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.session = None
        
    async def connect(self):
        """Connect to the trading agent"""
        self.session = aiohttp.ClientSession()
        # In a real implementation, you would connect via WebSocket or HTTP
        print("Connected to trading agent")
        
    async def run_demo(self):
        """Run demonstration of trading agent features"""
        print("\n" + "="*60)
        print("Trading Agent Demo")
        print("="*60)
        
        # 1. Get market analysis
        print("\n1. Getting AI Market Analysis...")
        analysis = await self.call_tool("ai_market_analysis", {"symbol": "BTCUSD"})
        print(f"Analysis: {analysis.get('analysis', 'N/A')[:200]}...")
        print(f"Recommendation: {analysis.get('recommendation', 'N/A')}")
        
        # 2. Get trading advice
        print("\n2. Getting AI Trading Advice...")
        advice = await self.call_tool("ai_trading_advice", {"symbol": "BTCUSD"})
        print(f"Suggested Position: {advice.get('suggested_position_size', 'N/A')}")
        print(f"Stop Loss: ${advice.get('suggested_stop_loss', 'N/A')}")
        print(f"Take Profit: ${advice.get('suggested_take_profit', 'N/A')}")
        
        # 3. Place a demo order
        print("\n3. Placing Demo Market Order...")
        order = await self.call_tool("place_market_order", {
            "symbol": "BTCUSD",
            "side": "buy",
            "quantity": 0.01
        })
        print(f"Order Result: {order.get('message', 'N/A')}")
        
        # 4. Create a price alert
        print("\n4. Creating Price Alert...")
        alert = await self.call_tool("create_price_alert", {
            "symbol": "BTCUSD",
            "condition": "above",
            "price": 55000,
            "action": "notify"
        })
        print(f"Alert Created: {alert.get('message', 'N/A')}")
        
        # 5. Check positions
        print("\n5. Current Positions...")
        positions = await self.call_tool("get_positions", {})
        print(f"Active Positions: {len(positions)}")
        
        # 6. Get risk metrics
        print("\n6. Risk Metrics...")
        risk = await self.call_tool("get_risk_metrics", {})
        print(f"Daily P&L: ${risk.get('daily_pnl', 0):.2f}")
        print(f"Risk per trade: {risk.get('risk_per_trade', 0)*100:.1f}%")
        
        print("\n" + "="*60)
        print("Demo completed!")
        
    async def call_tool(self, tool_name: str, params: Dict) -> Dict:
        """Call a tool on the MCP server"""
        # In a real implementation, you would make HTTP requests
        # This is a simplified mock for demonstration
        print(f"  Calling {tool_name}...")
        
        # Simulate async call
        await asyncio.sleep(0.5)
        
        # Return mock response
        return {"success": True, "message": f"Mock response for {tool_name}"}
    
    async def close(self):
        """Close the client connection"""
        if self.session:
            await self.session.close()

# ============= Main Application with Signal Handling =============

class TradingAgentApplication:
    """Main application with graceful shutdown"""
    
    def __init__(self):
        self.components = []
        self.is_running = False
        
    async def initialize(self):
        """Initialize all components"""
        print("Initializing Trading Agent...")
        
        # Initialize components
        self.db = DatabaseManager()
        self.risk_profile = RiskProfile()
        self.risk_manager = AdvancedRiskManager(self.db, self.risk_profile)
        self.order_manager = AdvancedOrderManager(self.db, self.risk_manager)
        self.alert_manager = AlertManager(self.db, self.order_manager)
        self.ai_agent = AdvancedAIAgent()
        self.performance_monitor = PerformanceMonitor(self.db)
        self.webhook_sender = EnhancedWebhookSender()
        
        self.components = [
            self.db, self.risk_manager, self.order_manager,
            self.alert_manager, self.performance_monitor
        ]
        
        print("All components initialized")
        
    async def start(self):
        """Start the trading agent"""
        self.is_running = True
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        
        print("\n" + "="*60)
        print("AI Trading Agent Started Successfully!")
        print("="*60)
        print("\nFeatures Available:")
        print("  ✓ Order Management (Market, Limit, Stop, Stop-Limit, Trailing Stop, Bracket)")
        print("  ✓ Advanced Risk Management (VaR, Correlation, Concentration)")
        print("  ✓ Price Alerts with Automatic Orders")
        print("  ✓ Webhook Notifications with Retry Logic")
        print("  ✓ AI Market Analysis (Ollama Integration)")
        print("  ✓ Performance Monitoring & Reporting")
        print("  ✓ Persistent Storage (SQLite)")
        print("\nServer is running... Press Ctrl+C to stop")
        print("="*60)
        
        # Start background tasks
        await self.start_background_tasks()
        
        # Keep running
        while self.is_running:
            await asyncio.sleep(1)
            
    async def start_background_tasks(self):
        """Start background monitoring tasks"""
        asyncio.create_task(self.monitor_performance())
        asyncio.create_task(self.generate_daily_reports())
        
    async def monitor_performance(self):
        """Monitor performance metrics"""
        while self.is_running:
            await asyncio.sleep(3600)  # Every hour
            
            # Get performance report
            report = self.performance_monitor.get_performance_report()
            
            # Log performance metrics
            logger.info(f"Performance Report - Win Rate: {report['overall']['win_rate']:.2%}, "
                       f"Total P&L: ${report['overall']['total_pnl']:.2f}")
            
            # Send alerts if performance deteriorates
            if report['overall']['max_drawdown'] > 0.15:
                await self.webhook_sender.send_webhook_with_retry(
                    "https://your-webhook-url.com/alert",
                    {
                        'type': 'performance_alert',
                        'message': f'High drawdown detected: {report["overall"]["max_drawdown"]:.2%}',
                        'metrics': report['overall']
                    }
                )
                
    async def generate_daily_reports(self):
        """Generate daily performance reports"""
        while self.is_running:
            # Run at midnight
            now = datetime.now()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            wait_seconds = (midnight - now).total_seconds()
            
            await asyncio.sleep(wait_seconds)
            
            if self.is_running:
                report = self.performance_monitor.get_performance_report()
                
                # Save daily report
                with open(f"reports/daily_report_{now.strftime('%Y%m%d')}.json", 'w') as f:
                    json.dump(report, f, default=str, indent=2)
                
                logger.info(f"Daily report generated for {now.strftime('%Y-%m-%d')}")
    
    async def shutdown(self):
        """Graceful shutdown"""
        print("\n\nShutting down Trading Agent...")
        self.is_running = False
        
        # Save final performance report
        final_report = self.performance_monitor.get_performance_report()
        with open("reports/final_report.json", 'w') as f:
            json.dump(final_report, f, default=str, indent=2)
        
        # Close webhook session
        await self.webhook_sender.close()
        
        print("Trading Agent shutdown complete")
        sys.exit(0)

# ============= Run Application =============

async def main():
    """Main entry point"""
    app = TradingAgentApplication()
    
    try:
        await app.initialize()
        await app.start()
    except KeyboardInterrupt:
        await app.shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await app.shutdown()

if __name__ == "__main__":
    # Create reports directory
    os.makedirs("reports", exist_ok=True)
    
    # Run application
    asyncio.run(main())
    
    