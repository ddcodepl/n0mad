#!/usr/bin/env python3
"""
Notification Manager

Handles event detection and routing for task status changes,
integrating with the existing status transition system to provide
real-time notifications through various channels including Slack.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.services.slack_message_builder import MessagePriority, SlackMessageBuilder, TaskStatusChangeData
from src.core.services.slack_service import SlackApiClient, SlackMessage
from src.utils.logging_config import get_logger
from src.utils.slack_config import get_slack_config
from src.utils.task_status import TaskStatus

# Import security manager (with fallback if not available)
try:
    from utils.slack_security import get_slack_security_manager

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

logger = get_logger(__name__)


class NotificationChannel(str, Enum):
    """Available notification channels."""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"


class EventType(str, Enum):
    """Types of events that can trigger notifications."""

    TASK_STATUS_CHANGE = "task_status_change"
    TASK_COMPLETION = "task_completion"
    TASK_FAILURE = "task_failure"
    BULK_UPDATE = "bulk_update"
    SYSTEM_ALERT = "system_alert"


@dataclass
class NotificationEvent:
    """
    Represents a notification event with all necessary data.
    """

    event_id: str
    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    channels: List[NotificationChannel] = field(default_factory=list)
    priority: MessagePriority = MessagePriority.MEDIUM
    processed: bool = False
    retry_count: int = 0

    def __post_init__(self):
        if not self.channels:
            self.channels = [NotificationChannel.SLACK]


@dataclass
class NotificationFilter:
    """
    Configuration for filtering which events should trigger notifications.
    """

    enabled_statuses: Set[str] = field(default_factory=set)
    ignored_statuses: Set[str] = field(default_factory=set)
    min_priority: MessagePriority = MessagePriority.LOW
    enabled_transitions: List[tuple] = field(default_factory=list)
    ignored_transitions: List[tuple] = field(default_factory=list)
    cooldown_seconds: int = 60

    def __post_init__(self):
        # Default to all statuses if none specified
        if not self.enabled_statuses and not self.ignored_statuses:
            self.enabled_statuses = {status.value for status in TaskStatus}


class NotificationManager:
    """
    Manages event detection and notification routing for task status changes.

    Integrates with the status transition system to capture events and route
    them to appropriate notification channels with filtering and deduplication.
    """

    def __init__(self, enable_slack: bool = True):
        """
        Initialize the notification manager.

        Args:
            enable_slack: Whether to enable Slack notifications
        """
        # Threading for async processing
        self._lock = threading.RLock()
        self._event_queue = []
        self._processing_thread = None
        self._running = False

        # Event tracking for deduplication
        self._recent_events = {}  # event_key -> timestamp
        self._event_history = []
        self._max_history = 1000

        # Notification channels
        self._slack_client = None
        self._slack_message_builder = None

        if enable_slack:
            try:
                config = get_slack_config()
                if config.is_enabled():
                    self._slack_client = SlackApiClient(config)
                    self._slack_message_builder = SlackMessageBuilder()
                    logger.info("✅ Slack notifications enabled")
                else:
                    logger.info("ℹ️ Slack notifications disabled in configuration")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Slack client: {e}")

        # Filtering configuration
        self._filter = NotificationFilter()

        # Event handlers
        self._event_handlers = {
            EventType.TASK_STATUS_CHANGE: self._handle_status_change_event,
            EventType.TASK_COMPLETION: self._handle_completion_event,
            EventType.TASK_FAILURE: self._handle_failure_event,
            EventType.BULK_UPDATE: self._handle_bulk_update_event,
            EventType.SYSTEM_ALERT: self._handle_system_alert_event,
        }

        # Statistics
        self._stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_filtered": 0,
            "events_failed": 0,
            "notifications_sent": 0,
            "by_channel": defaultdict(int),
            "by_event_type": defaultdict(int),
        }

        logger.info("🔔 NotificationManager initialized")

    def start(self):
        """Start the notification processing thread."""
        with self._lock:
            if not self._running:
                self._running = True
                self._processing_thread = threading.Thread(target=self._process_events, daemon=True, name="NotificationProcessor")
                self._processing_thread.start()
                logger.info("🚀 Notification processing started")

    def stop(self):
        """Stop the notification processing thread."""
        with self._lock:
            if self._running:
                self._running = False
                if self._processing_thread:
                    self._processing_thread.join(timeout=5.0)
                logger.info("🛑 Notification processing stopped")

    def notify_status_change(
        self,
        task_id: str,
        task_title: str,
        from_status: str,
        to_status: str,
        user_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Notify about a task status change.

        Args:
            task_id: Task identifier
            task_title: Human-readable task title
            from_status: Previous status
            to_status: New status
            user_id: Optional user who made the change
            ticket_id: Optional ticket identifier
            metadata: Additional metadata
        """
        # Create event data
        event_data = {
            "task_id": task_id,
            "task_title": task_title,
            "from_status": from_status,
            "to_status": to_status,
            "user_id": user_id,
            "ticket_id": ticket_id,
            "metadata": metadata or {},
        }

        # Determine event type and priority
        event_type = EventType.TASK_STATUS_CHANGE
        priority = MessagePriority.MEDIUM

        if to_status == TaskStatus.DONE.value:
            event_type = EventType.TASK_COMPLETION
            priority = MessagePriority.HIGH
        elif to_status == TaskStatus.FAILED.value:
            event_type = EventType.TASK_FAILURE
            priority = MessagePriority.URGENT

        # Create and queue event
        event = NotificationEvent(
            event_id=f"status_{task_id}_{int(time.time())}",
            event_type=event_type,
            timestamp=datetime.now(),
            data=event_data,
            priority=priority,
        )

        self._queue_event(event)

    def notify_bulk_update(self, updates: List[Dict[str, Any]]):
        """
        Notify about bulk status updates.

        Args:
            updates: List of status update dictionaries
        """
        event = NotificationEvent(
            event_id=f"bulk_{int(time.time())}",
            event_type=EventType.BULK_UPDATE,
            timestamp=datetime.now(),
            data={"updates": updates},
            priority=MessagePriority.MEDIUM,
        )

        self._queue_event(event)

    def notify_system_alert(
        self,
        title: str,
        message: str,
        alert_type: str = "info",
        priority: MessagePriority = MessagePriority.HIGH,
    ):
        """
        Send a system alert notification.

        Args:
            title: Alert title
            message: Alert message
            alert_type: Type of alert (info, warning, error, success)
            priority: Message priority
        """
        event = NotificationEvent(
            event_id=f"alert_{int(time.time())}",
            event_type=EventType.SYSTEM_ALERT,
            timestamp=datetime.now(),
            data={"title": title, "message": message, "alert_type": alert_type},
            priority=priority,
        )

        self._queue_event(event)

    def configure_filter(
        self,
        enabled_statuses: Optional[Set[str]] = None,
        ignored_statuses: Optional[Set[str]] = None,
        min_priority: Optional[MessagePriority] = None,
        cooldown_seconds: Optional[int] = None,
    ):
        """
        Configure notification filtering.

        Args:
            enabled_statuses: Set of statuses to include
            ignored_statuses: Set of statuses to ignore
            min_priority: Minimum priority for notifications
            cooldown_seconds: Cooldown period for duplicate events
        """
        with self._lock:
            if enabled_statuses is not None:
                self._filter.enabled_statuses = enabled_statuses

            if ignored_statuses is not None:
                self._filter.ignored_statuses = ignored_statuses

            if min_priority is not None:
                self._filter.min_priority = min_priority

            if cooldown_seconds is not None:
                self._filter.cooldown_seconds = cooldown_seconds

            logger.info(f"🔧 Notification filter updated")

    def _queue_event(self, event: NotificationEvent):
        """Queue an event for processing."""
        with self._lock:
            self._event_queue.append(event)
            self._stats["events_received"] += 1
            self._stats["by_event_type"][event.event_type.value] += 1

        # Start processing if not already running
        if not self._running:
            self.start()

    def _process_events(self):
        """Main event processing loop."""
        logger.info("🔄 Notification event processing loop started")

        while self._running:
            try:
                events_to_process = []

                # Get events from queue
                with self._lock:
                    if self._event_queue:
                        events_to_process = self._event_queue[:]
                        self._event_queue.clear()

                # Process each event
                for event in events_to_process:
                    try:
                        self._process_single_event(event)
                    except Exception as e:
                        logger.error(f"❌ Error processing event {event.event_id}: {e}")
                        self._stats["events_failed"] += 1

                # Sleep between processing cycles
                time.sleep(1.0)

            except Exception as e:
                logger.error(f"❌ Error in notification processing loop: {e}")
                time.sleep(5.0)  # Longer sleep on error

        logger.info("🏁 Notification event processing loop stopped")

    def _process_single_event(self, event: NotificationEvent):
        """Process a single notification event."""
        try:
            # Apply filtering
            if not self._should_process_event(event):
                self._stats["events_filtered"] += 1
                return

            # Check for duplicates
            if self._is_duplicate_event(event):
                logger.debug(f"🔄 Duplicate event filtered: {event.event_id}")
                self._stats["events_filtered"] += 1
                return

            # Get handler for event type
            handler = self._event_handlers.get(event.event_type)
            if not handler:
                logger.warning(f"⚠️ No handler for event type: {event.event_type}")
                return

            # Process event
            handler(event)

            # Mark as processed
            event.processed = True
            self._stats["events_processed"] += 1

            # Add to history
            self._add_to_history(event)

            logger.debug(f"✅ Processed event: {event.event_id}")

        except Exception as e:
            logger.error(f"❌ Error processing event {event.event_id}: {e}")
            self._stats["events_failed"] += 1

    def _should_process_event(self, event: NotificationEvent) -> bool:
        """Check if an event should be processed based on filters."""
        # Check priority
        if event.priority.value < self._filter.min_priority.value:
            return False

        # Check status-specific filtering for status change events
        if event.event_type == EventType.TASK_STATUS_CHANGE:
            data = event.data
            from_status = data.get("from_status")
            to_status = data.get("to_status")

            # Check ignored statuses
            if to_status in self._filter.ignored_statuses or from_status in self._filter.ignored_statuses:
                return False

            # Check enabled statuses (if specified)
            if self._filter.enabled_statuses and to_status not in self._filter.enabled_statuses:
                return False

            # Check transition-specific rules
            transition = (from_status, to_status)
            if transition in self._filter.ignored_transitions:
                return False

            if self._filter.enabled_transitions and transition not in self._filter.enabled_transitions:
                return False

        return True

    def _is_duplicate_event(self, event: NotificationEvent) -> bool:
        """Check if an event is a duplicate within the cooldown period."""
        # Create event key for deduplication
        if event.event_type == EventType.TASK_STATUS_CHANGE:
            data = event.data
            event_key = f"{data.get('task_id')}_{data.get('to_status')}"
        else:
            event_key = f"{event.event_type}_{event.event_id}"

        current_time = time.time()

        # Check if we've seen this event recently
        if event_key in self._recent_events:
            last_time = self._recent_events[event_key]
            if current_time - last_time < self._filter.cooldown_seconds:
                return True

        # Update recent events tracking
        self._recent_events[event_key] = current_time

        # Clean up old events
        cutoff_time = current_time - (self._filter.cooldown_seconds * 2)
        expired_keys = [k for k, t in self._recent_events.items() if t < cutoff_time]
        for key in expired_keys:
            del self._recent_events[key]

        return False

    def _handle_status_change_event(self, event: NotificationEvent):
        """Handle task status change events."""
        data = event.data

        # Send Slack notification if enabled
        if self._slack_client and self._slack_message_builder:
            try:
                # Create task status change data
                status_data = TaskStatusChangeData(
                    task_id=data["task_id"],
                    task_title=data["task_title"],
                    from_status=data["from_status"],
                    to_status=data["to_status"],
                    timestamp=event.timestamp,
                    user_id=data.get("user_id"),
                    ticket_id=data.get("ticket_id"),
                    metadata=data.get("metadata", {}),
                )

                # Build message
                config = get_slack_config()
                channel = config.get_channel_for_priority(event.priority)

                message_config = self._slack_message_builder.build_task_status_change_message(data=status_data, channel=channel, priority=event.priority)

                # Create Slack message
                slack_message = SlackMessage(
                    channel=message_config["channel"],
                    text=message_config["text"],
                    blocks=message_config["blocks"],
                    priority=event.priority,
                )

                # Send message
                result = self._slack_client.send_message_with_retry(slack_message)

                if result.is_success():
                    self._stats["notifications_sent"] += 1
                    self._stats["by_channel"][NotificationChannel.SLACK.value] += 1
                    logger.info(f"✅ Slack notification sent for task {data['task_id']}")
                else:
                    logger.error(f"❌ Failed to send Slack notification: {result.error}")

            except Exception as e:
                logger.error(f"❌ Error sending Slack notification: {e}")

    def _handle_completion_event(self, event: NotificationEvent):
        """Handle task completion events."""
        # Use same handler as status change but with completion-specific formatting
        self._handle_status_change_event(event)

    def _handle_failure_event(self, event: NotificationEvent):
        """Handle task failure events."""
        # Use same handler as status change but with failure-specific formatting
        self._handle_status_change_event(event)

    def _handle_bulk_update_event(self, event: NotificationEvent):
        """Handle bulk update events."""
        # Implementation for bulk updates
        logger.info(f"📊 Bulk update event: {len(event.data.get('updates', []))} tasks")

    def _handle_system_alert_event(self, event: NotificationEvent):
        """Handle system alert events."""
        data = event.data

        # Send Slack notification if enabled
        if self._slack_client and self._slack_message_builder:
            try:
                config = get_slack_config()
                channel = config.error_channel if data.get("alert_type") == "error" else config.default_channel

                message_config = self._slack_message_builder.build_system_alert_message(
                    title=data["title"],
                    message=data["message"],
                    channel=channel,
                    alert_type=data.get("alert_type", "info"),
                    priority=event.priority,
                )

                slack_message = SlackMessage(
                    channel=message_config["channel"],
                    text=message_config["text"],
                    blocks=message_config["blocks"],
                    priority=event.priority,
                )

                result = self._slack_client.send_message_with_retry(slack_message)

                if result.is_success():
                    self._stats["notifications_sent"] += 1
                    self._stats["by_channel"][NotificationChannel.SLACK.value] += 1
                    logger.info(f"✅ System alert sent to Slack")
                else:
                    logger.error(f"❌ Failed to send system alert: {result.error}")

            except Exception as e:
                logger.error(f"❌ Error sending system alert: {e}")

    def _add_to_history(self, event: NotificationEvent):
        """Add event to processing history."""
        with self._lock:
            self._event_history.append(event)

            # Keep history manageable
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history :]

    def get_statistics(self) -> Dict[str, Any]:
        """Get notification processing statistics."""
        with self._lock:
            return {
                **self._stats,
                "queue_size": len(self._event_queue),
                "recent_events_tracked": len(self._recent_events),
                "history_size": len(self._event_history),
                "running": self._running,
                "slack_enabled": self._slack_client is not None,
            }

    def get_recent_events(self, limit: int = 50) -> List[NotificationEvent]:
        """Get recent events from history."""
        with self._lock:
            return self._event_history[-limit:]

    def test_notification(self, message: str = "Test notification") -> bool:
        """
        Send a test notification to verify the system is working.

        Args:
            message: Test message to send

        Returns:
            True if test was successful
        """
        try:
            self.notify_system_alert(
                title="Test Notification",
                message=message,
                alert_type="info",
                priority=MessagePriority.LOW,
            )
            return True
        except Exception as e:
            logger.error(f"❌ Test notification failed: {e}")
            return False


# Global notification manager instance
_notification_manager = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
