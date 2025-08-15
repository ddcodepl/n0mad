"""
Custom exception hierarchy for the Nomad application.
"""

from typing import Any, Dict, Optional


class NomadError(Exception):
    """Base exception for all Nomad errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ConfigurationError(NomadError):
    """Configuration-related errors."""

    pass


class NotionAPIError(NomadError):
    """Notion API-related errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code


class NotionRateLimitError(NotionAPIError):
    """Notion API rate limit errors."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class NotionAuthenticationError(NotionAPIError):
    """Notion API authentication errors."""

    def __init__(self, message: str = "Invalid Notion token", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class ProcessingError(NomadError):
    """Task processing errors."""

    def __init__(self, message: str, task_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.task_id = task_id


class ValidationError(NomadError):
    """Data validation errors."""

    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


class FileOperationError(NomadError):
    """File operation errors."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.operation = operation


class DatabaseError(NomadError):
    """Database operation errors."""

    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.query = query


class AIProviderError(NomadError):
    """AI provider API errors."""

    def __init__(self, message: str, provider: Optional[str] = None, model: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.provider = provider
        self.model = model


class RetryableError(NomadError):
    """Errors that can be retried."""

    def __init__(self, message: str, retry_count: int = 0, max_retries: int = 3, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_count = retry_count
        self.max_retries = max_retries

    @property
    def can_retry(self) -> bool:
        """Check if this error can be retried."""
        return self.retry_count < self.max_retries


class TaskError(ProcessingError):
    """Task-specific errors."""

    def __init__(self, message: str, task_id: Optional[str] = None, stage: Optional[str] = None, **kwargs):
        super().__init__(message, task_id=task_id, **kwargs)
        self.stage = stage


class ContentProcessingError(ProcessingError):
    """Content processing errors."""

    def __init__(self, message: str, content_type: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.content_type = content_type
