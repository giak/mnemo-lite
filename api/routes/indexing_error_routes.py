"""
API routes for indexing error tracking.

Endpoints:
- GET /api/v1/indexing/batch/errors/{repository} - List errors with filtering
- GET /api/v1/indexing/batch/errors/{repository}/summary - Error counts by type
"""

from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine

from models.indexing_error_models import IndexingErrorsListResponse
from services.indexing_error_service import IndexingErrorService
from dependencies import get_db_engine


router = APIRouter(
    prefix="/api/v1/indexing/batch/errors",
    tags=["error-tracking"]
)


@router.get("/{repository}", response_model=IndexingErrorsListResponse)
async def get_indexing_errors(
    repository: str,
    error_type: Optional[str] = Query(None, description="Filter by error type"),
    limit: int = Query(100, ge=1, le=1000, description="Max errors to return"),
    offset: int = Query(0, ge=0, description="Number of errors to skip"),
    engine: AsyncEngine = Depends(get_db_engine)
):
    """
    Get indexing errors for a repository.

    Query parameters:
    - error_type: Filter by specific error type (parsing_error, chunking_error, etc.)
    - limit: Maximum number of errors to return (1-1000, default: 100)
    - offset: Pagination offset (default: 0)

    Returns:
    - errors: List of error records
    - total: Total count matching filters
    - repository: Repository name
    - filters: Applied filters
    """
    service = IndexingErrorService(engine)

    errors, total = await service.get_errors(
        repository=repository,
        error_type=error_type,
        limit=limit,
        offset=offset
    )

    return IndexingErrorsListResponse(
        errors=errors,
        total=total,
        repository=repository,
        filters={
            "error_type": error_type,
            "limit": limit,
            "offset": offset
        }
    )


@router.get("/{repository}/summary")
async def get_error_summary(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine)
):
    """
    Get summary of errors grouped by error_type.

    Returns:
    - repository: Repository name
    - summary: Dict mapping error_type to count
    - total_errors: Total count across all types
    """
    service = IndexingErrorService(engine)

    summary = await service.get_error_summary(repository)
    total_errors = sum(summary.values())

    return {
        "repository": repository,
        "summary": summary,
        "total_errors": total_errors
    }
