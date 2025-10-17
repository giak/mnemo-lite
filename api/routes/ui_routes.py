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

from dependencies import get_event_repository, get_embedding_service, get_db_engine
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
        complexity_query = text("""
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
        # (same logic as EPIC-06 DELETE endpoint)
        delete_chunks = text("""
            DELETE FROM code_chunks
            WHERE repository = :repository
        """)

        delete_nodes = text("""
            DELETE FROM nodes
            WHERE props->>'repository' = :repository
        """)

        delete_edges = text("""
            DELETE FROM edges
            WHERE NOT EXISTS (
                SELECT 1 FROM nodes WHERE nodes.node_id = edges.source_node_id
            )
        """)

        async with engine.begin() as conn:
            result1 = await conn.execute(delete_chunks, {"repository": repository})
            result2 = await conn.execute(delete_nodes, {"repository": repository})
            result3 = await conn.execute(delete_edges)

        logger.info(
            f"Deleted repository '{repository}': "
            f"{result1.rowcount} chunks, {result2.rowcount} nodes, {result3.rowcount} orphaned edges"
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


@router.get("/code/search/results", response_class=HTMLResponse)
async def code_search_results(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    mode: str = Query("hybrid", description="Search mode: hybrid, lexical, vector"),
    repository: Optional[str] = Query(None, description="Filter by repository"),
    language: Optional[str] = Query(None, description="Filter by language"),
    chunk_type: Optional[str] = Query(None, description="Filter by chunk type"),
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
        # Fetch nodes
        nodes_query = text("""
            SELECT
                node_id,
                node_type,
                label,
                properties,
                created_at
            FROM nodes
            ORDER BY created_at DESC
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
                    "created_at": row[4].isoformat() if row[4] else None
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
    Code Upload Interface (EPIC-07 Story 4).

    Upload code files for indexing.
    """
    return templates.TemplateResponse(
        "code_upload.html",
        {"request": request}
    )


@router.post("/code/upload/process")
async def code_upload_process(
    request: Request,
    engine = Depends(get_db_engine)
):
    """
    Process code upload and index files (EPIC-07 Story 4).

    Receives files from drag & drop interface and calls the indexing API.
    """
    try:
        # Parse request body
        payload = await request.json()

        # Validate payload
        if not payload.get("repository"):
            return {"error": "Repository name is required"}

        if not payload.get("files"):
            return {"error": "No files provided"}

        # Call the indexing service directly (same pattern as API endpoint)
        from services.code_chunking_service import CodeChunkingService
        from services.metadata_extractor_service import MetadataExtractorService
        from services.dual_embedding_service import DualEmbeddingService
        from services.graph_construction_service import GraphConstructionService
        from db.repositories.code_chunk_repository import CodeChunkRepository
        from services.code_indexing_service import (
            CodeIndexingService,
            FileInput,
            IndexingOptions,
        )

        # Create service with dependencies
        chunking_service = CodeChunkingService()
        metadata_service = MetadataExtractorService()
        embedding_service = DualEmbeddingService()
        graph_service = GraphConstructionService(engine)
        chunk_repository = CodeChunkRepository(engine)

        indexing_service = CodeIndexingService(
            engine=engine,
            chunking_service=chunking_service,
            metadata_service=metadata_service,
            embedding_service=embedding_service,
            graph_service=graph_service,
            chunk_repository=chunk_repository,
        )

        # Convert request to service models
        files = [
            FileInput(
                path=f["path"],
                content=f["content"],
                language=f.get("language"),
            )
            for f in payload["files"]
        ]

        options = IndexingOptions(
            extract_metadata=payload.get("extract_metadata", True),
            generate_embeddings=payload.get("generate_embeddings", True),
            build_graph=payload.get("build_graph", True),
            repository=payload["repository"],
            commit_hash=payload.get("commit_hash"),
        )

        # Index files
        summary = await indexing_service.index_repository(files, options)

        # Return response
        return {
            "repository": summary.repository,
            "indexed_files": summary.indexed_files,
            "indexed_chunks": summary.indexed_chunks,
            "indexed_nodes": summary.indexed_nodes,
            "indexed_edges": summary.indexed_edges,
            "failed_files": summary.failed_files,
            "processing_time_ms": summary.processing_time_ms,
            "errors": summary.errors,
        }

    except Exception as e:
        logger.error(f"Code upload processing failed: {e}", exc_info=True)
        return {"error": str(e)}
