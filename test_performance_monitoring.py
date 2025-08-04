#!/usr/bin/env python3
"""
Test script for performance monitoring functionality
"""
import time
import threading
from src.performance_monitor import PerformanceMonitor
from src.performance_integration import (
    initialize_performance_monitoring,
    integrate_all_components,
    log_performance_summary,
    PerformanceContext,
    performance_tracked
)


@performance_tracked("test_function")
def simulate_work(duration: float):
    """Simulate some work that takes time."""
    print(f"⚙️ Simulating work for {duration:.2f} seconds...")
    time.sleep(duration)
    return f"Work completed in {duration:.2f}s"


def test_basic_monitoring():
    """Test basic performance monitoring functionality."""
    print("🧪 Testing basic performance monitoring...")
    
    # Initialize monitoring
    monitor = initialize_performance_monitoring(
        collection_interval=0.5,  # Fast collection for testing
        history_size=100,
        enable_auto_gc=True,
        auto_start=True
    )
    
    print("✅ Performance monitoring initialized")
    
    # Test manual task timing
    task_id = monitor.start_task_timing("manual_test_task")
    time.sleep(1.0)
    duration = monitor.end_task_timing(task_id)
    print(f"✅ Manual task timing: {duration:.2f}s")
    
    # Test context manager
    with PerformanceContext("context_test"):
        time.sleep(0.5)
    print("✅ Context manager test completed")
    
    # Test decorator
    result = simulate_work(0.3)
    print(f"✅ Decorator test: {result}")
    
    # Wait for some metrics to be collected
    print("⏳ Collecting metrics for 3 seconds...")
    time.sleep(3.0)
    
    # Get performance summary
    summary = monitor.get_performance_summary()
    print(f"📊 Metrics collected: {summary['metrics_collected']}")
    print(f"📊 Active tasks: {summary['active_tasks']}")
    print(f"📊 Completed tasks: {summary['completed_tasks']}")
    
    # Get task statistics
    task_stats = monitor.get_task_performance_stats()
    print(f"📊 Task statistics: {task_stats}")
    
    # Log comprehensive summary
    log_performance_summary()
    
    # Test optimization
    optimization_results = monitor.optimize_performance()
    print(f"🔧 Optimization results: {optimization_results}")
    
    monitor.stop_monitoring()
    print("✅ Basic monitoring test completed")


def test_concurrent_monitoring():
    """Test performance monitoring with concurrent operations."""
    print("🧪 Testing concurrent performance monitoring...")
    
    monitor = initialize_performance_monitoring(
        collection_interval=0.2,
        history_size=200,
        auto_start=True
    )
    
    def worker_task(worker_id: int, iterations: int):
        """Worker function for concurrent testing."""
        for i in range(iterations):
            with PerformanceContext(f"worker_{worker_id}_task_{i}"):
                # Simulate varying workloads
                work_time = 0.1 + (i % 3) * 0.1
                time.sleep(work_time)
        print(f"✅ Worker {worker_id} completed {iterations} tasks")
    
    # Start multiple worker threads
    threads = []
    for worker_id in range(3):
        thread = threading.Thread(
            target=worker_task,
            args=(worker_id, 5),
            name=f"Worker-{worker_id}"
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all workers to complete
    for thread in threads:
        thread.join()
    
    # Wait for final metrics collection
    time.sleep(2.0)
    
    # Get final statistics
    task_stats = monitor.get_task_performance_stats()
    print(f"📊 Concurrent test completed tasks: {task_stats['total_completed']}")
    print(f"📊 Average duration: {task_stats['average_duration']:.3f}s")
    print(f"📊 SLA compliance: {task_stats['sla_compliance_rate']:.1f}%")
    
    # Check for any alerts
    alerts = monitor.get_recent_alerts(hours=1)
    if alerts:
        print(f"⚠️ Performance alerts generated: {len(alerts)}")
        for alert in alerts[-3:]:  # Show last 3 alerts
            print(f"   [{alert.alert_type.value}] {alert.message}")
    else:
        print("✅ No performance alerts during concurrent test")
    
    log_performance_summary()
    monitor.stop_monitoring()
    print("✅ Concurrent monitoring test completed")


def test_stress_monitoring():
    """Test performance monitoring under stress conditions."""
    print("🧪 Testing stress performance monitoring...")
    
    monitor = initialize_performance_monitoring(
        collection_interval=0.1,  # Very fast collection
        history_size=500,
        enable_auto_gc=True,
        auto_start=True
    )
    
    # Generate a lot of short tasks to stress the system
    print("⚡ Generating high-frequency tasks...")
    
    for batch in range(5):
        batch_start = time.time()
        
        # Rapid task generation
        for i in range(20):
            task_id = monitor.start_task_timing(f"stress_batch_{batch}_task_{i}")
            # Very short tasks
            time.sleep(0.01)
            monitor.end_task_timing(task_id)
        
        batch_duration = time.time() - batch_start
        print(f"   Batch {batch + 1}: 20 tasks in {batch_duration:.3f}s")
        
        # Brief pause between batches
        time.sleep(0.1)
    
    # Wait for metrics collection
    time.sleep(1.0)
    
    # Check system performance under stress
    summary = monitor.get_performance_summary()
    task_stats = monitor.get_task_performance_stats()
    
    print(f"📊 Stress test results:")
    print(f"   Total tasks: {task_stats['total_completed']}")
    print(f"   Metrics collected: {summary['metrics_collected']}")
    print(f"   Memory usage: {summary['current_metrics'].get('memory_usage_percent', {}).get('value', 'N/A')}%")
    print(f"   CPU usage: {summary['current_metrics'].get('cpu_usage_percent', {}).get('value', 'N/A')}%")
    
    # Test optimization under stress
    optimization = monitor.optimize_performance()
    print(f"🔧 Stress optimization: {len(optimization['actions_taken'])} actions")
    
    # Check for performance alerts
    alerts = monitor.get_recent_alerts(hours=1)
    print(f"⚠️ Alerts during stress test: {len(alerts)}")
    
    monitor.stop_monitoring()
    print("✅ Stress monitoring test completed")


def test_integration():
    """Test integration with existing components."""
    print("🧪 Testing component integration...")
    
    # Initialize monitoring and integration
    initialize_performance_monitoring(auto_start=True)
    integrate_all_components()
    
    print("✅ Component integration completed")
    
    # Note: Full integration testing would require the actual components
    # This is a placeholder for integration verification
    print("ℹ️ Integration test requires actual components (StatusTransitionManager, etc.)")
    print("ℹ️ Integration monkey-patches have been applied successfully")
    
    log_performance_summary()
    print("✅ Integration test completed")


def main():
    """Run all performance monitoring tests."""
    print("🚀 Starting Performance Monitoring Test Suite")
    print("=" * 60)
    
    try:
        test_basic_monitoring()
        print("\n" + "-" * 60 + "\n")
        
        test_concurrent_monitoring()
        print("\n" + "-" * 60 + "\n")
        
        test_stress_monitoring()
        print("\n" + "-" * 60 + "\n")
        
        test_integration()
        print("\n" + "=" * 60)
        
        print("🎉 All performance monitoring tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())