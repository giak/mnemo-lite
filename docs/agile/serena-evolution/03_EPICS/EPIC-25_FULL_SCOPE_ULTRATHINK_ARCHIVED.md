# EPIC-25: UI/UX Refonte Complète - ULTRATHINK

**Version**: 1.0.0
**Date**: 2025-11-01
**Type**: ULTRATHINK (Deep Analysis)
**Status**: BRAINSTORM
**Priority**: P1 (User Experience Critical)

---

## 🎯 Vision Stratégique

**Problème actuel**: Interface fragmentée avec navigation peu intuitive, pas de vision d'ensemble du système, monitoring basique dispersé.

**Vision cible**: Interface unifiée, professionnelle, avec monitoring temps réel complet et navigation claire vers toutes les features.

**Impact attendu**:
- +50% efficacité utilisateur (temps de recherche réduit)
- Monitoring proactif (détection problèmes avant crash)
- Expérience premium (vs POC actuel)

---

## 📊 Analyse État Actuel (Audit UI/UX)

### Pages Existantes

| Page | URL | État | Problèmes |
|------|-----|------|-----------|
| **Code Search** | `/ui/code_search` | ✅ Fonctionnel | Navigation floue, pas de filters visuels |
| **Code Graph** | `/ui/code_graph` | ⚠️ Basique | Graph simple, pas de zoom/pan smooth, légendes manquantes |
| **Monitoring Basic** | `/ui/monitoring` | ⚠️ Minimal | Métriques statiques, pas de temps réel |
| **Monitoring Advanced** | `/ui/monitoring/advanced` | ⚠️ Incomplet | Logs limités, pas de streaming, pas de filtering |
| **Auto-save Dashboard** | `/ui/autosave` (?) | ❓ Existe? | Si oui, isolé, pas de lien navigation |

### Navigation Actuelle

**Problème**: Pas de navbar unifiée, navigation par URL directe uniquement.

**Impact**:
- Utilisateur doit connaître les URLs
- Pas de découvrabilité des features
- Sensation de "pages isolées" vs "application cohérente"

### Monitoring Actuel

**Limitations identifiées**:
- ❌ Pas de streaming temps réel (WebSocket/SSE)
- ❌ Logs non filtrable dynamiquement
- ❌ Métriques CPU/RAM/Disk non affichées
- ❌ Erreurs pas mise en évidence (alertes)
- ❌ Pas de graphiques temps réel (CPU usage over time)
- ❌ Pas de vue "santé globale" du système

### Embeddings (2 modèles distincts)

**Configuration actuelle** (`.env.example`):
1. **EMBEDDING_MODEL** = `nomic-ai/nomic-embed-text-v1.5` (768 dims)
   - **Usage**: Conversations, docstrings, comments, texte général
   - **Stats**: ~7,972 conversations auto-indexées
   - **Performance**: ~10ms search avg

2. **CODE_EMBEDDING_MODEL** = `jinaai/jina-embeddings-v2-base-code` (768 dims)
   - **Usage**: Source code, functions, classes (code chunks)
   - **Stats**: ~125,000 code chunks indexés
   - **Performance**: ~12ms search avg

**Problème actuel**: Pas de visibilité séparée sur:
- Nombre d'embeddings par modèle (conversations vs code)
- Taille DB vectorielle par type
- Performance search comparative (text vs code)
- Quelle proportion utilise quel modèle
- Distribution sémantique (clusters?)

---

## 🎨 Brainstorm Features UI/UX

### 1. Navigation Unifiée 🧭

**Concept**: Navbar permanente avec toutes les features

**Design proposé**:
```
┌─────────────────────────────────────────────────────────────────┐
│ 🧠 MnemoLite  [Search] [Graph] [Dashboard] [Monitoring] [⚙️]   │
└─────────────────────────────────────────────────────────────────┘
```

**Features**:
- **Logo + Nom**: Lien vers dashboard principal
- **Search**: Recherche unifiée (conversations + code)
- **Graph**: Visualization des dépendances code
- **Dashboard**: Vue d'ensemble métriques + santé
- **Monitoring**: Logs + erreurs + computing temps réel
- **Settings** (⚙️): Configuration, admin

**Détails techniques**:
- Sticky header (reste visible au scroll)
- Active state (highlight page actuelle)
- Responsive (collapse en hamburger menu sur mobile)
- Dark mode toggle dans settings

---

### 2. Dashboard Principal (Landing Page) 📊

**Objectif**: Vue d'ensemble instantanée de tout le système

**Layout proposé**:
```
┌─────────────────────────────────────────────────────────┐
│                    🧠 MnemoLite Dashboard                │
├───────────────┬──────────────────┬─────────────────────┤
│ 🏥 Santé      │ 💾 Storage       │ ⚡ Performance       │
│ ● Healthy     │ Conversations:   │ Search: 8-12ms      │
│ CPU: 23%      │   7,972 (2.1GB)  │ Graph: 45ms         │
│ RAM: 1.2/4GB  │ Code Chunks:     │ Uptime: 4d 3h       │
│ Disk: 45/100  │   125k (890MB)   │                     │
├───────────────┴──────────────────┴─────────────────────┤
│ 📈 Activity (Last 24h)                                  │
│ ┌──────────────────────────────────────────────────┐   │
│ │  [Line chart: API calls over time]                │   │
│ │  Peak: 1,234 req/h @ 14:00                       │   │
│ └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────┤
│ 🔍 Embeddings Overview (2 Modèles Distincts)            │
│ ┌────────────────────────┬────────────────────────────┐ │
│ │ 💬 TEXT (Conversations)│ 💻 CODE (Code Chunks)      │ │
│ │ 7,972 embeddings       │ 125,000 embeddings         │ │
│ │ nomic-text-v1.5        │ jina-code-v2               │ │
│ │ Dim: 768               │ Dim: 768                   │ │
│ │ Index: HNSW            │ Index: HNSW                │ │
│ │ Avg query: 10ms        │ Avg query: 12ms            │ │
│ └────────────────────────┴────────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│ ⚠️ Recent Alerts (Last 1h)                              │
│ • No critical alerts                           ✅        │
│ • 2 warnings (slow queries >100ms)             ⚠️        │
├──────────────────────────────────────────────────────┤
│ 🚀 Quick Actions                                        │
│ [Search Code] [View Graph] [Check Logs] [Run Test]     │
└──────────────────────────────────────────────────────┘
```

**Sections détaillées**:

#### A. Santé Système (Health Check)
- **Status global**: Green/Yellow/Red indicator
- **CPU**: Usage % + mini graph (sparkline)
- **RAM**: Usage + limite (bar chart)
- **Disk**: Usage + alerte si >80%
- **Services**: API ✅, PostgreSQL ✅, Redis ✅ (avec latency)

