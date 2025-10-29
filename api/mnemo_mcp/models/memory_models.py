"""
Memory models for MCP (Model Context Protocol) integration.

EPIC-23 Story 23.3: Persistent memory storage for LLM interactions.
Provides CRUD operations and semantic search for memories.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from enum import Enum


class MemoryType(str, Enum):
    """Memory classification types."""
    NOTE = "note"                    # General observations, thoughts
    DECISION = "decision"            # ADR-like decisions (why X was chosen)
    TASK = "task"                    # TODO items, action items
    REFERENCE = "reference"          # Documentation links, external resources
    CONVERSATION = "conversation"    # Dialogue context for multi-turn chats


class MemoryBase(BaseModel):
    """Base model for memory with common fields."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short memory title (1-200 chars)"
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Full memory content (plain text or markdown)"
    )
    memory_type: MemoryType = Field(
        default=MemoryType.NOTE,
        description="Memory classification: note, decision, task, reference, conversation"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="User-defined tags for filtering (e.g., ['python', 'async'])"
    )
    author: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional author attribution (e.g., 'Claude', 'User', 'System')"
    )
    project_id: Optional[uuid.UUID] = Field(
        None,
        description="Project UUID for scoping (null = global memory)"
    )
    related_chunks: List[uuid.UUID] = Field(
        default_factory=list,
        description="Array of code_chunks.id for linking memories to code"
    )
    resource_links: List[Dict[str, str]] = Field(
        default_factory=list,
        description="MCP 2025-06-18 resource links: [{'uri': '...', 'type': '...'}]"
    )

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate tags: trim whitespace, remove duplicates, lowercase."""
        if not v:
            return []
        # Trim, lowercase, remove empty strings
        cleaned = [tag.strip().lower() for tag in v if tag.strip()]
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in cleaned:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        return unique_tags

    @field_validator('resource_links')
    @classmethod
    def validate_resource_links(cls, v: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate resource links have required 'uri' field."""
        if not v:
            return []
        for link in v:
            if 'uri' not in link:
                raise ValueError("Resource link must contain 'uri' field")
        return v


class MemoryCreate(MemoryBase):
    """Model for creating a new memory."""
    pass


class MemoryUpdate(BaseModel):
    """Model for updating an existing memory (partial update).

    All fields are optional. Only provided fields will be updated.
    """

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Update memory title"
    )
    content: Optional[str] = Field(
        None,
        min_length=1,
        description="Update memory content"
    )
    memory_type: Optional[MemoryType] = Field(
        None,
        description="Update memory classification"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Update tags (replaces existing tags)"
    )
    author: Optional[str] = Field(
        None,
        max_length=100,
        description="Update author attribution"
    )
    related_chunks: Optional[List[uuid.UUID]] = Field(
        None,
        description="Update related code chunks (replaces existing)"
    )
    resource_links: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Update resource links (replaces existing)"
    )

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags if provided."""
        if v is None:
            return None
        # Same validation as MemoryBase
        cleaned = [tag.strip().lower() for tag in v if tag.strip()]
        seen = set()
        unique_tags = []
        for tag in cleaned:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        return unique_tags


class Memory(MemoryBase):
    """Complete memory model with all fields (from database)."""

    id: uuid.UUID = Field(
        ...,
        description="Unique memory identifier (UUID v4)"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp (UTC)"
    )
    embedding: Optional[List[float]] = Field(
        None,
        description="Semantic embedding vector (768D)"
    )
    embedding_model: Optional[str] = Field(
        None,
        description="Model name used for embedding (e.g., 'nomic-embed-text-v1.5')"
    )
    deleted_at: Optional[datetime] = Field(
        None,
        description="Soft delete timestamp (null = active)"
    )
    similarity_score: Optional[float] = Field(
        None,
        description="Similarity score (only present in search results)"
    )


class MemoryResponse(BaseModel):
    """Response for write_memory and update_memory tools.

    Lightweight response (doesn't include full embedding).
    """

    id: uuid.UUID = Field(
        ...,
        description="Memory UUID"
    )
    title: str = Field(
        ...,
        description="Memory title"
    )
    memory_type: MemoryType = Field(
        ...,
        description="Memory classification"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp"
    )
    embedding_generated: bool = Field(
        ...,
        description="Whether embedding was successfully generated"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Memory tags for categorization and search"
    )
    author: Optional[str] = Field(
        None,
        description="Memory author/creator"
    )
    content_preview: Optional[str] = Field(
        None,
        description="First 200 characters of content"
    )


class PaginationMetadata(BaseModel):
    """Pagination metadata for list/search responses."""

    limit: int = Field(
        ...,
        description="Results per page"
    )
    offset: int = Field(
        ...,
        description="Current offset"
    )
    total: int = Field(
        ...,
        description="Total results available"
    )
    has_more: bool = Field(
        ...,
        description="Whether more results are available"
    )


class MemoryListResponse(BaseModel):
    """Response for memories://list resource."""

    memories: List[Memory] = Field(
        ...,
        description="List of memories (embeddings excluded for bandwidth)"
    )
    pagination: PaginationMetadata = Field(
        ...,
        description="Pagination metadata"
    )


class MemorySearchResponse(BaseModel):
    """Response for memories://search resource."""

    query: str = Field(
        ...,
        description="Search query text"
    )
    memories: List[Memory] = Field(
        ...,
        description="Ranked memories with similarity scores"
    )
    pagination: PaginationMetadata = Field(
        ...,
        description="Pagination metadata"
    )
    metadata: Dict[str, Any] = Field(
        ...,
        description="Search metadata (threshold, embedding_model, etc.)"
    )


class DeleteMemoryResponse(BaseModel):
    """Response for delete_memory tool."""

    id: uuid.UUID = Field(
        ...,
        description="Deleted memory UUID"
    )
    deleted_at: datetime = Field(
        ...,
        description="Deletion timestamp"
    )
    permanent: bool = Field(
        ...,
        description="Whether deletion is permanent (hard delete)"
    )
    can_restore: bool = Field(
        ...,
        description="Whether memory can be restored (false for permanent delete)"
    )


class MemoryFilters(BaseModel):
    """Filters for memory list/search queries."""

    project_id: Optional[uuid.UUID] = Field(
        None,
        description="Filter by project UUID"
    )
    memory_type: Optional[MemoryType] = Field(
        None,
        description="Filter by memory type"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Filter by tags (AND logic - memory must have all tags)"
    )
    author: Optional[str] = Field(
        None,
        description="Filter by author"
    )
    include_deleted: bool = Field(
        False,
        description="Include soft-deleted memories (default: false)"
    )
    created_after: Optional[datetime] = Field(
        None,
        description="Filter memories created after this timestamp"
    )
    created_before: Optional[datetime] = Field(
        None,
        description="Filter memories created before this timestamp"
    )

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate tags: trim whitespace, lowercase, remove duplicates.

        Must match MemoryBase.validate_tags() to ensure consistent filtering.
        """
        if not v:
            return []
        # Trim, lowercase, remove empty strings
        cleaned = [tag.strip().lower() for tag in v if tag.strip()]
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in cleaned:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        return unique_tags
