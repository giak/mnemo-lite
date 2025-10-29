"""
MCP Shared Pydantic Models

Provides shared data models used across multiple MCP components.
All models use Pydantic for type safety and validation (MCP 2025-06-18 requirement).
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================================================
# Common Models
# ============================================================================

class ResourceLink(BaseModel):
    """
    MCP 2025-06-18 Resource Link.

    Links between related resources for navigation.
    Example: Search result links to code graph, memory links to related chunks.
    """
    uri: str = Field(description="Resource URI (e.g., 'graph://nodes/uuid')")
    title: str = Field(description="Human-readable link title")
    description: Optional[str] = Field(
        default=None,
        description="Optional description of the linked resource"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "uri": "graph://nodes/550e8400-e29b-41d4-a716-446655440000",
                "title": "View code graph",
                "description": "Navigate function calls and imports"
            }
        }


class CacheMetadata(BaseModel):
    """Metadata about cache usage for a response."""
    cache_hit: bool = False
    cache_key: Optional[str] = None
    ttl_seconds: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "cache_hit": True,
                "cache_key": "search:a1b2c3d4",
                "ttl_seconds": 300
            }
        }


# ============================================================================
# Code Search Models
# ============================================================================

class CodeChunk(BaseModel):
    """
    A single code chunk from search results.

    Represents a semantic code unit (function, class, method, etc.)
    extracted from a source file.
    """
    id: UUID = Field(description="Unique chunk identifier")
    file_path: str = Field(description="Relative file path")
    start_line: int = Field(description="Start line number (1-indexed)")
    end_line: int = Field(description="End line number (inclusive)")
    content: str = Field(description="Chunk source code content")
    language: str = Field(description="Programming language (python, javascript, etc.)")
    chunk_type: str = Field(
        description="Chunk type (function, class, method, import, etc.)"
    )
    qualified_name: Optional[str] = Field(
        default=None,
        description="Fully qualified name (e.g., 'api.services.search.HybridSearch')"
    )
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Search relevance score (0.0 to 1.0)"
    )
    indexed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when chunk was indexed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "file_path": "api/services/search.py",
                "start_line": 45,
                "end_line": 67,
                "content": "async def hybrid_search(self, query: str):...",
                "language": "python",
                "chunk_type": "function",
                "qualified_name": "api.services.search.hybrid_search",
                "score": 0.89
            }
        }


# ============================================================================
# Memory Models
# ============================================================================

class Memory(BaseModel):
    """
    A persistent memory stored in MnemoLite.

    Memories are project-specific notes, decisions, bug reports, or features
    that persist across sessions and can be searched semantically.
    """
    id: UUID = Field(description="Unique memory identifier")
    name: str = Field(description="Memory name (unique per project)")
    content: str = Field(description="Memory content (supports markdown)")
    memory_type: Literal["note", "decision", "bug", "feature"] = Field(
        default="note",
        description="Memory type for categorization"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for organization and filtering"
    )
    author: Optional[str] = Field(
        default=None,
        description="Author username or identifier"
    )
    project_id: Optional[UUID] = Field(
        default=None,
        description="Associated project (for multi-project support)"
    )
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    resource_links: List[ResourceLink] = Field(
        default_factory=list,
        description="MCP 2025-06-18 resource links"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (JSONB)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "auth-refactor-decision",
                "content": "## Decision: Migrate to JWT\n\nRationale: Better scalability...",
                "memory_type": "decision",
                "tags": ["auth", "architecture"],
                "author": "developer",
                "project_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T10:00:00Z"
            }
        }


# ============================================================================
# Code Graph Models
# ============================================================================

class CodeGraphNode(BaseModel):
    """A node in the code graph (function, class, etc.)."""
    id: UUID = Field(description="Node ID (chunk_id)")
    chunk_id: UUID = Field(description="Associated code chunk ID")
    name: str = Field(description="Node name (function/class name)")
    qualified_name: Optional[str] = Field(
        default=None,
        description="Fully qualified name"
    )
    chunk_type: str = Field(description="Node type (function, class, method, etc.)")
    file_path: str = Field(description="Source file path")
    language: str = Field(description="Programming language")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional node metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "authenticate_user",
                "qualified_name": "api.auth.authenticate_user",
                "chunk_type": "function",
                "file_path": "api/auth.py",
                "language": "python"
            }
        }


class CodeGraphEdge(BaseModel):
    """An edge in the code graph (call, import, inheritance, etc.)."""
    source_id: UUID = Field(description="Source node ID")
    target_id: UUID = Field(description="Target node ID")
    relation_type: Literal["calls", "imports", "inherits", "uses", "defines", "references"] = Field(
        description="Relationship type"
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Edge weight (for importance/frequency)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional edge metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "target_id": "660e8400-e29b-41d4-a716-446655440001",
                "relation_type": "calls",
                "weight": 1.0
            }
        }


# ============================================================================
# Project Models
# ============================================================================

class ProjectInfo(BaseModel):
    """Information about an indexed project."""
    id: UUID = Field(description="Project identifier")
    name: str = Field(description="Project name")
    indexed_files: int = Field(description="Number of indexed files")
    total_chunks: int = Field(description="Total code chunks")
    last_indexed: Optional[datetime] = Field(
        default=None,
        description="Last indexing timestamp"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages found"
    )
    is_active: bool = Field(
        default=False,
        description="Whether this is the currently active project"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "mnemolite",
                "indexed_files": 234,
                "total_chunks": 1567,
                "last_indexed": "2025-01-15T10:00:00Z",
                "languages": ["python", "javascript"],
                "is_active": True
            }
        }


# ============================================================================
# Analytics Models
# ============================================================================

class CacheStats(BaseModel):
    """Redis cache statistics."""
    total_keys: int = Field(description="Total cached keys")
    memory_usage_mb: float = Field(description="Memory usage in megabytes")
    hit_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Cache hit rate (0.0 to 1.0)"
    )
    total_hits: int = Field(description="Total cache hits")
    total_misses: int = Field(description="Total cache misses")

    class Config:
        json_schema_extra = {
            "example": {
                "total_keys": 1234,
                "memory_usage_mb": 45.6,
                "hit_rate": 0.82,
                "total_hits": 5678,
                "total_misses": 1234
            }
        }
