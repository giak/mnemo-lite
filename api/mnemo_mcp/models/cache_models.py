"""
Pydantic models for Cache Management (EPIC-23 Story 23.6).

Models for cache clearing, cache statistics, and cache layer metrics.
"""
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

from mnemo_mcp.base import MCPBaseResponse


# ============================================================================
# Clear Cache Models
# ============================================================================


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
    entries_cleared: int = Field(
        default=0,
        description="Number of entries cleared (L1 only)"
    )
    impact_warning: str = Field(
        default="Cache cleared - performance may temporarily degrade until cache is repopulated",
        description="Warning about temporary performance impact"
    )


# ============================================================================
# Cache Statistics Models
# ============================================================================


class CacheLayerStats(BaseModel):
    """Statistics for a single cache layer."""
    hit_rate_percent: float = Field(
        description="Cache hit rate (0-100)"
    )
    hits: int = Field(
        description="Total cache hits"
    )
    misses: int = Field(
        description="Total cache misses"
    )
    # L1-specific fields
    size_mb: float = Field(
        default=0,
        description="Cache size in MB (L1 only)"
    )
    entries: int = Field(
        default=0,
        description="Number of cached entries (L1 only)"
    )
    evictions: int = Field(
        default=0,
        description="Number of evictions (L1 only)"
    )
    utilization_percent: float = Field(
        default=0,
        description="Cache utilization percentage (L1 only)"
    )
    # L2-specific fields
    memory_used_mb: float = Field(
        default=0,
        description="Memory used in MB (L2 only)"
    )
    memory_peak_mb: float = Field(
        default=0,
        description="Peak memory used in MB (L2 only)"
    )
    connected: bool = Field(
        default=True,
        description="Connection status (L2 only)"
    )
    errors: int = Field(
        default=0,
        description="Number of errors (L2 only)"
    )


class CacheStatsResponse(MCPBaseResponse):
    """Cache statistics response."""
    l1: CacheLayerStats = Field(
        description="L1 cache stats (in-memory)"
    )
    l2: CacheLayerStats = Field(
        description="L2 cache stats (Redis)"
    )
    cascade: Dict[str, Any] = Field(
        description="Combined cascade metrics (combined_hit_rate_percent, l1_to_l2_promotions)"
    )
    overall_hit_rate: float = Field(
        description="Combined hit rate across all layers (0-100)"
    )
    timestamp: str = Field(
        description="Timestamp of stats snapshot (ISO 8601)"
    )
