#!/usr/bin/env python3
"""
Unit tests for branch checkbox state detection functionality.

Tests the CheckboxStateDetector class and related checkbox parsing logic.
"""
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from core.services.branch_service import CheckboxStateDetector


class TestCheckboxStateDetector(unittest.TestCase):
    """Test cases for CheckboxStateDetector class."""

    def setUp(self):
        """Set up test cases."""
        self.detector = CheckboxStateDetector()

    def test_detect_branch_creation_request_with_checked_checkbox(self):
        """Test detection when branch creation checkbox is checked."""
        # Test with Notion-style checkbox
        task_data = {"properties": {"New Branch": {"type": "checkbox", "checkbox": True}}}

        result = self.detector.detect_branch_creation_request(task_data)
        self.assertTrue(result)

    def test_detect_branch_creation_request_with_unchecked_checkbox(self):
        """Test detection when branch creation checkbox is unchecked."""
        task_data = {"properties": {"New Branch": {"type": "checkbox", "checkbox": False}}}

        result = self.detector.detect_branch_creation_request(task_data)
        self.assertFalse(result)

    def test_detect_branch_creation_request_multiple_checkbox_names(self):
        """Test detection with various checkbox property names."""
        checkbox_names = ["New Branch", "Create Branch", "Branch", "new_branch", "create_branch"]

        for checkbox_name in checkbox_names:
            with self.subTest(checkbox_name=checkbox_name):
                task_data = {"properties": {checkbox_name: {"type": "checkbox", "checkbox": True}}}

                result = self.detector.detect_branch_creation_request(task_data)
                self.assertTrue(result, f"Failed to detect checkbox: {checkbox_name}")

    def test_detect_branch_creation_request_case_insensitive(self):
        """Test case-insensitive checkbox detection."""
        task_data = {"properties": {"NEW BRANCH": {"type": "checkbox", "checkbox": True}}}  # Different case

        result = self.detector.detect_branch_creation_request(task_data)
        self.assertTrue(result)

    def test_detect_branch_creation_request_no_properties(self):
        """Test detection when task has no properties."""
        task_data = {}
        result = self.detector.detect_branch_creation_request(task_data)
        self.assertFalse(result)

        # Test with None task
        result = self.detector.detect_branch_creation_request(None)
        self.assertFalse(result)

        # Test with empty properties
        task_data = {"properties": {}}
        result = self.detector.detect_branch_creation_request(task_data)
        self.assertFalse(result)

    def test_detect_branch_creation_request_invalid_task_data(self):
        """Test detection with invalid task data."""
        invalid_inputs = [None, "not a dict", 123, [], {"properties": "not a dict"}]

        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input):
                result = self.detector.detect_branch_creation_request(invalid_input)
                self.assertFalse(result)

    def test_is_checkbox_checked_various_formats(self):
        """Test checkbox validation with various property formats."""
        # Notion checkbox format
        self.assertTrue(self.detector._is_checkbox_checked({"type": "checkbox", "checkbox": True}))

        self.assertFalse(self.detector._is_checkbox_checked({"type": "checkbox", "checkbox": False}))

        # Value-based format
        self.assertTrue(self.detector._is_checkbox_checked({"value": True}))

        self.assertTrue(self.detector._is_checkbox_checked({"value": "true"}))

        self.assertTrue(self.detector._is_checkbox_checked({"value": "yes"}))

        self.assertTrue(self.detector._is_checkbox_checked({"value": "1"}))

        self.assertTrue(self.detector._is_checkbox_checked({"value": "checked"}))

        self.assertFalse(self.detector._is_checkbox_checked({"value": "false"}))

        self.assertFalse(self.detector._is_checkbox_checked({"value": "no"}))

        # Direct boolean
        self.assertTrue(self.detector._is_checkbox_checked(True))
        self.assertFalse(self.detector._is_checkbox_checked(False))

        # Invalid formats
        self.assertFalse(self.detector._is_checkbox_checked(None))
        self.assertFalse(self.detector._is_checkbox_checked("string"))
        self.assertFalse(self.detector._is_checkbox_checked(123))
        self.assertFalse(self.detector._is_checkbox_checked({}))

    def test_extract_branch_preferences_full_example(self):
        """Test extracting comprehensive branch preferences."""
        task_data = {
            "properties": {
                "New Branch": {"type": "checkbox", "checkbox": True},
                "Base Branch": {"type": "rich_text", "rich_text": [{"plain_text": "develop"}]},
                "Branch Name": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "feature-custom-name"}],
                },
            }
        }

        preferences = self.detector.extract_branch_preferences(task_data)

        expected = {
            "create_branch": True,
            "base_branch": "develop",
            "branch_name_override": "feature-custom-name",
        }

        self.assertEqual(preferences, expected)

    def test_extract_branch_preferences_minimal_example(self):
        """Test extracting branch preferences with minimal data."""
        task_data = {"properties": {"Create Branch": {"type": "checkbox", "checkbox": True}}}

        preferences = self.detector.extract_branch_preferences(task_data)

        expected = {"create_branch": True, "base_branch": None, "branch_name_override": None}

        self.assertEqual(preferences, expected)

    def test_extract_branch_preferences_no_branch_request(self):
        """Test extracting preferences when no branch is requested."""
        task_data = {"properties": {"Some Other Property": {"type": "text", "text": "value"}}}

        preferences = self.detector.extract_branch_preferences(task_data)

        expected = {"create_branch": False, "base_branch": None, "branch_name_override": None}

        self.assertEqual(preferences, expected)

    def test_extract_text_value_rich_text_format(self):
        """Test extracting text from Notion rich text format."""
        property_data = {"type": "rich_text", "rich_text": [{"plain_text": "test value"}]}

        result = self.detector._extract_text_value(property_data)
        self.assertEqual(result, "test value")

    def test_extract_text_value_title_format(self):
        """Test extracting text from Notion title format."""
        property_data = {"type": "title", "title": [{"plain_text": "title value"}]}

        result = self.detector._extract_text_value(property_data)
        self.assertEqual(result, "title value")

    def test_extract_text_value_simple_format(self):
        """Test extracting text from simple value format."""
        property_data = {"value": "simple value"}

        result = self.detector._extract_text_value(property_data)
        self.assertEqual(result, "simple value")

    def test_extract_text_value_empty_and_invalid(self):
        """Test extracting text from empty and invalid formats."""
        # Empty rich text
        result = self.detector._extract_text_value({"type": "rich_text", "rich_text": []})
        self.assertIsNone(result)

        # None input
        result = self.detector._extract_text_value(None)
        self.assertIsNone(result)

        # Invalid format
        result = self.detector._extract_text_value("not a dict")
        self.assertIsNone(result)

        # Missing fields
        result = self.detector._extract_text_value(
            {
                "type": "rich_text"
                # missing rich_text field
            }
        )
        self.assertIsNone(result)

    def test_extract_text_value_whitespace_handling(self):
        """Test that extracted text values handle whitespace correctly."""
        property_data = {"value": "  text with spaces  "}

        result = self.detector._extract_text_value(property_data)
        self.assertEqual(result, "text with spaces")

    @patch("core.services.branch_service.logger")
    def test_logging_on_detection(self, mock_logger):
        """Test that appropriate logging occurs during detection."""
        task_data = {"properties": {"New Branch": {"type": "checkbox", "checkbox": True}}}

        result = self.detector.detect_branch_creation_request(task_data)

        self.assertTrue(result)
        mock_logger.info.assert_called_with("✅ Branch creation requested via 'New Branch' checkbox")

    def test_checkbox_property_names_coverage(self):
        """Test that all defined checkbox property names work correctly."""
        for prop_name in self.detector.CHECKBOX_PROPERTY_NAMES:
            with self.subTest(property_name=prop_name):
                task_data = {"properties": {prop_name: {"type": "checkbox", "checkbox": True}}}

                result = self.detector.detect_branch_creation_request(task_data)
                self.assertTrue(result, f"Property name not detected: {prop_name}")


