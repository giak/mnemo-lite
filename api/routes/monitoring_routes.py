"""
Monitoring routes for MnemoLite.

Provides real-time operational monitoring endpoints for MCO.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/status")
async def get_system_status(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get overall system status.

    Returns:
        - status: "operational" | "degraded" | "critical"
        - timestamp: current time
        - summary: counts by severity
    """
    try:
        async with engine.connect() as conn:
            # Count events by severity (last 24h)
            query = """
                SELECT
                    COALESCE(metadata->>'severity', 'info') as severity,
                    COUNT(*) as count
                FROM events
                WHERE timestamp > NOW() - INTERVAL '24 hours'
                GROUP BY severity
            """
            result = await conn.execute(text(query))
            rows = result.mappings().all()

            severity_counts = {
                "critical": 0,
                "warning": 0,
                "info": 0
            }

            for row in rows:
                severity = row["severity"].lower()
                if severity in severity_counts:
                    severity_counts[severity] = row["count"]

            # Determine overall status
            if severity_counts["critical"] > 0:
                status = "critical"
            elif severity_counts["warning"] > 5:
                status = "degraded"
            else:
                status = "operational"

            return {
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": severity_counts
            }

    except Exception as e:
        logger.error(f"Failed to get system status: {e}", exc_info=True)
        return {
            "status": "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {"critical": 0, "warning": 0, "info": 0},
            "error": str(e)
        }


