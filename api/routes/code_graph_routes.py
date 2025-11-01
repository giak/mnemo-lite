"""
Code Graph API routes for EPIC-06 Phase 2 Story 4.

Provides endpoints for code dependency graph construction and traversal.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine
from services.graph_construction_service import GraphConstructionService
from services.graph_traversal_service import GraphTraversalService
from models.graph_models import GraphStats, GraphTraversal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/code/graph", tags=["Code Graph"])


# Request/Response Models
class BuildGraphRequest(BaseModel):
    """Request to build graph for repository."""
    repository: str = Field(..., description="Repository name (e.g., 'MnemoLite')")
    language: str = Field(default="python", description="Programming language")


class TraverseGraphRequest(BaseModel):
    """Request to traverse graph from a node."""
    start_node_id: uuid.UUID = Field(..., description="Starting node ID")
    direction: str = Field(default="outbound", description="Direction: 'outbound' or 'inbound'")
    relationship: Optional[str] = Field(None, description="Filter by relationship type (e.g., 'calls')")
    max_depth: int = Field(default=3, ge=1, le=10, description="Maximum traversal depth")


class FindPathRequest(BaseModel):
    """Request to find shortest path between two nodes."""
    source_node_id: uuid.UUID = Field(..., description="Source node ID")
    target_node_id: uuid.UUID = Field(..., description="Target node ID")
    relationship: Optional[str] = Field(None, description="Filter by relationship type")
    max_depth: int = Field(default=10, ge=1, le=20, description="Maximum search depth")


class PathResponse(BaseModel):
    """Response containing path between nodes."""
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    path: Optional[List[uuid.UUID]] = None
    path_length: int = 0
    found: bool = False


# API Endpoints
@router.post("/build", response_model=GraphStats)
async def build_graph(
    request: BuildGraphRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> GraphStats:
    """
    Build code dependency graph for a repository.

    This endpoint:
    1. Gets all code chunks for the repository
    2. Creates nodes for functions/classes
    3. Resolves calls and imports
    4. Creates edges representing dependencies
    5. Returns statistics

    Example:
        POST /v1/code/graph/build
        {
            "repository": "MnemoLite",
            "language": "python"
        }

    Returns:
        GraphStats with construction metrics
    """
    try:
        logger.info(f"Building graph for repository: {request.repository}, language: {request.language}")
        service = GraphConstructionService(engine)
        stats = await service.build_graph_for_repository(
            repository=request.repository,
            languages=[request.language] if request.language else None
        )
        logger.info(f"Graph built successfully: {stats.total_nodes} nodes, {stats.total_edges} edges")
        return stats
    except Exception as e:
        logger.error(f"Failed to build graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to build graph: {str(e)}")


@router.post("/traverse", response_model=GraphTraversal)
async def traverse_graph(
    request: TraverseGraphRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> GraphTraversal:
    """
    Traverse graph from a starting node using recursive CTEs.

    Directions:
    - "outbound": Find dependencies (what this node calls/imports)
    - "inbound": Find dependents (what calls/imports this node)

    Example:
        POST /v1/code/graph/traverse
        {
            "start_node_id": "550e8400-e29b-41d4-a716-446655440000",
            "direction": "outbound",
            "relationship": "calls",
            "max_depth": 3
        }

    Returns:
        GraphTraversal with discovered nodes
    """
    try:
        logger.info(
            f"Traversing graph from node {request.start_node_id}, "
            f"direction={request.direction}, relationship={request.relationship}"
        )

        service = GraphTraversalService(engine)
        result = await service.traverse(
            start_node_id=request.start_node_id,
            direction=request.direction,
            relationship=request.relationship,
            max_depth=request.max_depth
        )

        logger.info(f"Traversal complete: found {result.total_nodes} nodes")
        return result

    except ValueError as e:
        logger.error(f"Invalid traversal request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to traverse graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to traverse graph: {str(e)}")


@router.post("/path", response_model=PathResponse)
async def find_path(
    request: FindPathRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> PathResponse:
    """
    Find shortest path between two nodes.

    Uses recursive CTE with path tracking to find the shortest path.

    Example:
        POST /v1/code/graph/path
        {
            "source_node_id": "550e8400-e29b-41d4-a716-446655440000",
            "target_node_id": "650e8400-e29b-41d4-a716-446655440001",
            "relationship": "calls",
            "max_depth": 10
        }

    Returns:
        PathResponse with path if found
    """
    try:
        logger.info(
            f"Finding path from {request.source_node_id} to {request.target_node_id}, "
            f"relationship={request.relationship}"
        )

        service = GraphTraversalService(engine)
        path = await service.find_path(
            source_node_id=request.source_node_id,
            target_node_id=request.target_node_id,
            relationship=request.relationship,
            max_depth=request.max_depth
        )

        if path:
            logger.info(f"Path found with {len(path)} hops")
            return PathResponse(
                source_node_id=request.source_node_id,
                target_node_id=request.target_node_id,
                path=path,
                path_length=len(path),
                found=True
            )
        else:
            logger.info("No path found")
            return PathResponse(
                source_node_id=request.source_node_id,
                target_node_id=request.target_node_id,
                path=None,
                path_length=0,
                found=False
            )

    except Exception as e:
        logger.error(f"Failed to find path: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find path: {str(e)}")


@router.get("/stats/{repository}", response_model=Dict[str, Any])
async def get_graph_stats(
    repository: str = Path(..., description="Repository name"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get statistics for a repository's graph.

    Returns counts of nodes and edges by type.

    Example:
        GET /v1/code/graph/stats/MnemoLite

    Returns:
        {
            "repository": "MnemoLite",
            "total_nodes": 150,
            "total_edges": 320,
            "nodes_by_type": {"function": 120, "class": 30},
            "edges_by_type": {"calls": 280, "imports": 40}
        }
    """
    try:
        from sqlalchemy.sql import text

        async with engine.connect() as conn:
            # Count nodes by type
            nodes_query = text("""
                SELECT
                    node_type,
                    COUNT(*) as count
                FROM nodes
                WHERE properties->>'file_path' LIKE :repository_pattern
                GROUP BY node_type
            """)

            nodes_result = await conn.execute(
                nodes_query,
                {"repository_pattern": f"%{repository}%"}
            )
            nodes_rows = nodes_result.fetchall()
            nodes_by_type = {row[0]: row[1] for row in nodes_rows}
            total_nodes = sum(nodes_by_type.values())

            # Count edges by type
            edges_query = text("""
                SELECT
                    e.relation_type,
                    COUNT(*) as count
                FROM edges e
                JOIN nodes n ON e.source_node_id = n.node_id
                WHERE n.properties->>'file_path' LIKE :repository_pattern
                GROUP BY e.relation_type
            """)

            edges_result = await conn.execute(
                edges_query,
                {"repository_pattern": f"%{repository}%"}
            )
            edges_rows = edges_result.fetchall()
            edges_by_type = {row[0]: row[1] for row in edges_rows}
            total_edges = sum(edges_by_type.values())

        return {
            "repository": repository,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type
        }

    except Exception as e:
        logger.error(f"Failed to get graph stats for {repository}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
