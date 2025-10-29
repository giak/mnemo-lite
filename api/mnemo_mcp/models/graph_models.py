"""
Pydantic models for MCP Graph Resources (EPIC-23 Story 23.4).

Models for exposing code dependency graphs via MCP protocol.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from mnemo_mcp.base import MCPBaseResponse


# ============================================================================
# Graph Node Models
# ============================================================================


class MCPNode(BaseModel):
    """
    A node in the code dependency graph.

    Represents a function, class, method, or module in the codebase.
    """
    node_id: UUID
    node_type: str = Field(
        description="Type of node: function, class, method, module"
    )
    label: str = Field(
        description="Display name (function/class name, fully qualified)"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (file_path, line_number, complexity, etc.)"
    )
    created_at: datetime

    # MCP 2025-06-18: Resource links to related resources
    resource_links: List[str] = Field(
        default_factory=list,
        description="URIs to related resources (code chunks, graph neighbors)"
    )

    model_config = {"from_attributes": True}


class MCPEdge(BaseModel):
    """
    An edge in the code dependency graph.

    Represents a relationship between two nodes (calls, imports, extends, uses).
    """
    edge_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    relation_type: str = Field(
        description="Type of relationship: calls, imports, extends, uses"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (call_count, line_number, etc.)"
    )
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Graph Traversal Models
# ============================================================================


class GraphTraversalQuery(BaseModel):
    """
    Query parameters for graph traversal.

    Used for filtering and pagination in graph traversal operations.
    """
    start_node_id: UUID = Field(
        description="Node to start traversal from"
    )
    direction: str = Field(
        default="outbound",
        description="Direction of traversal: outbound (dependencies) or inbound (dependents)"
    )
    relationship: Optional[str] = Field(
        default=None,
        description="Filter by edge type (calls, imports, extends, uses). None = all types."
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum depth to traverse (1-10, default: 3)"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of nodes to return (1-500, default: 50)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        le=10000,
        description="Pagination offset (0-10000, default: 0)"
    )


class GraphTraversalMetadata(BaseModel):
    """
    Metadata about graph traversal results.

    Includes pagination info and traversal statistics.
    """
    start_node: UUID
    direction: str
    relationship: str
    max_depth: int
    total_nodes: int
    returned_nodes: int
    limit: int
    offset: int
    has_more: bool
    cache_hit: bool = False
    execution_time_ms: float = 0.0


class GraphTraversalResponse(MCPBaseResponse):
    """
    Response for graph traversal operations.

    Returns discovered nodes with metadata and resource links.
    MCP 2025-06-18 compliant with resource links.
    """
    nodes: List[MCPNode] = Field(
        default_factory=list,
        description="Nodes discovered during traversal"
    )
    metadata: GraphTraversalMetadata

    # MCP 2025-06-18: Resource links for next/prev pages
    resource_links: List[str] = Field(
        default_factory=list,
        description="URIs for pagination (next_page, prev_page)"
    )


# ============================================================================
# Caller/Callee Models
# ============================================================================


class CallerCalleeQuery(BaseModel):
    """
    Query parameters for finding callers or callees.

    Used for graph://callers and graph://callees resources.
    """
    qualified_name: str = Field(
        description="Fully qualified name (e.g., 'module.ClassName.method_name')"
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum depth to traverse (1-10, default: 3)"
    )
    relationship_type: Optional[str] = Field(
        default="calls",
        description="Edge type to follow (calls, imports, etc.)"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of results (1-500, default: 50)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        le=10000,
        description="Pagination offset (0-10000, default: 0)"
    )


class CallerCalleeMetadata(BaseModel):
    """
    Metadata for caller/callee results.
    """
    qualified_name: str
    direction: str  # "inbound" (callers) or "outbound" (callees)
    max_depth: int
    total_found: int
    returned_count: int
    limit: int
    offset: int
    has_more: bool
    cache_hit: bool = False
    execution_time_ms: float = 0.0


class CallerCalleeResponse(MCPBaseResponse):
    """
    Response for caller/callee operations.

    Returns functions/methods that call or are called by the target.
    MCP 2025-06-18 compliant with resource links.
    """
    nodes: List[MCPNode] = Field(
        default_factory=list,
        description="Caller or callee nodes discovered"
    )
    metadata: CallerCalleeMetadata

    # MCP 2025-06-18: Resource links
    resource_links: List[str] = Field(
        default_factory=list,
        description="URIs for pagination and related resources"
    )


# ============================================================================
# Graph Node Details Models
# ============================================================================


class GraphNodeDetailsQuery(BaseModel):
    """
    Query parameters for getting node details with neighbors.
    """
    chunk_id: UUID = Field(
        description="UUID of code chunk (maps to node_id)"
    )
    include_callers: bool = Field(
        default=True,
        description="Include inbound edges (who calls this)"
    )
    include_callees: bool = Field(
        default=True,
        description="Include outbound edges (what this calls)"
    )
    max_neighbors: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum neighbors to return (1-100, default: 20)"
    )


class GraphNodeNeighbors(BaseModel):
    """
    Neighbors of a graph node (callers and callees).
    """
    callers: List[MCPNode] = Field(
        default_factory=list,
        description="Nodes that call/use this node"
    )
    callees: List[MCPNode] = Field(
        default_factory=list,
        description="Nodes called/used by this node"
    )
    edges: List[MCPEdge] = Field(
        default_factory=list,
        description="Edges connecting node to neighbors"
    )


class GraphNodeDetailsResponse(MCPBaseResponse):
    """
    Response for graph://nodes/{chunk_id} resource.

    Returns a node with its immediate neighbors (1-hop connections).
    MCP 2025-06-18 compliant with resource links.
    """
    node: Optional[MCPNode] = None
    neighbors: GraphNodeNeighbors = Field(default_factory=GraphNodeNeighbors)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (total_callers, total_callees, etc.)"
    )

    # MCP 2025-06-18: Resource links
    resource_links: List[str] = Field(
        default_factory=list,
        description="URIs to related resources (code chunk, full graph, etc.)"
    )


# ============================================================================
# Helper Functions
# ============================================================================


def build_node_resource_links(node_id: UUID, node_type: str, label: str) -> List[str]:
    """
    Build resource links for a graph node.

    MCP 2025-06-18: Resource links help navigation between related resources.

    Args:
        node_id: Node UUID
        node_type: Type of node (function, class, method, module)
        label: Node label (qualified name)

    Returns:
        List of resource URIs
    """
    links = []

    # Link to node details
    links.append(f"graph://nodes/{node_id}")

    # Link to callers/callees if applicable
    if node_type in ["function", "method", "class"]:
        links.append(f"graph://callers/{label}")
        links.append(f"graph://callees/{label}")

    # Note: Link to code://chunk/{node_id} would require mapping node_id to chunk_id
    # This is left for future implementation if nodes are linked to chunks

    return links


def build_pagination_links(
    base_uri: str,
    limit: int,
    offset: int,
    total_count: int
) -> List[str]:
    """
    Build pagination resource links.

    MCP 2025-06-18: Resource links for next/prev pages.

    Args:
        base_uri: Base URI template (e.g., "graph://traverse?start={id}")
        limit: Page size
        offset: Current offset
        total_count: Total number of results

    Returns:
        List of pagination URIs (next_page, prev_page, first_page, last_page)
    """
    links = []

    # Next page
    if offset + limit < total_count:
        next_offset = offset + limit
        links.append(f"{base_uri}&limit={limit}&offset={next_offset}  # next_page")

    # Previous page
    if offset > 0:
        prev_offset = max(0, offset - limit)
        links.append(f"{base_uri}&limit={limit}&offset={prev_offset}  # prev_page")

    # First page
    if offset > 0:
        links.append(f"{base_uri}&limit={limit}&offset=0  # first_page")

    # Last page
    if total_count > limit:
        last_offset = (total_count // limit) * limit
        links.append(f"{base_uri}&limit={limit}&offset={last_offset}  # last_page")

    return links