#### B. Storage Metrics
- **Conversations**:
  - Nombre total d'embeddings
  - Taille DB (GB)
  - Croissance (trend +XX/jour)
- **Code Chunks**:
  - Nombre total d'embeddings
  - Taille DB (GB)
  - Langages supportés (Python ✅, JS ⏳, etc.)

#### C. Performance Metrics
- **Search latency**: p50/p95/p99 (avec targets)
- **Graph render**: Temps moyen
- **API response time**: p50/p95
- **Uptime**: Depuis dernier démarrage

#### D. Activity Chart (Temps Réel)
- **Line chart**: API calls over time (1h/24h/7d selectors)
- **Hover**: Détails par endpoint
- **Color coding**: Success (green) vs Errors (red)

#### E. Embeddings Overview (2 Modèles Distincts)
- **2 cards côte-à-côte**: TEXT (Conversations) vs CODE (Code chunks)

**Card 1: TEXT Embeddings**
- **Modèle**: nomic-ai/nomic-embed-text-v1.5
- **Nombre**: 7,972 conversations
- **Dimension**: 768
- **Index**: HNSW (m=16, ef_construction=200)
- **Perf moyenne**: 10ms search
- **Dernière indexation**: Timestamp

**Card 2: CODE Embeddings**
- **Modèle**: jinaai/jina-embeddings-v2-base-code
- **Nombre**: 125,000 code chunks
- **Dimension**: 768
- **Index**: HNSW (m=16, ef_construction=200)
- **Perf moyenne**: 12ms search
- **Dernière indexation**: Timestamp

#### F. Recent Alerts
- **Liste dernières alertes**: Critical/Warning/Info
- **Types d'alertes**:
  - Slow query (>100ms)
  - High CPU (>80%)
  - Disk space low (<20%)
  - Service down
  - Embedding generation failed
- **Actions**: Lien vers logs, fix suggestions

#### G. Quick Actions
- **Boutons**: Actions fréquentes rapides
- **Search Code**: Ouvre modal search
- **View Graph**: Jump to graph page
- **Check Logs**: Jump to monitoring avec filtre erreurs
- **Run Test**: Déclenche health check complet

**Technos**:
- **Charts**: Chart.js ou Recharts (React)
- **Real-time updates**: Server-Sent Events (SSE) toutes les 5s
- **Responsive**: Grid layout (3 cols → 1 col mobile)

---

### 3. Recherche Unifiée 🔍

**Concept**: Single search bar qui cherche dans TOUT

**Features**:

#### A. Search Bar Global
```
┌──────────────────────────────────────────────────────┐
│  🔍  Search conversations, code, files...             │
│      [Type: All ▾] [Scope: Everything ▾]             │
└──────────────────────────────────────────────────────┘
```

**Filters**:
- **Type**: All | Conversations | Code | Files | Functions
- **Scope**: Everything | Current Project | Selected Repos
- **Date**: All time | Last 7 days | Last 30 days
- **Language**: All | Python | JavaScript | ...

