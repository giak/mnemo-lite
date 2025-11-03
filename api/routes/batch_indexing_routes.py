"""
Batch Indexing API Routes for EPIC-27.

Provides REST API endpoints for starting and monitoring batch indexing jobs.

EPIC-27: Batch Processing with Redis Streams
Task 10: API Endpoints for external access
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from models.batch_indexing_models import (
    BatchIndexingRequest,
    BatchIndexingResponse,
    BatchIndexingStatusResponse,
)
from services.batch_indexing_producer import BatchIndexingProducer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/indexing/batch", tags=["Batch Indexing"])


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/start",
    response_model=BatchIndexingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start batch indexing job",
    description="""
    Start a batch indexing job for a directory.

    **Flow**:
    1. Producer scans directory for files matching extensions
    2. Divides files into batches (40 files per batch)
    3. Enqueues batches into Redis Stream
    4. Initializes status Hash for tracking
    5. Returns job info

    **Usage**:
    - POST this endpoint to start indexing
    - Use GET /status/{repository} to monitor progress
    - Consumer daemon processes batches in background

    **Performance**:
    - Batch size: 40 files (~3min per batch)
    - Concurrent processing: 1 batch at a time
    - Memory isolated: Each batch in separate subprocess

    **Example**:
    ```bash
    curl -X POST http://localhost:8001/api/v1/indexing/batch/start \\
      -H "Content-Type: application/json" \\
      -d '{
        "directory": "/app/code_test",
        "repository": "code_test",
        "extensions": [".ts", ".js"]
      }'
    ```

    **Returns**:
    - job_id: Unique job identifier
    - total_files: Number of files found
    - total_batches: Number of batches created
    - status: "pending" (consumer will process)
    - message: Instructions for monitoring

    **EPIC-27**: Task 10 - REST API for batch indexing with Redis Streams
    """,
)
async def start_batch_indexing(
    request: BatchIndexingRequest,
) -> BatchIndexingResponse:
    """
    Start batch indexing job.

    Args:
        request: BatchIndexingRequest with directory, repository, extensions

    Returns:
        BatchIndexingResponse with job info

    Raises:
        HTTPException 400: Invalid directory or no files found
        HTTPException 500: Internal error during job creation
    """
    try:
        # Validate directory exists
        directory = Path(request.directory)
        if not directory.exists() or not directory.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Directory not found or invalid: {request.directory}",
            )

        # Create producer and enqueue batches
        producer = BatchIndexingProducer()

        try:
            job_info = await producer.scan_and_enqueue(
                directory=directory,
                repository=request.repository,
                extensions=request.extensions,
                include_tests=request.include_tests,
            )
        finally:
            await producer.close()

        # Validate that files were found
        if job_info["total_files"] == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No files found in {request.directory} with extensions {request.extensions}",
            )

        # Return success response
        message = f"Batch indexing started. Found {job_info['total_files']} files."
        if request.include_tests:
            message += " (including test files)"
        message += f" Use GET /status/{request.repository} to monitor progress."

        return BatchIndexingResponse(
            job_id=job_info["job_id"],
            repository=request.repository,
            total_files=job_info["total_files"],
            total_batches=job_info["total_batches"],
            status=job_info["status"],
            message=message,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to start batch indexing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start batch indexing: {str(e)}",
        )


@router.get(
    "/status/{repository}",
    response_model=BatchIndexingStatusResponse,
    summary="Get batch indexing status",
    description="""
    Get current status of batch indexing job for a repository.

    **Returns**:
    - job_id: Job identifier (or null if not found)
    - total_files: Total number of files to index
    - processed_files: Number of files processed successfully
    - failed_files: Number of files that failed
    - current_batch: Current batch being processed
    - total_batches: Total number of batches
    - status: Job status (pending, processing, completed, failed, not_found)
    - progress: Progress as "processed/total"
    - progress_percent: Progress percentage (0-100)
    - started_at: Job start timestamp
    - completed_at: Job completion timestamp (null if not completed)

    **Status values**:
    - `pending`: Job created, waiting for consumer
    - `processing`: Consumer actively processing batches
    - `completed`: All batches processed successfully
    - `failed`: Critical error occurred
    - `not_found`: No job found for repository

    **Example**:
    ```bash
    curl -s http://localhost:8001/api/v1/indexing/batch/status/code_test | jq
    ```

    **Monitoring**:
    - Poll this endpoint to track progress
    - Recommended interval: 2-5 seconds
    - Job completes when status="completed"

    **EPIC-27**: Task 10 - REST API for batch indexing status monitoring
    """,
)
async def get_batch_indexing_status(
    repository: str,
) -> BatchIndexingStatusResponse:
    """
    Get batch indexing status for repository.

    Args:
        repository: Repository name

    Returns:
        BatchIndexingStatusResponse with current status

    Raises:
        HTTPException 500: Error fetching status from Redis
    """
    try:
        # Create producer and get status
        producer = BatchIndexingProducer()

        try:
            status_data = await producer.get_status(repository)
        finally:
            await producer.close()

        # Check if job exists
        if status_data.get("status") == "not_found":
            return BatchIndexingStatusResponse(
                job_id=None,
                repository=repository,
                total_files=0,
                processed_files=0,
                failed_files=0,
                current_batch=0,
                total_batches=0,
                status="not_found",
                progress="0/0",
                progress_percent=0.0,
                started_at=None,
                completed_at=None,
            )

        # Calculate progress percentage
        total_files = status_data.get("total_files", 0)
        processed_files = status_data.get("processed_files", 0)
        progress_percent = (
            (processed_files / total_files * 100.0) if total_files > 0 else 0.0
        )

        # Return status response
        return BatchIndexingStatusResponse(
            job_id=status_data.get("job_id"),
            repository=repository,
            total_files=total_files,
            processed_files=processed_files,
            failed_files=status_data.get("failed_files", 0),
            current_batch=status_data.get("current_batch", 0),
            total_batches=status_data.get("total_batches", 0),
            status=status_data.get("status", "unknown"),
            progress=status_data.get("progress", "0/0"),
            progress_percent=round(progress_percent, 2),
            started_at=status_data.get("started_at"),
            completed_at=status_data.get("completed_at"),
        )

    except Exception as e:
        logger.error(f"Failed to get batch indexing status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get batch indexing status: {str(e)}",
        )
