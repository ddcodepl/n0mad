#!/usr/bin/env python3
"""
Slack Integration Test Configuration

Provides test configuration and utilities for Slack integration testing.
"""

import os
from typing import Any, Dict
from unittest.mock import Mock


class SlackTestConfig:
    """Test configuration for Slack integration tests."""

    # Test environment variables
    TEST_ENV_VARS = {
        "SLACK_BOT_TOKEN": "xoxb-test-token-123456789",
        "SLACK_APP_TOKEN": "xapp-test-token-123456789",
        "SLACK_DEFAULT_CHANNEL": "#test-general",
        "SLACK_ERROR_CHANNEL": "#test-errors",
        "SLACK_NOTIFICATIONS_ENABLED": "true",
        "SLACK_RATE_LIMIT_PER_MINUTE": "60",
        "SLACK_RETRY_ATTEMPTS": "3",
        "SLACK_RETRY_DELAY": "1",
        "SLACK_TIMEOUT": "10",
    }

    # Mock Slack API responses
    MOCK_RESPONSES = {
        "successful_message": {
            "ok": True,
            "channel": "C1234567890",
            "ts": "1234567890.123456",
            "message": {
                "type": "message",
                "subtype": None,
                "text": "Test message",
                "ts": "1234567890.123456",
            },
        },
        "failed_message_channel_not_found": {"ok": False, "error": "channel_not_found"},
        "failed_message_rate_limited": {
            "ok": False,
            "error": "rate_limited",
            "headers": {"retry-after": "30"},
        },
        "successful_auth_test": {
            "ok": True,
            "url": "https://test-workspace.slack.com/",
            "team": "Test Workspace",
            "user": "testbot",
            "team_id": "T1234567890",
            "user_id": "U1234567890",
            "bot_id": "B1234567890",
        },
        "failed_auth_test": {"ok": False, "error": "invalid_auth"},
        "channel_info": {
            "ok": True,
            "channel": {
                "id": "C1234567890",
                "name": "test-general",
                "is_channel": True,
                "is_group": False,
                "is_im": False,
                "created": 1234567890,
                "is_archived": False,
                "is_general": True,
                "unlinked": 0,
                "name_normalized": "test-general",
                "is_shared": False,
                "parent_conversation": None,
                "creator": "U1234567890",
                "is_ext_shared": False,
                "is_org_shared": False,
                "shared_team_ids": ["T1234567890"],
                "pending_shared": [],
                "pending_connected_team_ids": [],
                "is_pending_ext_shared": False,
                "is_member": True,
                "is_private": False,
                "is_mpim": False,
                "topic": {
                    "value": "Test channel for notifications",
                    "creator": "U1234567890",
                    "last_set": 1234567890,
                },
                "purpose": {
                    "value": "Testing Slack integration",
                    "creator": "U1234567890",
                    "last_set": 1234567890,
                },
                "num_members": 5,
            },
        },
    }

    @classmethod
    def get_test_task_data(cls) -> Dict[str, Any]:
        """Get sample task data for testing."""
        return {
            "task_id": "test-task-123",
            "task_title": "Test Task for Slack Integration",
            "task_description": "This is a test task used for validating Slack notifications",
            "from_status": "pending",
            "to_status": "in-progress",
            "user_id": "U1234567890",
            "ticket_id": "TEST-456",
            "channel": "#test-general",
            "metadata": {
                "priority": "high",
                "assignee": "testuser",
                "created_at": "2024-01-01T00:00:00Z",
            },
        }

    @classmethod
    def get_test_sensitive_data(cls) -> Dict[str, Any]:
        """Get sample data with sensitive information for sanitization testing."""
        return {
            "task_id": "test-task-456",
            "task_title": "Task with sensitive data",
            "task_description": """
                Contact the admin at admin@company.com or call 555-123-4567.
                Use API key sk-abcdef123456789 for authentication.
                The server is at 192.168.1.100.
                Password is secret123 for database access.
            """,
            "from_status": "pending",
            "to_status": "in-progress",
            "metadata": {
                "email": "user@example.com",
                "phone": "(555) 987-6543",
                "api_key": "ak-xyz789abc123def",
                "token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "credit_card": "4111-1111-1111-1111",
                "ssn": "123-45-6789",
                "ip_address": "10.0.0.1",
                "url": "https://internal.company.com/api/secret",
            },
        }

    @classmethod
    def get_test_invalid_data(cls) -> Dict[str, Any]:
        """Get invalid data for validation testing."""
        return {
            "task_id": "",  # Empty required field
            "task_title": "x" * 300,  # Too long
            "from_status": "INVALID_STATUS",
            "to_status": "ANOTHER_INVALID_STATUS",
            "channel": "Invalid Channel Name!@#",  # Invalid characters
            "metadata": {
                "suspicious_content": "<script>alert('xss')</script>",
                "sql_injection": "'; DROP TABLE tasks; --",
            },
        }

    @classmethod
    def get_mock_slack_client(cls, response_type: str = "successful_message") -> Mock:
        """
        Get a mock Slack client with predefined responses.

        Args:
            response_type: Type of response to mock

        Returns:
            Mock Slack client
        """
        mock_client = Mock()

        # Set up chat_postMessage mock
        if response_type in cls.MOCK_RESPONSES:
            mock_client.chat_postMessage.return_value = cls.MOCK_RESPONSES[response_type]
        else:
            mock_client.chat_postMessage.return_value = cls.MOCK_RESPONSES["successful_message"]

        # Set up auth_test mock
        mock_client.auth_test.return_value = cls.MOCK_RESPONSES["successful_auth_test"]

        # Set up conversations_info mock
        mock_client.conversations_info.return_value = cls.MOCK_RESPONSES["channel_info"]

        return mock_client

    @classmethod
    def setup_test_environment(cls):
        """Set up test environment variables."""
        for key, value in cls.TEST_ENV_VARS.items():
            os.environ[key] = value

    @classmethod
    def cleanup_test_environment(cls):
        """Clean up test environment variables."""
        for key in cls.TEST_ENV_VARS.keys():
            if key in os.environ:
                del os.environ[key]


