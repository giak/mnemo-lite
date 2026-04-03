"""
Tests for MCP analytics tools.

Tests: get_indexing_stats, get_memory_health, get_cache_stats, clear_cache
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mnemo_mcp.tools.analytics_tools import (
    GetIndexingStatsTool,
    GetMemoryHealthTool,
    GetCacheStatsTool,
    ClearCacheTool,
)


class TestGetIndexingStatsTool:
    """Tests for get_indexing_stats tool."""

    def test_get_name(self):
        tool = GetIndexingStatsTool()
        assert tool.get_name() == "get_indexing_stats"

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful indexing stats retrieval."""
        tool = GetIndexingStatsTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        chunk_row = MagicMock()
        chunk_row.__getitem__ = lambda self, i: [500, 100, "2026-04-01", "2026-01-01", 3][i]
        graph_row = MagicMock()
        graph_row.__getitem__ = lambda self, i: [200, 15][i]
        edge_row = MagicMock()
        edge_row.__getitem__ = lambda self, i: [400][i]

        mock_conn.execute = AsyncMock(side_effect=[
            MagicMock(fetchone=MagicMock(return_value=chunk_row)),
            MagicMock(fetchone=MagicMock(return_value=graph_row)),
            MagicMock(fetchone=MagicMock(return_value=edge_row)),
        ])

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(repository="test-repo")

        assert result["success"] is True
        assert result["total_files"] == 100
        assert result["total_chunks"] == 500
        assert result["total_nodes"] == 200
        assert result["total_edges"] == 400
        assert result["languages"] == 3
        assert result["modules"] == 15

    @pytest.mark.asyncio
    async def test_no_engine(self):
        """Test failure when engine not available."""
        tool = GetIndexingStatsTool()
        tool.inject_services({})

        result = await tool.execute()
        assert result["success"] is False


class TestGetMemoryHealthTool:
    """Tests for get_memory_health tool."""

    def test_get_name(self):
        tool = GetMemoryHealthTool()
        assert tool.get_name() == "get_memory_health"

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful memory health retrieval."""
        tool = GetMemoryHealthTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        total_row = MagicMock()
        total_row.__getitem__ = lambda self, i: [1000][i]
        embed_row = MagicMock()
        embed_row.__getitem__ = lambda self, i: [950][i]
        type_rows = [MagicMock(__getitem__=lambda s, i: ["note", 500][i])]
        history_row = MagicMock()
        history_row.__getitem__ = lambda self, i: [15][i]
        drift_row = MagicMock()
        drift_row.__getitem__ = lambda self, i: [3][i]
        decay_row = MagicMock()
        decay_row.__getitem__ = lambda self, i: [11][i]

        mock_conn.execute = AsyncMock(side_effect=[
            MagicMock(fetchone=MagicMock(return_value=total_row)),
            MagicMock(fetchone=MagicMock(return_value=embed_row)),
            MagicMock(fetchall=MagicMock(return_value=type_rows)),
            MagicMock(fetchone=MagicMock(return_value=history_row)),
            MagicMock(fetchone=MagicMock(return_value=drift_row)),
            MagicMock(fetchone=MagicMock(return_value=decay_row)),
        ])

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute()

        assert result["success"] is True
        assert result["total_memories"] == 1000
        assert result["with_embeddings"] == 950
        assert result["embedding_coverage_pct"] == 95.0
        assert result["history_count"] == 15
        assert result["needs_consolidation"] is False  # 15 < 20
        assert result["unconsumed_drifts"] == 3
        assert result["decay_rules"] == 11

    @pytest.mark.asyncio
    async def test_no_engine(self):
        """Test failure when engine not available."""
        tool = GetMemoryHealthTool()
        tool.inject_services({})

        result = await tool.execute()
        assert result["success"] is False


class TestGetCacheStatsTool:
    """Tests for get_cache_stats tool."""

    def test_get_name(self):
        tool = GetCacheStatsTool()
        assert tool.get_name() == "get_cache_stats"

    @pytest.mark.asyncio
    async def test_with_cache_services(self):
        """Test cache stats with chunk_cache and redis."""
        tool = GetCacheStatsTool()

        mock_chunk_cache = MagicMock()
        mock_chunk_cache.l1.stats.return_value = {
            "entries": 50,
            "hits": 800,
            "misses": 200,
            "hit_rate": 0.8,
            "max_size": 100,
        }

        mock_redis = AsyncMock()
        mock_redis.info.return_value = {
            "used_memory_human": "15.2M",
            "connected_clients": 5,
        }
        mock_redis.scan = AsyncMock(side_effect=[
            (0, ["search:v1:abc", "search:v1:def"]),
            (0, ["indexing:status:repo1"]),
            (0, ["indexing:lock:repo1"]),
        ])

        tool.inject_services({
            "chunk_cache": mock_chunk_cache,
            "redis": mock_redis,
        })

        result = await tool.execute()

        assert result["success"] is True
        assert result["l1"]["entries"] == 50
        assert result["l1"]["hit_rate"] == 0.8
        assert result["l2"]["used_memory_human"] == "15.2M"
        assert len(result["redis_keys"]["search_cache"]) == 2

    @pytest.mark.asyncio
    async def test_no_cache_services(self):
        """Test cache stats when no cache services available."""
        tool = GetCacheStatsTool()
        tool.inject_services({})

        result = await tool.execute()

        assert result["success"] is True
        assert result["l1"] == {}
        assert result["l2"]["status"] == "redis not available"
