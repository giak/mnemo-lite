"""
Tests for MCP Code Search Models (EPIC-23 Story 23.2).

Tests Pydantic models for code search tool including validation,
serialization, and edge cases.
"""

import json

import pytest
from pydantic import ValidationError

from mnemo_mcp.models.search_models import (
    CodeSearchFilters,
    CodeSearchMetadata,
    CodeSearchQuery,
    CodeSearchResponse,
    CodeSearchResult,
)


# ============================================================================
# CodeSearchFilters Tests
# ============================================================================


class TestCodeSearchFilters:
    """Test CodeSearchFilters model."""

    def test_empty_filters(self):
        """Test creating filters with no fields set."""
        filters = CodeSearchFilters()

        assert filters.language is None
        assert filters.chunk_type is None
        assert filters.repository is None
        assert filters.file_path is None
        assert filters.return_type is None
        assert filters.param_type is None

    def test_language_filter(self):
        """Test filtering by language."""
        filters = CodeSearchFilters(language="python")

        assert filters.language == "python"
        assert filters.chunk_type is None

    def test_multiple_filters(self):
        """Test setting multiple filters."""
        filters = CodeSearchFilters(
            language="python",
            chunk_type="function",
            repository="mnemolite",
            file_path="api/services/*.py"
        )

        assert filters.language == "python"
        assert filters.chunk_type == "function"
        assert filters.repository == "mnemolite"
        assert filters.file_path == "api/services/*.py"

    def test_lsp_filters(self):
        """Test LSP-enhanced filters (EPIC-14)."""
        filters = CodeSearchFilters(
            return_type="str",
            param_type="Context"
        )

        assert filters.return_type == "str"
        assert filters.param_type == "Context"

    def test_json_serialization(self):
        """Test filters serialize to JSON correctly."""
        filters = CodeSearchFilters(
            language="javascript",
            chunk_type="class"
        )

        json_str = filters.model_dump_json()
        data = json.loads(json_str)

        assert data["language"] == "javascript"
        assert data["chunk_type"] == "class"
        assert data["repository"] is None


# ============================================================================
# CodeSearchQuery Tests
# ============================================================================


class TestCodeSearchQuery:
    """Test CodeSearchQuery model."""

    def test_minimal_query(self):
        """Test creating query with only required field."""
        query = CodeSearchQuery(query="authentication")

        assert query.query == "authentication"
        assert query.limit == 10  # Default
        assert query.offset == 0  # Default
        assert query.filters is None
        assert query.enable_lexical is True
        assert query.enable_vector is True
        assert query.lexical_weight == 0.4
        assert query.vector_weight == 0.6

    def test_query_too_short(self):
        """Test query validation rejects empty string."""
        with pytest.raises(ValidationError) as exc_info:
            CodeSearchQuery(query="")

        error_str = str(exc_info.value).lower()
        assert "string_too_short" in error_str or "at least 1" in error_str

    def test_query_too_long(self):
        """Test query validation rejects string >500 chars."""
        long_query = "x" * 501

        with pytest.raises(ValidationError) as exc_info:
            CodeSearchQuery(query=long_query)

        error_str = str(exc_info.value).lower()
        assert "string_too_long" in error_str or "at most 500" in error_str

    def test_limit_validation_min(self):
        """Test limit must be >= 1."""
        with pytest.raises(ValidationError):
            CodeSearchQuery(query="test", limit=0)

    def test_limit_validation_max(self):
        """Test limit must be <= 100."""
        with pytest.raises(ValidationError):
            CodeSearchQuery(query="test", limit=101)

    def test_offset_validation_min(self):
        """Test offset must be >= 0."""
        with pytest.raises(ValidationError):
            CodeSearchQuery(query="test", offset=-1)

    def test_offset_validation_max(self):
        """Test offset must be <= 1000."""
        with pytest.raises(ValidationError):
            CodeSearchQuery(query="test", offset=1001)

    def test_custom_pagination(self):
        """Test setting custom limit and offset."""
        query = CodeSearchQuery(
            query="redis cache",
            limit=50,
            offset=100
        )

        assert query.limit == 50
        assert query.offset == 100

    def test_with_filters(self):
        """Test query with filters."""
        query = CodeSearchQuery(
            query="database connection",
            filters=CodeSearchFilters(
                language="python",
                chunk_type="function"
            )
        )

        assert query.filters is not None
        assert query.filters.language == "python"
        assert query.filters.chunk_type == "function"

    def test_disable_vector_search(self):
        """Test disabling vector search."""
        query = CodeSearchQuery(
            query="test",
            enable_vector=False
        )

        assert query.enable_lexical is True
        assert query.enable_vector is False

    def test_custom_weights(self):
        """Test setting custom lexical/vector weights."""
        query = CodeSearchQuery(
            query="test",
            lexical_weight=0.7,
            vector_weight=0.3
        )

        assert query.lexical_weight == 0.7
        assert query.vector_weight == 0.3

    def test_weight_validation_range(self):
        """Test weights must be in [0.0, 1.0] range."""
        with pytest.raises(ValidationError):
            CodeSearchQuery(query="test", lexical_weight=1.5)

        with pytest.raises(ValidationError):
            CodeSearchQuery(query="test", vector_weight=-0.1)


