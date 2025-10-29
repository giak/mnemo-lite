# EPIC-23 Story 23.6 ULTRATHINK - Analytics & Observability

**Story**: Analytics & Observability (2 pts, ~7h)
**Date**: 2025-10-28
**Status**: 📝 DESIGN PHASE

---

## 📋 EXECUTIVE SUMMARY

### Story Overview
Implement **3 MCP components** for cache management and search analytics:
1. **clear_cache tool** - Admin cache clearing with elicitation (L1/L2/all layers)
2. **cache://stats resource** - Real-time cache statistics (L1/L2/cascade metrics)
3. **analytics://search resource** - Search performance analytics (EPIC-22 integration)

**Note**: Sub-Story 23.6.4 (SSE real-time streaming) is **deferred to Story 23.8** (HTTP Transport) as SSE is not supported in stdio mode (Claude Desktop).

### Key Deliverables
- 1 Tool: `clear_cache` (with elicitation)
- 2 Resources: `cache://stats`, `analytics://search`
- 3 Pydantic models (ClearCacheRequest, CacheStatsResponse, SearchAnalyticsResponse)
- ~18 unit tests (6 clear_cache + 6 cache_stats + 6 search_analytics)

### Complexity Assessment
**Overall**: ⚡ **LOW COMPLEXITY** (85% reuse existing infrastructure)

**Why Low Complexity?**
- ✅ CascadeCache.stats() already implemented (EPIC-10)
- ✅ MetricsCollector.collect_api_metrics() already implemented (EPIC-22)
- ✅ No new services required (pure MCP wrappers)
- ✅ No DB migrations needed
- ✅ Standard elicitation pattern (reuse from Story 23.3)

**Risk Factors**:
- ⚠️ Cache clearing may impact performance temporarily (expected behavior)
- ⚠️ SSE not available in stdio mode (deferred to HTTP transport)

---

## 1. CONTEXT & BACKGROUND

### 1.1 Previous Stories Integration

**Story 23.5 (Project Indexing)**:
- ✅ Implemented CascadeCache for chunk caching
- ✅ Exposed cache_stats in index://status resource
- ✅ Pattern: Reuse existing services via MCP wrappers

**EPIC-10 (Cache Infrastructure)**:
- ✅ Story 10.1: CodeChunkCache (L1 in-memory LRU)
- ✅ Story 10.2: RedisCache (L2 distributed)
- ✅ Story 10.3: CascadeCache (L1/L2 coordination)
- ✅ Story 10.5: CacheMetricsCollector (historical snapshots)

**EPIC-22 (Observability)**:
- ✅ Story 22.1: MetricsCollector (API/Redis/PostgreSQL/System metrics)
- ✅ Story 22.2: Metrics table + middleware
- ✅ Story 22.3: Alert system

### 1.2 Existing Infrastructure

#### CascadeCache (EPIC-10)
```python
class CascadeCache:
    """L1 (in-memory) + L2 (Redis) + L3 (PostgreSQL) coordination."""

    async def stats(self) -> dict:
        """
        Returns:
        {
            "l1": {
                "hit_rate_percent": float,
                "size_mb": float,
                "entries": int,
                "hits": int,
                "misses": int,
                "evictions": int,
                "utilization_percent": float
            },
            "l2": {
                "hit_rate_percent": float,
                "connected": bool,
                "hits": int,
                "misses": int,
                "errors": int,
                "memory_used_mb": float,
                "memory_peak_mb": float
            },
            "cascade": {
                "combined_hit_rate_percent": float,
                "l1_to_l2_promotions": int
            }
        }
        """

    async def clear_all(self):
        """Clear both L1 and L2 caches."""

    async def invalidate(self, file_path: str):
        """Invalidate specific file across all layers."""
```

#### MetricsCollector (EPIC-22)
```python
class MetricsCollector:
    """Collects metrics from API, Redis, PostgreSQL, System."""

    async def collect_api_metrics(self, period_hours: int = 1) -> dict:
        """
        Returns:
        {
            "avg_latency_ms": float,
            "p50_latency_ms": float,
            "p95_latency_ms": float,
            "p99_latency_ms": float,
            "request_count": int,
            "requests_per_second": float,
            "error_count": int,
            "error_rate": float
        }
        """

    async def collect_redis_metrics(self) -> dict:
        """Redis memory, keys, hit rate, evictions."""

    async def collect_postgres_metrics(self) -> dict:
        """PostgreSQL connections, cache hit ratio, slow queries."""

    async def collect_system_metrics(self) -> dict:
        """CPU, memory, disk usage."""
```

