"""
UI routes for MnemoLite web interface.

Provides HTML pages for exploring events, search, and basic management.
Uses HTMX for dynamic interactions without full page reloads.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List

from dependencies import get_event_repository, get_embedding_service, get_db_engine
from db.repositories.event_repository import EventRepository
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["UI"])

# Templates will be configured in main.py
templates = None  # Will be injected

# Upload security configuration
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB max payload size
MAX_FILES_PER_UPLOAD = 10000  # Maximum number of files per upload
MAX_CONCURRENT_UPLOADS = 50  # Global limit on concurrent uploads
REPOSITORY_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,255}$")  # Alphanumeric + _-.  max 255 chars


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


@router.get("/monitoring/advanced", response_class=HTMLResponse)
async def monitoring_advanced_page(request: Request):
    """
    Advanced Observability Dashboard (EPIC-22 Story 22.2).

    Shows comprehensive system metrics:
    - API metrics: latency (avg, P50, P95, P99), throughput, error rate
    - Redis metrics: hit rate, memory usage, keys, evictions
    - PostgreSQL metrics: connections, cache hit ratio, slow queries
    - System metrics: CPU, memory, disk usage
    - Real-time logs stream (SSE)
    - Auto-refresh (10s)
    """
    return templates.TemplateResponse(
        "monitoring_advanced.html",
        {"request": request}
    )


@router.get("/cache", response_class=HTMLResponse)
async def cache_dashboard_page(request: Request):
    """
    Cache Performance Dashboard (EPIC-10 Story 10.5).

    Shows real-time cache metrics for L1/L2 cascade:
    - Combined hit rate (L1 + L2)
    - Individual layer hit rates
    - Memory usage (L1 size, L2 memory)
    - L2→L1 promotions count
    - Detailed layer statistics
    - Real-time charts (hit rates, memory distribution)
    - Manual cache flush actions
    - Auto-refresh (5s)
    """
    return templates.TemplateResponse(
        "cache_dashboard.html",
        {"request": request}
    )


# ============================================================================
# Code Intelligence UI Routes (EPIC-07)
# ============================================================================

@router.get("/code/", response_class=HTMLResponse)
async def code_dashboard(request: Request):
    """
    Code Intelligence Dashboard (EPIC-07 Story 5).

    Analytics and overview of indexed code repositories.
    """
    return templates.TemplateResponse(
        "code_dashboard.html",
        {"request": request}
    )


@router.get("/code/dashboard/data")
async def code_dashboard_data(engine = Depends(get_db_engine)):
    """
    Analytics data endpoint for Code Intelligence Dashboard (EPIC-07 Story 5).

    Returns:
    - KPIs: total repos, files, functions, avg complexity
    - Language distribution
    - Complexity distribution
    - Top 10 complex functions
    - Recent indexing activity
    """
    from sqlalchemy import text
    from collections import defaultdict

    try:
        # ========== KPIs ==========
        # Total repositories
        repos_query = text("""
            SELECT COUNT(DISTINCT repository) as total_repos
            FROM code_chunks
            WHERE repository IS NOT NULL
        """)

        # Total files
        files_query = text("""
            SELECT COUNT(DISTINCT file_path) as total_files
            FROM code_chunks
        """)

        # Total functions/classes (chunk_type = function, method, class)
        functions_query = text("""
            SELECT COUNT(*) as total_functions
            FROM code_chunks
            WHERE chunk_type IN ('function', 'method', 'class')
        """)

        # Average complexity
        complexity_query = text(r"""
            SELECT AVG(((metadata->>'complexity')::jsonb->>'cyclomatic')::float) as avg_complexity
            FROM code_chunks
            WHERE metadata->>'complexity' IS NOT NULL
              AND metadata->>'complexity' != 'null'
              AND (metadata->>'complexity')::jsonb->>'cyclomatic' IS NOT NULL
              AND (metadata->>'complexity')::jsonb->>'cyclomatic' ~ '^[0-9]+\.?[0-9]*$'
        """)

        async with engine.connect() as conn:
            repos_result = await conn.execute(repos_query)
            files_result = await conn.execute(files_query)
            functions_result = await conn.execute(functions_query)
            complexity_result = await conn.execute(complexity_query)

            total_repos = repos_result.scalar() or 0
            total_files = files_result.scalar() or 0
            total_functions = functions_result.scalar() or 0
            avg_complexity = complexity_result.scalar() or 0.0

        kpis = {
            "total_repositories": total_repos,
            "total_files": total_files,
            "total_functions": total_functions,
            "avg_complexity": avg_complexity
        }

        # ========== Language Distribution ==========
        language_query = text("""
            SELECT
                language,
                COUNT(*) as count
            FROM code_chunks
            WHERE language IS NOT NULL
            GROUP BY language
            ORDER BY count DESC
        """)

        async with engine.connect() as conn:
            language_result = await conn.execute(language_query)
            language_rows = language_result.fetchall()

        language_distribution = [
            {"language": row[0], "count": row[1]}
            for row in language_rows
        ]

        # ========== Complexity Distribution ==========
        complexity_dist_query = text("""
            SELECT
                CAST((metadata->>'complexity')::jsonb->>'cyclomatic' AS INTEGER) as complexity,
                COUNT(*) as count
            FROM code_chunks
            WHERE metadata->>'complexity' IS NOT NULL
              AND metadata->>'complexity' != 'null'
              AND (metadata->>'complexity')::jsonb->>'cyclomatic' IS NOT NULL
            GROUP BY complexity
            ORDER BY complexity
        """)

        async with engine.connect() as conn:
            complexity_dist_result = await conn.execute(complexity_dist_query)
            complexity_rows = complexity_dist_result.fetchall()

        complexity_distribution = [
            {"complexity": row[0] or 0, "count": row[1]}
            for row in complexity_rows
        ]

        # ========== Top 10 Complex Functions ==========
        top_complex_query = text("""
            SELECT
                name,
                file_path,
                language,
                CAST((metadata->>'complexity')::jsonb->>'cyclomatic' AS INTEGER) as complexity,
                CAST((metadata->>'complexity')::jsonb->>'lines_of_code' AS INTEGER) as lines
            FROM code_chunks
            WHERE metadata->>'complexity' IS NOT NULL
              AND metadata->>'complexity' != 'null'
              AND (metadata->>'complexity')::jsonb->>'cyclomatic' IS NOT NULL
              AND chunk_type IN ('function', 'method', 'class')
            ORDER BY complexity DESC
            LIMIT 10
        """)

        async with engine.connect() as conn:
            top_complex_result = await conn.execute(top_complex_query)
            top_complex_rows = top_complex_result.fetchall()

        top_complex_functions = [
            {
                "name": row[0] or "Unnamed",
                "file_path": row[1],
                "language": row[2],
                "complexity": row[3] or 0,
                "lines": row[4] or 0
            }
            for row in top_complex_rows
        ]

        # ========== Recent Activity ==========
        recent_activity_query = text("""
            SELECT
                repository,
                COUNT(DISTINCT file_path) as file_count,
                COUNT(*) as chunk_count,
                MAX(indexed_at) as last_indexed
            FROM code_chunks
            WHERE repository IS NOT NULL
            GROUP BY repository
            ORDER BY last_indexed DESC
            LIMIT 10
        """)

        async with engine.connect() as conn:
            recent_activity_result = await conn.execute(recent_activity_query)
            recent_activity_rows = recent_activity_result.fetchall()

        recent_activity = [
            {
                "repository": row[0],
                "file_count": row[1],
                "chunk_count": row[2],
                "last_indexed": row[3].isoformat() if row[3] else None
            }
            for row in recent_activity_rows
        ]

        return {
            "kpis": kpis,
            "language_distribution": language_distribution,
            "complexity_distribution": complexity_distribution,
            "top_complex_functions": top_complex_functions,
            "recent_activity": recent_activity
        }

    except Exception as e:
        logger.error(f"Failed to load dashboard data: {e}", exc_info=True)
        return {
            "error": str(e),
            "kpis": {
                "total_repositories": 0,
                "total_files": 0,
                "total_functions": 0,
                "avg_complexity": 0.0
            },
            "language_distribution": [],
            "complexity_distribution": [],
            "top_complex_functions": [],
            "recent_activity": []
        }


@router.get("/lsp/stats")
async def lsp_stats(engine = Depends(get_db_engine)):
    """
    LSP Health Statistics endpoint (EPIC-14 Story 14.3).

    Returns real-time LSP server health metrics for dashboard widget:
    - LSP server uptime (simulated from indexed_at timestamps)
    - Query count (total chunks with LSP metadata)
    - Cache hit rate (from Redis L2 cache stats)
    - Type coverage (percentage of chunks with return_type)

    Used by lsp_monitor.js for Chart.js visualization.
    """
    from sqlalchemy import text
    import redis
    import os

    try:
        # ========== Type Coverage & Query Count ==========
        # Count chunks with LSP metadata (return_type, signature, or param_types)
        lsp_metadata_query = text("""
            SELECT
                COUNT(*) FILTER (WHERE metadata->>'return_type' IS NOT NULL) as chunks_with_return_type,
                COUNT(*) FILTER (WHERE metadata->>'signature' IS NOT NULL) as chunks_with_signature,
                COUNT(*) FILTER (WHERE metadata->>'param_types' IS NOT NULL) as chunks_with_params,
                COUNT(*) as total_chunks,
                MIN(indexed_at) as first_indexed,
                MAX(indexed_at) as last_indexed
            FROM code_chunks
            WHERE chunk_type IN ('function', 'method', 'class')
        """)

        async with engine.connect() as conn:
            result = await conn.execute(lsp_metadata_query)
            row = result.fetchone()

        chunks_with_return_type = row[0] or 0
        chunks_with_signature = row[1] or 0
        chunks_with_params = row[2] or 0
        total_chunks = row[3] or 0
        first_indexed = row[4]
        last_indexed = row[5]

        # Calculate type coverage percentage
        type_coverage = round((chunks_with_return_type / total_chunks * 100), 2) if total_chunks > 0 else 0

        # Calculate uptime (time since first indexing)
        uptime_seconds = 0
        uptime_display = "Not running"
        if first_indexed and last_indexed:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            uptime_delta = now - first_indexed
            uptime_seconds = int(uptime_delta.total_seconds())

            # Format uptime as human-readable
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60

            if days > 0:
                uptime_display = f"{days}d {hours}h"
            elif hours > 0:
                uptime_display = f"{hours}h {minutes}m"
            else:
                uptime_display = f"{minutes}m"

        # ========== Cache Hit Rate (from Redis L2) ==========
        cache_hit_rate = 0.0
        cache_hits = 0
        cache_misses = 0

        try:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            redis_client = redis.from_url(redis_url, decode_responses=True)

            # Get cache stats from Redis (EPIC-10 pattern)
            cache_hits = int(redis_client.get("cache:stats:hits") or 0)
            cache_misses = int(redis_client.get("cache:stats:misses") or 0)

            total_requests = cache_hits + cache_misses
            if total_requests > 0:
                cache_hit_rate = round((cache_hits / total_requests * 100), 2)

            redis_client.close()
        except Exception as redis_error:
            logger.warning(f"Failed to get Redis cache stats: {redis_error}")
            # Graceful degradation - continue with cache_hit_rate = 0

        # ========== LSP Server Status ==========
        # Determine status based on recent activity
        lsp_status = "running"
        if total_chunks == 0:
            lsp_status = "idle"
        elif last_indexed:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            time_since_last = now - last_indexed
            if time_since_last > timedelta(hours=24):
                lsp_status = "idle"

        return {
            "status": lsp_status,
            "uptime": {
                "seconds": uptime_seconds,
                "display": uptime_display
            },
            "query_count": {
                "total_chunks": total_chunks,
                "with_return_type": chunks_with_return_type,
                "with_signature": chunks_with_signature,
                "with_params": chunks_with_params
            },
            "cache": {
                "hit_rate": cache_hit_rate,
                "hits": cache_hits,
                "misses": cache_misses
            },
            "type_coverage": {
                "percentage": type_coverage,
                "chunks_with_types": chunks_with_return_type,
                "total_chunks": total_chunks
            },
            "timestamps": {
                "first_indexed": first_indexed.isoformat() if first_indexed else None,
                "last_indexed": last_indexed.isoformat() if last_indexed else None
            }
        }

    except Exception as e:
        logger.error(f"Failed to get LSP stats: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "uptime": {"seconds": 0, "display": "Error"},
            "query_count": {"total_chunks": 0, "with_return_type": 0, "with_signature": 0, "with_params": 0},
            "cache": {"hit_rate": 0.0, "hits": 0, "misses": 0},
            "type_coverage": {"percentage": 0.0, "chunks_with_types": 0, "total_chunks": 0},
            "timestamps": {"first_indexed": None, "last_indexed": None}
        }


@router.get("/code/repos", response_class=HTMLResponse)
async def code_repositories(request: Request):
    """
    Code Repository Manager (EPIC-07 Story 1).

    View and manage indexed code repositories.
    """
    return templates.TemplateResponse(
        "code_repos.html",
        {"request": request}
    )


@router.get("/code/repos/list", response_class=HTMLResponse)
async def code_repositories_list(
    request: Request,
    engine = Depends(get_db_engine)
):
    """
    Repository list partial (HTMX target).

    Fetches all indexed repositories from database.
    """
    from sqlalchemy import text

    try:
        # Query code_chunks grouped by repository (same as EPIC-06 API)
        query = text("""
            SELECT
                repository,
                COUNT(DISTINCT file_path) as file_count,
                COUNT(*) as chunk_count,
                MAX(indexed_at) as last_indexed
            FROM code_chunks
            WHERE repository IS NOT NULL
            GROUP BY repository
            ORDER BY last_indexed DESC
        """)

        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        repositories = [
            {
                "repository": row[0],
                "file_count": row[1],
                "chunk_count": row[2],
                "last_indexed": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]

        return templates.TemplateResponse(
            "partials/repo_list.html",
            {
                "request": request,
                "repositories": repositories
            }
        )

    except Exception as e:
        logger.error(f"Failed to fetch repositories: {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/error_message.html",
            {"request": request, "error": f"Failed to load repositories: {str(e)}"},
            status_code=500
        )


@router.delete("/code/repos/{repository}", response_class=HTMLResponse)
async def code_repository_delete(
    request: Request,
    repository: str,
    engine = Depends(get_db_engine)
):
    """
    Delete repository (HTMX target).

    Deletes repository from database and returns updated list.
    """
    from sqlalchemy import text

    try:
        # Delete code chunks, nodes, and edges for this repository
        # Order: edges first (to avoid FK issues), then nodes, then chunks

        # Step 1: Delete edges connected to nodes of this repository
        delete_edges = text("""
            DELETE FROM edges
            WHERE source_node_id IN (
                SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
            )
            OR target_node_id IN (
                SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
            )
        """)

        # Step 2: Delete nodes of this repository
        delete_nodes = text("""
            DELETE FROM nodes
            WHERE properties->>'repository' = :repository
        """)

        # Step 3: Delete code chunks of this repository
        delete_chunks = text("""
            DELETE FROM code_chunks
            WHERE repository = :repository
        """)

        async with engine.begin() as conn:
            result_edges = await conn.execute(delete_edges, {"repository": repository})
            result_nodes = await conn.execute(delete_nodes, {"repository": repository})
            result_chunks = await conn.execute(delete_chunks, {"repository": repository})

        logger.info(
            f"Deleted repository '{repository}': "
            f"{result_chunks.rowcount} chunks, {result_nodes.rowcount} nodes, {result_edges.rowcount} edges"
        )

        # Fetch updated repository list
        query = text("""
            SELECT
                repository,
                COUNT(DISTINCT file_path) as file_count,
                COUNT(*) as chunk_count,
                MAX(indexed_at) as last_indexed
            FROM code_chunks
            WHERE repository IS NOT NULL
            GROUP BY repository
            ORDER BY last_indexed DESC
        """)

        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        repositories = [
            {
                "repository": row[0],
                "file_count": row[1],
                "chunk_count": row[2],
                "last_indexed": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]

        return templates.TemplateResponse(
            "partials/repo_list.html",
            {
                "request": request,
                "repositories": repositories
            }
        )

    except Exception as e:
        logger.error(f"Failed to delete repository '{repository}': {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/error_message.html",
            {"request": request, "error": f"Failed to delete repository: {str(e)}"},
            status_code=500
        )


@router.get("/code/search", response_class=HTMLResponse)
async def code_search_page(request: Request):
    """
    Code Search Interface (EPIC-07 Story 2).

    Search indexed code with hybrid/lexical/vector modes.
    """
    return templates.TemplateResponse(
        "code_search.html",
        {"request": request}
    )


@router.get("/code/suggest")
async def code_suggest(
    q: str = Query(..., description="Autocomplete query"),
    field: str = Query("all", description="Field to suggest: all, name, return_type, param_type"),
    limit: int = Query(10, ge=1, le=50, description="Number of suggestions"),
    engine = Depends(get_db_engine)
):
    """
    Autocomplete suggestions endpoint (EPIC-14 Story 14.4).

    Returns intelligent autocomplete suggestions for:
    - Function names (fuzzy match)
    - Return types (from LSP metadata)
    - Parameter types (from LSP metadata)

    Used by autocomplete.js for type-aware filters.
    """
    from sqlalchemy import text

    try:
        suggestions = []

        # Fuzzy match function names
        if field in ("all", "name"):
            name_query = text("""
                SELECT DISTINCT name, LENGTH(name) as name_length
                FROM code_chunks
                WHERE name ILIKE :pattern
                  AND chunk_type IN ('function', 'method', 'class')
                ORDER BY name_length, name
                LIMIT :limit
            """)

            async with engine.connect() as conn:
                result = await conn.execute(name_query, {
                    "pattern": f"%{q}%",
                    "limit": limit
                })
                rows = result.fetchall()

            for row in rows:
                suggestions.append({
                    "value": row[0],  # name
                    "label": row[0],  # name
                    "type": "name",
                    "category": "Function/Class Name"
                })

        # Return type suggestions
        if field in ("all", "return_type"):
            return_type_query = text("""
                SELECT DISTINCT metadata->>'return_type' as return_type,
                       COUNT(*) as count
                FROM code_chunks
                WHERE metadata->>'return_type' IS NOT NULL
                  AND metadata->>'return_type' != ''
                  AND metadata->>'return_type' ILIKE :pattern
                GROUP BY return_type
                ORDER BY count DESC, return_type
                LIMIT :limit
            """)

            async with engine.connect() as conn:
                result = await conn.execute(return_type_query, {
                    "pattern": f"%{q}%",
                    "limit": limit
                })
                rows = result.fetchall()

            for row in rows:
                return_type = row[0]
                count = row[1]
                suggestions.append({
                    "value": return_type,
                    "label": f"{return_type} ({count} functions)",
                    "type": "return_type",
                    "category": "Return Type",
                    "count": count
                })

        # Parameter type suggestions
        if field in ("all", "param_type"):
            # Extract param types from metadata->param_types JSONB
            param_type_query = text("""
                SELECT DISTINCT param_type, COUNT(*) as count
                FROM (
                    SELECT jsonb_object_keys(metadata->'param_types') as param_name,
                           metadata->'param_types'->>jsonb_object_keys(metadata->'param_types') as param_type
                    FROM code_chunks
                    WHERE metadata->'param_types' IS NOT NULL
                ) sub
                WHERE param_type ILIKE :pattern
                GROUP BY param_type
                ORDER BY count DESC, param_type
                LIMIT :limit
            """)

            async with engine.connect() as conn:
                result = await conn.execute(param_type_query, {
                    "pattern": f"%{q}%",
                    "limit": limit
                })
                rows = result.fetchall()

            for row in rows:
                param_type = row[0]
                count = row[1]
                suggestions.append({
                    "value": param_type,
                    "label": f"{param_type} ({count} parameters)",
                    "type": "param_type",
                    "category": "Parameter Type",
                    "count": count
                })

        # Sort by relevance (exact match first, then prefix match, then count)
        suggestions.sort(key=lambda x: (
            0 if x["value"].lower() == q.lower() else 1,
            0 if x["value"].lower().startswith(q.lower()) else 1,
            -x.get("count", 0)
        ))

        return {
            "query": q,
            "suggestions": suggestions[:limit],
            "total": len(suggestions)
        }

    except Exception as e:
        logger.error(f"Autocomplete error: {e}", exc_info=True)
        return {
            "query": q,
            "suggestions": [],
            "total": 0,
            "error": str(e)
        }


@router.get("/code/search/results", response_class=HTMLResponse)
async def code_search_results(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    mode: str = Query("hybrid", description="Search mode: hybrid, lexical, vector"),
    repository: Optional[str] = Query(None, description="Filter by repository"),
    language: Optional[str] = Query(None, description="Filter by language"),
    chunk_type: Optional[str] = Query(None, description="Filter by chunk type"),
    return_type: Optional[str] = Query(None, description="Filter by return type (EPIC-14)"),
    param_type: Optional[str] = Query(None, description="Filter by parameter type (EPIC-14)"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    engine = Depends(get_db_engine),
    embedding_svc = Depends(get_embedding_service)
):
    """
    Code search results partial (HTMX target).

    Performs hybrid/lexical/vector search on code chunks.
    """
    try:
        from services.hybrid_code_search_service import (
            HybridCodeSearchService,
            SearchFilters,
        )

        # Validate query
        if not q or not q.strip():
            return templates.TemplateResponse(
                "partials/code_results.html",
                {
                    "request": request,
                    "results": [],
                    "total": 0,
                    "query": "",
                    "mode": mode,
                }
            )

        query = q.strip()

        # Build filters
        filters_dict = {}
        if repository:
            filters_dict["repository"] = repository
        if language:
            filters_dict["language"] = language
        if chunk_type:
            filters_dict["chunk_type"] = chunk_type
        if return_type:  # EPIC-14 Story 14.4
            filters_dict["return_type"] = return_type
        if param_type:  # EPIC-14 Story 14.4
            filters_dict["param_type"] = param_type

        filters = SearchFilters(**filters_dict) if filters_dict else None

        # Create search service
        search_service = HybridCodeSearchService(engine=engine)

        # Execute search based on mode
        if mode == "lexical":
            # Lexical-only search
            results = await search_service.lexical.search(
                query=query,
                filters=filters_dict if filters_dict else None,
                limit=limit,
            )

            context = {
                "request": request,
                "results": results,
                "total": len(results),
                "query": query,
                "mode": mode,
            }

        elif mode == "vector":
            # Vector-only search - requires embedding
            query_embedding = await embedding_svc.generate_embedding(query)

            results = await search_service.vector.search(
                embedding=query_embedding,
                embedding_domain="TEXT",  # Use TEXT domain for natural language queries
                filters=filters_dict if filters_dict else None,
                limit=limit,
            )

            context = {
                "request": request,
                "results": results,
                "total": len(results),
                "query": query,
                "mode": mode,
            }

        else:  # hybrid (default)
            # Hybrid search - requires embedding for vector component
            query_embedding = await embedding_svc.generate_embedding(query)

            response = await search_service.search(
                query=query,
                embedding_text=query_embedding,
                embedding_code=None,  # Use TEXT embedding for now
                filters=filters,
                top_k=limit,
                enable_lexical=True,
                enable_vector=True,
                lexical_weight=0.4,
                vector_weight=0.6,
                candidate_pool_size=100,
            )

            context = {
                "request": request,
                "results": response.results,
                "total": response.metadata.total_results,
                "query": query,
                "mode": mode,
                "metadata": response.metadata,
            }

        return templates.TemplateResponse(
            "partials/code_results.html",
            context
        )

    except Exception as e:
        logger.error(f"Code search error: {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/error_message.html",
            {"request": request, "error": f"Search failed: {str(e)}"},
            status_code=500
        )


@router.get("/code/graph", response_class=HTMLResponse)
async def code_graph_page(request: Request):
    """
    Code Dependency Graph (EPIC-07 Story 3).

    Interactive visualization of code dependencies.
    """
    return templates.TemplateResponse(
        "code_graph.html",
        {"request": request}
    )


@router.get("/code/graph/data")
async def code_graph_data(
    limit: int = Query(500, ge=1, le=5000, description="Max nodes to fetch"),
    engine = Depends(get_db_engine)
):
    """
    Code graph data endpoint for Cytoscape visualization (EPIC-07 Story 3).

    Returns nodes and edges in Cytoscape.js format.
    """
    from sqlalchemy import text

    try:
        # Fetch nodes with name_path from code_chunks (Story 11.3)
        nodes_query = text("""
            SELECT
                n.node_id,
                n.node_type,
                n.label,
                n.properties,
                n.created_at,
                c.name_path
            FROM nodes n
            LEFT JOIN code_chunks c ON
                CASE
                    WHEN n.properties->>'chunk_id' IS NOT NULL
                    THEN (n.properties->>'chunk_id')::uuid
                    ELSE NULL
                END = c.id
            ORDER BY n.created_at DESC
            LIMIT :limit
        """)

        async with engine.connect() as conn:
            nodes_result = await conn.execute(nodes_query, {"limit": limit})
            nodes_rows = nodes_result.fetchall()

        # Format nodes for Cytoscape
        cytoscape_nodes = []
        node_ids = set()
        for row in nodes_rows:
            node_id = str(row[0])
            node_ids.add(node_id)
            cytoscape_nodes.append({
                "data": {
                    "id": node_id,
                    "label": row[2] or "Unnamed",
                    "node_type": row[1],
                    "type": row[1],  # Alias for compatibility
                    "props": row[3] or {},
                    "created_at": row[4].isoformat() if row[4] else None,
                    "name_path": row[5]  # Story 11.3: Qualified name from code_chunks
                }
            })

        # Fetch edges for these nodes
        edges_query = text("""
            SELECT
                edge_id,
                source_node_id,
                target_node_id,
                relationship,
                props,
                created_at
            FROM edges
            WHERE source_node_id IN :node_ids
               OR target_node_id IN :node_ids
            LIMIT :limit
        """)

        async with engine.connect() as conn:
            # Convert set to list for SQL IN clause
            edges_result = await conn.execute(
                text("""
                    SELECT
                        edge_id,
                        source_node_id,
                        target_node_id,
                        relation_type,
                        properties,
                        created_at
                    FROM edges
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            edges_rows = edges_result.fetchall()

        # Format edges for Cytoscape
        cytoscape_edges = []
        for row in edges_rows:
            source_id = str(row[1])
            target_id = str(row[2])

            # Only include edges where both nodes are in our node set
            if source_id in node_ids and target_id in node_ids:
                cytoscape_edges.append({
                    "data": {
                        "id": str(row[0]),
                        "source": source_id,
                        "target": target_id,
                        "label": row[3] or "related_to",
                        "relationship": row[3],
                        "props": row[4] or {},
                        "created_at": row[5].isoformat() if row[5] else None
                    }
                })

        return {
            "nodes": cytoscape_nodes,
            "edges": cytoscape_edges
        }

    except Exception as e:
        logger.error(f"Failed to load graph data: {e}", exc_info=True)
        return {
            "nodes": [],
            "edges": [],
            "error": str(e)
        }


