# EPIC-22: Advanced Observability & Real-Time Monitoring - ULTRATHINK

**Date**: 2025-10-24
**Status**: 🧠 **BRAINSTORMING**
**Priorité**: P1 (Production-Critical)
**Dépendances**: EPIC-08 (Cache L2) ✅, EPIC-10 (Perf Validation) ✅

---

## 📊 État des Lieux (Ce qui existe)

### ✅ Monitoring Existant

**Dashboard UI** (`/ui/monitoring`):
- ✅ KPI cards (events critical/warning/info, DB size)
- ✅ Timeline events (ECharts)
- ✅ Events critiques (24h)
- ✅ Distribution par sévérité/projet/catégorie
- ✅ Auto-refresh 30s

**API Endpoints Existants**:
```
✅ /api/monitoring/status               → System status
✅ /api/monitoring/events/critical      → Critical events (24h)
✅ /api/monitoring/events/timeline      → Timeline (24h/7d/30d)
✅ /api/monitoring/events/distribution  → Distribution by severity/project/category
✅ /api/monitoring/metrics              → Total events, DB size, cache hit ratio, connections

✅ /performance/metrics                 → App metrics (counters, timers, gauges)
✅ /performance/cache/stats             → Query cache + embedding cache stats
✅ /performance/system                  → CPU, memory, disk, process stats
✅ /performance/database/pool           → DB pool stats (connections)
✅ /performance/database/slow-queries   → Slow queries (pg_stat_statements)
✅ /performance/database/indexes        → Index usage stats
✅ /performance/optimize/suggestions    → Auto suggestions

✅ /v1/cache/stats                      → L1/L2 cascade cache stats
✅ /v1/cache/flush                      → Manual cache flush
✅ /v1/cache/clear-all                  → Clear all caches
```

**Forces**:
- ✅ Foundation solide (PostgreSQL, cache, system metrics)
- ✅ SCADA theme cohérent
- ✅ Zero dépendances externes (pas de Prometheus/Grafana)
- ✅ HTMX + ECharts déjà intégrés

---

## ❌ Ce Qui Manque (Gaps Critiques)

### 1. ❌ **Redis Monitoring Détaillé**

**Problème**: `/v1/cache/stats` retourne stats L1/L2, mais **pas de détails Redis** :
- ❌ Memory usage Redis (used/max/percent)
- ❌ Hit rate par cache type (search_results, embeddings, graph_traversal)
- ❌ Keys count par type
- ❌ Evictions (LRU)
- ❌ Slow commands (SLOWLOG)
- ❌ Connections actives
- ❌ Average TTL par type

**Impact**: Impossible de diagnostiquer :
- "Pourquoi hit rate baisse ?" → Pas de breakdown par type
- "Redis plein ?" → Pas de vue memory
- "Evictions ?" → Pas de metric

---

### 2. ❌ **API Performance Par Endpoint**

**Problème**: `/performance/metrics` agrège tout, **pas de détails par endpoint** :
- ❌ Latency P50/P95/P99 par endpoint
- ❌ Throughput (req/s) par endpoint
- ❌ Error rate par endpoint
- ❌ Top erreurs avec stack traces
- ❌ Timeline latency (heatmap)

**Impact**: Impossible de répondre à :
- "Quel endpoint est lent ?"
- "Quelle erreur provoque les timeouts ?"
- "Latency normale pour /v1/code/search/hybrid ?"

---

### 3. ❌ **Logs en Temps Réel (Streaming)**

**Problème**: Pas de visualisation logs dans l'UI :
- ❌ Stream logs temps réel (SSE)
- ❌ Filtres (level, service, search)
- ❌ Colorisation par level
- ❌ Export logs (CSV/JSON)

**Impact**: Pour déboguer, il faut :
1. SSH sur serveur
2. `docker logs mnemo-api | grep ERROR`
3. Pas d'historique filtrable

---

### 4. ❌ **Dashboard Unifié (One-Pager)**

**Problème**: Monitoring dispersé :
- `/ui/monitoring` → Events only
- `/performance/*` → API calls only
- `/v1/cache/*` → API calls only

