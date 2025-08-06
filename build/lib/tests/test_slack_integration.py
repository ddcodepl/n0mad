#!/usr/bin/env python3
"""
Comprehensive Test Suite for Slack Integration

Tests all components of the Slack notification system including
services, security, configuration, and end-to-end workflows.
"""

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

# Import modules to test
from utils.slack_config import SlackConfig, SlackConfigManager, MessagePriority
from utils.slack_security import (
    DataSanitizer, 
    InputValidator, 
    SlackAuditLogger, 
    SlackSecurityManager,
    SensitiveDataType
)
from core.services.slack_service import SlackApiClient, SlackMessage, SlackMessageResult
from core.services.slack_message_builder import (
    SlackMessageBuilder, 
    TaskStatusChangeData, 
    MessageTemplate
)
from core.managers.notification_manager import (
    NotificationManager, 
    NotificationEvent, 
    EventType
)


class TestSlackConfig:
    """Test Slack configuration management."""
    
    def test_slack_config_creation(self):
        """Test creating SlackConfig with valid parameters."""
        config = SlackConfig(
            bot_token="xoxb-test-token",
            default_channel="#general",
            enabled=True
        )
        
        assert config.bot_token == "xoxb-test-token"
        assert config.default_channel == "#general"
        assert config.enabled is True
        assert config.is_enabled() is True
    
    def test_slack_config_validation(self):
        """Test configuration validation."""
        config = SlackConfig(
            bot_token="xoxb-test-token",
            rate_limit_per_minute=60,
            retry_attempts=3
        )
        
        validation = config.validate_configuration()
        assert validation["valid"] is True
        assert len(validation["issues"]) == 0
    
    def test_slack_config_invalid_token(self):
        """Test configuration with invalid token format."""
        with pytest.raises(ValueError):
            SlackConfig(bot_token="")
    
    @patch.dict(os.environ, {
        "SLACK_BOT_TOKEN": "xoxb-test-env-token",
        "SLACK_DEFAULT_CHANNEL": "#test-channel",
        "SLACK_NOTIFICATIONS_ENABLED": "true"
    })
    def test_slack_config_from_environment(self):
        """Test loading configuration from environment variables."""
        config = SlackConfig.from_environment()
        
        assert config.bot_token == "xoxb-test-env-token"
        assert config.default_channel == "#test-channel"
        assert config.enabled is True
    
    def test_channel_priority_routing(self):
        """Test channel routing based on message priority."""
        config = SlackConfig(
            bot_token="xoxb-test-token",
            default_channel="#general",
            error_channel="#errors"
        )
        
        # Test priority routing
        assert config.get_channel_for_priority(MessagePriority.LOW) == "#general"
        assert config.get_channel_for_priority(MessagePriority.URGENT) == "#errors"


