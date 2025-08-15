#!/usr/bin/env python3
"""
Git Commit Execution Service

Handles Git commit creation without pushing to remote repository.
Follows the same patterns as BranchService for consistency and reliability.
"""
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CommitResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NO_CHANGES = "no_changes"
    VALIDATION_FAILED = "validation_failed"
    ROLLBACK_SUCCESS = "rollback_success"
    ROLLBACK_FAILED = "rollback_failed"


@dataclass
class CommitOperation:
    """Represents a git commit operation with results and metadata"""

    operation_id: str
    ticket_id: str
    commit_message: str
    files_to_commit: Optional[List[str]] = None
    created_at: datetime = None
    result: Optional[CommitResult] = None
    error: Optional[str] = None
    git_output: Optional[str] = None
    commit_hash: Optional[str] = None
    files_committed: Optional[List[str]] = None
    pre_commit_status: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class GitRepositoryStatus:
    """Represents the current status of a Git repository"""

    def __init__(
        self,
        is_git_repo: bool = False,
        current_branch: str = "unknown",
        has_changes: bool = False,
        staged_files: List[str] = None,
        unstaged_files: List[str] = None,
        untracked_files: List[str] = None,
        commits_ahead: int = 0,
    ):
        self.is_git_repo = is_git_repo
        self.current_branch = current_branch
        self.has_changes = has_changes
        self.staged_files = staged_files or []
        self.unstaged_files = unstaged_files or []
        self.untracked_files = untracked_files or []
        self.commits_ahead = commits_ahead

    @property
    def total_changes(self) -> int:
        """Total number of changed files."""
        return len(self.staged_files) + len(self.unstaged_files) + len(self.untracked_files)

    @property
    def is_clean(self) -> bool:
        """Whether the repository has no changes."""
        return not self.has_changes and self.total_changes == 0