#### B. Search Results (Unified View)
```
┌──────────────────────────────────────────────────────┐
│ Results for "postgresql timeout" (23 found)          │
├──────────────────────────────────────────────────────┤
│ 💬 Conversations (8)                                  │
│ ┌────────────────────────────────────────────────┐   │
│ │ 📅 2025-10-15 | Score: 0.92                    │   │
│ │ "Discussion on PostgreSQL connection timeout"  │   │
│ │ ...snippet with highlighted keywords...        │   │
│ │ [View Full] [Related Code]                     │   │
│ └────────────────────────────────────────────────┘   │
│                                                       │
│ 💻 Code (12)                                          │
│ ┌────────────────────────────────────────────────┐   │
│ │ 📁 api/db/connection.py:45 | Score: 0.88       │   │
│ │ async def connect(timeout=30):                 │   │
│ │     """Connect with timeout"""                 │   │
│ │     ...highlighted code...                     │   │
│ │ [View File] [View Graph] [Copy]               │   │
│ └────────────────────────────────────────────────┘   │
│                                                       │
│ 🔧 Functions (3)                                      │
│ ┌────────────────────────────────────────────────┐   │
│ │ set_connection_timeout() in db/utils.py        │   │
│ │ Parameters: timeout: int, retry: bool          │   │
│ │ Returns: bool                                  │   │
│ │ [View Definition] [Find Usages]               │   │
│ └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**Features avancées**:
- **Instant search**: Résultats pendant typing (debounce 300ms)
- **Ranking**: Score de pertinence affiché
- **Highlighting**: Keywords surlignés dans snippets
- **Faceted search**: Filtres cumulatifs
- **Recent searches**: Historique dropdown
- **Saved searches**: Sauvegarder queries fréquentes
- **Export results**: JSON/CSV export

**Technos**:
- **Backend**: Endpoint `/api/v1/search/unified`
- **Hybrid search**: Combine lexical (BM25) + vector (cosine)
- **Caching**: Redis cache pour queries fréquentes
- **Pagination**: Infinite scroll ou pagination classique

---

### 4. Code Graph Avancé 🕸️

**Améliorations vs version actuelle**:

#### A. Graph Rendering
**Actuellement**: D3.js basique
**Proposé**:
- **Library**: Cytoscape.js (meilleur que D3 pour graphs)
- **Features**:
  - Zoom/Pan fluide (wheel + drag)
  - Layout algorithms: Force-directed, Hierarchical, Circular
  - Node clustering (group par module/package)
  - Edge bundling (reduce clutter)
  - Mini-map (overview en coin)

#### B. Interactivité
```
┌─────────────────────────────────────────────────────┐
│ 🕸️ Code Dependency Graph                            │
│ ┌────────────────────────────┬──────────────────┐   │
│ │ Controls                    │ Legend           │   │
│ │ [Layout: Force ▾]          │ ■ Services       │   │
│ │ [Filter: All ▾]            │ ■ Routes         │   │
│ │ [Depth: 2 ▾]               │ ■ Utils          │   │
│ │ [Show: Imports+Calls ✓]   │ ■ Tests          │   │
│ └────────────────────────────┴──────────────────┘   │
│                                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │         [Interactive Graph Canvas]              │  │
│ │                                                 │  │
│ │    ┌─────┐      ┌─────┐                        │  │
│ │    │ A.py│─────▶│ B.py│                        │  │
│ │    └─────┘      └─────┘                        │  │
│ │       │            │                            │  │
│ │       ▼            ▼                            │  │
│ │    ┌─────┐      ┌─────┐                        │  │
│ │    │ C.py│◀─────│ D.py│                        │  │
│ │    └─────┘      └─────┘                        │  │
│ │                                                 │  │
│ │  [Minimap: ┌──┐ ]                              │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ 📊 Selected: api/services/code_indexing_service.py  │
│ ┌────────────────────────────────────────────────┐  │
│ │ Imports (5):                                    │  │
│ │  • asyncpg                                      │  │
│ │  • sentence_transformers                       │  │
│ │  • ...                                          │  │
│ │                                                 │  │
│ │ Used By (12):                                   │  │
│ │  • api/routes/code_search_routes.py            │  │
│ │  • tests/services/test_indexing.py             │  │
│ │  • ...                                          │  │
│ │                                                 │  │
│ │ Complexity: Medium (Cyclomatic: 8)             │  │
│ │ Lines: 456                                      │  │
│ │ Last Modified: 2025-10-28                      │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ 🔧 Actions:                                          │
│ [View Source] [Find Path To...] [Export SVG/PNG]    │
└──────────────────────────────────────────────────────┘
```

**Features détaillées**:

**Layout Algorithms**:
- **Force-directed**: Nodes repoussent, edges attirent (organic)
- **Hierarchical**: Top-down (entry points → leaves)
- **Circular**: Modules en cercles concentriques
- **Grid**: Alignement strict (good for small graphs)

**Filtering**:
- **By type**: Services only, Routes only, etc.
- **By depth**: 1 hop, 2 hops, all
- **By pattern**: "*.test.py", "services/*"
- **By complexity**: Only files >X cyclomatic complexity

**Node Details Panel**:
- **Metrics**: Lines, complexity, dependencies count
- **Imports**: Liste avec links cliquables
- **Used by**: Reverse dependencies
- **History**: Last modified, author
- **Actions**: Jump to code, find path, highlight cluster

**Path Finding**:
- **Feature**: "Find path from A to B"
- **Use case**: "How does route X reach database?"
- **Display**: Highlight shortest path, show intermediate nodes

**Export**:
- **Formats**: SVG, PNG, JSON (graph data)
- **Use case**: Documentation, presentations

**Performance**:
- **Large graphs**: Virtual rendering (only visible nodes)
- **Caching**: Graph structure cached in Redis
- **Incremental**: Update graph incrementally (not full rebuild)

---

### 5. Monitoring Temps Réel ⚡

**Concept**: Dashboard live avec WebSocket/SSE streaming

**Layout proposé**:
```
┌──────────────────────────────────────────────────────┐
│ ⚡ Real-Time Monitoring                               │
├────────────────────┬─────────────────────────────────┤
│ 🖥️ System Metrics  │ 📊 Live Graph                    │
│ CPU:  [▓▓▓░░] 34%  │ ┌───────────────────────────┐   │
│ RAM:  [▓▓░░░] 28%  │ │ CPU % over time           │   │
│ Disk: [▓░░░░] 12%  │ │    ╱╲  ╱╲                 │   │
│ Net:  ↓45MB ↑12MB  │ │   ╱  ╲╱  ╲                │   │
│                    │ │  ╱         ╲___           │   │
│ 🚀 Services        │ │ Last 60 seconds           │   │
│ ● API      (23ms)  │ └───────────────────────────┘   │
│ ● PostgreSQL (5ms) │                                 │
│ ● Redis    (1ms)   │ 📈 Request Rate                 │
│ ● Embedding (45ms) │ ┌───────────────────────────┐   │
│                    │ │ 234 req/min                │   │
│ 🔥 Hot Endpoints   │ │ Peak: 456 @ 14:23          │   │
│ 1. /search   (45%) │ │ Avg:  198 req/min          │   │
│ 2. /graph    (23%) │ └───────────────────────────┘   │
│ 3. /autosave (18%) │                                 │
└────────────────────┴─────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ 📋 Live Logs (Auto-refresh)         [⏸️ Pause]       │
│ [Filter: ⚠️ Errors ▾] [Level: All ▾] [Clear]         │
├──────────────────────────────────────────────────────┤
│ 14:23:45 INFO  API request: GET /api/v1/search       │
│ 14:23:45 INFO  Query: "postgresql timeout"           │
│ 14:23:46 DEBUG Search completed in 12ms               │
│ 14:23:50 WARN  Slow query detected (125ms)           │ ⚠️
│ 14:23:51 ERROR Redis connection timeout              │ 🔴
│ 14:23:52 INFO  Retrying Redis connection...          │
│ 14:23:53 INFO  Redis reconnected                     │
│ [Auto-scroll ✓] [Export Logs] [Load More...]        │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ ⚠️ Active Alerts (2)                                  │
│ ┌────────────────────────────────────────────────┐   │
│ │ 🔴 CRITICAL: Disk space <20% (18% remaining)   │   │
│ │ Time: 14:20:34 | Duration: 3m 18s              │   │
│ │ [Acknowledge] [View Details] [Auto-cleanup]   │   │
│ └────────────────────────────────────────────────┘   │
│ ┌────────────────────────────────────────────────┐   │
│ │ ⚠️  WARNING: Slow queries (3 in last 5 min)    │   │
│ │ Avg latency: 145ms (target: <100ms)           │   │
│ │ [View Queries] [Analyze] [Dismiss]            │   │
│ └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**Features détaillées**:

#### A. System Metrics (Live)
**Update frequency**: 2 seconds
**Metrics**:
- **CPU**: % usage + cores breakdown (optional)
- **RAM**: Used/Total + % bar chart
- **Disk**: Used/Total + % + trend (growing fast?)
- **Network**: Download/Upload rate (MB/s)

**Visualization**:
- **Progress bars**: Color-coded (green <50%, yellow 50-80%, red >80%)
- **Sparklines**: Mini line charts (last 60 values)
- **Alerts**: Red pulse si >80%

#### B. Services Health
**Check frequency**: 5 seconds
**Services monitored**:
- **API**: HTTP /health endpoint → Latency
- **PostgreSQL**: Connection test → Latency
- **Redis**: PING command → Latency
- **Embedding service**: Test inference → Latency

**Display**:
- **Status**: Green dot (healthy) / Red dot (down)
- **Latency**: Response time en ms
- **Last check**: Timestamp

#### C. Live Graphs (Streaming)
**Update frequency**: 1 second
**Graphs**:
- **CPU over time**: Line chart (last 60s)
- **Request rate**: Bar chart (requests/min)
- **Response time**: Line chart p50/p95
- **Error rate**: Line chart (errors/min)

**Technology**:
- **Chart.js** avec update() dynamique
- **SSE stream**: Server envoie data points
- **Rolling window**: Keep last N points (60-300)

