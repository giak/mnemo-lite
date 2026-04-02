# EPIC-22 Story 22.6: Request Tracing - ULTRATHINK

**Story**: Request Tracing (2 pts)
**Status**: 🧠 **BRAINSTORMING**
**Date**: 2025-10-24
**EPIC**: EPIC-22 Advanced Observability & Real-Time Monitoring
**Phase**: Phase 2 (Standard)
**Priority**: P2 (Nice-to-Have, evaluating YAGNI)

---

## 📋 Vision & Objectif

**Vision**: "En 1 clic sur trace_id, voir le parcours complet d'une requête à travers tous les layers (API → Service → Repository)"

**Problème actuel**:
- ✅ trace_id existe (généré dans MetricsMiddleware depuis Story 22.1)
- ✅ trace_id stocké dans table `metrics` (metadata JSONB)
- ✅ trace_id retourné dans header `X-Trace-ID`
- ❌ **trace_id PAS visible dans logs UI**
- ❌ **trace_id PAS cliquable pour filtrer logs**
- ❌ **Pas de timeline visualization du parcours requête**

**Objectif Story 22.6**:
Rendre trace_id **visible, cliquable, et utile** pour debugging end-to-end.

---

## 🔍 État Actuel (Ce qui Existe Déjà)

### ✅ Backend Infrastructure (Story 22.1)

**1. trace_id Generation** (`api/middleware/metrics_middleware.py:41`):
```python
# Generate trace_id (UUID)
trace_id = str(uuid.uuid4())
request.state.trace_id = trace_id
```

**2. trace_id Storage** (Table `metrics`):
```json
{
  "endpoint": "/api/monitoring/advanced/summary",
  "method": "GET",
  "status_code": 200,
  "trace_id": "78a40fd1-f578-4e1a-8367-0c32708ea9dd"
}
```

**3. trace_id Response Header** (`api/middleware/metrics_middleware.py:54`):
```python
response.headers["X-Trace-ID"] = trace_id
```

**Vérifié**:
```bash
$ curl -I http://localhost:8001/api/monitoring/advanced/summary
X-Trace-ID: 78a40fd1-f578-4e1a-8367-0c32708ea9dd
```

---

### ❌ Ce qui Manque (Gap Analysis)

**1. trace_id dans Logs** ❌
- Logs structlog n'incluent **pas** trace_id automatiquement
- `LogsBuffer.add_log()` reçoit metadata mais trace_id absent
- **Cause**: Pas de contexte propagé depuis middleware vers logger

**2. UI Logs Stream** ❌
- Logs affichés: `[timestamp] [level] message`
- trace_id **pas affiché** même si présent
- **Cause**: Template ne l'extrait pas de metadata

**3. Filtre par trace_id** ❌
- Pas de champ de recherche dans UI
- Pas d'endpoint API `/logs?trace_id=xxx`
- **Cause**: Pas implémenté

**4. Timeline Visualization** ❌
- Pas de vue "request flow"
- Pas de durée par layer (API → Service → Repository)
- **Cause**: Pas d'instrumentation des services

---

## 💼 Valeur Business - Use Cases Réels

### Use Case 1: Debug Erreur Intermittente

**Scenario**: "L'endpoint `/v1/search` fail 5% du temps, impossible de reproduire"

**Avant Story 22.6** ❌:
```
1. User report "search failed"
2. Dev regarde logs → 1000+ lignes/minute
3. Impossible d'identifier quelle requête a failé
4. Pas de trace_id → "Can't debug intermittent errors"
5. Time: ∞ (non-debuggable)
```

**Après Story 22.6** ✅:
```
1. User report "search failed, trace_id: a1b2c3d4-..."
2. Dev: Ouvre UI monitoring → paste trace_id
3. Filtre logs par trace_id → 5 logs apparaissent
4. Voit exactement: API → SearchService → VectorDB (timeout)
5. Time: 30 secondes
```

**Impact**: **Debug 60x plus rapide** (30min → 30s)

---

### Use Case 2: Performance Root Cause

**Scenario**: "L'endpoint `/v1/graph/traverse` est lent (P95: 450ms), où est le bottleneck ?"

**Avant Story 22.6** ❌:
```
1. Dev sait P95 = 450ms (Story 22.5 ✅)
2. Mais impossible de savoir où le temps est passé:
   - API layer ?
   - Service layer ?
   - Database query ?
3. Solution: Ajouter logs manuellement + redeploy
4. Time: 1 heure (deploy + test)
```