---

## 2. TECHNICAL DESIGN

### 2.1 Sub-Story 23.6.1: Clear Cache Tool

**Objective**: Admin tool to clear cache layers with user confirmation

**Architecture Decision**: Tool (not Resource) - Write operation with side effects

#### Pydantic Models
```python
# File: api/mnemo_mcp/models/cache_models.py

from typing import Literal, Optional
from pydantic import BaseModel, Field
from mnemo_mcp.base import MCPBaseResponse


class ClearCacheRequest(BaseModel):
    """Request to clear cache layers."""
    layer: Literal["L1", "L2", "all"] = Field(
        default="all",
        description="Cache layer to clear (L1=in-memory, L2=Redis, all=both)"
    )
    confirm: bool = Field(
        default=False,
        description="Confirmation flag (set via elicitation)"
    )


class ClearCacheResponse(MCPBaseResponse):
    """Response from cache clear operation."""
    layer: str = Field(description="Layer that was cleared")
    entries_cleared: int = Field(default=0, description="Number of entries cleared")
    impact_warning: str = Field(
        default="Cache cleared - performance may temporarily degrade until cache is repopulated",
        description="Warning about temporary performance impact"
    )
```

#### Tool Implementation
```python
# File: api/mnemo_mcp/tools/analytics_tools.py

from typing import Optional
from mcp.server.fastmcp import Context

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.cache_models import ClearCacheRequest, ClearCacheResponse


class ClearCacheTool(BaseMCPComponent):
    """
    Tool: clear_cache - Clear cache layers (admin operation).

    Uses MCP elicitation for user confirmation (destructive operation).
    """

    def get_name(self) -> str:
        return "clear_cache"

    def get_description(self) -> str:
        return (
            "Clear cache layers (admin operation). "
            "Clears L1 (in-memory), L2 (Redis), or all. "
            "Performance may temporarily degrade."
        )

    async def execute(
        self,
        layer: str = "all",
        ctx: Optional[Context] = None
    ) -> dict:
        """
        Clear cache with elicitation confirmation.

        Args:
            layer: "L1", "L2", or "all" (default: "all")
            ctx: MCP context for elicitation

        Returns:
            ClearCacheResponse with confirmation and stats
        """
        # Validate layer
        if layer not in ("L1", "L2", "all"):
            return {
                "success": False,
                "message": f"Invalid layer '{layer}'. Must be 'L1', 'L2', or 'all'."
            }

        # Elicit confirmation (MCP 2025-06-18)
        if ctx:
            response = await ctx.elicit(
                prompt=(
                    f"Clear {layer} cache? This will:\n"
                    f"• Remove all cached data from {layer}\n"
                    f"• Temporarily degrade performance until cache is repopulated\n"
                    f"• Force all requests to hit slower storage layers\n\n"
                    f"Proceed?"
                ),
                schema={"type": "string", "enum": ["yes", "no"]}
            )

            if response.value == "no":
                return {
                    "success": False,
                    "message": "Cache clear cancelled by user"
                }

        # Get cache service
        chunk_cache = self.services.get("chunk_cache")  # CascadeCache instance
        if not chunk_cache:
            return {
                "success": False,
                "message": "Cache service not available"
            }

        # Clear cache based on layer
        try:
            entries_cleared = 0

            if layer == "L1":
                # Clear L1 only (in-memory)
                chunk_cache.l1.clear()
                entries_cleared = chunk_cache.l1.stats().get("entries", 0)

            elif layer == "L2":
                # Clear L2 only (Redis)
                await chunk_cache.l2.flush_all()
                # L2 doesn't track entries, use Redis INFO

            elif layer == "all":
                # Clear both L1 and L2
                await chunk_cache.clear_all()
                entries_cleared = chunk_cache.l1.stats().get("entries", 0)

            return {
                "success": True,
                "layer": layer,
                "entries_cleared": entries_cleared,
                "impact_warning": (
                    f"Cache {layer} cleared successfully. "
                    f"Performance may temporarily degrade until cache is repopulated."
                ),
                "message": f"Cache {layer} cleared successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to clear cache: {str(e)}",
                "error": str(e)
            }


# Singleton instance
clear_cache_tool = ClearCacheTool()
```

