"""
EPIC-26: Memories Monitor Backend API
Endpoints for Memories Monitor page displaying conversations, code, embeddings.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine, get_embedding_service
from interfaces.services import EmbeddingServiceProtocol

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
    offset: int = Query(default=0, ge=0),
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """
    Get recent memories (conversations) for timeline display.

    Args:
        limit: Number of recent items to return (1-100, default 10)
        offset: Number of memories to skip (for infinite scroll pagination)

    Returns:
        List of memory objects with: id, title, created_at, memory_type, tags, has_embedding
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        m.id,
                        m.title,
                        m.created_at,
                        m.memory_type,
                        m.tags,
                        (m.embedding IS NOT NULL) as has_embedding,
                        m.author,
                        m.project_id,
                        p.display_name as project_name
                    FROM memories m
                    LEFT JOIN projects p ON m.project_id = p.id
                    WHERE m.deleted_at IS NULL
                    AND m.memory_type = 'conversation'
                    ORDER BY m.created_at DESC
                    LIMIT :limit
                    OFFSET :offset
                """),
                {"limit": limit, "offset": offset}
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
                    "author": row.author,
                    "project_id": row.project_id,
                    "project_name": row.project_name
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


# Write endpoint

class MemoryCreateRequest(BaseModel):
    """Request body for creating a memory."""
    title: str = Field(..., min_length=1, max_length=200, description="Short memory title")
    content: str = Field(..., min_length=1, description="Full memory content")
    memory_type: str = Field("note", description="Type: note, decision, task, reference, conversation, investigation")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    author: Optional[str] = Field(None, max_length=100, description="Author attribution")
    embedding_source: Optional[str] = Field(None, description="Focused text for embedding (optional)")


class MemoryCreateResponse(BaseModel):
    """Response for memory creation."""
    id: str
    title: str
    memory_type: str
    created_at: str


@router.post("", response_model=MemoryCreateResponse, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> MemoryCreateResponse:
    """
    Create a new memory with semantic embedding.

    Generates an embedding from title+content (or embedding_source if provided)
    and stores the memory in PostgreSQL with pgvector.
    """
    import uuid
    from datetime import datetime, timezone
    from mnemo_mcp.models.memory_models import MemoryCreate, MemoryType
    from db.repositories.memory_repository import MemoryRepository
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

    try:
        # Validate memory_type
        try:
            memory_type_enum = MemoryType(request.memory_type)
        except ValueError:
            valid_types = [t.value for t in MemoryType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memory_type. Valid types: {', '.join(valid_types)}"
            )

        # Generate embedding
        embedding = None
        try:
            embedding_service = SentenceTransformerEmbeddingService()
            text_for_embedding = request.embedding_source or f"{request.title} {request.content}"
            embedding = await embedding_service.generate_embedding(text_for_embedding)
        except Exception as e:
            logger.warning(f"Embedding generation failed, storing without embedding: {e}")

        # Create memory
        memory_repo = MemoryRepository(engine)
        memory_create = MemoryCreate(
            title=request.title,
            content=request.content,
            memory_type=memory_type_enum,
            tags=request.tags,
            author=request.author,
            embedding_source=request.embedding_source,
        )

        memory = await memory_repo.create(memory_create, embedding=embedding)

        return MemoryCreateResponse(
            id=str(memory.id),
            title=memory.title,
            memory_type=memory.memory_type,
            created_at=memory.timestamp.isoformat() if hasattr(memory, 'timestamp') and memory.timestamp else datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create memory. Please try again later."
        )


# Update endpoint

class MemoryUpdateRequest(BaseModel):
    """Request body for updating a memory (all fields optional)."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    memory_type: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    embedding_source: Optional[str] = None


