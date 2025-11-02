import pytest
from services.batch_indexing_consumer import BatchIndexingConsumer
from services.batch_indexing_errors import ErrorType


def test_classify_error_timeout():
    """Test error classification for timeouts."""
    consumer = BatchIndexingConsumer()

    error = Exception("Batch processing timeout after 300s")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.SUBPROCESS_TIMEOUT


def test_classify_error_database():
    """Test error classification for DB errors."""
    consumer = BatchIndexingConsumer()

    error = Exception("Database connection failed")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.DB_CONNECTION_ERROR


def test_classify_error_memory():
    """Test error classification for OOM."""
    consumer = BatchIndexingConsumer()

    error = Exception("Out of memory (OOM)")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.OUT_OF_MEMORY


def test_classify_error_subprocess():
    """Test error classification for subprocess crashes."""
    consumer = BatchIndexingConsumer()

    error = Exception("Subprocess execution failed")
    error_type = consumer._classify_error(error)

    assert error_type == ErrorType.SUBPROCESS_CRASH
