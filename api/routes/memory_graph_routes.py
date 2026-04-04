"""
Memory Graph Routes — REST endpoints for memory graph visualization and consolidation.

These endpoints wrap the existing services for frontend consumption.
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memories", tags=["memory-graph"])


class ConsolidateRequest(BaseModel):
    """Request body for memory consolidation."""
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    source_ids: List[str] = Field(..., min_length=2)
    tags: Optional[List[str]] = None
    memory_type: Optional[str] = "note"
    author: Optional[str] = "consolidation"


@router.get("/graph")
async def get_memory_graph(
    min_score: float = Query(0.3, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """
    Get the memory relationship graph for visualization.

    Returns nodes (memories) and edges (relationships) for D3.js or G6 rendering.
    """
    try:
        from sqlalchemy.sql import text

        query = text("""
            SELECT
                mr.source_id::text,
                mr.target_id::text,
                mr.score,
                mr.relationship_types,
                mr.shared_entities,
                mr.shared_concepts,
                m1.title as source_title,
                m1.memory_type as source_type,
                m1.tags as source_tags,
                m2.title as target_title,
                m2.memory_type as target_type,
                m2.tags as target_tags
            FROM memory_relationships mr
            JOIN memories m1 ON m1.id = mr.source_id
            JOIN memories m2 ON m2.id = mr.target_id
            WHERE mr.score >= :min_score
              AND m1.deleted_at IS NULL
              AND m2.deleted_at IS NULL
            ORDER BY mr.score DESC
            LIMIT :limit
        """)

        async with engine.begin() as conn:
            result = await conn.execute(query, {"min_score": min_score, "limit": limit})
            rows = result.fetchall()

        nodes = {}
        edges = []

        for row in rows:
            source_id, target_id, score, rel_types, shared_e, shared_c = row[0], row[1], row[2], row[3], row[4], row[5]
            source_title, source_type, source_tags = row[6], row[7], row[8]
            target_title, target_type, target_tags = row[9], row[10], row[11]

            if source_id not in nodes:
                nodes[source_id] = {
                    "id": source_id,
                    "title": source_title,
                    "memory_type": source_type,
                    "size": 0,
                    "tags": source_tags or [],
                }
            if target_id not in nodes:
                nodes[target_id] = {
                    "id": target_id,
                    "title": target_title,
                    "memory_type": target_type,
                    "size": 0,
                    "tags": target_tags or [],
                }

            nodes[source_id]["size"] += 1
            nodes[target_id]["size"] += 1

            edges.append({
                "source": source_id,
                "target": target_id,
                "score": score,
                "types": rel_types or [],
                "shared_entities": list(shared_e) if shared_e else [],
                "shared_concepts": list(shared_c) if shared_c else [],
            })

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    except Exception as e:
        logger.error(f"Failed to get memory graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get memory graph: {e}")


@router.get("/consolidation/suggestions")
async def get_consolidation_suggestions(
    min_shared_entities: int = Query(2, ge=0),
    min_shared_concepts: int = Query(1, ge=0),
    memory_types: str = Query("note"),
    tags: str = Query("sys:history"),
    max_age_days: int = Query(30, ge=1),
    min_group_size: int = Query(3, ge=2),
    max_groups: int = Query(5, ge=1, le=20),
    similarity_threshold: float = Query(0.3, ge=0.0, le=1.0),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """
    Get consolidation suggestions based on entity/concept overlap.

    Returns groups of similar memories that could be consolidated.
    """
    try:
        from services.consolidation_suggestion_service import ConsolidationSuggestionService

        service = ConsolidationSuggestionService(engine=engine, redis_client=None)
        groups = await service.suggest_consolidation(
            min_shared_entities=min_shared_entities,
            min_shared_concepts=min_shared_concepts,
            memory_types=memory_types.split(",") if memory_types else ["note"],
            tags=tags.split(",") if tags else ["sys:history"],
            max_age_days=max_age_days,
            min_group_size=min_group_size,
            max_groups=max_groups,
            similarity_threshold=similarity_threshold,
        )

        result_groups = []
        for g in groups:
            result_groups.append({
                "source_ids": g.memory_ids,
                "titles": g.titles,
                "content_previews": g.content_previews,
                "shared_entities": list(g.shared_entities),
                "shared_concepts": list(g.shared_concepts),
                "avg_similarity": round(g.avg_similarity, 3),
                "suggested_title": service.suggest_title(g),
                "suggested_tags": ["sys:history"],
                "suggested_summary_hint": service.suggest_hint(g),
            })

        return {
            "groups": result_groups,
            "total_groups_found": len(result_groups),
        }

    except Exception as e:
        logger.error(f"Failed to get consolidation suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get consolidation suggestions: {e}")


@router.post("/consolidate")
async def consolidate_memories(
    request: ConsolidateRequest,
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """
    Consolidate a group of memories into one.

    Creates a new memory with the summary and soft-deletes the source memories.
    """
    try:
        from db.repositories.memory_repository import MemoryRepository
        from mnemo_mcp.models.memory_models import MemoryCreate, MemoryType

        repo = MemoryRepository(engine)

        embedding = None
        try:
            from services.dual_embedding_service import DualEmbeddingService
            from dependencies import DualEmbeddingServiceAdapter
            import os

            dual_service = DualEmbeddingService(
                text_model_name=os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
                code_model_name=os.getenv("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code"),
                dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
                device=os.getenv("EMBEDDING_DEVICE", "cpu"),
                cache_size=int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
            )
            embedding_service = DualEmbeddingServiceAdapter(dual_service)
            embedding_data = await embedding_service.generate_embedding(
                f"{request.title}\n\n{request.summary}",
                domain="text",
            )
            embedding = embedding_data.get("text", embedding_data) if isinstance(embedding_data, dict) else embedding_data
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")

        memory_create = MemoryCreate(
            title=request.title,
            content=request.summary,
            memory_type=MemoryType(request.memory_type) if request.memory_type else MemoryType.NOTE,
            tags=request.tags or ["sys:history:summary", "sys:consolidated"],
            author=request.author or "consolidation",
        )

        consolidated = await repo.create(memory_create, embedding=embedding)

        deleted_count = 0
        for source_id in request.source_ids:
            try:
                await repo.soft_delete(source_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to soft-delete {source_id}: {e}")

        return {
            "consolidated_memory": {
                "id": str(consolidated.id),
                "title": consolidated.title,
                "memory_type": consolidated.memory_type.value,
                "tags": consolidated.tags,
                "created_at": consolidated.created_at.isoformat(),
            },
            "deleted_count": deleted_count,
            "total_source_ids": len(request.source_ids),
            "source_ids": request.source_ids,
        }

    except Exception as e:
        logger.error(f"Consolidation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Consolidation failed: {e}")
