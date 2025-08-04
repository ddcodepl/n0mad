import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from clients.notion_wrapper import NotionClientWrapper
from utils.logging_config import get_logger

logger = get_logger(__name__)


class ProcessingStage(str, Enum):
    """Processing stages for feedback updates"""
    REFINING = "refining"
    PREPARING = "preparing"
    PROCESSING = "processing"
    COPYING = "copying"
    FINALIZING = "finalizing"
    STATUS_TRANSITION = "status_transition"
    ERROR_HANDLING = "error_handling"


@dataclass
class FeedbackEntry:
    """Represents a feedback entry"""
    timestamp: datetime
    stage: ProcessingStage
    message: str
    details: Optional[str] = None
    error: Optional[str] = None


class FeedbackManager:
    """
    Manages ticket feedback property updates with timestamped messages.
    Thread-safe and atomic operations that don't interfere with status transitions.
    """
    
    def __init__(self, notion_client: NotionClientWrapper):
        self.notion_client = notion_client
        self._feedback_lock = threading.RLock()  # Reentrant lock for nested operations
        self._max_retry_attempts = 3
        self._retry_delay = 1.0  # seconds
        
        logger.info("📝 FeedbackManager initialized with thread-safe operations")
    
    def add_feedback(self, page_id: str, stage: ProcessingStage, message: str, 
                    details: Optional[str] = None, error: Optional[str] = None) -> bool:
        """
        Add a timestamped feedback message to the ticket's Feedback property.
        
        Args:
            page_id: Notion page ID
            stage: Processing stage
            message: Main feedback message
            details: Optional additional details
            error: Optional error information
            
        Returns:
            True if feedback was successfully added, False otherwise
        """
        feedback_entry = FeedbackEntry(
            timestamp=datetime.now(),
            stage=stage,
            message=message,
            details=details,
            error=error
        )
        
        with self._feedback_lock:
            try:
                logger.info(f"📝 Adding feedback for page {page_id[:8]}... stage: {stage.value}")
                
                # Get current feedback content
                current_feedback = self._get_current_feedback(page_id)
                
                # Create new feedback entry text
                new_entry = self._format_feedback_entry(feedback_entry)
                
                # Append to existing feedback
                updated_feedback = self._append_feedback(current_feedback, new_entry)
                
                # Update the page with new feedback
                success = self._update_feedback_property(page_id, updated_feedback)
                
                if success:
                    logger.info(f"✅ Feedback added successfully for page {page_id[:8]}... [{stage.value}]")
                else:
                    logger.error(f"❌ Failed to add feedback for page {page_id[:8]}... [{stage.value}]")
                
                return success
                
            except Exception as e:
                logger.error(f"❌ Exception adding feedback for page {page_id[:8]}...: {e}")
                return False
    
    def update_stage_feedback(self, page_id: str, stage: ProcessingStage, 
                            status: str, details: Optional[str] = None) -> bool:
        """
        Update feedback for a specific processing stage with status.
        
        Args:
            page_id: Notion page ID
            stage: Processing stage
            status: Status (started, completed, failed, etc.)
            details: Optional details
            
        Returns:
            True if feedback was successfully updated, False otherwise
        """
        message = f"Stage {stage.value} {status}"
        return self.add_feedback(page_id, stage, message, details=details)
    
    def add_error_feedback(self, page_id: str, stage: ProcessingStage, 
                          error_message: str, details: Optional[str] = None) -> bool:
        """
        Add error feedback for a specific processing stage.
        
        Args:
            page_id: Notion page ID
            stage: Processing stage where error occurred
            error_message: Error message
            details: Optional additional details
            
        Returns:
            True if feedback was successfully added, False otherwise
        """
        message = f"Error in {stage.value}"
        return self.add_feedback(page_id, stage, message, details=details, error=error_message)
    
    def add_status_transition_feedback(self, page_id: str, from_status: str, 
                                     to_status: str, success: bool, 
                                     error: Optional[str] = None) -> bool:
        """
        Add feedback for status transitions.
        
        Args:
            page_id: Notion page ID
            from_status: Previous status
            to_status: Target status
            success: Whether transition was successful
            error: Optional error message if failed
            
        Returns:
            True if feedback was successfully added, False otherwise
        """
        if success:
            message = f"Status transition: {from_status} → {to_status}"
            details = "Transition completed successfully"
        else:
            message = f"Status transition failed: {from_status} → {to_status}"
            details = f"Transition failed with error: {error}" if error else "Unknown error"
        
        return self.add_feedback(
            page_id, 
            ProcessingStage.STATUS_TRANSITION, 
            message, 
            details=details,
            error=error if not success else None
        )
    
    def _get_current_feedback(self, page_id: str) -> str:
        """
        Get current feedback content from the page.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            Current feedback content as string
        """
        try:
            page = self.notion_client.get_page(page_id)
            properties = page.get("properties", {})
            feedback_prop = properties.get("Feedback", {})
            
            if "rich_text" in feedback_prop and feedback_prop["rich_text"]:
                # Extract text from rich_text array
                text_parts = []
                for text_obj in feedback_prop["rich_text"]:
                    if "text" in text_obj and "content" in text_obj["text"]:
                        text_parts.append(text_obj["text"]["content"])
                
                return "".join(text_parts)
            
            return ""  # Empty feedback
            
        except Exception as e:
            logger.warning(f"⚠️ Could not get current feedback for page {page_id[:8]}...: {e}")
            return ""
    
    def _format_feedback_entry(self, entry: FeedbackEntry) -> str:
        """
        Format a feedback entry as text.
        
        Args:
            entry: FeedbackEntry to format
            
        Returns:
            Formatted feedback entry string
        """
        timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Base entry format
        formatted_entry = f"[{timestamp_str}] {entry.stage.value.upper()}: {entry.message}"
        
        # Add details if provided
        if entry.details:
            formatted_entry += f"\n  Details: {entry.details}"
        
        # Add error if provided
        if entry.error:
            formatted_entry += f"\n  Error: {entry.error}"
        
        return formatted_entry
    
    def _append_feedback(self, current_feedback: str, new_entry: str) -> str:
        """
        Append new feedback entry to existing feedback.
        
        Args:
            current_feedback: Current feedback content
            new_entry: New feedback entry to append
            
        Returns:
            Updated feedback content
        """
        if current_feedback.strip():
            return f"{current_feedback}\n\n{new_entry}"
        else:
            return new_entry
    
    def _chunk_text(self, text: str, max_chunk_size: int = 2000) -> List[str]:
        """
        Split text into chunks that fit within Notion's character limits.
        
        Args:
            text: Text to chunk
            max_chunk_size: Maximum characters per chunk (default 2000)
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        current_pos = 0
        
        while current_pos < len(text):
            # Calculate end position for this chunk
            end_pos = current_pos + max_chunk_size
            
            if end_pos >= len(text):
                # Last chunk - take remaining text
                chunks.append(text[current_pos:])
                break
            
            # Try to find a good breaking point (newline, space, etc.)
            chunk_text = text[current_pos:end_pos]
            
            # Look for natural break points in order of preference
            break_chars = ['\n\n', '\n', '. ', ', ', ' ']
            best_break = -1
            
            for break_char in break_chars:
                last_break = chunk_text.rfind(break_char)
                if last_break > max_chunk_size * 0.7:  # Don't break too early
                    best_break = last_break + len(break_char)
                    break
            
            if best_break > 0:
                # Use natural break point
                chunks.append(text[current_pos:current_pos + best_break])
                current_pos += best_break
            else:
                # No good break point found, force break at max size
                chunks.append(text[current_pos:end_pos])
                current_pos = end_pos
        
        return chunks

    def _update_feedback_property(self, page_id: str, feedback_content: str) -> bool:
        """
        Update the Feedback property with new content, handling text chunking for long content.
        
        Args:
            page_id: Notion page ID
            feedback_content: New feedback content
            
        Returns:
            True if update was successful, False otherwise
        """
        attempt = 0
        while attempt < self._max_retry_attempts:
            try:
                # Split content into chunks if it exceeds Notion's limit
                text_chunks = self._chunk_text(feedback_content, max_chunk_size=2000)
                
                # Create rich_text objects for each chunk
                rich_text_objects = []
                for chunk in text_chunks:
                    rich_text_objects.append({
                        "type": "text",
                        "text": {
                            "content": chunk
                        }
                    })
                
                # Prepare rich_text format for Notion API
                properties = {
                    "Feedback": {
                        "rich_text": rich_text_objects
                    }
                }
                
                # Update the page
                updated_page = self.notion_client.update_page(page_id, properties)
                
                # Verify update was successful
                if updated_page and "properties" in updated_page:
                    return True
                else:
                    logger.warning(f"⚠️ Feedback update verification failed for page {page_id[:8]}...")
                    return False
                
            except Exception as e:
                attempt += 1
                logger.warning(f"⚠️ Feedback update attempt {attempt}/{self._max_retry_attempts} failed: {e}")
                
                if attempt < self._max_retry_attempts:
                    import time
                    time.sleep(self._retry_delay * attempt)  # Exponential backoff
                else:
                    logger.error(f"❌ All feedback update attempts failed for page {page_id[:8]}...")
                    return False
        
        return False
    
    def clear_feedback(self, page_id: str) -> bool:
        """
        Clear all feedback from a ticket.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            True if feedback was successfully cleared, False otherwise
        """
        with self._feedback_lock:
            try:
                logger.info(f"🧹 Clearing feedback for page {page_id[:8]}...")
                success = self._update_feedback_property(page_id, "")
                
                if success:
                    logger.info(f"✅ Feedback cleared successfully for page {page_id[:8]}...")
                else:
                    logger.error(f"❌ Failed to clear feedback for page {page_id[:8]}...")
                
                return success
                
            except Exception as e:
                logger.error(f"❌ Exception clearing feedback for page {page_id[:8]}...: {e}")
                return False
    
    def get_feedback_summary(self, page_id: str) -> Dict[str, Any]:
        """
        Get a summary of feedback entries for a ticket.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            Dictionary with feedback summary information
        """
        try:
            current_feedback = self._get_current_feedback(page_id)
            
            if not current_feedback.strip():
                return {
                    "total_entries": 0,
                    "last_update": None,
                    "stages_covered": [],
                    "has_errors": False,
                    "feedback_length": 0
                }
            
            # Parse feedback entries (basic analysis)
            lines = current_feedback.split('\n')
            entries = []
            stages_covered = set()
            has_errors = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('[') and '] ' in line:
                    # This is a timestamp line - count as an entry
                    entries.append(line)
                    
                    # Extract stage information after the timestamp
                    try:
                        # Split on '] ' to separate timestamp from content
                        parts = line.split('] ', 1)
                        if len(parts) >= 2:
                            content = parts[1].strip()
                            # Split on ':' to separate stage from message
                            if ':' in content:
                                stage = content.split(':')[0].strip().lower()
                                stages_covered.add(stage)
                    except Exception:
                        pass  # Skip parsing errors for individual lines
                
                # Check for errors in any line
                if 'error' in line.lower():
                    has_errors = True
            
            # Find last update timestamp
            last_update = None
            if entries:
                try:
                    # Extract timestamp from last entry
                    last_entry = entries[-1]
                    if '[' in last_entry and '] ' in last_entry:
                        timestamp_str = last_entry.split('[')[1].split('] ')[0]
                        last_update = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass  # Could not parse timestamp
            
            summary = {
                "total_entries": len(entries),
                "last_update": last_update.isoformat() if last_update else None,
                "stages_covered": list(stages_covered),
                "has_errors": has_errors,
                "feedback_length": len(current_feedback)
            }
            
            logger.info(f"📊 Feedback summary for page {page_id[:8]}...: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting feedback summary for page {page_id[:8]}...: {e}")
            return {
                "total_entries": 0,
                "last_update": None,
                "stages_covered": [],
                "has_errors": False,
                "feedback_length": 0,
                "error": str(e)
            }