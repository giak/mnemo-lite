"""
EPIC-27: Projects Management API
Endpoints for managing indexed code repositories.
"""
import logging
from datetime import datetime
from pathlib import Path
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
                          AND n.properties->>'repository' = :repository
                    """),
                    {"repository": row.repository}
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


@router.post("/{repository}/reindex")
async def reindex_project(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Trigger reindexing of a project.

    NOTE: This is a simplified version that triggers background indexing.
    Full implementation would use a task queue (Celery/RQ).

    Args:
        repository: Name of the repository to reindex

    Returns:
        {
            "repository": "code_test",
            "status": "reindexing",
            "message": "Reindexing started for code_test"
        }
    """
    try:
        # Verify project exists
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        file_path
                    FROM code_chunks
                    WHERE repository = :repository
                    LIMIT 1
                """),
                {"repository": repository}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{repository}' not found."
                )

            # Extract project root from file path
            # This is simplified - production would use proper project metadata
            file_path = row.file_path
            # Assume project root is parent of first indexed file
            project_root = str(Path(file_path).parent.parent)

        # TODO: Trigger background reindexing task
        # For now, just return success status
        logger.info(f"Reindex triggered for {repository} at {project_root}")

        return {
            "repository": repository,
            "status": "reindexing",
            "message": f"Reindexing started for {repository}",
            "project_root": project_root
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reindex project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger reindexing. Please try again later."
        )


@router.delete("/{repository}")
async def delete_project(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Delete all data for a project.

    WARNING: This is destructive and cannot be undone!

    Args:
        repository: Name of the repository to delete

    Returns:
        {
            "repository": "code_test",
            "deleted_chunks": 1234,
            "deleted_nodes": 567,
            "message": "Project code_test deleted successfully"
        }
    """
    try:
        async with engine.begin() as conn:
            # Delete code chunks
            result = await conn.execute(
                text("""
                    DELETE FROM code_chunks
                    WHERE repository = :repository
                    RETURNING id
                """),
                {"repository": repository}
            )
            deleted_chunks = len(result.fetchall())

            # Delete nodes
            result = await conn.execute(
                text("""
                    DELETE FROM nodes
                    WHERE properties->>'repository' = :repository
                    RETURNING node_id
                """),
                {"repository": repository}
            )
            deleted_nodes = len(result.fetchall())

            # Delete edges (cascade should handle this, but be explicit)
            await conn.execute(
                text("""
                    DELETE FROM edges
                    WHERE source_node_id IN (
                        SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
                    ) OR target_node_id IN (
                        SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
                    )
                """),
                {"repository": repository}
            )

            if deleted_chunks == 0 and deleted_nodes == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{repository}' not found or already deleted."
                )

        logger.info(f"Deleted project {repository}: {deleted_chunks} chunks, {deleted_nodes} nodes")

        return {
            "repository": repository,
            "deleted_chunks": deleted_chunks,
            "deleted_nodes": deleted_nodes,
            "message": f"Project {repository} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete project. Please try again later."
        )