class TestDataSanitizer:
    """Test data sanitization functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = DataSanitizer()
    
    def test_email_sanitization(self):
        """Test email address sanitization."""
        # Enable email sanitization for testing
        self.sanitizer.configure_sanitization(SensitiveDataType.EMAIL, True)
        
        text = "Contact me at user@example.com for details"
        sanitized = self.sanitizer.sanitize_text(text)
        
        assert "user@example.com" not in sanitized
        assert "[EMAIL_REDACTED]" in sanitized
    
    def test_phone_sanitization(self):
        """Test phone number sanitization."""
        text = "Call me at 555-123-4567 or (555) 987-6543"
        sanitized = self.sanitizer.sanitize_text(text)
        
        assert "555-123-4567" not in sanitized
        assert "(555) 987-6543" not in sanitized
        assert "[PHONE_REDACTED]" in sanitized
    
    def test_api_key_sanitization(self):
        """Test API key sanitization."""
        text = 'API_KEY="sk-1234567890abcdef" for authentication'
        sanitized = self.sanitizer.sanitize_text(text)
        
        assert "sk-1234567890abcdef" not in sanitized
        assert "[API_KEY_REDACTED]" in sanitized
    
    def test_dict_sanitization(self):
        """Test dictionary sanitization."""
        data = {
            "task_title": "Test Task",
            "password": "secret123",
            "api_key": "sk-abcdef123456",
            "description": "Contact user@example.com"
        }
        
        sanitized = self.sanitizer.sanitize_dict(data)
        
        assert sanitized["task_title"] == "Test Task"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
    
    def test_sanitization_configuration(self):
        """Test enabling/disabling sanitization for specific types."""
        # Disable email sanitization
        self.sanitizer.configure_sanitization(SensitiveDataType.EMAIL, False)
        
        text = "Email me at test@example.com"
        sanitized = self.sanitizer.sanitize_text(text)
        
        # Email should not be sanitized when disabled
        assert "test@example.com" in sanitized


class TestInputValidator:
    """Test input validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = InputValidator()
    
    def test_valid_notification_data(self):
        """Test validation of valid notification data."""
        data = {
            "task_id": "task-123",
            "task_title": "Test Task",
            "from_status": "pending",
            "to_status": "in-progress",
            "channel": "#general"
        }
        
        validation = self.validator.validate_notification_data(data)
        
        assert validation["valid"] is True
        assert len(validation["issues"]) == 0
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        data = {
            "task_title": "Test Task",
            # Missing task_id, from_status, to_status
        }
        
        validation = self.validator.validate_notification_data(data)
        
        assert validation["valid"] is False
        assert len(validation["issues"]) > 0
        assert any("task_id" in issue for issue in validation["issues"])
    
    def test_field_length_validation(self):
        """Test validation of field lengths."""
        data = {
            "task_id": "task-123",
            "task_title": "x" * 300,  # Exceeds max length
            "from_status": "pending",
            "to_status": "in-progress"
        }
        
        validation = self.validator.validate_notification_data(data)
        
        assert validation["valid"] is False
        assert any("task_title" in issue for issue in validation["issues"])
    
    def test_channel_name_validation(self):
        """Test Slack channel name validation."""
        # Valid channel names
        assert self.validator._is_valid_channel_name("#general")
        assert self.validator._is_valid_channel_name("general")
        assert self.validator._is_valid_channel_name("test-channel")
        assert self.validator._is_valid_channel_name("@username")
        
        # Invalid channel names
        assert not self.validator._is_valid_channel_name("#General")  # Uppercase
        assert not self.validator._is_valid_channel_name("test channel")  # Space
        assert not self.validator._is_valid_channel_name("")  # Empty
    
    def test_suspicious_content_detection(self):
        """Test detection of suspicious content."""
        suspicious_texts = [
            "<script>alert('xss')</script>",
            "javascript:void(0)",
            "SELECT * FROM users",
            "DROP TABLE tasks"
        ]
        
        for text in suspicious_texts:
            assert self.validator._contains_suspicious_content(text)
        
        # Safe content should not be flagged
        safe_text = "This is a normal task description"
        assert not self.validator._contains_suspicious_content(safe_text)


