"""
Task Locking and Concurrency Control System

Implements atomic task claiming and safe concurrency control mechanisms
to prevent duplicate task processing in multi-poller environments.
"""

import time
import threading
import hashlib
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)


class LockResult(str, Enum):
    """Results of lock operations."""
    SUCCESS = "success"
    ALREADY_LOCKED = "already_locked"
    STALE_LOCK = "stale_lock"
    INVALID_TASK = "invalid_task"
    TIMEOUT = "timeout"
    ERROR = "error"


class LockState(str, Enum):
    """Lock states for tasks."""
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    STALE = "stale"
    EXPIRED = "expired"


@dataclass
class TaskLock:
    """Represents a task lock with metadata."""
    task_id: str
    owner_id: str
    locked_at: datetime
    expires_at: datetime
    lock_version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if the lock has expired."""
        return datetime.now() > self.expires_at
    
    def is_stale(self, stale_timeout_minutes: int = 30) -> bool:
        """Check if the lock is stale (older than stale timeout)."""
        stale_threshold = datetime.now() - timedelta(minutes=stale_timeout_minutes)
        return self.locked_at < stale_threshold
    
    def time_remaining(self) -> timedelta:
        """Get remaining time before lock expires."""
        return max(timedelta(0), self.expires_at - datetime.now())


@dataclass
class LockAttemptResult:
    """Result of a lock attempt operation."""
    result: LockResult
    task_lock: Optional[TaskLock] = None
    error_message: Optional[str] = None
    existing_owner: Optional[str] = None
    retry_after_seconds: Optional[int] = None


@dataclass
class LockMetrics:
    """Metrics for lock operations."""
    total_attempts: int = 0
    successful_locks: int = 0
    failed_locks: int = 0
    stale_locks_cleaned: int = 0
    deadlocks_detected: int = 0
    average_lock_duration: float = 0.0
    lock_contention_rate: float = 0.0
    
    def get_success_rate(self) -> float:
        """Calculate lock success rate."""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_locks / self.total_attempts) * 100
    
    def get_contention_rate(self) -> float:
        """Calculate lock contention rate."""
        if self.total_attempts == 0:
            return 0.0
        return ((self.failed_locks - self.stale_locks_cleaned) / self.total_attempts) * 100


class TaskLockManager(ABC):
    """Abstract base class for task lock management."""
    
    @abstractmethod
    def try_lock_task(self, task_id: str, owner_id: str, 
                     timeout_minutes: int = 30) -> LockAttemptResult:
        """
        Attempt to acquire a lock on a task.
        
        Args:
            task_id: Unique identifier for the task
            owner_id: Unique identifier for the lock owner
            timeout_minutes: Lock timeout in minutes
            
        Returns:
            LockAttemptResult with success/failure information
        """
        pass
    
    @abstractmethod
    def release_lock(self, task_id: str, owner_id: str) -> bool:
        """
        Release a lock on a task.
        
        Args:
            task_id: Task identifier
            owner_id: Owner identifier
            
        Returns:
            True if lock was released, False otherwise
        """
        pass
    
    @abstractmethod
    def get_task_lock(self, task_id: str) -> Optional[TaskLock]:
        """
        Get current lock information for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskLock if locked, None if unlocked
        """
        pass
    
    @abstractmethod
    def cleanup_stale_locks(self, stale_timeout_minutes: int = 30) -> int:
        """
        Clean up stale/expired locks.
        
        Args:
            stale_timeout_minutes: Time after which locks are considered stale
            
        Returns:
            Number of locks cleaned up
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> LockMetrics:
        """Get lock operation metrics."""
        pass