**Après Story 22.6** ✅:
```
1. Dev clique trace_id dans "Slow Endpoints" panel
2. Timeline apparaît:
   [API: 5ms] → [GraphService: 430ms ⚠️] → [PostgreSQL: 10ms]
3. Root cause identifié: GraphService fait loop O(n²)
4. Time: 10 secondes
```

**Impact**: **Root cause 360x plus rapide** (1h → 10s)

---

### Use Case 3: Distributed Tracing (Future Multi-Service)

**Scenario**: MnemoLite scale → multiple services (API, Worker, Cache Service)

**Actuel (Single Service)**: ✅ trace_id existe mais inutilisé

**Futur (Multi-Service)**:
- trace_id propagé via HTTP headers
- Service A appelle Service B avec `X-Trace-ID`
- Timeline visualization cross-services:
  ```
  API (5ms) → Cache Service (2ms) → Worker (300ms) → PostgreSQL (20ms)
  ```

**Value**: Préparation architecture distribuée (zero refactor futur)

---

## 🏗️ Architecture Technique

### Layer 1: Contexte Propagation (trace_id → Logs)

**Problème**: Comment injecter trace_id dans tous les logs ?

**Option A**: Middleware bind to contextvars (Python 3.7+)
```python
import contextvars

trace_id_var = contextvars.ContextVar('trace_id', default=None)

# In middleware
trace_id_var.set(trace_id)

# In structlog processor
def add_trace_id_processor(logger, method_name, event_dict):
    trace_id = trace_id_var.get()
    if trace_id:
        event_dict['trace_id'] = trace_id
    return event_dict
```

**Pro**:
- ✅ Automatique (tous logs ont trace_id sans modification code)
- ✅ Thread-safe (contextvars isolated per request)
- ✅ Clean (pas de pollution arguments fonctions)

**Con**:
- ⚠️ Requiert ajout processor structlog

**Verdict**: ✅ **RECOMMANDÉ** (standard Python, zero boilerplate)

---

**Option B**: Manual bind in routes
```python
@router.get("/api/search")
async def search(request: Request):
    trace_id = request.state.trace_id
    logger = logger.bind(trace_id=trace_id)
    logger.info("Processing search")  # Has trace_id
```

**Pro**:
- ✅ Explicit (trace_id visible dans code)

**Con**:
- ❌ Boilerplate dans chaque route (100+ endpoints)
- ❌ Oubli facile (developer forget)
- ❌ Pas propagé aux services

**Verdict**: ❌ **NON RECOMMANDÉ** (trop de boilerplate)

---

### Layer 2: Logs Buffer Enrichment

**Changement**: `LogsBuffer.add_log()` doit stocker trace_id

**Avant** (Story 22.3):
```python
log_entry = {
    "timestamp": "...",
    "level": "info",
    "message": "Processing request",
    "metadata": {}  # Empty!
}
```

**Après** (Story 22.6):
```python
# structlog processor extracts trace_id from event_dict
log_entry = {
    "timestamp": "...",
    "level": "info",
    "message": "Processing request",
    "metadata": {
        "trace_id": "a1b2c3d4-...",  # ← Extracted
        "endpoint": "/v1/search",
        "method": "GET"
    }
}
```

**Changement Code**: ~10 lignes (processor structlog)

---

### Layer 3: UI Affichage trace_id

**Template `monitoring_advanced.html`** - Logs Display:

**Avant** (Story 22.3):
```html
<div class="log-entry">
    <span class="log-time">09:15:42</span>
    <span class="log-level info">INFO</span>
    <span class="log-message">Processing request</span>
</div>
```

**Après** (Story 22.6):
```html
<div class="log-entry">
    <span class="log-time">09:15:42</span>
    <span class="log-level info">INFO</span>
    <span class="log-message">Processing request</span>
    <span class="log-trace-id" onclick="filterByTraceId('a1b2c3d4...')">
        🔍 a1b2c3d4
    </span>
</div>
```

**Styles**:
```css
.log-trace-id {
    font-family: 'Courier New', monospace;
    font-size: 10px;
    color: #58a6ff;
    background: #1f2937;
    padding: 2px 6px;
    cursor: pointer;
    margin-left: 8px;
}

.log-trace-id:hover {
    background: #2d3748;
    text-decoration: underline;
}
```

**Changement Code**: ~20 lignes (template + CSS)

---

### Layer 4: Filtre par trace_id (Frontend)

**UI Component**: Search box au-dessus de logs stream

