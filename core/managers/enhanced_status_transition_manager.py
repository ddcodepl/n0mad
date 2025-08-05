#!/usr/bin/env python3
"""
Enhanced Status Transition Manager

Extends the base StatusTransitionManager with checkbox validation and commit functionality.
Provides integrated workflow for task completion with validation and git operations.
"""
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from clients.notion_wrapper import NotionClientWrapper
from core.managers.status_transition_manager import (
    StatusTransitionManager, 
    StatusTransition, 
    TransitionResult
)
from core.services.task_validation_service import (
    TaskStatusValidationService,
    ValidationOperation,
    ValidationResult,
    ValidationErrorCode
)
from core.services.commit_message_service import (
    CommitMessageGenerator,
    TaskCommitData,
    CommitType
)
from core.services.git_commit_service import (
    GitCommitService,
    CommitOperation,
    CommitResult
)
from utils.task_status import TaskStatus
from utils.logging_config import get_logger
from utils.global_config import get_global_config

logger = get_logger(__name__)


class EnhancedTransitionResult(str, Enum):
    """Extended transition results including validation and commit states."""
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK_SUCCESS = "rollback_success"
    ROLLBACK_FAILED = "rollback_failed"
    VALIDATION_FAILED = "validation_failed"
    COMMIT_FAILED = "commit_failed"
    CHECKBOX_VALIDATION_FAILED = "checkbox_validation_failed"


@dataclass
class EnhancedStatusTransition(StatusTransition):
    """Extended status transition with validation and commit information."""
    # Validation information
    validation_operation: Optional[ValidationOperation] = None
    validation_result: Optional[ValidationResult] = None
    validation_error_code: Optional[ValidationErrorCode] = None
    
    # Commit information
    commit_operation: Optional[CommitOperation] = None
    commit_result: Optional[CommitResult] = None
    commit_hash: Optional[str] = None
    commit_message: Optional[str] = None
    
    # Enhanced metadata
    ticket_id: Optional[str] = None
    task_title: Optional[str] = None
    requires_commit: bool = False
    rollback_attempted: bool = False
    rollback_operations: List[str] = field(default_factory=list)


