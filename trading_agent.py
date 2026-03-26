# trading_agent.py
import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib
import hmac

import aiohttp
import pandas as pd
import numpy as np
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
import ollama
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= Data Models =============

@dataclass
class Order:
    """Order model"""
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', 'stop', 'stop_limit'
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = 'GTC'
    order_id: Optional[str] = None
    status: str = 'pending'
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class Position:
    """Position model"""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    updated_at: datetime = None

@dataclass
class RiskProfile:
    """Risk management profile"""
    max_position_size: float = 100000  # Maximum position size in currency
    max_daily_loss: float = 10000  # Maximum daily loss
    max_drawdown: float = 0.15  # Maximum drawdown percentage
    max_leverage: float = 2.0  # Maximum leverage
    risk_per_trade: float = 0.02  # 2% risk per trade
    stop_loss_default: float = 0.02  # Default 2% stop loss
    take_profit_default: float = 0.04  # Default 4% take profit

@dataclass
class Alert:
    """Alert model"""
    alert_id: str
    symbol: str
    condition_type: str  # 'price_above', 'price_below', 'volume', 'indicator'
    condition_value: float
    action: str  # 'notify', 'order', 'webhook'
    order_details: Optional[Dict] = None
    webhook_url: Optional[str] = None
    is_active: bool = True
    triggered_at: Optional[datetime] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.alert_id is None:
            self.alert_id = hashlib.md5(
                f"{self.symbol}{self.created_at}".encode()
            ).hexdigest()[:8]

# ============= Database Manager =============

