"""
Tests for MCP memory search tool.

Tests cover:
- Tag-only search (embeddings disabled in MCP tools)
- Cache hit/miss behavior
- Input validation (empty query, invalid memory_type, limits)
- Tag query detection (sys:* queries skip embedding)
- Correct attribute access on search results
- Regression: is_tag_query bug fix (NameError)
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from mnemo_mcp.tools.memory_tools import SearchMemoryTool
from mnemo_mcp.models.memory_models import MemoryType


# ---------------------------------------------------------------------------
# Mock dataclasses matching the real HybridMemorySearch* structures exactly
# ---------------------------------------------------------------------------

@dataclass
class MockHybridMemorySearchResult:
    """Mock matching HybridMemorySearchResult from hybrid_memory_search_service."""
    memory_id: str
    rrf_score: float
    rank: int
    title: str
    content_preview: str
    memory_type: str
    tags: List[str]
    created_at: str
    author: Optional[str] = None
    lexical_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    rerank_score: Optional[float] = None
    contribution: Dict[str, float] = None

    def __post_init__(self):
        if self.contribution is None:
            self.contribution = {}


@dataclass
class MockHybridMemorySearchMetadata:
    """Mock matching HybridMemorySearchMetadata."""
    total_results: int
    lexical_count: int
    vector_count: int
    unique_after_fusion: int
    lexical_enabled: bool
    vector_enabled: bool
    lexical_weight: float
    vector_weight: float
    execution_time_ms: float
    reranking_enabled: bool = False
    lexical_time_ms: Optional[float] = None
    vector_time_ms: Optional[float] = None
    fusion_time_ms: Optional[float] = None
    reranking_time_ms: Optional[float] = None


@dataclass
class MockHybridMemorySearchResponse:
    """Mock matching HybridMemorySearchResponse."""
    results: List[MockHybridMemorySearchResult]
    metadata: MockHybridMemorySearchMetadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx


@pytest.fixture
def mock_embedding_service():
    service = AsyncMock()
    service.generate_embedding.return_value = [0.1] * 768
    return service


@pytest.fixture
def mock_hybrid_search_service():
    return AsyncMock()


@pytest.fixture
def mock_memory_repository():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def sample_hybrid_results():
    return [
        MockHybridMemorySearchResult(
            memory_id="aaa-bbb-ccc",
            rrf_score=0.95,
            rank=1,
            title="DSA censure investigation",
            content_preview="The DSA mass censorship investigation found...",
            memory_type="investigation",
            tags=["sys:pattern", "dsa"],
            created_at="2026-04-01T10:00:00Z",
            author="Claude",
            lexical_score=0.8,
            vector_similarity=0.9,
        ),
        MockHybridMemorySearchResult(
            memory_id="ddd-eee-fff",
            rrf_score=0.72,
            rank=2,
            title="Foreign interference notes",
            content_preview="Notes on foreign electoral interference...",
            memory_type="note",
            tags=["sys:core"],
            created_at="2026-03-28T15:00:00Z",
            author="User",
            lexical_score=0.6,
            vector_similarity=0.75,
        ),
    ]


@pytest.fixture
def sample_hybrid_response(sample_hybrid_results):
    return MockHybridMemorySearchResponse(
        results=sample_hybrid_results,
        metadata=MockHybridMemorySearchMetadata(
            total_results=2,
            lexical_count=2,
            vector_count=2,
            unique_after_fusion=2,
            lexical_enabled=True,
            vector_enabled=True,
            lexical_weight=0.5,
            vector_weight=0.5,
            execution_time_ms=45.2,
        ),
    )


def _make_mock_memory(
    memory_id="111-222-333",
    title="Test Memory",
    content="Test content here",
    memory_type_value="note",
    tags=None,
    created_at_iso="2026-04-01T00:00:00Z"
):
    """Helper to create a MagicMock memory object."""
    mock = MagicMock()
    mock.id = memory_id
    mock.title = title
    mock.content = content
    mock.memory_type = MagicMock(value=memory_type_value)
    mock.tags = tags or []
    mock.created_at = MagicMock()
    mock.created_at.isoformat.return_value = created_at_iso
    mock.similarity_score = None  # Prevent MagicMock default from getattr
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchMemoryTool:
    """Unit tests for SearchMemoryTool."""

    def test_get_name(self):
        tool = SearchMemoryTool()
        assert tool.get_name() == "search_memory"

    # ---- Tag-only search (current MCP behavior — embeddings disabled) ----

    @pytest.mark.asyncio
    async def test_tag_only_search_no_embedding(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Test tag-only search skips embedding generation."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="111-222-333",
            title="Core protocol",
            content="This is the core protocol content.",
            tags=["sys:protocol"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None  # cache miss

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="sys:protocol",
            tags=["sys:protocol"],
            limit=10,
        )

        assert result["metadata"]["search_mode"] == "tag_only"
        assert len(result["memories"]) == 1
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_tag_query_detection_no_embedding(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Test that queries starting with sys: work correctly."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="444-555-666",
            title="History memory",
            content="Historical data",
            tags=["sys:history"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="sys:history",
            limit=5,
        )

        assert result["metadata"]["search_mode"] == "tag_only"
        assert len(result["memories"]) == 1

    # ---- Regression: is_tag_query NameError bug fix ----

    @pytest.mark.asyncio
    async def test_regression_is_tag_query_no_nameerror(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """
        Regression test: ensure is_tag_query NameError does not recur.

        Bug: line 773 referenced undefined variable `is_tag_query` instead
        of `is_tag_only`, causing NameError on every search_memory call
        when falling back to tag-only search.
        """
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="regression-test-id",
            title="Regression test",
            content="Content for regression test",
            tags=["test"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        # This should NOT raise NameError
        result = await tool.execute(
            ctx=mock_ctx,
            query="regression test",
            limit=5,
        )

        assert len(result["memories"]) == 1
        assert result["memories"][0]["id"] == "regression-test-id"
        # P2: free-text query without search_mode now uses the text fallback
        assert result["metadata"]["search_mode"] == "text"

    # ---- Input validation ----

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, mock_ctx):
        """Test that empty query raises ValueError."""
        tool = SearchMemoryTool()
        tool.inject_services({})

        with pytest.raises(ValueError, match="Query or tags is required"):
            await tool.execute(ctx=mock_ctx, query="")

    @pytest.mark.asyncio
    async def test_whitespace_query_raises(self, mock_ctx):
        """Test that whitespace-only query raises ValueError."""
        tool = SearchMemoryTool()
        tool.inject_services({})

        with pytest.raises(ValueError, match="Query or tags is required"):
            await tool.execute(ctx=mock_ctx, query="   ")

    @pytest.mark.asyncio
    async def test_empty_query_with_tags_succeeds(self, mock_ctx, mock_memory_repository, mock_redis):
        """Test that empty query with tags is valid (tag-only listing mode)."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="tag-list-id",
            title="Tag list result",
            content="Content",
            tags=["sys:core"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query=None,
            tags=["sys:core"],
            limit=5,
        )

        assert len(result["memories"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_memory_type_raises(self, mock_ctx):
        """Test that invalid memory_type raises ValueError."""
        tool = SearchMemoryTool()
        tool.inject_services({})

        with pytest.raises(ValueError, match="Invalid memory_type"):
            await tool.execute(ctx=mock_ctx, query="test", memory_type="invalid_type")

    @pytest.mark.asyncio
    async def test_valid_memory_types_accepted(self, mock_ctx, mock_memory_repository, mock_redis):
        """Test that all valid memory types are accepted."""
        mock_mem = _make_mock_memory()
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool = SearchMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        for mt in ["note", "decision", "task", "reference", "conversation", "investigation"]:
            result = await tool.execute(
                ctx=mock_ctx,
                query="test",
                memory_type=mt,
                limit=1,
            )
            assert "memories" in result

    @pytest.mark.asyncio
    async def test_limit_clamped_to_50(self, mock_ctx, mock_memory_repository, mock_redis):
        """Test that limit is clamped to max 50."""
        mock_mem = _make_mock_memory()
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool = SearchMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(ctx=mock_ctx, query="test", limit=100)
        assert result["limit"] == 50

    @pytest.mark.asyncio
    async def test_limit_minimum_1(self, mock_ctx, mock_memory_repository, mock_redis):
        """Test that limit minimum is 1."""
        mock_mem = _make_mock_memory()
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool = SearchMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(ctx=mock_ctx, query="test", limit=0)
        assert result["limit"] == 1

    # ---- Tag normalization ----

    @pytest.mark.asyncio
    async def test_string_tags_converted_to_list(self, mock_ctx, mock_memory_repository, mock_redis):
        """Test that string tags are converted to list."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="777-888-999",
            title="Test",
            content="Content",
            tags=["sys:core"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="sys:core",
            tags="sys:core",
            limit=5,
        )

        assert result["metadata"]["search_mode"] == "tag_only"

    # ---- Cache behavior ----

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(
        self, mock_ctx, mock_redis
    ):
        """Test that cache hit returns cached data without searching."""
        tool = SearchMemoryTool()

        cached_result = {
            "query": "cached query",
            "memories": [{"id": "cached-id", "title": "Cached"}],
            "total": 1,
            "metadata": {"search_mode": "hybrid"}
        }
        mock_redis.get.return_value = json.dumps(cached_result)

        tool.inject_services({
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="cached query",
            limit=5,
        )

        assert result["memories"][0]["id"] == "cached-id"
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_search_and_writes_cache(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Test that cache miss calls search and writes to cache."""
        mock_mem = _make_mock_memory()
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None  # explicit cache miss

        tool = SearchMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="uncached query",
            search_mode="tag",  # explicite : un résultat dégradé (défaut hybrid sans embedding) n'est jamais caché (EPIC-80)
            limit=5,
        )

        assert len(result["memories"]) == 1
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_differs_by_search_mode(
        self, mock_ctx, mock_memory_repository, mock_redis,
        mock_hybrid_search_service, sample_hybrid_response
    ):
        """EPIC-80: la clé cache intègre search_mode.

        Même requête en mode tag puis en mode hybrid → deux clés distinctes :
        le résultat d'un mode ne peut pas être servi à l'autre (avant EPIC-80 :
        clé partagée, un résultat hybrid dégradé était servi à une recherche tag).
        """
        mock_mem = _make_mock_memory(
            memory_id="mode-key-id", title="Mode key", content="Content", tags=[],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None  # cache miss à chaque appel

        mock_embedding = AsyncMock()
        mock_embedding.generate_embedding.return_value = [0.1] * 768
        mock_hybrid_search_service.search.return_value = sample_hybrid_response

        tool = SearchMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "embedding_service": mock_embedding,
            "hybrid_memory_search_service": mock_hybrid_search_service,
            "redis": mock_redis,
        })

        # Mode tag (explicite) → fallback text, cache écrit sous clé A
        await tool.execute(ctx=mock_ctx, query="DSA censorship", search_mode="tag", limit=5)
        # Mode hybrid → succès embedding, cache écrit sous clé B
        await tool.execute(ctx=mock_ctx, query="DSA censorship", search_mode="hybrid", limit=5)

        # Les 2 recherches ont tourné (2 misses, 2 writes) et les clés diffèrent
        assert mock_redis.get.call_count == 2
        assert mock_redis.setex.call_count == 2
        key_a = mock_redis.setex.call_args_list[0][0][0]
        key_b = mock_redis.setex.call_args_list[1][0][0]
        assert key_a != key_b

    @pytest.mark.asyncio
    async def test_degraded_hybrid_result_not_cached(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """EPIC-80: un résultat dégradé (embedding en échec) ne doit jamais être mis en cache.

        Il est transitoire (cold start) : même sous sa propre clé de mode, il serait
        servi à une recherche ultérieure du même mode dont l'embedding aurait réussi.
        """
        mock_embedding = AsyncMock()
        mock_embedding.generate_embedding.side_effect = RuntimeError("Model unavailable")

        mock_mem = _make_mock_memory(
            memory_id="degraded-nocache",
            title="Degraded",
            content="Content when embedding fails",
            tags=[],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool = SearchMemoryTool()
        tool.inject_services({
            "embedding_service": mock_embedding,
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="test query",
            search_mode="hybrid",
            limit=5,
        )

        # Le fallback fonctionne et est signalé...
        assert result["metadata"]["embedding_failed"] is True
        assert result["metadata"]["search_mode"] == "text"
        # ... mais rien n'est mis en cache
        mock_redis.setex.assert_not_called()

    # ---- Fallback when hybrid service unavailable ----

    @pytest.mark.asyncio
    async def test_fallback_to_repository_search(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Test fallback when hybrid_memory_search_service is not available."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="fallback-id",
            title="Fallback result",
            content="Fallback content here",
            tags=["test"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="fallback test",
            limit=5,
        )

        assert len(result["memories"]) == 1
        assert result["memories"][0]["id"] == "fallback-id"
        assert result["memories"][0]["title"] == "Fallback result"

    # ---- P2: text fallback (query without search_mode) ----

    @pytest.mark.asyncio
    async def test_query_without_search_mode_uses_text_fallback(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Query without search_mode must use search_by_tags with query_text, never tag=[query]."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="text-id",
            title="Parrainages 2022",
            content="Asselineau a recueilli 293 parrainages",
            tags=["kernel"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="Asselineau 293",
            limit=5,
        )

        assert len(result["memories"]) == 1
        assert result["metadata"]["search_mode"] == "text"
        call_kwargs = mock_memory_repository.search_by_tags.call_args.kwargs
        assert call_kwargs["query_text"] == "Asselineau 293"

    @pytest.mark.asyncio
    async def test_colon_free_text_uses_text_fallback(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Free text with a French colon must NOT be treated as a tag lookup."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="colon-id",
            title="Loi 76-528",
            content="loi du 18 juin 1976 parrainages",
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(ctx=mock_ctx, query="loi 76-528 : parrainages", limit=5)

        assert result["metadata"]["search_mode"] == "text"
        call_kwargs = mock_memory_repository.search_by_tags.call_args.kwargs
        assert call_kwargs["query_text"] == "loi 76-528 : parrainages"

    @pytest.mark.asyncio
    async def test_multi_colon_tag_uses_tag_lookup(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Nested tags (sys:pattern:candidate) must be treated as a tag lookup, not free text."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="nested-tag-id",
            title="Nested",
            content="x",
            tags=["sys:pattern:candidate"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(ctx=mock_ctx, query="sys:pattern:candidate", limit=5)

        assert result["metadata"]["search_mode"] == "tag_only"
        filters = mock_memory_repository.search_by_tags.call_args.kwargs["filters"]
        assert filters.tags == ["sys:pattern:candidate"]

    @pytest.mark.asyncio
    async def test_tags_without_query_stays_tag_only(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Tags-only listing must keep using search_by_tags without query_text."""
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(memory_id="tag-id", title="Tagged", content="x", tags=["sys:anchor"])
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query=None,
            tags=["sys:anchor"],
            limit=5,
        )

        assert result["metadata"]["search_mode"] == "tag_only"
        call_kwargs = mock_memory_repository.search_by_tags.call_args.kwargs
        assert call_kwargs.get("query_text") is None

    # ---- P5-a: conversations excluded by default ----

    @pytest.mark.asyncio
    async def test_fallback_excludes_conversations_by_default(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Text fallback must exclude memory_type=conversation when no memory_type filter given."""
        tool = SearchMemoryTool()

        mock_memory_repository.search_by_tags.return_value = ([], 0)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        await tool.execute(ctx=mock_ctx, query="parrainages", limit=5)

        filters = mock_memory_repository.search_by_tags.call_args.kwargs["filters"]
        assert filters.exclude_conversations is True

    @pytest.mark.asyncio
    async def test_explicit_memory_type_disables_conversation_exclusion(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Explicit memory_type=conversation must disable the exclusion."""
        tool = SearchMemoryTool()

        mock_memory_repository.search_by_tags.return_value = ([], 0)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        await tool.execute(
            ctx=mock_ctx,
            query=None,
            tags=["kernel"],
            memory_type="conversation",
            limit=5,
        )

        filters = mock_memory_repository.search_by_tags.call_args.kwargs["filters"]
        assert filters.exclude_conversations is False

    # ---- Error handling ----

    @pytest.mark.asyncio
    async def test_embedding_failure_falls_back_to_text_search(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Test that embedding failure falls back to text search (not tag=[query])."""
        tool = SearchMemoryTool()

        mock_embedding = AsyncMock()
        mock_embedding.generate_embedding.side_effect = RuntimeError("Model unavailable")

        mock_mem = _make_mock_memory(
            memory_id="fallback-embed",
            title="Embedding fallback",
            content="Content when embedding fails",
            tags=[],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "embedding_service": mock_embedding,
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="test query",
            limit=5,
        )

        assert len(result["memories"]) == 1
        # P2: query without search_mode → text fallback (even when hybrid embedding failed)
        assert result["metadata"]["search_mode"] == "text"
        call_kwargs = mock_memory_repository.search_by_tags.call_args.kwargs
        assert call_kwargs.get("query_text") == "test query"

    @pytest.mark.asyncio
    async def test_hybrid_embedding_failure_reports_fallback(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """EPIC-79 Story 79.2: search_mode=hybrid avec embedding en échec expose le fallback.

        La réponse doit signaler embedding_failed: true + embedding_fallback_reason
        + requested_search_mode: hybrid, pour que l'agent voie la dégradation
        (avant : fallback silencieux en search_mode: text).
        """
        tool = SearchMemoryTool()

        mock_embedding = AsyncMock()
        mock_embedding.generate_embedding.side_effect = RuntimeError("Model unavailable")

        mock_mem = _make_mock_memory(
            memory_id="fallback-hybrid",
            title="Hybrid fallback",
            content="Content when hybrid embedding fails",
            tags=[],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "embedding_service": mock_embedding,
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="test query",
            search_mode="hybrid",
            limit=5,
        )

        # Le fallback fonctionne (résilience préservée)
        assert len(result["memories"]) == 1
        assert result["metadata"]["search_mode"] == "text"
        # ... mais n'est plus silencieux : la dégradation est visible
        assert result["metadata"]["requested_search_mode"] == "hybrid"
        assert result["metadata"]["embedding_failed"] is True
        assert "Model unavailable" in result["metadata"]["embedding_fallback_reason"]

    @pytest.mark.asyncio
    async def test_hybrid_success_reports_no_fallback(
        self, mock_ctx, mock_memory_repository, mock_redis,
        mock_hybrid_search_service, sample_hybrid_response
    ):
        """EPIC-79 Story 79.2: hybrid réussi → embedding_failed: false, pas de fallback_reason."""
        tool = SearchMemoryTool()

        mock_embedding = AsyncMock()
        mock_embedding.generate_embedding.return_value = [0.1] * 768
        mock_hybrid_search_service.search.return_value = sample_hybrid_response
        mock_redis.get.return_value = None

        tool.inject_services({
            "embedding_service": mock_embedding,
            "memory_repository": mock_memory_repository,
            "hybrid_memory_search_service": mock_hybrid_search_service,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="DSA censorship",
            search_mode="hybrid",
            limit=5,
        )

        assert result["metadata"]["search_mode"] == "hybrid"
        assert result["metadata"]["requested_search_mode"] == "hybrid"
        assert result["metadata"]["embedding_failed"] is False
        assert "embedding_fallback_reason" not in result["metadata"]
        assert len(result["memories"]) == 2

    @pytest.mark.asyncio
    async def test_hybrid_no_embedding_service_reports_fallback(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """EPIC-79 Story 79.2 (review): hybrid demandé sans service d'embedding → signalé.

        Avant : le fallback était silencieux (embedding_failed restait False par défaut
        car le bloc embedding est sauté). Après : embedding_failed: true +
        embedding_fallback_reason: "no_embedding_service".
        """
        tool = SearchMemoryTool()

        mock_mem = _make_mock_memory(
            memory_id="fallback-nosvc",
            title="No service fallback",
            content="Content when no embedding service",
            tags=[],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="test query",
            search_mode="hybrid",
            limit=5,
        )

        assert len(result["memories"]) == 1
        assert result["metadata"]["search_mode"] == "text"
        assert result["metadata"]["requested_search_mode"] == "hybrid"
        assert result["metadata"]["embedding_failed"] is True
        assert result["metadata"]["embedding_fallback_reason"] == "no_embedding_service"

    # ---- Response structure ----

    @pytest.mark.asyncio
    async def test_response_structure(
        self, mock_ctx, mock_memory_repository, mock_redis
    ):
        """Test that response has all required fields."""
        mock_mem = _make_mock_memory(
            memory_id="struct-id",
            title="Structure test",
            content="Content for structure test",
            tags=["test"],
        )
        mock_memory_repository.search_by_tags.return_value = ([mock_mem], 1)
        mock_redis.get.return_value = None

        tool = SearchMemoryTool()
        tool.inject_services({
            "memory_repository": mock_memory_repository,
            "redis": mock_redis,
        })

        result = await tool.execute(
            ctx=mock_ctx,
            query="structure test",
            limit=5,
            offset=0,
        )

        # Top-level fields
        assert "query" in result
        assert "memories" in result
        assert "total" in result
        assert "limit" in result
        assert "offset" in result
        assert "has_more" in result
        assert "metadata" in result

        # Metadata fields
        meta = result["metadata"]
        assert "search_mode" in meta
        assert "embedding_time_ms" in meta

        # Memory fields
        for m in result["memories"]:
            assert "id" in m
            assert "title" in m
            assert "content_preview" in m
            assert "memory_type" in m
            assert "tags" in m
            assert "created_at" in m
            assert "highlights" in m
