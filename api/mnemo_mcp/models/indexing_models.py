"""
Pydantic models for MCP Indexing Tools & Resources (EPIC-23 Story 23.5).

Models for project indexing, status tracking, and progress reporting.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from mnemo_mcp.base import MCPBaseResponse


# ============================================================================
# Indexing Request/Response Models
# ============================================================================


class IndexingOptions(BaseModel):
    """Options for project indexing."""
    extract_metadata: bool = Field(
        default=True,
        description="Extract metadata (complexity, parameters, calls)"
    )
    generate_embeddings: bool = Field(
        default=True,
        description="Generate dual embeddings (TEXT + CODE domains)"
    )
    build_graph: bool = Field(
        default=True,
        description="Build dependency graph (nodes + edges)"
    )
    repository: str = Field(
        default="default",
        description="Repository name for organization"
    )
    respect_gitignore: bool = Field(
        default=True,
        description="Skip files matching .gitignore patterns"
    )


class IndexResult(MCPBaseResponse):
    """Result of project indexing operation."""
    repository: str = Field(
        description="Repository name"
    )
    indexed_files: int = Field(
        description="Number of files successfully indexed"
    )
    indexed_chunks: int = Field(
        description="Total code chunks created"
    )
    indexed_nodes: int = Field(
        description="Graph nodes created (functions, classes)"
    )
    indexed_edges: int = Field(
        description="Graph edges created (calls, imports)"
    )
    failed_files: int = Field(
        description="Number of files that failed to index"
    )
    processing_time_ms: float = Field(
        description="Total processing time in milliseconds"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of errors encountered"
    )


class FileIndexResult(MCPBaseResponse):
    """Result of single file indexing operation."""
    file_path: str = Field(
        description="Path to indexed file"
    )
    chunks_created: int = Field(
        description="Number of chunks created from this file"
    )
    processing_time_ms: float = Field(
        description="Processing time in milliseconds"
    )
    cache_hit: bool = Field(
        default=False,
        description="True if result was from cache"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if indexing failed"
    )


# ============================================================================
# Index Status Models
# ============================================================================


class IndexStatus(MCPBaseResponse):
    """Current indexing status for a repository."""
    repository: str = Field(
        description="Repository name"
    )
    status: Literal["not_indexed", "in_progress", "completed", "failed", "unknown"] = Field(
        description="Current indexing status"
    )
    total_files: int = Field(
        default=0,
        description="Total number of indexed files"
    )
    indexed_files: int = Field(
        default=0,
        description="Number of files successfully indexed (for in_progress)"
    )
    total_chunks: int = Field(
        default=0,
        description="Total code chunks in database"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages detected"
    )
    last_indexed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last successful indexing"
    )
    embedding_model: str = Field(
        default="nomic-embed-text-v1.5",
        description="Embedding model used"
    )
    cache_stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Cache statistics (L1/L2 hit rates)"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when indexing started (for in_progress)"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when indexing completed"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if status is 'failed'"
    )


# ============================================================================
# Progress Reporting Models
# ============================================================================


class ProgressUpdate(BaseModel):
    """Progress update during indexing."""
    current: int = Field(
        description="Current progress (files indexed)"
    )
    total: int = Field(
        description="Total files to index"
    )
    percentage: float = Field(
        description="Progress percentage (0.0 to 1.0)"
    )
    message: str = Field(
        description="Human-readable status message"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Current file being indexed"
    )


# ============================================================================
# Reindexing Models
# ============================================================================


class ReindexFileRequest(BaseModel):
    """Request to reindex a single file."""
    file_path: str = Field(
        description="Path to file to reindex"
    )
    repository: str = Field(
        default="default",
        description="Repository name"
    )
    force_cache_invalidation: bool = Field(
        default=True,
        description="Force cache invalidation before reindexing"
    )