**Besoin**: **Dashboard unifié** avec tout sur 1 page :
- API KPIs (latency, throughput)
- Redis KPIs (hit rate, memory)
- PostgreSQL KPIs (connections, slow queries)
- Logs stream
- System resources (CPU, RAM)

---

### 5. ❌ **Alerting & Notifications**

**Problème**: Aucune alerte automatique :
- ❌ Cache hit rate < 70% → Warning
- ❌ Memory > 80% → Critical
- ❌ Slow queries > 1000ms → Warning
- ❌ Evictions > 100/h → Info

**Impact**: Réactif au lieu de proactif

---

### 6. ❌ **Request Tracing (Trace ID)**

**Problème**: Pas de trace_id cross-layers :
- Requête API → Service → Repository → PostgreSQL
- Impossible de suivre une requête end-to-end

**Besoin**: Middleware trace_id + logs structlog avec trace_id

---

### 7. ❌ **Historical Trends (Comparaison Temporelle)**

**Problème**: Pas de comparaison "maintenant vs hier" :
- Latency P95 aujourd'hui: 120ms
- Latency P95 hier: 105ms → +14.3% 🚨

**Impact**: Détecter trends avant qu'ils ne deviennent critiques

---

## 🎯 Proposition EPIC-22: Advanced Observability

### Vision

**"En 30 secondes, l'admin peut diagnostiquer n'importe quel problème production depuis l'UI"**

**Features**:
1. **Dashboard Unifié** → `/ui/monitoring/advanced` (one-pager)
2. **Redis Deep Dive** → Breakdown par cache type, memory, evictions
3. **API Performance** → Latency P50/P95/P99 par endpoint, heatmap
4. **Logs Streaming** → SSE temps réel avec filtres
5. **Request Tracing** → trace_id end-to-end
6. **Smart Alerting** → Seuils configurables + notifications UI
7. **Historical Trends** → Comparaison temporelle

---

## 🏗️ Architecture EPIC-22 (Approche KISS)

### Principe: **EXTEND > REBUILD**

**Stack (Zero Nouvelle Dépendance)**:
- Logs → `structlog` (déjà présent) + SSE endpoint
- Métriques → Table PostgreSQL `metrics` (nouvelle)
- UI → HTMX + ECharts (déjà présents)
- Temps réel → Server-Sent Events (native browser)
- Cache → Redis (déjà présent)

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│ UI: /ui/monitoring/advanced                                     │
│ ├─ 4 KPI Cards (API, Redis, PostgreSQL, System)                │
│ ├─ 3 Line Charts (Latency, Hit Rate, Connections)              │
│ ├─ 1 Table (Slow Queries)                                      │
│ └─ 1 Live Logs Stream (SSE)                                    │
└─────────────────────────────────────────────────────────────────┘
                           ↓ HTMX polling (5s) + SSE
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend                                                 │
│                                                                 │
│ /api/monitoring/advanced/summary → JSON                        │
│ /api/monitoring/redis/detailed → JSON                          │
│ /api/monitoring/api/endpoints → JSON                           │
│ /api/monitoring/logs/stream → SSE                              │
│                                                                 │
│ Middleware: TraceIDMiddleware (inject trace_id)                │
│ Service: MetricsCollector (record metrics)                     │
└─────────────────────────────────────────────────────────────────┘
             ↓                    ↓                   ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ PostgreSQL       │  │ Redis            │  │ Logs             │
