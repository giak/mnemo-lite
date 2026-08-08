"""
Memory Relationship Routes — API endpoints for relationship graph.
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memories", tags=["memory-relationships"])


class ComputeRelationshipsRequest(BaseModel):
    entities: List[str] = Field(default_factory=list)
    concepts: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    auto_tags: List[str] = Field(default_factory=list)


@router.post("/{memory_id}/compute-relationships")
async def compute_relationships(
    memory_id: str,
    request: ComputeRelationshipsRequest,
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """
    EPIC-29: Compute and store relationships for a memory.
    Called by the worker after entity extraction completes.
    """
    try:
        from services.memory_relationship_service import MemoryRelationshipService

        service = MemoryRelationshipService(engine=engine)
        relationships = await service.compute_relationships(
            memory_id=memory_id,
            entities=[e.lower() for e in request.entities],
            concepts=[c.lower() for c in request.concepts],
            tags=[t.lower() for t in request.tags],
            auto_tags=[t.lower() for t in request.auto_tags],
        )

        return {
            "success": True,
            "memory_id": memory_id,
            "relationships_found": len(relationships),
        }

    except Exception as e:
        logger.error(f"Relationship computation failed for {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Relationship computation failed: {e}")


@router.get("/{memory_id}/related")
async def get_related_memories(
    memory_id: str,
    max_depth: int = Query(default=1, ge=1, le=3),
    min_score: float = Query(default=0.1, ge=0.0, le=1.0),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """
    EPIC-29: Get related memories via BFS traversal.
    """
    try:
        from services.memory_relationship_service import MemoryRelationshipService

        service = MemoryRelationshipService(engine=engine)
        related = await service.get_related_memories(
            memory_id=memory_id,
            max_depth=max_depth,
            min_score=min_score,
        )

        # Enrich with memory details
        if related:
            memory_ids = [r["memory_id"] for r in related]
            query = text("""
                SELECT id::text, title, memory_type, tags
                FROM memories
                WHERE id = ANY(:ids) AND deleted_at IS NULL
            """)
            async with engine.begin() as conn:
                result = await conn.execute(query, {"ids": memory_ids})
                memories = {str(row[0]): {"title": row[1], "memory_type": row[2], "tags": row[3]} for row in result}

            for r in related:
                mem_info = memories.get(r["memory_id"], {})
                r.update(mem_info)

        return {
            "memory_id": memory_id,
            "related": related,
            "total": len(related),
        }

    except Exception as e:
        logger.error(f"Failed to get related memories for {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get related memories: {e}")
