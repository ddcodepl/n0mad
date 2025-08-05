#!/usr/bin/env python3
"""
Slack Integration Performance Benchmark

Provides comprehensive performance testing and benchmarking for the
Slack notification system under various load conditions.
"""

import time
import threading
import psutil
import statistics
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import argparse
import json

# Import the modules to benchmark
from core.managers.notification_manager import NotificationManager
from utils.slack_security import SlackSecurityManager
from core.services.slack_message_builder import SlackMessageBuilder, TaskStatusChangeData
from utils.slack_config import MessagePriority


@dataclass
class BenchmarkResult:
    """Results from a performance benchmark test."""
    test_name: str
    duration_seconds: float
    operations_count: int
    operations_per_second: float
    memory_usage_mb: float
    memory_peak_mb: float
    success_rate: float
    errors: List[str]
    metadata: Dict[str, Any]


class SlackPerformanceBenchmark:
    """
    Comprehensive performance benchmark suite for Slack integration.
    """
    
    def __init__(self):
        """Initialize the benchmark suite."""
        self.results: List[BenchmarkResult] = []
        self.process = psutil.Process()
        
    def run_all_benchmarks(self) -> Dict[str, BenchmarkResult]:
        """
        Run all performance benchmarks.
        
        Returns:
            Dictionary of benchmark results
        """
        benchmarks = [
            ("notification_creation", self.benchmark_notification_creation),
            ("message_formatting", self.benchmark_message_formatting),
            ("security_sanitization", self.benchmark_security_sanitization),
            ("concurrent_notifications", self.benchmark_concurrent_notifications),
            ("bulk_processing", self.benchmark_bulk_processing),
            ("memory_usage", self.benchmark_memory_usage),
            ("queue_performance", self.benchmark_queue_performance)
        ]
        
        results = {}
        
        for name, benchmark_func in benchmarks:
            print(f"🏃‍♂️ Running benchmark: {name}")
            try:
                result = benchmark_func()
                results[name] = result
                self.results.append(result)
                print(f"✅ {name}: {result.operations_per_second:.2f} ops/sec")
            except Exception as e:
                print(f"❌ {name} failed: {e}")
                results[name] = BenchmarkResult(
                    test_name=name,
                    duration_seconds=0,
                    operations_count=0,
                    operations_per_second=0,
                    memory_usage_mb=0,
                    memory_peak_mb=0,
                    success_rate=0,
                    errors=[str(e)],
                    metadata={}
                )
        
        return results
    
    def benchmark_notification_creation(self) -> BenchmarkResult:
        """Benchmark notification creation performance."""
        notification_manager = NotificationManager(enable_slack=False)
        
        operations_count = 1000
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        errors = []
        
        start_time = time.time()
        
        for i in range(operations_count):
            try:
                notification_manager.notify_status_change(
                    task_id=f"benchmark-{i}",
                    task_title=f"Benchmark Task {i}",
                    from_status="pending",
                    to_status="in-progress",
                    ticket_id=f"BENCH-{i}"
                )
                
                # Track peak memory usage
                current_memory = self._get_memory_usage()
                peak_memory = max(peak_memory, current_memory)
                
            except Exception as e:
                errors.append(str(e))
        
        # Allow processing time
        time.sleep(0.5)
        
        end_time = time.time()
        duration = end_time - start_time
        end_memory = self._get_memory_usage()
        
        success_rate = (operations_count - len(errors)) / operations_count * 100
        
        return BenchmarkResult(
            test_name="notification_creation",
            duration_seconds=duration,
            operations_count=operations_count,
            operations_per_second=operations_count / duration,
            memory_usage_mb=end_memory - start_memory,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],  # Keep first 10 errors
            metadata={
                "start_memory_mb": start_memory,
                "end_memory_mb": end_memory
            }
        )
    
    def benchmark_message_formatting(self) -> BenchmarkResult:
        """Benchmark message formatting performance."""
        message_builder = SlackMessageBuilder()
        
        operations_count = 5000
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        errors = []
        
        # Prepare test data
        task_data = TaskStatusChangeData(
            task_id="benchmark-task",
            task_title="Performance Benchmark Task",
            from_status="pending",
            to_status="in-progress",
            timestamp=datetime.now(),
            ticket_id="PERF-123"
        )
        
        start_time = time.time()
        
        for i in range(operations_count):
            try:
                # Alternate between different message types
                if i % 3 == 0:
                    message_builder.build_task_status_change_message(
                        data=task_data,
                        channel="#general",
                        priority=MessagePriority.MEDIUM
                    )
                elif i % 3 == 1:
                    message_builder.build_task_completion_message(
                        data=task_data,
                        channel="#general"
                    )
                else:
                    message_builder.build_task_failure_message(
                        data=task_data,
                        channel="#errors",
                        error_details="Performance test error"
                    )
                
                # Track peak memory
                if i % 100 == 0:  # Check memory every 100 operations
                    current_memory = self._get_memory_usage()
                    peak_memory = max(peak_memory, current_memory)
                
            except Exception as e:
                errors.append(str(e))
        
        end_time = time.time()
        duration = end_time - start_time
        end_memory = self._get_memory_usage()
        
        success_rate = (operations_count - len(errors)) / operations_count * 100
        
        return BenchmarkResult(
            test_name="message_formatting",
            duration_seconds=duration,
            operations_count=operations_count,
            operations_per_second=operations_count / duration,
            memory_usage_mb=end_memory - start_memory,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],
            metadata={
                "message_types_tested": 3,
                "avg_time_per_message_ms": (duration / operations_count) * 1000
            }
        )
    
    def benchmark_security_sanitization(self) -> BenchmarkResult:
        """Benchmark security sanitization performance."""
        security_manager = SlackSecurityManager()
        
        operations_count = 2000
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        errors = []
        
        # Prepare test data with sensitive information
        test_data = {
            "task_id": "security-test-123",
            "task_title": "Security Test Task",
            "task_description": """
                Contact admin at admin@company.com or call 555-123-4567.
                API key: sk-1234567890abcdef
                Credit card: 4111-1111-1111-1111
                SSN: 123-45-6789
                Server IP: 192.168.1.100
            """,
            "from_status": "pending",
            "to_status": "in-progress",
            "metadata": {
                "password": "secret123",
                "token": "bearer-xyz789abc123",
                "email": "user@example.com"
            }
        }
        
        start_time = time.time()
        
        for i in range(operations_count):
            try:
                # Create variation in data
                varied_data = test_data.copy()
                varied_data["task_id"] = f"security-test-{i}"
                
                secured = security_manager.secure_notification_data(varied_data)
                
                # Verify security was applied
                if not secured["secure"]:
                    errors.append(f"Security not properly applied for iteration {i}")
                
                # Track peak memory
                if i % 100 == 0:
                    current_memory = self._get_memory_usage()
                    peak_memory = max(peak_memory, current_memory)
                
            except Exception as e:
                errors.append(str(e))
        
        end_time = time.time()
        duration = end_time - start_time
        end_memory = self._get_memory_usage()
        
        success_rate = (operations_count - len(errors)) / operations_count * 100
        
        return BenchmarkResult(
            test_name="security_sanitization",
            duration_seconds=duration,
            operations_count=operations_count,
            operations_per_second=operations_count / duration,
            memory_usage_mb=end_memory - start_memory,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],
            metadata={
                "data_fields_processed": len(test_data) + len(test_data["metadata"]),
                "avg_sanitization_time_ms": (duration / operations_count) * 1000
            }
        )
    
    def benchmark_concurrent_notifications(self) -> BenchmarkResult:
        """Benchmark concurrent notification handling."""
        notification_manager = NotificationManager(enable_slack=False)
        
        num_threads = 10
        notifications_per_thread = 100
        total_operations = num_threads * notifications_per_thread
        
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        errors = []
        thread_results = []
        
        def worker_thread(thread_id: int):
            """Worker thread for concurrent testing."""
            thread_errors = []
            thread_start = time.time()
            
            for i in range(notifications_per_thread):
                try:
                    notification_manager.notify_status_change(
                        task_id=f"concurrent-{thread_id}-{i}",
                        task_title=f"Concurrent Task {thread_id}-{i}",
                        from_status="pending",
                        to_status="in-progress",
                        ticket_id=f"CONC-{thread_id}-{i}"
                    )
                except Exception as e:
                    thread_errors.append(str(e))
            
            thread_end = time.time()
            thread_results.append({
                "thread_id": thread_id,
                "duration": thread_end - thread_start,
                "errors": len(thread_errors)
            })
            errors.extend(thread_errors)
        
        # Start concurrent threads
        start_time = time.time()
        threads = []
        
        for thread_id in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Monitor memory during concurrent execution
        memory_samples = []
        for thread in threads:
            thread.join(timeout=0.1)
            memory_samples.append(self._get_memory_usage())
            peak_memory = max(peak_memory, memory_samples[-1])
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Allow processing time
        time.sleep(1.0)
        
        end_time = time.time()
        duration = end_time - start_time
        end_memory = self._get_memory_usage()
        
        success_rate = (total_operations - len(errors)) / total_operations * 100
        
        return BenchmarkResult(
            test_name="concurrent_notifications",
            duration_seconds=duration,
            operations_count=total_operations,
            operations_per_second=total_operations / duration,
            memory_usage_mb=end_memory - start_memory,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],
            metadata={
                "num_threads": num_threads,
                "notifications_per_thread": notifications_per_thread,
                "thread_results": thread_results,
                "memory_samples": len(memory_samples)
            }
        )
    
    def benchmark_bulk_processing(self) -> BenchmarkResult:
        """Benchmark bulk notification processing."""
        notification_manager = NotificationManager(enable_slack=False)
        
        bulk_size = 1000
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        errors = []
        
        # Prepare bulk notifications
        notifications = []
        for i in range(bulk_size):
            notifications.append({
                "task_id": f"bulk-{i}",
                "task_title": f"Bulk Task {i}",
                "from_status": "pending" if i % 2 == 0 else "in-progress",
                "to_status": "in-progress" if i % 2 == 0 else "done",
                "ticket_id": f"BULK-{i}"
            })
        
        start_time = time.time()
        
        # Send bulk notifications
        for i, notification in enumerate(notifications):
            try:
                notification_manager.notify_status_change(**notification)
                
                # Track memory every 100 operations
                if i % 100 == 0:
                    current_memory = self._get_memory_usage()
                    peak_memory = max(peak_memory, current_memory)
                
            except Exception as e:
                errors.append(str(e))
        
        # Allow processing time
        time.sleep(2.0)
        
        end_time = time.time()
        duration = end_time - start_time
        end_memory = self._get_memory_usage()
        
        success_rate = (bulk_size - len(errors)) / bulk_size * 100
        
        return BenchmarkResult(
            test_name="bulk_processing",
            duration_seconds=duration,
            operations_count=bulk_size,
            operations_per_second=bulk_size / duration,
            memory_usage_mb=end_memory - start_memory,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],
            metadata={
                "bulk_size": bulk_size,
                "processing_time_seconds": duration - 2.0,  # Subtract sleep time
                "queue_processing_included": True
            }
        )
    
    def benchmark_memory_usage(self) -> BenchmarkResult:
        """Benchmark memory usage patterns."""
        notification_manager = NotificationManager(enable_slack=False)
        
        operations_count = 2000
        start_memory = self._get_memory_usage()
        memory_samples = [start_memory]
        errors = []
        
        start_time = time.time()
        
        for i in range(operations_count):
            try:
                notification_manager.notify_status_change(
                    task_id=f"memory-test-{i}",
                    task_title=f"Memory Test Task {i}",
                    from_status="pending",
                    to_status="in-progress"
                )
                
                # Sample memory every 50 operations
                if i % 50 == 0:
                    memory_samples.append(self._get_memory_usage())
                
            except Exception as e:
                errors.append(str(e))
        
        # Allow processing and garbage collection
        time.sleep(1.0)
        
        end_time = time.time()
        duration = end_time - start_time
        end_memory = self._get_memory_usage()
        
        # Calculate memory statistics
        peak_memory = max(memory_samples)
        avg_memory = statistics.mean(memory_samples)
        memory_growth = end_memory - start_memory
        
        success_rate = (operations_count - len(errors)) / operations_count * 100
        
        return BenchmarkResult(
            test_name="memory_usage",
            duration_seconds=duration,
            operations_count=operations_count,
            operations_per_second=operations_count / duration,
            memory_usage_mb=memory_growth,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],
            metadata={
                "start_memory_mb": start_memory,
                "end_memory_mb": end_memory,
                "avg_memory_mb": avg_memory,
                "memory_samples": len(memory_samples),
                "memory_growth_mb": memory_growth,
                "memory_efficiency_score": operations_count / max(1, memory_growth)
            }
        )
    
    def benchmark_queue_performance(self) -> BenchmarkResult:
        """Benchmark notification queue performance."""
        notification_manager = NotificationManager(enable_slack=False)
        
        operations_count = 1500
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        errors = []
        queue_sizes = []
        
        start_time = time.time()
        
        # Rapid-fire notifications to test queue handling
        for i in range(operations_count):
            try:
                notification_manager.notify_status_change(
                    task_id=f"queue-test-{i}",
                    task_title=f"Queue Test Task {i}",
                    from_status="pending",
                    to_status="in-progress"
                )
                
                # Sample queue size periodically
                if i % 100 == 0:
                    stats = notification_manager.get_statistics()
                    queue_sizes.append(stats.get("queue_size", 0))
                    
                    current_memory = self._get_memory_usage()
                    peak_memory = max(peak_memory, current_memory)
                
            except Exception as e:
                errors.append(str(e))
        
        # Allow queue processing
        processing_start = time.time()
        time.sleep(3.0)  # Allow processing time
        processing_end = time.time()
        
        end_time = time.time()
        total_duration = end_time - start_time
        processing_duration = processing_end - processing_start
        
        end_memory = self._get_memory_usage()
        
        # Get final statistics
        final_stats = notification_manager.get_statistics()
        
        success_rate = (operations_count - len(errors)) / operations_count * 100
        
        return BenchmarkResult(
            test_name="queue_performance",
            duration_seconds=total_duration,
            operations_count=operations_count,
            operations_per_second=operations_count / total_duration,
            memory_usage_mb=end_memory - start_memory,
            memory_peak_mb=peak_memory,
            success_rate=success_rate,
            errors=errors[:10],
            metadata={
                "queue_sizes_sampled": queue_sizes,
                "max_queue_size": max(queue_sizes) if queue_sizes else 0,
                "final_queue_size": final_stats.get("queue_size", 0),
                "events_processed": final_stats.get("events_processed", 0),
                "processing_duration": processing_duration,
                "queue_throughput": final_stats.get("events_processed", 0) / max(0.1, processing_duration)
            }
        )
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def generate_report(self, results: Dict[str, BenchmarkResult]) -> str:
        """Generate a comprehensive performance report."""
        report = []
        report.append("# Slack Integration Performance Benchmark Report")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")
        
        # Summary table
        report.append("## Performance Summary")
        report.append("")
        report.append("| Test | Ops/Sec | Memory (MB) | Success Rate |")
        report.append("|------|---------|-------------|--------------|")
        
        for name, result in results.items():
            report.append(f"| {name} | {result.operations_per_second:.2f} | {result.memory_usage_mb:.2f} | {result.success_rate:.1f}% |")
        
        report.append("")
        
        # Detailed results
        report.append("## Detailed Results")
        report.append("")
        
        for name, result in results.items():
            report.append(f"### {result.test_name}")
            report.append(f"- **Operations**: {result.operations_count}")
            report.append(f"- **Duration**: {result.duration_seconds:.3f} seconds")
            report.append(f"- **Throughput**: {result.operations_per_second:.2f} ops/sec")
            report.append(f"- **Memory Usage**: {result.memory_usage_mb:.2f} MB")
            report.append(f"- **Peak Memory**: {result.memory_peak_mb:.2f} MB")
            report.append(f"- **Success Rate**: {result.success_rate:.1f}%")
            
            if result.errors:
                report.append(f"- **Errors**: {len(result.errors)} (showing first few)")
                for error in result.errors[:3]:
                    report.append(f"  - {error}")
            
            if result.metadata:
                report.append("- **Metadata**:")
                for key, value in result.metadata.items():
                    if isinstance(value, (int, float)):
                        report.append(f"  - {key}: {value}")
                    elif isinstance(value, str):
                        report.append(f"  - {key}: {value}")
            
            report.append("")
        
        # Performance thresholds check
        report.append("## Performance Threshold Analysis")
        report.append("")
        
        thresholds = {
            "min_ops_per_second": 100,
            "max_memory_usage_mb": 50,
            "min_success_rate": 95.0
        }
        
        for name, result in results.items():
            issues = []
            
            if result.operations_per_second < thresholds["min_ops_per_second"]:
                issues.append(f"Low throughput: {result.operations_per_second:.2f} < {thresholds['min_ops_per_second']}")
            
            if result.memory_usage_mb > thresholds["max_memory_usage_mb"]:
                issues.append(f"High memory usage: {result.memory_usage_mb:.2f} > {thresholds['max_memory_usage_mb']}")
            
            if result.success_rate < thresholds["min_success_rate"]:
                issues.append(f"Low success rate: {result.success_rate:.1f}% < {thresholds['min_success_rate']}%")
            
            if issues:
                report.append(f"**{name}**: ⚠️ Issues found")
                for issue in issues:
                    report.append(f"  - {issue}")
            else:
                report.append(f"**{name}**: ✅ All thresholds met")
        
        return "\n".join(report)
    
    def save_results(self, results: Dict[str, BenchmarkResult], filename: str):
        """Save benchmark results to a JSON file."""
        json_data = {}
        
        for name, result in results.items():
            json_data[name] = {
                "test_name": result.test_name,
                "duration_seconds": result.duration_seconds,
                "operations_count": result.operations_count,
                "operations_per_second": result.operations_per_second,
                "memory_usage_mb": result.memory_usage_mb,
                "memory_peak_mb": result.memory_peak_mb,
                "success_rate": result.success_rate,
                "error_count": len(result.errors),
                "errors": result.errors,
                "metadata": result.metadata
            }
        
        json_data["benchmark_info"] = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(results),
            "platform": "python",
            "version": "1.0"
        }
        
        with open(filename, 'w') as f:
            json.dump(json_data, f, indent=2)


