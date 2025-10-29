"""
Pydantic models for Configuration & Utilities (EPIC-23 Story 23.7).

Models for project switching, project listing, and language configuration.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from mnemo_mcp.base import MCPBaseResponse


# ============================================================================
# Project Switching Models (Sub-Story 23.7.1)
# ============================================================================


class SwitchProjectRequest(BaseModel):
    """Request to switch active project/repository."""

    repository: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Repository/project name to switch to"
    )
    confirm: bool = Field(
        default=False,
        description="Skip confirmation elicitation if True (for automation)"
    )


class SwitchProjectResponse(MCPBaseResponse):
    """Response from switch_project tool."""

    repository: str = Field(description="Active repository name")
    indexed_files: int = Field(description="Number of indexed files")
    total_chunks: int = Field(description="Total code chunks")
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages found"
    )
    last_indexed: Optional[str] = Field(
        default=None,
        description="Last indexing timestamp (ISO 8601)"
    )


# ============================================================================
# Project Listing Models (Sub-Story 23.7.1)
# ============================================================================


class ProjectListItem(BaseModel):
    """Information about a single indexed project (for listing)."""

    repository: str = Field(description="Repository/project name")
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


class ProjectsListResponse(BaseModel):
    """List of all indexed projects."""

    projects: List[ProjectListItem] = Field(description="List of projects")
    total: int = Field(description="Total number of projects")
    active_repository: Optional[str] = Field(
        default=None,
        description="Currently active repository name"
    )


# ============================================================================
# Language Configuration Models (Sub-Story 23.7.2)
# ============================================================================


class LanguageInfo(BaseModel):
    """Information about a supported programming language."""

    name: str = Field(description="Language display name (e.g., 'Python')")
    extensions: List[str] = Field(
        description="File extensions (e.g., ['.py', '.pyi'])"
    )
    tree_sitter_grammar: str = Field(
        description="Tree-sitter grammar name (e.g., 'tree-sitter-python')"
    )
    embedding_model: str = Field(
        default="nomic-embed-text-v1.5",
        description="Embedding model used for this language"
    )


class SupportedLanguagesResponse(BaseModel):
    """List of supported programming languages."""

    languages: List[LanguageInfo] = Field(description="List of languages")
    total: int = Field(description="Total number of supported languages")
