"""
Unit tests for Analytics Tools and Resources (EPIC-23 Story 23.6).

Tests cover:
- ClearCacheTool: elicitation, layer clearing (L1/L2/all), validation, error handling
- CacheStatsResource: stats retrieval, L2 disconnection, graceful degradation
- SearchAnalyticsResource: period validation, metrics integration, error handling
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from mnemo_mcp.tools.analytics_tools import (
    ClearCacheTool,
    clear_cache_tool,
)
from mnemo_mcp.resources.analytics_resources import (
    CacheStatsResource,
    SearchAnalyticsResource,
    cache_stats_resource,
    search_analytics_resource,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    # Mock CascadeCache (chunk_cache)
    mock_l1 = Mock()
    mock_l1.stats = Mock(return_value={
        "hits": 1000,
        "misses": 200,
        "hit_rate_percent": 83.3,
        "size_mb": 45.2,
        "entries": 500,
        "evictions": 50,
        "utilization_percent": 90.4,
    })
    mock_l1.clear = Mock()

    mock_l2 = AsyncMock()
    mock_l2.flush_all = AsyncMock()

    mock_chunk_cache = Mock()
    mock_chunk_cache.l1 = mock_l1
    mock_chunk_cache.l2 = mock_l2
    mock_chunk_cache.stats = AsyncMock(return_value={
        "l1": {
            "hits": 1000,
            "misses": 200,
            "hit_rate_percent": 83.3,
            "size_mb": 45.2,
            "entries": 500,
            "evictions": 50,
            "utilization_percent": 90.4,
        },
        "l2": {
            "hits": 800,
            "misses": 400,
            "hit_rate_percent": 66.7,
            "memory_used_mb": 128.5,
            "memory_peak_mb": 150.0,
            "connected": True,
            "errors": 0,
        },
        "cascade": {
            "combined_hit_rate_percent": 75.0,
            "l1_to_l2_promotions": 150,
        }
    })
    mock_chunk_cache.clear_all = AsyncMock()

    # Mock MetricsCollector
    mock_metrics_collector = AsyncMock()
    mock_metrics_collector.collect_api_metrics = AsyncMock(return_value={
        "request_count": 1500,
        "avg_latency_ms": 125.5,
        "p50_latency_ms": 100.0,
        "p95_latency_ms": 250.0,
        "p99_latency_ms": 450.0,
        "requests_per_second": 15.2,
        "error_count": 15,
        "error_rate": 1.0,
    })

    return {
        "chunk_cache": mock_chunk_cache,
        "metrics_collector": mock_metrics_collector,
    }


@pytest.fixture
def mock_context_elicit_yes():
    """Mock MCP context that confirms elicitation (yes)."""
    mock_ctx = AsyncMock()
    mock_response = Mock()
    mock_response.value = "yes"
    mock_ctx.elicit = AsyncMock(return_value=mock_response)
    return mock_ctx


@pytest.fixture
def mock_context_elicit_no():
    """Mock MCP context that cancels elicitation (no)."""
    mock_ctx = AsyncMock()
    mock_response = Mock()
    mock_response.value = "no"
    mock_ctx.elicit = AsyncMock(return_value=mock_response)
    return mock_ctx


# ============================================================================
# ClearCacheTool Tests (6 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_clear_cache_tool_elicitation_yes(mock_services, mock_context_elicit_yes):
    """Test cache clearing with elicitation confirmed (yes)."""
    tool = ClearCacheTool()
    tool.inject_services(mock_services)

    result = await tool.execute(layer="all", ctx=mock_context_elicit_yes)

    # Should succeed
    assert result["success"] is True
    assert result["layer"] == "all"
    assert "entries_cleared" in result
    assert "impact_warning" in result
    assert "recovery time" in result["impact_warning"].lower()

    # Verify elicitation was called
    mock_context_elicit_yes.elicit.assert_called_once()
    elicit_call_prompt = mock_context_elicit_yes.elicit.call_args[1]["prompt"]
    assert "Clear all cache" in elicit_call_prompt
    assert "High (all caches)" in elicit_call_prompt

    # Verify cache was cleared
    mock_services["chunk_cache"].clear_all.assert_called_once()


@pytest.mark.asyncio
async def test_clear_cache_tool_elicitation_no(mock_services, mock_context_elicit_no):
    """Test cache clearing with elicitation cancelled (no)."""
    tool = ClearCacheTool()
    tool.inject_services(mock_services)

    result = await tool.execute(layer="L1", ctx=mock_context_elicit_no)

    # Should fail with cancellation message
    assert result["success"] is False
    assert "cancelled" in result["message"].lower()
    assert result["layer"] == "L1"

    # Verify elicitation was called
    mock_context_elicit_no.elicit.assert_called_once()

    # Verify cache was NOT cleared
    mock_services["chunk_cache"].l1.clear.assert_not_called()
    mock_services["chunk_cache"].clear_all.assert_not_called()


@pytest.mark.asyncio
async def test_clear_cache_tool_l1_only(mock_services, mock_context_elicit_yes):
    """Test clearing L1 cache only."""
    tool = ClearCacheTool()
    tool.inject_services(mock_services)

    result = await tool.execute(layer="L1", ctx=mock_context_elicit_yes)

    # Should succeed
    assert result["success"] is True
    assert result["layer"] == "L1"
    assert result["entries_cleared"] == 500  # From mock L1 stats

    # Verify only L1 was cleared
    mock_services["chunk_cache"].l1.clear.assert_called_once()
    mock_services["chunk_cache"].l2.flush_all.assert_not_called()
    mock_services["chunk_cache"].clear_all.assert_not_called()


@pytest.mark.asyncio
async def test_clear_cache_tool_l2_only(mock_services, mock_context_elicit_yes):
    """Test clearing L2 cache only."""
    tool = ClearCacheTool()
    tool.inject_services(mock_services)

    result = await tool.execute(layer="L2", ctx=mock_context_elicit_yes)

    # Should succeed
    assert result["success"] is True
    assert result["layer"] == "L2"
    assert result["entries_cleared"] == 0  # L2 doesn't track entries

    # Verify only L2 was cleared
    mock_services["chunk_cache"].l2.flush_all.assert_called_once()
    mock_services["chunk_cache"].l1.clear.assert_not_called()
    mock_services["chunk_cache"].clear_all.assert_not_called()


@pytest.mark.asyncio
async def test_clear_cache_tool_invalid_layer(mock_services):
    """Test clearing with invalid layer parameter."""
    tool = ClearCacheTool()
    tool.inject_services(mock_services)

    result = await tool.execute(layer="L3", ctx=None)

    # Should fail validation
    assert result["success"] is False
    assert "Invalid layer" in result["message"]
    assert "'L3'" in result["message"]

    # Verify cache was NOT cleared
    mock_services["chunk_cache"].l1.clear.assert_not_called()
    mock_services["chunk_cache"].l2.flush_all.assert_not_called()
    mock_services["chunk_cache"].clear_all.assert_not_called()


@pytest.mark.asyncio
async def test_clear_cache_tool_service_unavailable():
    """Test clearing when cache service is unavailable."""
    tool = ClearCacheTool()
    tool.inject_services({"chunk_cache": None})  # Service unavailable

    result = await tool.execute(layer="all", ctx=None)

    # Should fail gracefully
    assert result["success"] is False
    assert "not available" in result["message"].lower()


# ============================================================================
# CacheStatsResource Tests (6 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_cache_stats_resource_success(mock_services):
    """Test successful cache stats retrieval."""
    resource = CacheStatsResource()
    resource.inject_services(mock_services)

    result = await resource.get(ctx=None)

    # Should succeed
    assert result["success"] is True
    assert "l1" in result
    assert "l2" in result
    assert "cascade" in result
    assert "overall_hit_rate" in result
    assert "timestamp" in result
    assert result["message"] == "Cache statistics retrieved successfully"

    # Verify L1 stats
    l1 = result["l1"]
    assert l1["hit_rate_percent"] == 83.3
    assert l1["hits"] == 1000
    assert l1["misses"] == 200
    assert l1["size_mb"] == 45.2
    assert l1["entries"] == 500
    assert l1["evictions"] == 50
    assert l1["utilization_percent"] == 90.4

    # Verify L2 stats
    l2 = result["l2"]
    assert l2["hit_rate_percent"] == 66.7
    assert l2["hits"] == 800
    assert l2["misses"] == 400
    assert l2["memory_used_mb"] == 128.5
    assert l2["connected"] is True
    assert l2["errors"] == 0

    # Verify cascade stats
    assert result["cascade"]["combined_hit_rate_percent"] == 75.0
    assert result["overall_hit_rate"] == 75.0


@pytest.mark.asyncio
async def test_cache_stats_resource_l1_high_hit_rate(mock_services):
    """Test cache stats with high L1 hit rate (>90%)."""
    # Update mock to return high L1 hit rate
    mock_services["chunk_cache"].stats = AsyncMock(return_value={
        "l1": {
            "hits": 9500,
            "misses": 500,
            "hit_rate_percent": 95.0,
            "size_mb": 60.0,
            "entries": 800,
            "evictions": 10,
            "utilization_percent": 80.0,
        },
        "l2": {
            "hits": 200,
            "misses": 300,
            "hit_rate_percent": 40.0,
            "memory_used_mb": 50.0,
            "memory_peak_mb": 60.0,
            "connected": True,
            "errors": 0,
        },
        "cascade": {
            "combined_hit_rate_percent": 97.0,
            "l1_to_l2_promotions": 50,
        }
    })

    resource = CacheStatsResource()
    resource.inject_services(mock_services)

    result = await resource.get(ctx=None)

    # L1 should show high hit rate
    assert result["success"] is True
    assert result["l1"]["hit_rate_percent"] == 95.0
    assert result["overall_hit_rate"] == 97.0


@pytest.mark.asyncio
async def test_cache_stats_resource_l2_disconnected(mock_services):
    """Test cache stats when L2 (Redis) is disconnected."""
    # Update mock to simulate Redis disconnection
    mock_services["chunk_cache"].stats = AsyncMock(return_value={
        "l1": {
            "hits": 1000,
            "misses": 200,
            "hit_rate_percent": 83.3,
            "size_mb": 45.2,
            "entries": 500,
            "evictions": 50,
            "utilization_percent": 90.4,
        },
        "l2": {
            "hits": 0,
            "misses": 0,
            "hit_rate_percent": 0.0,
            "memory_used_mb": 0.0,
            "memory_peak_mb": 0.0,
            "connected": False,  # Disconnected
            "errors": 5,
        },
        "cascade": {
            "combined_hit_rate_percent": 83.3,  # Same as L1 (graceful degradation)
            "l1_to_l2_promotions": 0,
        }
    })

    resource = CacheStatsResource()
    resource.inject_services(mock_services)

    result = await resource.get(ctx=None)

    # Should succeed with graceful degradation
    assert result["success"] is True
    assert result["l2"]["connected"] is False
    assert result["l2"]["errors"] == 5
    assert result["overall_hit_rate"] == 83.3  # Falls back to L1 only


@pytest.mark.asyncio
async def test_cache_stats_resource_service_unavailable():
    """Test cache stats when cache service is unavailable."""
    resource = CacheStatsResource()
    resource.inject_services({"chunk_cache": None})  # Service unavailable

    result = await resource.get(ctx=None)

    # Should fail gracefully
    assert result["success"] is False
    assert "not available" in result["message"].lower()


@pytest.mark.asyncio
async def test_cache_stats_resource_timestamp_format(mock_services):
    """Test that timestamp is in ISO 8601 format."""
    resource = CacheStatsResource()
    resource.inject_services(mock_services)

    result = await resource.get(ctx=None)

    # Verify timestamp format
    assert result["success"] is True
    timestamp = result["timestamp"]
    # Should be parseable as ISO 8601
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_cache_stats_resource_singleton():
    """Test that resource singleton is properly initialized."""
    # Verify singleton exists
    assert cache_stats_resource is not None
    assert isinstance(cache_stats_resource, CacheStatsResource)


# ============================================================================
# SearchAnalyticsResource Tests (6 tests)
# ============================================================================

@pytest.mark.asyncio
async def test_search_analytics_resource_success_24h(mock_services):
    """Test successful search analytics retrieval (default 24h)."""
    resource = SearchAnalyticsResource()
    resource.inject_services(mock_services)

    result = await resource.get(period_hours=24, ctx=None)

    # Should succeed
    assert result["success"] is True
    assert result["period_hours"] == 24
    assert result["total_queries"] == 1500
    assert result["avg_latency_ms"] == 125.5
    assert result["p50_latency_ms"] == 100.0
    assert result["p95_latency_ms"] == 250.0
    assert result["p99_latency_ms"] == 450.0
    assert result["requests_per_second"] == 15.2
    assert result["error_count"] == 15
    assert result["error_rate"] == 1.0
    assert "timestamp" in result
    assert "Search analytics for last 24h" in result["message"]

    # Verify MetricsCollector was called
    mock_services["metrics_collector"].collect_api_metrics.assert_called_once_with(
        period_hours=24
    )


@pytest.mark.asyncio
async def test_search_analytics_resource_custom_periods(mock_services):
    """Test search analytics with custom time periods (1h, 168h)."""
    resource = SearchAnalyticsResource()
    resource.inject_services(mock_services)

    # Test 1 hour
    result_1h = await resource.get(period_hours=1, ctx=None)
    assert result_1h["success"] is True
    assert result_1h["period_hours"] == 1

    # Test 168 hours (1 week - max)
    result_168h = await resource.get(period_hours=168, ctx=None)
    assert result_168h["success"] is True
    assert result_168h["period_hours"] == 168


@pytest.mark.asyncio
async def test_search_analytics_resource_period_validation(mock_services):
    """Test search analytics period validation (1-168 hours)."""
    resource = SearchAnalyticsResource()
    resource.inject_services(mock_services)

    # Test period < 1 (invalid)
    result_too_low = await resource.get(period_hours=0, ctx=None)
    assert result_too_low["success"] is False
    assert "must be between 1 and 168" in result_too_low["message"]

    # Test period > 168 (invalid)
    result_too_high = await resource.get(period_hours=169, ctx=None)
    assert result_too_high["success"] is False
    assert "must be between 1 and 168" in result_too_high["message"]

    # Verify MetricsCollector was NOT called for invalid periods
    mock_services["metrics_collector"].collect_api_metrics.assert_not_called()


@pytest.mark.asyncio
async def test_search_analytics_resource_no_data(mock_services):
    """Test search analytics when no data available (0 queries)."""
    # Update mock to return no data
    mock_services["metrics_collector"].collect_api_metrics = AsyncMock(return_value={
        "request_count": 0,
        "avg_latency_ms": 0.0,
        "p50_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
        "p99_latency_ms": 0.0,
        "requests_per_second": 0.0,
        "error_count": 0,
        "error_rate": 0.0,
    })

    resource = SearchAnalyticsResource()
    resource.inject_services(mock_services)

    result = await resource.get(period_hours=24, ctx=None)

    # Should succeed with zeros
    assert result["success"] is True
    assert result["total_queries"] == 0
    assert result["avg_latency_ms"] == 0.0
    assert result["requests_per_second"] == 0.0


@pytest.mark.asyncio
async def test_search_analytics_resource_high_error_rate(mock_services):
    """Test search analytics with high error rate (>10%)."""
    # Update mock to return high error rate
    mock_services["metrics_collector"].collect_api_metrics = AsyncMock(return_value={
        "request_count": 1000,
        "avg_latency_ms": 200.0,
        "p50_latency_ms": 150.0,
        "p95_latency_ms": 500.0,
        "p99_latency_ms": 1000.0,
        "requests_per_second": 10.0,
        "error_count": 150,  # 15% error rate
        "error_rate": 15.0,
    })

    resource = SearchAnalyticsResource()
    resource.inject_services(mock_services)

    result = await resource.get(period_hours=24, ctx=None)

    # Should succeed and report high error rate
    assert result["success"] is True
    assert result["error_count"] == 150
    assert result["error_rate"] == 15.0


@pytest.mark.asyncio
async def test_search_analytics_resource_service_unavailable():
    """Test search analytics when MetricsCollector is unavailable."""
    resource = SearchAnalyticsResource()
    resource.inject_services({"metrics_collector": None})  # Service unavailable

    result = await resource.get(period_hours=24, ctx=None)

    # Should fail gracefully
    assert result["success"] is False
    assert "not available" in result["message"].lower()
    assert "EPIC-22" in result["message"]


# ============================================================================
# Singleton Tests
# ============================================================================

def test_singletons_initialized():
    """Test that all singletons are properly initialized."""
    # Verify tool singleton
    assert clear_cache_tool is not None
    assert isinstance(clear_cache_tool, ClearCacheTool)

    # Verify resource singletons
    assert cache_stats_resource is not None
    assert isinstance(cache_stats_resource, CacheStatsResource)
    assert search_analytics_resource is not None
    assert isinstance(search_analytics_resource, SearchAnalyticsResource)
