import hashlib
import json
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CopyResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


@dataclass
class CopyOperation:
    """Represents a file copy operation"""

    operation_id: str
    source_path: str
    destination_path: str
    ticket_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[CopyResult] = None
    error: Optional[str] = None
    source_size: Optional[int] = None
    destination_size: Optional[int] = None
    backup_path: Optional[str] = None
    checksum_source: Optional[str] = None
    checksum_destination: Optional[str] = None


class TaskFileManager:
    """
    Manages task file copy operations with atomic operations, backup, and rollback capabilities.
    Includes path validation, disk space checking, and permission handling.
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self._copy_lock = threading.RLock()
        self._operation_history: List[CopyOperation] = []
        self._max_history = 100

        # Default paths - tasks stored in root directory
        from src.utils.file_operations import get_tasks_dir

        tasks_base_dir = get_tasks_dir()
        if not os.path.isabs(tasks_base_dir):
            tasks_base_dir = os.path.join(project_root, tasks_base_dir)
        self.tasks_source_dir = os.path.join(tasks_base_dir, "tasks")
        self.taskmaster_tasks_path = os.path.join(project_root, ".taskmaster", "tasks", "tasks.json")

        logger.info("📁 TaskFileManager initialized")
        logger.info(f"   📂 Source directory: {self.tasks_source_dir}")
        logger.info(f"   📄 TaskMaster tasks file: {self.taskmaster_tasks_path}")

    def copy_task_file_to_taskmaster(self, ticket_id: str, source_file_path: Optional[str] = None) -> CopyOperation:
        """
        Copy a task file from tasks/tasks/<ticket_id>.json to .taskmaster/tasks/tasks.json.

        Args:
            ticket_id: Ticket ID for the task file
            source_file_path: Optional custom source file path

        Returns:
            CopyOperation object with operation results
        """
        operation_id = f"copy_{ticket_id}_{int(datetime.now().timestamp())}"

        # Determine source path
        if source_file_path is None:
            source_file_path = os.path.join(self.tasks_source_dir, f"{ticket_id}.json")

        operation = CopyOperation(
            operation_id=operation_id,
            source_path=source_file_path,
            destination_path=self.taskmaster_tasks_path,
            ticket_id=ticket_id,
            start_time=datetime.now(),
        )

        with self._copy_lock:
            try:
                logger.info(f"📋 Starting task file copy operation")
                logger.info(f"   🎫 Ticket ID: {ticket_id}")
                logger.info(f"   📄 Source: {source_file_path}")
                logger.info(f"   📄 Destination: {self.taskmaster_tasks_path}")
                logger.info(f"   🆔 Operation ID: {operation_id}")

                # Step 1: Validate paths
                self._validate_paths(operation)
                if operation.result == CopyResult.FAILED:
                    return self._finalize_operation(operation)

                # Step 2: Check source file exists and get info
                if not os.path.exists(operation.source_path):
                    operation.result = CopyResult.FAILED
                    operation.error = f"Source file does not exist: {operation.source_path}"
                    logger.error(f"❌ {operation.error}")
                    return self._finalize_operation(operation)

                operation.source_size = os.path.getsize(operation.source_path)
                operation.checksum_source = self._calculate_checksum(operation.source_path)

                # Step 3: Check disk space
                if not self._check_disk_space(operation):
                    return self._finalize_operation(operation)

                # Step 4: Create backup of existing destination file
                backup_created = self._create_backup(operation)
                if operation.result == CopyResult.FAILED:
                    return self._finalize_operation(operation)

                # Step 5: Load and merge JSON content
                merged_content = self._merge_task_content(operation)
                if operation.result == CopyResult.FAILED:
                    if backup_created:
                        self._restore_backup(operation)
                    return self._finalize_operation(operation)

                # Step 6: Write merged content atomically
                success = self._write_atomic(operation, merged_content)
                if not success:
                    if backup_created:
                        self._restore_backup(operation)
                    return self._finalize_operation(operation)

                # Step 7: Verify copy integrity
                if os.path.exists(operation.destination_path):
                    operation.destination_size = os.path.getsize(operation.destination_path)
                    # For JSON merge, we don't compare checksums as content is different

                operation.result = CopyResult.SUCCESS
                logger.info(f"✅ Task file copy operation completed successfully")

                return self._finalize_operation(operation)

            except Exception as e:
                operation.result = CopyResult.FAILED
                operation.error = str(e)
                logger.error(f"❌ Task file copy operation failed: {e}")

                # Attempt to restore backup if it exists
                if operation.backup_path and os.path.exists(operation.backup_path):
                    try:
                        self._restore_backup(operation)
                        logger.info("🔄 Backup restored after failure")
                    except Exception as restore_error:
                        logger.error(f"❌ Failed to restore backup: {restore_error}")

                return self._finalize_operation(operation)

    def _validate_paths(self, operation: CopyOperation):
        """Validate and sanitize file paths to prevent path traversal attacks."""
        try:
            # Resolve absolute paths
            source_abs = os.path.abspath(operation.source_path)
            dest_abs = os.path.abspath(operation.destination_path)

            # Check that source is within expected directory structure
            project_abs = os.path.abspath(self.project_root)
            if not source_abs.startswith(project_abs):
                operation.result = CopyResult.FAILED
                operation.error = f"Source path outside project root: {source_abs}"
                logger.error(f"🚫 {operation.error}")
                return

            if not dest_abs.startswith(project_abs):
                operation.result = CopyResult.FAILED
                operation.error = f"Destination path outside project root: {dest_abs}"
                logger.error(f"🚫 {operation.error}")
                return

            # Check for path traversal attempts
            if ".." in operation.source_path or ".." in operation.destination_path:
                operation.result = CopyResult.FAILED
                operation.error = "Path traversal attempt detected"
                logger.error(f"🚫 {operation.error}")
                return

            # Update paths to absolute paths
            operation.source_path = source_abs
            operation.destination_path = dest_abs

            logger.info("✅ Path validation passed")

        except Exception as e:
            operation.result = CopyResult.FAILED
            operation.error = f"Path validation error: {e}"
            logger.error(f"❌ {operation.error}")

    def _check_disk_space(self, operation: CopyOperation) -> bool:
        """Check if there's enough disk space for the copy operation."""
        try:
            # Get required space (source file size + 10% buffer)
            required_space = int(operation.source_size * 1.1)

            # Get available space
            statvfs = os.statvfs(os.path.dirname(operation.destination_path))
            available_space = statvfs.f_frsize * statvfs.f_bavail

            if available_space < required_space:
                operation.result = CopyResult.FAILED
                operation.error = f"Insufficient disk space: need {required_space}, have {available_space}"
                logger.error(f"💾 {operation.error}")
                return False

            logger.info(f"💾 Disk space check passed: {available_space} bytes available")
            return True

        except Exception as e:
            operation.result = CopyResult.FAILED
            operation.error = f"Disk space check error: {e}"
            logger.error(f"❌ {operation.error}")
            return False

    def _create_backup(self, operation: CopyOperation) -> bool:
        """Create a backup of the destination file if it exists."""
        try:
            if not os.path.exists(operation.destination_path):
                logger.info("ℹ️ No existing destination file to backup")
                return False

            # Create backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(operation.destination_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)

            backup_filename = f"tasks_{timestamp}_{operation.ticket_id}.json.bak"
            backup_path = os.path.join(backup_dir, backup_filename)

            shutil.copy2(operation.destination_path, backup_path)
            operation.backup_path = backup_path

            logger.info(f"💾 Backup created: {backup_path}")
            return True

        except Exception as e:
            operation.result = CopyResult.FAILED
            operation.error = f"Backup creation error: {e}"
            logger.error(f"❌ {operation.error}")
            return False

    def _merge_task_content(self, operation: CopyOperation) -> Optional[Dict[str, Any]]:
        """
        Merge the source task file content with existing TaskMaster tasks.json.
        For multi-queue scenarios, we need to merge the task data appropriately.
        """
        try:
            # Load source task file
            with open(operation.source_path, "r", encoding="utf-8") as f:
                source_content = json.load(f)

            # Load existing TaskMaster tasks file if it exists
            existing_content = {}
            if os.path.exists(operation.destination_path):
                try:
                    with open(operation.destination_path, "r", encoding="utf-8") as f:
                        existing_content = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"⚠️ Could not load existing tasks file: {e}")
                    logger.info("📄 Starting with empty tasks structure")

            # Merge logic: replace the entire content for now
            # In a multi-queue scenario, you might want more sophisticated merging
            merged_content = source_content.copy()

            logger.info("🔀 Task content merged successfully")
            logger.info(f"   📊 Source tags: {list(source_content.keys()) if isinstance(source_content, dict) else 'N/A'}")

            return merged_content

        except Exception as e:
            operation.result = CopyResult.FAILED
            operation.error = f"Content merge error: {e}"
            logger.error(f"❌ {operation.error}")
            return None

    def _write_atomic(self, operation: CopyOperation, content: Dict[str, Any]) -> bool:
        """Write content to destination file atomically using temporary file."""
        try:
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(operation.destination_path), exist_ok=True)

            # Write to temporary file first
            temp_fd, temp_path = tempfile.mkstemp(
                dir=os.path.dirname(operation.destination_path),
                prefix=f"tasks_temp_{operation.ticket_id}_",
                suffix=".json",
            )

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)

                # Verify temp file was created correctly
                if not os.path.exists(temp_path):
                    raise Exception("Temporary file was not created")

                temp_size = os.path.getsize(temp_path)
                if temp_size == 0:
                    raise Exception("Temporary file is empty")

                # Atomic move from temp to destination
                shutil.move(temp_path, operation.destination_path)

                # Set appropriate permissions
                os.chmod(operation.destination_path, 0o644)

                logger.info(f"✅ Atomic write completed: {temp_size} bytes")
                return True

            except Exception as e:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e

        except Exception as e:
            operation.result = CopyResult.FAILED
            operation.error = f"Atomic write error: {e}"
            logger.error(f"❌ {operation.error}")
            return False

    def _restore_backup(self, operation: CopyOperation):
        """Restore the backup file."""
        if not operation.backup_path or not os.path.exists(operation.backup_path):
            raise Exception("No backup file available for restore")

        shutil.copy2(operation.backup_path, operation.destination_path)
        logger.info(f"🔄 Backup restored from: {operation.backup_path}")

    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _finalize_operation(self, operation: CopyOperation) -> CopyOperation:
        """Finalize the copy operation and add to history."""
        operation.end_time = datetime.now()
        self._add_to_history(operation)

        # Log final status
        duration = (operation.end_time - operation.start_time).total_seconds()
        logger.info(f"🏁 Copy operation completed: {operation.result}")
        logger.info(f"   ⏱️ Duration: {duration:.2f}s")
        if operation.source_size:
            logger.info(f"   📏 Source size: {operation.source_size} bytes")
        if operation.destination_size:
            logger.info(f"   📏 Destination size: {operation.destination_size} bytes")

        return operation

    def _add_to_history(self, operation: CopyOperation):
        """Add operation to history with size management."""
        self._operation_history.append(operation)

        # Keep history size manageable
        if len(self._operation_history) > self._max_history:
            self._operation_history = self._operation_history[-self._max_history :]

    def get_operation_history(self, limit: int = 50) -> List[CopyOperation]:
        """
        Get copy operation history for monitoring and debugging.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of CopyOperation objects
        """
        with self._copy_lock:
            return self._operation_history[-limit:] if limit else self._operation_history

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get copy operation statistics for monitoring.

        Returns:
            Dictionary with copy operation statistics
        """
        with self._copy_lock:
            total_operations = len(self._operation_history)
            successful = len([op for op in self._operation_history if op.result == CopyResult.SUCCESS])
            failed = len([op for op in self._operation_history if op.result == CopyResult.FAILED])
            skipped = len([op for op in self._operation_history if op.result == CopyResult.SKIPPED])
            rolled_back = len([op for op in self._operation_history if op.result == CopyResult.ROLLED_BACK])

            # Calculate total bytes copied
            total_bytes = sum(op.source_size for op in self._operation_history if op.result == CopyResult.SUCCESS and op.source_size is not None)

            stats = {
                "total_operations": total_operations,
                "successful_operations": successful,
                "failed_operations": failed,
                "skipped_operations": skipped,
                "rolled_back_operations": rolled_back,
                "success_rate": ((successful / total_operations * 100) if total_operations > 0 else 0),
                "total_bytes_copied": total_bytes,
                "backups_created": len([op for op in self._operation_history if op.backup_path is not None]),
            }

            logger.info(f"📊 Task File Copy Statistics: {stats}")
            return stats

    def cleanup_backups(self, max_age_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old backup files.

        Args:
            max_age_days: Maximum age of backup files to keep

        Returns:
            Dictionary with cleanup results
        """
        try:
            backup_dir = os.path.join(os.path.dirname(self.taskmaster_tasks_path), "backups")

            if not os.path.exists(backup_dir):
                return {"cleaned_files": 0, "total_size_freed": 0, "errors": 0}

            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
            cleaned_files = 0
            total_size_freed = 0
            errors = 0

            for filename in os.listdir(backup_dir):
                file_path = os.path.join(backup_dir, filename)

                try:
                    if filename.endswith(".bak") and os.path.isfile(file_path):
                        file_mtime = os.path.getmtime(file_path)

                        if file_mtime < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            cleaned_files += 1
                            total_size_freed += file_size
                            logger.info(f"🗑️ Cleaned up old backup: {filename}")

                except Exception as e:
                    errors += 1
                    logger.error(f"❌ Error cleaning backup file {filename}: {e}")

            result = {
                "cleaned_files": cleaned_files,
                "total_size_freed": total_size_freed,
                "errors": errors,
            }

            logger.info(f"🧹 Backup cleanup completed: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Backup cleanup failed: {e}")
            return {"cleaned_files": 0, "total_size_freed": 0, "errors": 1, "error": str(e)}
