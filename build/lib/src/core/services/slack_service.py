#!/usr/bin/env python3
"""
Slack API Integration Service

Provides abstracted Slack API client with proper error handling,
authentication, and message formatting for task status notifications.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_SDK_AVAILABLE = True
except ImportError:
    WebClient = None
    SlackApiError = Exception
    SLACK_SDK_AVAILABLE = False

from src.utils.logging_config import get_logger
from src.utils.slack_config import MessagePriority, SlackConfig, get_slack_config

# Import security manager (with fallback if not available)
try:
    from src.utils.slack_security import get_slack_security_manager

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

logger = get_logger(__name__)


class SlackMessageResult(str, Enum):
    """Result status for Slack message operations."""

    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    DISABLED = "disabled"
    SDK_UNAVAILABLE = "sdk_unavailable"


@dataclass
class SlackMessage:
    """
    Represents a Slack message to be sent.
    """

    channel: str
    text: str
    blocks: Optional[List[Dict[str, Any]]] = None
    priority: MessagePriority = MessagePriority.MEDIUM
    timestamp: datetime = None
    retry_count: int = 0

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class SlackMessageOperation:
    """
    Represents a Slack message operation with results.
    """

    operation_id: str
    message: SlackMessage
    result: SlackMessageResult
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None
    retry_after: Optional[int] = None

    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.result == SlackMessageResult.SUCCESS

    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if the operation can be retried."""
        return self.message.retry_count < max_retries and self.result in [
            SlackMessageResult.FAILED,
            SlackMessageResult.RATE_LIMITED,
        ]


