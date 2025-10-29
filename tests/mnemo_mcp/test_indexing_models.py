"""
Tests for MCP Indexing Models (EPIC-23 Story 23.5).

Tests Pydantic models for project indexing, status tracking, and progress reporting.
"""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from mnemo_mcp.models.indexing_models import (
    FileIndexResult,
    IndexingOptions,
    IndexResult,
    IndexStatus,
    ProgressUpdate,
    ReindexFileRequest,
)


# ============================================================================
# IndexingOptions Tests
# ============================================================================


class TestIndexingOptions:
    """Test IndexingOptions model."""

    def test_default_values(self):
        """Test IndexingOptions with default values."""
        options = IndexingOptions()

        assert options.extract_metadata is True
        assert options.generate_embeddings is True
        assert options.build_graph is True
        assert options.repository == "default"
        assert options.respect_gitignore is True

    def test_custom_values(self):
        """Test IndexingOptions with custom values."""
        options = IndexingOptions(
            extract_metadata=False,
            generate_embeddings=False,
            build_graph=False,
            repository="custom-repo",
            respect_gitignore=False
        )

        assert options.extract_metadata is False
        assert options.generate_embeddings is False
        assert options.build_graph is False
        assert options.repository == "custom-repo"
        assert options.respect_gitignore is False

    def test_json_serialization(self):
        """Test IndexingOptions JSON serialization."""
        options = IndexingOptions(repository="test-repo")

        json_str = options.model_dump_json()
        data = json.loads(json_str)

        assert data["extract_metadata"] is True
        assert data["repository"] == "test-repo"


# ============================================================================
# IndexResult Tests
# ============================================================================


class TestIndexResult:
    """Test IndexResult model."""

    def test_valid_result(self):
        """Test creating valid IndexResult."""
        result = IndexResult(
            success=True,
            repository="test-repo",
            indexed_files=100,
            indexed_chunks=500,
            indexed_nodes=250,
            indexed_edges=300,
            failed_files=5,
            processing_time_ms=12345.67,
            errors=[],
            message="Indexing completed"
        )

        assert result.success is True
        assert result.repository == "test-repo"
        assert result.indexed_files == 100
        assert result.indexed_chunks == 500
        assert result.indexed_nodes == 250
        assert result.indexed_edges == 300
        assert result.failed_files == 5
        assert result.processing_time_ms == 12345.67
        assert result.errors == []

    def test_result_with_errors(self):
        """Test IndexResult with error list."""
        result = IndexResult(
            success=False,
            repository="test-repo",
            indexed_files=50,
            indexed_chunks=200,
            indexed_nodes=100,
            indexed_edges=120,
            failed_files=10,
            processing_time_ms=5000.0,
            errors=[
                {"file": "test.py", "error": "Parse error"},
                {"file": "main.py", "error": "Encoding error"}
            ],
            message="Indexing failed"
        )

        assert result.success is False
        assert len(result.errors) == 2
        assert result.errors[0]["file"] == "test.py"

    def test_missing_required_fields(self):
        """Test IndexResult raises error for missing required fields."""
        with pytest.raises(ValidationError):
            IndexResult(
                success=True,
                repository="test"
                # Missing required fields
            )


# ============================================================================
# FileIndexResult Tests
# ============================================================================


class TestFileIndexResult:
    """Test FileIndexResult model."""

    def test_successful_file_index(self):
        """Test FileIndexResult for successful indexing."""
        result = FileIndexResult(
            success=True,
            file_path="api/main.py",
            chunks_created=10,
            processing_time_ms=123.45,
            cache_hit=False,
            error=None,
            message="File indexed successfully"
        )

        assert result.success is True
        assert result.file_path == "api/main.py"
        assert result.chunks_created == 10
        assert result.processing_time_ms == 123.45
        assert result.cache_hit is False
        assert result.error is None

    def test_failed_file_index(self):
        """Test FileIndexResult for failed indexing."""
        result = FileIndexResult(
            success=False,
            file_path="broken.py",
            chunks_created=0,
            processing_time_ms=50.0,
            cache_hit=False,
            error="Syntax error at line 42",
            message="Indexing failed"
        )

        assert result.success is False
        assert result.chunks_created == 0
        assert result.error == "Syntax error at line 42"

    def test_cache_hit_result(self):
        """Test FileIndexResult with cache hit."""
        result = FileIndexResult(
            success=True,
            file_path="cached.py",
            chunks_created=5,
            processing_time_ms=1.5,
            cache_hit=True,
            message="From cache"
        )

        assert result.cache_hit is True
        assert result.processing_time_ms < 10  # Cache should be fast


# ============================================================================
# IndexStatus Tests
# ============================================================================


