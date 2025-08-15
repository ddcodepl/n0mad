#!/usr/bin/env python3
"""
Unit tests for CommitMessageGenerator

Tests message generation, type detection, optimization, and validation.
"""
import unittest

from core.services.commit_message_service import CommitMessageGenerator, CommitType, CommitValidationResult, TaskCommitData


class TestCommitMessageGenerator(unittest.TestCase):
    """Test cases for CommitMessageGenerator."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.generator = CommitMessageGenerator()

        # Sample test data
        self.basic_task_data = TaskCommitData(
            ticket_id="NOMAD-123",
            task_title="Implement user authentication system",
            task_description="Add JWT-based authentication with login/logout functionality",
            completion_summary="Added authentication service with JWT tokens",
        )

        self.fix_task_data = TaskCommitData(
            ticket_id="NOMAD-456",
            task_title="Fix login validation bug",
            task_description="Resolve issue where empty passwords were accepted",
            completion_summary="Fixed password validation to reject empty values",
        )

        self.docs_task_data = TaskCommitData(
            ticket_id="NOMAD-789",
            task_title="Update API documentation",
            task_description="Add examples and improve endpoint descriptions",
            completion_summary="Updated REST API docs with examples",
        )

    def test_generate_basic_commit_message(self):
        """Test basic commit message generation."""
        message = self.generator.generate_commit_message(self.basic_task_data)

        # Should follow conventional commits format
        self.assertRegex(
            message,
            r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|wip)(\(.+\))?!?:",
        )

        # Should include ticket number
        self.assertIn("NOMAD-123", message)

        # Should be within length limits
        self.assertLessEqual(len(message), self.generator.max_subject_length)

        # Should start with feat for new functionality
        self.assertTrue(message.startswith("feat"))

    def test_commit_type_detection_feat(self):
        """Test automatic detection of feature commits."""
        detected_type = self.generator._detect_commit_type(self.basic_task_data)
        self.assertEqual(detected_type, CommitType.FEAT)

    def test_commit_type_detection_fix(self):
        """Test automatic detection of fix commits."""
        detected_type = self.generator._detect_commit_type(self.fix_task_data)
        self.assertEqual(detected_type, CommitType.FIX)

    def test_commit_type_detection_docs(self):
        """Test automatic detection of docs commits."""
        detected_type = self.generator._detect_commit_type(self.docs_task_data)
        self.assertEqual(detected_type, CommitType.DOCS)

    def test_scope_extraction_from_ticket_id(self):
        """Test scope extraction from ticket ID patterns."""
        task_with_scope = TaskCommitData(ticket_id="NOMAD-AUTH-123", task_title="Add login functionality")

        scope = self.generator._extract_scope(task_with_scope)
        self.assertEqual(scope, "auth")

    def test_scope_extraction_from_changed_files(self):
        """Test scope extraction from changed files."""
        task_with_files = TaskCommitData(
            ticket_id="NOMAD-123",
            task_title="Update auth service",
            changed_files=["src/auth/login.py", "src/auth/tokens.py", "tests/auth/test_login.py"],
        )

        scope = self.generator._extract_scope(task_with_files)
        self.assertEqual(scope, "auth")

    def test_scope_extraction_from_title(self):
        """Test scope extraction from task title keywords."""
        test_cases = [
            ("Add API endpoint for users", "api"),
            ("Fix database connection issue", "db"),
            ("Update UI component styling", "ui"),
            ("Improve test coverage", "test"),
            ("Update configuration settings", "config"),
        ]

        for title, expected_scope in test_cases:
            with self.subTest(title=title):
                task_data = TaskCommitData(ticket_id="TEST-123", task_title=title)
                scope = self.generator._extract_scope(task_data)
                self.assertEqual(scope, expected_scope)

    def test_description_cleaning(self):
        """Test description cleaning and normalization."""
        test_cases = [
            # (raw_description, ticket_id, expected_cleaned)
            (
                "NOMAD-123: Implement user authentication",
                "NOMAD-123",
                "implement user authentication",
            ),
            ("Task: Add login functionality", "NOMAD-456", "add login functionality"),
            ("Feature: Enhanced search capabilities", "NOMAD-789", "enhanced search capabilities"),
            ("  Multiple   spaces   cleaned  ", "TEST-1", "multiple spaces cleaned"),
        ]

        for raw_desc, ticket_id, expected in test_cases:
            with self.subTest(raw_desc=raw_desc):
                cleaned = self.generator._clean_description(raw_desc, ticket_id)
                self.assertEqual(cleaned, expected)

    def test_description_optimization_for_length(self):
        """Test description optimization when it's too long."""
        long_task = TaskCommitData(
            ticket_id="NOMAD-123",
            task_title="Implement a very comprehensive user authentication and authorization system with JWT tokens, refresh tokens, role-based access control, and password reset functionality",
            task_description="This is a complex implementation",
        )

        message = self.generator.generate_commit_message(long_task)

        # Should be within length limits
        self.assertLessEqual(len(message), self.generator.max_subject_length)

        # Should still contain essential information
        self.assertIn("NOMAD-123", message)
        self.assertTrue(message.startswith("feat"))

    def test_word_replacements(self):
        """Test that word replacements work for common terms."""
        task_with_long_words = TaskCommitData(
            ticket_id="NOMAD-123",
            task_title="Add authentication implementation for database configuration management",
        )

        description = self.generator._generate_description(task_with_long_words, CommitType.FEAT)
        optimized = self.generator._optimize_description(description, CommitType.FEAT, None, "NOMAD-123")

        # Should contain abbreviated forms
        self.assertIn("auth", optimized)
        self.assertIn("config", optimized)
        self.assertIn("db", optimized)

    def test_custom_commit_type_override(self):
        """Test that custom commit type overrides detection."""
        message = self.generator.generate_commit_message(self.basic_task_data, commit_type=CommitType.CHORE)

        self.assertTrue(message.startswith("chore"))

    def test_custom_scope_override(self):
        """Test that custom scope overrides detection."""
        message = self.generator.generate_commit_message(self.basic_task_data, custom_scope="custom")

        self.assertIn("(custom)", message)

    def test_breaking_change_indication(self):
        """Test breaking change indication in commit message."""
        breaking_task = TaskCommitData(
            ticket_id="NOMAD-123",
            task_title="Remove deprecated API endpoints",
            is_breaking_change=True,
        )

        message = self.generator.generate_commit_message(breaking_task)

        # Should include breaking change indicator
        self.assertIn("!", message)
        self.assertRegex(message, r"^[a-z]+(\(.+\))?!:")

    def test_batch_message_generation(self):
        """Test generating messages for multiple tasks."""
        tasks = [self.basic_task_data, self.fix_task_data, self.docs_task_data]

        results = self.generator.generate_batch_messages(tasks)

        self.assertEqual(len(results), 3)

        # Check each result is a tuple of (ticket_id, message)
        for ticket_id, message in results:
            self.assertIsInstance(ticket_id, str)
            self.assertIsInstance(message, str)
            self.assertIn(ticket_id, message)

    def test_commit_message_validation_valid(self):
        """Test validation of a valid commit message."""
        valid_message = "feat(auth): add JWT authentication (NOMAD-123)"

        result = self.generator.validate_custom_message(valid_message)

        self.assertIsInstance(result, CommitValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_commit_message_validation_too_long(self):
        """Test validation of an overly long commit message."""
        long_message = "feat: " + "x" * 100 + " (NOMAD-123)"

        result = self.generator.validate_custom_message(long_message)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("too long", result.errors[0])

    def test_commit_message_validation_invalid_format(self):
        """Test validation of commit message with invalid format."""
        invalid_message = "just some random commit message"

        result = self.generator.validate_custom_message(invalid_message)

        # Should have warnings about format
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("conventional commits", result.warnings[0])

    def test_fallback_message_generation(self):
        """Test fallback message generation when main generation fails."""
        # Test with minimal data
        minimal_task = TaskCommitData(ticket_id="NOMAD-999", task_title="Simple task")

        fallback = self.generator._generate_fallback_message(minimal_task)

        self.assertIn("NOMAD-999", fallback)
        self.assertTrue(fallback.startswith("feat:"))
        self.assertLessEqual(len(fallback), self.generator.max_subject_length)

    def test_redundant_word_removal(self):
        """Test removal of redundant words for conciseness."""
        redundant_description = "Add the very comprehensive authentication system for all the users"

        cleaned = self.generator._remove_redundant_words(redundant_description)

        # Should remove redundant words while keeping meaning
        self.assertNotIn(" the ", cleaned)
        self.assertNotIn(" very ", cleaned)
        self.assertNotIn(" all ", cleaned)
        self.assertIn("authentication", cleaned)
        self.assertIn("system", cleaned)

    def test_aggressive_abbreviations(self):
        """Test aggressive abbreviation application."""
        long_description = "implementation of authentication service with parameter validation"

        abbreviated = self.generator._apply_aggressive_abbreviations(long_description)

        # Should contain abbreviated forms
        self.assertIn("impl", abbreviated)
        self.assertIn("auth", abbreviated)
        self.assertIn("svc", abbreviated)
        self.assertIn("param", abbreviated)

    def test_supported_types_method(self):
        """Test that all supported commit types are returned."""
        supported_types = self.generator.get_supported_types()

        self.assertIsInstance(supported_types, list)
        self.assertIn(CommitType.FEAT, supported_types)
        self.assertIn(CommitType.FIX, supported_types)
        self.assertIn(CommitType.DOCS, supported_types)
        self.assertEqual(len(supported_types), len(CommitType))

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        # Empty title
        empty_task = TaskCommitData(ticket_id="NOMAD-123", task_title="")
        message = self.generator.generate_commit_message(empty_task)
        self.assertIsNotNone(message)
        self.assertIn("NOMAD-123", message)

        # Very short title
        short_task = TaskCommitData(ticket_id="NOMAD-456", task_title="Fix")
        message = self.generator.generate_commit_message(short_task)
        self.assertIsNotNone(message)
        self.assertIn("fix", message.lower())

        # Unicode characters
        unicode_task = TaskCommitData(ticket_id="NOMAD-789", task_title="Add émoji support for users")
        message = self.generator.generate_commit_message(unicode_task)
        self.assertIsNotNone(message)
        self.assertIn("NOMAD-789", message)


class TestCommitValidationResult(unittest.TestCase):
    """Test cases for CommitValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creation of validation results."""
        result = CommitValidationResult(is_valid=True, errors=[], warnings=["Minor formatting issue"])

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0], "Minor formatting issue")


class TestTaskCommitData(unittest.TestCase):
    """Test cases for TaskCommitData dataclass."""

    def test_task_commit_data_creation(self):
        """Test creation of task commit data."""
        task_data = TaskCommitData(
            ticket_id="TEST-123",
            task_title="Test task",
            task_description="Test description",
            changed_files=["file1.py", "file2.py"],
            is_breaking_change=True,
        )

        self.assertEqual(task_data.ticket_id, "TEST-123")
        self.assertEqual(task_data.task_title, "Test task")
        self.assertEqual(task_data.task_description, "Test description")
        self.assertEqual(len(task_data.changed_files), 2)
        self.assertTrue(task_data.is_breaking_change)

    def test_task_commit_data_defaults(self):
        """Test default values for optional fields."""
        task_data = TaskCommitData(ticket_id="TEST-456", task_title="Minimal task")

        self.assertIsNone(task_data.task_description)
        self.assertIsNone(task_data.completion_summary)
        self.assertIsNone(task_data.changed_files)
        self.assertFalse(task_data.is_breaking_change)


if __name__ == "__main__":
    unittest.main()
