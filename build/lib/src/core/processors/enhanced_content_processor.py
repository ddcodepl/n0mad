#!/usr/bin/env python3
"""
Enhanced Content Processor with Branch Creation Integration

Extended version of ContentProcessor that includes Git branch creation
functionality integrated into the task processing pipeline.
"""
import logging
from typing import Any, Dict, List, Optional

from src.core.managers.branch_feedback_manager import BranchFeedbackManager
from src.core.managers.branch_integration_manager import BranchIntegrationManager
from src.core.processors.content_processor import ContentProcessor
from src.core.services.branch_service import CheckboxStateDetector
from src.utils.branch_config import get_branch_config
from src.utils.checkbox_utils import CheckboxUtilities

logger = logging.getLogger(__name__)


class EnhancedContentProcessor(ContentProcessor):
    """
    Enhanced content processor with integrated Git branch creation support.

    This processor extends the base ContentProcessor to include:
    1. Checkbox state detection for branch creation requests
    2. Git branch creation before/after content processing
    3. Enhanced error handling and user feedback
    4. Configuration-driven branch creation behavior
    """

    def __init__(
        self,
        notion_client,
        openai_client,
        file_ops,
        project_root: str,
        enable_branch_integration: bool = True,
    ):

        # Initialize base processor
        super().__init__(notion_client, openai_client, file_ops)

        self.project_root = project_root
        self.enable_branch_integration = enable_branch_integration

        # Initialize branch components if enabled
        if self.enable_branch_integration:
            try:
                self.branch_config = get_branch_config(project_root)
                self.branch_integration_manager = BranchIntegrationManager(project_root)
                self.branch_feedback_manager = BranchFeedbackManager(enable_detailed_logging=True)
                self.checkbox_detector = CheckboxStateDetector()
                self.checkbox_utilities = CheckboxUtilities()

                logger.info("🔗 Enhanced ContentProcessor initialized with branch integration")
                logger.info(f"   📁 Project root: {project_root}")
                logger.info(f"   ⚙️  Branch creation enabled: {self.branch_config.enabled}")

            except Exception as e:
                logger.error(f"❌ Failed to initialize branch integration: {e}")
                self.enable_branch_integration = False
                logger.warning("⚠️  Falling back to standard content processing")
        else:
            logger.info("📝 Enhanced ContentProcessor initialized without branch integration")

    def process_task(self, task: Dict[str, Any], shutdown_flag: callable = None) -> Dict[str, Any]:
        """
        Process a task with integrated branch creation support.

        This method extends the base process_task to include:
        1. Pre-processing checkbox detection
        2. Optional branch creation before content processing
        3. Enhanced result reporting with branch information

        Args:
            task: Task data to process
            shutdown_flag: Optional shutdown flag callable

        Returns:
            Enhanced result dictionary with branch integration information
        """
        # First run the base validation
        base_result = self._validate_task_input(task)
        if base_result.get("status") == "failed":
            return base_result

        page_id = task["id"]
        title = task.get("title", "Untitled")
        task_id = self._extract_task_identifier(task)

        logger.info(f"🔄 Enhanced processing for task: {title} (ID: {task_id})")

        # Initialize enhanced result structure
        result = {
            "task_id": task_id,
            "page_id": page_id,
            "title": title,
            "status": "processing",
            "steps_completed": [],
            "branch_integration": {
                "enabled": self.enable_branch_integration,
                "checkbox_detected": False,
                "branch_requested": False,
                "branch_created": False,
                "branch_name": None,
                "integration_error": None,
            },
        }

        try:
            # Step 1: Checkbox Analysis and Branch Integration (if enabled)
            if self.enable_branch_integration and self.branch_config.enabled:
                branch_integration_result = self._handle_branch_integration(task, page_id, task_id)
                result["branch_integration"].update(branch_integration_result)
                result["steps_completed"].append("branch_integration_analyzed")

                # Log checkbox analysis for debugging
                if result["branch_integration"]["checkbox_detected"]:
                    checkbox_summary = self.checkbox_utilities.get_checkbox_summary(task)
                    self.checkbox_utilities.log_checkbox_analysis(task_id, checkbox_summary)

            # Step 2: Standard Content Processing
            logger.info(f"📝 Starting standard content processing for {task_id}")

            # Check for shutdown before content processing
            if shutdown_flag and shutdown_flag():
                logger.info(f"⏹️  Shutdown requested before content processing for {task_id}")
                result["status"] = "aborted"
                result["message"] = "Processing aborted due to shutdown"
                return result

            # Run base content processing
            base_processing_result = super().process_task(task, shutdown_flag)

            # Merge base processing results
            result.update(base_processing_result)

            # Step 3: Post-processing branch updates (if applicable)
            if self.enable_branch_integration and result["branch_integration"]["branch_created"] and result.get("status") == "completed":

                self._update_branch_with_processing_results(task_id, result["branch_integration"]["branch_name"], result)

            logger.info(f"✅ Enhanced processing completed for {task_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Enhanced processing failed for {task_id}: {e}")
            result["status"] = "failed"
            result["error"] = str(e)

            # Report integration error if branch integration was involved
            if self.enable_branch_integration and result["branch_integration"]["branch_requested"]:
                result["branch_integration"]["integration_error"] = str(e)
                self.branch_feedback_manager.report_integration_result(self._create_failed_integration_operation(task_id, title, str(e)))

            return result

    def _validate_task_input(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate task input and return error result if invalid."""
        if task is None:
            logger.error("Received None task in enhanced process_task")
            return {"page_id": "unknown", "status": "failed", "error": "Task is None"}

        if not isinstance(task, dict):
            logger.error(f"Received invalid task type: {type(task)}")
            return {
                "page_id": "unknown",
                "status": "failed",
                "error": f"Invalid task type: {type(task)}",
            }

        if "id" not in task:
            logger.error("Task missing required 'id' field")
            return {"page_id": "unknown", "status": "failed", "error": "Task missing 'id' field"}

        return {"status": "valid"}

    def _extract_task_identifier(self, task: Dict[str, Any]) -> str:
        """Extract a clean task identifier for branch creation."""
        # Try to get property ID first (cleaner format)
        if "properties" in task and "ID" in task["properties"]:
            id_property = task["properties"]["ID"]
            if id_property.get("type") == "unique_id" and "unique_id" in id_property:
                unique_id = id_property["unique_id"]
                if unique_id:
                    prefix = unique_id.get("prefix", "")
                    number = unique_id.get("number", "")
                    return f"{prefix}-{number}"

        # Fallback to page ID
        return task["id"]

    def _handle_branch_integration(self, task: Dict[str, Any], page_id: str, task_id: str) -> Dict[str, Any]:
        """
        Handle branch integration for a task.

        Args:
            task: Task data
            page_id: Page identifier
            task_id: Task identifier

        Returns:
            Dictionary with integration results
        """
        integration_result = {
            "checkbox_detected": False,
            "branch_requested": False,
            "branch_created": False,
            "branch_name": None,
            "integration_error": None,
            "operation_id": None,
        }

        try:
            logger.info(f"🔍 Analyzing checkbox state for task {task_id}")

            # Detect checkbox state
            branch_preferences = self.checkbox_detector.extract_branch_preferences(task)
            integration_result["checkbox_detected"] = True
            integration_result["branch_requested"] = branch_preferences.get("create_branch", False)

            # Report checkbox detection
            self.branch_feedback_manager.report_checkbox_detection(
                task_id=task_id,
                page_id=page_id,
                checkbox_detected=True,
                branch_requested=integration_result["branch_requested"],
                checkbox_properties=self.branch_config.checkbox_property_names,
            )

            if not integration_result["branch_requested"]:
                logger.info(f"ℹ️  No branch creation requested for task {task_id}")
                return integration_result

            # Validate configuration allows branch creation
            if not self._validate_branch_creation_allowed(task_id, branch_preferences):
                integration_result["integration_error"] = "Branch creation not allowed by configuration"
                return integration_result

            # Perform branch integration
            logger.info(f"🌿 Performing branch integration for task {task_id}")

            branch_integration_op = self.branch_integration_manager.process_task_for_branch_creation(task)
            integration_result["operation_id"] = branch_integration_op.operation_id

            if branch_integration_op.branch_operation:
                integration_result["branch_created"] = branch_integration_op.branch_operation.result.value == "success"
                integration_result["branch_name"] = branch_integration_op.branch_operation.branch_name

                # Report branch creation results
                self.branch_feedback_manager.report_branch_creation_result(
                    task_id=task_id,
                    page_id=page_id,
                    branch_operation=branch_integration_op.branch_operation,
                )

            if branch_integration_op.error:
                integration_result["integration_error"] = branch_integration_op.error

            # Report overall integration result
            self.branch_feedback_manager.report_integration_result(branch_integration_op)

            return integration_result

        except Exception as e:
            logger.error(f"❌ Branch integration failed for task {task_id}: {e}")
            integration_result["integration_error"] = str(e)
            return integration_result

    def _validate_branch_creation_allowed(self, task_id: str, branch_preferences: Dict[str, Any]) -> bool:
        """
        Validate that branch creation is allowed based on configuration and preferences.

        Args:
            task_id: Task identifier
            branch_preferences: Branch preferences from checkbox detection

        Returns:
            True if branch creation is allowed, False otherwise
        """
        # Check if base branch is allowed
        base_branch = branch_preferences.get("base_branch") or self.branch_config.default_base_branch

        if not self.branch_config.is_base_branch_allowed(base_branch):
            logger.warning(f"⚠️  Base branch '{base_branch}' not allowed for task {task_id}")
            return False

        # Check if custom branch name is forbidden
        custom_branch_name = branch_preferences.get("branch_name_override")
        if custom_branch_name and self.branch_config.is_branch_name_forbidden(custom_branch_name):
            logger.warning(f"⚠️  Custom branch name '{custom_branch_name}' is forbidden for task {task_id}")
            return False

        return True

    def _update_branch_with_processing_results(self, task_id: str, branch_name: str, processing_result: Dict[str, Any]) -> None:
        """
        Update branch with processing results (e.g., commit processing status).

        This could be extended to automatically commit processed files to the branch.

        Args:
            task_id: Task identifier
            branch_name: Created branch name
            processing_result: Processing results
        """
        logger.info(f"📝 Branch '{branch_name}' available for task {task_id}")
        logger.info(f"   📊 Processing status: {processing_result.get('status')}")
        logger.info(f"   📁 Files processed: {len(processing_result.get('steps_completed', []))}")

        # Future enhancement: Could automatically commit processed files
        # This would require additional Git operations and configuration

    def _create_failed_integration_operation(self, task_id: str, task_title: str, error: str):
        """Create a failed integration operation for error reporting."""
        from datetime import datetime

        from core.managers.branch_integration_manager import BranchIntegrationOperation, IntegrationResult

        return BranchIntegrationOperation(
            operation_id=f"failed_{task_id}_{int(datetime.now().timestamp())}",
            task_id=task_id,
            task_title=task_title,
            checkbox_detected=True,
            branch_requested=True,
            integration_result=IntegrationResult.FAILED,
            error=error,
            created_at=datetime.now(),
            completed_at=datetime.now(),
        )

    def get_branch_integration_statistics(self) -> Dict[str, Any]:
        """
        Get branch integration statistics for monitoring.

        Returns:
            Dictionary with integration statistics
        """
        if not self.enable_branch_integration:
            return {"integration_enabled": False, "message": "Branch integration is disabled"}

        try:
            integration_stats = self.branch_integration_manager.get_integration_statistics()
            feedback_stats = self.branch_feedback_manager.get_feedback_statistics()

            return {
                "integration_enabled": True,
                "configuration": {
                    "enabled": self.branch_config.enabled,
                    "default_base_branch": self.branch_config.default_base_branch,
                    "naming_strategy": self.branch_config.naming_strategy.value,
                },
                "integration_stats": integration_stats,
                "feedback_stats": feedback_stats,
            }

        except Exception as e:
            logger.error(f"❌ Error getting branch integration statistics: {e}")
            return {"integration_enabled": True, "error": str(e)}

    def is_branch_integration_enabled(self) -> bool:
        """Check if branch integration is enabled and configured."""
        return self.enable_branch_integration and hasattr(self, "branch_config") and self.branch_config.enabled
