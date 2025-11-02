"""
Data models for rich metadata and metrics.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class DetailedMetadata(BaseModel):
    """Detailed metadata for code nodes (JSONB storage)."""
    metadata_id: UUID
    node_id: UUID
    chunk_id: UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComputedMetrics(BaseModel):
    """Computed code quality metrics."""
    metric_id: UUID
    node_id: UUID
    chunk_id: UUID
    repository: str

    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0

    afferent_coupling: int = 0
    efferent_coupling: int = 0

    pagerank_score: Optional[float] = None
    betweenness_centrality: Optional[float] = None

    version: int = 1
    computed_at: datetime

    class Config:
        from_attributes = True


class EdgeWeight(BaseModel):
    """Edge weight and importance metrics."""
    weight_id: UUID
    edge_id: UUID

    call_count: int = 1
    importance_score: float = 1.0
    is_critical_path: bool = False

    version: int = 1
    updated_at: datetime

    class Config:
        from_attributes = True