class TestIndexStatus:
    """Test IndexStatus model."""

    def test_not_indexed_status(self):
        """Test IndexStatus for not indexed repository."""
        status = IndexStatus(
            success=True,
            repository="new-repo",
            status="not_indexed",
            total_files=0,
            indexed_files=0,
            total_chunks=0,
            languages=[],
            message="Repository not indexed"
        )

        assert status.status == "not_indexed"
        assert status.total_files == 0
        assert status.total_chunks == 0
        assert status.languages == []

    def test_in_progress_status(self):
        """Test IndexStatus for in-progress indexing."""
        started = datetime.utcnow()

        status = IndexStatus(
            success=True,
            repository="test-repo",
            status="in_progress",
            total_files=100,
            indexed_files=50,
            total_chunks=200,
            languages=["python", "javascript"],
            started_at=started,
            message="Indexing in progress"
        )

        assert status.status == "in_progress"
        assert status.total_files == 100
        assert status.indexed_files == 50
        assert status.started_at == started

    def test_completed_status(self):
        """Test IndexStatus for completed indexing."""
        completed = datetime.utcnow()

        status = IndexStatus(
            success=True,
            repository="test-repo",
            status="completed",
            total_files=100,
            indexed_files=100,
            total_chunks=500,
            languages=["python", "javascript", "go"],
            last_indexed_at=completed,
            completed_at=completed,
            embedding_model="nomic-embed-text-v1.5",
            cache_stats={"l1_hit_rate": 0.85, "l2_hit_rate": 0.92},
            message="Indexing completed"
        )

        assert status.status == "completed"
        assert status.total_files == 100
        assert status.indexed_files == 100
        assert len(status.languages) == 3
        assert status.cache_stats["l1_hit_rate"] == 0.85

    def test_failed_status(self):
        """Test IndexStatus for failed indexing."""
        status = IndexStatus(
            success=False,
            repository="test-repo",
            status="failed",
            total_files=100,
            indexed_files=30,
            total_chunks=150,
            languages=["python"],
            error="Database connection lost",
            message="Indexing failed"
        )

        assert status.status == "failed"
        assert status.error == "Database connection lost"

    def test_status_enum_validation(self):
        """Test IndexStatus validates status enum."""
        with pytest.raises(ValidationError):
            IndexStatus(
                success=True,
                repository="test",
                status="invalid_status",  # Not in enum
                message="Test"
            )

    def test_default_cache_stats(self):
        """Test IndexStatus with default empty cache_stats."""
        status = IndexStatus(
            success=True,
            repository="test",
            status="completed",
            message="Test"
        )

        assert status.cache_stats == {}


# ============================================================================
# ProgressUpdate Tests
# ============================================================================


class TestProgressUpdate:
    """Test ProgressUpdate model."""

    def test_progress_update_basic(self):
        """Test creating basic ProgressUpdate."""
        update = ProgressUpdate(
            current=50,
            total=100,
            percentage=0.5,
            message="Indexing files..."
        )

        assert update.current == 50
        assert update.total == 100
        assert update.percentage == 0.5
        assert update.message == "Indexing files..."
        assert update.file_path is None

    def test_progress_update_with_file(self):
        """Test ProgressUpdate with current file path."""
        update = ProgressUpdate(
            current=42,
            total=100,
            percentage=0.42,
            message="Processing",
            file_path="api/services/search.py"
        )

        assert update.current == 42
        assert update.file_path == "api/services/search.py"

    def test_progress_calculation(self):
        """Test ProgressUpdate percentage calculation."""
        update = ProgressUpdate(
            current=25,
            total=200,
            percentage=0.125,
            message="Progress"
        )

        # Verify percentage matches current/total
        expected = 25 / 200
        assert update.percentage == expected


# ============================================================================
# ReindexFileRequest Tests
# ============================================================================


class TestReindexFileRequest:
    """Test ReindexFileRequest model."""

    def test_basic_reindex_request(self):
        """Test creating basic ReindexFileRequest."""
        request = ReindexFileRequest(
            file_path="api/main.py"
        )

        assert request.file_path == "api/main.py"
        assert request.repository == "default"
        assert request.force_cache_invalidation is True

    def test_custom_reindex_request(self):
        """Test ReindexFileRequest with custom values."""
        request = ReindexFileRequest(
            file_path="src/utils.py",
            repository="custom-repo",
            force_cache_invalidation=False
        )

        assert request.file_path == "src/utils.py"
        assert request.repository == "custom-repo"
        assert request.force_cache_invalidation is False

    def test_missing_file_path(self):
        """Test ReindexFileRequest raises error without file_path."""
        with pytest.raises(ValidationError):
            ReindexFileRequest()  # Missing required file_path