class TestCheckboxIntegration(unittest.TestCase):
    """Integration tests for checkbox detection with real-world scenarios."""

    def setUp(self):
        """Set up integration test cases."""
        self.detector = CheckboxStateDetector()

    def test_notion_page_format_simulation(self):
        """Test with simulated Notion page format."""
        # Simulates a real Notion page with various properties
        notion_page = {
            "id": "page-123",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": "Implement user authentication"},
                            "plain_text": "Implement user authentication",
                        }
                    ],
                },
                "Status": {"type": "status", "status": {"name": "In Progress", "color": "blue"}},
                "New Branch": {"type": "checkbox", "checkbox": True},
                "Priority": {"type": "select", "select": {"name": "High", "color": "red"}},
                "Base Branch": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "text": {"content": "develop"}, "plain_text": "develop"}],
                },
            },
        }

        # Test detection
        branch_requested = self.detector.detect_branch_creation_request(notion_page)
        self.assertTrue(branch_requested)

        # Test preferences extraction
        preferences = self.detector.extract_branch_preferences(notion_page)
        expected_preferences = {
            "create_branch": True,
            "base_branch": "develop",
            "branch_name_override": None,
        }
        self.assertEqual(preferences, expected_preferences)

    def test_taskmaster_task_format_simulation(self):
        """Test with simulated Task Master task format."""
        taskmaster_task = {
            "id": 123,
            "title": "Add dark mode support",
            "description": "Implement dark mode toggle functionality",
            "priority": "high",
            "status": "pending",
            "properties": {
                "create_branch": {"value": True},
                "base_branch": {"value": "main"},
                "custom_branch": {"value": "feature-dark-mode"},
            },
        }

        # Test detection
        branch_requested = self.detector.detect_branch_creation_request(taskmaster_task)
        self.assertTrue(branch_requested)

        # Test preferences extraction
        preferences = self.detector.extract_branch_preferences(taskmaster_task)
        expected_preferences = {
            "create_branch": True,
            "base_branch": "main",
            "branch_name_override": "feature-dark-mode",
        }
        self.assertEqual(preferences, expected_preferences)

    def test_mixed_format_handling(self):
        """Test handling of mixed property formats in a single task."""
        mixed_task = {
            "properties": {
                # Notion-style checkbox
                "New Branch": {"type": "checkbox", "checkbox": True},
                # Simple value style
                "base_branch": {"value": "staging"},
                # Rich text style
                "Branch Name": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "hotfix-security-patch"}],
                },
            }
        }

        preferences = self.detector.extract_branch_preferences(mixed_task)
        expected_preferences = {
            "create_branch": True,
            "base_branch": "staging",
            "branch_name_override": "hotfix-security-patch",
        }
        self.assertEqual(preferences, expected_preferences)


if __name__ == "__main__":
    unittest.main()
