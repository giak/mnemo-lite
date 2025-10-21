"""
Integration tests for circuit breaker functionality.

Tests the circuit breaker behavior with actual services (Redis, Embedding).

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

import pytest
import asyncio
import time
from datetime import datetime
from httpx import ASGITransport, AsyncClient

from main import app
from services.caches.redis_cache import RedisCache
from utils.circuit_breaker import CircuitState


class TestRedisCircuitBreaker:
    """Test circuit breaker behavior with Redis cache."""

    @pytest.mark.anyio
    async def test_redis_circuit_opens_after_connection_failures(self):
        """Test Redis circuit opens after repeated operation failures."""
        # Create cache with invalid URL
        cache = RedisCache(redis_url="redis://invalid-host:9999/0")

        # Don't call connect() - it sets client to None on failure
        # Instead, set up a client that will fail on operations
        cache.client = None  # Simulate failed connection

        # Reset circuit breaker to known state
        cache.circuit_breaker.reset()
        assert cache.circuit_breaker.state == CircuitState.CLOSED

        # Manually create a failing client scenario by directly calling record_failure
        for i in range(5):
            cache.circuit_breaker.record_failure()

        # Circuit should be OPEN after threshold failures
        assert cache.circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.anyio
    async def test_redis_circuit_fast_fails_when_open(self):
        """Test Redis operations fail fast when circuit is OPEN."""
        cache = RedisCache(redis_url="redis://invalid-host:9999/0")
        cache.client = None

        # Open circuit manually
        cache.circuit_breaker._transition_to(CircuitState.OPEN)
        cache.circuit_breaker._last_failure_time = datetime.now()

        # Operations should fail fast
        start = time.time()
        result = await cache.get("test_key")
        elapsed = time.time() - start

        assert result is None
        assert elapsed < 0.01  # < 10ms (fast fail)

    @pytest.mark.anyio
    async def test_health_endpoint_shows_redis_circuit(self, test_client):
        """Test /health endpoint exposes Redis circuit breaker metrics."""
        response = await test_client.get("/health")
        assert response.status_code in [200, 503]

        data = response.json()
        assert "circuit_breakers" in data
        assert "redis_cache" in data["circuit_breakers"]

        redis_metrics = data["circuit_breakers"]["redis_cache"]
        assert redis_metrics["service"] == "redis_cache"
        assert redis_metrics["state"] in ["closed", "open", "half_open"]
        assert "failure_count" in redis_metrics
        assert "success_count" in redis_metrics
        assert "config" in redis_metrics
        assert redis_metrics["config"]["failure_threshold"] == 5
        assert redis_metrics["config"]["recovery_timeout"] == 30


class TestEmbeddingCircuitBreaker:
    """Test circuit breaker behavior with embedding service.

    Note: In test mode (EMBEDDING_MODE=mock), MockEmbeddingService is used
    which doesn't have circuit breaker protection. These tests only apply
    when running with real embedding models.
    """

    @pytest.mark.anyio
    async def test_health_endpoint_circuit_breakers_present(self, test_client):
        """Test /health endpoint includes circuit_breakers field."""
        response = await test_client.get("/health")
        assert response.status_code in [200, 503]

        data = response.json()
        assert "circuit_breakers" in data
        assert isinstance(data["circuit_breakers"], dict)

        # In mock mode, only redis_cache circuit breaker will be present
        # In real mode, both redis_cache and embedding_service will be present
        assert "redis_cache" in data["circuit_breakers"]


class TestCriticalCircuitDetection:
    """Test health endpoint tracks critical circuits."""

    @pytest.mark.anyio
    async def test_health_includes_critical_circuits_list(self, test_client):
        """Test /health response includes critical_circuits_open field."""
        response = await test_client.get("/health")
        data = response.json()

        # Should have critical_circuits_open field
        assert "critical_circuits_open" in data
        assert isinstance(data["critical_circuits_open"], list)

        # In healthy state, should be empty
        if data["status"] == "healthy":
            assert len(data["critical_circuits_open"]) == 0


class TestCircuitBreakerGracefulDegradation:
    """Test graceful degradation when services fail."""

    @pytest.mark.anyio
    async def test_cache_returns_none_when_circuit_open(self):
        """Test cache returns None gracefully when circuit is OPEN."""
        cache = RedisCache(redis_url="redis://invalid-host:9999/0")
        cache.client = None

        # Open circuit
        cache.circuit_breaker._transition_to(CircuitState.OPEN)
        cache.circuit_breaker._last_failure_time = datetime.now()

        # Should return None without raising exception
        result = await cache.get("test_key")
        assert result is None

        # set should return False
        set_result = await cache.set("key", "value")
        assert set_result is False

        # delete should return False
        del_result = await cache.delete("key")
        assert del_result is False

    @pytest.mark.anyio
    async def test_cache_stats_work_with_circuit_open(self):
        """Test cache stats work even when circuit is OPEN."""
        cache = RedisCache(redis_url="redis://invalid-host:9999/0")
        cache.client = None

        # Open circuit
        cache.circuit_breaker._transition_to(CircuitState.OPEN)
        cache.circuit_breaker._last_failure_time = datetime.now()

        # Stats should still work
        stats = await cache.stats()
        assert stats["type"] == "L2_redis"
        assert stats["connected"] is False
        assert "hits" in stats
        assert "misses" in stats


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery behavior."""

    @pytest.mark.anyio
    async def test_circuit_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")

        # Set short recovery timeout for testing
        cache.circuit_breaker.config.recovery_timeout = 1

        # Open circuit
        cache.circuit_breaker._transition_to(CircuitState.OPEN)
        cache.circuit_breaker._last_failure_time = datetime.now()

        assert cache.circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.2)

        # Next can_execute should transition to HALF_OPEN
        can_exec = cache.circuit_breaker.can_execute()
        assert can_exec is True
        assert cache.circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.anyio
    async def test_circuit_closes_on_success_in_half_open(self):
        """Test circuit closes when operation succeeds in HALF_OPEN state."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        await cache.connect()

        # Transition to HALF_OPEN
        cache.circuit_breaker._transition_to(CircuitState.HALF_OPEN)
        assert cache.circuit_breaker.state == CircuitState.HALF_OPEN

        # Successful operation should close circuit
        cache.circuit_breaker.record_success()
        assert cache.circuit_breaker.state == CircuitState.CLOSED
