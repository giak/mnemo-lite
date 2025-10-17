"""
Performance monitoring routes for MnemoLite.

Simple endpoints to check performance metrics, cache stats, and system health.
No complex APM - just what's needed for local monitoring.
"""

from fastapi import APIRouter, Depends, Request
from typing import Dict, Any
import psutil
import os
from datetime import datetime

from dependencies import get_db_engine, get_cached_embedding_service
from services.optimization_helpers import query_cache, metrics

router = APIRouter(
    prefix="/performance",
    tags=["Performance"],
    responses={404: {"description": "Not found"}},
)


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Get application metrics.

    Returns counters, timers, and gauges collected during runtime.
    """
    return metrics.get_all_stats()


@router.get("/cache/stats")
async def get_cache_stats(request: Request) -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns stats for query cache and embedding cache.
    """
    stats = {
        "query_cache": query_cache.get_stats()
    }

    # Get embedding cache stats if available
    if hasattr(request.app.state, "embedding_cache"):
        stats["embedding_cache"] = request.app.state.embedding_cache.get_stats()

    # Get cached embedding service stats if available
    if hasattr(request.app.state, "cached_embedding_service"):
        service = request.app.state.cached_embedding_service
        if hasattr(service, "get_cache_stats"):
            stats["embedding_service_cache"] = service.get_cache_stats()

    return stats


@router.post("/cache/clear")
async def clear_caches(request: Request) -> Dict[str, str]:
    """
    Clear all caches.

    Useful for testing or when cache gets stale.
    """
    # Clear query cache
    query_cache.clear()

    # Clear embedding cache if available
    if hasattr(request.app.state, "embedding_cache"):
        request.app.state.embedding_cache.clear()

    # Clear cached embedding service cache if available
    if hasattr(request.app.state, "cached_embedding_service"):
        service = request.app.state.cached_embedding_service
        if hasattr(service, "clear_cache"):
            service.clear_cache()

    return {"status": "All caches cleared"}


@router.get("/system")
async def get_system_info() -> Dict[str, Any]:
    """
    Get system resource usage.

    Returns CPU, memory, and disk usage.
    """
    # CPU info
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()

    # Memory info
    memory = psutil.virtual_memory()
    memory_used_mb = memory.used / 1024 / 1024
    memory_total_mb = memory.total / 1024 / 1024
    memory_percent = memory.percent

    # Disk info
    disk = psutil.disk_usage("/")
    disk_used_gb = disk.used / 1024 / 1024 / 1024
    disk_total_gb = disk.total / 1024 / 1024 / 1024
    disk_percent = disk.percent

    # Process info
    process = psutil.Process(os.getpid())
    process_memory_mb = process.memory_info().rss / 1024 / 1024
    process_cpu_percent = process.cpu_percent()
    process_threads = process.num_threads()

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count
        },
        "memory": {
            "used_mb": round(memory_used_mb, 2),
            "total_mb": round(memory_total_mb, 2),
            "percent": memory_percent
        },
        "disk": {
            "used_gb": round(disk_used_gb, 2),
            "total_gb": round(disk_total_gb, 2),
            "percent": disk_percent
        },
        "process": {
            "memory_mb": round(process_memory_mb, 2),
            "cpu_percent": process_cpu_percent,
            "threads": process_threads
        }
    }


