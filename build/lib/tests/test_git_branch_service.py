#!/usr/bin/env python3
"""
Unit tests for Git branch creation service functionality.

Tests the GitBranchService class and related Git operations.
"""
import unittest
import tempfile
import os
import subprocess
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from core.services.branch_service import (
    GitBranchService, 
    BranchCreationResult, 
    BranchOperation,
    TaskNameValidator
)


class TestGitBranchService(unittest.TestCase):
    """Test cases for GitBranchService class."""
    
    def setUp(self):
        """Set up test cases."""
        self.temp_dir = tempfile.mkdtemp()
        self.service = GitBranchService(self.temp_dir)
    
    def tearDown(self):
        """Clean up test cases."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_is_git_repository_valid(self, mock_run):
        """Test Git repository detection for valid repo."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.service._is_git_repository()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--git-dir"],
            cwd=self.service.project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('core.services.branch_service.subprocess.run')
    def test_is_git_repository_invalid(self, mock_run):
        """Test Git repository detection for invalid repo."""
        mock_run.return_value = MagicMock(returncode=1)
        
        result = self.service._is_git_repository()
        
        self.assertFalse(result)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_is_git_repository_exception(self, mock_run):
        """Test Git repository detection with exception."""
        mock_run.side_effect = Exception("Command failed")
        
        result = self.service._is_git_repository()
        
        self.assertFalse(result)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_branch_exists_true(self, mock_run):
        """Test branch existence check when branch exists."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  feature-branch\n"
        )
        
        result = self.service._branch_exists("feature-branch")
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["git", "branch", "--list", "feature-branch"],
            cwd=self.service.project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('core.services.branch_service.subprocess.run')
    def test_branch_exists_false(self, mock_run):
        """Test branch existence check when branch doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=""
        )
        
        result = self.service._branch_exists("non-existent-branch")
        
        self.assertFalse(result)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_ensure_base_branch_exists_locally(self, mock_run):
        """Test base branch validation when branch exists locally."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  master\n"
        )
        
        result = self.service._ensure_base_branch("master")
        
        self.assertTrue(result)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_ensure_base_branch_exists_remotely(self, mock_run):
        """Test base branch validation when branch exists remotely."""
        # First call (local) fails, second call (remote) succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # Local check fails
            MagicMock(returncode=0, stdout="  origin/develop\n")  # Remote check succeeds
        ]
        
        result = self.service._ensure_base_branch("develop")
        
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_create_git_branch_success(self, mock_run):
        """Test successful Git branch creation."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Switched to a new branch 'feature-branch'\n",
            stderr=""
        )
        
        success, output = self.service._create_git_branch("feature-branch", "master")
        
        self.assertTrue(success)
        self.assertIn("Switched to a new branch", output)
        mock_run.assert_called_once_with(
            ["git", "checkout", "-b", "feature-branch", "master"],
            cwd=self.service.project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
    
    @patch('core.services.branch_service.subprocess.run')
    def test_create_git_branch_failure(self, mock_run):
        """Test failed Git branch creation."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="fatal: A branch named 'feature-branch' already exists.\n"
        )
        
        success, output = self.service._create_git_branch("feature-branch", "master")
        
        self.assertFalse(success)
        self.assertIn("already exists", output)
    
    @patch('core.services.branch_service.subprocess.run')
    def test_create_git_branch_force_mode(self, mock_run):
        """Test Git branch creation in force mode."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        success, output = self.service._create_git_branch("feature-branch", "master", force=True)
        
        self.assertTrue(success)
        mock_run.assert_called_once_with(
            ["git", "branch", "-f", "feature-branch", "master"],
            cwd=self.service.project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
    
    @patch('core.services.branch_service.subprocess.run')
    def test_create_git_branch_timeout(self, mock_run):
        """Test Git branch creation timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)
        
        success, output = self.service._create_git_branch("feature-branch", "master")
        
        self.assertFalse(success)
        self.assertEqual(output, "Git command timed out")
    
    def test_create_branch_for_task_complete_flow(self):
        """Test complete branch creation flow."""
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=False), \
             patch.object(self.service, '_ensure_base_branch', return_value=True), \
             patch.object(self.service, '_create_git_branch', return_value=(True, "Branch created")):
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123",
                task_title="Fix user login bug",
                base_branch="develop"
            )
            
            self.assertEqual(operation.result, BranchCreationResult.SUCCESS)
            self.assertEqual(operation.task_id, "TASK-123")
            self.assertEqual(operation.task_title, "Fix user login bug")
            self.assertEqual(operation.base_branch, "develop")
            self.assertTrue(operation.branch_name.startswith("TASK-123"))
            self.assertIn("Fix-user-login-bug", operation.branch_name)
    
    def test_create_branch_for_task_not_git_repo(self):
        """Test branch creation when not in Git repository."""
        with patch.object(self.service, '_is_git_repository', return_value=False):
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123",
                task_title="Fix bug"
            )
            
            self.assertEqual(operation.result, BranchCreationResult.FAILED)
            self.assertEqual(operation.error, "Not in a Git repository")
    
    def test_create_branch_for_task_branch_exists(self):
        """Test branch creation when branch already exists."""
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=True):
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123", 
                task_title="Fix bug"
            )
            
            self.assertEqual(operation.result, BranchCreationResult.ALREADY_EXISTS)
            self.assertIn("already exists", operation.error)
    
    def test_create_branch_for_task_invalid_base_branch(self):
        """Test branch creation with invalid base branch."""
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=False), \
             patch.object(self.service, '_ensure_base_branch', return_value=False):
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123",
                task_title="Fix bug",
                base_branch="non-existent"
            )
            
            self.assertEqual(operation.result, BranchCreationResult.FAILED)
            self.assertIn("does not exist", operation.error)
    
    def test_create_branch_for_task_git_command_fails(self):
        """Test branch creation when Git command fails."""
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=False), \
             patch.object(self.service, '_ensure_base_branch', return_value=True), \
             patch.object(self.service, '_create_git_branch', return_value=(False, "Git error")):
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123",
                task_title="Fix bug"
            )
            
            self.assertEqual(operation.result, BranchCreationResult.FAILED)
            self.assertIn("Git command failed", operation.error)
    
    def test_create_branch_for_task_force_creation(self):
        """Test forced branch creation."""
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=True), \
             patch.object(self.service, '_ensure_base_branch', return_value=True), \
             patch.object(self.service, '_create_git_branch', return_value=(True, "Branch created")) as mock_create:
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123",
                task_title="Fix bug",
                force=True
            )
            
            self.assertEqual(operation.result, BranchCreationResult.SUCCESS)
            mock_create.assert_called_once()
            # Verify force parameter was passed
            args, kwargs = mock_create.call_args
            self.assertTrue(args[2])  # force parameter
    
    def test_create_branch_for_task_exception_handling(self):
        """Test exception handling during branch creation."""
        with patch.object(self.service, '_is_git_repository', side_effect=Exception("Unexpected error")):
            
            operation = self.service.create_branch_for_task(
                task_id="TASK-123",
                task_title="Fix bug"
            )
            
            self.assertEqual(operation.result, BranchCreationResult.FAILED)
            self.assertEqual(operation.error, "Unexpected error")
    
    def test_operation_history_tracking(self):
        """Test that operations are tracked in history."""
        initial_count = len(self.service.get_operation_history())
        
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=False), \
             patch.object(self.service, '_ensure_base_branch', return_value=True), \
             patch.object(self.service, '_create_git_branch', return_value=(True, "Success")):
            
            self.service.create_branch_for_task("TASK-123", "Fix bug")
            
        history = self.service.get_operation_history()
        self.assertEqual(len(history), initial_count + 1)
        
        latest_operation = history[-1]
        self.assertEqual(latest_operation.task_id, "TASK-123")
        self.assertEqual(latest_operation.result, BranchCreationResult.SUCCESS)
    
    def test_get_statistics(self):
        """Test statistics generation."""
        # Create some mock operations
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=False), \
             patch.object(self.service, '_ensure_base_branch', return_value=True), \
             patch.object(self.service, '_create_git_branch', return_value=(True, "Success")):
            
            # Create successful operation
            self.service.create_branch_for_task("TASK-1", "Success")
            
        with patch.object(self.service, '_is_git_repository', return_value=False):
            # Create failed operation
            self.service.create_branch_for_task("TASK-2", "Failure")
        
        stats = self.service.get_statistics()
        
        self.assertEqual(stats["total_operations"], 2)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["success_rate"], 50.0)
    
    def test_default_base_branch_usage(self):
        """Test that default base branch is used when none specified."""
        self.service.default_base_branch = "develop"
        
        with patch.object(self.service, '_is_git_repository', return_value=True), \
             patch.object(self.service, '_branch_exists', return_value=False), \
             patch.object(self.service, '_ensure_base_branch', return_value=True) as mock_ensure, \
             patch.object(self.service, '_create_git_branch', return_value=(True, "Success")):
            
            operation = self.service.create_branch_for_task("TASK-123", "Fix bug")
            
            mock_ensure.assert_called_once_with("develop")
            self.assertEqual(operation.base_branch, "develop")
    
    def test_branch_name_sanitization(self):
        """Test that task titles are properly sanitized for branch names."""
        test_cases = [
            ("Fix: Login Bug!", "Fix-Login-Bug"),
            ("Add @mention Feature", "Add-mention-Feature"),
            ("Update User Profile", "Update-User-Profile")
        ]
        
        for task_title, expected_pattern in test_cases:
            with patch.object(self.service, '_is_git_repository', return_value=True), \
                 patch.object(self.service, '_branch_exists', return_value=False), \
                 patch.object(self.service, '_ensure_base_branch', return_value=True), \
                 patch.object(self.service, '_create_git_branch', return_value=(True, "Success")):
                
                operation = self.service.create_branch_for_task("TASK-123", task_title)
                
                # Branch name should contain sanitized version
                self.assertIn(expected_pattern, operation.branch_name)
                self.assertTrue(self.service.validator.is_valid_branch_name(operation.branch_name))


class TestGitBranchServiceIntegration(unittest.TestCase):
    """Integration tests for GitBranchService with real Git operations."""
    
    def setUp(self):
        """Set up integration tests with temporary Git repository."""
        self.temp_dir = tempfile.mkdtemp()
        self.git_repo = Path(self.temp_dir)
        
        # Initialize a real Git repository for testing
        try:
            subprocess.run(
                ["git", "init"], 
                cwd=self.temp_dir, 
                capture_output=True, 
                check=True,
                timeout=10
            )
            
            # Configure git user for commits (required for some operations)
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=self.temp_dir,
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=self.temp_dir,
                capture_output=True,
                timeout=10
            )
            
            # Create initial commit
            (self.git_repo / "README.md").write_text("# Test Repository")
            subprocess.run(
                ["git", "add", "README.md"],
                cwd=self.temp_dir,
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=self.temp_dir,
                capture_output=True,
                timeout=10
            )
            
            self.git_available = True
            
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self.git_available = False
        
        self.service = GitBranchService(self.temp_dir)
    
    def tearDown(self):
        """Clean up integration tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_real_git_repository_detection(self):
        """Test repository detection with real Git repo."""
        if not self.git_available:
            self.skipTest("Git not available")
        
        result = self.service._is_git_repository()
        self.assertTrue(result)
    
    def test_real_branch_creation(self):
        """Test actual branch creation with real Git."""
        if not self.git_available:
            self.skipTest("Git not available")
        
        operation = self.service.create_branch_for_task(
            task_id="TEST-001",
            task_title="Integration test branch",
            base_branch="master"
        )
        
        # Should succeed
        self.assertEqual(operation.result, BranchCreationResult.SUCCESS)
        
        # Branch should actually exist
        self.assertTrue(self.service._branch_exists(operation.branch_name))
    
    def test_real_branch_already_exists(self):
        """Test branch creation when branch already exists."""
        if not self.git_available:
            self.skipTest("Git not available")
        
        # Create branch first time
        operation1 = self.service.create_branch_for_task(
            task_id="TEST-002",
            task_title="Duplicate test",
            base_branch="master"
        )
        self.assertEqual(operation1.result, BranchCreationResult.SUCCESS)
        
        # Try to create same branch again
        operation2 = self.service.create_branch_for_task(
            task_id="TEST-002",
            task_title="Duplicate test",
            base_branch="master"
        )
        self.assertEqual(operation2.result, BranchCreationResult.ALREADY_EXISTS)
    
    def test_real_invalid_base_branch(self):
        """Test branch creation with invalid base branch."""
        if not self.git_available:
            self.skipTest("Git not available")
        
        operation = self.service.create_branch_for_task(
            task_id="TEST-003", 
            task_title="Invalid base test",
            base_branch="non-existent-branch"
        )
        
        self.assertEqual(operation.result, BranchCreationResult.FAILED)
        self.assertIn("does not exist", operation.error)


if __name__ == '__main__':
    unittest.main()