import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from notion_wrapper import NotionClientWrapper
from task_status import TaskStatus
from logging_config import get_logger

logger = get_logger(__name__)


class TransitionResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK_SUCCESS = "rollback_success"
    ROLLBACK_FAILED = "rollback_failed"


@dataclass
class StatusTransition:
    """Represents a status transition operation"""
    page_id: str
    from_status: str
    to_status: str
    timestamp: datetime
    result: Optional[TransitionResult] = None
    error: Optional[str] = None
    rollback_attempted: bool = False
    rollback_result: Optional[TransitionResult] = None


class StatusTransitionManager:
    """
    Manages atomic status transitions with error handling and rollback capabilities.
    Thread-safe for concurrent ticket processing.
    """
    
    def __init__(self, notion_client: NotionClientWrapper):
        self.notion_client = notion_client
        self._transition_lock = threading.RLock()  # Reentrant lock for nested operations
        self._transition_history: List[StatusTransition] = []
        self._max_history = 1000  # Keep last 1000 transitions for debugging
        
        # Valid status transitions mapping
        self._valid_transitions = {
            TaskStatus.QUEUED_TO_RUN.value: [TaskStatus.IN_PROGRESS.value],
            TaskStatus.IN_PROGRESS.value: [TaskStatus.DONE.value, TaskStatus.FAILED.value],
            TaskStatus.FAILED.value: [TaskStatus.QUEUED_TO_RUN.value, TaskStatus.IN_PROGRESS.value],
            TaskStatus.DONE.value: []  # Final state
        }
        
        logger.info("🔄 StatusTransitionManager initialized with thread-safe operations")
    
    def is_valid_transition(self, from_status: str, to_status: str) -> bool:
        """
        Check if a status transition is valid.
        
        Args:
            from_status: Current status
            to_status: Target status
            
        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = self._valid_transitions.get(from_status, [])
        is_valid = to_status in valid_targets
        
        if not is_valid:
            logger.warning(f"⚠️ Invalid transition attempted: {from_status} → {to_status}")
            logger.info(f"📋 Valid transitions from '{from_status}': {valid_targets}")
        
        return is_valid
    
    def transition_status(self, page_id: str, from_status: str, to_status: str, 
                         validate_transition: bool = True) -> StatusTransition:
        """
        Perform an atomic status transition with error handling.
        
        Args:
            page_id: Notion page ID
            from_status: Expected current status
            to_status: Target status
            validate_transition: Whether to validate transition rules
            
        Returns:
            StatusTransition object with operation results
        """
        transition = StatusTransition(
            page_id=page_id,
            from_status=from_status,
            to_status=to_status,
            timestamp=datetime.now()
        )
        
        # Thread-safe operation
        with self._transition_lock:
            try:
                logger.info(f"🔄 Starting status transition: {from_status} → {to_status} for page {page_id[:8]}...")
                
                # Validate transition if requested
                if validate_transition and not self.is_valid_transition(from_status, to_status):
                    transition.result = TransitionResult.FAILED
                    transition.error = f"Invalid transition: {from_status} → {to_status}"
                    self._add_to_history(transition)
                    return transition
                
                # Get current status to verify it matches expected from_status
                try:
                    current_page = self.notion_client.get_page(page_id)
                    current_status = self._extract_current_status(current_page)
                    
                    if current_status != from_status:
                        logger.warning(f"⚠️ Status mismatch: expected '{from_status}', found '{current_status}'")
                        # Update from_status to actual current status for accuracy
                        transition.from_status = current_status
                        
                        # Re-validate with actual current status
                        if validate_transition and not self.is_valid_transition(current_status, to_status):
                            transition.result = TransitionResult.FAILED
                            transition.error = f"Invalid transition from actual status: {current_status} → {to_status}"
                            self._add_to_history(transition)
                            return transition
                
                except Exception as status_check_error:
                    logger.warning(f"⚠️ Could not verify current status: {status_check_error}")
                    # Continue with transition attempt anyway
                
                # Perform the status update
                updated_page = self.notion_client.update_page_status(page_id, to_status)
                
                # Verify the update was successful
                updated_status = self._extract_current_status(updated_page)
                if updated_status == to_status:
                    transition.result = TransitionResult.SUCCESS
                    logger.info(f"✅ Status transition successful: {transition.from_status} → {to_status} for page {page_id[:8]}...")
                else:
                    transition.result = TransitionResult.FAILED
                    transition.error = f"Status update failed: expected '{to_status}', got '{updated_status}'"
                    logger.error(f"❌ Status transition failed: {transition.error}")
                
            except Exception as e:
                transition.result = TransitionResult.FAILED
                transition.error = str(e)
                logger.error(f"❌ Status transition failed with exception: {e}")
            
            # Add to history for tracking
            self._add_to_history(transition)
            return transition
    
    def rollback_transition(self, transition: StatusTransition) -> StatusTransition:
        """
        Attempt to rollback a status transition.
        
        Args:
            transition: The transition to rollback
            
        Returns:
            Updated StatusTransition object with rollback results
        """
        if transition.rollback_attempted:
            logger.warning(f"⚠️ Rollback already attempted for transition {transition.page_id[:8]}...")
            return transition
        
        with self._transition_lock:
            try:
                logger.info(f"🔄 Attempting rollback: {transition.to_status} → {transition.from_status} for page {transition.page_id[:8]}...")
                
                transition.rollback_attempted = True
                
                # Perform rollback status update
                self.notion_client.update_page_status(transition.page_id, transition.from_status)
                
                # Verify rollback was successful
                current_page = self.notion_client.get_page(transition.page_id)
                current_status = self._extract_current_status(current_page)
                
                if current_status == transition.from_status:
                    transition.rollback_result = TransitionResult.ROLLBACK_SUCCESS
                    logger.info(f"✅ Rollback successful: {transition.to_status} → {transition.from_status} for page {transition.page_id[:8]}...")
                else:
                    transition.rollback_result = TransitionResult.ROLLBACK_FAILED
                    logger.error(f"❌ Rollback failed: expected '{transition.from_status}', got '{current_status}'")
                
            except Exception as e:
                transition.rollback_result = TransitionResult.ROLLBACK_FAILED
                logger.error(f"❌ Rollback failed with exception: {e}")
            
            return transition
    
    def batch_transition_status(self, transitions: List[Tuple[str, str, str]]) -> List[StatusTransition]:
        """
        Perform multiple status transitions with automatic rollback on any failure.
        
        Args:
            transitions: List of (page_id, from_status, to_status) tuples
            
        Returns:
            List of StatusTransition objects
        """
        results = []
        successful_transitions = []
        
        with self._transition_lock:
            logger.info(f"🔄 Starting batch status transition for {len(transitions)} tickets...")
            
            # Attempt all transitions
            for page_id, from_status, to_status in transitions:
                result = self.transition_status(page_id, from_status, to_status)
                results.append(result)
                
                if result.result == TransitionResult.SUCCESS:
                    successful_transitions.append(result)
                else:
                    # Failure detected - rollback all successful transitions
                    logger.error(f"❌ Batch transition failed at page {page_id[:8]}..., initiating rollback...")
                    
                    for successful_transition in successful_transitions:
                        rollback_result = self.rollback_transition(successful_transition)
                        logger.info(f"🔄 Rollback result for {successful_transition.page_id[:8]}...: {rollback_result.rollback_result}")
                    
                    break
            
            successful_count = len(successful_transitions)
            total_count = len(transitions)
            
            logger.info(f"📊 Batch transition results: {successful_count}/{total_count} successful")
            
            if successful_count == total_count:
                logger.info("✅ All batch transitions completed successfully")
            else:
                logger.warning(f"⚠️ Batch transition partially failed, {len(successful_transitions)} rollbacks attempted")
        
        return results
    
    def _extract_current_status(self, page: Dict[str, Any]) -> str:
        """
        Extract current status from a Notion page object.
        
        Args:
            page: Notion page object
            
        Returns:
            Current status string
        """
        try:
            properties = page.get("properties", {})
            status_prop = properties.get("Status", {})
            
            # Handle different status property types
            if "status" in status_prop and status_prop["status"]:
                return status_prop["status"]["name"]
            elif "select" in status_prop and status_prop["select"]:
                return status_prop["select"]["name"]
            else:
                logger.warning("⚠️ Could not extract status from page properties")
                return "Unknown"
                
        except Exception as e:
            logger.error(f"❌ Error extracting status from page: {e}")
            return "Unknown"
    
    def _add_to_history(self, transition: StatusTransition):
        """Add transition to history with size management."""
        self._transition_history.append(transition)
        
        # Keep history size manageable
        if len(self._transition_history) > self._max_history:
            self._transition_history = self._transition_history[-self._max_history:]
    
    def get_transition_history(self, page_id: Optional[str] = None, 
                             limit: int = 100) -> List[StatusTransition]:
        """
        Get transition history for debugging and monitoring.
        
        Args:
            page_id: Optional page ID to filter by
            limit: Maximum number of transitions to return
            
        Returns:
            List of StatusTransition objects
        """
        with self._transition_lock:
            history = self._transition_history
            
            if page_id:
                history = [t for t in history if t.page_id == page_id]
            
            return history[-limit:] if limit else history
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get transition statistics for monitoring.
        
        Returns:
            Dictionary with transition statistics
        """
        with self._transition_lock:
            total_transitions = len(self._transition_history)
            successful = len([t for t in self._transition_history if t.result == TransitionResult.SUCCESS])
            failed = len([t for t in self._transition_history if t.result == TransitionResult.FAILED])
            rollbacks_attempted = len([t for t in self._transition_history if t.rollback_attempted])
            rollbacks_successful = len([t for t in self._transition_history if t.rollback_result == TransitionResult.ROLLBACK_SUCCESS])
            
            stats = {
                "total_transitions": total_transitions,
                "successful_transitions": successful,
                "failed_transitions": failed,
                "rollbacks_attempted": rollbacks_attempted,
                "rollbacks_successful": rollbacks_successful,
                "success_rate": (successful / total_transitions * 100) if total_transitions > 0 else 0,
                "rollback_success_rate": (rollbacks_successful / rollbacks_attempted * 100) if rollbacks_attempted > 0 else 0
            }
            
            logger.info(f"📊 Transition Statistics: {stats}")
            return stats