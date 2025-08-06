#!/usr/bin/env python3
"""
Enhanced Task Status Validation Service

Provides validation logic for task status transitions with Notion checkbox validation.
Integrates with existing StatusTransitionManager to enforce business rules.
"""
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from clients.notion_wrapper import NotionClientWrapper
from utils.task_status import TaskStatus
from utils.logging_config import get_logger
from utils.checkbox_utils import CheckboxUtilities, CheckboxParser

logger = get_logger(__name__)


class ValidationResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CHECKBOX_NOT_FOUND = "checkbox_not_found"
    CHECKBOX_UNCHECKED = "checkbox_unchecked"
    API_ERROR = "api_error"
    CACHED = "cached"


class ValidationErrorCode(str, Enum):
    CHECKBOX_VALIDATION_FAILED = "CHECKBOX_VALIDATION_FAILED"
    CHECKBOX_NOT_FOUND = "CHECKBOX_NOT_FOUND"
    CHECKBOX_UNCHECKED = "CHECKBOX_UNCHECKED"
    NOTION_API_ERROR = "NOTION_API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


@dataclass
class ValidationOperation:
    """Represents a validation operation with results and metadata"""
    operation_id: str
    page_id: str
    from_status: str
    to_status: str
    checkbox_name: str
    timestamp: datetime
    result: Optional[ValidationResult] = None
    error_code: Optional[ValidationErrorCode] = None
    error_message: Optional[str] = None
    checkbox_value: Optional[bool] = None
    was_cached: bool = False
    api_call_duration: float = 0.0
    
    
@dataclass
class CheckboxCacheEntry:
    """Represents a cached checkbox validation result"""
    page_id: str
    checkbox_name: str
    checkbox_value: bool
    timestamp: datetime
    confidence: float
    