#### D. Live Logs (Streaming)
**Update method**: Server-Sent Events (SSE)
**Features**:
- **Auto-scroll**: Scroll to bottom on new log
- **Pause**: Stop auto-scroll (read old logs)
- **Filters**:
  - **Level**: ALL, DEBUG, INFO, WARN, ERROR
  - **Source**: ALL, API, Database, Embedding, etc.
  - **Text search**: Filter by keyword
- **Color coding**:
  - DEBUG: Gray
  - INFO: Blue
  - WARN: Yellow
  - ERROR: Red (bold)
- **Actions**:
  - **Export**: Download logs as .txt
  - **Clear**: Clear display (not delete logs)
  - **Load more**: Fetch older logs

**Implementation**:
```python
# Backend: SSE endpoint
@router.get("/v1/monitoring/logs/stream")
async def stream_logs():
    async def event_generator():
        while True:
            log = await log_queue.get()  # Real-time logs from queue
            yield f"data: {json.dumps(log)}\n\n"
    return EventSourceResponse(event_generator())
```

```javascript
// Frontend: SSE consumer
const eventSource = new EventSource('/api/v1/monitoring/logs/stream');
eventSource.onmessage = (event) => {
    const log = JSON.parse(event.data);
    appendLogToUI(log);
};
```

#### E. Active Alerts
**Alert types**:
- **CRITICAL** (🔴): Service down, disk full, etc.
- **WARNING** (⚠️): Slow queries, high CPU, etc.
- **INFO** (ℹ️): Service restarted, backup completed, etc.

**Alert lifecycle**:
1. **Triggered**: Condition met (e.g., disk <20%)
2. **Active**: Alert displayed in dashboard
3. **Acknowledged**: User clicks "Acknowledge"
4. **Resolved**: Condition resolved (e.g., disk cleaned)
5. **Closed**: Alert removed from active list

**Actions**:
- **Acknowledge**: Mark as "seen" (stop blinking)
- **View Details**: Open modal with full context
- **Auto-fix**: If possible (e.g., cleanup old logs)
- **Dismiss**: User decides it's not important
- **Snooze**: Hide for X minutes

**Storage**:
- **Active alerts**: In-memory (Redis)
- **Alert history**: PostgreSQL table
- **Query**: Last 24h alerts for trends

---

### 6. Settings & Configuration ⚙️

**Concept**: Page admin pour configuration

**Sections**:

#### A. General Settings
- **Application name**: MnemoLite (editable)
- **Theme**: Light / Dark / Auto
- **Language**: EN / FR
- **Timezone**: UTC+1, etc.

#### B. Performance Settings
- **Cache TTL**: L1 (seconds), L2 (minutes), L3 (hours)
- **Max results**: Search limit (default 50)
- **Timeout**: API timeout (default 30s)
- **Batch size**: Embedding batch (default 32)

#### C. Monitoring Settings
- **Metrics retention**: 7 days / 30 days / 90 days
- **Log level**: DEBUG / INFO / WARN / ERROR
- **Alert thresholds**:
  - CPU alert at: 80%
  - RAM alert at: 80%
  - Disk alert at: 20% free
  - Slow query at: 100ms

#### D. Embedding Settings (2 Modèles)

**TEXT Model (Conversations)**:
- **Model**: nomic-ai/nomic-embed-text-v1.5 (read-only)
- **Dimension**: 768 (read-only)
- **Usage**: Conversations, docstrings, comments

**CODE Model (Code Chunks)**:
- **Model**: jinaai/jina-embeddings-v2-base-code (read-only)
- **Dimension**: 768 (read-only)
- **Usage**: Source code, functions, classes

**HNSW Parameters** (shared):
- **m**: 16 (tunable, impact: recall vs speed)
- **ef_construction**: 200 (tunable, impact: index build time)
- **ef_search**: 100 (tunable, impact: query time vs recall)

**Processing**:
- **Batch size**: 32 (tunable, impact: throughput vs memory)
- **Max queue size**: 1000 (tunable, impact: backpressure)

#### E. Search Settings
- **Hybrid weights**: Lexical 40% / Vector 60%
- **RRF constant k**: 60 (tunable)
- **Max depth**: Graph traversal depth (default 3)

#### F. Database Settings (Read-only)
- **PostgreSQL version**: 18.0
- **pgvector version**: 0.8.1
- **Connection pool**: 10
- **Max connections**: 100

---

## 🏗️ Architecture Technique UI/UX

### Stack Technologique Proposé

#### Frontend
**Option 1: React SPA** (Recommandé)
```
├── React 18
├── TypeScript
├── Vite (build tool)
├── TailwindCSS (styling)
├── Shadcn/UI (component library)
├── Chart.js (charts)
├── Cytoscape.js (graph)
├── React Query (data fetching)
└── Zustand (state management)
```

**Pourquoi React**:
- Ecosystème mature
- 
  SSE/WebSocket facile
- Composants réutilisables
- TypeScript intégré
- Performance (Virtual DOM)

**Option 2: Keep Jinja2 + HTMX** (Minimal)
```
├── Jinja2 templates
├── HTMX (interactivité)
├── Alpine.js (JavaScript minimal)
├── TailwindCSS (styling)
├── Chart.js (charts)
└── Vanilla JS (custom needs)
```

**Pourquoi HTMX**:
- Pas de build step
- Simplicité
- SSR (Server-Side Rendering)
- Moins de JS à écrire

**Recommandation**: **React** pour features avancées (real-time, complexité), **HTMX** si on veut rester simple.

#### Backend (Inchangé)
```
├── FastAPI (Python 3.11+)
├── PostgreSQL 18
├── Redis (cache)
└── SSE (Server-Sent Events) pour streaming
```

**Nouveaux endpoints nécessaires**:
```python
# Dashboard
GET /api/v1/dashboard/summary
GET /api/v1/dashboard/health

# Search unifié
GET /api/v1/search/unified?q=...&type=...&scope=...

# Graph avancé
GET /api/v1/graph/full?depth=...&filter=...
GET /api/v1/graph/path?from=...&to=...

# Monitoring temps réel
GET /api/v1/monitoring/metrics/stream  # SSE
GET /api/v1/monitoring/logs/stream     # SSE
GET /api/v1/monitoring/alerts

# Settings
GET /api/v1/settings
PUT /api/v1/settings
```

### Real-Time Architecture

**Server-Sent Events (SSE) vs WebSocket**:

| Feature | SSE | WebSocket |
|---------|-----|-----------|
| **Direction** | Server → Client only | Bidirectional |
| **Protocol** | HTTP | WS (upgrade from HTTP) |
| **Reconnect** | Auto (browser) | Manual |
| **Use case** | Metrics, logs streaming | Chat, gaming |

