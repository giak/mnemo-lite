# EPIC-20: Observabilité & Monitoring Intégré - ULTRATHINK

**Date**: 2025-10-23
**Status**: 🧠 Brainstorming
**Priorité**: Haute (Production-Critical)

---

## 🎯 Vision

**Créer un système d'observabilité intégré dans l'UI MnemoLite** permettant de voir en temps réel :
- 📊 Performance des API endpoints
- 🔴 État du cache Redis (hits/misses, memory)
- 🐘 Performance PostgreSQL (queries, connections)
- 📝 Logs structurés en temps réel
- 📈 Métriques système (CPU, RAM, I/O)

**Principe** : L'admin doit pouvoir **diagnostiquer un problème en production en 30 secondes** depuis l'UI.

---

## 🧠 Brainstorming: Que Monitorer ?

### 1. 📊 API & Workflow

#### Métriques Essentielles

**Par Endpoint** :
```
GET  /v1/code/search/hybrid
├─ Throughput: 12.5 req/s
├─ Latency P50: 45ms
├─ Latency P95: 120ms
├─ Latency P99: 250ms
├─ Success Rate: 99.2%
├─ Error Rate: 0.8%
└─ Top Errors:
   └─ TimeoutError: 5 (last 1h)
```

**Endpoints à Monitorer** :
- `/v1/code/search/hybrid` (critique)
- `/v1/code/search/lexical`
- `/v1/code/search/vector`
- `/v1/code/index` (POST)
- `/v1/code/graph/build`
- `/v1/code/graph/traverse`
- `/ui/*` (pages)

**Visualisation** :
- Timeline (dernières 24h)
- Heatmap par heure/endpoint
- Table triable par latence/erreurs

---

### 2. 🔴 Redis Cache

#### Métriques Essentielles

**Global** :
```
Redis Status: ✅ Connected
├─ Memory Used: 245 MB / 2 GB (12%)
├─ Hit Rate: 87.3% (last 1h)
├─ Keys Total: 1,247
├─ Evictions: 23 (last 1h)
└─ Connections: 5 / 20
```

**Par Cache Type** :
```
search_results
├─ Keys: 342
├─ Hit Rate: 92%
├─ Avg TTL: 28s / 30s
└─ Top Keys: [...]

embeddings
├─ Keys: 105
├─ Hit Rate: 78%
├─ Avg TTL: 45s / 60s
└─ Top Keys: [...]

graph_traversal
├─ Keys: 89
├─ Hit Rate: 95%
└─ Avg TTL: 98s / 120s
```

**Alertes** :
- Hit rate < 70% → "Cache inefficace"
- Memory > 80% → "Risque d'éviction"
- Evictions > 100/h → "TTL trop élevé?"

**Visualisation** :
- Gauge pour memory usage
- Line chart pour hit rate (temps réel)
- Bar chart par cache type

---

### 3. 🐘 PostgreSQL

#### Métriques Essentielles

**Connexions** :
```
PostgreSQL Status: ✅ Healthy
├─ Active Connections: 8 / 20
├─ Idle Connections: 2
├─ Max Connections: 100
└─ Connection Pool: OK
```

**Performance** :
```
Query Performance
├─ Slow Queries (>100ms): 3 (last 1h)
├─ Total Queries: 2,847
├─ Avg Query Time: 12ms
└─ Cache Hit Ratio: 98.5%
```

**Top Slow Queries** :
```sql
1. SELECT * FROM code_chunks WHERE ... (245ms, 5 calls)
2. INSERT INTO events ... (180ms, 12 calls)
3. SELECT COUNT(*) FROM nodes ... (120ms, 3 calls)
```

**Tables** :
```
code_chunks
├─ Rows: 14,523
├─ Size: 45 MB
├─ Index Size: 12 MB
└─ Last Vacuum: 2h ago

events
├─ Rows: 8,941
├─ Size: 28 MB
└─ Partitioned: No
```

**Alertes** :
- Slow queries > 10/h → "Optimisation requise"
- Cache hit ratio < 95% → "Index manquants?"
- Active connections > 80% → "Risque de saturation"

**Visualisation** :
- Timeline slow queries
- Table queries avec EXPLAIN
- Gauge connections/memory

---

### 4. 📝 Logs en Temps Réel

#### Interface de Logs

**Filtres** :
```
[Level: ALL ▾] [Service: ALL ▾] [Time: Last 1h ▾] [Search: ___________]
```

