# EPIC-20 Phase 1 MVP - Implémentation Détaillée

**Date**: 2025-10-23
**Status**: 📋 Plan d'Implémentation
**Effort**: 5 points (1 semaine)
**Priorité**: 🔥 Haute

---

## 🎯 Objectif MVP

**Créer un dashboard de monitoring basique mais fonctionnel** permettant de :
1. ✅ Voir métriques temps réel (API, Redis, PostgreSQL)
2. ✅ Consulter logs structurés en streaming
3. ✅ Identifier problèmes rapidement (<30s)

**Principe**: KISS - Utiliser stack existante (PG, structlog, Chart.js, HTMX)

---

## 📊 Stories du MVP

### Story 20.1: Infrastructure de Métriques (2 pts)
- Migration DB (table `metrics`)
- Service `MetricsCollector`
- Endpoints API `/api/monitoring/*`

### Story 20.2: Dashboard Monitoring UI (2 pts)
- Page `/ui/monitoring/advanced`
- Cartes résumé (API, Redis, PostgreSQL)
- Graphs Chart.js

### Story 20.3: Logs Temps Réel (1 pt)
- SSE endpoint `/api/logs/stream`
- UI logs avec filtres
- Auto-scroll + colorisation

---

## 🏗️ Architecture Détaillée

### Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROWSER                                 │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐    │
│  │ /ui/monitoring/advanced                               │    │
│  │                                                       │    │
│  │  ┌──────┐  ┌──────┐  ┌──────┐                       │    │
│  │  │ API  │  │Redis │  │  PG  │  ← Cartes Metrics     │    │
│  │  └──────┘  └──────┘  └──────┘                       │    │
│  │                                                       │    │
│  │  ┌────────────────────────────────┐                  │    │
│  │  │ Chart.js (Latency Timeline)    │                  │    │
│  │  └────────────────────────────────┘                  │    │
│  │                                                       │    │
│  │  ┌────────────────────────────────┐                  │    │
│  │  │ Live Logs (SSE Stream)         │                  │    │
│  │  │ 21:50:12 [INFO] search...      │                  │    │
│  │  │ 21:50:11 [DEBUG] cache_hit...  │                  │    │
│  │  └────────────────────────────────┘                  │    │
│  └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         │ HTTP (HTMX)                        │ SSE
         │ GET /api/monitoring/summary        │ GET /api/logs/stream
         │ (every 5s)                         │ (continuous)
         ↓                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ Monitoring Routes (/api/monitoring/*)                │     │
│  │                                                      │     │
│  │  GET  /summary          → MetricsAggregator         │     │
│  │  GET  /redis/status     → RedisMonitor              │     │
│  │  GET  /postgres/status  → PostgresMonitor           │     │
│  │  GET  /api/latency      → LatencyCollector          │     │
│  └──────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ Services Layer                                       │     │
│  │                                                      │     │
│  │  MetricsCollector  ─┬─ collect_api_metrics()       │     │
│  │                     ├─ collect_redis_metrics()      │     │
│  │                     └─ collect_postgres_metrics()   │     │
│  │                                                      │     │
│  │  MetricsRecorder   ─── record_metric()              │     │
│  │                                                      │     │
│  │  LogStreamer       ─── stream_logs_sse()            │     │
│  └──────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ Middleware                                           │     │
│  │                                                      │     │
│  │  @app.middleware("http")                            │     │
│  │  async def track_request_metrics():                 │     │
│  │      # Mesure latency                               │     │
│  │      # Record dans table metrics                    │     │
│  │      # Log structuré                                │     │
│  └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
         │                           │                    │
         ↓                           ↓                    ↓
┌─────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ PostgreSQL      │   │ Redis            │   │ Logs (stdout)    │
│                 │   │                  │   │                  │
│ ┌─────────────┐ │   │ INFO (stats)     │   │ structlog        │
│ │metrics      │ │   │ SLOWLOG          │   │ JSON format      │
│ │- id         │ │   │ MEMORY           │   │                  │
│ │- timestamp  │ │   │                  │   │ Rotation: 7d     │
│ │- type       │ │   └──────────────────┘   └──────────────────┘
│ │- name       │ │
│ │- value      │ │
│ │- metadata   │ │
│ └─────────────┘ │
│                 │
│ pg_stat_*       │
│ - activity      │
│ - statements    │
└─────────────────┘
```

---

## 💾 Modèles de Données

### 1. Table `metrics` (PostgreSQL)

```sql
-- db/migrations/v5_to_v6_monitoring_metrics.sql

CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Type de métrique
    metric_type VARCHAR(50) NOT NULL,  -- 'api', 'redis', 'postgres', 'system'

    -- Nom de la métrique
    metric_name VARCHAR(100) NOT NULL, -- 'request_latency', 'hit_rate', 'connections'

    -- Valeur
    value DOUBLE PRECISION NOT NULL,

    -- Métadonnées additionnelles (endpoint, error, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Index pour requêtes rapides
    CONSTRAINT metrics_type_check CHECK (metric_type IN ('api', 'redis', 'postgres', 'system', 'cache'))
);

-- Index pour queries fréquentes (agrégation par type/période)
CREATE INDEX idx_metrics_type_timestamp ON metrics (metric_type, timestamp DESC);
CREATE INDEX idx_metrics_name_timestamp ON metrics (metric_name, timestamp DESC);

-- Index GIN pour recherches dans metadata
CREATE INDEX idx_metrics_metadata ON metrics USING gin (metadata jsonb_path_ops);

-- Partition par jour (optionnel, activer si >100k metrics/jour)
-- CREATE TABLE metrics_2025_10_23 PARTITION OF metrics
-- FOR VALUES FROM ('2025-10-23') TO ('2025-10-24');

-- Retention policy: garder 30 jours
-- Cron job: DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days';

COMMENT ON TABLE metrics IS 'Stockage des métriques système pour monitoring (EPIC-20)';
COMMENT ON COLUMN metrics.metadata IS 'Champs additionnels: endpoint, error_type, cache_type, etc.';
```

**Exemples de données** :

```sql
-- API latency
INSERT INTO metrics (metric_type, metric_name, value, metadata) VALUES
('api', 'request_latency_ms', 45.2, '{"endpoint": "/v1/code/search/hybrid", "method": "GET", "status": 200}'::jsonb);

-- Redis hit rate
INSERT INTO metrics (metric_type, metric_name, value, metadata) VALUES
('redis', 'hit_rate_percent', 87.3, '{"cache_type": "search_results"}'::jsonb);

-- PostgreSQL connections
INSERT INTO metrics (metric_type, metric_name, value, metadata) VALUES
('postgres', 'active_connections', 8, '{}'::jsonb);
```

---

### 2. Modèles Pydantic

```python
# api/models/monitoring.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class MetricType(str, Enum):
    """Types de métriques supportées."""
    API = "api"
    REDIS = "redis"
    POSTGRES = "postgres"
    SYSTEM = "system"
    CACHE = "cache"

class MetricCreate(BaseModel):
    """Modèle pour créer une métrique."""
    metric_type: MetricType
    metric_name: str = Field(..., max_length=100)
    value: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Metric(MetricCreate):
    """Modèle métrique complet avec ID."""
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True

class MetricsSummary(BaseModel):
    """Résumé des métriques pour dashboard."""
    api: "ApiMetrics"
    redis: "RedisMetrics"
    postgres: "PostgresMetrics"
    system: Optional["SystemMetrics"] = None

class ApiMetrics(BaseModel):
    """Métriques API."""
    request_rate: float = Field(..., description="Requests per second")
    latency_p50: float = Field(..., description="P50 latency in ms")
    latency_p95: float = Field(..., description="P95 latency in ms")
    latency_p99: float = Field(..., description="P99 latency in ms")
    success_rate: float = Field(..., description="Success rate percentage")
    error_rate: float = Field(..., description="Error rate percentage")
    top_endpoints: List[Dict[str, Any]] = Field(default_factory=list)

class RedisMetrics(BaseModel):
    """Métriques Redis."""
    status: str = Field(..., description="Connected/Disconnected")
    memory_used_mb: float
    memory_max_mb: float
    memory_percent: float
    hit_rate_percent: float
    keys_total: int
    evicted_keys: int
    connected_clients: int

class PostgresMetrics(BaseModel):
    """Métriques PostgreSQL."""
    status: str = Field(..., description="Healthy/Degraded/Down")
    connections_active: int
    connections_idle: int
    connections_total: int
    connections_max: int
    cache_hit_ratio_percent: float
    slow_queries_count: int = Field(..., description="Queries >100ms in last hour")

class SystemMetrics(BaseModel):
    """Métriques système (optionnel)."""
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    memory_percent: float
```

---

## 🛠️ Implémentation Services

### 1. MetricsRecorder (Enregistrement)

```python
# api/services/metrics_recorder.py

"""
Service pour enregistrer les métriques dans PostgreSQL.

Usage:
    recorder = MetricsRecorder(engine)
    await recorder.record_api_latency("/v1/code/search", 45.2, status=200)
"""

import logging
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import Dict, Any, Optional
from models.monitoring import MetricType

logger = logging.getLogger(__name__)

class MetricsRecorder:
    """Enregistre les métriques dans PostgreSQL."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._buffer = []  # Buffer pour batch inserts
        self._buffer_size = 10  # Flush tous les 10 metrics

    async def record_metric(
        self,
        metric_type: MetricType,
        metric_name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Enregistre une métrique.

        Args:
            metric_type: Type de métrique (api, redis, postgres)
            metric_name: Nom (request_latency_ms, hit_rate_percent)
            value: Valeur numérique
            metadata: Champs additionnels (endpoint, cache_type, etc.)
        """
        self._buffer.append({
            "metric_type": metric_type.value,
            "metric_name": metric_name,
            "value": value,
            "metadata": metadata or {}
        })

        # Flush si buffer plein
        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def flush(self):
        """Écrit toutes les métriques en buffer dans la DB (batch)."""
        if not self._buffer:
            return

        try:
            async with self.engine.begin() as conn:
                # Batch insert
                await conn.execute(
                    """
                    INSERT INTO metrics (metric_type, metric_name, value, metadata)
                    SELECT * FROM unnest(
                        $1::varchar[],
                        $2::varchar[],
                        $3::float[],
                        $4::jsonb[]
                    )
                    """,
                    (
                        [m["metric_type"] for m in self._buffer],
                        [m["metric_name"] for m in self._buffer],
                        [m["value"] for m in self._buffer],
                        [m["metadata"] for m in self._buffer]
                    )
                )

            logger.debug(f"Flushed {len(self._buffer)} metrics to DB")
            self._buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
            # Ne pas perdre les metrics, réessayer au prochain flush
            # (ou implémenter retry logic)

    # Helpers pour types spécifiques
    async def record_api_latency(
        self,
        endpoint: str,
        latency_ms: float,
        method: str = "GET",
        status: int = 200
    ):
        """Record API request latency."""
        await self.record_metric(
            MetricType.API,
            "request_latency_ms",
            latency_ms,
            {"endpoint": endpoint, "method": method, "status": status}
        )

    async def record_redis_hit_rate(self, cache_type: str, hit_rate: float):
        """Record Redis cache hit rate."""
        await self.record_metric(
            MetricType.REDIS,
            "hit_rate_percent",
            hit_rate,
            {"cache_type": cache_type}
        )

    async def record_postgres_connections(self, active: int, idle: int):
        """Record PostgreSQL connections."""
        await self.record_metric(
            MetricType.POSTGRES,
            "connections_active",
            active
        )
        await self.record_metric(
            MetricType.POSTGRES,
            "connections_idle",
            idle
        )
```

---

### 2. MetricsCollector (Lecture/Agrégation)

```python
# api/services/metrics_collector.py

"""
Service pour collecter et agréger les métriques depuis DB/Redis/PostgreSQL.

Usage:
    collector = MetricsCollector(engine, redis_client)
    summary = await collector.get_metrics_summary(period="1h")
"""

import logging
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from models.monitoring import (
    MetricsSummary, ApiMetrics, RedisMetrics, PostgresMetrics
)

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collecte et agrège les métriques."""

    def __init__(self, engine: AsyncEngine, redis_client):
        self.engine = engine
        self.redis = redis_client

    async def get_metrics_summary(self, period: str = "1h") -> MetricsSummary:
        """
        Récupère résumé des métriques pour dashboard.

        Args:
            period: Période à analyser ("1h", "24h", "7d")

        Returns:
            MetricsSummary avec métriques API, Redis, PostgreSQL
        """
        # Parse period
        interval = self._parse_period(period)

        # Collect en parallèle
        api_metrics = await self._collect_api_metrics(interval)
        redis_metrics = await self._collect_redis_metrics()
        postgres_metrics = await self._collect_postgres_metrics()

        return MetricsSummary(
            api=api_metrics,
            redis=redis_metrics,
            postgres=postgres_metrics
        )

    async def _collect_api_metrics(self, interval: timedelta) -> ApiMetrics:
        """Collecte métriques API depuis table metrics."""
        async with self.engine.begin() as conn:
            # Latences (P50, P95, P99)
            result = await conn.execute(
                """
                SELECT
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY value) as p50,
                    percentile_cont(0.95) WITHIN GROUP (ORDER BY value) as p95,
                    percentile_cont(0.99) WITHIN GROUP (ORDER BY value) as p99,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE (metadata->>'status')::int >= 400) as errors
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'request_latency_ms'
                  AND timestamp > NOW() - $1
                """,
                (interval,)
            )
            row = result.fetchone()

            # Request rate (req/sec)
            total_requests = row['total'] if row else 0
            request_rate = total_requests / interval.total_seconds()

            # Success/Error rate
            errors = row['errors'] if row else 0
            success_rate = ((total_requests - errors) / total_requests * 100) if total_requests > 0 else 100
            error_rate = (errors / total_requests * 100) if total_requests > 0 else 0

            # Top endpoints (optionnel)
            result = await conn.execute(
                """
                SELECT
                    metadata->>'endpoint' as endpoint,
                    COUNT(*) as count,
                    AVG(value) as avg_latency
                FROM metrics
                WHERE metric_type = 'api'
                  AND timestamp > NOW() - $1
                GROUP BY metadata->>'endpoint'
                ORDER BY count DESC
                LIMIT 5
                """,
                (interval,)
            )
            top_endpoints = [dict(r) for r in result.fetchall()]

            return ApiMetrics(
                request_rate=round(request_rate, 2),
                latency_p50=round(row['p50'] or 0, 2),
                latency_p95=round(row['p95'] or 0, 2),
                latency_p99=round(row['p99'] or 0, 2),
                success_rate=round(success_rate, 2),
                error_rate=round(error_rate, 2),
                top_endpoints=top_endpoints
            )

    async def _collect_redis_metrics(self) -> RedisMetrics:
        """Collecte métriques Redis via INFO command."""
        try:
            info = await self.redis.info()
            stats = await self.redis.info("stats")

            # Memory
            memory_used_mb = info.get('used_memory', 0) / (1024 * 1024)
            memory_max_mb = 2048  # From config (or read from info)

            # Hit rate
            hits = stats.get('keyspace_hits', 0)
            misses = stats.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0

            return RedisMetrics(
                status="Connected",
                memory_used_mb=round(memory_used_mb, 1),
                memory_max_mb=memory_max_mb,
                memory_percent=round(memory_used_mb / memory_max_mb * 100, 1),
                hit_rate_percent=round(hit_rate, 1),
                keys_total=await self.redis.dbsize(),
                evicted_keys=info.get('evicted_keys', 0),
                connected_clients=info.get('connected_clients', 0)
            )

        except Exception as e:
            logger.error(f"Failed to collect Redis metrics: {e}")
            return RedisMetrics(
                status="Disconnected",
                memory_used_mb=0,
                memory_max_mb=2048,
                memory_percent=0,
                hit_rate_percent=0,
                keys_total=0,
                evicted_keys=0,
                connected_clients=0
            )

    async def _collect_postgres_metrics(self) -> PostgresMetrics:
        """Collecte métriques PostgreSQL via pg_stat_*."""
        async with self.engine.begin() as conn:
            # Connexions
            result = await conn.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE state = 'active') as active,
                    COUNT(*) FILTER (WHERE state = 'idle') as idle,
                    COUNT(*) as total
                FROM pg_stat_activity
            """)
            connections = result.fetchone()

            # Cache hit ratio
            result = await conn.execute("""
                SELECT
                    COALESCE(
                        sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100,
                        0
                    ) as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            cache_hit_ratio = result.scalar() or 0

            # Slow queries (from pg_stat_statements si activé)
            # Sinon, compter depuis table metrics
            result = await conn.execute("""
                SELECT COUNT(*) as slow_queries
                FROM metrics
                WHERE metric_type = 'postgres'
                  AND metric_name = 'query_duration_ms'
                  AND value > 100
                  AND timestamp > NOW() - INTERVAL '1 hour'
            """)
            slow_queries = result.scalar() or 0

            return PostgresMetrics(
                status="Healthy",
                connections_active=connections['active'],
                connections_idle=connections['idle'],
                connections_total=connections['total'],
                connections_max=100,  # From config
                cache_hit_ratio_percent=round(cache_hit_ratio, 2),
                slow_queries_count=slow_queries
            )

    def _parse_period(self, period: str) -> timedelta:
        """Parse period string to timedelta."""
        mapping = {
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7)
        }
        return mapping.get(period, timedelta(hours=1))
```

---

### 3. Middleware de Tracking

```python
# api/main.py (ajout middleware)

import time
import structlog
from fastapi import Request
from services.metrics_recorder import MetricsRecorder

logger = structlog.get_logger(__name__)

# Global recorder (initialisé au startup)
metrics_recorder: Optional[MetricsRecorder] = None

@app.middleware("http")
async def track_request_metrics(request: Request, call_next):
    """
    Middleware pour tracker toutes les requêtes et enregistrer métriques.

    Mesure:
    - Latence de la requête
    - Status code
    - Endpoint

    Enregistre dans table metrics + logs structurés.
    """
    start_time = time.time()

    # Process request
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        logger.error("request_failed", error=str(e), path=request.url.path)
        raise

    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000

    # Extract endpoint
    endpoint = request.url.path

    # Log structuré (déjà fait par search_metrics.py)
    logger.info(
        "request_completed",
        endpoint=endpoint,
        method=request.method,
        status=status_code,
        latency_ms=round(latency_ms, 2)
    )

    # Record métrique (async, non-bloquant)
    if metrics_recorder:
        await metrics_recorder.record_api_latency(
            endpoint=endpoint,
            latency_ms=latency_ms,
            method=request.method,
            status=status_code
        )

    return response

@app.on_event("startup")
async def startup_event():
    """Initialize metrics recorder."""
    global metrics_recorder
    metrics_recorder = MetricsRecorder(app.state.db_engine)

@app.on_event("shutdown")
async def shutdown_event():
    """Flush remaining metrics."""
    if metrics_recorder:
        await metrics_recorder.flush()
```

---

## 🌐 API Endpoints

```python
# api/routes/monitoring_routes.py

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from services.metrics_collector import MetricsCollector
from services.log_streamer import LogStreamer
from models.monitoring import MetricsSummary, ApiMetrics, RedisMetrics, PostgresMetrics

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    period: str = Query("1h", regex="^(5m|15m|1h|24h|7d)$"),
    collector: MetricsCollector = Depends()
):
    """
    Résumé des métriques pour dashboard.

    Args:
        period: Période à analyser (5m, 15m, 1h, 24h, 7d)

    Returns:
        Métriques API, Redis, PostgreSQL agrégées
    """
    return await collector.get_metrics_summary(period)

@router.get("/api/latency")
async def get_api_latency_timeline(
    period: str = Query("1h", regex="^(1h|24h|7d)$"),
    collector: MetricsCollector = Depends()
):
    """
    Timeline de latence API (pour Chart.js).

    Returns:
        {
            "labels": ["10:00", "10:05", ...],
            "datasets": [
                {"label": "P50", "data": [45, 48, ...]},
                {"label": "P95", "data": [120, 125, ...]}
            ]
        }
    """
    # TODO: Implémenter agrégation par bucket (5min)
    pass

@router.get("/redis/status", response_model=RedisMetrics)
async def get_redis_status(collector: MetricsCollector = Depends()):
    """Métriques Redis détaillées."""
    return await collector._collect_redis_metrics()

@router.get("/postgres/status", response_model=PostgresMetrics)
async def get_postgres_status(collector: MetricsCollector = Depends()):
    """Métriques PostgreSQL détaillées."""
    return await collector._collect_postgres_metrics()

@router.get("/logs/stream")
async def stream_logs(
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARN|ERROR)$"),
    service: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """
    Stream logs en temps réel via Server-Sent Events (SSE).

    Args:
        level: Filtrer par level (DEBUG, INFO, WARN, ERROR)
        service: Filtrer par service
        search: Recherche full-text

    Returns:
        SSE stream
    """
    streamer = LogStreamer(level=level, service=service, search=search)

    async def event_generator():
        async for log in streamer.stream():
            yield f"data: {log}\n\n"

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

## 🎨 UI Implementation

### 1. Template Principal

```html
<!-- templates/monitoring_advanced.html -->

{% extends "base.html" %}

{% block title %}Advanced Monitoring - MnemoLite{% endblock %}

{% block content %}
<div class="monitoring-container">
    <header class="monitoring-header">
        <h1>🎛️ Advanced Monitoring</h1>

        <!-- Period Selector -->
        <select id="period-selector" hx-get="/api/monitoring/summary"
                hx-trigger="change" hx-target="#metrics-summary"
                hx-vals='js:{period: event.target.value}'>
            <option value="5m">Last 5 minutes</option>
            <option value="15m">Last 15 minutes</option>
            <option value="1h" selected>Last 1 hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
        </select>
    </header>

    <!-- Metrics Summary Cards -->
    <div id="metrics-summary"
         hx-get="/api/monitoring/summary?period=1h"
         hx-trigger="load, every 5s"
         hx-swap="innerHTML">
        <!-- Partial will be loaded here -->
        <div class="loading">Loading metrics...</div>
    </div>

    <!-- Latency Chart -->
    <div class="chart-container">
        <h2>📈 API Latency (Last 1h)</h2>
        <canvas id="latencyChart" width="800" height="300"></canvas>
    </div>

    <!-- Live Logs -->
    <div class="logs-container">
        <h2>📝 Live Logs</h2>

        <!-- Filters -->
        <div class="logs-filters">
            <select id="log-level">
                <option value="">All Levels</option>
                <option value="ERROR">ERROR</option>
                <option value="WARN">WARN</option>
                <option value="INFO">INFO</option>
                <option value="DEBUG">DEBUG</option>
            </select>

            <input type="text" id="log-search" placeholder="Search...">

            <button id="pause-logs">Pause</button>
            <button id="clear-logs">Clear</button>
            <button id="export-logs">Export CSV</button>
        </div>

        <!-- Log Stream -->
        <div id="logs-stream" class="logs-stream">
            <!-- Logs will be appended here via SSE -->
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="{{ url_for('static', path='/js/components/monitoring.js') }}"></script>
{% endblock %}
```

---

### 2. Partial: Metrics Cards

```html
<!-- templates/partials/metrics_summary.html -->

<div class="metrics-cards">
    <!-- API Card -->
    <div class="metric-card">
        <div class="metric-icon">📊</div>
        <h3>API</h3>
        <div class="metric-value">{{ api.request_rate }} req/s</div>
        <div class="metric-details">
            <span>P50: {{ api.latency_p50 }}ms</span>
            <span>P95: {{ api.latency_p95 }}ms</span>
            <span class="{% if api.success_rate < 95 %}warning{% endif %}">
                Success: {{ api.success_rate }}%
            </span>
        </div>
    </div>

    <!-- Redis Card -->
    <div class="metric-card {% if redis.status != 'Connected' %}error{% endif %}">
        <div class="metric-icon">🔴</div>
        <h3>Redis</h3>
        <div class="metric-value">{{ redis.hit_rate_percent }}%</div>
        <div class="metric-details">
            <span>Hit Rate</span>
            <span>{{ redis.memory_used_mb }} MB / {{ redis.memory_max_mb }} MB</span>
            <span class="{% if redis.memory_percent > 80 %}warning{% endif %}">
                Memory: {{ redis.memory_percent }}%
            </span>
        </div>
    </div>

    <!-- PostgreSQL Card -->
    <div class="metric-card {% if postgres.status != 'Healthy' %}error{% endif %}">
        <div class="metric-icon">🐘</div>
        <h3>PostgreSQL</h3>
        <div class="metric-value">{{ postgres.connections_active }}/{{ postgres.connections_max }}</div>
        <div class="metric-details">
            <span>Active Connections</span>
            <span>Cache Hit: {{ postgres.cache_hit_ratio_percent }}%</span>
            <span class="{% if postgres.slow_queries_count > 10 %}warning{% endif %}">
                Slow Queries: {{ postgres.slow_queries_count }}
            </span>
        </div>
    </div>
</div>
```

---

### 3. JavaScript: Chart.js + SSE

```javascript
// static/js/components/monitoring.js

/**
 * Monitoring Dashboard - EPIC-20
 */

class MonitoringDashboard {
    constructor() {
        this.latencyChart = null;
        this.logEventSource = null;
        this.isPaused = false;

        this.initChart();
        this.initLogStream();
        this.initEventListeners();
    }

    /**
     * Initialize Chart.js for latency timeline.
     */
    initChart() {
        const ctx = document.getElementById('latencyChart');
        if (!ctx) return;

        this.latencyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'P50',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    },
                    {
                        label: 'P95',
                        data: [],
                        borderColor: 'rgb(255, 159, 64)',
                        tension: 0.1
                    },
                    {
                        label: 'P99',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Latency (ms)'
                        }
                    }
                }
            }
        });

        // Update every 5s
        this.updateChartPeriodically();
    }

    /**
     * Update chart data from API.
     */
    async updateChartPeriodically() {
        setInterval(async () => {
            const period = document.getElementById('period-selector').value;
            const response = await fetch(`/api/monitoring/api/latency?period=${period}`);
            const data = await response.json();

            this.latencyChart.data.labels = data.labels;
            this.latencyChart.data.datasets[0].data = data.datasets[0].data;
            this.latencyChart.data.datasets[1].data = data.datasets[1].data;
            this.latencyChart.data.datasets[2].data = data.datasets[2].data;
            this.latencyChart.update();
        }, 5000);
    }

    /**
     * Initialize Server-Sent Events for live logs.
     */
    initLogStream() {
        const level = document.getElementById('log-level').value;
        const search = document.getElementById('log-search').value;

        let url = '/api/monitoring/logs/stream';
        const params = new URLSearchParams();
        if (level) params.append('level', level);
        if (search) params.append('search', search);
        if (params.toString()) url += '?' + params.toString();

        this.logEventSource = new EventSource(url);

        this.logEventSource.onmessage = (event) => {
            if (this.isPaused) return;

            const log = JSON.parse(event.data);
            this.appendLog(log);
        };

        this.logEventSource.onerror = (error) => {
            console.error('SSE error:', error);
            this.logEventSource.close();
            // Reconnect after 5s
            setTimeout(() => this.initLogStream(), 5000);
        };
    }

    /**
     * Append log entry to stream.
     */
    appendLog(log) {
        const logsStream = document.getElementById('logs-stream');
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${log.level.toLowerCase()}`;

        logEntry.innerHTML = `
            <span class="log-timestamp">${log.timestamp}</span>
            <span class="log-level">[${log.level}]</span>
            <span class="log-message">${log.message}</span>
        `;

        logsStream.appendChild(logEntry);

        // Auto-scroll
        logsStream.scrollTop = logsStream.scrollHeight;

        // Limit to 100 entries
        if (logsStream.children.length > 100) {
            logsStream.removeChild(logsStream.firstChild);
        }
    }

    /**
     * Initialize event listeners.
     */
    initEventListeners() {
        // Pause logs
        document.getElementById('pause-logs')?.addEventListener('click', () => {
            this.isPaused = !this.isPaused;
            const btn = document.getElementById('pause-logs');
            btn.textContent = this.isPaused ? 'Resume' : 'Pause';
        });

        // Clear logs
        document.getElementById('clear-logs')?.addEventListener('click', () => {
            document.getElementById('logs-stream').innerHTML = '';
        });

        // Export logs
        document.getElementById('export-logs')?.addEventListener('click', () => {
            this.exportLogsCSV();
        });

        // Filter logs on change
        document.getElementById('log-level')?.addEventListener('change', () => {
            this.reconnectLogStream();
        });

        document.getElementById('log-search')?.addEventListener('input', debounce(() => {
            this.reconnectLogStream();
        }, 500));
    }

    /**
     * Reconnect log stream with new filters.
     */
    reconnectLogStream() {
        if (this.logEventSource) {
            this.logEventSource.close();
        }
        this.initLogStream();
    }

    /**
     * Export logs as CSV.
     */
    exportLogsCSV() {
        const logs = Array.from(document.querySelectorAll('.log-entry'));
        const csv = logs.map(log => {
            const timestamp = log.querySelector('.log-timestamp').textContent;
            const level = log.querySelector('.log-level').textContent;
            const message = log.querySelector('.log-message').textContent;
            return `"${timestamp}","${level}","${message}"`;
        }).join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `logs-${Date.now()}.csv`;
        a.click();
    }
}

// Utility: debounce
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    new MonitoringDashboard();
});
```

---

## 🚀 Plan d'Implémentation

### Jour 1-2: Infrastructure (Story 20.1)

**Tasks** :
1. ✅ Migration DB (`v5_to_v6_monitoring_metrics.sql`)
2. ✅ Modèles Pydantic (`models/monitoring.py`)
3. ✅ Service `MetricsRecorder`
4. ✅ Service `MetricsCollector`
5. ✅ Middleware tracking
6. ✅ Tests unitaires services

**Validation** :
```bash
# Test recorder
python -m pytest tests/unit/test_metrics_recorder.py -v

# Test collector
python -m pytest tests/unit/test_metrics_collector.py -v
```

---

### Jour 3-4: Dashboard UI (Story 20.2)

**Tasks** :
1. ✅ Template `monitoring_advanced.html`
2. ✅ Partial `metrics_summary.html`
3. ✅ CSS styling (SCADA theme)
4. ✅ JavaScript Chart.js
5. ✅ API endpoints (`/api/monitoring/*`)
6. ✅ HTMX auto-refresh (5s)

**Validation** :
```bash
# Ouvrir dashboard
open http://localhost:8001/ui/monitoring/advanced

# Vérifier cartes s'affichent
# Vérifier auto-refresh fonctionne
```

---

### Jour 5: Logs Streaming (Story 20.3)

**Tasks** :
1. ✅ Service `LogStreamer` (SSE)
2. ✅ Endpoint `/api/logs/stream`
3. ✅ JavaScript SSE client
4. ✅ Filtres (level, search)
5. ✅ Auto-scroll + colorisation
6. ✅ Export CSV

**Validation** :
```bash
# Test SSE
curl -N http://localhost:8001/api/monitoring/logs/stream

# Vérifier UI logs s'affichent temps réel
# Tester filtres
# Tester export
```

---

## ✅ Checklist Avant Production

- [ ] Migration DB exécutée
- [ ] Index créés (performance)
- [ ] Middleware activé
- [ ] Endpoints API testés
- [ ] UI dashboard fonctionnel
- [ ] Logs streaming fonctionne
- [ ] Tests passent (>90% coverage)
- [ ] Docs à jour
- [ ] Pas de perf degradation (<2ms overhead)

---

## 📊 Estimation Finale

| Task | Effort | Assigné |
|------|--------|---------|
| Story 20.1: Infrastructure | 2 jours | Dev 1 |
| Story 20.2: Dashboard UI | 2 jours | Dev 1 |
| Story 20.3: Logs Streaming | 1 jour | Dev 1 |
| **Total** | **5 jours** | **1 dev** |

---

**Créé** : 2025-10-23
**Status** : 📋 Plan Prêt à Implémenter
**Next** : Commencer Story 20.1
