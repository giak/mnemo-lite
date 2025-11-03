import pytest
from datetime import datetime
from pydantic import ValidationError
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


def test_indexing_error_create_rejects_invalid_error_type():
    """Test that invalid error_type values are rejected at API validation time."""
    with pytest.raises(ValidationError) as exc_info:
        IndexingErrorCreate(
            repository="test_repo",
            file_path="/test/file.ts",
            error_type="invalid_error_type",  # Invalid type
            error_message="Test error"
        )

    # Verify the validation error is about error_type
    error_dict = exc_info.value.errors()[0]
    assert error_dict['loc'] == ('error_type',)
    assert 'literal_error' in error_dict['type'] or 'enum' in error_dict['type']


def test_indexing_error_create_accepts_all_valid_error_types():
    """Test that all valid error types are accepted."""
    valid_types = ['parsing_error', 'encoding_error', 'chunking_error',
                   'embedding_error', 'persistence_error']

    for error_type in valid_types:
        error = IndexingErrorCreate(
            repository="test_repo",
            file_path="/test/file.ts",
            error_type=error_type,
            error_message="Test error"
        )
        assert error.error_type == error_type
