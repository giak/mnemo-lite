"""
L1 In-Memory Cache for Code Chunks with MD5 Content Hashing.

Provides hash-based caching with LRU eviction to prevent serving stale data.
Inspired by Serena's ls.py MD5 pattern.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from collections import OrderedDict
import hashlib
import structlog

logger = structlog.get_logger()


@dataclass
class CachedChunkEntry:
    """Cached chunk data with content hash for validation."""

    file_path: str
    content_hash: str  # MD5 of source code
    chunks: List[dict]  # Serialized CodeChunk objects
    metadata: dict
    cached_at: datetime
    size_bytes: int


class CodeChunkCache:
    """L1 in-memory cache with LRU eviction and MD5 validation."""

    def __init__(self, max_size_mb: int = 100):
        """
        Initialize cache with maximum size limit.

        Args:
            max_size_mb: Maximum cache size in megabytes (default: 100MB)
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size = 0
        self.cache: OrderedDict[str, CachedChunkEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

        logger.info(
            "L1 cache initialized",
            max_size_mb=max_size_mb,
            max_size_bytes=self.max_size_bytes,
        )

    def get(self, file_path: str, source_code: str) -> Optional[List[dict]]:
        """
        Get cached chunks if content hash matches (zero-trust validation).

        Args:
            file_path: Path to the file
            source_code: Current source code content

        Returns:
            List of cached chunk dicts if hash matches, None otherwise
        """
        content_hash = self._compute_hash(source_code)

        if file_path in self.cache:
            entry = self.cache[file_path]

            # ZERO-TRUST: Validate hash
            if entry.content_hash == content_hash:
                # Move to end (LRU: most recently used)
                self.cache.move_to_end(file_path)
                self.hits += 1
                logger.debug(
                    "L1 cache HIT",
                    file_path=file_path,
                    content_hash=content_hash[:8],
                    chunks=len(entry.chunks),
                )
                return entry.chunks
            else:
                # Content changed → hash mismatch → invalidate
                logger.debug(
                    "L1 cache INVALID (hash mismatch)",
                    file_path=file_path,
                    cached_hash=entry.content_hash[:8],
                    current_hash=content_hash[:8],
                )
                self._evict(file_path)

        self.misses += 1
        logger.debug("L1 cache MISS", file_path=file_path)
        return None

    def put(self, file_path: str, source_code: str, chunks: List[dict]):
        """
        Store chunks with content hash.

        Args:
            file_path: Path to the file
            source_code: Source code content
            chunks: List of chunk dicts to cache
        """
        content_hash = self._compute_hash(source_code)

        # Estimate size (rough approximation)
        size = len(source_code)
        for chunk in chunks:
            if isinstance(chunk, dict):
                size += len(chunk.get("source_code", ""))
            else:
                # Handle CodeChunk objects
                size += len(getattr(chunk, "source_code", ""))

        # Evict LRU entries if needed to make space
        while self.current_size + size > self.max_size_bytes and self.cache:
            self._evict_lru()

        # Remove old entry if exists
        if file_path in self.cache:
            self._evict(file_path)

        entry = CachedChunkEntry(
            file_path=file_path,
            content_hash=content_hash,
            chunks=chunks,
            metadata={"chunk_count": len(chunks)},
            cached_at=datetime.now(),
            size_bytes=size,
        )

        self.cache[file_path] = entry
        self.current_size += size

        logger.debug(
            "L1 cache PUT",
            file_path=file_path,
            content_hash=content_hash[:8],
            chunks=len(chunks),
            size_kb=size / 1024,
            cache_size_mb=self.current_size / (1024 * 1024),
        )

    def invalidate(self, file_path: str):
        """
        Manually invalidate entry.

        Args:
            file_path: Path to the file to invalidate
        """
        if file_path in self.cache:
            self._evict(file_path)
            logger.info("L1 cache invalidated", file_path=file_path)

    def clear(self):
        """Clear entire cache."""
        count = len(self.cache)
        self.cache.clear()
        self.current_size = 0
        logger.info("L1 cache cleared", entries_removed=count)

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with hit rate, size, entries count, etc.
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "type": "L1_memory",
            "size_mb": round(self.current_size / (1024 * 1024), 2),
            "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2),
            "entries": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate_percent": round(hit_rate, 2),
            "utilization_percent": round(
                self.current_size / self.max_size_bytes * 100, 2
            ),
        }

    def _compute_hash(self, source_code: str) -> str:
        """
        Compute MD5 hash of source code.

        Note: MD5 is used for cache integrity checking (not cryptographic security).
        This is the same pattern as Serena's ls.py.

        Args:
            source_code: Source code content

        Returns:
            MD5 hex digest
        """
        return hashlib.md5(source_code.encode()).hexdigest()

    def _evict(self, file_path: str):
        """
        Evict specific entry.

        Args:
            file_path: Path to the file to evict
        """
        if file_path in self.cache:
            entry = self.cache.pop(file_path)
            self.current_size -= entry.size_bytes
            self.evictions += 1
            logger.debug(
                "L1 cache evicted (explicit)",
                file_path=file_path,
                size_kb=entry.size_bytes / 1024,
            )

    def _evict_lru(self):
        """Evict least recently used entry (LRU policy)."""
        if self.cache:
            file_path, entry = self.cache.popitem(last=False)  # Remove first (oldest)
            self.current_size -= entry.size_bytes
            self.evictions += 1
            logger.debug(
                "L1 cache evicted (LRU)",
                file_path=file_path,
                size_kb=entry.size_bytes / 1024,
                cache_size_mb=self.current_size / (1024 * 1024),
            )
