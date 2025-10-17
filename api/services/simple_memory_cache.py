"""
Simple memory cache for MnemoLite.
Ultra-fast, zero-dependency caching solution.
"""

from typing import Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import json
import hashlib
import asyncio


class SimpleMemoryCache:
    """Thread-safe memory cache with TTL support."""

    def __init__(self, ttl_seconds: int = 60, max_items: int = 1000):
        self._cache: dict = {}
        self._timestamps: dict = {}
        self.ttl = ttl_seconds
        self.max_items = max_items
        self.hits = 0
        self.misses = 0
        self._lock = asyncio.Lock()

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate unique cache key from arguments."""
        # Filter out non-serializable objects
        filtered_kwargs = {k: str(v) for k, v in kwargs.items()
                          if not k.startswith('_') and k not in ['request', 'db_engine', 'service']}
        key_data = json.dumps({
            'prefix': prefix,
            'args': [str(a) for a in args if not callable(a)],
            'kwargs': filtered_kwargs
        }, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        async with self._lock:
            if key in self._cache:
                timestamp = self._timestamps.get(key)
                if timestamp and (datetime.now() - timestamp).seconds < self.ttl:
                    self.hits += 1
                    return self._cache[key]
                else:
                    # Expired, clean up
                    del self._cache[key]
                    del self._timestamps[key]

            self.misses += 1
            return None

    async def set(self, key: str, value: Any):
        """Store value in cache."""
        async with self._lock:
            self._cache[key] = value
            self._timestamps[key] = datetime.now()

            # Simple cleanup (keep max items)
            if len(self._cache) > self.max_items:
                # Remove oldest 10% of entries
                num_to_remove = max(1, self.max_items // 10)
                oldest_keys = sorted(self._timestamps.keys(),
                                   key=lambda k: self._timestamps[k])[:num_to_remove]
                for k in oldest_keys:
                    del self._cache[k]
                    del self._timestamps[k]

    async def clear(self):
        """Clear all cached items."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    async def remove(self, key: str) -> bool:
        """Remove specific key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
                return True
            return False

    def cache_async(self, ttl: Optional[int] = None):
        """Decorator for async functions."""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Skip caching for certain parameters
                if kwargs.get('no_cache', False):
                    return await func(*args, **kwargs)

                cache_key = self._make_key(func.__name__, *args, **kwargs)
                cached = await self.get(cache_key)

                if cached is not None:
                    return cached

                result = await func(*args, **kwargs)

                # Only cache successful results
                if result is not None:
                    await self.set(cache_key, result)

                return result
            return wrapper
        return decorator

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        # Calculate memory usage estimate
        import sys
        cache_size = sys.getsizeof(self._cache) + sys.getsizeof(self._timestamps)

        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'items_cached': len(self._cache),
            'max_items': self.max_items,
            'ttl_seconds': self.ttl,
            'memory_bytes': cache_size,
            'memory_mb': round(cache_size / 1024 / 1024, 2)
        }


# Global cache instances for different purposes
_event_cache = SimpleMemoryCache(ttl_seconds=60, max_items=500)
_search_cache = SimpleMemoryCache(ttl_seconds=30, max_items=200)
_graph_cache = SimpleMemoryCache(ttl_seconds=120, max_items=100)


def get_event_cache() -> SimpleMemoryCache:
    """Get event cache instance."""
    return _event_cache


def get_search_cache() -> SimpleMemoryCache:
    """Get search cache instance."""
    return _search_cache


def get_graph_cache() -> SimpleMemoryCache:
    """Get graph cache instance."""
    return _graph_cache


async def get_all_cache_stats() -> dict:
    """Get statistics from all caches."""
    return {
        'event_cache': _event_cache.get_stats(),
        'search_cache': _search_cache.get_stats(),
        'graph_cache': _graph_cache.get_stats(),
        'total_hits': _event_cache.hits + _search_cache.hits + _graph_cache.hits,
        'total_misses': _event_cache.misses + _search_cache.misses + _graph_cache.misses,
    }