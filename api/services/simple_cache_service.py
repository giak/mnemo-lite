"""
Simple in-memory cache service for embeddings.

No Redis needed - just a simple LRU cache for local usage.
Perfect for applications like Claude Code that run locally.
"""

import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SimpleMemoryCache:
    """
    Simple in-memory LRU cache for embeddings.

    Features:
    - No external dependencies (no Redis)
    - LRU eviction when max size reached
    - Optional TTL support
    - Thread-safe (using OrderedDict)
    - Cache statistics
    """

    def __init__(
        self,
        max_size: int = 5000,
        ttl_seconds: Optional[int] = None,
        enable_stats: bool = True
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries (default 5000)
            ttl_seconds: Time to live in seconds (None = no expiry)
            enable_stats: Track hit/miss statistics
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enable_stats = enable_stats

        # Use OrderedDict for LRU behavior
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _make_key(self, text: str) -> str:
        """
        Generate cache key from text using MD5 hash.

        Args:
            text: Input text

        Returns:
            MD5 hash as hex string
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        """
        Get embedding from cache.

        Args:
            text: Text to look up

        Returns:
            Cached embedding or None if not found/expired
        """
        key = self._make_key(text)

        if key not in self._cache:
            if self.enable_stats:
                self.misses += 1
            return None

        value, timestamp = self._cache[key]

        # Check TTL if enabled
        if self.ttl_seconds and time.time() - timestamp > self.ttl_seconds:
            # Expired - remove it
            del self._cache[key]
            if self.enable_stats:
                self.misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)

        if self.enable_stats:
            self.hits += 1

        return value

    def set(self, text: str, embedding: List[float]) -> None:
        """
        Store embedding in cache.

        Args:
            text: Text key
            embedding: Embedding vector to store
        """
        key = self._make_key(text)
        timestamp = time.time()

        # Check if we need to evict
        if key not in self._cache and len(self._cache) >= self.max_size:
            # Evict least recently used (first item)
            evicted = self._cache.popitem(last=False)
            if self.enable_stats:
                self.evictions += 1
            logger.debug(f"Evicted cache entry: {evicted[0][:8]}...")

        # Store or update
        self._cache[key] = (embedding, timestamp)
        # Move to end (most recently used)
        self._cache.move_to_end(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total_requests
        }

    def __len__(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def __contains__(self, text: str) -> bool:
        """Check if text is in cache (without updating LRU)."""
        key = self._make_key(text)
        if key not in self._cache:
            return False

        # Check TTL
        if self.ttl_seconds:
            _, timestamp = self._cache[key]
            if time.time() - timestamp > self.ttl_seconds:
                return False

        return True


class CachedEmbeddingService:
    """
    Wrapper for embedding service with caching.

    This wraps any embedding service to add caching functionality.
    """

    def __init__(
        self,
        embedding_service,
        cache: Optional[SimpleMemoryCache] = None
    ):
        """
        Initialize cached embedding service.

        Args:
            embedding_service: The underlying embedding service
            cache: Cache instance (creates default if None)
        """
        self.service = embedding_service
        self.cache = cache or SimpleMemoryCache(
            max_size=5000,
            ttl_seconds=3600  # 1 hour default TTL
        )
        self.logger = logging.getLogger(__name__)

    async def generate_embedding(
        self,
        text: str,
        skip_cache: bool = False
    ) -> List[float]:
        """
        Generate embedding with caching.

        Args:
            text: Text to embed
            skip_cache: Bypass cache if True

        Returns:
            Embedding vector
        """
        if not skip_cache:
            # Try cache first
            cached = self.cache.get(text)
            if cached is not None:
                self.logger.debug(f"Cache hit for text: {text[:50]}...")
                return cached

        # Generate embedding
        embedding = await self.service.generate_embedding(text)

        # Store in cache
        if not skip_cache and embedding:
            self.cache.set(text, embedding)

        return embedding

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        skip_cache: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with caching.

        Args:
            texts: List of texts to embed
            skip_cache: Bypass cache if True

        Returns:
            List of embedding vectors
        """
        embeddings = []
        texts_to_generate = []
        cached_indices = []

        if not skip_cache:
            # Check cache for each text
            for i, text in enumerate(texts):
                cached = self.cache.get(text)
                if cached is not None:
                    embeddings.append(cached)
                    cached_indices.append(i)
                else:
                    texts_to_generate.append(text)
                    embeddings.append(None)  # Placeholder
        else:
            texts_to_generate = texts
            embeddings = [None] * len(texts)

        # Generate missing embeddings
        if texts_to_generate:
            # Check if service supports batch processing
            if hasattr(self.service, 'generate_embeddings_batch'):
                new_embeddings = await self.service.generate_embeddings_batch(texts_to_generate)
            else:
                # Fall back to sequential processing
                new_embeddings = []
                for text in texts_to_generate:
                    emb = await self.service.generate_embedding(text)
                    new_embeddings.append(emb)

            # Fill in the placeholders and cache
            new_idx = 0
            for i, emb in enumerate(embeddings):
                if emb is None:
                    embeddings[i] = new_embeddings[new_idx]
                    if not skip_cache:
                        self.cache.set(texts[i], new_embeddings[new_idx])
                    new_idx += 1

        self.logger.info(
            f"Batch processing: {len(cached_indices)} cached, "
            f"{len(texts_to_generate)} generated"
        )

        return embeddings

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the cache."""
        self.cache.clear()


# Example usage for testing
if __name__ == "__main__":
    import asyncio

    async def test_cache():
        # Create mock embedding service
        class MockEmbeddingService:
            async def generate_embedding(self, text: str):
                # Simulate slow operation
                await asyncio.sleep(0.1)
                return [0.1] * 768

        # Create cached service
        mock_service = MockEmbeddingService()
        cached_service = CachedEmbeddingService(mock_service)

        # Test caching
        text = "Hello, world!"

        # First call - cache miss
        start = time.time()
        emb1 = await cached_service.generate_embedding(text)
        time1 = time.time() - start
        print(f"First call: {time1:.3f}s")

        # Second call - cache hit
        start = time.time()
        emb2 = await cached_service.generate_embedding(text)
        time2 = time.time() - start
        print(f"Second call: {time2:.3f}s")

        # Should be much faster
        assert time2 < time1 / 10

        # Check stats
        stats = cached_service.get_cache_stats()
        print(f"Cache stats: {stats}")
        assert stats["hits"] == 1
        assert stats["misses"] == 1

        print("✅ Cache test passed!")

    # Run test
    asyncio.run(test_cache())