**Stream de Logs** :
```
2025-10-23 21:50:12 [INFO ] search_completed query="validate email" latency=45ms
2025-10-23 21:50:11 [DEBUG] cache_hit key="search:validate..." ttl=28s
2025-10-23 21:50:10 [WARN ] slow_query duration=120ms table="code_chunks"
2025-10-23 21:50:05 [ERROR] timeout endpoint="/v1/code/search/hybrid" duration=5002ms
```

**Features** :
- ✅ Streaming temps réel (SSE ou WebSocket)
- ✅ Filtrage multi-critères
- ✅ Recherche full-text
- ✅ Colorisation par level
- ✅ Expand pour voir JSON complet
- ✅ Export (JSON, CSV)

**Niveaux** :
- ERROR (rouge)
- WARN (orange)
- INFO (bleu)
- DEBUG (gris)

---

### 5. 📈 Système (Host Metrics)

#### Métriques Essentielles

**CPU** :
```
CPU Usage
├─ Current: 34%
├─ Avg (1h): 28%
├─ Processes:
│  ├─ uvicorn: 18%
│  ├─ postgres: 12%
│  └─ redis: 4%
```

**Mémoire** :
```
Memory Usage
├─ Used: 1.2 GB / 4 GB (30%)
├─ Processes:
│  ├─ postgres: 580 MB
│  ├─ uvicorn: 450 MB
│  └─ redis: 245 MB
```

**Disk I/O** :
```
Disk I/O
├─ Read: 2.5 MB/s
├─ Write: 1.2 MB/s
└─ IOPS: 450
```

**Réseau** :
```
Network
├─ In: 5.2 Mbps
├─ Out: 3.1 Mbps
└─ Connections: 47
```

**Visualisation** :
- Sparklines pour CPU/RAM
- Real-time updates (5s interval)
- Alertes si > 80%

---

## 🏗️ Architecture Proposée

### Approche 1️⃣: KISS (MVP - Recommandé)

**Stack** :
- Logs → `structlog` (déjà fait) + endpoint `/api/logs/stream`
- Métriques → PostgreSQL table `metrics` + agregation
- UI → HTMX + Chart.js (déjà utilisés)
- Temps réel → Server-Sent Events (SSE) ou polling

**Avantages** :
- ✅ Pas de nouvelle dépendance
- ✅ Utilise stack existante
- ✅ Simple à maintenir
- ✅ 2-3 jours de dev

**Architecture** :
```
┌─────────────────────────────────────────────────────────────┐
│ UI Dashboard (/ui/monitoring/advanced)                      │
│ ├─ Chart.js (graphs)                                       │
│ ├─ HTMX (updates partiels)                                 │
│ └─ SSE (logs temps réel)                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓ HTTP/SSE
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Backend                                             │
│ ├─ /api/monitoring/metrics (JSON)                          │
│ ├─ /api/monitoring/logs/stream (SSE)                       │
│ ├─ /api/monitoring/redis (status)                          │
│ └─ /api/monitoring/postgres (stats)                        │
└─────────────────────────────────────────────────────────────┘
                    ↓                      ↓
┌──────────────────────────┐  ┌─────────────────────────────┐
│ PostgreSQL               │  │ Redis                       │
│ ├─ pg_stat_statements    │  │ ├─ INFO (memory, keys)     │
│ ├─ pg_stat_activity      │  │ └─ SLOWLOG                 │
│ └─ Table: metrics        │  └─────────────────────────────┘
└──────────────────────────┘
```

**Stockage Métriques** :
```sql
CREATE TABLE metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,  -- 'api', 'redis', 'postgres'
    metric_name VARCHAR(100) NOT NULL, -- 'latency', 'hit_rate', etc.
    value FLOAT NOT NULL,
    metadata JSONB,

    INDEX idx_metrics_type_time (metric_type, timestamp DESC)
);

-- Partition par jour (optionnel si gros volume)
```

**Exemple d'insertion** :
```python
# Dans search_metrics.py (déjà existant)
async def record_metric(db, metric_type: str, metric_name: str, value: float, metadata: dict):
    await db.execute(
        "INSERT INTO metrics (metric_type, metric_name, value, metadata) VALUES ($1, $2, $3, $4)",
        metric_type, metric_name, value, metadata
    )
```

---

### Approche 2️⃣: Standard (Prometheus-Like)