**Recommandation**: **SSE** pour monitoring (simpler, auto-reconnect)

**Implementation pattern**:
```python
# Backend: SSE endpoint
from fastapi.responses import StreamingResponse

async def metrics_stream():
    async def event_generator():
        while True:
            metrics = await collect_metrics()
            yield f"data: {json.dumps(metrics)}\n\n"
            await asyncio.sleep(2)  # Update every 2s
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Frontend: Consumer
const eventSource = new EventSource('/api/v1/monitoring/metrics/stream');
eventSource.onmessage = (event) => {
    const metrics = JSON.parse(event.data);
    updateDashboard(metrics);
};
```

---

## 📐 Wireframes (ASCII)

### Dashboard Principal
```
┌──────────────────────────────────────────────────────────────────┐
│ 🧠 MnemoLite  [Search] [Graph] [Dashboard*] [Monitoring] [⚙️]   │ ← Navbar
├──────────────────────────────────────────────────────────────────┤
│                        📊 Dashboard                               │
│                                                                   │
│ ┌──────────────┬──────────────┬──────────────┬──────────────┐   │
│ │ 🏥 Health    │ 💾 Storage   │ ⚡ Perf       │ 📊 Activity  │   │ ← Metrics Cards
│ │ ● Healthy    │ Conv: 7,972  │ Search: 10ms │ 234 req/min  │   │
│ │ CPU: 23%     │ Code: 125k   │ Graph: 45ms  │ ↑ 12%        │   │
│ └──────────────┴──────────────┴──────────────┴──────────────┘   │
│                                                                   │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ 📈 API Calls (Last 24h)                                      │ │ ← Line Chart
│ │                                ╱╲                            │ │
│ │                            ╱╲ ╱  ╲  ╱╲                       │ │
│ │                         ╱╲╱  ╲    ╲╱  ╲                      │ │
│ │ ────────────────────────────────────────────────────────────│ │
│ │ 00:00    06:00    12:00    18:00    23:59                   │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌────────────────────┬────────────────────────────────────────┐  │
│ │ 🔍 Embeddings      │ ⚠️ Recent Alerts (2)                   │  │ ← Two columns
│ │ ┌────────┬────────┐│ • 🔴 Disk space <20%                   │  │
│ │ │💬 Conv │💻 Code ││ • ⚠️ Slow queries (3)                  │  │
│ │ │7,972   │125k   ││ [View All Alerts →]                    │  │
│ │ │10ms avg│12ms avg││                                        │  │
│ │ └────────┴────────┘│                                        │  │
│ └────────────────────┴────────────────────────────────────────┘  │
│                                                                   │
│ 🚀 Quick Actions:                                                │
│ [🔍 Search Code] [🕸️ View Graph] [📋 Check Logs] [🧪 Run Test]  │ ← Action buttons
└──────────────────────────────────────────────────────────────────┘
```

### Search Unifiée
```
┌──────────────────────────────────────────────────────────────────┐
│ 🧠 MnemoLite  [Search*] [Graph] [Dashboard] [Monitoring] [⚙️]   │
├──────────────────────────────────────────────────────────────────┤
│                      🔍 Unified Search                            │
│                                                                   │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ 🔍  postgresql timeout                              [×]    │   │ ← Search bar
│ │     [Type: All ▾] [Scope: Everything ▾] [Date: All ▾]    │   │ ← Filters
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ Results: 23 found in 15ms                        [Export ↓]      │
│                                                                   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 💬 Conversations (8)                                   [Expand ▾] │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ 📅 2025-10-15 14:23 | Score: 0.92                         │   │
│ │ Discussion on PostgreSQL connection timeout                │   │
│ │ "...we should set a timeout of 30s to avoid hanging..."   │   │ ← Snippet
│ │ [View Full Conversation] [Related Code]                   │   │
│ └────────────────────────────────────────────────────────────┘   │
│ ...7 more conversations...                                       │
│                                                                   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 💻 Code (12)                                           [Expand ▾] │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ 📁 api/db/connection.py:45 | Score: 0.88                   │   │
│ │ async def connect(timeout=30):                             │   │
│ │     """Connect to PostgreSQL with timeout"""               │   │
│ │     await asyncpg.connect(timeout=timeout)                 │   │ ← Code snippet
│ │ [View File] [View in Graph] [Copy Code]                   │   │
│ └────────────────────────────────────────────────────────────┘   │
│ ...11 more code results...                                       │
│                                                                   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ 🔧 Functions (3)                                       [Expand ▾] │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ set_connection_timeout() in api/db/utils.py                │   │
│ │ Parameters: timeout: int, retry: bool = True               │   │
│ │ Returns: bool                                              │   │
│ │ [View Definition] [Find All Usages]                       │   │
│ └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Monitoring Temps Réel
```
┌──────────────────────────────────────────────────────────────────┐
│ 🧠 MnemoLite  [Search] [Graph] [Dashboard] [Monitoring*] [⚙️]   │
├──────────────────────────────────────────────────────────────────┤
│                    ⚡ Real-Time Monitoring                        │
│                                                                   │
│ ┌────────────────────┬─────────────────────────────────────────┐ │
│ │ 🖥️ System (Live)   │ 📊 CPU Usage (Last 60s)                 │ │
│ │ CPU:  [▓▓▓░░] 34%  │ ┌───────────────────────────────────┐   │ │
│ │ RAM:  [▓▓░░░] 28%  │ │    ╱╲  ╱╲                         │   │ │
│ │ Disk: [▓░░░░] 12%  │ │   ╱  ╲╱  ╲      ╱╲                │   │ │ ← Live charts
│ │ Net:  ↓45 ↑12 MB/s │ │  ╱         ╲___╱  ╲___            │   │ │
│ │                    │ │ ──────────────────────────────────│   │ │
│ │ 🚀 Services        │ │ 0s        30s        60s          │   │ │
│ │ ● API      (23ms)  │ └───────────────────────────────────┘   │ │
│ │ ● PostgreSQL (5ms) │                                         │ │
│ │ ● Redis    (1ms)   │ 📈 Request Rate (Last 5m)               │ │
│ │ ● Embedding (45ms) │ ┌───────────────────────────────────┐   │ │
│ └────────────────────┤ │ ████████ 234 req/min               │   │ │
│                      │ │ Peak: 456 @ 14:23                 │   │ │
│                      │ │ Avg:  198 req/min                 │   │ │
│                      │ └───────────────────────────────────┘   │ │
│                      └─────────────────────────────────────────┘ │
│                                                                   │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ 📋 Live Logs (Auto-refresh)              [⏸️ Pause] [Clear] │ │ ← Logs stream
│ │ [Filter: All ▾] [Level: All ▾] [Search: _____________]      │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ 14:23:45 INFO  API request: GET /api/v1/search              │ │
│ │ 14:23:45 INFO  Query: "postgresql timeout"                  │ │
│ │ 14:23:46 DEBUG Search completed in 12ms                      │ │
│ │ 14:23:50 WARN  Slow query detected (125ms)           ⚠️     │ │
│ │ 14:23:51 ERROR Redis connection timeout              🔴     │ │
│ │ 14:23:52 INFO  Retrying Redis connection...                 │ │
│ │ 14:23:53 INFO  Redis reconnected                            │ │
│ │ [Auto-scroll ✓] [Export] [Load More...]                    │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ ⚠️ Active Alerts (2)                           [View All →] │ │ ← Alerts
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ 🔴 CRITICAL: Disk space <20% (18% remaining)                │ │
│ │ Duration: 3m 18s | [Acknowledge] [Auto-cleanup] [Details]  │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ ⚠️  WARNING: Slow queries (3 in last 5 min)                 │ │
│ │ Avg: 145ms (target <100ms) | [View Queries] [Dismiss]      │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🎨 Propositions Additionnelles (Bonus)