# ============================================================================
# CodeSearchResult Tests
# ============================================================================


class TestCodeSearchResult:
    """Test CodeSearchResult model."""

    def test_minimal_result(self):
        """Test creating result with required fields only."""
        result = CodeSearchResult(
            chunk_id="550e8400-e29b-41d4-a716-446655440000",
            rrf_score=0.85,
            rank=1,
            source_code="def authenticate(user): pass",
            name="authenticate",
            language="python",
            chunk_type="function",
            file_path="api/auth.py"
        )

        assert result.chunk_id == "550e8400-e29b-41d4-a716-446655440000"
        assert result.rrf_score == 0.85
        assert result.rank == 1
        assert result.name == "authenticate"
        assert result.metadata == {}
        assert result.related_nodes == []

    def test_result_with_scores(self):
        """Test result with lexical and vector scores."""
        result = CodeSearchResult(
            chunk_id="test-id",
            rrf_score=0.92,
            rank=1,
            source_code="code",
            name="test_func",
            language="python",
            chunk_type="function",
            file_path="test.py",
            lexical_score=0.75,
            vector_similarity=0.89,
            vector_distance=0.11,
            contribution={"lexical": 0.4, "vector": 0.6}
        )

        assert result.lexical_score == 0.75
        assert result.vector_similarity == 0.89
        assert result.vector_distance == 0.11
        assert result.contribution["lexical"] == 0.4
        assert result.contribution["vector"] == 0.6

    def test_result_with_name_path(self):
        """Test result with hierarchical name path (EPIC-11)."""
        result = CodeSearchResult(
            chunk_id="test-id",
            rrf_score=0.5,
            rank=1,
            source_code="code",
            name="my_method",
            name_path="MyClass.my_method",
            language="python",
            chunk_type="method",
            file_path="api/models.py"
        )

        assert result.name_path == "MyClass.my_method"

    def test_result_with_metadata(self):
        """Test result with additional metadata."""
        result = CodeSearchResult(
            chunk_id="test-id",
            rrf_score=0.5,
            rank=1,
            source_code="code",
            name="func",
            language="python",
            chunk_type="function",
            file_path="test.py",
            metadata={
                "repository": "mnemolite",
                "start_line": 10,
                "end_line": 25,
                "complexity": 5
            }
        )

        assert result.metadata["repository"] == "mnemolite"
        assert result.metadata["start_line"] == 10
        assert result.metadata["complexity"] == 5

    def test_rank_validation(self):
        """Test rank must be >= 1."""
        with pytest.raises(ValidationError):
            CodeSearchResult(
                chunk_id="test",
                rrf_score=0.5,
                rank=0,  # Invalid
                source_code="code",
                name="func",
                language="python",
                chunk_type="function",
                file_path="test.py"
            )


# ============================================================================
# CodeSearchMetadata Tests
# ============================================================================


class TestCodeSearchMetadata:
    """Test CodeSearchMetadata model."""

    def test_basic_metadata(self):
        """Test creating metadata with basic fields."""
        metadata = CodeSearchMetadata(
            total_results=42,
            lexical_count=25,
            vector_count=30,
            unique_after_fusion=40,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.4,
            vector_weight=0.6,
            execution_time_ms=123.45
        )

        assert metadata.total_results == 42
        assert metadata.lexical_count == 25
        assert metadata.vector_count == 30
        assert metadata.unique_after_fusion == 40
        assert metadata.execution_time_ms == 123.45

    def test_timing_breakdown(self):
        """Test metadata with detailed timing breakdown."""
        metadata = CodeSearchMetadata(
            total_results=10,
            lexical_count=5,
            vector_count=7,
            unique_after_fusion=10,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.5,
            vector_weight=0.5,
            execution_time_ms=100.0,
            lexical_time_ms=30.0,
            vector_time_ms=50.0,
            fusion_time_ms=20.0
        )

        assert metadata.lexical_time_ms == 30.0
        assert metadata.vector_time_ms == 50.0
        assert metadata.fusion_time_ms == 20.0
        assert metadata.graph_time_ms is None

    def test_cache_hit(self):
        """Test metadata with cache hit."""
        metadata = CodeSearchMetadata(
            total_results=5,
            lexical_count=0,
            vector_count=0,
            unique_after_fusion=5,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.4,
            vector_weight=0.6,
            execution_time_ms=2.5,
            cache_hit=True
        )

        assert metadata.cache_hit is True
        assert metadata.execution_time_ms == 2.5  # Fast!

    def test_lexical_only_search(self):
        """Test metadata for lexical-only search."""
        metadata = CodeSearchMetadata(
            total_results=10,
            lexical_count=10,
            vector_count=0,
            unique_after_fusion=10,
            lexical_enabled=True,
            vector_enabled=False,
            lexical_weight=1.0,
            vector_weight=0.0,
            execution_time_ms=50.0
        )

        assert metadata.lexical_enabled is True
        assert metadata.vector_enabled is False
        assert metadata.vector_count == 0

    def test_graph_expansion_future(self):
        """Test graph expansion field (future feature)."""
        metadata = CodeSearchMetadata(
            total_results=10,
            lexical_count=5,
            vector_count=5,
            unique_after_fusion=10,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.5,
            vector_weight=0.5,
            execution_time_ms=100.0,
            graph_expansion_enabled=False
        )

        assert metadata.graph_expansion_enabled is False


