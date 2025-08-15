#!/usr/bin/env python3
"""
Unit tests for TaskFileManager - Task File Copy Mechanism
Tests atomic file operations, backup/rollback, path validation, and statistics tracking.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from task_file_manager import CopyOperation, CopyResult, TaskFileManager


class TestTaskFileManager(unittest.TestCase):
    """Test suite for TaskFileManager functionality."""

    def setUp(self):
        """Set up test environment with temporary directories."""
        self.test_dir = tempfile.mkdtemp()
        self.project_root = self.test_dir

        # Create test directory structure
        self.tasks_source_dir = os.path.join(self.test_dir, "tasks", "tasks")
        self.taskmaster_dir = os.path.join(self.test_dir, ".taskmaster", "tasks")
        self.taskmaster_tasks_path = os.path.join(self.taskmaster_dir, "tasks.json")

        os.makedirs(self.tasks_source_dir, exist_ok=True)
        os.makedirs(self.taskmaster_dir, exist_ok=True)

        self.manager = TaskFileManager(self.project_root)

    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_test_task_file(self, ticket_id: str, content: dict = None) -> str:
        """Helper method to create a test task file."""
        if content is None:
            content = {
                "default": {
                    "1": {
                        "id": "1",
                        "title": f"Test Task for {ticket_id}",
                        "description": f"Test task description for ticket {ticket_id}",
                        "status": "pending",
                        "priority": "medium",
                    }
                }
            }

        file_path = os.path.join(self.tasks_source_dir, f"{ticket_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)

        return file_path

    def create_existing_taskmaster_file(self, content: dict = None) -> str:
        """Helper method to create existing TaskMaster tasks file."""
        if content is None:
            content = {
                "default": {
                    "1": {
                        "id": "1",
                        "title": "Existing Task",
                        "description": "Existing task in TaskMaster",
                        "status": "done",
                        "priority": "high",
                    }
                }
            }

        with open(self.taskmaster_tasks_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)

        return self.taskmaster_tasks_path

    def test_initialization(self):
        """Test TaskFileManager initialization."""
        self.assertEqual(self.manager.project_root, self.project_root)
        self.assertTrue(os.path.exists(self.manager.tasks_source_dir))
        self.assertTrue(os.path.exists(os.path.dirname(self.manager.taskmaster_tasks_path)))
        self.assertEqual(len(self.manager._operation_history), 0)

    def test_successful_copy_operation(self):
        """Test successful task file copy operation."""
        # Create test source file
        ticket_id = "NOMAD-123"
        test_content = {
            "default": {
                "1": {
                    "id": "1",
                    "title": "Test Task",
                    "description": "Test description",
                    "status": "pending",
                    "priority": "high",
                }
            }
        }
        source_path = self.create_test_task_file(ticket_id, test_content)

        # Perform copy operation
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Verify operation success
        self.assertEqual(operation.result, CopyResult.SUCCESS)
        self.assertEqual(operation.ticket_id, ticket_id)
        self.assertIsNotNone(operation.start_time)
        self.assertIsNotNone(operation.end_time)
        self.assertIsNone(operation.error)

        # Verify destination file exists and has correct content
        self.assertTrue(os.path.exists(self.taskmaster_tasks_path))

        with open(self.taskmaster_tasks_path, "r", encoding="utf-8") as f:
            copied_content = json.load(f)

        self.assertEqual(copied_content, test_content)

        # Verify operation history
        history = self.manager.get_operation_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].result, CopyResult.SUCCESS)

    def test_copy_with_backup_creation(self):
        """Test copy operation with existing file backup."""
        ticket_id = "NOMAD-456"

        # Create existing TaskMaster file
        existing_content = {"existing": "data"}
        self.create_existing_taskmaster_file(existing_content)

        # Create new task file
        new_content = {"new": "data"}
        self.create_test_task_file(ticket_id, new_content)

        # Perform copy operation
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Verify operation success
        self.assertEqual(operation.result, CopyResult.SUCCESS)
        self.assertIsNotNone(operation.backup_path)

        # Verify backup was created
        self.assertTrue(os.path.exists(operation.backup_path))

        # Verify backup contains original content
        with open(operation.backup_path, "r", encoding="utf-8") as f:
            backup_content = json.load(f)

        self.assertEqual(backup_content, existing_content)

        # Verify destination has new content
        with open(self.taskmaster_tasks_path, "r", encoding="utf-8") as f:
            final_content = json.load(f)

        self.assertEqual(final_content, new_content)

    def test_copy_nonexistent_source_file(self):
        """Test copy operation with nonexistent source file."""
        ticket_id = "NOMAD-NONEXISTENT"

        # Attempt to copy nonexistent file
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Verify operation failed
        self.assertEqual(operation.result, CopyResult.FAILED)
        self.assertIsNotNone(operation.error)
        self.assertIn("Source file does not exist", operation.error)

        # Verify no destination file was created
        self.assertFalse(os.path.exists(self.taskmaster_tasks_path))

    def test_path_validation(self):
        """Test path validation and security checks."""
        ticket_id = "NOMAD-PATH-TEST"

        # Test path traversal attempt
        malicious_path = "../../../etc/passwd"
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id, malicious_path)

        # Verify operation failed due to path validation
        self.assertEqual(operation.result, CopyResult.FAILED)
        self.assertIn("outside project root", operation.error)

    def test_custom_source_path(self):
        """Test copy operation with custom source path."""
        ticket_id = "NOMAD-CUSTOM"

        # Create custom source file in different location
        custom_dir = os.path.join(self.test_dir, "custom")
        os.makedirs(custom_dir, exist_ok=True)
        custom_path = os.path.join(custom_dir, "custom_task.json")

        custom_content = {"custom": "task"}
        with open(custom_path, "w", encoding="utf-8") as f:
            json.dump(custom_content, f, indent=2)

        # Perform copy with custom source path
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id, custom_path)

        # Verify operation success
        self.assertEqual(operation.result, CopyResult.SUCCESS)
        self.assertEqual(operation.source_path, os.path.abspath(custom_path))

        # Verify content was copied correctly
        with open(self.taskmaster_tasks_path, "r", encoding="utf-8") as f:
            copied_content = json.load(f)

        self.assertEqual(copied_content, custom_content)

    def test_insufficient_disk_space(self):
        """Test copy operation with insufficient disk space."""
        ticket_id = "NOMAD-DISKSPACE"
        self.create_test_task_file(ticket_id)

        # Mock the disk space check method directly
        original_check = self.manager._check_disk_space

        def failing_disk_check(operation):
            operation.result = CopyResult.FAILED
            operation.error = "Insufficient disk space: need 1000000, have 100"
            return False

        self.manager._check_disk_space = failing_disk_check

        try:
            # Attempt copy operation
            operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

            # Verify operation failed due to disk space
            self.assertEqual(operation.result, CopyResult.FAILED)
            self.assertIn("Insufficient disk space", operation.error)
        finally:
            # Restore original method
            self.manager._check_disk_space = original_check

    def test_atomic_write_failure_rollback(self):
        """Test rollback behavior when atomic write fails."""
        ticket_id = "NOMAD-ROLLBACK"

        # Create existing TaskMaster file
        existing_content = {"existing": "content"}
        self.create_existing_taskmaster_file(existing_content)

        # Create source file
        self.create_test_task_file(ticket_id)

        # Mock atomic write to fail after backup is created
        original_write_atomic = self.manager._write_atomic

        def failing_write_atomic(operation, content):
            operation.result = CopyResult.FAILED
            operation.error = "Simulated write failure"
            return False

        self.manager._write_atomic = failing_write_atomic

        # Attempt copy operation
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Verify operation failed
        self.assertEqual(operation.result, CopyResult.FAILED)
        self.assertIn("Simulated write failure", operation.error)

        # Verify original content was restored
        with open(self.taskmaster_tasks_path, "r", encoding="utf-8") as f:
            restored_content = json.load(f)

        self.assertEqual(restored_content, existing_content)

        # Restore original method
        self.manager._write_atomic = original_write_atomic

    def test_concurrent_operations(self):
        """Test thread safety with concurrent copy operations."""
        num_threads = 5
        operations = []

        def copy_task(thread_id):
            ticket_id = f"NOMAD-THREAD-{thread_id}"
            content = {"thread_id": thread_id, "data": f"test_{thread_id}"}
            self.create_test_task_file(ticket_id, content)

            operation = self.manager.copy_task_file_to_taskmaster(ticket_id)
            operations.append(operation)

        # Start concurrent threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=copy_task, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all operations completed
        self.assertEqual(len(operations), num_threads)

        # At least one operation should succeed (the last one to write)
        successful_ops = [op for op in operations if op.result == CopyResult.SUCCESS]
        self.assertGreater(len(successful_ops), 0)

        # Verify history contains all operations
        history = self.manager.get_operation_history()
        self.assertEqual(len(history), num_threads)

    def test_checksum_calculation(self):
        """Test checksum calculation for integrity verification."""
        ticket_id = "NOMAD-CHECKSUM"
        source_path = self.create_test_task_file(ticket_id)

        # Calculate checksum directly
        checksum1 = self.manager._calculate_checksum(source_path)
        checksum2 = self.manager._calculate_checksum(source_path)

        # Verify consistent checksums
        self.assertEqual(checksum1, checksum2)
        self.assertEqual(len(checksum1), 32)  # MD5 hex digest length

    def test_operation_statistics(self):
        """Test operation statistics tracking."""
        # Initially no operations
        stats = self.manager.get_statistics()
        self.assertEqual(stats["total_operations"], 0)

        # Perform successful operation
        ticket_id = "NOMAD-STATS-SUCCESS"
        self.create_test_task_file(ticket_id)
        self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Perform failed operation
        ticket_id_fail = "NOMAD-STATS-FAIL"
        self.manager.copy_task_file_to_taskmaster(ticket_id_fail)  # No source file

        # Check updated statistics
        stats = self.manager.get_statistics()
        self.assertEqual(stats["total_operations"], 2)
        self.assertEqual(stats["successful_operations"], 1)
        self.assertEqual(stats["failed_operations"], 1)
        self.assertEqual(stats["success_rate"], 50.0)
        self.assertGreater(stats["total_bytes_copied"], 0)

    def test_backup_cleanup(self):
        """Test backup file cleanup functionality."""
        ticket_id = "NOMAD-CLEANUP"

        # Create existing TaskMaster file to ensure backup creation
        self.create_existing_taskmaster_file()
        self.create_test_task_file(ticket_id)

        # Perform copy operation (creates backup)
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)
        self.assertEqual(operation.result, CopyResult.SUCCESS)
        self.assertIsNotNone(operation.backup_path)

        # Verify backup exists
        self.assertTrue(os.path.exists(operation.backup_path))

        # Test cleanup with recent files (should not clean)
        cleanup_results = self.manager.cleanup_backups(max_age_days=30)
        self.assertEqual(cleanup_results["cleaned_files"], 0)
        self.assertTrue(os.path.exists(operation.backup_path))

        # Test cleanup with old files (simulate by modifying age)
        cleanup_results = self.manager.cleanup_backups(max_age_days=0)
        self.assertEqual(cleanup_results["cleaned_files"], 1)
        self.assertGreater(cleanup_results["total_size_freed"], 0)

    def test_operation_history_management(self):
        """Test operation history size management."""
        # Set small history limit for testing
        original_max = self.manager._max_history
        self.manager._max_history = 3

        try:
            # Perform more operations than history limit
            for i in range(5):
                ticket_id = f"NOMAD-HISTORY-{i}"
                if i % 2 == 0:  # Create source for even numbers
                    self.create_test_task_file(ticket_id)
                self.manager.copy_task_file_to_taskmaster(ticket_id)

            # Verify history is limited
            history = self.manager.get_operation_history()
            self.assertEqual(len(history), 3)

            # Verify it keeps the most recent operations
            ticket_ids = [op.ticket_id for op in history]
            self.assertIn("NOMAD-HISTORY-4", ticket_ids)
            self.assertNotIn("NOMAD-HISTORY-0", ticket_ids)

        finally:
            # Restore original limit
            self.manager._max_history = original_max

    def test_json_merge_functionality(self):
        """Test JSON content merging logic."""
        ticket_id = "NOMAD-MERGE"

        # Create source task with new content
        new_content = {"default": {"2": {"id": "2", "title": "New Task", "status": "pending"}}}
        self.create_test_task_file(ticket_id, new_content)

        # Perform copy operation
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Verify merge behavior (currently replaces entire content)
        self.assertEqual(operation.result, CopyResult.SUCCESS)

        with open(self.taskmaster_tasks_path, "r", encoding="utf-8") as f:
            final_content = json.load(f)

        self.assertEqual(final_content, new_content)

    def test_error_handling_invalid_json(self):
        """Test error handling with invalid JSON content."""
        ticket_id = "NOMAD-INVALID-JSON"

        # Create source file with invalid JSON
        source_path = os.path.join(self.tasks_source_dir, f"{ticket_id}.json")
        with open(source_path, "w") as f:
            f.write("{ invalid json content")

        # Attempt copy operation
        operation = self.manager.copy_task_file_to_taskmaster(ticket_id)

        # Verify operation failed gracefully
        self.assertEqual(operation.result, CopyResult.FAILED)
        self.assertIn("Content merge error", operation.error)


class TestCopyOperation(unittest.TestCase):
    """Test suite for CopyOperation dataclass."""

    def test_copy_operation_creation(self):
        """Test CopyOperation object creation and attributes."""
        start_time = datetime.now()

        operation = CopyOperation(
            operation_id="test_op_123",
            source_path="/test/source.json",
            destination_path="/test/dest.json",
            ticket_id="NOMAD-TEST",
            start_time=start_time,
        )

        self.assertEqual(operation.operation_id, "test_op_123")
        self.assertEqual(operation.source_path, "/test/source.json")
        self.assertEqual(operation.destination_path, "/test/dest.json")
        self.assertEqual(operation.ticket_id, "NOMAD-TEST")
        self.assertEqual(operation.start_time, start_time)
        self.assertIsNone(operation.end_time)
        self.assertIsNone(operation.result)


if __name__ == "__main__":
    # Configure logging for tests
    import logging

    logging.basicConfig(level=logging.WARNING)  # Reduce noise during tests

    # Run the tests
    unittest.main(verbosity=2)
