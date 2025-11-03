import pytest
from datetime import datetime
from models.indexing_error_models import IndexingErrorCreate, IndexingErrorResponse


def test_indexing_error_create_minimal():
    """Test creating error with minimal required fields."""
    error = IndexingErrorCreate(
        repository="test_repo",
        file_path="/test/file.ts",
        error_type="parsing_error",
        error_message="Unexpected token"
    )

    assert error.repository == "test_repo"
    assert error.file_path == "/test/file.ts"
    assert error.error_type == "parsing_error"
    assert error.error_message == "Unexpected token"
    assert error.error_traceback is None
    assert error.chunk_type is None
    assert error.language is None


def test_indexing_error_create_with_optionals():
    """Test creating error with all optional fields."""
    error = IndexingErrorCreate(
        repository="test_repo",
        file_path="/test/file.ts",
        error_type="chunking_error",
        error_message="Failed to extract chunks",
        error_traceback="Traceback (most recent call last)...",
        chunk_type="class",
        language="typescript"
    )

    assert error.error_traceback == "Traceback (most recent call last)..."
    assert error.chunk_type == "class"
    assert error.language == "typescript"


def test_indexing_error_response_model():
    """Test response model includes error_id and timestamp."""
    # Test that IndexingErrorResponse can be imported and instantiated
    from models.indexing_error_models import IndexingErrorResponse

    error = IndexingErrorResponse(
        error_id=1,
        repository="test_repo",
        file_path="/test/file.ts",
        error_type="parsing_error",
        error_message="Test error",
        occurred_at=datetime.now()
    )

    assert error.error_id == 1
    assert error.repository == "test_repo"
    assert error.occurred_at is not None