### 1. Embedding Visualizer 🔬

**Concept**: Visualiser les embeddings en 2D/3D via t-SNE ou UMAP

**Use case**:
- Voir si conversations similaires se "clustent"
- Identifier outliers (embeddings bizarres)
- Comprendre distribution sémantique

**UI**:
```
┌──────────────────────────────────────────────────────────────────┐
│ 🔬 Embedding Visualizer                                          │
│ [Dataset: Conversations ▾] [Method: t-SNE ▾] [Perplexity: 30]   │
├──────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────┐   │
│ │                                                            │   │
│ │         •  •       •  Cluster 1: PostgreSQL               │   │
│ │      • •  • •                                             │   │
│ │    •  •    •  •                                           │   │
│ │                                                            │   │
│ │            •   • •                                         │   │
│ │           •  •  •    Cluster 2: Python                    │   │
│ │            • •  •                                          │   │
│ │                                                            │   │
│ │                       •                                    │   │
│ │                    •  •   Outliers                         │   │
│ │                                                            │   │
│ │ [Zoom] [Pan] [Select Cluster] [Export]                    │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ 📊 Selected Cluster Details:                                     │
│ • Cluster 1: 234 conversations                                   │
│ • Centroid keywords: postgresql, database, connection, timeout   │
│ • Avg distance to centroid: 0.23                                 │
│ • [View All Conversations in Cluster]                           │
└──────────────────────────────────────────────────────────────────┘
```

**Technos**:
- **t-SNE**: sklearn.manifold.TSNE (Python backend)
- **3D viz**: Three.js or Plotly
- **Clustering**: HDBSCAN

### 2. Query Builder Visual 🏗️

**Concept**: Construire requêtes complexes visuellement (vs texte)

**UI**:
```
┌──────────────────────────────────────────────────────────────────┐
│ 🏗️ Visual Query Builder                                          │
├──────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ Find:  [Conversations ▾]                                   │   │
│ │ Where: [+ Add Condition]                                   │   │
│ │                                                            │   │
│ │   ┌─────────────────────────────────────────────────────┐ │   │
│ │   │ Field: [Date ▾]  Operator: [After ▾]  Value: 2025-10-01│   │
│ │   └─────────────────────────────────────────────────────┘ │   │
│ │   AND                                                      │   │
│ │   ┌─────────────────────────────────────────────────────┐ │   │
│ │   │ Field: [Keywords ▾]  Operator: [Contains ▾]  "postgres"│   │
│ │   └─────────────────────────────────────────────────────┘ │   │
│ │   AND                                                      │   │
│ │   ┌─────────────────────────────────────────────────────┐ │   │
│ │   │ Field: [Score ▾]  Operator: [> ▾]  Value: 0.8       │   │
│ │   └─────────────────────────────────────────────────────┘ │   │
│ │                                                            │   │
│ │ Order by: [Date ▾] [Descending ▾]                         │   │
│ │ Limit: [50 ▾]                                              │   │
│ │                                                            │   │
│ │ [Preview Results (23)] [Run Query] [Save Query]           │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ 📝 Generated Query (SQL):                                        │
│ SELECT * FROM conversations                                      │
│ WHERE date > '2025-10-01'                                        │
│   AND content LIKE '%postgres%'                                 │
│   AND similarity_score > 0.8                                     │
│ ORDER BY date DESC                                               │
│ LIMIT 50;                                                        │
└──────────────────────────────────────────────────────────────────┘
```

### 3. Batch Operations 🔁

**Concept**: Actions en masse sur résultats

**Use case**:
- Supprimer 50 vieilles conversations
- Re-indexer 100 chunks
- Exporter 200 embeddings

