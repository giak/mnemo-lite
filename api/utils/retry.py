"""
Retry utilities with exponential backoff and jitter.

Story: EPIC-12 Story 12.5 - Retry Logic with Backoff
Author: Claude Code
Date: 2025-10-22
"""

import asyncio
import random
from typing import Callable, TypeVar, Optional, Tuple, Type
from functools import wraps
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')

# Default retryable exceptions
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    # Add more as needed (asyncpg, redis exceptions imported dynamically)
)


class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay cap in seconds
        jitter: Whether to add random jitter (±25%)
        retryable_exceptions: Tuple of exception types that trigger retries
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of attempts (default: 3)
            base_delay: Base delay in seconds (default: 1.0)
            max_delay: Maximum delay in seconds (default: 30.0)
            jitter: Add random jitter ±25% (default: True)
            retryable_exceptions: Tuple of retryable exceptions
                (default: DEFAULT_RETRYABLE_EXCEPTIONS)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or DEFAULT_RETRYABLE_EXCEPTIONS


def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    jitter: bool = True
) -> float:
    """
    Calculate retry delay with exponential backoff and optional jitter.

    Formula:
    - Exponential backoff: delay = base_delay * (2 ^ attempt)
    - Jitter: delay += random.uniform(-0.25 * delay, +0.25 * delay)
    - Cap: min(delay, max_delay)

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter (±25%)

    Returns:
        Delay in seconds (non-negative)

    Example:
        >>> calculate_delay(0, 1.0, 30.0, jitter=False)
        1.0  # 1.0 * 2^0
        >>> calculate_delay(1, 1.0, 30.0, jitter=False)
        2.0  # 1.0 * 2^1
        >>> calculate_delay(2, 1.0, 30.0, jitter=False)
        4.0  # 1.0 * 2^2
    """
    # Exponential backoff: delay = base * (2 ^ attempt)
    delay = min(base_delay * (2 ** attempt), max_delay)

    if jitter:
        # Add jitter: random ±25%
        jitter_amount = delay * random.uniform(-0.25, 0.25)
        delay += jitter_amount

    return max(0, delay)  # Ensure non-negative


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for async functions to add retry logic with exponential backoff.

    Usage:
        @with_retry(RetryConfig(max_attempts=5, base_delay=2.0))
        async def my_operation():
            # Operation that might fail transiently
            ...

    Args:
        config: Retry configuration (uses defaults if None)

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(RetryConfig(max_attempts=3))
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()

        # If request fails with TimeoutError, it will retry up to 3 times
        data = await fetch_data()
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            attempt = 0
            last_exception = None

            while attempt < config.max_attempts:
                try:
                    return await func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e
                    attempt += 1

                    if attempt >= config.max_attempts:
                        logger.error(
                            f"Max retry attempts ({config.max_attempts}) exceeded",
                            function=func.__name__,
                            error=str(e),
                            error_type=type(e).__name__,
                            attempt=attempt
                        )
                        raise

                    delay = calculate_delay(
                        attempt - 1,
                        config.base_delay,
                        config.max_delay,
                        config.jitter
                    )

                    logger.warning(
                        f"Retryable error, retrying in {delay:.2f}s",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay=delay
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop exited unexpectedly")

        return wrapper
    return decorator


# ============================================================================
# Retry configurations for different operation types
# ============================================================================

# Cache operations: Fast retries (transient Redis failures)
CACHE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    jitter=True
)

# Database operations: Medium retries (connection pool, deadlocks)
DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    jitter=True
)

# Embedding operations: Conservative retries (slow operation)
EMBEDDING_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
    jitter=True
)

# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    jitter=True
)


def get_retry_config(operation_type: str) -> RetryConfig:
    """
    Get retry configuration for operation type.

    Args:
        operation_type: Type of operation ('cache', 'database', 'embedding', 'default')

    Returns:
        RetryConfig for the operation type

    Example:
        config = get_retry_config('cache')
        @with_retry(config)
        async def cache_operation():
            ...
    """
    configs = {
        "cache": CACHE_RETRY_CONFIG,
        "database": DATABASE_RETRY_CONFIG,
        "embedding": EMBEDDING_RETRY_CONFIG,
        "default": DEFAULT_RETRY_CONFIG
    }
    return configs.get(operation_type, DEFAULT_RETRY_CONFIG)


# ============================================================================
# Helper to add retryable exceptions dynamically
# ============================================================================

def add_retryable_exceptions(*exceptions: Type[Exception]) -> None:
    """
    Add exceptions to the global DEFAULT_RETRYABLE_EXCEPTIONS.

    Useful for adding asyncpg, redis exceptions without hard dependencies.

    Args:
        *exceptions: Exception types to add

    Example:
        try:
            import asyncpg
            add_retryable_exceptions(
                asyncpg.exceptions.TooManyConnectionsError,
                asyncpg.exceptions.DeadlockDetectedError
            )
        except ImportError:
            pass
    """
    global DEFAULT_RETRYABLE_EXCEPTIONS
    DEFAULT_RETRYABLE_EXCEPTIONS = DEFAULT_RETRYABLE_EXCEPTIONS + exceptions
