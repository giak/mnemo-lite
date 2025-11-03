"""
Pydantic models for indexing error tracking.

Error types:
- parsing_error: Tree-sitter parsing failed (complex TypeScript syntax)
- encoding_error: File encoding issue (non-UTF8)
- chunking_error: Failed to create chunks from AST
- embedding_error: Failed to generate embeddings
- persistence_error: Failed to write to database
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class IndexingErrorCreate(BaseModel):
    """Model for creating a new indexing error record."""

    repository: str = Field(..., description="Repository name")
    file_path: str = Field(..., description="Full path to file that failed")
    error_type: str = Field(
        ...,
        description="Error category: parsing_error, encoding_error, chunking_error, embedding_error, persistence_error"
    )
    error_message: str = Field(..., description="Short error message")
    error_traceback: Optional[str] = Field(None, description="Full stack trace")
    chunk_type: Optional[str] = Field(None, description="Type of chunk being processed (class, function, etc.)")
    language: Optional[str] = Field(None, description="Programming language (typescript, javascript)")


class IndexingErrorResponse(BaseModel):
    """Model for error records returned by API."""

    error_id: int
    repository: str
    file_path: str
    error_type: str
    error_message: str
    error_traceback: Optional[str] = None
    chunk_type: Optional[str] = None
    language: Optional[str] = None
    occurred_at: datetime

    class Config:
        from_attributes = True  # Enable SQLAlchemy model conversion


class IndexingErrorsListResponse(BaseModel):
    """Model for paginated list of errors."""

    errors: list[IndexingErrorResponse]
    total: int
    repository: str
    filters: dict = Field(default_factory=dict)
