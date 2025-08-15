#!/usr/bin/env python3
"""
Performance Integration - Integrates performance monitoring into existing components
Provides decorators and mixins for seamless performance tracking across the application.
"""
import functools
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.utils.logging_config import get_logger
from src.utils.performance_monitor import PerformanceMonitor

logger = get_logger(__name__)

# Global performance monitor instance
_global_performance_monitor: Optional[PerformanceMonitor] = None


def initialize_performance_monitoring(
    collection_interval: float = 1.0,
    history_size: int = 1000,
    enable_auto_gc: bool = True,
    auto_start: bool = True,
) -> PerformanceMonitor:
    """
    Initialize global performance monitoring.

    Args:
        collection_interval: Metrics collection interval in seconds
        history_size: Number of metrics to keep in history
        enable_auto_gc: Enable automatic garbage collection
        auto_start: Start monitoring immediately

    Returns:
        PerformanceMonitor instance
    """
    global _global_performance_monitor

    if _global_performance_monitor is not None:
        logger.warning("⚠️ Performance monitoring already initialized")
        return _global_performance_monitor

    _global_performance_monitor = PerformanceMonitor(
        collection_interval=collection_interval,
        history_size=history_size,
        enable_auto_gc=enable_auto_gc,
    )

    if auto_start:
        _global_performance_monitor.start_monitoring()

    logger.info("🚀 Global performance monitoring initialized")
    return _global_performance_monitor


def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """Get the global performance monitor instance."""
    return _global_performance_monitor


def performance_tracked(task_name: Optional[str] = None):
    """
    Decorator to track performance of functions/methods.

    Args:
        task_name: Optional custom task name for tracking
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            if not monitor:
                # Performance monitoring not initialized, just run the function
                return func(*args, **kwargs)

            # Generate task ID
            func_task_name = task_name or f"{func.__module__}.{func.__name__}"
            task_id = f"{func_task_name}_{int(time.time()*1000)}"

            # Start timing
            monitor.start_task_timing(task_id)

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # End timing
                duration = monitor.end_task_timing(task_id)
                if duration is not None:
                    logger.debug(f"📊 Function {func.__name__} completed in {duration:.3f}s")

        return wrapper

    return decorator


class PerformanceMixin:
    """
    Mixin class to add performance monitoring capabilities to existing classes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._perf_monitor = get_performance_monitor()
        self._active_operations: Dict[str, str] = {}  # operation_name -> task_id

    def _start_operation_timing(self, operation_name: str) -> str:
        """Start timing an operation."""
        if not self._perf_monitor:
            return ""

        task_id = f"{self.__class__.__name__}.{operation_name}_{int(time.time()*1000)}"
        self._perf_monitor.start_task_timing(task_id)
        self._active_operations[operation_name] = task_id
        return task_id

    def _end_operation_timing(self, operation_name: str) -> Optional[float]:
        """End timing an operation."""
        if not self._perf_monitor or operation_name not in self._active_operations:
            return None

        task_id = self._active_operations.pop(operation_name)
        return self._perf_monitor.end_task_timing(task_id)

    def _add_performance_metric(self, name: str, value: float, unit: str, tags: Optional[Dict[str, str]] = None):
        """Add a custom performance metric."""
        if self._perf_monitor:
            self._perf_monitor._add_metric(name, value, unit, datetime.now(), tags)


def integrate_with_status_transition_manager():
    """Integrate performance monitoring with StatusTransitionManager."""
    try:
        from core.managers.status_transition_manager import StatusTransitionManager

        # Monkey patch the original methods
        original_transition = StatusTransitionManager.transition_status
        original_batch_transition = StatusTransitionManager.batch_transition_status

        @performance_tracked("status_transition")
        def tracked_transition_status(self, page_id: str, from_status: str, to_status: str, validate_transition: bool = True):
            return original_transition(self, page_id, from_status, to_status, validate_transition)

        @performance_tracked("batch_status_transition")
        def tracked_batch_transition_status(self, transitions):
            return original_batch_transition(self, transitions)

        StatusTransitionManager.transition_status = tracked_transition_status
        StatusTransitionManager.batch_transition_status = tracked_batch_transition_status

        logger.info("✅ Performance monitoring integrated with StatusTransitionManager")

    except ImportError as e:
        logger.warning(f"⚠️ Could not integrate with StatusTransitionManager: {e}")


def integrate_with_claude_engine_invoker():
    """Integrate performance monitoring with ClaudeEngineInvoker."""
    try:
        from clients.claude_engine_invoker import ClaudeEngineInvoker

        # Monkey patch the original method
        original_invoke = ClaudeEngineInvoker.invoke_claude_engine

        @performance_tracked("claude_engine_invocation")
        def tracked_invoke_claude_engine(self, ticket_id: str, page_id: str):
            return original_invoke(self, ticket_id, page_id)

        ClaudeEngineInvoker.invoke_claude_engine = tracked_invoke_claude_engine

        logger.info("✅ Performance monitoring integrated with ClaudeEngineInvoker")

    except ImportError as e:
        logger.warning(f"⚠️ Could not integrate with ClaudeEngineInvoker: {e}")


def integrate_with_task_file_manager():
    """Integrate performance monitoring with TaskFileManager."""
    try:
        from core.managers.task_file_manager import TaskFileManager

        # Monkey patch the original method
        original_copy = TaskFileManager.copy_task_file_to_taskmaster

        @performance_tracked("task_file_copy")
        def tracked_copy_task_file_to_taskmaster(self, ticket_id: str, source_file_path: Optional[str] = None):
            return original_copy(self, ticket_id, source_file_path)

        TaskFileManager.copy_task_file_to_taskmaster = tracked_copy_task_file_to_taskmaster

        logger.info("✅ Performance monitoring integrated with TaskFileManager")

    except ImportError as e:
        logger.warning(f"⚠️ Could not integrate with TaskFileManager: {e}")


