"""
Search Metrics Logging - EPIC-18

Helper functions pour logger les métriques de recherche de manière structurée.

Principe: KISS - Logs structurés simples pour monitoring sans Prometheus/Grafana.
"""

import structlog
from typing import Optional, Dict, Any

logger = structlog.get_logger(__name__)


def log_search_metrics(
    query: str,
    method: str,
    results_count: int,
    execution_time_ms: float,
    lexical_count: int = 0,
    vector_count: int = 0,
    repository: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """
    Log search metrics de manière structurée.

    Usage:
        log_search_metrics(
            query="validate email",
            method="hybrid",
            results_count=5,
            execution_time_ms=45.2,
            lexical_count=3,
            vector_count=4
        )

    Analyse simple avec grep/jq:
        # Searches per hour
        docker logs mnemo-api --since 1h | grep "search_completed" | wc -l

        # Average latency
        docker logs mnemo-api --since 1h | grep "search_completed" | \
          jq '.execution_time_ms' | awk '{sum+=$1; n++} END {print sum/n}'

        # Slow searches (>200ms)
        docker logs mnemo-api --since 1h | grep "search_completed" | \
          jq 'select(.execution_time_ms > 200)'

        # Vector search usage rate
        docker logs mnemo-api --since 1h | grep "search_completed" | \
          jq 'select(.vector_count > 0)' | wc -l

    Args:
        query: Search query text
        method: Search method ("hybrid", "lexical", "vector")
        results_count: Number of results returned
        execution_time_ms: Total execution time in milliseconds
        lexical_count: Number of results from lexical search
        vector_count: Number of results from vector search
        repository: Optional repository filter
        filters: Optional additional filters applied
        error: Optional error message if search failed
    """
    # Categorize latency for easy filtering
    if execution_time_ms < 50:
        latency_bucket = "fast"
    elif execution_time_ms < 200:
        latency_bucket = "medium"
    else:
        latency_bucket = "slow"

    # Log level based on error
    log_level = "error" if error else "info"

    # Prepare log data
    log_data = {
        "event": "search_completed",
        "method": method,
        "query_length": len(query),
        "query_preview": query[:50] if len(query) > 50 else query,
        "results_count": results_count,
        "lexical_count": lexical_count,
        "vector_count": vector_count,
        "execution_time_ms": round(execution_time_ms, 2),
        "latency_bucket": latency_bucket,
    }

    # Add optional fields
    if repository:
        log_data["repository"] = repository

    if filters:
        log_data["filters"] = filters

    if error:
        log_data["error"] = error
        log_data["success"] = False
    else:
        log_data["success"] = True

    # Log
    if log_level == "error":
        logger.error(**log_data)
    else:
        logger.info(**log_data)


def log_embedding_generation_metrics(
    text: str,
    domain: str,
    generation_time_ms: float,
    dimension: int = 768,
    cache_hit: bool = False,
    error: Optional[str] = None
):
    """
    Log embedding generation metrics.

    Usage:
        log_embedding_generation_metrics(
            text="validate email",
            domain="TEXT",
            generation_time_ms=15.3,
            cache_hit=False
        )

    Analyse:
        # Cache hit rate
        docker logs mnemo-api --since 1h | grep "embedding_generated" | \
          jq -s 'map(select(.cache_hit)) | length / (length + 1) * 100'

        # Average generation time
        docker logs mnemo-api --since 1h | grep "embedding_generated" | \
          jq '.generation_time_ms' | awk '{sum+=$1} END {print sum/NR}'

    Args:
        text: Input text for embedding
        domain: Embedding domain ("TEXT", "CODE", "HYBRID")
        generation_time_ms: Generation time in milliseconds
        dimension: Embedding dimension (default 768)
        cache_hit: Whether embedding was retrieved from cache
        error: Optional error message
    """
    # Categorize speed
    if generation_time_ms < 10:
        speed_bucket = "fast"
    elif generation_time_ms < 30:
        speed_bucket = "medium"
    else:
        speed_bucket = "slow"

    log_data = {
        "event": "embedding_generated",
        "domain": domain,
        "text_length": len(text),
        "text_preview": text[:50] if len(text) > 50 else text,
        "generation_time_ms": round(generation_time_ms, 2),
        "speed_bucket": speed_bucket,
        "dimension": dimension,
        "cache_hit": cache_hit,
        "success": error is None
    }

    if error:
        log_data["error"] = error
        logger.error(**log_data)
    else:
        logger.info(**log_data)


def log_indexing_metrics(
    repository: str,
    files_count: int,
    chunks_created: int,
    indexing_time_ms: float,
    embeddings_generated: bool = True,
    metadata_extracted: bool = True,
    error: Optional[str] = None
):
    """
    Log indexing metrics.

    Usage:
        log_indexing_metrics(
            repository="my-repo",
            files_count=10,
            chunks_created=47,
            indexing_time_ms=1234.5,
            embeddings_generated=True
        )

    Analyse:
        # Indexing throughput (chunks/second)
        docker logs mnemo-api --since 24h | grep "indexing_completed" | \
          jq '.chunks_created / (.indexing_time_ms / 1000)' | awk '{sum+=$1} END {print sum/NR}'

        # Failed indexations
        docker logs mnemo-api --since 24h | grep "indexing_completed" | \
          jq 'select(.success == false)'

    Args:
        repository: Repository name
        files_count: Number of files indexed
        chunks_created: Number of code chunks created
        indexing_time_ms: Total indexing time in milliseconds
        embeddings_generated: Whether embeddings were generated
        metadata_extracted: Whether metadata was extracted
        error: Optional error message
    """
    # Calculate throughput
    if indexing_time_ms > 0:
        chunks_per_second = chunks_created / (indexing_time_ms / 1000)
    else:
        chunks_per_second = 0

    log_data = {
        "event": "indexing_completed",
        "repository": repository,
        "files_count": files_count,
        "chunks_created": chunks_created,
        "indexing_time_ms": round(indexing_time_ms, 2),
        "chunks_per_second": round(chunks_per_second, 2),
        "embeddings_generated": embeddings_generated,
        "metadata_extracted": metadata_extracted,
        "success": error is None
    }

    if error:
        log_data["error"] = error
        logger.error(**log_data)
    else:
        logger.info(**log_data)


def log_cache_metrics(
    cache_type: str,
    operation: str,
    hit: bool,
    key_preview: Optional[str] = None,
    ttl_seconds: Optional[int] = None
):
    """
    Log cache operations (hit/miss/eviction).

    Usage:
        log_cache_metrics(
            cache_type="embedding",
            operation="get",
            hit=True,
            key_preview="query:validate..."
        )

    Analyse:
        # Cache hit rate by type
        docker logs mnemo-api --since 1h | grep "cache_operation" | \
          jq -s 'group_by(.cache_type) | map({type: .[0].cache_type, hit_rate: (map(select(.hit)) | length) / length * 100})'

    Args:
        cache_type: Type of cache ("embedding", "search", "chunk")
        operation: Operation type ("get", "set", "evict")
        hit: Whether it was a cache hit (for 'get' operations)
        key_preview: Optional preview of cache key
        ttl_seconds: Optional TTL for 'set' operations
    """
    log_data = {
        "event": "cache_operation",
        "cache_type": cache_type,
        "operation": operation,
        "hit": hit if operation == "get" else None
    }

    if key_preview:
        log_data["key_preview"] = key_preview

    if ttl_seconds is not None:
        log_data["ttl_seconds"] = ttl_seconds

    logger.debug(**log_data)


# ==============================================================================
# Examples & Cheat Sheet
# ==============================================================================

"""
CHEAT SHEET: Analyses Simples avec docker logs + jq

1. SEARCH METRICS
-----------------

# Searches per hour
docker logs mnemo-api --since 1h | grep "search_completed" | wc -l

# Average latency
docker logs mnemo-api --since 1h | grep "search_completed" | \\
  jq '.execution_time_ms' | awk '{sum+=$1; n++} END {print sum/n}'

# P95 latency
docker logs mnemo-api --since 1h | grep "search_completed" | \\
  jq -s 'map(.execution_time_ms) | sort | .[length * 0.95 | floor]'

# Slow searches (>200ms)
docker logs mnemo-api --since 1h | grep "search_completed" | \\
  jq 'select(.execution_time_ms > 200)'

# Search method distribution
docker logs mnemo-api --since 1h | grep "search_completed" | \\
  jq -s 'group_by(.method) | map({method: .[0].method, count: length})'

# Vector search usage rate
docker logs mnemo-api --since 1h | grep "search_completed" | \\
  jq -s 'map(select(.vector_count > 0)) | length / (length + 1) * 100'


2. EMBEDDING METRICS
--------------------

# Cache hit rate
docker logs mnemo-api --since 1h | grep "embedding_generated" | \\
  jq -s 'map(select(.cache_hit)) | length / length * 100'

# Average generation time
docker logs mnemo-api --since 1h | grep "embedding_generated" | \\
  jq '.generation_time_ms' | awk '{sum+=$1} END {print sum/NR}'

# Generation time by domain
docker logs mnemo-api --since 1h | grep "embedding_generated" | \\
  jq -s 'group_by(.domain) | map({domain: .[0].domain, avg: (map(.generation_time_ms) | add / length)})'


3. INDEXING METRICS
-------------------

# Total chunks indexed today
docker logs mnemo-api --since 24h | grep "indexing_completed" | \\
  jq -s 'map(.chunks_created) | add'

# Average indexing throughput (chunks/sec)
docker logs mnemo-api --since 24h | grep "indexing_completed" | \\
  jq '.chunks_per_second' | awk '{sum+=$1} END {print sum/NR}'

# Failed indexations
docker logs mnemo-api --since 24h | grep "indexing_completed" | \\
  jq 'select(.success == false)'


4. CACHE METRICS
----------------

# Cache hit rate by type
docker logs mnemo-api --since 1h | grep "cache_operation" | \\
  jq -s 'group_by(.cache_type) | map({type: .[0].cache_type, hits: (map(select(.hit)) | length), total: length})'


5. ERROR TRACKING
-----------------

# All errors in last hour
docker logs mnemo-api --since 1h | grep '"level":"error"'

# Errors by event type
docker logs mnemo-api --since 1h | grep '"level":"error"' | \\
  jq -s 'group_by(.event) | map({event: .[0].event, count: length})'


6. QUICK DASHBOARD (one-liner)
-------------------------------

# Single command to show all key metrics
docker logs mnemo-api --since 1h | \\
  jq -s 'map(select(.event == "search_completed")) | \\
  {searches: length, avg_latency: (map(.execution_time_ms) | add / length), \\
  vector_usage: (map(select(.vector_count > 0)) | length / length * 100)}'
"""


if __name__ == "__main__":
    """Example usage."""
    import asyncio

    async def example():
        # Example 1: Log search metrics
        log_search_metrics(
            query="validate email address",
            method="hybrid",
            results_count=5,
            execution_time_ms=45.2,
            lexical_count=3,
            vector_count=4,
            repository="my-repo"
        )

        # Example 2: Log embedding generation
        log_embedding_generation_metrics(
            text="validate email",
            domain="TEXT",
            generation_time_ms=15.3,
            cache_hit=False
        )

        # Example 3: Log indexing
        log_indexing_metrics(
            repository="backend-api",
            files_count=10,
            chunks_created=47,
            indexing_time_ms=1234.5,
            embeddings_generated=True
        )

    asyncio.run(example())