```html
<div class="logs-filter">
    <input
        type="text"
        id="trace-id-filter"
        placeholder="Filter by trace_id (click trace or paste)"
        class="trace-filter-input"
    >
    <button onclick="clearTraceFilter()">✖ Clear</button>
</div>
```

**JavaScript**:
```javascript
let currentTraceFilter = null;

function filterByTraceId(traceId) {
    currentTraceFilter = traceId;
    document.getElementById('trace-id-filter').value = traceId;

    // Hide logs that don't match
    document.querySelectorAll('.log-entry').forEach(entry => {
        const entryTraceId = entry.dataset.traceId;
        if (entryTraceId === traceId) {
            entry.style.display = 'block';
            entry.classList.add('trace-filtered');
        } else {
            entry.style.display = 'none';
        }
    });
}

function clearTraceFilter() {
    currentTraceFilter = null;
    document.getElementById('trace-id-filter').value = '';

    // Show all logs
    document.querySelectorAll('.log-entry').forEach(entry => {
        entry.style.display = 'block';
        entry.classList.remove('trace-filtered');
    });
}
```

**Changement Code**: ~40 lignes (HTML + JS)

---

### Layer 5: Timeline Visualization (Phase 3 - Nice-to-Have)

**Objectif**: Visualiser le flow temporal d'une requête

**Données Nécessaires**:
```json
{
  "trace_id": "a1b2c3d4-...",
  "spans": [
    {
      "layer": "API",
      "start_ms": 0,
      "duration_ms": 5,
      "status": "success"
    },
    {
      "layer": "SearchService",
      "start_ms": 5,
      "duration_ms": 350,
      "status": "success"
    },
    {
      "layer": "PostgreSQL",
      "start_ms": 355,
      "duration_ms": 40,
      "status": "success"
    }
  ],
  "total_duration_ms": 395
}
```

**UI Visualization** (ECharts Gantt):
```
API         ▓▓▓ 5ms
Service          ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 350ms ⚠️
PostgreSQL                           ▓▓▓▓ 40ms
            |-------|-------|-------|
            0      100     200     300    395ms
```

**Complexité**: 🔴 **HIGH** (requires instrumentation all layers)

**Verdict**: ⏸️ **DEFER to Phase 3** (overkill for single service)

---

## 📊 Complexité vs Bénéfice

### Minimal Implementation (Phase 2)

**Features**:
1. ✅ trace_id dans logs (contextvars + processor)
2. ✅ trace_id affiché dans UI logs
3. ✅ trace_id cliquable → filtre logs
4. ❌ Pas de timeline visualization

**Effort Estimé**: **4 heures** (2 pts)
- Backend: 1h (contextvars + processor)
- UI: 1.5h (display + filter)
- Testing: 1h
- Documentation: 0.5h

**Bénéfice**: 🟢 **HIGH**
- Debug erreurs intermittentes: 60x faster
- User peut reporter trace_id (self-service)
- Foundation pour distributed tracing

**ROI**: ✅ **Excellent** (4h dev → hundreds of hours saved debugging)

---

### Full Implementation (Phase 3)

**Features**:
1. ✅ trace_id dans logs
2. ✅ trace_id cliquable
3. ✅ **Timeline visualization** (Gantt chart)
4. ✅ **Span instrumentation** (API → Service → Repository)
5. ✅ **Flame graph** (pour profiling détaillé)

**Effort Estimé**: **16 heures** (8 pts)
- Span instrumentation: 6h (all services + repositories)
- Timeline backend: 3h (collect + aggregate spans)
- Timeline UI: 4h (ECharts Gantt + flame graph)
- Testing: 2h
- Documentation: 1h

**Bénéfice**: 🟡 **MEDIUM**
- Timeline utile mais **single service** = overkill
- Flame graph nice-to-have (profiling déjà possible via cProfile)

**ROI**: ⚠️ **Questionable** (16h dev pour marginal gain)

---

## 🎯 YAGNI Test (You Ain't Gonna Need It)

### Question 1: "Avons-nous actuellement un problème de debugging ?"

**Réponse**: 🟡 **Parfois**
- Error rate actuel: 0% (Phase 2 Story 22.5) ✅
- Slow endpoints: 1 seul (/summary, 108ms) ✅
- Intermittent errors: Pas observé récemment ✅

**Verdict**: Pas de problème **urgent** actuellement

---

### Question 2: "Le bénéfice justifie-t-il 4h de dev ?"

**Scenarios Réels**:

