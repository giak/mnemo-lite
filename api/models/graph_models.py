"""
Pydantic models for graph nodes and edges (EPIC-06 Phase 2 Story 4).

Models for code dependency graph construction and traversal.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class NodeModel(BaseModel):
    """Node in code dependency graph."""

    node_id: uuid.UUID
    node_type: str  # "function", "class", "method", "module"
    label: str  # Function/class name
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_db_record(cls, record: Dict[str, Any]) -> "NodeModel":
        """Create NodeModel from database record."""
        return cls(
            node_id=record["node_id"],
            node_type=record["node_type"],
            label=record["label"] if record["label"] else "",
            properties=record["properties"] if record["properties"] else {},
            created_at=record["created_at"],
        )

    class Config:
        from_attributes = True


class NodeCreate(BaseModel):
    """Data for creating a new node."""

    node_type: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class EdgeModel(BaseModel):
    """Edge representing code dependency."""

    edge_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relation_type: str  # "calls", "imports", "extends", "uses"
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_db_record(cls, record: Dict[str, Any]) -> "EdgeModel":
        """Create EdgeModel from database record."""
        return cls(
            edge_id=record["edge_id"],
            source_node_id=record["source_node_id"],
            target_node_id=record["target_node_id"],
            relation_type=record["relation_type"],
            properties=record["properties"] if record["properties"] else {},
            created_at=record["created_at"],
        )

    class Config:
        from_attributes = True


class EdgeCreate(BaseModel):
    """Data for creating a new edge."""

    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relation_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphTraversal(BaseModel):
    """Result of graph traversal query."""

    start_node: uuid.UUID
    direction: str  # "outbound" | "inbound"
    relationship: str
    max_depth: int
    nodes: list[NodeModel] = Field(default_factory=list)
    total_nodes: int = 0

    class Config:
        from_attributes = True


class GraphStats(BaseModel):
    """Statistics about graph construction."""

    repository: str
    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: Dict[str, int] = Field(default_factory=dict)
    edges_by_type: Dict[str, int] = Field(default_factory=dict)
    construction_time_seconds: float = 0.0
    resolution_accuracy: Optional[float] = None  # Percentage of calls resolved

    class Config:
        from_attributes = True