@router.get("/database/pool")
async def get_db_pool_stats(engine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get database connection pool statistics.

    Shows active connections, pool size, and overflow.
    """
    pool = engine.pool

    return {
        "size": pool.size(),
        "checked_in": pool.checked_in_connections,
        "checked_out": pool.checked_out_connections,
        "overflow": pool.overflow(),
        "total": pool.size() + pool.overflow()
    }


@router.get("/database/slow-queries")
async def get_slow_queries(
    engine = Depends(get_db_engine),
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get slowest queries.

    Requires pg_stat_statements extension.
    """
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            # Check if pg_stat_statements is available
            check_query = text("""
                SELECT EXISTS (
                    SELECT FROM pg_extension
                    WHERE extname = 'pg_stat_statements'
                )
            """)
            result = await conn.execute(check_query)
            has_extension = result.scalar()

            if not has_extension:
                return {
                    "error": "pg_stat_statements extension not installed",
                    "hint": "Run: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
                }

            # Get slow queries
            query = text("""
                SELECT
                    query,
                    calls,
                    total_exec_time as total_time_ms,
                    mean_exec_time as mean_time_ms,
                    stddev_exec_time as stddev_time_ms,
                    rows
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat%'
                ORDER BY mean_exec_time DESC
                LIMIT :limit
            """)

            result = await conn.execute(query, {"limit": limit})
            queries = []

            for row in result.mappings():
                queries.append({
                    "query": row["query"][:200],  # Truncate long queries
                    "calls": row["calls"],
                    "mean_time_ms": round(row["mean_time_ms"], 2),
                    "total_time_ms": round(row["total_time_ms"], 2),
                    "rows": row["rows"]
                })

            return {"slow_queries": queries}

    except Exception as e:
        return {"error": str(e)}


@router.get("/database/indexes")
async def get_index_usage(engine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get index usage statistics.

    Shows which indexes are being used and their size.
    """
    from sqlalchemy import text

    async with engine.connect() as conn:
        query = text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                pg_size_pretty(pg_relation_size(indexrelid)) as size
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
            ORDER BY idx_scan DESC
        """)

        result = await conn.execute(query)
        indexes = []

        for row in result.mappings():
            indexes.append({
                "table": row["tablename"],
                "index": row["indexname"],
                "scans": row["scans"],
                "tuples_read": row["tuples_read"],
                "size": row["size"]
            })

        # Identify unused indexes
        unused = [idx for idx in indexes if idx["scans"] == 0]

        return {
            "total_indexes": len(indexes),
            "unused_indexes": len(unused),
            "indexes": indexes[:20],  # Top 20
            "unused": unused
        }


@router.get("/optimize/suggestions")
async def get_optimization_suggestions(
    request: Request,
    engine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get optimization suggestions based on current metrics.

    Analyzes cache hit rates, slow queries, and provides recommendations.
    """
    suggestions = []

    # Check query cache hit rate
    cache_stats = query_cache.get_stats()
    if cache_stats["total_queries"] > 100:
        hit_rate = float(cache_stats["hit_rate"].rstrip("%"))
        if hit_rate < 50:
            suggestions.append({
                "category": "cache",
                "issue": f"Low query cache hit rate: {hit_rate:.1f}%",
                "suggestion": "Consider increasing cache TTL or cache size"
            })

    # Check embedding cache if available
    if hasattr(request.app.state, "embedding_cache"):
        emb_stats = request.app.state.embedding_cache.get_stats()
        if emb_stats["total_requests"] > 100:
            hit_rate = float(emb_stats["hit_rate"].rstrip("%"))
            if hit_rate < 70:
                suggestions.append({
                    "category": "cache",
                    "issue": f"Low embedding cache hit rate: {hit_rate:.1f}%",
                    "suggestion": "Consider pre-warming cache or increasing size"
                })

    # Check database pool
    pool = engine.pool
    if pool.overflow() > 0:
        suggestions.append({
            "category": "database",
            "issue": f"Connection pool overflow: {pool.overflow()} connections",
            "suggestion": "Consider increasing pool_size in configuration"
        })

    # Check system resources
    memory = psutil.virtual_memory()
    if memory.percent > 80:
        suggestions.append({
            "category": "system",
            "issue": f"High memory usage: {memory.percent}%",
            "suggestion": "Consider reducing cache sizes or restarting application"
        })

    # Check process memory
    process = psutil.Process(os.getpid())
    process_memory_mb = process.memory_info().rss / 1024 / 1024
    if process_memory_mb > 1000:  # More than 1GB
        suggestions.append({
            "category": "process",
            "issue": f"High process memory: {process_memory_mb:.0f}MB",
            "suggestion": "Consider reducing batch sizes or cache limits"
        })

    return {
        "suggestions": suggestions,
        "summary": {
            "total_issues": len(suggestions),
            "categories": list(set(s["category"] for s in suggestions))
        }
    }


# Add psutil to requirements
# pip install psutil