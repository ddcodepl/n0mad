#!/usr/bin/env python3
"""
Performance Monitor - Comprehensive performance monitoring and optimization system
Tracks CPU usage, memory usage, processing latency, SLA compliance, and provides optimization recommendations.
"""
import psutil
import time
import threading
import gc
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import statistics
from logging_config import get_logger

logger = get_logger(__name__)


class PerformanceLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


class SLAStatus(str, Enum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    VIOLATED = "violated"


@dataclass
class PerformanceMetric:
    """Individual performance metric measurement"""
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SLAThreshold:
    """SLA threshold configuration"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    unit: str
    description: str


@dataclass
class PerformanceAlert:
    """Performance alert/warning"""
    timestamp: datetime
    alert_type: PerformanceLevel
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    suggestions: List[str] = field(default_factory=list)


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system with real-time metrics collection,
    SLA compliance tracking, and optimization recommendations.
    """
    
    def __init__(self, 
                 collection_interval: float = 1.0,
                 history_size: int = 1000,
                 enable_auto_gc: bool = True):
        self.collection_interval = collection_interval
        self.history_size = history_size
        self.enable_auto_gc = enable_auto_gc
        
        # Thread-safe data structures
        self._metrics_lock = threading.RLock()
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Metrics storage - circular buffers for efficiency
        self._metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self._alerts_history: deque = deque(maxlen=100)
        
        # Performance counters
        self._start_time = datetime.now()
        self._last_gc_time = time.time()
        self._process = psutil.Process()
        
        # SLA thresholds
        self._sla_thresholds = {
            "task_processing_time": SLAThreshold(
                "task_processing_time", 300.0, 600.0, "seconds",
                "Individual task processing time"
            ),
            "session_processing_time": SLAThreshold(
                "session_processing_time", 3600.0, 7200.0, "seconds",
                "Multi-task session processing time"
            ),
            "memory_usage_percent": SLAThreshold(
                "memory_usage_percent", 70.0, 90.0, "percent",
                "System memory usage percentage"
            ),
            "cpu_usage_percent": SLAThreshold(
                "cpu_usage_percent", 80.0, 95.0, "percent",
                "CPU usage percentage"
            ),
            "disk_usage_percent": SLAThreshold(
                "disk_usage_percent", 80.0, 95.0, "percent",
                "Disk usage percentage"
            )
        }
        
        # Task processing tracking
        self._active_tasks: Dict[str, datetime] = {}
        self._completed_tasks: List[Tuple[str, float]] = []
        
        logger.info("📊 PerformanceMonitor initialized")
        logger.info(f"   📈 Collection interval: {collection_interval}s")
        logger.info(f"   📊 History size: {history_size} metrics")
        logger.info(f"   🗑️ Auto GC enabled: {enable_auto_gc}")
    
    def start_monitoring(self):
        """Start background performance monitoring."""
        with self._metrics_lock:
            if self._monitoring_active:
                logger.warning("⚠️ Performance monitoring already active")
                return
            
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="PerformanceMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            
            logger.info("🚀 Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop background performance monitoring."""
        with self._metrics_lock:
            if not self._monitoring_active:
                logger.warning("⚠️ Performance monitoring not active")
                return
            
            self._monitoring_active = False
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5.0)
            
            logger.info("⏹️ Performance monitoring stopped")
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        logger.info("📊 Performance monitoring loop started")
        
        while self._monitoring_active:
            try:
                # Collect system metrics
                self._collect_system_metrics()
                
                # Check SLA compliance
                self._check_sla_compliance()
                
                # Auto garbage collection if enabled
                if self.enable_auto_gc:
                    self._auto_garbage_collect()
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                time.sleep(self.collection_interval)
        
        logger.info("📊 Performance monitoring loop stopped")
    
    def _collect_system_metrics(self):
        """Collect system performance metrics."""
        timestamp = datetime.now()
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            self._add_metric("cpu_usage_percent", cpu_percent, "percent", timestamp)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self._add_metric("memory_usage_percent", memory.percent, "percent", timestamp)
            self._add_metric("memory_available_gb", memory.available / (1024**3), "gb", timestamp)
            self._add_metric("memory_used_gb", memory.used / (1024**3), "gb", timestamp)
            
            # Process-specific metrics
            process_memory = self._process.memory_info()
            self._add_metric("process_memory_rss_mb", process_memory.rss / (1024**2), "mb", timestamp)
            self._add_metric("process_memory_vms_mb", process_memory.vms / (1024**2), "mb", timestamp)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self._add_metric("disk_usage_percent", disk_percent, "percent", timestamp)
            self._add_metric("disk_free_gb", disk.free / (1024**3), "gb", timestamp)
            
            # Load average (Unix systems)
            try:
                load_avg = psutil.getloadavg()
                self._add_metric("load_average_1m", load_avg[0], "load", timestamp)
                self._add_metric("load_average_5m", load_avg[1], "load", timestamp)
                self._add_metric("load_average_15m", load_avg[2], "load", timestamp)
            except AttributeError:
                # getloadavg not available on Windows
                pass
            
        except Exception as e:
            logger.error(f"❌ Error collecting system metrics: {e}")
    
    def _add_metric(self, name: str, value: float, unit: str, timestamp: datetime, tags: Optional[Dict[str, str]] = None):
        """Add a metric to the history."""
        metric = PerformanceMetric(
            timestamp=timestamp,
            metric_name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        
        with self._metrics_lock:
            self._metrics_history[name].append(metric)
    
    def _check_sla_compliance(self):
        """Check SLA compliance for all configured thresholds."""
        with self._metrics_lock:
            for threshold_name, threshold in self._sla_thresholds.items():
                if threshold_name not in self._metrics_history:
                    continue
                
                recent_metrics = list(self._metrics_history[threshold_name])
                if not recent_metrics:
                    continue
                
                # Get latest value
                latest_metric = recent_metrics[-1]
                current_value = latest_metric.value
                
                # Check thresholds
                alert_level = None
                suggestions = []
                
                if current_value >= threshold.critical_threshold:
                    alert_level = PerformanceLevel.CRITICAL
                    suggestions = self._get_optimization_suggestions(threshold_name, current_value)
                elif current_value >= threshold.warning_threshold:
                    alert_level = PerformanceLevel.WARNING
                    suggestions = self._get_optimization_suggestions(threshold_name, current_value)
                
                if alert_level:
                    alert = PerformanceAlert(
                        timestamp=datetime.now(),
                        alert_type=alert_level,
                        metric_name=threshold_name,
                        current_value=current_value,
                        threshold_value=threshold.warning_threshold if alert_level == PerformanceLevel.WARNING else threshold.critical_threshold,
                        message=f"{threshold.description} exceeded threshold: {current_value:.2f} {threshold.unit}",
                        suggestions=suggestions
                    )
                    
                    self._alerts_history.append(alert)
                    logger.warning(f"⚠️ Performance Alert [{alert_level.value.upper()}]: {alert.message}")
                    
                    for suggestion in suggestions:
                        logger.info(f"💡 Suggestion: {suggestion}")
    
    def _get_optimization_suggestions(self, metric_name: str, current_value: float) -> List[str]:
        """Get optimization suggestions based on metric type and value."""
        suggestions = []
        
        if metric_name == "memory_usage_percent":
            suggestions.extend([
                "Consider reducing batch sizes for concurrent operations",
                "Enable garbage collection optimization",
                "Check for memory leaks in task processing",
                "Implement memory pooling for frequently allocated objects"
            ])
        elif metric_name == "cpu_usage_percent":
            suggestions.extend([
                "Reduce concurrent task processing limit",
                "Implement task queuing with backpressure",
                "Optimize CPU-intensive operations",
                "Consider task scheduling optimization"
            ])
        elif metric_name == "task_processing_time":
            suggestions.extend([
                "Review Claude engine timeout settings",
                "Optimize file I/O operations",
                "Implement task complexity-based routing",
                "Check for network latency issues"
            ])
        elif metric_name == "disk_usage_percent":
            suggestions.extend([
                "Clean up old backup files",
                "Implement log rotation",
                "Archive completed task files",
                "Monitor temporary file cleanup"
            ])
        
        return suggestions
    
    def _auto_garbage_collect(self):
        """Perform automatic garbage collection if needed."""
        current_time = time.time()
        
        # Run GC every 60 seconds if memory usage is high
        if current_time - self._last_gc_time > 60:
            memory_metrics = list(self._metrics_history.get("memory_usage_percent", []))
            if memory_metrics:
                latest_memory = memory_metrics[-1].value
                if latest_memory > 70.0:  # High memory usage
                    gc.collect()
                    self._last_gc_time = current_time
                    logger.info(f"🗑️ Automatic garbage collection performed (memory at {latest_memory:.1f}%)")
    
    def start_task_timing(self, task_id: str) -> str:
        """Start timing a task."""
        with self._metrics_lock:
            self._active_tasks[task_id] = datetime.now()
            logger.debug(f"⏱️ Started timing task: {task_id}")
            return task_id
    
    def end_task_timing(self, task_id: str) -> Optional[float]:
        """End timing a task and return duration in seconds."""
        with self._metrics_lock:
            if task_id not in self._active_tasks:
                logger.warning(f"⚠️ Task timing not found: {task_id}")
                return None
            
            start_time = self._active_tasks.pop(task_id)
            duration = (datetime.now() - start_time).total_seconds()
            
            # Record the completion
            self._completed_tasks.append((task_id, duration))
            
            # Keep only recent completions
            if len(self._completed_tasks) > self.history_size:
                self._completed_tasks = self._completed_tasks[-self.history_size:]
            
            # Add to metrics
            self._add_metric("task_processing_time", duration, "seconds", datetime.now(), 
                           tags={"task_id": task_id})
            
            logger.info(f"⏱️ Task {task_id} completed in {duration:.2f}s")
            return duration
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        with self._metrics_lock:
            summary = {
                "monitoring_active": self._monitoring_active,
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                "metrics_collected": sum(len(history) for history in self._metrics_history.values()),
                "active_tasks": len(self._active_tasks),
                "completed_tasks": len(self._completed_tasks),
                "recent_alerts": len([a for a in self._alerts_history if (datetime.now() - a.timestamp).total_seconds() < 3600]),
                "current_metrics": {},
                "sla_status": {},
                "performance_trends": {}
            }
            
            # Get latest metrics
            for metric_name, history in self._metrics_history.items():
                if history:
                    latest = history[-1]
                    summary["current_metrics"][metric_name] = {
                        "value": latest.value,
                        "unit": latest.unit,
                        "timestamp": latest.timestamp.isoformat()
                    }
            
            # SLA compliance status
            for threshold_name, threshold in self._sla_thresholds.items():
                if threshold_name in self._metrics_history and self._metrics_history[threshold_name]:
                    current_value = self._metrics_history[threshold_name][-1].value
                    
                    if current_value >= threshold.critical_threshold:
                        status = SLAStatus.VIOLATED
                    elif current_value >= threshold.warning_threshold:
                        status = SLAStatus.AT_RISK
                    else:
                        status = SLAStatus.COMPLIANT
                    
                    summary["sla_status"][threshold_name] = {
                        "status": status.value,
                        "current_value": current_value,
                        "warning_threshold": threshold.warning_threshold,
                        "critical_threshold": threshold.critical_threshold
                    }
            
            # Performance trends (last hour)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            for metric_name, history in self._metrics_history.items():
                recent_values = [m.value for m in history if m.timestamp >= one_hour_ago]
                if len(recent_values) >= 2:
                    trend_direction = "stable"
                    if len(recent_values) >= 10:
                        # Calculate trend using simple linear regression
                        recent_avg = statistics.mean(recent_values[-10:])
                        older_avg = statistics.mean(recent_values[-20:-10]) if len(recent_values) >= 20 else recent_avg
                        
                        if recent_avg > older_avg * 1.1:
                            trend_direction = "increasing"
                        elif recent_avg < older_avg * 0.9:
                            trend_direction = "decreasing"
                    
                    summary["performance_trends"][metric_name] = {
                        "trend": trend_direction,
                        "recent_average": statistics.mean(recent_values),
                        "recent_max": max(recent_values),
                        "recent_min": min(recent_values),
                        "sample_count": len(recent_values)
                    }
            
            return summary
    
    def get_task_performance_stats(self) -> Dict[str, Any]:
        """Get task processing performance statistics."""
        with self._metrics_lock:
            if not self._completed_tasks:
                return {
                    "total_completed": 0,
                    "average_duration": 0.0,
                    "min_duration": 0.0,
                    "max_duration": 0.0,
                    "median_duration": 0.0,
                    "tasks_under_sla": 0,
                    "sla_compliance_rate": 0.0
                }
            
            durations = [duration for _, duration in self._completed_tasks]
            sla_threshold = self._sla_thresholds["task_processing_time"].warning_threshold
            tasks_under_sla = sum(1 for d in durations if d <= sla_threshold)
            
            stats = {
                "total_completed": len(durations),
                "average_duration": statistics.mean(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "median_duration": statistics.median(durations),
                "tasks_under_sla": tasks_under_sla,
                "sla_compliance_rate": (tasks_under_sla / len(durations)) * 100 if durations else 0.0
            }
            
            # Performance categorization
            if len(durations) >= 10:
                stats["percentile_95"] = statistics.quantiles(durations, n=20)[18]  # 95th percentile
                stats["percentile_99"] = statistics.quantiles(durations, n=100)[98]  # 99th percentile
            
            return stats
    
    def get_recent_alerts(self, hours: int = 24) -> List[PerformanceAlert]:
        """Get recent performance alerts."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        with self._metrics_lock:
            return [alert for alert in self._alerts_history if alert.timestamp >= cutoff_time]
    
    def optimize_performance(self) -> Dict[str, Any]:
        """Run performance optimization routines."""
        optimization_results = {
            "timestamp": datetime.now().isoformat(),
            "actions_taken": [],
            "recommendations": []
        }
        
        with self._metrics_lock:
            # Force garbage collection
            if self.enable_auto_gc:
                before_mem = psutil.virtual_memory().percent
                gc.collect()
                after_mem = psutil.virtual_memory().percent
                mem_freed = before_mem - after_mem
                
                optimization_results["actions_taken"].append({
                    "action": "garbage_collection",
                    "memory_freed_percent": mem_freed,
                    "success": True
                })
            
            # Clear old metrics to free memory
            old_size = sum(len(history) for history in self._metrics_history.values())
            for history in self._metrics_history.values():
                if len(history) > self.history_size // 2:
                    # Keep only recent half
                    while len(history) > self.history_size // 2:
                        history.popleft()
            
            new_size = sum(len(history) for history in self._metrics_history.values())
            metrics_cleared = old_size - new_size
            
            if metrics_cleared > 0:
                optimization_results["actions_taken"].append({
                    "action": "metrics_cleanup",
                    "metrics_cleared": metrics_cleared,
                    "success": True
                })
            
            # Generate recommendations based on current performance
            summary = self.get_performance_summary()
            
            for metric_name, sla_info in summary.get("sla_status", {}).items():
                if sla_info["status"] != "compliant":
                    suggestions = self._get_optimization_suggestions(metric_name, sla_info["current_value"])
                    optimization_results["recommendations"].extend(suggestions)
        
        logger.info(f"🔧 Performance optimization completed: {len(optimization_results['actions_taken'])} actions, {len(optimization_results['recommendations'])} recommendations")
        return optimization_results
    
    def __enter__(self):
        """Context manager entry."""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()