│                  │  │                  │  │                  │
│ Table: metrics   │  │ INFO commands    │  │ structlog        │
│ ├─ timestamp     │  │ ├─ memory        │  │ ├─ trace_id     │
│ ├─ metric_type   │  │ ├─ keys count    │  │ ├─ level        │
│ ├─ metric_name   │  │ └─ slowlog       │  │ └─ endpoint     │
│ ├─ value         │  │                  │  │                  │
│ └─ metadata      │  └──────────────────┘  └──────────────────┘
└──────────────────┘
```

---

## 📝 Stories EPIC-22 (21 points)

### 🟢 Phase 1: MVP (5 pts) - Must-Have

#### Story 22.1: Table Metrics + Infrastructure (2 pts)

**Objectif**: Stocker métriques dans PostgreSQL

**Tasks**:
- [x] Migration: table `metrics` (id, timestamp, metric_type, metric_name, value, metadata)
- [x] Service: `MetricsCollector` (record_metric, collect_api_metrics, collect_redis_metrics)
- [x] Middleware: `MetricsMiddleware` (record latency per endpoint)
- [x] Endpoint: `/api/monitoring/metrics/record` (POST)

**Acceptance Criteria**:
- [x] Table `metrics` créée avec indexes (type, timestamp DESC)
- [x] Métriques enregistrées automatiquement par request
- [x] Endpoint POST pour recording manuel

---

#### Story 22.2: Dashboard Unifié UI (2 pts)

**Objectif**: Page `/ui/monitoring/advanced` (one-pager)

**Features**:
- 4 KPI cards (API latency, Redis hit rate, PostgreSQL connections, System memory)
- Timeline latency (dernière 1h)
- Top 5 slow queries
- Redis memory gauge
- Auto-refresh HTMX (5s)

**Acceptance Criteria**:
- [x] Page `/ui/monitoring/advanced` accessible
- [x] HTMX polling `/api/monitoring/advanced/summary` (5s)
- [x] ECharts timeline latency P50/P95
- [x] SCADA theme cohérent

---

#### Story 22.3: Logs Streaming Temps Réel (1 pt)

**Objectif**: Stream logs via SSE

**Features**:
- Endpoint `/api/monitoring/logs/stream` (SSE)
- UI: Live logs avec auto-scroll
- Filtres: level (ERROR, WARN, INFO, DEBUG), service, search text
- Colorisation par level

**Acceptance Criteria**:
- [x] SSE stream fonctionne
- [x] Logs affichés en temps réel
- [x] Filtres fonctionnent côté client (JavaScript)
- [x] Auto-scroll activable

---

### 🟡 Phase 2: Standard (8 pts) - Should-Have

#### Story 22.4: Redis Monitoring Détaillé (2 pts)

**Objectif**: Breakdown Redis par cache type

**Features**:
- Endpoint `/api/monitoring/redis/detailed`
- Hit rate par type (search_results, embeddings, graph_traversal)
- Memory usage (used/max/percent)
- Keys count par type (prefix analysis)
- Evictions (last 1h)
- Top keys (SCAN avec limit)

**Acceptance Criteria**:
- [x] Endpoint retourne JSON avec breakdown
- [x] UI: Card "Redis" avec 3 sub-cards (search, embeddings, graph)
- [x] Gauge memory avec alerte si > 80%

---

#### Story 22.5: API Performance Par Endpoint (3 pts)

**Objectif**: Latency breakdown par endpoint

**Features**:
- Endpoint `/api/monitoring/api/endpoints`
- Latency P50/P95/P99 par endpoint (last 1h)
- Throughput (req/s) par endpoint
- Error rate par endpoint
- Top 5 erreurs avec count
- Heatmap latency (endpoint × heure)

**Acceptance Criteria**:
- [x] Métriques agrégées depuis table `metrics`
- [x] UI: Table triable par latency/errors
- [x] Heatmap ECharts (endpoint × heure)
- [x] P95 latency par endpoint visible

---

#### Story 22.6: Request Tracing (2 pts)

**Objectif**: Trace_id end-to-end

**Features**:
- Middleware `TraceIDMiddleware` (inject trace_id UUID)
- Header `X-Trace-ID` dans response
- Logs structlog avec trace_id
- UI: Logs stream affiche trace_id cliquable
- Click trace_id → filter logs par trace_id

**Acceptance Criteria**:
- [x] Tous les logs ont trace_id
- [x] Header X-Trace-ID présent
- [x] UI logs: clic sur trace_id filtre automatiquement

---

#### Story 22.7: Smart Alerting (1 pt)

**Objectif**: Alertes automatiques

**Features**:
- Service `AlertingService` (check_thresholds)
- Alerts table (id, alert_type, severity, message, timestamp, acknowledged)
- Endpoint `/api/monitoring/alerts` (GET active alerts)
- UI: Badge rouge dans navbar (count alerts)
- Clic badge → modal avec liste alerts

**Seuils**:
- Cache hit rate < 70% → Warning
- Memory > 80% → Critical
- Slow queries > 1s → Warning
- Evictions > 100/h → Info
- Error rate > 5% → Critical

**Acceptance Criteria**:
- [x] Alertes créées automatiquement (background task 1min)
- [x] UI badge affiche count
- [x] Alertes archivables (acknowledged=true)

---

### 🔵 Phase 3: Nice-to-Have (8 pts)

#### Story 22.8: Historical Trends (2 pts)

**Objectif**: Comparaison temporelle

**Features**:
- Endpoint `/api/monitoring/trends`
- Comparison: now vs 1h ago vs 1d ago vs 1w ago
- Metrics: latency, hit rate, connections, error rate
- UI: Delta % avec flèches (↑ rouge, ↓ vert)

**Acceptance Criteria**:
- [x] Trends calculés depuis table `metrics`
- [x] UI: Cards affichent delta %
- [x] Warning si trend > +20%

---

#### Story 22.9: Slow Query Explain Auto (2 pts)

**Objectif**: EXPLAIN automatique pour slow queries

**Features**:
- Détection slow query (> 1s)
- EXPLAIN ANALYZE automatique
- Stockage plan dans metadata
- UI: Affichage plan + suggestions d'index
- Suggestions: "Missing index on column X"

**Acceptance Criteria**:
- [x] Slow queries capturées avec EXPLAIN
- [x] UI: Bouton "View Plan" pour chaque slow query
- [x] Suggestions index affichées

---

#### Story 22.10: Export & Reporting (1 pt)

**Objectif**: Export metrics

**Features**:
- Endpoint `/api/monitoring/export?format=csv&period=24h`
- Formats: CSV, JSON
- UI: Bouton "Export" dans dashboard

**Acceptance Criteria**:
- [x] CSV/JSON téléchargeable
- [x] Periods: 1h, 24h, 7d, 30d

---

#### Story 22.11: Prometheus Export (2 pts)

**Objectif**: Métriques format Prometheus (optionnel)

**Features**:
- Endpoint `/metrics` (Prometheus format)
- Exposition: counters, gauges, histograms
- Compatible Grafana

**Acceptance Criteria**:
- [x] Endpoint `/metrics` retourne Prometheus format
- [x] Importable dans Grafana

---

#### Story 22.12: Anomaly Detection (1 pt)

**Objectif**: Détection anomalies (ML simple)

**Features**:
- Algorithme: Moving Average + 3σ (écart-type)
- Métriques surveillées: latency, hit rate, error rate
- UI: Badge "Anomaly Detected" si deviation > 3σ

**Acceptance Criteria**:
- [x] Anomalies détectées automatiquement
- [x] UI: Badge orange si anomaly
- [x] Details: "Latency P95: 450ms (expected: 120ms, +275%)"

---

## 🎨 UI/UX Mockup: `/ui/monitoring/advanced`

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ 🎛️  MnemoLite Advanced Monitoring                      [Auto-Refresh: 5s ✓]  │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│ │ 📊 API       │ │ 🔴 Redis     │ │ 🐘 PostgreSQL│ │ 💻 System    │        │
│ │ P95: 85ms    │ │ Hit: 87.3%   │ │ Conn: 8/20   │ │ RAM: 45%     │        │
│ │ 15 req/s     │ │ 245 MB / 2GB │ │ Cache: 98.5% │ │ CPU: 28%     │        │
│ │ ↓ -5ms (vs1h)│ │ ↑ Evict: 23  │ │ Slow: 3/h    │ │ Disk: 62%    │        │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 📈 API Latency P95 by Endpoint (Last 1h)                  [Heatmap View]│ │
│ │                                                                         │ │
│ │    [Line chart: P50, P95, P99 pour top 5 endpoints]                    │ │
│ │    /v1/code/search/hybrid: P95 = 85ms                                  │ │
│ │    /v1/code/search/lexical: P95 = 42ms                                 │ │
│ │    /v1/code/graph/traverse: P95 = 120ms                                │ │
│ │                                                                         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│ ┌───────────────────────────────┐ ┌───────────────────────────────────────┐ │
│ │ 🔴 Redis Breakdown            │ │ 🐘 Top 5 Slow Queries                 │ │
│ │                               │ │                                       │ │
│ │ search_results:               │ │ 1. SELECT * FROM code_chunks          │ │
│ │   Hit: 92%  Keys: 342         │ │    WHERE name LIKE ...                │ │
│ │                               │ │    ⏱ 245ms (5 calls)                  │ │
│ │ embeddings:                   │ │    [View EXPLAIN →]                   │ │
│ │   Hit: 78%  Keys: 105         │ │                                       │ │
│ │                               │ │ 2. INSERT INTO events ...             │ │
│ │ graph_traversal:              │ │    ⏱ 180ms (12 calls)                 │ │
│ │   Hit: 95%  Keys: 89          │ │                                       │ │
│ │                               │ │ [...3 more queries]                   │ │
│ └───────────────────────────────┘ └───────────────────────────────────────┘ │
│                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 📝 Live Logs (SSE Stream)                                    [Pause] [▼] │ │
│ │ [Level: ALL ▾] [Service: ALL ▾] [Search: ____________] [Export CSV]    │ │
│ │                                                                         │ │
│ │ 21:50:12 [INFO ] trace=abc123 search_completed query="validate" 45ms   │ │
│ │ 21:50:11 [DEBUG] trace=abc123 cache_hit key="search:validate..." 28s   │ │
│ │ 21:50:10 [WARN ] trace=def456 slow_query duration=120ms table="code_ch"│ │
│ │ 21:50:05 [ERROR] trace=def456 timeout endpoint="/v1/code/search" 5002ms│ │
│ │                                                                         │ │
│ │ [Auto-scroll ✓] [Show trace_id ✓] [Color by level ✓]                  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 🚨 Active Alerts (2)                                                    │ │
│ │                                                                         │ │
│ │ ⚠️  WARNING - Redis evictions high: 150/h (threshold: 100/h)            │ │
│ │     Suggestion: Consider increasing Redis maxmemory or TTL              │ │
│ │     [Acknowledge]                                                       │ │
│ │                                                                         │ │
│ │ ⚠️  WARNING - Slow queries detected: 5 queries > 1s (last 1h)           │ │
│ │     Suggestion: View slow queries table above for details               │ │
│ │     [Acknowledge]                                                       │ │
│ │                                                                         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 💡 Idées Supplémentaires (Brainstorm)

### 1. **Health Check Détaillé (Health Dashboard)**

**Feature**: Page `/ui/health` (public, no auth)

**Contenu**:
- ✅/❌ PostgreSQL (latency < 10ms)
- ✅/❌ Redis (latency < 5ms)
- ✅/❌ Disk space (> 10% free)
- ✅/❌ Memory (< 80% used)
- Overall status: 🟢 Operational | 🟡 Degraded | 🔴 Critical

**Use Case**: Status page pour monitoring externe (UptimeRobot, etc.)

---

### 2. **Query Plan Visualizer**

**Feature**: Visualisation plan d'exécution PostgreSQL

**UI**:
- Slow query détectée → Clic "View Plan"
- Modal affiche plan d'exécution formaté
- Highlight: Seq Scan (rouge), Index Scan (vert)
- Suggestions: "Add index on column X"

**Example**:
```
Query: SELECT * FROM code_chunks WHERE name LIKE '%validate%'