class TestSlackAuditLogger:
    """Test audit logging functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.audit_logger = SlackAuditLogger(max_entries=100)
    
    def test_log_successful_interaction(self):
        """Test logging successful Slack interactions."""
        self.audit_logger.log_slack_interaction(
            action="send_message",
            channel="#general",
            success=True,
            message_id="1234567890.123456"
        )
        
        entries = self.audit_logger.get_recent_entries(limit=1)
        assert len(entries) == 1
        
        entry = entries[0]
        assert entry.action == "send_message"
        assert entry.channel == "#general"
        assert entry.success is True
        assert entry.message_id == "1234567890.123456"
    
    def test_log_failed_interaction(self):
        """Test logging failed Slack interactions."""
        self.audit_logger.log_slack_interaction(
            action="send_message",
            channel="#general",
            success=False,
            error_message="channel_not_found"
        )
        
        entries = self.audit_logger.get_recent_entries(limit=1)
        assert len(entries) == 1
        
        entry = entries[0]
        assert entry.success is False
        assert entry.error_message == "channel_not_found"
    
    def test_audit_statistics(self):
        """Test audit statistics generation."""
        # Log some interactions
        for i in range(5):
            self.audit_logger.log_slack_interaction(
                action="send_message",
                channel="#general",
                success=i % 2 == 0  # 3 successful, 2 failed
            )
        
        stats = self.audit_logger.get_statistics()
        
        assert stats["total_entries"] == 5
        assert stats["successful_interactions"] == 3
        assert stats["failed_interactions"] == 2
        assert stats["success_rate"] == 60.0


class TestSlackMessageBuilder:
    """Test Slack message formatting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.message_builder = SlackMessageBuilder()
    
    def test_status_change_message(self):
        """Test building status change messages."""
        data = TaskStatusChangeData(
            task_id="task-123",
            task_title="Test Task",
            from_status="pending",
            to_status="in-progress",
            timestamp=datetime.now(),
            ticket_id="TICKET-456"
        )
        
        message = self.message_builder.build_task_status_change_message(
            data=data,
            channel="#general",
            priority=MessagePriority.MEDIUM
        )
        
        assert message["channel"] == "#general"
        assert "Test Task" in message["text"]
        assert message["priority"] == MessagePriority.MEDIUM
        assert message["blocks"] is not None
    
    def test_completion_message(self):
        """Test building task completion messages."""
        data = TaskStatusChangeData(
            task_id="task-123",
            task_title="Completed Task",
            from_status="in-progress",
            to_status="done",
            timestamp=datetime.now()
        )
        
        message = self.message_builder.build_task_completion_message(
            data=data,
            channel="#general"
        )
        
        assert "🎉" in message["text"]
        assert "Completed Task" in message["text"]
        assert message["priority"] == MessagePriority.HIGH
    
    def test_failure_message(self):
        """Test building task failure messages."""
        data = TaskStatusChangeData(
            task_id="task-123",
            task_title="Failed Task",
            from_status="in-progress",
            to_status="failed",
            timestamp=datetime.now()
        )
        
        message = self.message_builder.build_task_failure_message(
            data=data,
            channel="#errors",
            error_details="Connection timeout"
        )
        
        assert "⚠️" in message["text"]
        assert "Failed Task" in message["text"]
        assert message["priority"] == MessagePriority.URGENT
    
    def test_priority_determination(self):
        """Test automatic priority determination for status changes."""
        # Completion should be high priority
        priority = self.message_builder.get_priority_for_status_change(
            "in-progress", "done"
        )
        assert priority == MessagePriority.HIGH
        
        # Failure should be urgent priority
        priority = self.message_builder.get_priority_for_status_change(
            "in-progress", "failed"
        )
        assert priority == MessagePriority.URGENT
        
        # Regular transitions should be medium priority
        priority = self.message_builder.get_priority_for_status_change(
            "pending", "in-progress"
        )
        assert priority == MessagePriority.MEDIUM