@router.get("/events/critical")
async def get_critical_events(
    limit: int = Query(10, ge=1, le=50),
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """
    Get recent critical events (last 24h).

    Returns list of critical events with full details.
    """
    try:
        async with engine.connect() as conn:
            query = """
                SELECT
                    id::text,
                    content,
                    metadata,
                    timestamp,
                    EXTRACT(EPOCH FROM (NOW() - timestamp)) as age_seconds
                FROM events
                WHERE metadata->>'severity' = 'critical'
                  AND timestamp > NOW() - INTERVAL '24 hours'
                ORDER BY timestamp DESC
                LIMIT :limit
            """
            result = await conn.execute(text(query), {"limit": limit})
            rows = result.mappings().all()

            events = []
            for row in rows:
                # Format age
                age_seconds = int(row["age_seconds"])
                if age_seconds < 60:
                    age_str = f"{age_seconds}s ago"
                elif age_seconds < 3600:
                    age_str = f"{age_seconds // 60}m ago"
                else:
                    age_str = f"{age_seconds // 3600}h ago"

                events.append({
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "timestamp": row["timestamp"].isoformat(),
                    "age": age_str
                })

            return events

    except Exception as e:
        logger.error(f"Failed to get critical events: {e}", exc_info=True)
        return []


@router.get("/events/timeline")
async def get_events_timeline(
    period: str = Query("24h", description="Time period: 24h, 7d, 30d"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """
    Get event counts over time for timeline chart.

    Returns hourly buckets for 24h, daily buckets for longer periods.
    """
    try:
        async with engine.connect() as conn:
            # Parse period
            period_map = {
                "24h": ("1 hour", "hour"),
                "7d": ("7 days", "day"),
                "30d": ("30 days", "day")
            }

            interval, trunc = period_map.get(period, ("1 day", "hour"))

            # Build query
            query = f"""
                SELECT
                    date_trunc('{trunc}', timestamp) as bucket,
                    COUNT(*) as count
                FROM events
                WHERE timestamp > NOW() - INTERVAL '{interval}'
            """

            params = {}

            if severity:
                query += " AND metadata->>'severity' = :severity"
                params["severity"] = severity

            query += """
                GROUP BY bucket
                ORDER BY bucket
            """

            result = await conn.execute(text(query), params)
            rows = result.mappings().all()

            timeline = []
            for row in rows:
                timeline.append({
                    "time": row["bucket"].isoformat(),
                    "count": row["count"]
                })

            return timeline

    except Exception as e:
        logger.error(f"Failed to get events timeline: {e}", exc_info=True)
        return []


@router.get("/events/distribution")
async def get_events_distribution(
    period: str = Query("24h", description="Time period"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get event distribution by various dimensions.

    Returns:
        - by_severity: counts by severity level
        - by_project: counts by project
        - by_category: counts by category
    """
    try:
        async with engine.connect() as conn:
            # Parse period
            period_map = {
                "24h": "1 hour",
                "7d": "7 days",
                "30d": "30 days"
            }
            interval = period_map.get(period, "1 day")

            # By severity
            severity_query = """
                SELECT
                    COALESCE(metadata->>'severity', 'info') as severity,
                    COUNT(*) as count
                FROM events
                WHERE timestamp > NOW() - INTERVAL :interval
                GROUP BY severity
                ORDER BY count DESC
            """

            # By project
            project_query = """
                SELECT
                    COALESCE(metadata->>'project', 'unknown') as project,
                    COUNT(*) as count
                FROM events
                WHERE timestamp > NOW() - INTERVAL :interval
                GROUP BY project
                ORDER BY count DESC
                LIMIT 10
            """

            # By category
            category_query = """
                SELECT
                    COALESCE(metadata->>'category', 'unknown') as category,
                    COUNT(*) as count
                FROM events
                WHERE timestamp > NOW() - INTERVAL :interval
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """

            params = {"interval": interval}

            # Execute queries
            sev_result = await conn.execute(text(severity_query), params)
            sev_rows = sev_result.mappings().all()

            proj_result = await conn.execute(text(project_query), params)
            proj_rows = proj_result.mappings().all()

            cat_result = await conn.execute(text(category_query), params)
            cat_rows = cat_result.mappings().all()

            return {
                "by_severity": [
                    {"label": row["severity"], "count": row["count"]}
                    for row in sev_rows
                ],
                "by_project": [
                    {"label": row["project"], "count": row["count"]}
                    for row in proj_rows
                ],
                "by_category": [
                    {"label": row["category"], "count": row["count"]}
                    for row in cat_rows
                ]
            }

    except Exception as e:
        logger.error(f"Failed to get distribution: {e}", exc_info=True)
        return {
            "by_severity": [],
            "by_project": [],
            "by_category": []
        }


@router.get("/metrics")
async def get_system_metrics(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get system-level metrics.

    Returns:
        - total_events: total count
        - db_size_mb: database size
        - cache_hit_ratio: PostgreSQL cache performance
        - active_connections: current DB connections
    """
    try:
        async with engine.connect() as conn:
            # Total events
            total_result = await conn.execute(text("SELECT COUNT(*) as count FROM events"))
            total_count = total_result.scalar()

            # DB size
            size_result = await conn.execute(
                text("SELECT pg_database_size(current_database()) as size")
            )
            db_size_bytes = size_result.scalar()
            db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

            # Cache hit ratio
            cache_result = await conn.execute(text("""
                SELECT
                    CASE
                        WHEN (sum(heap_blks_hit) + sum(heap_blks_read)) = 0 THEN 0
                        ELSE round(sum(heap_blks_hit)::numeric /
                             (sum(heap_blks_hit) + sum(heap_blks_read)), 4)
                    END as cache_hit_ratio
                FROM pg_statio_user_tables
            """))
            cache_ratio = cache_result.scalar() or 0

            # Active connections
            conn_result = await conn.execute(text("""
                SELECT COUNT(*) as count
                FROM pg_stat_activity
                WHERE datname = current_database()
            """))
            active_conns = conn_result.scalar()

            return {
                "total_events": total_count,
                "db_size_mb": db_size_mb,
                "cache_hit_ratio": float(cache_ratio),
                "active_connections": active_conns
            }

    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}", exc_info=True)
        return {
            "total_events": 0,
            "db_size_mb": 0,
            "cache_hit_ratio": 0,
            "active_connections": 0,
            "error": str(e)
        }