#### Tests
```python
# File: tests/mnemo_mcp/test_analytics_tools.py

@pytest.mark.asyncio
async def test_clear_cache_l1_with_elicitation_yes():
    """Test clear L1 cache with user confirmation."""
    # Mock services and elicitation response
    # Verify L1 cleared, L2 untouched

@pytest.mark.asyncio
async def test_clear_cache_elicitation_no():
    """Test cache clear cancelled by user."""
    # Mock elicitation returning "no"
    # Verify cache NOT cleared

@pytest.mark.asyncio
async def test_clear_cache_all():
    """Test clear all cache layers."""
    # Verify both L1 and L2 cleared

@pytest.mark.asyncio
async def test_clear_cache_invalid_layer():
    """Test invalid layer parameter."""
    # Verify error returned

@pytest.mark.asyncio
async def test_clear_cache_service_unavailable():
    """Test cache service not available."""

@pytest.mark.asyncio
async def test_clear_cache_without_context():
    """Test clearing without elicitation context."""
    # Should proceed without confirmation (API mode)
```

---

### 2.2 Sub-Story 23.6.2: Cache Stats Resource

**Objective**: Resource exposing real-time cache statistics

**Architecture Decision**: Resource (not Tool) - Read-only operation

#### Pydantic Models
```python
# File: api/mnemo_mcp/models/cache_models.py

from typing import Dict, Any
from pydantic import BaseModel, Field


class CacheLayerStats(BaseModel):
    """Statistics for a single cache layer."""
    hit_rate_percent: float = Field(description="Cache hit rate (0-100)")
    hits: int = Field(description="Total cache hits")
    misses: int = Field(description="Total cache misses")
    size_mb: float = Field(default=0, description="Cache size in MB (L1 only)")
    entries: int = Field(default=0, description="Number of cached entries (L1 only)")
    evictions: int = Field(default=0, description="Number of evictions (L1 only)")
    utilization_percent: float = Field(default=0, description="Cache utilization (L1 only)")
    memory_used_mb: float = Field(default=0, description="Memory used (L2 only)")
    connected: bool = Field(default=True, description="Connection status (L2 only)")


class CacheStatsResponse(MCPBaseResponse):
    """Cache statistics response."""
    l1: CacheLayerStats = Field(description="L1 cache stats (in-memory)")
    l2: CacheLayerStats = Field(description="L2 cache stats (Redis)")
    cascade: Dict[str, Any] = Field(description="Combined cascade metrics")
    overall_hit_rate: float = Field(description="Combined hit rate across all layers")
    timestamp: str = Field(description="Timestamp of stats snapshot (ISO 8601)")
```

#### Resource Implementation
```python
# File: api/mnemo_mcp/resources/analytics_resources.py

from datetime import datetime
from typing import Optional

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.cache_models import (
    CacheStatsResponse,
    CacheLayerStats,
)


class CacheStatsResource(BaseMCPComponent):
    """
    Resource: cache://stats - Get cache statistics.

    Returns real-time statistics from L1, L2, and cascade cache.
    """

    async def get(self, ctx: Optional = None) -> dict:
        """
        Get cache statistics.

        Returns:
            CacheStatsResponse with L1, L2, cascade stats
        """
        # Get cache service
        chunk_cache = self.services.get("chunk_cache")
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
            )

            l2_stats = CacheLayerStats(
                hit_rate_percent=stats["l2"]["hit_rate_percent"],
                hits=stats["l2"]["hits"],
                misses=stats["l2"]["misses"],
                memory_used_mb=stats["l2"]["memory_used_mb"],
                connected=stats["l2"]["connected"],
            )

            return {
                "success": True,
                "l1": l1_stats.model_dump(),
                "l2": l2_stats.model_dump(),
                "cascade": stats["cascade"],
                "overall_hit_rate": stats["cascade"]["combined_hit_rate_percent"],
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Cache statistics retrieved successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to retrieve cache stats: {str(e)}",
                "error": str(e)
            }


# Singleton instance
cache_stats_resource = CacheStatsResource()
```

