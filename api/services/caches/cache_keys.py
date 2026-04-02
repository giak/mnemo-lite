"""
Centralized cache key management for L2 Redis cache (EPIC-10 Story 10.2).

Provides consistent, collision-resistant key generation for different cache types.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional


def search_result_key(
    query: str,
    repository: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    filters: Optional[Dict[str, Any]] = None,
    enable_lexical: bool = True,
    enable_vector: bool = True,
    lexical_weight: float = 0.5,
    vector_weight: float = 0.5,
) -> str:
    """
    Generate cache key for search results — includes ALL parameters.

    EPIC-32 Story 32.1: Fixed to include filters, offset, weights, and
    enable flags to prevent returning wrong cached results.

    Args:
        query: Search query text
        repository: Optional repository filter
        limit: Result limit
        offset: Pagination offset
        filters: Optional filter dict (language, chunk_type, file_path, etc.)
        enable_lexical: Whether lexical search is enabled
        enable_vector: Whether vector search is enabled
        lexical_weight: Weight for lexical results in RRF
        vector_weight: Weight for vector results in RRF

    Returns:
        Cache key in format: search:v2:{sha256_hash}
    """
    params = {
        "q": query,
        "r": repository,
        "l": limit,
        "o": offset,
        "f": filters or {},
        "el": enable_lexical,
        "ev": enable_vector,
        "lw": lexical_weight,
        "vw": vector_weight,
    }
    param_str = json.dumps(params, sort_keys=True)
    key_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
    return f"search:v2:{key_hash}"


def graph_traversal_key(
    node_id: str,
    max_hops: int = 3,
    relation_types: Optional[List[str]] = None,
) -> str:
    """
    Generate cache key for graph traversal results.

    Args:
        node_id: Starting node UUID
        max_hops: Maximum traversal depth
        relation_types: List of relation types to follow (e.g., ["calls", "imports"])

    Returns:
        Cache key in format: graph:{node_id}:hops{N}:{relations}

    Example:
        graph:123e4567-e89b:hops3:calls,imports
    """
    relations = ",".join(sorted(relation_types)) if relation_types else "all"
    # Truncate node_id for readability (first 12 chars)
    node_short = node_id[:12] if len(node_id) > 12 else node_id
    return f"graph:{node_short}:hops{max_hops}:{relations}"


def embedding_key(text_hash: str) -> str:
    """
    Generate cache key for embedding vectors.

    Args:
        text_hash: MD5 hash of text content

    Returns:
        Cache key in format: embedding:{hash}

    Example:
        embedding:a3f2b9c1d4e5f6a7b8c9d0e1f2a3b4c5
    """
    return f"embedding:{text_hash}"


def repository_metadata_key(repo_name: str) -> str:
    """
    Generate cache key for repository metadata.

    Args:
        repo_name: Repository name

    Returns:
        Cache key in format: repo:meta:{repo_name}

    Example:
        repo:meta:my-project
    """
    return f"repo:meta:{repo_name}"


def code_chunk_key(file_path: str, content_hash: str) -> str:
    """
    Generate cache key for code chunks.

    Args:
        file_path: File path
        content_hash: MD5 hash of file content

    Returns:
        Cache key in format: chunks:{file_path}:{hash}

    Example:
        chunks:src/main.py:a3f2b9c1d4e5f6a7
    """
    # Use only last 16 chars of hash for brevity
    hash_short = content_hash[-16:]
    return f"chunks:{file_path}:{hash_short}"


def repository_pattern(repo_name: str) -> str:
    """
    Generate pattern to match all keys for a repository.

    Used for cache invalidation when repository is re-indexed.

    Args:
        repo_name: Repository name

    Returns:
        Redis pattern for all repository keys

    Example:
        *:my-project:* matches search, graph, and chunk keys for my-project
    """
    return f"*:{repo_name}:*"
