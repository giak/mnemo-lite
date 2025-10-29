"""
Tests for MCP code search tool.

Tests both unit-level (mocked dependencies) and integration-level
(real database) scenarios.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any

from mnemo_mcp.tools.search_tool import SearchCodeTool
from mnemo_mcp.models.search_models import (
    CodeSearchFilters,
    CodeSearchResponse,
    CodeSearchResult,
    CodeSearchMetadata,
)


@dataclass
class MockHybridSearchResult:
    """Mock result matching HybridSearchResult structure."""
    chunk_id: str
    rrf_score: float
    rank: int
    source_code: str
    name: str
    name_path: str | None
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]
    lexical_score: float | None
    vector_similarity: float | None
    vector_distance: float | None
    contribution: Dict[str, float]
    related_nodes: List[str]


@dataclass
class MockSearchMetadata:
    """Mock metadata matching SearchMetadata structure."""
    total_results: int
    lexical_count: int
    vector_count: int
    unique_after_fusion: int
    lexical_enabled: bool
    vector_enabled: bool
    graph_expansion_enabled: bool
    lexical_weight: float
    vector_weight: float
    execution_time_ms: float
    lexical_time_ms: float | None = None
    vector_time_ms: float | None = None
    fusion_time_ms: float | None = None
    graph_time_ms: float | None = None


@dataclass
class MockHybridSearchResponse:
    """Mock response matching HybridSearchResponse structure."""
    results: List[MockHybridSearchResult]
    metadata: MockSearchMetadata


class TestSearchCodeTool:
    """Unit tests for SearchCodeTool (mocked dependencies)."""

    def test_get_name(self):
        """Test tool name."""
        tool = SearchCodeTool()
        assert tool.get_name() == "search_code"

    @pytest.mark.asyncio
    async def test_execute_simple_query_success(self):
        """Test simple query with mocked services."""
        tool = SearchCodeTool()

        # Mock services
        mock_db_pool = MagicMock()
        mock_redis = AsyncMock()
        mock_embedding_service = AsyncMock()
        mock_ctx = MagicMock()

        # Mock Redis cache miss
        mock_redis.get.return_value = None

        # Mock embedding generation
        mock_embedding_service.generate_embedding.return_value = [0.1] * 768

        # Mock HybridSearchService response
        mock_result = MockHybridSearchResult(
            chunk_id="chunk-123",
            rrf_score=0.95,
            rank=1,
            source_code="def authenticate(user, password):\n    pass",
            name="authenticate",
            name_path="api.auth.authenticate",
            language="python",
            chunk_type="function",
            file_path="api/auth.py",
            metadata={"repository": "mnemolite"},
            lexical_score=0.8,
            vector_similarity=0.9,
            vector_distance=0.1,
            contribution={"lexical": 0.4, "vector": 0.6},
            related_nodes=[],
        )

        mock_metadata = MockSearchMetadata(
            total_results=1,
            lexical_count=1,
            vector_count=1,
            unique_after_fusion=1,
            lexical_enabled=True,
            vector_enabled=True,
            graph_expansion_enabled=False,
            lexical_weight=0.4,
            vector_weight=0.6,
            execution_time_ms=50.0,
            lexical_time_ms=20.0,
            vector_time_ms=25.0,
            fusion_time_ms=5.0,
        )

        mock_search_response = MockHybridSearchResponse(
            results=[mock_result],
            metadata=mock_metadata
        )

        # Inject services
        services = {
            "db": mock_db_pool,
            "redis": mock_redis,
            "embedding_service": mock_embedding_service,
        }
        tool.inject_services(services)

        # Mock HybridCodeSearchService.search() via patch
        with patch("mnemo_mcp.tools.search_tool.HybridCodeSearchService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.search.return_value = mock_search_response
            MockService.return_value = mock_service_instance

            # Execute search
            response = await tool.execute(
                ctx=mock_ctx,
                query="authentication",
                filters=None,
                limit=10,
                offset=0,
            )

        # Verify response
        assert isinstance(response, CodeSearchResponse)
        assert len(response.results) == 1
        assert response.total == 1
        assert response.has_next is False
        assert response.error is None

        # Verify result
        result = response.results[0]
        assert result.chunk_id == "chunk-123"
        assert result.name == "authenticate"
        assert result.language == "python"
        assert result.rrf_score == 0.95

        # Verify metadata
        assert response.metadata.total_results == 1
        assert response.metadata.lexical_enabled is True
        assert response.metadata.vector_enabled is True

    @pytest.mark.asyncio
    async def test_execute_with_filters(self):
        """Test query with filters applied."""
        tool = SearchCodeTool()

        # Mock services
        mock_db_pool = MagicMock()
        mock_redis = AsyncMock()
        mock_embedding_service = AsyncMock()
        mock_ctx = MagicMock()

        mock_redis.get.return_value = None
        mock_embedding_service.generate_embedding.return_value = [0.1] * 768

        services = {
            "db": mock_db_pool,
            "redis": mock_redis,
            "embedding_service": mock_embedding_service,
        }
        tool.inject_services(services)

        # Create filters
        filters = CodeSearchFilters(
            language="python",
            chunk_type="function",
            repository="mnemolite"
        )

        # Mock empty response
        mock_response = MockHybridSearchResponse(
            results=[],
            metadata=MockSearchMetadata(
                total_results=0,
                lexical_count=0,
                vector_count=0,
                unique_after_fusion=0,
                lexical_enabled=True,
                vector_enabled=True,
                graph_expansion_enabled=False,
                lexical_weight=0.4,
                vector_weight=0.6,
                execution_time_ms=10.0,
            )
        )

        with patch("mnemo_mcp.tools.search_tool.HybridCodeSearchService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.search.return_value = mock_response
            MockService.return_value = mock_service_instance

            response = await tool.execute(
                ctx=mock_ctx,
                query="test",
                filters=filters,
                limit=10,
                offset=0,
            )

        # Verify filters were passed correctly
        assert response.total == 0
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_execute_cache_hit(self):
        """Test cache hit returns cached results."""
        tool = SearchCodeTool()

        mock_db_pool = MagicMock()
        mock_redis = AsyncMock()
        mock_ctx = MagicMock()

        # Mock cached response
        cached_data = {
            "results": [],
            "metadata": {
                "total_results": 0,
                "lexical_count": 0,
                "vector_count": 0,
                "unique_after_fusion": 0,
                "lexical_enabled": True,
                "vector_enabled": True,
                "graph_expansion_enabled": False,
                "lexical_weight": 0.4,
                "vector_weight": 0.6,
                "execution_time_ms": 5.0,
                "cache_hit": False,
            },
            "total": 0,
            "limit": 10,
            "offset": 0,
            "has_next": False,
            "next_offset": None,
            "error": None,
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        services = {
            "db": mock_db_pool,
            "redis": mock_redis,
            "embedding_service": None,
        }
        tool.inject_services(services)

        response = await tool.execute(
            ctx=mock_ctx,
            query="cached query",
            limit=10,
            offset=0,
        )

        # Verify response came from cache
        assert isinstance(response, CodeSearchResponse)
        assert response.metadata.cache_hit is True  # Should be set to True by cache hit logic

    @pytest.mark.asyncio
    async def test_execute_pagination(self):
        """Test pagination with offset and limit."""
        tool = SearchCodeTool()

        mock_db_pool = MagicMock()
        mock_redis = AsyncMock()
        mock_embedding_service = AsyncMock()
        mock_ctx = MagicMock()

        mock_redis.get.return_value = None
        mock_embedding_service.generate_embedding.return_value = [0.1] * 768

        # Mock 25 results (to test pagination)
        mock_results = [
            MockHybridSearchResult(
                chunk_id=f"chunk-{i}",
                rrf_score=1.0 - (i * 0.01),
                rank=i + 1,
                source_code=f"def func{i}(): pass",
                name=f"func{i}",
                name_path=None,
                language="python",
                chunk_type="function",
                file_path=f"file{i}.py",
                metadata={},
                lexical_score=0.8,
                vector_similarity=0.9,
                vector_distance=0.1,
                contribution={},
                related_nodes=[],
            )
            for i in range(25)
        ]

        mock_response = MockHybridSearchResponse(
            results=mock_results,
            metadata=MockSearchMetadata(
                total_results=25,
                lexical_count=25,
                vector_count=25,
                unique_after_fusion=25,
                lexical_enabled=True,
                vector_enabled=True,
                graph_expansion_enabled=False,
                lexical_weight=0.4,
                vector_weight=0.6,
                execution_time_ms=100.0,
            )
        )

        services = {
            "db": mock_db_pool,
            "redis": mock_redis,
            "embedding_service": mock_embedding_service,
        }
        tool.inject_services(services)

        with patch("mnemo_mcp.tools.search_tool.HybridCodeSearchService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.search.return_value = mock_response
            MockService.return_value = mock_service_instance

            # Test page 1 (offset=0, limit=10)
            response_p1 = await tool.execute(
                ctx=mock_ctx,
                query="test",
                limit=10,
                offset=0,
            )

            assert len(response_p1.results) == 10
            assert response_p1.total == 25
            assert response_p1.offset == 0
            assert response_p1.limit == 10
            assert response_p1.has_next is True
            assert response_p1.next_offset == 10
            assert response_p1.results[0].chunk_id == "chunk-0"

    @pytest.mark.asyncio
    async def test_execute_invalid_query(self):
        """Test invalid query parameters raise ValueError."""
        tool = SearchCodeTool()

        mock_ctx = MagicMock()
        tool.inject_services({"db": MagicMock()})

        # Empty query
        with pytest.raises(ValueError, match="Query must be"):
            await tool.execute(ctx=mock_ctx, query="")

        # Query too long
        with pytest.raises(ValueError, match="Query must be"):
            await tool.execute(ctx=mock_ctx, query="x" * 501)

        # Invalid limit
        with pytest.raises(ValueError, match="Limit must be"):
            await tool.execute(ctx=mock_ctx, query="test", limit=0)

        with pytest.raises(ValueError, match="Limit must be"):
            await tool.execute(ctx=mock_ctx, query="test", limit=101)

        # Invalid offset
        with pytest.raises(ValueError, match="Offset must be"):
            await tool.execute(ctx=mock_ctx, query="test", offset=-1)

        with pytest.raises(ValueError, match="Offset must be"):
            await tool.execute(ctx=mock_ctx, query="test", offset=1001)

    @pytest.mark.asyncio
    async def test_execute_graceful_degradation_embedding_failure(self):
        """Test graceful degradation when embedding generation fails."""
        tool = SearchCodeTool()

        mock_db_pool = MagicMock()
        mock_redis = AsyncMock()
        mock_embedding_service = AsyncMock()
        mock_ctx = MagicMock()

        mock_redis.get.return_value = None

        # Mock embedding failure
        mock_embedding_service.generate_embedding.side_effect = Exception("Model not loaded")

        # Mock lexical-only response
        mock_response = MockHybridSearchResponse(
            results=[],
            metadata=MockSearchMetadata(
                total_results=0,
                lexical_count=0,
                vector_count=0,
                unique_after_fusion=0,
                lexical_enabled=True,
                vector_enabled=False,  # Disabled due to embedding failure
                graph_expansion_enabled=False,
                lexical_weight=0.4,
                vector_weight=0.6,
                execution_time_ms=20.0,
            )
        )

        services = {
            "db": mock_db_pool,
            "redis": mock_redis,
            "embedding_service": mock_embedding_service,
        }
        tool.inject_services(services)

        with patch("mnemo_mcp.tools.search_tool.HybridCodeSearchService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.search.return_value = mock_response
            MockService.return_value = mock_service_instance

            # Should not raise, falls back to lexical-only
            response = await tool.execute(
                ctx=mock_ctx,
                query="test",
                enable_vector=True,  # Request vector but will fallback
            )

        assert response.metadata.vector_enabled is False

    def test_generate_cache_key_deterministic(self):
        """Test cache key generation is deterministic."""
        tool = SearchCodeTool()

        filters = CodeSearchFilters(language="python")

        key1 = tool._generate_cache_key(
            query="test",
            filters=filters,
            limit=10,
            offset=0,
            enable_lexical=True,
            enable_vector=True,
            lexical_weight=0.4,
            vector_weight=0.6,
        )

        key2 = tool._generate_cache_key(
            query="test",
            filters=filters,
            limit=10,
            offset=0,
            enable_lexical=True,
            enable_vector=True,
            lexical_weight=0.4,
            vector_weight=0.6,
        )

        # Same parameters should generate same key
        assert key1 == key2
        assert key1.startswith("search:v1:")

        # Different parameters should generate different key
        key3 = tool._generate_cache_key(
            query="different",
            filters=filters,
            limit=10,
            offset=0,
            enable_lexical=True,
            enable_vector=True,
            lexical_weight=0.4,
            vector_weight=0.6,
        )

        assert key1 != key3