#### Tests
```python
@pytest.mark.asyncio
async def test_cache_stats_success():
    """Test successful cache stats retrieval."""
    # Mock chunk_cache.stats() returning valid stats
    # Verify response structure

@pytest.mark.asyncio
async def test_cache_stats_l1_high_hit_rate():
    """Test cache stats with high L1 hit rate."""

@pytest.mark.asyncio
async def test_cache_stats_l2_disconnected():
    """Test cache stats when L2 (Redis) is disconnected."""

@pytest.mark.asyncio
async def test_cache_stats_service_unavailable():
    """Test error when cache service not available."""

@pytest.mark.asyncio
async def test_cache_stats_timestamp_format():
    """Test timestamp is valid ISO 8601 format."""

@pytest.mark.asyncio
async def test_cache_stats_singleton_available():
    """Test singleton instance is available."""
```

---

### 2.3 Sub-Story 23.6.3: Search Analytics Resource

**Objective**: Resource exposing search performance analytics (EPIC-22 integration)

**Architecture Decision**: Resource (not Tool) - Read-only operation, integrates with existing MetricsCollector

#### Pydantic Models
```python
# File: api/mnemo_mcp/models/analytics_models.py

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from mnemo_mcp.base import MCPBaseResponse


class SearchAnalyticsQuery(BaseModel):
    """Query parameters for search analytics."""
    period_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Time period in hours (1-168)"
    )


class SearchAnalyticsResponse(MCPBaseResponse):
    """Search analytics response."""
    period_hours: int = Field(description="Analysis period in hours")
    total_queries: int = Field(description="Total search queries in period")
    avg_latency_ms: float = Field(description="Average query latency")
    p50_latency_ms: float = Field(description="P50 (median) latency")
    p95_latency_ms: float = Field(description="P95 latency")
    p99_latency_ms: float = Field(description="P99 latency")
    requests_per_second: float = Field(description="Average queries per second")
    error_count: int = Field(description="Number of failed queries")
    error_rate: float = Field(description="Error rate percentage")
    timestamp: str = Field(description="Timestamp of analysis (ISO 8601)")
```

#### Resource Implementation
```python
# File: api/mnemo_mcp/resources/analytics_resources.py

class SearchAnalyticsResource(BaseMCPComponent):
    """
    Resource: analytics://search - Get search performance analytics.

    Integrates with EPIC-22 MetricsCollector to provide search analytics.
    """

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
        metrics_collector = self.services.get("metrics_collector")
        if not metrics_collector:
            return {
                "success": False,
                "message": "MetricsCollector service not available"
            }

        try:
            # Collect API metrics (includes search endpoints)
            api_metrics = await metrics_collector.collect_api_metrics(
                period_hours=period_hours
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
            return {
                "success": False,
                "message": f"Failed to retrieve search analytics: {str(e)}",
                "error": str(e)
            }


# Singleton instance
search_analytics_resource = SearchAnalyticsResource()
```

#### Tests
```python
@pytest.mark.asyncio
async def test_search_analytics_success():
    """Test successful search analytics retrieval."""

@pytest.mark.asyncio
async def test_search_analytics_custom_period():
    """Test analytics with custom period (48h)."""

@pytest.mark.asyncio
async def test_search_analytics_period_validation():
    """Test period validation (out of range)."""

@pytest.mark.asyncio
async def test_search_analytics_no_data():
    """Test analytics when no searches in period."""

@pytest.mark.asyncio
async def test_search_analytics_high_error_rate():
    """Test analytics with high error rate."""

@pytest.mark.asyncio
async def test_search_analytics_service_unavailable():
    """Test error when metrics collector not available."""
```

---

### 2.4 Sub-Story 23.6.4: Real-Time Stats via SSE

**Status**: ⏸️ **DEFERRED TO STORY 23.8** (HTTP Transport)

**Rationale**:
- SSE (Server-Sent Events) requires HTTP transport
- Claude Desktop uses stdio transport (no SSE support)
- Story 23.8 will implement HTTP/SSE server setup
- This sub-story should be moved to Story 23.8

**Implementation Note** (for Story 23.8):
```python
# Future implementation (Story 23.8)

from sse_starlette.sse import EventSourceResponse

@app.get("/analytics/stream")
async def stream_analytics():
    """SSE endpoint for real-time analytics."""
    async def event_generator():
        while True:
            # Get stats
            cache_stats = await cache_stats_resource.get()
            search_analytics = await search_analytics_resource.get(period_hours=1)

            yield {
                "event": "analytics_update",
                "data": json.dumps({
                    "cache": cache_stats,
                    "search": search_analytics,
                    "timestamp": datetime.utcnow().isoformat()
                })
            }

            await asyncio.sleep(5)  # Update every 5s

    return EventSourceResponse(event_generator())
```

