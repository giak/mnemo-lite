"""
Query optimization helpers and performance utilities for MnemoLite.

Simple, pragmatic optimizations for local usage - no over-engineering.
"""

import hashlib
import time
import logging
from collections import defaultdict, OrderedDict
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryResultCache:
    """
    Simple cache for query results with TTL.

    Perfect for caching repeated queries in local applications.
    No Redis needed - just Python dict with TTL.
    """

    def __init__(self, max_size: int = 100, default_ttl: int = 60):
        """
        Initialize query cache.

        Args:
            max_size: Maximum cached queries
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Tuple[Any, float, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _make_key(self, query: str, params: Dict) -> str:
        """Generate cache key from query and params."""
        key_str = f"{query}:{sorted(params.items())}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, params: Dict) -> Optional[Any]:
        """Get cached result if exists and not expired."""
        key = self._make_key(query, params)

        if key not in self._cache:
            self.misses += 1
            return None

        result, timestamp, ttl = self._cache[key]

        # Check TTL
        if time.time() - timestamp > ttl:
            del self._cache[key]
            self.misses += 1
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        self.hits += 1
        return result

    def set(self, query: str, params: Dict, result: Any, ttl: Optional[int] = None):
        """Cache query result."""
        key = self._make_key(query, params)
        ttl = ttl or self.default_ttl

        # Evict LRU if needed
        if key not in self._cache and len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (result, time.time(), ttl)
        self._cache.move_to_end(key)

    async def get_or_execute(
        self,
        query: str,
        params: Dict,
        executor: Callable,
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or execute query."""
        # Check cache
        cached = self.get(query, params)
        if cached is not None:
            logger.debug(f"Query cache hit: {self.hits}/{self.hits + self.misses}")
            return cached

        # Execute query
        result = await executor(query, params)

        # Cache result
        self.set(query, params, result, ttl)

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_queries": total
        }

    def clear(self):
        """Clear cache."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0


class SimpleMetrics:
    """
    Lightweight metrics collection for local monitoring.

    No Prometheus/Grafana needed - just simple counters and timers.
    """

    def __init__(self):
        """Initialize metrics."""
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        self.gauges = {}
        self._start_time = time.time()

    def inc(self, name: str, value: int = 1):
        """Increment counter."""
        self.counters[name] += value

    def set_gauge(self, name: str, value: float):
        """Set gauge value."""
        self.gauges[name] = value

    @contextmanager
    def timer(self, name: str):
        """Context manager to time operations."""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.timers[name].append(duration)

    async def atimer(self, name: str):
        """Async context manager to time operations."""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.timers[name].append(duration)

    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a timer."""
        times = self.timers.get(name, [])
        if not times:
            return {}

        return {
            "count": len(times),
            "total": sum(times),
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
            "last": times[-1] if times else 0
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get all metrics."""
        uptime = time.time() - self._start_time

        timer_stats = {}
        for name, times in self.timers.items():
            if times:
                timer_stats[name] = {
                    "count": len(times),
                    "avg_ms": sum(times) / len(times) * 1000,
                    "max_ms": max(times) * 1000
                }

        return {
            "uptime_seconds": uptime,
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timers": timer_stats
        }

    def reset(self):
        """Reset all metrics."""
        self.counters.clear()
        self.timers.clear()
        self.gauges.clear()
        self._start_time = time.time()


class LazyLoader:
    """
    Lazy loading wrapper for expensive resources.

    Loads resource only when first accessed.
    """

    def __init__(self, loader_func: Callable):
        """
        Initialize lazy loader.

        Args:
            loader_func: Function to load the resource
        """
        self._loader_func = loader_func
        self._resource = None
        self._loaded = False
        self._load_time = None

    async def get(self):
        """Get resource (load if needed)."""
        if not self._loaded:
            start = time.time()
            self._resource = await self._loader_func()
            self._load_time = time.time() - start
            self._loaded = True
            logger.info(f"Lazy loaded resource in {self._load_time:.2f}s")

        return self._resource

    def is_loaded(self) -> bool:
        """Check if resource is loaded."""
        return self._loaded

    def get_load_time(self) -> Optional[float]:
        """Get load time if loaded."""
        return self._load_time


class BulkProcessor:
    """
    Helper for processing items in bulk.

    Accumulates items and processes them in batches.
    """

    def __init__(self, batch_size: int = 100, flush_interval: float = 1.0):
        """
        Initialize bulk processor.

        Args:
            batch_size: Max items per batch
            flush_interval: Max seconds before auto-flush
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer = []
        self._last_flush = time.time()

    def add(self, item: Any) -> bool:
        """
        Add item to buffer.

        Returns:
            True if batch is ready to process
        """
        self._buffer.append(item)

        # Check if should flush
        if len(self._buffer) >= self.batch_size:
            return True

        if time.time() - self._last_flush > self.flush_interval:
            return True

        return False

    def get_batch(self) -> List[Any]:
        """Get current batch and clear buffer."""
        batch = self._buffer[:]
        self._buffer.clear()
        self._last_flush = time.time()
        return batch

    def pending_count(self) -> int:
        """Get number of pending items."""
        return len(self._buffer)


class LogOptimizer:
    """
    Optimize logging for production.

    Reduces log volume while keeping important information.
    """

    @staticmethod
    def configure_for_production():
        """Configure logging for production (minimal logs)."""
        # Silence noisy loggers
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        logging.getLogger("transformers").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        # Set root logger to WARNING
        logging.getLogger().setLevel(logging.WARNING)

        # Keep our app loggers at INFO
        logging.getLogger("api").setLevel(logging.INFO)
        logging.getLogger("services").setLevel(logging.INFO)
        logging.getLogger("db").setLevel(logging.INFO)

        logger.info("Logging optimized for production")

    @staticmethod
    def configure_for_development():
        """Configure logging for development (verbose logs)."""
        # Enable SQL logging
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

        # Set root logger to DEBUG
        logging.getLogger().setLevel(logging.DEBUG)

        logger.info("Logging configured for development")


class SmartPrefetcher:
    """
    Prefetch related data to avoid N+1 queries.

    Simple implementation for common patterns.
    """

    @staticmethod
    async def prefetch_with_join(
        engine,
        main_table: str,
        join_table: str,
        join_condition: str,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Fetch main records with joined data in one query.

        Args:
            engine: Database engine
            main_table: Main table name
            join_table: Table to join
            join_condition: JOIN ON condition
            filters: Optional WHERE filters

        Returns:
            List of records with joined data
        """
        from sqlalchemy import text

        # Build query
        query = f"""
            SELECT
                m.*,
                j.*
            FROM {main_table} m
            LEFT JOIN {join_table} j ON {join_condition}
        """

        # Add filters if provided
        if filters:
            conditions = [f"m.{k} = :{k}" for k in filters.keys()]
            query += " WHERE " + " AND ".join(conditions)

        # Execute
        async with engine.connect() as conn:
            result = await conn.execute(text(query), filters or {})
            rows = result.mappings().all()

        # Group by main record
        grouped = defaultdict(list)
        for row in rows:
            main_id = row.get("id")
            grouped[main_id].append(dict(row))

        return list(grouped.values())


# Global instances for convenience
query_cache = QueryResultCache()
metrics = SimpleMetrics()

# Configure logging based on environment
import os
if os.getenv("ENVIRONMENT") == "production":
    LogOptimizer.configure_for_production()
else:
    LogOptimizer.configure_for_development()


# Example usage
if __name__ == "__main__":
    import asyncio

    async def example():
        # Query cache example
        async def slow_query(query: str, params: Dict):
            await asyncio.sleep(1)  # Simulate slow query
            return {"result": "data"}

        # First call - slow
        result1 = await query_cache.get_or_execute(
            "SELECT * FROM events",
            {"limit": 10},
            slow_query
        )

        # Second call - instant (cached)
        result2 = await query_cache.get_or_execute(
            "SELECT * FROM events",
            {"limit": 10},
            slow_query
        )

        print(f"Cache stats: {query_cache.get_stats()}")

        # Metrics example
        with metrics.timer("operation"):
            await asyncio.sleep(0.1)

        metrics.inc("requests")
        metrics.set_gauge("memory_mb", 123.4)

        print(f"Metrics: {metrics.get_all_stats()}")

    asyncio.run(example())