"""
Centralized timeout configuration for all operations.

Timeouts are defined in seconds. Values are conservative (high) initially,
and should be tuned based on production metrics.

EPIC-12 Story 12.1: Timeout-Based Execution
"""

from typing import Dict

from api.core.settings import get_settings


# Default timeouts (seconds)
# All values can be overridden via environment variables (now centralized in AppSettings)
TIMEOUTS: Dict[str, float] = {}


def _load_timeouts() -> Dict[str, float]:
    """Load timeouts from AppSettings (centralized config)."""
    s = get_settings()
    return {
        "tree_sitter_parse": s.TIMEOUT_TREE_SITTER,
        "embedding_generation_single": s.TIMEOUT_EMBEDDING_SINGLE,
        "embedding_generation_batch": s.TIMEOUT_EMBEDDING_BATCH,
        "graph_construction": s.TIMEOUT_GRAPH_CONSTRUCTION,
        "graph_traversal": s.TIMEOUT_GRAPH_TRAVERSAL,
        "vector_search": s.TIMEOUT_VECTOR_SEARCH,
        "lexical_search": s.TIMEOUT_LEXICAL_SEARCH,
        "hybrid_search": s.TIMEOUT_HYBRID_SEARCH,
        "cache_get": s.TIMEOUT_CACHE_GET,
        "cache_put": s.TIMEOUT_CACHE_PUT,
        "database_query": s.TIMEOUT_DATABASE_QUERY,
        "database_transaction": s.TIMEOUT_DATABASE_TRANSACTION,
        "index_file": s.TIMEOUT_INDEX_FILE,
    }


TIMEOUTS = _load_timeouts()


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
    Reset all timeouts to default values from AppSettings.

    Useful for testing or recovering from misconfiguration.
    """
    global TIMEOUTS
    TIMEOUTS = _load_timeouts()