"""
Code Search API Routes (v1).

Provides hybrid code search endpoints combining lexical (pg_trgm)
and semantic (HNSW) search with RRF fusion.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from services.hybrid_code_search_service import (
    HybridCodeSearchService,
    HybridSearchResponse,
    SearchFilters,
)
from dependencies import get_db_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/code/search", tags=["code-search"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SearchFiltersModel(BaseModel):
    """Filters for code search."""
    language: Optional[str] = Field(None, description="Filter by programming language (e.g., 'python')")
    chunk_type: Optional[str] = Field(None, description="Filter by chunk type (e.g., 'function', 'class')")
    repository: Optional[str] = Field(None, description="Filter by repository name")
    file_path: Optional[str] = Field(None, description="Filter by file path (partial match)")


class HybridSearchRequest(BaseModel):
    """Request for hybrid code search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query (keywords)")

    embedding_text: Optional[List[float]] = Field(
        None,
        description="Optional TEXT domain embedding (768D). If not provided, lexical-only search.",
    )

    embedding_code: Optional[List[float]] = Field(
        None,
        description="Optional CODE domain embedding (768D). Used if provided, otherwise TEXT embedding used.",
    )

    filters: Optional[SearchFiltersModel] = Field(None, description="Optional search filters")

    top_k: int = Field(10, ge=1, le=100, description="Number of results to return (1-100)")

    enable_lexical: bool = Field(True, description="Enable lexical search (pg_trgm)")
    enable_vector: bool = Field(True, description="Enable vector search (HNSW)")

    lexical_weight: float = Field(0.4, ge=0.0, le=1.0, description="Weight for lexical results in RRF (0.0-1.0)")
    vector_weight: float = Field(0.6, ge=0.0, le=1.0, description="Weight for vector results in RRF (0.0-1.0)")

    candidate_pool_size: int = Field(
        100,
        ge=10,
        le=1000,
        description="Candidate pool size per method before fusion (10-1000)",
    )

    auto_weights: bool = Field(
        False,
        description="Automatically adjust weights based on query analysis (overrides lexical_weight/vector_weight)",
    )


class HybridSearchResultModel(BaseModel):
    """Single result from hybrid search."""
    chunk_id: str
    rrf_score: float
    rank: int

    source_code: str
    name: str
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]

    lexical_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    vector_distance: Optional[float] = None

    contribution: Dict[str, float]
    related_nodes: List[str] = []


class SearchMetadataModel(BaseModel):
    """Metadata about search execution."""
    total_results: int
    lexical_count: int
    vector_count: int
    unique_after_fusion: int

    lexical_enabled: bool
    vector_enabled: bool
    graph_expansion_enabled: bool

    lexical_weight: float
    vector_weight: float

    execution_time_ms: float
    lexical_time_ms: Optional[float] = None
    vector_time_ms: Optional[float] = None
    fusion_time_ms: Optional[float] = None
    graph_time_ms: Optional[float] = None


class HybridSearchResponseModel(BaseModel):
    """Response from hybrid code search."""
    results: List[HybridSearchResultModel]
    metadata: SearchMetadataModel


