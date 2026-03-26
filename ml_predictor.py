# ml_predictor.py - Machine Learning Integration
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

class MLPricePredictor:
    """Machine learning model for price prediction"""
    
    def __init__(self, model_path: str = "models/"):
        self.model_path = model_path
        self.classifier = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        self.regressor = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        
    def prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare features for ML model"""
        features = pd.DataFrame()
        
        # Price-based features
        features['returns'] = df['close'].pct_change()
        features['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        features['volatility'] = features['returns'].rolling(20).std()
        
        # Moving averages
        features['sma_5'] = df['close'].rolling(5).mean() / df['close']
        features['sma_10'] = df['close'].rolling(10).mean() / df['close']
        features['sma_20'] = df['close'].rolling(20).mean() / df['close']
        features['sma_50'] = df['close'].rolling(50).mean() / df['close']
        
        # Price momentum
        features['momentum_5'] = df['close'].pct_change(5)
        features['momentum_10'] = df['close'].pct_change(10)
        
        # Volume features
        if 'volume' in df.columns:
            features['volume_change'] = df['volume'].pct_change()
            features['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # Technical indicators
        features['rsi'] = self.calculate_rsi(df['close'])
        features['macd'] = self.calculate_macd(df['close'])
        
        # Price levels
        features['high_low_ratio'] = df['high'] / df['low'] if 'high' in df.columns else 1
        features['close_open_ratio'] = df['close'] / df['open'] if 'open' in df.columns else 1
        
        # Drop NaN values
        features = features.dropna()
        
        return features.values, features.columns.tolist()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: pd.Series) -> pd.Series:
        """Calculate MACD"""
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        return macd
    
    async def train(self, historical_data: Dict[str, pd.DataFrame]):
        """Train ML models on historical data"""
        all_features = []
        all_targets_class = []
        all_targets_reg = []
        
        for symbol, df in historical_data.items():
            if len(df) < 100:
                continue
                
            features, _ = self.prepare_features(df)
            
            # Classification target: price direction (up/down)
            future_returns = df['close'].shift(-5).pct_change(5).dropna()
            target_class = (future_returns > 0).astype(int)
            
            # Regression target: future price change
            target_reg = future_returns.values
            
            # Align features with targets
            min_len = min(len(features), len(target_class))
            all_features.append(features[:min_len])
            all_targets_class.append(target_class[:min_len])
            all_targets_reg.append(target_reg[:min_len])
        
        if not all_features:
            return False
        
        # Combine all data
        X = np.vstack(all_features)
        y_class = np.hstack(all_targets_class)
        y_reg = np.hstack(all_targets_reg)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train-test split
        X_train, X_test, y_train_class, y_test_class = train_test_split(
            X_scaled, y_class, test_size=0.2, random_state=42
        )
        _, _, y_train_reg, y_test_reg = train_test_split(
            X_scaled, y_reg, test_size=0.2, random_state=42
        )
        
        # Train models
        self.classifier.fit(X_train, y_train_class)
        self.regressor.fit(X_train, y_train_reg)
        
        # Evaluate
        class_accuracy = self.classifier.score(X_test, y_test_class)
        reg_score = self.regressor.score(X_test, y_test_reg)
        
        self.is_trained = True
        
        # Save models
        joblib.dump(self.classifier, f"{self.model_path}/classifier.pkl")
        joblib.dump(self.regressor, f"{self.model_path}/regressor.pkl")
        joblib.dump(self.scaler, f"{self.model_path}/scaler.pkl")
        
        return {
            'accuracy': class_accuracy,
            'r2_score': reg_score,
            'samples': len(X)
        }
    
    async def predict(self, symbol: str, current_data: pd.DataFrame) -> Dict[str, float]:
        """Make prediction for symbol"""
        if not self.is_trained:
            return {'error': 'Model not trained'}
        
        features, _ = self.prepare_features(current_data)
        if len(features) == 0:
            return {'error': 'Insufficient data'}
        
        features_scaled = self.scaler.transform(features[-1:])
        
        # Get predictions
        direction_prob = self.classifier.predict_proba(features_scaled)[0]
        expected_return = self.regressor.predict(features_scaled)[0]
        
        return {
            'direction': 'up' if direction_prob[1] > 0.5 else 'down',
            'confidence': max(direction_prob) * 100,
            'expected_return': expected_return * 100,
            'buy_probability': direction_prob[1] * 100,
            'sell_probability': direction_prob[0] * 100
        }

# ============= Advanced Order Execution Algorithms =============

class SmartOrderRouter:
    """Smart order routing for best execution"""
    
    def __init__(self):
        self.exchanges = {}
        self.latency_stats = {}
        
    def add_exchange(self, name: str, provider: MarketDataProvider, fee_rate: float):
        """Add exchange to router"""
        self.exchanges[name] = {
            'provider': provider,
            'fee_rate': fee_rate,
            'latency': 0.0
        }
    
    async def get_best_price(self, symbol: str, side: str, quantity: float) -> Dict:
        """Find best price across exchanges"""
        best_price = None
        best_exchange = None
        quotes = {}
        
        for name, exchange in self.exchanges.items():
            try:
                price = await exchange['provider'].get_current_price(symbol)
                quotes[name] = price
                
                # Calculate effective price with fees
                effective_price = price * (1 + exchange['fee_rate']) if side == 'buy' else price * (1 - exchange['fee_rate'])
                
                if best_price is None or effective_price < best_price:
                    best_price = effective_price
                    best_exchange = name
                    
            except Exception as e:
                logger.error(f"Error getting price from {name}: {e}")
        
        return {
            'best_exchange': best_exchange,
            'best_price': best_price,
            'all_quotes': quotes,
            'savings': self._calculate_savings(quotes, best_exchange)
        }
    
    def _calculate_savings(self, quotes: Dict, best_exchange: str) -> float:
        """Calculate potential savings"""
        if not quotes or best_exchange not in quotes:
            return 0.0
        
        avg_price = sum(quotes.values()) / len(quotes)
        best_price = quotes[best_exchange]
        
        return (avg_price - best_price) / avg_price * 100

class TWAPExecutor:
    """Time-Weighted Average Price execution"""
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.active_orders = {}
        
    async def execute_twap(self, order: Order, duration_minutes: int, slices: int):
        """Execute order using TWAP algorithm"""
        slice_quantity = order.quantity / slices
        slice_interval = (duration_minutes * 60) / slices
        
        results = []
        
        for i in range(slices):
            slice_order = Order(
                symbol=order.symbol,
                side=order.side,
                order_type='market',
                quantity=slice_quantity
            )
            
            result = await self.order_manager.place_order(slice_order)
            results.append(result)
            
            if i < slices - 1:
                await asyncio.sleep(slice_interval)
        
        # Calculate average execution price
        total_cost = sum(r.get('price', 0) * slice_quantity for r in results if r.get('success'))
        avg_price = total_cost / order.quantity if order.quantity > 0 else 0
        
        return {
            'success': True,
            'slices_executed': len([r for r in results if r.get('success')]),
            'average_price': avg_price,
            'total_quantity': order.quantity,
            'executions': results
        }

class VWAPExecutor:
    """Volume-Weighted Average Price execution"""
    
    def __init__(self, order_manager: OrderManager, market_data: MarketDataProvider):
        self.order_manager = order_manager
        self.market_data = market_data
        
    async def execute_vwap(self, order: Order, historical_volume_profile: pd.Series):
        """Execute order using VWAP algorithm"""
        # Calculate expected volume distribution
        total_volume = historical_volume_profile.sum()
        volume_percentages = historical_volume_profile / total_volume
        
        # Distribute order based on volume profile
        results = []
        cumulative_quantity = 0
        
        for i, volume_pct in enumerate(volume_percentages):
            slice_quantity = order.quantity * volume_pct
            
            if cumulative_quantity + slice_quantity > order.quantity:
                slice_quantity = order.quantity - cumulative_quantity
            
            if slice_quantity > 0:
                slice_order = Order(
                    symbol=order.symbol,
                    side=order.side,
                    order_type='market',
                    quantity=slice_quantity
                )
                
                result = await self.order_manager.place_order(slice_order)
                results.append(result)
                cumulative_quantity += slice_quantity
            
            if cumulative_quantity >= order.quantity:
                break
            
            # Wait for next slice
            await asyncio.sleep(60)  # 1 minute intervals
        
        return {
            'success': True,
            'slices_executed': len(results),
            'total_quantity': cumulative_quantity,
            'executions': results
        }

# ============= Market Microstructure Analysis =============

class MarketMicrostructure:
    """Analyze market microstructure and order flow"""
    
    def __init__(self, market_data: MarketDataProvider):
        self.market_data = market_data
        self.order_flow_imbalance = {}
        
    async def analyze_order_flow(self, symbol: str, depth: int = 10) -> Dict:
        """Analyze order flow imbalance"""
        # Get order book (mock implementation)
        order_book = await self.get_order_book(symbol, depth)
        
        # Calculate bid-ask spread
        best_bid = order_book['bids'][0][0] if order_book['bids'] else 0
        best_ask = order_book['asks'][0][0] if order_book['asks'] else 0
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid) * 100 if best_bid > 0 else 0
        
        # Calculate order book imbalance
        bid_volume = sum(level[1] for level in order_book['bids'][:depth])
        ask_volume = sum(level[1] for level in order_book['asks'][:depth])
        total_volume = bid_volume + ask_volume
        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
        
        # Calculate weighted average prices
        bid_wap = sum(level[0] * level[1] for level in order_book['bids'][:depth]) / bid_volume if bid_volume > 0 else 0
        ask_wap = sum(level[0] * level[1] for level in order_book['asks'][:depth]) / ask_volume if ask_volume > 0 else 0
        
        # Calculate market impact
        market_impact = self.estimate_market_impact(order_book)
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': spread,
            'spread_pct': spread_pct,
            'order_imbalance': imbalance,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'bid_wap': bid_wap,
            'ask_wap': ask_wap,
            'market_impact': market_impact,
            'liquidity_score': self.calculate_liquidity_score(order_book)
        }
    
    async def get_order_book(self, symbol: str, depth: int = 10) -> Dict:
        """Get order book data"""
        # Mock order book - replace with real data
        import random
        
        mid_price = await self.market_data.get_current_price(symbol)
        bids = []
        asks = []
        
        for i in range(depth):
            bid_price = mid_price * (1 - random.uniform(0.0001, 0.01) * (i + 1))
            bid_volume = random.uniform(0.1, 10) * (depth - i)
            bids.append([bid_price, bid_volume])
            
            ask_price = mid_price * (1 + random.uniform(0.0001, 0.01) * (i + 1))
            ask_volume = random.uniform(0.1, 10) * (depth - i)
            asks.append([ask_price, ask_volume])
        
        return {'bids': bids, 'asks': asks}
    
    def estimate_market_impact(self, order_book: Dict) -> float:
        """Estimate market impact for a market order"""
        if not order_book['asks'] or not order_book['bids']:
            return 0.0
        
        # Simplified market impact calculation
        bid_liquidity = order_book['bids'][0][1]
        ask_liquidity = order_book['asks'][0][1]
        total_liquidity = (bid_liquidity + ask_liquidity) / 2
        
        return 1 / (total_liquidity + 1)  # Simplified formula
    
    def calculate_liquidity_score(self, order_book: Dict) -> float:
        """Calculate liquidity score"""
        if not order_book['asks'] or not order_book['bids']:
            return 0.0
        
        bid_liquidity = sum(level[1] for level in order_book['bids'][:5])
        ask_liquidity = sum(level[1] for level in order_book['asks'][:5])
        total_liquidity = (bid_liquidity + ask_liquidity) / 2
        
        # Normalize to 0-1 scale (assuming max liquidity of 1000)
        return min(total_liquidity / 1000, 1.0)

# ============= Web Admin Interface =============

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import List

class WebAdminInterface:
    """Web-based admin interface for trading agent"""
    
    def __init__(self, trading_agent: CompleteTradingAgent, port: int = 8500):
        self.agent = trading_agent
        self.port = port
        self.app = FastAPI(title="Trading Agent Admin Interface")
        self.active_websockets: List[WebSocket] = []
        
        self.setup_routes()
        self.setup_middleware()
        
    def setup_middleware(self):
        """Setup FastAPI middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
    def setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/")
        async def root():
            return HTMLResponse(self.get_dashboard_html())
        
        @self.app.get("/api/status")
        async def get_status():
            """Get system status"""
            return {
                'status': 'running',
                'uptime': (datetime.now() - self.agent.start_time).total_seconds(),
                'active_orders': len(self.agent.order_manager.orders),
                'positions': len(self.agent.db.get_positions()),
                'alerts': len(self.agent.db.get_alerts()),
                'daily_pnl': self.agent.risk_manager.daily_pnl
            }
        
        @self.app.get("/api/positions")
        async def get_positions():
            """Get current positions"""
            return self.agent.db.get_positions()
        
        @self.app.get("/api/orders")
        async def get_orders(symbol: str = None):
            """Get orders"""
            return self.agent.db.get_orders(symbol)
        
        @self.app.get("/api/alerts")
        async def get_alerts():
            """Get alerts"""
            return self.agent.db.get_alerts()
        
        @self.app.get("/api/performance")
        async def get_performance():
            """Get performance metrics"""
            return self.agent.performance_monitor.get_performance_report()
        
        @self.app.get("/api/risk-metrics")
        async def get_risk_metrics():
            """Get risk metrics"""
            return {
                'risk_profile': asdict(self.agent.risk_profile),
                'daily_pnl': self.agent.risk_manager.daily_pnl,
                'drawdown': self.agent.risk_manager._calculate_drawdown(),
                'var': await self.agent.risk_manager.calculate_var(
                    self.agent.db.get_positions()
                )
            }
        
        @self.app.post("/api/orders/market")
        async def place_market_order(symbol: str, side: str, quantity: float):
            """Place market order"""
            order = Order(
                symbol=symbol,
                side=side,
                order_type='market',
                quantity=quantity
            )
            result = await self.agent.order_manager.place_order(order)
            return result
        
        @self.app.post("/api/alerts/price")
        async def create_price_alert(symbol: str, condition: str, price: float):
            """Create price alert"""
            alert = Alert(
                alert_id=None,
                symbol=symbol,
                condition_type=f'price_{condition}',
                condition_value=price,
                action='notify'
            )
            result = await self.agent.alert_manager.create_alert(alert)
            return result
        
        @self.app.post("/api/risk/update")
        async def update_risk_profile(
            max_position_size: float = None,
            max_daily_loss: float = None,
            risk_per_trade: float = None
        ):
            """Update risk profile"""
            if max_position_size:
                self.agent.risk_profile.max_position_size = max_position_size
            if max_daily_loss:
                self.agent.risk_profile.max_daily_loss = max_daily_loss
            if risk_per_trade:
                self.agent.risk_profile.risk_per_trade = risk_per_trade
            
            return {'success': True, 'risk_profile': asdict(self.agent.risk_profile)}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.active_websockets.append(websocket)
            
            try:
                while True:
                    # Receive client messages
                    data = await websocket.receive_json()
                    await self.handle_websocket_message(data, websocket)
            except WebSocketDisconnect:
                self.active_websockets.remove(websocket)
        
        @self.app.get("/admin/dashboard")
        async def admin_dashboard():
            """Admin dashboard HTML"""
            return HTMLResponse(self.get_admin_html())
    
    def get_dashboard_html(self) -> str:
        """Get main dashboard HTML"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trading Agent Dashboard</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #f5f5f5;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }
                .metric-card {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .metric-value {
                    font-size: 32px;
                    font-weight: bold;
                    color: #667eea;
                }
                .metric-label {
                    color: #666;
                    margin-top: 10px;
                }
                .section {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th, td {
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                th {
                    background: #f8f9fa;
                    font-weight: bold;
                }
                .positive {
                    color: #10b981;
                }
                .negative {
                    color: #ef4444;
                }
                button {
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                }
                button:hover {
                    background: #5a67d8;
                }
                input, select {
                    padding: 8px;
                    margin: 5px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🤖 AI Trading Agent Dashboard</h1>
                <p>Real-time monitoring and control interface</p>
            </div>
            
            <div class="metrics-grid" id="metrics">
                <!-- Dynamic metrics will be loaded here -->
            </div>
            
            <div class="section">
                <h2>📊 Current Positions</h2>
                <div id="positions-table"></div>
            </div>
            
            <div class="section">
                <h2>💰 Place Order</h2>
                <input type="text" id="symbol" placeholder="Symbol (e.g., BTCUSD)">
                <select id="side">
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                </select>
                <input type="number" id="quantity" placeholder="Quantity">
                <button onclick="placeOrder()">Place Market Order</button>
            </div>
            
            <div class="section">
                <h2>🔔 Create Alert</h2>
                <input type="text" id="alert-symbol" placeholder="Symbol">
                <select id="alert-condition">
                    <option value="above">Price Above</option>
                    <option value="below">Price Below</option>
                </select>
                <input type="number" id="alert-price" placeholder="Price">
                <button onclick="createAlert()">Create Alert</button>
            </div>
            
            <div class="section">
                <h2>⚠️ Risk Management</h2>
                <div id="risk-metrics"></div>
                <button onclick="updateRiskProfile()">Update Risk Profile</button>
            </div>
            
            <script>
                // WebSocket connection for real-time updates
                const ws = new WebSocket(`ws://${window.location.host}/ws`);
                
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                };
                
                // Load initial data
                async function loadData() {
                    await loadStatus();
                    await loadPositions();
                    await loadRiskMetrics();
                }
                
                async function loadStatus() {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    updateMetrics(data);
                }
                
                async function loadPositions() {
                    const response = await fetch('/api/positions');
                    const positions = await response.json();
                    displayPositions(positions);
                }
                
                async function loadRiskMetrics() {
                    const response = await fetch('/api/risk-metrics');
                    const metrics = await response.json();
                    displayRiskMetrics(metrics);
                }
                
                function updateMetrics(data) {
                    const metricsHtml = `
                        <div class="metric-card">
                            <div class="metric-value">$${data.daily_pnl.toFixed(2)}</div>
                            <div class="metric-label">Daily P&L</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">${data.active_orders}</div>
                            <div class="metric-label">Active Orders</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">${data.positions}</div>
                            <div class="metric-label">Open Positions</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">${data.alerts}</div>
                            <div class="metric-label">Active Alerts</div>
                        </div>
                    `;
                    document.getElementById('metrics').innerHTML = metricsHtml;
                }
                
                function displayPositions(positions) {
                    if (positions.length === 0) {
                        document.getElementById('positions-table').innerHTML = '<p>No open positions</p>';
                        return;
                    }
                    
                    let html = '<table><tr><th>Symbol</th><th>Quantity</th><th>Avg Price</th><th>Current Price</th><th>Unrealized P&L</th></tr>';
                    positions.forEach(pos => {
                        const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
                        html += `<tr>
                            <td>${pos.symbol}</td>
                            <td>${pos.quantity}</td>
                            <td>$${pos.avg_price.toFixed(2)}</td>
                            <td>$${pos.current_price.toFixed(2)}</td>
                            <td class="${pnlClass}">$${pos.unrealized_pnl.toFixed(2)}</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('positions-table').innerHTML = html;
                }
                
                function displayRiskMetrics(metrics) {
                    const html = `
                        <p><strong>Max Position Size:</strong> $${metrics.risk_profile.max_position_size}</p>
                        <p><strong>Max Daily Loss:</strong> $${metrics.risk_profile.max_daily_loss}</p>
                        <p><strong>Risk per Trade:</strong> ${(metrics.risk_profile.risk_per_trade * 100).toFixed(1)}%</p>
                        <p><strong>Current Daily P&L:</strong> $${metrics.daily_pnl.toFixed(2)}</p>
                        <p><strong>Current Drawdown:</strong> ${(metrics.drawdown * 100).toFixed(2)}%</p>
                        <p><strong>Value at Risk (95%):</strong> $${metrics.var.toFixed(2)}</p>
                    `;
                    document.getElementById('risk-metrics').innerHTML = html;
                }
                
                async function placeOrder() {
                    const symbol = document.getElementById('symbol').value;
                    const side = document.getElementById('side').value;
                    const quantity = parseFloat(document.getElementById('quantity').value);
                    
                    const response = await fetch(`/api/orders/market?symbol=${symbol}&side=${side}&quantity=${quantity}`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    alert(result.message);
                    loadData();
                }
                
                async function createAlert() {
                    const symbol = document.getElementById('alert-symbol').value;
                    const condition = document.getElementById('alert-condition').value;
                    const price = parseFloat(document.getElementById('alert-price').value);
                    
                    const response = await fetch(`/api/alerts/price?symbol=${symbol}&condition=${condition}&price=${price}`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    alert(result.message);
                }
                
                function updateDashboard(data) {
                    // Update dashboard with real-time data
                    if (data.update_type === 'price') {
                        // Update price displays
                    } else if (data.update_type === 'order') {
                        loadData();
                    }
                }
                
                // Initial load
                loadData();
                
                // Refresh every 5 seconds
                setInterval(loadData, 5000);
            </script>
        </body>
        </html>
        """
    
    def get_admin_html(self) -> str:
        """Get admin panel HTML"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Panel - Trading Agent</title>
            <style>
                body {
                    font-family: monospace;
                    margin: 0;
                    padding: 20px;
                    background: #1a1a1a;
                    color: #00ff00;
                }
                .terminal {
                    background: #000;
                    padding: 20px;
                    border-radius: 5px;
                    font-family: monospace;
                }
                .command-line {
                    display: flex;
                    margin: 10px 0;
                }
                .prompt {
                    color: #00ff00;
                    margin-right: 10px;
                }
                input {
                    background: #000;
                    border: none;
                    color: #00ff00;
                    font-family: monospace;
                    flex: 1;
                    outline: none;
                }
                .output {
                    margin: 10px 0;
                    white-space: pre-wrap;
                }
                .help {
                    color: #ffff00;
                }
            </style>
        </head>
        <body>
            <h1>🖥️ Trading Agent Admin Console</h1>
            <div class="terminal">
                <div class="output" id="output">
                    Trading Agent Admin Console v1.0<br>
                    Type 'help' for available commands<br><br>
                </div>
                <div class="command-line">
                    <span class="prompt">$></span>
                    <input type="text" id="command" autofocus>
                </div>
            </div>
            
            <script>
                const output = document.getElementById('output');
                const commandInput = document.getElementById('command');
                
                commandInput.addEventListener('keypress', async (e) => {
                    if (e.key === 'Enter') {
                        const command = commandInput.value;
                        commandInput.value = '';
                        await executeCommand(command);
                    }
                });
                
                async function executeCommand(cmd) {
                    // Display command
                    output.innerHTML += `<span class="prompt">$></span> ${cmd}<br>`;
                    
                    const parts = cmd.trim().split(' ');
                    const action = parts[0];
                    
                    try {
                        let response;
                        switch(action) {
                            case 'help':
                                response = `
Available commands:
  status          - Show system status
  positions       - List current positions
  orders          - List recent orders
  alerts          - List active alerts
  risk            - Show risk metrics
  performance     - Show performance report
  place <symbol> <side> <quantity> - Place market order
  alert <symbol> <above/below> <price> - Create price alert
  stop            - Stop the trading agent
  clear           - Clear screen
                                `;
                                break;
                                
                            case 'status':
                                const statusResp = await fetch('/api/status');
                                const status = await statusResp.json();
                                response = JSON.stringify(status, null, 2);
                                break;
                                
                            case 'positions':
                                const posResp = await fetch('/api/positions');
                                const positions = await posResp.json();
                                response = JSON.stringify(positions, null, 2);
                                break;
                                
                            case 'orders':
                                const ordersResp = await fetch('/api/orders');
                                const orders = await ordersResp.json();
                                response = JSON.stringify(orders, null, 2);
                                break;
                                
                            case 'alerts':
                                const alertsResp = await fetch('/api/alerts');
                                const alerts = await alertsResp.json();
                                response = JSON.stringify(alerts, null, 2);
                                break;
                                
                            case 'risk':
                                const riskResp = await fetch('/api/risk-metrics');
                                const risk = await riskResp.json();
                                response = JSON.stringify(risk, null, 2);
                                break;
                                
                            case 'performance':
                                const perfResp = await fetch('/api/performance');
                                const perf = await perfResp.json();
                                response = JSON.stringify(perf, null, 2);
                                break;
                                
                            case 'place':
                                if (parts.length < 4) {
                                    response = 'Usage: place <symbol> <side> <quantity>';
                                } else {
                                    const orderResp = await fetch(`/api/orders/market?symbol=${parts[1]}&side=${parts[2]}&quantity=${parts[3]}`, {
                                        method: 'POST'
                                    });
                                    const order = await orderResp.json();
                                    response = JSON.stringify(order, null, 2);
                                }
                                break;
                                
                            case 'alert':
                                if (parts.length < 4) {
                                    response = 'Usage: alert <symbol> <above/below> <price>';
                                } else {
                                    const alertResp = await fetch(`/api/alerts/price?symbol=${parts[1]}&condition=${parts[2]}&price=${parts[3]}`, {
                                        method: 'POST'
                                    });
                                    const alert = await alertResp.json();
                                    response = JSON.stringify(alert, null, 2);
                                }
                                break;
                                
                            case 'clear':
                                output.innerHTML = '';
                                response = '';
                                break;
                                
                            case 'stop':
                                response = 'Shutting down trading agent...';
                                output.innerHTML += response + '<br>';
                                setTimeout(() => {
                                    fetch('/api/shutdown', {method: 'POST'});
                                }, 1000);
                                break;
                                
                            default:
                                response = `Unknown command: ${action}. Type 'help' for available commands.`;
                        }
                        
                        if (response) {
                            output.innerHTML += response + '<br>';
                        }
                        
                        // Scroll to bottom
                        output.scrollTop = output.scrollHeight;
                        
                    } catch (error) {
                        output.innerHTML += `Error: ${error.message}<br>`;
                    }
                }
            </script>
        </body>
        </html>
        """
    
    async def handle_websocket_message(self, data: Dict, websocket: WebSocket):
        """Handle WebSocket messages"""
        message_type = data.get('type')
        
        if message_type == 'subscribe':
            channels = data.get('channels', [])
            websocket.channels = channels
            await websocket.send_json({'status': 'subscribed', 'channels': channels})
            
        elif message_type == 'command':
            command = data.get('command')
            # Execute command and return result
            result = await self.execute_admin_command(command)
            await websocket.send_json(result)
    
    async def execute_admin_command(self, command: str) -> Dict:
        """Execute admin command"""
        # Parse and execute command
        return {'status': 'executed', 'command': command}
    
    async def broadcast_update(self, update: Dict):
        """Broadcast update to all connected WebSocket clients"""
        for websocket in self.active_websockets:
            try:
                await websocket.send_json(update)
            except:
                pass
    
    async def start(self):
        """Start web admin interface"""
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

