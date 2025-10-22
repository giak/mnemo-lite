"""
L2 Redis Cache for MnemoLite v3.0 (EPIC-10 Story 10.2).

Async Redis client with connection pooling, graceful degradation,
and comprehensive metrics tracking.

EPIC-12 Story 12.3: Added circuit breaker for fault tolerance.
"""

from typing import Any, Optional
import json
import structlog
from datetime import timedelta

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # Graceful degradation if redis not installed

from utils.circuit_breaker import CircuitBreaker
from config.circuit_breakers import REDIS_CIRCUIT_CONFIG
from utils.circuit_breaker_registry import register_circuit_breaker
from utils.retry import with_retry, RetryConfig

logger = structlog.get_logger()

# EPIC-12 Story 12.5: Retry configuration for Redis operations
REDIS_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    jitter=True,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
    )
)

# Add redis.exceptions if available
try:
    import redis.exceptions
    REDIS_RETRY_CONFIG.retryable_exceptions = (
        ConnectionError,
        TimeoutError,
        redis.exceptions.ConnectionError,
        redis.exceptions.TimeoutError,
    )
except (ImportError, AttributeError):
    pass


class RedisCache:
    """
    L2 Redis cache with async operations and graceful degradation.

    Features:
    - Async connection pooling (max 20 connections)
    - JSON serialization for complex objects
    - Configurable TTL per operation
    - Graceful degradation if Redis unavailable
    - Comprehensive metrics (hits, misses, errors)
    - Pattern-based cache invalidation
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.hits = 0
        self.misses = 0
        self.errors = 0

        # EPIC-12 Story 12.3: Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=REDIS_CIRCUIT_CONFIG.failure_threshold,
            recovery_timeout=REDIS_CIRCUIT_CONFIG.recovery_timeout,
            half_open_max_calls=REDIS_CIRCUIT_CONFIG.half_open_max_calls,
            name="redis_cache"
        )

        # Register for health monitoring
        register_circuit_breaker(self.circuit_breaker)

    async def connect(self):
        """
        Initialize Redis connection pool.

        Creates connection with max 20 connections.
        Logs error and continues without cache if connection fails.
        """
        if redis is None:
            logger.warning("Redis library not installed - L2 cache disabled")
            return

        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            await self.client.ping()
            logger.info("Redis L2 cache connected", url=self.redis_url)
        except Exception as e:
            logger.error("Redis connection failed - continuing without L2 cache", error=str(e))
            self.client = None

    async def disconnect(self):
        """Close Redis connection pool."""
        if self.client:
            await self.client.aclose()
            logger.info("Redis L2 cache disconnected")

    @with_retry(REDIS_RETRY_CONFIG)  # EPIC-12 Story 12.5: Add retry logic
    async def _get_with_retry(self, key: str) -> Optional[str]:
        """
        Internal get with retry logic.

        EPIC-12 Story 12.5: This method will retry on transient failures.
        """
        return await self.client.get(key)

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        EPIC-12 Story 12.3: Protected with circuit breaker.
        EPIC-12 Story 12.5: With retry logic for transient failures.

        Args:
            key: Cache key

        Returns:
            Deserialized value if found, None otherwise
        """
        # EPIC-12 Story 12.3: Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.debug(
                "redis_circuit_open",
                circuit_state=self.circuit_breaker.state.value,
                message="Circuit breaker OPEN, skipping Redis"
            )
            return None

        if not self.client:
            return None

        try:
            value = await self._get_with_retry(key)  # EPIC-12 Story 12.5: Use retry
            if value:
                self.hits += 1
                self.circuit_breaker.record_success()  # EPIC-12 Story 12.3
                logger.debug("L2 cache HIT", key=key[:50])
                return json.loads(value)
            else:
                self.misses += 1
                logger.debug("L2 cache MISS", key=key[:50])
                return None
        except Exception as e:
            self.errors += 1
            self.circuit_breaker.record_failure()  # EPIC-12 Story 12.3
            logger.warning(
                "Redis GET error - fallback to L3",
                key=key[:50],
                error=str(e),
                circuit_state=self.circuit_breaker.state.value
            )
            return None

    @with_retry(REDIS_RETRY_CONFIG)  # EPIC-12 Story 12.5: Add retry logic
    async def _set_with_retry(self, key: str, serialized: str, ttl_seconds: int) -> bool:
        """
        Internal set with retry logic.

        EPIC-12 Story 12.5: This method will retry on transient failures.
        """
        await self.client.setex(
            key,
            timedelta(seconds=ttl_seconds),
            serialized,
        )
        return True

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """
        Set value in cache with TTL.

        EPIC-12 Story 12.3: Protected with circuit breaker.
        EPIC-12 Story 12.5: With retry logic for transient failures.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default: 300 = 5 minutes)

        Returns:
            True if set successfully, False otherwise
        """
        # EPIC-12 Story 12.3: Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.debug(
                "redis_circuit_open",
                circuit_state=self.circuit_breaker.state.value,
                message="Circuit breaker OPEN, skipping Redis"
            )
            return False

        if not self.client:
            return False

        try:
            serialized = json.dumps(value)
            await self._set_with_retry(key, serialized, ttl_seconds)  # EPIC-12 Story 12.5
            self.circuit_breaker.record_success()  # EPIC-12 Story 12.3
            logger.debug("L2 cache SET", key=key[:50], ttl=ttl_seconds)
            return True
        except Exception as e:
            self.errors += 1
            self.circuit_breaker.record_failure()  # EPIC-12 Story 12.3
            logger.warning(
                "Redis SET error",
                key=key[:50],
                error=str(e),
                circuit_state=self.circuit_breaker.state.value
            )
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        EPIC-12 Story 12.3: Protected with circuit breaker.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        # EPIC-12 Story 12.3: Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.debug(
                "redis_circuit_open",
                circuit_state=self.circuit_breaker.state.value,
                message="Circuit breaker OPEN, skipping Redis"
            )
            return False

        if not self.client:
            return False

        try:
            await self.client.delete(key)
            self.circuit_breaker.record_success()  # EPIC-12 Story 12.3
            logger.debug("L2 cache DELETE", key=key[:50])
            return True
        except Exception as e:
            self.errors += 1
            self.circuit_breaker.record_failure()  # EPIC-12 Story 12.3
            logger.warning(
                "Redis DELETE error",
                key=key[:50],
                error=str(e),
                circuit_state=self.circuit_breaker.state.value
            )
            return False

    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "search:*", "graph:repo_name:*")

        Returns:
            Number of keys deleted
        """
        if not self.client:
            return 0

        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.client.delete(*keys)
                logger.info("Flushed cache pattern", pattern=pattern, count=len(keys))
                return deleted
            return 0
        except Exception as e:
            self.errors += 1
            logger.warning("Redis FLUSH error", pattern=pattern, error=str(e))
            return 0

    async def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, errors, hit_rate, memory usage, etc.
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        info = {}
        if self.client:
            try:
                info = await self.client.info("memory")
            except Exception as e:
                logger.warning("Failed to get Redis info", error=str(e))

        return {
            "type": "L2_redis",
            "connected": self.client is not None,
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate_percent": round(hit_rate, 2),
            "memory_used_mb": info.get("used_memory", 0) / (1024 * 1024),
            "memory_peak_mb": info.get("used_memory_peak", 0) / (1024 * 1024),
        }
