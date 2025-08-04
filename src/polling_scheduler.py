"""
Continuous polling scheduler for processing queued tasks at configurable intervals.
Implements circuit breaker pattern and comprehensive error handling.
"""

import time
import threading
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from config import config_manager
from logging_config import get_logger

logger = get_logger(__name__)


class SchedulerState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures detected, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class PollingMetrics:
    """Metrics for polling scheduler performance and health."""
    total_polls: int = 0
    successful_polls: int = 0
    failed_polls: int = 0
    tasks_processed: int = 0
    last_poll_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    average_poll_duration: float = 0.0
    circuit_breaker_trips: int = 0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout: int = 60  # Seconds to wait before attempting recovery
    success_threshold: int = 2  # Successful calls needed to close circuit


class PollingScheduler:
    """
    Continuous polling scheduler that processes queued tasks at configurable intervals.
    
    Features:
    - Configurable polling intervals
    - Graceful start/stop mechanisms
    - Circuit breaker pattern for failure handling
    - Comprehensive error handling and recovery
    - Metrics collection and monitoring
    - Thread-safe operations
    """
    
    def __init__(self, task_processor_callback: Callable[[], Dict[str, Any]], 
                 circuit_breaker_config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize the polling scheduler.
        
        Args:
            task_processor_callback: Function to call for processing queued tasks
            circuit_breaker_config: Circuit breaker configuration
        """
        self.task_processor_callback = task_processor_callback
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        
        # Scheduler state
        self._state = SchedulerState.STOPPED
        self._state_lock = threading.RLock()
        
        # Threading
        self._polling_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Circuit breaker
        self._circuit_state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        
        # Metrics
        self.metrics = PollingMetrics()
        
        logger.info("🕒 Polling scheduler initialized")
    
    def start(self) -> bool:
        """
        Start the continuous polling scheduler.
        
        Returns:
            True if started successfully, False otherwise
        """
        with self._state_lock:
            if self._state != SchedulerState.STOPPED:
                logger.warning(f"⚠️ Cannot start scheduler in state: {self._state}")
                return False
            
            # Check if continuous polling is enabled
            if not config_manager.get_enable_continuous_polling():
                logger.info("ℹ️ Continuous polling is disabled in configuration")
                return False
            
            self._state = SchedulerState.STARTING
            logger.info("🚀 Starting continuous polling scheduler...")
            
            try:
                # Reset shutdown event
                self._shutdown_event.clear()
                
                # Create and start polling thread
                self._polling_thread = threading.Thread(
                    target=self._polling_loop,
                    name="PollingScheduler",
                    daemon=False
                )
                self._polling_thread.start()
                
                # Wait a moment to ensure thread started successfully
                time.sleep(0.1)
                
                if self._polling_thread.is_alive():
                    self._state = SchedulerState.RUNNING
                    interval = config_manager.get_polling_interval_minutes()
                    logger.info(f"✅ Polling scheduler started successfully (interval: {interval} minute(s))")
                    return True
                else:
                    self._state = SchedulerState.FAILED
                    logger.error("❌ Failed to start polling thread")
                    return False
                    
            except Exception as e:
                self._state = SchedulerState.FAILED
                logger.error(f"❌ Failed to start polling scheduler: {e}")
                return False
    
    def stop(self, timeout: float = 30.0) -> bool:
        """
        Stop the continuous polling scheduler gracefully.
        
        Args:
            timeout: Maximum time to wait for shutdown in seconds
            
        Returns:
            True if stopped successfully, False otherwise
        """
        with self._state_lock:
            if self._state in [SchedulerState.STOPPED, SchedulerState.STOPPING]:
                logger.info("ℹ️ Scheduler already stopped or stopping")
                return True
            
            self._state = SchedulerState.STOPPING
            logger.info("⏹️ Stopping polling scheduler...")
            
            try:
                # Signal shutdown
                self._shutdown_event.set()
                
                # Wait for polling thread to finish
                if self._polling_thread and self._polling_thread.is_alive():
                    self._polling_thread.join(timeout=timeout)
                    
                    if self._polling_thread.is_alive():
                        logger.warning(f"⚠️ Polling thread did not stop within {timeout} seconds")
                        return False
                
                self._state = SchedulerState.STOPPED
                logger.info("✅ Polling scheduler stopped successfully")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error stopping polling scheduler: {e}")
                return False
    
    def _polling_loop(self):
        """Main polling loop that runs in a separate thread."""
        logger.info("🔄 Polling loop started")
        
        while not self._shutdown_event.is_set():
            try:
                poll_start_time = datetime.now()
                
                # Check circuit breaker state
                if not self._circuit_breaker_check():
                    logger.info("⚠️ Circuit breaker is open, skipping poll")
                    self._wait_for_next_poll()
                    continue
                
                logger.info("🔍 Starting scheduled poll for queued tasks...")
                
                # Execute task processing callback
                result = self._execute_with_circuit_breaker()
                
                # Update metrics
                poll_duration = (datetime.now() - poll_start_time).total_seconds()
                self._update_metrics(True, poll_duration, result)
                
                logger.info(f"✅ Poll completed successfully in {poll_duration:.2f}s")
                
            except Exception as e:
                poll_duration = (datetime.now() - poll_start_time).total_seconds()
                self._update_metrics(False, poll_duration, None)
                logger.error(f"❌ Poll failed after {poll_duration:.2f}s: {e}")
            
            # Wait for next polling interval
            if not self._shutdown_event.is_set():
                self._wait_for_next_poll()
        
        logger.info("🏁 Polling loop finished")
    
    def _circuit_breaker_check(self) -> bool:
        """
        Check circuit breaker state and determine if polling should proceed.
        
        Returns:
            True if polling should proceed, False otherwise
        """
        now = datetime.now()
        
        if self._circuit_state == CircuitBreakerState.CLOSED:
            return True
        
        elif self._circuit_state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (self._last_failure_time and 
                now - self._last_failure_time >= timedelta(seconds=self.circuit_breaker_config.recovery_timeout)):
                logger.info("🔄 Circuit breaker moving to HALF_OPEN state for recovery test")
                self._circuit_state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        
        elif self._circuit_state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def _execute_with_circuit_breaker(self) -> Dict[str, Any]:
        """
        Execute task processing with circuit breaker pattern.
        
        Returns:
            Result from task processor callback
        
        Raises:
            Exception if circuit breaker trips or callback fails
        """
        try:
            result = self.task_processor_callback()
            
            # Success - handle circuit breaker state
            if self._circuit_state == CircuitBreakerState.HALF_OPEN:
                self._failure_count += 1
                if self._failure_count >= self.circuit_breaker_config.success_threshold:
                    logger.info("✅ Circuit breaker closing - service recovered")
                    self._circuit_state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
            
            return result
            
        except Exception as e:
            # Failure - update circuit breaker
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            if self._circuit_state == CircuitBreakerState.CLOSED:
                if self._failure_count >= self.circuit_breaker_config.failure_threshold:
                    logger.error(f"💥 Circuit breaker opening due to {self._failure_count} consecutive failures")
                    self._circuit_state = CircuitBreakerState.OPEN
                    self.metrics.circuit_breaker_trips += 1
            elif self._circuit_state == CircuitBreakerState.HALF_OPEN:
                logger.error("💥 Circuit breaker reopening due to failure during recovery test")
                self._circuit_state = CircuitBreakerState.OPEN
                self.metrics.circuit_breaker_trips += 1
            
            raise e
    
    def _wait_for_next_poll(self):
        """Wait for the next polling interval or shutdown signal."""
        interval_minutes = config_manager.get_polling_interval_minutes()
        interval_seconds = interval_minutes * 60
        
        logger.info(f"⏱️ Waiting {interval_minutes} minute(s) until next poll...")
        
        # Use shutdown event as interruptible sleep
        self._shutdown_event.wait(timeout=interval_seconds)
    
    def _update_metrics(self, success: bool, duration: float, result: Optional[Dict[str, Any]]):
        """Update polling metrics."""
        now = datetime.now()
        
        self.metrics.total_polls += 1
        self.metrics.last_poll_time = now
        
        if success:
            self.metrics.successful_polls += 1
            self.metrics.last_success_time = now
            
            # Extract task count from result if available
            if result and 'summary' in result:
                tasks_processed = result['summary'].get('successful_tickets', 0)
                self.metrics.tasks_processed += tasks_processed
        else:
            self.metrics.failed_polls += 1
            self.metrics.last_failure_time = now
        
        # Update average duration
        if self.metrics.total_polls > 0:
            self.metrics.average_poll_duration = (
                (self.metrics.average_poll_duration * (self.metrics.total_polls - 1) + duration) / 
                self.metrics.total_polls
            )
    
    
    def get_state(self) -> SchedulerState:
        """Get current scheduler state."""
        with self._state_lock:
            return self._state
    
    def request_shutdown(self):
        """Request graceful shutdown of the polling scheduler."""
        logger.info("📡 Shutdown requested for polling scheduler...")
        self._shutdown_event.set()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current polling metrics.
        
        Returns:
            Dictionary with polling statistics
        """
        return {
            "state": self._state.value,
            "circuit_breaker_state": self._circuit_state.value,
            "total_polls": self.metrics.total_polls,
            "successful_polls": self.metrics.successful_polls,
            "failed_polls": self.metrics.failed_polls,
            "tasks_processed": self.metrics.tasks_processed,
            "success_rate": (self.metrics.successful_polls / self.metrics.total_polls * 100) if self.metrics.total_polls > 0 else 0,
            "average_poll_duration": self.metrics.average_poll_duration,
            "circuit_breaker_trips": self.metrics.circuit_breaker_trips,
            "last_poll_time": self.metrics.last_poll_time.isoformat() if self.metrics.last_poll_time else None,
            "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
            "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
            "polling_interval_minutes": config_manager.get_polling_interval_minutes(),
            "continuous_polling_enabled": config_manager.get_enable_continuous_polling()
        }
    
    def is_running(self) -> bool:
        """Check if scheduler is currently running."""
        return self._state == SchedulerState.RUNNING
    
    def force_poll(self) -> Dict[str, Any]:
        """
        Force an immediate poll (for testing/debugging).
        
        Returns:
            Result from task processor callback
        
        Raises:
            RuntimeError if scheduler is not running
        """
        if not self.is_running():
            raise RuntimeError("Scheduler must be running to force a poll")
        
        logger.info("🚀 Forcing immediate poll...")
        return self.task_processor_callback()