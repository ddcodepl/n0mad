#!/usr/bin/env python3
"""
Slack Message Builder Service

Creates formatted Slack messages for task status change notifications
with user-friendly formatting, blocks, and contextual information.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from utils.slack_config import MessagePriority
from utils.logging_config import get_logger
from utils.task_status import TaskStatus

logger = get_logger(__name__)


class MessageTemplate(str, Enum):
    """Available message templates for different types of notifications."""
    TASK_STATUS_CHANGE = "task_status_change"
    TASK_COMPLETION = "task_completion" 
    TASK_FAILURE = "task_failure"
    BULK_STATUS_UPDATE = "bulk_status_update"
    SYSTEM_ALERT = "system_alert"


@dataclass
class TaskStatusChangeData:
    """
    Data structure for task status change notifications.
    """
    task_id: str
    task_title: str
    from_status: str
    to_status: str
    timestamp: datetime
    user_id: Optional[str] = None
    ticket_id: Optional[str] = None
    task_description: Optional[str] = None
    commit_hash: Optional[str] = None
    validation_result: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SlackMessageBuilder:
    """
    Service for building formatted Slack messages for task notifications.
    
    Provides methods to create rich, contextual messages with proper formatting,
    blocks, and priority handling for different types of task events.
    """
    
    def __init__(self):
        """Initialize the message builder."""
        # Status emoji mapping for visual feedback
        self.status_emojis = {
            TaskStatus.IDEAS.value: "💡",
            TaskStatus.TO_REFINE.value: "📝",
            TaskStatus.REFINED.value: "✨",
            TaskStatus.PREPARE_TASKS.value: "🔧",
            TaskStatus.PREPARING_TASKS.value: "⚙️",
            TaskStatus.READY_TO_RUN.value: "🚀",
            TaskStatus.QUEUED_TO_RUN.value: "⏳",
            TaskStatus.IN_PROGRESS.value: "🔄",
            TaskStatus.FAILED.value: "❌",
            TaskStatus.DONE.value: "✅"
        }
        
        # Priority colors for message styling
        self.priority_colors = {
            MessagePriority.LOW: "#36C5F0",      # Light Blue
            MessagePriority.MEDIUM: "#2EB67D",   # Green
            MessagePriority.HIGH: "#ECB22E",     # Yellow
            MessagePriority.URGENT: "#E01E5A"    # Red
        }
    
    def build_task_status_change_message(self, 
                                       data: TaskStatusChangeData,
                                       channel: str,
                                       priority: MessagePriority = MessagePriority.MEDIUM) -> Dict[str, Any]:
        """
        Build a formatted message for task status changes.
        
        Args:
            data: Task status change data
            channel: Target Slack channel
            priority: Message priority level
            
        Returns:
            Dictionary with message configuration
        """
        from_emoji = self.status_emojis.get(data.from_status, "📋")
        to_emoji = self.status_emojis.get(data.to_status, "📋")
        
        # Build main message text
        text = f"{from_emoji} → {to_emoji} Task status changed: *{data.task_title}*"
        
        if data.ticket_id:
            text = f"{from_emoji} → {to_emoji} Task {data.ticket_id} status changed: *{data.task_title}*"
        
        # Build rich blocks for better formatting
        blocks = self._build_status_change_blocks(data, priority)
        
        return {
            "channel": channel,
            "text": text,
            "blocks": blocks,
            "priority": priority
        }
    
    def build_task_completion_message(self,
                                    data: TaskStatusChangeData,
                                    channel: str,
                                    priority: MessagePriority = MessagePriority.HIGH) -> Dict[str, Any]:
        """
        Build a formatted message for task completions.
        
        Args:
            data: Task completion data
            channel: Target Slack channel
            priority: Message priority level
            
        Returns:
            Dictionary with message configuration
        """
        text = f"🎉 Task completed: *{data.task_title}*"
        
        if data.ticket_id:
            text = f"🎉 Task {data.ticket_id} completed: *{data.task_title}*"
        
        blocks = self._build_completion_blocks(data, priority)
        
        return {
            "channel": channel,
            "text": text,
            "blocks": blocks,
            "priority": priority
        }
    
    def build_task_failure_message(self,
                                 data: TaskStatusChangeData,
                                 channel: str,
                                 error_details: Optional[str] = None,
                                 priority: MessagePriority = MessagePriority.URGENT) -> Dict[str, Any]:
        """
        Build a formatted message for task failures.
        
        Args:
            data: Task failure data
            channel: Target Slack channel
            error_details: Optional error details
            priority: Message priority level
            
        Returns:
            Dictionary with message configuration
        """
        text = f"⚠️ Task failed: *{data.task_title}*"
        
        if data.ticket_id:
            text = f"⚠️ Task {data.ticket_id} failed: *{data.task_title}*"
        
        blocks = self._build_failure_blocks(data, error_details, priority)
        
        return {
            "channel": channel,
            "text": text,
            "blocks": blocks,
            "priority": priority
        }
    
    def build_bulk_update_message(self,
                                updates: List[TaskStatusChangeData],
                                channel: str,
                                priority: MessagePriority = MessagePriority.MEDIUM) -> Dict[str, Any]:
        """
        Build a formatted message for bulk status updates.
        
        Args:
            updates: List of task status changes
            channel: Target Slack channel
            priority: Message priority level
            
        Returns:
            Dictionary with message configuration
        """
        count = len(updates)
        text = f"📊 {count} tasks updated"
        
        blocks = self._build_bulk_update_blocks(updates, priority)
        
        return {
            "channel": channel,
            "text": text,
            "blocks": blocks,
            "priority": priority
        }
    
    def build_system_alert_message(self,
                                 title: str,
                                 message: str,
                                 channel: str,
                                 alert_type: str = "info",
                                 priority: MessagePriority = MessagePriority.HIGH) -> Dict[str, Any]:
        """
        Build a formatted system alert message.
        
        Args:
            title: Alert title
            message: Alert message
            channel: Target Slack channel
            alert_type: Type of alert (info, warning, error)
            priority: Message priority level
            
        Returns:
            Dictionary with message configuration
        """
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
            "success": "✅"
        }
        
        emoji = emoji_map.get(alert_type, "📢")
        text = f"{emoji} {title}"
        
        blocks = self._build_system_alert_blocks(title, message, alert_type, priority)
        
        return {
            "channel": channel,
            "text": text,
            "blocks": blocks,
            "priority": priority
        }
    
    def _build_status_change_blocks(self, 
                                  data: TaskStatusChangeData, 
                                  priority: MessagePriority) -> List[Dict[str, Any]]:
        """Build Slack blocks for status change messages."""
        blocks = []
        
        # Header block
        from_emoji = self.status_emojis.get(data.from_status, "📋")
        to_emoji = self.status_emojis.get(data.to_status, "📋")
        
        header_text = f"{from_emoji} → {to_emoji} *{data.task_title}*"
        if data.ticket_id:
            header_text = f"{from_emoji} → {to_emoji} *{data.ticket_id}: {data.task_title}*"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header_text
            }
        })
        
        # Details section
        details_fields = []
        
        details_fields.append({
            "type": "mrkdwn",
            "text": f"*Status:* {data.from_status} → {data.to_status}"
        })
        
        if data.user_id:
            details_fields.append({
                "type": "mrkdwn",
                "text": f"*Updated by:* <@{data.user_id}>"
            })
        
        details_fields.append({
            "type": "mrkdwn",
            "text": f"*Time:* {data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        })
        
        if data.commit_hash:
            commit_short = data.commit_hash[:8] if len(data.commit_hash) > 8 else data.commit_hash
            details_fields.append({
                "type": "mrkdwn",
                "text": f"*Commit:* `{commit_short}`"
            })
        
        blocks.append({
            "type": "section",
            "fields": details_fields
        })
        
        # Add description if available
        if data.task_description:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:* {data.task_description[:200]}{'...' if len(data.task_description) > 200 else ''}"
                }
            })
        
        # Add validation result if available
        if data.validation_result:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Validation: {data.validation_result}"
                    }
                ]
            })
        
        # Color bar based on priority
        blocks.append({
            "type": "divider"
        })
        
        return blocks
    
    def _build_completion_blocks(self, 
                               data: TaskStatusChangeData, 
                               priority: MessagePriority) -> List[Dict[str, Any]]:
        """Build Slack blocks for task completion messages."""
        blocks = []
        
        # Celebration header
        header_text = f"🎉 *Task Completed!*\n{data.task_title}"
        if data.ticket_id:
            header_text = f"🎉 *Task {data.ticket_id} Completed!*\n{data.task_title}"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header_text
            }
        })
        
        # Completion details
        details_fields = []
        
        details_fields.append({
            "type": "mrkdwn",
            "text": f"*Completed:* {data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        })
        
        if data.user_id:
            details_fields.append({
                "type": "mrkdwn",
                "text": f"*Completed by:* <@{data.user_id}>"
            })
        
        if data.commit_hash:
            commit_short = data.commit_hash[:8] if len(data.commit_hash) > 8 else data.commit_hash
            details_fields.append({
                "type": "mrkdwn",
                "text": f"*Final commit:* `{commit_short}`"
            })
        
        blocks.append({
            "type": "section",
            "fields": details_fields
        })
        
        return blocks
    
    def _build_failure_blocks(self, 
                            data: TaskStatusChangeData, 
                            error_details: Optional[str],
                            priority: MessagePriority) -> List[Dict[str, Any]]:
        """Build Slack blocks for task failure messages."""
        blocks = []
        
        # Error header
        header_text = f"⚠️ *Task Failed*\n{data.task_title}"
        if data.ticket_id:
            header_text = f"⚠️ *Task {data.ticket_id} Failed*\n{data.task_title}"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header_text
            }
        })
        
        # Failure details
        details_fields = []
        
        details_fields.append({
            "type": "mrkdwn",
            "text": f"*Failed:* {data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        })
        
        details_fields.append({
            "type": "mrkdwn",
            "text": f"*Status:* {data.from_status} → {data.to_status}"
        })
        
        blocks.append({
            "type": "section",
            "fields": details_fields
        })
        
        # Error details if available
        if error_details:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:* ```{error_details[:500]}{'...' if len(error_details) > 500 else ''}```"
                }
            })
        
        return blocks
    
    def _build_bulk_update_blocks(self, 
                                updates: List[TaskStatusChangeData],
                                priority: MessagePriority) -> List[Dict[str, Any]]:
        """Build Slack blocks for bulk update messages."""
        blocks = []
        
        # Summary header
        count = len(updates)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📊 *{count} Tasks Updated*"
            }
        })
        
        # Group updates by status transition
        status_groups = {}
        for update in updates:
            transition = f"{update.from_status} → {update.to_status}"
            if transition not in status_groups:
                status_groups[transition] = []
            status_groups[transition].append(update)
        
        # Show summary of transitions
        summary_fields = []
        for transition, group_updates in status_groups.items():
            from_status, to_status = transition.split(" → ")
            from_emoji = self.status_emojis.get(from_status, "📋")
            to_emoji = self.status_emojis.get(to_status, "📋")
            
            summary_fields.append({
                "type": "mrkdwn",
                "text": f"{from_emoji} → {to_emoji} *{len(group_updates)}* tasks: {transition}"
            })
        
        blocks.append({
            "type": "section",
            "fields": summary_fields[:10]  # Limit to first 10 transitions
        })
        
        # Show individual tasks (limited)
        if len(updates) <= 5:
            blocks.append({
                "type": "divider"
            })
            
            for update in updates[:5]:
                emoji = self.status_emojis.get(update.to_status, "📋")
                task_text = f"{emoji} {update.task_title}"
                if update.ticket_id:
                    task_text = f"{emoji} {update.ticket_id}: {update.task_title}"
                
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": task_text
                        }
                    ]
                })
        
        return blocks
    
    def _build_system_alert_blocks(self, 
                                 title: str,
                                 message: str,
                                 alert_type: str,
                                 priority: MessagePriority) -> List[Dict[str, Any]]:
        """Build Slack blocks for system alert messages."""
        blocks = []
        
        # Alert header
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️", 
            "error": "🚨",
            "success": "✅"
        }
        
        emoji = emoji_map.get(alert_type, "📢")
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{title}*"
            }
        })
        
        # Alert message
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": message
            }
        })
        
        # Timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Alert time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })
        
        return blocks
    
    def get_priority_for_status_change(self, from_status: str, to_status: str) -> MessagePriority:
        """
        Determine the appropriate message priority for a status change.
        
        Args:
            from_status: Original status
            to_status: New status
            
        Returns:
            MessagePriority for the status change
        """
        # Completion notifications are high priority
        if to_status in [TaskStatus.DONE.value]:
            return MessagePriority.HIGH
        
        # Failure notifications are urgent
        if to_status in [TaskStatus.FAILED.value]:
            return MessagePriority.URGENT
        
        # In-progress notifications are medium priority  
        if to_status in [TaskStatus.IN_PROGRESS.value, TaskStatus.QUEUED_TO_RUN.value]:
            return MessagePriority.MEDIUM
        
        # Other transitions are low priority
        return MessagePriority.LOW