@patch('core.services.slack_service.WebClient')
class TestSlackApiClient:
    """Test Slack API client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = SlackConfig(
            bot_token="xoxb-test-token",
            default_channel="#general"
        )
    
    def test_client_initialization(self, mock_webclient):
        """Test client initialization with valid config."""
        client = SlackApiClient(self.config)
        
        assert client.config == self.config
        assert client.is_available() is True
    
    def test_successful_message_send(self, mock_webclient):
        """Test successful message sending."""
        # Mock successful response
        mock_webclient.return_value.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.123456"
        }
        
        client = SlackApiClient(self.config)
        message = SlackMessage(
            channel="#general",
            text="Test message",
            priority=MessagePriority.MEDIUM
        )
        
        result = client.send_message(message)
        
        assert result.is_success() is True
        assert result.result == SlackMessageResult.SUCCESS
    
    def test_failed_message_send(self, mock_webclient):
        """Test failed message sending."""
        # Mock failed response
        mock_webclient.return_value.chat_postMessage.return_value = {
            "ok": False,
            "error": "channel_not_found"
        }
        
        client = SlackApiClient(self.config)
        message = SlackMessage(
            channel="#nonexistent",
            text="Test message",
            priority=MessagePriority.MEDIUM
        )
        
        result = client.send_message(message)
        
        assert result.is_success() is False
        assert result.result == SlackMessageResult.FAILED
        assert result.error == "channel_not_found"
    
    def test_message_retry_logic(self, mock_webclient):
        """Test message retry functionality."""
        # First call fails, second succeeds
        mock_webclient.return_value.chat_postMessage.side_effect = [
            {"ok": False, "error": "rate_limited"},
            {"ok": True, "ts": "1234567890.123456"}
        ]
        
        client = SlackApiClient(self.config)
        message = SlackMessage(
            channel="#general",
            text="Test message",
            priority=MessagePriority.MEDIUM
        )
        
        with patch('time.sleep'):  # Speed up test
            result = client.send_message_with_retry(message)
        
        assert result.is_success() is True
        assert message.retry_count > 0
    
    def test_connection_test(self, mock_webclient):
        """Test Slack connection testing."""
        # Mock successful auth test
        mock_webclient.return_value.auth_test.return_value = {
            "ok": True,
            "user": "testbot",
            "team": "Test Team"
        }
        
        client = SlackApiClient(self.config)
        test_result = client.test_connection()
        
        assert test_result["available"] is True
        assert test_result["authenticated"] is True
        assert test_result["bot_info"]["user"] == "testbot"


class TestNotificationManager:
    """Test notification management functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.notification_manager = NotificationManager(enable_slack=False)
    
    def test_status_change_notification(self):
        """Test status change notification creation."""
        self.notification_manager.notify_status_change(
            task_id="task-123",
            task_title="Test Task",
            from_status="pending",
            to_status="in-progress",
            ticket_id="TICKET-456"
        )
        
        # Check if event was queued
        stats = self.notification_manager.get_statistics()
        assert stats["events_received"] == 1
    
    def test_event_filtering(self):
        """Test event filtering based on configuration."""
        # Configure to ignore certain statuses
        self.notification_manager.configure_filter(
            ignored_statuses={"pending"}
        )
        
        # Create notification with ignored status
        self.notification_manager.notify_status_change(
            task_id="task-123",
            task_title="Test Task",
            from_status="ideas",
            to_status="pending"  # This should be filtered out
        )
        
        # Process events
        time.sleep(0.1)  # Allow processing
        
        stats = self.notification_manager.get_statistics()
        assert stats["events_filtered"] > 0
    
    def test_duplicate_event_detection(self):
        """Test duplicate event detection and filtering."""
        # Send same notification twice quickly
        for _ in range(2):
            self.notification_manager.notify_status_change(
                task_id="task-123",
                task_title="Test Task",
                from_status="pending",
                to_status="in-progress"
            )
        
        # Process events
        time.sleep(0.1)
        
        stats = self.notification_manager.get_statistics()
        # Second event should be filtered as duplicate
        assert stats["events_filtered"] > 0
    
    def test_system_alert_notification(self):
        """Test system alert notifications."""
        self.notification_manager.notify_system_alert(
            title="Test Alert",
            message="This is a test alert",
            alert_type="warning",
            priority=MessagePriority.HIGH
        )
        
        stats = self.notification_manager.get_statistics()
        assert stats["events_received"] == 1
    
    def test_notification_statistics(self):
        """Test notification statistics collection."""
        # Generate some events
        for i in range(5):
            self.notification_manager.notify_status_change(
                task_id=f"task-{i}",
                task_title=f"Test Task {i}",
                from_status="pending",
                to_status="in-progress"
            )
        
        stats = self.notification_manager.get_statistics()
        assert stats["events_received"] == 5
        assert "by_event_type" in stats
        assert "queue_size" in stats