class InMemoryTaskLockManager(TaskLockManager):
    """
    In-memory implementation of task lock manager.
    Suitable for single-instance deployments or testing.
    """
    
    def __init__(self):
        self._locks: Dict[str, TaskLock] = {}
        self._lock_mutex = threading.RLock()
        self._metrics = LockMetrics()
        self._lock_durations: List[float] = []
        
        logger.info("🔒 InMemoryTaskLockManager initialized")
    
    def try_lock_task(self, task_id: str, owner_id: str, 
                     timeout_minutes: int = 30) -> LockAttemptResult:
        """Attempt to acquire a lock on a task."""
        start_time = time.time()
        
        with self._lock_mutex:
            self._metrics.total_attempts += 1
            
            try:
                # Check if task is already locked
                existing_lock = self._locks.get(task_id)
                
                if existing_lock:
                    # Check if lock is expired or stale
                    if existing_lock.is_expired():
                        logger.info(f"🕐 Removing expired lock for task {task_id}")
                        del self._locks[task_id]
                        existing_lock = None
                    elif existing_lock.is_stale():
                        logger.warning(f"🚨 Removing stale lock for task {task_id} (owned by {existing_lock.owner_id})")
                        del self._locks[task_id]
                        self._metrics.stale_locks_cleaned += 1
                        existing_lock = None
                    elif existing_lock.owner_id == owner_id:
                        # Same owner trying to re-lock - update expiration
                        existing_lock.expires_at = datetime.now() + timedelta(minutes=timeout_minutes)
                        existing_lock.lock_version += 1
                        
                        logger.info(f"🔄 Renewed lock for task {task_id} by owner {owner_id}")
                        return LockAttemptResult(
                            result=LockResult.SUCCESS,
                            task_lock=existing_lock
                        )
                    else:
                        # Task is locked by someone else
                        self._metrics.failed_locks += 1
                        retry_after = int(existing_lock.time_remaining().total_seconds())
                        
                        logger.debug(f"🚫 Task {task_id} already locked by {existing_lock.owner_id}")
                        return LockAttemptResult(
                            result=LockResult.ALREADY_LOCKED,
                            existing_owner=existing_lock.owner_id,
                            retry_after_seconds=max(60, retry_after)  # At least 1 minute
                        )
                
                # Create new lock
                now = datetime.now()
                new_lock = TaskLock(
                    task_id=task_id,
                    owner_id=owner_id,
                    locked_at=now,
                    expires_at=now + timedelta(minutes=timeout_minutes),
                    lock_version=1,
                    metadata={
                        "lock_attempt_duration": time.time() - start_time,
                        "created_by": "InMemoryTaskLockManager"
                    }
                )
                
                self._locks[task_id] = new_lock
                self._metrics.successful_locks += 1
                
                logger.info(f"✅ Successfully locked task {task_id} for owner {owner_id} (expires in {timeout_minutes} minutes)")
                
                return LockAttemptResult(
                    result=LockResult.SUCCESS,
                    task_lock=new_lock
                )
                
            except Exception as e:
                self._metrics.failed_locks += 1
                logger.error(f"❌ Error attempting to lock task {task_id}: {e}")
                
                return LockAttemptResult(
                    result=LockResult.ERROR,
                    error_message=str(e)
                )
    
    def release_lock(self, task_id: str, owner_id: str) -> bool:
        """Release a lock on a task."""
        with self._lock_mutex:
            try:
                existing_lock = self._locks.get(task_id)
                
                if not existing_lock:
                    logger.warning(f"⚠️ Attempted to release non-existent lock for task {task_id}")
                    return False
                
                if existing_lock.owner_id != owner_id:
                    logger.error(f"🚫 Cannot release lock for task {task_id}: owned by {existing_lock.owner_id}, not {owner_id}")
                    return False
                
                # Calculate lock duration for metrics
                lock_duration = (datetime.now() - existing_lock.locked_at).total_seconds()
                self._lock_durations.append(lock_duration)
                
                # Keep only recent durations for average calculation
                if len(self._lock_durations) > 1000:
                    self._lock_durations = self._lock_durations[-500:]
                
                # Update average lock duration
                if self._lock_durations:
                    self._metrics.average_lock_duration = sum(self._lock_durations) / len(self._lock_durations)
                
                del self._locks[task_id]
                
                logger.info(f"🔓 Released lock for task {task_id} by owner {owner_id} (held for {lock_duration:.1f}s)")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error releasing lock for task {task_id}: {e}")
                return False
    
    def get_task_lock(self, task_id: str) -> Optional[TaskLock]:
        """Get current lock information for a task."""
        with self._lock_mutex:
            lock = self._locks.get(task_id)
            
            if lock and lock.is_expired():
                logger.info(f"🕐 Removing expired lock for task {task_id}")
                del self._locks[task_id]
                return None
            
            return lock
    
    def cleanup_stale_locks(self, stale_timeout_minutes: int = 30) -> int:
        """Clean up stale/expired locks."""
        with self._lock_mutex:
            stale_tasks = []
            now = datetime.now()
            
            for task_id, lock in self._locks.items():
                if lock.is_expired() or lock.is_stale(stale_timeout_minutes):
                    stale_tasks.append(task_id)
            
            for task_id in stale_tasks:
                lock = self._locks[task_id]
                del self._locks[task_id]
                
                if lock.is_expired():
                    logger.info(f"🧹 Cleaned up expired lock for task {task_id} (expired {(now - lock.expires_at).total_seconds():.0f}s ago)")
                else:
                    logger.warning(f"🧹 Cleaned up stale lock for task {task_id} (locked {(now - lock.locked_at).total_seconds():.0f}s ago)")
            
            if stale_tasks:
                self._metrics.stale_locks_cleaned += len(stale_tasks)
                logger.info(f"🧹 Cleaned up {len(stale_tasks)} stale/expired locks")
            
            return len(stale_tasks)
    
    def get_metrics(self) -> LockMetrics:
        """Get lock operation metrics."""
        with self._lock_mutex:
            # Update contention rate
            if self._metrics.total_attempts > 0:
                contention_failures = self._metrics.failed_locks - self._metrics.stale_locks_cleaned
                self._metrics.lock_contention_rate = (contention_failures / self._metrics.total_attempts) * 100
            
            return LockMetrics(
                total_attempts=self._metrics.total_attempts,
                successful_locks=self._metrics.successful_locks,
                failed_locks=self._metrics.failed_locks,
                stale_locks_cleaned=self._metrics.stale_locks_cleaned,
                deadlocks_detected=self._metrics.deadlocks_detected,
                average_lock_duration=self._metrics.average_lock_duration,
                lock_contention_rate=self._metrics.lock_contention_rate
            )
    
    def get_active_locks(self) -> Dict[str, TaskLock]:
        """Get all currently active locks."""
        with self._lock_mutex:
            return self._locks.copy()
    
    def force_release_all_locks(self) -> int:
        """Force release all locks (for testing/emergency use)."""
        with self._lock_mutex:
            count = len(self._locks)
            self._locks.clear()
            logger.warning(f"🚨 Force released all {count} locks")
            return count