class LexicalSearchRequest(BaseModel):
    """Request for lexical-only search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query (keywords)")
    filters: Optional[SearchFiltersModel] = Field(None, description="Optional search filters")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results (1-1000)")


class VectorSearchRequest(BaseModel):
    """Request for vector-only search."""
    embedding: List[float] = Field(..., description="Query embedding (768D)")
    embedding_domain: str = Field("TEXT", description="Embedding domain: 'TEXT' or 'CODE'")
    filters: Optional[SearchFiltersModel] = Field(None, description="Optional search filters")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results (1-1000)")


# ============================================================================
# Dependency Injection
# ============================================================================

async def get_hybrid_search_service(
    engine: AsyncEngine = Depends(get_db_engine),
) -> HybridCodeSearchService:
    """Get HybridCodeSearchService instance."""
    return HybridCodeSearchService(engine=engine)


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/hybrid",
    response_model=HybridSearchResponseModel,
    status_code=status.HTTP_200_OK,
    summary="Hybrid Code Search",
    description="""
    Execute hybrid code search combining lexical (pg_trgm) and semantic (HNSW) search with RRF fusion.

    **Search Methods**:
    - **Lexical**: PostgreSQL trigram similarity on source code and function names (fuzzy keyword matching)
    - **Vector**: HNSW approximate nearest neighbor search on embeddings (semantic similarity)
    - **RRF Fusion**: Reciprocal Rank Fusion combines results without score normalization (k=60)

    **Performance**: <50ms P95 on 10k chunks with parallel execution

    **Usage**:
    - Provide `query` for lexical search (required)
    - Provide `embedding_text` or `embedding_code` for vector search (optional)
    - Adjust `lexical_weight` and `vector_weight` for custom fusion (default: 0.4/0.6)
    - Use `auto_weights=true` for automatic weight selection based on query analysis

    **Filters**: Filter by language, chunk_type, repository, or file_path

    **Examples**:
    - Keyword search: `{"query": "calculate total price", "enable_vector": false}`
    - Semantic search: `{"query": "...", "embedding_text": [...], "enable_lexical": false}`
    - Hybrid search: `{"query": "...", "embedding_text": [...]}`
    """,
)
async def hybrid_search(
    request: HybridSearchRequest,
    service: HybridCodeSearchService = Depends(get_hybrid_search_service),
) -> HybridSearchResponseModel:
    """
    Execute hybrid code search.

    Combines lexical and semantic search with RRF fusion.
    """
    try:
        # Convert filters
        filters = None
        if request.filters:
            filters = SearchFilters(
                language=request.filters.language,
                chunk_type=request.filters.chunk_type,
                repository=request.filters.repository,
                file_path=request.filters.file_path,
            )

        # Execute search
        if request.auto_weights:
            # Use automatic weight selection
            response = await service.search_with_auto_weights(
                query=request.query,
                embedding_text=request.embedding_text,
                embedding_code=request.embedding_code,
                filters=filters,
                top_k=request.top_k,
            )
        else:
            # Use manual weights
            response = await service.search(
                query=request.query,
                embedding_text=request.embedding_text,
                embedding_code=request.embedding_code,
                filters=filters,
                top_k=request.top_k,
                enable_lexical=request.enable_lexical,
                enable_vector=request.enable_vector,
                lexical_weight=request.lexical_weight,
                vector_weight=request.vector_weight,
                candidate_pool_size=request.candidate_pool_size,
            )

        # Convert to response model
        return HybridSearchResponseModel(
            results=[
                HybridSearchResultModel(
                    chunk_id=r.chunk_id,
                    rrf_score=r.rrf_score,
                    rank=r.rank,
                    source_code=r.source_code,
                    name=r.name,
                    language=r.language,
                    chunk_type=r.chunk_type,
                    file_path=r.file_path,
                    metadata=r.metadata,
                    lexical_score=r.lexical_score,
                    vector_similarity=r.vector_similarity,
                    vector_distance=r.vector_distance,
                    contribution=r.contribution,
                    related_nodes=r.related_nodes,
                )
                for r in response.results
            ],
            metadata=SearchMetadataModel(
                total_results=response.metadata.total_results,
                lexical_count=response.metadata.lexical_count,
                vector_count=response.metadata.vector_count,
                unique_after_fusion=response.metadata.unique_after_fusion,
                lexical_enabled=response.metadata.lexical_enabled,
                vector_enabled=response.metadata.vector_enabled,
                graph_expansion_enabled=response.metadata.graph_expansion_enabled,
                lexical_weight=response.metadata.lexical_weight,
                vector_weight=response.metadata.vector_weight,
                execution_time_ms=response.metadata.execution_time_ms,
                lexical_time_ms=response.metadata.lexical_time_ms,
                vector_time_ms=response.metadata.vector_time_ms,
                fusion_time_ms=response.metadata.fusion_time_ms,
                graph_time_ms=response.metadata.graph_time_ms,
            ),
        )

    except ValueError as e:
        logger.error(f"Validation error in hybrid search: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hybrid search failed. Please check logs for details.",
        )


@router.post(
    "/lexical",
    status_code=status.HTTP_200_OK,
    summary="Lexical-Only Search",
    description="""
    Execute lexical-only search using PostgreSQL trigram similarity.

    Useful for:
    - Testing/comparison with hybrid search
    - Keyword-only queries without embeddings
    - Debugging lexical search performance

    Uses pg_trgm similarity on source_code and name columns with fuzzy matching.
    """,
)
async def lexical_search(
    request: LexicalSearchRequest,
    service: HybridCodeSearchService = Depends(get_hybrid_search_service),
):
    """Execute lexical-only search."""
    try:
        # Convert filters
        filters_dict = None
        if request.filters:
            filters_dict = {
                k: v
                for k, v in {
                    "language": request.filters.language,
                    "chunk_type": request.filters.chunk_type,
                    "repository": request.filters.repository,
                    "file_path": request.filters.file_path,
                }.items()
                if v is not None
            }

        # Execute lexical search
        results = await service.lexical.search(
            query=request.query,
            filters=filters_dict,
            limit=request.limit,
        )

        return {
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "similarity_score": r.similarity_score,
                    "rank": r.rank,
                    "source_code": r.source_code,
                    "name": r.name,
                    "language": r.language,
                    "chunk_type": r.chunk_type,
                    "file_path": r.file_path,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "total_results": len(results),
        }

    except ValueError as e:
        logger.error(f"Validation error in lexical search: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Lexical search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lexical search failed. Please check logs for details.",
        )


@router.post(
    "/vector",
    status_code=status.HTTP_200_OK,
    summary="Vector-Only Search",
    description="""
    Execute vector-only search using HNSW approximate nearest neighbor search.

    Useful for:
    - Testing/comparison with hybrid search
    - Pure semantic search without keywords
    - Debugging vector search performance

    Uses pgvector HNSW indexes on embedding_text or embedding_code columns.
    """,
)
async def vector_search(
    request: VectorSearchRequest,
    service: HybridCodeSearchService = Depends(get_hybrid_search_service),
):
    """Execute vector-only search."""
    try:
        # Validate embedding domain
        if request.embedding_domain not in ("TEXT", "CODE"):
            raise ValueError("embedding_domain must be 'TEXT' or 'CODE'")

        # Convert filters
        filters_dict = None
        if request.filters:
            filters_dict = {
                k: v
                for k, v in {
                    "language": request.filters.language,
                    "chunk_type": request.filters.chunk_type,
                    "repository": request.filters.repository,
                    "file_path": request.filters.file_path,
                }.items()
                if v is not None
            }

        # Execute vector search
        results = await service.vector.search(
            embedding=request.embedding,
            embedding_domain=request.embedding_domain,
            filters=filters_dict,
            limit=request.limit,
        )

        return {
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "distance": r.distance,
                    "similarity": r.similarity,
                    "rank": r.rank,
                    "source_code": r.source_code,
                    "name": r.name,
                    "language": r.language,
                    "chunk_type": r.chunk_type,
                    "file_path": r.file_path,
                    "metadata": r.metadata,
                    "embedding_domain": r.embedding_domain,
                }
                for r in results
            ],
            "total_results": len(results),
            "embedding_domain": request.embedding_domain,
        }

    except ValueError as e:
        logger.error(f"Validation error in vector search: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vector search failed. Please check logs for details.",
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Search Service Health Check",
    description="Check if search services are operational.",
)
async def search_health(
    engine: AsyncEngine = Depends(get_db_engine),
):
    """Check search service health."""
    try:
        # Check database connection
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()

        # Check if required tables exist
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name IN ('code_chunks', 'nodes', 'edges')
            """))
            table_count = result.scalar()

        return {
            "status": "healthy",
            "database": "connected",
            "required_tables": f"{table_count}/3",
            "services": {
                "lexical_search": "available",
                "vector_search": "available",
                "rrf_fusion": "available",
                "hybrid_search": "available",
            },
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service unhealthy. Please check logs for details.",
        )
