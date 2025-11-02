"""
Centralized timeout configuration for all operations.

Timeouts are defined in seconds. Values are conservative (high) initially,
and should be tuned based on production metrics.

EPIC-12 Story 12.1: Timeout-Based Execution
"""

import os
from typing import Dict

# Default timeouts (seconds)
# All values can be overridden via environment variables
TIMEOUTS: Dict[str, float] = {
    # Code parsing (CPU-bound)
    "tree_sitter_parse": float(os.getenv("TIMEOUT_TREE_SITTER", "5.0")),

    # Embedding generation (CPU-bound, batched)
    # EPIC-26: Increased from 10s to 30s for large TypeScript/JavaScript files
    "embedding_generation_single": float(os.getenv("TIMEOUT_EMBEDDING_SINGLE", "30.0")),
    "embedding_generation_batch": float(os.getenv("TIMEOUT_EMBEDDING_BATCH", "60.0")),

    # Graph operations
    "graph_construction": float(os.getenv("TIMEOUT_GRAPH_CONSTRUCTION", "10.0")),
    "graph_traversal": float(os.getenv("TIMEOUT_GRAPH_TRAVERSAL", "5.0")),

    # Search operations
    "vector_search": float(os.getenv("TIMEOUT_VECTOR_SEARCH", "5.0")),
    "lexical_search": float(os.getenv("TIMEOUT_LEXICAL_SEARCH", "3.0")),
    "hybrid_search": float(os.getenv("TIMEOUT_HYBRID_SEARCH", "10.0")),

    # Cache operations
    "cache_get": float(os.getenv("TIMEOUT_CACHE_GET", "1.0")),
    "cache_put": float(os.getenv("TIMEOUT_CACHE_PUT", "2.0")),

    # Database operations
    "database_query": float(os.getenv("TIMEOUT_DATABASE_QUERY", "10.0")),
    "database_transaction": float(os.getenv("TIMEOUT_DATABASE_TRANSACTION", "30.0")),

    # High-level operations (cumulative timeouts)
    "index_file": float(os.getenv("TIMEOUT_INDEX_FILE", "60.0")),  # Sum of sub-operations + buffer
}


def get_timeout(operation: str, default: float = 30.0) -> float:
    """
    Get timeout for operation with fallback.

    Args:
        operation: Operation name (key in TIMEOUTS dict)
        default: Default timeout if operation not found (default: 30s)

    Returns:
        Timeout in seconds

    Example:
        >>> timeout = get_timeout("tree_sitter_parse")  # 5.0
        >>> timeout = get_timeout("unknown_op")  # 30.0 (default)
    """
    return TIMEOUTS.get(operation, default)


def set_timeout(operation: str, timeout: float) -> None:
    """
    Update timeout for operation at runtime.

    Useful for dynamic tuning based on repository size or hardware.

    Args:
        operation: Operation name
        timeout: New timeout in seconds

    Example:
        >>> # Increase timeout for large repositories
        >>> set_timeout("index_file", 120.0)
    """
    if timeout <= 0:
        raise ValueError(f"Timeout must be positive, got {timeout}")

    TIMEOUTS[operation] = timeout


def get_all_timeouts() -> Dict[str, float]:
    """
    Get all configured timeouts.

    Useful for debugging, monitoring, or displaying configuration.

    Returns:
        Copy of TIMEOUTS dict

    Example:
        >>> timeouts = get_all_timeouts()
        >>> print(f"Tree-sitter timeout: {timeouts['tree_sitter_parse']}s")
    """
    return TIMEOUTS.copy()


def reset_to_defaults() -> None:
    """
    Reset all timeouts to default values.

    Useful for testing or recovering from misconfiguration.
    """
    global TIMEOUTS

    TIMEOUTS = {
        "tree_sitter_parse": 5.0,
        "embedding_generation_single": 30.0,  # EPIC-26: Increased for large files
        "embedding_generation_batch": 60.0,   # EPIC-26: Increased for large batches
        "graph_construction": 10.0,
        "graph_traversal": 5.0,
        "vector_search": 5.0,
        "lexical_search": 3.0,
        "hybrid_search": 10.0,
        "cache_get": 1.0,
        "cache_put": 2.0,
        "database_query": 10.0,
        "database_transaction": 30.0,
        "index_file": 60.0,
    }
