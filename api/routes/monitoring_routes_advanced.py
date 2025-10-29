"""
EPIC-22 Story 22.1/22.3/22.5/22.7: Advanced Monitoring Routes

New endpoints:
- GET /api/monitoring/advanced/summary → All metrics summary (for dashboard)
- GET /api/monitoring/advanced/logs/stream → SSE logs stream
- GET /api/monitoring/advanced/performance/endpoints → API performance by endpoint (Story 22.5)
- GET /api/monitoring/advanced/performance/slow-endpoints → Slow endpoints with impact (Story 22.5)
- GET /api/monitoring/advanced/performance/error-hotspots → Error breakdown by endpoint (Story 22.5)
- GET /api/monitoring/advanced/alerts → Get active alerts (Story 22.7)
- GET /api/monitoring/advanced/alerts/counts → Get alert counts by severity (Story 22.7)
- POST /api/monitoring/advanced/alerts/{alert_id}/acknowledge → Acknowledge alert (Story 22.7)
"""

import asyncio
import structlog
from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import StreamingResponse
from services.metrics_collector import MetricsCollector
from services.logs_buffer import get_logs_buffer
from dependencies import get_metrics_collector, get_endpoint_performance_service, get_monitoring_alert_service
import json

logger = structlog.get_logger()

router = APIRouter(prefix="/api/monitoring/advanced", tags=["Monitoring Advanced"])


@router.get("/summary")
async def get_advanced_summary(
    collector: MetricsCollector = Depends(get_metrics_collector)
):
    """
    Get comprehensive metrics summary for dashboard.

    Returns:
    {
      "api": {...},
      "redis": {...},
      "postgres": {...},
      "system": {...}
    }
    """
    return await collector.collect_all()