class DatabaseTaskLockManager(TaskLockManager):
    """
    Database-backed implementation of task lock manager.
    Suitable for multi-instance deployments with shared database.
    """
    
    def __init__(self, database_operations):
        """
        Initialize with database operations instance.
        
        Args:
            database_operations: DatabaseOperations instance for persistence
        """
        self.db_ops = database_operations
        self._metrics = LockMetrics()
        self._instance_id = self._generate_instance_id()
        
        logger.info(f"🔒 DatabaseTaskLockManager initialized (instance: {self._instance_id})")
    
    def _generate_instance_id(self) -> str:
        """Generate unique instance identifier."""
        # Use combination of timestamp and random UUID
        timestamp = str(int(time.time() * 1000))
        unique_id = str(uuid.uuid4())[:8]
        return f"poller-{timestamp}-{unique_id}"
    
    def try_lock_task(self, task_id: str, owner_id: str, 
                     timeout_minutes: int = 30) -> LockAttemptResult:
        """
        Attempt to acquire a lock on a task using database-level atomic operations.
        
        This implementation uses the task status field as the locking mechanism:
        - Only tasks with 'Queued' status can be locked
        - Locking changes status to 'In progress' atomically
        - Owner information is stored in metadata
        """
        start_time = time.time()
        self._metrics.total_attempts += 1
        
        try:
            # Create lock metadata
            now = datetime.now()
            lock_metadata = {
                "locked_by": owner_id,
                "locked_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=timeout_minutes)).isoformat(),
                "instance_id": self._instance_id,
                "lock_version": 1
            }
            
            # Attempt atomic status update from 'Queued' to 'In progress'
            # This serves as the locking mechanism
            success = self._atomic_status_update(
                task_id=task_id,
                from_status="Queued to run",
                to_status="In progress",
                lock_metadata=lock_metadata
            )
            
            if success:
                task_lock = TaskLock(
                    task_id=task_id,
                    owner_id=owner_id,
                    locked_at=now,
                    expires_at=now + timedelta(minutes=timeout_minutes),
                    lock_version=1,
                    metadata=lock_metadata
                )
                
                self._metrics.successful_locks += 1
                
                logger.info(f"✅ Successfully locked task {task_id} for owner {owner_id} via database")
                
                return LockAttemptResult(
                    result=LockResult.SUCCESS,
                    task_lock=task_lock
                )
            else:
                # Check if task is in different state (might be already locked)
                task_status = self._get_task_status(task_id)
                
                if task_status == "In progress":
                    # Task is already being processed
                    existing_owner = self._get_task_lock_owner(task_id)
                    self._metrics.failed_locks += 1
                    
                    logger.debug(f"🚫 Task {task_id} already locked (in progress) by {existing_owner}")
                    
                    return LockAttemptResult(
                        result=LockResult.ALREADY_LOCKED,
                        existing_owner=existing_owner,
                        retry_after_seconds=300  # 5 minutes
                    )
                else:
                    # Task might not exist or be in invalid state
                    self._metrics.failed_locks += 1
                    
                    logger.warning(f"⚠️ Cannot lock task {task_id}: current status is {task_status}")
                    
                    return LockAttemptResult(
                        result=LockResult.INVALID_TASK,
                        error_message=f"Task status is {task_status}, expected 'Queued to run'"
                    )
                    
        except Exception as e:
            self._metrics.failed_locks += 1
            logger.error(f"❌ Error attempting to lock task {task_id}: {e}")
            
            return LockAttemptResult(
                result=LockResult.ERROR,
                error_message=str(e)
            )
    
    def release_lock(self, task_id: str, owner_id: str) -> bool:
        """Release a lock by updating task status."""
        try:
            # Verify ownership before releasing
            current_owner = self._get_task_lock_owner(task_id)
            if current_owner != owner_id:
                logger.error(f"🚫 Cannot release lock for task {task_id}: owned by {current_owner}, not {owner_id}")
                return False
            
            # Update status back to queued or to done/failed based on context
            # For now, we'll assume the calling code manages the final status
            logger.info(f"🔓 Lock released for task {task_id} by owner {owner_id} (status transition managed externally)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error releasing lock for task {task_id}: {e}")
            return False
    
    def get_task_lock(self, task_id: str) -> Optional[TaskLock]:
        """Get current lock information for a task."""
        try:
            status = self._get_task_status(task_id)
            
            if status == "In progress":
                # Task is locked, get lock metadata
                owner = self._get_task_lock_owner(task_id)
                lock_metadata = self._get_task_lock_metadata(task_id)
                
                if lock_metadata:
                    locked_at = datetime.fromisoformat(lock_metadata.get("locked_at", datetime.now().isoformat()))
                    expires_at = datetime.fromisoformat(lock_metadata.get("expires_at", datetime.now().isoformat()))
                    
                    return TaskLock(
                        task_id=task_id,
                        owner_id=owner,
                        locked_at=locked_at,
                        expires_at=expires_at,
                        lock_version=lock_metadata.get("lock_version", 1),
                        metadata=lock_metadata
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting lock for task {task_id}: {e}")
            return None
    
    def cleanup_stale_locks(self, stale_timeout_minutes: int = 30) -> int:
        """Clean up stale locks by resetting expired 'In progress' tasks."""
        try:
            # This would require querying for tasks in 'In progress' status
            # and checking their lock metadata for expiration
            # Implementation depends on the specific database schema
            
            logger.info("🧹 Database lock cleanup not implemented yet (requires schema design)")
            return 0
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up stale locks: {e}")
            return 0
    
    def get_metrics(self) -> LockMetrics:
        """Get lock operation metrics."""
        return self._metrics
    
    def _atomic_status_update(self, task_id: str, from_status: str, to_status: str, 
                            lock_metadata: Dict[str, Any]) -> bool:
        """
        Perform atomic status update (compare-and-swap operation).
        
        This is a placeholder for the actual database implementation.
        The real implementation would use database-specific atomic operations.
        """
        # This would be implemented using database-specific atomic operations
        # For example, in SQL: UPDATE tasks SET status = ? WHERE id = ? AND status = ?
        # Returns True only if exactly one row was updated
        
        logger.debug(f"🔄 Atomic status update for task {task_id}: {from_status} -> {to_status}")
        
        # Placeholder implementation - would be replaced with actual database call
        return True  # Simulated success
    
    def _get_task_status(self, task_id: str) -> Optional[str]:
        """Get current status of a task."""
        # Placeholder - would query database for task status
        return "Queued to run"  # Simulated status
    
    def _get_task_lock_owner(self, task_id: str) -> Optional[str]:
        """Get the owner of a task lock."""
        # Placeholder - would extract from task metadata
        return self._instance_id  # Simulated owner
    
    def _get_task_lock_metadata(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get lock metadata for a task."""
        # Placeholder - would extract from task properties
        return {
            "locked_by": self._instance_id,
            "locked_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=30)).isoformat(),
            "instance_id": self._instance_id,
            "lock_version": 1
        }


class TaskLockManagerFactory:
    """Factory for creating task lock manager instances."""
    
    @staticmethod
    def create_lock_manager(manager_type: str = "memory", **kwargs) -> TaskLockManager:
        """
        Create a task lock manager instance.
        
        Args:
            manager_type: Type of manager ("memory" or "database")
            **kwargs: Additional arguments for specific manager types
            
        Returns:
            TaskLockManager instance
        """
        if manager_type.lower() == "memory":
            return InMemoryTaskLockManager()
        elif manager_type.lower() == "database":
            database_operations = kwargs.get("database_operations")
            if not database_operations:
                raise ValueError("database_operations required for DatabaseTaskLockManager")
            return DatabaseTaskLockManager(database_operations)
        else:
            raise ValueError(f"Unknown manager type: {manager_type}")


# Utility functions for common locking patterns

def with_task_lock(lock_manager: TaskLockManager, task_id: str, owner_id: str, 
                  timeout_minutes: int = 30):
    """Context manager for task locking."""
    
    class TaskLockContext:
        def __init__(self):
            self.lock_result = None
            self.acquired = False
        
        def __enter__(self):
            self.lock_result = lock_manager.try_lock_task(task_id, owner_id, timeout_minutes)
            self.acquired = self.lock_result.result == LockResult.SUCCESS
            
            if not self.acquired:
                raise RuntimeError(f"Failed to acquire lock for task {task_id}: {self.lock_result.result}")
            
            return self.lock_result.task_lock
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.acquired:
                success = lock_manager.release_lock(task_id, owner_id)
                if not success:
                    logger.warning(f"⚠️ Failed to release lock for task {task_id}")
    
    return TaskLockContext()


def safe_task_claim(lock_manager: TaskLockManager, task_id: str, owner_id: str,
                   processor_func, timeout_minutes: int = 30) -> Tuple[bool, Any]:
    """
    Safely claim and process a task with automatic lock management.
    
    Args:
        lock_manager: Task lock manager instance
        task_id: Task identifier
        owner_id: Owner identifier
        processor_func: Function to process the task
        timeout_minutes: Lock timeout
        
    Returns:
        Tuple of (success, result)
    """
    try:
        with with_task_lock(lock_manager, task_id, owner_id, timeout_minutes) as task_lock:
            logger.info(f"🔒 Processing task {task_id} with lock {task_lock.lock_version}")
            result = processor_func(task_id)
            return True, result
            
    except RuntimeError as e:
        logger.warning(f"⚠️ Could not acquire lock for task {task_id}: {e}")
        return False, None
    except Exception as e:
        logger.error(f"❌ Error processing task {task_id}: {e}")
        return False, str(e)