Plan:
└─ Seq Scan on code_chunks (cost=0..1000 rows=100)  🔴 SLOW
   Filter: (name ~~ '%validate%')

Suggestion:
CREATE INDEX idx_code_chunks_name_trgm
ON code_chunks USING gin (name gin_trgm_ops);
```

---

### 3. **WebSocket Events (Alternative SSE)**

**Feature**: Stream logs via WebSocket au lieu de SSE

**Avantages**:
- Bidirectionnel (client peut envoyer commandes)
- Moins de overhead que SSE
- Compatible tous browsers

**Use Case**: Si SSE pose problème (proxies, timeouts)

---

### 4. **Cache Warmup Manual**

**Feature**: Endpoint `/v1/cache/warmup`

**Params**:
- `repository`: Warm up cache for specific repository
- `popular_queries`: Warm up most popular queries (top 10)

**Use Case**: Après cache flush, reconstruire cache rapidement

---

### 5. **Query Performance Index**

**Feature**: Score global performance

**Calcul**:
```
Performance Index = (
    0.4 × Cache Hit Rate +
    0.3 × (100 - Avg Latency P95 / 10) +
    0.2 × (100 - Error Rate) +
    0.1 × (100 - Memory %)
) / 100

Example:
- Cache Hit: 87% → 0.4 × 87 = 34.8
- Latency P95: 85ms → 0.3 × (100 - 8.5) = 27.45
- Error Rate: 0.5% → 0.2 × 99.5 = 19.9
- Memory: 45% → 0.1 × 55 = 5.5