**Scenario A**: User report "Search failed at 14:32"
- Avant: `grep "14:32" logs | grep error` → 50+ lignes
- Après: User donne trace_id → 3 logs filtrés ✅

**Scenario B**: Performance investigation
- Avant: Manual logs + timing analysis (30min)
- Après: Click trace_id → voir tous logs requête (10s) ✅

**Conclusion**: ✅ **OUI**, 4h dev justifié par:
- Réduction temps debugging: 30min → 10s (180x)
- User self-service (peut reporter trace_id)
- Foundation pour future (distributed tracing)

---

### Question 3: "Timeline visualization est-elle nécessaire ?"

**MnemoLite actuel**:
- Single service (API + PostgreSQL)
- Pas de microservices
- Pas de distributed calls

**Distributed Tracing Value**:
```
Single Service:  API → [Service → Repository] → PostgreSQL
                 ↑______________|________________↑
                        (same process)

Multi-Service:   API → Cache Service → Worker → PostgreSQL
                 ↑        ↑              ↑         ↑
                 (service A)  (service B)  (service C)  (DB)
```

**Verdict**: ❌ **NON** pour Phase 2
- Timeline overkill pour single service
- Peut être ajoutée si/quand multi-service architecture

---

## 📝 Implémentation Recommandée (Phase 2 - Minimal)

### Task Breakdown

**Task 1**: Backend - trace_id Propagation (1.5h)

**Files**:
- `api/main.py` (structlog config)
- `api/middleware/metrics_middleware.py` (contextvars)

**Code**:
```python
# api/main.py
import contextvars
import structlog

# Global context var for trace_id
trace_id_var = contextvars.ContextVar('trace_id', default=None)

# Structlog processor to add trace_id
def add_trace_id_processor(logger, method_name, event_dict):
    trace_id = trace_id_var.get()
    if trace_id:
        event_dict['trace_id'] = trace_id
    return event_dict

# Add to structlog processor chain
structlog.configure(
    processors=[
        add_trace_id_processor,  # ← Add this
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

# api/middleware/metrics_middleware.py
from main import trace_id_var

async def dispatch(self, request: Request, call_next):
    trace_id = str(uuid.uuid4())

    # Set in contextvars (available to all logs)
    trace_id_var.set(trace_id)  # ← Add this line

    request.state.trace_id = trace_id
    # ... rest unchanged
```

**Acceptance**:
- [x] Tous logs structlog ont `trace_id` field
- [x] trace_id propagé automatiquement (pas de manual bind)
- [x] LogsBuffer reçoit trace_id dans metadata

---

**Task 2**: UI - Display trace_id (1h)

**File**: `templates/monitoring_advanced.html`

**Changes**:
```html
<!-- Logs entry template (JavaScript) -->
<script>
function renderLogEntry(log) {
    const traceId = log.metadata?.trace_id || null;
    const traceIdHtml = traceId
        ? `<span class="log-trace-id" onclick="filterByTraceId('${traceId}')" title="${traceId}">
             🔍 ${traceId.substring(0, 8)}
           </span>`
        : '';

    return `
        <div class="log-entry" data-trace-id="${traceId || ''}">
            <span class="log-time">${formatTime(log.timestamp)}</span>
            <span class="log-level ${log.level}">${log.level.toUpperCase()}</span>
            <span class="log-message">${log.message}</span>
            ${traceIdHtml}
        </div>
    `;
}
</script>

<!-- CSS styles -->
<style>
.log-trace-id {
    font-family: 'Courier New', monospace;
    font-size: 10px;
    color: #58a6ff;
    background: #1f2937;
    padding: 2px 6px;
    cursor: pointer;
    margin-left: 8px;
    border-radius: 0;
    transition: background 0.08s ease;
}

.log-trace-id:hover {
    background: #2d3748;
    text-decoration: underline;
}
</style>
```

**Acceptance**:
- [x] trace_id affiché dans chaque log entry
- [x] Format: `🔍 a1b2c3d4` (8 premiers chars)
- [x] Hover tooltip montre full trace_id
- [x] Style cohérent SCADA theme

---

**Task 3**: UI - Filter by trace_id (1.5h)

**File**: `templates/monitoring_advanced.html`