class EnhancedStatusTransitionManager(StatusTransitionManager):
    """
    Enhanced status transition manager with integrated validation and commit functionality.
    
    Features:
    - Checkbox validation before status transitions
    - Automatic commit generation and execution
    - Transaction-like behavior with rollback capabilities
    - Configurable commit requirements
    - Comprehensive error handling and user feedback
    """
    
    def __init__(self, 
                 notion_client: NotionClientWrapper,
                 project_root: Optional[str] = None,
                 enable_validation: bool = True,
                 enable_commits: bool = True):
        """
        Initialize the enhanced status transition manager.
        
        Args:
            notion_client: Notion API client wrapper
            project_root: Project root directory for git operations
            enable_validation: Whether to enable checkbox validation
            enable_commits: Whether to enable automatic commits
        """
        # Initialize base class
        super().__init__(notion_client)
        
        # Get configuration
        self.global_config = get_global_config()
        validation_config = self.global_config.get_validation_config()
        
        # Initialize services
        self.validation_service = None
        self.commit_message_generator = None
        self.git_commit_service = None
        
        if enable_validation:
            self.validation_service = TaskStatusValidationService(
                notion_client=notion_client,
                cache_ttl_minutes=validation_config.get('cache_ttl_minutes', 5),
                enabled=validation_config.get('enabled', True)
            )
        
        if enable_commits and project_root:
            self.commit_message_generator = CommitMessageGenerator()
            self.git_commit_service = GitCommitService(project_root=project_root)
        
        # Configuration
        self.enable_validation = enable_validation and self.validation_service is not None
        self.enable_commits = enable_commits and self.git_commit_service is not None
        self.project_root = project_root
        
        # Enhanced tracking
        self._enhanced_transition_history: List[EnhancedStatusTransition] = []
        self._max_enhanced_history = 1000
        
        logger.info(f"🔧 EnhancedStatusTransitionManager initialized")
        logger.info(f"   🔒 Validation: {'enabled' if self.enable_validation else 'disabled'}")
        logger.info(f"   📝 Commits: {'enabled' if self.enable_commits else 'disabled'}")
    
    def transition_status_enhanced(self, 
                                  page_id: str, 
                                  from_status: str, 
                                  to_status: str,
                                  ticket_id: Optional[str] = None,
                                  task_title: Optional[str] = None,
                                  validate_transition: bool = True,
                                  force_commit: bool = False) -> EnhancedStatusTransition:
        """
        Perform an enhanced status transition with validation and commit integration.
        
        Args:
            page_id: Notion page ID
            from_status: Expected current status
            to_status: Target status
            ticket_id: Optional ticket identifier
            task_title: Optional task title for commit message
            validate_transition: Whether to validate transition rules
            force_commit: Force commit even if not normally required
            
        Returns:
            EnhancedStatusTransition with comprehensive results
        """
        # Create enhanced transition object
        transition = EnhancedStatusTransition(
            page_id=page_id,
            from_status=from_status,
            to_status=to_status,
            timestamp=datetime.now(),
            ticket_id=ticket_id,
            task_title=task_title,
            requires_commit=self._requires_commit(from_status, to_status) or force_commit
        )
        
        # Thread-safe operation
        with self._transition_lock:
            try:
                logger.info(f"🔄 Starting enhanced transition: {from_status} → {to_status} for page {page_id[:8]}...")
                if ticket_id:
                    logger.info(f"   🎫 Ticket: {ticket_id}")
                
                # Phase 1: Standard validation
                if validate_transition and not self.is_valid_transition(from_status, to_status):
                    transition.result = EnhancedTransitionResult.FAILED
                    transition.error = f"Invalid transition: {from_status} → {to_status}"
                    logger.error(f"❌ {transition.error}")
                    return self._finalize_enhanced_transition(transition)
                
                # Phase 2: Checkbox validation (if enabled and required)
                if self.enable_validation and transition.requires_commit:
                    validation_result = self._perform_checkbox_validation(page_id, ticket_id)
                    transition.validation_operation = validation_result
                    transition.validation_result = validation_result.result
                    transition.validation_error_code = validation_result.error_code
                    
                    if validation_result.result not in [ValidationResult.SUCCESS, ValidationResult.SKIPPED]:
                        transition.result = EnhancedTransitionResult.CHECKBOX_VALIDATION_FAILED
                        transition.error = validation_result.error_message
                        logger.error(f"❌ Checkbox validation failed: {transition.error}")
                        return self._finalize_enhanced_transition(transition)
                    
                    logger.info("✅ Checkbox validation passed")
                
                # Phase 3: Execute status transition
                base_transition = self._execute_base_transition(page_id, from_status, to_status, validate_transition)
                
                # Copy base transition results
                transition.result = base_transition.result
                transition.error = base_transition.error
                transition.rollback_attempted = base_transition.rollback_attempted
                transition.rollback_result = base_transition.rollback_result
                
                if base_transition.result != TransitionResult.SUCCESS:
                    logger.error(f"❌ Base status transition failed: {transition.error}")
                    return self._finalize_enhanced_transition(transition)
                
                logger.info("✅ Status transition successful")
                
                # Phase 4: Create commit (if enabled and required)
                if self.enable_commits and transition.requires_commit:
                    commit_result = self._create_commit_for_transition(transition)
                    transition.commit_operation = commit_result
                    transition.commit_result = commit_result.result
                    transition.commit_hash = commit_result.commit_hash
                    transition.commit_message = commit_result.commit_message
                    
                    if commit_result.result != CommitResult.SUCCESS:
                        logger.error(f"❌ Commit creation failed: {commit_result.error}")
                        
                        # Attempt rollback of status transition
                        rollback_success = self._rollback_status_transition(page_id, from_status, to_status)
                        if rollback_success:
                            transition.result = EnhancedTransitionResult.ROLLBACK_SUCCESS
                            transition.rollback_attempted = True
                            transition.rollback_operations.append("status_transition")
                            logger.info("✅ Successfully rolled back status transition")
                        else:
                            transition.result = EnhancedTransitionResult.COMMIT_FAILED
                            transition.rollback_attempted = True
                            transition.rollback_operations.append("status_transition_failed")
                            logger.error("❌ Failed to rollback status transition")
                        
                        return self._finalize_enhanced_transition(transition)
                    
                    logger.info(f"✅ Commit created successfully: {commit_result.commit_hash[:8] if commit_result.commit_hash else 'unknown'}")
                
                # Phase 5: Final success
                transition.result = EnhancedTransitionResult.SUCCESS
                logger.info(f"✅ Enhanced transition completed successfully")
                
                return self._finalize_enhanced_transition(transition)
                
            except Exception as e:
                transition.result = EnhancedTransitionResult.FAILED
                transition.error = str(e)
                logger.error(f"❌ Enhanced transition failed with exception: {e}")
                return self._finalize_enhanced_transition(transition)
    
    def _perform_checkbox_validation(self, 
                                   page_id: str, 
                                   ticket_id: Optional[str]) -> ValidationOperation:
        """
        Perform checkbox validation for the transition.
        
        Args:
            page_id: Notion page ID
            ticket_id: Optional ticket identifier
            
        Returns:
            ValidationOperation with results
        """
        try:
            return self.validation_service.validate_task_transition(
                page_id=page_id,
                from_status="in-progress",  # Simplified for this context
                to_status="done",
                ticket_id=ticket_id
            )
        except Exception as e:
            logger.error(f"❌ Exception during checkbox validation: {e}")
            # Create a failed validation operation
            from core.services.task_validation_service import ValidationOperation
            operation = ValidationOperation(
                operation_id=f"val_error_{int(time.time())}",
                page_id=page_id,
                from_status="in-progress",
                to_status="done",
                checkbox_name="Commit",
                timestamp=datetime.now(),
                result=ValidationResult.FAILED,
                error_code=ValidationErrorCode.NOTION_API_ERROR,
                error_message=str(e)
            )
            return operation
    
    def _execute_base_transition(self, 
                               page_id: str, 
                               from_status: str, 
                               to_status: str,
                               validate_transition: bool) -> StatusTransition:
        """
        Execute the base status transition using the parent class method.
        
        Args:
            page_id: Notion page ID
            from_status: Current status
            to_status: Target status
            validate_transition: Whether to validate transition
            
        Returns:
            StatusTransition with results
        """
        return super().transition_status(page_id, from_status, to_status, validate_transition)
    
    def _create_commit_for_transition(self, transition: EnhancedStatusTransition) -> CommitOperation:
        """
        Create a git commit for the completed transition.
        
        Args:
            transition: Enhanced status transition object
            
        Returns:
            CommitOperation with results
        """
        try:
            # Prepare task commit data
            task_data = TaskCommitData(
                ticket_id=transition.ticket_id or f"TASK-{transition.page_id[:8]}",
                task_title=transition.task_title or "Task completion",
                task_description=f"Status transition: {transition.from_status} → {transition.to_status}",
                completion_summary=f"Completed task and updated status to {transition.to_status}"
            )
            
            # Generate commit message
            commit_message = self.commit_message_generator.generate_commit_message(
                task_data=task_data,
                commit_type=CommitType.FEAT  # Default to feature completion
            )
            
            # Execute commit
            return self.git_commit_service.execute_commit(
                ticket_id=task_data.ticket_id,
                commit_message=commit_message,
                stage_all_changes=True
            )
            
        except Exception as e:
            logger.error(f"❌ Exception during commit creation: {e}")
            # Create a failed commit operation
            from core.services.git_commit_service import CommitOperation
            operation = CommitOperation(
                operation_id=f"commit_error_{int(time.time())}",
                ticket_id=transition.ticket_id or "unknown",
                commit_message="Failed to generate commit message"
            )
            operation.result = CommitResult.FAILED
            operation.error = str(e)
            return operation
    
    def _rollback_status_transition(self, 
                                  page_id: str, 
                                  original_status: str, 
                                  attempted_status: str) -> bool:
        """
        Attempt to rollback a status transition.
        
        Args:
            page_id: Notion page ID
            original_status: Original status to restore
            attempted_status: Status that was attempted
            
        Returns:
            True if rollback was successful
        """
        try:
            logger.info(f"🔄 Attempting status rollback: {attempted_status} → {original_status}")
            
            rollback_transition = super().transition_status(
                page_id=page_id,
                from_status=attempted_status,
                to_status=original_status,
                validate_transition=False  # Skip validation for rollback
            )
            
            success = rollback_transition.result == TransitionResult.SUCCESS
            if success:
                logger.info("✅ Status rollback successful")
            else:
                logger.error(f"❌ Status rollback failed: {rollback_transition.error}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Exception during status rollback: {e}")
            return False
    
    def _requires_commit(self, from_status: str, to_status: str) -> bool:
        """
        Determine if a status transition requires a commit.
        
        Args:
            from_status: Current status
            to_status: Target status
            
        Returns:
            True if commit is required
        """
        # Define transitions that require commits
        commit_required_transitions = [
            ("in-progress", "done"),
            ("In progress", "Done"),
            ("IN_PROGRESS", "DONE"),
            ("in_progress", "finished"),
            ("In Progress", "Finished")
        ]
        
        # Normalize for case-insensitive comparison
        normalized_transition = (from_status.lower().strip(), to_status.lower().strip())
        
        for required_from, required_to in commit_required_transitions:
            if (normalized_transition[0] == required_from.lower() and 
                normalized_transition[1] == required_to.lower()):
                return True
        
        # Also check if target status indicates completion
        completion_statuses = ['done', 'finished', 'complete', 'completed']
        return to_status.lower().strip() in completion_statuses
    
    def _finalize_enhanced_transition(self, transition: EnhancedStatusTransition) -> EnhancedStatusTransition:
        """
        Finalize enhanced transition and add to history.
        
        Args:
            transition: Enhanced transition to finalize
            
        Returns:
            The finalized transition
        """
        # Add to enhanced history
        self._enhanced_transition_history.append(transition)
        
        # Keep history manageable
        if len(self._enhanced_transition_history) > self._max_enhanced_history:
            self._enhanced_transition_history = self._enhanced_transition_history[-self._max_enhanced_history:]
        
        # Also add to base class history
        base_transition = StatusTransition(
            page_id=transition.page_id,
            from_status=transition.from_status,
            to_status=transition.to_status,
            timestamp=transition.timestamp,
            result=transition.result.value if hasattr(transition.result, 'value') else transition.result,
            error=transition.error,
            rollback_attempted=transition.rollback_attempted,
            rollback_result=transition.rollback_result
        )
        self._add_to_history(base_transition)
        
        return transition
    
    def get_enhanced_transition_history(self, 
                                      page_id: Optional[str] = None, 
                                      limit: int = 100) -> List[EnhancedStatusTransition]:
        """
        Get enhanced transition history with filtering.
        
        Args:
            page_id: Optional page ID to filter by
            limit: Maximum number of transitions to return
            
        Returns:
            List of EnhancedStatusTransition objects
        """
        history = self._enhanced_transition_history
        
        if page_id:
            history = [t for t in history if t.page_id == page_id]
        
        return history[-limit:] if limit else history
    
    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """
        Get enhanced transition statistics including validation and commit metrics.
        
        Returns:
            Dictionary with comprehensive statistics
        """
        base_stats = super().get_statistics()
        
        total_enhanced = len(self._enhanced_transition_history)
        if total_enhanced == 0:
            return {**base_stats, "enhanced_transitions": 0}
        
        # Enhanced transition statistics
        successful_enhanced = len([t for t in self._enhanced_transition_history 
                                 if t.result == EnhancedTransitionResult.SUCCESS])
        validation_failed = len([t for t in self._enhanced_transition_history 
                               if t.result == EnhancedTransitionResult.CHECKBOX_VALIDATION_FAILED])
        commit_failed = len([t for t in self._enhanced_transition_history 
                           if t.result == EnhancedTransitionResult.COMMIT_FAILED])
        rollback_successful = len([t for t in self._enhanced_transition_history 
                                 if t.result == EnhancedTransitionResult.ROLLBACK_SUCCESS])
        
        # Validation statistics
        validation_operations = [t.validation_operation for t in self._enhanced_transition_history 
                               if t.validation_operation is not None]
        validation_success_rate = 0.0
        if validation_operations:
            successful_validations = len([v for v in validation_operations 
                                        if v.result == ValidationResult.SUCCESS])
            validation_success_rate = (successful_validations / len(validation_operations)) * 100
        
        # Commit statistics
        commit_operations = [t.commit_operation for t in self._enhanced_transition_history 
                           if t.commit_operation is not None]
        commit_success_rate = 0.0
        if commit_operations:
            successful_commits = len([c for c in commit_operations 
                                    if c.result == CommitResult.SUCCESS])
            commit_success_rate = (successful_commits / len(commit_operations)) * 100
        
        enhanced_stats = {
            "enhanced_transitions": total_enhanced,
            "enhanced_success_rate": (successful_enhanced / total_enhanced) * 100,
            "validation_failed": validation_failed,
            "commit_failed": commit_failed,
            "rollback_successful": rollback_successful,
            "validation_success_rate": validation_success_rate,
            "commit_success_rate": commit_success_rate,
            "total_validations": len(validation_operations),
            "total_commits": len(commit_operations),
            "services_enabled": {
                "validation": self.enable_validation,
                "commits": self.enable_commits
            }
        }
        
        return {**base_stats, **enhanced_stats}
    
    def is_validation_enabled(self) -> bool:
        """Check if validation is enabled."""
        return self.enable_validation
    
    def is_commit_enabled(self) -> bool:
        """Check if commits are enabled."""
        return self.enable_commits
    
    def configure_validation(self, enabled: bool):
        """
        Enable or disable validation.
        
        Args:
            enabled: Whether to enable validation
        """
        if self.validation_service:
            self.validation_service.set_enabled(enabled)
        self.enable_validation = enabled and self.validation_service is not None
        logger.info(f"🔧 Validation {'enabled' if self.enable_validation else 'disabled'}")
    
    def configure_commits(self, enabled: bool):
        """
        Enable or disable commits.
        
        Args:
            enabled: Whether to enable commits
        """
        self.enable_commits = enabled and self.git_commit_service is not None
        logger.info(f"🔧 Commits {'enabled' if self.enable_commits else 'disabled'}")