"""
Cascade cache for EPIC-10 Story 10.3 - L1/L2 coordination with automatic promotion.

Implements intelligent cache cascading:
- L1 hit → return immediately (0.01ms)
- L1 miss → check L2 → promote to L1 if found (1-5ms)
- L1/L2 miss → query L3 (PostgreSQL) → populate both layers (100-200ms)

This ensures hot data automatically migrates to faster layers.
"""

import hashlib
import structlog
from typing import List, Optional

from models.code_chunk_models import CodeChunkModel
from services.caches.code_chunk_cache import CodeChunkCache
from services.caches.redis_cache import RedisCache

logger = structlog.get_logger()


class CascadeCache:
    """
    Coordinated L1/L2 cache with automatic promotion.

    Architecture:
    - L1 (CodeChunkCache): In-memory LRU cache (100MB, <0.01ms)
    - L2 (RedisCache): Distributed cache (2GB, 1-5ms)
    - L3 (PostgreSQL): Source of truth (unlimited, 100-200ms)

    Promotion Strategy:
    - L2 hit → auto-promote to L1 (warm → hot migration)
    - Write-through: populate both L1 and L2 on cache miss
    - Invalidation: clear both layers together
    """

    def __init__(self, l1_cache: CodeChunkCache, l2_cache: RedisCache):
        """
        Initialize cascade cache with L1 and L2 instances.

        Args:
            l1_cache: In-memory code chunk cache (Story 10.1)
            l2_cache: Redis distributed cache (Story 10.2)
        """
        self.l1 = l1_cache
        self.l2 = l2_cache
        self.l1_promotions = 0  # Track L2→L1 promotions

        logger.info(
            "CascadeCache initialized",
            l1_max_mb=l1_cache.max_size_bytes / (1024 * 1024),
            l2_connected=l2_cache.client is not None
        )

    async def get_chunks(
        self,
        file_path: str,
        source_code: str
    ) -> Optional[List[CodeChunkModel]]:
        """
        Get chunks with L1→L2→L3 cascade logic.

        Flow:
        1. Check L1 (in-memory) with MD5 validation
        2. On L1 miss, check L2 (Redis)
        3. On L2 hit, promote to L1 for future fast access
        4. On L1/L2 miss, return None (caller queries L3)

        Args:
            file_path: Path to source file
            source_code: Full source code (for MD5 validation)

        Returns:
            List of CodeChunkModel if cache hit (L1 or L2), None if miss
        """

        # LAYER 1: In-Memory Cache (fastest)
        chunks = self.l1.get(file_path, source_code)
        if chunks:
            logger.debug(
                "L1 cache HIT",
                file=file_path,
                chunks=len(chunks),
                latency_estimate="<0.01ms"
            )
            return chunks

        # LAYER 2: Redis Cache (fast, shared across instances)
        content_hash = self._compute_hash(source_code)
        cache_key = f"chunks:{file_path}:{content_hash}"

        cached_data = await self.l2.get(cache_key)
        if cached_data:
            logger.info(
                "L2 cache HIT → promoting to L1",
                file=file_path,
                chunks=len(cached_data),
                latency_estimate="1-5ms"
            )

            # Deserialize from Redis format
            try:
                chunks = [CodeChunkModel(**c) for c in cached_data]
            except Exception as e:
                logger.warning(
                    "L2 deserialization failed",
                    file=file_path,
                    error=str(e)
                )
                # Invalidate corrupted L2 entry
                await self.l2.delete(cache_key)
                return None

            # PROMOTE TO L1 (warm → hot migration)
            self.l1.put(file_path, source_code, chunks)
            self.l1_promotions += 1

            logger.debug(
                "L2→L1 promotion successful",
                file=file_path,
                total_promotions=self.l1_promotions
            )

            return chunks

        # LAYER 1+2 MISS: Return None, caller will query L3 (PostgreSQL)
        logger.debug(
            "L1/L2 cache MISS",
            file=file_path,
            latency_estimate="100-200ms (L3 required)"
        )
        return None

    async def put_chunks(
        self,
        file_path: str,
        source_code: str,
        chunks: List[CodeChunkModel],
        l2_ttl: int = 300
    ):
        """
        Store chunks in both L1 and L2 (write-through strategy).

        This ensures:
        - Fast subsequent access (L1)
        - Shared cache across API instances (L2)
        - Automatic promotion path exists

        Args:
            file_path: Path to source file
            source_code: Full source code (for MD5 hashing)
            chunks: List of code chunks to cache
            l2_ttl: Time-to-live for L2 in seconds (default: 5 minutes)
        """

        # POPULATE L1: Always store in memory for fast access
        self.l1.put(file_path, source_code, chunks)

        # POPULATE L2: Store in Redis with TTL
        content_hash = self._compute_hash(source_code)
        cache_key = f"chunks:{file_path}:{content_hash}"

        # Serialize for Redis storage
        try:
            serialized = [c.model_dump() for c in chunks]
            await self.l2.set(cache_key, serialized, ttl_seconds=l2_ttl)

            logger.debug(
                "L1+L2 cache populated",
                file=file_path,
                chunks=len(chunks),
                l2_ttl=l2_ttl
            )
        except Exception as e:
            logger.warning(
                "L2 cache population failed (L1 still populated)",
                file=file_path,
                error=str(e)
            )

    async def invalidate(self, file_path: str):
        """
        Invalidate cache across all layers.

        Use cases:
        - File updated → old chunks must be purged
        - Manual cache flush

        Args:
            file_path: Path to file (invalidates all hash variants)
        """

        # Invalidate L1 (single entry)
        self.l1.invalidate(file_path)

        # Invalidate L2 (all hash variants via pattern)
        pattern = f"chunks:{file_path}:*"
        await self.l2.flush_pattern(pattern)

        logger.info(
            "Cache invalidated (L1+L2)",
            file=file_path,
            pattern=pattern
        )

    async def invalidate_repository(self, repository: str):
        """
        Invalidate all chunks for a repository.

        Use case: Repository re-indexed → flush all old data

        Args:
            repository: Repository name
        """

        # L1: Clear entire cache (no repository-level granularity)
        # NOTE: This is aggressive but ensures consistency
        self.l1.clear()

        # L2: Flush all chunk keys (Redis pattern matching)
        pattern = "chunks:*"
        await self.l2.flush_pattern(pattern)

        logger.info(
            "Repository cache invalidated (L1+L2)",
            repository=repository,
            strategy="full_flush"
        )

    async def stats(self) -> dict:
        """
        Get combined statistics across L1 and L2.

        Returns:
            Dictionary with L1, L2, and cascade-specific metrics
        """

        l1_stats = self.l1.stats()
        l2_stats = await self.l2.stats()

        # Calculate combined hit rate
        combined_hit_rate = self._calculate_combined_hit_rate(l1_stats, l2_stats)

        return {
            "l1": l1_stats,
            "l2": l2_stats,
            "cascade": {
                "l1_hit_rate_percent": l1_stats["hit_rate_percent"],
                "l2_hit_rate_percent": l2_stats["hit_rate_percent"],
                "combined_hit_rate_percent": combined_hit_rate,
                "l1_to_l2_promotions": self.l1_promotions,
                "strategy": "L1 → L2 → L3 (PostgreSQL)"
            }
        }

    def _calculate_combined_hit_rate(self, l1_stats: dict, l2_stats: dict) -> float:
        """
        Calculate effective hit rate across L1+L2.

        Formula:
        - L1 hit rate: % of requests served by L1
        - L2 hit rate (of L1 misses): % of L1 misses served by L2
        - Combined: L1 + (1 - L1) × L2

        Example:
        - L1: 70% hit rate
        - L2: 80% hit rate (of remaining 30%)
        - Combined: 70% + (30% × 80%) = 70% + 24% = 94%

        Returns:
            Combined hit rate percentage (0-100)
        """

        l1_hit_rate = l1_stats["hit_rate_percent"] / 100  # Convert to fraction
        l2_hit_rate = l2_stats["hit_rate_percent"] / 100

        # Combined = hits from L1 + hits from L2 (among L1 misses)
        combined = l1_hit_rate + (1 - l1_hit_rate) * l2_hit_rate

        return round(combined * 100, 2)  # Convert back to percentage

    def _compute_hash(self, source_code: str) -> str:
        """
        Compute MD5 hash of source code for cache key.

        Args:
            source_code: Full source code

        Returns:
            MD5 hex digest (32 characters)
        """
        return hashlib.md5(source_code.encode()).hexdigest()
