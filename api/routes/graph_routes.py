"""
Graph API routes for MnemoLite.

Provides endpoints for graph visualization and exploration.
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["Graph"])


@router.get("/nodes")
async def get_graph_nodes(
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    limit: int = Query(100, ge=1, le=1000, description="Max nodes to return"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get nodes and edges for graph visualization.

    Returns a structure compatible with Cytoscape.js:
    {
        "nodes": [{"data": {"id": "...", "label": "...", "type": "..."}}],
        "edges": [{"data": {"id": "...", "source": "...", "target": "...", "label": "..."}}]
    }
    """
    try:
        async with engine.connect() as conn:
            # Build nodes query
            nodes_query = """
                SELECT
                    node_id::text as id,
                    node_type,
                    label,
                    properties,
                    created_at
                FROM nodes
            """
            params = {"limit": limit}

            if node_type:
                nodes_query += " WHERE node_type = :node_type"
                params["node_type"] = node_type

            nodes_query += " ORDER BY created_at DESC LIMIT :limit"

            # Execute nodes query
            nodes_result = await conn.execute(text(nodes_query), params)
            nodes_rows = nodes_result.mappings().all()

            # Get node IDs for edge filtering
            node_ids = [row["id"] for row in nodes_rows]

            # Get edges for these nodes
            edges_data = []
            if node_ids:
                edges_query = """
                    SELECT
                        edge_id::text as id,
                        source_node_id::text as source,
                        target_node_id::text as target,
                        relation_type as label,
                        properties,
                        created_at
                    FROM edges
                    WHERE source_node_id::text = ANY(:node_ids)
                      AND target_node_id::text = ANY(:node_ids)
                    LIMIT :limit
                """
                edges_result = await conn.execute(
                    text(edges_query),
                    {"node_ids": node_ids, "limit": limit}
                )
                edges_rows = edges_result.mappings().all()

                edges_data = [
                    {
                        "data": {
                            "id": row["id"],
                            "source": row["source"],
                            "target": row["target"],
                            "label": row["label"] or "related_to",
                            "created_at": row["created_at"].isoformat() if row["created_at"] else None
                        }
                    }
                    for row in edges_rows
                ]

            # Format nodes for Cytoscape
            nodes_data = [
                {
                    "data": {
                        "id": row["id"],
                        "label": row["label"] or row["id"][:8],
                        "type": row["node_type"] or "unknown",
                        "props": row["properties"] or {},
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None
                    }
                }
                for row in nodes_rows
            ]

            return {
                "nodes": nodes_data,
                "edges": edges_data,
                "stats": {
                    "total_nodes": len(nodes_data),
                    "total_edges": len(edges_data)
                }
            }

    except Exception as e:
        logger.error(f"Failed to get graph nodes: {e}", exc_info=True)
        return {
            "nodes": [],
            "edges": [],
            "stats": {"total_nodes": 0, "total_edges": 0},
            "error": str(e)
        }


@router.get("/expand/{node_id}")
async def expand_node(
    node_id: str,
    depth: int = Query(1, ge=1, le=3, description="Depth of expansion (1-3 hops)"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Expand a node to show its connected neighbors up to N hops.

    Uses recursive CTE to traverse the graph.
    """
    try:
        async with engine.connect() as conn:
            # Recursive CTE to find connected nodes
            query = """
                WITH RECURSIVE node_expansion AS (
                    -- Base case: the node itself
                    SELECT
                        node_id::text as id,
                        node_type,
                        label,
                        properties,
                        created_at,
                        0 as depth
                    FROM nodes
                    WHERE node_id::text = :node_id

                    UNION ALL

                    -- Recursive case: connected nodes
                    SELECT DISTINCT
                        n.node_id::text as id,
                        n.node_type,
                        n.label,
                        n.properties,
                        n.created_at,
                        ne.depth + 1 as depth
                    FROM node_expansion ne
                    JOIN edges e ON (e.source_node_id::text = ne.id OR e.target_node_id::text = ne.id)
                    JOIN nodes n ON (
                        (e.source_node_id::text = ne.id AND n.node_id::text = e.target_node_id::text)
                        OR
                        (e.target_node_id::text = ne.id AND n.node_id::text = e.source_node_id::text)
                    )
                    WHERE ne.depth < :depth
                )
                SELECT * FROM node_expansion
            """

            nodes_result = await conn.execute(
                text(query),
                {"node_id": node_id, "depth": depth}
            )
            nodes_rows = nodes_result.mappings().all()

            # Get edges between these nodes
            node_ids = [row["id"] for row in nodes_rows]
            edges_data = []

            if len(node_ids) > 1:
                edges_query = """
                    SELECT
                        edge_id::text as id,
                        source_node_id::text as source,
                        target_node_id::text as target,
                        relation_type as label,
                        properties,
                        created_at
                    FROM edges
                    WHERE source_node_id::text = ANY(:node_ids)
                      AND target_node_id::text = ANY(:node_ids)
                """
                edges_result = await conn.execute(
                    text(edges_query),
                    {"node_ids": node_ids}
                )
                edges_rows = edges_result.mappings().all()

                edges_data = [
                    {
                        "data": {
                            "id": row["id"],
                            "source": row["source"],
                            "target": row["target"],
                            "label": row["label"] or "related_to",
                            "created_at": row["created_at"].isoformat() if row["created_at"] else None
                        }
                    }
                    for row in edges_rows
                ]

            nodes_data = [
                {
                    "data": {
                        "id": row["id"],
                        "label": row["label"] or row["id"][:8],
                        "type": row["node_type"] or "unknown",
                        "depth": row["depth"],
                        "props": row["properties"] or {},
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None
                    }
                }
                for row in nodes_rows
            ]

            return {
                "nodes": nodes_data,
                "edges": edges_data,
                "stats": {
                    "total_nodes": len(nodes_data),
                    "total_edges": len(edges_data),
                    "max_depth": depth
                }
            }

    except Exception as e:
        logger.error(f"Failed to expand node {node_id}: {e}", exc_info=True)
        return {
            "nodes": [],
            "edges": [],
            "stats": {"total_nodes": 0, "total_edges": 0},
            "error": str(e)
        }
