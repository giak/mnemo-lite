"""
Code Indexing API Routes (v1) for EPIC-06 Phase 4 Story 6.

Provides endpoints for indexing code repositories into MnemoLite.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.code_chunk_repository import CodeChunkRepository
from db.repositories.node_repository import NodeRepository  # EPIC-12 Story 12.2
from db.repositories.edge_repository import EdgeRepository  # EPIC-12 Story 12.2
from dependencies import (
    get_db_engine,
    get_code_chunk_cache,
    get_redis_cache,  # EPIC-13 Story 13.4
    get_chunk_repository,  # EPIC-12 Story 12.2
    get_node_repository,   # EPIC-12 Story 12.2
    get_edge_repository,   # EPIC-12 Story 12.2
)
from services.caches import CodeChunkCache, RedisCache
from services.code_chunking_service import CodeChunkingService
from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
)
from services.dual_embedding_service import DualEmbeddingService
from services.graph_construction_service import GraphConstructionService
from services.lsp import PyrightLSPClient, TypeExtractorService  # EPIC-13 Story 13.2
from services.metadata_extractor_service import MetadataExtractorService
from services.symbol_path_service import SymbolPathService  # EPIC-11

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/code/index", tags=["code-indexing"])


# ============================================================================
# Request/Response Models
# ============================================================================


class FileInputModel(BaseModel):
    """Input file for indexing."""

    path: str = Field(
        ..., description="File path (relative to repository root)"
    )
    content: str = Field(..., description="File content (source code)")
    language: Optional[str] = Field(
        None, description="Programming language (auto-detected if not provided)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "path": "src/main.py",
                "content": "def main():\n    print('Hello, World!')",
                "language": "python",
            }
        }
    }


class IndexRequest(BaseModel):
    """Request to index files."""

    repository: str = Field(..., description="Repository name/identifier")
    repository_root: str = Field("/app", description="EPIC-11: Absolute path to repository root for name_path generation")
    files: List[FileInputModel] = Field(..., description="List of files to index")
    commit_hash: Optional[str] = Field(
        None, description="Git commit hash (optional)"
    )
    extract_metadata: bool = Field(
        True, description="Extract metadata (complexity, calls, etc.)"
    )
    generate_embeddings: bool = Field(
        True, description="Generate dual embeddings (TEXT + CODE)"
    )
    build_graph: bool = Field(
        True, description="Build call graph after indexing"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "repository": "my-project",
                "files": [
                    {
                        "path": "src/main.py",
                        "content": "def main():\n    print('Hello, World!')",
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": True,
                "build_graph": True,
            }
        }
    }


class IndexResponse(BaseModel):
    """Response from indexing operation."""

    repository: str
    indexed_files: int
    indexed_chunks: int
    indexed_nodes: int
    indexed_edges: int
    failed_files: int
    processing_time_ms: float
    errors: List[Dict[str, Any]]

    model_config = {
        "json_schema_extra": {
            "example": {
                "repository": "my-project",
                "indexed_files": 5,
                "indexed_chunks": 42,
                "indexed_nodes": 38,
                "indexed_edges": 51,
                "failed_files": 0,
                "processing_time_ms": 2341.5,
                "errors": [],
            }
        }
    }


class RepositoryInfo(BaseModel):
    """Information about an indexed repository."""

    repository: str
    file_count: int
    chunk_count: int
    last_indexed: Optional[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "repository": "my-project",
                "file_count": 127,
                "chunk_count": 543,
                "last_indexed": "2025-10-16T10:30:00Z",
            }
        }
    }


class RepositoryListResponse(BaseModel):
    """Response listing all repositories."""

    repositories: List[RepositoryInfo]

    model_config = {
        "json_schema_extra": {
            "example": {
                "repositories": [
                    {
                        "repository": "my-project",
                        "file_count": 127,
                        "chunk_count": 543,
                        "last_indexed": "2025-10-16T10:30:00Z",
                    }
                ]
            }
        }
    }


class DeleteRepositoryResponse(BaseModel):
    """Response from deleting a repository."""

    repository: str
    deleted_chunks: int
    deleted_nodes: int
    deleted_edges: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "repository": "my-project",
                "deleted_chunks": 543,
                "deleted_nodes": 412,
                "deleted_edges": 638,
            }
        }
    }


# ============================================================================
# Dependency Injection
# ============================================================================


async def get_indexing_service(
    engine: AsyncEngine = Depends(get_db_engine),
    chunk_cache: CodeChunkCache = Depends(get_code_chunk_cache),
    redis_cache: RedisCache = Depends(get_redis_cache),  # EPIC-13 Story 13.4
) -> CodeIndexingService:
    """Get CodeIndexingService instance with all dependencies (including L1 cache)."""
    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    embedding_service = DualEmbeddingService()
    graph_service = GraphConstructionService(engine)
    chunk_repository = CodeChunkRepository(engine)
    symbol_path_service = SymbolPathService()  # EPIC-11 Story 11.1

    # EPIC-13 Story 13.2/13.4: LSP Type Extraction with L2 Redis caching
    # Story 13.2: Type extraction service
    # Story 13.4: Redis caching for 10× performance improvement
    type_extractor = None
    try:
        lsp_client = PyrightLSPClient()
        await lsp_client.start()
        # Pass redis_cache for LSP result caching (Story 13.4)
        type_extractor = TypeExtractorService(
            lsp_client=lsp_client,
            redis_cache=redis_cache  # Story 13.4: L2 cache for LSP results
        )
        logger.info("TypeExtractorService initialized with Pyright LSP and Redis cache")
    except Exception as e:
        # Graceful degradation: LSP unavailable, continue without type extraction
        logger.warning(f"Failed to initialize LSP client, type extraction disabled: {e}")
        type_extractor = None

    return CodeIndexingService(
        engine=engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
        chunk_cache=chunk_cache,  # Inject L1 cache (EPIC-10 Story 10.1)
        symbol_path_service=symbol_path_service,  # EPIC-11: Hierarchical name_path generation
        type_extractor=type_extractor,  # EPIC-13 Story 13.2: Optional LSP type extraction
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "",
    response_model=IndexResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index code files",
    description="""
    Index a list of code files into MnemoLite.

    **Pipeline (7 steps)**:
    1. **Language detection** (if not provided)
    2. **Tree-sitter parsing** → semantic chunks
    3. **Metadata extraction** (complexity, calls, docstrings, etc.)
    4. **Dual embedding generation** (TEXT + CODE, 768D)
    5. **Storage** in PostgreSQL (code_chunks table)
    6. **Call graph construction** (nodes + edges tables)
    7. **Summary generation**

    **Performance targets**:
    - <500ms per file (300 LOC average)
    - Batch processing supported

    **Error handling**:
    - Individual file failures don't stop batch
    - Errors returned in response
    - Partial success possible

    **Building blocks used**:
    - CodeChunkingService (Story 1)
    - MetadataExtractorService (Story 3)
    - DualEmbeddingService (Story 0.2)
    - GraphConstructionService (Story 4)
    - CodeChunkRepository (Story 2bis)
    """,
)
async def index_files(
    request: IndexRequest,
    service: CodeIndexingService = Depends(get_indexing_service),
) -> IndexResponse:
    """
    Index code files into MnemoLite.

    Args:
        request: IndexRequest with files and options
        service: CodeIndexingService (injected)

    Returns:
        IndexResponse with statistics
    """
    try:
        # Convert request to service models
        files = [
            FileInput(
                path=f.path,
                content=f.content,
                language=f.language,
            )
            for f in request.files
        ]

        options = IndexingOptions(
            extract_metadata=request.extract_metadata,
            generate_embeddings=request.generate_embeddings,
            build_graph=request.build_graph,
            repository=request.repository,
            repository_root=request.repository_root,  # EPIC-11: Pass repository root for name_path
            commit_hash=request.commit_hash,
        )

        # Index files
        summary = await service.index_repository(files, options)

        # Return response
        return IndexResponse(
            repository=summary.repository,
            indexed_files=summary.indexed_files,
            indexed_chunks=summary.indexed_chunks,
            indexed_nodes=summary.indexed_nodes,
            indexed_edges=summary.indexed_edges,
            failed_files=summary.failed_files,
            processing_time_ms=summary.processing_time_ms,
            errors=summary.errors,
        )

    except ValueError as e:
        logger.error(f"Validation error in index_files: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Index files failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Indexing failed. Please check logs for details.",
        )


@router.get(
    "/repositories",
    response_model=RepositoryListResponse,
    summary="List indexed repositories",
    description="""
    Get list of all indexed repositories with statistics.

    Returns for each repository:
    - Repository name
    - Number of indexed files
    - Number of chunks
    - Last indexed timestamp
    """,
)
async def list_repositories(
    engine: AsyncEngine = Depends(get_db_engine),
) -> RepositoryListResponse:
    """
    List all indexed repositories.

    Args:
        engine: Database engine (injected)

    Returns:
        RepositoryListResponse with repository list
    """
    try:
        # Query code_chunks grouped by repository
        query = text("""
            SELECT
                repository,
                COUNT(DISTINCT file_path) as file_count,
                COUNT(*) as chunk_count,
                MAX(indexed_at) as last_indexed
            FROM code_chunks
            WHERE repository IS NOT NULL
            GROUP BY repository
            ORDER BY last_indexed DESC
        """)

        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        repositories = [
            RepositoryInfo(
                repository=row[0],
                file_count=row[1],
                chunk_count=row[2],
                last_indexed=row[3].isoformat() if row[3] else None,
            )
            for row in rows
        ]

        return RepositoryListResponse(repositories=repositories)

    except Exception as e:
        logger.error(f"List repositories failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list repositories. Please check logs for details.",
        )


@router.delete(
    "/repositories/{repository}",
    response_model=DeleteRepositoryResponse,
    summary="Delete repository",
    description="""
    Delete all indexed data for a repository.

    Deletes:
    - All code chunks for the repository
    - All nodes associated with the repository
    - All orphaned edges (edges without source/target nodes)

    **Warning**: This operation is irreversible.

    EPIC-12 Story 12.2: Atomic transaction ensures all-or-nothing deletion.
    """,
)
async def delete_repository(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine),
    chunk_repo: CodeChunkRepository = Depends(get_chunk_repository),
    node_repo: NodeRepository = Depends(get_node_repository),
    edge_repo: EdgeRepository = Depends(get_edge_repository),
) -> DeleteRepositoryResponse:
    """
    Delete all indexed data for a repository.

    EPIC-12 Story 12.2: Uses repository bulk delete methods with transaction support
    for atomic all-or-nothing deletion with cache invalidation coordination.

    Args:
        repository: Repository name
        engine: Database engine (injected)
        chunk_repo: Code chunk repository (injected)
        node_repo: Node repository (injected)
        edge_repo: Edge repository (injected)

    Returns:
        DeleteRepositoryResponse with deletion statistics
    """
    try:
        # EPIC-12 Story 12.2: Wrap all deletions in transaction
        # If any deletion fails, entire operation is rolled back (atomic operation)
        async with engine.begin() as conn:
            logger.info(
                f"EPIC-12: Starting atomic repository deletion transaction for '{repository}'"
            )

            # Delete code chunks using repository method
            deleted_chunks = await chunk_repo.delete_by_repository(repository, connection=conn)

            # Delete nodes using repository method
            deleted_nodes = await node_repo.delete_by_repository(repository, connection=conn)

            # Delete orphaned edges (edges without source/target nodes)
            delete_edges_query = text("""
                DELETE FROM edges
                WHERE NOT EXISTS (
                    SELECT 1 FROM nodes WHERE nodes.node_id = edges.source_node_id
                )
            """)
            result3 = await conn.execute(delete_edges_query)
            deleted_edges = result3.rowcount

            # Transaction auto-commits on successful context exit
            logger.info(
                f"✅ EPIC-12: Repository deletion transaction committed - "
                f"{deleted_chunks} chunks, {deleted_nodes} nodes, {deleted_edges} edges deleted atomically"
            )

        return DeleteRepositoryResponse(
            repository=repository,
            deleted_chunks=deleted_chunks,
            deleted_nodes=deleted_nodes,
            deleted_edges=deleted_edges,
        )

    except Exception as e:
        # Transaction auto-rolled back on exception
        logger.error(
            f"EPIC-12: Repository deletion transaction rolled back: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete repository. Please check logs for details.",
        )


@router.get(
    "/health",
    summary="Health check",
    description="Check if indexing service is operational",
)
async def health_check(
    engine: AsyncEngine = Depends(get_db_engine),
):
    """
    Health check for indexing service.

    Args:
        engine: Database engine (injected)

    Returns:
        Health status and available services
    """
    try:
        # Check database connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Check if required tables exist
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name IN ('code_chunks', 'nodes', 'edges')
            """)
            )
            table_count = result.scalar()

        return {
            "status": "healthy",
            "database": "connected",
            "required_tables": f"{table_count}/3",
            "services": [
                "code_chunking",
                "metadata_extraction",
                "embedding_generation",
                "graph_construction",
            ],
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Indexing service unhealthy. Please check logs for details.",
        )


@router.get(
    "/cache/stats",
    summary="Get L1 cache statistics",
    description="""
    Get statistics about the L1 in-memory cache for code chunks.

    Returns:
    - Cache type (L1_memory)
    - Current size (MB) and maximum size (MB)
    - Number of cached entries
    - Hit/miss statistics
    - Eviction count
    - Hit rate percentage
    - Cache utilization percentage

    **EPIC-10 Story 10.1**: L1 In-Memory Cache with LRU eviction and MD5 validation.
    """,
)
async def get_cache_stats(
    cache: CodeChunkCache = Depends(get_code_chunk_cache),
) -> Dict[str, Any]:
    """
    Get L1 cache statistics.

    Args:
        cache: CodeChunkCache instance (injected)

    Returns:
        Cache statistics dictionary
    """
    try:
        return cache.stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics.",
        )
