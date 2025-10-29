"""
Pydantic models for Analytics (EPIC-23 Story 23.6).

Models for search analytics and performance metrics.
"""
from typing import Optional
from pydantic import BaseModel, Field

from mnemo_mcp.base import MCPBaseResponse


# ============================================================================
# Search Analytics Models
# ============================================================================


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
    period_hours: int = Field(
        description="Analysis period in hours"
    )
    total_queries: int = Field(
        description="Total search queries in period"
    )
    avg_latency_ms: float = Field(
        description="Average query latency in milliseconds"
    )
    p50_latency_ms: float = Field(
        description="P50 (median) latency in milliseconds"
    )
    p95_latency_ms: float = Field(
        description="P95 latency in milliseconds"
    )
    p99_latency_ms: float = Field(
        description="P99 latency in milliseconds"
    )
    requests_per_second: float = Field(
        description="Average queries per second"
    )
    error_count: int = Field(
        description="Number of failed queries"
    )
    error_rate: float = Field(
        description="Error rate percentage (0-100)"
    )
    timestamp: str = Field(
        description="Timestamp of analysis (ISO 8601)"
    )