---

## 3. FILE STRUCTURE

### New Files (3 files)
```
api/
├── mnemo_mcp/
│   ├── models/
│   │   ├── cache_models.py          # NEW: 80 lines (ClearCacheRequest, CacheStatsResponse, CacheLayerStats)
│   │   └── analytics_models.py      # NEW: 50 lines (SearchAnalyticsQuery, SearchAnalyticsResponse)
│   ├── tools/
│   │   └── analytics_tools.py       # NEW: 120 lines (ClearCacheTool)
│   └── resources/
│       └── analytics_resources.py   # NEW: 160 lines (CacheStatsResource, SearchAnalyticsResource)

tests/
└── mnemo_mcp/
    └── test_analytics_tools.py      # NEW: 350 lines (18 tests)
```

### Modified Files (1 file)
```
api/
└── mnemo_mcp/
    └── server.py                    # MODIFY: Register analytics components
```

**Total New Code**: ~760 lines (implementation + tests)

---

## 4. IMPLEMENTATION PLAN

### Phase 1: Models (1h)
1. Create `cache_models.py` (80 lines)
   - ClearCacheRequest, ClearCacheResponse
   - CacheLayerStats, CacheStatsResponse
2. Create `analytics_models.py` (50 lines)
   - SearchAnalyticsQuery, SearchAnalyticsResponse

### Phase 2: Clear Cache Tool (2h)
1. Create `analytics_tools.py` (120 lines)
   - Implement ClearCacheTool with elicitation
   - Handle L1/L2/all layer clearing
   - Error handling
2. Write tests (6 tests, ~100 lines)
   - Elicitation flows (yes/no)
   - Layer-specific clearing
   - Error scenarios

### Phase 3: Cache Stats Resource (1.5h)
1. Create `analytics_resources.py` - Part 1 (80 lines)
   - Implement CacheStatsResource
   - Map CascadeCache.stats() to Pydantic models
2. Write tests (6 tests, ~100 lines)
   - Success scenarios
   - L2 disconnected
   - Service unavailable

### Phase 4: Search Analytics Resource (1.5h)
1. Update `analytics_resources.py` - Part 2 (+80 lines)
   - Implement SearchAnalyticsResource
   - Integrate with MetricsCollector
2. Write tests (6 tests, ~150 lines)
   - Different time periods
   - No data scenarios
   - Validation

### Phase 5: Server Integration (1h)
1. Update `server.py`
   - Register clear_cache tool
   - Register cache://stats resource
   - Register analytics://search resource
   - Service injection

**Total**: ~7h (matches estimate)

---

## 5. TESTING STRATEGY

### Unit Tests (18 tests)

#### ClearCacheTool (6 tests)
1. ✅ Clear L1 with elicitation (yes)
2. ✅ Clear L2 with elicitation (yes)
3. ✅ Clear all with elicitation (yes)
4. ✅ Elicitation cancelled (no)
5. ✅ Invalid layer parameter
6. ✅ Cache service unavailable

#### CacheStatsResource (6 tests)
1. ✅ Successful stats retrieval
2. ✅ L1 high hit rate scenario
3. ✅ L2 disconnected scenario
4. ✅ Cache service unavailable
5. ✅ Timestamp format validation
6. ✅ Singleton instance available

#### SearchAnalyticsResource (6 tests)
1. ✅ Successful analytics retrieval (24h)
2. ✅ Custom period (48h, 1h, 168h)
3. ✅ Period validation (out of range)
4. ✅ No data in period
5. ✅ High error rate scenario
6. ✅ Metrics collector unavailable

### Integration Tests (3 scenarios)

**Scenario 1: Cache Management Workflow**
```python
async def test_cache_management_workflow():
    # 1. Get initial cache stats
    stats_before = await cache_stats_resource.get()
    assert stats_before["success"]

    # 2. Clear cache (with confirmation)
    clear_result = await clear_cache_tool.execute(layer="all", ctx=mock_ctx)
    assert clear_result["success"]

    # 3. Verify stats show empty cache
    stats_after = await cache_stats_resource.get()
    assert stats_after["l1"]["entries"] == 0
```

