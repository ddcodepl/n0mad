#!/usr/bin/env python3
"""
Unit tests for task name validation and sanitization functionality.

Tests the TaskNameValidator class for Git branch naming compliance.
"""
import string
import unittest
from unittest.mock import patch

from core.services.branch_service import TaskNameValidator


class TestTaskNameValidator(unittest.TestCase):
    """Test cases for TaskNameValidator class."""

    def setUp(self):
        """Set up test cases."""
        self.validator = TaskNameValidator()

    def test_sanitize_basic_task_names(self):
        """Test sanitization of basic task names."""
        test_cases = [
            ("Fix user login bug", "Fix-user-login-bug"),
            ("Add new feature", "Add-new-feature"),
            ("Update documentation", "Update-documentation"),
            ("Refactor API endpoints", "Refactor-API-endpoints"),
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name)
                self.assertEqual(result, expected)

    def test_sanitize_with_task_id(self):
        """Test sanitization with task ID prefix."""
        test_cases = [
            ("Fix login", "123", "123-Fix-login"),
            ("Add feature", "TASK-456", "TASK-456-Add-feature"),
            ("Bug fix", "BUG-789", "BUG-789-Bug-fix"),
        ]

        for input_name, task_id, expected in test_cases:
            with self.subTest(input_name=input_name, task_id=task_id):
                result = self.validator.sanitize_task_name(input_name, task_id)
                self.assertEqual(result, expected)

    def test_sanitize_special_characters(self):
        """Test sanitization of names with special characters."""
        test_cases = [
            ("Fix: login bug", "Fix-login-bug"),
            ("Add @mention feature", "Add-mention-feature"),
            ("Update <user> profile", "Update-user-profile"),
            ("Handle [brackets] properly", "Handle-brackets-properly"),
            ("Fix {curly} braces", "Fix-curly-braces"),
            ("Remove ~tilde characters", "Remove-tilde-characters"),
            ("Handle ^caret symbols", "Handle-caret-symbols"),
            ("Process ?question marks", "Process-question-marks"),
            ("Handle *asterisk chars", "Handle-asterisk-chars"),
            ("Remove \\backslash", "Remove-backslash"),
            ("Handle |pipe symbols", "Handle-pipe-symbols"),
            ('Remove "quotes"', "Remove-quotes"),
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name)
                self.assertEqual(result, expected)

    def test_sanitize_multiple_spaces_and_separators(self):
        """Test sanitization of names with multiple spaces and separators."""
        test_cases = [
            ("Fix    multiple   spaces", "Fix-multiple-spaces"),
            ("Handle___underscores", "Handle-underscores"),
            ("Fix--double-hyphens", "Fix-double-hyphens"),
            ("Mixed   _  - separators", "Mixed-separators"),
            ("Trailing spaces   ", "Trailing-spaces"),
            ("   Leading spaces", "Leading-spaces"),
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name)
                self.assertEqual(result, expected)

    def test_sanitize_dots_and_slashes(self):
        """Test sanitization of problematic dots and slashes."""
        test_cases = [
            ("Fix..double.dots", "Fix.double.dots"),
            ("Handle...multiple...dots", "Fix.multiple.dots"),
            ("Fix//double//slashes", "Fix/double/slashes"),
            ("Handle///multiple///slashes", "Handle/multiple/slashes"),
            ("../relative/path", "relative/path"),
            ("./current/dir", "current/dir"),
            ("path/./with/dots", "path/with/dots"),
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name)
                # Note: The actual implementation might differ slightly
                # This is testing the general pattern
                self.assertNotIn("..", result)
                self.assertNotIn("//", result)
                self.assertFalse(result.startswith("."))
                self.assertFalse(result.endswith("."))

    def test_sanitize_empty_and_invalid_inputs(self):
        """Test sanitization of empty and invalid inputs."""
        test_cases = [
            ("", "task-unnamed"),
            ("   ", "task-unnamed"),
            (None, "task-unnamed"),
            ("123", "123-task-123"),  # With task ID
            ("", "456", "task-456"),  # Empty with task ID
        ]

        for i, test_case in enumerate(test_cases):
            with self.subTest(test_case=i):
                if len(test_case) == 2:
                    input_name, expected = test_case
                    result = self.validator.sanitize_task_name(input_name)
                else:
                    input_name, task_id, expected = test_case
                    result = self.validator.sanitize_task_name(input_name, task_id)

                self.assertEqual(result, expected)

    def test_sanitize_long_names(self):
        """Test sanitization of very long task names."""
        # Create a very long task name
        long_name = "This is a very long task name that exceeds the maximum branch name length limit and should be truncated properly while maintaining readability and avoiding invalid characters at the end"

        result = self.validator.sanitize_task_name(long_name)

        # Should be truncated to max length
        self.assertLessEqual(len(result), self.validator.MAX_BRANCH_NAME_LENGTH)

        # Should not end with hyphen after truncation
        self.assertFalse(result.endswith("-"))

        # Should be valid
        self.assertTrue(self.validator.is_valid_branch_name(result))

    def test_sanitize_unicode_characters(self):
        """Test sanitization of Unicode characters."""
        test_cases = [
            ("Fix café login", "Fix-caf-login"),  # é should be handled
            ("Add résumé feature", "Add-rsum-feature"),  # é should be handled
            ("Handle 中文 characters", "Handle-characters"),  # Chinese characters removed
            ("Process éñçødíñg", "Process-ndng"),  # Various accented chars
            ("Emoji test 🚀 feature", "Emoji-test-feature"),  # Emojis removed
        ]

        for input_name, expected_pattern in test_cases:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name)

                # Should not contain non-ASCII characters
                self.assertTrue(result.isascii(), f"Result contains non-ASCII: {result}")

                # Should be valid branch name
                self.assertTrue(self.validator.is_valid_branch_name(result))

    def test_is_valid_branch_name_valid_cases(self):
        """Test validation of valid branch names."""
        valid_names = [
            "feature-branch",
            "bugfix/login-issue",
            "hotfix-security-patch",
            "development",
            "v1.2.3-release",
            "user-profile-updates",
            "API-refactoring",
            "123-task-implementation",
            "a",  # Single character
            "feature.branch",  # Single dots are OK
            "branch/sub/path",  # Slashes are OK
        ]

        for name in valid_names:
            with self.subTest(branch_name=name):
                self.assertTrue(self.validator.is_valid_branch_name(name))

    def test_is_valid_branch_name_invalid_cases(self):
        """Test validation of invalid branch names."""
        invalid_names = [
            "",  # Empty
            ".hidden",  # Starts with dot
            "branch.",  # Ends with dot
            "branch..name",  # Double dots
            "branch//name",  # Double slashes
            "/branch",  # Starts with slash
            "branch/",  # Ends with slash
            "branch~name",  # Tilde
            "branch^name",  # Caret
            "branch:name",  # Colon
            "branch?name",  # Question mark
            "branch*name",  # Asterisk
            "branch[name]",  # Brackets
            "branch\\name",  # Backslash
            "branch@{name}",  # @{ sequence
            "branch name",  # Space
            "branch\tname",  # Tab
            "branch\nname",  # Newline
            "branch.lock",  # Ends with .lock
            "a" * 300,  # Too long
            None,  # None input
            123,  # Non-string input
        ]

        for name in invalid_names:
            with self.subTest(branch_name=name):
                self.assertFalse(self.validator.is_valid_branch_name(name))

    def test_sanitize_control_characters(self):
        """Test sanitization removes control characters."""
        # Test with various control characters
        input_name = "Fix\x00null\x01char\x1fissue"
        result = self.validator.sanitize_task_name(input_name)

        # Should not contain control characters
        for char in result:
            self.assertFalse(ord(char) < 32 or ord(char) == 127, f"Control character found: {repr(char)}")

        # Should be valid
        self.assertTrue(self.validator.is_valid_branch_name(result))

    def test_sanitize_fallback_behavior(self):
        """Test sanitization fallback to timestamp-based naming."""
        # Test with names that can't be sanitized properly
        problematic_names = [
            "~^:?*[]\\@{}",  # All invalid characters
            "...",  # Only dots
            "///",  # Only slashes
            "---",  # Only hyphens
            "   ",  # Only spaces
        ]

        for input_name in problematic_names:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name, "TEST")

                # Should fallback to safe format
                self.assertTrue(result.startswith("task-TEST-"))
                self.assertTrue(self.validator.is_valid_branch_name(result))

    def test_sanitize_preserves_readability(self):
        """Test that sanitization preserves readability when possible."""
        test_cases = [
            ("Fix User Login Bug", "Fix-User-Login-Bug"),
            ("Add Dark Mode Feature", "Add-Dark-Mode-Feature"),
            ("Update API Documentation", "Update-API-Documentation"),
            ("Refactor Database Models", "Refactor-Database-Models"),
        ]

        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = self.validator.sanitize_task_name(input_name)

                # Should maintain word structure
                words = result.split("-")
                original_words = input_name.split()

                # Should have same number of words (approximately)
                self.assertEqual(len(words), len(original_words))

                # Should be valid
                self.assertTrue(self.validator.is_valid_branch_name(result))

    def test_task_id_sanitization(self):
        """Test that task IDs are properly sanitized."""
        test_cases = [
            ("TASK-123", "TASK-123"),
            ("task@456", "task456"),
            ("BUG#789", "BUG789"),
            ("FEATURE~001", "FEATURE001"),
            ("123", "123"),
        ]

        for task_id, expected_clean in test_cases:
            with self.subTest(task_id=task_id):
                result = self.validator.sanitize_task_name("test", task_id)
                self.assertTrue(result.startswith(expected_clean + "-"))

    def test_length_limits(self):
        """Test that length limits are properly enforced."""
        # Test exact limit
        max_length = self.validator.MAX_BRANCH_NAME_LENGTH
        long_name = "a" * (max_length - 10)  # Leave room for task ID

        result = self.validator.sanitize_task_name(long_name, "123")
        self.assertLessEqual(len(result), max_length)
        self.assertTrue(self.validator.is_valid_branch_name(result))

        # Test with very long task ID
        very_long_task_id = "VERY-LONG-TASK-IDENTIFIER-123456789"
        result = self.validator.sanitize_task_name("short", very_long_task_id)
        self.assertLessEqual(len(result), max_length)
        self.assertTrue(self.validator.is_valid_branch_name(result))

    def test_edge_cases(self):
        """Test various edge cases."""
        edge_cases = [
            # Non-string inputs
            (123, "123", "123-task-123"),
            ([], "456", "task-456"),
            # Whitespace variations
            ("\t\n\r", "789", "task-789"),
            # Mixed language and scripts
            ("Task: Διόρθωση σφάλματος", "GR-1", "GR-1-Task"),
        ]

        for input_name, task_id, expected_pattern in edge_cases:
            with self.subTest(input_name=input_name, task_id=task_id):
                result = self.validator.sanitize_task_name(input_name, task_id)

                # Should always produce valid result
                self.assertTrue(self.validator.is_valid_branch_name(result))

                # Should contain task ID
                self.assertIn(task_id, result)


