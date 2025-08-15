#!/usr/bin/env python3
"""
Slack Security Utilities

Provides security controls and data protection measures for Slack integration
including data sanitization, input validation, and audit logging.
"""

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SensitiveDataType(str, Enum):
    """Types of sensitive data that need sanitization."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    API_KEY = "api_key"
    TOKEN = "token"
    PASSWORD = "password"
    IP_ADDRESS = "ip_address"
    URL = "url"


@dataclass
class AuditLogEntry:
    """
    Audit log entry for Slack API interactions.
    """

    timestamp: datetime
    action: str
    user_id: Optional[str]
    channel: str
    message_id: Optional[str]
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DataSanitizer:
    """
    Handles sanitization of sensitive data in notification content.

    Provides methods to detect and sanitize various types of sensitive
    information before sending to Slack.
    """

    def __init__(self):
        """Initialize the data sanitizer with regex patterns."""
        # Regex patterns for detecting sensitive data
        self.patterns = {
            SensitiveDataType.EMAIL: re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", re.IGNORECASE),
            SensitiveDataType.PHONE: re.compile(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"),
            SensitiveDataType.SSN: re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
            SensitiveDataType.CREDIT_CARD: re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
            SensitiveDataType.API_KEY: re.compile(
                r'\b(?:api[_-]?key|access[_-]?token|secret[_-]?key)["\s]*[:=]["\s]*[A-Za-z0-9+/=]{20,}\b',
                re.IGNORECASE,
            ),
            SensitiveDataType.TOKEN: re.compile(r"\b(?:bearer\s+)?[A-Za-z0-9+/=]{32,}\b", re.IGNORECASE),
            SensitiveDataType.PASSWORD: re.compile(r'\bpassword["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE),
            SensitiveDataType.IP_ADDRESS: re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
            SensitiveDataType.URL: re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE),
        }

        # Replacement patterns
        self.replacements = {
            SensitiveDataType.EMAIL: "[EMAIL_REDACTED]",
            SensitiveDataType.PHONE: "[PHONE_REDACTED]",
            SensitiveDataType.SSN: "[SSN_REDACTED]",
            SensitiveDataType.CREDIT_CARD: "[CARD_REDACTED]",
            SensitiveDataType.API_KEY: "[API_KEY_REDACTED]",
            SensitiveDataType.TOKEN: "[TOKEN_REDACTED]",
            SensitiveDataType.PASSWORD: "[PASSWORD_REDACTED]",
            SensitiveDataType.IP_ADDRESS: "[IP_REDACTED]",
            SensitiveDataType.URL: "[URL_REDACTED]",
        }

        # Configuration for what to sanitize
        self.enabled_sanitization = {
            SensitiveDataType.EMAIL: False,  # Usually OK to show emails
            SensitiveDataType.PHONE: True,
            SensitiveDataType.SSN: True,
            SensitiveDataType.CREDIT_CARD: True,
            SensitiveDataType.API_KEY: True,
            SensitiveDataType.TOKEN: True,
            SensitiveDataType.PASSWORD: True,
            SensitiveDataType.IP_ADDRESS: True,
            SensitiveDataType.URL: False,  # URLs are usually OK to show
        }

    def sanitize_text(self, text: str, sensitive_types: Optional[Set[SensitiveDataType]] = None) -> str:
        """
        Sanitize sensitive data from text content.

        Args:
            text: Text to sanitize
            sensitive_types: Specific types to sanitize (None = use defaults)

        Returns:
            Sanitized text with sensitive data replaced
        """
        if not text:
            return text

        sanitized_text = text
        types_to_check = sensitive_types or set(self.enabled_sanitization.keys())

        for data_type in types_to_check:
            if self.enabled_sanitization.get(data_type, True):
                pattern = self.patterns.get(data_type)
                replacement = self.replacements.get(data_type, "[REDACTED]")

                if pattern:
                    sanitized_text = pattern.sub(replacement, sanitized_text)

        return sanitized_text

    def sanitize_dict(self, data: Dict[str, Any], sensitive_keys: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        Sanitize sensitive data from dictionary values.

        Args:
            data: Dictionary to sanitize
            sensitive_keys: Keys that contain sensitive data

        Returns:
            Dictionary with sanitized values
        """
        if not data:
            return data

        sensitive_keys = sensitive_keys or {
            "password",
            "token",
            "api_key",
            "secret",
            "auth",
            "credential",
            "private_key",
            "passphrase",
        }

        sanitized_data = {}

        for key, value in data.items():
            key_lower = key.lower()

            # Check if key is known to be sensitive
            if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                sanitized_data[key] = "[REDACTED]"
            elif isinstance(value, str):
                sanitized_data[key] = self.sanitize_text(value)
            elif isinstance(value, dict):
                sanitized_data[key] = self.sanitize_dict(value, sensitive_keys)
            elif isinstance(value, list):
                sanitized_data[key] = [self.sanitize_text(item) if isinstance(item, str) else item for item in value]
            else:
                sanitized_data[key] = value

        return sanitized_data

    def configure_sanitization(self, data_type: SensitiveDataType, enabled: bool):
        """
        Configure whether a specific data type should be sanitized.

        Args:
            data_type: Type of sensitive data
            enabled: Whether to sanitize this type
        """
        self.enabled_sanitization[data_type] = enabled
        logger.info(f"🔧 Sanitization for {data_type.value}: {'enabled' if enabled else 'disabled'}")


class InputValidator:
    """
    Validates input data for security and format requirements.
    """

    def __init__(self):
        """Initialize the input validator."""
        self.max_lengths = {
            "task_title": 200,
            "task_description": 1000,
            "channel_name": 50,
            "user_id": 50,
            "ticket_id": 50,
            "message_text": 4000,  # Slack limit
        }

    def validate_notification_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate notification data for security and format requirements.

        Args:
            data: Notification data to validate

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check required fields
        required_fields = ["task_id", "task_title", "from_status", "to_status"]
        for field in required_fields:
            if not data.get(field):
                issues.append(f"Missing required field: {field}")

        # Validate field lengths
        for field, max_length in self.max_lengths.items():
            value = data.get(field)
            if isinstance(value, str) and len(value) > max_length:
                issues.append(f"Field '{field}' exceeds maximum length of {max_length}")

        # Validate channel name format
        channel = data.get("channel")
        if channel and not self._is_valid_channel_name(channel):
            issues.append(f"Invalid channel name format: {channel}")

        # Check for suspicious content
        text_fields = ["task_title", "task_description", "message_text"]
        for field in text_fields:
            value = data.get(field)
            if isinstance(value, str):
                if self._contains_suspicious_content(value):
                    warnings.append(f"Field '{field}' contains potentially suspicious content")

        return {"valid": len(issues) == 0, "issues": issues, "warnings": warnings}

    def _is_valid_channel_name(self, channel: str) -> bool:
        """Validate Slack channel name format."""
        if not channel:
            return False

        # Slack channel names can be #channel or channel or @user
        if channel.startswith("#") or channel.startswith("@"):
            channel = channel[1:]

        # Check format: lowercase, numbers, hyphens, underscores
        return re.match(r"^[a-z0-9_-]+$", channel) is not None

    def _contains_suspicious_content(self, text: str) -> bool:
        """Check for potentially suspicious content."""
        suspicious_patterns = [
            r"<script\b",  # Script tags
            r"javascript:",  # JavaScript URLs
            r"on\w+\s*=",  # Event handlers
            r"SELECT\s+.*\s+FROM",  # SQL injection
            r"UNION\s+SELECT",  # SQL injection
            r"DROP\s+TABLE",  # SQL injection
        ]

        text_lower = text.lower()
        return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in suspicious_patterns)


class SlackAuditLogger:
    """
    Handles audit logging for Slack API interactions.
    """

    def __init__(self, max_entries: int = 10000):
        """
        Initialize the audit logger.

        Args:
            max_entries: Maximum number of audit entries to keep in memory
        """
        self.audit_log: List[AuditLogEntry] = []
        self.max_entries = max_entries
        self._entry_count = 0

    def log_slack_interaction(
        self,
        action: str,
        channel: str,
        success: bool,
        user_id: Optional[str] = None,
        message_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log a Slack API interaction.

        Args:
            action: Action performed (e.g., 'send_message', 'get_channel_info')
            channel: Target channel
            success: Whether the action was successful
            user_id: Optional user ID
            message_id: Optional message ID
            error_message: Optional error message if action failed
            metadata: Additional metadata
        """
        entry = AuditLogEntry(
            timestamp=datetime.now(),
            action=action,
            user_id=user_id,
            channel=channel,
            message_id=message_id,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
        )

        self.audit_log.append(entry)
        self._entry_count += 1

        # Keep log size manageable
        if len(self.audit_log) > self.max_entries:
            self.audit_log = self.audit_log[-self.max_entries :]

        # Log to standard logger as well
        level = "INFO" if success else "ERROR"
        message = f"Slack {action} - Channel: {channel} - Success: {success}"
        if error_message:
            message += f" - Error: {error_message}"

        if success:
            logger.info(f"🔍 {message}")
        else:
            logger.error(f"🔍 {message}")

    def get_recent_entries(self, limit: int = 100) -> List[AuditLogEntry]:
        """
        Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent audit log entries
        """
        return self.audit_log[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get audit statistics.

        Returns:
            Dictionary with audit statistics
        """
        total_entries = len(self.audit_log)
        if total_entries == 0:
            return {"total_entries": 0, "success_rate": 0.0, "actions": {}, "channels": {}}

        successful = sum(1 for entry in self.audit_log if entry.success)
        success_rate = (successful / total_entries) * 100

        # Count actions
        action_counts = {}
        for entry in self.audit_log:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1

        # Count channels
        channel_counts = {}
        for entry in self.audit_log:
            channel_counts[entry.channel] = channel_counts.get(entry.channel, 0) + 1

        return {
            "total_entries": total_entries,
            "lifetime_entries": self._entry_count,
            "success_rate": success_rate,
            "successful_interactions": successful,
            "failed_interactions": total_entries - successful,
            "actions": action_counts,
            "channels": channel_counts,
        }


class SlackSecurityManager:
    """
    Comprehensive security manager for Slack integration.

    Combines data sanitization, input validation, and audit logging
    into a unified security management system.
    """

    def __init__(self):
        """Initialize the security manager."""
        self.sanitizer = DataSanitizer()
        self.validator = InputValidator()
        self.audit_logger = SlackAuditLogger()

        logger.info("🔒 Slack security manager initialized")

    def secure_notification_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply security measures to notification data.

        Args:
            data: Raw notification data

        Returns:
            Dictionary with secured data and validation results
        """
        # Validate input
        validation = self.validator.validate_notification_data(data)

        if not validation["valid"]:
            logger.warning(f"⚠️ Notification data validation failed: {validation['issues']}")
            return {"data": data, "validation": validation, "sanitized": False, "secure": False}

        # Sanitize sensitive data
        sanitized_data = self.sanitizer.sanitize_dict(data)

        # Hash sensitive IDs for logging
        secure_data = sanitized_data.copy()
        if "task_id" in secure_data:
            secure_data["task_id_hash"] = self._hash_id(secure_data["task_id"])

        return {"data": sanitized_data, "validation": validation, "sanitized": True, "secure": True}

    def log_slack_interaction(self, **kwargs):
        """Log Slack interaction with security context."""
        self.audit_logger.log_slack_interaction(**kwargs)

    def get_security_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive security statistics.

        Returns:
            Dictionary with security statistics
        """
        audit_stats = self.audit_logger.get_statistics()

        return {
            "audit_logging": audit_stats,
            "sanitization_enabled": self.sanitizer.enabled_sanitization,
            "validation_max_lengths": self.validator.max_lengths,
        }

    def _hash_id(self, task_id: str) -> str:
        """Create a secure hash of a task ID for logging."""
        return hashlib.sha256(task_id.encode()).hexdigest()[:16]


# Global security manager instance
_security_manager = None


def get_slack_security_manager() -> SlackSecurityManager:
    """Get the global Slack security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SlackSecurityManager()
    return _security_manager
