import pytest
from services.batch_indexing_errors import ErrorType, ErrorHandler


def test_retryable_errors_identified():
    """Test retryable errors are correctly classified."""
    assert ErrorHandler.is_retryable(ErrorType.SUBPROCESS_TIMEOUT) is True
    assert ErrorHandler.is_retryable(ErrorType.DB_CONNECTION_ERROR) is True
    assert ErrorHandler.is_retryable(ErrorType.SUBPROCESS_CRASH) is True

    # Non-retryable
    assert ErrorHandler.is_retryable(ErrorType.FILE_NOT_FOUND) is False
    assert ErrorHandler.is_retryable(ErrorType.PARSE_ERROR) is False


def test_critical_errors_stop_consumer():
    """Test critical errors should stop consumer."""
    assert ErrorHandler.should_stop_consumer(ErrorType.REDIS_CONNECTION_LOST) is True
    assert ErrorHandler.should_stop_consumer(ErrorType.OUT_OF_MEMORY) is True
    assert ErrorHandler.should_stop_consumer(ErrorType.CRITICAL_ERROR) is True

    # Non-critical
    assert ErrorHandler.should_stop_consumer(ErrorType.SUBPROCESS_TIMEOUT) is False


def test_exponential_backoff():
    """Test retry delay uses exponential backoff."""
    assert ErrorHandler.get_retry_delay(1) == 5   # 5s
    assert ErrorHandler.get_retry_delay(2) == 10  # 10s
    assert ErrorHandler.get_retry_delay(3) == 20  # 20s
    assert ErrorHandler.get_retry_delay(10) == 60 # Max 60s
