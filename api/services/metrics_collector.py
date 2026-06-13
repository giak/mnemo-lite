"""
EPIC-22 Story 22.1: Metrics Collector Service

Collects metrics from various sources:
- API: Latency, throughput, errors (from metrics table)
- Redis: Hit rate, memory, keys, evictions (from Redis INFO)
- PostgreSQL: Connections, cache hit ratio, slow queries (from pg_stat_*)
- System: CPU, memory, disk (from psutil)

Architecture:
- Async methods for all I/O
- Returns structured dicts (ready for JSON serialization)
- No side effects (pure data collection)
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text
import psutil
import redis.asyncio as aioredis

logger = structlog.get_logger()


class MetricsCollector:
    """Collects system metrics from multiple sources."""

    def __init__(self, db_engine: AsyncEngine, redis_client: aioredis.Redis):
        self.engine = db_engine
        self.redis = redis_client

    async def collect_all(self) -> Dict[str, Any]:
        """
        Collect all metrics in parallel.

        Returns dict with keys: api, redis, postgres, system
        """
        # TODO: Use asyncio.gather for parallel collection (optimization)
        return {
            "api": await self.collect_api_metrics(),
            "redis": await self.collect_redis_metrics(),
            "postgres": await self.collect_postgres_metrics(),
            "system": await self.collect_system_metrics()
        }

    # ====== API Metrics ======

    async def collect_api_metrics(self, period_hours: int = 1) -> Dict[str, Any]:
        """
        Collect API performance metrics from metrics table.

        Returns:
        - avg_latency_ms: Average latency (last 1h)
        - p50_latency_ms: P50 latency
        - p95_latency_ms: P95 latency
        - p99_latency_ms: P99 latency
        - request_count: Total requests
        - requests_per_second: Throughput
        - error_count: Total errors (status >= 400)
        - error_rate: Error rate (%)
        """
        try:
            async with self.engine.connect() as conn:
                # Aggregate latency stats
                query = text("""
                    SELECT
                        COUNT(*) as total_requests,
                        AVG(value) as avg_latency_ms,
                        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50_latency_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99_latency_ms,
                        COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400) as error_count
                    FROM metrics
                    WHERE metric_type = 'api'
                      AND metric_name = 'latency_ms'
                      AND timestamp > NOW() - INTERVAL '1 hour' * :period_hours
                """)

                result = await conn.execute(query, {"period_hours": period_hours})
                row = result.mappings().first()

                if not row or row["total_requests"] == 0:
                    return {
                        "avg_latency_ms": 0,
                        "p50_latency_ms": 0,
                        "p95_latency_ms": 0,
                        "p99_latency_ms": 0,
                        "request_count": 0,
                        "requests_per_second": 0,
                        "error_count": 0,
                        "error_rate": 0
                    }

                total_requests = row["total_requests"]
                error_count = row["error_count"] or 0

                # Calculate requests per second
                requests_per_second = total_requests / (period_hours * 3600)

                return {
                    "avg_latency_ms": round(row["avg_latency_ms"] or 0, 2),
                    "p50_latency_ms": round(row["p50_latency_ms"] or 0, 2),
                    "p95_latency_ms": round(row["p95_latency_ms"] or 0, 2),
                    "p99_latency_ms": round(row["p99_latency_ms"] or 0, 2),
                    "request_count": total_requests,
                    "requests_per_second": round(requests_per_second, 2),
                    "error_count": error_count,
                    "error_rate": round((error_count / total_requests) * 100, 2) if total_requests > 0 else 0
                }

        except Exception as e:
            logger.error("Failed to collect API metrics", error=str(e))
            return {
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "request_count": 0,
                "requests_per_second": 0,
                "error_count": 0,
                "error_rate": 0
            }

    # ====== Redis Metrics ======

    async def collect_redis_metrics(self) -> Dict[str, Any]:
        """
        Collect Redis performance metrics.

        Returns:
        - connected: bool (Redis availability)
        - memory_used_mb: Memory used (MB)
        - memory_max_mb: Max memory (MB)
        - memory_percent: Memory usage (%)
        - keys_total: Total keys
        - hit_rate: Cache hit rate (%)
        - evicted_keys: Keys evicted (LRU)
        - connected_clients: Active connections
        """
        try:
            # Get Redis INFO
            info = await self.redis.info()

            memory_used_bytes = info.get("used_memory", 0)
            memory_max_bytes = info.get("maxmemory", 0)

            # If maxmemory = 0, Redis has no limit (use system memory as fallback)
            if memory_max_bytes == 0:
                memory_max_bytes = 2 * 1024 * 1024 * 1024  # Default 2GB

            memory_used_mb = memory_used_bytes / (1024 * 1024)
            memory_max_mb = memory_max_bytes / (1024 * 1024)
            memory_percent = (memory_used_bytes / memory_max_bytes) * 100 if memory_max_bytes > 0 else 0

            # Calculate hit rate
            keyspace_hits = info.get("keyspace_hits", 0)
            keyspace_misses = info.get("keyspace_misses", 0)
            total_requests = keyspace_hits + keyspace_misses
            hit_rate = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0

            # Keys count
            keys_total = await self.redis.dbsize()

            return {
                "connected": True,
                "memory_used_mb": round(memory_used_mb, 2),
                "memory_max_mb": round(memory_max_mb, 2),
                "memory_percent": round(memory_percent, 2),
                "keys_total": keys_total,
                "hit_rate": round(hit_rate, 2),
                "evicted_keys": info.get("evicted_keys", 0),
                "connected_clients": info.get("connected_clients", 0)
            }

        except Exception as e:
            logger.error("Failed to collect Redis metrics", error=str(e))
            return {
                "connected": False,
                "memory_used_mb": 0,
                "memory_max_mb": 0,
                "memory_percent": 0,
                "keys_total": 0,
                "hit_rate": 0,
                "evicted_keys": 0,
                "connected_clients": 0
            }

    # ====== PostgreSQL Metrics ======

    async def collect_postgres_metrics(self) -> Dict[str, Any]:
        """
        Collect PostgreSQL performance metrics.

        Returns:
        - connections_active: Active connections
        - connections_idle: Idle connections
        - connections_total: Total connections
        - connections_max: Max connections allowed
        - cache_hit_ratio: Buffer cache hit ratio (%)
        - db_size_mb: Database size (MB)
        - slow_queries_count: Slow queries (>100ms) in last 1h
        """
        try:
            async with self.engine.connect() as conn:
                # Active connections
                conn_query = text("""
                    SELECT
                        COUNT(*) FILTER (WHERE state = 'active') as active,
                        COUNT(*) FILTER (WHERE state = 'idle') as idle,
                        COUNT(*) as total
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
                conn_result = await conn.execute(conn_query)
                conn_row = conn_result.mappings().first()

                # Max connections
                max_conn_query = text("SHOW max_connections")
                max_conn_result = await conn.execute(max_conn_query)
                max_connections = int(max_conn_result.scalar())

                # Cache hit ratio
                cache_query = text("""
                    SELECT
                        CASE
                            WHEN (sum(heap_blks_hit) + sum(heap_blks_read)) = 0 THEN 100
                            ELSE round(
                                sum(heap_blks_hit)::numeric /
                                (sum(heap_blks_hit) + sum(heap_blks_read)) * 100,
                                2
                            )
                        END as cache_hit_ratio
                    FROM pg_statio_user_tables
                """)
                cache_result = await conn.execute(cache_query)
                cache_hit_ratio = cache_result.scalar() or 100

                # Database size
                size_query = text("SELECT pg_database_size(current_database()) as size")
                size_result = await conn.execute(size_query)
                db_size_bytes = size_result.scalar()
                db_size_mb = db_size_bytes / (1024 * 1024)

                # Slow queries (from metrics table, if we store query times there)
                slow_query = text("""
                    SELECT COUNT(*) as count
                    FROM metrics
                    WHERE metric_type = 'api'
                      AND metric_name = 'latency_ms'
                      AND value > 100
                      AND timestamp > NOW() - INTERVAL '1 hour'
                """)
                slow_result = await conn.execute(slow_query)
                slow_queries_count = slow_result.scalar() or 0

                return {
                    "connections_active": conn_row["active"] or 0,
                    "connections_idle": conn_row["idle"] or 0,
                    "connections_total": conn_row["total"] or 0,
                    "connections_max": max_connections,
                    "cache_hit_ratio": float(cache_hit_ratio),
                    "db_size_mb": round(db_size_mb, 2),
                    "slow_queries_count": slow_queries_count
                }

        except Exception as e:
            logger.error("Failed to collect PostgreSQL metrics", error=str(e))
            return {
                "connections_active": 0,
                "connections_idle": 0,
                "connections_total": 0,
                "connections_max": 0,
                "cache_hit_ratio": 0,
                "db_size_mb": 0,
                "slow_queries_count": 0
            }

    # ====== System Metrics ======

    async def collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system resource metrics (CPU, memory, disk).

        Returns:
        - cpu_percent: CPU usage (%)
        - cpu_count: Number of CPUs
        - memory_used_mb: Memory used (MB)
        - memory_total_mb: Total memory (MB)
        - memory_percent: Memory usage (%)
        - disk_used_gb: Disk used (GB)
        - disk_total_gb: Total disk (GB)
        - disk_percent: Disk usage (%)
        """
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()

            # Memory
            memory = psutil.virtual_memory()
            memory_used_mb = memory.used / (1024 * 1024)
            memory_total_mb = memory.total / (1024 * 1024)
            memory_percent = memory.percent

            # Disk
            disk = psutil.disk_usage("/")
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_total_gb = disk.total / (1024 * 1024 * 1024)
            disk_percent = disk.percent

            return {
                "cpu_percent": round(cpu_percent, 2),
                "cpu_count": cpu_count,
                "memory_used_mb": round(memory_used_mb, 2),
                "memory_total_mb": round(memory_total_mb, 2),
                "memory_percent": round(memory_percent, 2),
                "disk_used_gb": round(disk_used_gb, 2),
                "disk_total_gb": round(disk_total_gb, 2),
                "disk_percent": round(disk_percent, 2)
            }

        except Exception as e:
            logger.error("Failed to collect system metrics", error=str(e))
            return {
                "cpu_percent": 0,
                "cpu_count": 0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "memory_percent": 0,
                "disk_used_gb": 0,
                "disk_total_gb": 0,
                "disk_percent": 0
            }
