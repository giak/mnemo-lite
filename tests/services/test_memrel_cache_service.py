"""Tests for EPIC-29: Memory Relationship Cache Service."""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from services.memrel_cache_service import MemRelCacheService


class TestMemRelCacheService:
    """Tests for MemRelCacheService."""

    @pytest.mark.asyncio
    async def test_get_related_cache_hit(self):
        """Test returns cached data on hit."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps([{"memory_id": "mem-2", "depth": 1}]))

        service = MemRelCacheService(redis_client=mock_redis)
        result = await service.get_related("mem-1", max_depth=1)

        assert result == [{"memory_id": "mem-2", "depth": 1}]
        mock_redis.get.assert_called_once_with("memrel:mem-1:d1")

    @pytest.mark.asyncio
    async def test_get_related_cache_miss(self):
        """Test returns None on miss."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        service = MemRelCacheService(redis_client=mock_redis)
        result = await service.get_related("mem-1", max_depth=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_set_related(self):
        """Test caches related memories."""
        mock_redis = AsyncMock()

        service = MemRelCacheService(redis_client=mock_redis)
        await service.set_related("mem-1", max_depth=1, data=[{"id": "mem-2"}], ttl=300)

        mock_redis.setex.assert_called_once_with(
            "memrel:mem-1:d1", 300, json.dumps([{"id": "mem-2"}])
        )

    @pytest.mark.asyncio
    async def test_get_graph_cache_hit(self):
        """Test returns cached graph data on hit."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"nodes": [], "edges": []}))

        service = MemRelCacheService(redis_client=mock_redis)
        result = await service.get_graph(min_score=0.3)

        assert result == {"nodes": [], "edges": []}

    @pytest.mark.asyncio
    async def test_set_graph(self):
        """Test caches graph data."""
        mock_redis = AsyncMock()

        service = MemRelCacheService(redis_client=mock_redis)
        await service.set_graph(min_score=0.3, data={"nodes": [], "edges": []}, ttl=600)

        mock_redis.setex.assert_called_once_with(
            "memgraph:min0.3", 600, json.dumps({"nodes": [], "edges": []})
        )

    @pytest.mark.asyncio
    async def test_invalidate_memory(self):
        """Test invalidates all caches for a memory."""
        mock_redis = AsyncMock()

        service = MemRelCacheService(redis_client=mock_redis)
        await service.invalidate_memory("mem-1")

        # Should delete depth 1-3 caches
        assert mock_redis.delete.call_count >= 3
        calls = [c[0][0] for c in mock_redis.delete.call_args_list]
        assert "memrel:mem-1:d1" in calls
        assert "memrel:mem-1:d2" in calls
        assert "memrel:mem-1:d3" in calls

    @pytest.mark.asyncio
    async def test_no_redis(self):
        """Test graceful degradation when Redis is unavailable."""
        service = MemRelCacheService(redis_client=None)

        assert await service.get_related("mem-1", 1) is None
        assert await service.get_graph(0.3) is None
        # Should not raise
        await service.set_related("mem-1", 1, [])
        await service.set_graph(0.3, {})
        await service.invalidate_memory("mem-1")