**Scenario 2: Analytics Monitoring**
```python
async def test_analytics_monitoring():
    # 1. Perform some searches (via search_code tool)
    # 2. Wait for metrics to be recorded
    # 3. Retrieve analytics
    analytics = await search_analytics_resource.get(period_hours=1)
    assert analytics["success"]
    assert analytics["total_queries"] > 0
```

**Scenario 3: Graceful Degradation**
```python
async def test_graceful_degradation():
    # 1. Disconnect Redis
    # 2. Get cache stats (should show L2 disconnected)
    stats = await cache_stats_resource.get()
    assert not stats["l2"]["connected"]

    # 3. Clear cache (should still work for L1)
    result = await clear_cache_tool.execute(layer="L1", ctx=mock_ctx)
    assert result["success"]
```

---

## 6. DEPENDENCIES & RISKS

### Dependencies
1. ✅ CascadeCache.stats() - Already implemented (EPIC-10 Story 10.3)
2. ✅ CascadeCache.clear_all() - Already implemented
3. ✅ MetricsCollector.collect_api_metrics() - Already implemented (EPIC-22 Story 22.1)
4. ✅ Elicitation pattern - Established in Story 23.3 (delete_memory)

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Cache clearing impacts performance | High | Medium | Expected behavior - show warning in elicitation |
| MetricsCollector unavailable | Low | Medium | Graceful degradation - return error |
| Redis disconnected during clear | Low | Low | Handle exception, clear L1 only |
| SSE not available in stdio | Certain | Low | Defer to Story 23.8 (HTTP transport) |

### Mitigations
1. **Performance Impact**: Clear warning in elicitation prompt
2. **Service Availability**: Check service existence before operations
3. **Error Handling**: Comprehensive try/except blocks with logging
4. **SSE Deferral**: Document in Story 23.8 requirements

---

## 7. PERFORMANCE CONSIDERATIONS

### Cache Clearing Performance
- **L1 Clear**: <1ms (in-memory)
- **L2 Clear**: 10-50ms (Redis FLUSHDB)
- **All Clear**: 10-50ms (parallel)

### Stats Retrieval Performance
- **Cache Stats**: <10ms (in-memory + Redis INFO)
- **Search Analytics**: 50-200ms (PostgreSQL aggregation query)

### Expected Load
- **clear_cache**: Rare admin operation (manual intervention only)
- **cache://stats**: Moderate (monitoring dashboards, ~1 req/min)
- **analytics://search**: Moderate (analytics queries, ~1 req/5min)

**No performance concerns** - All operations are fast or infrequent.

---

## 8. OPEN QUESTIONS & DECISIONS

### 8.1 Questions for User

1. ~~**Sub-Story 23.6.4 (SSE)**: Should we defer to Story 23.8 or skip entirely?~~
   - **DECISION**: Defer to Story 23.8 (HTTP Transport) ✅

2. **Cache clearing scope**: Should clear_cache also clear search result cache (Redis L2)?
   - **RECOMMENDATION**: Yes, clear all Redis keys (not just chunk cache)

3. **Analytics period limits**: Should we enforce max period (1 week)?
   - **RECOMMENDATION**: Yes, max 168 hours (1 week) to prevent expensive queries

4. **Elicitation required**: Should clear_cache ALWAYS require elicitation, or only for "all"?
   - **RECOMMENDATION**: Always require elicitation (destructive operation)

### 8.2 Decisions Made

| Decision | Rationale |
|----------|-----------|
| Defer SSE to Story 23.8 | SSE requires HTTP transport, not available in stdio mode |
| Use existing MetricsCollector | No need to reimplement analytics logic |
| Elicitation for all clear operations | Consistent with delete_memory pattern (Story 23.3) |
| Max period: 1 week | Prevents expensive DB queries |
| Clear all Redis keys | More comprehensive cache management |

---

## 9. TESTING & VALIDATION

### MCP Inspector Testing

**Test Cases**:
1. **clear_cache tool**:
   - Call with layer="L1", verify elicitation prompt
   - Confirm "yes", verify success response
   - Confirm "no", verify cancellation
   - Call with layer="all", verify both layers cleared

