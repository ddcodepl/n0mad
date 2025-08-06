#!/usr/bin/env python3
"""
Branch Feedback Manager

Manages user feedback, error handling, and status reporting for Git branch creation operations.
Integrates with the existing feedback system to provide comprehensive status updates.
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from core.managers.feedback_manager import FeedbackManager, ProcessingStage
from core.services.branch_service import BranchCreationResult, BranchOperation
from core.managers.branch_integration_manager import BranchIntegrationOperation, IntegrationResult


logger = logging.getLogger(__name__)


class BranchFeedbackType(str, Enum):
    """Types of branch-related feedback."""
    CHECKBOX_DETECTED = "checkbox_detected"
    BRANCH_CREATION_STARTED = "branch_creation_started"
    BRANCH_CREATION_SUCCESS = "branch_creation_success"
    BRANCH_CREATION_FAILED = "branch_creation_failed"
    BRANCH_ALREADY_EXISTS = "branch_already_exists"
    BRANCH_VALIDATION_ERROR = "branch_validation_error"
    INTEGRATION_SUCCESS = "integration_success"
    INTEGRATION_FAILED = "integration_failed"


@dataclass
class BranchFeedbackEntry:
    """Represents a branch-related feedback entry."""
    feedback_id: str
    task_id: str
    page_id: Optional[str]
    feedback_type: BranchFeedbackType
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    branch_name: Optional[str] = None
    operation_id: Optional[str] = None


class BranchFeedbackManager:
    """
    Manages feedback and error handling for branch creation operations.
    
    This manager provides:
    1. Status updates during branch creation
    2. Error reporting and handling
    3. User feedback integration
    4. Integration with existing FeedbackManager
    """
    
    def __init__(self, 
                 feedback_manager: Optional[FeedbackManager] = None,
                 enable_detailed_logging: bool = True):
        
        self.feedback_manager = feedback_manager
        self.enable_detailed_logging = enable_detailed_logging
        
        # Feedback tracking
        self._feedback_history: List[BranchFeedbackEntry] = []
        self._max_history = 500
        
        logger.info("📢 BranchFeedbackManager initialized")
        if self.feedback_manager:
            logger.info("   🔗 Integrated with existing FeedbackManager")
        else:
            logger.info("   📝 Operating in standalone mode")
    
    def report_checkbox_detection(self, 
                                  task_id: str, 
                                  page_id: Optional[str],
                                  checkbox_detected: bool,
                                  branch_requested: bool,
                                  checkbox_properties: List[str] = None) -> None:
        """
        Report checkbox detection results.
        
        Args:
            task_id: Task identifier  
            page_id: Page identifier (for Notion integration)
            checkbox_detected: Whether checkbox detection was successful
            branch_requested: Whether branch creation was requested
            checkbox_properties: List of checkbox properties found
        """
        if branch_requested:
            message = f"Branch creation requested for task {task_id}"
            details = {
                "checkbox_detected": checkbox_detected,
                "checkbox_properties": checkbox_properties or []
            }
        else:
            message = f"No branch creation requested for task {task_id}"
            details = {"checkbox_detected": checkbox_detected}
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=BranchFeedbackType.CHECKBOX_DETECTED,
            message=message,
            details=details
        )
        
        self._add_feedback_entry(feedback_entry)
        
        # Integrate with existing feedback manager
        if self.feedback_manager and page_id:
            stage = ProcessingStage.PROCESSING  # Use appropriate stage
            self.feedback_manager.add_feedback(
                page_id=page_id,
                stage=stage,
                message=message,
                details=details
            )
        
        if self.enable_detailed_logging:
            if branch_requested:
                logger.info(f"✅ Branch creation requested for task {task_id}")
                if checkbox_properties:
                    logger.info(f"   📋 Checkbox properties: {', '.join(checkbox_properties)}")
            else:
                logger.info(f"ℹ️  No branch creation requested for task {task_id}")
    
    def report_branch_creation_started(self,
                                       task_id: str,
                                       page_id: Optional[str],
                                       branch_name: str,
                                       base_branch: str,
                                       operation_id: str) -> None:
        """
        Report that branch creation has started.
        
        Args:
            task_id: Task identifier
            page_id: Page identifier
            branch_name: Name of branch being created
            base_branch: Base branch name
            operation_id: Operation identifier
        """
        message = f"Creating Git branch '{branch_name}' for task {task_id}"
        details = {
            "branch_name": branch_name,
            "base_branch": base_branch,
            "operation_id": operation_id
        }
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=BranchFeedbackType.BRANCH_CREATION_STARTED,
            message=message,
            details=details,
            branch_name=branch_name,
            operation_id=operation_id
        )
        
        self._add_feedback_entry(feedback_entry)
        
        # Integrate with existing feedback manager
        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id=page_id,
                stage=ProcessingStage.PROCESSING,
                message=message,
                details=details
            )
        
        if self.enable_detailed_logging:
            logger.info(f"🌿 Creating branch '{branch_name}' from '{base_branch}' for task {task_id}")
    
    def report_branch_creation_result(self,
                                      task_id: str,
                                      page_id: Optional[str],
                                      branch_operation: BranchOperation) -> None:
        """
        Report branch creation results.
        
        Args:
            task_id: Task identifier
            page_id: Page identifier
            branch_operation: Completed branch operation
        """
        if branch_operation.result == BranchCreationResult.SUCCESS:
            self._report_branch_success(task_id, page_id, branch_operation)
        elif branch_operation.result == BranchCreationResult.ALREADY_EXISTS:
            self._report_branch_already_exists(task_id, page_id, branch_operation)
        else:
            self._report_branch_failure(task_id, page_id, branch_operation)
    
    def _report_branch_success(self,
                               task_id: str, 
                               page_id: Optional[str],
                               branch_operation: BranchOperation) -> None:
        """Report successful branch creation."""
        message = f"Git branch '{branch_operation.branch_name}' created successfully for task {task_id}"
        details = {
            "branch_name": branch_operation.branch_name,
            "base_branch": branch_operation.base_branch,
            "operation_id": branch_operation.operation_id,
            "git_output": branch_operation.git_output
        }
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=BranchFeedbackType.BRANCH_CREATION_SUCCESS,
            message=message,
            details=details,
            branch_name=branch_operation.branch_name,
            operation_id=branch_operation.operation_id
        )
        
        self._add_feedback_entry(feedback_entry)
        
        # Integrate with existing feedback manager
        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id=page_id,
                stage=ProcessingStage.PROCESSING,
                message=message,
                details=details
            )
        
        if self.enable_detailed_logging:
            logger.info(f"✅ Branch '{branch_operation.branch_name}' created successfully for task {task_id}")
    
    def _report_branch_already_exists(self,
                                      task_id: str,
                                      page_id: Optional[str], 
                                      branch_operation: BranchOperation) -> None:
        """Report that branch already exists."""
        message = f"Git branch '{branch_operation.branch_name}' already exists for task {task_id}"
        details = {
            "branch_name": branch_operation.branch_name,
            "base_branch": branch_operation.base_branch,
            "operation_id": branch_operation.operation_id
        }
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=BranchFeedbackType.BRANCH_ALREADY_EXISTS,
            message=message,
            details=details,
            branch_name=branch_operation.branch_name,
            operation_id=branch_operation.operation_id
        )
        
        self._add_feedback_entry(feedback_entry)
        
        # Integrate with existing feedback manager (as warning)
        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id=page_id,
                stage=ProcessingStage.PROCESSING,
                message=message,
                details=details
            )
        
        if self.enable_detailed_logging:
            logger.warning(f"⚠️  Branch '{branch_operation.branch_name}' already exists for task {task_id}")
    
    def _report_branch_failure(self,
                               task_id: str,
                               page_id: Optional[str],
                               branch_operation: BranchOperation) -> None:
        """Report branch creation failure."""
        message = f"Failed to create Git branch '{branch_operation.branch_name}' for task {task_id}"
        error_msg = branch_operation.error or "Unknown error"
        
        details = {
            "branch_name": branch_operation.branch_name,
            "base_branch": branch_operation.base_branch,
            "operation_id": branch_operation.operation_id,
            "git_output": branch_operation.git_output,
            "error": error_msg
        }
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=BranchFeedbackType.BRANCH_CREATION_FAILED,
            message=message,
            details=details,
            error=error_msg,
            branch_name=branch_operation.branch_name,
            operation_id=branch_operation.operation_id
        )
        
        self._add_feedback_entry(feedback_entry)
        
        # Integrate with existing feedback manager (as error)
        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id=page_id,
                stage=ProcessingStage.ERROR_HANDLING,
                message=message,
                details=details,
                error=error_msg
            )
        
        if self.enable_detailed_logging:
            logger.error(f"❌ Failed to create branch '{branch_operation.branch_name}' for task {task_id}: {error_msg}")
    
    def report_integration_result(self,
                                  integration_operation: BranchIntegrationOperation) -> None:
        """
        Report integration operation results.
        
        Args:
            integration_operation: Completed integration operation
        """
        task_id = integration_operation.task_id
        page_id = None  # Integration operations might not have page_id
        
        if integration_operation.integration_result == IntegrationResult.SUCCESS:
            message = f"Branch integration completed successfully for task {task_id}"
            feedback_type = BranchFeedbackType.INTEGRATION_SUCCESS
            error = None
        elif integration_operation.integration_result == IntegrationResult.PARTIAL_SUCCESS:
            message = f"Branch integration partially successful for task {task_id}"
            feedback_type = BranchFeedbackType.INTEGRATION_SUCCESS
            error = integration_operation.error
        else:
            message = f"Branch integration failed for task {task_id}"
            feedback_type = BranchFeedbackType.INTEGRATION_FAILED
            error = integration_operation.error
        
        details = {
            "operation_id": integration_operation.operation_id,
            "branch_requested": integration_operation.branch_requested,
            "integration_result": integration_operation.integration_result.value if integration_operation.integration_result else None,
            "branch_created": integration_operation.branch_operation.result == BranchCreationResult.SUCCESS if integration_operation.branch_operation else False,
            "branch_name": integration_operation.branch_operation.branch_name if integration_operation.branch_operation else None
        }
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=feedback_type,
            message=message,
            details=details,
            error=error,
            branch_name=integration_operation.branch_operation.branch_name if integration_operation.branch_operation else None,
            operation_id=integration_operation.operation_id
        )
        
        self._add_feedback_entry(feedback_entry)
        
        if self.enable_detailed_logging:
            if integration_operation.integration_result == IntegrationResult.SUCCESS:
                logger.info(f"✅ Branch integration successful for task {task_id}")
            elif integration_operation.integration_result == IntegrationResult.PARTIAL_SUCCESS:
                logger.warning(f"⚠️  Branch integration partially successful for task {task_id}: {error}")
            else:
                logger.error(f"❌ Branch integration failed for task {task_id}: {error}")
    
    def report_validation_error(self,
                                task_id: str,
                                page_id: Optional[str],
                                validation_error: str,
                                branch_name: Optional[str] = None) -> None:
        """
        Report branch name validation errors.
        
        Args:
            task_id: Task identifier
            page_id: Page identifier
            validation_error: Validation error message
            branch_name: Invalid branch name (if applicable)
        """
        message = f"Branch name validation failed for task {task_id}"
        details = {
            "validation_error": validation_error,
            "branch_name": branch_name
        }
        
        feedback_entry = self._create_feedback_entry(
            task_id=task_id,
            page_id=page_id,
            feedback_type=BranchFeedbackType.BRANCH_VALIDATION_ERROR,
            message=message,
            details=details,
            error=validation_error,
            branch_name=branch_name
        )
        
        self._add_feedback_entry(feedback_entry)
        
        # Integrate with existing feedback manager
        if self.feedback_manager and page_id:
            self.feedback_manager.add_feedback(
                page_id=page_id,
                stage=ProcessingStage.ERROR_HANDLING,
                message=message,
                details=details,
                error=validation_error
            )
        
        if self.enable_detailed_logging:
            logger.error(f"❌ Branch validation failed for task {task_id}: {validation_error}")
    
    def _create_feedback_entry(self,
                               task_id: str,
                               page_id: Optional[str],
                               feedback_type: BranchFeedbackType,
                               message: str,
                               details: Optional[Dict[str, Any]] = None,
                               error: Optional[str] = None,
                               branch_name: Optional[str] = None,
                               operation_id: Optional[str] = None) -> BranchFeedbackEntry:
        """Create a new feedback entry."""
        feedback_id = f"branch_feedback_{task_id}_{int(datetime.now().timestamp())}"
        
        return BranchFeedbackEntry(
            feedback_id=feedback_id,
            task_id=task_id,
            page_id=page_id,
            feedback_type=feedback_type,
            message=message,
            details=details,
            error=error,
            created_at=datetime.now(),
            branch_name=branch_name,
            operation_id=operation_id
        )
    
    def _add_feedback_entry(self, feedback_entry: BranchFeedbackEntry) -> None:
        """Add feedback entry to history."""
        self._feedback_history.append(feedback_entry)
        
        # Keep history manageable
        if len(self._feedback_history) > self._max_history:
            self._feedback_history = self._feedback_history[-self._max_history:]
    
    def get_feedback_history(self, 
                             task_id: Optional[str] = None,
                             feedback_type: Optional[BranchFeedbackType] = None,
                             limit: int = 50) -> List[BranchFeedbackEntry]:
        """
        Get feedback history with optional filtering.
        
        Args:
            task_id: Filter by task ID
            feedback_type: Filter by feedback type
            limit: Maximum number of entries to return
            
        Returns:
            List of feedback entries
        """
        entries = self._feedback_history
        
        # Apply filters
        if task_id:
            entries = [entry for entry in entries if entry.task_id == task_id]
        
        if feedback_type:
            entries = [entry for entry in entries if entry.feedback_type == feedback_type]
        
        # Apply limit
        return entries[-limit:] if limit else entries
    
    def get_task_feedback_summary(self, task_id: str) -> Dict[str, Any]:
        """
        Get feedback summary for a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dictionary with feedback summary
        """
        task_entries = self.get_feedback_history(task_id=task_id)
        
        if not task_entries:
            return {
                "task_id": task_id,
                "has_feedback": False,
                "total_entries": 0
            }
        
        # Categorize feedback
        feedback_counts = {}
        for entry in task_entries:
            feedback_type = entry.feedback_type.value
            feedback_counts[feedback_type] = feedback_counts.get(feedback_type, 0) + 1
        
        # Find latest branch creation info
        latest_branch_entry = None
        for entry in reversed(task_entries):
            if entry.branch_name:
                latest_branch_entry = entry
                break
        
        return {
            "task_id": task_id,
            "has_feedback": True,
            "total_entries": len(task_entries),
            "feedback_counts": feedback_counts,
            "latest_branch_name": latest_branch_entry.branch_name if latest_branch_entry else None,
            "latest_operation_id": latest_branch_entry.operation_id if latest_branch_entry else None,
            "first_entry": task_entries[0].created_at.isoformat() if task_entries else None,
            "last_entry": task_entries[-1].created_at.isoformat() if task_entries else None
        }
    
    def get_feedback_statistics(self) -> Dict[str, Any]:
        """Get overall feedback statistics."""
        total_entries = len(self._feedback_history)
        
        if total_entries == 0:
            return {
                "total_entries": 0,
                "feedback_type_counts": {},
                "tasks_with_feedback": 0,
                "branches_created": 0,
                "creation_failures": 0
            }
        
        # Count by feedback type
        feedback_type_counts = {}
        for entry in self._feedback_history:
            feedback_type = entry.feedback_type.value
            feedback_type_counts[feedback_type] = feedback_type_counts.get(feedback_type, 0) + 1
        
        # Count unique tasks
        unique_tasks = len(set(entry.task_id for entry in self._feedback_history))
        
        # Count branches created and failures
        branches_created = feedback_type_counts.get(BranchFeedbackType.BRANCH_CREATION_SUCCESS.value, 0)
        creation_failures = feedback_type_counts.get(BranchFeedbackType.BRANCH_CREATION_FAILED.value, 0)
        
        return {
            "total_entries": total_entries,
            "feedback_type_counts": feedback_type_counts,
            "tasks_with_feedback": unique_tasks,
            "branches_created": branches_created,
            "creation_failures": creation_failures,
            "success_rate": (branches_created / (branches_created + creation_failures) * 100) if (branches_created + creation_failures) > 0 else 0.0
        }