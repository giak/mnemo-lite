"""
EPIC-26: Memories Monitor Backend API
Endpoints for Memories Monitor page displaying conversations, code, embeddings.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])

# Read embedding model names from environment variables
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
CODE_EMBEDDING_MODEL = os.getenv("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code")


@router.get("/stats")
async def get_memories_stats(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get overall memories statistics for dashboard.

    Returns:
        - total: Total memories count
        - today: Memories added today
        - embedding_rate: Percentage with embeddings
        - last_activity: Most recent memory timestamp
    """
    try:
        async with engine.begin() as conn:
            # Total memories
            result = await conn.execute(
                text("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL")
            )
            total = result.scalar() or 0

            # Today's count (last 24 hours)
            result = await conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM memories
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    AND deleted_at IS NULL
                """)
            )
            today = result.scalar() or 0

            # Embedding success rate
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_emb,
                        COUNT(*) as total
                    FROM memories
                    WHERE deleted_at IS NULL
                """)
            )
            row = result.fetchone()
            embedding_rate = (row.with_emb / row.total * 100) if row.total > 0 else 0

            # Last activity
            result = await conn.execute(
                text("SELECT MAX(created_at) FROM memories WHERE deleted_at IS NULL")
            )
            last_activity = result.scalar()

        return {
            "total": total,
            "today": today,
            "embedding_rate": round(embedding_rate, 1),
            "last_activity": last_activity.isoformat() if last_activity else None
        }
    except Exception as e:
        logger.error(f"Failed to get memories stats: {e}", exc_info=True)
        # Don't expose internal errors to clients
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve memories statistics. Please try again later."
        )


@router.get("/recent")
async def get_recent_memories(
    limit: int = Query(default=10, ge=1, le=100),
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """
    Get recent memories (conversations) for timeline display.

    Args:
        limit: Number of recent items to return (1-100, default 10)

    Returns:
        List of memory objects with: id, title, created_at, memory_type, tags, has_embedding
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        id,
                        title,
                        created_at,
                        memory_type,
                        tags,
                        (embedding IS NOT NULL) as has_embedding,
                        author
                    FROM memories
                    WHERE deleted_at IS NULL
                    AND memory_type = 'conversation'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.fetchall()

            memories = []
            for row in rows:
                memories.append({
                    "id": str(row.id),
                    "title": row.title,
                    "created_at": row.created_at.isoformat(),
                    "memory_type": row.memory_type,
                    "tags": row.tags or [],
                    "has_embedding": row.has_embedding,
                    "author": row.author
                })

            return memories
    except Exception as e:
        logger.error(f"Failed to get recent memories: {e}", exc_info=True)
        # Don't expose internal errors to clients
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve recent memories. Please try again later."
        )


@router.get("/code-chunks/recent")
async def get_recent_code_chunks(
    limit: int = Query(default=10, ge=1, le=100),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get recent code chunk indexing activity.

    Args:
        limit: Number of recent items to return (1-100, default 10)

    Returns:
        Dictionary with indexing_stats (today's activity) and recent_chunks list
    """
    try:
        async with engine.begin() as conn:
            # Today's indexing stats
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) as chunks_today,
                        COUNT(DISTINCT file_path) as files_today
                    FROM code_chunks
                    WHERE indexed_at >= NOW() - INTERVAL '24 hours'
                """)
            )
            stats = result.fetchone()

            # Recent chunks
            result = await conn.execute(
                text("""
                    SELECT
                        id,
                        file_path,
                        chunk_type,
                        repository,
                        language,
                        indexed_at,
                        source_code
                    FROM code_chunks
                    ORDER BY indexed_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.fetchall()

            recent_chunks = []
            for row in rows:
                # Extract chunk name from content (first line, max 50 chars)
                content_preview = row.source_code[:50].split('\n')[0] if row.source_code else ""

                recent_chunks.append({
                    "id": str(row.id),
                    "file_path": row.file_path,
                    "chunk_type": row.chunk_type,
                    "repository": row.repository,
                    "language": row.language,
                    "indexed_at": row.indexed_at.isoformat(),
                    "content_preview": content_preview
                })

            return {
                "indexing_stats": {
                    "chunks_today": stats.chunks_today or 0,
                    "files_today": stats.files_today or 0
                },
                "recent_chunks": recent_chunks
            }
    except Exception as e:
        logger.error(f"Failed to get recent code chunks: {e}", exc_info=True)
        # Don't expose internal errors to clients
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve recent code chunks. Please try again later."
        )


@router.get("/embeddings/health")
async def get_embeddings_health(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get embedding health alerts and status.

    Returns:
        - text_embeddings: count, success_rate, model
        - code_embeddings: count, model
        - alerts: list of issues (e.g., memories without embeddings)
    """
    try:
        async with engine.begin() as conn:
            # Text embeddings health
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_emb
                    FROM memories
                    WHERE deleted_at IS NULL
                """)
            )
            text_stats = result.fetchone()
            text_success_rate = (text_stats.with_emb / text_stats.total * 100) if text_stats.total > 0 else 0

            # Code embeddings (all code_chunks have embeddings by design)
            result = await conn.execute(
                text("SELECT COUNT(*) FROM code_chunks")
            )
            code_count = result.scalar() or 0

            # Alerts
            alerts = []
            memories_without_embeddings = text_stats.total - text_stats.with_emb
            if memories_without_embeddings > 0:
                alerts.append({
                    "type": "warning",
                    "message": f"{memories_without_embeddings} memories without embeddings"
                })

        return {
            "text_embeddings": {
                "total": text_stats.total,
                "with_embeddings": text_stats.with_emb,
                "success_rate": round(text_success_rate, 1),
                "model": EMBEDDING_MODEL
            },
            "code_embeddings": {
                "total": code_count,
                "model": CODE_EMBEDDING_MODEL
            },
            "alerts": alerts,
            "status": "healthy" if text_success_rate > 90 else "degraded"
        }
    except Exception as e:
        logger.error(f"Failed to get embeddings health: {e}", exc_info=True)
        # Don't expose internal errors to clients
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve embeddings health. Please try again later."
        )
