"""
Code chunk models for EPIC-06 Phase 1.

Pydantic models for code intelligence features including AST-based chunking,
dual embeddings, and code metadata.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    """Type of code chunk based on AST structure."""

    # Python (Phase 1)
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"

    # JavaScript/TypeScript (Phase 1.5)
    ARROW_FUNCTION = "arrow_function"      # const foo = () => {}
    ASYNC_FUNCTION = "async_function"      # async function foo() {}
    GENERATOR = "generator"                 # function* foo() {}

    # TypeScript-specific
    INTERFACE = "interface"                 # interface User {}
    TYPE_ALIAS = "type_alias"              # type User = {...}
    ENUM = "enum"                          # enum Status {}

    # PHP-specific (Phase 1.6)
    TRAIT = "trait"                        # trait Loggable {}
    NAMESPACE = "namespace"                # namespace App\Models;

    # Vue-specific (Phase 1.6)
    VUE_COMPONENT = "vue_component"        # Complete Vue SFC
    VUE_TEMPLATE = "vue_template"          # <template> section
    VUE_SCRIPT = "vue_script"              # <script> section
    VUE_STYLE = "vue_style"                # <style> section

    # Fallback
    FALLBACK_FIXED = "fallback_fixed"  # Fallback when AST parsing fails


class EmbeddingDomain(str, Enum):
    """Domain for embedding generation."""

    TEXT = "text"  # General text embeddings (docstrings, comments)
    CODE = "code"  # Code-specialized embeddings
    HYBRID = "hybrid"  # Both text and code embeddings


class CodeChunk(BaseModel):
    """
    Basic code chunk model for AST parsing (Story 1).
    Used during chunking process before DB storage.
    """

    file_path: str = Field(..., description="Path to source file")
    language: str = Field(..., description="Programming language (python, javascript, etc.)")
    chunk_type: ChunkType = Field(..., description="Type of code chunk")
    name: Optional[str] = Field(None, description="Name of function/class/method")
    source_code: str = Field(..., description="Source code content")
    start_line: Optional[int] = Field(None, description="Start line number in file")
    end_line: Optional[int] = Field(None, description="End line number in file")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Code metadata (complexity, params, etc.)")
    repository: Optional[str] = Field(None, description="Repository name")
    commit_hash: Optional[str] = Field(None, description="Git commit hash")


class CodeChunkBase(CodeChunk):
    """Base model for code chunks with common fields (alias for backwards compatibility)."""
    pass

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "src/utils/calculator.py",
                "language": "python",
                "chunk_type": "function",
                "name": "calculate_total",
                "source_code": "def calculate_total(items):\n    return sum(item.price for item in items)",
                "start_line": 10,
                "end_line": 12,
                "metadata": {"complexity": {"cyclomatic": 2}, "parameters": ["items"]},
                "repository": "my-project",
                "commit_hash": "abc123"
            }
        }
    }


class CodeChunkCreate(CodeChunkBase):
    """Input model for creating a code chunk."""

    embedding_text: Optional[list[float]] = Field(None, description="Text embedding (768D)")
    embedding_code: Optional[list[float]] = Field(None, description="Code embedding (768D)")

    def validate_embedding_dimensions(self) -> None:
        """Validate that embeddings are 768D if present."""
        if self.embedding_text and len(self.embedding_text) != 768:
            raise ValueError(f"embedding_text must be 768D, got {len(self.embedding_text)}")
        if self.embedding_code and len(self.embedding_code) != 768:
            raise ValueError(f"embedding_code must be 768D, got {len(self.embedding_code)}")


class CodeChunkUpdate(BaseModel):
    """Model for updating a code chunk (partial updates)."""

    source_code: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    embedding_text: Optional[list[float]] = None
    embedding_code: Optional[list[float]] = None
    last_modified: Optional[datetime] = None


class CodeChunkModel(CodeChunkBase):
    """Output model for code chunk from database."""

    id: UUID = Field(..., description="Unique chunk ID")
    indexed_at: datetime = Field(..., description="Timestamp when chunk was indexed")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    node_id: Optional[UUID] = Field(None, description="Graph node ID (for dependency graph)")
    embedding_text: Optional[list[float]] = Field(None, description="Text embedding (768D)")
    embedding_code: Optional[list[float]] = Field(None, description="Code embedding (768D)")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "src/utils/calculator.py",
                "language": "python",
                "chunk_type": "function",
                "name": "calculate_total",
                "source_code": "def calculate_total(items):\n    return sum(item.price for item in items)",
                "start_line": 10,
                "end_line": 12,
                "metadata": {"complexity": {"cyclomatic": 2}},
                "indexed_at": "2025-10-16T10:30:00Z",
                "last_modified": None,
                "node_id": None,
                "repository": "my-project",
                "commit_hash": "abc123",
                "embedding_text": [0.1] * 768,
                "embedding_code": [0.2] * 768
            }
        }
    }

    @staticmethod
    def _format_embedding_for_db(embedding: Optional[list[float]]) -> Optional[str]:
        """Format embedding list to string for pgvector."""
        if embedding is None:
            return None
        return "[" + ",".join(map(str, embedding)) + "]"

    @classmethod
    def from_db_record(cls, record_data: Any) -> "CodeChunkModel":
        """Create CodeChunkModel from database record, parsing embeddings from strings."""
        import json
        import ast

        # Convert record to dict
        try:
            record_dict = dict(record_data)
        except (TypeError, ValueError) as e:
            raise TypeError(f"Expected dict-like record, got {type(record_data).__name__}") from e

        # Parse metadata if it's a string
        if isinstance(record_dict.get("metadata"), str):
            try:
                record_dict["metadata"] = json.loads(record_dict["metadata"])
            except json.JSONDecodeError:
                record_dict["metadata"] = {}

        # Parse embeddings from strings to lists
        for emb_field in ["embedding_text", "embedding_code"]:
            emb_value = record_dict.get(emb_field)
            if isinstance(emb_value, str):
                try:
                    parsed = ast.literal_eval(emb_value)
                    if isinstance(parsed, list) and all(isinstance(x, (int, float)) for x in parsed):
                        record_dict[emb_field] = parsed
                    else:
                        record_dict[emb_field] = None
                except (ValueError, SyntaxError):
                    record_dict[emb_field] = None
            elif hasattr(emb_value, 'tolist'):  # Handle numpy arrays
                record_dict[emb_field] = emb_value.tolist()

        return cls.model_validate(record_dict)


class CodeUnit(BaseModel):
    """
    Intermediate model for AST code units during parsing.
    Used by CodeChunkingService to identify and split code structures.
    """

    node_type: str = Field(..., description="AST node type (FunctionDef, ClassDef, etc.)")
    name: Optional[str] = Field(None, description="Name of function/class")
    source_code: str = Field(..., description="Source code of this unit")
    start_line: int = Field(..., description="Start line in source file")
    end_line: int = Field(..., description="End line in source file")
    size: int = Field(..., description="Size in characters")
    children: list["CodeUnit"] = Field(default_factory=list, description="Nested code units")

    model_config = {
        "json_schema_extra": {
            "example": {
                "node_type": "FunctionDef",
                "name": "calculate_total",
                "source_code": "def calculate_total(items):\n    return sum(item.price for item in items)",
                "start_line": 10,
                "end_line": 12,
                "size": 73,
                "children": []
            }
        }
    }


# Search request/response models

class CodeSearchRequest(BaseModel):
    """Request model for code search API."""

    query: str = Field(..., description="Search query (natural language or code snippet)")
    language: Optional[str] = Field(None, description="Filter by programming language")
    chunk_type: Optional[ChunkType] = Field(None, description="Filter by chunk type")
    repository: Optional[str] = Field(None, description="Filter by repository")
    embedding_domain: EmbeddingDomain = Field(
        EmbeddingDomain.CODE,
        description="Which embedding to use for search"
    )
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "function that calculates totals",
                "language": "python",
                "chunk_type": "function",
                "repository": "my-project",
                "embedding_domain": "code",
                "limit": 10
            }
        }
    }


class CodeSearchResult(BaseModel):
    """Search result with similarity score."""

    chunk: CodeChunkModel
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")

    model_config = {
        "json_schema_extra": {
            "example": {
                "chunk": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "calculate_total",
                    "file_path": "src/utils/calculator.py",
                    "language": "python",
                    "chunk_type": "function",
                    "source_code": "def calculate_total(items): ...",
                },
                "similarity": 0.92
            }
        }
    }


class CodeSearchResponse(BaseModel):
    """Response model for code search API."""

    results: list[CodeSearchResult]
    total: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Original query")
    embedding_domain: EmbeddingDomain

    model_config = {
        "json_schema_extra": {
            "example": {
                "results": [],
                "total": 5,
                "query": "function that calculates totals",
                "embedding_domain": "code"
            }
        }
    }