class DatabaseManager:
    """SQLite database manager for persistent storage"""
    
    def __init__(self, db_path: str = "trading_agent.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            # Orders table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL,
                    stop_price REAL,
                    time_in_force TEXT,
                    status TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            
            # Positions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    quantity REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pnl REAL,
                    realized_pnl REAL,
                    updated_at TIMESTAMP
                )
            """)
            
            # Alerts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    condition_value REAL NOT NULL,
                    action TEXT NOT NULL,
                    order_details TEXT,
                    webhook_url TEXT,
                    is_active INTEGER,
                    triggered_at TIMESTAMP,
                    created_at TIMESTAMP
                )
            """)
            
            # Risk metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TIMESTAMP,
                    daily_pnl REAL,
                    total_exposure REAL,
                    drawdown REAL,
                    winning_trades INTEGER,
                    losing_trades INTEGER
                )
            """)
            
            conn.commit()
    
    def save_order(self, order: Order):
        """Save order to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO orders 
                (order_id, symbol, side, order_type, quantity, price, 
                 stop_price, time_in_force, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.order_id, order.symbol, order.side, order.order_type,
                order.quantity, order.price, order.stop_price, order.time_in_force,
                order.status, order.created_at, order.updated_at
            ))
            conn.commit()
    
    def save_position(self, position: Position):
        """Save position to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO positions
                (symbol, quantity, avg_price, current_price, unrealized_pnl, 
                 realized_pnl, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                position.symbol, position.quantity, position.avg_price,
                position.current_price, position.unrealized_pnl,
                position.realized_pnl, position.updated_at
            ))
            conn.commit()
    
    def save_alert(self, alert: Alert):
        """Save alert to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO alerts
                (alert_id, symbol, condition_type, condition_value, action,
                 order_details, webhook_url, is_active, triggered_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.symbol, alert.condition_type,
                alert.condition_value, alert.action,
                json.dumps(alert.order_details) if alert.order_details else None,
                alert.webhook_url, 1 if alert.is_active else 0,
                alert.triggered_at, alert.created_at
            ))
            conn.commit()
    
    def get_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get orders from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if symbol:
                cursor = conn.execute(
                    "SELECT * FROM orders WHERE symbol = ? ORDER BY created_at DESC",
                    (symbol,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM orders ORDER BY created_at DESC"
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_positions(self) -> List[Dict]:
        """Get positions from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM positions")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_alerts(self, active_only: bool = True) -> List[Dict]:
        """Get alerts from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if active_only:
                cursor = conn.execute(
                    "SELECT * FROM alerts WHERE is_active = 1"
                )
            else:
                cursor = conn.execute("SELECT * FROM alerts")
            return [dict(row) for row in cursor.fetchall()]

# ============= Market Data Provider =============

class MarketDataProvider:
    """Mock market data provider - Replace with real API"""
    
    def __init__(self):
        self.prices = {
            'BTCUSD': 50000,
            'ETHUSD': 3000,
            'AAPL': 175.50,
            'GOOGL': 140.25,
            'MSFT': 380.75
        }
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        # Simulate price movement
        import random
        change = random.uniform(-0.02, 0.02)
        current = self.prices.get(symbol, 100)
        new_price = current * (1 + change)
        self.prices[symbol] = new_price
        return new_price
    
    async def get_historical_data(self, symbol: str, period: str = '1d') -> pd.DataFrame:
        """Get historical price data"""
        # Mock historical data - replace with real API
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
        prices = np.random.randn(100).cumsum() + self.prices[symbol]
        df = pd.DataFrame({'price': prices}, index=dates)
        return df

# ============= Risk Manager =============

class RiskManager:
    """Risk management system"""
    
    def __init__(self, db: DatabaseManager, profile: RiskProfile = None):
        self.db = db
        self.profile = profile or RiskProfile()
        self.daily_pnl = 0.0
        self.daily_trades = []
    
    async def validate_order(self, order: Order, current_price: float) -> tuple[bool, str]:
        """Validate order against risk rules"""
        
        # Check position size
        position_value = order.quantity * current_price
        if position_value > self.profile.max_position_size:
            return False, f"Position size {position_value} exceeds maximum {self.profile.max_position_size}"
        
        # Check risk per trade
        risk_amount = position_value * self.profile.risk_per_trade
        if risk_amount > self.profile.max_daily_loss - abs(self.daily_pnl):
            return False, f"Risk amount {risk_amount} would exceed remaining daily loss limit"
        
        # Check existing positions
        positions = self.db.get_positions()
        total_exposure = sum(p['quantity'] * (p['current_price'] or p['avg_price']) 
                           for p in positions)
        
        if order.side == 'buy':
            total_exposure += position_value
            if total_exposure > self.profile.max_position_size * self.profile.max_leverage:
                return False, "Total exposure exceeds maximum allowed"
        
        # Check drawdown
        if self._calculate_drawdown() > self.profile.max_drawdown:
            return False, f"Current drawdown {self._calculate_drawdown()} exceeds maximum allowed"
        
        return True, "Order validated"
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown"""
        # Implement drawdown calculation
        return 0.05  # Mock value
    
    async def update_metrics(self, pnl: float):
        """Update risk metrics"""
        self.daily_pnl += pnl
        self.daily_trades.append({
            'timestamp': datetime.now(),
            'pnl': pnl
        })
        
        # Save to database
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("""
                INSERT INTO risk_metrics (date, daily_pnl, winning_trades, losing_trades)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.now(),
                self.daily_pnl,
                len([t for t in self.daily_trades if t['pnl'] > 0]),
                len([t for t in self.daily_trades if t['pnl'] < 0])
            ))
            conn.commit()

# ============= Order Manager =============