@router.put("/{memory_id}")
async def update_memory_endpoint(
    memory_id: str,
    request: MemoryUpdateRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """Update an existing memory (partial update). Regenerates embedding if content changes."""
    from datetime import timezone
    from mnemo_mcp.models.memory_models import MemoryUpdate, MemoryType
    from db.repositories.memory_repository import MemoryRepository
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

    try:
        # Validate memory_type if provided
        if request.memory_type:
            try:
                MemoryType(request.memory_type)
            except ValueError:
                valid_types = [t.value for t in MemoryType]
                raise HTTPException(status_code=400, detail=f"Invalid memory_type. Valid: {', '.join(valid_types)}")

        # Regenerate embedding if content changed
        embedding = None
        regenerate = False
        if request.title or request.content or request.embedding_source:
            try:
                svc = SentenceTransformerEmbeddingService()
                text = request.embedding_source or f"{request.title or ''} {request.content or ''}"
                if text.strip():
                    embedding = await svc.generate_embedding(text)
                    regenerate = True
            except Exception as e:
                logger.warning(f"Embedding regeneration failed: {e}")

        memory_repo = MemoryRepository(engine)
        update = MemoryUpdate(
            title=request.title,
            content=request.content,
            memory_type=MemoryType(request.memory_type) if request.memory_type else None,
            tags=request.tags,
            author=request.author,
            embedding_source=request.embedding_source,
        )

        result = await memory_repo.update(
            memory_id, update,
            regenerate_embedding=regenerate,
            new_embedding=embedding,
        )

        if not result:
            raise HTTPException(status_code=404, detail="Memory not found or deleted.")

        return {
            "id": str(result.id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "embedding_regenerated": regenerate,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update memory.")


# Delete endpoint

@router.delete("/{memory_id}")
async def delete_memory_endpoint(
    memory_id: str,
    permanent: bool = Query(False, description="Hard delete (irreversible)"),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """Delete a memory (soft by default, hard with ?permanent=true)."""
    from datetime import timezone
    from db.repositories.memory_repository import MemoryRepository

    try:
        memory_repo = MemoryRepository(engine)

        if permanent:
            success = await memory_repo.delete_permanently(memory_id)
        else:
            success = await memory_repo.soft_delete(memory_id)

        if not success:
            raise HTTPException(status_code=404, detail="Memory not found.")

        result = {"id": memory_id, "deleted": True, "permanent": permanent}
        if not permanent:
            result["deleted_at"] = datetime.now(timezone.utc).isoformat()
            result["can_restore"] = True
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete memory.")


@router.get("/{memory_id}")
async def get_memory_by_id(
    memory_id: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get full memory details by ID.

    Args:
        memory_id: UUID of the memory

    Returns:
        Full memory object with content, metadata, tags, etc.
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        id,
                        title,
                        content,
                        memory_type,
                        tags,
                        author,
                        created_at,
                        updated_at,
                        project_id,
                        (embedding IS NOT NULL) as has_embedding
                    FROM memories
                    WHERE id = :memory_id
                    AND deleted_at IS NULL
                """),
                {"memory_id": memory_id}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail="Memory not found or has been deleted."
                )

            return {
                "id": str(row.id),
                "title": row.title,
                "content": row.content,
                "memory_type": row.memory_type,
                "tags": row.tags or [],
                "author": row.author,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "project_id": str(row.project_id) if row.project_id else None,
                "has_embedding": row.has_embedding
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory by ID: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve memory. Please try again later."
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


# Search endpoint models and implementation

class MemorySearchRequest(BaseModel):
    """Request body for memory search."""
    query: str = Field(..., min_length=1, description="Search query")
    memory_type: Optional[str] = Field(None, description="Filter by memory type")
    tags: List[str] = Field(default_factory=list, description="Filter by tags (AND logic)")
    limit: int = Field(20, ge=1, le=100, description="Max results")
    offset: int = Field(0, ge=0, description="Pagination offset")


class MemorySearchResult(BaseModel):
    """Single memory search result."""
    id: str
    title: str
    content_preview: str
    memory_type: str
    tags: List[str]
    author: Optional[str]
    created_at: str
    score: float


class MemorySearchResponse(BaseModel):
    """Response for memory search."""
    results: List[MemorySearchResult]
    total: int
    query: str
    search_time_ms: float


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    engine: AsyncEngine = Depends(get_db_engine),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service)
) -> MemorySearchResponse:
    """
    Semantic search on memories.

    Uses hybrid lexical + vector search with RRF fusion.
    Supports filtering by memory_type (note, decision, task, reference, conversation, investigation).

    Returns:
        MemorySearchResponse with results, total count, and search metadata.
    """
    import time
    from services.hybrid_memory_search_service import HybridMemorySearchService
    from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType

    start_time = time.time()

    try:
        # Validate memory_type if provided
        memory_type_enum = None
        if request.memory_type:
            try:
                memory_type_enum = MemoryType(request.memory_type)
            except ValueError:
                valid_types = [t.value for t in MemoryType]
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid memory_type. Valid types: {', '.join(valid_types)}"
                )

        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)

        # Build filters
        filters = MemoryFilters(
            memory_type=memory_type_enum,
            tags=request.tags or [],
        )

        # Search using hybrid service
        search_service = HybridMemorySearchService(engine)
        response = await search_service.search(
            query=request.query,
            embedding=query_embedding,
            filters=filters,
            limit=request.limit,
            offset=request.offset,
        )

        # Convert to response format
        results = []
        for hr in response.results:
            results.append(MemorySearchResult(
                id=str(hr.memory_id),
                title=hr.title,
                content_preview=hr.content_preview,
                memory_type=hr.memory_type,
                tags=hr.tags or [],
                author=hr.author,
                created_at=hr.created_at,
                score=round(hr.rrf_score, 4),
            ))

        elapsed_ms = (time.time() - start_time) * 1000

        return MemorySearchResponse(
            results=results,
            total=response.metadata.total_results,
            query=request.query,
            search_time_ms=round(elapsed_ms, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Memory search failed. Please try again later."
        )
