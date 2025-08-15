#!/usr/bin/env python3
"""
Branch-Integrated Task Processor

Extended multi-queue processor that integrates Git branch creation functionality
into the task processing pipeline with proper transaction-like behavior.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.managers.branch_feedback_manager import BranchFeedbackManager
from src.core.managers.branch_integration_manager import BranchIntegrationManager, BranchIntegrationOperation, IntegrationResult
from src.core.processors.multi_queue_processor import MultiQueueProcessor, ProcessingResult, ProcessingSession, QueuedTaskItem
from src.core.services.branch_service import BranchCreationResult
from src.utils.branch_config import get_branch_config

logger = logging.getLogger(__name__)


class BranchProcessingResult(str, Enum):
    """Extended processing results including branch operations."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    SUCCESS_WITH_BRANCH = "success_with_branch"
    FAILED_BRANCH_ONLY = "failed_branch_only"
    FAILED_TASK_ONLY = "failed_task_only"


@dataclass
class BranchIntegratedTaskItem(QueuedTaskItem):
    """Extended task item with branch integration metadata."""

    branch_requested: bool = False
    branch_created: bool = False
    branch_name: Optional[str] = None
    branch_integration_error: Optional[str] = None
    branch_operation_id: Optional[str] = None


@dataclass
class BranchIntegratedSession(ProcessingSession):
    """Extended processing session with branch operation tracking."""

    branch_operations: int = 0
    successful_branch_operations: int = 0
    failed_branch_operations: int = 0
    branch_integration_stats: Dict[str, Any] = None