def integrate_with_multi_queue_processor():
    """Integrate performance monitoring with MultiQueueProcessor."""
    try:
        from core.processors.multi_queue_processor import MultiQueueProcessor

        # Monkey patch key methods
        original_process_queued_tasks = MultiQueueProcessor.process_queued_tasks
        original_process_single_task = MultiQueueProcessor._process_single_task_with_retry

        @performance_tracked("multi_queue_processing_session")
        def tracked_process_queued_tasks(self, cancellation_check: Callable = None):
            return original_process_queued_tasks(self, cancellation_check)

        @performance_tracked("single_task_processing")
        def tracked_process_single_task_with_retry(self, task_item):
            return original_process_single_task(self, task_item)

        MultiQueueProcessor.process_queued_tasks = tracked_process_queued_tasks
        MultiQueueProcessor._process_single_task_with_retry = tracked_process_single_task_with_retry

        logger.info("✅ Performance monitoring integrated with MultiQueueProcessor")

    except ImportError as e:
        logger.warning(f"⚠️ Could not integrate with MultiQueueProcessor: {e}")


def integrate_all_components():
    """Integrate performance monitoring with all supported components."""
    logger.info("🔗 Integrating performance monitoring with all components...")

    integrate_with_status_transition_manager()
    integrate_with_claude_engine_invoker()
    integrate_with_task_file_manager()
    integrate_with_multi_queue_processor()

    logger.info("🎉 Performance monitoring integration completed")


def get_comprehensive_performance_report() -> Dict[str, Any]:
    """Get a comprehensive performance report combining all metrics."""
    monitor = get_performance_monitor()
    if not monitor:
        return {"error": "Performance monitoring not initialized"}

    report = {
        "timestamp": datetime.now().isoformat(),
        "system_summary": monitor.get_performance_summary(),
        "task_statistics": monitor.get_task_performance_stats(),
        "recent_alerts": [
            {
                "timestamp": alert.timestamp.isoformat(),
                "level": alert.alert_type.value,
                "metric": alert.metric_name,
                "message": alert.message,
                "suggestions": alert.suggestions,
            }
            for alert in monitor.get_recent_alerts(hours=1)
        ],
        "optimization_status": monitor.optimize_performance(),
        "sla_compliance": {},
    }

    # Add SLA compliance summary
    sla_status = report["system_summary"].get("sla_status", {})
    compliant_count = sum(1 for status in sla_status.values() if status["status"] == "compliant")
    total_slas = len(sla_status)

    report["sla_compliance"] = {
        "total_slas": total_slas,
        "compliant_slas": compliant_count,
        "compliance_rate": (compliant_count / total_slas * 100) if total_slas > 0 else 100,
        "violations": [
            {
                "metric": metric,
                "status": info["status"],
                "current_value": info["current_value"],
                "threshold": (info["critical_threshold"] if info["status"] == "violated" else info["warning_threshold"]),
            }
            for metric, info in sla_status.items()
            if info["status"] != "compliant"
        ],
    }

    return report


def log_performance_summary():
    """Log a comprehensive performance summary."""
    report = get_comprehensive_performance_report()

    if "error" in report:
        logger.warning(f"⚠️ {report['error']}")
        return

    logger.info("📊 =======  PERFORMANCE SUMMARY  =======")

    # System metrics
    current_metrics = report["system_summary"].get("current_metrics", {})
    logger.info("🖥️  System Metrics:")
    for metric, data in current_metrics.items():
        if "percent" in data["unit"]:
            logger.info(f"   {metric}: {data['value']:.1f}%")
        elif "gb" in data["unit"]:
            logger.info(f"   {metric}: {data['value']:.2f} GB")
        elif "mb" in data["unit"]:
            logger.info(f"   {metric}: {data['value']:.1f} MB")
        else:
            logger.info(f"   {metric}: {data['value']:.2f} {data['unit']}")

    # Task performance
    task_stats = report["task_statistics"]
    logger.info("📋 Task Performance:")
    logger.info(f"   Total completed: {task_stats['total_completed']}")
    logger.info(f"   Average duration: {task_stats['average_duration']:.2f}s")
    logger.info(f"   SLA compliance: {task_stats['sla_compliance_rate']:.1f}%")

    # SLA compliance
    sla_info = report["sla_compliance"]
    logger.info("📏 SLA Compliance:")
    logger.info(f"   Overall compliance: {sla_info['compliance_rate']:.1f}%")
    logger.info(f"   Violations: {len(sla_info['violations'])}")

    # Recent alerts
    alert_count = len(report["recent_alerts"])
    if alert_count > 0:
        logger.warning(f"⚠️ Recent alerts (last hour): {alert_count}")
        for alert in report["recent_alerts"][-3:]:  # Show last 3 alerts
            logger.warning(f"   [{alert['level'].upper()}] {alert['message']}")
    else:
        logger.info("✅ No recent performance alerts")

    logger.info("📊 ====================================")


# Context manager for performance monitoring
class PerformanceContext:
    """Context manager for temporary performance monitoring sessions."""

    def __init__(self, session_name: str):
        self.session_name = session_name
        self.monitor = get_performance_monitor()
        self.task_id = None

    def __enter__(self):
        if self.monitor:
            self.task_id = self.monitor.start_task_timing(f"session_{self.session_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.monitor and self.task_id:
            duration = self.monitor.end_task_timing(self.task_id)
            logger.info(f"📊 Performance session '{self.session_name}' completed in {duration:.2f}s")