class GitCommitService:
    """
    Service for executing git commits without pushing to remote repository.

    Features:
    - Pre-commit validation and repository status checking
    - Flexible file staging (all changes or specific files)
    - Commit execution with comprehensive error handling
    - Post-commit verification and rollback capabilities
    - Explicit separation of commit and push operations
    - Operation history tracking for debugging
    """

    def __init__(self, project_root: str, max_retries: int = 3):
        """
        Initialize the git commit service.

        Args:
            project_root: Path to the project root directory
            max_retries: Maximum retry attempts for git operations
        """
        self.project_root = Path(project_root)
        self.max_retries = max_retries
        self.default_timeout = 30  # seconds

        # Operation tracking
        self._commit_history: List[CommitOperation] = []
        self._max_history = 1000

        # Git command validation
        self._validate_git_availability()

        logger.info(f"🔧 GitCommitService initialized (project: {self.project_root})")

    def execute_commit(
        self,
        ticket_id: str,
        commit_message: str,
        file_paths: Optional[List[str]] = None,
        stage_all_changes: bool = True,
        dry_run: bool = False,
    ) -> CommitOperation:
        """
        Execute a git commit with specified parameters.

        Args:
            ticket_id: Ticket identifier for tracking
            commit_message: Commit message to use
            file_paths: Specific files to commit (None for all changes)
            stage_all_changes: Whether to stage all changes or only specified files
            dry_run: If True, perform validation without actual commit

        Returns:
            CommitOperation with results and metadata
        """
        operation_id = f"commit_{ticket_id}_{int(time.time())}"

        operation = CommitOperation(
            operation_id=operation_id,
            ticket_id=ticket_id,
            commit_message=commit_message,
            files_to_commit=file_paths,
        )

        try:
            logger.info(f"🔄 Executing commit for ticket {ticket_id}")
            logger.info(f"   📝 Message: {commit_message}")
            logger.info(f"   📁 Files: {'all changes' if stage_all_changes else file_paths}")
            logger.info(f"   🧪 Dry run: {dry_run}")

            # Step 1: Validate repository state
            repo_status = self._get_repository_status()
            operation.pre_commit_status = self._repository_status_to_dict(repo_status)

            if not repo_status.is_git_repo:
                operation.result = CommitResult.VALIDATION_FAILED
                operation.error = "Not in a Git repository"
                logger.error(f"❌ {operation.error}")
                return self._finalize_operation(operation)

            # Step 2: Check for changes to commit
            if not repo_status.has_changes and repo_status.total_changes == 0:
                operation.result = CommitResult.NO_CHANGES
                operation.error = "No changes to commit"
                logger.info(f"ℹ️ {operation.error}")
                return self._finalize_operation(operation)

            # Step 3: Validate commit message
            if not self._validate_commit_message(commit_message):
                operation.result = CommitResult.VALIDATION_FAILED
                operation.error = "Invalid commit message format"
                logger.error(f"❌ {operation.error}")
                return self._finalize_operation(operation)

            if dry_run:
                operation.result = CommitResult.SUCCESS
                operation.error = "Dry run completed successfully"
                logger.info("✅ Dry run validation passed")
                return self._finalize_operation(operation)

            # Step 4: Stage files
            staged_successfully = self._stage_files(file_paths, stage_all_changes)
            if not staged_successfully:
                operation.result = CommitResult.FAILED
                operation.error = "Failed to stage files for commit"
                logger.error(f"❌ {operation.error}")
                return self._finalize_operation(operation)

            # Step 5: Execute commit
            success, output, commit_hash = self._create_git_commit(commit_message)
            operation.git_output = output

            if success and commit_hash:
                operation.result = CommitResult.SUCCESS
                operation.commit_hash = commit_hash
                operation.files_committed = self._get_committed_files(commit_hash)
                logger.info(f"✅ Commit created successfully: {commit_hash[:8]}")
            else:
                operation.result = CommitResult.FAILED
                operation.error = f"Commit failed: {output}"
                logger.error(f"❌ Commit failed: {output}")

            return self._finalize_operation(operation)

        except Exception as e:
            operation.result = CommitResult.FAILED
            operation.error = str(e)
            logger.error(f"❌ Exception during commit execution: {e}")
            return self._finalize_operation(operation)

    def get_repository_status(self) -> GitRepositoryStatus:
        """
        Get current repository status information.

        Returns:
            GitRepositoryStatus object with current state
        """
        return self._get_repository_status()

    def rollback_commit(self, commit_hash: str) -> CommitOperation:
        """
        Rollback a specific commit (soft reset).

        Args:
            commit_hash: Hash of commit to rollback

        Returns:
            CommitOperation with rollback results
        """
        operation_id = f"rollback_{commit_hash[:8]}_{int(time.time())}"

        operation = CommitOperation(
            operation_id=operation_id,
            ticket_id=f"rollback-{commit_hash[:8]}",
            commit_message=f"Rollback commit {commit_hash[:8]}",
            commit_hash=commit_hash,
        )

        try:
            logger.info(f"🔄 Rolling back commit: {commit_hash[:8]}")

            success, output = self._rollback_git_commit(commit_hash)
            operation.git_output = output

            if success:
                operation.result = CommitResult.ROLLBACK_SUCCESS
                logger.info(f"✅ Rollback successful: {commit_hash[:8]}")
            else:
                operation.result = CommitResult.ROLLBACK_FAILED
                operation.error = f"Rollback failed: {output}"
                logger.error(f"❌ Rollback failed: {output}")

            return self._finalize_operation(operation)

        except Exception as e:
            operation.result = CommitResult.ROLLBACK_FAILED
            operation.error = str(e)
            logger.error(f"❌ Exception during rollback: {e}")
            return self._finalize_operation(operation)

    def _get_repository_status(self) -> GitRepositoryStatus:
        """Get comprehensive repository status."""
        try:
            # Check if it's a git repository
            if not self._is_git_repository():
                return GitRepositoryStatus(is_git_repo=False)

            # Get current branch
            current_branch = self._get_current_branch()

            # Get file status
            staged_files, unstaged_files, untracked_files = self._get_file_status()

            has_changes = len(staged_files) > 0 or len(unstaged_files) > 0 or len(untracked_files) > 0

            # Get commits ahead of remote
            commits_ahead = self._get_commits_ahead()

            return GitRepositoryStatus(
                is_git_repo=True,
                current_branch=current_branch,
                has_changes=has_changes,
                staged_files=staged_files,
                unstaged_files=unstaged_files,
                untracked_files=untracked_files,
                commits_ahead=commits_ahead,
            )

        except Exception as e:
            logger.error(f"❌ Failed to get repository status: {e}")
            return GitRepositoryStatus(is_git_repo=False)

    def _is_git_repository(self) -> bool:
        """Check if the current directory is a Git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_current_branch(self) -> str:
        """Get the current Git branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return "unknown"

        except Exception:
            return "unknown"

    def _get_file_status(self) -> Tuple[List[str], List[str], List[str]]:
        """
        Get lists of staged, unstaged, and untracked files.

        Returns:
            Tuple of (staged_files, unstaged_files, untracked_files)
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return [], [], []

            staged_files = []
            unstaged_files = []
            untracked_files = []

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                status_code = line[:2]
                file_path = line[3:]

                # Parse git status codes
                if status_code[0] in ["A", "M", "D", "R", "C"]:  # Staged changes
                    staged_files.append(file_path)

                if status_code[1] in ["M", "D"]:  # Unstaged changes
                    unstaged_files.append(file_path)

                if status_code == "??":  # Untracked files
                    untracked_files.append(file_path)

            return staged_files, unstaged_files, untracked_files

        except Exception as e:
            logger.error(f"❌ Failed to get file status: {e}")
            return [], [], []

    def _get_commits_ahead(self) -> int:
        """Get number of commits ahead of remote branch."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return int(result.stdout.strip())
            else:
                return 0

        except Exception:
            return 0

    def _validate_commit_message(self, message: str) -> bool:
        """
        Validate commit message format and content.

        Args:
            message: Commit message to validate

        Returns:
            True if message is valid
        """
        if not message or not message.strip():
            return False

        # Check minimum length
        if len(message.strip()) < 5:
            return False

        # Check maximum length for subject line
        first_line = message.split("\n")[0]
        if len(first_line) > 72:
            return False

        # Check for common problematic patterns
        if message.strip().lower() in ["wip", "temp", "fix", "update", "change"]:
            return False

        return True

    def _stage_files(self, file_paths: Optional[List[str]], stage_all_changes: bool) -> bool:
        """
        Stage files for commit.

        Args:
            file_paths: Specific files to stage
            stage_all_changes: Whether to stage all changes

        Returns:
            True if staging was successful
        """
        try:
            if stage_all_changes:
                # Stage all changes
                result = subprocess.run(
                    ["git", "add", "."],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=self.default_timeout,
                )

                if result.returncode == 0:
                    logger.debug("📁 Staged all changes")
                    return True
                else:
                    logger.error(f"❌ Failed to stage all changes: {result.stderr}")
                    return False

            elif file_paths:
                # Stage specific files
                cmd = ["git", "add"] + file_paths
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=self.default_timeout,
                )

                if result.returncode == 0:
                    logger.debug(f"📁 Staged {len(file_paths)} specific files")
                    return True
                else:
                    logger.error(f"❌ Failed to stage specific files: {result.stderr}")
                    return False

            else:
                # No files specified and not staging all - check if anything is already staged
                staged_files, _, _ = self._get_file_status()
                if staged_files:
                    logger.debug(f"📁 Using {len(staged_files)} already staged files")
                    return True
                else:
                    logger.error("❌ No files to stage and nothing already staged")
                    return False

        except Exception as e:
            logger.error(f"❌ Exception during file staging: {e}")
            return False

    def _create_git_commit(self, commit_message: str) -> Tuple[bool, str, Optional[str]]:
        """
        Create a git commit with the specified message.

        Args:
            commit_message: Message for the commit

        Returns:
            Tuple of (success: bool, output: str, commit_hash: Optional[str])
        """
        try:
            # Create the commit
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.default_timeout,
            )

            output = result.stdout + result.stderr

            if result.returncode == 0:
                # Get the commit hash
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None
                return True, output.strip(), commit_hash
            else:
                return False, output.strip(), None

        except subprocess.TimeoutExpired:
            return False, "Git commit operation timed out", None
        except Exception as e:
            return False, f"Exception during commit: {str(e)}", None

    def _get_committed_files(self, commit_hash: str) -> List[str]:
        """
        Get list of files in a specific commit.

        Args:
            commit_hash: Hash of the commit

        Returns:
            List of file paths in the commit
        """
        try:
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
                return files
            else:
                return []

        except Exception:
            return []

    def _rollback_git_commit(self, commit_hash: str) -> Tuple[bool, str]:
        """
        Rollback a commit using git reset.

        Args:
            commit_hash: Hash of commit to rollback

        Returns:
            Tuple of (success: bool, output: str)
        """
        try:
            # Soft reset to preserve working directory changes
            result = subprocess.run(
                ["git", "reset", "--soft", f"{commit_hash}^"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.default_timeout,
            )

            output = result.stdout + result.stderr
            return result.returncode == 0, output.strip()

        except subprocess.TimeoutExpired:
            return False, "Git rollback operation timed out"
        except Exception as e:
            return False, f"Exception during rollback: {str(e)}"

    def _validate_git_availability(self):
        """Validate that git command is available."""
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                logger.debug(f"✅ Git available: {result.stdout.strip()}")
            else:
                logger.warning("⚠️ Git command not available or not working properly")

        except Exception as e:
            logger.error(f"❌ Git validation failed: {e}")

    def _repository_status_to_dict(self, status: GitRepositoryStatus) -> Dict[str, Any]:
        """Convert repository status to dictionary for logging/storage."""
        return {
            "is_git_repo": status.is_git_repo,
            "current_branch": status.current_branch,
            "has_changes": status.has_changes,
            "staged_files_count": len(status.staged_files),
            "unstaged_files_count": len(status.unstaged_files),
            "untracked_files_count": len(status.untracked_files),
            "total_changes": status.total_changes,
            "commits_ahead": status.commits_ahead,
            "is_clean": status.is_clean,
        }

    def _finalize_operation(self, operation: CommitOperation) -> CommitOperation:
        """Finalize the operation and add to history."""
        self._commit_history.append(operation)

        # Keep history manageable
        if len(self._commit_history) > self._max_history:
            self._commit_history = self._commit_history[-self._max_history :]

        return operation

    def get_commit_history(self, limit: int = 50) -> List[CommitOperation]:
        """
        Get commit operation history.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of CommitOperation objects
        """
        return self._commit_history[-limit:] if limit else self._commit_history

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get commit operation statistics.

        Returns:
            Dictionary with operation statistics
        """
        total = len(self._commit_history)
        if total == 0:
            return {"total_operations": 0, "success_rate": 0.0, "result_distribution": {}}

        successful = len([op for op in self._commit_history if op.result == CommitResult.SUCCESS])
        failed = len([op for op in self._commit_history if op.result == CommitResult.FAILED])
        no_changes = len([op for op in self._commit_history if op.result == CommitResult.NO_CHANGES])
        validation_failed = len([op for op in self._commit_history if op.result == CommitResult.VALIDATION_FAILED])

        return {
            "total_operations": total,
            "successful": successful,
            "failed": failed,
            "no_changes": no_changes,
            "validation_failed": validation_failed,
            "success_rate": (successful / total * 100),
            "result_distribution": {
                CommitResult.SUCCESS.value: successful,
                CommitResult.FAILED.value: failed,
                CommitResult.NO_CHANGES.value: no_changes,
                CommitResult.VALIDATION_FAILED.value: validation_failed,
            },
        }