class SlackApiClient:
    """
    Abstracted Slack API client with error handling and retry mechanisms.

    Provides methods for sending messages, handling rate limits, and managing
    authentication with proper error recovery.
    """

    def __init__(self, config: Optional[SlackConfig] = None):
        """
        Initialize the Slack API client.

        Args:
            config: Optional SlackConfig instance. If None, loads from environment.
        """
        self.config = config or get_slack_config()
        self._client: Optional[WebClient] = None
        self._last_request_time = 0
        self._rate_limit_reset_time = 0

        # Initialize security manager
        self._security_manager = None
        if SECURITY_AVAILABLE:
            try:
                self._security_manager = get_slack_security_manager()
                logger.debug("🔒 Security manager initialized for Slack client")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize security manager: {e}")

        # Initialize client if SDK is available and config is valid
        if SLACK_SDK_AVAILABLE and self.config.is_enabled():
            try:
                self._client = WebClient(token=self.config.bot_token, timeout=self.config.timeout_seconds)
                logger.info("🔧 Slack API client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Slack client: {e}")
                self._client = None
        elif not SLACK_SDK_AVAILABLE:
            logger.warning("⚠️ Slack SDK not available - install with: pip install slack-sdk")
        elif not self.config.is_enabled():
            logger.info("ℹ️ Slack notifications are disabled")

    def is_available(self) -> bool:
        """Check if Slack client is available and configured."""
        return SLACK_SDK_AVAILABLE and self.config.is_enabled() and self._client is not None

    def send_message(self, message: SlackMessage) -> SlackMessageOperation:
        """
        Send a message to Slack with error handling and retry logic.

        Args:
            message: SlackMessage to send

        Returns:
            SlackMessageOperation with results
        """
        operation_id = f"slack_msg_{int(time.time())}_{message.retry_count}"

        operation = SlackMessageOperation(operation_id=operation_id, message=message, result=SlackMessageResult.FAILED)

        # Check if client is available
        if not self.is_available():
            if not SLACK_SDK_AVAILABLE:
                operation.result = SlackMessageResult.SDK_UNAVAILABLE
                operation.error = "Slack SDK not available"
            elif not self.config.is_enabled():
                operation.result = SlackMessageResult.DISABLED
                operation.error = "Slack notifications disabled"
            else:
                operation.error = "Slack client not initialized"

            logger.debug(f"🚫 Slack message not sent: {operation.error}")
            return operation

        try:
            # Check rate limiting
            if self._is_rate_limited():
                operation.result = SlackMessageResult.RATE_LIMITED
                operation.error = "Rate limited"
                operation.retry_after = max(1, self._rate_limit_reset_time - int(time.time()))
                logger.warning(f"⏱️ Slack rate limited, retry after {operation.retry_after}s")
                return operation

            # Apply rate limiting
            self._apply_rate_limit()

            # Prepare message payload
            payload = {"channel": message.channel, "text": message.text}

            # Add blocks if provided
            if message.blocks:
                payload["blocks"] = message.blocks

            # Send message
            logger.info(f"📤 Sending Slack message to {message.channel}")
            response = self._client.chat_postMessage(**payload)

            # Check response
            if response.get("ok"):
                operation.result = SlackMessageResult.SUCCESS
                operation.response = response.data
                operation.delivered_at = datetime.now()
                logger.info(f"✅ Slack message sent successfully to {message.channel}")

                # Log successful interaction
                if self._security_manager:
                    self._security_manager.log_slack_interaction(
                        action="send_message",
                        channel=message.channel,
                        success=True,
                        message_id=response.get("ts"),
                        metadata={
                            "priority": message.priority.value,
                            "blocks_count": len(message.blocks) if message.blocks else 0,
                        },
                    )
            else:
                operation.result = SlackMessageResult.FAILED
                operation.error = response.get("error", "Unknown error")
                logger.error(f"❌ Slack message failed: {operation.error}")

                # Log failed interaction
                if self._security_manager:
                    self._security_manager.log_slack_interaction(
                        action="send_message",
                        channel=message.channel,
                        success=False,
                        error_message=operation.error,
                        metadata={"priority": message.priority.value},
                    )

        except SlackApiError as e:
            operation.result = SlackMessageResult.FAILED
            operation.error = str(e)

            # Handle specific Slack API errors
            if e.response.get("error") == "rate_limited":
                operation.result = SlackMessageResult.RATE_LIMITED
                # Extract retry_after if provided
                retry_after = e.response.get("headers", {}).get("retry-after")
                if retry_after:
                    operation.retry_after = int(retry_after)
                    self._rate_limit_reset_time = int(time.time()) + operation.retry_after

                logger.warning(f"⏱️ Slack API rate limited: {e}")
            else:
                logger.error(f"❌ Slack API error: {e}")

        except Exception as e:
            operation.result = SlackMessageResult.FAILED
            operation.error = str(e)
            logger.error(f"❌ Unexpected error sending Slack message: {e}")

        return operation

    def send_message_with_retry(self, message: SlackMessage) -> SlackMessageOperation:
        """
        Send a message with automatic retry logic.

        Args:
            message: SlackMessage to send

        Returns:
            SlackMessageOperation with final results
        """
        max_retries = self.config.retry_attempts
        operation = None

        for attempt in range(max_retries + 1):
            message.retry_count = attempt
            operation = self.send_message(message)

            if operation.is_success():
                break

            if not operation.can_retry(max_retries):
                break

            # Wait before retry
            if operation.retry_after:
                sleep_time = operation.retry_after
            else:
                sleep_time = self.config.retry_delay_seconds * (2**attempt)  # Exponential backoff

            logger.info(f"🔄 Retrying Slack message in {sleep_time}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(sleep_time)

        if operation and not operation.is_success():
            logger.error(f"❌ Failed to send Slack message after {max_retries} retries: {operation.error}")

        return operation

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Slack connection and return status information.

        Returns:
            Dictionary with connection test results
        """
        result = {"available": False, "authenticated": False, "bot_info": None, "error": None}

        if not self.is_available():
            result["error"] = "Client not available"
            return result

        result["available"] = True

        try:
            # Test authentication
            auth_response = self._client.auth_test()

            if auth_response.get("ok"):
                result["authenticated"] = True
                result["bot_info"] = {
                    "user": auth_response.get("user"),
                    "team": auth_response.get("team"),
                    "url": auth_response.get("url"),
                }
                logger.info("✅ Slack connection test successful")
            else:
                result["error"] = auth_response.get("error", "Authentication failed")
                logger.error(f"❌ Slack authentication failed: {result['error']}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"❌ Slack connection test failed: {e}")

        return result

    def _is_rate_limited(self) -> bool:
        """Check if we're currently rate limited."""
        return time.time() < self._rate_limit_reset_time

    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        min_interval = 60.0 / self.config.rate_limit_per_minute

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def get_channel_info(self, channel: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a Slack channel.

        Args:
            channel: Channel name or ID

        Returns:
            Channel information dictionary or None if not found
        """
        if not self.is_available():
            return None

        try:
            response = self._client.conversations_info(channel=channel)
            if response.get("ok"):
                return response.get("channel")
        except Exception as e:
            logger.debug(f"Could not get channel info for {channel}: {e}")

        return None

    def validate_channel(self, channel: str) -> bool:
        """
        Validate that a channel exists and is accessible.

        Args:
            channel: Channel name or ID

        Returns:
            True if channel is valid and accessible
        """
        channel_info = self.get_channel_info(channel)
        return channel_info is not None

    def get_client_info(self) -> Dict[str, Any]:
        """
        Get information about the current client configuration.

        Returns:
            Dictionary with client information
        """
        return {
            "sdk_available": SLACK_SDK_AVAILABLE,
            "client_initialized": self._client is not None,
            "config_enabled": self.config.is_enabled(),
            "rate_limit_per_minute": self.config.rate_limit_per_minute,
            "retry_attempts": self.config.retry_attempts,
            "timeout_seconds": self.config.timeout_seconds,
            "default_channel": self.config.default_channel,
            "error_channel": self.config.error_channel,
        }
