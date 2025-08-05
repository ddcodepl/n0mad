#!/usr/bin/env python3
"""
Branch Integration Manager

Integrates Git branch creation functionality with the existing task processing pipeline.
Handles coordination between checkbox detection, branch creation, and task status updates.
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from core.services.branch_service import (
    GitBranchService, 
    CheckboxStateDetector, 
    BranchCreationResult,
    BranchOperation
)
from utils.task_status import TaskStatus


logger = logging.getLogger(__name__)


class IntegrationResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL_SUCCESS = "partial_success"


@dataclass
class BranchIntegrationOperation:
    """Represents a complete branch integration operation"""
    operation_id: str
    task_id: str
    task_title: str
    checkbox_detected: bool
    branch_requested: bool
    branch_operation: Optional[BranchOperation] = None
    integration_result: Optional[IntegrationResult] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BranchIntegrationManager:
    """
    Manages the integration of branch creation with task processing.
    
    This manager coordinates between:
    1. Checkbox state detection in task properties
    2. Branch creation service
    3. Task status updates and error handling
    4. Integration with existing processing pipeline
    """
    
    def __init__(self, 
                 project_root: str,
                 git_service: Optional[GitBranchService] = None,
                 checkbox_detector: Optional[CheckboxStateDetector] = None,
                 default_base_branch: str = "master"):
        
        self.project_root = project_root
        self.default_base_branch = default_base_branch
        
        # Initialize services
        self.git_service = git_service or GitBranchService(project_root, default_base_branch)
        self.checkbox_detector = checkbox_detector or CheckboxStateDetector()
        
        # Operation tracking
        self._integration_history: List[BranchIntegrationOperation] = []
        self._max_history = 100
        
        logger.info("🔗 BranchIntegrationManager initialized")
        logger.info(f"   📁 Project root: {project_root}")
        logger.info(f"   🌱 Default base branch: {default_base_branch}")
    
    def process_task_for_branch_creation(self, task: Dict[str, Any]) -> BranchIntegrationOperation:
        """
        Process a task for potential branch creation.
        
        This is the main entry point for integrating branch creation into task processing.
        
        Args:
            task: Task data with properties and metadata
            
        Returns:
            BranchIntegrationOperation with complete results
        """
        # Extract task identifiers
        task_id = self._extract_task_id(task)
        task_title = self._extract_task_title(task)
        operation_id = f"integration_{task_id}_{int(datetime.now().timestamp())}"
        
        operation = BranchIntegrationOperation(
            operation_id=operation_id,
            task_id=task_id,
            task_title=task_title,
            checkbox_detected=False,
            branch_requested=False,
            created_at=datetime.now()
        )
        
        try:
            logger.info(f"🔗 Processing task {task_id} for branch creation")
            logger.info(f"   📝 Task title: {task_title}")
            
            # Step 1: Detect checkbox state
            branch_preferences = self.checkbox_detector.extract_branch_preferences(task)
            operation.checkbox_detected = True
            operation.branch_requested = branch_preferences.get("create_branch", False)
            
            if not operation.branch_requested:
                logger.info(f"ℹ️  Task {task_id} does not request branch creation")
                operation.integration_result = IntegrationResult.SKIPPED
                return self._finalize_integration_operation(operation)
            
            logger.info(f"✅ Task {task_id} requests branch creation")
            
            # Step 2: Extract branch creation parameters
            base_branch = branch_preferences.get("base_branch") or self.default_base_branch
            custom_branch_name = branch_preferences.get("branch_name_override")
            
            # Use custom branch name if provided, otherwise use task title
            branch_title = custom_branch_name or task_title
            
            logger.info(f"   🌱 Base branch: {base_branch}")
            if custom_branch_name:
                logger.info(f"   📝 Custom branch name: {custom_branch_name}")
            
            # Step 3: Create the branch
            branch_operation = self.git_service.create_branch_for_task(
                task_id=task_id,
                task_title=branch_title,
                base_branch=base_branch,
                force=False  # Don't force by default
            )
            
            operation.branch_operation = branch_operation
            
            # Step 4: Handle results
            if branch_operation.result == BranchCreationResult.SUCCESS:
                operation.integration_result = IntegrationResult.SUCCESS
                logger.info(f"✅ Branch creation completed successfully for task {task_id}")
                logger.info(f"   🌿 Branch name: {branch_operation.branch_name}")
                
            elif branch_operation.result == BranchCreationResult.ALREADY_EXISTS:
                operation.integration_result = IntegrationResult.PARTIAL_SUCCESS
                logger.warning(f"⚠️  Branch already exists for task {task_id}: {branch_operation.branch_name}")
                
            else:
                operation.integration_result = IntegrationResult.FAILED
                operation.error = branch_operation.error
                logger.error(f"❌ Branch creation failed for task {task_id}: {branch_operation.error}")
            
            return self._finalize_integration_operation(operation)
            
        except Exception as e:
            operation.integration_result = IntegrationResult.FAILED
            operation.error = str(e)
            logger.error(f"❌ Exception during branch integration for task {task_id}: {e}")
            return self._finalize_integration_operation(operation)
    
    def integrate_with_content_processor(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Integration hook for ContentProcessor workflow.
        
        This method can be called from ContentProcessor.process_task() to handle
        branch creation before or after content processing.
        
        Args:
            task: Task being processed
            
        Returns:
            Updated task data with branch integration results
        """
        integration_op = self.process_task_for_branch_creation(task)
        
        # Add branch integration metadata to task
        branch_metadata = {
            "branch_integration": {
                "operation_id": integration_op.operation_id,
                "branch_requested": integration_op.branch_requested,
                "integration_result": integration_op.integration_result.value if integration_op.integration_result else None,
                "branch_created": integration_op.branch_operation.result == BranchCreationResult.SUCCESS if integration_op.branch_operation else False,
                "branch_name": integration_op.branch_operation.branch_name if integration_op.branch_operation else None,
                "error": integration_op.error
            }
        }
        
        # Create updated task data
        updated_task = task.copy()
        if "metadata" not in updated_task:
            updated_task["metadata"] = {}
        updated_task["metadata"].update(branch_metadata)
        
        return updated_task
    
    def integrate_with_multi_queue_processor(self, task_item) -> Dict[str, Any]:
        """
        Integration hook for MultiQueueProcessor workflow.
        
        This method can be called during task execution in MultiQueueProcessor
        to handle branch creation as part of the task processing pipeline.
        
        Args:
            task_item: QueuedTaskItem being processed
            
        Returns:
            Integration results dictionary
        """
        # Extract task data from QueuedTaskItem
        task_data = {
            "id": task_item.task_id,
            "title": task_item.title,
            "properties": task_item.metadata.get("taskmaster_task", {}).get("properties", {}) if task_item.metadata else {}
        }
        
        integration_op = self.process_task_for_branch_creation(task_data)
        
        return {
            "integration_operation": integration_op,
            "branch_created": integration_op.branch_operation.result == BranchCreationResult.SUCCESS if integration_op.branch_operation else False,
            "branch_name": integration_op.branch_operation.branch_name if integration_op.branch_operation else None,
            "integration_success": integration_op.integration_result in [IntegrationResult.SUCCESS, IntegrationResult.PARTIAL_SUCCESS]
        }
    
    def get_task_branch_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get branch creation status for a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dictionary with branch status information
        """
        # Find the most recent integration operation for this task
        task_operations = [op for op in self._integration_history if op.task_id == task_id]
        
        if not task_operations:
            return {
                "task_id": task_id,
                "has_integration": False,
                "branch_created": False,
                "branch_name": None
            }
        
        latest_op = max(task_operations, key=lambda op: op.created_at)
        
        return {
            "task_id": task_id,
            "has_integration": True,
            "operation_id": latest_op.operation_id,
            "branch_requested": latest_op.branch_requested,
            "branch_created": latest_op.branch_operation.result == BranchCreationResult.SUCCESS if latest_op.branch_operation else False,
            "branch_name": latest_op.branch_operation.branch_name if latest_op.branch_operation else None,
            "integration_result": latest_op.integration_result.value if latest_op.integration_result else None,
            "error": latest_op.error,
            "created_at": latest_op.created_at.isoformat(),
            "completed_at": latest_op.completed_at.isoformat() if latest_op.completed_at else None
        }
    
    def _extract_task_id(self, task: Dict[str, Any]) -> str:
        """Extract task ID from task data."""
        # Try various common task ID fields
        for field in ["id", "task_id", "page_id", "ticket_id"]:
            if field in task and task[field]:
                return str(task[field])
        
        # Try to extract from properties
        if "properties" in task and "ID" in task["properties"]:
            id_property = task["properties"]["ID"]
            if id_property.get("type") == "unique_id" and "unique_id" in id_property:
                unique_id = id_property["unique_id"]
                if unique_id:
                    prefix = unique_id.get("prefix", "")
                    number = unique_id.get("number", "")
                    return f"{prefix}-{number}"
        
        # Fallback to timestamp-based ID
        return f"task-{int(datetime.now().timestamp())}"
    
    def _extract_task_title(self, task: Dict[str, Any]) -> str:
        """Extract task title from task data."""
        # Try various common title fields
        for field in ["title", "name", "summary"]:
            if field in task and task[field]:
                return str(task[field])
        
        # Try to extract from properties
        if "properties" in task:
            # Try title property
            if "Name" in task["properties"]:
                title_prop = task["properties"]["Name"]
                if title_prop.get("type") == "title":
                    title_data = title_prop.get("title", [])
                    if title_data and len(title_data) > 0:
                        return title_data[0].get("plain_text", "Untitled")
        
        return "Untitled"
    
    def _finalize_integration_operation(self, operation: BranchIntegrationOperation) -> BranchIntegrationOperation:
        """Finalize integration operation and add to history."""
        operation.completed_at = datetime.now()
        
        # Add to history
        self._integration_history.append(operation)
        
        # Keep history manageable
        if len(self._integration_history) > self._max_history:
            self._integration_history = self._integration_history[-self._max_history:]
        
        return operation
    
    def get_integration_history(self, limit: int = 50) -> List[BranchIntegrationOperation]:
        """Get integration operation history."""
        return self._integration_history[-limit:] if limit else self._integration_history
    
    def get_integration_statistics(self) -> Dict[str, Any]:
        """Get branch integration statistics."""
        total = len(self._integration_history)
        requested = len([op for op in self._integration_history if op.branch_requested])
        successful = len([op for op in self._integration_history if op.integration_result == IntegrationResult.SUCCESS])
        failed = len([op for op in self._integration_history if op.integration_result == IntegrationResult.FAILED])
        skipped = len([op for op in self._integration_history if op.integration_result == IntegrationResult.SKIPPED])
        partial = len([op for op in self._integration_history if op.integration_result == IntegrationResult.PARTIAL_SUCCESS])
        
        branches_created = len([op for op in self._integration_history 
                               if op.branch_operation and op.branch_operation.result == BranchCreationResult.SUCCESS])
        
        return {
            "total_integrations": total,
            "branch_requests": requested,
            "successful_integrations": successful,
            "failed_integrations": failed,
            "skipped_integrations": skipped,
            "partial_success": partial,
            "branches_created": branches_created,
            "branch_request_rate": (requested / total * 100) if total > 0 else 0.0,
            "success_rate": (successful / requested * 100) if requested > 0 else 0.0,
            "branch_creation_rate": (branches_created / requested * 100) if requested > 0 else 0.0
        }


class BranchIntegrationConfiguration:
    """
    Configuration management for branch integration functionality.
    """
    
    def __init__(self):
        self.default_base_branch = "master"
        self.enable_branch_creation = True
        self.force_branch_creation = False
        self.branch_naming_prefix = ""
        self.max_branch_name_length = 250
        
        # Error handling configuration
        self.fail_task_on_branch_error = False
        self.retry_branch_creation = True
        self.max_branch_retries = 2
        
        # Integration points
        self.integrate_with_content_processor = True
        self.integrate_with_multi_queue_processor = True
        self.run_before_content_processing = True
        
        logger.info("⚙️  BranchIntegrationConfiguration initialized with defaults")
    
    def update_from_dict(self, config: Dict[str, Any]) -> None:
        """Update configuration from dictionary."""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"⚙️  Updated config: {key} = {value}")
            else:
                logger.warning(f"⚠️  Unknown configuration key: {key}")
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return {
            "default_base_branch": self.default_base_branch,
            "enable_branch_creation": self.enable_branch_creation,
            "force_branch_creation": self.force_branch_creation,
            "branch_naming_prefix": self.branch_naming_prefix,
            "max_branch_name_length": self.max_branch_name_length,
            "fail_task_on_branch_error": self.fail_task_on_branch_error,
            "retry_branch_creation": self.retry_branch_creation,
            "max_branch_retries": self.max_branch_retries,
            "integrate_with_content_processor": self.integrate_with_content_processor,
            "integrate_with_multi_queue_processor": self.integrate_with_multi_queue_processor,
            "run_before_content_processing": self.run_before_content_processing
        }