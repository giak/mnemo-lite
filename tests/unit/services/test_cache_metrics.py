"""
Unit tests for Cache Metrics Collector (EPIC-10 Story 10.5).

Tests metrics collection, aggregation, and historical tracking.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from services.caches.cache_metrics import (
    CacheMetricsCollector,
    CacheMetricSnapshot,
    get_metrics_collector
)


class TestCacheMetricSnapshot:
    """Test CacheMetricSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a metric snapshot."""
        snapshot = CacheMetricSnapshot(
            timestamp=datetime(2025, 10, 20, 10, 30, 0),
            l1_hit_rate=85.5,
            l1_size_mb=42.3,
            l1_entries=150,
            l1_hits=1000,
            l1_misses=200,
            l1_evictions=10,
            l1_utilization_percent=42.3,
            l2_hit_rate=75.2,
            l2_connected=True,
            l2_hits=500,
            l2_misses=100,
            l2_errors=2,
            l2_memory_used_mb=120.5,
            l2_memory_peak_mb=150.0,
            combined_hit_rate=92.3,
            l1_to_l2_promotions=50
        )

        assert snapshot.l1_hit_rate == 85.5
        assert snapshot.l2_connected is True
        assert snapshot.combined_hit_rate == 92.3

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = CacheMetricSnapshot(
            timestamp=datetime(2025, 10, 20, 10, 30, 0),
            l1_hit_rate=85.5,
            l1_size_mb=42.3,
            l1_entries=150,
            l1_hits=1000,
            l1_misses=200,
            l1_evictions=10,
            l1_utilization_percent=42.3,
            l2_hit_rate=75.2,
            l2_connected=True,
            l2_hits=500,
            l2_misses=100,
            l2_errors=2,
            l2_memory_used_mb=120.5,
            l2_memory_peak_mb=150.0,
            combined_hit_rate=92.3,
            l1_to_l2_promotions=50
        )

        data = snapshot.to_dict()

        assert data['l1_hit_rate'] == 85.5
        assert data['timestamp'] == '2025-10-20T10:30:00'
        assert data['l2_connected'] is True


class TestCacheMetricsCollector:
    """Test suite for CacheMetricsCollector."""

    @pytest.mark.anyio
    async def test_collector_initialization(self):
        """Test collector initializes correctly."""
        collector = CacheMetricsCollector(max_snapshots=500)

        assert collector.max_snapshots == 500
        assert collector.get_snapshot_count() == 0
        assert len(collector.snapshots) == 0

    @pytest.mark.anyio
    async def test_collect_snapshot(self):
        """Test collecting a metrics snapshot."""
        # Mock cascade cache
        cascade_cache = MagicMock()
        cascade_cache.stats = AsyncMock(return_value={
            "l1": {
                "hit_rate_percent": 85.5,
                "size_mb": 42.3,
                "entries": 150,
                "hits": 1000,
                "misses": 200,
                "evictions": 10,
                "utilization_percent": 42.3
            },
            "l2": {
                "hit_rate_percent": 75.2,
                "connected": True,
                "hits": 500,
                "misses": 100,
                "errors": 2,
                "memory_used_mb": 120.5,
                "memory_peak_mb": 150.0
            },
            "cascade": {
                "combined_hit_rate_percent": 92.3,
                "l1_to_l2_promotions": 50
            }
        })

        collector = CacheMetricsCollector(max_snapshots=1000)
        snapshot = await collector.collect(cascade_cache)

        # Verify snapshot was collected
        assert collector.get_snapshot_count() == 1
        assert snapshot.l1_hit_rate == 85.5
        assert snapshot.l2_hit_rate == 75.2
        assert snapshot.combined_hit_rate == 92.3

    @pytest.mark.anyio
    async def test_collect_multiple_snapshots(self):
        """Test collecting multiple snapshots."""
        cascade_cache = MagicMock()
        cascade_cache.stats = AsyncMock(return_value={
            "l1": {
                "hit_rate_percent": 85.0,
                "size_mb": 40.0,
                "entries": 100,
                "hits": 1000,
                "misses": 200,
                "evictions": 5,
                "utilization_percent": 40.0
            },
            "l2": {
                "hit_rate_percent": 75.0,
                "connected": True,
                "hits": 500,
                "misses": 100,
                "errors": 0,
                "memory_used_mb": 100.0,
                "memory_peak_mb": 120.0
            },
            "cascade": {
                "combined_hit_rate_percent": 90.0,
                "l1_to_l2_promotions": 50
            }
        })

        collector = CacheMetricsCollector(max_snapshots=1000)

        # Collect 5 snapshots
        for i in range(5):
            await collector.collect(cascade_cache)

        assert collector.get_snapshot_count() == 5

    @pytest.mark.anyio
    async def test_snapshot_trimming(self):
        """Test automatic trimming when max_snapshots exceeded."""
        cascade_cache = MagicMock()
        cascade_cache.stats = AsyncMock(return_value={
            "l1": {
                "hit_rate_percent": 85.0,
                "size_mb": 40.0,
                "entries": 100,
                "hits": 1000,
                "misses": 200,
                "evictions": 5,
                "utilization_percent": 40.0
            },
            "l2": {
                "hit_rate_percent": 75.0,
                "connected": True,
                "hits": 500,
                "misses": 100,
                "errors": 0,
                "memory_used_mb": 100.0,
                "memory_peak_mb": 120.0
            },
            "cascade": {
                "combined_hit_rate_percent": 90.0,
                "l1_to_l2_promotions": 50
            }
        })

        collector = CacheMetricsCollector(max_snapshots=10)

        # Collect 15 snapshots (exceeds max of 10)
        for i in range(15):
            await collector.collect(cascade_cache)

        # Should have trimmed to 10
        assert collector.get_snapshot_count() == 10

    @pytest.mark.anyio
    async def test_get_summary_empty(self):
        """Test get_summary with no snapshots."""
        collector = CacheMetricsCollector(max_snapshots=1000)
        summary = collector.get_summary()

        assert summary['snapshot_count'] == 0
        assert 'message' in summary

    @pytest.mark.anyio
    async def test_get_summary_with_data(self):
        """Test get_summary calculates correct aggregates."""
        cascade_cache = MagicMock()

        # Mock varying stats over time
        stats_sequence = [
            {
                "l1": {
                    "hit_rate_percent": 80.0,
                    "size_mb": 40.0,
                    "entries": 100,
                    "hits": 800,
                    "misses": 200,
                    "evictions": 5,
                    "utilization_percent": 40.0
                },
                "l2": {
                    "hit_rate_percent": 70.0,
                    "connected": True,
                    "hits": 400,
                    "misses": 100,
                    "errors": 0,
                    "memory_used_mb": 100.0,
                    "memory_peak_mb": 120.0
                },
                "cascade": {
                    "combined_hit_rate_percent": 86.0,
                    "l1_to_l2_promotions": 40
                }
            },
            {
                "l1": {
                    "hit_rate_percent": 90.0,
                    "size_mb": 50.0,
                    "entries": 150,
                    "hits": 1800,
                    "misses": 200,
                    "evictions": 10,
                    "utilization_percent": 50.0
                },
                "l2": {
                    "hit_rate_percent": 80.0,
                    "connected": True,
                    "hits": 800,
                    "misses": 200,
                    "errors": 2,
                    "memory_used_mb": 150.0,
                    "memory_peak_mb": 160.0
                },
                "cascade": {
                    "combined_hit_rate_percent": 94.0,
                    "l1_to_l2_promotions": 80
                }
            }
        ]

        collector = CacheMetricsCollector(max_snapshots=1000)

        # Collect both snapshots
        for stats in stats_sequence:
            cascade_cache.stats = AsyncMock(return_value=stats)
            await collector.collect(cascade_cache)

        summary = collector.get_summary(last_n=2)

        # Verify aggregates
        assert summary['snapshot_count'] == 2

        # Average L1 hit rate: (80 + 90) / 2 = 85.0
        assert summary['l1']['avg_hit_rate'] == 85.0

        # Total L1 hits: 800 + 1800 = 2600
        assert summary['l1']['total_hits'] == 2600

        # Average combined hit rate: (86 + 94) / 2 = 90.0
        assert summary['cascade']['avg_combined_hit_rate'] == 90.0

    @pytest.mark.anyio
    async def test_get_recent_snapshots(self):
        """Test retrieving recent snapshots."""
        cascade_cache = MagicMock()
        cascade_cache.stats = AsyncMock(return_value={
            "l1": {
                "hit_rate_percent": 85.0,
                "size_mb": 40.0,
                "entries": 100,
                "hits": 1000,
                "misses": 200,
                "evictions": 5,
                "utilization_percent": 40.0
            },
            "l2": {
                "hit_rate_percent": 75.0,
                "connected": True,
                "hits": 500,
                "misses": 100,
                "errors": 0,
                "memory_used_mb": 100.0,
                "memory_peak_mb": 120.0
            },
            "cascade": {
                "combined_hit_rate_percent": 90.0,
                "l1_to_l2_promotions": 50
            }
        })

        collector = CacheMetricsCollector(max_snapshots=1000)

        # Collect 5 snapshots
        for i in range(5):
            await collector.collect(cascade_cache)

        # Get 3 most recent
        recent = collector.get_recent_snapshots(count=3)

        assert len(recent) == 3
        assert all(isinstance(s, dict) for s in recent)

    @pytest.mark.anyio
    async def test_clear_snapshots(self):
        """Test clearing all snapshots."""
        cascade_cache = MagicMock()
        cascade_cache.stats = AsyncMock(return_value={
            "l1": {
                "hit_rate_percent": 85.0,
                "size_mb": 40.0,
                "entries": 100,
                "hits": 1000,
                "misses": 200,
                "evictions": 5,
                "utilization_percent": 40.0
            },
            "l2": {
                "hit_rate_percent": 75.0,
                "connected": True,
                "hits": 500,
                "misses": 100,
                "errors": 0,
                "memory_used_mb": 100.0,
                "memory_peak_mb": 120.0
            },
            "cascade": {
                "combined_hit_rate_percent": 90.0,
                "l1_to_l2_promotions": 50
            }
        })

        collector = CacheMetricsCollector(max_snapshots=1000)

        # Collect some snapshots
        for i in range(5):
            await collector.collect(cascade_cache)

        assert collector.get_snapshot_count() == 5

        # Clear all
        collector.clear()

        assert collector.get_snapshot_count() == 0

    def test_get_metrics_collector_singleton(self):
        """Test singleton instance retrieval."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        # Should return same instance
        assert collector1 is collector2

    @pytest.mark.anyio
    async def test_collect_with_missing_evictions(self):
        """Test collector handles missing evictions field gracefully."""
        cascade_cache = MagicMock()
        cascade_cache.stats = AsyncMock(return_value={
            "l1": {
                "hit_rate_percent": 85.0,
                "size_mb": 40.0,
                "entries": 100,
                "hits": 1000,
                "misses": 200,
                # evictions field missing
                "utilization_percent": 40.0
            },
            "l2": {
                "hit_rate_percent": 75.0,
                "connected": True,
                "hits": 500,
                "misses": 100,
                "errors": 0,
                "memory_used_mb": 100.0,
                "memory_peak_mb": 120.0
            },
            "cascade": {
                "combined_hit_rate_percent": 90.0,
                "l1_to_l2_promotions": 50
            }
        })

        collector = CacheMetricsCollector(max_snapshots=1000)
        snapshot = await collector.collect(cascade_cache)

        # Should default to 0
        assert snapshot.l1_evictions == 0
