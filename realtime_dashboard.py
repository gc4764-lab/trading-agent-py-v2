# realtime_dashboard.py - WebSocket-based real-time dashboard
import asyncio
import json
import websockets
from typing import Dict, Any, Set
from datetime import datetime
import aiohttp
from dataclasses import dataclass, asdict
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@dataclass
class DashboardUpdate:
    """Dashboard update data"""
    timestamp: datetime
    update_type: str  # 'price', 'order', 'position', 'alert', 'performance'
    data: Dict[str, Any]

class RealtimeDashboard:
    """Real-time WebSocket dashboard for monitoring"""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.update_queue = asyncio.Queue()
        self.market_data = MarketDataProvider()
        
    async def start(self):
        """Start WebSocket server"""
        async with websockets.serve(self.handle_client, "localhost", self.port):
            print(f"Dashboard WebSocket server running on ws://localhost:{self.port}")
            await self.broadcast_updates()
    
    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle WebSocket client connection"""
        self.connected_clients.add(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.handle_client_message(data, websocket)
        finally:
            self.connected_clients.remove(websocket)
    
    async def handle_client_message(self, data: Dict, websocket):
        """Handle messages from client"""
        command = data.get('command')
        
        if command == 'subscribe':
            channels = data.get('channels', [])
            # Store subscription preferences per client
            websocket.subscriptions = channels
            await websocket.send(json.dumps({
                'status': 'subscribed',
                'channels': channels
            }))
    
    async def broadcast_updates(self):
        """Broadcast updates to connected clients"""
        while True:
            update = await self.update_queue.get()
            
            for client in self.connected_clients.copy():
                try:
                    # Check if client is subscribed to this update type
                    if hasattr(client, 'subscriptions'):
                        if update.update_type in client.subscriptions or 'all' in client.subscriptions:
                            await client.send(json.dumps(asdict(update), default=str))
                except websockets.exceptions.ConnectionClosed:
                    self.connected_clients.remove(client)
    
    async def send_update(self, update: DashboardUpdate):
        """Send update to queue"""
        await self.update_queue.put(update)
    
    async def generate_html_dashboard(self) -> str:
        """Generate HTML dashboard with real-time charts"""
        # Create sample dashboard
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=('Price Chart', 'Order Book', 'Performance', 'Risk Metrics', 'Positions', 'Alerts'),
            specs=[[{'type': 'scatter'}, {'type': 'bar'}],
                   [{'type': 'indicator'}, {'type': 'table'}],
                   [{'type': 'bar'}, {'type': 'scatter'}]]
        )
        
        # Add price chart
        fig.add_trace(
            go.Scatter(x=[], y=[], mode='lines', name='Price'),
            row=1, col=1
        )
        
        # Add order book
        fig.add_trace(
            go.Bar(x=[], y=[], name='Bids'),
            row=1, col=2
        )
        
        # Add performance indicator
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=0,
                title={'text': "Win Rate"},
                domain={'row': 0, 'column': 1}
            ),
            row=2, col=1
        )
        
        # Convert to HTML
        html = fig.to_html(include_plotlyjs='cdn', full_html=False)
        
        # Add WebSocket JavaScript for real-time updates
        ws_script = """
        <script>
            const ws = new WebSocket('ws://localhost:8765');
            
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    command: 'subscribe',
                    channels: ['price', 'order', 'position', 'performance']
                }));
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
            
            function updateDashboard(data) {
                console.log('Update received:', data);
                // Update charts dynamically
            }
        </script>
        """
        
        return html + ws_script

# ============= Real Market Data Providers =============

class BinanceDataProvider(MarketDataProvider):
    """Binance cryptocurrency data provider"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.binance.com"
        self.session = None
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current price from Binance"""
        session = await self.get_session()
        
        # Format symbol (e.g., BTCUSDT)
        symbol_formatted = symbol.replace('USD', 'USDT')
        
        async with session.get(f"{self.base_url}/api/v3/ticker/price", 
                               params={'symbol': symbol_formatted}) as response:
            data = await response.json()
            return float(data['price'])
    
    async def get_historical_data(self, symbol: str, period: str = '1d') -> pd.DataFrame:
        """Get historical klines from Binance"""
        session = await self.get_session()
        symbol_formatted = symbol.replace('USD', 'USDT')
        
        # Map period to Binance interval
        interval_map = {
            '1m': '1m', '5m': '5m', '1h': '1h', '4h': '4h',
            '1d': '1d', '1w': '1w'
        }
        interval = interval_map.get(period, '1d')
        
        # Calculate limit based on period
        limit_map = {'1d': 100, '1w': 52, '1m': 30}
        limit = limit_map.get(period, 100)
        
        async with session.get(f"{self.base_url}/api/v3/klines",
                               params={
                                   'symbol': symbol_formatted,
                                   'interval': interval,
                                   'limit': limit
                               }) as response:
            data = await response.json()
            
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df['close'] = df['close'].astype(float)
            
            return df[['close']]
    
    async def place_order_via_api(self, order: Order) -> Dict:
        """Place order directly on Binance (requires API keys)"""
        if not self.api_key or not self.api_secret:
            raise Exception("API keys required for live trading")
        
        session = await self.get_session()
        symbol_formatted = order.symbol.replace('USD', 'USDT')
        
        # Map order type
        type_map = {
            'market': 'MARKET',
            'limit': 'LIMIT',
            'stop': 'STOP_LOSS',
            'stop_limit': 'STOP_LOSS_LIMIT'
        }
        
        params = {
            'symbol': symbol_formatted,
            'side': order.side.upper(),
            'type': type_map.get(order.order_type, 'MARKET'),
            'quantity': order.quantity,
            'timestamp': int(datetime.now().timestamp() * 1000)
        }
        
        if order.price:
            params['price'] = order.price
        if order.stop_price:
            params['stopPrice'] = order.stop_price
        
        # Add signature
        import hmac
        import hashlib
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        
        headers = {'X-MBX-APIKEY': self.api_key}
        
        async with session.post(f"{self.base_url}/api/v3/order",
                                params=params, headers=headers) as response:
            return await response.json()

class AlpacaDataProvider(MarketDataProvider):
    """Alpaca stock market data provider"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://paper-api.alpaca.markets"
        self.session = None
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current price from Alpaca"""
        session = await self.get_session()
        headers = {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.api_secret
        }
        
        async with session.get(f"{self.base_url}/v2/stocks/{symbol}/trades/latest",
                               headers=headers) as response:
            data = await response.json()
            return float(data['trade']['p'])
    
    async def get_historical_data(self, symbol: str, period: str = '1d') -> pd.DataFrame:
        """Get historical bars from Alpaca"""
        session = await self.get_session()
        headers = {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.api_secret
        }
        
        # Map period to timeframe
        timeframe_map = {
            '1m': '1Min', '5m': '5Min', '1h': '1Hour',
            '1d': '1Day', '1w': '1Week'
        }
        timeframe = timeframe_map.get(period, '1Day')
        
        async with session.get(f"{self.base_url}/v2/stocks/{symbol}/bars",
                               params={'timeframe': timeframe, 'limit': 100},
                               headers=headers) as response:
            data = await response.json()
            
            df = pd.DataFrame(data['bars'])
            df['timestamp'] = pd.to_datetime(df['t'])
            df.set_index('timestamp', inplace=True)
            
            return df[['c']].rename(columns={'c': 'close'})

# ============= Multi-Asset Portfolio Manager =============

class MultiAssetPortfolioManager:
    """Manage portfolio across multiple asset classes"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.asset_allocation = {}
        self.rebalancing_threshold = 0.05  # 5% rebalancing threshold
        
    async def add_asset_class(self, asset_class: str, target_allocation: float):
        """Add asset class with target allocation"""
        self.asset_allocation[asset_class] = {
            'target': target_allocation,
            'current': 0.0,
            'symbols': []
        }
        
    async def add_symbol_to_class(self, asset_class: str, symbol: str, weight: float = 1.0):
        """Add symbol to asset class with weight"""
        if asset_class in self.asset_allocation:
            self.asset_allocation[asset_class]['symbols'].append({
                'symbol': symbol,
                'weight': weight
            })
    
    async def calculate_current_allocation(self) -> Dict[str, float]:
        """Calculate current portfolio allocation"""
        positions = self.db.get_positions()
        total_value = 0
        class_values = {cls: 0 for cls in self.asset_allocation.keys()}
        
        for pos in positions:
            # Determine asset class for position
            asset_class = await self._get_asset_class(pos['symbol'])
            if asset_class:
                price = await self.market_data.get_current_price(pos['symbol'])
                value = pos['quantity'] * price
                class_values[asset_class] += value
                total_value += value
        
        # Calculate percentages
        allocations = {}
        for cls, value in class_values.items():
            allocations[cls] = value / total_value if total_value > 0 else 0
            
        return allocations
    
    async def check_rebalancing_needed(self) -> bool:
        """Check if portfolio needs rebalancing"""
        current = await self.calculate_current_allocation()
        
        for asset_class, target_data in self.asset_allocation.items():
            target = target_data['target']
            current_allocation = current.get(asset_class, 0)
            
            if abs(current_allocation - target) > self.rebalancing_threshold:
                return True
                
        return False
    
    async def rebalance_portfolio(self) -> List[Dict]:
        """Rebalance portfolio to target allocations"""
        if not await self.check_rebalancing_needed():
            return []
        
        current = await self.calculate_current_allocation()
        total_value = sum(current.values())
        orders = []
        
        for asset_class, target_data in self.asset_allocation.items():
            target_value = target_data['target'] * total_value
            current_value = current.get(asset_class, 0) * total_value
            delta = target_value - current_value
            
            if abs(delta) > 100:  # Minimum trade size
                # Determine which symbol to trade
                symbols = target_data['symbols']
                if symbols:
                    symbol_data = symbols[0]  # Use first symbol for simplicity
                    symbol = symbol_data['symbol']
                    price = await self.market_data.get_current_price(symbol)
                    quantity = abs(delta) / price
                    
                    side = 'buy' if delta > 0 else 'sell'
                    
                    order = Order(
                        symbol=symbol,
                        side=side,
                        order_type='market',
                        quantity=quantity
                    )
                    orders.append(order)
        
        return orders
    
    async def _get_asset_class(self, symbol: str) -> Optional[str]:
        """Determine asset class for symbol"""
        # Simple classification based on symbol
        crypto_symbols = ['BTC', 'ETH', 'SOL', 'ADA']
        stock_symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']
        
        if symbol in crypto_symbols:
            return 'crypto'
        elif symbol in stock_symbols:
            return 'stocks'
        else:
            return None

