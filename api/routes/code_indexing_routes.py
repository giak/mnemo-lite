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
from dependencies import get_db_engine
from services.code_chunking_service import CodeChunkingService
from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
)
from services.dual_embedding_service import DualEmbeddingService
from services.graph_construction_service import GraphConstructionService
from services.metadata_extractor_service import MetadataExtractorService

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
) -> CodeIndexingService:
    """Get CodeIndexingService instance with all dependencies."""
    chunking_service = CodeChunkingService()
    metadata_service = MetadataExtractorService()
    embedding_service = DualEmbeddingService()
    graph_service = GraphConstructionService(engine)
    chunk_repository = CodeChunkRepository(engine)

    return CodeIndexingService(
        engine=engine,
        chunking_service=chunking_service,
        metadata_service=metadata_service,
        embedding_service=embedding_service,
        graph_service=graph_service,
        chunk_repository=chunk_repository,
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
    """,
)
async def delete_repository(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine),
) -> DeleteRepositoryResponse:
    """
    Delete all indexed data for a repository.

    Args:
        repository: Repository name
        engine: Database engine (injected)

    Returns:
        DeleteRepositoryResponse with deletion statistics
    """
    try:
        # Delete code chunks
        delete_chunks = text("""
            DELETE FROM code_chunks
            WHERE repository = :repository
        """)

        # Delete nodes (assuming nodes have repository in props)
        delete_nodes = text("""
            DELETE FROM nodes
            WHERE props->>'repository' = :repository
        """)

        # Delete orphaned edges
        delete_edges = text("""
            DELETE FROM edges
            WHERE NOT EXISTS (
                SELECT 1 FROM nodes WHERE nodes.node_id = edges.source_node_id
            )
        """)

        async with engine.begin() as conn:
            result1 = await conn.execute(
                delete_chunks, {"repository": repository}
            )
            result2 = await conn.execute(delete_nodes, {"repository": repository})
            result3 = await conn.execute(delete_edges)

        return DeleteRepositoryResponse(
            repository=repository,
            deleted_chunks=result1.rowcount,
            deleted_nodes=result2.rowcount,
            deleted_edges=result3.rowcount,
        )

    except Exception as e:
        logger.error(f"Delete repository failed: {e}", exc_info=True)
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