**Stack** :
- Métriques → Prometheus + Grafana
- Logs → Loki
- Traces → Tempo (optionnel)

**Avantages** :
- ✅ Industry standard
- ✅ Nombreux dashboards pré-faits
- ✅ Alerting puissant

**Inconvénients** :
- ❌ Complexité accrue (3+ services)
- ❌ Maintenance overhead
- ❌ Pas intégré à l'UI MnemoLite

**Verdict** : ⏸️ **YAGNI** pour l'instant (sauf si besoin multi-instance)

---

### Approche 3️⃣: Hybrid

**Stack** :
- Métriques → Table PostgreSQL + export Prometheus (optionnel)
- Logs → structlog + UI intégrée
- UI → MnemoLite (natif) + Grafana (externe, optionnel)

**Avantages** :
- ✅ Flexibilité
- ✅ Peut évoluer vers Prometheus plus tard
- ✅ Pas de lock-in

---

## 🎨 UI/UX Proposée

### Dashboard Principal (`/ui/monitoring/advanced`)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🎛️  MnemoLite Monitoring                                  [Last 1h ▾]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐             │
│ │ 📊 API         │ │ 🔴 Redis       │ │ 🐘 PostgreSQL  │             │
│ │ 15 req/s       │ │ 87% hit rate   │ │ 8/20 conn      │             │
│ │ 45ms P50       │ │ 245 MB / 2 GB  │ │ 98.5% cache    │             │
│ └────────────────┘ └────────────────┘ └────────────────┘             │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ 📈 Latency by Endpoint (Last 1h)                                │   │
│ │                                                                 │   │
│ │    [Line chart: P50/P95/P99 pour chaque endpoint]              │   │
│ │                                                                 │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│ ┌──────────────────────────────┐ ┌──────────────────────────────┐    │
│ │ 🔴 Redis Hit Rate            │ │ 🐘 Top Slow Queries          │    │
│ │ [Gauge chart: 87%]           │ │ 1. SELECT ... (245ms)        │    │
│ │                              │ │ 2. INSERT ... (180ms)        │    │
│ │ search: 92%                  │ │ 3. SELECT ... (120ms)        │    │
│ │ embed: 78%                   │ │ [View Details →]             │    │
│ │ graph: 95%                   │ └──────────────────────────────┘    │
│ └──────────────────────────────┘                                      │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐   │
│ │ 📝 Live Logs                                            [Pause] │   │
│ │ [Level ▾] [Service ▾] [Search: ____________]                   │   │
│ │                                                                 │   │
│ │ 21:50:12 [INFO ] search_completed latency=45ms                 │   │
│ │ 21:50:11 [DEBUG] cache_hit key="search:..."                    │   │
│ │ 21:50:10 [WARN ] slow_query duration=120ms                     │   │
│ │ 21:50:05 [ERROR] timeout duration=5002ms                       │   │
│ │                                                                 │   │
│ │ [Auto-scroll ✓] [Export CSV]                                   │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pages Détaillées

**`/ui/monitoring/redis`** :
- Hit rate par cache type (timeline)
- Memory usage (gauge)
- Top keys (table)
- Evictions (timeline)
- Commandes Redis (SLOWLOG)

**`/ui/monitoring/postgres`** :
- Slow queries (table avec EXPLAIN)
- Connexions actives (gauge)
- Cache hit ratio (timeline)
- Tables sizes (bar chart)
- Index usage (table)

**`/ui/monitoring/api`** :
- Latency par endpoint (heatmap)
- Error rate (timeline)
- Top erreurs (table)
- Request rate (sparkline)

**`/ui/monitoring/logs`** :
- Stream temps réel
- Filtres avancés
- Full-text search
- Export

---

## 🚀 Features Proposées (Prioritées)

### 🟢 MVP (Must-Have - 5 pts)

**Story 20.1: Infrastructure de Métriques (2 pts)**
- Table `metrics` PostgreSQL
- Service `MetricsCollector`
- Endpoints API `/api/monitoring/*`

**Story 20.2: Dashboard Monitoring UI (2 pts)**
- Page `/ui/monitoring/advanced`
- Cartes résumé (API, Redis, PostgreSQL)
- Charts basiques (Chart.js)

**Story 20.3: Logs en Temps Réel (1 pt)**
- SSE endpoint `/api/logs/stream`
- UI logs avec filtres
- Auto-scroll + colorisation