# ============= Deployment Scripts =============

#!/bin/bash
# deploy.sh - Deployment script

DEPLOY_SCRIPT = """
#!/bin/bash

echo "🚀 Deploying AI Trading Agent..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting." >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required but not installed. Aborting." >&2; exit 1; }

# Build Docker image
echo "📦 Building Docker image..."
docker build -t trading-agent:latest .

# Push to registry (if using Kubernetes)
if [ "$1" == "k8s" ]; then
    echo "☸️ Deploying to Kubernetes..."
    kubectl apply -f kubernetes/deployment.yaml
    kubectl apply -f kubernetes/service.yaml
    kubectl apply -f kubernetes/configmap.yaml
    kubectl rollout status deployment/trading-agent
elif [ "$1" == "docker" ]; then
    echo "🐳 Deploying with Docker Compose..."
    docker-compose up -d
else
    echo "❌ Please specify deployment target: k8s or docker"
    exit 1
fi

echo "✅ Deployment complete!"
"""

# ============= Monitoring Dashboard =============

class MonitoringDashboard:
    """Real-time monitoring dashboard with charts"""
    
    def __init__(self):
        self.metrics_history = {
            'pnl': [],
            'positions': [],
            'volume': [],
            'timestamps': []
        }
        
    def record_metric(self, metric_name: str, value: float):
        """Record metric value"""
        if metric_name not in self.metrics_history:
            self.metrics_history[metric_name] = []
        
        self.metrics_history[metric_name].append({
            'timestamp': datetime.now(),
            'value': value
        })
        
        # Keep last 1000 points
        if len(self.metrics_history[metric_name]) > 1000:
            self.metrics_history[metric_name].pop(0)
    
    def generate_charts(self) -> str:
        """Generate HTML charts"""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=('P&L Over Time', 'Position Sizes', 
                          'Trade Volume', 'Risk Metrics',
                          'Win Rate', 'Drawdown')
        )
        
        # P&L chart
        if self.metrics_history.get('pnl'):
            pnl_data = self.metrics_history['pnl']
            fig.add_trace(
                go.Scatter(
                    x=[d['timestamp'] for d in pnl_data],
                    y=[d['value'] for d in pnl_data],
                    mode='lines',
                    name='P&L',
                    line=dict(color='green')
                ),
                row=1, col=1
            )
        
        # Position sizes
        if self.metrics_history.get('positions'):
            pos_data = self.metrics_history['positions']
            fig.add_trace(
                go.Bar(
                    x=[d['timestamp'] for d in pos_data],
                    y=[d['value'] for d in pos_data],
                    name='Positions'
                ),
                row=1, col=2
            )
        
        # Volume chart
        if self.metrics_history.get('volume'):
            vol_data = self.metrics_history['volume']
            fig.add_trace(
                go.Scatter(
                    x=[d['timestamp'] for d in vol_data],
                    y=[d['value'] for d in vol_data],
                    mode='lines',
                    fill='tozeroy',
                    name='Volume'
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            title="Trading Agent Performance Dashboard",
            height=800,
            showlegend=True
        )
        
        return fig.to_html(include_plotlyjs='cdn', full_html=False)

# ============= Main Entry Point with All Features =============

async def main_with_all_features():
    """Main entry point with all features enabled"""
    
    # Initialize configuration
    config = ConfigurationManager()
    
    # Initialize components
    db = DatabaseManager(config.get('database.path', 'trading_agent.db'))
    risk_profile = RiskProfile(
        max_position_size=config.get('risk_management.max_position_size', 100000),
        max_daily_loss=config.get('risk_management.max_daily_loss', 10000),
        risk_per_trade=config.get('risk_management.risk_per_trade', 0.02)
    )
    
    # Initialize advanced components
    risk_manager = AdvancedRiskManager(db, risk_profile)
    order_manager = AdvancedOrderManager(db, risk_manager)
    alert_manager = EnhancedAlertManager(db, order_manager)
    ai_agent = AdvancedAIAgent(config.get('ai.model', 'llama2'))
    ml_predictor = MLPricePredictor()
    smart_router = SmartOrderRouter()
    microstructure = MarketMicrostructure(MarketDataProvider())
    
    # Initialize execution algorithms
    twap_executor = TWAPExecutor(order_manager)
    vwap_executor = VWAPExecutor(order_manager, MarketDataProvider())
    
    # Initialize web interface
    web_interface = WebAdminInterface(None, port=8500)  # Will set agent later
    
    # Initialize monitoring
    monitoring = MonitoringDashboard()
    
    # Initialize metrics collector
    metrics = MetricsCollector()
    
    # Start all services
    print("="*60)
    print("🤖 AI Trading Agent - Complete Edition")
    print("="*60)
    print("\n✅ Components initialized:")
    print("  ✓ Order Management (Market, Limit, Stop, TWAP, VWAP)")
    print("  ✓ Advanced Risk Management (VaR, Correlation, Stress Testing)")
    print("  ✓ AI Analysis (Ollama Integration)")
    print("  ✓ ML Price Prediction (Random Forest, Gradient Boosting)")
    print("  ✓ Smart Order Routing")
    print("  ✓ Market Microstructure Analysis")
    print("  ✓ Real-time Web Dashboard")
    print("  ✓ Admin Console")
    print("  ✓ Monitoring & Metrics")
    print("  ✓ WebSocket Notifications")
    print("\n🌐 Web Interface: http://localhost:8500")
    print("📊 Admin Console: http://localhost:8500/admin/dashboard")
    print("📈 Metrics: http://localhost:9090/metrics")
    print("❤️ Health Check: http://localhost:8080/health")
    print("\nPress Ctrl+C to stop")
    print("="*60)
    
    # Run web interface in background
    asyncio.create_task(web_interface.start())
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
            
            # Update monitoring
            positions = db.get_positions()
            monitoring.record_metric('positions', len(positions))
            
            # Calculate total P&L
            total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
            monitoring.record_metric('pnl', total_pnl)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        # Clean shutdown
        await web_interface.app.shutdown()

if __name__ == "__main__":
    asyncio.run(main_with_all_features())