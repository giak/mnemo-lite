# EPIC-22: Advanced Observability & Real-Time Monitoring

**Date de création**: 2025-10-24
**Status**: 🟡 **PHASE 2 IN PROGRESS** (Story 22.5 ✅ | 22.6 ✅ | 22.7 ⏳)
**Priorité**: P1 (Production-Critical)
**Points totaux**: 19 pts (Phase 1: 5 pts ✅ | Phase 2: 6 pts 🟡 | Phase 3: 8 pts ⏸️)
**Progress**: 10/19 pts = **53% Complete**

---

## 📊 Vision

**"En 30 secondes, l'admin peut diagnostiquer n'importe quel problème production depuis l'UI"**

Production-ready observability intégrée nativement dans MnemoLite, **sans dépendances externes** (pas de Prometheus/Grafana/ELK).

---

## 🎯 Objectifs

### Problèmes Résolus
1. ❌ **Avant**: Monitoring dispersé entre `/ui/monitoring` (events), `/performance/*` (API), `/v1/cache/*` (cache)
2. ❌ **Avant**: Pas de visibilité Redis détaillée (memory, hit rate par type, evictions)
3. ❌ **Avant**: Pas de latency par endpoint (impossible de trouver les endpoints lents)
4. ❌ **Avant**: Pas de logs streaming temps réel (besoin SSH + docker logs)
5. ❌ **Avant**: Réactif au lieu de proactif (pas d'alerting)

### Solutions Apportées (Phase 1 ✅)
1. ✅ **Dashboard unifié** `/ui/monitoring/advanced` → Tout sur 1 page
2. ✅ **Métriques persistées** → Table PostgreSQL `metrics` avec historique
3. ✅ **Logs streaming** → SSE temps réel avec filtres
4. ✅ **KPIs temps réel** → API latency, Redis hit rate, PostgreSQL connections, System resources
5. ✅ **Request tracing** → trace_id (UUID) dans headers et logs

---

## 🏗️ Architecture

### Stack (Zero Nouvelle Dépendance)
```
✅ Backend: FastAPI (already present)
✅ DB: PostgreSQL 18 (already present)
✅ UI: HTMX + Jinja2 (already present)
✅ Charts: ECharts 5.5.0 (local assets)
✅ Logs: structlog (already present)
✅ Cache: Redis (already present)
✅ New: Server-Sent Events (SSE) - Native browser API
```

### Système
```
┌─────────────────────────────────────────────────────────────────┐
│ UI: /ui/monitoring/advanced                                     │
│ ├─ 4+ KPI Cards (API, Redis, PostgreSQL, System)               │
│ ├─ 4 Charts (Latency, Redis Memory, PG Connections, Resources) │
│ ├─ Metrics Table (détails)                                     │
│ └─ Logs Stream (SSE real-time)                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓ HTMX polling (10s) + SSE
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI Backend                                                 │
│ ├─ MetricsMiddleware (record latency + trace_id)               │
│ ├─ MetricsCollector (aggregate from PostgreSQL + Redis INFO)   │
│ └─ LogsBuffer (circular buffer for SSE streaming)              │
└─────────────────────────────────────────────────────────────────┘
             ↓                    ↓                   ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ PostgreSQL       │  │ Redis            │  │ structlog        │
│ Table: metrics   │  │ INFO commands    │  │ Logs buffer      │
│ - Latency/req    │  │ - Memory stats   │  │ - Circular       │
│ - Indexed        │  │ - Hit/miss       │  │ - Max 1000 logs  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 📝 Stories & Status

### 🟢 Phase 1: MVP (5 pts) - ✅ **COMPLETED**

#### ✅ Story 22.1: Metrics Infrastructure (2 pts)
**Status**: ✅ Completed (2025-10-24)
**Files**:
- `db/migrations/v5_to_v6_metrics_table.sql` (migration)
- `api/services/metrics_collector.py` (service layer)
- `api/middleware/metrics_middleware.py` (auto-recording)
- `api/routes/monitoring_routes_advanced.py` (endpoints)

**Deliverables**:
- [x] Table `metrics` créée avec indexes optimisés
- [x] 158+ métriques API déjà collectées
- [x] MetricsMiddleware record latency automatiquement
- [x] trace_id (UUID) injecté dans headers et logs
- [x] Endpoint `/api/monitoring/advanced/summary` fonctionnel

**Voir**: `EPIC-22_STORY_22.1_COMPLETION_REPORT.md`

---

#### ✅ Story 22.2: Dashboard Unifié UI (2 pts)
**Status**: ✅ Completed (2025-10-24)
**Files**:
- `templates/monitoring_advanced.html` (dashboard UI)
- `static/vendor/echarts.min.js` (local assets)
- `static/vendor/prism*.js` (local assets)

**Deliverables**:
- [x] Page `/ui/monitoring/advanced` accessible
- [x] 6 KPI cards (API P95, Redis hit rate, PG cache, CPU, Memory, RPS)
- [x] 4 ECharts (Latency, Redis Memory, PG Connections, System Resources)
- [x] Auto-refresh HTMX (10s interval)
- [x] SCADA theme cohérent (GitHub dark)
- [x] Metrics table détaillée avec status colors

**Voir**: `EPIC-22_STORY_22.2_COMPLETION_REPORT.md`

---

#### ✅ Story 22.3: Logs Streaming Temps Réel (1 pt)
**Status**: ✅ Completed (2025-10-24)
**Files**:
- `api/services/logs_buffer.py` (circular buffer)
- `api/routes/monitoring_routes_advanced.py` (SSE endpoint)
- `templates/monitoring_advanced.html` (EventSource client)

**Deliverables**:
- [x] SSE endpoint `/api/monitoring/advanced/logs/stream` actif
- [x] LogsBuffer (circular, max 1000 logs, ~1MB)
- [x] Logs affichés temps réel avec colorisation
- [x] Auto-scroll et filtres (level, search)
- [x] Intégration structlog → buffer → SSE

**Voir**: `EPIC-22_STORY_22.3_COMPLETION_REPORT.md`

---

**Phase 1 Summary**: `EPIC-22_PHASE_1_COMPLETION_REPORT.md`

---

### 🟡 Phase 2: Standard (6 pts) - 🟡 **IN PROGRESS** (5/6 pts = 83%)

#### ⏸️ Story 22.4: Redis Monitoring Détaillé (2 pts) - **SKIPPED**
**Status**: ⏸️ Skipped (YAGNI - deferred to Phase 3)
**Raison**: Cache vide actuellement (0 keys), pas de problème identifié. Manual diagnosis suffisant.
**Trigger pour réactivation**: Redis keys > 5000 OU (hit_rate < 70% ET memory > 80%)
**Objectif**: Breakdown Redis par cache type

**Features**:
- Hit rate par type (search_results, embeddings, graph_traversal)
- Memory usage détaillé
- Keys count par prefix
- Evictions timeline
- Top keys (SCAN)

**Acceptance**:
- [ ] Endpoint `/api/monitoring/redis/detailed`
- [ ] UI: Cards breakdown par cache type
- [ ] Gauge memory avec alertes

---

#### ✅ Story 22.5: API Performance Par Endpoint (3 pts)
**Status**: ✅ Completed (2025-10-24)
**Objectif**: Latency breakdown par endpoint
**Durée**: 3.25h (estimé: 4.5h) ⚡ **28% plus rapide**

**Features Delivered**:
- ✅ Service `EndpointPerformanceService` (3 methods: stats, slow endpoints, error hotspots)
- ✅ 3 REST API endpoints (`/performance/endpoints`, `/performance/slow-endpoints`, `/performance/error-hotspots`)
- ✅ Endpoint normalization (UUIDs → :uuid, IDs → :id, hashes → :hash)
- ✅ UI Table: 20 endpoints avec P50/P95/P99, error rate, RPS
- ✅ UI Panel: "Slow Endpoints" avec impact calculation (time wasted/hour)
- ✅ Color-coding dynamique (latency + error rate)
- ✅ Sélecteur période (1h/24h/7d)
- ✅ Auto-refresh 10s intégré

**Acceptance**:
- [x] Agrégation depuis `metrics` table (PERCENTILE_CONT)
- [x] UI: Table triable (endpoint, method, latency, errors)
- [x] Endpoint normalization middleware
- [x] Slow endpoints panel avec impact calculation
- [x] Query performance < 50ms ✅
- [x] 250+ métriques analysées

**Files**:
- `api/services/endpoint_performance_service.py` (NEW, 313 LOC)
- `api/routes/monitoring_routes_advanced.py` (+142 LOC)
- `api/middleware/metrics_middleware.py` (+48 LOC)
- `api/dependencies.py` (+28 LOC)
- `templates/monitoring_advanced.html` (+273 LOC)

**Voir**: `EPIC-22_STORY_22.5_COMPLETION_REPORT.md`

---

#### ✅ Story 22.6: Request Tracing (2 pts)
**Status**: ✅ Completed (2025-10-24)
**Objectif**: trace_id end-to-end cliquable
**Durée**: 2h (design + implementation + testing + documentation)

**Features Delivered**:
- ✅ contextvars-based trace_id propagation (zero boilerplate)
- ✅ Clickable trace_id badges in logs UI (🔍 a1b2c3d4)
- ✅ Filter by trace_id with live match indicator
- ✅ X-Trace-ID header in all responses
- ✅ LogsBuffer integration with trace_id in metadata
- ✅ YAGNI: Timeline visualization deferred (single service, no distributed tracing need)

**Acceptance**:
- [x] Tous logs ont trace_id (via structlog processor)
- [x] UI: trace_id cliquable dans logs stream
- [x] Filter input + clear button + match count
- [x] Auto-filter new logs when filter active

**Files**:
- `api/utils/logging_config.py` (NEW, 95 LOC)
- `api/main.py` (+3 LOC - configure_logging call)
- `api/middleware/metrics_middleware.py` (+3 LOC - contextvars.set)
- `templates/monitoring_advanced.html` (+172 LOC - UI badges & filter)

**Voir**: `EPIC-22_STORY_22.6_COMPLETION_REPORT.md`

---

#### ⏳ Story 22.7: Smart Alerting (1 pt)
**Status**: ⏳ Not Started
**Objectif**: Alertes automatiques seuils

**Features**:
- Service AlertingService (check thresholds)
- Table `alerts` (id, type, severity, message, ack)
- Endpoint `/api/monitoring/alerts`
- UI: Badge navbar (count alerts)
- Modal alerts avec acknowledge

**Seuils**:
- Cache hit rate < 70% → Warning
- Memory > 80% → Critical
- Slow queries > 1s → Warning
- Evictions > 100/h → Info
- Error rate > 5% → Critical

**Acceptance**:
- [ ] Alertes créées automatiquement (background task 1min)
- [ ] UI badge + modal
- [ ] Acknowledge → archivage

---

### 🔵 Phase 3: Nice-to-Have (8 pts) - ⏸️ **YAGNI**

Stories 22.8-22.12:
- Historical Trends (comparaison temporelle)
- Slow Query Explain Auto
- Export & Reporting (CSV/JSON)
- Prometheus Export (optionnel)
- Anomaly Detection (ML simple)

**Décision**: Reporter après Phase 2 validée

---

## 📊 Métriques Clés (État Actuel)

D'après `/api/monitoring/advanced/summary` (2025-10-24):

**API**:
- P95 Latency: 108.96ms
- P99 Latency: 115.33ms
- Request count: 158 (dernière 1h)
- Throughput: 0.04 req/s
- Error rate: 5.7% (9 errors)

**Redis**:
- Connected: ✅ Yes
- Memory: 1.05 MB / 2048 MB (0.05%)
- Hit rate: 0% (cache vide actuellement)
- Keys: 0
- Evicted: 0

**PostgreSQL**:
- Connections: 6 / 100 (1 active, 5 idle)
- Cache hit ratio: 95.36% ✅
- DB size: 26.11 MB
- Slow queries (>100ms): 58

**System**:
- CPU: 15% (16 cores)
- Memory: 73.4% (38.7 GB / 58 GB)
- Disk: 81.8% (728 GB / 937 GB)

---

## 🎨 UI Design (SCADA Theme)

Dashboard `/ui/monitoring/advanced`:
- **Status Banner**: 🟢 Operational | Auto-refresh toggle
- **KPI Grid**: 6 cards (API, Redis, PostgreSQL, CPU, Memory, RPS)
- **Charts Grid**: 4 ECharts (Latency, Redis Memory, PG Connections, Resources)
- **Metrics Table**: Detailed breakdown avec status colors
- **Logs Stream**: SSE real-time avec filtres

**Theme**: GitHub Dark + SCADA Industrial (zero rounded corners, monospace fonts, cyan/green accents)

---

## 🔗 Fichiers Clés

### Backend
```
api/
├── middleware/
│   └── metrics_middleware.py          # Auto-record latency + trace_id
├── routes/
│   └── monitoring_routes_advanced.py  # /api/monitoring/advanced/*
├── services/
│   ├── metrics_collector.py           # Collect from PostgreSQL/Redis/System
│   └── logs_buffer.py                 # Circular buffer for SSE
db/migrations/
└── v5_to_v6_metrics_table.sql         # CREATE TABLE metrics
```

### Frontend
```
templates/
└── monitoring_advanced.html            # Dashboard UI
static/vendor/
├── echarts.min.js                      # Charts (local)
├── prism*.js                           # Syntax highlighting (local)
└── prism-okaidia.min.css               # Prism theme (local)
```

---

## ⚠️ Considérations Techniques

### Performance Impact
- **MetricsMiddleware overhead**: ~1-2ms par request (async INSERT)
- **Batch inserts** possible si volume élevé (100 metrics/batch)
- **Retention**: 30 jours (cleanup cron job)

### Scalabilité
- **Single instance** (actuel): ✅ Table `metrics` PostgreSQL suffisante
- **Multi-instance** (futur): ⏸️ Besoin Prometheus + shared Redis

### Sécurité
- `/ui/monitoring/advanced` = Admin only (TODO: add auth check)
- API endpoints protégés
- Logs: Ne jamais logger passwords/tokens

---

## 🧪 Tests

**Unit Tests**:
- `tests/test_metrics_collector.py`
- `tests/test_metrics_middleware.py`

**Integration Tests**:
- `tests/integration/test_monitoring_advanced_ui.py`
- `tests/integration/test_sse_streaming.py`

**Coverage**:
- MetricsCollector: ✅ Tested
- MetricsMiddleware: ✅ Tested
- SSE endpoint: ✅ Tested
- UI: ⏳ Manual testing only

---

## 📈 Timeline & Effort

| Phase | Stories | Points | Durée Estimée | Durée Réelle | Status |
|-------|---------|--------|---------------|--------------|--------|
| Phase 1: MVP | 22.1-22.3 | 5 pts | 5 jours | 3 jours ⚡ | ✅ Done |
| Phase 2: Standard | 22.5-22.7 | 6 pts | 4 jours | 0.5 jour (partial) | 🟡 In Progress (50%) |
| Phase 3: Nice-to-Have | 22.4, 22.8-22.12 | 8 pts | 6 jours | - | ⏸️ YAGNI |
| **Total** | 11 stories | **19 pts** | **15 jours** | **3.5 jours** | **42% done** |

**Notes**:
- Story 22.4 (Redis breakdown) deferred to Phase 3 (YAGNI - no current need)
- Phase 1 delivered 40% faster than estimated (3 days vs 5 days)
- Phase 2 Story 22.5 delivered 28% faster (3.25h vs 4.5h)

**Velocity**: 8 pts / 3.5 days = **2.29 pts/day** (excellent)

---

## 🎯 Prochaines Étapes

### Immédiat (Phase 2)
1. **Story 22.4**: Redis breakdown par cache type
2. **Story 22.5**: API performance par endpoint (P95 heatmap)
3. **Story 22.6**: Request tracing cliquable
4. **Story 22.7**: Smart alerting

### Nice-to-Have (Phase 3)
- Attendre validation Phase 2
- Évaluer besoin réel (YAGNI test)

---

## 📚 Documentation

- **Design**: `EPIC-22_OBSERVABILITY_ULTRATHINK.md`
- **Implementation**: `EPIC-22_PHASE_1_IMPLEMENTATION_ULTRATHINK.md`
- **Phase 1 Summary**: `EPIC-22_PHASE_1_COMPLETION_REPORT.md`
- **Phase 1 Story Reports**:
  - `EPIC-22_STORY_22.1_COMPLETION_REPORT.md` (Metrics Infrastructure)
  - `EPIC-22_STORY_22.2_COMPLETION_REPORT.md` (Dashboard UI)
  - `EPIC-22_STORY_22.3_COMPLETION_REPORT.md` (Logs Streaming)
- **Phase 2 Story Reports**:
  - `EPIC-22_STORY_22.4_ULTRATHINK.md` (Redis Monitoring - SKIPPED)
  - `EPIC-22_STORY_22.5_ULTRATHINK.md` (API Performance - Design)
  - `EPIC-22_STORY_22.5_COMPLETION_REPORT.md` (API Performance - Completed ✅)

---

## ✅ Acceptance Criteria (Phase 1)

### Global
- [x] Dashboard `/ui/monitoring/advanced` accessible et fonctionnel
- [x] Métriques temps réel (auto-refresh 10s)
- [x] Logs streaming SSE connecté
- [x] Zero dépendances externes (pas de Prometheus/Grafana)
- [x] SCADA theme cohérent
- [x] Assets locaux (echarts, prism)

### Métriques
- [x] Table `metrics` créée avec indexes
- [x] API latency enregistrée automatiquement
- [x] trace_id dans tous headers/logs
- [x] Agrégation P50/P95/P99 fonctionnelle
- [x] Redis/PostgreSQL/System metrics collectés

### UI/UX
- [x] KPI cards affichent valeurs réelles
- [x] Charts ECharts initialisés et mis à jour
- [x] Logs stream affiche logs temps réel
- [x] Filtres logs fonctionnels
- [x] Auto-scroll activable

---

**Créé**: 2025-10-24
**Dernière mise à jour**: 2025-10-24
**Auteur**: Claude Code + User
**Status**: Phase 1 ✅ Complete | Phase 2 ⏳ Pending
**Version**: 1.0.0