@router.get("/code/upload", response_class=HTMLResponse)
async def code_upload_page(request: Request):
    """
    Advanced Code Upload Interface (EPIC-09).

    Upload entire codebases - folders, ZIP files, or individual files.
    Supports recursive folder traversal, ZIP extraction, and batch processing.
    Real-time progress tracking with polling.
    """
    return templates.TemplateResponse(
        "code_upload_advanced.html",
        {"request": request}
    )


@router.post("/code/upload/process")
async def code_upload_process(
    request: Request,
    engine = Depends(get_db_engine)
):
    """
    Process code upload and index files (EPIC-09 Advanced Upload).

    SECURITY HARDENED VERSION with comprehensive input validation:
    - Request size validation (max 50MB)
    - Repository name validation (alphanumeric + _-. only)
    - Files array structure validation
    - Individual file validation (path safety, content type, size)
    - Rate limiting (max concurrent uploads)
    - Safe background task execution with exception handling

    Handles batch processing of entire codebases with:
    - Chunked processing for large uploads (batch size configurable)
    - Memory-efficient processing
    - Detailed error tracking per file
    - Support for folder/ZIP uploads from frontend
    - Real-time progress tracking via polling endpoint

    Returns immediately with upload_id, processing continues in background.
    Use GET /ui/code/upload/status/{upload_id} to poll for progress.

    Raises:
        HTTPException 413: Payload too large (>50MB)
        HTTPException 400: Invalid input (repository name, files structure, etc.)
        HTTPException 429: Too many concurrent uploads
    """
    import uuid
    import asyncio
    from services.upload_progress_tracker import get_tracker
    from routes.ui_upload_handler import safe_process_upload_with_tracking

    try:
        # SECURITY CHECK #1: Validate Content-Length BEFORE parsing JSON
        content_length = request.headers.get("content-length")
        if content_length:
            content_length_int = int(content_length)
            if content_length_int > MAX_UPLOAD_SIZE:
                logger.warning(f"Upload rejected: Content-Length {content_length_int} exceeds max {MAX_UPLOAD_SIZE}")
                raise HTTPException(
                    status_code=413,
                    detail=f"Payload too large: {content_length_int} bytes (max {MAX_UPLOAD_SIZE} bytes / {MAX_UPLOAD_SIZE // 1024 // 1024}MB)"
                )

        # Parse request body (with exception handling for invalid JSON)
        try:
            payload = await request.json()
        except ValueError as e:
            logger.warning(f"Upload rejected: Invalid JSON - {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON payload: {str(e)}"
            )

        # SECURITY CHECK #2: Validate repository name
        if not payload.get("repository"):
            raise HTTPException(400, "Repository name is required")

        repo_name = payload["repository"]
        if not isinstance(repo_name, str):
            raise HTTPException(400, "Repository name must be a string")

        if not REPOSITORY_NAME_PATTERN.match(repo_name):
            logger.warning(f"Upload rejected: Invalid repository name '{repo_name}'")
            raise HTTPException(
                400,
                f"Invalid repository name. Allowed characters: a-z A-Z 0-9 _ - . (max 255 chars). Got: '{repo_name}'"
            )

        # SECURITY CHECK #3: Validate files array
        if not payload.get("files"):
            raise HTTPException(400, "No files provided")

        if not isinstance(payload["files"], list):
            raise HTTPException(400, "Files must be an array")

        if len(payload["files"]) == 0:
            raise HTTPException(400, "Files array is empty")

        if len(payload["files"]) > MAX_FILES_PER_UPLOAD:
            logger.warning(f"Upload rejected: Too many files ({len(payload['files'])} > {MAX_FILES_PER_UPLOAD})")
            raise HTTPException(
                400,
                f"Too many files: {len(payload['files'])} files (max {MAX_FILES_PER_UPLOAD})"
            )

        # SECURITY CHECK #4: Validate each file structure (basic validation)
        for idx, file_data in enumerate(payload["files"]):
            if not isinstance(file_data, dict):
                raise HTTPException(400, f"File {idx}: must be an object")

            if "path" not in file_data or "content" not in file_data:
                raise HTTPException(400, f"File {idx}: missing 'path' or 'content' field")

            if not isinstance(file_data["path"], str):
                raise HTTPException(400, f"File {idx}: 'path' must be a string")

            if not isinstance(file_data["content"], str):
                raise HTTPException(400, f"File {idx}: 'content' must be a string")

            # Note: Path traversal validation is done in ui_upload_handler.validate_safe_path()
            # during processing, not here, to avoid double-validation overhead

        # SECURITY CHECK #5: Rate limiting - Check concurrent uploads
        tracker = get_tracker()

        # PHASE 2: Use async get_all_sessions() with await
        all_sessions = await tracker.get_all_sessions()
        active_sessions = [
            s for s in all_sessions
            if s.get("status") == "processing"
        ]

        if len(active_sessions) >= MAX_CONCURRENT_UPLOADS:
            logger.warning(
                f"Upload rejected: Too many active uploads ({len(active_sessions)} >= {MAX_CONCURRENT_UPLOADS})"
            )
            raise HTTPException(
                429,
                f"Too many active uploads ({len(active_sessions)}). Please wait and try again."
            )

        # Generate unique upload ID
        upload_id = str(uuid.uuid4())
        total_files = len(payload["files"])

        # Create progress tracker session (PHASE 2: now async)
        progress = await tracker.create_session(
            upload_id=upload_id,
            repository=repo_name,
            total_files=total_files
        )

        logger.info(
            f"[{upload_id}] Created upload session: {total_files} files for repository '{repo_name}' "
            f"(active uploads: {len(active_sessions) + 1}/{MAX_CONCURRENT_UPLOADS})"
        )

        # Get pre-loaded embedding service from app.state
        embedding_service = getattr(request.app.state, "embedding_service", None)
        if embedding_service:
            logger.info(f"[{upload_id}] Using pre-loaded embedding service from app.state")
        else:
            logger.warning(f"[{upload_id}] No pre-loaded embedding service, will create new instance")

        # Launch background processing task with SAFE wrapper
        asyncio.create_task(safe_process_upload_with_tracking(
            payload=payload,
            engine=engine,
            upload_id=upload_id,
            progress=progress,
            embedding_service=embedding_service
        ))

        logger.info(f"[{upload_id}] Background task launched successfully")

        # Return immediately with upload ID for polling
        return {
            "status": "processing",
            "upload_id": upload_id,
            "repository": repo_name,
            "total_files": total_files,
            "message": f"Upload processing started. Poll /ui/code/upload/status/{upload_id} for progress."
        }

    except HTTPException:
        # Re-raise HTTP exceptions (they're already formatted correctly)
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error starting upload: {e}", exc_info=True)
        raise HTTPException(
            500,
            f"Internal server error: {str(e)}"
        )



@router.get("/code/upload/status/{upload_id}")
async def code_upload_status(upload_id: str):
    """
    Get real-time progress status for an upload session (EPIC-09).

    Provides detailed progress information including:
    - Current file being processed
    - Pipeline stage breakdown
    - File counters (indexed, failed, total)
    - Elapsed time and estimated remaining time
    - Recent file activity
    - Error list (limited to 100)

    Used by frontend for polling-based progress updates.
    """
    from services.upload_progress_tracker import get_tracker

    try:
        tracker = get_tracker()

        # PHASE 2: get_session() is now async
        progress = await tracker.get_session(upload_id)

        if not progress:
            return {
                "error": "Upload session not found",
                "status": "not_found"
            }

        return progress.to_dict()

    except Exception as e:
        logger.error(f"Failed to get upload status for {upload_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/autosave", response_class=HTMLResponse)
async def autosave_dashboard(request: Request):
    """
    Dashboard de monitoring de l'auto-save des conversations.
    EPIC-24: Auto-Save Conversations - UI/UX
    """
    return templates.TemplateResponse(
        "autosave_dashboard.html",
        {"request": request}
    )