**Changes**:
```html
<!-- Add filter input above logs container -->
<div class="logs-panel">
    <div class="panel-header">
        <span class="panel-title">📜 Real-Time Logs Stream</span>
        <div class="logs-filter-controls">
            <input
                type="text"
                id="trace-id-filter"
                placeholder="Filter by trace_id (click or paste)"
                class="trace-filter-input"
            >
            <button onclick="clearTraceFilter()" class="filter-clear-btn">✖</button>
        </div>
    </div>
    <div class="logs-container" id="logs-container">
        <!-- Logs rendered here -->
    </div>
</div>

<script>
let currentTraceFilter = null;

function filterByTraceId(traceId) {
    currentTraceFilter = traceId;
    document.getElementById('trace-id-filter').value = traceId;

    // Filter visible logs
    document.querySelectorAll('.log-entry').forEach(entry => {
        const entryTraceId = entry.dataset.traceId;
        if (entryTraceId === traceId) {
            entry.style.display = 'block';
            entry.classList.add('trace-filtered');
        } else {
            entry.style.display = 'none';
        }
    });

    // Update counter
    const matchCount = document.querySelectorAll('.trace-filtered').length;
    console.log(`Filtered to ${matchCount} logs with trace_id: ${traceId}`);
}

function clearTraceFilter() {
    currentTraceFilter = null;
    document.getElementById('trace-id-filter').value = '';

    // Show all logs
    document.querySelectorAll('.log-entry').forEach(entry => {
        entry.style.display = 'block';
        entry.classList.remove('trace-filtered');
    });
}

// Manual filter input
document.getElementById('trace-id-filter')?.addEventListener('input', (e) => {
    const traceId = e.target.value.trim();
    if (traceId.length >= 8) {  // Min 8 chars
        filterByTraceId(traceId);
    } else if (traceId.length === 0) {
        clearTraceFilter();
    }
});

// Modify SSE log rendering to respect filter
function appendLog(log) {
    // ... render log entry ...

    // If filter active, hide non-matching logs
    if (currentTraceFilter) {
        const entryTraceId = log.metadata?.trace_id;
        if (entryTraceId !== currentTraceFilter) {
            logDiv.style.display = 'none';
        } else {
            logDiv.classList.add('trace-filtered');
        }
    }

    logsContainer.appendChild(logDiv);
}
</script>

<style>
.logs-filter-controls {
    display: flex;
    gap: 8px;
    align-items: center;
}

.trace-filter-input {
    background: #0d1117;
    border: 1px solid #30363d;
    color: #c9d1d9;
    padding: 6px 12px;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    min-width: 300px;
}

.trace-filter-input:focus {
    outline: 1px solid #58a6ff;
    outline-offset: -1px;
}

.filter-clear-btn {
    background: #0d1117;
    border: 1px solid #30363d;
    color: #8b949e;
    padding: 6px 12px;
    font-size: 12px;
    cursor: pointer;
    transition: border-color 0.08s ease;
}

.filter-clear-btn:hover {
    border-color: #f85149;
    color: #f85149;
}

.log-entry.trace-filtered {
    background: #1a2332;  /* Highlight filtered logs */
    border-left: 2px solid #58a6ff;
}
</style>
```

**Acceptance**:
- [x] Input field pour trace_id au-dessus logs stream
- [x] Click sur trace_id badge → filtre automatique
- [x] Manual paste trace_id → filtre automatique
- [x] Clear button pour réinitialiser filtre
- [x] Logs filtrés highlighted (background + border)

---

**Task 4**: Testing & Documentation (1h)

**Testing Manual**:
```bash
# Test 1: Verify trace_id in logs
curl http://localhost:8001/api/monitoring/advanced/summary -v
# Check X-Trace-ID header → copy trace_id

# Test 2: Check logs stream includes trace_id
curl -N http://localhost:8001/api/monitoring/advanced/logs/stream | head -5
# Verify: logs contain "trace_id": "..."

# Test 3: UI trace_id display
# Open http://localhost:8001/ui/monitoring/advanced
# Verify: Each log shows 🔍 trace_id badge

# Test 4: UI filter by trace_id
# Click on trace_id badge
# Verify: Only logs with that trace_id visible

# Test 5: Manual paste trace_id
# Paste full trace_id in filter input
# Verify: Filter works
```

**Documentation**:
- Update `EPIC-22_README.md` (Story 22.6 status)
- Create `EPIC-22_STORY_22.6_COMPLETION_REPORT.md`

---

## 💡 Recommandations

### ✅ Implémentation Recommandée (Phase 2)

**Scope**: Minimal Implementation
- trace_id propagation (contextvars)
- trace_id display in logs UI
- trace_id clickable filter

**Effort**: 4h (2 pts)
**Value**: HIGH (debug 180x faster)
**ROI**: Excellent

