"""
Centralized error handling for batch indexing.

EPIC-27: Batch Processing with Redis Streams
"""

from enum import Enum
from typing import Dict


class ErrorType(Enum):
    """Types of errors in batch indexing pipeline."""

    # File-level errors (continue-on-error)
    FILE_NOT_FOUND = "file_not_found"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    EMBEDDING_ERROR = "embedding_generation_failed"

    # Batch-level errors (retry batch)
    SUBPROCESS_CRASH = "subprocess_crash"
    SUBPROCESS_TIMEOUT = "subprocess_timeout"
    DB_CONNECTION_ERROR = "db_connection_error"

    # System-level errors (stop consumer)
    REDIS_CONNECTION_LOST = "redis_connection_lost"
    OUT_OF_MEMORY = "out_of_memory"
    CRITICAL_ERROR = "critical_error"


class ErrorHandler:
    """Centralized error handling logic."""

    @staticmethod
    def is_retryable(error_type: ErrorType) -> bool:
        """
        Determine if error is retryable.

        Returns:
            True if error should trigger batch retry
        """
        retryable = {
            ErrorType.SUBPROCESS_TIMEOUT,
            ErrorType.DB_CONNECTION_ERROR,
            ErrorType.SUBPROCESS_CRASH
        }
        return error_type in retryable

    @staticmethod
    def should_stop_consumer(error_type: ErrorType) -> bool:
        """
        Determine if consumer should stop.

        Returns:
            True if error is critical and consumer must stop
        """
        critical = {
            ErrorType.REDIS_CONNECTION_LOST,
            ErrorType.OUT_OF_MEMORY,
            ErrorType.CRITICAL_ERROR
        }
        return error_type in critical

    @staticmethod
    def get_retry_delay(attempt: int) -> int:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Retry attempt number (1-indexed)

        Returns:
            Delay in seconds (max 60s)

        Formula: min(5 * 2^(attempt-1), 60)
        """
        return min(5 * (2 ** (attempt - 1)), 60)
