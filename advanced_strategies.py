# advanced_strategies.py - Automated Trading Strategy Coordination
import asyncio
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass
import uuid

class StrategyType(Enum):
    """Trading strategy types"""
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    TREND_FOLLOWING = "trend_following"
    ML_BASED = "ml_based"

@dataclass
class StrategyConfig:
    """Strategy configuration"""
    strategy_id: str
    name: str
    type: StrategyType
    symbol: str
    parameters: Dict
    is_active: bool = True
    allocation_percent: float = 0.0
    max_positions: int = 1
    cooldown_period: int = 60  # seconds

class StrategyCoordinator:
    """Coordinate multiple trading strategies"""
    
    def __init__(self, order_manager: OrderManager, risk_manager: RiskManager):
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.strategies: Dict[str, 'BaseStrategy'] = {}
        self.strategy_states: Dict[str, Dict] = {}
        self.strategy_queue = asyncio.Queue()
        self.running = False
        
    def register_strategy(self, strategy: 'BaseStrategy'):
        """Register a trading strategy"""
        self.strategies[strategy.config.strategy_id] = strategy
        self.strategy_states[strategy.config.strategy_id] = {
            'status': 'registered',
            'last_run': None,
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0
        }
        
    async def start(self):
        """Start all registered strategies"""
        self.running = True
        
        # Start strategy execution loop
        asyncio.create_task(self._execute_strategies())
        
        # Start monitoring loop
        asyncio.create_task(self._monitor_strategies())
        
    async def _execute_strategies(self):
        """Execute strategies in order"""
        while self.running:
            try:
                # Get next strategy to execute
                strategy_id = await self.strategy_queue.get()
                strategy = self.strategies.get(strategy_id)
                
                if strategy and strategy.config.is_active:
                    # Check cooldown
                    last_run = self.strategy_states[strategy_id]['last_run']
                    if last_run:
                        elapsed = (datetime.now() - last_run).total_seconds()
                        if elapsed < strategy.config.cooldown_period:
                            await self.strategy_queue.put(strategy_id)
                            continue
                    
                    # Execute strategy
                    try:
                        signals = await strategy.analyze()
                        if signals:
                            await self._process_signals(strategy, signals)
                        
                        # Update state
                        self.strategy_states[strategy_id]['last_run'] = datetime.now()
                        self.strategy_states[strategy_id]['status'] = 'executed'
                        
                    except Exception as e:
                        logger.error(f"Strategy {strategy_id} execution error: {e}")
                        self.strategy_states[strategy_id]['status'] = 'error'
                
                await asyncio.sleep(0.1)  # Small delay
                
            except Exception as e:
                logger.error(f"Strategy execution loop error: {e}")
                
    async def _process_signals(self, strategy: 'BaseStrategy', signals: List[Dict]):
        """Process trading signals from strategy"""
        for signal in signals:
            # Check risk limits
            position_value = signal['quantity'] * signal.get('price', 0)
            if position_value > self.risk_manager.profile.max_position_size * strategy.config.allocation_percent:
                continue
                
            # Place order
            order = Order(
                symbol=signal['symbol'],
                side=signal['side'],
                order_type=signal.get('order_type', 'market'),
                quantity=signal['quantity'],
                price=signal.get('price'),
                stop_price=signal.get('stop_price')
            )
            
            result = await self.order_manager.place_order(order)
            
            if result['success']:
                self.strategy_states[strategy.config.strategy_id]['total_trades'] += 1
                
                # Record signal
                await self._record_signal(strategy.config.strategy_id, signal, result)
                
    async def _record_signal(self, strategy_id: str, signal: Dict, result: Dict):
        """Record signal for performance tracking"""
        # Store in database
        with sqlite3.connect(self.order_manager.db.db_path) as conn:
            conn.execute("""
                INSERT INTO strategy_signals 
                (signal_id, strategy_id, symbol, side, quantity, price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                strategy_id,
                signal['symbol'],
                signal['side'],
                signal['quantity'],
                signal.get('price'),
                result['status'],
                datetime.now()
            ))
            conn.commit()
    
    async def _monitor_strategies(self):
        """Monitor strategy performance"""
        while self.running:
            await asyncio.sleep(60)  # Check every minute
            
            for strategy_id, strategy in self.strategies.items():
                # Check performance metrics
                state = self.strategy_states[strategy_id]
                
                if state['total_trades'] > 0:
                    win_rate = state['winning_trades'] / state['total_trades']
                    
                    # Auto-disable poor performing strategies
                    if win_rate < 0.4 and state['total_trades'] > 10:
                        strategy.config.is_active = False
                        logger.warning(f"Strategy {strategy_id} disabled due to low win rate: {win_rate:.2%}")

class BaseStrategy:
    """Base class for trading strategies"""
    
    def __init__(self, config: StrategyConfig, market_data: MarketDataProvider):
        self.config = config
        self.market_data = market_data
        self.indicators = TechnicalIndicators()
        
    async def analyze(self) -> List[Dict]:
        """Analyze market and generate signals"""
        raise NotImplementedError

class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands"""
    
    async def analyze(self) -> List[Dict]:
        signals = []
        
        # Get historical data
        df = await self.market_data.get_historical_data(self.config.symbol, '1h')
        if len(df) < 50:
            return signals
            
        # Calculate Bollinger Bands
        bb = self.indicators.calculate_bollinger_bands(df['close'])
        current_price = df['close'].iloc[-1]
        
        # Mean reversion signals
        if current_price < bb['lower'].iloc[-1]:
            # Oversold - potential buy
            quantity = self.config.parameters.get('quantity', 1)
            signals.append({
                'symbol': self.config.symbol,
                'side': 'buy',
                'order_type': 'limit',
                'quantity': quantity,
                'price': current_price,
                'stop_price': current_price * 0.98
            })
            
        elif current_price > bb['upper'].iloc[-1]:
            # Overbought - potential sell
            quantity = self.config.parameters.get('quantity', 1)
            signals.append({
                'symbol': self.config.symbol,
                'side': 'sell',
                'order_type': 'limit',
                'quantity': quantity,
                'price': current_price,
                'stop_price': current_price * 1.02
            })
            
        return signals

class MomentumStrategy(BaseStrategy):
    """Momentum strategy using RSI and MACD"""
    
    async def analyze(self) -> List[Dict]:
        signals = []
        
        df = await self.market_data.get_historical_data(self.config.symbol, '1h')
        if len(df) < 100:
            return signals
            
        # Calculate indicators
        rsi = self.indicators.calculate_rsi(df['close'])
        macd = self.indicators.calculate_macd(df['close'])
        
        current_rsi = rsi.iloc[-1]
        current_macd = macd['macd'].iloc[-1]
        current_signal = macd['signal'].iloc[-1]
        
        # Momentum signals
        if current_rsi < 30 and current_macd > current_signal:
            # Bullish momentum
            quantity = self.config.parameters.get('quantity', 1)
            signals.append({
                'symbol': self.config.symbol,
                'side': 'buy',
                'order_type': 'market',
                'quantity': quantity
            })
            
        elif current_rsi > 70 and current_macd < current_signal:
            # Bearish momentum
            quantity = self.config.parameters.get('quantity', 1)
            signals.append({
                'symbol': self.config.symbol,
                'side': 'sell',
                'order_type': 'market',
                'quantity': quantity
            })
            
        return signals

# ============= Disaster Recovery System =============

class DisasterRecoverySystem:
    """Disaster recovery and failover system"""
    
    def __init__(self, db: DatabaseManager, order_manager: OrderManager):
        self.db = db
        self.order_manager = order_manager
        self.backup_path = "backups/"
        self.is_recovering = False
        self.recovery_checkpoints = []
        
        # Create backup directory
        os.makedirs(self.backup_path, exist_ok=True)
        
    async def create_checkpoint(self):
        """Create system checkpoint"""
        checkpoint_id = f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Backup database
        backup_file = f"{self.backup_path}/{checkpoint_id}.db"
        with sqlite3.connect(self.db.db_path) as src:
            with sqlite3.connect(backup_file) as dst:
                src.backup(dst)
        
        # Save order states
        orders = self.db.get_orders()
        with open(f"{self.backup_path}/{checkpoint_id}_orders.json", 'w') as f:
            json.dump(orders, f, default=str)
        
        # Save position states
        positions = self.db.get_positions()
        with open(f"{self.backup_path}/{checkpoint_id}_positions.json", 'w') as f:
            json.dump(positions, f, default=str)
        
        self.recovery_checkpoints.append({
            'id': checkpoint_id,
            'timestamp': datetime.now(),
            'file': backup_file,
            'orders_count': len(orders),
            'positions_count': len(positions)
        })
        
        # Keep only last 10 checkpoints
        if len(self.recovery_checkpoints) > 10:
            old_checkpoint = self.recovery_checkpoints.pop(0)
            os.remove(f"{self.backup_path}/{old_checkpoint['id']}.db")
            os.remove(f"{self.backup_path}/{old_checkpoint['id']}_orders.json")
            os.remove(f"{self.backup_path}/{old_checkpoint['id']}_positions.json")
        
        return checkpoint_id
    
    async def recover_from_checkpoint(self, checkpoint_id: str) -> bool:
        """Recover system from checkpoint"""
        if self.is_recovering:
            return False
            
        self.is_recovering = True
        
        try:
            # Find checkpoint
            checkpoint = next((c for c in self.recovery_checkpoints if c['id'] == checkpoint_id), None)
            if not checkpoint:
                return False
            
            # Restore database
            with sqlite3.connect(checkpoint['file']) as src:
                with sqlite3.connect(self.db.db_path) as dst:
                    src.backup(dst)
            
            # Restore orders
            with open(f"{self.backup_path}/{checkpoint_id}_orders.json", 'r') as f:
                orders = json.load(f)
                for order_data in orders:
                    order = Order(**order_data)
                    self.db.save_order(order)
            
            # Restore positions
            with open(f"{self.backup_path}/{checkpoint_id}_positions.json", 'r') as f:
                positions = json.load(f)
                for pos_data in positions:
                    position = Position(**pos_data)
                    self.db.save_position(position)
            
            logger.info(f"Recovered from checkpoint: {checkpoint_id}")
            return True
            
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            return False
            
        finally:
            self.is_recovering = False
    
    async def auto_recovery(self):
        """Automatic recovery on failure"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            try:
                # Check system health
                if not await self._check_system_health():
                    # Find latest checkpoint
                    if self.recovery_checkpoints:
                        latest = self.recovery_checkpoints[-1]
                        await self.recover_from_checkpoint(latest['id'])
                        
            except Exception as e:
                logger.error(f"Auto recovery check failed: {e}")
    
    async def _check_system_health(self) -> bool:
        """Check system health"""
        try:
            # Check database connectivity
            self.db.get_orders(limit=1)
            
            # Check order manager
            if hasattr(self.order_manager, 'is_healthy'):
                return await self.order_manager.is_healthy()
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

# ============= Real-time Risk Dashboard =============

class RiskDashboard:
    """Real-time risk monitoring dashboard"""
    
    def __init__(self, risk_manager: RiskManager, db: DatabaseManager):
        self.risk_manager = risk_manager
        self.db = db
        self.updates = asyncio.Queue()
        
    async def generate_risk_report(self) -> Dict:
        """Generate comprehensive risk report"""
        positions = self.db.get_positions()
        
        # Calculate portfolio metrics
        total_exposure = sum(p['quantity'] * p['current_price'] for p in positions)
        var = await self.risk_manager.calculate_var(positions)
        stress_loss = await self._calculate_stress_loss(positions)
        
        # Calculate concentration risks
        concentration_risks = self._calculate_concentration_risks(positions)
        
        # Calculate correlation risks
        correlation_risks = await self._calculate_correlation_risks(positions)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'portfolio_metrics': {
                'total_exposure': total_exposure,
                'value_at_risk_95': var,
                'stress_loss_20pct': stress_loss,
                'leverage_ratio': total_exposure / self.risk_manager.profile.max_position_size
            },
            'concentration_risks': concentration_risks,
            'correlation_risks': correlation_risks,
            'risk_limits': {
                'max_position_size': self.risk_manager.profile.max_position_size,
                'max_daily_loss': self.risk_manager.profile.max_daily_loss,
                'risk_per_trade': self.risk_manager.profile.risk_per_trade,
                'current_daily_pnl': self.risk_manager.daily_pnl,
                'remaining_daily_loss': self.risk_manager.profile.max_daily_loss - self.risk_manager.daily_pnl
            },
            'warning_levels': self._calculate_warning_levels()
        }
    
    async def _calculate_stress_loss(self, positions: List[Dict]) -> float:
        """Calculate potential loss under stress scenario"""
        stress_factor = 0.2  # 20% market drop
        total_loss = sum(p['quantity'] * p['current_price'] * stress_factor for p in positions)
        return total_loss
    
    def _calculate_concentration_risks(self, positions: List[Dict]) -> List[Dict]:
        """Calculate concentration risks"""
        if not positions:
            return []
            
        total_value = sum(p['quantity'] * p['current_price'] for p in positions)
        risks = []
        
        for pos in positions:
            value = pos['quantity'] * pos['current_price']
            concentration = value / total_value if total_value > 0 else 0
            
            if concentration > 0.25:  # 25% concentration threshold
                risks.append({
                    'symbol': pos['symbol'],
                    'concentration': concentration,
                    'value': value,
                    'risk_level': 'high' if concentration > 0.4 else 'medium'
                })
                
        return risks
    
    async def _calculate_correlation_risks(self, positions: List[Dict]) -> List[Dict]:
        """Calculate correlation-based risks"""
        risks = []
        
        for i, pos1 in enumerate(positions):
            for pos2 in positions[i+1:]:
                correlation = await self.risk_manager._get_correlation(pos1['symbol'], pos2['symbol'])
                
                if correlation > 0.8:  # High correlation threshold
                    risks.append({
                        'symbol1': pos1['symbol'],
                        'symbol2': pos2['symbol'],
                        'correlation': correlation,
                        'risk_level': 'high'
                    })
                    
        return risks
    
    def _calculate_warning_levels(self) -> Dict:
        """Calculate warning levels"""
        warnings = []
        
        # Daily loss warning
        remaining = self.risk_manager.profile.max_daily_loss - self.risk_manager.daily_pnl
        if remaining < self.risk_manager.profile.max_daily_loss * 0.2:
            warnings.append({
                'type': 'daily_loss',
                'level': 'critical',
                'message': f'Only {remaining:.2f} remaining from daily loss limit'
            })
        
        # Position size warning
        positions = self.db.get_positions()
        for pos in positions:
            position_value = pos['quantity'] * pos['current_price']
            if position_value > self.risk_manager.profile.max_position_size * 0.8:
                warnings.append({
                    'type': 'position_size',
                    'symbol': pos['symbol'],
                    'level': 'warning',
                    'message': f'Position size {position_value:.2f} is near limit'
                })
        
        return {'warnings': warnings}

# ============= Exchange Integration Layer =============

class ExchangeConnector:
    """Unified interface for multiple exchanges"""
    
    def __init__(self):
        self.exchanges = {}
        self.active_exchange = None
        
    def register_exchange(self, name: str, exchange: MarketDataProvider):
        """Register an exchange"""
        self.exchanges[name] = exchange
        
    async def switch_exchange(self, name: str):
        """Switch active exchange"""
        if name in self.exchanges:
            self.active_exchange = name
            logger.info(f"Switched to exchange: {name}")
            
    async def get_price(self, symbol: str) -> float:
        """Get price from active exchange"""
        if not self.active_exchange:
            raise Exception("No active exchange")
            
        exchange = self.exchanges[self.active_exchange]
        return await exchange.get_current_price(symbol)
    
    async def get_prices_all_exchanges(self, symbol: str) -> Dict:
        """Get price from all exchanges"""
        prices = {}
        for name, exchange in self.exchanges.items():
            try:
                price = await exchange.get_current_price(symbol)
                prices[name] = price
            except Exception as e:
                prices[name] = f"Error: {e}"
        return prices

# ============= Automated Reporting System =============

class ReportingSystem:
    """Automated reporting and notifications"""
    
    def __init__(self, db: DatabaseManager, risk_dashboard: RiskDashboard):
        self.db = db
        self.risk_dashboard = risk_dashboard
        self.report_schedule = {}
        
    async def generate_daily_report(self) -> Dict:
        """Generate daily performance report"""
        # Get daily metrics
        orders = self.db.get_orders()
        today_orders = [o for o in orders if datetime.fromisoformat(o['created_at']).date() == datetime.now().date()]
        
        # Calculate daily P&L
        total_pnl = 0
        winning_trades = 0
        losing_trades = 0
        
        for order in today_orders:
            if order['status'] == 'filled':
                # Simplified P&L calculation
                pnl = order.get('pnl', 0)
                total_pnl += pnl
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
        
        # Get risk report
        risk_report = await self.risk_dashboard.generate_risk_report()
        
        report = {
            'date': datetime.now().date().isoformat(),
            'performance': {
                'total_trades': len(today_orders),
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': winning_trades / len(today_orders) if today_orders else 0,
                'total_pnl': total_pnl,
                'average_pnl': total_pnl / len(today_orders) if today_orders else 0
            },
            'risk_metrics': risk_report,
            'positions': self.db.get_positions(),
            'active_alerts': len(self.db.get_alerts())
        }
        
        # Save report
        report_file = f"reports/daily_report_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, default=str, indent=2)
        
        return report
    
    async def generate_weekly_report(self) -> Dict:
        """Generate weekly performance report"""
        # Get last 7 days of orders
        week_ago = datetime.now() - timedelta(days=7)
        orders = self.db.get_orders()
        week_orders = [o for o in orders if datetime.fromisoformat(o['created_at']) > week_ago]
        
        # Calculate weekly metrics
        total_pnl = sum(o.get('pnl', 0) for o in week_orders if o['status'] == 'filled')
        
        # Calculate best and worst performing symbols
        symbol_performance = {}
        for order in week_orders:
            symbol = order['symbol']
            pnl = order.get('pnl', 0)
            if symbol not in symbol_performance:
                symbol_performance[symbol] = {'pnl': 0, 'trades': 0}
            symbol_performance[symbol]['pnl'] += pnl
            symbol_performance[symbol]['trades'] += 1
        
        best_symbol = max(symbol_performance.items(), key=lambda x: x[1]['pnl']) if symbol_performance else None
        worst_symbol = min(symbol_performance.items(), key=lambda x: x[1]['pnl']) if symbol_performance else None
        
        return {
            'period': {
                'start': week_ago.isoformat(),
                'end': datetime.now().isoformat()
            },
            'performance': {
                'total_trades': len(week_orders),
                'total_pnl': total_pnl,
                'average_daily_pnl': total_pnl / 7,
                'best_symbol': best_symbol,
                'worst_symbol': worst_symbol
            },
            'sharpe_ratio': await self._calculate_sharpe_ratio(week_orders),
            'max_drawdown': await self._calculate_max_drawdown(week_orders)
        }
    
    async def _calculate_sharpe_ratio(self, orders: List[Dict]) -> float:
        """Calculate Sharpe ratio for period"""
        daily_returns = []
        for order in orders:
            if order['status'] == 'filled':
                daily_returns.append(order.get('pnl', 0))
        
        if not daily_returns:
            return 0
            
        avg_return = statistics.mean(daily_returns)
        std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 1
        
        if std_return == 0:
            return 0
            
        return avg_return / std_return
    
    async def _calculate_max_drawdown(self, orders: List[Dict]) -> float:
        """Calculate maximum drawdown"""
        cumulative_pnl = []
        current = 0
        
        for order in orders:
            if order['status'] == 'filled':
                current += order.get('pnl', 0)
                cumulative_pnl.append(current)
        
        if not cumulative_pnl:
            return 0
            
        peak = cumulative_pnl[0]
        drawdowns = []
        
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            drawdowns.append(drawdown)
            
        return max(drawdowns)

# ============= Performance Analytics =============

class PerformanceAnalytics:
    """Advanced performance analytics"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        
    async def analyze_trading_patterns(self) -> Dict:
        """Analyze trading patterns and behaviors"""
        orders = self.db.get_orders()
        
        # Time-based analysis
        hourly_performance = {}
        for order in orders:
            if order['status'] == 'filled':
                hour = datetime.fromisoformat(order['created_at']).hour
                pnl = order.get('pnl', 0)
                
                if hour not in hourly_performance:
                    hourly_performance[hour] = {'total_pnl': 0, 'trades': 0}
                hourly_performance[hour]['total_pnl'] += pnl
                hourly_performance[hour]['trades'] += 1
        
        # Find best and worst hours
        best_hour = max(hourly_performance.items(), key=lambda x: x[1]['total_pnl']) if hourly_performance else None
        worst_hour = min(hourly_performance.items(), key=lambda x: x[1]['total_pnl']) if hourly_performance else None
        
        # Order size analysis
        order_sizes = [o['quantity'] for o in orders if o['status'] == 'filled']
        
        return {
            'hourly_performance': hourly_performance,
            'best_trading_hour': best_hour,
            'worst_trading_hour': worst_hour,
            'average_order_size': statistics.mean(order_sizes) if order_sizes else 0,
            'median_order_size': statistics.median(order_sizes) if order_sizes else 0,
            'order_size_std': statistics.stdev(order_sizes) if len(order_sizes) > 1 else 0
        }
    
    async def calculate_risk_adjusted_returns(self) -> Dict:
        """Calculate risk-adjusted return metrics"""
        orders = self.db.get_orders()
        filled_orders = [o for o in orders if o['status'] == 'filled']
        
        if not filled_orders:
            return {}
        
        returns = [o.get('pnl', 0) for o in filled_orders]
        
        # Calculate various metrics
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 1
        
        # Sortino ratio (using downside deviation)
        negative_returns = [r for r in returns if r < 0]
        downside_std = statistics.stdev(negative_returns) if len(negative_returns) > 1 else 1
        
        # Calmar ratio
        max_drawdown = await self._calculate_max_drawdown(filled_orders)
        
        return {
            'sharpe_ratio': avg_return / std_return if std_return > 0 else 0,
            'sortino_ratio': avg_return / downside_std if downside_std > 0 else 0,
            'calmar_ratio': avg_return / max_drawdown if max_drawdown > 0 else 0,
            'information_ratio': avg_return / std_return,  # Simplified
            'treynor_ratio': avg_return / std_return,  # Simplified
            'beta': 1.0,  # Placeholder - would need market data
            'alpha': avg_return - 0.02  # Assuming 2% risk-free rate
        }
    
    async def _calculate_max_drawdown(self, orders: List[Dict]) -> float:
        """Calculate maximum drawdown from orders"""
        cumulative = []
        current = 0
        
        for order in orders:
            current += order.get('pnl', 0)
            cumulative.append(current)
        
        if not cumulative:
            return 0
            
        peak = cumulative[0]
        drawdowns = []
        
        for value in cumulative:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            drawdowns.append(drawdown)
            
        return max(drawdowns)

# ============= Complete Integration Test Suite =============

import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
class TestCompleteSystem:
    """Complete system integration tests"""
    
    @pytest.fixture
    async def setup_system(self):
        """Setup test system"""
        db = DatabaseManager(':memory:')
        risk_profile = RiskProfile()
        risk_manager = RiskManager(db, risk_profile)
        order_manager = OrderManager(db, risk_manager)
        alert_manager = AlertManager(db, order_manager)
        
        return {
            'db': db,
            'risk_manager': risk_manager,
            'order_manager': order_manager,
            'alert_manager': alert_manager
        }
    
    async def test_end_to_end_order_flow(self, setup_system):
        """Test complete order flow"""
        components = await setup_system
        
        # Place order
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=0.1
        )
        result = await components['order_manager'].place_order(order)
        assert result['success'] == True
        
        # Verify order saved
        orders = components['db'].get_orders()
        assert len(orders) == 1
        assert orders[0]['symbol'] == 'BTCUSD'
        
        # Verify position updated
        positions = components['db'].get_positions()
        assert len(positions) == 1
        assert positions[0]['symbol'] == 'BTCUSD'
    
    async def test_alert_trigger(self, setup_system):
        """Test alert triggering"""
        components = await setup_system
        
        # Create alert
        alert = Alert(
            alert_id=None,
            symbol='BTCUSD',
            condition_type='price_above',
            condition_value=100000,  # Very high price
            action='notify'
        )
        result = await components['alert_manager'].create_alert(alert)
        assert result['success'] == True
        
        # Verify alert created
        alerts = components['db'].get_alerts()
        assert len(alerts) == 1
    
    async def test_risk_validation(self, setup_system):
        """Test risk validation"""
        components = await setup_system
        
        # Try to place oversized order
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=1000000  # Very large quantity
        )
        result = await components['order_manager'].place_order(order)
        assert result['success'] == False
        assert 'exceeds maximum' in result['message'].lower()
    
    async def test_strategy_execution(self):
        """Test strategy execution"""
        market_data = MarketDataProvider()
        
        # Test mean reversion strategy
        strategy_config = StrategyConfig(
            strategy_id='test_1',
            name='Mean Reversion Test',
            type=StrategyType.MEAN_REVERSION,
            symbol='BTCUSD',
            parameters={'quantity': 0.1}
        )
        
        strategy = MeanReversionStrategy(strategy_config, market_data)
        signals = await strategy.analyze()
        
        # Should return list (possibly empty)
        assert isinstance(signals, list)
    
    async def test_disaster_recovery(self, setup_system):
        """Test disaster recovery"""
        components = await setup_system
        
        # Create recovery system
        recovery = DisasterRecoverySystem(
            components['db'],
            components['order_manager']
        )
        
        # Create checkpoint
        checkpoint_id = await recovery.create_checkpoint()
        assert checkpoint_id is not None
        
        # Verify checkpoint files exist
        assert os.path.exists(f"{recovery.backup_path}/{checkpoint_id}.db")
        
        # Test recovery (would need to simulate failure)

# ============= API Documentation =============

API_DOCUMENTATION = """
# Trading Agent API Documentation

## Base URL: `http://localhost:8000`

## Authentication
All API endpoints require API key authentication: