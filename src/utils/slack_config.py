#!/usr/bin/env python3
"""
Slack Configuration Management

Handles configuration for Slack integration including tokens, channels,
and notification preferences with proper security controls.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MessagePriority(str, Enum):
    """Message priority levels for Slack notifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class SlackChannelConfig:
    """Configuration for a specific Slack channel."""

    name: str
    id: str
    enabled: bool = True
    priorities: List[MessagePriority] = None

    def __post_init__(self):
        if self.priorities is None:
            self.priorities = list(MessagePriority)


@dataclass
class SlackConfig:
    """
    Configuration for Slack integration.

    Handles secure token management, channel routing, and notification preferences.
    """

    bot_token: str
    app_token: Optional[str] = None
    default_channel: str = "#general"
    error_channel: str = "#errors"
    enabled: bool = True
    rate_limit_per_minute: int = 60
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 30

    # Channel configurations
    channels: Dict[str, SlackChannelConfig] = None

    def __post_init__(self):
        if self.channels is None:
            self.channels = {}

        # Validate required configuration
        if not self.bot_token:
            raise ValueError("Slack bot token is required")

        if not self.bot_token.startswith("xoxb-"):
            logger.warning("⚠️ Bot token doesn't follow expected format (xoxb-)")

        if self.app_token and not self.app_token.startswith("xapp-"):
            logger.warning("⚠️ App token doesn't follow expected format (xapp-)")

    @classmethod
    def from_environment(cls) -> "SlackConfig":
        """
        Create SlackConfig from environment variables.

        Environment variables:
          SLACK_BOT_TOKEN - Required Slack bot token
          SLACK_APP_TOKEN - Optional Slack app token
          SLACK_DEFAULT_CHANNEL - Default channel for notifications
          SLACK_ERROR_CHANNEL - Channel for error notifications
          SLACK_NOTIFICATIONS_ENABLED - Enable/disable notifications
          SLACK_RATE_LIMIT_PER_MINUTE - Rate limiting
          SLACK_RETRY_ATTEMPTS - Number of retry attempts
          SLACK_RETRY_DELAY - Delay between retries in seconds
          SLACK_TIMEOUT - Request timeout in seconds

        Returns:
            SlackConfig instance

        Raises:
            ValueError: If required configuration is missing
        """
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")

        return cls(
            bot_token=bot_token,
            app_token=os.getenv("SLACK_APP_TOKEN"),
            default_channel=os.getenv("SLACK_DEFAULT_CHANNEL", "#general"),
            error_channel=os.getenv("SLACK_ERROR_CHANNEL", "#errors"),
            enabled=os.getenv("SLACK_NOTIFICATIONS_ENABLED", "true").lower() == "true",
            rate_limit_per_minute=int(os.getenv("SLACK_RATE_LIMIT_PER_MINUTE", "60")),
            retry_attempts=int(os.getenv("SLACK_RETRY_ATTEMPTS", "3")),
            retry_delay_seconds=int(os.getenv("SLACK_RETRY_DELAY", "5")),
            timeout_seconds=int(os.getenv("SLACK_TIMEOUT", "30")),
        )

    def get_channel_for_priority(self, priority: MessagePriority) -> str:
        """
        Get the appropriate channel for a message priority.

        Args:
            priority: Message priority level

        Returns:
            Channel name to use
        """
        # Check if any configured channels handle this priority
        for channel_name, channel_config in self.channels.items():
            if channel_config.enabled and priority in channel_config.priorities:
                return channel_name

        # Use error channel for urgent messages if available
        if priority == MessagePriority.URGENT and self.error_channel:
            return self.error_channel

        # Fall back to default channel
        return self.default_channel

    def add_channel_config(
        self,
        channel_name: str,
        channel_id: str,
        priorities: List[MessagePriority] = None,
        enabled: bool = True,
    ):
        """
        Add configuration for a specific channel.

        Args:
            channel_name: Channel name (e.g., "#general")
            channel_id: Slack channel ID
            priorities: List of priorities this channel handles
            enabled: Whether this channel is enabled
        """
        self.channels[channel_name] = SlackChannelConfig(
            name=channel_name,
            id=channel_id,
            enabled=enabled,
            priorities=priorities or list(MessagePriority),
        )

        logger.info(f"📝 Added Slack channel config: {channel_name} ({channel_id})")

    def is_enabled(self) -> bool:
        """Check if Slack notifications are enabled."""
        return self.enabled and bool(self.bot_token)

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the current configuration.

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check required fields
        if not self.bot_token:
            issues.append("Missing bot token")
        elif not self.bot_token.startswith("xoxb-"):
            warnings.append("Bot token format may be incorrect")

        if self.app_token and not self.app_token.startswith("xapp-"):
            warnings.append("App token format may be incorrect")

        # Check channel configurations
        if not self.default_channel:
            issues.append("Default channel not configured")

        if not self.error_channel:
            warnings.append("Error channel not configured")

        # Check rate limiting
        if self.rate_limit_per_minute <= 0:
            issues.append("Rate limit must be positive")

        if self.retry_attempts < 0:
            issues.append("Retry attempts cannot be negative")

        if self.retry_delay_seconds <= 0:
            warnings.append("Retry delay should be positive")

        if self.timeout_seconds <= 0:
            issues.append("Timeout must be positive")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "enabled": self.is_enabled(),
        }

    def get_masked_config(self) -> Dict[str, Any]:
        """
        Get configuration with sensitive data masked for logging.

        Returns:
            Dictionary with masked sensitive values
        """
        return {
            "bot_token": f"{self.bot_token[:8]}..." if self.bot_token else None,
            "app_token": f"{self.app_token[:8]}..." if self.app_token else None,
            "default_channel": self.default_channel,
            "error_channel": self.error_channel,
            "enabled": self.enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "retry_attempts": self.retry_attempts,
            "retry_delay_seconds": self.retry_delay_seconds,
            "timeout_seconds": self.timeout_seconds,
            "channels_configured": len(self.channels),
        }


class SlackConfigManager:
    """
    Manager for Slack configuration with caching and validation.
    """

    def __init__(self):
        self._config: Optional[SlackConfig] = None
        self._config_loaded = False

    def get_config(self, force_reload: bool = False) -> SlackConfig:
        """
        Get Slack configuration, loading from environment if needed.

        Args:
            force_reload: Force reload from environment

        Returns:
            SlackConfig instance

        Raises:
            ValueError: If configuration is invalid
        """
        if not self._config_loaded or force_reload:
            try:
                self._config = SlackConfig.from_environment()
                self._config_loaded = True

                # Validate configuration
                validation = self._config.validate_configuration()

                if not validation["valid"]:
                    logger.error("❌ Slack configuration validation failed:")
                    for issue in validation["issues"]:
                        logger.error(f"   • {issue}")
                    raise ValueError(f"Invalid Slack configuration: {validation['issues']}")

                if validation["warnings"]:
                    logger.warning("⚠️ Slack configuration warnings:")
                    for warning in validation["warnings"]:
                        logger.warning(f"   • {warning}")

                masked_config = self._config.get_masked_config()
                logger.info(f"🔧 Slack configuration loaded: {masked_config}")

            except Exception as e:
                logger.error(f"❌ Failed to load Slack configuration: {e}")
                # Create disabled config as fallback
                self._config = SlackConfig(bot_token="", enabled=False)
                self._config_loaded = True

        return self._config

    def is_configured(self) -> bool:
        """Check if Slack is properly configured."""
        try:
            config = self.get_config()
            return config.is_enabled()
        except Exception:
            return False

    def reload_config(self) -> SlackConfig:
        """Force reload configuration from environment."""
        return self.get_config(force_reload=True)


# Global configuration manager instance
_slack_config_manager = SlackConfigManager()


def get_slack_config(force_reload: bool = False) -> SlackConfig:
    """
    Get global Slack configuration.

    Args:
        force_reload: Force reload from environment

    Returns:
        SlackConfig instance
    """
    return _slack_config_manager.get_config(force_reload)


def is_slack_configured() -> bool:
    """Check if Slack integration is properly configured."""
    return _slack_config_manager.is_configured()
