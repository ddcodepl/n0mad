#!/usr/bin/env python3
"""
Git Branch Creation Service

Handles Git branch creation for tasks with proper validation, error handling,
and integration with the existing task processing pipeline.
"""
import os
import re
import subprocess
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)


class BranchCreationResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ALREADY_EXISTS = "already_exists"


@dataclass
class BranchOperation:
    """Represents a branch creation operation"""
    operation_id: str
    task_id: str
    task_title: str
    branch_name: str
    base_branch: str
    created_at: datetime
    result: Optional[BranchCreationResult] = None
    error: Optional[str] = None
    git_output: Optional[str] = None


class TaskNameValidator:
    """
    Validates and sanitizes task names for Git branch naming conventions.
    """
    
    # Git branch naming rules
    MAX_BRANCH_NAME_LENGTH = 250
    INVALID_PATTERNS = [
        r'\.\.+',           # Two or more consecutive dots
        r'^\.|\.$',         # Starting or ending with dot
        r'[\x00-\x1f\x7f]', # Control characters
        r'[ \t]+$',         # Trailing whitespace
        r'^[ \t]+',         # Leading whitespace
        r'[~^:\?*\[\]\\]',  # Invalid characters
        r'@\{',             # @{ sequence
        r'//+',             # Multiple consecutive slashes
        r'^/',              # Starting with slash
        r'/$',              # Ending with slash
    ]
    
    @classmethod
    def sanitize_task_name(cls, task_name: str, task_id: str = "") -> str:
        """
        Sanitize a task name to be suitable for Git branch naming.
        
        Args:
            task_name: Original task name
            task_id: Optional task ID to include in branch name
            
        Returns:
            Sanitized branch name
        """
        if not task_name or not isinstance(task_name, str):
            return f"task-{task_id}" if task_id else "task-unnamed"
        
        # Start with the task name
        branch_name = task_name.strip()
        
        # Replace spaces and common separators with hyphens
        branch_name = re.sub(r'[\s_]+', '-', branch_name)
        
        # Remove or replace invalid characters
        branch_name = re.sub(r'[~^:\?*\[\]\\@\{\}]', '', branch_name)
        branch_name = re.sub(r'[<>|"]', '-', branch_name)
        
        # Fix dots and slashes
        branch_name = re.sub(r'\.\.+', '.', branch_name)
        branch_name = re.sub(r'//+', '/', branch_name)
        branch_name = branch_name.strip('./')
        
        # Remove control characters
        branch_name = re.sub(r'[\x00-\x1f\x7f]', '', branch_name)
        
        # Collapse multiple hyphens
        branch_name = re.sub(r'-+', '-', branch_name)
        
        # Remove leading/trailing hyphens
        branch_name = branch_name.strip('-')
        
        # Ensure it's not empty
        if not branch_name:
            branch_name = f"task-{task_id}" if task_id else "task-unnamed"
        
        # Add task ID prefix if provided
        if task_id:
            # Clean task ID
            clean_task_id = re.sub(r'[^a-zA-Z0-9-]', '', str(task_id))
            if clean_task_id:
                branch_name = f"{clean_task_id}-{branch_name}"
        
        # Truncate if too long
        if len(branch_name) > cls.MAX_BRANCH_NAME_LENGTH:
            branch_name = branch_name[:cls.MAX_BRANCH_NAME_LENGTH].rstrip('-')
        
        # Final validation
        if not cls.is_valid_branch_name(branch_name):
            # Fallback to simple format
            safe_id = re.sub(r'[^a-zA-Z0-9]', '', str(task_id)) if task_id else "unnamed"
            branch_name = f"task-{safe_id}-{int(datetime.now().timestamp())}"
        
        return branch_name
    
    @classmethod
    def is_valid_branch_name(cls, branch_name: str) -> bool:
        """
        Validate a branch name against Git naming rules.
        
        Args:
            branch_name: Branch name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not branch_name or not isinstance(branch_name, str):
            return False
        
        # Check length
        if len(branch_name) > cls.MAX_BRANCH_NAME_LENGTH:
            return False
        
        # Check against invalid patterns
        for pattern in cls.INVALID_PATTERNS:
            if re.search(pattern, branch_name):
                return False
        
        # Check for lock file extension
        if branch_name.endswith('.lock'):
            return False
        
        return True


class GitBranchService:
    """
    Core service for Git branch creation and management.
    """
    
    def __init__(self, project_root: str, default_base_branch: str = "master"):
        self.project_root = Path(project_root)
        self.default_base_branch = default_base_branch
        self.validator = TaskNameValidator()
        self._operation_history: List[BranchOperation] = []
        
        logger.info(f"🌿 GitBranchService initialized")
        logger.info(f"   📁 Project root: {self.project_root}")
        logger.info(f"   🌱 Default base branch: {self.default_base_branch}")
    
    def create_branch_for_task(self, 
                               task_id: str, 
                               task_title: str, 
                               base_branch: Optional[str] = None,
                               force: bool = False) -> BranchOperation:
        """
        Create a Git branch for a task.
        
        Args:
            task_id: Unique task identifier
            task_title: Task title/name
            base_branch: Base branch to create from (defaults to default_base_branch)
            force: Whether to force creation even if branch exists
            
        Returns:
            BranchOperation with results
        """
        operation_id = f"branch_{task_id}_{int(datetime.now().timestamp())}"
        base_branch = base_branch or self.default_base_branch
        
        # Sanitize task name for branch
        branch_name = self.validator.sanitize_task_name(task_title, task_id)
        
        operation = BranchOperation(
            operation_id=operation_id,
            task_id=task_id,
            task_title=task_title,
            branch_name=branch_name,
            base_branch=base_branch,
            created_at=datetime.now()
        )
        
        try:
            logger.info(f"🌿 Creating branch for task {task_id}")
            logger.info(f"   📝 Task title: {task_title}")
            logger.info(f"   🌱 Branch name: {branch_name}")
            logger.info(f"   🔗 Base branch: {base_branch}")
            
            # Validate we're in a Git repository
            if not self._is_git_repository():
                operation.result = BranchCreationResult.FAILED
                operation.error = "Not in a Git repository"
                logger.error(f"❌ {operation.error}")
                return self._finalize_operation(operation)
            
            # Check if branch already exists
            if self._branch_exists(branch_name) and not force:
                operation.result = BranchCreationResult.ALREADY_EXISTS
                operation.error = f"Branch '{branch_name}' already exists"
                logger.warning(f"⚠️ {operation.error}")
                return self._finalize_operation(operation)
            
            # Ensure we're on the correct base branch or it exists
            if not self._ensure_base_branch(base_branch):
                operation.result = BranchCreationResult.FAILED
                operation.error = f"Base branch '{base_branch}' does not exist"
                logger.error(f"❌ {operation.error}")
                return self._finalize_operation(operation)
            
            # Create the branch
            success, output = self._create_git_branch(branch_name, base_branch, force)
            operation.git_output = output
            
            if success:
                operation.result = BranchCreationResult.SUCCESS
                logger.info(f"✅ Branch '{branch_name}' created successfully")
            else:
                operation.result = BranchCreationResult.FAILED
                operation.error = f"Git command failed: {output}"
                logger.error(f"❌ Failed to create branch: {output}")
            
            return self._finalize_operation(operation)
            
        except Exception as e:
            operation.result = BranchCreationResult.FAILED
            operation.error = str(e)
            logger.error(f"❌ Exception creating branch for task {task_id}: {e}")
            return self._finalize_operation(operation)
    
    def _is_git_repository(self) -> bool:
        """Check if the current directory is a Git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists locally."""
        try:
            result = subprocess.run(
                ["git", "branch", "--list", branch_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0 and branch_name in result.stdout
        except Exception:
            return False
    
    def _ensure_base_branch(self, base_branch: str) -> bool:
        """Ensure the base branch exists."""
        try:
            # Check if branch exists locally
            result = subprocess.run(
                ["git", "branch", "--list", base_branch],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and base_branch in result.stdout:
                return True
            
            # Check if it exists as a remote branch
            result = subprocess.run(
                ["git", "branch", "-r", "--list", f"*/{base_branch}"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return result.returncode == 0 and base_branch in result.stdout
            
        except Exception:
            return False
    
    def _create_git_branch(self, branch_name: str, base_branch: str, force: bool = False) -> tuple[bool, str]:
        """
        Create a Git branch using git commands.
        
        Args:
            branch_name: Name of the new branch
            base_branch: Base branch to create from
            force: Whether to force creation
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        try:
            # Build git command
            cmd = ["git", "checkout", "-b", branch_name, base_branch]
            if force:
                cmd = ["git", "branch", "-f", branch_name, base_branch]
            
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            return result.returncode == 0, output.strip()
            
        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except Exception as e:
            return False, f"Exception: {str(e)}"
    
    def _finalize_operation(self, operation: BranchOperation) -> BranchOperation:
        """Finalize the operation and add to history."""
        self._operation_history.append(operation)
        
        # Keep history manageable
        if len(self._operation_history) > 100:
            self._operation_history = self._operation_history[-100:]
        
        return operation
    
    def get_operation_history(self, limit: int = 50) -> List[BranchOperation]:
        """Get branch operation history."""
        return self._operation_history[-limit:] if limit else self._operation_history
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get branch creation statistics."""
        total = len(self._operation_history)
        successful = len([op for op in self._operation_history if op.result == BranchCreationResult.SUCCESS])
        failed = len([op for op in self._operation_history if op.result == BranchCreationResult.FAILED])
        already_exists = len([op for op in self._operation_history if op.result == BranchCreationResult.ALREADY_EXISTS])
        skipped = len([op for op in self._operation_history if op.result == BranchCreationResult.SKIPPED])
        
        return {
            "total_operations": total,
            "successful": successful,
            "failed": failed,
            "already_exists": already_exists,
            "skipped": skipped,
            "success_rate": (successful / total * 100) if total > 0 else 0.0
        }


class CheckboxStateDetector:
    """
    Detects checkbox states in task properties for branch creation.
    """
    
    # Common checkbox property names to look for
    CHECKBOX_PROPERTY_NAMES = [
        "New Branch",
        "Create Branch", 
        "Branch",
        "new_branch",
        "create_branch",
        "branch_creation"
    ]
    
    @classmethod
    def detect_branch_creation_request(cls, task: Dict[str, Any]) -> bool:
        """
        Detect if a task requests branch creation based on checkbox properties.
        
        Args:
            task: Task data from Notion or other source
            
        Returns:
            True if branch creation is requested, False otherwise
        """
        if not task or not isinstance(task, dict):
            return False
        
        properties = task.get("properties", {})
        if not properties:
            return False
        
        # Check for checkbox properties
        for prop_name in cls.CHECKBOX_PROPERTY_NAMES:
            # Try exact match first
            if prop_name in properties:
                prop_data = properties[prop_name]
                if cls._is_checkbox_checked(prop_data):
                    logger.info(f"✅ Branch creation requested via '{prop_name}' checkbox")
                    return True
            
            # Try case-insensitive match
            for actual_prop_name, prop_data in properties.items():
                if actual_prop_name.lower() == prop_name.lower():
                    if cls._is_checkbox_checked(prop_data):
                        logger.info(f"✅ Branch creation requested via '{actual_prop_name}' checkbox")
                        return True
        
        return False
    
    @classmethod
    def _is_checkbox_checked(cls, property_data: Dict[str, Any]) -> bool:
        """
        Check if a property represents a checked checkbox.
        
        Args:
            property_data: Property data from Notion
            
        Returns:
            True if checkbox is checked
        """
        if not isinstance(property_data, dict):
            return False
            
        # Handle Notion checkbox format
        if property_data.get("type") == "checkbox":
            return property_data.get("checkbox", False) is True
        
        # Handle other possible formats
        if "value" in property_data:
            value = property_data["value"]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ["true", "yes", "1", "checked"]
        
        # Direct boolean value
        if isinstance(property_data, bool):
            return property_data
            
        return False
    
    @classmethod
    def extract_branch_preferences(cls, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract branch creation preferences from task properties.
        
        Args:
            task: Task data
            
        Returns:
            Dictionary with branch preferences
        """
        preferences = {
            "create_branch": False,
            "base_branch": None,
            "branch_name_override": None
        }
        
        if not task or not isinstance(task, dict):
            return preferences
        
        properties = task.get("properties", {})
        
        # Detect branch creation request
        preferences["create_branch"] = cls.detect_branch_creation_request(task)
        
        # Look for base branch specification
        base_branch_props = ["Base Branch", "base_branch", "from_branch"]
        for prop_name in base_branch_props:
            if prop_name in properties:
                prop_data = properties[prop_name]
                base_branch = cls._extract_text_value(prop_data)
                if base_branch:
                    preferences["base_branch"] = base_branch
                    break
        
        # Look for custom branch name
        branch_name_props = ["Branch Name", "branch_name", "custom_branch"]
        for prop_name in branch_name_props:
            if prop_name in properties:
                prop_data = properties[prop_name]
                branch_name = cls._extract_text_value(prop_data)
                if branch_name:
                    preferences["branch_name_override"] = branch_name
                    break
        
        return preferences
    
    @classmethod
    def _extract_text_value(cls, property_data: Dict[str, Any]) -> Optional[str]:
        """Extract text value from various property formats."""
        if not isinstance(property_data, dict):
            return None
        
        # Notion rich text format
        if property_data.get("type") == "rich_text":
            rich_text = property_data.get("rich_text", [])
            if rich_text and len(rich_text) > 0:
                return rich_text[0].get("plain_text", "").strip()
        
        # Notion title format
        if property_data.get("type") == "title":
            title = property_data.get("title", [])
            if title and len(title) > 0:
                return title[0].get("plain_text", "").strip()
        
        # Simple text value
        if "value" in property_data:
            value = property_data["value"]
            if isinstance(value, str):
                return value.strip()
        
        return None