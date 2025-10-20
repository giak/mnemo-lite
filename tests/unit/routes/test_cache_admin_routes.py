"""
Unit tests for Cache Admin Routes (EPIC-10 Story 10.4).

Tests manual cache invalidation endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from routes import cache_admin_routes
from services.caches.cascade_cache import CascadeCache
from services.caches.code_chunk_cache import CodeChunkCache
from services.caches.redis_cache import RedisCache


@pytest.fixture
def app():
    """Create test FastAPI app with cache admin routes."""
    test_app = FastAPI()
    test_app.include_router(cache_admin_routes.router)
    return test_app


@pytest.fixture
def mock_cascade_cache():
    """Create mock CascadeCache for testing."""
    cascade = MagicMock(spec=CascadeCache)

    # Mock L1 and L2 caches
    cascade.l1 = MagicMock(spec=CodeChunkCache)
    cascade.l2 = MagicMock(spec=RedisCache)

    # Mock async methods
    cascade.invalidate = AsyncMock()
    cascade.invalidate_repository = AsyncMock()
    cascade.l2.flush_pattern = AsyncMock()
    cascade.stats = AsyncMock(return_value={
        "l1": {
            "type": "L1_memory",
            "size_mb": 25.3,
            "max_size_mb": 100.0,
            "entries": 142,
            "hits": 1523,
            "misses": 287,
            "hit_rate_percent": 84.1,
            "utilization_percent": 25.3
        },
        "l2": {
            "type": "L2_redis",
            "connected": True,
            "hits": 215,
            "misses": 72,
            "hit_rate_percent": 74.9,
            "memory_used_mb": 45.2,
            "memory_peak_mb": 52.1
        },
        "cascade": {
            "l1_hit_rate_percent": 84.1,
            "l2_hit_rate_percent": 74.9,
            "combined_hit_rate_percent": 92.3,
            "l1_to_l2_promotions": 215,
            "strategy": "L1 → L2 → L3 (PostgreSQL)"
        }
    })

    return cascade


class TestCacheAdminRoutes:
    """Test suite for cache admin routes."""

    @pytest.mark.anyio
    async def test_flush_cache_file_scope(self, app, mock_cascade_cache):
        """Test flushing cache for specific file."""
        file_path = "src/utils/helper.py"

        # Override dependency
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/cache/flush",
                json={
                    "scope": "file",
                    "file_path": file_path
                }
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["scope"] == "file"
        assert data["target"] == file_path
        assert "Cache invalidated for file" in data["message"]

        # Verify invalidate was called
        mock_cascade_cache.invalidate.assert_called_once_with(file_path)

    @pytest.mark.anyio
    async def test_flush_cache_repository_scope(self, app, mock_cascade_cache):
        """Test flushing cache for entire repository."""
        repository = "my-repo"

        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/cache/flush",
                json={
                    "scope": "repository",
                    "repository": repository
                }
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["scope"] == "repository"
        assert data["target"] == repository
        assert "Cache invalidated for repository" in data["message"]

        # Verify invalidate_repository was called
        mock_cascade_cache.invalidate_repository.assert_called_once_with(repository)

    @pytest.mark.anyio
    async def test_flush_cache_all_scope(self, app, mock_cascade_cache):
        """Test flushing entire L1+L2 cache."""
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/cache/flush",
                json={
                    "scope": "all"
                }
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["scope"] == "all"
        assert "All caches flushed" in data["message"]

        # Verify L1 and L2 were cleared
        mock_cascade_cache.l1.clear.assert_called_once()
        mock_cascade_cache.l2.flush_pattern.assert_called_once_with("*")

    @pytest.mark.anyio
    async def test_flush_cache_default_scope_is_all(self, app, mock_cascade_cache):
        """Test default flush scope is 'all'."""
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # POST without body (defaults to all)
            response = await client.post("/v1/cache/flush")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["scope"] == "all"

        mock_cascade_cache.l1.clear.assert_called_once()

    @pytest.mark.anyio
    async def test_flush_cache_invalid_scope(self, app, mock_cascade_cache):
        """Test invalid scope returns 400 error."""
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/cache/flush",
                json={
                    "scope": "file",
                    # Missing file_path
                }
            )

        # Should return 400 due to missing file_path
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_flush_cache_missing_repository(self, app, mock_cascade_cache):
        """Test repository scope without repository parameter returns 400."""
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/cache/flush",
                json={
                    "scope": "repository",
                    # Missing repository
                }
            )

        # Should return 400
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_get_cache_stats(self, app, mock_cascade_cache):
        """Test GET /v1/cache/stats returns correct structure."""
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/cache/stats")

        # Assertions
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "l1" in data
        assert "l2" in data
        assert "cascade" in data

        # Verify L1 stats
        assert data["l1"]["type"] == "L1_memory"
        assert data["l1"]["hit_rate_percent"] == 84.1
        assert data["l1"]["entries"] == 142

        # Verify L2 stats
        assert data["l2"]["type"] == "L2_redis"
        assert data["l2"]["connected"] is True
        assert data["l2"]["hit_rate_percent"] == 74.9

        # Verify cascade stats
        assert data["cascade"]["combined_hit_rate_percent"] == 92.3
        assert data["cascade"]["l1_to_l2_promotions"] == 215
        assert data["cascade"]["strategy"] == "L1 → L2 → L3 (PostgreSQL)"

        # Verify stats() was called
        mock_cascade_cache.stats.assert_called_once()

    @pytest.mark.anyio
    async def test_clear_all_caches(self, app, mock_cascade_cache):
        """Test POST /v1/cache/clear-all (destructive operation)."""
        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/cache/clear-all")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["l1_cleared"] is True
        assert data["l2_cleared"] is True
        assert "All caches cleared" in data["message"]

        # Verify both caches were cleared
        mock_cascade_cache.l1.clear.assert_called_once()
        mock_cascade_cache.l2.flush_pattern.assert_called_once_with("*")

    @pytest.mark.anyio
    async def test_flush_cache_exception_handling(self, app, mock_cascade_cache):
        """Test flush endpoint handles exceptions gracefully."""
        # Make invalidate raise an exception
        mock_cascade_cache.invalidate.side_effect = Exception("Redis connection failed")

        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/cache/flush",
                json={
                    "scope": "file",
                    "file_path": "test.py"
                }
            )

        # Should return 500 with error detail
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Cache flush failed" in data["detail"]

    @pytest.mark.anyio
    async def test_stats_exception_handling(self, app, mock_cascade_cache):
        """Test stats endpoint handles exceptions gracefully."""
        # Make stats raise an exception
        mock_cascade_cache.stats.side_effect = Exception("Stats retrieval failed")

        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/cache/stats")

        # Should return 500 with error detail
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to retrieve cache stats" in data["detail"]

    @pytest.mark.anyio
    async def test_clear_all_exception_handling(self, app, mock_cascade_cache):
        """Test clear-all endpoint handles exceptions gracefully."""
        # Make L2 flush_pattern raise an exception
        mock_cascade_cache.l2.flush_pattern.side_effect = Exception("L2 flush failed")

        app.dependency_overrides[cache_admin_routes.get_cascade_cache] = lambda: mock_cascade_cache

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/cache/clear-all")

        # Should return 500 with error detail
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to clear caches" in data["detail"]
