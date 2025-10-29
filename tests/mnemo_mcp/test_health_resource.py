"""
Tests for MCP health resource.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from mnemo_mcp.resources.health_resource import HealthStatusResource, HealthStatus


class TestHealthStatusResource:
    """Tests for health status resource."""

    def test_get_name(self):
        """Test resource URI."""
        resource = HealthStatusResource()
        assert resource.get_name() == "health://status"

    @pytest.mark.asyncio
    async def test_get_healthy(self):
        """Test health check when all services connected."""
        resource = HealthStatusResource()

        # Mock services (DB and Redis connected)
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_db.acquire.return_value.__aenter__.return_value = mock_conn
        mock_db.acquire.return_value.__aexit__.return_value = None

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        resource.inject_services({
            "db": mock_db,
            "redis": mock_redis
        })

        # Mock context
        ctx = MagicMock()

        # Execute
        response = await resource.get(ctx)

        # Verify
        assert isinstance(response, HealthStatus)
        assert response.status == "healthy"
        assert response.database_connected is True
        assert response.redis_connected is True
        assert response.uptime_seconds >= 0.0
        assert response.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_degraded(self):
        """Test health check when Redis unavailable."""
        resource = HealthStatusResource()

        # Mock services (DB connected, Redis fails)
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_db.acquire.return_value.__aenter__.return_value = mock_conn
        mock_db.acquire.return_value.__aexit__.return_value = None

        # Redis that fails
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Redis unavailable"))

        resource.inject_services({
            "db": mock_db,
            "redis": mock_redis
        })

        ctx = MagicMock()

        # Execute
        response = await resource.get(ctx)

        # Verify degraded state
        assert response.status == "degraded"
        assert response.database_connected is True
        assert response.redis_connected is False

    @pytest.mark.asyncio
    async def test_get_unhealthy(self):
        """Test health check when DB unavailable."""
        resource = HealthStatusResource()

        # Mock services (DB fails)
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("DB unavailable"))
        mock_db.acquire.return_value.__aenter__.return_value = mock_conn
        mock_db.acquire.return_value.__aexit__.return_value = None

        resource.inject_services({
            "db": mock_db,
            "redis": None
        })

        ctx = MagicMock()

        # Execute
        response = await resource.get(ctx)

        # Verify unhealthy state
        assert response.status == "unhealthy"
        assert response.database_connected is False

    @pytest.mark.asyncio
    async def test_health_response_serialization(self):
        """Test HealthStatus can be serialized to dict."""
        resource = HealthStatusResource()

        # No services injected
        ctx = MagicMock()

        response = await resource.get(ctx)
        response_dict = response.model_dump()

        assert isinstance(response_dict, dict)
        assert "status" in response_dict
        assert "timestamp" in response_dict
        assert "database_connected" in response_dict
        assert "redis_connected" in response_dict