class OrderManager:
    """Order management system"""
    
    def __init__(self, db: DatabaseManager, risk_manager: RiskManager):
        self.db = db
        self.risk_manager = risk_manager
        self.market_data = MarketDataProvider()
        self.orders = {}
    
    async def place_order(self, order: Order) -> Dict[str, Any]:
        """Place a new order"""
        try:
            # Get current price
            current_price = await self.market_data.get_current_price(order.symbol)
            
            # Validate order
            is_valid, message = await self.risk_manager.validate_order(order, current_price)
            if not is_valid:
                return {'success': False, 'message': message}
            
            # Generate order ID
            order.order_id = hashlib.md5(
                f"{order.symbol}{datetime.now()}".encode()
            ).hexdigest()[:12]
            
            # Process order based on type
            if order.order_type == 'market':
                return await self._execute_market_order(order, current_price)
            elif order.order_type == 'limit':
                return await self._place_limit_order(order)
            elif order.order_type == 'stop':
                return await self._place_stop_order(order)
            elif order.order_type == 'stop_limit':
                return await self._place_stop_limit_order(order)
            else:
                return {'success': False, 'message': f'Unknown order type: {order.order_type}'}
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {'success': False, 'message': str(e)}
    
    async def _execute_market_order(self, order: Order, current_price: float) -> Dict[str, Any]:
        """Execute market order immediately"""
        try:
            # Execute at current price
            order.price = current_price
            order.status = 'filled'
            order.updated_at = datetime.now()
            
            # Save order
            self.db.save_order(order)
            
            # Update position
            await self._update_position(order)
            
            logger.info(f"Market order executed: {order.order_id} - {order.symbol} {order.side} {order.quantity}")
            
            return {
                'success': True,
                'order_id': order.order_id,
                'message': f'Market order executed at {current_price}',
                'order': asdict(order)
            }
            
        except Exception as e:
            logger.error(f"Error executing market order: {e}")
            return {'success': False, 'message': str(e)}
    
    async def _place_limit_order(self, order: Order) -> Dict[str, Any]:
        """Place limit order"""
        order.status = 'pending'
        self.db.save_order(order)
        self.orders[order.order_id] = order
        
        # Monitor for execution
        asyncio.create_task(self._monitor_limit_order(order))
        
        return {
            'success': True,
            'order_id': order.order_id,
            'message': f'Limit order placed at {order.price}',
            'order': asdict(order)
        }
    
    async def _place_stop_order(self, order: Order) -> Dict[str, Any]:
        """Place stop order"""
        order.status = 'pending'
        self.db.save_order(order)
        self.orders[order.order_id] = order
        
        asyncio.create_task(self._monitor_stop_order(order))
        
        return {
            'success': True,
            'order_id': order.order_id,
            'message': f'Stop order placed at {order.stop_price}',
            'order': asdict(order)
        }
    
    async def _place_stop_limit_order(self, order: Order) -> Dict[str, Any]:
        """Place stop-limit order"""
        order.status = 'pending'
        self.db.save_order(order)
        self.orders[order.order_id] = order
        
        asyncio.create_task(self._monitor_stop_limit_order(order))
        
        return {
            'success': True,
            'order_id': order.order_id,
            'message': f'Stop-limit order placed - Stop: {order.stop_price}, Limit: {order.price}',
            'order': asdict(order)
        }
    
    async def _monitor_limit_order(self, order: Order):
        """Monitor limit order for execution"""
        while order.status == 'pending':
            current_price = await self.market_data.get_current_price(order.symbol)
            
            if (order.side == 'buy' and current_price <= order.price) or \
               (order.side == 'sell' and current_price >= order.price):
                await self._execute_limit_order(order, current_price)
                break
            
            await asyncio.sleep(5)  # Check every 5 seconds
    
    async def _execute_limit_order(self, order: Order, current_price: float):
        """Execute limit order"""
        order.price = current_price
        order.status = 'filled'
        order.updated_at = datetime.now()
        self.db.save_order(order)
        await self._update_position(order)
        logger.info(f"Limit order executed: {order.order_id}")
    
    async def _monitor_stop_order(self, order: Order):
        """Monitor stop order for trigger"""
        while order.status == 'pending':
            current_price = await self.market_data.get_current_price(order.symbol)
            
            if (order.side == 'buy' and current_price >= order.stop_price) or \
               (order.side == 'sell' and current_price <= order.stop_price):
                # Trigger stop - convert to market order
                order.order_type = 'market'
                result = await self._execute_market_order(order, current_price)
                if result['success']:
                    order.status = 'filled'
                break
            
            await asyncio.sleep(5)
    
    async def _monitor_stop_limit_order(self, order: Order):
        """Monitor stop-limit order"""
        while order.status == 'pending':
            current_price = await self.market_data.get_current_price(order.symbol)
            
            if (order.side == 'buy' and current_price >= order.stop_price):
                # Trigger stop - place limit order
                order.order_type = 'limit'
                await self._place_limit_order(order)
                break
            
            await asyncio.sleep(5)
    
    async def _update_position(self, order: Order):
        """Update position after order execution"""
        # Get existing position
        positions = self.db.get_positions()
        position = next((p for p in positions if p['symbol'] == order.symbol), None)
        
        if position:
            # Update existing position
            if order.side == 'buy':
                new_quantity = position['quantity'] + order.quantity
                avg_price = ((position['quantity'] * position['avg_price']) + 
                            (order.quantity * order.price)) / new_quantity
            else:  # sell
                new_quantity = position['quantity'] - order.quantity
                avg_price = position['avg_price']
                
                # Calculate realized P&L
                realized_pnl = (order.price - position['avg_price']) * order.quantity
                position['realized_pnl'] += realized_pnl
                await self.risk_manager.update_metrics(realized_pnl)
            
            updated_position = Position(
                symbol=order.symbol,
                quantity=new_quantity,
                avg_price=avg_price,
                current_price=order.price,
                unrealized_pnl=0,
                realized_pnl=position.get('realized_pnl', 0),
                updated_at=datetime.now()
            )
        else:
            # Create new position
            updated_position = Position(
                symbol=order.symbol,
                quantity=order.quantity if order.side == 'buy' else -order.quantity,
                avg_price=order.price,
                current_price=order.price,
                unrealized_pnl=0,
                updated_at=datetime.now()
            )
        
        self.db.save_position(updated_position)