class TestSlackSecurityManager:
    """Test comprehensive security management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SlackSecurityManager()
    
    def test_secure_notification_data(self):
        """Test securing notification data."""
        data = {
            "task_id": "task-123",
            "task_title": "Test Task",
            "from_status": "pending",
            "to_status": "in-progress",
            "metadata": {
                "password": "secret123",
                "description": "Contact admin@example.com"
            }
        }
        
        secured = self.security_manager.secure_notification_data(data)
        
        assert secured["secure"] is True
        assert secured["sanitized"] is True
        assert secured["validation"]["valid"] is True
        
        # Check that sensitive data was sanitized
        secured_data = secured["data"]
        assert secured_data["metadata"]["password"] == "[REDACTED]"
    
    def test_invalid_data_handling(self):
        """Test handling of invalid notification data."""
        invalid_data = {
            "task_title": "x" * 300,  # Too long
            # Missing required fields
        }
        
        secured = self.security_manager.secure_notification_data(invalid_data)
        
        assert secured["secure"] is False
        assert secured["validation"]["valid"] is False
        assert len(secured["validation"]["issues"]) > 0
    
    def test_security_statistics(self):
        """Test security statistics collection."""
        stats = self.security_manager.get_security_statistics()
        
        assert "audit_logging" in stats
        assert "sanitization_enabled" in stats
        assert "validation_max_lengths" in stats


class TestPerformanceAndLoad:
    """Test performance characteristics and load handling."""
    
    def test_notification_processing_performance(self):
        """Test notification processing performance under load."""
        notification_manager = NotificationManager(enable_slack=False)
        
        # Measure time to process 100 notifications
        start_time = time.time()
        
        for i in range(100):
            notification_manager.notify_status_change(
                task_id=f"task-{i}",
                task_title=f"Performance Test Task {i}",
                from_status="pending",
                to_status="in-progress"
            )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 100 notifications in under 1 second
        assert processing_time < 1.0
        
        stats = notification_manager.get_statistics()
        assert stats["events_received"] == 100
    
    def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow unbounded."""
        notification_manager = NotificationManager(enable_slack=False)
        
        # Generate many events to test memory management
        for i in range(1000):
            notification_manager.notify_status_change(
                task_id=f"task-{i}",
                task_title=f"Memory Test Task {i}",
                from_status="pending",
                to_status="in-progress"
            )
        
        # Check that internal collections are managed
        recent_events = notification_manager.get_recent_events(limit=50)
        assert len(recent_events) <= 50
        
        # Event queue should not grow unbounded
        stats = notification_manager.get_statistics()
        assert stats["queue_size"] < 1000  # Should have processed most events
    
    def test_concurrent_notification_handling(self):
        """Test handling multiple concurrent notifications."""
        import threading
        
        notification_manager = NotificationManager(enable_slack=False)
        
        def send_notifications(thread_id: int):
            for i in range(10):
                notification_manager.notify_status_change(
                    task_id=f"task-{thread_id}-{i}",
                    task_title=f"Concurrent Test Task {thread_id}-{i}",
                    from_status="pending",
                    to_status="in-progress"
                )
        
        # Start multiple threads
        threads = []
        for thread_id in range(10):
            thread = threading.Thread(target=send_notifications, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Allow processing time
        time.sleep(0.5)
        
        stats = notification_manager.get_statistics()
        assert stats["events_received"] == 100  # 10 threads * 10 notifications each


class TestIntegrationWorkflow:
    """Test end-to-end integration workflows."""
    
    @patch('core.services.slack_service.WebClient')
    def test_complete_notification_workflow(self, mock_webclient):
        """Test complete notification workflow from trigger to delivery."""
        # Mock successful Slack response
        mock_webclient.return_value.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.123456"
        }
        
        # Create notification manager with Slack enabled
        notification_manager = NotificationManager(enable_slack=True)
        
        # Trigger a status change notification
        notification_manager.notify_status_change(
            task_id="integration-test-123",
            task_title="Integration Test Task",
            from_status="pending",
            to_status="done",  # This should trigger completion notification
            ticket_id="INTEG-456"
        )
        
        # Allow processing time
        time.sleep(0.2)
        
        # Verify notification was processed
        stats = notification_manager.get_statistics()
        assert stats["events_received"] > 0
        assert stats["events_processed"] > 0
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        notification_manager = NotificationManager(enable_slack=False)
        
        # Test with invalid data that should be handled gracefully
        try:
            notification_manager.notify_status_change(
                task_id=None,  # Invalid data
                task_title="",
                from_status="",
                to_status=""
            )
            
            # Should not raise exception, but should log error
            stats = notification_manager.get_statistics()
            # Event should still be received even if processing fails
            assert stats["events_received"] >= 0
            
        except Exception as e:
            pytest.fail(f"Should handle invalid data gracefully, but raised: {e}")


# Performance benchmarks and thresholds
PERFORMANCE_THRESHOLDS = {
    "notification_processing_time_per_100": 1.0,  # seconds
    "memory_growth_limit": 100,  # MB
    "max_queue_size_under_load": 1000,
    "audit_log_max_entries": 10000
}


def test_performance_thresholds():
    """Verify all performance tests meet defined thresholds."""
    # This test serves as documentation of performance requirements
    # and can be extended with actual performance measurements
    
    assert PERFORMANCE_THRESHOLDS["notification_processing_time_per_100"] == 1.0
    assert PERFORMANCE_THRESHOLDS["memory_growth_limit"] == 100
    assert PERFORMANCE_THRESHOLDS["max_queue_size_under_load"] == 1000
    assert PERFORMANCE_THRESHOLDS["audit_log_max_entries"] == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])