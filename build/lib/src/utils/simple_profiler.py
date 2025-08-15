"""
Simple performance profiler without external dependencies.
"""

import functools
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, ContextManager, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SimpleMetrics:
    """Simple performance metrics."""

    name: str
    duration: float
    start_time: float
    end_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class SimpleProfiler:
    """Simple thread-safe performance profiler."""

    def __init__(self, max_history: int = 1000):
        """Initialize profiler."""
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self._lock = threading.Lock()

    def record_metric(self, metric: SimpleMetrics) -> None:
        """Record a performance metric."""
        with self._lock:
            self.metrics.append(metric)

    @contextmanager
    def profile_operation(self, name: str) -> ContextManager[None]:
        """Context manager for profiling operations."""
        start_time = time.time()

        try:
            yield
        finally:
            end_time = time.time()

            metric = SimpleMetrics(name=name, duration=end_time - start_time, start_time=start_time, end_time=end_time)

            self.record_metric(metric)

    def profile_function(self, name: Optional[str] = None):
        """Decorator for profiling functions."""

        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.profile_operation(profile_name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of recorded metrics."""
        with self._lock:
            if not self.metrics:
                return {"total_operations": 0, "operations": {}}

            operations = defaultdict(list)
            for metric in self.metrics:
                operations[metric.name].append(metric.duration)

            summary = {}
            for name, durations in operations.items():
                summary[name] = {
                    "count": len(durations),
                    "total_duration": sum(durations),
                    "avg_duration": sum(durations) / len(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                }

            return {"total_operations": len(self.metrics), "operations": summary}


# Global profiler instance
simple_profiler = SimpleProfiler()


@contextmanager
def profile_context(name: str):
    """Convenience context manager for profiling."""
    with simple_profiler.profile_operation(name):
        yield


def profile_operation(name: Optional[str] = None):
    """Convenience decorator for profiling operations."""
    return simple_profiler.profile_function(name)
