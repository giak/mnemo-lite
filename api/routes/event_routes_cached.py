"""
Event routes with caching optimization.
This module adds caching to critical event endpoints for improved performance.
"""

import logging
from typing import Dict, Any, List, Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body

from models.event_models import EventModel, EventCreate
from services.event_service import EventService
from dependencies import get_event_service
from services.simple_memory_cache import get_event_cache, get_search_cache

# Configuration
logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])

# Cache instances
event_cache = get_event_cache()
search_cache = get_search_cache()


@router.post("/", response_model=EventModel, status_code=201)
async def create_event(
    event: EventCreate,
    service: Annotated[EventService, Depends(get_event_service)],
) -> EventModel:
    """Create a new event (not cached as it modifies data)."""
    try:
        new_event = await service.create_event(event)

        # Invalidate relevant caches after creation
        await search_cache.clear()  # Clear search cache since new data added

        return new_event
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{event_id}", response_model=EventModel)
async def get_event(
    event_id: UUID,
    service: Annotated[EventService, Depends(get_event_service)],
    no_cache: bool = Query(False, description="Bypass cache"),
) -> EventModel:
    """Get event by ID with caching."""
    # Check cache first
    cache_key = f"event_{event_id}"

    if not no_cache:
        cached = await event_cache.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT for event {event_id}")
            return cached

    try:
        event = await service.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        # Cache successful result
        await event_cache.set(cache_key, event)
        logger.debug(f"Cache MISS for event {event_id} - cached now")

        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{event_id}/metadata", response_model=EventModel)
async def update_event_metadata(
    event_id: UUID,
    metadata: Dict[str, Any],
    service: Annotated[EventService, Depends(get_event_service)],
) -> EventModel:
    """Update event metadata (invalidates cache)."""
    try:
        updated_event = await service.update_event_metadata(event_id, metadata)
        if updated_event is None:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        # Invalidate caches after update
        cache_key = f"event_{event_id}"
        await event_cache.remove(cache_key)
        await search_cache.clear()

        return updated_event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: UUID,
    service: Annotated[EventService, Depends(get_event_service)],
) -> None:
    """Delete event (invalidates cache)."""
    try:
        success = await service.delete_event(event_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        # Invalidate caches after deletion
        cache_key = f"event_{event_id}"
        await event_cache.remove(cache_key)
        await search_cache.clear()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filter/metadata", response_model=List[EventModel])
@search_cache.cache_async(ttl=30)  # Cache for 30 seconds
async def filter_events_by_metadata(
    service: Annotated[EventService, Depends(get_event_service)],
    metadata_filter: Dict[str, Any] = Body(...),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[EventModel]:
    """Filter events by metadata with caching."""
    try:
        return await service.filter_events_by_metadata(metadata_filter, limit, offset)
    except Exception as e:
        logger.error(f"Error filtering events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/embedding", response_model=List[EventModel])
async def search_events_by_embedding(
    service: Annotated[EventService, Depends(get_event_service)],
    embedding: List[float] = Body(...),
    limit: int = Query(5, ge=1, le=100),
    no_cache: bool = Query(False, description="Bypass cache"),
) -> List[EventModel]:
    """Search events by embedding with caching."""
    # Create cache key from embedding (using first/last few values for speed)
    cache_key = f"emb_search_{embedding[0]:.4f}_{embedding[-1]:.4f}_{limit}"

    if not no_cache:
        cached = await search_cache.get(cache_key)
        if cached:
            logger.debug("Cache HIT for embedding search")
            return cached

    try:
        results = await service.search_events_by_embedding(embedding, limit)

        # Cache results
        await search_cache.set(cache_key, results)
        logger.debug("Cache MISS for embedding search - cached now")

        return results
    except Exception as e:
        logger.error(f"Error searching events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_statistics() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    return {
        "event_cache": event_cache.get_stats(),
        "search_cache": search_cache.get_stats(),
    }


@router.post("/cache/clear", status_code=204)
async def clear_all_caches() -> None:
    """Clear all caches (admin endpoint)."""
    await event_cache.clear()
    await search_cache.clear()
    logger.info("All event caches cleared")