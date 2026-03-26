# sentiment_analyzer.py - News and Social Media Sentiment Analysis
import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import re
from textblob import TextBlob
import numpy as np
from collections import deque

class SentimentAnalyzer:
    """Analyze market sentiment from news and social media"""
    
    def __init__(self, api_keys: Dict[str, str] = None):
        self.api_keys = api_keys or {}
        self.sentiment_scores = {}
        self.news_cache = {}
        self.sentiment_history = deque(maxlen=1000)
        
    async def get_news_sentiment(self, symbol: str) -> Dict[str, float]:
        """Get sentiment from financial news"""
        try:
            # Fetch news from multiple sources
            news_sources = await self._fetch_news(symbol)
            
            if not news_sources:
                return {'sentiment': 0, 'confidence': 0, 'sources': 0}
            
            sentiments = []
            for article in news_sources:
                # Analyze article text
                text = f"{article.get('title', '')} {article.get('description', '')}"
                sentiment = self._analyze_text(text)
                sentiments.append(sentiment)
            
            # Calculate aggregate sentiment
            avg_sentiment = np.mean(sentiments)
            confidence = min(len(sentiments) / 10, 1.0)  # Confidence based on number of sources
            
            # Store in history
            self.sentiment_history.append({
                'timestamp': datetime.now(),
                'symbol': symbol,
                'sentiment': avg_sentiment,
                'sources': len(sentiments)
            })
            
            return {
                'sentiment': avg_sentiment,
                'confidence': confidence,
                'sources': len(sentiments),
                'articles': news_sources[:5]  # Return top 5 articles
            }
            
        except Exception as e:
            logger.error(f"Error analyzing news sentiment: {e}")
            return {'sentiment': 0, 'confidence': 0, 'sources': 0, 'error': str(e)}
    
    async def get_social_sentiment(self, symbol: str) -> Dict[str, float]:
        """Get sentiment from social media (Twitter, Reddit, etc.)"""
        try:
            # Fetch social media posts
            posts = await self._fetch_social_posts(symbol)
            
            if not posts:
                return {'sentiment': 0, 'confidence': 0, 'posts': 0}
            
            sentiments = []
            for post in posts:
                sentiment = self._analyze_text(post.get('text', ''))
                # Weight by engagement (likes, retweets)
                weight = post.get('engagement', 1)
                sentiments.extend([sentiment] * weight)
            
            # Calculate weighted sentiment
            avg_sentiment = np.mean(sentiments)
            confidence = min(len(posts) / 50, 1.0)
            
            # Detect sentiment trends
            trend = self._calculate_sentiment_trend(symbol)
            
            return {
                'sentiment': avg_sentiment,
                'confidence': confidence,
                'posts': len(posts),
                'trend': trend,
                'momentum': self._calculate_sentiment_momentum()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing social sentiment: {e}")
            return {'sentiment': 0, 'confidence': 0, 'posts': 0}
    
    def _analyze_text(self, text: str) -> float:
        """Analyze text sentiment using TextBlob"""
        blob = TextBlob(text)
        
        # Get polarity (-1 to 1)
        polarity = blob.sentiment.polarity
        
        # Apply financial domain-specific adjustments
        financial_keywords = {
            'bullish': 0.5, 'bearish': -0.5, 'buy': 0.3, 'sell': -0.3,
            'up': 0.2, 'down': -0.2, 'profit': 0.3, 'loss': -0.3,
            'growth': 0.4, 'decline': -0.4, 'rally': 0.4, 'crash': -0.6
        }
        
        # Adjust sentiment based on financial keywords
        text_lower = text.lower()
        for keyword, impact in financial_keywords.items():
            if keyword in text_lower:
                polarity += impact * 0.1
        
        # Clamp to [-1, 1]
        return max(-1, min(1, polarity))
    
    async def _fetch_news(self, symbol: str) -> List[Dict]:
        """Fetch news from various APIs"""
        articles = []
        
        # Try different news sources
        if 'newsapi' in self.api_keys:
            articles.extend(await self._fetch_newsapi(symbol))
        
        if 'alphavantage' in self.api_keys:
            articles.extend(await self._fetch_alphavantage_news(symbol))
        
        return articles
    
    async def _fetch_social_posts(self, symbol: str) -> List[Dict]:
        """Fetch social media posts"""
        posts = []
        
        # Mock implementation - replace with actual API calls
        # In production, integrate with Twitter API, Reddit API, etc.
        
        return posts
    
    def _calculate_sentiment_trend(self, symbol: str) -> str:
        """Calculate sentiment trend direction"""
        recent_sentiments = [s for s in self.sentiment_history 
                           if s['symbol'] == symbol][-10:]
        
        if len(recent_sentiments) < 5:
            return 'neutral'
        
        values = [s['sentiment'] for s in recent_sentiments]
        slope = np.polyfit(range(len(values)), values, 1)[0]
        
        if slope > 0.05:
            return 'improving'
        elif slope < -0.05:
            return 'deteriorating'
        else:
            return 'stable'
    
    def _calculate_sentiment_momentum(self) -> float:
        """Calculate sentiment momentum"""
        if len(self.sentiment_history) < 2:
            return 0.0
        
        recent = [s['sentiment'] for s in list(self.sentiment_history)[-5:]]
        older = [s['sentiment'] for s in list(self.sentiment_history)[-10:-5]]
        
        if not older:
            return 0.0
        
        recent_avg = np.mean(recent)
        older_avg = np.mean(older)
        
        return recent_avg - older_avg

# ============= Portfolio Optimization Engine =============

class PortfolioOptimizer:
    """Modern portfolio theory optimization"""
    
    def __init__(self, market_data: MarketDataProvider):
        self.market_data = market_data
        self.returns_cache = {}
        
    async def optimize_portfolio(self, symbols: List[str], 
                                 target_return: float = None,
                                 risk_free_rate: float = 0.02) -> Dict:
        """Optimize portfolio using Markowitz optimization"""
        
        # Get historical returns
        returns = await self._get_returns_matrix(symbols)
        
        if returns.empty:
            return {'error': 'Insufficient data for optimization'}
        
        # Calculate expected returns and covariance
        expected_returns = returns.mean() * 252  # Annualized
        covariance = returns.cov() * 252
        
        # Number of assets
        n_assets = len(symbols)
        
        # Generate random portfolios for efficient frontier
        n_portfolios = 5000
        results = np.zeros((3, n_portfolios))
        
        for i in range(n_portfolios):
            # Random weights
            weights = np.random.random(n_assets)
            weights /= np.sum(weights)
            
            # Portfolio return and risk
            portfolio_return = np.sum(weights * expected_returns)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(covariance, weights)))
            
            # Sharpe ratio
            sharpe = (portfolio_return - risk_free_rate) / portfolio_std
            
            results[0, i] = portfolio_return
            results[1, i] = portfolio_std
            results[2, i] = sharpe
        
        # Find optimal portfolios
        max_sharpe_idx = np.argmax(results[2])
        min_vol_idx = np.argmin(results[1])
        
        # Calculate optimal weights
        optimal_weights = await self._calculate_optimal_weights(
            expected_returns, covariance, risk_free_rate
        )
        
        return {
            'efficient_frontier': {
                'returns': results[0].tolist(),
                'risks': results[1].tolist(),
                'sharpe_ratios': results[2].tolist()
            },
            'max_sharpe': {
                'return': results[0, max_sharpe_idx],
                'risk': results[1, max_sharpe_idx],
                'sharpe': results[2, max_sharpe_idx]
            },
            'min_volatility': {
                'return': results[0, min_vol_idx],
                'risk': results[1, min_vol_idx],
                'sharpe': results[2, min_vol_idx]
            },
            'optimal_weights': optimal_weights,
            'symbols': symbols
        }
    
    async def _get_returns_matrix(self, symbols: List[str]) -> pd.DataFrame:
        """Get historical returns for symbols"""
        returns_dict = {}
        
        for symbol in symbols:
            if symbol in self.returns_cache:
                returns_dict[symbol] = self.returns_cache[symbol]
            else:
                # Get historical data
                hist_data = await self.market_data.get_historical_data(symbol, period='1d')
                returns = hist_data['close'].pct_change().dropna()
                returns_dict[symbol] = returns
                self.returns_cache[symbol] = returns
        
        return pd.DataFrame(returns_dict)
    
    async def _calculate_optimal_weights(self, expected_returns: pd.Series, 
                                         covariance: pd.DataFrame,
                                         risk_free_rate: float) -> Dict[str, float]:
        """Calculate optimal weights using quadratic programming"""
        from scipy.optimize import minimize
        
        n_assets = len(expected_returns)
        
        def objective(weights):
            portfolio_return = np.sum(weights * expected_returns)
            portfolio_risk = np.sqrt(np.dot(weights.T, np.dot(covariance, weights)))
            return -(portfolio_return - risk_free_rate) / portfolio_risk
        
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum of weights = 1
        ]
        
        bounds = [(0, 1) for _ in range(n_assets)]
        
        result = minimize(
            objective,
            n_assets * [1. / n_assets],
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            return {symbol: weight for symbol, weight in zip(expected_returns.index, result.x)}
        else:
            return {}

# ============= Real-time Risk Monitor =============

class RealTimeRiskMonitor:
    """Real-time risk monitoring with alerts"""
    
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.risk_limits = {
            'var_limit': 0.05,  # 5% VaR limit
            'concentration_limit': 0.25,  # 25% concentration limit
            'correlation_limit': 0.8,  # 80% correlation limit
            'leverage_limit': 2.0,  # 2x leverage limit
            'volatility_limit': 0.5  # 50% volatility limit
        }
        self.risk_events = []
        self.monitoring_active = False
        
    async def start_monitoring(self):
        """Start real-time risk monitoring"""
        self.monitoring_active = True
        
        while self.monitoring_active:
            try:
                # Get current positions
                positions = self.risk_manager.db.get_positions()
                
                if positions:
                    # Check each risk metric
                    risks = await self._check_all_risks(positions)
                    
                    # Trigger alerts for exceeded limits
                    for risk_name, risk_data in risks.items():
                        if risk_data['exceeded']:
                            await self._trigger_risk_alert(risk_name, risk_data)
                    
                    # Log risk snapshot
                    self._log_risk_snapshot(risks)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in risk monitoring: {e}")
                await asyncio.sleep(5)
    
    async def _check_all_risks(self, positions: List[Dict]) -> Dict:
        """Check all risk metrics"""
        risks = {}
        
        # Value at Risk
        var = await self.risk_manager.calculate_var(positions)
        risks['var'] = {
            'value': var,
            'limit': self.risk_limits['var_limit'],
            'exceeded': var > self.risk_limits['var_limit'],
            'severity': var / self.risk_limits['var_limit']
        }
        
        # Concentration risk
        total_value = sum(p['quantity'] * p['current_price'] for p in positions)
        for pos in positions:
            pos_value = pos['quantity'] * pos['current_price']
            concentration = pos_value / total_value if total_value > 0 else 0
            if concentration > self.risk_limits['concentration_limit']:
                risks[f'concentration_{pos["symbol"]}'] = {
                    'value': concentration,
                    'limit': self.risk_limits['concentration_limit'],
                    'exceeded': True,
                    'symbol': pos['symbol']
                }
        
        # Leverage risk
        leverage = total_value / self.risk_manager.profile.max_position_size
        risks['leverage'] = {
            'value': leverage,
            'limit': self.risk_limits['leverage_limit'],
            'exceeded': leverage > self.risk_limits['leverage_limit']
        }
        
        # Volatility risk
        volatilities = await self._calculate_portfolio_volatility(positions)
        risks['volatility'] = {
            'value': volatilities['annualized'],
            'limit': self.risk_limits['volatility_limit'],
            'exceeded': volatilities['annualized'] > self.risk_limits['volatility_limit'],
            'daily': volatilities['daily']
        }
        
        return risks
    
    async def _trigger_risk_alert(self, risk_name: str, risk_data: Dict):
        """Trigger alert for risk limit breach"""
        alert = {
            'timestamp': datetime.now(),
            'risk_type': risk_name,
            'details': risk_data,
            'severity': 'high' if risk_data.get('severity', 1) > 1.5 else 'medium'
        }
        
        self.risk_events.append(alert)
        
        # Log alert
        logger.warning(f"Risk alert: {risk_name} - {risk_data}")
        
        # Send webhook notification
        if hasattr(self.risk_manager, 'webhook_sender'):
            await self.risk_manager.webhook_sender.send_webhook_with_retry(
                "https://your-webhook-url.com/risk-alert",
                alert
            )
    
    def _log_risk_snapshot(self, risks: Dict):
        """Log risk snapshot for monitoring"""
        # Store in database or time-series DB
        pass
    
    async def _calculate_portfolio_volatility(self, positions: List[Dict]) -> Dict:
        """Calculate portfolio volatility"""
        if not positions:
            return {'daily': 0, 'annualized': 0}
        
        # Get returns for all positions
        returns_list = []
        for pos in positions:
            hist_data = await self.risk_manager.market_data.get_historical_data(
                pos['symbol'], period='1d'
            )
            returns = hist_data['close'].pct_change().dropna()
            returns_list.append(returns)
        
        if returns_list:
            # Calculate portfolio returns (simplified)
            portfolio_returns = pd.DataFrame(returns_list).mean(axis=0)
            daily_vol = portfolio_returns.std()
            annualized_vol = daily_vol * np.sqrt(252)
            
            return {'daily': daily_vol, 'annualized': annualized_vol}
        
        return {'daily': 0, 'annualized': 0}

# ============= Automated Trading Strategies =============

class AutomatedStrategies:
    """Automated trading strategies with AI integration"""
    
    def __init__(self, order_manager: OrderManager, ai_agent: AIAgent):
        self.order_manager = order_manager
        self.ai_agent = ai_agent
        self.active_strategies = {}
        
    async def momentum_strategy(self, symbol: str, lookback: int = 20,
                                 threshold: float = 0.05) -> Dict:
        """Momentum-based trading strategy"""
        # Get historical data
        hist_data = await self.order_manager.market_data.get_historical_data(symbol)
        
        if len(hist_data) < lookback:
            return {'status': 'insufficient_data'}
        
        # Calculate momentum
        returns = hist_data['close'].pct_change(lookback).iloc[-1]
        
        # Get AI analysis for confirmation
        ai_analysis = await self.ai_agent.analyze_market(symbol)
        
        if returns > threshold and ai_analysis['sentiment'] == 'bullish':
            # Buy signal
            position_size = await self._calculate_position_size(symbol)
            order = Order(
                symbol=symbol,
                side='buy',
                order_type='market',
                quantity=position_size
            )
            result = await self.order_manager.place_order(order)
            return {'action': 'buy', 'momentum': returns, 'result': result}
            
        elif returns < -threshold and ai_analysis['sentiment'] == 'bearish':
            # Sell signal
            position_size = await self._calculate_position_size(symbol)
            order = Order(
                symbol=symbol,
                side='sell',
                order_type='market',
                quantity=position_size
            )
            result = await self.order_manager.place_order(order)
            return {'action': 'sell', 'momentum': returns, 'result': result}
        
        return {'action': 'hold', 'momentum': returns}
    
    async def mean_reversion_strategy(self, symbol: str, lookback: int = 20,
                                       zscore_threshold: float = 2.0) -> Dict:
        """Mean reversion trading strategy"""
        hist_data = await self.order_manager.market_data.get_historical_data(symbol)
        
        if len(hist_data) < lookback:
            return {'status': 'insufficient_data'}
        
        # Calculate z-score
        sma = hist_data['close'].rolling(lookback).mean()
        std = hist_data['close'].rolling(lookback).std()
        zscore = (hist_data['close'] - sma) / std
        current_zscore = zscore.iloc[-1]
        
        # Get current position
        positions = self.order_manager.db.get_positions()
        current_position = next((p for p in positions if p['symbol'] == symbol), None)
        
        if current_zscore > zscore_threshold:
            # Overbought - sell
            if current_position and current_position['quantity'] > 0:
                order = Order(
                    symbol=symbol,
                    side='sell',
                    order_type='market',
                    quantity=current_position['quantity']
                )
                result = await self.order_manager.place_order(order)
                return {'action': 'sell', 'zscore': current_zscore, 'result': result}
                
        elif current_zscore < -zscore_threshold:
            # Oversold - buy
            position_size = await self._calculate_position_size(symbol)
            order = Order(
                symbol=symbol,
                side='buy',
                order_type='market',
                quantity=position_size
            )
            result = await self.order_manager.place_order(order)
            return {'action': 'buy', 'zscore': current_zscore, 'result': result}
        
        return {'action': 'hold', 'zscore': current_zscore}
    
    async def _calculate_position_size(self, symbol: str) -> float:
        """Calculate position size based on risk"""
        current_price = await self.order_manager.market_data.get_current_price(symbol)
        risk_amount = self.order_manager.risk_manager.profile.max_position_size * \
                     self.order_manager.risk_manager.profile.risk_per_trade
        
        position_size = risk_amount / current_price
        return position_size

# ============= Performance Analytics =============

class PerformanceAnalytics:
    """Advanced performance analytics and reporting"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        
    def calculate_sharpe_ratio(self, returns: List[float], 
                               risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if not returns:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return sharpe
    
    def calculate_sortino_ratio(self, returns: List[float]) -> float:
        """Calculate Sortino ratio (downside risk)"""
        if not returns:
            return 0.0
        
        returns_array = np.array(returns)
        downside_returns = returns_array[returns_array < 0]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_deviation = np.std(downside_returns)
        sortino = np.mean(returns_array) / downside_deviation * np.sqrt(252)
        return sortino
    
    def calculate_calmar_ratio(self, annual_return: float, 
                               max_drawdown: float) -> float:
        """Calculate Calmar ratio"""
        if max_drawdown == 0:
            return 0.0
        return annual_return / max_drawdown
    
    def calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate win rate"""
        if not trades:
            return 0.0
        
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        return len(winning_trades) / len(trades)
    
    def calculate_profit_factor(self, trades: List[Dict]) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        
        if gross_loss == 0:
            return float('inf')
        
        return gross_profit / gross_loss
    
    def calculate_expected_value(self, trades: List[Dict]) -> float:
        """Calculate expected value per trade"""
        if not trades:
            return 0.0
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        return total_pnl / len(trades)
    
    def generate_performance_report(self, start_date: datetime, 
                                    end_date: datetime) -> Dict:
        """Generate comprehensive performance report"""
        # Get trades in period
        orders = self.db.get_orders()
        trades = [o for o in orders if o.get('status') == 'filled']
        
        # Filter by date
        trades_in_period = [t for t in trades if start_date <= t.get('created_at') <= end_date]
        
        # Calculate metrics
        returns = [self._calculate_trade_return(t) for t in trades_in_period]
        pnls = [t.get('quantity', 0) * (t.get('price', 0) - t.get('avg_price', 0)) 
                for t in trades_in_period]
        
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'performance': {
                'total_trades': len(trades_in_period),
                'winning_trades': len([p for p in pnls if p > 0]),
                'losing_trades': len([p for p in pnls if p < 0]),
                'win_rate': self.calculate_win_rate(trades_in_period),
                'profit_factor': self.calculate_profit_factor(trades_in_period),
                'expected_value': self.calculate_expected_value(trades_in_period),
                'total_pnl': sum(pnls),
                'average_win': np.mean([p for p in pnls if p > 0]) if pnls else 0,
                'average_loss': np.mean([p for p in pnls if p < 0]) if pnls else 0
            },
            'risk_metrics': {
                'sharpe_ratio': self.calculate_sharpe_ratio(returns),
                'sortino_ratio': self.calculate_sortino_ratio(returns),
                'max_drawdown': self._calculate_max_drawdown(pnls),
                'volatility': np.std(returns) if returns else 0
            }
        }
        
        return report
    
    def _calculate_trade_return(self, trade: Dict) -> float:
        """Calculate return for a trade"""
        if trade.get('avg_price', 0) == 0:
            return 0.0
        return (trade.get('price', 0) - trade.get('avg_price', 0)) / trade.get('avg_price', 1)
    
    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not pnls:
            return 0.0
        
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(np.min(drawdown)) if len(drawdown) > 0 else 0.0

# ============= CI/CD Pipeline Configuration =============

"""
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  DOCKER_REGISTRY: ghcr.io
  IMAGE_NAME: trading-agent

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
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
        pytest --cov=. --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Log in to GitHub Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.DOCKER_REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: .
        file: Dockerfile.prod
        push: true
        tags: |
          ${{ env.DOCKER_REGISTRY }}/${{ github.repository }}:latest
          ${{ env.DOCKER_REGISTRY }}/${{ github.repository }}:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Kubernetes
      env:
        KUBE_CONFIG: ${{ secrets.KUBE_CONFIG }}
      run: |
        echo "$KUBE_CONFIG" | base64 --decode > kubeconfig
        kubectl --kubeconfig=kubeconfig set image deployment/trading-agent \
          trading-agent=${{ env.DOCKER_REGISTRY }}/${{ github.repository }}:${{ github.sha }}
        kubectl --kubeconfig=kubeconfig rollout status deployment/trading-agent
"""

# ============= API Documentation =============

"""
# API Documentation

## Trading Agent API

### Orders

#### Place Market Order
```http
POST /api/orders/market
Content-Type: application/json

{
    "symbol": "BTCUSD",
    "side": "buy",
    "quantity": 0.1
}