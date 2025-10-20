"""
Unit tests for RedisCache (EPIC-10 Story 10.2).

Tests L2 Redis cache with async operations, graceful degradation,
and comprehensive error handling.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.caches import RedisCache


class TestRedisCacheInitialization:
    """Test suite for RedisCache initialization."""

    def test_cache_initialization_default_url(self):
        """Test cache initializes with default Redis URL."""
        cache = RedisCache()

        assert cache.redis_url == "redis://localhost:6379/0"
        assert cache.client is None
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.errors == 0

    def test_cache_initialization_custom_url(self):
        """Test cache initializes with custom Redis URL."""
        custom_url = "redis://redis-server:6380/1"
        cache = RedisCache(redis_url=custom_url)

        assert cache.redis_url == custom_url
        assert cache.client is None


class TestRedisCacheConnection:
    """Test suite for Redis connection lifecycle."""

    @pytest_asyncio.fixture
    async def mock_redis_client(self):
        """Create mock Redis client."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.aclose = AsyncMock()
        mock_client.info = AsyncMock(return_value={
            "used_memory": 1024 * 1024,  # 1MB
            "used_memory_peak": 2 * 1024 * 1024,  # 2MB
        })
        return mock_client

    @pytest.mark.anyio
    async def test_connect_successful(self, mock_redis_client):
        """Test successful Redis connection."""
        cache = RedisCache()

        with patch('services.caches.redis_cache.redis') as mock_redis:
            mock_redis.from_url = MagicMock(return_value=mock_redis_client)

            await cache.connect()

            assert cache.client is not None
            mock_redis.from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.anyio
    async def test_connect_graceful_degradation_on_failure(self):
        """Test graceful degradation when Redis connection fails."""
        cache = RedisCache()

        with patch('services.caches.redis_cache.redis') as mock_redis:
            mock_redis.from_url = MagicMock(side_effect=Exception("Connection refused"))

            # Should not raise exception - graceful degradation
            await cache.connect()

            assert cache.client is None

    @pytest.mark.anyio
    async def test_connect_when_redis_library_not_installed(self):
        """Test graceful degradation when redis library not installed."""
        cache = RedisCache()

        with patch('services.caches.redis_cache.redis', None):
            # Should not raise exception
            await cache.connect()

            assert cache.client is None

    @pytest.mark.anyio
    async def test_disconnect(self, mock_redis_client):
        """Test Redis disconnection."""
        cache = RedisCache()
        cache.client = mock_redis_client

        await cache.disconnect()

        mock_redis_client.aclose.assert_called_once()

    @pytest.mark.anyio
    async def test_disconnect_when_not_connected(self):
        """Test disconnect when client is None."""
        cache = RedisCache()

        # Should not raise exception
        await cache.disconnect()