# ============= Enhanced Alert System =============

class EnhancedAlertManager(AlertManager):
    """Alert manager with advanced conditions"""
    
    def __init__(self, db: DatabaseManager, order_manager: OrderManager):
        super().__init__(db, order_manager)
        
    async def create_technical_alert(self, symbol: str, indicator: str, 
                                      condition: str, value: float,
                                      action: str = 'notify') -> Dict:
        """Create alert based on technical indicators"""
        alert = Alert(
            alert_id=None,
            symbol=symbol,
            condition_type=f'indicator_{indicator}',
            condition_value=value,
            action=action
        )
        
        # Store additional condition info
        alert.indicator = indicator
        alert.indicator_condition = condition
        
        return await self.create_alert(alert)
    
    async def create_volume_alert(self, symbol: str, condition: str, 
                                   volume_threshold: float) -> Dict:
        """Create alert based on volume spike"""
        alert = Alert(
            alert_id=None,
            symbol=symbol,
            condition_type='volume_spike',
            condition_value=volume_threshold,
            action='notify'
        )
        
        return await self.create_alert(alert)
    
    async def _monitor_technical_alert(self, alert: Alert):
        """Monitor technical indicator alerts"""
        indicators = TechnicalIndicators()
        
        while alert.is_active:
            try:
                # Get historical data
                historical_data = await self.market_data.get_historical_data(alert.symbol, '1h')
                current_price = historical_data['close'].iloc[-1]
                
                if alert.condition_type == 'indicator_rsi':
                    rsi = indicators.calculate_rsi(historical_data['close']).iloc[-1]
                    
                    if alert.indicator_condition == 'above' and rsi > alert.condition_value:
                        await self._trigger_alert(alert, current_price)
                    elif alert.indicator_condition == 'below' and rsi < alert.condition_value:
                        await self._trigger_alert(alert, current_price)
                        
                elif alert.condition_type == 'indicator_macd':
                    macd_data = indicators.calculate_macd(historical_data['close'])
                    macd_line = macd_data['macd'].iloc[-1]
                    signal_line = macd_data['signal'].iloc[-1]
                    
                    if alert.indicator_condition == 'cross_above' and macd_line > signal_line:
                        await self._trigger_alert(alert, current_price)
                    elif alert.indicator_condition == 'cross_below' and macd_line < signal_line:
                        await self._trigger_alert(alert, current_price)
                
                elif alert.condition_type == 'volume_spike':
                    volume = historical_data['volume'].iloc[-1] if 'volume' in historical_data else 0
                    avg_volume = historical_data['volume'].tail(20).mean() if 'volume' in historical_data else 0
                    
                    if volume > avg_volume * alert.condition_value:
                        await self._trigger_alert(alert, current_price)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring technical alert: {e}")
                await asyncio.sleep(60)

