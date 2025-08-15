"""
Performance profiling and monitoring utilities for production-ready code.
"""

import cProfile
import functools
import io
import json
import logging
import pstats
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""

    name: str
    duration: float
    memory_usage: float
    cpu_percent: float
    start_time: float
    end_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "duration": self.duration,
            "memory_usage": self.memory_usage,
            "cpu_percent": self.cpu_percent,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata,
        }


@dataclass
class AggregatedMetrics:
    """Aggregated performance metrics."""

    name: str
    call_count: int
    total_duration: float
    avg_duration: float
    min_duration: float
    max_duration: float
    avg_memory: float
    avg_cpu: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "call_count": self.call_count,
            "total_duration": self.total_duration,
            "avg_duration": self.avg_duration,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration,
            "avg_memory": self.avg_memory,
            "avg_cpu": self.avg_cpu,
        }


class PerformanceProfiler:
    """Thread-safe performance profiler for monitoring application performance."""

    def __init__(self, max_history: int = 1000):
        """Initialize profiler."""
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.aggregated: Dict[str, List[PerformanceMetrics]] = defaultdict(list)
        self._lock = threading.Lock()
        self._active_profiles: Dict[str, Dict[str, Any]] = {}
        self._process = psutil.Process()

    def record_metric(self, metric: PerformanceMetrics) -> None:
        """Record a performance metric."""
        with self._lock:
            self.metrics.append(metric)
            self.aggregated[metric.name].append(metric)

            # Keep only recent metrics for aggregation
            if len(self.aggregated[metric.name]) > 100:
                self.aggregated[metric.name] = self.aggregated[metric.name][-100:]

    @contextmanager
    def profile_operation(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> ContextManager[None]:
        """Context manager for profiling operations."""
        start_time = time.time()
        start_memory = self._get_memory_usage()
        start_cpu = self._get_cpu_percent()

        try:
            yield
        finally:
            end_time = time.time()
            end_memory = self._get_memory_usage()
            end_cpu = self._get_cpu_percent()

            metric = PerformanceMetrics(
                name=name,
                duration=end_time - start_time,
                memory_usage=end_memory - start_memory,
                cpu_percent=(start_cpu + end_cpu) / 2,
                start_time=start_time,
                end_time=end_time,
                metadata=metadata or {},
            )

            self.record_metric(metric)

    def profile_function(self, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Decorator for profiling functions."""

        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.profile_operation(profile_name, metadata):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def get_aggregated_metrics(self, name: Optional[str] = None) -> Dict[str, AggregatedMetrics]:
        """Get aggregated metrics for operations."""
        with self._lock:
            results = {}

            operations = [name] if name else self.aggregated.keys()

            for op_name in operations:
                if op_name not in self.aggregated:
                    continue

                metrics = self.aggregated[op_name]
                if not metrics:
                    continue

                durations = [m.duration for m in metrics]
                memories = [m.memory_usage for m in metrics]
                cpus = [m.cpu_percent for m in metrics]

                aggregated = AggregatedMetrics(
                    name=op_name,
                    call_count=len(metrics),
                    total_duration=sum(durations),
                    avg_duration=sum(durations) / len(durations),
                    min_duration=min(durations),
                    max_duration=max(durations),
                    avg_memory=sum(memories) / len(memories) if memories else 0,
                    avg_cpu=sum(cpus) / len(cpus) if cpus else 0,
                )

                results[op_name] = aggregated

            return results

    def get_slow_operations(self, threshold: float = 1.0, limit: int = 10) -> List[PerformanceMetrics]:
        """Get operations that took longer than threshold."""
        with self._lock:
            slow_ops = [m for m in self.metrics if m.duration > threshold]
            return sorted(slow_ops, key=lambda x: x.duration, reverse=True)[:limit]

    def get_memory_intensive_operations(self, threshold: float = 100.0, limit: int = 10) -> List[PerformanceMetrics]:
        """Get operations that used more memory than threshold (MB)."""
        with self._lock:
            memory_ops = [m for m in self.metrics if abs(m.memory_usage) > threshold * 1024 * 1024]
            return sorted(memory_ops, key=lambda x: abs(x.memory_usage), reverse=True)[:limit]

    def export_metrics(self, file_path: Path, format: str = "json") -> None:
        """Export metrics to file."""
        aggregated = self.get_aggregated_metrics()

        if format == "json":
            data = {
                "aggregated_metrics": {name: metrics.to_dict() for name, metrics in aggregated.items()},
                "total_operations": len(self.metrics),
                "export_timestamp": time.time(),
            }

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

        logger.info(f"Exported performance metrics to {file_path}")

    def clear_metrics(self) -> None:
        """Clear all recorded metrics."""
        with self._lock:
            self.metrics.clear()
            self.aggregated.clear()

    def _get_memory_usage(self) -> float:
        """Get current memory usage in bytes."""
        return self._process.memory_info().rss

    def _get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        return self._process.cpu_percent()

    def profile_with_cprofile(self, name: str) -> ContextManager[cProfile.Profile]:
        """Context manager for detailed cProfile profiling."""

        @contextmanager
        def profile_context():
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                yield profiler
            finally:
                profiler.disable()

                # Store profile results
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s)
                ps.sort_stats("cumulative")
                ps.print_stats(20)  # Top 20 functions

                profile_data = s.getvalue()
                logger.info(f"Profile for {name}:\n{profile_data}")

                # Store in active profiles for later analysis
                with self._lock:
                    self._active_profiles[name] = {
                        "timestamp": time.time(),
                        "profile_data": profile_data,
                        "stats": ps,
                    }

        return profile_context()


# Global profiler instance
profiler = PerformanceProfiler()


# Convenience decorators
def profile_operation(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """Convenience decorator for profiling operations."""
    return profiler.profile_function(name, metadata)


@contextmanager
def profile_context(name: str, metadata: Optional[Dict[str, Any]] = None):
    """Convenience context manager for profiling."""
    with profiler.profile_operation(name, metadata):
        yield


class PerformanceMonitor:
    """System-wide performance monitor."""

    def __init__(self, interval: float = 5.0):
        """Initialize monitor."""
        self.interval = interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.system_metrics: deque = deque(maxlen=100)
        self._lock = threading.Lock()

    def start_monitoring(self) -> None:
        """Start system monitoring."""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Performance monitoring started")

    def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logger.info("Performance monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring:
            try:
                timestamp = time.time()
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage("/")

                system_metric = {
                    "timestamp": timestamp,
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_percent": disk.percent,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_free_gb": disk.free / (1024**3),
                }

                with self._lock:
                    self.system_metrics.append(system_metric)

                time.sleep(self.interval)

            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                time.sleep(self.interval)

    def get_current_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        with self._lock:
            if self.system_metrics:
                return self.system_metrics[-1].copy()
            return {}

    def get_system_metrics_history(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get system metrics history for specified minutes."""
        cutoff_time = time.time() - (minutes * 60)

        with self._lock:
            return [metric for metric in self.system_metrics if metric["timestamp"] > cutoff_time]

    def check_system_health(self) -> Dict[str, Any]:
        """Check system health and return status."""
        current_metrics = self.get_current_system_metrics()

        if not current_metrics:
            return {"status": "unknown", "message": "No metrics available"}

        issues = []

        # Check CPU usage
        if current_metrics.get("cpu_percent", 0) > 80:
            issues.append("High CPU usage")

        # Check memory usage
        if current_metrics.get("memory_percent", 0) > 85:
            issues.append("High memory usage")

        # Check disk usage
        if current_metrics.get("disk_percent", 0) > 90:
            issues.append("High disk usage")

        if issues:
            return {
                "status": "warning",
                "message": f"System issues detected: {', '.join(issues)}",
                "metrics": current_metrics,
                "issues": issues,
            }
        else:
            return {
                "status": "healthy",
                "message": "System is running normally",
                "metrics": current_metrics,
            }


# Global monitor instance
monitor = PerformanceMonitor()


def start_performance_monitoring(interval: float = 5.0) -> None:
    """Start global performance monitoring."""
    global monitor
    monitor.interval = interval
    monitor.start_monitoring()


def stop_performance_monitoring() -> None:
    """Stop global performance monitoring."""
    global monitor
    monitor.stop_monitoring()


def get_performance_summary() -> Dict[str, Any]:
    """Get comprehensive performance summary."""
    aggregated = profiler.get_aggregated_metrics()
    slow_ops = profiler.get_slow_operations()
    memory_ops = profiler.get_memory_intensive_operations()
    system_health = monitor.check_system_health()

    return {
        "aggregated_metrics": {name: metrics.to_dict() for name, metrics in aggregated.items()},
        "slow_operations": [op.to_dict() for op in slow_ops],
        "memory_intensive_operations": [op.to_dict() for op in memory_ops],
        "system_health": system_health,
        "total_recorded_operations": len(profiler.metrics),
        "summary_timestamp": time.time(),
    }