---

### 🟡 Standard (Should-Have - 8 pts)

**Story 20.4: Redis Monitoring Détaillé (2 pts)**
- Hit rate par cache type
- Memory usage + alertes
- Top keys analysis

**Story 20.5: PostgreSQL Monitoring Détaillé (3 pts)**
- Slow queries avec EXPLAIN
- Connexions actives
- Cache hit ratio
- Index usage

**Story 20.6: API Performance Analysis (2 pts)**
- Latency breakdown par endpoint
- Error tracking avec stack traces
- Request rate timeline

**Story 20.7: Alerting Simple (1 pt)**
- Alertes configurables (seuils)
- Notifications dans l'UI (badge rouge)
- Log des alertes

---

### 🔵 Nice-to-Have (8 pts)

**Story 20.8: Export Prometheus (2 pts)**
- Endpoint `/metrics` format Prometheus
- Export metrics vers TSDB externe

**Story 20.9: Distributed Tracing (3 pts)**
- Trace ID per request
- Span tracking (DB, Redis, API)
- UI flame graph

**Story 20.10: Predictive Alerting (2 pts)**
- ML simple (trend analysis)
- "Cache hit rate baisse depuis 1h"
- "Latency augmente depuis 30min"

**Story 20.11: Historical Reports (1 pt)**
- Daily/Weekly reports PDF
- Email digest
- Trends analysis

---

## 🎯 API Design

### Endpoints Proposés

```python
# Métriques
GET  /api/monitoring/metrics?type=api&period=1h       → JSON metrics
GET  /api/monitoring/metrics/summary                  → JSON summary (cards)

# Redis
GET  /api/monitoring/redis/status                     → JSON status
GET  /api/monitoring/redis/keys                       → JSON top keys
GET  /api/monitoring/redis/stats                      → JSON hit rate, etc.

# PostgreSQL
GET  /api/monitoring/postgres/status                  → JSON status
GET  /api/monitoring/postgres/slow_queries            → JSON slow queries
GET  /api/monitoring/postgres/connections             → JSON connections
GET  /api/monitoring/postgres/tables                  → JSON tables stats

# Logs
GET  /api/monitoring/logs/stream                      → SSE stream
GET  /api/monitoring/logs?level=error&since=1h        → JSON logs

# Système
GET  /api/monitoring/system/cpu                       → JSON CPU usage
GET  /api/monitoring/system/memory                    → JSON memory usage
GET  /api/monitoring/system/disk                      → JSON disk I/O
```

---

## 🔧 Implémentation Technique

### 1. Service de Collection

```python
# api/services/metrics_collector.py

import asyncio
import psutil
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncEngine

class MetricsCollector:
    """Collecte métriques système, Redis, PostgreSQL."""

    def __init__(self, engine: AsyncEngine, redis_client):
        self.engine = engine
        self.redis = redis_client

    async def collect_api_metrics(self) -> Dict[str, Any]:
        """Collecte métriques API depuis table metrics."""
        async with self.engine.begin() as conn:
            # Agrégation dernière heure
            result = await conn.execute("""
                SELECT
                    metric_name,
                    AVG(value) as avg_value,
                    MAX(value) as max_value,
                    COUNT(*) as count
                FROM metrics
                WHERE metric_type = 'api'
                  AND timestamp > NOW() - INTERVAL '1 hour'
                GROUP BY metric_name
            """)
            return {row['metric_name']: row for row in result}

    async def collect_redis_metrics(self) -> Dict[str, Any]:
        """Collecte métriques Redis."""
        info = await self.redis.info()

        return {
            "memory_used_mb": info['used_memory'] / (1024 * 1024),
            "memory_max_mb": 2048,  # from config
            "keys_total": await self.redis.dbsize(),
            "hit_rate": self._calculate_hit_rate(info),
            "connected_clients": info['connected_clients'],
            "evicted_keys": info.get('evicted_keys', 0)
        }

    async def collect_postgres_metrics(self) -> Dict[str, Any]:
        """Collecte métriques PostgreSQL."""
        async with self.engine.begin() as conn:
            # Connexions actives
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
                    sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100 as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            cache_hit = result.scalar()

            return {
                "connections_active": connections['active'],
                "connections_idle": connections['idle'],
                "connections_total": connections['total'],
                "cache_hit_ratio": cache_hit or 0
            }

    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collecte métriques système (CPU, RAM)."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_used_mb": psutil.virtual_memory().used / (1024 * 1024),
            "memory_total_mb": psutil.virtual_memory().total / (1024 * 1024),
            "memory_percent": psutil.virtual_memory().percent
        }
```