@router.get("/logs/stream")
async def logs_stream():
    """
    Server-Sent Events (SSE) stream for real-time logs.

    Streams log entries from the LogsBuffer to the client.

    Returns:
        StreamingResponse with text/event-stream content-type
    """
    async def event_generator():
        """Generate SSE events from logs buffer."""
        logs_buffer = get_logs_buffer()
        last_sent_index = 0

        # Send initial logs (last 50)
        initial_logs = logs_buffer.get_recent_logs(count=50)
        for log in reversed(initial_logs):  # Send oldest first
            yield f"data: {json.dumps(log)}\n\n"
            last_sent_index += 1

        # Stream new logs as they arrive
        try:
            while True:
                await asyncio.sleep(1)  # Poll every second

                # Get all logs and send only new ones
                all_logs = logs_buffer.get_all_logs()
                current_size = len(all_logs)

                if current_size > last_sent_index:
                    # Send new logs (reversed to get oldest→newest)
                    new_logs = list(reversed(all_logs[:current_size - last_sent_index]))
                    for log in new_logs:
                        yield f"data: {json.dumps(log)}\n\n"
                    last_sent_index = current_size

                # Keep-alive ping
                yield f": ping\n\n"

        except asyncio.CancelledError:
            logger.info("SSE logs stream closed by client")
        except Exception as e:
            logger.error("Error in SSE logs stream", error=str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ============================================================================
# EPIC-22 Story 22.5: API Performance by Endpoint
# ============================================================================

@router.get("/performance/endpoints")
async def get_api_performance_by_endpoint(
    period_hours: int = Query(default=1, ge=1, le=168, description="Time window in hours (1h, 24h, 168h)"),
    limit: int = Query(default=50, ge=1, le=100, description="Max number of endpoints to return"),
    service = Depends(get_endpoint_performance_service)
):
    """
    Get API performance stats aggregated by endpoint.

    Analyzes metrics from the last N hours and returns:
    - Request count per endpoint
    - P50/P95/P99 latency percentiles
    - Error count and error rate
    - Throughput (requests per second)

    Args:
        period_hours: Time window (1=1h, 24=1d, 168=1w)
        limit: Max endpoints to return (sorted by request count desc)

    Returns:
        List of endpoint performance stats

    Example:
        GET /api/monitoring/advanced/performance/endpoints?period_hours=1&limit=10

        Response:
        [
          {
            "endpoint": "/api/monitoring/advanced/summary",
            "method": "GET",
            "request_count": 222,
            "avg_latency_ms": 106.3,
            "p50_latency_ms": 95.2,
            "p95_latency_ms": 150.1,
            "p99_latency_ms": 164.6,
            "error_count": 0,
            "error_rate": 0.0,
            "requests_per_second": 0.062
          }
        ]
    """
    logger.info(
        "EPIC-22 Story 22.5: get_api_performance_by_endpoint",
        period_hours=period_hours,
        limit=limit
    )
    return await service.get_endpoint_stats(period_hours=period_hours, limit=limit)


@router.get("/performance/slow-endpoints")
async def get_slow_endpoints(
    threshold_ms: int = Query(default=100, ge=10, le=5000, description="P95 latency threshold in ms"),
    period_hours: int = Query(default=1, ge=1, le=168, description="Time window in hours"),
    service = Depends(get_endpoint_performance_service)
):
    """
    Get endpoints with P95 latency above threshold.

    Identifies slow endpoints and calculates their impact:
    - Impact = calls × (latency - threshold) = time wasted per hour

    This helps prioritize optimization efforts by showing which
    endpoints waste the most time above the target latency.

    Args:
        threshold_ms: P95 latency threshold (default 100ms)
        period_hours: Time window (1=1h, 24=1d, 168=1w)

    Returns:
        List of slow endpoints with impact calculation

    Example:
        GET /api/monitoring/advanced/performance/slow-endpoints?threshold_ms=100

        Response:
        [
          {
            "endpoint": "/v1/code/search/hybrid",
            "request_count": 45,
            "p95_latency_ms": 450.2,
            "target_latency_ms": 100,
            "latency_above_target_ms": 350.2,
            "impact_seconds_wasted_per_hour": 15.75
          }
        ]
    """
    logger.info(
        "EPIC-22 Story 22.5: get_slow_endpoints",
        threshold_ms=threshold_ms,
        period_hours=period_hours
    )
    return await service.get_slow_endpoints(threshold_ms=threshold_ms, period_hours=period_hours)


@router.get("/performance/error-hotspots")
async def get_error_hotspots(
    period_hours: int = Query(default=1, ge=1, le=168, description="Time window in hours"),
    service = Depends(get_endpoint_performance_service)
):
    """
    Get endpoints with errors grouped by status code.

    Provides detailed error breakdown:
    - Total errors per endpoint
    - Error rate (% of requests)
    - Breakdown by HTTP status code (400, 500, etc.)
    - Average latency when errors occur

    Args:
        period_hours: Time window (1=1h, 24=1d, 168=1w)

    Returns:
        List of endpoints with error breakdown

    Example:
        GET /api/monitoring/advanced/performance/error-hotspots?period_hours=24

        Response:
        [
          {
            "endpoint": "/v1/code/search/hybrid",
            "total_errors": 8,
            "total_requests": 45,
            "error_rate": 17.8,
            "status_codes": [
              {"code": "500", "count": 5},
              {"code": "400", "count": 3}
            ],
            "avg_latency_on_error_ms": 520.3
          }
        ]
    """
    logger.info(
        "EPIC-22 Story 22.5: get_error_hotspots",
        period_hours=period_hours
    )
    return await service.get_error_hotspots(period_hours=period_hours)


# ============================================================================
# EPIC-22 Story 22.7: Smart Alerting
# ============================================================================

@router.get("/alerts")
async def get_active_alerts(
    limit: int = Query(default=100, ge=1, le=500, description="Max alerts to return"),
    service = Depends(get_monitoring_alert_service)
):
    """
    Get all unacknowledged alerts (newest first).

    Args:
        limit: Maximum number of alerts to return (default: 100)

    Returns:
        List of alert dictionaries

    Example:
        GET /api/monitoring/advanced/alerts?limit=50

        Response:
        [
          {
            "id": "uuid...",
            "created_at": "2025-10-24T10:30:00Z",
            "alert_type": "memory_high",
            "severity": "critical",
            "message": "System memory usage is 85.7% (threshold: 80%)",
            "value": 85.7,
            "threshold": 80.0,
            "metadata": {}
          }
        ]
    """
    logger.info("EPIC-22 Story 22.7: get_active_alerts", limit=limit)
    return await service.get_active_alerts(limit=limit)


@router.get("/alerts/counts")
async def get_alert_counts(
    service = Depends(get_monitoring_alert_service)
):
    """
    Get count of unacknowledged alerts by severity.

    Returns:
        Dict with counts by severity

    Example:
        GET /api/monitoring/advanced/alerts/counts

        Response:
        {
          "critical": 2,
          "warning": 5,
          "info": 1,
          "total": 8
        }
    """
    logger.info("EPIC-22 Story 22.7: get_alert_counts")
    return await service.get_alert_counts()


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str = Path(..., description="Alert UUID to acknowledge"),
    service = Depends(get_monitoring_alert_service)
):
    """
    Acknowledge an alert.

    Marks alert as acknowledged and sets acknowledged_at timestamp.

    Args:
        alert_id: UUID of alert to acknowledge

    Returns:
        Success status

    Example:
        POST /api/monitoring/advanced/alerts/550e8400-e29b-41d4-a716-446655440000/acknowledge

        Response:
        {
          "success": true,
          "alert_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    """
    logger.info("EPIC-22 Story 22.7: acknowledge_alert", alert_id=alert_id)
    success = await service.acknowledge_alert(alert_id, acknowledged_by="web_ui")

    if not success:
        return {"success": False, "error": "Alert not found or already acknowledged"}

    return {"success": True, "alert_id": alert_id}