class BranchIntegratedProcessor(MultiQueueProcessor):
    """
    Multi-queue processor with integrated Git branch creation functionality.

    This processor extends the base MultiQueueProcessor to include:
    1. Pre-task branch creation based on checkbox detection
    2. Transaction-like behavior for task+branch operations
    3. Proper rollback mechanisms on failures
    4. Enhanced progress tracking and reporting
    5. Backward compatibility with existing workflows
    """

    def __init__(
        self,
        database_ops,
        status_manager,
        feedback_manager,
        claude_invoker,
        task_file_manager,
        project_root: str = None,
        max_retry_attempts: int = 3,
        task_timeout_minutes: int = 30,
        inter_task_delay_seconds: int = 2,
        taskmaster_callback=None,
        enable_branch_integration: bool = True,
    ):

        # Initialize base processor
        super().__init__(
            database_ops=database_ops,
            status_manager=status_manager,
            feedback_manager=feedback_manager,
            claude_invoker=claude_invoker,
            task_file_manager=task_file_manager,
            project_root=project_root,
            max_retry_attempts=max_retry_attempts,
            task_timeout_minutes=task_timeout_minutes,
            inter_task_delay_seconds=inter_task_delay_seconds,
            taskmaster_callback=taskmaster_callback,
        )

        self.enable_branch_integration = enable_branch_integration

        # Initialize branch integration components
        if self.enable_branch_integration and project_root:
            try:
                self.branch_config = get_branch_config(project_root)
                self.branch_integration_manager = BranchIntegrationManager(project_root)
                self.branch_feedback_manager = BranchFeedbackManager(feedback_manager=feedback_manager, enable_detailed_logging=True)

                logger.info("🔗 BranchIntegratedProcessor initialized with branch integration")
                logger.info(f"   📁 Project root: {project_root}")
                logger.info(f"   ⚙️  Branch creation enabled: {self.branch_config.enabled}")

            except Exception as e:
                logger.error(f"❌ Failed to initialize branch integration: {e}")
                logger.warning("⚠️  Falling back to standard multi-queue processing")
                self.enable_branch_integration = False
        else:
            logger.info("📝 BranchIntegratedProcessor initialized without branch integration")

    def process_queued_tasks(self, cancellation_check: callable = None) -> ProcessingSession:
        """
        Process queued tasks with integrated branch creation support.

        Args:
            cancellation_check: Optional cancellation check function

        Returns:
            BranchIntegratedSession with complete results including branch operations
        """
        session_id = f"branch_integrated_{int(datetime.now().timestamp())}"

        with self._processing_lock:
            try:
                logger.info("🎬 Starting branch-integrated task processing session")
                logger.info(f"   🆔 Session ID: {session_id}")
                logger.info(f"   🔗 Branch integration: {'enabled' if self.enable_branch_integration else 'disabled'}")

                # Initialize extended processing session
                self._current_session = BranchIntegratedSession(
                    session_id=session_id,
                    start_time=datetime.now(),
                    processing_results=[],
                    error_summary=[],
                    branch_integration_stats={},
                )

                # Step 1: Discover and prioritize queued tasks
                logger.info("📋 Step 1: Discovering and prioritizing queued tasks...")
                task_queue = self._discover_and_prioritize_tasks()

                if not task_queue:
                    logger.info("ℹ️  No queued tasks found")
                    self._current_session.end_time = datetime.now()
                    self._finalize_session()
                    return self._current_session

                # Step 2: Enhance tasks with branch integration metadata
                if self.enable_branch_integration:
                    task_queue = self._enhance_tasks_with_branch_metadata(task_queue)

                self._current_session.total_tasks = len(task_queue)
                logger.info(f"✅ Discovered {len(task_queue)} queued tasks for processing")

                # Step 3: Pre-processing validation and setup
                logger.info("🔍 Step 2: Pre-processing validation and resource setup...")
                self._prepare_processing_environment()

                # Step 4: Sequential task processing with branch integration
                logger.info("⚡ Step 3: Sequential task processing with branch integration...")
                self._process_task_queue_with_branches(task_queue, cancellation_check)

                # Step 5: Post-processing cleanup and summary
                logger.info("🧹 Step 4: Post-processing cleanup and summary...")
                self._cleanup_processing_environment()

                self._current_session.end_time = datetime.now()
                self._finalize_session()

                # Log final summary with branch statistics
                self._log_session_summary_with_branches()

                return self._current_session

            except Exception as e:
                logger.error(f"❌ Critical error in branch-integrated processing: {e}")
                if self._current_session:
                    self._current_session.end_time = datetime.now()
                    self._current_session.error_summary.append(
                        {
                            "type": "critical_session_error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    self._finalize_session()
                raise e

    def _enhance_tasks_with_branch_metadata(self, task_queue: List[QueuedTaskItem]) -> List[BranchIntegratedTaskItem]:
        """
        Enhance tasks with branch integration metadata.

        Args:
            task_queue: Original task queue

        Returns:
            Enhanced task queue with branch metadata
        """
        enhanced_tasks = []

        for task_item in task_queue:
            try:
                # Convert to enhanced task item
                enhanced_task = BranchIntegratedTaskItem(
                    task_id=task_item.task_id,
                    page_id=task_item.page_id,
                    title=task_item.title,
                    priority=task_item.priority,
                    queued_time=task_item.queued_time,
                    dependencies=task_item.dependencies,
                    metadata=task_item.metadata,
                    retry_count=task_item.retry_count,
                    last_error=task_item.last_error,
                )

                # Analyze branch requirements if enabled
                if self.enable_branch_integration and self.branch_config.enabled:
                    branch_analysis = self._analyze_task_branch_requirements(task_item)
                    enhanced_task.branch_requested = branch_analysis.get("branch_requested", False)

                    if enhanced_task.branch_requested:
                        logger.info(f"🌿 Task {task_item.task_id} requests branch creation")

                enhanced_tasks.append(enhanced_task)

            except Exception as e:
                logger.warning(f"⚠️  Failed to enhance task {task_item.task_id} with branch metadata: {e}")
                # Convert to enhanced task without branch integration
                enhanced_task = BranchIntegratedTaskItem(
                    task_id=task_item.task_id,
                    page_id=task_item.page_id,
                    title=task_item.title,
                    priority=task_item.priority,
                    queued_time=task_item.queued_time,
                    dependencies=task_item.dependencies,
                    metadata=task_item.metadata,
                    retry_count=task_item.retry_count,
                    last_error=task_item.last_error,
                    branch_requested=False,
                )
                enhanced_tasks.append(enhanced_task)

        return enhanced_tasks

    def _analyze_task_branch_requirements(self, task_item: QueuedTaskItem) -> Dict[str, Any]:
        """
        Analyze if a task requires branch creation.

        Args:
            task_item: Task to analyze

        Returns:
            Dictionary with branch requirement analysis
        """
        try:
            # Create task data for branch analysis
            task_data = {
                "id": task_item.task_id,
                "title": task_item.title,
                "properties": (task_item.metadata.get("taskmaster_task", {}).get("properties", {}) if task_item.metadata else {}),
            }

            # Use integration manager to analyze requirements
            branch_preferences = self.branch_integration_manager.checkbox_detector.extract_branch_preferences(task_data)

            return {
                "branch_requested": branch_preferences.get("create_branch", False),
                "base_branch": branch_preferences.get("base_branch"),
                "custom_branch_name": branch_preferences.get("branch_name_override"),
                "preferences": branch_preferences,
            }

        except Exception as e:
            logger.error(f"❌ Error analyzing branch requirements for task {task_item.task_id}: {e}")
            return {"branch_requested": False, "error": str(e)}

    def _process_task_queue_with_branches(self, task_queue: List[BranchIntegratedTaskItem], cancellation_check: callable = None):
        """
        Process the task queue with integrated branch creation.

        Args:
            task_queue: Enhanced task queue with branch metadata
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
                if task_item.branch_requested:
                    logger.info(f"   🌿 Branch creation requested")

                # Process individual task with branch integration
                result = self._process_single_task_with_branch_integration(task_item)

                # Record result and update counters
                self._record_processing_result(result)

                # Inter-task delay for resource recovery
                if i < len(task_queue) - 1 and not self._cancellation_requested:
                    logger.info(f"⏱️ Inter-task delay: {self.inter_task_delay_seconds}s")
                    time.sleep(self.inter_task_delay_seconds)

            except Exception as e:
                logger.error(f"❌ Unexpected error processing task {task_item.task_id}: {e}")

                # Record error
                error_result = self._create_error_result(task_item, str(e))
                self._record_processing_result(error_result)

                continue  # Continue with next task

        # Handle remaining tasks if cancelled
        if self._cancellation_requested:
            self._handle_cancelled_tasks(task_queue)

    def _process_single_task_with_branch_integration(self, task_item: BranchIntegratedTaskItem) -> Dict[str, Any]:
        """
        Process a single task with integrated branch creation support.

        This method implements transaction-like behavior:
        1. Create branch if requested
        2. Process task normally
        3. On failure, attempt to rollback branch creation if applicable

        Args:
            task_item: Enhanced task item with branch metadata

        Returns:
            Processing result dictionary with branch integration information
        """
        start_time = datetime.now()

        result = {
            "task_id": task_item.task_id,
            "page_id": task_item.page_id,
            "title": task_item.title,
            "status": BranchProcessingResult.SUCCESS,
            "processing_time": 0.0,
            "timestamp": datetime.now().isoformat(),
            "branch_integration": {
                "requested": task_item.branch_requested,
                "created": False,
                "branch_name": None,
                "operation_id": None,
                "error": None,
            },
        }

        branch_operation = None

        try:
            # Step 1: Branch creation (if requested)
            if task_item.branch_requested and self.enable_branch_integration:
                logger.info(f"🌿 Creating branch for task {task_item.task_id}")

                branch_integration_result = self.branch_integration_manager.integrate_with_multi_queue_processor(task_item)
                branch_operation = branch_integration_result.get("integration_operation")

                if branch_integration_result.get("branch_created", False):
                    task_item.branch_created = True
                    task_item.branch_name = branch_integration_result.get("branch_name")
                    task_item.branch_operation_id = branch_operation.operation_id if branch_operation else None

                    result["branch_integration"].update(
                        {
                            "created": True,
                            "branch_name": task_item.branch_name,
                            "operation_id": task_item.branch_operation_id,
                        }
                    )

                    self._current_session.branch_operations += 1
                    self._current_session.successful_branch_operations += 1

                    logger.info(f"✅ Branch '{task_item.branch_name}' created for task {task_item.task_id}")

                elif not branch_integration_result.get("integration_success", False):
                    # Branch creation failed
                    error_msg = branch_operation.error if branch_operation else "Branch creation failed"
                    task_item.branch_integration_error = error_msg
                    result["branch_integration"]["error"] = error_msg

                    self._current_session.branch_operations += 1
                    self._current_session.failed_branch_operations += 1

                    logger.error(f"❌ Branch creation failed for task {task_item.task_id}: {error_msg}")

                    # Decide whether to continue with task processing
                    if self.branch_config.fail_task_on_branch_error:
                        result["status"] = BranchProcessingResult.FAILED_BRANCH_ONLY
                        return self._finalize_processing_result(result, start_time)

            # Step 2: Standard task processing
            logger.info(f"📝 Processing task content for {task_item.task_id}")

            # Convert enhanced task back to standard format for processing
            standard_task_item = QueuedTaskItem(
                task_id=task_item.task_id,
                page_id=task_item.page_id,
                title=task_item.title,
                priority=task_item.priority,
                queued_time=task_item.queued_time,
                dependencies=task_item.dependencies,
                metadata=task_item.metadata,
                retry_count=task_item.retry_count,
                last_error=task_item.last_error,
            )

            # Use base class method for task processing
            task_result = self._execute_single_task(standard_task_item)

            # Update result based on task processing outcome
            if task_result["status"] == ProcessingResult.SUCCESS:
                if task_item.branch_created:
                    result["status"] = BranchProcessingResult.SUCCESS_WITH_BRANCH
                else:
                    result["status"] = BranchProcessingResult.SUCCESS

                logger.info(f"✅ Task processing completed successfully for {task_item.task_id}")

            else:
                # Task processing failed - consider rollback
                if task_item.branch_created and self.branch_config.retry_on_failure:
                    logger.warning(f"⚠️  Task processing failed, but branch was created for {task_item.task_id}")
                    result["status"] = BranchProcessingResult.FAILED_TASK_ONLY
                    # Note: We don't automatically delete the branch - it might be useful for debugging
                else:
                    result["status"] = BranchProcessingResult.FAILED

                result["error"] = task_result.get("error", "Task processing failed")
                logger.error(f"❌ Task processing failed for {task_item.task_id}: {result['error']}")

            # Merge task processing results
            task_processing_results = {k: v for k, v in task_result.items() if k not in ["task_id", "page_id", "title"]}
            result.update(task_processing_results)

            return self._finalize_processing_result(result, start_time)

        except Exception as e:
            logger.error(f"❌ Exception during integrated processing for task {task_item.task_id}: {e}")

            result["status"] = BranchProcessingResult.FAILED
            result["error"] = str(e)

            # Track branch operation even if task failed
            if task_item.branch_requested:
                if task_item.branch_created:
                    result["branch_integration"]["created"] = True
                    result["branch_integration"]["branch_name"] = task_item.branch_name
                result["branch_integration"]["error"] = str(e)

            return self._finalize_processing_result(result, start_time)

    def _record_processing_result(self, result: Dict[str, Any]):
        """Record processing result and update session counters."""
        self._current_session.processing_results.append(result)
        self._current_session.processed_tasks += 1

        # Update counters based on result status
        status = result["status"]
        if status in [BranchProcessingResult.SUCCESS, BranchProcessingResult.SUCCESS_WITH_BRANCH]:
            self._current_session.successful_tasks += 1
        elif status in [
            BranchProcessingResult.FAILED,
            BranchProcessingResult.FAILED_BRANCH_ONLY,
            BranchProcessingResult.FAILED_TASK_ONLY,
        ]:
            self._current_session.failed_tasks += 1
        elif status == BranchProcessingResult.SKIPPED:
            self._current_session.skipped_tasks += 1
        elif status == BranchProcessingResult.CANCELLED:
            self._current_session.cancelled_tasks += 1

    def _create_error_result(self, task_item: BranchIntegratedTaskItem, error: str) -> Dict[str, Any]:
        """Create an error result for a task."""
        return {
            "task_id": task_item.task_id,
            "page_id": task_item.page_id,
            "title": task_item.title,
            "status": BranchProcessingResult.FAILED,
            "error": error,
            "processing_time": 0.0,
            "timestamp": datetime.now().isoformat(),
            "branch_integration": {
                "requested": task_item.branch_requested,
                "created": task_item.branch_created,
                "branch_name": task_item.branch_name,
                "operation_id": task_item.branch_operation_id,
                "error": task_item.branch_integration_error,
            },
        }

    def _handle_cancelled_tasks(self, task_queue: List[BranchIntegratedTaskItem]):
        """Handle remaining tasks when processing is cancelled."""
        remaining_tasks = task_queue[self._current_session.processed_tasks :]
        for task_item in remaining_tasks:
            cancelled_result = {
                "task_id": task_item.task_id,
                "page_id": task_item.page_id,
                "title": task_item.title,
                "status": BranchProcessingResult.CANCELLED,
                "error": "Processing cancelled",
                "processing_time": 0.0,
                "timestamp": datetime.now().isoformat(),
                "branch_integration": {
                    "requested": task_item.branch_requested,
                    "created": False,
                    "branch_name": None,
                    "operation_id": None,
                    "error": "Processing cancelled",
                },
            }
            self._current_session.processing_results.append(cancelled_result)
            self._current_session.cancelled_tasks += 1

    def _finalize_processing_result(self, result: Dict[str, Any], start_time: datetime) -> Dict[str, Any]:
        """Finalize processing result with timing information."""
        processing_time = (datetime.now() - start_time).total_seconds()
        result["processing_time"] = processing_time
        return result

    def _log_session_summary_with_branches(self):
        """Log comprehensive session summary including branch operations."""
        if not self._current_session:
            return

        session = self._current_session
        duration = (session.end_time - session.start_time).total_seconds() if session.end_time else 0

        logger.info("🎉 Branch-Integrated Processing Session Completed!")
        logger.info(f"📊 Session Summary:")
        logger.info(f"   🆔 Session ID: {session.session_id}")
        logger.info(f"   ⏱️ Duration: {duration:.2f}s")
        logger.info(f"   📋 Total tasks: {session.total_tasks}")
        logger.info(f"   🔄 Processed tasks: {session.processed_tasks}")
        logger.info(f"   ✅ Successful: {session.successful_tasks}")
        logger.info(f"   ❌ Failed: {session.failed_tasks}")
        logger.info(f"   ⏭️ Skipped: {session.skipped_tasks}")
        logger.info(f"   ⏹️ Cancelled: {session.cancelled_tasks}")

        # Branch operation summary
        if hasattr(session, "branch_operations") and session.branch_operations > 0:
            logger.info(f"🌿 Branch Operations:")
            logger.info(f"   🔄 Total branch operations: {session.branch_operations}")
            logger.info(f"   ✅ Successful branch operations: {session.successful_branch_operations}")
            logger.info(f"   ❌ Failed branch operations: {session.failed_branch_operations}")

            if session.branch_operations > 0:
                branch_success_rate = (session.successful_branch_operations / session.branch_operations) * 100
                logger.info(f"   📊 Branch success rate: {branch_success_rate:.1f}%")

        if session.total_tasks > 0:
            success_rate = (session.successful_tasks / session.total_tasks) * 100
            logger.info(f"   📊 Overall success rate: {success_rate:.1f}%")

            if duration > 0:
                avg_time = duration / session.processed_tasks if session.processed_tasks > 0 else 0
                logger.info(f"   ⏱️ Average time per task: {avg_time:.2f}s")

    def get_branch_integration_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics including branch integration."""
        base_stats = self.get_processing_statistics()

        if self.enable_branch_integration:
            try:
                integration_stats = self.branch_integration_manager.get_integration_statistics()
                feedback_stats = self.branch_feedback_manager.get_feedback_statistics()

                return {
                    **base_stats,
                    "branch_integration_enabled": True,
                    "branch_config": {
                        "enabled": self.branch_config.enabled,
                        "default_base_branch": self.branch_config.default_base_branch,
                        "naming_strategy": self.branch_config.naming_strategy.value,
                    },
                    "integration_statistics": integration_stats,
                    "feedback_statistics": feedback_stats,
                }
            except Exception as e:
                logger.error(f"❌ Error getting branch integration statistics: {e}")
                return {**base_stats, "branch_integration_enabled": True, "error": str(e)}
        else:
            return {**base_stats, "branch_integration_enabled": False}