---

### 2. Endpoint API

```python
# api/routes/monitoring_routes.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from services.metrics_collector import MetricsCollector

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

@router.get("/metrics/summary")
async def get_metrics_summary(collector: MetricsCollector = Depends()):
    """Résumé des métriques pour dashboard."""
    return {
        "api": await collector.collect_api_metrics(),
        "redis": await collector.collect_redis_metrics(),
        "postgres": await collector.collect_postgres_metrics(),
        "system": await collector.collect_system_metrics()
    }

@router.get("/logs/stream")
async def stream_logs():
    """Stream logs en temps réel via SSE."""
    async def event_generator():
        # Lire logs depuis file ou database
        while True:
            # Simulate log stream
            log = await get_latest_log()
            yield f"data: {json.dumps(log)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 3. UI Component (HTMX + Chart.js)

```html
<!-- templates/monitoring_advanced.html -->

<div id="monitoring-dashboard" hx-get="/api/monitoring/metrics/summary"
     hx-trigger="every 5s" hx-swap="innerHTML">

    <!-- Cards Summary -->
    <div class="metrics-cards">
        <div class="card">
            <h3>📊 API</h3>
            <div class="metric-value">{{ api.request_rate }} req/s</div>
            <div class="metric-detail">P50: {{ api.latency_p50 }}ms</div>
        </div>

        <div class="card">
            <h3>🔴 Redis</h3>
            <div class="metric-value">{{ redis.hit_rate }}%</div>
            <div class="metric-detail">{{ redis.memory_used_mb }} MB</div>
        </div>

        <div class="card">
            <h3>🐘 PostgreSQL</h3>
            <div class="metric-value">{{ postgres.connections_active }}/20</div>
            <div class="metric-detail">Cache: {{ postgres.cache_hit_ratio }}%</div>
        </div>
    </div>

    <!-- Charts -->
    <canvas id="latencyChart"></canvas>

    <script>
        // Update Chart.js avec nouvelles données
        updateLatencyChart({{ chart_data | tojson }});
    </script>
</div>

<!-- Live Logs (SSE) -->
<div id="live-logs">
    <script>
        const evtSource = new EventSource('/api/monitoring/logs/stream');
        evtSource.onmessage = (event) => {
            const log = JSON.parse(event.data);
            appendLog(log);  // Ajoute log à la liste
        };
    </script>
</div>
```

---

## 💡 Idées Supplémentaires

### 1. Health Checks Auto

**Endpoint** : `/health/detailed`

```json
{
    "status": "healthy",
    "checks": {
        "postgres": {"status": "ok", "latency_ms": 2},
        "redis": {"status": "ok", "latency_ms": 1},
        "disk": {"status": "ok", "usage_percent": 45},
        "memory": {"status": "warning", "usage_percent": 85}
    }
}
```

**UI** : Badge vert/orange/rouge dans navbar

---

### 2. Request Tracing

**Ajouter Trace ID** :
```python
import uuid
from fastapi import Request

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id

    # Log avec trace_id
    logger.bind(trace_id=trace_id).info("request_started")

    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response
```

**Affichage** : Dans logs UI, cliquer sur trace_id affiche tous les logs liés

---

### 3. Comparaison Temporelle

**Feature** : Comparer metrics "maintenant" vs "hier" vs "semaine dernière"

```
Latency P95
├─ Now:       120ms
├─ Yesterday: 115ms (+4.3%)
└─ Last Week: 105ms (+14.3%)  ⚠️ Trending up
```

---

### 4. Query Explain Automatique

**Feature** : Slow query détectée → EXPLAIN ANALYZE automatique → stocké

**UI** : Afficher plan d'exécution avec suggestions d'index

```sql
-- Query détectée lente
SELECT * FROM code_chunks WHERE name LIKE '%validate%'