class TaskStatusValidationService:
    """
    Enhanced task status validation service with Notion checkbox validation.
    
    Features:
    - Checkbox validation for status transitions
    - Caching to reduce API calls
    - Comprehensive error handling
    - Audit logging
    - Integration with existing status transition system
    """
    
    def __init__(self, 
                 notion_client: NotionClientWrapper,
                 cache_ttl_minutes: int = 5,
                 enabled: bool = True):
        """
        Initialize the validation service.
        
        Args:
            notion_client: Notion API client wrapper
            cache_ttl_minutes: Cache time-to-live in minutes
            enabled: Whether validation is enabled (feature toggle)
        """
        self.notion_client = notion_client
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.enabled = enabled
        
        # Checkbox validation cache
        self._checkbox_cache: Dict[str, CheckboxCacheEntry] = {}
        self._validation_history: List[ValidationOperation] = []
        self._max_history = 1000
        
        # Checkbox utilities for advanced parsing
        self.checkbox_utilities = CheckboxUtilities()
        self.checkbox_parser = CheckboxParser()
        
        # Configuration
        self.commit_checkbox_names = [
            "Commit", "commit", "Ready to commit", "Can commit", 
            "Ready to Commit", "Commit Ready", "Commit?"
        ]
        
        # Status transitions that require validation
        self.validation_required_transitions = {
            (TaskStatus.IN_PROGRESS.value, TaskStatus.DONE.value),
            ("In progress", "Done"),
            ("in-progress", "done"),
            ("In Progress", "Finished"),
            ("in_progress", "finished")
        }
        
        logger.info(f"🔒 TaskStatusValidationService initialized (enabled: {enabled}, cache_ttl: {cache_ttl_minutes}m)")
    
    def validate_task_transition(self, 
                                page_id: str, 
                                from_status: str, 
                                to_status: str,
                                ticket_id: Optional[str] = None) -> ValidationOperation:
        """
        Validate a task status transition with checkbox requirements.
        
        Args:
            page_id: Notion page ID
            from_status: Current status
            to_status: Target status
            ticket_id: Optional ticket identifier for logging
            
        Returns:
            ValidationOperation with results
        """
        operation_id = f"validate_{page_id[:8]}_{int(time.time())}"
        
        operation = ValidationOperation(
            operation_id=operation_id,
            page_id=page_id,
            from_status=from_status,
            to_status=to_status,
            checkbox_name="Commit",  # Default, may be updated
            timestamp=datetime.now()
        )
        
        try:
            logger.info(f"🔍 Validating transition: {from_status} → {to_status} for page {page_id[:8]}...")
            
            # Check if validation is enabled
            if not self.enabled:
                operation.result = ValidationResult.SKIPPED
                logger.info("⏭️ Validation disabled, skipping checkbox check")
                self._add_to_history(operation)
                return operation
            
            # Check if this transition requires validation
            if not self._requires_validation(from_status, to_status):
                operation.result = ValidationResult.SKIPPED
                logger.info(f"⏭️ Transition {from_status} → {to_status} doesn't require validation")
                self._add_to_history(operation)
                return operation
            
            # Perform checkbox validation
            checkbox_result = self._validate_commit_checkbox(page_id)
            
            # Update operation with results
            operation.checkbox_name = checkbox_result.get("checkbox_name", "Commit")
            operation.checkbox_value = checkbox_result.get("checkbox_value")
            operation.was_cached = checkbox_result.get("was_cached", False)
            operation.api_call_duration = checkbox_result.get("api_duration", 0.0)
            
            if checkbox_result["success"]:
                if checkbox_result["checkbox_value"]:
                    operation.result = ValidationResult.SUCCESS
                    logger.info(f"✅ Validation passed: checkbox '{operation.checkbox_name}' is checked")
                else:
                    operation.result = ValidationResult.CHECKBOX_UNCHECKED
                    operation.error_code = ValidationErrorCode.CHECKBOX_UNCHECKED
                    operation.error_message = f"Checkbox '{operation.checkbox_name}' must be checked before marking as finished"
                    logger.warning(f"❌ Validation failed: checkbox not checked")
            else:
                if checkbox_result.get("checkbox_found", False):
                    operation.result = ValidationResult.FAILED
                    operation.error_code = ValidationErrorCode.CHECKBOX_VALIDATION_FAILED
                    operation.error_message = checkbox_result.get("error", "Checkbox validation failed")
                else:
                    operation.result = ValidationResult.CHECKBOX_NOT_FOUND
                    operation.error_code = ValidationErrorCode.CHECKBOX_NOT_FOUND
                    operation.error_message = f"No commit checkbox found in page properties"
                    logger.warning(f"⚠️ No commit checkbox found in page {page_id[:8]}...")
            
            self._add_to_history(operation)
            return operation
            
        except Exception as e:
            operation.result = ValidationResult.FAILED
            operation.error_code = ValidationErrorCode.NOTION_API_ERROR
            operation.error_message = str(e)
            logger.error(f"❌ Validation exception for page {page_id[:8]}...: {e}")
            self._add_to_history(operation)
            return operation
    
    def check_notion_commit_checkbox(self, page_id: str) -> Dict[str, Any]:
        """
        Check the commit checkbox state for a Notion page.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            Dictionary with checkbox state and metadata
        """
        return self._validate_commit_checkbox(page_id)
    
    def _validate_commit_checkbox(self, page_id: str) -> Dict[str, Any]:
        """
        Internal method to validate commit checkbox with caching.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "success": False,
            "checkbox_value": False,
            "checkbox_found": False,
            "checkbox_name": None,
            "was_cached": False,
            "api_duration": 0.0,
            "error": None
        }
        
        try:
            # Check cache first
            cached_result = self._get_cached_checkbox_state(page_id)
            if cached_result:
                result.update({
                    "success": True,
                    "checkbox_value": cached_result.checkbox_value,
                    "checkbox_found": True,
                    "checkbox_name": cached_result.checkbox_name,
                    "was_cached": True,
                    "confidence": cached_result.confidence
                })
                logger.debug(f"📋 Using cached checkbox state for page {page_id[:8]}...")
                return result
            
            # Make API call to get page data
            start_time = time.time()
            
            try:
                page_data = self.notion_client.get_page(page_id)
                api_duration = time.time() - start_time
                result["api_duration"] = api_duration
                
            except Exception as api_error:
                result["error"] = f"Notion API error: {str(api_error)}"
                logger.error(f"❌ Failed to fetch page {page_id[:8]}...: {api_error}")
                return result
            
            # Search for commit checkboxes using utilities
            commit_checkboxes = self.checkbox_utilities.find_checkbox_properties(
                page_data, 
                self.commit_checkbox_names
            )
            
            if not commit_checkboxes:
                result["error"] = "No commit checkbox properties found"
                logger.debug(f"📋 No commit checkboxes found in page {page_id[:8]}...")
                return result
            
            # Use the first found checkbox (prioritized by search order)
            primary_checkbox = commit_checkboxes[0]
            result.update({
                "success": True,
                "checkbox_value": primary_checkbox.value,
                "checkbox_found": True,
                "checkbox_name": primary_checkbox.name,
                "confidence": primary_checkbox.confidence
            })
            
            # Cache the result
            self._cache_checkbox_state(
                page_id=page_id,
                checkbox_name=primary_checkbox.name,
                checkbox_value=primary_checkbox.value,
                confidence=primary_checkbox.confidence
            )
            
            logger.debug(f"📋 Checkbox '{primary_checkbox.name}' state: {primary_checkbox.value} (confidence: {primary_checkbox.confidence:.2f})")
            return result
            
        except Exception as e:
            result["error"] = f"Validation exception: {str(e)}"
            logger.error(f"❌ Checkbox validation exception: {e}")
            return result
    
    def _requires_validation(self, from_status: str, to_status: str) -> bool:
        """
        Check if a status transition requires checkbox validation.
        
        Args:
            from_status: Current status
            to_status: Target status
            
        Returns:
            True if validation is required
        """
        # Normalize status values for comparison
        normalized_transition = (from_status.strip(), to_status.strip())
        
        # Check exact matches
        if normalized_transition in self.validation_required_transitions:
            return True
        
        # Check case-insensitive matches
        normalized_lower = (from_status.lower().strip(), to_status.lower().strip())
        for valid_from, valid_to in self.validation_required_transitions:
            if (normalized_lower[0] == valid_from.lower() and 
                normalized_lower[1] == valid_to.lower()):
                return True
        
        # Check for "finished" or "done" target states
        to_status_lower = to_status.lower().strip()
        if to_status_lower in ['done', 'finished', 'complete', 'completed']:
            return True
        
        return False
    
    def _get_cached_checkbox_state(self, page_id: str) -> Optional[CheckboxCacheEntry]:
        """
        Get cached checkbox state if available and not expired.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            Cached entry or None if not found/expired
        """
        # Clean up expired entries first
        self._cleanup_expired_cache()
        
        for checkbox_name in self.commit_checkbox_names:
            cache_key = f"{page_id}:{checkbox_name}"
            if cache_key in self._checkbox_cache:
                entry = self._checkbox_cache[cache_key]
                if datetime.now() - entry.timestamp <= self.cache_ttl:
                    return entry
        
        return None
    
    def _cache_checkbox_state(self, 
                             page_id: str, 
                             checkbox_name: str, 
                             checkbox_value: bool,
                             confidence: float = 1.0):
        """
        Cache checkbox state for future use.
        
        Args:
            page_id: Notion page ID
            checkbox_name: Name of the checkbox property
            checkbox_value: Checkbox state (True/False)
            confidence: Confidence in the parsed value
        """
        cache_key = f"{page_id}:{checkbox_name}"
        entry = CheckboxCacheEntry(
            page_id=page_id,
            checkbox_name=checkbox_name,
            checkbox_value=checkbox_value,
            timestamp=datetime.now(),
            confidence=confidence
        )
        
        self._checkbox_cache[cache_key] = entry
        logger.debug(f"💾 Cached checkbox state: {checkbox_name}={checkbox_value}")
    
    def _cleanup_expired_cache(self):
        """Remove expired cache entries."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._checkbox_cache.items()
            if now - entry.timestamp > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self._checkbox_cache[key]
        
        if expired_keys:
            logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
    
    def _add_to_history(self, operation: ValidationOperation):
        """Add validation operation to history with size management."""
        self._validation_history.append(operation)
        
        # Keep history size manageable
        if len(self._validation_history) > self._max_history:
            self._validation_history = self._validation_history[-self._max_history:]
    
    def get_validation_history(self, 
                              page_id: Optional[str] = None, 
                              limit: int = 100) -> List[ValidationOperation]:
        """
        Get validation history for monitoring and debugging.
        
        Args:
            page_id: Optional page ID to filter by
            limit: Maximum number of operations to return
            
        Returns:
            List of ValidationOperation objects
        """
        history = self._validation_history
        
        if page_id:
            history = [op for op in history if op.page_id == page_id]
        
        return history[-limit:] if limit else history
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """
        Get validation statistics for monitoring.
        
        Returns:
            Dictionary with validation statistics
        """
        total_validations = len(self._validation_history)
        if total_validations == 0:
            return {
                "total_validations": 0,
                "success_rate": 0.0,
                "cache_hit_rate": 0.0,
                "average_api_duration": 0.0
            }
        
        successful = len([op for op in self._validation_history if op.result == ValidationResult.SUCCESS])
        cached = len([op for op in self._validation_history if op.was_cached])
        api_calls = [op for op in self._validation_history if op.api_call_duration > 0]
        
        stats = {
            "total_validations": total_validations,
            "successful_validations": successful,
            "failed_validations": total_validations - successful,
            "success_rate": (successful / total_validations * 100),
            "cache_hit_rate": (cached / total_validations * 100),
            "cache_size": len(self._checkbox_cache),
            "average_api_duration": sum(op.api_call_duration for op in api_calls) / len(api_calls) if api_calls else 0.0,
            "result_distribution": self._get_result_distribution()
        }
        
        return stats
    
    def _get_result_distribution(self) -> Dict[str, int]:
        """Get distribution of validation results."""
        distribution = {}
        for result in ValidationResult:
            count = len([op for op in self._validation_history if op.result == result])
            distribution[result.value] = count
        return distribution
    
    def clear_cache(self) -> int:
        """
        Clear the checkbox validation cache.
        
        Returns:
            Number of entries cleared
        """
        cache_size = len(self._checkbox_cache)
        self._checkbox_cache.clear()
        logger.info(f"🧹 Cleared validation cache ({cache_size} entries)")
        return cache_size
    
    def is_enabled(self) -> bool:
        """Check if validation is enabled."""
        return self.enabled
    
    def set_enabled(self, enabled: bool):
        """Enable or disable validation."""
        self.enabled = enabled
        logger.info(f"🔧 Validation {'enabled' if enabled else 'disabled'}")
    
    def configure_commit_checkboxes(self, checkbox_names: List[str]):
        """
        Configure the list of checkbox names to search for.
        
        Args:
            checkbox_names: List of checkbox property names
        """
        self.commit_checkbox_names = checkbox_names
        # Clear cache since checkbox names changed
        self.clear_cache()
        logger.info(f"🔧 Updated commit checkbox names: {checkbox_names}")
    
    def add_validation_transition(self, from_status: str, to_status: str):
        """
        Add a status transition that requires validation.
        
        Args:
            from_status: Source status
            to_status: Target status
        """
        self.validation_required_transitions.add((from_status, to_status))
        logger.info(f"➕ Added validation transition: {from_status} → {to_status}")