# ============= Alert Manager =============

class AlertManager:
    """Alert management system"""
    
    def __init__(self, db: DatabaseManager, order_manager: OrderManager):
        self.db = db
        self.order_manager = order_manager
        self.market_data = MarketDataProvider()
        self.active_alerts = {}
        self.webhook_sender = WebhookSender()
    
    async def create_alert(self, alert: Alert) -> Dict[str, Any]:
        """Create a new alert"""
        try:
            alert.alert_id = hashlib.md5(
                f"{alert.symbol}{datetime.now()}".encode()
            ).hexdigest()[:8]
            
            self.db.save_alert(alert)
            self.active_alerts[alert.alert_id] = alert
            
            # Start monitoring
            asyncio.create_task(self._monitor_alert(alert))
            
            return {
                'success': True,
                'alert_id': alert.alert_id,
                'message': f'Alert created for {alert.symbol}'
            }
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return {'success': False, 'message': str(e)}
    
    async def _monitor_alert(self, alert: Alert):
        """Monitor alert conditions"""
        while alert.is_active:
            try:
                current_price = await self.market_data.get_current_price(alert.symbol)
                should_trigger = False
                
                # Check condition
                if alert.condition_type == 'price_above' and current_price > alert.condition_value:
                    should_trigger = True
                elif alert.condition_type == 'price_below' and current_price < alert.condition_value:
                    should_trigger = True
                
                if should_trigger:
                    await self._trigger_alert(alert, current_price)
                    break
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring alert {alert.alert_id}: {e}")
                await asyncio.sleep(10)
    
    async def _trigger_alert(self, alert: Alert, current_price: float):
        """Trigger alert action"""
        alert.triggered_at = datetime.now()
        alert.is_active = False
        self.db.save_alert(alert)
        
        if alert.action == 'notify':
            logger.info(f"Alert triggered: {alert.alert_id} - {alert.symbol} at {current_price}")
            return {'message': 'Alert triggered', 'price': current_price}
            
        elif alert.action == 'order' and alert.order_details:
            # Place order based on alert
            order = Order(
                symbol=alert.symbol,
                side=alert.order_details.get('side', 'buy'),
                order_type=alert.order_details.get('order_type', 'market'),
                quantity=alert.order_details.get('quantity', 1),
                price=alert.order_details.get('price'),
                stop_price=alert.order_details.get('stop_price')
            )
            result = await self.order_manager.place_order(order)
            return result
            
        elif alert.action == 'webhook' and alert.webhook_url:
            # Send webhook
            data = {
                'alert_id': alert.alert_id,
                'symbol': alert.symbol,
                'price': current_price,
                'condition_type': alert.condition_type,
                'condition_value': alert.condition_value,
                'timestamp': datetime.now().isoformat()
            }
            await self.webhook_sender.send_webhook(alert.webhook_url, data)
            return {'message': 'Webhook sent', 'data': data}
        
        return {'message': 'Alert triggered', 'action': alert.action}

