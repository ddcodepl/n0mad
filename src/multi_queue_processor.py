#!/usr/bin/env python3
"""
Multi-Queue Task Processor - Orchestrates sequential processing of multiple queued tasks
Handles task prioritization, resource management, error recovery, and progress tracking.
"""
import threading
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from logging_config import get_logger
from feedback_manager import ProcessingStage

logger = get_logger(__name__)


class ProcessingResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueuedTaskItem:
    """Represents a task in the processing queue"""
    task_id: str
    page_id: str
    title: str
    priority: TaskPriority
    queued_time: datetime
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None
    retry_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ProcessingSession:
    """Represents a multi-queue processing session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_tasks: int = 0
    processed_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    cancelled_tasks: int = 0
    processing_results: List[Dict[str, Any]] = None
    error_summary: List[Dict[str, Any]] = None


class MultiQueueProcessor:
    """
    Orchestrates sequential processing of multiple queued tasks with resource management,
    error recovery, and progress tracking for multi-queue scenarios.
    """
    
    def __init__(self, 
                 database_ops,
                 status_manager, 
                 feedback_manager, 
                 claude_invoker, 
                 task_file_manager,
                 max_retry_attempts: int = 3,
                 task_timeout_minutes: int = 30,
                 inter_task_delay_seconds: int = 2):
        self.database_ops = database_ops
        self.status_manager = status_manager
        self.feedback_manager = feedback_manager
        self.claude_invoker = claude_invoker
        self.task_file_manager = task_file_manager
        
        self.max_retry_attempts = max_retry_attempts
        self.task_timeout_seconds = task_timeout_minutes * 60
        self.inter_task_delay_seconds = inter_task_delay_seconds
        
        self._processing_lock = threading.RLock()
        self._session_history: List[ProcessingSession] = []
        self._max_history = 50
        self._current_session: Optional[ProcessingSession] = None
        self._cancellation_requested = False
        
        # Task priority mapping for sorting
        self._priority_weights = {
            TaskPriority.CRITICAL: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 1
        }
        
        logger.info("🚀 MultiQueueProcessor initialized")
        logger.info(f"   🔄 Max retry attempts: {max_retry_attempts}")
        logger.info(f"   ⏰ Task timeout: {task_timeout_minutes}m")
        logger.info(f"   ⏱️ Inter-task delay: {inter_task_delay_seconds}s")
    
    def process_queued_tasks(self, cancellation_check: callable = None) -> ProcessingSession:
        """
        Process all queued tasks sequentially with proper orchestration.
        
        Args:
            cancellation_check: Optional callable that returns True if processing should be cancelled
            
        Returns:
            ProcessingSession with complete results and statistics
        """
        session_id = f"multi_queue_{int(datetime.now().timestamp())}"
        
        with self._processing_lock:
            try:
                logger.info("🎬 Starting multi-queue task processing session")
                logger.info(f"   🆔 Session ID: {session_id}")
                
                # Initialize processing session
                self._current_session = ProcessingSession(
                    session_id=session_id,
                    start_time=datetime.now(),
                    processing_results=[],
                    error_summary=[]
                )
                
                # Step 1: Discover and prioritize queued tasks
                logger.info("📋 Step 1: Discovering and prioritizing queued tasks...")
                task_queue = self._discover_and_prioritize_tasks()
                
                if not task_queue:
                    logger.info("ℹ️  No queued tasks found")
                    self._current_session.end_time = datetime.now()
                    self._finalize_session()
                    return self._current_session
                
                self._current_session.total_tasks = len(task_queue)
                logger.info(f"✅ Discovered {len(task_queue)} queued tasks for processing")
                
                # Step 2: Pre-processing validation and setup
                logger.info("🔍 Step 2: Pre-processing validation and resource setup...")
                self._prepare_processing_environment()
                
                # Step 3: Sequential task processing with orchestration
                logger.info("⚡ Step 3: Sequential task processing...")
                self._process_task_queue(task_queue, cancellation_check)
                
                # Step 4: Post-processing cleanup and summary
                logger.info("🧹 Step 4: Post-processing cleanup and summary...")
                self._cleanup_processing_environment()
                
                self._current_session.end_time = datetime.now()
                self._finalize_session()
                
                # Log final summary
                self._log_session_summary()
                
                return self._current_session
                
            except Exception as e:
                logger.error(f"❌ Critical error in multi-queue processing: {e}")
                if self._current_session:
                    self._current_session.end_time = datetime.now()
                    self._current_session.error_summary.append({
                        "type": "critical_session_error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    self._finalize_session()
                raise e
    
    def _discover_and_prioritize_tasks(self) -> List[QueuedTaskItem]:
        """
        Discover all queued tasks and prioritize them for processing.
        
        Returns:
            Prioritized list of QueuedTaskItem objects
        """
        try:
            # Get all queued tasks from database
            raw_tasks = self.database_ops.get_queued_tasks()
            
            if not raw_tasks:
                return []
            
            # Convert to QueuedTaskItem objects with priority assessment
            task_items = []
            for task in raw_tasks:
                try:
                    # Extract priority from task metadata or default to medium
                    priority = self._assess_task_priority(task)
                    
                    task_item = QueuedTaskItem(
                        task_id=task.get("ticket_id"),
                        page_id=task.get("id"),
                        title=task.get("title", "Untitled"),
                        priority=priority,
                        queued_time=datetime.now(),  # Could be extracted from task metadata
                        dependencies=task.get("dependencies", []),
                        metadata=task
                    )
                    task_items.append(task_item)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to process task item: {e}")
                    continue
            
            # Sort by priority (critical first, then by queued time)
            sorted_tasks = sorted(
                task_items,
                key=lambda t: (
                    -self._priority_weights.get(t.priority, 2),  # Higher priority first
                    t.queued_time  # Earlier queued time first for same priority
                )
            )
            
            logger.info(f"📊 Task prioritization completed:")
            priority_counts = {}
            for task in sorted_tasks:
                priority_counts[task.priority.value] = priority_counts.get(task.priority.value, 0) + 1
                logger.info(f"   🎫 {task.task_id} - {task.title[:50]}... (Priority: {task.priority.value})")
            
            for priority, count in priority_counts.items():
                logger.info(f"   📊 {priority.upper()}: {count} tasks")
            
            return sorted_tasks
            
        except Exception as e:
            logger.error(f"❌ Error discovering and prioritizing tasks: {e}")
            return []
    
    def _assess_task_priority(self, task: Dict[str, Any]) -> TaskPriority:
        """
        Assess task priority based on various factors.
        
        Args:
            task: Raw task data from database
            
        Returns:
            TaskPriority enum value
        """
        # Check for explicit priority in task properties
        if "priority" in task:
            priority_str = str(task["priority"]).lower()
            if priority_str in ["critical", "urgent"]:
                return TaskPriority.CRITICAL
            elif priority_str in ["high", "important"]:
                return TaskPriority.HIGH
            elif priority_str in ["low", "minor"]:
                return TaskPriority.LOW
        
        # Check for priority indicators in title
        title = task.get("title", "").lower()
        if any(keyword in title for keyword in ["urgent", "critical", "emergency", "hotfix"]):
            return TaskPriority.CRITICAL
        elif any(keyword in title for keyword in ["important", "high", "priority"]):
            return TaskPriority.HIGH
        elif any(keyword in title for keyword in ["minor", "low", "trivial"]):
            return TaskPriority.LOW
        
        # Default to medium priority
        return TaskPriority.MEDIUM
    
    def _prepare_processing_environment(self):
        """Prepare the processing environment and validate resources."""
        logger.info("🔧 Preparing processing environment...")
        
        # Cleanup any stale resources from previous sessions
        self.claude_invoker.cleanup_active_processes()
        
        # Cleanup old backup files to free space
        try:
            cleanup_results = self.task_file_manager.cleanup_backups(max_age_days=7)
            if cleanup_results and cleanup_results.get('cleaned_files', 0) > 0:
                logger.info(f"🧹 Cleanup: {cleanup_results['cleaned_files']} old backups removed")
        except Exception as e:
            logger.warning(f"⚠️ Backup cleanup error: {e}")
        
        # Validate system resources and readiness
        # This could include checking disk space, memory, network connectivity, etc.
        logger.info("✅ Processing environment prepared")
    
    def _process_task_queue(self, task_queue: List[QueuedTaskItem], cancellation_check: callable = None):
        """
        Process the prioritized task queue sequentially.
        
        Args:
            task_queue: Prioritized list of tasks to process
            cancellation_check: Optional cancellation check function
        """
        for i, task_item in enumerate(task_queue):
            try:
                # Check for cancellation
                if cancellation_check and cancellation_check():
                    logger.info("⏹️ Processing cancellation requested")
                    self._cancellation_requested = True
                    break
                
                if self._cancellation_requested:
                    break
                
                logger.info(f"📄 Processing task {i+1}/{len(task_queue)}: {task_item.title}")
                logger.info(f"   🎫 Ticket ID: {task_item.task_id}")
                logger.info(f"   📊 Priority: {task_item.priority.value}")
                
                # Process individual task with retry logic
                result = self._process_single_task_with_retry(task_item)
                
                # Record result
                self._current_session.processing_results.append(result)
                self._current_session.processed_tasks += 1
                
                # Update counters based on result
                if result["status"] == ProcessingResult.SUCCESS:
                    self._current_session.successful_tasks += 1
                elif result["status"] == ProcessingResult.FAILED:
                    self._current_session.failed_tasks += 1
                elif result["status"] == ProcessingResult.SKIPPED:
                    self._current_session.skipped_tasks += 1
                elif result["status"] == ProcessingResult.CANCELLED:
                    self._current_session.cancelled_tasks += 1
                
                # Inter-task delay for resource recovery
                if i < len(task_queue) - 1 and not self._cancellation_requested:
                    logger.info(f"⏱️ Inter-task delay: {self.inter_task_delay_seconds}s")
                    time.sleep(self.inter_task_delay_seconds)
                
            except Exception as e:
                logger.error(f"❌ Unexpected error processing task {task_item.task_id}: {e}")
                
                # Record error
                error_result = {
                    "task_id": task_item.task_id,
                    "page_id": task_item.page_id,
                    "title": task_item.title,
                    "status": ProcessingResult.FAILED,
                    "error": str(e),
                    "processing_time": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
                
                self._current_session.processing_results.append(error_result)
                self._current_session.processed_tasks += 1
                self._current_session.failed_tasks += 1
                
                self._current_session.error_summary.append({
                    "task_id": task_item.task_id,
                    "type": "processing_error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
                continue  # Continue with next task
        
        # Handle remaining tasks if cancelled
        if self._cancellation_requested:
            remaining_tasks = task_queue[self._current_session.processed_tasks:]
            for task_item in remaining_tasks:
                cancelled_result = {
                    "task_id": task_item.task_id,
                    "page_id": task_item.page_id,
                    "title": task_item.title,
                    "status": ProcessingResult.CANCELLED,
                    "error": "Processing cancelled",
                    "processing_time": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
                self._current_session.processing_results.append(cancelled_result)
                self._current_session.cancelled_tasks += 1
    
    def _process_single_task_with_retry(self, task_item: QueuedTaskItem) -> Dict[str, Any]:
        """
        Process a single task with retry logic and comprehensive error handling.
        
        Args:
            task_item: Task to process
            
        Returns:
            Dictionary with processing results
        """
        start_time = datetime.now()
        
        for attempt in range(self.max_retry_attempts + 1):
            try:
                if attempt > 0:
                    logger.info(f"🔄 Retry attempt {attempt}/{self.max_retry_attempts} for task {task_item.task_id}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                
                # Attempt to process the task
                result = self._execute_single_task(task_item)
                
                if result["status"] == ProcessingResult.SUCCESS:
                    processing_time = (datetime.now() - start_time).total_seconds()
                    result["processing_time"] = processing_time
                    result["retry_count"] = attempt
                    logger.info(f"✅ Task {task_item.task_id} completed successfully on attempt {attempt + 1}")
                    return result
                
                # If not successful, prepare for retry
                task_item.retry_count = attempt + 1
                task_item.last_error = result.get("error", "Unknown error")
                
                if attempt < self.max_retry_attempts:
                    logger.warning(f"⚠️ Task {task_item.task_id} failed on attempt {attempt + 1}, will retry")
                    continue
                else:
                    logger.error(f"❌ Task {task_item.task_id} failed after {self.max_retry_attempts} attempts")
                    processing_time = (datetime.now() - start_time).total_seconds()
                    result["processing_time"] = processing_time
                    result["retry_count"] = attempt + 1
                    return result
                
            except Exception as e:
                logger.error(f"❌ Exception during task processing attempt {attempt + 1}: {e}")
                
                if attempt >= self.max_retry_attempts:
                    processing_time = (datetime.now() - start_time).total_seconds()
                    return {
                        "task_id": task_item.task_id,
                        "page_id": task_item.page_id,
                        "title": task_item.title,
                        "status": ProcessingResult.FAILED,
                        "error": str(e),
                        "processing_time": processing_time,
                        "retry_count": attempt + 1,
                        "timestamp": datetime.now().isoformat()
                    }
        
        # Should not reach here, but failsafe
        processing_time = (datetime.now() - start_time).total_seconds()
        return {
            "task_id": task_item.task_id,
            "page_id": task_item.page_id,
            "title": task_item.title,
            "status": ProcessingResult.FAILED,
            "error": "Max retries exceeded",
            "processing_time": processing_time,
            "retry_count": self.max_retry_attempts + 1,
            "timestamp": datetime.now().isoformat()
        }
    
    def _execute_single_task(self, task_item: QueuedTaskItem) -> Dict[str, Any]:
        """
        Execute a single task through the complete processing pipeline.
        
        Args:
            task_item: Task to execute
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Step 1: Status transition to 'In progress'
            transition_to_progress = self.status_manager.transition_status(
                task_item.page_id, "Queued to run", "In progress"
            )
            
            if transition_to_progress.result != "success":
                self.feedback_manager.add_status_transition_feedback(
                    task_item.page_id, "Queued to run", "In progress", False, transition_to_progress.error
                )
                return {
                    "task_id": task_item.task_id,
                    "page_id": task_item.page_id,
                    "title": task_item.title,
                    "status": ProcessingResult.FAILED,
                    "error": f"Status transition failed: {transition_to_progress.error}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Add progress feedback
            self.feedback_manager.add_status_transition_feedback(
                task_item.page_id, "Queued to run", "In progress", True
            )
            
            # Step 2: Claude engine invocation
            logger.info(f"🤖 Invoking Claude engine for task {task_item.task_id}")
            self.feedback_manager.add_feedback(
                task_item.page_id, ProcessingStage.PROCESSING,
                "Starting Claude engine invocation",
                details=f"Multi-queue processing: task {task_item.task_id}"
            )
            
            invocation_result = self.claude_invoker.invoke_claude_engine(task_item.task_id, task_item.page_id)
            
            if invocation_result.result != "success":
                error_msg = f"Claude invocation failed: {invocation_result.error}"
                self.feedback_manager.add_feedback(
                    task_item.page_id, ProcessingStage.PROCESSING,
                    "Claude engine invocation failed",
                    error=error_msg
                )
                
                # Attempt rollback
                rollback_result = self.status_manager.rollback_transition(transition_to_progress)
                if rollback_result.rollback_result == "rollback_success":
                    logger.info(f"✅ Rolled back task {task_item.task_id} to 'Queued to run'")
                
                return {
                    "task_id": task_item.task_id,
                    "page_id": task_item.page_id,
                    "title": task_item.title,
                    "status": ProcessingResult.FAILED,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Add success feedback for Claude invocation
            self.feedback_manager.add_feedback(
                task_item.page_id, ProcessingStage.PROCESSING,
                "Claude engine invocation completed successfully",
                details=f"Duration: {invocation_result.duration_seconds:.2f}s"
            )
            
            # Step 3: Task file copy to TaskMaster
            logger.info(f"📋 Copying task file for {task_item.task_id}")
            self.feedback_manager.add_feedback(
                task_item.page_id, ProcessingStage.COPYING, 
                "Starting task file copy to TaskMaster"
            )
            
            copy_operation = self.task_file_manager.copy_task_file_to_taskmaster(task_item.task_id)
            
            if copy_operation.result == "success":
                self.feedback_manager.add_feedback(
                    task_item.page_id, ProcessingStage.COPYING,
                    "Task file copy completed successfully",
                    details=f"Copied {copy_operation.source_size} bytes"
                )
            else:
                # Log warning but continue - file copy failure is not critical
                logger.warning(f"⚠️ Task file copy failed for {task_item.task_id}: {copy_operation.error}")
                self.feedback_manager.add_feedback(
                    task_item.page_id, ProcessingStage.COPYING,
                    "Task file copy failed - continuing with processing",
                    error=copy_operation.error
                )
            
            # Step 4: Final status transition to 'Done'
            transition_to_done = self.status_manager.transition_status(
                task_item.page_id, "In progress", "Done"
            )
            
            if transition_to_done.result != "success":
                error_msg = f"Final status transition failed: {transition_to_done.error}"
                self.feedback_manager.add_status_transition_feedback(
                    task_item.page_id, "In progress", "Done", False, transition_to_done.error
                )
                
                return {
                    "task_id": task_item.task_id,
                    "page_id": task_item.page_id,
                    "title": task_item.title,
                    "status": ProcessingResult.FAILED,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Add final success feedback
            self.feedback_manager.add_status_transition_feedback(
                task_item.page_id, "In progress", "Done", True
            )
            
            self.feedback_manager.add_feedback(
                task_item.page_id, ProcessingStage.FINALIZING,
                "Task processing completed successfully",
                details=f"Multi-queue processing: task {task_item.task_id} completed"
            )
            
            return {
                "task_id": task_item.task_id,
                "page_id": task_item.page_id,
                "title": task_item.title,
                "status": ProcessingResult.SUCCESS,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error executing task {task_item.task_id}: {e}")
            
            # Add error feedback if possible
            try:
                self.feedback_manager.add_feedback(
                    task_item.page_id, ProcessingStage.ERROR_HANDLING,
                    f"Task execution error: {str(e)}",
                    error=str(e)
                )
            except:
                pass  # Don't fail on feedback errors
            
            return {
                "task_id": task_item.task_id,
                "page_id": task_item.page_id,
                "title": task_item.title,
                "status": ProcessingResult.FAILED,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _cleanup_processing_environment(self):
        """Clean up processing environment after session completion."""
        logger.info("🧹 Cleaning up processing environment...")
        
        # Cleanup any active processes
        self.claude_invoker.cleanup_active_processes()
        
        # Final backup cleanup
        try:
            cleanup_results = self.task_file_manager.cleanup_backups(max_age_days=1)
            if cleanup_results and cleanup_results.get('cleaned_files', 0) > 0:
                logger.info(f"🧹 Final cleanup: {cleanup_results['cleaned_files']} files removed")
        except Exception as e:
            logger.warning(f"⚠️ Backup cleanup error: {e}")
        
        logger.info("✅ Processing environment cleanup completed")
    
    def _finalize_session(self):
        """Finalize the current processing session."""
        if self._current_session:
            # Add to history
            self._session_history.append(self._current_session)
            
            # Manage history size
            if len(self._session_history) > self._max_history:
                self._session_history = self._session_history[-self._max_history:]
            
            logger.info(f"📊 Session {self._current_session.session_id} finalized")
    
    def _log_session_summary(self):
        """Log comprehensive session summary."""
        if not self._current_session:
            return
        
        session = self._current_session
        duration = (session.end_time - session.start_time).total_seconds() if session.end_time else 0
        
        logger.info("🎉 Multi-Queue Processing Session Completed!")
        logger.info(f"📊 Session Summary:")
        logger.info(f"   🆔 Session ID: {session.session_id}")
        logger.info(f"   ⏱️ Duration: {duration:.2f}s")
        logger.info(f"   📋 Total tasks: {session.total_tasks}")
        logger.info(f"   🔄 Processed tasks: {session.processed_tasks}")
        logger.info(f"   ✅ Successful: {session.successful_tasks}")
        logger.info(f"   ❌ Failed: {session.failed_tasks}")
        logger.info(f"   ⏭️ Skipped: {session.skipped_tasks}")
        logger.info(f"   ⏹️ Cancelled: {session.cancelled_tasks}")
        
        if session.total_tasks > 0:
            success_rate = (session.successful_tasks / session.total_tasks) * 100
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
            
            if duration > 0:
                avg_time = duration / session.processed_tasks if session.processed_tasks > 0 else 0
                logger.info(f"   ⏱️ Average time per task: {avg_time:.2f}s")
        
        # Log error summary if there were errors
        if session.error_summary:
            logger.warning(f"⚠️ Errors encountered during session:")
            for error in session.error_summary[:5]:  # Show first 5 errors
                logger.warning(f"   ❌ {error['type']}: {error['error'][:100]}...")
    
    def request_cancellation(self):
        """Request cancellation of current processing session."""
        self._cancellation_requested = True
        logger.info("⏹️ Processing cancellation requested")
    
    def get_session_history(self, limit: int = 10) -> List[ProcessingSession]:
        """
        Get processing session history.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of ProcessingSession objects
        """
        with self._processing_lock:
            return self._session_history[-limit:] if limit else self._session_history
    
    def get_current_session(self) -> Optional[ProcessingSession]:
        """Get the current processing session if active."""
        return self._current_session
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics across all sessions.
        
        Returns:
            Dictionary with processing statistics
        """
        with self._processing_lock:
            if not self._session_history:
                return {
                    "total_sessions": 0,
                    "total_tasks_processed": 0,
                    "overall_success_rate": 0.0,
                    "average_session_duration": 0.0,
                    "total_processing_time": 0.0
                }
            
            total_sessions = len(self._session_history)
            total_tasks = sum(session.total_tasks for session in self._session_history)
            total_successful = sum(session.successful_tasks for session in self._session_history)
            total_failed = sum(session.failed_tasks for session in self._session_history)
            
            # Calculate durations
            total_duration = 0.0
            valid_durations = 0
            for session in self._session_history:
                if session.end_time:
                    duration = (session.end_time - session.start_time).total_seconds()
                    total_duration += duration
                    valid_durations += 1
            
            avg_duration = total_duration / valid_durations if valid_durations > 0 else 0.0
            success_rate = (total_successful / total_tasks * 100) if total_tasks > 0 else 0.0
            
            stats = {
                "total_sessions": total_sessions,
                "total_tasks_processed": total_tasks,
                "successful_tasks": total_successful,
                "failed_tasks": total_failed,
                "overall_success_rate": round(success_rate, 2),
                "average_session_duration": round(avg_duration, 2),
                "total_processing_time": round(total_duration, 2),
                "sessions_with_errors": len([s for s in self._session_history if s.error_summary])
            }
            
            logger.info(f"📊 Multi-Queue Processing Statistics: {stats}")
            return stats