def main():
    """Main entry point for performance benchmarking."""
    parser = argparse.ArgumentParser(description="Slack Integration Performance Benchmark")
    parser.add_argument("--output", "-o", default="slack_benchmark_results.json",
                       help="Output file for benchmark results")
    parser.add_argument("--report", "-r", default="slack_benchmark_report.md",
                       help="Output file for benchmark report")
    parser.add_argument("--tests", "-t", nargs="+",
                       help="Specific tests to run (default: all)")
    
    args = parser.parse_args()
    
    benchmark = SlackPerformanceBenchmark()
    
    print("🚀 Starting Slack Integration Performance Benchmark")
    print("=" * 60)
    
    start_time = time.time()
    results = benchmark.run_all_benchmarks()
    end_time = time.time()
    
    total_duration = end_time - start_time
    
    print("=" * 60)
    print(f"✅ Benchmark completed in {total_duration:.2f} seconds")
    print(f"📊 Total tests: {len(results)}")
    
    # Save results
    benchmark.save_results(results, args.output)
    print(f"💾 Results saved to: {args.output}")
    
    # Generate and save report
    report = benchmark.generate_report(results)
    with open(args.report, 'w') as f:
        f.write(report)
    print(f"📄 Report saved to: {args.report}")
    
    # Print summary
    print("\n📈 Performance Summary:")
    print("-" * 40)
    for name, result in results.items():
        status = "✅" if result.success_rate > 95 else "⚠️"
        print(f"{status} {name}: {result.operations_per_second:.2f} ops/sec")


if __name__ == "__main__":
    main()