# ============= Webhook Sender =============

class WebhookSender:
    """Webhook sender for notifications"""
    
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def send_webhook(self, url: str, data: Dict, method: str = 'POST'):
        """Send webhook to specified URL"""
        try:
            session = await self.get_session()
            
            async with session.request(
                method, url, 
                json=data,
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    logger.info(f"Webhook sent to {url}")
                    return await response.json()
                else:
                    logger.error(f"Webhook failed: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return None
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()

# ============= AI Agent =============

class AIAgent:
    """AI-powered trading agent using Ollama"""
    
    def __init__(self, model_name: str = "llama2"):
        self.model_name = model_name
        self.market_data = MarketDataProvider()
        
    async def analyze_market(self, symbol: str) -> Dict[str, Any]:
        """Get AI analysis of market conditions"""
        try:
            # Get market data
            current_price = await self.market_data.get_current_price(symbol)
            historical_data = await self.market_data.get_historical_data(symbol)
            
            # Calculate technical indicators
            recent_prices = historical_data['price'].tail(20)
            sma_20 = recent_prices.mean()
            volatility = recent_prices.std() / recent_prices.mean()
            
            # Prepare prompt for LLM
            prompt = f"""
            Analyze the following market data for {symbol}:
            Current Price: ${current_price:.2f}
            20-period SMA: ${sma_20:.2f}
            Volatility: {volatility:.2%}
            
            Based on this data:
            1. What is your market sentiment (bullish/bearish/neutral)?
            2. What is your confidence level (0-100%)?
            3. What is your recommendation (buy/sell/hold)?
            4. What risk level do you see (low/medium/high)?
            
            Provide a brief analysis.
            """
            
            # Get response from Ollama
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            
            analysis = response['message']['content']
            
            # Parse sentiment and recommendation (simplified)
            sentiment = 'neutral'
            recommendation = 'hold'
            confidence = 50
            
            if 'bullish' in analysis.lower():
                sentiment = 'bullish'
                recommendation = 'buy'
                confidence = 70
            elif 'bearish' in analysis.lower():
                sentiment = 'bearish'
                recommendation = 'sell'
                confidence = 70
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'analysis': analysis,
                'sentiment': sentiment,
                'recommendation': recommendation,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'recommendation': 'hold'
            }
    
    async def generate_trading_advice(self, symbol: str, risk_profile: RiskProfile) -> Dict:
        """Generate trading advice based on AI analysis"""
        analysis = await self.analyze_market(symbol)
        
        if analysis.get('error'):
            return analysis
        
        # Calculate position size based on risk
        risk_amount = risk_profile.max_position_size * risk_profile.risk_per_trade
        position_size = risk_amount / analysis['current_price']
        
        return {
            **analysis,
            'suggested_position_size': position_size,
            'suggested_stop_loss': analysis['current_price'] * (1 - risk_profile.stop_loss_default),
            'suggested_take_profit': analysis['current_price'] * (1 + risk_profile.take_profit_default),
            'risk_percentage': risk_profile.risk_per_trade * 100
        }

# ============= FastMCP Server =============

# Initialize components
db = DatabaseManager()
risk_profile = RiskProfile()
risk_manager = RiskManager(db, risk_profile)
order_manager = OrderManager(db, risk_manager)
alert_manager = AlertManager(db, order_manager)
ai_agent = AIAgent()

# Create MCP server
mcp = FastMCP("Trading Agent")

# ============= Order Endpoints =============

@mcp.tool()
async def place_market_order(symbol: str, side: str, quantity: float) -> Dict[str, Any]:
    """Place a market order"""
    order = Order(
        symbol=symbol.upper(),
        side=side.lower(),
        order_type='market',
        quantity=quantity
    )
    return await order_manager.place_order(order)

@mcp.tool()
async def place_limit_order(symbol: str, side: str, quantity: float, price: float) -> Dict[str, Any]:
    """Place a limit order"""
    order = Order(
        symbol=symbol.upper(),
        side=side.lower(),
        order_type='limit',
        quantity=quantity,
        price=price
    )
    return await order_manager.place_order(order)

@mcp.tool()
async def place_stop_order(symbol: str, side: str, quantity: float, stop_price: float) -> Dict[str, Any]:
    """Place a stop order"""
    order = Order(
        symbol=symbol.upper(),
        side=side.lower(),
        order_type='stop',
        quantity=quantity,
        stop_price=stop_price
    )
    return await order_manager.place_order(order)

@mcp.tool()
async def cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel an existing order"""
    if order_id in order_manager.orders:
        order = order_manager.orders[order_id]
        order.status = 'cancelled'
        order.updated_at = datetime.now()
        db.save_order(order)
        del order_manager.orders[order_id]
        return {'success': True, 'message': f'Order {order_id} cancelled'}
    return {'success': False, 'message': 'Order not found'}

@mcp.tool()
async def get_orders(symbol: Optional[str] = None) -> List[Dict]:
    """Get all orders"""
    return db.get_orders(symbol)

# ============= Position Endpoints =============

@mcp.tool()
async def get_positions() -> List[Dict]:
    """Get current positions"""
    return db.get_positions()

@mcp.tool()
async def close_position(symbol: str) -> Dict[str, Any]:
    """Close a position"""
    positions = db.get_positions()
    position = next((p for p in positions if p['symbol'] == symbol), None)
    
    if position:
        side = 'sell' if position['quantity'] > 0 else 'buy'
        order = Order(
            symbol=symbol,
            side=side,
            order_type='market',
            quantity=abs(position['quantity'])
        )
        return await order_manager.place_order(order)
    
    return {'success': False, 'message': f'No position found for {symbol}'}

# ============= Alert Endpoints =============

@mcp.tool()
async def create_price_alert(symbol: str, condition: str, price: float, action: str = 'notify') -> Dict[str, Any]:
    """Create a price alert"""
    condition_type = 'price_above' if condition == 'above' else 'price_below'
    
    alert = Alert(
        alert_id=None,
        symbol=symbol.upper(),
        condition_type=condition_type,
        condition_value=price,
        action=action,
        order_details=None if action == 'notify' else {'side': 'buy', 'quantity': 1}
    )
    return await alert_manager.create_alert(alert)

@mcp.tool()
async def create_alert_with_order(symbol: str, condition: str, price: float, 
                                   order_side: str, order_type: str, quantity: float) -> Dict[str, Any]:
    """Create an alert that places an order when triggered"""
    condition_type = 'price_above' if condition == 'above' else 'price_below'
    
    alert = Alert(
        alert_id=None,
        symbol=symbol.upper(),
        condition_type=condition_type,
        condition_value=price,
        action='order',
        order_details={
            'side': order_side,
            'order_type': order_type,
            'quantity': quantity
        }
    )
    return await alert_manager.create_alert(alert)

@mcp.tool()
async def get_alerts(active_only: bool = True) -> List[Dict]:
    """Get all alerts"""
    return db.get_alerts(active_only)

@mcp.tool()
async def delete_alert(alert_id: str) -> Dict[str, Any]:
    """Delete an alert"""
    alerts = db.get_alerts(active_only=False)
    alert = next((a for a in alerts if a['alert_id'] == alert_id), None)
    
    if alert:
        alert['is_active'] = 0
        # Update in database
        with sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "UPDATE alerts SET is_active = 0 WHERE alert_id = ?",
                (alert_id,)
            )
            conn.commit()
        
        if alert_id in alert_manager.active_alerts:
            del alert_manager.active_alerts[alert_id]
        
        return {'success': True, 'message': f'Alert {alert_id} deleted'}
    
    return {'success': False, 'message': 'Alert not found'}

# ============= Risk Management Endpoints =============

@mcp.tool()
async def get_risk_metrics() -> Dict[str, Any]:
    """Get current risk metrics"""
    return {
        'max_position_size': risk_profile.max_position_size,
        'max_daily_loss': risk_profile.max_daily_loss,
        'max_drawdown': risk_profile.max_drawdown,
        'max_leverage': risk_profile.max_leverage,
        'risk_per_trade': risk_profile.risk_per_trade,
        'daily_pnl': risk_manager.daily_pnl,
        'daily_trades_count': len(risk_manager.daily_trades)
    }

@mcp.tool()
async def update_risk_profile(
    max_position_size: Optional[float] = None,
    max_daily_loss: Optional[float] = None,
    risk_per_trade: Optional[float] = None,
    stop_loss_default: Optional[float] = None,
    take_profit_default: Optional[float] = None
) -> Dict[str, Any]:
    """Update risk profile settings"""
    if max_position_size:
        risk_profile.max_position_size = max_position_size
    if max_daily_loss:
        risk_profile.max_daily_loss = max_daily_loss
    if risk_per_trade:
        risk_profile.risk_per_trade = risk_per_trade
    if stop_loss_default:
        risk_profile.stop_loss_default = stop_loss_default
    if take_profit_default:
        risk_profile.take_profit_default = take_profit_default
    
    return {
        'success': True,
        'risk_profile': {
            'max_position_size': risk_profile.max_position_size,
            'max_daily_loss': risk_profile.max_daily_loss,
            'risk_per_trade': risk_profile.risk_per_trade,
            'stop_loss_default': risk_profile.stop_loss_default,
            'take_profit_default': risk_profile.take_profit_default
        }
    }

# ============= AI Analysis Endpoints =============

@mcp.tool()
async def ai_market_analysis(symbol: str) -> Dict[str, Any]:
    """Get AI-powered market analysis"""
    return await ai_agent.analyze_market(symbol.upper())

@mcp.tool()
async def ai_trading_advice(symbol: str) -> Dict[str, Any]:
    """Get AI trading advice with position sizing"""
    return await ai_agent.generate_trading_advice(symbol.upper(), risk_profile)

# ============= Webhook Endpoints =============

@mcp.tool()
async def send_webhook_notification(url: str, message: str) -> Dict[str, Any]:
    """Send a webhook notification"""
    webhook = WebhookSender()
    data = {
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'type': 'notification'
    }
    result = await webhook.send_webhook(url, data)
    await webhook.close()
    return {'success': result is not None, 'result': result}

@mcp.tool()
async def create_webhook_alert(symbol: str, condition: str, price: float, webhook_url: str) -> Dict[str, Any]:
    """Create an alert that sends webhook when triggered"""
    condition_type = 'price_above' if condition == 'above' else 'price_below'
    
    alert = Alert(
        alert_id=None,
        symbol=symbol.upper(),
        condition_type=condition_type,
        condition_value=price,
        action='webhook',
        webhook_url=webhook_url
    )
    return await alert_manager.create_alert(alert)

# ============= Market Data Endpoints =============

@mcp.tool()
async def get_current_price(symbol: str) -> Dict[str, Any]:
    """Get current price for a symbol"""
    market_data = MarketDataProvider()
    price = await market_data.get_current_price(symbol.upper())
    return {
        'symbol': symbol,
        'price': price,
        'timestamp': datetime.now().isoformat()
    }

# ============= Main Application =============

if __name__ == "__main__":
    print("=" * 50)
    print("AI Trading Agent with Ollama")
    print("=" * 50)
    print("\nStarting server...")
    print("Available features:")
    print("  - Order placement (market, limit, stop, stop-limit)")
    print("  - Risk management")
    print("  - Price alerts")
    print("  - Alert-based orders")
    print("  - Webhook notifications")
    print("  - AI market analysis using Ollama")
    print("\nServer is running...")
    
    # Run the MCP server
    mcp.run()