Performance Index = 87.65/100 → Grade: B+
```

**UI**: Jauge + grade (A+, A, B, C, D, F)

---

### 6. **Distributed Tracing (OpenTelemetry - Nice-to-Have)**

**Feature**: Traces distribuées (si multi-service plus tard)

**Stack**: OpenTelemetry + Tempo

**Use Case**: Uniquement si architecture devient multi-services

**Verdict**: ⏸️ **YAGNI** pour l'instant

---

### 7. **Performance Regression Detection**

**Feature**: Détection régression entre versions

**Workflow**:
1. Tag metrics avec version (git commit hash)
2. Compare P95 latency avant/après deploy
3. Alert si regression > 20%

**Example**:
```
🚨 Performance Regression Detected!
Version: abc123 → def456
Endpoint: /v1/code/search/hybrid
Latency P95: 85ms → 125ms (+47%)  🔴
Recommendation: Rollback or investigate
```

---

### 8. **Capacity Planning**

**Feature**: Projection future usage

**Metrics**:
- DB size growth (MB/day)
- Redis memory growth
- Request rate trend

**UI**:
```
Capacity Projections (Next 30 Days):
├─ DB Size: 150 MB → 180 MB (+20%)
├─ Redis Memory: 245 MB → 290 MB (+18%)
└─ Req Rate: 15 req/s → 20 req/s (+33%)