class TestRedisCacheOperations:
    """Test suite for Redis cache get/set/delete operations."""

    @pytest_asyncio.fixture
    async def connected_cache(self, mock_redis_client):
        """Create connected RedisCache with mock client."""
        cache = RedisCache()
        cache.client = mock_redis_client
        return cache

    @pytest_asyncio.fixture
    async def mock_redis_client(self):
        """Create mock Redis client."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.scan_iter = AsyncMock()
        mock_client.info = AsyncMock(return_value={
            "used_memory": 1024 * 1024,
            "used_memory_peak": 2 * 1024 * 1024,
        })
        return mock_client

    @pytest.mark.anyio
    async def test_get_cache_hit(self, connected_cache, mock_redis_client):
        """Test cache GET with HIT."""
        import json

        test_data = {"key": "value", "number": 42}
        mock_redis_client.get = AsyncMock(return_value=json.dumps(test_data))

        result = await connected_cache.get("test_key")

        assert result == test_data
        assert connected_cache.hits == 1
        assert connected_cache.misses == 0
        mock_redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.anyio
    async def test_get_cache_miss(self, connected_cache, mock_redis_client):
        """Test cache GET with MISS."""
        mock_redis_client.get = AsyncMock(return_value=None)

        result = await connected_cache.get("nonexistent_key")

        assert result is None
        assert connected_cache.hits == 0
        assert connected_cache.misses == 1

    @pytest.mark.anyio
    async def test_get_when_not_connected(self):
        """Test GET when client is None (graceful degradation)."""
        cache = RedisCache()

        result = await cache.get("test_key")

        assert result is None

    @pytest.mark.anyio
    async def test_get_error_handling(self, connected_cache, mock_redis_client):
        """Test GET error handling with graceful fallback."""
        mock_redis_client.get = AsyncMock(side_effect=Exception("Redis timeout"))

        result = await connected_cache.get("test_key")

        assert result is None
        assert connected_cache.errors == 1

    @pytest.mark.anyio
    async def test_set_successful(self, connected_cache, mock_redis_client):
        """Test cache SET operation."""
        test_data = {"key": "value", "nested": {"data": 123}}

        success = await connected_cache.set("test_key", test_data, ttl_seconds=60)

        assert success is True
        mock_redis_client.setex.assert_called_once()

        # Check arguments
        call_args = mock_redis_client.setex.call_args
        assert call_args[0][0] == "test_key"  # key
        # TTL as timedelta
        assert call_args[0][1].total_seconds() == 60
        # Serialized JSON
        import json
        assert json.loads(call_args[0][2]) == test_data

    @pytest.mark.anyio
    async def test_set_default_ttl(self, connected_cache, mock_redis_client):
        """Test SET with default TTL (300 seconds)."""
        await connected_cache.set("test_key", {"data": "value"})

        call_args = mock_redis_client.setex.call_args
        assert call_args[0][1].total_seconds() == 300  # Default TTL

    @pytest.mark.anyio
    async def test_set_when_not_connected(self):
        """Test SET when client is None (graceful degradation)."""
        cache = RedisCache()

        success = await cache.set("test_key", {"data": "value"})

        assert success is False

    @pytest.mark.anyio
    async def test_set_error_handling(self, connected_cache, mock_redis_client):
        """Test SET error handling."""
        mock_redis_client.setex = AsyncMock(side_effect=Exception("Redis write error"))

        success = await connected_cache.set("test_key", {"data": "value"})

        assert success is False
        assert connected_cache.errors == 1

    @pytest.mark.anyio
    async def test_delete_successful(self, connected_cache, mock_redis_client):
        """Test DELETE operation."""
        success = await connected_cache.delete("test_key")

        assert success is True
        mock_redis_client.delete.assert_called_once_with("test_key")

    @pytest.mark.anyio
    async def test_delete_when_not_connected(self):
        """Test DELETE when client is None."""
        cache = RedisCache()

        success = await cache.delete("test_key")

        assert success is False

    @pytest.mark.anyio
    async def test_delete_error_handling(self, connected_cache, mock_redis_client):
        """Test DELETE error handling."""
        mock_redis_client.delete = AsyncMock(side_effect=Exception("Redis delete error"))

        success = await connected_cache.delete("test_key")

        assert success is False
        assert connected_cache.errors == 1


class TestRedisCachePatternFlush:
    """Test suite for pattern-based cache invalidation."""

    @pytest_asyncio.fixture
    async def mock_redis_client_with_keys(self):
        """Create mock Redis client with scan_iter support."""
        mock_client = AsyncMock()

        # Mock async iterator for scan_iter
        async def async_keys_iter(*args, **kwargs):
            for key in ["search:test1", "search:test2", "search:test3"]:
                yield key

        mock_client.scan_iter = MagicMock(return_value=async_keys_iter())
        mock_client.delete = AsyncMock(return_value=3)
        mock_client.info = AsyncMock(return_value={
            "used_memory": 1024,
            "used_memory_peak": 2048,
        })
        return mock_client

    @pytest.mark.anyio
    async def test_flush_pattern_successful(self, mock_redis_client_with_keys):
        """Test flush_pattern deletes matching keys."""
        cache = RedisCache()
        cache.client = mock_redis_client_with_keys

        deleted = await cache.flush_pattern("search:*")

        assert deleted == 3
        mock_redis_client_with_keys.scan_iter.assert_called_once_with(match="search:*")
        mock_redis_client_with_keys.delete.assert_called_once()

    @pytest.mark.anyio
    async def test_flush_pattern_no_matches(self):
        """Test flush_pattern when no keys match."""
        mock_client = AsyncMock()

        # Empty async iterator
        async def empty_iter(*args, **kwargs):
            return
            yield  # Make it a generator

        mock_client.scan_iter = MagicMock(return_value=empty_iter())

        cache = RedisCache()
        cache.client = mock_client

        deleted = await cache.flush_pattern("nonexistent:*")

        assert deleted == 0

    @pytest.mark.anyio
    async def test_flush_pattern_when_not_connected(self):
        """Test flush_pattern when client is None."""
        cache = RedisCache()

        deleted = await cache.flush_pattern("test:*")

        assert deleted == 0

    @pytest.mark.anyio
    async def test_flush_pattern_error_handling(self):
        """Test flush_pattern error handling."""
        mock_client = AsyncMock()
        mock_client.scan_iter = MagicMock(side_effect=Exception("Redis scan error"))

        cache = RedisCache()
        cache.client = mock_client

        deleted = await cache.flush_pattern("test:*")

        assert deleted == 0
        assert cache.errors == 1


class TestRedisCacheStats:
    """Test suite for cache statistics."""

    @pytest.mark.anyio
    async def test_stats_when_connected(self):
        """Test stats returns complete metrics when connected."""
        mock_client = AsyncMock()
        mock_client.info = AsyncMock(return_value={
            "used_memory": 5 * 1024 * 1024,  # 5MB
            "used_memory_peak": 10 * 1024 * 1024,  # 10MB
        })

        cache = RedisCache()
        cache.client = mock_client
        cache.hits = 80
        cache.misses = 20
        cache.errors = 5

        stats = await cache.stats()

        assert stats["type"] == "L2_redis"
        assert stats["connected"] is True
        assert stats["hits"] == 80
        assert stats["misses"] == 20
        assert stats["errors"] == 5
        assert stats["hit_rate_percent"] == 80.0  # 80/100
        assert stats["memory_used_mb"] == 5.0
        assert stats["memory_peak_mb"] == 10.0

    @pytest.mark.anyio
    async def test_stats_when_not_connected(self):
        """Test stats returns basic metrics when not connected."""
        cache = RedisCache()
        cache.hits = 10
        cache.misses = 5

        stats = await cache.stats()

        assert stats["type"] == "L2_redis"
        assert stats["connected"] is False
        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["hit_rate_percent"] == 66.67  # 10/15
        assert stats["memory_used_mb"] == 0
        assert stats["memory_peak_mb"] == 0

    @pytest.mark.anyio
    async def test_stats_zero_requests(self):
        """Test stats with zero requests (avoid division by zero)."""
        cache = RedisCache()

        stats = await cache.stats()

        assert stats["hit_rate_percent"] == 0

    @pytest.mark.anyio
    async def test_stats_redis_info_error(self):
        """Test stats handles Redis info() error gracefully."""
        mock_client = AsyncMock()
        mock_client.info = AsyncMock(side_effect=Exception("Info command failed"))

        cache = RedisCache()
        cache.client = mock_client

        # Should not raise exception
        stats = await cache.stats()

        assert stats["connected"] is True
        assert stats["memory_used_mb"] == 0  # Fallback to 0


class TestRedisCacheComplexDataTypes:
    """Test suite for complex data type serialization."""

    @pytest_asyncio.fixture
    async def connected_cache(self):
        """Create connected RedisCache with real-ish mock."""
        mock_client = AsyncMock()

        # Storage for testing serialization
        storage = {}

        async def mock_get(key):
            return storage.get(key)

        async def mock_setex(key, ttl, value):
            storage[key] = value
            return True

        mock_client.get = mock_get
        mock_client.setex = mock_setex
        mock_client.info = AsyncMock(return_value={
            "used_memory": 1024,
            "used_memory_peak": 2048,
        })

        cache = RedisCache()
        cache.client = mock_client
        return cache

    @pytest.mark.anyio
    async def test_nested_dict_serialization(self, connected_cache):
        """Test nested dictionary serialization/deserialization."""
        complex_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": 42,
                        "list": [1, 2, 3],
                    }
                }
            },
            "array": [{"item": 1}, {"item": 2}],
        }

        await connected_cache.set("complex", complex_data)
        result = await connected_cache.get("complex")

        assert result == complex_data

    @pytest.mark.anyio
    async def test_list_serialization(self, connected_cache):
        """Test list serialization."""
        data = [1, 2, 3, {"nested": "value"}, [4, 5, 6]]

        await connected_cache.set("list", data)
        result = await connected_cache.get("list")

        assert result == data

    @pytest.mark.anyio
    async def test_none_value_serialization(self, connected_cache):
        """Test None value serialization."""
        await connected_cache.set("none_key", None)
        result = await connected_cache.get("none_key")

        assert result is None

    @pytest.mark.anyio
    async def test_boolean_serialization(self, connected_cache):
        """Test boolean serialization."""
        await connected_cache.set("true_key", True)
        await connected_cache.set("false_key", False)

        assert await connected_cache.get("true_key") is True
        assert await connected_cache.get("false_key") is False

    @pytest.mark.anyio
    async def test_number_serialization(self, connected_cache):
        """Test number serialization (int, float)."""
        await connected_cache.set("int", 42)
        await connected_cache.set("float", 3.14159)

        assert await connected_cache.get("int") == 42
        assert await connected_cache.get("float") == 3.14159


class TestRedisCacheMetricsTracking:
    """Test suite for hits/misses/errors tracking."""

    @pytest.mark.anyio
    async def test_hits_counter_increments(self):
        """Test hits counter increments on cache HIT."""
        import json

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=json.dumps({"data": "value"}))

        cache = RedisCache()
        cache.client = mock_client

        await cache.get("key1")
        await cache.get("key2")
        await cache.get("key3")

        assert cache.hits == 3
        assert cache.misses == 0

    @pytest.mark.anyio
    async def test_misses_counter_increments(self):
        """Test misses counter increments on cache MISS."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)

        cache = RedisCache()
        cache.client = mock_client

        await cache.get("key1")
        await cache.get("key2")

        assert cache.hits == 0
        assert cache.misses == 2

    @pytest.mark.anyio
    async def test_errors_counter_increments(self):
        """Test errors counter increments on exceptions."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Redis error"))
        mock_client.setex = AsyncMock(side_effect=Exception("Redis error"))
        mock_client.delete = AsyncMock(side_effect=Exception("Redis error"))

        cache = RedisCache()
        cache.client = mock_client

        await cache.get("key1")
        await cache.set("key2", "value")
        await cache.delete("key3")

        assert cache.errors == 3

    @pytest.mark.anyio
    async def test_mixed_operations_tracking(self):
        """Test accurate tracking with mixed HIT/MISS/ERROR operations."""
        import json

        mock_client = AsyncMock()

        # Key1: HIT, Key2: MISS, Key3: ERROR
        async def mock_get(key):
            if key == "key1":
                return json.dumps({"data": "value"})
            elif key == "key2":
                return None
            else:
                raise Exception("Redis timeout")

        mock_client.get = mock_get

        cache = RedisCache()
        cache.client = mock_client

        await cache.get("key1")  # HIT
        await cache.get("key2")  # MISS
        await cache.get("key3")  # ERROR

        assert cache.hits == 1
        assert cache.misses == 1
        assert cache.errors == 1
