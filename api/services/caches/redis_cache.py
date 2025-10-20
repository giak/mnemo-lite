"""
L2 Redis Cache for MnemoLite v3.0 (EPIC-10 Story 10.2).

Async Redis client with connection pooling, graceful degradation,
and comprehensive metrics tracking.
"""

from typing import Any, Optional
import json
import structlog
from datetime import timedelta

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # Graceful degradation if redis not installed

logger = structlog.get_logger()


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

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Deserialized value if found, None otherwise
        """
        if not self.client:
            return None

        try:
            value = await self.client.get(key)
            if value:
                self.hits += 1
                logger.debug("L2 cache HIT", key=key[:50])
                return json.loads(value)
            else:
                self.misses += 1
                logger.debug("L2 cache MISS", key=key[:50])
                return None
        except Exception as e:
            self.errors += 1
            logger.warning("Redis GET error - fallback to L3", key=key[:50], error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default: 300 = 5 minutes)

        Returns:
            True if set successfully, False otherwise
        """
        if not self.client:
            return False

        try:
            serialized = json.dumps(value)
            await self.client.setex(
                key,
                timedelta(seconds=ttl_seconds),
                serialized,
            )
            logger.debug("L2 cache SET", key=key[:50], ttl=ttl_seconds)
            return True
        except Exception as e:
            self.errors += 1
            logger.warning("Redis SET error", key=key[:50], error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        if not self.client:
            return False

        try:
            await self.client.delete(key)
            logger.debug("L2 cache DELETE", key=key[:50])
            return True
        except Exception as e:
            self.errors += 1
            logger.warning("Redis DELETE error", key=key[:50], error=str(e))
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