# ============= Testing Framework =============

import unittest
from unittest.mock import Mock, patch

class TestTradingAgent(unittest.TestCase):
    """Unit tests for trading agent"""
    
    def setUp(self):
        """Set up test environment"""
        self.db = DatabaseManager(':memory:')
        self.risk_profile = RiskProfile()
        self.risk_manager = RiskManager(self.db, self.risk_profile)
        self.order_manager = OrderManager(self.db, self.risk_manager)
        
    def test_order_creation(self):
        """Test order creation"""
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=0.1
        )
        
        self.assertEqual(order.symbol, 'BTCUSD')
        self.assertEqual(order.side, 'buy')
        self.assertEqual(order.quantity, 0.1)
        
    def test_risk_validation(self):
        """Test risk validation logic"""
        async def test():
            order = Order(
                symbol='BTCUSD',
                side='buy',
                order_type='market',
                quantity=1000  # Large quantity
            )
            
            is_valid, message = await self.risk_manager.validate_order(order, 50000)
            self.assertFalse(is_valid)
            self.assertIn("exceeds maximum", message)
            
        asyncio.run(test())
        
    def test_position_calculation(self):
        """Test position calculation"""
        position = Position(
            symbol='BTCUSD',
            quantity=1.0,
            avg_price=50000,
            current_price=51000,
            unrealized_pnl=1000
        )
        
        self.assertEqual(position.unrealized_pnl, 1000)
        
    def test_alert_creation(self):
        """Test alert creation"""
        alert = Alert(
            alert_id=None,
            symbol='BTCUSD',
            condition_type='price_above',
            condition_value=55000,
            action='notify'
        )
        
        self.assertIsNotNone(alert.alert_id)
        self.assertEqual(alert.symbol, 'BTCUSD')
        
    @patch('ollama.chat')
    def test_ai_analysis(self, mock_chat):
        """Test AI analysis with mocked Ollama"""
        mock_chat.return_value = {
            'message': {
                'content': 'Bullish outlook with strong momentum. Recommended action: buy.'
            }
        }
        
        async def test():
            agent = AIAgent()
            result = await agent.analyze_market('BTCUSD')
            self.assertIn('bullish', result['sentiment'].lower())
            
        asyncio.run(test())

class IntegrationTest(unittest.TestCase):
    """Integration tests"""
    
    async def test_end_to_end_workflow(self):
        """Test complete trading workflow"""
        # Initialize components
        db = DatabaseManager(':memory:')
        risk_profile = RiskProfile()
        risk_manager = RiskManager(db, risk_profile)
        order_manager = OrderManager(db, risk_manager)
        alert_manager = AlertManager(db, order_manager)
        
        # Place order
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=0.01
        )
        result = await order_manager.place_order(order)
        self.assertTrue(result['success'])
        
        # Create alert
        alert = Alert(
            alert_id=None,
            symbol='BTCUSD',
            condition_type='price_above',
            condition_value=60000,
            action='notify'
        )
        alert_result = await alert_manager.create_alert(alert)
        self.assertTrue(alert_result['success'])
        
        # Get positions
        positions = db.get_positions()
        self.assertEqual(len(positions), 1)

