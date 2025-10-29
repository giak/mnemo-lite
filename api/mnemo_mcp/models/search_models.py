"""
Code Search Pydantic Models for MCP.

Based on HybridSearchService dataclasses but using Pydantic for:
- JSON schema generation (MCP Inspector)
- Validation
- Serialization/deserialization

Story 23.2.1 - Sub-story: Pydantic models for code search tool.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CodeSearchFilters(BaseModel):
    """
    Search filters for code search.

    Allows filtering results by language, chunk type, repository, file path,
    and LSP-enhanced filters (return_type, param_type from EPIC-14).
    """

    language: Optional[str] = Field(
        None,
        description="Filter by programming language (e.g., 'python', 'javascript', 'typescript')",
        examples=["python", "javascript", "go"]
    )

    chunk_type: Optional[str] = Field(
        None,
        description="Filter by chunk type (e.g., 'function', 'class', 'method')",
        examples=["function", "class", "method", "variable"]
    )

    repository: Optional[str] = Field(
        None,
        description="Filter by repository name",
        examples=["mnemolite", "serena"]
    )

    file_path: Optional[str] = Field(
        None,
        description="Filter by file path (supports wildcards)",
        examples=["api/services/*.py", "src/serena/**/*.ts"]
    )

    return_type: Optional[str] = Field(
        None,
        description="Filter by LSP return type annotation (EPIC-14)",
        examples=["str", "int", "List[str]", "Optional[Dict]"]
    )

    param_type: Optional[str] = Field(
        None,
        description="Filter by LSP parameter type annotation (EPIC-14)",
        examples=["str", "int", "Context"]
    )


class CodeSearchQuery(BaseModel):
    """
    Input parameters for code search tool.

    Supports both simple keyword search and advanced semantic search with
    filters and pagination.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query (keywords or natural language question)",
        examples=[
            "authentication function",
            "how to connect to database",
            "redis cache implementation"
        ]
    )

    # Pagination
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
    )

    offset: int = Field(
        0,
        ge=0,
        le=1000,
        description="Offset for pagination (0-1000, use cursor for deep pagination)",
    )

    # Filters
    filters: Optional[CodeSearchFilters] = Field(
        None,
        description="Optional filters to narrow search results"
    )

    # Search configuration
    enable_lexical: bool = Field(
        True,
        description="Enable lexical (keyword-based) search using pg_trgm"
    )

    enable_vector: bool = Field(
        True,
        description="Enable vector (semantic) search using embeddings"
    )

    lexical_weight: float = Field(
        0.4,
        ge=0.0,
        le=1.0,
        description="Weight for lexical search in RRF fusion (0.0-1.0)"
    )

    vector_weight: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        description="Weight for vector search in RRF fusion (0.0-1.0)"
    )


class CodeSearchResult(BaseModel):
    """
    Individual search result from hybrid code search.

    Contains fused RRF scores, source code, metadata, and optional
    LSP-enhanced information.
    """

    chunk_id: str = Field(
        ...,
        description="Unique chunk identifier (UUID)"
    )

    rrf_score: float = Field(
        ...,
        ge=0.0,
        description="RRF (Reciprocal Rank Fusion) score combining lexical and vector results"
    )

    rank: int = Field(
        ...,
        ge=1,
        description="Final rank in search results (1-indexed)"
    )

    # Code content
    source_code: str = Field(
        ...,
        description="Source code of the chunk"
    )

    name: str = Field(
        ...,
        description="Symbol name (function, class, method, etc.)"
    )

    name_path: Optional[str] = Field(
        None,
        description="Hierarchical qualified name (e.g., 'MyClass.my_method') from EPIC-11"
    )

    # File metadata
    language: str = Field(
        ...,
        description="Programming language"
    )

    chunk_type: str = Field(
        ...,
        description="Type of code chunk (function, class, method, etc.)"
    )

    file_path: str = Field(
        ...,
        description="Relative file path from repository root"
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (repository, line numbers, LSP info, etc.)"
    )

    # Score breakdown
    lexical_score: Optional[float] = Field(
        None,
        ge=0.0,
        description="Lexical (trigram) similarity score if lexical search was enabled"
    )

    vector_similarity: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Vector cosine similarity if vector search was enabled"
    )

    vector_distance: Optional[float] = Field(
        None,
        ge=0.0,
        description="Vector L2 distance if vector search was enabled"
    )

    contribution: Dict[str, float] = Field(
        default_factory=dict,
        description="RRF contribution breakdown (lexical, vector)"
    )

    # Graph expansion (future)
    related_nodes: List[str] = Field(
        default_factory=list,
        description="Related chunk IDs from graph expansion (dependency traversal)"
    )


class CodeSearchMetadata(BaseModel):
    """
    Metadata about search execution.

    Contains timing information, result counts, and search configuration.
    """

    total_results: int = Field(
        ...,
        ge=0,
        description="Total number of results found"
    )

    lexical_count: int = Field(
        ...,
        ge=0,
        description="Number of results from lexical search"
    )

    vector_count: int = Field(
        ...,
        ge=0,
        description="Number of results from vector search"
    )

    unique_after_fusion: int = Field(
        ...,
        ge=0,
        description="Number of unique results after RRF fusion"
    )

    # Search configuration
    lexical_enabled: bool = Field(
        ...,
        description="Whether lexical search was enabled"
    )

    vector_enabled: bool = Field(
        ...,
        description="Whether vector search was enabled"
    )

    graph_expansion_enabled: bool = Field(
        False,
        description="Whether graph expansion was enabled (future feature)"
    )

    lexical_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Lexical weight used in RRF fusion"
    )

    vector_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Vector weight used in RRF fusion"
    )

    # Timing breakdown
    execution_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Total execution time in milliseconds"
    )

    lexical_time_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="Lexical search execution time in milliseconds"
    )

    vector_time_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="Vector search execution time in milliseconds"
    )

    fusion_time_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="RRF fusion execution time in milliseconds"
    )

    graph_time_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="Graph expansion time in milliseconds (if enabled)"
    )

    # Cache info
    cache_hit: bool = Field(
        False,
        description="Whether result was served from Redis L2 cache"
    )


class CodeSearchResponse(BaseModel):
    """
    Complete response from code search tool.

    Contains search results, metadata, and pagination info.
    """

    results: List[CodeSearchResult] = Field(
        ...,
        description="List of search results ordered by RRF score (descending)"
    )

    metadata: CodeSearchMetadata = Field(
        ...,
        description="Search execution metadata"
    )

    # Pagination
    total: int = Field(
        ...,
        ge=0,
        description="Total number of results available (before pagination)"
    )

    limit: int = Field(
        ...,
        ge=1,
        description="Limit used for this query"
    )

    offset: int = Field(
        ...,
        ge=0,
        description="Offset used for this query"
    )

    has_next: bool = Field(
        ...,
        description="Whether more results are available"
    )

    next_offset: Optional[int] = Field(
        None,
        description="Offset for next page (if has_next is True)"
    )

    # Optional error info
    error: Optional[str] = Field(
        None,
        description="Error message if search failed (graceful degradation)"
    )
