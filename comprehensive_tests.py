# comprehensive_tests.py - Complete Test Suite
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

class TestPerformance:
    """Performance and load tests"""
    
    @pytest.mark.performance
    async def test_order_throughput(self):
        """Test order processing throughput"""
        order_manager = OrderManager(DatabaseManager(':memory:'), RiskManager())
        
        start_time = time.time()
        orders_placed = 0
        
        # Place 1000 orders
        for i in range(1000):
            order = Order(
                symbol=f"TEST{i}",
                side='buy',
                order_type='market',
                quantity=0.1
            )
            await order_manager.place_order(order)
            orders_placed += 1
        
        elapsed = time.time() - start_time
        throughput = orders_placed / elapsed
        
        assert throughput > 100  # At least 100 orders per second
        print(f"Order throughput: {throughput:.2f} orders/sec")
    
    @pytest.mark.performance
    async def test_market_data_latency(self):
        """Test market data retrieval latency"""
        market_data = MarketDataProvider()
        
        latencies = []
        for _ in range(100):
            start = time.time()
            await market_data.get_current_price("BTCUSD")
            latencies.append((time.time() - start) * 1000)  # Convert to ms
        
        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        
        assert avg_latency < 50  # Average latency under 50ms
        assert p95_latency < 100  # 95th percentile under 100ms
        
        print(f"Avg latency: {avg_latency:.2f}ms, P95: {p95_latency:.2f}ms")
    
    @pytest.mark.performance
    async def test_concurrent_orders(self):
        """Test concurrent order processing"""
        order_manager = OrderManager(DatabaseManager(':memory:'), RiskManager())
        
        async def place_order(i):
            order = Order(
                symbol=f"BTCUSD",
                side='buy',
                order_type='market',
                quantity=0.1
            )
            return await order_manager.place_order(order)
        
        start_time = time.time()
        results = await asyncio.gather(*[place_order(i) for i in range(100)])
        elapsed = time.time() - start_time
        
        success_count = sum(1 for r in results if r.get('success'))
        assert success_count == 100
        assert elapsed < 5  # 100 concurrent orders under 5 seconds

class TestSecurity:
    """Security and encryption tests"""
    
    def test_password_hashing(self):
        """Test password hashing"""
        security = SecurityManager()
        
        password = "test_password_123"
        hashed = security.hash_password(password)
        
        assert hashed != password
        assert security.verify_password(password, hashed)
        assert not security.verify_password("wrong_password", hashed)
    
    def test_encryption(self):
        """Test data encryption"""
        security = SecurityManager()
        
        original = "sensitive_data_123"
        encrypted = security.encrypt(original)
        
        assert encrypted != original
        decrypted = security.decrypt(encrypted)
        assert decrypted == original
    
    def test_api_key_generation(self):
        """Test API key generation"""
        security = SecurityManager()
        
        key1 = security.generate_api_key()
        key2 = security.generate_api_key()
        
        assert len(key1) == 43  # URL-safe base64 length
        assert key1 != key2
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting"""
        security = SecurityManager()
        
        # Make 100 requests
        for i in range(100):
            allowed = security.rate_limit_check("test_key", limit=100, window=60)
            assert allowed
        
        # 101st request should be rate limited
        allowed = security.rate_limit_check("test_key", limit=100, window=60)
        assert not allowed

class TestErrorHandling:
    """Error handling tests"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """Test circuit breaker pattern"""
        error_handler = ErrorHandler()
        
        failures = 0
        
        @error_handler.circuit_breaker("test_service", failure_threshold=3, recovery_timeout=5)
        async def flaky_service():
            nonlocal failures
            failures += 1
            if failures <= 3:
                raise Exception("Service failed")
            return "success"
        
        # First 3 calls should fail
        for i in range(3):
            with pytest.raises(Exception):
                await flaky_service()
        
        # Circuit should be open
        with pytest.raises(TradingError) as exc_info:
            await flaky_service()
        assert "circuit breaker" in str(exc_info.value).lower()
        
        # Wait for recovery
        await asyncio.sleep(6)
        
        # Should work now
        result = await flaky_service()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery mechanisms"""
        recovery = DisasterRecoverySystem(DatabaseManager(':memory:'), OrderManager())
        
        # Create checkpoint
        checkpoint_id = await recovery.create_checkpoint()
        assert checkpoint_id is not None
        
        # Simulate failure by deleting data
        # (implementation depends on actual system)
        
        # Recover
        result = await recovery.recover_from_checkpoint(checkpoint_id)
        assert result is True

