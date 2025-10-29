"""
EPIC-22 Story 22.5: Endpoint Performance Analyzer

Aggregates API metrics by endpoint from metrics table.

Usage:
    service = EndpointPerformanceService(db_engine)
    stats = await service.get_endpoint_stats(period_hours=1)
"""

import structlog
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = structlog.get_logger()


class EndpointPerformanceService:
    """Analyzes API performance by endpoint."""

    def __init__(self, db_engine: AsyncEngine):
        self.engine = db_engine

    async def get_endpoint_stats(
        self,
        period_hours: int = 1,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get performance stats aggregated by endpoint.

        Args:
            period_hours: Time window (1, 24, 168 for 1h, 1d, 1w)
            limit: Max endpoints to return

        Returns:
            List of endpoint stats sorted by request count desc

        Example:
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
        async with self.engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT
                    metadata->>'endpoint' as endpoint,
                    metadata->>'method' as method,
                    COUNT(*) as request_count,
                    AVG(value) as avg_latency_ms,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99_latency_ms,
                    MIN(value) as min_latency_ms,
                    MAX(value) as max_latency_ms,
                    COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400) as error_count,
                    (COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400)::float /
                     NULLIF(COUNT(*)::float, 0) * 100) as error_rate,
                    -- Throughput
                    (COUNT(*)::float / :period_seconds) as requests_per_second
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'latency_ms'
                  AND timestamp > NOW() - INTERVAL '1 hour' * :period_hours
                  -- Filter out static assets (noise)
                  AND metadata->>'endpoint' NOT LIKE '/static/%'
                GROUP BY metadata->>'endpoint', metadata->>'method'
                HAVING COUNT(*) > 1  -- Filter out single-request endpoints
                ORDER BY request_count DESC
                LIMIT :limit
            """), {
                "period_hours": period_hours,
                "period_seconds": period_hours * 3600,
                "limit": limit
            })

            rows = result.mappings().all()

            # Format response
            endpoints = []
            for row in rows:
                endpoints.append({
                    "endpoint": row["endpoint"],
                    "method": row["method"] or "GET",
                    "request_count": row["request_count"],
                    "avg_latency_ms": round(row["avg_latency_ms"], 2),
                    "p50_latency_ms": round(row["p50_latency_ms"], 2),
                    "p95_latency_ms": round(row["p95_latency_ms"], 2),
                    "p99_latency_ms": round(row["p99_latency_ms"], 2),
                    "min_latency_ms": round(row["min_latency_ms"], 2),
                    "max_latency_ms": round(row["max_latency_ms"], 2),
                    "error_count": row["error_count"] or 0,
                    "error_rate": round(row["error_rate"] or 0, 2),
                    "requests_per_second": round(row["requests_per_second"], 3)
                })

            logger.info(
                "Endpoint stats collected",
                period_hours=period_hours,
                endpoint_count=len(endpoints)
            )

            return endpoints

    async def get_slow_endpoints(
        self,
        threshold_ms: int = 100,
        period_hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get endpoints with P95 latency above threshold.

        Includes impact calculation: how much time is wasted above target.

        Args:
            threshold_ms: P95 latency threshold (default 100ms)
            period_hours: Time window

        Returns:
            List of slow endpoints with impact calculation

        Example:
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
        async with self.engine.connect() as conn:
            result = await conn.execute(text("""
                WITH endpoint_stats AS (
                    SELECT
                        metadata->>'endpoint' as endpoint,
                        COUNT(*) as request_count,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms
                    FROM metrics
                    WHERE metric_type = 'api'
                      AND metric_name = 'latency_ms'
                      AND timestamp > NOW() - INTERVAL '1 hour' * :period_hours
                      AND metadata->>'endpoint' NOT LIKE '/static/%'
                    GROUP BY metadata->>'endpoint'
                    HAVING COUNT(*) > 1
                )
                SELECT
                    endpoint,
                    request_count,
                    p95_latency_ms,
                    -- Impact: how much time wasted above threshold
                    (p95_latency_ms - :threshold) as latency_above_threshold,
                    (request_count * (p95_latency_ms - :threshold) / 1000.0) as impact_seconds_wasted
                FROM endpoint_stats
                WHERE p95_latency_ms > :threshold
                ORDER BY impact_seconds_wasted DESC
            """), {
                "period_hours": period_hours,
                "threshold": threshold_ms
            })

            rows = result.mappings().all()

            slow_endpoints = []
            for row in rows:
                slow_endpoints.append({
                    "endpoint": row["endpoint"],
                    "request_count": row["request_count"],
                    "p95_latency_ms": round(row["p95_latency_ms"], 2),
                    "target_latency_ms": threshold_ms,
                    "latency_above_target_ms": round(row["latency_above_threshold"], 2),
                    "impact_seconds_wasted_per_hour": round(row["impact_seconds_wasted"], 2)
                })

            logger.info(
                "Slow endpoints identified",
                threshold_ms=threshold_ms,
                count=len(slow_endpoints)
            )

            return slow_endpoints

    async def get_error_hotspots(
        self,
        period_hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get endpoints with errors grouped by status code.

        Args:
            period_hours: Time window

        Returns:
            List of endpoints with error breakdown

        Example:
            [
              {
                "endpoint": "/v1/code/search/hybrid",
                "total_errors": 8,
                "error_rate": 17.8,
                "status_codes": [
                  {"code": "500", "count": 5},
                  {"code": "400", "count": 3}
                ],
                "avg_latency_on_error_ms": 520.3
              }
            ]
        """
        async with self.engine.connect() as conn:
            # Get error details
            error_result = await conn.execute(text("""
                SELECT
                    metadata->>'endpoint' as endpoint,
                    metadata->>'status_code' as status_code,
                    COUNT(*) as error_count,
                    AVG(value) as avg_latency_ms
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'latency_ms'
                  AND (metadata->>'status_code')::int >= 400
                  AND timestamp > NOW() - INTERVAL '1 hour' * :period_hours
                  AND metadata->>'endpoint' NOT LIKE '/static/%'
                GROUP BY metadata->>'endpoint', metadata->>'status_code'
                ORDER BY error_count DESC
            """), {"period_hours": period_hours})

            error_rows = error_result.mappings().all()

            # Get total requests per endpoint for error rate calculation
            total_result = await conn.execute(text("""
                SELECT
                    metadata->>'endpoint' as endpoint,
                    COUNT(*) as total_count
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'latency_ms'
                  AND timestamp > NOW() - INTERVAL '1 hour' * :period_hours
                  AND metadata->>'endpoint' NOT LIKE '/static/%'
                GROUP BY metadata->>'endpoint'
            """), {"period_hours": period_hours})

            total_rows = total_result.mappings().all()
            total_by_endpoint = {row["endpoint"]: row["total_count"] for row in total_rows}

            # Group by endpoint
            errors_by_endpoint = {}
            for row in error_rows:
                endpoint = row["endpoint"]
                if endpoint not in errors_by_endpoint:
                    total_requests = total_by_endpoint.get(endpoint, 0)
                    errors_by_endpoint[endpoint] = {
                        "endpoint": endpoint,
                        "total_errors": 0,
                        "total_requests": total_requests,
                        "error_rate": 0.0,
                        "status_codes": [],
                        "avg_latency_on_error_ms": []
                    }

                errors_by_endpoint[endpoint]["total_errors"] += row["error_count"]
                errors_by_endpoint[endpoint]["status_codes"].append({
                    "code": row["status_code"],
                    "count": row["error_count"]
                })
                errors_by_endpoint[endpoint]["avg_latency_on_error_ms"].append(
                    row["avg_latency_ms"] * row["error_count"]
                )

            # Calculate error rates and average latencies
            result = []
            for endpoint, data in errors_by_endpoint.items():
                total_errors = data["total_errors"]
                total_requests = data["total_requests"]
                error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

                # Weighted average latency
                total_weighted_latency = sum(data["avg_latency_on_error_ms"])
                avg_latency = total_weighted_latency / total_errors if total_errors > 0 else 0

                result.append({
                    "endpoint": endpoint,
                    "total_errors": total_errors,
                    "total_requests": total_requests,
                    "error_rate": round(error_rate, 2),
                    "status_codes": data["status_codes"],
                    "avg_latency_on_error_ms": round(avg_latency, 2)
                })

            # Sort by error count desc
            result.sort(key=lambda x: x["total_errors"], reverse=True)

            logger.info(
                "Error hotspots identified",
                count=len(result)
            )

            return result