# ============================================================================
# CodeSearchResponse Tests
# ============================================================================


class TestCodeSearchResponse:
    """Test CodeSearchResponse model."""

    def test_basic_response(self):
        """Test creating response with results."""
        results = [
            CodeSearchResult(
                chunk_id="id1",
                rrf_score=0.9,
                rank=1,
                source_code="code1",
                name="func1",
                language="python",
                chunk_type="function",
                file_path="test1.py"
            ),
            CodeSearchResult(
                chunk_id="id2",
                rrf_score=0.8,
                rank=2,
                source_code="code2",
                name="func2",
                language="python",
                chunk_type="function",
                file_path="test2.py"
            )
        ]

        metadata = CodeSearchMetadata(
            total_results=2,
            lexical_count=2,
            vector_count=2,
            unique_after_fusion=2,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.4,
            vector_weight=0.6,
            execution_time_ms=50.0
        )

        response = CodeSearchResponse(
            results=results,
            metadata=metadata,
            total=100,
            limit=10,
            offset=0,
            has_next=True,
            next_offset=10
        )

        assert len(response.results) == 2
        assert response.total == 100
        assert response.has_next is True
        assert response.next_offset == 10

    def test_empty_results(self):
        """Test response with no results."""
        metadata = CodeSearchMetadata(
            total_results=0,
            lexical_count=0,
            vector_count=0,
            unique_after_fusion=0,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.4,
            vector_weight=0.6,
            execution_time_ms=10.0
        )

        response = CodeSearchResponse(
            results=[],
            metadata=metadata,
            total=0,
            limit=10,
            offset=0,
            has_next=False,
            next_offset=None
        )

        assert response.results == []
        assert response.total == 0
        assert response.has_next is False
        assert response.next_offset is None

    def test_last_page(self):
        """Test response for last page (no next)."""
        results = [
            CodeSearchResult(
                chunk_id="id1",
                rrf_score=0.5,
                rank=1,
                source_code="code",
                name="func",
                language="python",
                chunk_type="function",
                file_path="test.py"
            )
        ]

        metadata = CodeSearchMetadata(
            total_results=1,
            lexical_count=1,
            vector_count=1,
            unique_after_fusion=1,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.5,
            vector_weight=0.5,
            execution_time_ms=20.0
        )

        response = CodeSearchResponse(
            results=results,
            metadata=metadata,
            total=21,
            limit=10,
            offset=20,
            has_next=False,
            next_offset=None
        )

        assert response.has_next is False
        assert response.next_offset is None
        assert response.offset == 20

    def test_response_with_error(self):
        """Test response with graceful degradation error."""
        metadata = CodeSearchMetadata(
            total_results=5,
            lexical_count=5,
            vector_count=0,
            unique_after_fusion=5,
            lexical_enabled=True,
            vector_enabled=False,  # Vector failed
            lexical_weight=1.0,
            vector_weight=0.0,
            execution_time_ms=30.0
        )

        response = CodeSearchResponse(
            results=[],
            metadata=metadata,
            total=5,
            limit=10,
            offset=0,
            has_next=False,
            next_offset=None,
            error="Embedding service unavailable - using lexical search only"
        )

        assert response.error is not None
        assert "lexical search only" in response.error
        assert response.metadata.vector_enabled is False

    def test_json_serialization(self):
        """Test complete response serializes to JSON."""
        results = [
            CodeSearchResult(
                chunk_id="test-id",
                rrf_score=0.75,
                rank=1,
                source_code="def test(): pass",
                name="test",
                language="python",
                chunk_type="function",
                file_path="test.py"
            )
        ]

        metadata = CodeSearchMetadata(
            total_results=1,
            lexical_count=1,
            vector_count=1,
            unique_after_fusion=1,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.4,
            vector_weight=0.6,
            execution_time_ms=25.0
        )

        response = CodeSearchResponse(
            results=results,
            metadata=metadata,
            total=1,
            limit=10,
            offset=0,
            has_next=False,
            next_offset=None
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "test"
        assert data["metadata"]["execution_time_ms"] == 25.0
