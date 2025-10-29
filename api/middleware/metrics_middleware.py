"""
EPIC-22 Story 22.1/22.5: Metrics Middleware

Records API request metrics:
- Latency (ms)
- Endpoint (normalized)
- Method
- Status code
- Trace ID (UUID)

Stores in PostgreSQL table `metrics` asynchronously.

Story 22.5: Added endpoint normalization to group dynamic paths:
- /api/users/123 → /api/users/:id
- /v1/events/abc-def-123 → /v1/events/:uuid
"""

import time
import uuid
import re
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = structlog.get_logger()


def normalize_endpoint(path: str) -> str:
    """
    Normalize endpoint paths to group dynamic IDs (EPIC-22 Story 22.5).

    Replaces dynamic segments with placeholders:
    - UUIDs → :uuid
    - Numeric IDs → :id
    - Hexadecimal hashes → :hash

    Examples:
        /api/users/123 → /api/users/:id
        /v1/events/550e8400-e29b-41d4-a716-446655440000 → /v1/events/:uuid
        /api/repos/my-repo-123 → /api/repos/my-repo-:id

    Args:
        path: Original endpoint path

    Returns:
        Normalized path with placeholders

    Note:
        - Preserves query parameters (not included in path)
        - Case-sensitive matching
        - Order matters: UUIDs checked before numeric IDs
    """
    # Replace UUIDs (8-4-4-4-12 format)
    path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/:uuid', path, flags=re.IGNORECASE)

    # Replace long hexadecimal hashes (32+ chars, like MD5/SHA256)
    path = re.sub(r'/[0-9a-f]{32,}', '/:hash', path, flags=re.IGNORECASE)

    # Replace numeric IDs (pure digits)
    path = re.sub(r'/\d+', '/:id', path)

    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to record API metrics.

    For each request:
    1. Generate trace_id (UUID)
    2. Measure latency
    3. Store in metrics table (async batch insert)
    4. Add X-Trace-ID header to response
    """

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Generate trace_id
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

        # EPIC-22 Story 22.6: Set trace_id in contextvars for automatic log propagation
        from utils.logging_config import trace_id_var
        trace_id_var.set(trace_id)

        # Start timer
        start_time = time.perf_counter()

        # Process request
        response: Response = await call_next(request)

        # Calculate latency
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Add trace_id to response headers
        response.headers["X-Trace-ID"] = trace_id

        # Record metric (async, non-blocking)
        try:
            # Normalize endpoint to group dynamic IDs (Story 22.5)
            normalized_endpoint = normalize_endpoint(request.url.path)

            await self._record_metric(
                request=request,
                trace_id=trace_id,
                endpoint=normalized_endpoint,
                method=request.method,
                status_code=response.status_code,
                latency_ms=latency_ms
            )
        except Exception as e:
            # Don't fail request if metric recording fails
            logger.warning(
                "Failed to record metric",
                trace_id=trace_id,
                error=str(e)
            )

        return response

    async def _record_metric(
        self,
        request: Request,
        trace_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float
    ):
        """
        Insert metric into PostgreSQL.

        Metadata stores: endpoint, method, status_code, trace_id
        """
        # Skip health check endpoints (too noisy)
        if endpoint in ["/health", "/api/health", "/metrics"]:
            return

        # Get engine from app.state (set during lifespan)
        engine = getattr(request.app.state, "db_engine", None)
        if engine is None:
            logger.debug("DB engine not available, skipping metric recording")
            return

        # Build metadata as JSONB
        import json
        metadata = json.dumps({
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "trace_id": trace_id
        })

        async with engine.begin() as conn:
            query = text("""
                INSERT INTO metrics (metric_type, metric_name, value, metadata)
                VALUES ('api', 'latency_ms', :latency_ms, CAST(:metadata AS jsonb))
            """)

            await conn.execute(query, {
                "latency_ms": latency_ms,
                "metadata": metadata
            })