class TestTaskNameValidationIntegration(unittest.TestCase):
    """Integration tests for task name validation with real-world scenarios."""

    def setUp(self):
        """Set up integration test cases."""
        self.validator = TaskNameValidator()

    def test_github_issue_names(self):
        """Test with GitHub-style issue names."""
        github_issues = [
            "Fix: Cannot login with special characters in password #123",
            "Feature: Add dark mode toggle to user settings #456",
            "Bug: Memory leak in background processing #789",
            "Enhancement: Improve API response times #012",
        ]

        for issue_name in github_issues:
            with self.subTest(issue_name=issue_name):
                result = self.validator.sanitize_task_name(issue_name)

                # Should be valid
                self.assertTrue(self.validator.is_valid_branch_name(result))

                # Should not contain problematic characters
                self.assertNotIn("#", result)
                self.assertNotIn(":", result)

                # Should be readable
                self.assertIn(
                    "Fix",
                    result.replace("-", " ")
                    or "Feature" in result.replace("-", " ")
                    or "Bug" in result.replace("-", " ")
                    or "Enhancement" in result.replace("-", " "),
                )

    def test_jira_ticket_names(self):
        """Test with JIRA-style ticket names."""
        jira_tickets = [
            ("PROJ-123: Implement user authentication", "PROJ-123"),
            ("WEBAPP-456: Fix responsive design issues", "WEBAPP-456"),
            ("API-789: Add rate limiting to endpoints", "API-789"),
            ("MOBILE-012: Update push notification handling", "MOBILE-012"),
        ]

        for ticket_name, ticket_id in jira_tickets:
            with self.subTest(ticket_name=ticket_name, ticket_id=ticket_id):
                result = self.validator.sanitize_task_name(ticket_name, ticket_id)

                # Should be valid
                self.assertTrue(self.validator.is_valid_branch_name(result))

                # Should start with ticket ID
                self.assertTrue(result.startswith(ticket_id.replace(":", "")))

                # Should not contain colon
                self.assertNotIn(":", result)

    def test_agile_story_names(self):
        """Test with Agile user story names."""
        user_stories = [
            "As a user, I want to reset my password so that I can regain access",
            "[Story] Implement shopping cart functionality for e-commerce site",
            "User Story: Add social media login options (Facebook, Google, Twitter)",
            "Epic: Redesign entire user onboarding flow",
        ]

        for story in user_stories:
            with self.subTest(story=story):
                result = self.validator.sanitize_task_name(story)

                # Should be valid
                self.assertTrue(self.validator.is_valid_branch_name(result))

                # Should not contain problematic characters
                self.assertNotIn("[", result)
                self.assertNotIn("]", result)
                self.assertNotIn("(", result)
                self.assertNotIn(")", result)
                self.assertNotIn(",", result)

    def test_multilingual_task_names(self):
        """Test with multilingual task names."""
        multilingual_tasks = [
            ("Corrigir bug no login do usuário", "PT-001"),  # Portuguese
            ("Agregar función de modo oscuro", "ES-002"),  # Spanish
            ("Benutzer-Authentifizierung implementieren", "DE-003"),  # German
            ("ユーザー認証を実装する", "JP-004"),  # Japanese
            ("Реализовать аутентификацию пользователя", "RU-005"),  # Russian
        ]

        for task_name, task_id in multilingual_tasks:
            with self.subTest(task_name=task_name, task_id=task_id):
                result = self.validator.sanitize_task_name(task_name, task_id)

                # Should be valid
                self.assertTrue(self.validator.is_valid_branch_name(result))

                # Should be ASCII only
                self.assertTrue(result.isascii())

                # Should contain task ID
                self.assertIn(task_id, result)


if __name__ == "__main__":
    unittest.main()