**UI**:
```
┌──────────────────────────────────────────────────────────────────┐
│ 🔁 Batch Operations                                              │
├──────────────────────────────────────────────────────────────────┤
│ Selection: 234 items selected                                    │
│                                                                   │
│ Actions:                                                          │
│ [Delete Selected]  [Re-index]  [Export]  [Tag]  [Move]          │
│                                                                   │
│ ⚠️ WARNING: This action will affect 234 items. Confirm?          │
│ [Cancel] [Confirm Delete]                                        │
│                                                                   │
│ 📊 Progress:                                                      │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ [▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░] 65% (152/234 items processed)      │   │
│ │ Estimated time remaining: 12 seconds                       │   │
│ └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 4. Comparison Mode 🔀

**Concept**: Comparer 2 versions d'un code chunk ou conversation

**Use case**:
- "Comment ce code a évolué?"
- "Quelle version de ma conversation est meilleure?"

**UI**:
```
┌──────────────────────────────────────────────────────────────────┐
│ 🔀 Comparison View                                               │
├──────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────┬──────────────────────────────────┐  │
│ │ Version A (2025-10-15)   │ Version B (2025-10-28)          │  │
│ ├──────────────────────────┼──────────────────────────────────┤  │
│ │ async def connect():     │ async def connect(timeout=30):   │  │
│ │     await asyncpg.connect│     await asyncpg.connect(      │  │
│ │         ()               │         timeout=timeout)         │  │ ← Diff highlight
│ │                          │     # Added timeout handling      │  │
│ │     return True          │     return True                  │  │
│ └──────────────────────────┴──────────────────────────────────┘  │
│                                                                   │
│ Changes:                                                          │
│ + Added: timeout parameter (line 1)                              │
│ + Added: timeout in asyncpg call (line 2-3)                      │
│ + Added: comment explaining timeout (line 4)                     │
│                                                                   │
│ [Use Version A] [Use Version B] [Merge Manually]                 │
└──────────────────────────────────────────────────────────────────┘
```

### 5. Notebook/Playground 📓

**Concept**: Interface type Jupyter pour tester queries

**Use case**:
- Tester requêtes API
- Expérimenter embeddings
- Debugger searches

**UI**:
```
┌──────────────────────────────────────────────────────────────────┐
│ 📓 MnemoLite Playground                                          │
├──────────────────────────────────────────────────────────────────┤
│ Cell 1: [Python ▾]                                    [Run ▶️]   │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ # Test search API                                          │   │
│ │ response = await client.get(                               │   │
│ │     "/api/v1/search/unified",                              │   │
│ │     params={"q": "postgresql", "type": "code"}             │   │
│ │ )                                                          │   │
│ │ print(response.json())                                     │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ Output:                                                           │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ {                                                          │   │
│ │   "results": [                                             │   │
│ │     {"file": "api/db/connection.py", "score": 0.92, ...}   │   │
│ │   ],                                                       │   │
│ │   "total": 23,                                             │   │
│ │   "time_ms": 12                                            │   │
│ │ }                                                          │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ Cell 2: [Markdown ▾]                                  [Run ▶️]   │
│ ┌────────────────────────────────────────────────────────────┐   │
│ │ ## Analysis                                                │   │
│ │ The search returned 23 results in 12ms.                    │   │
│ │ Top result has score 0.92 (very relevant).                 │   │
│ └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│ [+ New Cell] [Save Notebook] [Export HTML]                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📦 Décomposition en Stories (Estimation)

### Phase 1: Infrastructure & Navigation (13 pts)

**Story 25.1: Navbar Unifiée + Routing** (5 pts)
- Créer navbar sticky avec tous les liens
- Setup routing (React Router ou FastAPI routes)
- Active state highlighting
- Responsive collapse (hamburger menu)
- **Tests**: Navigation tests, responsive tests
- **Files**: `components/Navbar.tsx`, `routes/index.tsx`

**Story 25.2: Dashboard Backend API** (3 pts)
- Endpoint `/api/v1/dashboard/summary`
- Endpoint `/api/v1/dashboard/health`
- Aggregation métriques (CPU, RAM, Disk, Services)
- **Tests**: API tests, health check tests
- **Files**: `routes/dashboard_routes.py`, `services/system_metrics.py`

**Story 25.3: Dashboard Frontend (Layout + Cards)** (5 pts)
- Layout principal (grid 4 cards)
- Cards: Santé, Storage, Performance, Activity
- Basic styling (TailwindCSS)
- Responsive design
- **Tests**: Component tests, layout tests
- **Files**: `pages/Dashboard.tsx`, `components/MetricCard.tsx`

---

### Phase 2: Dashboard Complet (18 pts)

**Story 25.4: Embeddings Overview Cards** (3 pts)
- 2 cards (Conversations vs Code)
- Métriques: Count, model, dimension, avg latency
- API endpoint: `/api/v1/embeddings/stats`
- **Tests**: API tests, component tests
- **Files**: `components/EmbeddingCard.tsx`, `routes/embeddings_routes.py`

**Story 25.5: Activity Chart (Line Chart)** (5 pts)
- Chart.js integration
- API endpoint: `/api/v1/dashboard/activity?period=24h`
- Time series data (API calls over time)
- Hover tooltips (endpoint details)
- **Tests**: Chart rendering tests, data tests
- **Files**: `components/ActivityChart.tsx`, `routes/dashboard_routes.py`

**Story 25.6: Recent Alerts Widget** (5 pts)
- Fetch `/api/v1/monitoring/alerts`
- Display last 5 alerts (Critical/Warning)
- Color coding + icons
- Click → jump to monitoring page
- **Tests**: Alert display tests, API tests
- **Files**: `components/AlertsWidget.tsx`, `routes/monitoring_routes.py`

**Story 25.7: Quick Actions Buttons** (2 pts)
- 4 boutons: Search, Graph, Logs, Test
- Modal open ou redirect
- Icons + tooltips
- **Tests**: Button click tests
- **Files**: `components/QuickActions.tsx`

**Story 25.8: Real-Time Dashboard (SSE)** (3 pts)
- SSE endpoint: `/api/v1/dashboard/stream`
- Update métriques every 5s
- Auto-reconnect si disconnect
- **Tests**: SSE connection tests, reconnect tests
- **Files**: `hooks/useDashboardStream.ts`, `routes/dashboard_routes.py`

---

### Phase 3: Recherche Unifiée (15 pts)

**Story 25.9: Unified Search Backend** (8 pts)
- Endpoint `/api/v1/search/unified`
- Search across: Conversations + Code + Functions
- Hybrid search (lexical + vector)
- Faceted filters (type, scope, date)
- Ranking + scoring
- **Tests**: Search tests (all types), ranking tests
- **Files**: `routes/search_unified_routes.py`, `services/unified_search.py`

**Story 25.10: Unified Search Frontend** (5 pts)
- Search bar + filters
- Results grouped by type (Conversations, Code, Functions)
- Highlighting keywords
- Pagination or infinite scroll
- **Tests**: Search UI tests, filter tests
- **Files**: `pages/UnifiedSearch.tsx`, `components/SearchResults.tsx`

**Story 25.11: Search Instant Preview** (2 pts)
- Instant results pendant typing (debounce 300ms)
- Dropdown preview (top 5 results)
- Click → full results page
- **Tests**: Debounce tests, preview tests
- **Files**: `components/InstantSearch.tsx`

---

### Phase 4: Graph Avancé (13 pts)

**Story 25.12: Cytoscape.js Integration** (5 pts)
- Replace D3.js par Cytoscape.js
- Basic layout (force-directed)
- Zoom/Pan fluide
- Node click → details panel
- **Tests**: Graph rendering tests, interaction tests
- **Files**: `components/CodeGraph.tsx`, `utils/graph.ts`

**Story 25.13: Graph Layout Algorithms** (3 pts)
- Multiple layouts: Force, Hierarchical, Circular, Grid
- Selector UI (dropdown)
- Smooth transition entre layouts
- **Tests**: Layout switch tests
- **Files**: `components/GraphControls.tsx`, `utils/graph_layouts.ts`

