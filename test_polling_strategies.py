#!/usr/bin/env python3
"""
Test script for polling strategy pattern implementation
Tests all strategy types and their behavior under different conditions
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from polling_strategies import (
    PollingStrategy, PollingContext, PollingDecision,
    PollingStrategyType, PollingStrategyFactory,
    FixedIntervalStrategy, ExponentialBackoffStrategy,
    AdaptiveStrategy, ScheduledWindowsStrategy,
    DEFAULT_STRATEGY_CONFIGS
)


def test_fixed_interval_strategy():
    """Test fixed interval strategy"""
    print("🧪 Testing FixedIntervalStrategy...")
    
    strategy = FixedIntervalStrategy(interval_minutes=5)
    
    # Test basic functionality
    assert strategy.get_strategy_type() == PollingStrategyType.FIXED_INTERVAL
    
    context = PollingContext()
    decision = strategy.decide_next_poll(context)
    
    assert decision.should_poll == True
    assert decision.wait_time_seconds == 300  # 5 minutes
    assert "Fixed interval" in decision.reason
    assert decision.metadata["interval_minutes"] == 5
    
    # Test configuration
    strategy.configure({"interval_minutes": 10})
    config = strategy.get_configuration()
    assert config["interval_minutes"] == 10
    
    decision = strategy.decide_next_poll(context)
    assert decision.wait_time_seconds == 600  # 10 minutes
    
    print("✅ FixedIntervalStrategy tests passed")


def test_exponential_backoff_strategy():
    """Test exponential backoff strategy"""
    print("🧪 Testing ExponentialBackoffStrategy...")
    
    strategy = ExponentialBackoffStrategy(
        base_interval_minutes=2,
        max_interval_minutes=32,
        backoff_multiplier=2.0
    )
    
    assert strategy.get_strategy_type() == PollingStrategyType.EXPONENTIAL_BACKOFF
    
    # Test with no failures
    context = PollingContext(consecutive_failures=0, consecutive_successes=1)
    decision = strategy.decide_next_poll(context)
    assert decision.wait_time_seconds == 120  # 2 minutes base
    
    # Test with failures
    context = PollingContext(consecutive_failures=2)
    decision = strategy.decide_next_poll(context)
    expected_interval = 2 * (2.0 ** 2)  # 8 minutes
    assert decision.wait_time_seconds == expected_interval * 60
    assert "failures: 2" in decision.reason
    
    # Test max interval cap
    context = PollingContext(consecutive_failures=10)  # Would be very large
    decision = strategy.decide_next_poll(context)
    assert decision.wait_time_seconds == 32 * 60  # Capped at max
    
    # Test configuration
    strategy.configure({
        "base_interval_minutes": 1,
        "max_interval_minutes": 16,
        "backoff_multiplier": 1.5
    })
    config = strategy.get_configuration()
    assert config["base_interval_minutes"] == 1
    assert config["backoff_multiplier"] == 1.5
    
    print("✅ ExponentialBackoffStrategy tests passed")


def test_adaptive_strategy():
    """Test adaptive strategy"""
    print("🧪 Testing AdaptiveStrategy...")
    
    strategy = AdaptiveStrategy(
        base_interval_minutes=5,
        min_interval_minutes=1,
        max_interval_minutes=30,
        queue_threshold=5
    )
    
    assert strategy.get_strategy_type() == PollingStrategyType.ADAPTIVE
    
    # Test with empty queue
    context = PollingContext(queue_depth=0)
    decision = strategy.decide_next_poll(context)
    # Should be longer than base (5 * 1.5 = 7.5 minutes)
    assert decision.wait_time_seconds > 5 * 60
    assert "empty queue" in decision.reason
    
    # Test with high queue depth
    context = PollingContext(queue_depth=10)  # Above threshold of 5
    decision = strategy.decide_next_poll(context)
    # Should be shorter than base
    assert decision.wait_time_seconds < 5 * 60
    assert "high queue depth" in decision.reason
    
    # Test with high system load
    context = PollingContext(system_load=0.9, queue_depth=3)
    decision = strategy.decide_next_poll(context)
    # Should be longer due to high load
    assert decision.wait_time_seconds > 5 * 60
    assert "high system load" in decision.reason
    
    # Test bounds enforcement
    context = PollingContext(queue_depth=100)  # Extreme value
    decision = strategy.decide_next_poll(context)
    # Should respect minimum bound
    assert decision.wait_time_seconds >= 1 * 60
    
    print("✅ AdaptiveStrategy tests passed")


def test_scheduled_windows_strategy():
    """Test scheduled windows strategy"""
    print("🧪 Testing ScheduledWindowsStrategy...")
    
    # Create a strategy with specific windows
    windows = [
        {"start_hour": 9, "end_hour": 17, "days": [0, 1, 2, 3, 4]},  # Mon-Fri 9-5
        {"start_hour": 10, "end_hour": 14, "days": [5]}  # Saturday 10-2
    ]
    
    strategy = ScheduledWindowsStrategy(windows=windows, interval_minutes=10)
    
    assert strategy.get_strategy_type() == PollingStrategyType.SCHEDULED_WINDOWS
    
    # Mock current time to test different scenarios
    # We can't easily mock datetime.now() in this simple test,
    # so we'll test the configuration and basic functionality
    
    context = PollingContext()
    decision = strategy.decide_next_poll(context)
    
    # Decision should either be to poll now or wait
    assert isinstance(decision.should_poll, bool)
    assert decision.wait_time_seconds >= 0
    
    if decision.should_poll:
        assert "Active window" in decision.reason
        assert decision.metadata["in_window"] == True
    else:
        assert "Outside polling window" in decision.reason
        assert decision.metadata["in_window"] == False
    
    # Test configuration
    new_windows = [{"start_hour": 8, "end_hour": 18, "days": [0, 1, 2, 3, 4]}]
    strategy.configure({"windows": new_windows, "interval_minutes": 15})
    config = strategy.get_configuration()
    assert config["windows"] == new_windows
    assert config["interval_minutes"] == 15
    
    print("✅ ScheduledWindowsStrategy tests passed")


def test_strategy_factory():
    """Test polling strategy factory"""
    print("🧪 Testing PollingStrategyFactory...")
    
    # Test getting available strategies
    available = PollingStrategyFactory.get_available_strategies()
    assert PollingStrategyType.FIXED_INTERVAL in available
    assert PollingStrategyType.EXPONENTIAL_BACKOFF in available
    assert PollingStrategyType.ADAPTIVE in available
    assert PollingStrategyType.SCHEDULED_WINDOWS in available
    
    # Test creating strategies
    fixed_strategy = PollingStrategyFactory.create_strategy(
        PollingStrategyType.FIXED_INTERVAL,
        {"interval_minutes": 3}
    )
    assert isinstance(fixed_strategy, FixedIntervalStrategy)
    assert fixed_strategy.get_configuration()["interval_minutes"] == 3
    
    adaptive_strategy = PollingStrategyFactory.create_strategy(
        PollingStrategyType.ADAPTIVE,
        {"base_interval_minutes": 10}
    )
    assert isinstance(adaptive_strategy, AdaptiveStrategy)
    assert adaptive_strategy.get_configuration()["base_interval_minutes"] == 10
    
    # Test invalid strategy type
    try:
        PollingStrategyFactory.create_strategy("invalid_strategy")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported strategy type" in str(e)
    
    print("✅ PollingStrategyFactory tests passed")


def test_default_configurations():
    """Test default strategy configurations"""
    print("🧪 Testing default configurations...")
    
    # Test that all default configs can create working strategies
    for strategy_type, config in DEFAULT_STRATEGY_CONFIGS.items():
        strategy = PollingStrategyFactory.create_strategy(strategy_type, config)
        
        # Test basic operation
        context = PollingContext()
        decision = strategy.decide_next_poll(context)
        
        assert isinstance(decision, PollingDecision)
        assert decision.wait_time_seconds >= 0
        assert isinstance(decision.reason, str)
        assert isinstance(decision.metadata, dict)
        
        # Test configuration retrieval
        retrieved_config = strategy.get_configuration()
        assert isinstance(retrieved_config, dict)
    
    print("✅ Default configurations tests passed")


def test_polling_context():
    """Test polling context functionality"""
    print("🧪 Testing PollingContext...")
    
    context = PollingContext(
        consecutive_failures=3,
        consecutive_successes=0,
        total_polls=50,
        queue_depth=7,
        last_poll_duration=2.5,
        average_processing_time=45.0,
        system_load=0.65,
        error_rate=0.06
    )
    
    # Test that context data is preserved
    assert context.consecutive_failures == 3
    assert context.queue_depth == 7
    assert context.error_rate == 0.06
    
    # Test with different strategies
    strategies = [
        FixedIntervalStrategy(interval_minutes=2),
        ExponentialBackoffStrategy(),
        AdaptiveStrategy(queue_threshold=5),
    ]
    
    for strategy in strategies:
        decision = strategy.decide_next_poll(context)
        
        # All strategies should handle the context without error
        assert isinstance(decision, PollingDecision)
        assert decision.wait_time_seconds > 0
    
    print("✅ PollingContext tests passed")


def test_strategy_state_management():
    """Test strategy state management"""
    print("🧪 Testing strategy state management...")
    
    # Test exponential backoff state reset
    backoff_strategy = ExponentialBackoffStrategy(base_interval_minutes=1)
    
    # Cause some backoff
    context = PollingContext(consecutive_failures=3)
    decision1 = backoff_strategy.decide_next_poll(context)
    
    # Reset state
    backoff_strategy.reset_state()
    
    # Should be back to base interval
    context = PollingContext(consecutive_failures=0)
    decision2 = backoff_strategy.decide_next_poll(context)
    
    assert decision2.wait_time_seconds <= decision1.wait_time_seconds
    
    # Test metrics retrieval (base implementation returns empty dict)
    metrics = backoff_strategy.get_metrics()
    assert isinstance(metrics, dict)
    
    print("✅ Strategy state management tests passed")


def performance_benchmark():
    """Basic performance benchmark for strategies"""
    print("🧪 Running performance benchmark...")
    
    import time
    
    strategies = [
        FixedIntervalStrategy(),
        ExponentialBackoffStrategy(),
        AdaptiveStrategy(),
    ]
    
    context = PollingContext(
        consecutive_failures=2,
        queue_depth=10,
        system_load=0.7,
        error_rate=0.05
    )
    
    iterations = 1000
    
    for strategy in strategies:
        start_time = time.time()
        
        for _ in range(iterations):
            decision = strategy.decide_next_poll(context)
        
        end_time = time.time()
        duration = end_time - start_time
        ops_per_second = iterations / duration
        
        print(f"   📊 {strategy.get_strategy_type().value}: "
              f"{ops_per_second:.1f} decisions/sec ({duration:.4f}s total)")
    
    print("✅ Performance benchmark completed")


def main():
    """Run all tests"""
    print("🚀 Starting polling strategy pattern tests...\n")
    
    try:
        test_fixed_interval_strategy()
        test_exponential_backoff_strategy()
        test_adaptive_strategy()
        test_scheduled_windows_strategy()
        test_strategy_factory()
        test_default_configurations()
        test_polling_context()
        test_strategy_state_management()
        performance_benchmark()
        
        print("\n🎉 All polling strategy tests passed successfully!")
        print("✅ Polling Strategy Pattern implementation is working correctly")
        
        # Demo the strategy factory
        print("\n📋 Strategy Pattern Demo:")
        
        for strategy_type in PollingStrategyFactory.get_available_strategies():
            strategy = PollingStrategyFactory.create_strategy(
                strategy_type, 
                DEFAULT_STRATEGY_CONFIGS.get(strategy_type, {})
            )
            
            context = PollingContext(consecutive_failures=1, queue_depth=3)
            decision = strategy.decide_next_poll(context)
            
            print(f"   🎯 {strategy_type.value}:")
            print(f"      ⏱️  Wait time: {decision.wait_time_seconds/60:.1f} minutes")
            print(f"      📝 Reason: {decision.reason}")
            print(f"      🔄 Should poll: {decision.should_poll}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)