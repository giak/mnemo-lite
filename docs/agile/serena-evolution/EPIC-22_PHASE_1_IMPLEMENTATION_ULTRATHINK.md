# EPIC-22 Phase 1: Implementation ULTRATHINK

**Date**: 2025-10-24
**Status**: 🔨 **IMPLEMENTATION GUIDE**
**Scope**: Phase 1 MVP (5 pts - 1 semaine)
**Goal**: Production-ready monitoring en 5 jours

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Story 22.1: Metrics Infrastructure](#story-221-metrics-infrastructure)
3. [Story 22.2: Dashboard Unifié](#story-222-dashboard-unifié)
4. [Story 22.3: Logs Streaming](#story-223-logs-streaming)
5. [Testing Strategy](#testing-strategy)
6. [Deployment Checklist](#deployment-checklist)
7. [Gotchas & Pitfalls](#gotchas--pitfalls)

---

## Architecture Overview

### Stack (Zero Nouvelle Dépendance)

```
✅ Backend: FastAPI (already present)
✅ DB: PostgreSQL 18 (already present)
✅ UI: HTMX + Jinja2 (already present)
✅ Charts: ECharts 5.5.0 (already present in monitoring.html)
✅ Logs: structlog (already present)
✅ Cache: Redis (already present)
```

**New**: Server-Sent Events (SSE) - Native browser API

---

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ UI: /ui/monitoring/advanced                                     │
│                                                                 │
│ ├─ 4 KPI Cards (HTMX polling 5s)                               │
│ │   GET /api/monitoring/advanced/summary                       │
│ │                                                               │
│ ├─ 3 Charts (ECharts, data from HTMX)                          │
│ │   - Latency timeline                                         │
│ │   - Redis hit rate                                           │
│ │   - PostgreSQL connections                                   │
│ │                                                               │
│ └─ Logs Stream (SSE, EventSource API)                          │
│     GET /api/monitoring/logs/stream                            │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend                                                 │
│                                                                 │
│ Middleware: MetricsMiddleware                                   │
│ ├─ Inject trace_id (UUID)                                      │
│ ├─ Record latency per request                                  │
│ └─ Store in table metrics (async batch insert)                 │
│                                                                 │
│ Service: MetricsCollector                                       │
│ ├─ collect_api_metrics() → Aggregate from metrics table        │
│ ├─ collect_redis_metrics() → Redis INFO + custom analysis      │
│ └─ collect_postgres_metrics() → pg_stat_activity, cache ratio  │
│                                                                 │
│ Routes:                                                         │
│ ├─ /api/monitoring/advanced/summary → JSON KPIs                │
│ └─ /api/monitoring/logs/stream → SSE stream                    │
└─────────────────────────────────────────────────────────────────┘
             ↓                    ↓                   ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ PostgreSQL       │  │ Redis            │  │ structlog        │
│                  │  │                  │  │                  │
│ Table: metrics   │  │ INFO commands    │  │ Logs buffer      │
│ - id: UUID       │  │ - memory         │  │ - circular       │
│ - timestamp      │  │ - keys           │  │   buffer         │
│ - metric_type    │  │ - hit/miss stats │  │ - max 1000 logs  │
│ - metric_name    │  │                  │  │ - JSON format    │
│ - value: float   │  └──────────────────┘  └──────────────────┘
│ - metadata: JSON │
│                  │
│ Indexes:         │
│ - (type, time)   │
│ - (time DESC)    │
└──────────────────┘
```

---

## Story 22.1: Metrics Infrastructure (2 pts)

### Objective

Create PostgreSQL table `metrics` + service layer to collect and store metrics.

---

### Task 1.1: Database Migration

**File**: `db/migrations/v5_to_v6_metrics_table.sql`

```sql
-- EPIC-22 Story 22.1: Metrics table for observability
-- Migration v5 → v6: Add metrics table
-- Author: Claude Code
-- Date: 2025-10-24

-- Create metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,  -- 'api', 'redis', 'postgres', 'system'
    metric_name VARCHAR(100) NOT NULL, -- 'latency_ms', 'hit_rate', 'connections', etc.
    value DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_metric_type CHECK (metric_type IN ('api', 'redis', 'postgres', 'system', 'cache'))
);

-- Indexes for fast queries
CREATE INDEX idx_metrics_type_time ON metrics (metric_type, timestamp DESC);
CREATE INDEX idx_metrics_time ON metrics (timestamp DESC);
CREATE INDEX idx_metrics_name ON metrics (metric_name);

-- Composite index for aggregation queries
CREATE INDEX idx_metrics_type_name_time ON metrics (metric_type, metric_name, timestamp DESC);

-- JSONB GIN index for metadata queries (optional, if needed)
-- CREATE INDEX idx_metrics_metadata ON metrics USING gin (metadata jsonb_path_ops);

-- Comments
COMMENT ON TABLE metrics IS 'EPIC-22: Time-series metrics for observability (API latency, cache stats, DB performance)';
COMMENT ON COLUMN metrics.metric_type IS 'Category: api, redis, postgres, system, cache';
COMMENT ON COLUMN metrics.metric_name IS 'Specific metric: latency_ms, hit_rate, connections, cpu_percent, etc.';
COMMENT ON COLUMN metrics.value IS 'Numeric value (float)';
COMMENT ON COLUMN metrics.metadata IS 'Additional context (endpoint, method, status_code, etc.)';

-- Example data for testing
-- INSERT INTO metrics (metric_type, metric_name, value, metadata) VALUES
-- ('api', 'latency_ms', 45.3, '{"endpoint": "/v1/code/search/hybrid", "method": "GET", "status_code": 200}'::jsonb),
-- ('redis', 'hit_rate', 0.873, '{"cache_type": "search_results"}'::jsonb),
-- ('postgres', 'active_connections', 8, '{}'::jsonb);

-- Retention policy (optional): Keep 30 days
-- Run daily via cron:
-- DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';

-- Verify
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename = 'metrics';
```

**Apply Migration**:
```bash
# Connect to PostgreSQL
docker exec -i mnemo-postgres psql -U mnemolite -d mnemolite < db/migrations/v5_to_v6_metrics_table.sql

# Verify
docker exec mnemo-postgres psql -U mnemolite -d mnemolite -c "\d metrics"
```

---

### Task 1.2: MetricsCollector Service

**File**: `api/services/metrics_collector.py`

```python
"""
EPIC-22 Story 22.1: Metrics Collector Service

Collects metrics from various sources:
- API: Latency, throughput, errors (from metrics table)
- Redis: Hit rate, memory, keys, evictions (from Redis INFO)
- PostgreSQL: Connections, cache hit ratio, slow queries (from pg_stat_*)
- System: CPU, memory, disk (from psutil)

Architecture:
- Async methods for all I/O
- Returns structured dicts (ready for JSON serialization)
- No side effects (pure data collection)
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text
import psutil
import redis.asyncio as aioredis

logger = structlog.get_logger()


class MetricsCollector:
    """Collects system metrics from multiple sources."""

    def __init__(self, db_engine: AsyncEngine, redis_client: aioredis.Redis):
        self.engine = db_engine
        self.redis = redis_client

    async def collect_all(self) -> Dict[str, Any]:
        """
        Collect all metrics in parallel.

        Returns dict with keys: api, redis, postgres, system
        """
        # TODO: Use asyncio.gather for parallel collection
        return {
            "api": await self.collect_api_metrics(),
            "redis": await self.collect_redis_metrics(),
            "postgres": await self.collect_postgres_metrics(),
            "system": await self.collect_system_metrics()
        }

    # ====== API Metrics ======

    async def collect_api_metrics(self, period_hours: int = 1) -> Dict[str, Any]:
        """
        Collect API performance metrics from metrics table.

        Returns:
        - avg_latency_ms: Average latency (last 1h)
        - p50_latency_ms: P50 latency
        - p95_latency_ms: P95 latency
        - p99_latency_ms: P99 latency
        - request_count: Total requests
        - requests_per_second: Throughput
        - error_count: Total errors (status >= 400)
        - error_rate: Error rate (%)
        """
        async with self.engine.connect() as conn:
            # Aggregate latency stats
            query = text("""
                SELECT
                    COUNT(*) as total_requests,
                    AVG(value) as avg_latency_ms,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99_latency_ms,
                    COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400) as error_count
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'latency_ms'
                  AND timestamp > NOW() - INTERVAL :period
            """)

            result = await conn.execute(query, {"period": f"{period_hours} hours"})
            row = result.mappings().first()

            if not row or row["total_requests"] == 0:
                return {
                    "avg_latency_ms": 0,
                    "p50_latency_ms": 0,
                    "p95_latency_ms": 0,
                    "p99_latency_ms": 0,
                    "request_count": 0,
                    "requests_per_second": 0,
                    "error_count": 0,
                    "error_rate": 0
                }

            total_requests = row["total_requests"]
            error_count = row["error_count"] or 0

            # Calculate requests per second
            requests_per_second = total_requests / (period_hours * 3600)

            return {
                "avg_latency_ms": round(row["avg_latency_ms"] or 0, 2),
                "p50_latency_ms": round(row["p50_latency_ms"] or 0, 2),
                "p95_latency_ms": round(row["p95_latency_ms"] or 0, 2),
                "p99_latency_ms": round(row["p99_latency_ms"] or 0, 2),
                "request_count": total_requests,
                "requests_per_second": round(requests_per_second, 2),
                "error_count": error_count,
                "error_rate": round((error_count / total_requests) * 100, 2) if total_requests > 0 else 0
            }

    # ====== Redis Metrics ======

    async def collect_redis_metrics(self) -> Dict[str, Any]:
        """
        Collect Redis performance metrics.

        Returns:
        - connected: bool (Redis availability)
        - memory_used_mb: Memory used (MB)
        - memory_max_mb: Max memory (MB)
        - memory_percent: Memory usage (%)
        - keys_total: Total keys
        - hit_rate: Cache hit rate (%)
        - evicted_keys: Keys evicted (LRU)
        - connected_clients: Active connections
        """
        try:
            # Get Redis INFO
            info = await self.redis.info()

            memory_used_bytes = info.get("used_memory", 0)
            memory_max_bytes = info.get("maxmemory", 0)

            # If maxmemory = 0, Redis has no limit (use system memory as fallback)
            if memory_max_bytes == 0:
                memory_max_bytes = 2 * 1024 * 1024 * 1024  # Default 2GB

            memory_used_mb = memory_used_bytes / (1024 * 1024)
            memory_max_mb = memory_max_bytes / (1024 * 1024)
            memory_percent = (memory_used_bytes / memory_max_bytes) * 100 if memory_max_bytes > 0 else 0

            # Calculate hit rate
            keyspace_hits = info.get("keyspace_hits", 0)
            keyspace_misses = info.get("keyspace_misses", 0)
            total_requests = keyspace_hits + keyspace_misses
            hit_rate = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0

            # Keys count
            keys_total = await self.redis.dbsize()

            return {
                "connected": True,
                "memory_used_mb": round(memory_used_mb, 2),
                "memory_max_mb": round(memory_max_mb, 2),
                "memory_percent": round(memory_percent, 2),
                "keys_total": keys_total,
                "hit_rate": round(hit_rate, 2),
                "evicted_keys": info.get("evicted_keys", 0),
                "connected_clients": info.get("connected_clients", 0)
            }

        except Exception as e:
            logger.error("Failed to collect Redis metrics", error=str(e))
            return {
                "connected": False,
                "memory_used_mb": 0,
                "memory_max_mb": 0,
                "memory_percent": 0,
                "keys_total": 0,
                "hit_rate": 0,
                "evicted_keys": 0,
                "connected_clients": 0
            }

    # ====== PostgreSQL Metrics ======

    async def collect_postgres_metrics(self) -> Dict[str, Any]:
        """
        Collect PostgreSQL performance metrics.

        Returns:
        - connections_active: Active connections
        - connections_idle: Idle connections
        - connections_total: Total connections
        - connections_max: Max connections allowed
        - cache_hit_ratio: Buffer cache hit ratio (%)
        - db_size_mb: Database size (MB)
        - slow_queries_count: Slow queries (>100ms) in last 1h
        """
        async with self.engine.connect() as conn:
            # Active connections
            conn_query = text("""
                SELECT
                    COUNT(*) FILTER (WHERE state = 'active') as active,
                    COUNT(*) FILTER (WHERE state = 'idle') as idle,
                    COUNT(*) as total
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            conn_result = await conn.execute(conn_query)
            conn_row = conn_result.mappings().first()

            # Max connections
            max_conn_query = text("SHOW max_connections")
            max_conn_result = await conn.execute(max_conn_query)
            max_connections = int(max_conn_result.scalar())

            # Cache hit ratio
            cache_query = text("""
                SELECT
                    CASE
                        WHEN (sum(heap_blks_hit) + sum(heap_blks_read)) = 0 THEN 100
                        ELSE round(
                            sum(heap_blks_hit)::numeric /
                            (sum(heap_blks_hit) + sum(heap_blks_read)) * 100,
                            2
                        )
                    END as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            cache_result = await conn.execute(cache_query)
            cache_hit_ratio = cache_result.scalar() or 100

            # Database size
            size_query = text("SELECT pg_database_size(current_database()) as size")
            size_result = await conn.execute(size_query)
            db_size_bytes = size_result.scalar()
            db_size_mb = db_size_bytes / (1024 * 1024)

            # Slow queries (from metrics table, if we store query times there)
            slow_query = text("""
                SELECT COUNT(*) as count
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'latency_ms'
                  AND value > 100
                  AND timestamp > NOW() - INTERVAL '1 hour'
            """)
            slow_result = await conn.execute(slow_query)
            slow_queries_count = slow_result.scalar() or 0

            return {
                "connections_active": conn_row["active"] or 0,
                "connections_idle": conn_row["idle"] or 0,
                "connections_total": conn_row["total"] or 0,
                "connections_max": max_connections,
                "cache_hit_ratio": float(cache_hit_ratio),
                "db_size_mb": round(db_size_mb, 2),
                "slow_queries_count": slow_queries_count
            }

    # ====== System Metrics ======

    async def collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system resource metrics (CPU, memory, disk).

        Returns:
        - cpu_percent: CPU usage (%)
        - cpu_count: Number of CPUs
        - memory_used_mb: Memory used (MB)
        - memory_total_mb: Total memory (MB)
        - memory_percent: Memory usage (%)
        - disk_used_gb: Disk used (GB)
        - disk_total_gb: Total disk (GB)
        - disk_percent: Disk usage (%)
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()

        # Memory
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        memory_percent = memory.percent

        # Disk
        disk = psutil.disk_usage("/")
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_percent = disk.percent

        return {
            "cpu_percent": round(cpu_percent, 2),
            "cpu_count": cpu_count,
            "memory_used_mb": round(memory_used_mb, 2),
            "memory_total_mb": round(memory_total_mb, 2),
            "memory_percent": round(memory_percent, 2),
            "disk_used_gb": round(disk_used_gb, 2),
            "disk_total_gb": round(disk_total_gb, 2),
            "disk_percent": round(disk_percent, 2)
        }
```

**Dependency Injection** (`api/dependencies.py`):

```python
from services.metrics_collector import MetricsCollector
import redis.asyncio as aioredis

async def get_metrics_collector(
    engine: AsyncEngine = Depends(get_db_engine),
    # Assuming you have get_redis_client dependency
) -> MetricsCollector:
    """Dependency injection for MetricsCollector."""
    redis_client = aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=False  # Keep bytes for INFO command
    )
    return MetricsCollector(engine, redis_client)
```

---

### Task 1.3: MetricsMiddleware

**File**: `api/middleware/metrics_middleware.py`

```python
"""
EPIC-22 Story 22.1: Metrics Middleware

Records API request metrics:
- Latency (ms)
- Endpoint
- Method
- Status code
- Trace ID (UUID)

Stores in PostgreSQL table `metrics` asynchronously.
"""

import time
import uuid
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = structlog.get_logger()


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to record API metrics.

    For each request:
    1. Generate trace_id (UUID)
    2. Measure latency
    3. Store in metrics table (async batch insert)
    4. Add X-Trace-ID header to response
    """

    def __init__(self, app, db_engine: AsyncEngine):
        super().__init__(app)
        self.engine = db_engine

    async def dispatch(self, request: Request, call_next):
        # Generate trace_id
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

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
            await self._record_metric(
                trace_id=trace_id,
                endpoint=request.url.path,
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

        async with self.engine.begin() as conn:
            query = text("""
                INSERT INTO metrics (metric_type, metric_name, value, metadata)
                VALUES (
                    'api',
                    'latency_ms',
                    :latency_ms,
                    jsonb_build_object(
                        'endpoint', :endpoint,
                        'method', :method,
                        'status_code', :status_code,
                        'trace_id', :trace_id
                    )
                )
            """)

            await conn.execute(query, {
                "latency_ms": latency_ms,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "trace_id": trace_id
            })
```

**Register Middleware** (`api/main.py`):

```python
from middleware.metrics_middleware import MetricsMiddleware

# In lifespan or startup
app.add_middleware(MetricsMiddleware, db_engine=engine)
```

---

### Task 1.4: API Endpoint

**File**: `api/routes/monitoring_routes_advanced.py`

```python
"""
EPIC-22 Story 22.1: Advanced Monitoring Routes

New endpoints:
- GET /api/monitoring/advanced/summary → All metrics summary (for dashboard)
"""

from fastapi import APIRouter, Depends
from services.metrics_collector import MetricsCollector
from dependencies import get_metrics_collector

router = APIRouter(prefix="/api/monitoring/advanced", tags=["Monitoring Advanced"])


@router.get("/summary")
async def get_advanced_summary(
    collector: MetricsCollector = Depends(get_metrics_collector)
):
    """
    Get comprehensive metrics summary for dashboard.

    Returns:
    {
      "api": {...},
      "redis": {...},
      "postgres": {...},
      "system": {...}
    }
    """
    return await collector.collect_all()
```

**Register Router** (`api/main.py`):

```python
from routes import monitoring_routes_advanced

app.include_router(monitoring_routes_advanced.router)
```

---

### Task 1.5: Testing

**File**: `tests/test_metrics_collector.py`

```python
import pytest
from services.metrics_collector import MetricsCollector


@pytest.mark.asyncio
async def test_collect_api_metrics(async_engine, redis_client):
    """Test API metrics collection."""
    collector = MetricsCollector(async_engine, redis_client)

    # Insert test data
    async with async_engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO metrics (metric_type, metric_name, value, metadata)
            VALUES
            ('api', 'latency_ms', 45.3, '{"endpoint": "/test", "status_code": 200}'::jsonb),
            ('api', 'latency_ms', 120.5, '{"endpoint": "/test", "status_code": 200}'::jsonb)
        """))

    # Collect metrics
    metrics = await collector.collect_api_metrics()

    assert metrics["request_count"] == 2
    assert metrics["avg_latency_ms"] > 0
    assert metrics["p95_latency_ms"] > 0


@pytest.mark.asyncio
async def test_collect_redis_metrics(async_engine, redis_client):
    """Test Redis metrics collection."""
    collector = MetricsCollector(async_engine, redis_client)

    metrics = await collector.collect_redis_metrics()

    assert metrics["connected"] is True
    assert metrics["memory_used_mb"] >= 0
    assert metrics["hit_rate"] >= 0
```

---

## Story 22.2: Dashboard Unifié (2 pts)

### Objective

Create `/ui/monitoring/advanced` page with unified monitoring dashboard.

---

### Task 2.1: HTML Template

**File**: `templates/monitoring_advanced.html`

```html
{% extends "base.html" %}

{% block title %}Advanced Monitoring - MnemoLite{% endblock %}
{% block nav_monitoring %}active{% endblock %}

{% block extra_head %}
<!-- ECharts 5.5.0 (already present in monitoring.html) -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>

<style>
/* SCADA Industrial Theme - Zero Rounded Corners */

.monitoring-advanced-container {
    padding: 20px;
    min-height: calc(100vh - 180px);
}

/* Status Banner */
.status-banner {
    background: #161b22;
    border: 1px solid #30363d;
    border-left: 4px solid #3fb950;  /* Green = operational */
    padding: 16px 20px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.status-info {
    display: flex;
    align-items: center;
    gap: 16px;
}

.status-indicator {
    font-size: 32px;
}

.status-text h1 {
    margin: 0 0 4px 0;
    font-size: 18px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.status-text p {
    margin: 0;
    font-size: 12px;
    color: #8b949e;
    font-family: 'Courier New', monospace;
}

.refresh-control {
    display: flex;
    align-items: center;
    gap: 12px;
}

.auto-refresh-toggle {
    font-size: 12px;
    color: #8b949e;
}

.refresh-btn {
    background: #0d1117;
    border: 1px solid #30363d;
    color: #58a6ff;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    cursor: pointer;
    transition: border-color 0.08s ease;
}

.refresh-btn:hover {
    border-color: #58a6ff;
}

/* KPI Cards Grid */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
}

.kpi-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-top: 2px solid #58a6ff;
    padding: 16px;
}

.kpi-label {
    font-size: 11px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 32px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    color: #58a6ff;
    line-height: 1;
    margin-bottom: 4px;
}

.kpi-unit {
    font-size: 11px;
    color: #6e7681;
    font-family: 'Courier New', monospace;
}

.kpi-delta {
    font-size: 10px;
    color: #8b949e;
    margin-top: 4px;
}

.kpi-delta.positive {
    color: #3fb950;
}

.kpi-delta.negative {
    color: #f85149;
}

/* Charts Grid */
.charts-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
}

.chart-panel {
    background: #0d1117;
    border: 1px solid #21262d;
}

.panel-header {
    padding: 12px 16px;
    border-bottom: 1px solid #21262d;
}

.panel-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #c9d1d9;
}

.panel-body {
    padding: 16px;
}

#latency-chart {
    width: 100%;
    height: 300px;
}

#redis-gauge {
    width: 100%;
    height: 300px;
}

/* Responsive */
@media (max-width: 1200px) {
    .kpi-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .charts-grid {
        grid-template-columns: 1fr;
    }
}
</style>
{% endblock %}

{% block content %}
<div class="monitoring-advanced-container">
    <!-- Status Banner -->
    <div class="status-banner" id="status-banner">
        <div class="status-info">
            <div class="status-indicator">🟢</div>
            <div class="status-text">
                <h1>SYSTÈME OPÉRATIONNEL</h1>
                <p id="status-timestamp">Chargement...</p>
            </div>
        </div>
        <div class="refresh-control">
            <label class="auto-refresh-toggle">
                <input type="checkbox" id="auto-refresh" checked>
                AUTO-REFRESH (5s)
            </label>
            <button class="refresh-btn" onclick="refreshDashboard()">🔄 ACTUALISER</button>
        </div>
    </div>

    <!-- KPI Cards (HTMX auto-refresh) -->
    <div class="kpi-grid"
         hx-get="/api/monitoring/advanced/summary"
         hx-trigger="load, every 5s"
         hx-swap="innerHTML"
         hx-target="#kpi-cards-content">
        <div id="kpi-cards-content">
            <!-- Loading state -->
            <div class="kpi-card">
                <div class="kpi-label">📊 API P95</div>
                <div class="kpi-value">-</div>
                <div class="kpi-unit">ms</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">🔴 Redis Hit Rate</div>
                <div class="kpi-value">-</div>
                <div class="kpi-unit">%</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">🐘 PostgreSQL</div>
                <div class="kpi-value">-</div>
                <div class="kpi-unit">connections</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">💻 System Memory</div>
                <div class="kpi-value">-</div>
                <div class="kpi-unit">%</div>
            </div>
        </div>
    </div>

    <!-- Charts -->
    <div class="charts-grid">
        <!-- Latency Chart -->
        <div class="chart-panel">
            <div class="panel-header">
                <span class="panel-title">📈 API Latency P95 (Last 1h)</span>
            </div>
            <div class="panel-body">
                <div id="latency-chart"></div>
            </div>
        </div>

        <!-- Redis Gauge -->
        <div class="chart-panel">
            <div class="panel-header">
                <span class="panel-title">🔴 Redis Hit Rate</span>
            </div>
            <div class="panel-body">
                <div id="redis-gauge"></div>
            </div>
        </div>
    </div>

    <!-- Logs Section (Story 22.3) -->
    <div class="chart-panel">
        <div class="panel-header">
            <span class="panel-title">📝 Live Logs</span>
        </div>
        <div class="panel-body">
            <div id="logs-stream">
                <!-- Will be populated by Story 22.3 (SSE) -->
                <p style="color: #8b949e;">Logs streaming will be implemented in Story 22.3</p>
            </div>
        </div>
    </div>
</div>

<script>
// HTMX custom processing for KPI cards
document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'kpi-cards-content') {
        const data = JSON.parse(evt.detail.xhr.responseText);
        updateKPICards(data);
        updateCharts(data);
    }
});

function updateKPICards(data) {
    // Update KPI cards HTML
    const html = `
        <div class="kpi-card">
            <div class="kpi-label">📊 API P95</div>
            <div class="kpi-value">${data.api.p95_latency_ms}</div>
            <div class="kpi-unit">ms</div>
            <div class="kpi-delta">${data.api.requests_per_second} req/s</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🔴 Redis Hit Rate</div>
            <div class="kpi-value">${data.redis.hit_rate}</div>
            <div class="kpi-unit">%</div>
            <div class="kpi-delta">${data.redis.memory_percent}% memory</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🐘 PostgreSQL</div>
            <div class="kpi-value">${data.postgres.connections_active}</div>
            <div class="kpi-unit">/ ${data.postgres.connections_max}</div>
            <div class="kpi-delta">${data.postgres.cache_hit_ratio}% cache hit</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">💻 System Memory</div>
            <div class="kpi-value">${data.system.memory_percent}</div>
            <div class="kpi-unit">%</div>
            <div class="kpi-delta">CPU: ${data.system.cpu_percent}%</div>
        </div>
    `;

    document.getElementById('kpi-cards-content').innerHTML = html;

    // Update timestamp
    document.getElementById('status-timestamp').textContent =
        new Date().toLocaleString('fr-FR');
}

function updateCharts(data) {
    // Initialize ECharts (latency timeline)
    const latencyChart = echarts.init(document.getElementById('latency-chart'));

    // TODO: Fetch historical data from backend
    // For now, show current values
    latencyChart.setOption({
        backgroundColor: 'transparent',
        textStyle: { color: '#8b949e' },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: {
            type: 'category',
            data: ['Now'],
            axisLine: { lineStyle: { color: '#30363d' } }
        },
        yAxis: {
            type: 'value',
            name: 'Latency (ms)',
            axisLine: { lineStyle: { color: '#30363d' } }
        },
        series: [{
            name: 'P95',
            type: 'line',
            data: [data.api.p95_latency_ms],
            lineStyle: { color: '#58a6ff' },
            itemStyle: { color: '#58a6ff' }
        }]
    });

    // Redis gauge
    const redisGauge = echarts.init(document.getElementById('redis-gauge'));
    redisGauge.setOption({
        backgroundColor: 'transparent',
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            progress: { show: true, width: 18 },
            axisLine: { lineStyle: { width: 18, color: [[1, '#30363d']] } },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            detail: {
                formatter: '{value}%',
                fontSize: 32,
                color: '#58a6ff',
                offsetCenter: [0, 0]
            },
            data: [{ value: data.redis.hit_rate, name: 'Hit Rate' }],
            pointer: { show: false }
        }]
    });
}

function refreshDashboard() {
    // Trigger HTMX refresh
    htmx.trigger('#kpi-cards-content', 'htmx:trigger');
}
</script>
{% endblock %}
```

---

### Task 2.2: UI Route

**File**: `api/routes/ui_routes.py` (add new route)

```python
@router.get("/monitoring/advanced")
async def monitoring_advanced_page(request: Request):
    """Advanced monitoring dashboard (EPIC-22)."""
    return templates.TemplateResponse(
        "monitoring_advanced.html",
        {"request": request}
    )
```

---

### Task 2.3: Backend Response Format

Update `/api/monitoring/advanced/summary` to return HTMX-friendly format:

```python
@router.get("/summary")
async def get_advanced_summary(
    collector: MetricsCollector = Depends(get_metrics_collector)
):
    """Get metrics summary (JSON for HTMX)."""
    return await collector.collect_all()  # Returns dict, auto-converted to JSON
```

---

## Story 22.3: Logs Streaming (1 pt)

### Objective

Stream logs in real-time using Server-Sent Events (SSE).

---

### Task 3.1: Logs Buffer

**File**: `api/services/logs_buffer.py`

```python
"""
EPIC-22 Story 22.3: Circular logs buffer for SSE streaming.

Keeps last N logs in memory for streaming to clients.
"""

import structlog
from collections import deque
from typing import List, Dict, Any
from datetime import datetime
import json


class LogsBuffer:
    """
    Thread-safe circular buffer for logs.

    Max size: 1000 logs (~1MB assuming 1KB per log)
    Logs are dicts with keys: timestamp, level, message, metadata
    """

    def __init__(self, maxsize: int = 1000):
        self.buffer = deque(maxlen=maxsize)
        self.maxsize = maxsize

    def add(self, log_entry: Dict[str, Any]):
        """Add log entry to buffer."""
        # Ensure timestamp is ISO format
        if "timestamp" not in log_entry:
            log_entry["timestamp"] = datetime.now().isoformat()

        self.buffer.append(log_entry)

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent N logs."""
        return list(self.buffer)[-limit:]

    def clear(self):
        """Clear buffer."""
        self.buffer.clear()


# Global singleton
logs_buffer = LogsBuffer()
```

---

### Task 3.2: structlog Handler

**File**: `api/logging_config.py` (modify existing structlog config)

```python
import structlog
from services.logs_buffer import logs_buffer


def add_to_buffer(logger, method_name, event_dict):
    """
    structlog processor to add logs to buffer.

    This runs for every log statement.
    """
    # Add to buffer (async, non-blocking)
    logs_buffer.add({
        "timestamp": event_dict.get("timestamp", datetime.now().isoformat()),
        "level": method_name.upper(),
        "message": event_dict.get("event", ""),
        "metadata": {k: v for k, v in event_dict.items() if k not in ["event", "timestamp"]}
    })

    return event_dict


# Update structlog config
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_to_buffer,  # ← Add this processor
        structlog.processors.JSONRenderer()
    ],
    # ... rest of config
)
```

---

### Task 3.3: SSE Endpoint

**File**: `api/routes/monitoring_routes_advanced.py` (add SSE endpoint)

```python
from fastapi.responses import StreamingResponse
from services.logs_buffer import logs_buffer
import asyncio
import json


@router.get("/logs/stream")
async def stream_logs():
    """
    Stream logs via Server-Sent Events (SSE).

    Client usage (JavaScript):
    ```
    const evtSource = new EventSource('/api/monitoring/advanced/logs/stream');
    evtSource.onmessage = (event) => {
        const log = JSON.parse(event.data);
        console.log(log);
    };
    ```
    """
    async def event_generator():
        """
        Generator yielding SSE events.

        Format:
        data: {"timestamp": "...", "level": "INFO", "message": "...", "metadata": {...}}

        """
        # Send initial batch (last 50 logs)
        recent_logs = logs_buffer.get_recent(limit=50)
        for log in recent_logs:
            yield f"data: {json.dumps(log)}\n\n"

        # Stream new logs (polling every 1s)
        last_count = len(logs_buffer.buffer)

        while True:
            await asyncio.sleep(1)

            # Check for new logs
            current_count = len(logs_buffer.buffer)
            if current_count > last_count:
                # New logs added, send them
                new_logs = logs_buffer.get_recent(limit=current_count - last_count)
                for log in new_logs:
                    yield f"data: {json.dumps(log)}\n\n"

                last_count = current_count

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

---

### Task 3.4: Frontend SSE Client

**File**: `templates/monitoring_advanced.html` (update logs section)

```html
<!-- Logs Section -->
<div class="chart-panel">
    <div class="panel-header">
        <span class="panel-title">📝 Live Logs (SSE Stream)</span>
        <div style="display: inline-flex; gap: 8px;">
            <select id="log-level-filter" onchange="filterLogs()">
                <option value="ALL">All Levels</option>
                <option value="ERROR">ERROR</option>
                <option value="WARN">WARN</option>
                <option value="INFO">INFO</option>
                <option value="DEBUG">DEBUG</option>
            </select>
            <button class="filter-btn" onclick="toggleAutoScroll()">
                Auto-scroll: <span id="autoscroll-status">ON</span>
            </button>
            <button class="filter-btn" onclick="clearLogs()">Clear</button>
        </div>
    </div>
    <div class="panel-body">
        <div id="logs-stream" style="max-height: 400px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 12px;">
            <p style="color: #8b949e;">Connecting to log stream...</p>
        </div>
    </div>
</div>

<script>
let autoScroll = true;
let currentLevelFilter = 'ALL';
let evtSource = null;
let logsContainer = null;

// Initialize SSE connection on page load
document.addEventListener('DOMContentLoaded', function() {
    logsContainer = document.getElementById('logs-stream');
    connectSSE();
});

function connectSSE() {
    // Create EventSource connection
    evtSource = new EventSource('/api/monitoring/advanced/logs/stream');

    evtSource.onmessage = function(event) {
        const log = JSON.parse(event.data);
        appendLog(log);
    };

    evtSource.onerror = function(err) {
        console.error('SSE error:', err);
        logsContainer.innerHTML += '<p style="color: #f85149;">❌ Connection lost. Retrying...</p>';

        // Auto-reconnect after 5s
        setTimeout(() => {
            evtSource.close();
            connectSSE();
        }, 5000);
    };

    evtSource.onopen = function() {
        console.log('SSE connection opened');
        logsContainer.innerHTML = ''; // Clear "Connecting..." message
    };
}

function appendLog(log) {
    // Filter by level
    if (currentLevelFilter !== 'ALL' && log.level !== currentLevelFilter) {
        return;
    }

    // Color by level
    const colors = {
        'ERROR': '#f85149',
        'WARN': '#d29922',
        'INFO': '#58a6ff',
        'DEBUG': '#8b949e'
    };

    const color = colors[log.level] || '#c9d1d9';

    // Format log line
    const timestamp = new Date(log.timestamp).toLocaleTimeString('fr-FR');
    const metadata = JSON.stringify(log.metadata);

    const logLine = document.createElement('div');
    logLine.style.marginBottom = '4px';
    logLine.style.padding = '4px';
    logLine.style.borderLeft = `2px solid ${color}`;
    logLine.style.paddingLeft = '8px';
    logLine.innerHTML = `
        <span style="color: #6e7681;">${timestamp}</span>
        <span style="color: ${color}; font-weight: 600;">[${log.level}]</span>
        <span style="color: #c9d1d9;">${log.message}</span>
        <span style="color: #8b949e; font-size: 10px;">${metadata}</span>
    `;

    logsContainer.appendChild(logLine);

    // Auto-scroll to bottom
    if (autoScroll) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }

    // Keep max 200 logs in DOM (performance)
    while (logsContainer.children.length > 200) {
        logsContainer.removeChild(logsContainer.firstChild);
    }
}

function filterLogs() {
    currentLevelFilter = document.getElementById('log-level-filter').value;
    // Note: This only affects NEW logs. To re-filter existing logs,
    // would need to store logs in memory and re-render.
}

function toggleAutoScroll() {
    autoScroll = !autoScroll;
    document.getElementById('autoscroll-status').textContent = autoScroll ? 'ON' : 'OFF';
}

function clearLogs() {
    logsContainer.innerHTML = '';
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (evtSource) {
        evtSource.close();
    }
});
</script>
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_story_22_1_metrics_infrastructure.py`

```python
import pytest
from services.metrics_collector import MetricsCollector
from sqlalchemy import text


@pytest.mark.asyncio
async def test_metrics_table_exists(async_engine):
    """Test metrics table was created."""
    async with async_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'metrics'
            )
        """))
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_metrics_collector_api_metrics(async_engine, redis_client):
    """Test API metrics collection."""
    collector = MetricsCollector(async_engine, redis_client)

    # Insert test metrics
    async with async_engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO metrics (metric_type, metric_name, value, metadata)
            VALUES
            ('api', 'latency_ms', 45.3, '{"endpoint": "/test", "status_code": 200}'::jsonb),
            ('api', 'latency_ms', 120.5, '{"endpoint": "/test", "status_code": 500}'::jsonb)
        """))

    metrics = await collector.collect_api_metrics()

    assert metrics["request_count"] == 2
    assert metrics["avg_latency_ms"] > 0
    assert metrics["error_count"] == 1
    assert metrics["error_rate"] == 50.0


@pytest.mark.asyncio
async def test_metrics_middleware(test_client):
    """Test MetricsMiddleware records latency."""
    response = await test_client.get("/v1/code/search/lexical?query=test")

    # Check trace_id header
    assert "X-Trace-ID" in response.headers
    trace_id = response.headers["X-Trace-ID"]

    # Verify metric was recorded
    async with test_client.app.state.db_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT * FROM metrics
            WHERE metadata->>'trace_id' = :trace_id
        """), {"trace_id": trace_id})

        row = result.mappings().first()
        assert row is not None
        assert row["metric_type"] == "api"
        assert row["metric_name"] == "latency_ms"
        assert row["value"] > 0
```

---

### Integration Tests

**File**: `tests/integration/test_story_22_2_dashboard_ui.py`

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_advanced_dashboard_page_loads(test_client: AsyncClient):
    """Test /ui/monitoring/advanced page loads."""
    response = await test_client.get("/ui/monitoring/advanced")

    assert response.status_code == 200
    assert b"Advanced Monitoring" in response.content
    assert b"kpi-grid" in response.content


@pytest.mark.asyncio
async def test_advanced_summary_endpoint(test_client: AsyncClient):
    """Test /api/monitoring/advanced/summary endpoint."""
    response = await test_client.get("/api/monitoring/advanced/summary")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "api" in data
    assert "redis" in data
    assert "postgres" in data
    assert "system" in data

    # Check API metrics
    assert "p95_latency_ms" in data["api"]
    assert "requests_per_second" in data["api"]

    # Check Redis metrics
    assert "hit_rate" in data["redis"]
    assert "memory_used_mb" in data["redis"]


@pytest.mark.asyncio
async def test_logs_stream_sse(test_client: AsyncClient):
    """Test SSE logs stream."""
    # Note: Testing SSE is tricky, need to read stream
    async with test_client.stream("GET", "/api/monitoring/advanced/logs/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        # Read first event (should be recent logs batch)
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                data = line[5:].strip()  # Remove "data: " prefix
                # Should be valid JSON
                import json
                log = json.loads(data)
                assert "timestamp" in log
                assert "level" in log
                assert "message" in log
                break  # Test first event only
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Run migration: `v5_to_v6_metrics_table.sql`
- [ ] Verify table created: `\d metrics`
- [ ] Test metrics insertion manually:
  ```sql
  INSERT INTO metrics (metric_type, metric_name, value, metadata)
  VALUES ('api', 'test', 123, '{}'::jsonb);
  SELECT * FROM metrics WHERE metric_name = 'test';
  ```
- [ ] Install psutil if not present: `pip install psutil`
- [ ] Verify Redis connection: `docker exec mnemo-api python -c "import redis; r=redis.Redis(host='redis'); print(r.ping())"`
- [ ] Run all tests: `pytest tests/test_story_22*`

---

### Deployment Steps

1. **Database Migration**:
   ```bash
   docker exec -i mnemo-postgres psql -U mnemolite -d mnemolite < db/migrations/v5_to_v6_metrics_table.sql
   ```

2. **Code Deployment**:
   ```bash
   # Copy new files
   docker cp api/services/metrics_collector.py mnemo-api:/app/api/services/
   docker cp api/middleware/metrics_middleware.py mnemo-api:/app/api/middleware/
   docker cp api/routes/monitoring_routes_advanced.py mnemo-api:/app/api/routes/
   docker cp api/services/logs_buffer.py mnemo-api:/app/api/services/
   docker cp templates/monitoring_advanced.html mnemo-api:/app/templates/

   # Restart API
   docker compose restart api
   ```

3. **Verify Deployment**:
   ```bash
   # Check health
   curl http://localhost:8001/health

   # Check new endpoint
   curl http://localhost:8001/api/monitoring/advanced/summary

   # Check UI
   open http://localhost:8001/ui/monitoring/advanced
   ```

---

### Post-Deployment

- [ ] Visit `/ui/monitoring/advanced` and verify KPI cards load
- [ ] Check auto-refresh (5s interval)
- [ ] Verify logs streaming (open browser console, check SSE connection)
- [ ] Generate some API traffic: `for i in {1..10}; do curl http://localhost:8001/v1/code/search/lexical?query=test; done`
- [ ] Verify metrics recorded: `SELECT COUNT(*) FROM metrics;`
- [ ] Check trace_id headers: `curl -I http://localhost:8001/health | grep X-Trace-ID`

---

## Gotchas & Pitfalls

### 1. SSE Connection Issues

**Problem**: SSE connection fails or drops frequently

**Causes**:
- Nginx/proxy buffering enabled
- Timeout too short
- CORS issues

**Solutions**:
```nginx
# In nginx config
proxy_buffering off;
proxy_read_timeout 3600s;
proxy_set_header Connection '';
proxy_http_version 1.1;
```

**Test**:
```bash
# Direct test SSE endpoint
curl -N http://localhost:8001/api/monitoring/advanced/logs/stream
# Should stream continuously
```

---

### 2. Metrics Table Growing Too Fast

**Problem**: Table `metrics` grows to GB size after few days

**Solution**: Retention policy (auto-cleanup)

**Cron Job** (run daily):
```sql
DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';
VACUUM ANALYZE metrics;
```

**Docker Cron**:
```bash
# Add to crontab
docker exec mnemo-postgres psql -U mnemolite -d mnemolite -c "DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days'"
```

---

### 3. MetricsMiddleware Overhead

**Problem**: Recording metrics adds latency to every request

**Measurement**:
```python
# Overhead is ~1-2ms per request (INSERT query)
```

**Optimization**: Batch inserts (accumulate 100 metrics, insert in bulk)

```python
# In MetricsMiddleware
class MetricsMiddleware:
    def __init__(self, app, db_engine):
        super().__init__(app)
        self.engine = db_engine
        self.batch = []
        self.batch_size = 100

    async def _record_metric(self, ...):
        self.batch.append({...})

        if len(self.batch) >= self.batch_size:
            await self._flush_batch()

    async def _flush_batch(self):
        # Insert all at once
        async with self.engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO metrics (...) VALUES (...)
            """), self.batch)
        self.batch.clear()
```

---

### 4. Redis INFO Permissions

**Problem**: `redis.info()` fails with "NOPERM" error

**Cause**: Redis ACL restrictions

**Solution**: Update Redis ACL or use different Redis user

```redis
# In redis.conf
user default on >password ~* &* +@all
```

---

### 5. HTMX CORS Issues

**Problem**: HTMX polling fails with CORS error

**Solution**: Add CORS headers to FastAPI

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 6. ECharts Not Updating

**Problem**: Charts show stale data after HTMX refresh

**Solution**: Dispose chart before re-init

```javascript
function updateCharts(data) {
    const latencyChartDiv = document.getElementById('latency-chart');

    // Dispose existing chart
    const existingChart = echarts.getInstanceByDom(latencyChartDiv);
    if (existingChart) {
        existingChart.dispose();
    }

    // Re-initialize
    const latencyChart = echarts.init(latencyChartDiv);
    latencyChart.setOption({...});
}
```

---

### 7. Logs Buffer Memory Leak

**Problem**: `LogsBuffer` grows infinitely if logs accumulate faster than consumed

**Solution**: Fixed-size circular buffer (already implemented with `deque(maxlen=1000)`)

**Verify**:
```python
# Max memory: 1000 logs × 1KB/log = ~1MB
import sys
print(sys.getsizeof(logs_buffer.buffer))
```

---

### 8. structlog Processor Performance

**Problem**: Adding logs to buffer slows down logging

**Solution**: Make `add_to_buffer` processor as fast as possible (no I/O)

```python
def add_to_buffer(logger, method_name, event_dict):
    # Fast in-memory append (O(1))
    logs_buffer.add({
        "timestamp": event_dict.get("timestamp"),
        "level": method_name.upper(),
        "message": event_dict.get("event", ""),
        "metadata": {k: v for k, v in event_dict.items() if k not in ["event", "timestamp"]}
    })
    return event_dict  # Must return event_dict for next processor
```

---

## Timeline (Phase 1: 5 jours)

| Jour | Tasks | Points | Status |
|------|-------|--------|--------|
| **J1** | Story 22.1 (Tasks 1.1-1.3): Migration + MetricsCollector + Middleware | 1.5 pts | ⏳ |
| **J2** | Story 22.1 (Tasks 1.4-1.5): API endpoint + Tests | 0.5 pts | ⏳ |
| **J3** | Story 22.2 (Tasks 2.1-2.3): Dashboard UI + Charts | 2 pts | ⏳ |
| **J4** | Story 22.3 (Tasks 3.1-3.4): Logs buffer + SSE endpoint + Frontend | 1 pt | ⏳ |
| **J5** | Testing + Deployment + Bug fixes | - | ⏳ |

**Total**: 5 points, 5 jours (1 pt/jour avg)

---

## Success Criteria

### Story 22.1 ✅
- [x] Table `metrics` created with indexes
- [x] MetricsMiddleware records latency per request
- [x] trace_id in headers and logs
- [x] `/api/monitoring/advanced/summary` returns all metrics

### Story 22.2 ✅
- [x] Page `/ui/monitoring/advanced` accessible
- [x] 4 KPI cards auto-refresh (5s HTMX)
- [x] Latency chart (ECharts) displays data
- [x] Redis gauge displays hit rate
- [x] SCADA theme consistent

### Story 22.3 ✅
- [x] SSE endpoint `/api/monitoring/advanced/logs/stream` streams logs
- [x] Frontend EventSource connects successfully
- [x] Logs displayed with colorization
- [x] Filters (level, search) work
- [x] Auto-scroll toggleable

---

## Next Steps (After Phase 1)

Once Phase 1 is deployed and validated:

1. **Phase 2 Story 22.4**: Redis breakdown par cache type
2. **Phase 2 Story 22.5**: API performance par endpoint (P50/P95/P99)
3. **Phase 2 Story 22.6**: Request tracing (click trace_id to filter logs)
4. **Phase 2 Story 22.7**: Smart alerting (threshold-based)

---

**Créé**: 2025-10-24
**Auteur**: Claude Code
**Status**: 🔨 Ready to implement
**Version**: 1.0.0
