"""
Pydantic models for batch indexing API.

EPIC-27: Batch Processing with Redis Streams
Task 10: API Endpoints for external access
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class BatchIndexingRequest(BaseModel):
    """Request to start batch indexing job."""

    directory: str = Field(
        ...,
        description="Directory to index (absolute path)",
        examples=["/app/code_test"]
    )
    repository: str = Field(
        ...,
        description="Repository name",
        examples=["code_test"]
    )
    extensions: List[str] = Field(
        default=[".ts", ".js"],
        description="File extensions to index",
        examples=[[".ts", ".js"]]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "directory": "/app/code_test",
                "repository": "code_test",
                "extensions": [".ts", ".js"]
            }
        }
    }


class BatchIndexingResponse(BaseModel):
    """Response from starting batch indexing job."""

    job_id: str = Field(..., description="Unique job identifier")
    repository: str = Field(..., description="Repository name")
    total_files: int = Field(..., description="Total number of files to index")
    total_batches: int = Field(..., description="Total number of batches")
    status: str = Field(..., description="Job status (pending, processing, completed, failed)")
    message: str = Field(..., description="Human-readable status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "repository": "code_test",
                "total_files": 261,
                "total_batches": 7,
                "status": "pending",
                "message": "Batch indexing started. Use GET /status/{repository} to monitor progress."
            }
        }
    }


class BatchIndexingStatusResponse(BaseModel):
    """Response with current batch indexing status."""

    job_id: Optional[str] = Field(None, description="Job identifier (null if not found)")
    repository: str = Field(..., description="Repository name")
    total_files: int = Field(..., description="Total number of files")
    processed_files: int = Field(..., description="Number of files processed successfully")
    failed_files: int = Field(..., description="Number of files that failed")
    current_batch: int = Field(..., description="Current batch number being processed")
    total_batches: int = Field(..., description="Total number of batches")
    status: str = Field(..., description="Job status (pending, processing, completed, failed, not_found)")
    progress: str = Field(..., description="Progress as 'processed/total'")
    progress_percent: float = Field(..., description="Progress percentage (0-100)")
    started_at: Optional[str] = Field(None, description="Job start timestamp (ISO format)")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp (ISO format)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "repository": "code_test",
                "total_files": 261,
                "processed_files": 180,
                "failed_files": 2,
                "current_batch": 5,
                "total_batches": 7,
                "status": "processing",
                "progress": "180/261",
                "progress_percent": 68.96,
                "started_at": "2025-11-02T10:30:00",
                "completed_at": None
            }
        }
    }
