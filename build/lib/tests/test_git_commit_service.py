#!/usr/bin/env python3
"""
Unit tests for GitCommitService

Tests commit execution, repository status, error handling, and rollback functionality.
"""
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from core.services.git_commit_service import CommitOperation, CommitResult, GitCommitService, GitRepositoryStatus


class TestGitCommitService(unittest.TestCase):
    """Test cases for GitCommitService."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.service = GitCommitService(project_root=self.temp_dir)

        # Sample test data
        self.test_ticket_id = "NOMAD-123"
        self.test_commit_message = "feat: add user authentication (NOMAD-123)"
        self.test_commit_hash = "abc123def456"

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("subprocess.run")
    def test_execute_commit_success(self, mock_run):
        """Test successful commit execution."""
        # Mock git repository check
        mock_run.side_effect = [
            # git rev-parse --git-dir (is_git_repository)
            Mock(returncode=0, stdout="", stderr=""),
            # git branch --show-current (get_current_branch)
            Mock(returncode=0, stdout="main\n", stderr=""),
            # git status --porcelain (get_file_status)
            Mock(returncode=0, stdout="M  file1.py\n?? file2.py\n", stderr=""),
            # git rev-list --count @{u}..HEAD (get_commits_ahead)
            Mock(returncode=1, stdout="", stderr=""),  # No remote
            # git add . (stage_files)
            Mock(returncode=0, stdout="", stderr=""),
            # git commit -m "..." (create_git_commit)
            Mock(returncode=0, stdout="[main abc123d] feat: add auth\n", stderr=""),
            # git rev-parse HEAD (get commit hash)
            Mock(returncode=0, stdout=f"{self.test_commit_hash}\n", stderr=""),
            # git diff-tree --no-commit-id --name-only -r abc123d (get_committed_files)
            Mock(returncode=0, stdout="file1.py\nfile2.py\n", stderr=""),
        ]

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message)

        # Verify
        self.assertIsInstance(result, CommitOperation)
        self.assertEqual(result.result, CommitResult.SUCCESS)
        self.assertEqual(result.ticket_id, self.test_ticket_id)
        self.assertEqual(result.commit_message, self.test_commit_message)
        self.assertEqual(result.commit_hash, self.test_commit_hash)
        self.assertEqual(len(result.files_committed), 2)
        self.assertIn("file1.py", result.files_committed)
        self.assertIn("file2.py", result.files_committed)

    @patch("subprocess.run")
    def test_execute_commit_not_git_repo(self, mock_run):
        """Test commit execution when not in a git repository."""
        # Mock git repository check failure
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="")

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message)

        # Verify
        self.assertEqual(result.result, CommitResult.VALIDATION_FAILED)
        self.assertIn("Not in a Git repository", result.error)

    @patch("subprocess.run")
    def test_execute_commit_no_changes(self, mock_run):
        """Test commit execution when there are no changes."""
        # Mock git commands
        mock_run.side_effect = [
            # git rev-parse --git-dir (is_git_repository)
            Mock(returncode=0, stdout="", stderr=""),
            # git branch --show-current (get_current_branch)
            Mock(returncode=0, stdout="main\n", stderr=""),
            # git status --porcelain (get_file_status) - no changes
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-list --count @{u}..HEAD (get_commits_ahead)
            Mock(returncode=1, stdout="", stderr=""),
        ]

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message)

        # Verify
        self.assertEqual(result.result, CommitResult.NO_CHANGES)
        self.assertIn("No changes to commit", result.error)

    def test_execute_commit_invalid_message(self):
        """Test commit execution with invalid commit message."""
        invalid_messages = [
            "",  # Empty
            "   ",  # Whitespace only
            "fix",  # Too short/generic
            "x" * 100,  # Too long
        ]

        for invalid_message in invalid_messages:
            with self.subTest(message=invalid_message):
                with patch("subprocess.run") as mock_run:
                    # Mock valid git repo
                    mock_run.side_effect = [
                        Mock(returncode=0, stdout="", stderr=""),  # is_git_repository
                        Mock(returncode=0, stdout="main\n", stderr=""),  # get_current_branch
                        Mock(returncode=0, stdout="M  file1.py\n", stderr=""),  # get_file_status
                        Mock(returncode=1, stdout="", stderr=""),  # get_commits_ahead
                    ]

                    result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=invalid_message)

                    self.assertEqual(result.result, CommitResult.VALIDATION_FAILED)
                    self.assertIn("Invalid commit message", result.error)

    @patch("subprocess.run")
    def test_execute_commit_staging_failure(self, mock_run):
        """Test commit execution when file staging fails."""
        mock_run.side_effect = [
            # Repository validation (successful)
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="main\n", stderr=""),
            Mock(returncode=0, stdout="M  file1.py\n", stderr=""),
            Mock(returncode=1, stdout="", stderr=""),
            # git add . (staging failure)
            Mock(returncode=1, stdout="", stderr="Permission denied"),
        ]

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message)

        # Verify
        self.assertEqual(result.result, CommitResult.FAILED)
        self.assertIn("Failed to stage files", result.error)

    @patch("subprocess.run")
    def test_execute_commit_git_failure(self, mock_run):
        """Test commit execution when git commit fails."""
        mock_run.side_effect = [
            # Repository validation and staging (successful)
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="main\n", stderr=""),
            Mock(returncode=0, stdout="M  file1.py\n", stderr=""),
            Mock(returncode=1, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),  # staging success
            # git commit failure
            Mock(returncode=1, stdout="", stderr="nothing to commit, working tree clean"),
        ]

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message)

        # Verify
        self.assertEqual(result.result, CommitResult.FAILED)
        self.assertIn("Commit failed", result.error)

    @patch("subprocess.run")
    def test_execute_commit_dry_run(self, mock_run):
        """Test dry run mode."""
        mock_run.side_effect = [
            # Repository validation (successful)
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="main\n", stderr=""),
            Mock(returncode=0, stdout="M  file1.py\n", stderr=""),
            Mock(returncode=1, stdout="", stderr=""),
        ]

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message, dry_run=True)

        # Verify
        self.assertEqual(result.result, CommitResult.SUCCESS)
        self.assertIn("Dry run completed", result.error)
        self.assertIsNone(result.commit_hash)

        # Should not call git add or git commit
        git_add_calls = [call for call in mock_run.call_args_list if "add" in str(call)]
        git_commit_calls = [call for call in mock_run.call_args_list if "commit" in str(call)]
        self.assertEqual(len(git_add_calls), 0)
        self.assertEqual(len(git_commit_calls), 0)

    @patch("subprocess.run")
    def test_execute_commit_specific_files(self, mock_run):
        """Test commit execution with specific files."""
        mock_run.side_effect = [
            # Repository validation (successful)
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="main\n", stderr=""),
            Mock(returncode=0, stdout="M  file1.py\nM  file2.py\n", stderr=""),
            Mock(returncode=1, stdout="", stderr=""),
            # git add file1.py file2.py (specific files)
            Mock(returncode=0, stdout="", stderr=""),
            # git commit
            Mock(returncode=0, stdout="[main abc123d] feat: add auth\n", stderr=""),
            Mock(returncode=0, stdout=f"{self.test_commit_hash}\n", stderr=""),
            Mock(returncode=0, stdout="file1.py\n", stderr=""),
        ]

        # Execute
        result = self.service.execute_commit(
            ticket_id=self.test_ticket_id,
            commit_message=self.test_commit_message,
            file_paths=["file1.py", "file2.py"],
            stage_all_changes=False,
        )

        # Verify
        self.assertEqual(result.result, CommitResult.SUCCESS)

        # Check that git add was called with specific files
        add_call = mock_run.call_args_list[4]  # 5th call should be git add
        self.assertIn("add", str(add_call))
        self.assertIn("file1.py", str(add_call))
        self.assertIn("file2.py", str(add_call))

    @patch("subprocess.run")
    def test_get_repository_status(self, mock_run):
        """Test repository status retrieval."""
        mock_run.side_effect = [
            # git rev-parse --git-dir
            Mock(returncode=0, stdout="", stderr=""),
            # git branch --show-current
            Mock(returncode=0, stdout="feature-branch\n", stderr=""),
            # git status --porcelain
            Mock(returncode=0, stdout="M  staged.py\n M unstaged.py\n?? untracked.py\n", stderr=""),
            # git rev-list --count @{u}..HEAD
            Mock(returncode=0, stdout="3\n", stderr=""),
        ]

        # Execute
        status = self.service.get_repository_status()

        # Verify
        self.assertIsInstance(status, GitRepositoryStatus)
        self.assertTrue(status.is_git_repo)
        self.assertEqual(status.current_branch, "feature-branch")
        self.assertTrue(status.has_changes)
        self.assertEqual(len(status.staged_files), 1)
        self.assertEqual(len(status.unstaged_files), 1)
        self.assertEqual(len(status.untracked_files), 1)
        self.assertEqual(status.commits_ahead, 3)
        self.assertFalse(status.is_clean)

    @patch("subprocess.run")
    def test_rollback_commit_success(self, mock_run):
        """Test successful commit rollback."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Execute
        result = self.service.rollback_commit(self.test_commit_hash)

        # Verify
        self.assertIsInstance(result, CommitOperation)
        self.assertEqual(result.result, CommitResult.ROLLBACK_SUCCESS)
        self.assertEqual(result.commit_hash, self.test_commit_hash)

        # Verify git reset was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn("reset", call_args)
        self.assertIn("--soft", call_args)
        self.assertIn(f"{self.test_commit_hash}^", call_args)

    @patch("subprocess.run")
    def test_rollback_commit_failure(self, mock_run):
        """Test commit rollback failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: bad revision")

        # Execute
        result = self.service.rollback_commit(self.test_commit_hash)

        # Verify
        self.assertEqual(result.result, CommitResult.ROLLBACK_FAILED)
        self.assertIn("Rollback failed", result.error)

    def test_commit_message_validation(self):
        """Test commit message validation logic."""
        valid_messages = [
            "feat: add user authentication",
            "fix: resolve login bug (TICKET-123)",
            "docs: update API documentation",
            "refactor: improve code structure",
        ]

        invalid_messages = [
            "",  # Empty
            "   ",  # Whitespace only
            "fix",  # Too short
            "wip",  # Generic
            "x" * 80,  # Too long
        ]

        for message in valid_messages:
            with self.subTest(message=message):
                self.assertTrue(self.service._validate_commit_message(message))

        for message in invalid_messages:
            with self.subTest(message=message):
                self.assertFalse(self.service._validate_commit_message(message))

    def test_commit_history_tracking(self):
        """Test that commit operations are tracked in history."""
        # Create a mock operation
        operation = CommitOperation(operation_id="test_op_1", ticket_id="NOMAD-123", commit_message="test commit")
        operation.result = CommitResult.SUCCESS

        # Add to history
        self.service._finalize_operation(operation)

        # Verify history
        history = self.service.get_commit_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].operation_id, "test_op_1")
        self.assertEqual(history[0].result, CommitResult.SUCCESS)

    def test_statistics_calculation(self):
        """Test commit operation statistics calculation."""
        # Create mock operations with different results
        operations = [
            (CommitResult.SUCCESS, "NOMAD-1"),
            (CommitResult.SUCCESS, "NOMAD-2"),
            (CommitResult.FAILED, "NOMAD-3"),
            (CommitResult.NO_CHANGES, "NOMAD-4"),
        ]

        for result, ticket in operations:
            operation = CommitOperation(
                operation_id=f"op_{ticket}",
                ticket_id=ticket,
                commit_message=f"test commit for {ticket}",
            )
            operation.result = result
            self.service._finalize_operation(operation)

        # Get statistics
        stats = self.service.get_statistics()

        # Verify
        self.assertEqual(stats["total_operations"], 4)
        self.assertEqual(stats["successful"], 2)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["no_changes"], 1)
        self.assertEqual(stats["success_rate"], 50.0)
        self.assertIn("result_distribution", stats)

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run):
        """Test handling of git command timeouts."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)

        # Execute
        result = self.service.execute_commit(ticket_id=self.test_ticket_id, commit_message=self.test_commit_message)

        # Should handle timeout gracefully
        self.assertEqual(result.result, CommitResult.FAILED)
        # The exact error might vary depending on which git command times out first
        self.assertIsNotNone(result.error)

    def test_git_repository_status_properties(self):
        """Test GitRepositoryStatus computed properties."""
        # Test clean repository
        clean_status = GitRepositoryStatus(
            is_git_repo=True,
            current_branch="main",
            has_changes=False,
            staged_files=[],
            unstaged_files=[],
            untracked_files=[],
        )

        self.assertTrue(clean_status.is_clean)
        self.assertEqual(clean_status.total_changes, 0)

        # Test dirty repository
        dirty_status = GitRepositoryStatus(
            is_git_repo=True,
            current_branch="main",
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=["file2.py"],
            untracked_files=["file3.py"],
        )

        self.assertFalse(dirty_status.is_clean)
        self.assertEqual(dirty_status.total_changes, 3)

    def test_operation_dataclass_post_init(self):
        """Test CommitOperation dataclass post-initialization."""
        operation = CommitOperation(operation_id="test_op", ticket_id="NOMAD-123", commit_message="test message")

        # Should automatically set created_at
        self.assertIsNotNone(operation.created_at)
        self.assertIsInstance(operation.created_at, datetime)

        # Test with explicit created_at
        explicit_time = datetime(2023, 1, 1, 12, 0, 0)
        operation2 = CommitOperation(
            operation_id="test_op2",
            ticket_id="NOMAD-456",
            commit_message="test message 2",
            created_at=explicit_time,
        )

        self.assertEqual(operation2.created_at, explicit_time)


if __name__ == "__main__":
    unittest.main()
