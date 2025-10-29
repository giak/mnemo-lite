"""
Tests for MCP Analytics & Cache Models (EPIC-23 Priority LOW).

Tests Pydantic models for analytics and cache management including
SearchAnalyticsQuery, SearchAnalyticsResponse, ClearCacheRequest,
ClearCacheResponse, CacheLayerStats, and CacheStatsResponse.
"""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from mnemo_mcp.models.analytics_models import (
    SearchAnalyticsQuery,
    SearchAnalyticsResponse,
)
from mnemo_mcp.models.cache_models import (
    CacheLayerStats,
    CacheStatsResponse,
    ClearCacheRequest,
    ClearCacheResponse,
)


# ============================================================================
# SearchAnalyticsQuery Tests
# ============================================================================


class TestSearchAnalyticsQuery:
    """Test SearchAnalyticsQuery model."""

    def test_default_period(self):
        """Test default period is 24 hours."""
        query = SearchAnalyticsQuery()

        assert query.period_hours == 24

    def test_custom_period(self):
        """Test setting custom period."""
        query = SearchAnalyticsQuery(period_hours=72)

        assert query.period_hours == 72

    def test_period_validation_min(self):
        """Test period must be >= 1."""
        with pytest.raises(ValidationError):
            SearchAnalyticsQuery(period_hours=0)

    def test_period_validation_max(self):
        """Test period must be <= 168 (1 week)."""
        with pytest.raises(ValidationError):
            SearchAnalyticsQuery(period_hours=169)

    def test_valid_period_range(self):
        """Test valid periods within range."""
        for hours in [1, 24, 48, 72, 168]:
            query = SearchAnalyticsQuery(period_hours=hours)
            assert query.period_hours == hours


# ============================================================================
# SearchAnalyticsResponse Tests
# ============================================================================