**Story 25.14: Graph Filters & Details Panel** (3 pts)
- Filter by type (Services, Routes, Utils, Tests)
- Filter by depth (1, 2, 3 hops)
- Details panel: Imports, Used by, Metrics
- **Tests**: Filter tests, panel tests
- **Files**: `components/GraphFilters.tsx`, `components/NodeDetailsPanel.tsx`

**Story 25.15: Path Finding Feature** (2 pts)
- UI: "Find path from A to B"
- Backend: Shortest path algorithm (NetworkX)
- Highlight path in graph
- **Tests**: Path finding tests
- **Files**: `routes/graph_routes.py`, `services/graph_path.py`

---

### Phase 5: Monitoring Temps Réel (20 pts)

**Story 25.16: System Metrics Backend (SSE)** (5 pts)
- SSE endpoint: `/api/v1/monitoring/metrics/stream`
- Collect: CPU, RAM, Disk, Network
- Update every 2 seconds
- **Tests**: Metrics collection tests, SSE tests
- **Files**: `routes/monitoring_routes.py`, `services/system_monitor.py`

**Story 25.17: System Metrics Frontend (Live Charts)** (5 pts)
- Progress bars: CPU, RAM, Disk
- Live line charts (CPU over time)
- SSE consumer (auto-reconnect)
- **Tests**: Chart update tests, SSE consumer tests
- **Files**: `components/SystemMetrics.tsx`, `hooks/useMetricsStream.ts`

**Story 25.18: Services Health Check** (3 pts)
- Ping: API, PostgreSQL, Redis, Embedding
- Display latency + status (green/red dot)
- Update every 5s
- **Tests**: Health check tests
- **Files**: `services/health_check.py`, `components/ServicesHealth.tsx`

**Story 25.19: Live Logs Streaming (SSE)** (5 pts)
- SSE endpoint: `/api/v1/monitoring/logs/stream`
- Log queue (in-memory or Redis)
- Filters: Level, source, keyword
- Auto-scroll + pause
- **Tests**: Log streaming tests, filter tests
- **Files**: `routes/monitoring_routes.py`, `components/LiveLogs.tsx`

**Story 25.20: Active Alerts System** (2 pts)
- Alert triggers (CPU >80%, Disk <20%, etc.)
- Display in monitoring page + dashboard
- Actions: Acknowledge, dismiss, view details
- **Tests**: Alert trigger tests, UI tests
- **Files**: `services/alerts.py`, `components/ActiveAlerts.tsx`

---

### Phase 6: Settings & Polish (8 pts)

**Story 25.21: Settings Page (Backend + Frontend)** (5 pts)
- GET/PUT `/api/v1/settings`
- Sections: General, Performance, Monitoring, Embeddings
- Form validation
- Save → persist to DB or config file
- **Tests**: Settings CRUD tests, validation tests
- **Files**: `pages/Settings.tsx`, `routes/settings_routes.py`

**Story 25.22: Dark Mode Toggle** (2 pts)
- TailwindCSS dark mode classes
- Toggle in navbar or settings
- Persist preference (localStorage)
- **Tests**: Theme switch tests
- **Files**: `components/ThemeToggle.tsx`, `utils/theme.ts`

**Story 25.23: Responsive Design (Mobile)** (1 pt)
- Test all pages on mobile (375px width)
- Hamburger menu for navbar
- Cards stack vertically
- **Tests**: Responsive tests (Playwright)
- **Files**: Update all components with responsive classes

---

## 📊 Estimation Totale

| Phase | Stories | Points | Durée Estimée |
|-------|---------|--------|---------------|
| **Phase 1**: Navigation | 3 | 13 pts | 1-2 semaines |
| **Phase 2**: Dashboard | 5 | 18 pts | 2-3 semaines |
| **Phase 3**: Search | 3 | 15 pts | 2 semaines |
| **Phase 4**: Graph | 4 | 13 pts | 1-2 semaines |
| **Phase 5**: Monitoring | 5 | 20 pts | 2-3 semaines |
| **Phase 6**: Settings | 3 | 8 pts | 1 semaine |
| **TOTAL** | **23 stories** | **87 pts** | **9-13 semaines** |

**Facteurs d'ajustement**:
- **Solo dev**: ×1.5 (pas de parallélisation)
- **Apprentissage**: Si React nouveau, ×1.3
- **Bugs imprévus**: Buffer +20%

**Estimation réaliste**: **11-16 semaines** (3-4 mois)

---

## 🚀 Recommandations Stratégiques

### Ordre d'Implémentation Suggéré

**MVP1 (4-6 semaines)**:
1. Phase 1: Navigation (13 pts) - **FOUNDATIONAL**
2. Phase 2: Dashboard (18 pts) - **HIGH VALUE**

**MVP2 (6-8 semaines)**:
3. Phase 3: Search (15 pts) - **USER DEMAND**
4. Phase 5: Monitoring (20 pts) - **OPERATIONAL NEED**

**MVP3 (8-12 semaines)**:
5. Phase 4: Graph (13 pts) - **NICE TO HAVE**
6. Phase 6: Settings (8 pts) - **POLISH**

### Tech Stack Decision

**Si React**:
- ✅ Pros: Riche ecosystem, SSE facile, scalable
- ❌ Cons: Build complexity, learning curve
- **Durée**: +2 semaines (learning)

**Si HTMX**:
- ✅ Pros: Simple, no build, SSR
- ❌ Cons: Moins de libs, custom JS pour charts
- **Durée**: Base timeline

**Recommandation**: **React** si projet long-terme, **HTMX** si MVP rapide.

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| **SSE complexity** | High | POC early, test reconnect |
| **Chart perf (large data)** | Medium | Pagination, sampling |
| **Graph slow (1000+ nodes)** | High | Virtual rendering, lazy load |
| **Responsive break** | Medium | Test early, use Tailwind defaults |

---

## 📝 Prochaines Étapes

1. **Validation utilisateur**: User confirme vision + priorités
2. **Tech stack decision**: React vs HTMX
3. **Phase 1 kick-off**: Stories 25.1-25.3
4. **Prototyping**: Navbar + Dashboard layout
5. **Iteration**: Ajuster si feedback

---

## 🤔 Questions Ouvertes

1. **Frontend stack**: React ou HTMX?
2. **Dark mode**: Prioritaire ou Phase 6?
3. **Mobile**: Must-have ou nice-to-have?
4. **Embeddings viz**: Inclure ou separate EPIC?
5. **Export features**: Quels formats? (CSV, JSON, PDF?)
6. **Multi-user**: Authentification needed?
7. **Notebook**: Jupyter-like ou just API docs?

---

**Document Status**: ✅ READY FOR REVIEW
**Next Step**: User validation + tech stack decision
**Estimated Total**: 87 story points (3-4 months solo dev)