Warnings:
⚠️  Redis will reach 90% capacity in 45 days
    Recommendation: Increase maxmemory to 3GB
```

---

### 9. **Session Recording (Request Replay)**

**Feature**: Enregistrer requêtes pour replay

**Workflow**:
1. Capture request (method, path, body, headers)
2. Store in table `request_history`
3. UI: "Replay" button → re-execute request
4. Compare response time before/after

**Use Case**: Testing perf après optimisation

---

### 10. **Custom Dashboards**

**Feature**: Builder de dashboard custom

**UI**:
- Drag & drop widgets (chart, gauge, table)
- Save layouts per user
- Export/import dashboard config (JSON)

**Use Case**: Chaque user peut créer son propre dashboard

---

## ⚠️ Considérations Techniques

### 1. Performance Impact

**Recording Métriques**:
- Overhead: ~1-2ms par request
- Insertion DB: async (non-bloquant)
- Batch inserts: toutes les 10s (réduire load DB)

**Optimisations**:
- Table `metrics` partitionnée par jour (si volume élevé)
- Indexes: (metric_type, timestamp DESC)
- Retention: 30 jours (auto-cleanup)

---

### 2. Sécurité

**Accès Dashboard**:
- `/ui/monitoring/advanced` = **Admin only**
- Authentication requise (RBAC)
- API endpoints protégés

**Logs**:
- Ne jamais logger passwords/tokens
- Anonymiser PII (emails, IPs)
- Filtrer sensitive data

---

### 3. Scalabilité

**Single Instance** (actuel):
- ✅ Table `metrics` PostgreSQL
- ✅ Agregation en mémoire
- ✅ HTMX polling

**Multi-Instance** (futur):
- ⏸️ Besoin Prometheus + Grafana
- ⏸️ Shared Redis pour métriques
- ⏸️ Distributed tracing (Tempo)

**Verdict**: YAGNI pour l'instant, architecture actuelle suffisante

---

### 4. Retention Policy

**Metrics**:
- Keep: 30 jours
- Cleanup: Cron job daily (`DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL '30 days'`)

**Logs**:
- Keep: 7 jours
- Rotation: logrotate ou docker logs driver

---

## 📊 Estimation Points & Timeline

| Phase | Stories | Points | Timeline |
|-------|---------|--------|----------|
| **Phase 1: MVP** | 22.1-22.3 | 5 pts | 1 semaine |
| **Phase 2: Standard** | 22.4-22.7 | 8 pts | 2 semaines |
| **Phase 3: Nice-to-Have** | 22.8-22.12 | 8 pts | 2 semaines |
| **Total** | 12 stories | **21 pts** | **5 semaines** |

---

## 🎯 Recommandation

### Phase 1: MVP (5 pts) - ✅ **À FAIRE MAINTENANT**

**Objectif**: Monitoring basique production-ready

**Features**:
1. Table `metrics` + infrastructure
2. Dashboard `/ui/monitoring/advanced` unifié
3. Logs streaming temps réel (SSE)

**Valeur**:
- ✅ Visibilité immédiate production
- ✅ Détection rapide problèmes
- ✅ Zero dépendance externe
- ✅ KISS

**Timeline**: 1 semaine (5 jours)

---

### Phase 2: Standard (8 pts) - ✅ **RECOMMANDÉ**

**Objectif**: Monitoring production-grade

**Features**:
1. Redis monitoring détaillé (breakdown par type)
2. API performance par endpoint (P50/P95/P99)
3. Request tracing (trace_id)
4. Smart alerting (seuils + notifications)

**Valeur**:
- ✅ Diagnostic approfondi
- ✅ Optimisations guidées par data
- ✅ Alertes proactives
- ✅ Traçabilité end-to-end

**Timeline**: 2 semaines

---

### Phase 3: Nice-to-Have (8 pts) - ⏸️ **YAGNI (pour l'instant)**

**Uniquement si**:
- Multi-instance deployment
- Équipe DevOps dédiée
- Besoin traces distribuées
- Budget temps disponible

**Sinon**: ⏸️ Reporter après Phase 2

---

## 🔗 Comparaison avec Alternatives

### MnemoLite EPIC-22 (Approche KISS)

**Pros**:
- ✅ Zero dépendance externe
- ✅ Intégré dans UI native
- ✅ HTMX + ECharts (déjà présents)
- ✅ 1 dashboard = tout visible
- ✅ Maintenance minimale

**Cons**:
- ❌ Pas de visualisations Grafana
- ❌ Pas de clustering multi-instance (pour l'instant)

---

### Prometheus + Grafana

**Pros**:
- ✅ Industry standard
- ✅ Dashboards pré-faits
- ✅ Alerting puissant
- ✅ Multi-instance ready

**Cons**:
- ❌ 2+ services supplémentaires (Prometheus, Grafana)
- ❌ Maintenance overhead
- ❌ Pas intégré UI MnemoLite
- ❌ Complexité accrue

**Verdict**: ⏸️ **YAGNI** (sauf si multi-instance)

---

### ELK Stack (Elasticsearch + Logstash + Kibana)

**Pros**:
- ✅ Logs centralisés
- ✅ Full-text search puissant
- ✅ Visualisations Kibana

**Cons**:
- ❌ 3 services (Elastic, Logstash, Kibana)
- ❌ Lourd (>2GB RAM)
- ❌ Complexité extrême

**Verdict**: ⏸️ **OVERKILL** pour MnemoLite

---

## 🎉 Conclusion

**EPIC-22 = Production-Ready Observability Sans Complexité**

**Principe**:
- **EXTEND > REBUILD** (leverage existant)
- **KISS** (zero Prometheus/Grafana/ELK)
- **YAGNI** (Phase 1 = 80% valeur, 20% effort)

**Next Step**: Créer `EPIC-22_README.md` avec plan d'action détaillé

---

**Créé**: 2025-10-24
**Auteur**: Claude Code + Brainstorming User
**Status**: 🧠 Awaiting approval
**Version**: 1.0.0