class TestSearchAnalyticsResponse:
    """Test SearchAnalyticsResponse model."""

    def test_basic_response(self):
        """Test creating analytics response."""
        response = SearchAnalyticsResponse(
            success=True,
            message="Analytics retrieved",
            period_hours=24,
            total_queries=1500,
            avg_latency_ms=85.5,
            p50_latency_ms=75.0,
            p95_latency_ms=150.0,
            p99_latency_ms=250.0,
            requests_per_second=0.0174,
            error_count=3,
            error_rate=0.2,
            timestamp="2025-01-15T12:00:00Z"
        )

        assert response.success is True
        assert response.period_hours == 24
        assert response.total_queries == 1500
        assert response.avg_latency_ms == 85.5
        assert response.p50_latency_ms == 75.0
        assert response.p95_latency_ms == 150.0
        assert response.p99_latency_ms == 250.0
        assert response.requests_per_second == 0.0174
        assert response.error_count == 3
        assert response.error_rate == 0.2

    def test_latency_percentiles(self):
        """Test latency percentile ordering (P50 < P95 < P99)."""
        response = SearchAnalyticsResponse(
            success=True,
            message="Test",
            period_hours=24,
            total_queries=100,
            avg_latency_ms=50.0,
            p50_latency_ms=40.0,
            p95_latency_ms=90.0,
            p99_latency_ms=150.0,
            requests_per_second=0.1,
            error_count=0,
            error_rate=0.0,
            timestamp="2025-01-15T12:00:00Z"
        )

        assert response.p50_latency_ms < response.p95_latency_ms
        assert response.p95_latency_ms < response.p99_latency_ms

    def test_zero_errors(self):
        """Test analytics with zero errors."""
        response = SearchAnalyticsResponse(
            success=True,
            message="Perfect performance",
            period_hours=24,
            total_queries=1000,
            avg_latency_ms=50.0,
            p50_latency_ms=45.0,
            p95_latency_ms=85.0,
            p99_latency_ms=120.0,
            requests_per_second=0.5,
            error_count=0,
            error_rate=0.0,
            timestamp="2025-01-15T12:00:00Z"
        )

        assert response.error_count == 0
        assert response.error_rate == 0.0

    def test_json_serialization(self):
        """Test analytics response serializes to JSON."""
        response = SearchAnalyticsResponse(
            success=True,
            message="Test",
            period_hours=24,
            total_queries=100,
            avg_latency_ms=75.0,
            p50_latency_ms=70.0,
            p95_latency_ms=100.0,
            p99_latency_ms=150.0,
            requests_per_second=0.1,
            error_count=2,
            error_rate=2.0,
            timestamp="2025-01-15T12:00:00Z"
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert data["success"] is True
        assert data["period_hours"] == 24
        assert data["total_queries"] == 100
        assert data["avg_latency_ms"] == 75.0
        assert data["error_rate"] == 2.0


# ============================================================================
# ClearCacheRequest Tests
# ============================================================================


class TestClearCacheRequest:
    """Test ClearCacheRequest model."""

    def test_default_values(self):
        """Test default values (layer=all, confirm=False)."""
        request = ClearCacheRequest()

        assert request.layer == "all"
        assert request.confirm is False

    def test_clear_l1_layer(self):
        """Test clearing L1 layer."""
        request = ClearCacheRequest(layer="L1", confirm=True)

        assert request.layer == "L1"
        assert request.confirm is True

    def test_clear_l2_layer(self):
        """Test clearing L2 layer."""
        request = ClearCacheRequest(layer="L2", confirm=True)

        assert request.layer == "L2"
        assert request.confirm is True

    def test_clear_all_layers(self):
        """Test clearing all layers."""
        request = ClearCacheRequest(layer="all", confirm=True)

        assert request.layer == "all"
        assert request.confirm is True

    def test_layer_validation(self):
        """Test layer must be one of L1, L2, or all."""
        with pytest.raises(ValidationError) as exc_info:
            ClearCacheRequest(layer="L3")  # Invalid layer

        error_str = str(exc_info.value).lower()
        assert "literal" in error_str or "input should be" in error_str

    def test_confirm_flag(self):
        """Test confirmation flag behavior."""
        request_no_confirm = ClearCacheRequest(layer="all", confirm=False)
        request_confirm = ClearCacheRequest(layer="all", confirm=True)

        assert request_no_confirm.confirm is False
        assert request_confirm.confirm is True


# ============================================================================
# ClearCacheResponse Tests
# ============================================================================


class TestClearCacheResponse:
    """Test ClearCacheResponse model."""

    def test_basic_response(self):
        """Test creating cache clear response."""
        response = ClearCacheResponse(
            success=True,
            message="Cache cleared successfully",
            layer="all",
            entries_cleared=150
        )

        assert response.success is True
        assert response.layer == "all"
        assert response.entries_cleared == 150
        assert "performance may temporarily degrade" in response.impact_warning

    def test_l1_clear_response(self):
        """Test L1 clear response with entry count."""
        response = ClearCacheResponse(
            success=True,
            message="L1 cache cleared",
            layer="L1",
            entries_cleared=75
        )

        assert response.layer == "L1"
        assert response.entries_cleared == 75

    def test_l2_clear_response(self):
        """Test L2 clear response (entries_cleared=0 for L2)."""
        response = ClearCacheResponse(
            success=True,
            message="L2 cache cleared",
            layer="L2",
            entries_cleared=0
        )

        assert response.layer == "L2"
        assert response.entries_cleared == 0

    def test_default_impact_warning(self):
        """Test default impact warning message."""
        response = ClearCacheResponse(
            success=True,
            message="Cache cleared",
            layer="all"
        )

        assert "performance may temporarily degrade" in response.impact_warning
        assert "repopulated" in response.impact_warning


# ============================================================================
# CacheLayerStats Tests
# ============================================================================


class TestCacheLayerStats:
    """Test CacheLayerStats model."""

    def test_l1_stats(self):
        """Test L1 cache statistics."""
        stats = CacheLayerStats(
            hit_rate_percent=85.5,
            hits=1710,
            misses=290,
            size_mb=12.5,
            entries=250,
            evictions=15,
            utilization_percent=62.5
        )

        assert stats.hit_rate_percent == 85.5
        assert stats.hits == 1710
        assert stats.misses == 290
        assert stats.size_mb == 12.5
        assert stats.entries == 250
        assert stats.evictions == 15
        assert stats.utilization_percent == 62.5

    def test_l2_stats(self):
        """Test L2 cache statistics."""
        stats = CacheLayerStats(
            hit_rate_percent=92.0,
            hits=920,
            misses=80,
            memory_used_mb=45.8,
            memory_peak_mb=50.0,
            connected=True,
            errors=0
        )

        assert stats.hit_rate_percent == 92.0
        assert stats.hits == 920
        assert stats.misses == 80
        assert stats.memory_used_mb == 45.8
        assert stats.memory_peak_mb == 50.0
        assert stats.connected is True
        assert stats.errors == 0

    def test_l2_disconnected(self):
        """Test L2 stats when disconnected."""
        stats = CacheLayerStats(
            hit_rate_percent=0.0,
            hits=0,
            misses=0,
            connected=False,
            errors=5
        )

        assert stats.connected is False
        assert stats.errors == 5

    def test_perfect_hit_rate(self):
        """Test cache with 100% hit rate."""
        stats = CacheLayerStats(
            hit_rate_percent=100.0,
            hits=1000,
            misses=0
        )

        assert stats.hit_rate_percent == 100.0
        assert stats.misses == 0

    def test_default_values(self):
        """Test default values for optional fields."""
        stats = CacheLayerStats(
            hit_rate_percent=75.0,
            hits=750,
            misses=250
        )

        # L1-specific defaults
        assert stats.size_mb == 0
        assert stats.entries == 0
        assert stats.evictions == 0
        assert stats.utilization_percent == 0

        # L2-specific defaults
        assert stats.memory_used_mb == 0
        assert stats.memory_peak_mb == 0
        assert stats.connected is True
        assert stats.errors == 0


# ============================================================================
# CacheStatsResponse Tests
# ============================================================================


class TestCacheStatsResponse:
    """Test CacheStatsResponse model."""

    def test_basic_stats_response(self):
        """Test creating cache stats response with nested layers."""
        l1_stats = CacheLayerStats(
            hit_rate_percent=85.0,
            hits=850,
            misses=150,
            size_mb=10.0,
            entries=200,
            evictions=5,
            utilization_percent=50.0
        )

        l2_stats = CacheLayerStats(
            hit_rate_percent=92.0,
            hits=138,
            misses=12,
            memory_used_mb=40.0,
            memory_peak_mb=45.0,
            connected=True,
            errors=0
        )

        response = CacheStatsResponse(
            success=True,
            message="Cache stats retrieved",
            l1=l1_stats,
            l2=l2_stats,
            cascade={
                "combined_hit_rate_percent": 98.8,
                "l1_to_l2_promotions": 138
            },
            overall_hit_rate=98.8,
            timestamp="2025-01-15T12:00:00Z"
        )

        assert response.success is True
        assert response.l1.hit_rate_percent == 85.0
        assert response.l2.hit_rate_percent == 92.0
        assert response.overall_hit_rate == 98.8
        assert response.cascade["combined_hit_rate_percent"] == 98.8
        assert response.cascade["l1_to_l2_promotions"] == 138

    def test_high_cascade_hit_rate(self):
        """Test cache with high cascade hit rate."""
        l1_stats = CacheLayerStats(
            hit_rate_percent=80.0,
            hits=8000,
            misses=2000
        )

        l2_stats = CacheLayerStats(
            hit_rate_percent=95.0,
            hits=1900,
            misses=100
        )

        response = CacheStatsResponse(
            success=True,
            message="High performance cache",
            l1=l1_stats,
            l2=l2_stats,
            cascade={
                "combined_hit_rate_percent": 99.0,
                "l1_to_l2_promotions": 1900
            },
            overall_hit_rate=99.0,
            timestamp="2025-01-15T12:00:00Z"
        )

        assert response.overall_hit_rate == 99.0
        assert response.l1.misses == 2000
        assert response.l2.hits == 1900

    def test_json_serialization(self):
        """Test complete stats response serializes to JSON."""
        l1_stats = CacheLayerStats(
            hit_rate_percent=75.0,
            hits=750,
            misses=250,
            size_mb=5.0,
            entries=100
        )

        l2_stats = CacheLayerStats(
            hit_rate_percent=90.0,
            hits=225,
            misses=25,
            memory_used_mb=20.0
        )

        response = CacheStatsResponse(
            success=True,
            message="Test",
            l1=l1_stats,
            l2=l2_stats,
            cascade={
                "combined_hit_rate_percent": 97.5,
                "l1_to_l2_promotions": 225
            },
            overall_hit_rate=97.5,
            timestamp="2025-01-15T12:00:00Z"
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert data["success"] is True
        assert data["overall_hit_rate"] == 97.5
        assert data["l1"]["hit_rate_percent"] == 75.0
        assert data["l2"]["hit_rate_percent"] == 90.0
        assert data["cascade"]["combined_hit_rate_percent"] == 97.5

    def test_l2_unavailable(self):
        """Test stats when L2 is unavailable."""
        l1_stats = CacheLayerStats(
            hit_rate_percent=85.0,
            hits=850,
            misses=150
        )

        l2_stats = CacheLayerStats(
            hit_rate_percent=0.0,
            hits=0,
            misses=0,
            connected=False,
            errors=1
        )

        response = CacheStatsResponse(
            success=True,
            message="L2 unavailable - L1 only",
            l1=l1_stats,
            l2=l2_stats,
            cascade={
                "combined_hit_rate_percent": 85.0,
                "l1_to_l2_promotions": 0
            },
            overall_hit_rate=85.0,
            timestamp="2025-01-15T12:00:00Z"
        )

        assert response.l2.connected is False
        assert response.l2.errors == 1
        assert response.overall_hit_rate == 85.0  # L1 only