-- EXPLAIN montre: Seq Scan (slow)
-- Suggestion: CREATE INDEX idx_code_chunks_name_trgm
--             USING gin (name gin_trgm_ops)
```

---

### 5. Anomaly Detection Simple

**Feature** : Détection de patterns anormaux

```
🚨 Anomaly Detected!
├─ Metric: api_latency_p95
├─ Current: 450ms
├─ Expected: 120ms (based on last 7 days)
├─ Deviation: +275%
└─ Suggestion: Check slow queries or cache hit rate
```

**Algorithme** : Simple moving average + 3σ (écart-type)

---

### 6. Export & Reporting

**Features** :
- Export CSV/JSON pour analyses externes
- PDF report quotidien/hebdomadaire
- Email digest (optionnel)

```python
@router.get("/monitoring/export")
async def export_metrics(format: str = "csv", period: str = "24h"):
    """Export métriques en CSV ou JSON."""
    metrics = await collector.collect_historical(period)

    if format == "csv":
        return generate_csv(metrics)
    else:
        return metrics
```

---

## ⚠️ Considérations Importantes

### Performance

**Impact sur API** :
- Collection métriques : ~1-2ms overhead par request
- Insertion DB : async (non-bloquant)
- Agregation : faite en background (cron 1min)

**Optimisations** :
- Batch inserts (toutes les 10s)
- Indexes sur table `metrics`
- Retention policy (garder 30 jours max)

---

### Sécurité

**Accès** :
- Dashboard monitoring = Admin only
- Authentication requise
- RBAC (role-based access control)

**Logs** :
- Ne jamais logger passwords/tokens
- Anonymiser données sensibles
- Filtrer PII (personally identifiable information)

---

### Scalabilité

**Single Instance** :
- Table `metrics` PostgreSQL OK
- Agregation en mémoire OK

**Multi-Instance** :
- Besoin Prometheus/Grafana
- Shared Redis pour métriques
- Distributed tracing (Tempo)

---

## 📊 Estimation Points

| Story | Description | Points | Priorité |
|-------|-------------|--------|----------|
| 20.1 | Infrastructure métriques | 2 | 🟢 MVP |
| 20.2 | Dashboard UI | 2 | 🟢 MVP |
| 20.3 | Logs temps réel | 1 | 🟢 MVP |
| 20.4 | Redis monitoring | 2 | 🟡 Standard |
| 20.5 | PostgreSQL monitoring | 3 | 🟡 Standard |
| 20.6 | API performance | 2 | 🟡 Standard |
| 20.7 | Alerting | 1 | 🟡 Standard |
| 20.8 | Export Prometheus | 2 | 🔵 Nice |
| 20.9 | Distributed tracing | 3 | 🔵 Nice |
| 20.10 | Predictive alerting | 2 | 🔵 Nice |
| 20.11 | Reports | 1 | 🔵 Nice |
| **TOTAL** | | **21 pts** | **~4 sprints** |

**MVP** : 5 pts (1 semaine)
**Standard** : +8 pts (2 semaines)
**Nice-to-Have** : +8 pts (2 semaines)

---

## 🎯 Recommandation

### Phase 1: MVP (5 pts) - À FAIRE

**Objectif** : Avoir monitoring basique en production

**Features** :
1. Table metrics + API endpoints
2. Dashboard `/ui/monitoring/advanced`
3. Logs streaming temps réel

**Valeur** :
- ✅ Visibilité immédiate sur production
- ✅ Détection rapide des problèmes
- ✅ Pas de dépendance externe
- ✅ KISS

**Timeline** : 1 semaine (5 jours)

---

### Phase 2: Standard (8 pts) - RECOMMANDÉ

**Objectif** : Monitoring production-grade

**Features** :
1. Redis monitoring détaillé
2. PostgreSQL slow queries
3. API performance breakdown
4. Alerting simple

**Valeur** :
- ✅ Diagnostic approfondi
- ✅ Optimisations guidées par data
- ✅ Alertes proactives

**Timeline** : 2 semaines

---

### Phase 3: Nice-to-Have (8 pts) - YAGNI

**Uniquement si** :
- Multi-instance deployment
- Équipe DevOps dédiée
- Besoin traces distribuées

**Sinon** : ⏸️ Reporter

---

## 🔗 Références

- **PostgreSQL stats** : https://www.postgresql.org/docs/current/monitoring-stats.html
- **Redis INFO** : https://redis.io/commands/info/
- **Chart.js** : https://www.chartjs.org/
- **SSE** : https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- **Prometheus** : https://prometheus.io/

---

**Créé** : 2025-10-23
**Auteur** : Brainstorming session
**Status** : 🧠 À valider par équipe
**Next** : Créer EPIC-20_README.md avec plan d'action
