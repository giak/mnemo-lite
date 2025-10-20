"""
Cache Administration Routes for EPIC-10 Story 10.4.

Provides endpoints for cache management:
- POST /v1/cache/flush - Manual cache invalidation
- GET /v1/cache/stats - Cache statistics and metrics
"""

from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dependencies import get_cascade_cache
from services.caches.cascade_cache import CascadeCache

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/cache", tags=["Cache Administration"])


# ====== Request/Response Models ======

class FlushRequest(BaseModel):
    """Request model for cache flush."""
    repository: Optional[str] = None
    file_path: Optional[str] = None
    scope: Optional[str] = "all"  # "all", "repository", "file"


class FlushResponse(BaseModel):
    """Response model for cache flush."""
    status: str
    scope: str
    target: Optional[str] = None
    message: str


# ====== Endpoints ======

@router.post("/flush", response_model=FlushResponse)
async def flush_cache(
    request: FlushRequest = FlushRequest(),
    cascade_cache: CascadeCache = Depends(get_cascade_cache)
):
    """
    Flush cache (all, repository, or file).

    **Scope Options**:
    - `all`: Flush entire L1 + L2 cache (default)
    - `repository`: Flush all cache for specific repository
    - `file`: Flush cache for specific file

    **Examples**:
    ```
    # Flush everything
    POST /v1/cache/flush
    {}

    # Flush specific repository
    POST /v1/cache/flush
    {"scope": "repository", "repository": "my-repo"}

    # Flush specific file
    POST /v1/cache/flush
    {"scope": "file", "file_path": "src/utils/helper.py"}
    ```

    **Returns**:
    - `status`: "success" or "error"
    - `scope`: What was flushed
    - `target`: Specific repository/file if applicable
    - `message`: Human-readable confirmation

    **Security Note**: This endpoint should be protected in production
    (e.g., require admin authentication).
    """

    try:
        if request.scope == "file" and request.file_path:
            # Flush specific file
            await cascade_cache.invalidate(request.file_path)

            logger.info(
                "Cache flushed via API",
                scope="file",
                file_path=request.file_path
            )

            return FlushResponse(
                status="success",
                scope="file",
                target=request.file_path,
                message=f"Cache invalidated for file: {request.file_path}"
            )

        elif request.scope == "repository" and request.repository:
            # Flush specific repository
            await cascade_cache.invalidate_repository(request.repository)

            logger.info(
                "Cache flushed via API",
                scope="repository",
                repository=request.repository
            )

            return FlushResponse(
                status="success",
                scope="repository",
                target=request.repository,
                message=f"Cache invalidated for repository: {request.repository}"
            )

        elif request.scope == "all":
            # Flush all caches (L1 + L2)
            cascade_cache.l1.clear()
            await cascade_cache.l2.flush_pattern("*")

            logger.warning(
                "Cache flushed via API",
                scope="all",
                message="FULL CACHE FLUSH - ALL L1+L2 CLEARED"
            )

            return FlushResponse(
                status="success",
                scope="all",
                message="All caches flushed (L1 + L2)"
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid scope or missing required parameters"
            )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is (don't convert to 500)
    except Exception as e:
        logger.error("Cache flush failed via API", error=str(e))
        raise HTTPException(status_code=500, detail=f"Cache flush failed: {str(e)}")


@router.get("/stats")
async def get_cache_stats(
    cascade_cache: CascadeCache = Depends(get_cascade_cache)
):
    """
    Get comprehensive cache statistics.

    **Returns**:
    ```json
    {
      "l1": {
        "type": "L1_memory",
        "size_mb": 25.3,
        "max_size_mb": 100.0,
        "entries": 142,
        "hits": 1523,
        "misses": 287,
        "hit_rate_percent": 84.1,
        "utilization_percent": 25.3
      },
      "l2": {
        "type": "L2_redis",
        "connected": true,
        "hits": 215,
        "misses": 72,
        "hit_rate_percent": 74.9,
        "memory_used_mb": 45.2,
        "memory_peak_mb": 52.1
      },
      "cascade": {
        "l1_hit_rate_percent": 84.1,
        "l2_hit_rate_percent": 74.9,
        "combined_hit_rate_percent": 92.3,
        "l1_to_l2_promotions": 215,
        "strategy": "L1 → L2 → L3 (PostgreSQL)"
      }
    }
    ```

    **Metrics Explained**:
    - **L1 (Memory)**:
      - `size_mb`: Current memory usage
      - `entries`: Number of cached files
      - `hit_rate_percent`: % of L1 lookups that hit
      - `utilization_percent`: % of max capacity used

    - **L2 (Redis)**:
      - `connected`: Redis availability
      - `hit_rate_percent`: % of L2 lookups that hit (among L1 misses)
      - `memory_used_mb`: Redis memory consumption

    - **Cascade**:
      - `combined_hit_rate_percent`: Effective hit rate across L1+L2
      - `l1_to_l2_promotions`: Count of L2 hits promoted to L1
      - Formula: `L1_rate + (1 - L1_rate) × L2_rate`

    **Use Cases**:
    - Monitor cache health
    - Tune cache sizes
    - Detect Redis failures (connected: false)
    - Track promotion effectiveness
    """

    try:
        stats = await cascade_cache.stats()

        logger.debug(
            "Cache stats requested via API",
            l1_hit_rate=stats["cascade"]["l1_hit_rate_percent"],
            l2_hit_rate=stats["cascade"]["l2_hit_rate_percent"],
            combined_hit_rate=stats["cascade"]["combined_hit_rate_percent"]
        )

        return stats

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error("Cache stats retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cache stats: {str(e)}")


@router.post("/clear-all")
async def clear_all_caches(
    cascade_cache: CascadeCache = Depends(get_cascade_cache)
):
    """
    DANGER: Clear ALL caches (L1 + L2) immediately.

    **Warning**: This is a destructive operation that will:
    - Clear all L1 in-memory cache
    - Flush all Redis L2 keys
    - Force all subsequent requests to hit PostgreSQL

    **Use Cases**:
    - Emergency cache corruption fix
    - Testing cache miss scenarios
    - Pre-deployment cache reset

    **Returns**:
    ```json
    {
      "status": "success",
      "message": "All caches cleared",
      "l1_cleared": true,
      "l2_cleared": true
    }
    ```

    **Security Note**: Protect this endpoint in production!
    """

    try:
        # Clear L1
        cascade_cache.l1.clear()
        l1_cleared = True

        # Flush L2 (all keys)
        await cascade_cache.l2.flush_pattern("*")
        l2_cleared = True

        logger.warning(
            "ALL CACHES CLEARED via API",
            l1_cleared=l1_cleared,
            l2_cleared=l2_cleared,
            message="DESTRUCTIVE OPERATION EXECUTED"
        )

        return {
            "status": "success",
            "message": "All caches cleared (L1 + L2)",
            "l1_cleared": l1_cleared,
            "l2_cleared": l2_cleared
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error("Clear all caches failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear caches: {str(e)}")
