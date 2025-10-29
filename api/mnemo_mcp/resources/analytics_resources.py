"""
MCP Analytics Resources (EPIC-23 Story 23.6).

Resources for cache statistics and search analytics.
"""
import structlog
from datetime import datetime
from typing import Optional

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.cache_models import CacheStatsResponse, CacheLayerStats
from mnemo_mcp.models.analytics_models import SearchAnalyticsResponse

logger = structlog.get_logger()


class CacheStatsResource(BaseMCPComponent):
    """
    Resource: cache://stats - Get cache statistics.

    Returns real-time statistics from L1 (in-memory), L2 (Redis), and cascade cache.

    Features:
    - L1 stats: hit rate, size, entries, evictions, utilization
    - L2 stats: hit rate, memory usage, connections, errors
    - Cascade stats: combined hit rate, L2→L1 promotions
    - Graceful degradation when L2 (Redis) is disconnected
    """

    def get_name(self) -> str:
        return "cache://stats"

    async def get(self, ctx: Optional = None) -> dict:
        """
        Get cache statistics.

        Returns:
            CacheStatsResponse with L1, L2, cascade stats
        """
        # Get cache service
        chunk_cache = self._services.get("chunk_cache") if self._services else None
        if not chunk_cache:
            return {
                "success": False,
                "message": "Cache service not available"
            }

        try:
            # Get stats from CascadeCache
            stats = await chunk_cache.stats()

            # Map to Pydantic models
            l1_stats = CacheLayerStats(
                hit_rate_percent=stats["l1"]["hit_rate_percent"],
                hits=stats["l1"]["hits"],
                misses=stats["l1"]["misses"],
                size_mb=stats["l1"]["size_mb"],
                entries=stats["l1"]["entries"],
                evictions=stats["l1"].get("evictions", 0),
                utilization_percent=stats["l1"]["utilization_percent"],
                # L2-specific fields (not applicable for L1)
                memory_used_mb=0,
                memory_peak_mb=0,
                connected=True,  # L1 is always "connected" (in-memory)
                errors=0
            )

            l2_stats = CacheLayerStats(
                hit_rate_percent=stats["l2"]["hit_rate_percent"],
                hits=stats["l2"]["hits"],
                misses=stats["l2"]["misses"],
                memory_used_mb=stats["l2"]["memory_used_mb"],
                memory_peak_mb=stats["l2"]["memory_peak_mb"],
                connected=stats["l2"]["connected"],
                errors=stats["l2"]["errors"],
                # L1-specific fields (not applicable for L2)
                size_mb=0,
                entries=0,
                evictions=0,
                utilization_percent=0
            )

            overall_hit_rate = stats["cascade"]["combined_hit_rate_percent"]

            logger.debug(
                "Cache stats retrieved",
                overall_hit_rate=overall_hit_rate,
                l1_entries=stats["l1"]["entries"],
                l2_connected=stats["l2"]["connected"]
            )

            return {
                "success": True,
                "l1": l1_stats.model_dump(),
                "l2": l2_stats.model_dump(),
                "cascade": stats["cascade"],
                "overall_hit_rate": overall_hit_rate,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Cache statistics retrieved successfully"
            }

        except Exception as e:
            logger.error(
                "Failed to retrieve cache stats",
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "message": f"Failed to retrieve cache stats: {str(e)}",
                "error": str(e)
            }


class SearchAnalyticsResource(BaseMCPComponent):
    """
    Resource: analytics://search - Get search performance analytics.

    Integrates with EPIC-22 MetricsCollector to provide search analytics:
    - Latency percentiles (avg, P50, P95, P99)
    - Throughput (requests per second)
    - Error rates
    - Total query count

    Features:
    - Configurable time period (1-168 hours)
    - PostgreSQL metrics table queries
    - Graceful degradation when MetricsCollector unavailable
    """

    def get_name(self) -> str:
        return "analytics://search"

    async def get(
        self,
        period_hours: int = 24,
        ctx: Optional = None
    ) -> dict:
        """
        Get search analytics for specified period.

        Args:
            period_hours: Analysis period (1-168 hours, default: 24)

        Returns:
            SearchAnalyticsResponse with latency, throughput, errors
        """
        # Validate period
        if not (1 <= period_hours <= 168):
            return {
                "success": False,
                "message": "period_hours must be between 1 and 168 (1 week)"
            }

        # Get metrics collector
        metrics_collector = self._services.get("metrics_collector") if self._services else None
        if not metrics_collector:
            return {
                "success": False,
                "message": "MetricsCollector service not available (EPIC-22 required)"
            }

        try:
            # Collect API metrics (includes search endpoints)
            api_metrics = await metrics_collector.collect_api_metrics(
                period_hours=period_hours
            )

            logger.debug(
                "Search analytics retrieved",
                period_hours=period_hours,
                total_queries=api_metrics["request_count"],
                avg_latency_ms=api_metrics["avg_latency_ms"],
                error_rate=api_metrics["error_rate"]
            )

            return {
                "success": True,
                "period_hours": period_hours,
                "total_queries": api_metrics["request_count"],
                "avg_latency_ms": api_metrics["avg_latency_ms"],
                "p50_latency_ms": api_metrics["p50_latency_ms"],
                "p95_latency_ms": api_metrics["p95_latency_ms"],
                "p99_latency_ms": api_metrics["p99_latency_ms"],
                "requests_per_second": api_metrics["requests_per_second"],
                "error_count": api_metrics["error_count"],
                "error_rate": api_metrics["error_rate"],
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Search analytics for last {period_hours}h retrieved successfully"
            }

        except Exception as e:
            logger.error(
                "Failed to retrieve search analytics",
                period_hours=period_hours,
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "message": f"Failed to retrieve search analytics: {str(e)}",
                "error": str(e)
            }


# Singleton instances for registration
cache_stats_resource = CacheStatsResource()
search_analytics_resource = SearchAnalyticsResource()
