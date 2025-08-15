"""
Retry decorator with exponential backoff for API calls and operations.
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, Union

try:
    from ..core.exceptions import NotionAPIError, NotionRateLimitError, RetryableError
except ImportError:
    # Fallback for standalone testing
    try:
        from core.exceptions import NotionAPIError, NotionRateLimitError, RetryableError
    except ImportError:
        # Define minimal exceptions for testing
        class RetryableError(Exception):
            def __init__(self, message, retry_count=0, max_retries=3):
                super().__init__(message)
                self.retry_count = retry_count
                self.max_retries = max_retries

            @property
            def can_retry(self):
                return self.retry_count < self.max_retries

        class NotionRateLimitError(Exception):
            pass

        class NotionAPIError(Exception):
            pass

        class NotionAuthenticationError(Exception):
            pass


logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (),
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay
        retryable_exceptions: Tuple of exception types that should trigger retries
        non_retryable_exceptions: Tuple of exception types that should never be retried
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _execute_with_retry(
                func,
                args,
                kwargs,
                max_retries,
                base_delay,
                max_delay,
                exponential_base,
                jitter,
                retryable_exceptions,
                non_retryable_exceptions,
            )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _execute_with_retry_async(
                func,
                args,
                kwargs,
                max_retries,
                base_delay,
                max_delay,
                exponential_base,
                jitter,
                retryable_exceptions,
                non_retryable_exceptions,
            )

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _calculate_delay(attempt: int, base_delay: float, max_delay: float, exponential_base: float, jitter: bool) -> float:
    """Calculate delay for given attempt with exponential backoff and optional jitter."""
    delay = min(base_delay * (exponential_base**attempt), max_delay)

    if jitter:
        # Add random jitter up to 25% of the delay
        import random

        jitter_amount = delay * 0.25 * random.random()
        delay += jitter_amount

    return delay


def _should_retry(
    exception: Exception,
    attempt: int,
    max_retries: int,
    retryable_exceptions: Tuple[Type[Exception], ...],
    non_retryable_exceptions: Tuple[Type[Exception], ...],
) -> bool:
    """Determine if an exception should trigger a retry."""

    # Check if we've exhausted retries
    if attempt >= max_retries:
        return False

    # Check for non-retryable exceptions first
    if isinstance(exception, non_retryable_exceptions):
        return False

    # Check for specific retryable patterns
    if isinstance(exception, RetryableError):
        return exception.can_retry

    # Check for rate limiting
    if isinstance(exception, NotionRateLimitError):
        return True

    # Check for network/timeout errors
    error_str = str(exception).lower()
    retryable_patterns = [
        "rate limit",
        "timeout",
        "connection",
        "network",
        "temporary",
        "service unavailable",
        "429",
        "502",
        "503",
        "504",
    ]

    if any(pattern in error_str for pattern in retryable_patterns):
        return True

    # Check if exception type is in retryable list
    return isinstance(exception, retryable_exceptions)


def _execute_with_retry(
    func: Callable,
    args: tuple,
    kwargs: dict,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    retryable_exceptions: Tuple[Type[Exception], ...],
    non_retryable_exceptions: Tuple[Type[Exception], ...],
) -> Any:
    """Execute function with retry logic (synchronous)."""

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = func(*args, **kwargs)

            # Log successful retry
            if attempt > 0:
                logger.info(f"✅ Function {func.__name__} succeeded on attempt {attempt + 1}")

            return result

        except Exception as e:
            last_exception = e

            # Check if we should retry
            if not _should_retry(e, attempt, max_retries, retryable_exceptions, non_retryable_exceptions):
                logger.error(f"❌ Function {func.__name__} failed on attempt {attempt + 1}, not retrying: {e}")
                raise

            # Calculate delay for next attempt
            if attempt < max_retries:
                delay = _calculate_delay(attempt, base_delay, max_delay, exponential_base, jitter)
                logger.warning(f"⚠️ Function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}: {e}")
                logger.info(f"⏳ Retrying in {delay:.2f} seconds...")
                time.sleep(delay)

    # If we get here, all retries failed
    logger.error(f"❌ Function {func.__name__} failed after {max_retries + 1} attempts")
    raise last_exception


async def _execute_with_retry_async(
    func: Callable,
    args: tuple,
    kwargs: dict,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    retryable_exceptions: Tuple[Type[Exception], ...],
    non_retryable_exceptions: Tuple[Type[Exception], ...],
) -> Any:
    """Execute async function with retry logic."""

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)

            # Log successful retry
            if attempt > 0:
                logger.info(f"✅ Async function {func.__name__} succeeded on attempt {attempt + 1}")

            return result

        except Exception as e:
            last_exception = e

            # Check if we should retry
            if not _should_retry(e, attempt, max_retries, retryable_exceptions, non_retryable_exceptions):
                logger.error(f"❌ Async function {func.__name__} failed on attempt {attempt + 1}, not retrying: {e}")
                raise

            # Calculate delay for next attempt
            if attempt < max_retries:
                delay = _calculate_delay(attempt, base_delay, max_delay, exponential_base, jitter)
                logger.warning(f"⚠️ Async function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}: {e}")
                logger.info(f"⏳ Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)

    # If we get here, all retries failed
    logger.error(f"❌ Async function {func.__name__} failed after {max_retries + 1} attempts")
    raise last_exception


# Predefined decorators for common use cases
try:
    notion_api_retry = retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(NotionAPIError, NotionRateLimitError, ConnectionError, TimeoutError),
        non_retryable_exceptions=(NotionAuthenticationError,),
    )
except NameError:
    # Fallback without NotionAuthenticationError if not available
    notion_api_retry = retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(NotionAPIError, NotionRateLimitError, ConnectionError, TimeoutError),
        non_retryable_exceptions=(),
    )

file_operation_retry = retry_with_backoff(
    max_retries=2,
    base_delay=0.5,
    max_delay=5.0,
    retryable_exceptions=(OSError, IOError, PermissionError),
    non_retryable_exceptions=(FileNotFoundError,),
)

ai_api_retry = retry_with_backoff(
    max_retries=3,
    base_delay=2.0,
    max_delay=60.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
    non_retryable_exceptions=(ValueError, TypeError),
)
