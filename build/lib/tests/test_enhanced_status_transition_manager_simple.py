#!/usr/bin/env python3
"""
Simplified unit tests for EnhancedStatusTransitionManager

Tests the core functionality without complex transition validation.
"""
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from core.managers.enhanced_status_transition_manager import EnhancedStatusTransition, EnhancedStatusTransitionManager, EnhancedTransitionResult
from core.managers.status_transition_manager import StatusTransition, TransitionResult
from core.services.git_commit_service import CommitOperation, CommitResult
from core.services.task_validation_service import ValidationErrorCode, ValidationOperation, ValidationResult


class TestEnhancedStatusTransitionManagerSimple(unittest.TestCase):
    """Simplified test cases for EnhancedStatusTransitionManager."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_notion_client = Mock()
        self.temp_dir = tempfile.mkdtemp()

        # Mock global config
        self.mock_global_config = Mock()
        self.mock_global_config.get_validation_config.return_value = {
            "cache_ttl_minutes": 5,
            "enabled": True,
            "checkbox_property_name": "Commit",
            "validation_enabled": True,
            "strict_validation": False,
        }

        # Create manager with all services enabled
        with patch(
            "core.managers.enhanced_status_transition_manager.get_global_config",
            return_value=self.mock_global_config,
        ):
            self.manager = EnhancedStatusTransitionManager(
                notion_client=self.mock_notion_client,
                project_root=self.temp_dir,
                enable_validation=True,
                enable_commits=True,
            )

        # Test data
        self.test_page_id = "test-page-123"
        self.test_ticket_id = "NOMAD-456"
        self.test_task_title = "Test task completion"

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_manager_initialization_with_services(self):
        """Test manager initialization with all services enabled."""
        self.assertTrue(self.manager.enable_validation)
        self.assertTrue(self.manager.enable_commits)
        self.assertIsNotNone(self.manager.validation_service)
        self.assertIsNotNone(self.manager.commit_message_generator)
        self.assertIsNotNone(self.manager.git_commit_service)
        self.assertEqual(self.manager.project_root, self.temp_dir)

    def test_requires_commit_logic(self):
        """Test commit requirement detection logic."""
        test_cases = [
            # (from_status, to_status, expected_requires_commit)
            ("in-progress", "done", True),
            ("In progress", "Done", True),
            ("IN_PROGRESS", "DONE", True),
            ("in_progress", "finished", True),
            ("todo", "in-progress", False),
            ("done", "in-progress", False),
            ("review", "completed", True),  # completion status
        ]

        for from_status, to_status, expected in test_cases:
            with self.subTest(from_status=from_status, to_status=to_status):
                result = self.manager._requires_commit(from_status, to_status)
                self.assertEqual(result, expected, f"Failed for {from_status} -> {to_status}")

    def test_successful_transition_with_mocked_base(self):
        """Test successful enhanced transition with all base methods mocked."""
        # Mock validation service
        mock_validation_operation = Mock(spec=ValidationOperation)
        mock_validation_operation.result = ValidationResult.SUCCESS
        mock_validation_operation.error_code = None
        mock_validation_operation.error_message = None

        # Mock base transition success
        mock_base_transition = Mock(spec=StatusTransition)
        mock_base_transition.result = TransitionResult.SUCCESS
        mock_base_transition.error = None
        mock_base_transition.rollback_attempted = False
        mock_base_transition.rollback_result = None

        # Mock commit service
        mock_commit_operation = Mock(spec=CommitOperation)
        mock_commit_operation.result = CommitResult.SUCCESS
        mock_commit_operation.commit_hash = "abc123def456"
        mock_commit_operation.commit_message = "feat: complete task (NOMAD-456)"
        mock_commit_operation.error = None

        with (
            patch.object(
                self.manager.validation_service,
                "validate_task_transition",
                return_value=mock_validation_operation,
            ),
            patch.object(self.manager, "_execute_base_transition", return_value=mock_base_transition),
            patch.object(self.manager, "_create_commit_for_transition", return_value=mock_commit_operation),
            patch.object(self.manager, "is_valid_transition", return_value=True),
        ):

            # Execute
            result = self.manager.transition_status_enhanced(
                page_id=self.test_page_id,
                from_status="in-progress",
                to_status="done",
                ticket_id=self.test_ticket_id,
                task_title=self.test_task_title,
            )

        # Verify
        self.assertIsInstance(result, EnhancedStatusTransition)
        self.assertEqual(result.result, EnhancedTransitionResult.SUCCESS)
        self.assertEqual(result.page_id, self.test_page_id)
        self.assertEqual(result.ticket_id, self.test_ticket_id)
        self.assertEqual(result.task_title, self.test_task_title)
        self.assertTrue(result.requires_commit)
        self.assertEqual(result.validation_result, ValidationResult.SUCCESS)
        self.assertEqual(result.commit_result, CommitResult.SUCCESS)
        self.assertEqual(result.commit_hash, "abc123def456")
        self.assertIsNone(result.error)

    def test_validation_failure_scenario(self):
        """Test transition when checkbox validation fails."""
        # Mock validation service failure
        mock_validation_operation = Mock(spec=ValidationOperation)
        mock_validation_operation.result = ValidationResult.FAILED
        mock_validation_operation.error_code = ValidationErrorCode.CHECKBOX_UNCHECKED
        mock_validation_operation.error_message = "Commit checkbox is not checked"

        with (
            patch.object(
                self.manager.validation_service,
                "validate_task_transition",
                return_value=mock_validation_operation,
            ),
            patch.object(self.manager, "is_valid_transition", return_value=True),
        ):

            # Execute
            result = self.manager.transition_status_enhanced(
                page_id=self.test_page_id,
                from_status="in-progress",
                to_status="done",
                ticket_id=self.test_ticket_id,
            )

        # Verify
        self.assertEqual(result.result, EnhancedTransitionResult.CHECKBOX_VALIDATION_FAILED)
        self.assertEqual(result.validation_result, ValidationResult.FAILED)
        self.assertEqual(result.validation_error_code, ValidationErrorCode.CHECKBOX_UNCHECKED)
        self.assertEqual(result.error, "Commit checkbox is not checked")
        self.assertIsNone(result.commit_operation)

    def test_transition_without_commit_requirement(self):
        """Test transition that doesn't require commit."""
        # Mock successful base transition
        mock_base_transition = Mock(spec=StatusTransition)
        mock_base_transition.result = TransitionResult.SUCCESS
        mock_base_transition.error = None
        mock_base_transition.rollback_attempted = False

        with (
            patch.object(self.manager, "_execute_base_transition", return_value=mock_base_transition),
            patch.object(self.manager, "_requires_commit", return_value=False),
            patch.object(self.manager, "is_valid_transition", return_value=True),
        ):

            result = self.manager.transition_status_enhanced(page_id=self.test_page_id, from_status="todo", to_status="in-progress")

        # Verify
        self.assertEqual(result.result, EnhancedTransitionResult.SUCCESS)
        self.assertFalse(result.requires_commit)
        self.assertIsNone(result.validation_operation)
        self.assertIsNone(result.commit_operation)

    def test_commit_failure_with_rollback(self):
        """Test commit failure with rollback functionality."""
        # Mock successful validation and base transition
        mock_validation_operation = Mock(spec=ValidationOperation)
        mock_validation_operation.result = ValidationResult.SUCCESS

        mock_base_transition = Mock(spec=StatusTransition)
        mock_base_transition.result = TransitionResult.SUCCESS
        mock_base_transition.error = None
        mock_base_transition.rollback_attempted = False

        # Mock commit failure
        mock_commit_operation = Mock(spec=CommitOperation)
        mock_commit_operation.result = CommitResult.FAILED
        mock_commit_operation.error = "Git commit failed"
        mock_commit_operation.commit_hash = None
        mock_commit_operation.commit_message = "failed commit message"

        with (
            patch.object(
                self.manager.validation_service,
                "validate_task_transition",
                return_value=mock_validation_operation,
            ),
            patch.object(self.manager, "_execute_base_transition", return_value=mock_base_transition),
            patch.object(self.manager, "_create_commit_for_transition", return_value=mock_commit_operation),
            patch.object(self.manager, "_rollback_status_transition", return_value=True),
            patch.object(self.manager, "is_valid_transition", return_value=True),
            patch.object(self.manager, "_requires_commit", return_value=True),
        ):

            result = self.manager.transition_status_enhanced(
                page_id=self.test_page_id,
                from_status="in-progress",
                to_status="done",
                ticket_id=self.test_ticket_id,
            )

        # Verify
        self.assertEqual(result.result, EnhancedTransitionResult.ROLLBACK_SUCCESS)
        self.assertTrue(result.rollback_attempted)
        self.assertIn("status_transition", result.rollback_operations)
        self.assertEqual(result.commit_result, CommitResult.FAILED)

    def test_enhanced_statistics_calculation(self):
        """Test enhanced statistics calculation."""
        # Manually add some mock transitions to the history
        transitions = [
            (EnhancedTransitionResult.SUCCESS, ValidationResult.SUCCESS, CommitResult.SUCCESS),
            (EnhancedTransitionResult.SUCCESS, ValidationResult.SUCCESS, CommitResult.SUCCESS),
            (EnhancedTransitionResult.CHECKBOX_VALIDATION_FAILED, ValidationResult.FAILED, None),
            (EnhancedTransitionResult.COMMIT_FAILED, ValidationResult.SUCCESS, CommitResult.FAILED),
            (
                EnhancedTransitionResult.ROLLBACK_SUCCESS,
                ValidationResult.SUCCESS,
                CommitResult.FAILED,
            ),
        ]

        for result, validation, commit in transitions:
            transition = EnhancedStatusTransition(
                page_id="test",
                from_status="in-progress",
                to_status="done",
                timestamp=datetime.now(),
            )
            transition.result = result

            if validation:
                mock_validation = Mock()
                mock_validation.result = validation
                transition.validation_operation = mock_validation

            if commit:
                mock_commit = Mock()
                mock_commit.result = commit
                transition.commit_operation = mock_commit

            self.manager._enhanced_transition_history.append(transition)

        # Get statistics
        stats = self.manager.get_enhanced_statistics()

        # Verify
        self.assertEqual(stats["enhanced_transitions"], 5)
        self.assertEqual(stats["enhanced_success_rate"], 40.0)  # 2/5 * 100
        self.assertEqual(stats["validation_failed"], 1)
        self.assertEqual(stats["commit_failed"], 1)
        self.assertEqual(stats["rollback_successful"], 1)
        self.assertEqual(stats["total_validations"], 5)
        self.assertEqual(stats["total_commits"], 4)
        self.assertTrue(stats["services_enabled"]["validation"])
        self.assertTrue(stats["services_enabled"]["commits"])

    def test_service_configuration_methods(self):
        """Test service configuration enable/disable methods."""
        # Test validation configuration
        self.assertTrue(self.manager.is_validation_enabled())
        self.manager.configure_validation(False)
        self.assertFalse(self.manager.is_validation_enabled())

        # Test commits configuration
        self.assertTrue(self.manager.is_commit_enabled())
        self.manager.configure_commits(False)
        self.assertFalse(self.manager.is_commit_enabled())

    def test_enhanced_transition_history_tracking(self):
        """Test that enhanced transitions are tracked in history."""
        # Mock successful base transition
        mock_base_transition = Mock(spec=StatusTransition)
        mock_base_transition.result = TransitionResult.SUCCESS
        mock_base_transition.error = None
        mock_base_transition.rollback_attempted = False

        with (
            patch.object(self.manager, "_execute_base_transition", return_value=mock_base_transition),
            patch.object(self.manager, "_requires_commit", return_value=False),
            patch.object(self.manager, "is_valid_transition", return_value=True),
        ):

            # Execute multiple transitions
            for i in range(3):
                self.manager.transition_status_enhanced(page_id=f"page_{i}", from_status="todo", to_status="in-progress")

        # Verify history
        history = self.manager.get_enhanced_transition_history()
        self.assertEqual(len(history), 3)

        # Test filtering by page_id
        filtered_history = self.manager.get_enhanced_transition_history(page_id="page_1")
        self.assertEqual(len(filtered_history), 1)
        self.assertEqual(filtered_history[0].page_id, "page_1")