2. **cache://stats resource**:
   - Fetch stats, verify JSON structure
   - Verify hit rates, sizes, entries
   - Check timestamp format

3. **analytics://search resource**:
   - Fetch analytics with period_hours=24
   - Verify latency percentiles
   - Check error rate

### Manual Testing Checklist
- [ ] Clear L1 cache, verify performance impact
- [ ] Clear L2 cache, verify Redis FLUSHDB
- [ ] Get cache stats after clearing
- [ ] Get analytics after searches
- [ ] Test with Redis disconnected

---

## 10. DOCUMENTATION

### MCP Component Descriptions

**Tool: clear_cache**
```
Clear cache layers (admin operation). Clears L1 (in-memory), L2 (Redis), or all.
Performance may temporarily degrade until cache is repopulated. Requires user confirmation.
```

**Resource: cache://stats**
```
Get real-time cache statistics for L1, L2, and cascade cache. Includes hit rates, sizes,
evictions, and memory usage.
```

**Resource: analytics://search**
```
Get search performance analytics for a specified time period (1-168 hours). Includes
latency percentiles, throughput, error rates, and total query count.
```

---

## 11. SUCCESS CRITERIA

### Functional Requirements
- ✅ clear_cache tool clears L1/L2/all layers
- ✅ Elicitation prompts user for confirmation
- ✅ cache://stats returns accurate statistics
- ✅ analytics://search returns search metrics
- ✅ All components handle missing services gracefully

### Non-Functional Requirements
- ✅ Cache clearing completes in <100ms
- ✅ Stats retrieval completes in <50ms
- ✅ Analytics query completes in <200ms
- ✅ 18 unit tests passing (100%)
- ✅ MCP 2025-06-18 compliant (elicitation, resource URIs)

### Integration Requirements
- ✅ Integrates with CascadeCache (EPIC-10)
- ✅ Integrates with MetricsCollector (EPIC-22)
- ✅ Registered in MCP server
- ✅ Documented in README

---

## 12. NEXT STEPS

### Pre-Implementation Checklist
- [ ] Review ULTRATHINK with user
- [ ] Get approval on SSE deferral
- [ ] Clarify cache clearing scope (all Redis keys?)
- [ ] Create TODO list for implementation

### Implementation Phases (7h total)
- **Day 1 Morning** (3h): Models + ClearCacheTool + Tests
- **Day 1 Afternoon** (2h): CacheStatsResource + Tests
- **Day 2 Morning** (2h): SearchAnalyticsResource + Tests + Server Integration

---

## 13. SUMMARY & RECOMMENDATIONS

### Key Insights
1. **85% infrastructure reuse** - CascadeCache.stats() and MetricsCollector already exist
2. **No new services needed** - Pure MCP wrappers over existing functionality
3. **SSE deferred** - Requires HTTP transport (Story 23.8)
4. **Simple elicitation pattern** - Reuse from Story 23.3

### Confidence Level
**Overall**: 95% confident in 7h estimate

**Breakdown**:
- Models: 100% (straightforward Pydantic)
- ClearCacheTool: 95% (elicitation pattern proven)
- CacheStatsResource: 95% (direct stats() call)
- SearchAnalyticsResource: 90% (MetricsCollector integration)

**Risk Factors**:
- ✅ All dependencies already implemented
- ✅ No DB migrations required
- ✅ Standard MCP patterns
- ⚠️ SSE deferred to Story 23.8 (expected)

### Go/No-Go Decision
**RECOMMENDATION**: ✅ **GO - Ready for Implementation**

**Rationale**:
- All technical challenges analyzed
- Clear implementation path
- No blockers identified
- Existing infrastructure well-tested
- Elicitation pattern proven (Story 23.3)
- No performance concerns

**Prerequisites**:
- ✅ User approval of design decisions
- ✅ Confirmation on SSE deferral
- ✅ Agreement on 7h estimate (3 sub-stories, not 4)

---

**Status**: 🟢 **READY FOR IMPLEMENTATION**
**Estimated Completion**: 7h (2 days at 3-4h/day)
**Confidence**: 95%
**Complexity**: ⚡ LOW (85% reuse)

**Note**: Sub-Story 23.6.4 (SSE) deferred to Story 23.8 (HTTP Transport). Story 23.6 is now **3 sub-stories** (not 4), maintaining 2 pts / ~7h estimate.
