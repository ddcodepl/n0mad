#!/usr/bin/env python3
"""
Unit tests for TaskStatusValidationService

Tests validation logic, caching, error handling, and integration patterns.
"""
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

from core.services.task_validation_service import CheckboxCacheEntry, TaskStatusValidationService, ValidationErrorCode, ValidationOperation, ValidationResult
from utils.checkbox_utils import CheckboxFormat, CheckboxProperty


class TestTaskStatusValidationService(unittest.TestCase):
    """Test cases for TaskStatusValidationService."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_notion_client = Mock()
        self.service = TaskStatusValidationService(notion_client=self.mock_notion_client, cache_ttl_minutes=5, enabled=True)

        # Sample test data
        self.test_page_id = "12345678-1234-1234-1234-123456789012"
        self.test_ticket_id = "NOMAD-123"

        # Sample Notion page data
        self.notion_page_with_checkbox = {
            "id": self.test_page_id,
            "properties": {
                "Commit": {"type": "checkbox", "checkbox": True},
                "Status": {"type": "status", "status": {"name": "In progress"}},
                "Name": {"type": "title", "title": [{"plain_text": "Test Task"}]},
            },
        }

        self.notion_page_checkbox_unchecked = {
            "id": self.test_page_id,
            "properties": {
                "Commit": {"type": "checkbox", "checkbox": False},
                "Status": {"type": "status", "status": {"name": "In progress"}},
            },
        }

        self.notion_page_no_checkbox = {
            "id": self.test_page_id,
            "properties": {
                "Status": {"type": "status", "status": {"name": "In progress"}},
                "Name": {"type": "title", "title": [{"plain_text": "Test Task"}]},
            },
        }

    def test_validate_task_transition_success(self):
        """Test successful validation when checkbox is checked."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_with_checkbox

        # Execute
        result = self.service.validate_task_transition(
            page_id=self.test_page_id,
            from_status="In progress",
            to_status="Done",
            ticket_id=self.test_ticket_id,
        )

        # Verify
        self.assertIsInstance(result, ValidationOperation)
        self.assertEqual(result.result, ValidationResult.SUCCESS)
        self.assertTrue(result.checkbox_value)
        self.assertEqual(result.checkbox_name, "Commit")
        self.assertIsNone(result.error_code)

        # Verify API was called
        self.mock_notion_client.get_page.assert_called_once_with(self.test_page_id)

    def test_validate_task_transition_checkbox_unchecked(self):
        """Test validation failure when checkbox is unchecked."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_checkbox_unchecked

        # Execute
        result = self.service.validate_task_transition(page_id=self.test_page_id, from_status="In progress", to_status="Done")

        # Verify
        self.assertEqual(result.result, ValidationResult.CHECKBOX_UNCHECKED)
        self.assertFalse(result.checkbox_value)
        self.assertEqual(result.error_code, ValidationErrorCode.CHECKBOX_UNCHECKED)
        self.assertIn("must be checked", result.error_message)

    def test_validate_task_transition_checkbox_not_found(self):
        """Test validation when checkbox property doesn't exist."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_no_checkbox

        # Execute
        result = self.service.validate_task_transition(page_id=self.test_page_id, from_status="In progress", to_status="Done")

        # Verify
        self.assertEqual(result.result, ValidationResult.CHECKBOX_NOT_FOUND)
        self.assertEqual(result.error_code, ValidationErrorCode.CHECKBOX_NOT_FOUND)
        self.assertIn("No commit checkbox found", result.error_message)

    def test_validate_task_transition_api_error(self):
        """Test validation when Notion API throws an error."""
        # Setup
        self.mock_notion_client.get_page.side_effect = Exception("API Error")

        # Execute
        result = self.service.validate_task_transition(page_id=self.test_page_id, from_status="In progress", to_status="Done")

        # Verify
        self.assertEqual(result.result, ValidationResult.FAILED)
        self.assertEqual(result.error_code, ValidationErrorCode.NOTION_API_ERROR)
        self.assertIn("API Error", result.error_message)

    def test_validate_task_transition_disabled(self):
        """Test validation when service is disabled."""
        # Setup
        self.service.enabled = False

        # Execute
        result = self.service.validate_task_transition(page_id=self.test_page_id, from_status="In progress", to_status="Done")

        # Verify
        self.assertEqual(result.result, ValidationResult.SKIPPED)
        self.mock_notion_client.get_page.assert_not_called()

    def test_validate_task_transition_no_validation_required(self):
        """Test validation skipped for transitions that don't require it."""
        # Execute - transition that doesn't require validation
        result = self.service.validate_task_transition(page_id=self.test_page_id, from_status="Ideas", to_status="To Refine")

        # Verify
        self.assertEqual(result.result, ValidationResult.SKIPPED)
        self.mock_notion_client.get_page.assert_not_called()

    def test_requires_validation_logic(self):
        """Test the logic for determining if validation is required."""
        # Test cases that should require validation
        validation_required_cases = [
            ("In progress", "Done"),
            ("in-progress", "done"),
            ("In Progress", "Finished"),
            ("In progress", "finished"),
            ("Whatever", "done"),  # Any transition to "done"
            ("Something", "finished"),  # Any transition to "finished"
        ]

        for from_status, to_status in validation_required_cases:
            with self.subTest(from_status=from_status, to_status=to_status):
                requires = self.service._requires_validation(from_status, to_status)
                self.assertTrue(requires, f"Should require validation: {from_status} → {to_status}")

        # Test cases that should NOT require validation
        no_validation_cases = [
            ("Ideas", "To Refine"),
            ("To Refine", "Refined"),
            ("Refined", "Prepare Tasks"),
            ("In progress", "Failed"),
        ]

        for from_status, to_status in no_validation_cases:
            with self.subTest(from_status=from_status, to_status=to_status):
                requires = self.service._requires_validation(from_status, to_status)
                self.assertFalse(requires, f"Should NOT require validation: {from_status} → {to_status}")

    def test_caching_functionality(self):
        """Test checkbox validation caching."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_with_checkbox

        # First call - should hit API and cache result
        result1 = self.service._validate_commit_checkbox(self.test_page_id)
        self.assertFalse(result1["was_cached"])
        self.assertTrue(result1["success"])
        self.assertTrue(result1["checkbox_value"])

        # Second call - should use cache
        result2 = self.service._validate_commit_checkbox(self.test_page_id)
        self.assertTrue(result2["was_cached"])
        self.assertTrue(result2["success"])
        self.assertTrue(result2["checkbox_value"])

        # Verify API was only called once
        self.mock_notion_client.get_page.assert_called_once()

    def test_cache_expiration(self):
        """Test that cache entries expire after TTL."""
        # Setup with very short TTL
        self.service.cache_ttl = timedelta(milliseconds=10)
        self.mock_notion_client.get_page.return_value = self.notion_page_with_checkbox

        # First call
        result1 = self.service._validate_commit_checkbox(self.test_page_id)
        self.assertFalse(result1["was_cached"])

        # Wait for cache to expire
        time.sleep(0.02)  # 20ms

        # Second call - cache expired, should hit API again
        result2 = self.service._validate_commit_checkbox(self.test_page_id)
        self.assertFalse(result2["was_cached"])

        # Verify API was called twice
        self.assertEqual(self.mock_notion_client.get_page.call_count, 2)

    def test_multiple_checkbox_names(self):
        """Test service finds checkboxes with different names."""
        # Setup page with different checkbox name
        page_with_different_checkbox = {
            "id": self.test_page_id,
            "properties": {"Ready to commit": {"type": "checkbox", "checkbox": True}},
        }

        self.mock_notion_client.get_page.return_value = page_with_different_checkbox

        # Execute
        result = self.service._validate_commit_checkbox(self.test_page_id)

        # Verify
        self.assertTrue(result["success"])
        self.assertTrue(result["checkbox_value"])
        self.assertEqual(result["checkbox_name"], "Ready to commit")

    def test_validation_history_tracking(self):
        """Test that validation operations are tracked in history."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_with_checkbox

        # Execute multiple validations
        result1 = self.service.validate_task_transition(self.test_page_id, "In progress", "Done")
        result2 = self.service.validate_task_transition(self.test_page_id, "Ideas", "To Refine")  # Won't require validation

        # Verify history
        history = self.service.get_validation_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].result, ValidationResult.SUCCESS)
        self.assertEqual(history[1].result, ValidationResult.SKIPPED)

    def test_validation_statistics(self):
        """Test validation statistics calculation."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_with_checkbox

        # Execute some validations
        self.service.validate_task_transition(self.test_page_id, "In progress", "Done")
        self.service.validate_task_transition(self.test_page_id, "Ideas", "To Refine")

        # Get statistics
        stats = self.service.get_validation_statistics()

        # Verify
        self.assertEqual(stats["total_validations"], 2)
        self.assertEqual(stats["successful_validations"], 1)
        self.assertEqual(stats["failed_validations"], 1)
        self.assertEqual(stats["success_rate"], 50.0)
        self.assertIn("result_distribution", stats)

    def test_cache_management(self):
        """Test cache clearing and cleanup functionality."""
        # Setup
        self.mock_notion_client.get_page.return_value = self.notion_page_with_checkbox

        # Create cache entry
        self.service._validate_commit_checkbox(self.test_page_id)
        self.assertGreater(len(self.service._checkbox_cache), 0)

        # Clear cache
        cleared_count = self.service.clear_cache()
        self.assertEqual(cleared_count, 1)
        self.assertEqual(len(self.service._checkbox_cache), 0)

    def test_configuration_methods(self):
        """Test service configuration methods."""
        # Test enabled/disabled
        self.assertTrue(self.service.is_enabled())

        self.service.set_enabled(False)
        self.assertFalse(self.service.is_enabled())

        # Test checkbox configuration
        new_checkboxes = ["Custom Commit", "Ready"]
        self.service.configure_commit_checkboxes(new_checkboxes)
        self.assertEqual(self.service.commit_checkbox_names, new_checkboxes)

        # Test adding validation transitions
        self.service.add_validation_transition("Custom Status", "Custom Done")
        self.assertIn(("Custom Status", "Custom Done"), self.service.validation_required_transitions)

    def test_error_code_handling(self):
        """Test that appropriate error codes are set for different failure scenarios."""
        test_cases = [
            # (mock_setup, expected_result, expected_error_code)
            (
                lambda: setattr(
                    self.mock_notion_client,
                    "get_page",
                    Mock(return_value=self.notion_page_checkbox_unchecked),
                ),
                ValidationResult.CHECKBOX_UNCHECKED,
                ValidationErrorCode.CHECKBOX_UNCHECKED,
            ),
            (
                lambda: setattr(
                    self.mock_notion_client,
                    "get_page",
                    Mock(return_value=self.notion_page_no_checkbox),
                ),
                ValidationResult.CHECKBOX_NOT_FOUND,
                ValidationErrorCode.CHECKBOX_NOT_FOUND,
            ),
            (
                lambda: setattr(
                    self.mock_notion_client,
                    "get_page",
                    Mock(side_effect=Exception("Network error")),
                ),
                ValidationResult.FAILED,
                ValidationErrorCode.NOTION_API_ERROR,
            ),
        ]

        for mock_setup, expected_result, expected_error_code in test_cases:
            with self.subTest(expected_result=expected_result):
                # Setup
                mock_setup()

                # Execute
                result = self.service.validate_task_transition(self.test_page_id, "In progress", "Done")

                # Verify
                self.assertEqual(result.result, expected_result)
                self.assertEqual(result.error_code, expected_error_code)


class TestValidationServiceIntegration(unittest.TestCase):
    """Integration tests for validation service with actual checkbox utilities."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.mock_notion_client = Mock()
        self.service = TaskStatusValidationService(notion_client=self.mock_notion_client, cache_ttl_minutes=1, enabled=True)

    def test_checkbox_utilities_integration(self):
        """Test integration with CheckboxUtilities for complex checkbox parsing."""
        # Setup page with complex checkbox format
        complex_page = {
            "id": "test-page-id",
            "properties": {
                "commit": {"type": "checkbox", "checkbox": True},  # lowercase name
                "Other Property": {"type": "rich_text", "rich_text": [{"plain_text": "Some text"}]},
            },
        }

        self.mock_notion_client.get_page.return_value = complex_page

        # Execute
        result = self.service._validate_commit_checkbox("test-page-id")

        # Verify
        self.assertTrue(result["success"])
        self.assertTrue(result["checkbox_value"])
        self.assertEqual(result["checkbox_name"], "commit")

    def test_confidence_scoring_integration(self):
        """Test that confidence scores from checkbox parsing are handled correctly."""
        # This test would verify that confidence scores from CheckboxProperty
        # are properly integrated into the validation results

        self.mock_notion_client.get_page.return_value = {
            "id": "test-page",
            "properties": {"Commit": {"type": "checkbox", "checkbox": True}},
        }

        result = self.service._validate_commit_checkbox("test-page")

        # Should include confidence information
        self.assertIn("confidence", result)
        self.assertIsInstance(result["confidence"], float)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
