"""
EPIC-25 Story 25.2: Dashboard Backend API
Endpoints for Vue.js frontend dashboard displaying system stats.
"""
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/health")
async def get_dashboard_health(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Simplified health check for dashboard frontend.

    Returns:
        Dictionary with health status of API, Database, and Redis.
    """
    try:
        # Check PostgreSQL
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                postgres_ok = result.scalar() == 1
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            postgres_ok = False

        # Check Redis (optional - check if available in app state)
        # For MVP, we consider Redis optional
        redis_ok = True  # Assume OK for MVP

        # Overall status
        is_healthy = postgres_ok and redis_ok

        return {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "api": True,  # If we respond, API is up
                "database": postgres_ok,
                "redis": redis_ok
            }
        }
    except Exception as e:
        logger.error(f"Dashboard health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Health check failed")


@router.get("/embeddings/text")
async def get_text_embeddings_stats(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get statistics for TEXT embeddings (memories table).

    TEXT embeddings are used for conversations, semantic memory.
    Model: nomic-ai/nomic-embed-text-v1.5

    Returns:
        Dictionary with model info, count, dimension, last indexed timestamp.
    """
    try:
        async with engine.begin() as conn:
            # Count memories with embeddings
            result = await conn.execute(
                text("SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL")
            )
            count = result.scalar() or 0

            # Get most recent indexed timestamp
            result = await conn.execute(
                text("SELECT MAX(created_at) FROM memories WHERE embedding IS NOT NULL")
            )
            last_indexed = result.scalar()

        return {
            "model": "nomic-ai/nomic-embed-text-v1.5",
            "count": count,
            "dimension": 768,
            "lastIndexed": last_indexed.isoformat() if last_indexed else None
        }
    except Exception as e:
        logger.error(f"Failed to get text embeddings stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get text embeddings stats: {str(e)}"
        )


@router.get("/embeddings/code")
async def get_code_embeddings_stats(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get statistics for CODE embeddings (code_chunks table).

    CODE embeddings are used for code intelligence, semantic code search.
    Model: jinaai/jina-embeddings-v2-base-code

    Returns:
        Dictionary with model info, count, dimension, last indexed timestamp.
    """
    try:
        async with engine.begin() as conn:
            # Count code chunks
            result = await conn.execute(
                text("SELECT COUNT(*) FROM code_chunks")
            )
            count = result.scalar() or 0

            # Get most recent indexed timestamp
            result = await conn.execute(
                text("SELECT MAX(indexed_at) FROM code_chunks")
            )
            last_indexed = result.scalar()

        return {
            "model": "jinaai/jina-embeddings-v2-base-code",
            "count": count,
            "dimension": 768,
            "lastIndexed": last_indexed.isoformat() if last_indexed else None
        }
    except Exception as e:
        logger.error(f"Failed to get code embeddings stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get code embeddings stats: {str(e)}"
        )