**Verdict**: ✅ **IMPLEMENT in Phase 2**

---

### ⏸️ À Reporter (Phase 3)

**Scope**: Advanced Features
- Timeline visualization (Gantt chart)
- Span instrumentation (API → Service → Repository)
- Flame graph profiling

**Raison**: Overkill pour single service
**Trigger**: Multi-service architecture OU performance problems détectés

**Verdict**: ⏸️ **DEFER to Phase 3** (YAGNI)

---

## 🎯 Acceptance Criteria (Story 22.6 - Minimal)

### Backend ✅
- [ ] contextvars `trace_id_var` créé
- [ ] Structlog processor `add_trace_id_processor` ajouté
- [ ] Middleware set trace_id in contextvars
- [ ] Tous logs structlog ont field `trace_id`
- [ ] LogsBuffer reçoit trace_id dans metadata

### Frontend ✅
- [ ] Logs UI affiche trace_id badge (🔍 a1b2c3d4)
- [ ] trace_id cliquable
- [ ] Click trace_id → filtre logs
- [ ] Input field pour manual paste trace_id
- [ ] Clear button pour reset filtre
- [ ] Logs filtrés highlighted (background + border)

### UX ✅
- [ ] trace_id visible sans scroll horizontal
- [ ] Hover tooltip montre full UUID
- [ ] Filter responsive (updates as you type)
- [ ] Clear filter restore all logs

### Performance ✅
- [ ] contextvars overhead < 1ms/req
- [ ] Filter performance acceptable (1000+ logs)
- [ ] No memory leak (filter state cleanup)

---

## 📊 Métriques Succès

**Time to Debug** (Target):
- Erreur intermittente: **< 1 minute** (avant: 30min)
- Performance investigation: **< 30 secondes** (avant: 1h)

**User Experience**:
- User peut reporter trace_id (self-service) ✅
- Dev peut filter logs by trace_id (1 click) ✅

**Technical**:
- 100% logs ont trace_id field ✅
- Zero manual bind required (automatic) ✅

---

## 🔗 Fichiers Impactés

```
Backend (3 fichiers):
api/
├── main.py                              # +20 LOC (contextvars + processor)
├── middleware/
│   └── metrics_middleware.py            # +2 LOC (contextvars.set)
└── services/
    └── logs_buffer.py                   # No change (already has metadata)

Frontend (1 fichier):
templates/
└── monitoring_advanced.html             # +120 LOC (display + filter)

Documentation:
docs/agile/serena-evolution/03_EPICS/
├── EPIC-22_STORY_22.6_ULTRATHINK.md     # This doc
└── EPIC-22_STORY_22.6_COMPLETION_REPORT.md  # After implementation

Total: 4 fichiers, ~142 LOC added
```

---

## ⚖️ Decision Matrix

| Critère | Minimal (Phase 2) | Full (Phase 3) |
|---------|-------------------|----------------|
| **Effort** | 4h (2 pts) ⚡ | 16h (8 pts) 🐌 |
| **Value** | HIGH 🟢 | MEDIUM 🟡 |
| **ROI** | Excellent ✅ | Questionable ⚠️ |
| **Urgency** | Nice-to-have | Low |
| **Complexity** | Low | High |
| **YAGNI** | Pass ✅ | Fail ❌ |
| **Recommendation** | ✅ DO IT | ⏸️ DEFER |

---

## 🎯 Résumé Exécutif

**Story 22.6 Request Tracing - Minimal Implementation**

**Objectif**: Rendre trace_id visible, cliquable, et utile pour debugging

**Scope Recommandé** (Phase 2):
- ✅ trace_id dans tous logs (contextvars + processor)
- ✅ trace_id affiché dans UI (badge cliquable)
- ✅ Filtre logs par trace_id (1 click OU paste)
- ❌ Timeline visualization (defer to Phase 3)

**Effort**: 4 heures (2 pts)
**ROI**: Excellent (debug 180x faster)
**Value**: HIGH (self-service debugging)

**YAGNI Test**: ✅ **PASS**
- Bénéfice justifié (user self-service + dev productivity)
- Minimal scope (pas de feature bloat)
- Foundation pour future (distributed tracing ready)

**Recommendation**: ✅ **IMPLEMENT in Phase 2**

**Prochaine étape**: Implementation ou attendre validation ?

---

**Créé par**: Claude Code + User
**Date**: 2025-10-24
**Status**: 🧠 **Brainstorming Complete**
**Decision**: ⏳ **Awaiting User Approval**
