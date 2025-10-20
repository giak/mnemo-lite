"""
Multi-Layer Cache System for MnemoLite v3.0.

Provides:
- L1 In-Memory Cache (CodeChunkCache) - LRU eviction with MD5 validation
- L2 Redis Cache (RedisCache) - Shared cache with async operations
- L1/L2 Cascade (CascadeCache) - Automatic promotion with intelligent layering
- Cache Metrics Collector (CacheMetricsCollector) - Historical metrics tracking
- Cache key management utilities
"""

from .code_chunk_cache import CodeChunkCache, CachedChunkEntry
from .redis_cache import RedisCache
from .cascade_cache import CascadeCache
from .cache_metrics import CacheMetricsCollector, CacheMetricSnapshot, get_metrics_collector
from . import cache_keys

__all__ = [
    "CodeChunkCache",
    "CachedChunkEntry",
    "RedisCache",
    "CascadeCache",
    "CacheMetricsCollector",
    "CacheMetricSnapshot",
    "get_metrics_collector",
    "cache_keys",
]