class TestIntegration:
    """End-to-end integration tests"""
    
    @pytest.mark.integration
    async def test_full_trading_workflow(self):
        """Test complete trading workflow"""
        # Initialize system
        db = DatabaseManager(':memory:')
        risk_manager = RiskManager(db)
        order_manager = OrderManager(db, risk_manager)
        alert_manager = AlertManager(db, order_manager)
        
        # Place order
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=0.1
        )
        result = await order_manager.place_order(order)
        assert result['success']
        
        # Verify position
        positions = db.get_positions()
        assert len(positions) == 1
        assert positions[0]['symbol'] == 'BTCUSD'
        
        # Create alert
        alert = Alert(
            alert_id=None,
            symbol='BTCUSD',
            condition_type='price_above',
            condition_value=60000,
            action='notify'
        )
        alert_result = await alert_manager.create_alert(alert)
        assert alert_result['success']
        
        # Get alerts
        alerts = db.get_alerts()
        assert len(alerts) == 1
        
        # Close position
        close_result = await order_manager.close_position('BTCUSD')
        assert close_result['success']
        
        # Verify position closed
        positions = db.get_positions()
        assert len(positions) == 0
    
    @pytest.mark.integration
    async def test_ai_analysis_integration(self):
        """Test AI analysis integration"""
        agent = AIAgent()
        
        result = await agent.analyze_market('BTCUSD')
        
        assert 'symbol' in result
        assert 'sentiment' in result
        assert 'recommendation' in result
        assert result['symbol'] == 'BTCUSD'
    
    @pytest.mark.integration
    async def test_risk_management_integration(self):
        """Test risk management integration"""
        db = DatabaseManager(':memory:')
        risk_profile = RiskProfile(max_position_size=1000, max_daily_loss=100)
        risk_manager = RiskManager(db, risk_profile)
        order_manager = OrderManager(db, risk_manager)
        
        # Try to place oversized order
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=100  # Would exceed position size
        )
        
        result = await order_manager.place_order(order)
        assert not result['success']
        assert 'exceeds' in result['message'].lower()
        
        # Place valid order
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=0.01
        )
        result = await order_manager.place_order(order)
        assert result['success']

class TestDataIntegrity:
    """Data integrity tests"""
    
    def test_order_consistency(self):
        """Test order data consistency"""
        db = DatabaseManager(':memory:')
        
        order = Order(
            symbol='BTCUSD',
            side='buy',
            order_type='market',
            quantity=0.1
        )
        
        db.save_order(order)
        
        saved_orders = db.get_orders()
        assert len(saved_orders) == 1
        
        saved = saved_orders[0]
        assert saved['symbol'] == order.symbol
        assert saved['quantity'] == order.quantity
        assert datetime.fromisoformat(saved['created_at']) == order.created_at
    
    def test_position_calculations(self):
        """Test position calculations"""
        position = Position(
            symbol='BTCUSD',
            quantity=1.0,
            avg_price=50000,
            current_price=51000,
            unrealized_pnl=1000
        )
        
        assert position.unrealized_pnl == 1000
        assert (position.current_price - position.avg_price) * position.quantity == 1000
    
    def test_alert_triggering(self):
        """Test alert triggering logic"""
        alert = Alert(
            alert_id='test',
            symbol='BTCUSD',
            condition_type='price_above',
            condition_value=50000,
            action='notify'
        )
        
        # Should trigger at 51000
        current_price = 51000
        should_trigger = (alert.condition_type == 'price_above' and 
                         current_price > alert.condition_value)
        assert should_trigger
        
        # Should not trigger at 49000
        current_price = 49000
        should_trigger = (alert.condition_type == 'price_above' and 
                         current_price > alert.condition_value)
        assert not should_trigger

# ============= Benchmark Suite =============

class BenchmarkSuite:
    """Performance benchmarking"""
    
    def __init__(self):
        self.results = []
        
    async def run_benchmark(self, name: str, func, iterations: int = 100):
        """Run benchmark"""
        times = []
        
        for i in range(iterations):
            start = time.time()
            await func()
            times.append(time.time() - start)
        
        avg_time = np.mean(times) * 1000  # Convert to ms
        p95_time = np.percentile(times, 95) * 1000
        throughput = iterations / np.sum(times)
        
        result = {
            'name': name,
            'avg_ms': avg_time,
            'p95_ms': p95_time,
            'throughput_ops_sec': throughput,
            'iterations': iterations
        }
        
        self.results.append(result)
        return result
    
    def print_results(self):
        """Print benchmark results"""
        table = Table(title="Benchmark Results")
        table.add_column("Test", style="cyan")
        table.add_column("Avg (ms)", justify="right")
        table.add_column("P95 (ms)", justify="right")
        table.add_column("Throughput (ops/sec)", justify="right")
        
        for result in self.results:
            table.add_row(
                result['name'],
                f"{result['avg_ms']:.2f}",
                f"{result['p95_ms']:.2f}",
                f"{result['throughput_ops_sec']:.2f}"
            )
        
        console.print(table)

# ============= Run Tests =============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=trading_agent", "--cov-report=html"])
    
    