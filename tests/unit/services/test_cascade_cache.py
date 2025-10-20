"""
Unit tests for CascadeCache (EPIC-10 Story 10.3).

Tests L1/L2 cascade coordination with automatic promotion.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from services.caches.cascade_cache import CascadeCache
from services.caches.code_chunk_cache import CodeChunkCache
from services.caches.redis_cache import RedisCache
from models.code_chunk_models import CodeChunkModel, ChunkType


class TestCascadeCache:
    """Test suite for CascadeCache."""

    @pytest.fixture
    def l1_cache(self):
        """Create mock L1 cache."""
        cache = MagicMock(spec=CodeChunkCache)
        cache.max_size_bytes = 100 * 1024 * 1024  # 100MB
        return cache

    @pytest.fixture
    def l2_cache(self):
        """Create mock L2 cache."""
        cache = MagicMock(spec=RedisCache)
        cache.client = MagicMock()  # Mock Redis client
        return cache

    @pytest.fixture
    def cascade_cache(self, l1_cache, l2_cache):
        """Create CascadeCache with mock L1 and L2."""
        return CascadeCache(l1_cache=l1_cache, l2_cache=l2_cache)

    @pytest.fixture
    def sample_chunks(self):
        """Sample CodeChunkModel list for testing."""
        return [
            CodeChunkModel(
                id=uuid4(),
                file_path="test.py",
                language="python",
                chunk_type=ChunkType.FUNCTION,
                name="hello",
                source_code="def hello(): pass",
                start_line=1,
                end_line=1,
                indexed_at=datetime.now(),
                metadata={"complexity": 1}
            )
        ]

    def test_cascade_cache_initialization(self, l1_cache, l2_cache):
        """Test cascade cache initializes correctly."""
        cascade = CascadeCache(l1_cache=l1_cache, l2_cache=l2_cache)

        assert cascade.l1 == l1_cache
        assert cascade.l2 == l2_cache
        assert cascade.l1_promotions == 0

    @pytest.mark.anyio
    async def test_l1_hit_fast_path(self, cascade_cache, l1_cache, l2_cache, sample_chunks):
        """Test L1 HIT (fast path) - no L2 lookup needed."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L1 HIT
        l1_cache.get.return_value = sample_chunks

        # GET from cascade
        result = await cascade_cache.get_chunks(file_path, source_code)

        # Assertions
        assert result == sample_chunks
        l1_cache.get.assert_called_once_with(file_path, source_code)
        # L2 should NOT be called (fast path)
        l2_cache.get.assert_not_called()

    @pytest.mark.anyio
    async def test_l1_miss_l2_hit_promotion(self, cascade_cache, l1_cache, l2_cache, sample_chunks):
        """Test L1 MISS → L2 HIT → auto-promote to L1."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L1 MISS
        l1_cache.get.return_value = None

        # Mock L2 HIT (returns serialized chunks)
        l2_cache.get = AsyncMock(return_value=[chunk.dict() for chunk in sample_chunks])

        # GET from cascade
        result = await cascade_cache.get_chunks(file_path, source_code)

        # Assertions
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "hello"

        # L1 should be called first
        l1_cache.get.assert_called_once_with(file_path, source_code)

        # L2 should be called after L1 miss
        l2_cache.get.assert_called_once()

        # L1 promotion should happen
        l1_cache.put.assert_called_once()
        assert cascade_cache.l1_promotions == 1

    @pytest.mark.anyio
    async def test_l1_l2_miss(self, cascade_cache, l1_cache, l2_cache):
        """Test L1 MISS → L2 MISS → return None (caller queries L3)."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L1 MISS
        l1_cache.get.return_value = None

        # Mock L2 MISS
        l2_cache.get = AsyncMock(return_value=None)

        # GET from cascade
        result = await cascade_cache.get_chunks(file_path, source_code)

        # Assertions
        assert result is None

        # Both L1 and L2 should be called
        l1_cache.get.assert_called_once_with(file_path, source_code)
        l2_cache.get.assert_called_once()

        # No promotion should happen
        l1_cache.put.assert_not_called()
        assert cascade_cache.l1_promotions == 0

    @pytest.mark.anyio
    async def test_l2_deserialization_failure(self, cascade_cache, l1_cache, l2_cache):
        """Test L2 HIT but deserialization fails → return None."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L1 MISS
        l1_cache.get.return_value = None

        # Mock L2 HIT with corrupted data
        l2_cache.get = AsyncMock(return_value=[{"invalid": "data"}])
        l2_cache.delete = AsyncMock()

        # GET from cascade
        result = await cascade_cache.get_chunks(file_path, source_code)

        # Assertions
        assert result is None

        # L2 should be invalidated due to corrupted data
        l2_cache.delete.assert_called_once()

        # No promotion should happen
        l1_cache.put.assert_not_called()

    @pytest.mark.anyio
    async def test_put_chunks_write_through(self, cascade_cache, l1_cache, l2_cache, sample_chunks):
        """Test PUT writes to both L1 and L2 (write-through strategy)."""
        file_path = "test.py"
        source_code = "def hello(): pass"
        l2_ttl = 300

        # Mock L2 set
        l2_cache.set = AsyncMock()

        # PUT to cascade
        await cascade_cache.put_chunks(file_path, source_code, sample_chunks, l2_ttl=l2_ttl)

        # Assertions
        # L1 should be populated
        l1_cache.put.assert_called_once_with(file_path, source_code, sample_chunks)

        # L2 should be populated with serialized chunks and TTL
        l2_cache.set.assert_called_once()
        call_args = l2_cache.set.call_args
        assert call_args.kwargs["ttl_seconds"] == l2_ttl

    @pytest.mark.anyio
    async def test_put_chunks_l2_failure_graceful(self, cascade_cache, l1_cache, l2_cache, sample_chunks):
        """Test PUT still populates L1 even if L2 fails (graceful degradation)."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L2 set to fail
        l2_cache.set = AsyncMock(side_effect=Exception("Redis unavailable"))

        # PUT to cascade (should not raise exception)
        await cascade_cache.put_chunks(file_path, source_code, sample_chunks)

        # L1 should still be populated
        l1_cache.put.assert_called_once_with(file_path, source_code, sample_chunks)

    @pytest.mark.anyio
    async def test_invalidate_both_layers(self, cascade_cache, l1_cache, l2_cache):
        """Test invalidate clears both L1 and L2."""
        file_path = "test.py"

        # Mock L2 flush_pattern
        l2_cache.flush_pattern = AsyncMock()

        # Invalidate
        await cascade_cache.invalidate(file_path)

        # Assertions
        l1_cache.invalidate.assert_called_once_with(file_path)
        l2_cache.flush_pattern.assert_called_once_with(f"chunks:{file_path}:*")

    @pytest.mark.anyio
    async def test_invalidate_repository(self, cascade_cache, l1_cache, l2_cache):
        """Test invalidate_repository clears entire cache."""
        repository = "my-repo"

        # Mock L2 flush_pattern
        l2_cache.flush_pattern = AsyncMock()

        # Invalidate repository
        await cascade_cache.invalidate_repository(repository)

        # Assertions
        l1_cache.clear.assert_called_once()
        l2_cache.flush_pattern.assert_called_once_with("chunks:*")

    @pytest.mark.anyio
    async def test_combined_hit_rate_calculation(self, cascade_cache, l1_cache, l2_cache):
        """Test combined L1+L2 hit rate calculation."""
        # Mock L1 stats (70% hit rate)
        l1_cache.stats.return_value = {
            "hit_rate_percent": 70.0,
            "hits": 70,
            "misses": 30
        }

        # Mock L2 stats (80% hit rate of L1 misses)
        l2_cache.stats = AsyncMock(return_value={
            "hit_rate_percent": 80.0,
            "hits": 24,  # 80% of 30 L1 misses
            "misses": 6
        })

        # Get stats
        stats = await cascade_cache.stats()

        # Expected combined hit rate: 70% + (30% × 80%) = 70% + 24% = 94%
        assert stats["cascade"]["combined_hit_rate_percent"] == 94.0
        assert stats["cascade"]["l1_hit_rate_percent"] == 70.0
        assert stats["cascade"]["l2_hit_rate_percent"] == 80.0

    @pytest.mark.anyio
    async def test_stats_structure(self, cascade_cache, l1_cache, l2_cache):
        """Test stats return correct structure."""
        # Mock L1 stats
        l1_cache.stats.return_value = {
            "hit_rate_percent": 50.0,
            "hits": 10,
            "misses": 10
        }

        # Mock L2 stats
        l2_cache.stats = AsyncMock(return_value={
            "hit_rate_percent": 60.0,
            "hits": 6,
            "misses": 4
        })

        # Get stats
        stats = await cascade_cache.stats()

        # Assertions
        assert "l1" in stats
        assert "l2" in stats
        assert "cascade" in stats

        cascade_stats = stats["cascade"]
        assert "l1_hit_rate_percent" in cascade_stats
        assert "l2_hit_rate_percent" in cascade_stats
        assert "combined_hit_rate_percent" in cascade_stats
        assert "l1_to_l2_promotions" in cascade_stats
        assert cascade_stats["strategy"] == "L1 → L2 → L3 (PostgreSQL)"

    @pytest.mark.anyio
    async def test_multiple_promotions_tracking(self, cascade_cache, l1_cache, l2_cache, sample_chunks):
        """Test L2→L1 promotions are tracked correctly."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L1 MISS, L2 HIT (3 times)
        l1_cache.get.return_value = None
        l2_cache.get = AsyncMock(return_value=[chunk.dict() for chunk in sample_chunks])

        # Perform 3 L2→L1 promotions
        await cascade_cache.get_chunks(file_path, source_code)
        await cascade_cache.get_chunks(file_path + "2", source_code)
        await cascade_cache.get_chunks(file_path + "3", source_code)

        # Assertions
        assert cascade_cache.l1_promotions == 3

    @pytest.mark.anyio
    async def test_put_chunks_default_ttl(self, cascade_cache, l1_cache, l2_cache, sample_chunks):
        """Test PUT uses default TTL of 300s for L2."""
        file_path = "test.py"
        source_code = "def hello(): pass"

        # Mock L2 set
        l2_cache.set = AsyncMock()

        # PUT without specifying TTL (should default to 300)
        await cascade_cache.put_chunks(file_path, source_code, sample_chunks)

        # L2 should be called with default TTL
        call_args = l2_cache.set.call_args
        assert call_args.kwargs["ttl_seconds"] == 300

    @pytest.mark.anyio
    async def test_hash_consistency(self, cascade_cache):
        """Test MD5 hash computation is consistent."""
        source_code = "def hello(): pass"

        # Compute hash twice
        hash1 = cascade_cache._compute_hash(source_code)
        hash2 = cascade_cache._compute_hash(source_code)

        # Should be identical
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex digest length

        # Different content should produce different hash
        hash3 = cascade_cache._compute_hash("different code")
        assert hash1 != hash3

    @pytest.mark.anyio
    async def test_combined_hit_rate_zero_division_protection(self, cascade_cache, l1_cache, l2_cache):
        """Test combined hit rate handles zero-division gracefully."""
        # Mock L1 stats (0% hit rate - edge case)
        l1_cache.stats.return_value = {
            "hit_rate_percent": 0.0,
            "hits": 0,
            "misses": 100
        }

        # Mock L2 stats (100% hit rate of L1 misses)
        l2_cache.stats = AsyncMock(return_value={
            "hit_rate_percent": 100.0,
            "hits": 100,
            "misses": 0
        })

        # Get stats
        stats = await cascade_cache.stats()

        # Combined should be: 0% + (100% × 100%) = 100%
        assert stats["cascade"]["combined_hit_rate_percent"] == 100.0
