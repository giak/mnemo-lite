"""
Cache Metrics Collector for EPIC-10 Story 10.5.

Collects and stores cache metrics snapshots over time for historical analysis.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


@dataclass
class CacheMetricSnapshot:
    """Snapshot of cache metrics at a specific timestamp."""

    timestamp: datetime

    # L1 metrics
    l1_hit_rate: float
    l1_size_mb: float
    l1_entries: int
    l1_hits: int
    l1_misses: int
    l1_evictions: int
    l1_utilization_percent: float

    # L2 metrics
    l2_hit_rate: float
    l2_connected: bool
    l2_hits: int
    l2_misses: int
    l2_errors: int
    l2_memory_used_mb: float
    l2_memory_peak_mb: float

    # Cascade metrics
    combined_hit_rate: float
    l1_to_l2_promotions: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class CacheMetricsCollector:
    """
    Collect and manage cache metrics over time.

    Stores up to max_snapshots of historical metrics for analysis and trending.
    Useful for:
    - Dashboard visualizations (time-series charts)
    - Performance trending analysis
    - Capacity planning
    - Anomaly detection
    """

    def __init__(self, max_snapshots: int = 1000):
        """
        Initialize metrics collector.

        Args:
            max_snapshots: Maximum number of snapshots to keep in memory.
                          Older snapshots are automatically evicted (FIFO).
        """
        self.snapshots: List[CacheMetricSnapshot] = []
        self.max_snapshots = max_snapshots

        logger.info(
            "Cache metrics collector initialized",
            max_snapshots=max_snapshots
        )

    async def collect(self, cascade_cache) -> CacheMetricSnapshot:
        """
        Collect current metrics snapshot from cascade cache.

        Args:
            cascade_cache: CascadeCache instance to collect metrics from

        Returns:
            CacheMetricSnapshot with current metrics
        """
        try:
            # Get stats from cascade cache
            stats = await cascade_cache.stats()

            # Create snapshot
            snapshot = CacheMetricSnapshot(
                timestamp=datetime.now(),

                # L1 metrics
                l1_hit_rate=stats["l1"]["hit_rate_percent"],
                l1_size_mb=stats["l1"]["size_mb"],
                l1_entries=stats["l1"]["entries"],
                l1_hits=stats["l1"]["hits"],
                l1_misses=stats["l1"]["misses"],
                l1_evictions=stats["l1"].get("evictions", 0),
                l1_utilization_percent=stats["l1"]["utilization_percent"],

                # L2 metrics
                l2_hit_rate=stats["l2"]["hit_rate_percent"],
                l2_connected=stats["l2"]["connected"],
                l2_hits=stats["l2"]["hits"],
                l2_misses=stats["l2"]["misses"],
                l2_errors=stats["l2"]["errors"],
                l2_memory_used_mb=stats["l2"]["memory_used_mb"],
                l2_memory_peak_mb=stats["l2"]["memory_peak_mb"],

                # Cascade metrics
                combined_hit_rate=stats["cascade"]["combined_hit_rate_percent"],
                l1_to_l2_promotions=stats["cascade"]["l1_to_l2_promotions"]
            )

            # Add to snapshots list
            self.snapshots.append(snapshot)

            # Trim old snapshots if limit exceeded
            if len(self.snapshots) > self.max_snapshots:
                removed_count = len(self.snapshots) - self.max_snapshots
                self.snapshots = self.snapshots[-self.max_snapshots:]

                logger.debug(
                    "Trimmed old cache metric snapshots",
                    removed_count=removed_count,
                    current_count=len(self.snapshots)
                )

            logger.debug(
                "Cache metrics snapshot collected",
                combined_hit_rate=snapshot.combined_hit_rate,
                l1_size_mb=snapshot.l1_size_mb,
                snapshot_count=len(self.snapshots)
            )

            return snapshot

        except Exception as e:
            logger.error("Failed to collect cache metrics snapshot", error=str(e))
            raise

    def get_summary(self, last_n: int = 100) -> Dict[str, Any]:
        """
        Get summary statistics for the last N snapshots.

        Args:
            last_n: Number of recent snapshots to include in summary

        Returns:
            Dictionary with aggregated metrics (averages, totals, etc.)
        """
        if not self.snapshots:
            return {
                "snapshot_count": 0,
                "message": "No metrics collected yet"
            }

        # Get recent snapshots
        recent = self.snapshots[-last_n:]

        if not recent:
            return {
                "snapshot_count": 0,
                "message": "No snapshots available"
            }

        # Calculate aggregates
        summary = {
            "snapshot_count": len(recent),
            "time_range": {
                "start": recent[0].timestamp.isoformat(),
                "end": recent[-1].timestamp.isoformat()
            },

            # L1 averages
            "l1": {
                "avg_hit_rate": sum(s.l1_hit_rate for s in recent) / len(recent),
                "avg_size_mb": sum(s.l1_size_mb for s in recent) / len(recent),
                "avg_entries": sum(s.l1_entries for s in recent) / len(recent),
                "total_hits": sum(s.l1_hits for s in recent),
                "total_misses": sum(s.l1_misses for s in recent),
                "total_evictions": sum(s.l1_evictions for s in recent),
                "avg_utilization_percent": sum(s.l1_utilization_percent for s in recent) / len(recent)
            },

            # L2 averages
            "l2": {
                "avg_hit_rate": sum(s.l2_hit_rate for s in recent) / len(recent),
                "total_hits": sum(s.l2_hits for s in recent),
                "total_misses": sum(s.l2_misses for s in recent),
                "total_errors": sum(s.l2_errors for s in recent),
                "avg_memory_used_mb": sum(s.l2_memory_used_mb for s in recent) / len(recent),
                "max_memory_peak_mb": max(s.l2_memory_peak_mb for s in recent),
                "online_count": sum(1 for s in recent if s.l2_connected),
                "offline_count": sum(1 for s in recent if not s.l2_connected)
            },

            # Cascade averages
            "cascade": {
                "avg_combined_hit_rate": sum(s.combined_hit_rate for s in recent) / len(recent),
                "total_promotions": sum(s.l1_to_l2_promotions for s in recent)
            }
        }

        logger.debug(
            "Cache metrics summary generated",
            snapshot_count=summary["snapshot_count"],
            avg_combined_hit_rate=summary["cascade"]["avg_combined_hit_rate"]
        )

        return summary

    def get_recent_snapshots(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Get the most recent N snapshots.

        Args:
            count: Number of recent snapshots to return

        Returns:
            List of snapshot dictionaries (for JSON serialization)
        """
        recent = self.snapshots[-count:]
        return [snapshot.to_dict() for snapshot in recent]

    def clear(self):
        """Clear all collected snapshots."""
        self.snapshots.clear()
        logger.info("Cache metrics snapshots cleared")

    def get_snapshot_count(self) -> int:
        """Get total number of snapshots collected."""
        return len(self.snapshots)


# Global singleton instance (optional - can be instantiated per-app)
_collector_instance = None


def get_metrics_collector() -> CacheMetricsCollector:
    """Get or create singleton metrics collector instance."""
    global _collector_instance

    if _collector_instance is None:
        _collector_instance = CacheMetricsCollector(max_snapshots=1000)

    return _collector_instance
