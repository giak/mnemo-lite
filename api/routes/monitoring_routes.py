"""
Monitoring routes for MnemoLite.

Provides real-time operational monitoring endpoints for MCO.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])
router_v1 = APIRouter(prefix="/api/v1", tags=["Monitoring v1"])


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


# ============================================================================
# Monitoring v1 Endpoints — Metrics & Alerts
# ============================================================================

@router_v1.get("/monitoring/latency")
async def get_latency_metrics(
    hours: int = Query(default=24, ge=1, le=168),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get API latency aggregated by hour for the last N hours.

    Returns avg, p95, max and count per hour bucket.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        date_trunc('hour', timestamp) AS hour,
                        AVG(value) AS avg,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95,
                        MAX(value) AS max,
                        COUNT(*) AS count
                    FROM metrics
                    WHERE metric_type = 'api'
                      AND metric_name = 'latency_ms'
                      AND timestamp >= NOW() - make_interval(hours => :hours)
                    GROUP BY hour
                    ORDER BY hour
                """),
                {"hours": hours}
            )
            rows = result.fetchall()

            data = [
                {
                    "hour": row.hour.isoformat(),
                    "avg": round(float(row.avg), 2),
                    "p95": round(float(row.p95), 2),
                    "max": round(float(row.max), 2),
                    "count": row.count,
                }
                for row in rows
            ]

            return {"data": data}

    except Exception as e:
        logger.error(f"Failed to get latency metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve latency metrics.")


@router_v1.get("/alerts/summary")
async def get_alerts_summary(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get alert counts grouped by type and severity.

    Returns unacknowledged and total counts per alert_type/severity pair.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        alert_type,
                        severity,
                        COUNT(*) FILTER (WHERE NOT acknowledged) AS unacked,
                        COUNT(*) AS total
                    FROM alerts
                    GROUP BY alert_type, severity
                    ORDER BY severity DESC, total DESC
                """)
            )
            rows = result.fetchall()

            data = [
                {
                    "alert_type": row.alert_type,
                    "severity": row.severity,
                    "unacked": row.unacked,
                    "total": row.total,
                }
                for row in rows
            ]

            return {"data": data}

    except Exception as e:
        logger.error(f"Failed to get alerts summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts summary.")


@router_v1.get("/alerts/recent")
async def get_recent_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    severity: Optional[str] = Query(default=None),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get recent alerts, optionally filtered by severity.
    """
    try:
        async with engine.connect() as conn:
            query = """
                SELECT
                    id::text,
                    alert_type,
                    severity,
                    message,
                    created_at,
                    value,
                    threshold,
                    acknowledged
                FROM alerts
            """
            params: Dict[str, Any] = {"limit": limit}

            if severity:
                query += " WHERE severity = :severity"
                params["severity"] = severity

            query += " ORDER BY created_at DESC LIMIT :limit"

            result = await conn.execute(text(query), params)
            rows = result.fetchall()

            data = [
                {
                    "id": row.id,
                    "alert_type": row.alert_type,
                    "severity": row.severity,
                    "message": row.message,
                    "created_at": row.created_at.isoformat(),
                    "value": round(float(row.value), 2),
                    "threshold": round(float(row.threshold), 2),
                    "acknowledged": row.acknowledged,
                }
                for row in rows
            ]

            return {"data": data}

    except Exception as e:
        logger.error(f"Failed to get recent alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve recent alerts.")


@router_v1.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Acknowledge an alert by ID.

    Sets acknowledged=true and records acknowledged_at timestamp.
    """
    try:
        # First check if the alert exists and its state
        async with engine.connect() as conn:
            check = await conn.execute(
                text("SELECT id, acknowledged FROM alerts WHERE id = :alert_id"),
                {"alert_id": alert_id}
            )
            existing = check.fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail="Alert not found.")
            if existing.acknowledged:
                raise HTTPException(status_code=409, detail="Alert is already acknowledged.")

        # Update in a transactional context
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    UPDATE alerts
                    SET acknowledged = TRUE,
                        acknowledged_at = NOW()
                    WHERE id = :alert_id
                      AND NOT acknowledged
                    RETURNING acknowledged_at
                """),
                {"alert_id": alert_id}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Alert not found.")

            return {
                "acknowledged": True,
                "acknowledged_at": row.acknowledged_at.isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert.")