class SlackTestUtilities:
    """Utility functions for Slack integration testing."""

    @staticmethod
    def assert_message_format(message: Dict[str, Any]):
        """Assert that a Slack message has the correct format."""
        assert "channel" in message
        assert "text" in message
        assert "priority" in message

        # If blocks are present, validate structure
        if "blocks" in message and message["blocks"]:
            for block in message["blocks"]:
                assert "type" in block
                assert block["type"] in ["section", "divider", "context", "header"]

    @staticmethod
    def assert_security_measures_applied(secured_data: Dict[str, Any]):
        """Assert that security measures have been properly applied."""
        assert "validation" in secured_data
        assert "sanitized" in secured_data
        assert "secure" in secured_data

        if secured_data["secure"]:
            # Check that validation passed
            assert secured_data["validation"]["valid"] is True
            assert secured_data["sanitized"] is True

    @staticmethod
    def count_redacted_fields(data: Dict[str, Any]) -> int:
        """Count the number of redacted fields in data."""
        count = 0

        def _count_redacted(obj):
            nonlocal count
            if isinstance(obj, dict):
                for value in obj.values():
                    _count_redacted(value)
            elif isinstance(obj, list):
                for item in obj:
                    _count_redacted(item)
            elif isinstance(obj, str) and "[" in obj and "REDACTED]" in obj:
                count += 1

        _count_redacted(data)
        return count

    @staticmethod
    def validate_audit_log_entry(entry) -> bool:
        """Validate that an audit log entry has the correct structure."""
        required_fields = ["timestamp", "action", "channel", "success"]

        for field in required_fields:
            if not hasattr(entry, field):
                return False

        # Validate timestamp
        if not isinstance(entry.timestamp, type(entry.timestamp)):
            return False

        # Validate success is boolean
        if not isinstance(entry.success, bool):
            return False

        return True


# Test data generators
class SlackTestDataGenerator:
    """Generates test data for various testing scenarios."""

    @staticmethod
    def generate_bulk_notifications(count: int = 100):
        """Generate bulk notifications for load testing."""
        notifications = []

        for i in range(count):
            notifications.append(
                {
                    "task_id": f"bulk-test-{i}",
                    "task_title": f"Bulk Test Task {i}",
                    "from_status": "pending" if i % 2 == 0 else "in-progress",
                    "to_status": "in-progress" if i % 2 == 0 else "done",
                    "timestamp": f"2024-01-01T{i:02d}:00:00Z",
                }
            )

        return notifications

    @staticmethod
    def generate_concurrent_notifications(threads: int = 10, per_thread: int = 10):
        """Generate notifications for concurrent testing."""
        all_notifications = []

        for thread_id in range(threads):
            thread_notifications = []
            for i in range(per_thread):
                thread_notifications.append(
                    {
                        "task_id": f"concurrent-{thread_id}-{i}",
                        "task_title": f"Concurrent Test Task {thread_id}-{i}",
                        "from_status": "pending",
                        "to_status": "in-progress",
                        "thread_id": thread_id,
                    }
                )
            all_notifications.append(thread_notifications)

        return all_notifications

    @staticmethod
    def generate_performance_test_data():
        """Generate data for performance testing."""
        return {
            "light_load": SlackTestDataGenerator.generate_bulk_notifications(10),
            "medium_load": SlackTestDataGenerator.generate_bulk_notifications(100),
            "heavy_load": SlackTestDataGenerator.generate_bulk_notifications(1000),
            "concurrent": SlackTestDataGenerator.generate_concurrent_notifications(5, 20),
        }


# Performance test configurations
PERFORMANCE_TEST_CONFIG = {
    "max_processing_time_per_notification": 0.01,  # 10ms per notification
    "max_memory_usage_mb": 100,
    "max_queue_size": 1000,
    "concurrent_threads": 10,
    "notifications_per_thread": 20,
    "load_test_duration_seconds": 30,
    "target_throughput_per_second": 100,
}


# Security test configurations
SECURITY_TEST_CONFIG = {
    "sensitive_data_patterns": [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{3}-?\d{2}-?\d{4}\b",  # SSN
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b",  # Credit card
        r'\b(?:api[_-]?key|access[_-]?token)["\s]*[:=]["\s]*[A-Za-z0-9+/=]{20,}\b',  # API keys
    ],
    "suspicious_content_patterns": [
        r"<script\b",
        r"javascript:",
        r"SELECT\s+.*\s+FROM",
        r"DROP\s+TABLE",
    ],
    "max_field_lengths": {
        "task_title": 200,
        "task_description": 1000,
        "channel_name": 50,
        "message_text": 4000,
    },
}
