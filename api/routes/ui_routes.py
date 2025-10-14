"""
UI routes for MnemoLite web interface.

Provides HTML pages for exploring events, search, and basic management.
Uses HTMX for dynamic interactions without full page reloads.
"""

import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List

from dependencies import get_event_repository, get_embedding_service
from db.repositories.event_repository import EventRepository
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["UI"])

# Templates will be configured in main.py
templates = None  # Will be injected


def set_templates(template_instance: Jinja2Templates):
    """Set templates instance (called from main.py)."""
    global templates
    templates = template_instance


def parse_period(period: Optional[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse period presets to datetime range.

    Args:
        period: Preset string ("1h", "6h", "24h", "7d", "30d", "all")

    Returns:
        Tuple of (ts_start, ts_end)
    """
    if not period or period == "all":
        return None, None

    now = datetime.now(timezone.utc)

    period_map = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }

    delta = period_map.get(period)
    if delta:
        return now - delta, now

    return None, None


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    period: Optional[str] = Query(None, description="Time period preset: 1h, 6h, 24h, 7d, 30d, all"),
    project: Optional[str] = Query(None, description="Filter by project"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(20, ge=1, le=100, description="Number of events to show"),
    repo: EventRepository = Depends(get_event_repository)
):
    """
    Main dashboard page showing recent events with filters.

    Supports filtering by time period, project, category, sort order and limit.
    If HX-Request header is present, returns only the event list partial.
    """
    try:
        # Parse period to datetime range
        ts_start, ts_end = parse_period(period)

        # Build metadata filter
        metadata_filter = {}
        if project:
            metadata_filter["project"] = project
        if category:
            metadata_filter["category"] = category

        # Fetch events with filters
        events, total = await repo.search_vector(
            vector=None,
            metadata=metadata_filter if metadata_filter else None,
            ts_start=ts_start,
            ts_end=ts_end,
            limit=limit,
            offset=0
        )

        context = {
            "request": request,
            "events": events,
            "total_count": total,
            "filters": {
                "period": period or "all",
                "project": project,
                "category": category,
                "sort_order": sort_order,
                "limit": limit
            },
            "target_url": "/ui/",
            "target_element": "#dashboard-content"
        }

        # Check if this is an HTMX request (partial update)
        is_htmx = request.headers.get("HX-Request") == "true"

        if is_htmx:
            # Return only the event list partial
            return templates.TemplateResponse(
                "partials/dashboard_events.html",
                context
            )
        else:
            # Return full page
            return templates.TemplateResponse(
                "dashboard.html",
                context
            )

    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)},
            status_code=500
        )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """
    Search page with form for semantic search.

    Results are loaded dynamically via HTMX.
    """
    return templates.TemplateResponse(
        "search.html",
        {"request": request}
    )


@router.get("/search/results", response_class=HTMLResponse)
async def search_results(
    request: Request,
    q: Optional[str] = None,
    period: Optional[str] = Query(None, description="Time period preset: 1h, 6h, 24h, 7d, 30d, all"),
    project: Optional[str] = Query(None, description="Filter by project"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100),
    repo: EventRepository = Depends(get_event_repository),
    embedding_svc: SentenceTransformerEmbeddingService = Depends(get_embedding_service)
):
    """
    Search results partial (HTMX target).

    Performs semantic search if query provided, otherwise returns recent events.
    Supports filtering by time period, project, and category.
    """
    try:
        # Parse period to datetime range
        ts_start, ts_end = parse_period(period)

        # Build metadata filter
        metadata_filter = {}
        if project:
            metadata_filter["project"] = project
        if category:
            metadata_filter["category"] = category

        if q and q.strip():
            # Generate embedding for query
            query_embedding = await embedding_svc.generate_embedding(q.strip())

            # Vector search with filters
            events, total = await repo.search_vector(
                vector=query_embedding,
                metadata=metadata_filter if metadata_filter else None,
                ts_start=ts_start,
                ts_end=ts_end,
                limit=limit,
                offset=0
            )

            context = {
                "request": request,
                "events": events,
                "query": q,
                "total": total,
                "search_performed": True
            }
        else:
            # No query - return recent events with filters
            events, total = await repo.search_vector(
                vector=None,
                metadata=metadata_filter if metadata_filter else None,
                ts_start=ts_start,
                ts_end=ts_end,
                limit=limit,
                offset=0
            )

            context = {
                "request": request,
                "events": events,
                "total": total,
                "search_performed": False
            }

        return templates.TemplateResponse(
            "partials/event_list.html",
            context
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/error_message.html",
            {"request": request, "error": str(e)},
            status_code=500
        )


@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail(
    request: Request,
    event_id: str,
    repo: EventRepository = Depends(get_event_repository)
):
    """
    Event detail partial (HTMX target).

    Shows full JSON content and metadata for a specific event.
    """
    try:
        import uuid
        event_uuid = uuid.UUID(event_id)

        event = await repo.get_by_id(event_uuid)

        if not event:
            return templates.TemplateResponse(
                "partials/error_message.html",
                {"request": request, "error": f"Event {event_id} not found"},
                status_code=404
            )

        return templates.TemplateResponse(
            "partials/event_detail.html",
            {
                "request": request,
                "event": event
            }
        )

    except ValueError:
        return templates.TemplateResponse(
            "partials/error_message.html",
            {"request": request, "error": f"Invalid event ID: {event_id}"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Event detail error: {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/error_message.html",
            {"request": request, "error": str(e)},
            status_code=500
        )


@router.get("/api/filters/options")
async def get_filter_options(
    repo: EventRepository = Depends(get_event_repository)
):
    """
    Get dynamic filter options from database.

    Returns distinct values for:
    - projects: metadata->>'project'
    - categories: metadata->>'category'

    This allows the UI to show only options that actually exist in the data,
    instead of hardcoding values in HTML templates.
    """
    try:
        from sqlalchemy import text

        async with repo.engine.connect() as conn:
            # Get distinct projects
            projects_result = await conn.execute(text("""
                SELECT DISTINCT metadata->>'project' as project
                FROM events
                WHERE metadata->>'project' IS NOT NULL
                  AND metadata->>'project' != ''
                ORDER BY project
            """))
            projects = [row.project for row in projects_result if row.project]

            # Get distinct categories
            categories_result = await conn.execute(text("""
                SELECT DISTINCT metadata->>'category' as category
                FROM events
                WHERE metadata->>'category' IS NOT NULL
                  AND metadata->>'category' != ''
                ORDER BY category
            """))
            categories = [row.category for row in categories_result if row.category]

            return {
                "projects": projects,
                "categories": categories
            }

    except Exception as e:
        logger.error(f"Failed to get filter options: {e}", exc_info=True)
        # Return empty lists on error (graceful degradation)
        return {
            "projects": [],
            "categories": []
        }


@router.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    """
    Graph visualization page.

    Shows interactive network graph of nodes and edges using Cytoscape.js.
    """
    return templates.TemplateResponse(
        "graph.html",
        {"request": request}
    )


@router.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    """
    Monitoring dashboard page.

    Shows real-time operational monitoring for MCO with:
    - System status (operational/degraded/critical)
    - KPI cards (critical/warning/info event counts)
    - Timeline chart (24h event trends)
    - Critical events list
    - Event distribution analysis
    - Auto-refresh (30s)
    """
    return templates.TemplateResponse(
        "monitoring.html",
        {"request": request}
    )
