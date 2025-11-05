"""
EPIC-27: Projects Management API
Endpoints for managing indexed code repositories.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class SetActiveProjectRequest(BaseModel):
    repository: str


# Simple in-memory store for active project (will be enhanced with Redis later)
_active_project = {"repository": "default"}


@router.get("")
async def list_projects(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    List all indexed projects with statistics.

    Returns:
        {
            "projects": [
                {
                    "repository": "code_test",
                    "files_count": 123,
                    "chunks_count": 456,
                    "languages": ["python", "typescript"],
                    "last_indexed": "2025-11-05T10:30:00",
                    "status": "healthy",
                    "total_loc": 12345,
                    "graph_coverage": 0.92
                },
                ...
            ]
        }
    """
    try:
        async with engine.begin() as conn:
            # Get repository statistics
            result = await conn.execute(
                text("""
                    SELECT
                        repository,
                        COUNT(DISTINCT file_path) as files_count,
                        COUNT(*) as chunks_count,
                        MAX(indexed_at) as last_indexed,
                        array_agg(DISTINCT language) FILTER (WHERE language IS NOT NULL) as languages,
                        SUM(CAST(metadata->>'loc' AS INTEGER)) FILTER (WHERE metadata->>'loc' IS NOT NULL) as total_loc
                    FROM code_chunks
                    WHERE repository IS NOT NULL
                    GROUP BY repository
                    ORDER BY last_indexed DESC
                """)
            )

            projects = []
            for row in result.fetchall():
                # Calculate graph coverage for this repository
                # Count nodes that have incoming or outgoing edges
                coverage_result = await conn.execute(
                    text("""
                        SELECT
                            COUNT(DISTINCT n.node_id) FILTER (
                                WHERE EXISTS (
                                    SELECT 1 FROM edges WHERE source_node_id = n.node_id OR target_node_id = n.node_id
                                )
                            ) as connected,
                            COUNT(DISTINCT n.node_id) as total
                        FROM nodes n
                        WHERE n.node_type = 'Module'
                          AND n.properties->>'file_path' LIKE :repository_pattern
                    """),
                    {"repository_pattern": f"{row.repository}/%"}
                )
                coverage_row = coverage_result.fetchone()
                graph_coverage = (coverage_row.connected / coverage_row.total) if coverage_row.total > 0 else 0

                # Determine status
                last_indexed = row.last_indexed
                if last_indexed:
                    days_since_index = (datetime.now(last_indexed.tzinfo) - last_indexed).days
                    if days_since_index > 7:
                        status = "needs_reindex"
                    elif graph_coverage < 0.5:
                        status = "poor_coverage"
                    else:
                        status = "healthy"
                else:
                    status = "error"

                projects.append({
                    "repository": row.repository,
                    "files_count": row.files_count,
                    "chunks_count": row.chunks_count,
                    "languages": row.languages or [],
                    "last_indexed": last_indexed.isoformat() if last_indexed else None,
                    "status": status,
                    "total_loc": row.total_loc or 0,
                    "graph_coverage": round(graph_coverage, 2)
                })

            return {"projects": projects}

    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve projects list. Please try again later."
        )


@router.get("/active")
async def get_active_project() -> Dict[str, str]:
    """
    Get the currently active project.

    Returns:
        {
            "repository": "code_test"
        }
    """
    return _active_project


@router.post("/active")
async def set_active_project(
    request: SetActiveProjectRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Set the active project for search and navigation.

    Args:
        request: {"repository": "project_name"}

    Returns:
        {
            "repository": "project_name",
            "message": "Active project switched to project_name"
        }
    """
    try:
        # Verify project exists
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT COUNT(*) as count
                    FROM code_chunks
                    WHERE repository = :repository
                """),
                {"repository": request.repository}
            )
            count = result.scalar()

            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{request.repository}' not found or has no indexed files."
                )

        # Update active project
        _active_project["repository"] = request.repository

        return {
            "repository": request.repository,
            "message": f"Active project switched to {request.repository}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set active project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to set active project. Please try again later."
        )