class TestEnhancedStatusTransition(unittest.TestCase):
    """Test cases for EnhancedStatusTransition dataclass."""

    def test_enhanced_transition_creation(self):
        """Test creation of enhanced status transition."""
        transition = EnhancedStatusTransition(
            page_id="test-page-123",
            from_status="in-progress",
            to_status="done",
            timestamp=datetime.now(),
            ticket_id="NOMAD-456",
            task_title="Test task",
            requires_commit=True,
        )

        self.assertEqual(transition.page_id, "test-page-123")
        self.assertEqual(transition.from_status, "in-progress")
        self.assertEqual(transition.to_status, "done")
        self.assertEqual(transition.ticket_id, "NOMAD-456")
        self.assertEqual(transition.task_title, "Test task")
        self.assertTrue(transition.requires_commit)
        self.assertFalse(transition.rollback_attempted)
        self.assertEqual(len(transition.rollback_operations), 0)

    def test_enhanced_transition_defaults(self):
        """Test default values for enhanced transition."""
        transition = EnhancedStatusTransition(
            page_id="test-page",
            from_status="todo",
            to_status="in-progress",
            timestamp=datetime.now(),
        )

        self.assertIsNone(transition.validation_operation)
        self.assertIsNone(transition.validation_result)
        self.assertIsNone(transition.validation_error_code)
        self.assertIsNone(transition.commit_operation)
        self.assertIsNone(transition.commit_result)
        self.assertIsNone(transition.commit_hash)
        self.assertIsNone(transition.commit_message)
        self.assertIsNone(transition.ticket_id)
        self.assertIsNone(transition.task_title)
        self.assertFalse(transition.requires_commit)
        self.assertFalse(transition.rollback_attempted)
        self.assertEqual(len(transition.rollback_operations), 0)


if __name__ == "__main__":
    unittest.main()
