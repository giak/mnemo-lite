"""
Centralized cache key management for L2 Redis cache (EPIC-10 Story 10.2).

Provides consistent, collision-resistant key generation for different cache types.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional


def search_result_key(query: str, repository: Optional[str] = None, limit: int = 10) -> str:
    """
    Generate cache key for search results.

    Args:
        query: Search query text
        repository: Optional repository filter
        limit: Result limit

    Returns:
        Cache key in format: search:{md5_hash}

    Example:
        search:a3f2b9c1d4e5f6a7b8c9d0e1f2a3b4c5
    """
    filters = {
        "query": query,
        "repository": repository,
        "limit": limit,
    }
    filter_str = json.dumps(filters, sort_keys=True)
    key_hash = hashlib.md5(filter_str.encode()).hexdigest()
    return f"search:{key_hash}"


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
