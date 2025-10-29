# EPIC-21: UI/UX Modernization - Ultrathink Analysis

**Date**: 2025-10-23
**Status**: BRAINSTORM / ULTRATHINK
**Objectif**: Moderniser l'UI/UX de MnemoLite pour visualiser facilement toutes les données (style SCADA maintenu)

---

## 🎯 Vision Globale

### Objectif Principal

**"Visualiser et consulter facilement et au mieux TOUTES les données de MnemoLite"**

- Maintenir le **style SCADA** (industriel, technique, dark theme)
- Améliorer l'**accessibilité** et l'**utilisabilité** des données
- Moderniser avec les **best practices 2025**
- Rester **KISS** : pas d'over-engineering, stack minimaliste

### Principes Directeurs

1. **EXTEND > REBUILD** : Améliorer progressivement, pas de refonte totale
2. **SCADA Aesthetic** : Style industriel, monospace, couleurs techniques
3. **Progressive Enhancement** : HTMX + Alpine.js (zéro JavaScript lourd)
4. **Real-time First** : SSE + polling pour données en temps réel
5. **Mobile-Aware** : Responsive mais desktop-first (usage technique)

---

## 📊 État des Lieux - Données à Visualiser

### 1. Code Intelligence (Actuel)

**Sources de données**:
- `code_chunks` : ~14 chunks (actuellement), potentiellement 1M+
  - Fields: file_path, language, chunk_type, source_code, name, name_path, start_line/end_line
  - Embeddings: text (768D) + code (768D)
  - Metadata: JSONB (complexity, calls, imports, signature)
- `nodes` : Graph nodes (fonction, classe, méthode)
  - Properties: chunk_id, file_path, complexity, signature
- `edges` : Graph relations (calls, imports)
  - Properties: JSONB (context)

**Visualisations actuelles**:
- `/ui/code/dashboard` : KPIs basiques (total files, chunks, functions, etc.)
- `/ui/code/search` : Résultats de recherche (liste)
- `/ui/code/graph` : Cytoscape.js pour visualiser dépendances
- `/ui/code/repos` : Liste des repositories
- `/ui/code/upload` : Upload de fichiers

**Problèmes identifiés**:
- Dashboard trop basique (juste des chiffres)
- Recherche peu interactive (pas de filtres avancés, pas de preview)
- Graph limité (pas de drill-down, pas de path highlighting)
- Pas de vue temporelle (évolution du code dans le temps)
- Pas de métriques de qualité code (complexity trends, hotspots)

### 2. Events System (Actuel)

**Sources de données**:
- `events` : ~50k events (actuellement), potentiellement 500k+
  - Fields: id, timestamp, content, embedding, metadata
  - Partitioning: prévu à 500k

**Visualisations actuelles**:
- `/ui/` : Dashboard principal avec KPIs
- `/ui/search` : Recherche d'événements
- Chart.js basique pour quelques métriques

**Problèmes identifiés**:
- Pas de vue temporelle (timeline)
- Pas de filtres avancés (par type, par période)
- Pas de drill-down dans les événements
- Pas de corrélation entre événements

### 3. Observability (EPIC-20 - À Venir)

**Sources de données futures**:
- `metrics` : Table PostgreSQL (API, Redis, PostgreSQL metrics)
- Logs structurés : via structlog (streaming SSE)
- Cache stats : Redis (hit rate, memory, keys)
- DB stats : PostgreSQL (connections, queries, slow queries)

**Visualisations prévues (EPIC-20 MVP)**:
- Dashboard avec Chart.js (latency, throughput, errors)
- SSE pour logs en temps réel
- Métriques système (CPU, RAM, disk)

**Opportunités d'amélioration**:
- Ajouter heat maps (hot endpoints, slow queries)
- Ajouter corrélations (errors vs latency)
- Ajouter alerting visuel (seuils, anomalies)

---

## 🔍 Recherche Web - Synthèse des Best Practices 2025

### 1. Dashboard Design Trends 2025

**Sources** : Various industry articles on modern dashboard design

**Tendances clés** :
1. **Real-time Dashboards** : Données en temps réel (SSE, WebSocket)
2. **AI-Driven Insights** : Suggestions automatiques, anomaly detection
3. **Mobile-First** : Responsive, touch-friendly (mais nous : desktop-first)
4. **Data Storytelling** : Contexte, pas juste des chiffres
5. **Dark Mode** : Standard en 2025 (nous : déjà SCADA dark theme)
6. **Micro-Interactions** : Animations subtiles, feedback utilisateur
7. **Progressive Disclosure** : Information hiérarchisée (drill-down)

**Application à MnemoLite** :
- ✅ Real-time : SSE + HTMX polling (déjà prévu EPIC-20)
- ⏸️ AI-Driven : YAGNI pour MVP (bonus futur)
- ✅ Dark Mode : SCADA theme déjà présent
- ✅ Progressive Disclosure : Implémenter drill-down partout
- 🆕 Data Storytelling : Ajouter contexte aux métriques

### 2. Data Visualization Libraries

**Comparatif des solutions** :

| Library | Pros | Cons | Use Case MnemoLite |
|---------|------|------|---------------------|
| **Chart.js 4.4** (actuel) | Simple, léger (60KB), bonne perf | Limité pour viz complexes | ✅ Garder pour dashboards basiques |
| **D3.js 7.x** | Très puissant, customizable | Lourd (500KB), courbe apprentissage | ⏸️ YAGNI pour MVP, considérer si besoins complexes |
| **Apache ECharts 5.x** | Scalable (1M+ points), beautiful, 3D | 900KB, complexe | 🆕 **RECOMMANDÉ** pour viz avancées |
| **Plotly.js** | Scientifique, interactive | Lourd (3MB), overkill | ❌ Trop lourd |
| **uPlot** | Ultra-rapide, léger (45KB) | Timeline only | 🆕 **RECOMMANDÉ** pour timelines |
| **Cytoscape.js 3.28** (actuel) | Excellent pour graphs | Spécialisé graphs | ✅ Garder pour code graph |

**Recommandations** :

1. **Garder Chart.js** pour dashboards basiques (EPIC-20 MVP)
   - KPIs, bar charts, line charts simples
   - Déjà intégré, performant, KISS

2. **Ajouter uPlot** pour timelines haute performance
   - Événements temporels (50k-500k points)
   - Métriques en temps réel (latency over time)
   - Logs streaming avec scrubber
   - **45KB** : négligeable

3. **Ajouter Apache ECharts** pour visualisations avancées
   - Heat maps (code hotspots, endpoint usage)
   - Sankey diagrams (data flow)
   - 3D graphs (si nécessaire)
   - Tree maps (code complexity)
   - **900KB** : acceptable pour valeur ajoutée

**Stack Finale Recommandée** :
```
Chart.js 4.4 (60KB)    → Dashboards basiques, KPIs
uPlot 1.6 (45KB)       → Timelines haute perf, scrubber
Apache ECharts 5.5 (900KB) → Viz avancées (heat maps, sankey, etc.)
Cytoscape.js 3.28 (300KB)  → Code graphs (déjà présent)
───────────────────────────────────────────────────────
Total: ~1.3MB (gzipped ~400KB) → Acceptable
```

### 3. HTMX 2.0 + Alpine.js Revolution

**HTMX 2.0** (Released Q1 2025) :

**Nouveautés clés** :
- `hx-on:*` : Event handlers simplifiés
- `hx-swap-oob` : Out-of-band swaps améliorés
- WebSocket support natif
- Meilleure intégration SSE
- View Transitions API support

**Alpine.js 3.x** :

**Pourquoi Alpine.js ?**
- **Léger** : 15KB gzipped
- **Reactive** : x-data, x-bind, x-show
- **Complémentaire à HTMX** : HTMX pour server, Alpine pour client
- **KISS** : Pas de build step, inline dans HTML

**Pattern HTMX + Alpine** :
```html
<!-- HTMX pour data fetching -->
<div hx-get="/api/metrics" hx-trigger="every 5s" hx-target="#metrics">
  <!-- Alpine pour interactions client-side -->
  <div x-data="{ view: 'chart' }">
    <button @click="view = 'chart'">Chart</button>
    <button @click="view = 'table'">Table</button>

    <div x-show="view === 'chart'">
      <canvas id="chart"></canvas>
    </div>
    <div x-show="view === 'table'">
      <table>...</table>
    </div>
  </div>
</div>
```

**Application à MnemoLite** :
- HTMX : déjà utilisé, continuer et étendre
- Alpine.js : **NOUVEAU**, ajouter pour interactions client
  - Filtres (show/hide)
  - Tabs (switch views)
  - Modals (overlays)
  - Dropdowns (menus)
  - Toggle states (expand/collapse)

### 4. SCADA Theme Modernization

**SCADA Style Guide 2025** :

**Couleurs** :
```css
/* Base (déjà présent) */
--bg-dark: #0a0e27;
--bg-card: #1a1f3a;
--text-primary: #e0e0e0;
--text-secondary: #a0a0a0;

/* Accents (améliorer contraste) */
--accent-blue: #00d4ff;    /* Info, liens */
--accent-green: #00ff88;   /* Success, positive */
--accent-red: #ff4466;     /* Error, alerts */
--accent-yellow: #ffcc00;  /* Warning */
--accent-cyan: #00ffdd;    /* Highlight */

/* Gradients (ajouter pour profondeur) */
--gradient-card: linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%);
--gradient-accent: linear-gradient(90deg, #00d4ff 0%, #00ff88 100%);

/* Borders (améliorer définition) */
--border-subtle: 1px solid rgba(0, 212, 255, 0.1);
--border-emphasis: 1px solid rgba(0, 212, 255, 0.3);
--border-glow: 0 0 10px rgba(0, 212, 255, 0.3);
```

**Typography** :
```css
/* Monospace (technique, SCADA) */
--font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;
--font-sans: 'Inter', 'Roboto', sans-serif; /* Pour labels, body text */

/* Sizes */
--text-xs: 0.75rem;   /* 12px - Labels */
--text-sm: 0.875rem;  /* 14px - Body */
--text-base: 1rem;    /* 16px - Default */
--text-lg: 1.125rem;  /* 18px - Headings */
--text-xl: 1.25rem;   /* 20px - Titles */
--text-2xl: 1.5rem;   /* 24px - Page headers */
```

**Components** :
```css
/* Cards */
.card-scada {
  background: var(--gradient-card);
  border: var(--border-subtle);
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
  transition: all 0.2s ease;
}

.card-scada:hover {
  border: var(--border-emphasis);
  box-shadow: var(--border-glow);
  transform: translateY(-2px);
}

/* Buttons */
.btn-scada {
  background: rgba(0, 212, 255, 0.1);
  border: var(--border-subtle);
  color: var(--accent-blue);
  padding: 0.5rem 1rem;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-scada:hover {
  background: rgba(0, 212, 255, 0.2);
  border-color: var(--accent-blue);
  box-shadow: 0 0 10px rgba(0, 212, 255, 0.2);
}

/* Inputs */
.input-scada {
  background: rgba(10, 14, 39, 0.5);
  border: var(--border-subtle);
  color: var(--text-primary);
  padding: 0.5rem 1rem;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  border-radius: 4px;
}

.input-scada:focus {
  outline: none;
  border-color: var(--accent-blue);
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
}

/* Badges */
.badge-scada {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid var(--accent-blue);
  color: var(--accent-blue);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Tables */
.table-scada {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}

.table-scada th {
  background: rgba(0, 212, 255, 0.05);
  border-bottom: 2px solid var(--accent-blue);
  color: var(--accent-blue);
  padding: 0.75rem;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: var(--text-xs);
}

.table-scada td {
  border-bottom: var(--border-subtle);
  padding: 0.75rem;
  color: var(--text-primary);
}

.table-scada tr:hover {
  background: rgba(0, 212, 255, 0.05);
}
```

**Micro-interactions** :
```css
/* Pulse animation pour real-time indicators */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.real-time-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: var(--accent-green);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
  box-shadow: 0 0 10px var(--accent-green);
}

/* Glow effect on hover */
.glow-on-hover:hover {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
  transition: box-shadow 0.3s ease;
}

/* Loading skeleton */
@keyframes shimmer {
  0% { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}

.skeleton {
  background: linear-gradient(
    90deg,
    rgba(26, 31, 58, 0.5) 0%,
    rgba(0, 212, 255, 0.1) 50%,
    rgba(26, 31, 58, 0.5) 100%
  );
  background-size: 1000px 100%;
  animation: shimmer 2s infinite;
}
```

---

## 🎨 Propositions UI/UX - Architecture Globale

### Philosophie de Navigation

**Hub & Spoke Model** :

```
Dashboard Général (Hub)
    │
    ├─→ Code Intelligence
    │   ├─→ Search (avec filtres avancés)
    │   ├─→ Graph (avec drill-down)
    │   ├─→ Analytics (quality metrics, trends)
    │   └─→ Repositories (management)
    │
    ├─→ Events System
    │   ├─→ Timeline (uPlot, scrubber)
    │   ├─→ Search (filtres avancés)
    │   └─→ Analytics (patterns, correlations)
    │
    └─→ Observability (EPIC-20)
        ├─→ Metrics Dashboard (real-time)
        ├─→ Logs Streaming (SSE)
        ├─→ Cache Stats (Redis)
        └─→ Database Stats (PostgreSQL)
```

**Navigation Bar** (Améliorer actuelle) :
```html
<nav class="navbar-scada">
  <div class="nav-brand">
    <span class="logo">⚡ MnemoLite</span>
    <span class="real-time-indicator"></span> <!-- Pulse si système actif -->
  </div>

  <div class="nav-links">
    <a href="/ui/" class="nav-link">
      <span class="icon">📊</span>
      <span>Dashboard</span>
    </a>

    <div class="nav-dropdown" x-data="{ open: false }">
      <button @click="open = !open" class="nav-link">
        <span class="icon">💻</span>
        <span>Code</span>
        <span class="arrow" :class="{ 'rotated': open }">▼</span>
      </button>
      <div x-show="open" x-transition class="dropdown-menu">
        <a href="/ui/code/search">Search</a>
        <a href="/ui/code/graph">Graph</a>
        <a href="/ui/code/analytics">Analytics</a>
        <a href="/ui/code/repos">Repositories</a>
      </div>
    </div>

    <div class="nav-dropdown" x-data="{ open: false }">
      <button @click="open = !open" class="nav-link">
        <span class="icon">📅</span>
        <span>Events</span>
        <span class="arrow" :class="{ 'rotated': open }">▼</span>
      </button>
      <div x-show="open" x-transition class="dropdown-menu">
        <a href="/ui/events/timeline">Timeline</a>
        <a href="/ui/events/search">Search</a>
        <a href="/ui/events/analytics">Analytics</a>
      </div>
    </div>

    <a href="/ui/observability" class="nav-link">
      <span class="icon">🔍</span>
      <span>Observability</span>
    </a>
  </div>

  <div class="nav-actions">
    <button class="btn-icon" title="Notifications">
      <span>🔔</span>
      <span class="badge" x-show="hasNotifications">3</span>
    </button>
    <button class="btn-icon" title="Settings">⚙️</button>
  </div>
</nav>
```

### Dashboard Général (Hub) - Refonte

**Objectif** : Vue d'ensemble de TOUT MnemoLite en un coup d'œil

**Layout** :
```
┌─────────────────────────────────────────────────────────────┐
│ ⚡ MnemoLite Dashboard                    [Real-time: ON] 🟢 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │ Events   │ │ Code     │ │ API      │ │ Cache    │         │
│ │ 50,234   │ │ 14 chunks│ │ 245 req/s│ │ 83% hit  │         │
│ │ +123 /h  │ │ 3 repos  │ │ 12ms P95 │ │ 1.2GB    │         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                               │
│ ┌───────────────────────────┐ ┌─────────────────────────┐   │
│ │  API Latency (Last Hour)  │ │  Events Timeline (24h)  │   │
│ │                           │ │                         │   │
│ │  [Chart.js Line Chart]    │ │  [uPlot Timeline]       │   │
│ │                           │ │                         │   │
│ └───────────────────────────┘ └─────────────────────────┘   │
│                                                               │
│ ┌───────────────────────────┐ ┌─────────────────────────┐   │
│ │  Code Complexity Heatmap  │ │  Cache Hit Rate (7d)    │   │
│ │                           │ │                         │   │
│ │  [ECharts Heatmap]        │ │  [Chart.js Bar]         │   │
│ │                           │ │                         │   │
│ └───────────────────────────┘ └─────────────────────────┘   │
│                                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  Recent Activity (Real-time SSE)                        │ │
│ │  • [12:34:56] Code indexed: user_service.py (5 chunks) │ │
│ │  • [12:34:45] Search query: "authentication" (120ms)   │ │
│ │  • [12:34:32] Cache hit: events_search (0ms)           │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Implémentation** :
```html
<!-- templates/dashboard_v2.html -->
{% extends "base.html" %}

{% block content %}
<div class="dashboard-grid" x-data="dashboard()">
  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi-card card-scada"
         hx-get="/api/ui/kpis/events"
         hx-trigger="every 5s"
         hx-swap="innerHTML">
      <div class="kpi-icon">📅</div>
      <div class="kpi-value">{{ events_count }}</div>
      <div class="kpi-label">Events</div>
      <div class="kpi-trend" :class="trendClass({{ events_trend }})">
        +{{ events_trend }} /h
      </div>
    </div>

    <div class="kpi-card card-scada"
         hx-get="/api/ui/kpis/code"
         hx-trigger="every 5s"
         hx-swap="innerHTML">
      <div class="kpi-icon">💻</div>
      <div class="kpi-value">{{ code_chunks }}</div>
      <div class="kpi-label">Code Chunks</div>
      <div class="kpi-sublabel">{{ repos_count }} repos</div>
    </div>

    <div class="kpi-card card-scada"
         hx-get="/api/ui/kpis/api"
         hx-trigger="every 5s"
         hx-swap="innerHTML">
      <div class="kpi-icon">🚀</div>
      <div class="kpi-value">{{ api_qps }}</div>
      <div class="kpi-label">Requests/sec</div>
      <div class="kpi-sublabel">P95: {{ api_p95 }}ms</div>
    </div>

    <div class="kpi-card card-scada"
         hx-get="/api/ui/kpis/cache"
         hx-trigger="every 5s"
         hx-swap="innerHTML">
      <div class="kpi-icon">⚡</div>
      <div class="kpi-value">{{ cache_hit_rate }}%</div>
      <div class="kpi-label">Cache Hit Rate</div>
      <div class="kpi-sublabel">{{ cache_memory_gb }}GB used</div>
    </div>
  </div>

  <!-- Charts Grid -->
  <div class="charts-grid">
    <div class="chart-card card-scada">
      <div class="chart-header">
        <h3>API Latency (Last Hour)</h3>
        <div class="chart-controls">
          <button @click="refreshChart('latency')" class="btn-icon">🔄</button>
        </div>
      </div>
      <canvas id="latency-chart"></canvas>
    </div>

    <div class="chart-card card-scada">
      <div class="chart-header">
        <h3>Events Timeline (24h)</h3>
        <div class="chart-controls">
          <button @click="toggleZoom()" class="btn-icon">🔍</button>
        </div>
      </div>
      <div id="events-timeline"></div> <!-- uPlot -->
    </div>

    <div class="chart-card card-scada">
      <div class="chart-header">
        <h3>Code Complexity Heatmap</h3>
        <select x-model="heatmapRepo" @change="updateHeatmap()">
          <option value="all">All Repos</option>
          <option value="repo1">Repo 1</option>
        </select>
      </div>
      <div id="complexity-heatmap"></div> <!-- ECharts -->
    </div>

    <div class="chart-card card-scada">
      <div class="chart-header">
        <h3>Cache Hit Rate (7d)</h3>
      </div>
      <canvas id="cache-chart"></canvas>
    </div>
  </div>

  <!-- Activity Feed (SSE) -->
  <div class="activity-card card-scada">
    <div class="activity-header">
      <h3>Recent Activity</h3>
      <span class="real-time-indicator"></span>
    </div>
    <div id="activity-feed"
         hx-ext="sse"
         sse-connect="/api/ui/activity/stream"
         sse-swap="activity">
      <!-- SSE updates here -->
    </div>
  </div>
</div>

<script>
function dashboard() {
  return {
    heatmapRepo: 'all',

    trendClass(trend) {
      return trend > 0 ? 'trend-up' : 'trend-down';
    },

    refreshChart(chartId) {
      // Trigger HTMX refresh
      htmx.trigger(`#${chartId}-chart`, 'refresh');
    },

    toggleZoom() {
      // Toggle uPlot zoom
      const plot = window.uPlotInstances['events-timeline'];
      plot.setScale('x', { min: null, max: null });
    },

    updateHeatmap() {
      // Update ECharts heatmap
      htmx.ajax('GET', `/api/ui/heatmap?repo=${this.heatmapRepo}`, {
        target: '#complexity-heatmap'
      });
    }
  };
}
</script>
{% endblock %}
```

---

## 💻 Code Intelligence - Refonte Complète

### 1. Code Search - Améliorations Majeures

**Problèmes actuels** :
- Pas de preview du code
- Filtres limités (juste query)
- Résultats en liste basique
- Pas de highlighting syntax
- Pas de jump-to-definition

**Nouvelles Features** :

**A. Filtres Avancés**
```html
<!-- templates/code_search_v2.html -->
<div class="search-container" x-data="codeSearch()">
  <!-- Search Bar -->
  <div class="search-bar">
    <input type="text"
           x-model="query"
           @keyup.enter="search()"
           placeholder="Search code... (e.g., 'authentication', 'class:User', 'complexity:>10')"
           class="input-scada input-large">
    <button @click="search()" class="btn-scada">Search</button>
  </div>

  <!-- Filters Panel (Collapsible) -->
  <div class="filters-panel" x-show="showFilters" x-transition>
    <div class="filters-grid">
      <!-- Language Filter -->
      <div class="filter-group">
        <label>Language</label>
        <select x-model="filters.language" class="input-scada">
          <option value="">All</option>
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="typescript">TypeScript</option>
        </select>
      </div>

      <!-- Chunk Type Filter -->
      <div class="filter-group">
        <label>Type</label>
        <div class="checkbox-group">
          <label><input type="checkbox" x-model="filters.types" value="function"> Function</label>
          <label><input type="checkbox" x-model="filters.types" value="class"> Class</label>
          <label><input type="checkbox" x-model="filters.types" value="method"> Method</label>
          <label><input type="checkbox" x-model="filters.types" value="module"> Module</label>
        </div>
      </div>

      <!-- Complexity Filter -->
      <div class="filter-group">
        <label>Complexity</label>
        <div class="range-inputs">
          <input type="number" x-model="filters.complexityMin" placeholder="Min" class="input-scada input-small">
          <span>-</span>
          <input type="number" x-model="filters.complexityMax" placeholder="Max" class="input-scada input-small">
        </div>
      </div>

      <!-- Repository Filter -->
      <div class="filter-group">
        <label>Repository</label>
        <select x-model="filters.repository" class="input-scada">
          <option value="">All</option>
          <template x-for="repo in repositories" :key="repo">
            <option :value="repo" x-text="repo"></option>
          </template>
        </select>
      </div>

      <!-- Sort -->
      <div class="filter-group">
        <label>Sort By</label>
        <select x-model="filters.sortBy" class="input-scada">
          <option value="relevance">Relevance</option>
          <option value="complexity">Complexity</option>
          <option value="name">Name</option>
          <option value="file_path">File Path</option>
        </select>
      </div>

      <!-- Search Mode -->
      <div class="filter-group">
        <label>Search Mode</label>
        <div class="radio-group">
          <label><input type="radio" x-model="filters.mode" value="hybrid"> Hybrid</label>
          <label><input type="radio" x-model="filters.mode" value="semantic"> Semantic</label>
          <label><input type="radio" x-model="filters.mode" value="lexical"> Lexical</label>
        </div>
      </div>
    </div>

    <div class="filters-actions">
      <button @click="applyFilters()" class="btn-scada">Apply</button>
      <button @click="resetFilters()" class="btn-scada-secondary">Reset</button>
    </div>
  </div>

  <button @click="showFilters = !showFilters" class="btn-toggle-filters">
    <span x-text="showFilters ? 'Hide Filters' : 'Show Filters'"></span>
    <span x-text="showFilters ? '▲' : '▼'"></span>
  </button>

  <!-- Results -->
  <div class="results-container">
    <div class="results-header">
      <span class="results-count">
        <template x-if="loading">
          <span>Searching...</span>
        </template>
        <template x-if="!loading && results.length > 0">
          <span x-text="`${results.length} results in ${searchTime}ms`"></span>
        </template>
      </span>

      <div class="view-switcher">
        <button @click="view = 'list'" :class="{ active: view === 'list' }" class="btn-icon">📄</button>
        <button @click="view = 'grid'" :class="{ active: view === 'grid' }" class="btn-icon">🔲</button>
        <button @click="view = 'tree'" :class="{ active: view === 'tree' }" class="btn-icon">🌳</button>
      </div>
    </div>

    <!-- List View -->
    <div x-show="view === 'list'" class="results-list">
      <template x-for="result in results" :key="result.id">
        <div class="result-card card-scada" @click="selectResult(result)">
          <div class="result-header">
            <div class="result-title">
              <span class="badge-scada" x-text="result.chunk_type"></span>
              <span class="result-name" x-text="result.name"></span>
            </div>
            <div class="result-metadata">
              <span class="metadata-item" x-text="`Complexity: ${result.complexity || 'N/A'}`"></span>
              <span class="metadata-item" x-text="`Lines: ${result.start_line}-${result.end_line}`"></span>
              <span class="metadata-item" x-text="`Score: ${(result.score * 100).toFixed(1)}%`"></span>
            </div>
          </div>

          <div class="result-path">
            <span class="path-icon">📁</span>
            <span x-text="result.file_path"></span>
          </div>

          <!-- Code Preview -->
          <div class="code-preview">
            <pre><code class="language-python" x-text="result.source_code.slice(0, 300) + '...'"></code></pre>
          </div>

          <div class="result-actions">
            <button @click.stop="viewInGraph(result)" class="btn-scada-small">View in Graph</button>
            <button @click.stop="viewFull(result)" class="btn-scada-small">View Full</button>
            <button @click.stop="copyCode(result)" class="btn-scada-small">Copy</button>
          </div>
        </div>
      </template>
    </div>

    <!-- Grid View -->
    <div x-show="view === 'grid'" class="results-grid">
      <template x-for="result in results" :key="result.id">
        <div class="result-card-compact card-scada" @click="selectResult(result)">
          <div class="badge-scada" x-text="result.chunk_type"></div>
          <div class="result-name-compact" x-text="result.name"></div>
          <div class="result-file" x-text="result.file_path.split('/').pop()"></div>
          <div class="result-complexity">
            <span>C:</span>
            <span x-text="result.complexity || 'N/A'"></span>
          </div>
        </div>
      </template>
    </div>

    <!-- Tree View (Hierarchical by file) -->
    <div x-show="view === 'tree'" class="results-tree">
      <template x-for="(chunks, file) in groupedResults" :key="file">
        <div class="tree-node" x-data="{ expanded: false }">
          <div class="tree-header" @click="expanded = !expanded">
            <span x-text="expanded ? '▼' : '▶'"></span>
            <span class="path-icon">📄</span>
            <span x-text="file"></span>
            <span class="badge-scada" x-text="`${chunks.length} chunks`"></span>
          </div>
          <div x-show="expanded" x-transition class="tree-children">
            <template x-for="chunk in chunks" :key="chunk.id">
              <div class="tree-child card-scada" @click="selectResult(chunk)">
                <span class="badge-scada" x-text="chunk.chunk_type"></span>
                <span x-text="chunk.name"></span>
                <span class="metadata-item" x-text="`Lines: ${chunk.start_line}-${chunk.end_line}`"></span>
              </div>
            </template>
          </div>
        </div>
      </template>
    </div>
  </div>

  <!-- Full View Modal -->
  <div x-show="selectedResult"
       x-transition
       class="modal-overlay"
       @click.self="selectedResult = null">
    <div class="modal-content card-scada">
      <div class="modal-header">
        <h2 x-text="selectedResult?.name"></h2>
        <button @click="selectedResult = null" class="btn-close">✕</button>
      </div>

      <div class="modal-metadata">
        <span class="badge-scada" x-text="selectedResult?.chunk_type"></span>
        <span x-text="selectedResult?.file_path"></span>
        <span x-text="`Lines: ${selectedResult?.start_line}-${selectedResult?.end_line}`"></span>
        <span x-text="`Complexity: ${selectedResult?.complexity || 'N/A'}`"></span>
      </div>

      <div class="modal-body">
        <pre><code class="language-python" x-text="selectedResult?.source_code"></code></pre>
      </div>

      <div class="modal-actions">
        <button @click="viewInGraph(selectedResult)" class="btn-scada">View in Graph</button>
        <button @click="copyCode(selectedResult)" class="btn-scada">Copy Code</button>
        <button @click="downloadFile(selectedResult)" class="btn-scada">Download File</button>
      </div>
    </div>
  </div>
</div>

<script>
function codeSearch() {
  return {
    query: '',
    showFilters: false,
    loading: false,
    results: [],
    searchTime: 0,
    view: 'list',
    selectedResult: null,
    repositories: [],

    filters: {
      language: '',
      types: [],
      complexityMin: null,
      complexityMax: null,
      repository: '',
      sortBy: 'relevance',
      mode: 'hybrid'
    },

    async search() {
      this.loading = true;
      const start = performance.now();

      const params = new URLSearchParams({
        query: this.query,
        ...this.filters
      });

      const response = await fetch(`/v1/code/search/hybrid?${params}`);
      this.results = await response.json();

      this.searchTime = Math.round(performance.now() - start);
      this.loading = false;
    },

    applyFilters() {
      this.search();
    },

    resetFilters() {
      this.filters = {
        language: '',
        types: [],
        complexityMin: null,
        complexityMax: null,
        repository: '',
        sortBy: 'relevance',
        mode: 'hybrid'
      };
      this.search();
    },

    selectResult(result) {
      this.selectedResult = result;
    },

    viewInGraph(result) {
      window.location.href = `/ui/code/graph?highlight=${result.id}`;
    },

    viewFull(result) {
      this.selectedResult = result;
    },

    copyCode(result) {
      navigator.clipboard.writeText(result.source_code);
      // Toast notification
    },

    downloadFile(result) {
      const blob = new Blob([result.source_code], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${result.name}.${result.language}`;
      a.click();
    },

    get groupedResults() {
      return this.results.reduce((acc, result) => {
        if (!acc[result.file_path]) acc[result.file_path] = [];
        acc[result.file_path].push(result);
        return acc;
      }, {});
    }
  };
}
</script>
```

**B. Syntax Highlighting**

Ajouter **Prism.js** (léger, 2KB core + 1KB per language) :
```html
<!-- base.html -->
<link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-okaidia.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-javascript.min.js"></script>

<style>
/* Override Prism theme pour SCADA */
code[class*="language-"],
pre[class*="language-"] {
  background: rgba(10, 14, 39, 0.8);
  color: #e0e0e0;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}

.token.keyword { color: var(--accent-blue); }
.token.string { color: var(--accent-green); }
.token.function { color: var(--accent-cyan); }
.token.comment { color: var(--text-secondary); }
</style>
```

### 2. Code Graph - Améliorations

**Problèmes actuels** :
- Pas de drill-down (click pour explorer)
- Pas de path highlighting
- Pas de filtres (par complexity, par type)
- Pas de minimap (navigation)
- Pas de layout switching (hierarchical, circular, etc.)

**Nouvelles Features** :

```html
<!-- templates/code_graph_v2.html -->
<div class="graph-container" x-data="codeGraph()">
  <!-- Toolbar -->
  <div class="graph-toolbar">
    <div class="toolbar-section">
      <label>Repository</label>
      <select x-model="repository" @change="loadGraph()" class="input-scada">
        <option value="">Select...</option>
        <template x-for="repo in repositories" :key="repo">
          <option :value="repo" x-text="repo"></option>
        </template>
      </select>
    </div>

    <div class="toolbar-section">
      <label>Layout</label>
      <select x-model="layout" @change="changeLayout()" class="input-scada">
        <option value="cose">Force-Directed</option>
        <option value="breadthfirst">Hierarchical</option>
        <option value="circle">Circular</option>
        <option value="grid">Grid</option>
        <option value="concentric">Concentric</option>
      </select>
    </div>

    <div class="toolbar-section">
      <label>Filter</label>
      <div class="filter-chips">
        <button @click="toggleFilter('function')"
                :class="{ active: filters.function }"
                class="chip-scada">
          Function
        </button>
        <button @click="toggleFilter('class')"
                :class="{ active: filters.class }"
                class="chip-scada">
          Class
        </button>
        <button @click="toggleFilter('method')"
                :class="{ active: filters.method }"
                class="chip-scada">
          Method
        </button>
      </div>
    </div>

    <div class="toolbar-section">
      <label>Complexity</label>
      <input type="range"
             x-model="complexityThreshold"
             @input="filterByComplexity()"
             min="0"
             max="20"
             class="range-scada">
      <span x-text="`> ${complexityThreshold}`"></span>
    </div>

    <div class="toolbar-actions">
      <button @click="resetView()" class="btn-scada">Reset View</button>
      <button @click="exportGraph()" class="btn-scada">Export PNG</button>
      <button @click="toggleMinimap()" class="btn-scada">
        <span x-text="minimapVisible ? 'Hide' : 'Show'"></span> Minimap
      </button>
    </div>
  </div>

  <!-- Graph Canvas -->
  <div class="graph-canvas-wrapper">
    <div id="cy" class="graph-canvas"></div>

    <!-- Minimap -->
    <div x-show="minimapVisible" class="graph-minimap">
      <canvas id="minimap"></canvas>
    </div>

    <!-- Loading Overlay -->
    <div x-show="loading" class="graph-loading">
      <div class="spinner"></div>
      <span>Loading graph...</span>
    </div>
  </div>

  <!-- Info Panel -->
  <div x-show="selectedNode" class="graph-info-panel card-scada">
    <div class="info-header">
      <h3 x-text="selectedNode?.label"></h3>
      <button @click="selectedNode = null" class="btn-close">✕</button>
    </div>

    <div class="info-body">
      <div class="info-row">
        <span class="label">Type:</span>
        <span class="badge-scada" x-text="selectedNode?.node_type"></span>
      </div>
      <div class="info-row">
        <span class="label">File:</span>
        <span x-text="selectedNode?.file_path"></span>
      </div>
      <div class="info-row">
        <span class="label">Complexity:</span>
        <span x-text="selectedNode?.complexity || 'N/A'"></span>
      </div>
      <div class="info-row">
        <span class="label">Calls:</span>
        <span x-text="selectedNode?.outgoing?.length || 0"></span>
      </div>
      <div class="info-row">
        <span class="label">Called By:</span>
        <span x-text="selectedNode?.incoming?.length || 0"></span>
      </div>
    </div>

    <div class="info-actions">
      <button @click="highlightDependencies(selectedNode)" class="btn-scada">
        Highlight Dependencies
      </button>
      <button @click="viewCode(selectedNode)" class="btn-scada">
        View Code
      </button>
      <button @click="findPath(selectedNode)" class="btn-scada">
        Find Path To...
      </button>
    </div>
  </div>

  <!-- Path Finder Modal -->
  <div x-show="pathFinderOpen" class="modal-overlay" @click.self="pathFinderOpen = false">
    <div class="modal-content card-scada">
      <h2>Find Path</h2>
      <p>From: <strong x-text="pathFrom?.label"></strong></p>
      <label>To:</label>
      <select x-model="pathTo" class="input-scada">
        <option value="">Select target...</option>
        <template x-for="node in allNodes" :key="node.id">
          <option :value="node.id" x-text="node.label"></option>
        </template>
      </select>
      <button @click="findShortestPath()" class="btn-scada">Find Path</button>

      <div x-show="pathResult" class="path-result">
        <h3>Shortest Path ({{ pathResult?.length }} steps):</h3>
        <ol>
          <template x-for="step in pathResult" :key="step.id">
            <li x-text="step.label"></li>
          </template>
        </ol>
      </div>
    </div>
  </div>
</div>

<script>
function codeGraph() {
  return {
    cy: null,
    repository: '',
    repositories: [],
    layout: 'cose',
    filters: { function: true, class: true, method: true },
    complexityThreshold: 0,
    loading: false,
    selectedNode: null,
    minimapVisible: false,
    pathFinderOpen: false,
    pathFrom: null,
    pathTo: null,
    pathResult: null,
    allNodes: [],

    async init() {
      // Initialize Cytoscape
      this.cy = cytoscape({
        container: document.getElementById('cy'),
        style: this.getCytoscapeStyle(),
        layout: { name: this.layout }
      });

      // Event listeners
      this.cy.on('tap', 'node', (evt) => {
        this.selectedNode = evt.target.data();
      });

      this.cy.on('mouseover', 'node', (evt) => {
        evt.target.addClass('hover');
      });

      this.cy.on('mouseout', 'node', (evt) => {
        evt.target.removeClass('hover');
      });

      // Load repositories
      await this.loadRepositories();
    },

    async loadRepositories() {
      const response = await fetch('/v1/code/graph/repositories');
      this.repositories = await response.json();
    },

    async loadGraph() {
      if (!this.repository) return;

      this.loading = true;
      const response = await fetch(`/v1/code/graph/build?repository=${this.repository}`);
      const data = await response.json();

      this.cy.elements().remove();
      this.cy.add(data.elements);
      this.cy.layout({ name: this.layout }).run();

      this.allNodes = this.cy.nodes().map(n => n.data());
      this.loading = false;
    },

    changeLayout() {
      this.cy.layout({ name: this.layout }).run();
    },

    toggleFilter(type) {
      this.filters[type] = !this.filters[type];
      this.applyFilters();
    },

    applyFilters() {
      this.cy.nodes().forEach(node => {
        const nodeType = node.data('node_type');
        if (this.filters[nodeType]) {
          node.show();
        } else {
          node.hide();
        }
      });
    },

    filterByComplexity() {
      this.cy.nodes().forEach(node => {
        const complexity = node.data('complexity') || 0;
        if (complexity >= this.complexityThreshold) {
          node.addClass('high-complexity');
        } else {
          node.removeClass('high-complexity');
        }
      });
    },

    resetView() {
      this.cy.fit();
      this.cy.center();
    },

    exportGraph() {
      const png = this.cy.png({ scale: 2 });
      const a = document.createElement('a');
      a.href = png;
      a.download = `graph-${this.repository}.png`;
      a.click();
    },

    toggleMinimap() {
      this.minimapVisible = !this.minimapVisible;
      if (this.minimapVisible) {
        this.renderMinimap();
      }
    },

    renderMinimap() {
      // Simple minimap rendering
      const canvas = document.getElementById('minimap');
      const ctx = canvas.getContext('2d');
      // ... minimap logic
    },

    highlightDependencies(node) {
      this.cy.elements().removeClass('highlighted');

      const nodeElem = this.cy.getElementById(node.id);
      nodeElem.addClass('highlighted');

      nodeElem.outgoers().addClass('highlighted');
      nodeElem.incomers().addClass('highlighted');
    },

    viewCode(node) {
      window.location.href = `/ui/code/search?chunk_id=${node.chunk_id}`;
    },

    findPath(node) {
      this.pathFrom = node;
      this.pathFinderOpen = true;
    },

    async findShortestPath() {
      const response = await fetch(
        `/v1/code/graph/path?source=${this.pathFrom.id}&target=${this.pathTo}`
      );
      const data = await response.json();
      this.pathResult = data.path;

      // Highlight path in graph
      this.cy.elements().removeClass('highlighted');
      data.path.forEach(step => {
        this.cy.getElementById(step.id).addClass('highlighted');
      });
    },

    getCytoscapeStyle() {
      return [
        {
          selector: 'node',
          style: {
            'background-color': '#1a1f3a',
            'border-color': '#00d4ff',
            'border-width': 2,
            'label': 'data(label)',
            'color': '#e0e0e0',
            'text-valign': 'center',
            'font-family': 'SF Mono, monospace',
            'font-size': '12px'
          }
        },
        {
          selector: 'node[node_type="function"]',
          style: {
            'shape': 'roundrectangle',
            'background-color': '#00d4ff20'
          }
        },
        {
          selector: 'node[node_type="class"]',
          style: {
            'shape': 'rectangle',
            'background-color': '#00ff8820'
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#00ff88',
            'border-width': 4,
            'background-color': '#00ff8840'
          }
        },
        {
          selector: 'node.high-complexity',
          style: {
            'border-color': '#ff4466',
            'background-color': '#ff446620'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#00d4ff40',
            'target-arrow-color': '#00d4ff40',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier'
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#00ff88',
            'target-arrow-color': '#00ff88',
            'width': 4
          }
        }
      ];
    }
  };
}
</script>
```

### 3. Code Analytics - NOUVEAU

**Objectif** : Métriques de qualité, tendances, hotspots

**Features** :
- Complexity distribution (histogram)
- Code hotspots (heatmap par fichier)
- Dependency graph metrics (centrality, betweenness)
- Code churn (si commits trackés)
- Language breakdown (pie chart)
- LOC trends over time

```html
<!-- templates/code_analytics.html -->
<div class="analytics-container" x-data="codeAnalytics()">
  <h1>Code Analytics</h1>

  <div class="analytics-filters">
    <select x-model="repository" @change="loadAnalytics()" class="input-scada">
      <option value="">All Repositories</option>
      <template x-for="repo in repositories" :key="repo">
        <option :value="repo" x-text="repo"></option>
      </template>
    </select>

    <select x-model="timeRange" @change="loadAnalytics()" class="input-scada">
      <option value="7d">Last 7 days</option>
      <option value="30d">Last 30 days</option>
      <option value="90d">Last 90 days</option>
      <option value="all">All time</option>
    </select>
  </div>

  <div class="analytics-grid">
    <!-- Complexity Distribution -->
    <div class="analytics-card card-scada">
      <h3>Complexity Distribution</h3>
      <canvas id="complexity-histogram"></canvas>
      <div class="analytics-summary">
        <span>Avg: <strong x-text="stats.avgComplexity"></strong></span>
        <span>Max: <strong x-text="stats.maxComplexity"></strong></span>
        <span>High (>10): <strong x-text="stats.highComplexityCount"></strong></span>
      </div>
    </div>

    <!-- Code Hotspots -->
    <div class="analytics-card card-scada large">
      <h3>Code Hotspots (by file)</h3>
      <div id="hotspots-heatmap"></div> <!-- ECharts Treemap -->
    </div>

    <!-- Language Breakdown -->
    <div class="analytics-card card-scada">
      <h3>Language Breakdown</h3>
      <canvas id="language-pie"></canvas>
    </div>

    <!-- Top 10 Most Complex Functions -->
    <div class="analytics-card card-scada">
      <h3>Top 10 Most Complex</h3>
      <table class="table-scada">
        <thead>
          <tr>
            <th>Function</th>
            <th>File</th>
            <th>Complexity</th>
          </tr>
        </thead>
        <tbody>
          <template x-for="item in topComplex" :key="item.id">
            <tr @click="viewCode(item)" style="cursor: pointer;">
              <td x-text="item.name"></td>
              <td x-text="item.file_path"></td>
              <td>
                <span class="complexity-badge"
                      :class="getComplexityClass(item.complexity)"
                      x-text="item.complexity">
                </span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Dependency Metrics -->
    <div class="analytics-card card-scada">
      <h3>Dependency Metrics</h3>
      <div class="metrics-list">
        <div class="metric-item">
          <span class="metric-label">Total Nodes:</span>
          <span class="metric-value" x-text="graphMetrics.totalNodes"></span>
        </div>
        <div class="metric-item">
          <span class="metric-label">Total Edges:</span>
          <span class="metric-value" x-text="graphMetrics.totalEdges"></span>
        </div>
        <div class="metric-item">
          <span class="metric-label">Avg Degree:</span>
          <span class="metric-value" x-text="graphMetrics.avgDegree.toFixed(2)"></span>
        </div>
        <div class="metric-item">
          <span class="metric-label">Max Depth:</span>
          <span class="metric-value" x-text="graphMetrics.maxDepth"></span>
        </div>
      </div>
    </div>

    <!-- LOC Trends (if time-series data available) -->
    <div class="analytics-card card-scada large">
      <h3>Lines of Code Trend</h3>
      <div id="loc-timeline"></div> <!-- uPlot -->
    </div>
  </div>
</div>

<script>
function codeAnalytics() {
  return {
    repository: '',
    repositories: [],
    timeRange: '30d',
    stats: {},
    topComplex: [],
    graphMetrics: {},

    async init() {
      await this.loadRepositories();
      await this.loadAnalytics();
    },

    async loadRepositories() {
      const response = await fetch('/v1/code/repositories');
      this.repositories = await response.json();
    },

    async loadAnalytics() {
      const params = new URLSearchParams({
        repository: this.repository,
        time_range: this.timeRange
      });

      const response = await fetch(`/v1/code/analytics?${params}`);
      const data = await response.json();

      this.stats = data.stats;
      this.topComplex = data.top_complex;
      this.graphMetrics = data.graph_metrics;

      this.renderCharts(data);
    },

    renderCharts(data) {
      // Complexity Histogram
      new Chart(document.getElementById('complexity-histogram'), {
        type: 'bar',
        data: {
          labels: data.complexity_bins.labels,
          datasets: [{
            label: 'Functions',
            data: data.complexity_bins.counts,
            backgroundColor: 'rgba(0, 212, 255, 0.3)',
            borderColor: 'rgba(0, 212, 255, 1)',
            borderWidth: 1
          }]
        },
        options: {
          // Chart.js options...
        }
      });

      // Hotspots Heatmap (ECharts Treemap)
      const hotspotsChart = echarts.init(document.getElementById('hotspots-heatmap'));
      hotspotsChart.setOption({
        series: [{
          type: 'treemap',
          data: data.hotspots.map(h => ({
            name: h.file_path,
            value: h.complexity * h.loc,
            itemStyle: {
              color: this.getHeatmapColor(h.complexity)
            }
          }))
        }]
      });

      // Language Pie
      new Chart(document.getElementById('language-pie'), {
        type: 'doughnut',
        data: {
          labels: data.languages.map(l => l.language),
          datasets: [{
            data: data.languages.map(l => l.count),
            backgroundColor: [
              'rgba(0, 212, 255, 0.5)',
              'rgba(0, 255, 136, 0.5)',
              'rgba(255, 68, 102, 0.5)',
              'rgba(255, 204, 0, 0.5)'
            ]
          }]
        }
      });

      // LOC Timeline (uPlot)
      if (data.loc_trend) {
        new uPlot(/* uPlot config */, data.loc_trend, document.getElementById('loc-timeline'));
      }
    },

    getComplexityClass(complexity) {
      if (complexity < 5) return 'low';
      if (complexity < 10) return 'medium';
      return 'high';
    },

    getHeatmapColor(complexity) {
      if (complexity < 5) return '#00d4ff';
      if (complexity < 10) return '#ffcc00';
      return '#ff4466';
    },

    viewCode(item) {
      window.location.href = `/ui/code/search?chunk_id=${item.id}`;
    }
  };
}
</script>
```

---

## 📅 Events System - Refonte

### 1. Events Timeline - NOUVEAU (uPlot)

**Objectif** : Visualiser 50k-500k événements de manière performante

**Features** :
- Timeline haute performance (uPlot)
- Scrubber (zoom + pan)
- Filtres temporels (date range picker)
- Event density heatmap
- Drill-down (click pour détails)

```html
<!-- templates/events_timeline.html -->
<div class="timeline-container" x-data="eventsTimeline()">
  <h1>Events Timeline</h1>

  <!-- Controls -->
  <div class="timeline-controls">
    <div class="time-range-picker">
      <input type="date" x-model="startDate" @change="loadEvents()" class="input-scada">
      <span>to</span>
      <input type="date" x-model="endDate" @change="loadEvents()" class="input-scada">
    </div>

    <div class="quick-filters">
      <button @click="setRange('1h')" class="btn-scada-small">Last Hour</button>
      <button @click="setRange('24h')" class="btn-scada-small">Last 24h</button>
      <button @click="setRange('7d')" class="btn-scada-small">Last 7d</button>
      <button @click="setRange('30d')" class="btn-scada-small">Last 30d</button>
    </div>

    <div class="view-options">
      <label>
        <input type="checkbox" x-model="showDensity"> Show Density Heatmap
      </label>
      <label>
        <input type="checkbox" x-model="showAggregated"> Aggregate by Hour
      </label>
    </div>
  </div>

  <!-- Timeline Chart (uPlot) -->
  <div class="timeline-chart card-scada">
    <div id="events-timeline-chart"></div>
    <div class="timeline-legend">
      <span><span class="legend-color" style="background: #00d4ff;"></span> Event Count</span>
    </div>
  </div>

  <!-- Density Heatmap (ECharts) -->
  <div x-show="showDensity" class="density-heatmap card-scada">
    <h3>Event Density (by hour & day)</h3>
    <div id="density-heatmap"></div>
  </div>

  <!-- Event List (for selected time range) -->
  <div class="events-list card-scada">
    <h3>Events in Selected Range (<span x-text="selectedEvents.length"></span>)</h3>

    <div class="events-table-wrapper">
      <table class="table-scada">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Content</th>
            <th>Metadata</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <template x-for="event in paginatedEvents" :key="event.id">
            <tr @click="selectEvent(event)">
              <td x-text="formatTimestamp(event.timestamp)"></td>
              <td x-text="event.content.slice(0, 100) + '...'"></td>
              <td>
                <template x-for="(value, key) in event.metadata" :key="key">
                  <span class="badge-scada" x-text="`${key}: ${value}`"></span>
                </template>
              </td>
              <td>
                <button @click.stop="viewDetails(event)" class="btn-scada-small">Details</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination">
      <button @click="prevPage()" :disabled="currentPage === 1" class="btn-scada">Previous</button>
      <span x-text="`Page ${currentPage} of ${totalPages}`"></span>
      <button @click="nextPage()" :disabled="currentPage === totalPages" class="btn-scada">Next</button>
    </div>
  </div>

  <!-- Event Details Modal -->
  <div x-show="selectedEvent" class="modal-overlay" @click.self="selectedEvent = null">
    <div class="modal-content card-scada">
      <div class="modal-header">
        <h2>Event Details</h2>
        <button @click="selectedEvent = null" class="btn-close">✕</button>
      </div>

      <div class="modal-body">
        <div class="detail-row">
          <span class="label">ID:</span>
          <span x-text="selectedEvent?.id"></span>
        </div>
        <div class="detail-row">
          <span class="label">Timestamp:</span>
          <span x-text="formatTimestamp(selectedEvent?.timestamp)"></span>
        </div>
        <div class="detail-row">
          <span class="label">Content:</span>
          <pre x-text="selectedEvent?.content"></pre>
        </div>
        <div class="detail-row">
          <span class="label">Metadata:</span>
          <pre x-text="JSON.stringify(selectedEvent?.metadata, null, 2)"></pre>
        </div>
      </div>

      <div class="modal-actions">
        <button @click="findSimilar(selectedEvent)" class="btn-scada">Find Similar</button>
        <button @click="copyEvent(selectedEvent)" class="btn-scada">Copy JSON</button>
      </div>
    </div>
  </div>
</div>

<script>
function eventsTimeline() {
  return {
    plot: null,
    startDate: null,
    endDate: null,
    showDensity: false,
    showAggregated: true,
    selectedEvents: [],
    selectedEvent: null,
    currentPage: 1,
    pageSize: 50,

    async init() {
      // Default to last 24h
      this.setRange('24h');
      await this.loadEvents();
    },

    setRange(range) {
      const now = new Date();
      this.endDate = now.toISOString().split('T')[0];

      const start = new Date(now);
      switch (range) {
        case '1h': start.setHours(start.getHours() - 1); break;
        case '24h': start.setDate(start.getDate() - 1); break;
        case '7d': start.setDate(start.getDate() - 7); break;
        case '30d': start.setDate(start.getDate() - 30); break;
      }
      this.startDate = start.toISOString().split('T')[0];

      this.loadEvents();
    },

    async loadEvents() {
      const response = await fetch(
        `/v1/events/timeline?start=${this.startDate}&end=${this.endDate}&aggregate=${this.showAggregated}`
      );
      const data = await response.json();

      this.renderTimeline(data.timeline);
      this.selectedEvents = data.events;

      if (this.showDensity) {
        this.renderDensityHeatmap(data.density);
      }
    },

    renderTimeline(data) {
      const opts = {
        width: 1200,
        height: 400,
        series: [
          {},
          {
            label: 'Events',
            stroke: '#00d4ff',
            width: 2,
            fill: 'rgba(0, 212, 255, 0.1)'
          }
        ],
        axes: [
          {},
          {
            label: 'Count',
            labelSize: 20
          }
        ],
        scales: {
          x: {
            time: true
          }
        },
        hooks: {
          setSelect: [
            (self) => {
              const min = self.scales.x.min;
              const max = self.scales.x.max;
              this.onTimeRangeSelected(min, max);
            }
          ]
        }
      };

      if (this.plot) {
        this.plot.setData([data.timestamps, data.counts]);
      } else {
        this.plot = new uPlot(opts, [data.timestamps, data.counts], document.getElementById('events-timeline-chart'));
      }
    },

    renderDensityHeatmap(data) {
      const chart = echarts.init(document.getElementById('density-heatmap'));
      chart.setOption({
        tooltip: {
          position: 'top'
        },
        grid: {
          height: '50%',
          top: '10%'
        },
        xAxis: {
          type: 'category',
          data: data.hours, // 0-23
          splitArea: {
            show: true
          }
        },
        yAxis: {
          type: 'category',
          data: data.days // Mon-Sun
        },
        visualMap: {
          min: 0,
          max: data.max,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: '15%',
          inRange: {
            color: ['#0a0e27', '#00d4ff', '#00ff88']
          }
        },
        series: [{
          name: 'Event Count',
          type: 'heatmap',
          data: data.matrix,
          label: {
            show: true
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 212, 255, 0.5)'
            }
          }
        }]
      });
    },

    onTimeRangeSelected(min, max) {
      // Filter selectedEvents by time range
      this.selectedEvents = this.selectedEvents.filter(e => {
        const ts = new Date(e.timestamp).getTime();
        return ts >= min * 1000 && ts <= max * 1000;
      });
      this.currentPage = 1;
    },

    get paginatedEvents() {
      const start = (this.currentPage - 1) * this.pageSize;
      return this.selectedEvents.slice(start, start + this.pageSize);
    },

    get totalPages() {
      return Math.ceil(this.selectedEvents.length / this.pageSize);
    },

    prevPage() {
      if (this.currentPage > 1) this.currentPage--;
    },

    nextPage() {
      if (this.currentPage < this.totalPages) this.currentPage++;
    },

    selectEvent(event) {
      this.selectedEvent = event;
    },

    viewDetails(event) {
      this.selectedEvent = event;
    },

    async findSimilar(event) {
      window.location.href = `/ui/events/search?similar_to=${event.id}`;
    },

    copyEvent(event) {
      navigator.clipboard.writeText(JSON.stringify(event, null, 2));
    },

    formatTimestamp(ts) {
      return new Date(ts).toLocaleString();
    }
  };
}
</script>
```

### 2. Events Search - Améliorations

**Similar to Code Search** :
- Filtres avancés (date range, metadata filters)
- Preview
- Drill-down
- Export (JSON, CSV)

---

## 🔍 Observability Dashboard - Améliorations (EPIC-20+)

**Intégration avec EPIC-20 MVP** :

### Ajouts proposés au-delà du MVP

**1. Heat Maps (ECharts)** :
```html
<!-- Hot Endpoints Heatmap -->
<div class="heatmap-card card-scada">
  <h3>API Endpoints Heatmap (by hour)</h3>
  <div id="endpoints-heatmap"></div>
</div>

<script>
// ECharts heatmap pour visualiser les endpoints les plus appelés par heure
const endpointsChart = echarts.init(document.getElementById('endpoints-heatmap'));
endpointsChart.setOption({
  xAxis: {
    type: 'category',
    data: hours // 0-23
  },
  yAxis: {
    type: 'category',
    data: endpoints // ['/v1/search', '/v1/code/search', ...]
  },
  visualMap: {
    min: 0,
    max: maxCalls,
    inRange: {
      color: ['#0a0e27', '#ffcc00', '#ff4466'] // Cold to hot
    }
  },
  series: [{
    type: 'heatmap',
    data: heatmapData // [[hour, endpoint_index, call_count], ...]
  }]
});
</script>
```

**2. Correlation Charts** :
```html
<!-- Error Rate vs Latency Correlation -->
<div class="correlation-card card-scada">
  <h3>Error Rate vs Latency</h3>
  <canvas id="correlation-chart"></canvas>
</div>

<script>
// Scatter plot pour visualiser corrélation
new Chart(document.getElementById('correlation-chart'), {
  type: 'scatter',
  data: {
    datasets: [{
      label: 'Requests',
      data: dataPoints.map(d => ({ x: d.latency, y: d.error_rate })),
      backgroundColor: 'rgba(0, 212, 255, 0.5)'
    }]
  },
  options: {
    scales: {
      x: { title: { display: true, text: 'Latency (ms)' } },
      y: { title: { display: true, text: 'Error Rate (%)' } }
    }
  }
});
</script>
```

**3. Alerting Visuel** :
```html
<!-- Alerts Panel -->
<div class="alerts-panel" x-data="alerts()">
  <template x-for="alert in activeAlerts" :key="alert.id">
    <div class="alert-card" :class="`alert-${alert.severity}`">
      <span class="alert-icon" x-text="getAlertIcon(alert.severity)"></span>
      <div class="alert-content">
        <h4 x-text="alert.title"></h4>
        <p x-text="alert.message"></p>
        <span class="alert-time" x-text="formatTime(alert.timestamp)"></span>
      </div>
      <button @click="dismissAlert(alert)" class="btn-dismiss">✕</button>
    </div>
  </template>
</div>

<style>
.alert-card {
  border-left: 4px solid;
  padding: 1rem;
  margin-bottom: 0.5rem;
  animation: slideIn 0.3s ease;
}

.alert-critical {
  border-color: #ff4466;
  background: rgba(255, 68, 102, 0.1);
}

.alert-warning {
  border-color: #ffcc00;
  background: rgba(255, 204, 0, 0.1);
}

.alert-info {
  border-color: #00d4ff;
  background: rgba(0, 212, 255, 0.1);
}

@keyframes slideIn {
  from {
    transform: translateX(-100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>

<script>
function alerts() {
  return {
    activeAlerts: [],

    init() {
      // SSE pour alerts en temps réel
      const evtSource = new EventSource('/api/ui/alerts/stream');
      evtSource.addEventListener('alert', (e) => {
        const alert = JSON.parse(e.data);
        this.activeAlerts.unshift(alert);

        // Auto-dismiss after 10s (info only)
        if (alert.severity === 'info') {
          setTimeout(() => this.dismissAlert(alert), 10000);
        }
      });
    },

    dismissAlert(alert) {
      this.activeAlerts = this.activeAlerts.filter(a => a.id !== alert.id);
    },

    getAlertIcon(severity) {
      switch (severity) {
        case 'critical': return '🔴';
        case 'warning': return '⚠️';
        case 'info': return 'ℹ️';
      }
    },

    formatTime(ts) {
      return new Date(ts).toLocaleTimeString();
    }
  };
}
</script>
```

---

## 🎨 Composants Réutilisables

### Component Library (SCADA-themed)

**Créer un fichier** : `static/js/components/scada-components.js`

```javascript
// SCADA Component Library for MnemoLite
// Alpine.js components

// KPI Card
Alpine.data('kpiCard', (config) => ({
  value: config.value || 0,
  label: config.label || '',
  trend: config.trend || 0,
  icon: config.icon || '📊',

  get trendClass() {
    return this.trend > 0 ? 'trend-up' : 'trend-down';
  },

  get trendIcon() {
    return this.trend > 0 ? '↑' : '↓';
  }
}));

// Chart Card with Auto-refresh
Alpine.data('chartCard', (config) => ({
  chart: null,
  refreshInterval: config.refreshInterval || 5000,
  endpoint: config.endpoint,

  init() {
    this.loadData();
    setInterval(() => this.loadData(), this.refreshInterval);
  },

  async loadData() {
    const response = await fetch(this.endpoint);
    const data = await response.json();
    this.renderChart(data);
  },

  renderChart(data) {
    if (!this.chart) {
      this.chart = new Chart(this.$refs.canvas, config.chartConfig);
    }
    this.chart.data = data;
    this.chart.update();
  }
}));

// Modal
Alpine.data('modal', () => ({
  open: false,

  show() {
    this.open = true;
    document.body.style.overflow = 'hidden';
  },

  hide() {
    this.open = false;
    document.body.style.overflow = '';
  }
}));

// Dropdown
Alpine.data('dropdown', () => ({
  open: false,

  toggle() {
    this.open = !this.open;
  },

  close() {
    this.open = false;
  }
}));

// Toast Notification
Alpine.store('toasts', {
  items: [],

  show(message, type = 'info', duration = 3000) {
    const id = Date.now();
    this.items.push({ id, message, type });

    setTimeout(() => {
      this.items = this.items.filter(t => t.id !== id);
    }, duration);
  },

  success(message) {
    this.show(message, 'success');
  },

  error(message) {
    this.show(message, 'error');
  },

  warning(message) {
    this.show(message, 'warning');
  }
});

// Tooltip
Alpine.directive('tooltip', (el, { expression }, { evaluate }) => {
  const content = evaluate(expression);

  el.addEventListener('mouseenter', () => {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip-scada';
    tooltip.textContent = content;
    document.body.appendChild(tooltip);

    const rect = el.getBoundingClientRect();
    tooltip.style.top = `${rect.top - tooltip.offsetHeight - 5}px`;
    tooltip.style.left = `${rect.left + rect.width / 2 - tooltip.offsetWidth / 2}px`;

    el._tooltip = tooltip;
  });

  el.addEventListener('mouseleave', () => {
    if (el._tooltip) {
      el._tooltip.remove();
      delete el._tooltip;
    }
  });
});

// Loading Skeleton
Alpine.data('skeleton', () => ({
  loading: true,

  async load(fetchFn) {
    this.loading = true;
    try {
      await fetchFn();
    } finally {
      this.loading = false;
    }
  }
}));
```

**Usage** :
```html
<!-- KPI Card Component -->
<div x-data="kpiCard({ value: 12345, label: 'Events', trend: 10, icon: '📅' })">
  <div class="kpi-card card-scada">
    <div class="kpi-icon" x-text="icon"></div>
    <div class="kpi-value" x-text="value"></div>
    <div class="kpi-label" x-text="label"></div>
    <div class="kpi-trend" :class="trendClass">
      <span x-text="trendIcon"></span>
      <span x-text="`${Math.abs(trend)}%`"></span>
    </div>
  </div>
</div>

<!-- Chart Card with Auto-refresh -->
<div x-data="chartCard({ endpoint: '/api/ui/metrics', refreshInterval: 5000, chartConfig: {...} })">
  <div class="chart-card card-scada">
    <h3>API Latency</h3>
    <canvas x-ref="canvas"></canvas>
  </div>
</div>

<!-- Toast Notifications -->
<div class="toasts-container">
  <template x-for="toast in $store.toasts.items" :key="toast.id">
    <div class="toast" :class="`toast-${toast.type}`" x-text="toast.message"></div>
  </template>
</div>

<button @click="$store.toasts.success('Operation successful!')">Test Toast</button>

<!-- Tooltip -->
<span x-tooltip="'This is a helpful tooltip'">Hover me</span>

<!-- Loading Skeleton -->
<div x-data="skeleton()" x-init="load(() => fetchData())">
  <template x-if="loading">
    <div class="skeleton" style="width: 100%; height: 200px;"></div>
  </template>
  <template x-if="!loading">
    <div><!-- Actual content --></div>
  </template>
</div>
```

---

## 📦 Stack Technique Finale

### Dependencies à Ajouter

```json
{
  "dependencies": {
    "existing": {
      "htmx": "1.9.12",
      "chart.js": "4.4.0",
      "cytoscape.js": "3.28.0"
    },
    "new": {
      "alpine.js": "3.14.0",        // 15KB - Reactive UI
      "uplot": "1.6.30",              // 45KB - Timeline charts
      "apache-echarts": "5.5.0",      // 900KB - Advanced viz
      "prism.js": "1.29.0"            // 2KB core + languages - Syntax highlighting
    }
  }
}
```

**Total size** : ~1.3MB uncompressed (~400KB gzipped)

**CDN Links** :
```html
<!-- base.html -->
<!-- Alpine.js -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>

<!-- uPlot -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.min.css">
<script src="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.iife.min.js"></script>

<!-- Apache ECharts -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>

<!-- Prism.js -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-okaidia.min.css">
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-javascript.min.js"></script>
```

---

## 🚀 Plan d'Implémentation

### Phase 1: Fondations (2-3 jours)

**Tâches** :
1. Ajouter Alpine.js à `base.html`
2. Créer `scada-components.js` (component library)
3. Mettre à jour CSS avec nouvelles variables (gradients, borders, etc.)
4. Créer templates de base : KPI cards, chart cards, modals

**Livrables** :
- `static/js/components/scada-components.js`
- `static/css/scada_v2.css` (updated)
- `templates/components/` (reusable partials)

### Phase 2: Dashboard Général (2 jours)

**Tâches** :
1. Refonte `templates/dashboard.html` → `dashboard_v2.html`
2. Ajouter endpoints API pour KPIs : `/api/ui/kpis/{events,code,api,cache}`
3. Intégrer Chart.js + uPlot pour charts
4. SSE pour activity feed : `/api/ui/activity/stream`

**Livrables** :
- `templates/dashboard_v2.html`
- `api/routes/ui_routes.py` (endpoints KPIs)
- Real-time activity feed

### Phase 3: Code Intelligence (4-5 jours)

**Tâches** :
1. **Code Search v2** :
   - Filtres avancés (language, type, complexity, repo)
   - Preview avec Prism.js
   - Views: list, grid, tree
   - Modal pour full view
2. **Code Graph v2** :
   - Drill-down (click handlers)
   - Path highlighting
   - Filters (complexity, type)
   - Minimap
   - Layout switching
3. **Code Analytics** (NOUVEAU) :
   - Complexity histogram (Chart.js)
   - Hotspots heatmap (ECharts treemap)
   - Language breakdown (Chart.js pie)
   - Top 10 complex functions
   - Dependency metrics

**Livrables** :
- `templates/code_search_v2.html`
- `templates/code_graph_v2.html`
- `templates/code_analytics.html` (NEW)
- `api/routes/code_analytics.py` (NEW)
- `api/services/code_analytics_service.py` (NEW)

### Phase 4: Events System (3 jours)

**Tâches** :
1. **Events Timeline** :
   - uPlot timeline avec scrubber
   - Date range picker
   - Aggregation (by hour)
   - Density heatmap (ECharts)
2. **Events Search v2** :
   - Filtres avancés (similar to code search)
   - Preview
   - Export (JSON, CSV)

**Livrables** :
- `templates/events_timeline.html` (NEW)
- `templates/events_search_v2.html`
- `api/routes/events_routes.py` (updated)

### Phase 5: Observability Enhancements (2 jours)

**Tâches** :
1. Heat maps (endpoints heatmap)
2. Correlation charts (error vs latency)
3. Alerting visuel (SSE alerts)

**Livrables** :
- `templates/observability_v2.html`
- `api/routes/observability_routes.py` (updated)
- SSE endpoint: `/api/ui/alerts/stream`

### Phase 6: Polish & Testing (2 jours)

**Tâches** :
1. Responsive design (mobile-aware)
2. Animations & micro-interactions
3. Loading states & skeletons
4. Error handling & toast notifications
5. Documentation (usage guide)

**Livrables** :
- Updated CSS avec animations
- Documentation : `docs/UI_UX_GUIDE.md`

**Total : ~15-17 jours**

---

## 📊 Estimation de la Charge

| Phase | Jours | Points |
|-------|-------|--------|
| Phase 1: Fondations | 2-3 | 5 |
| Phase 2: Dashboard | 2 | 5 |
| Phase 3: Code Intel | 4-5 | 13 |
| Phase 4: Events | 3 | 8 |
| Phase 5: Observability | 2 | 5 |
| Phase 6: Polish | 2 | 3 |
| **Total** | **15-17** | **39 points** |

---

## 🎯 Priorités & YAGNI

### Must-Have (MVP)

1. ✅ Alpine.js integration (component library)
2. ✅ Dashboard v2 (KPIs, charts, activity feed)
3. ✅ Code Search v2 (filtres, preview, views)
4. ✅ Code Graph v2 (drill-down, filters, layouts)
5. ✅ Syntax highlighting (Prism.js)

### Should-Have (Post-MVP)

6. ✅ Events Timeline (uPlot)
7. ✅ Code Analytics (NEW)
8. ✅ Observability heat maps
9. ✅ Alerting visuel

### Nice-to-Have (Future)

10. ⏸️ Code churn analytics (requires git commit tracking)
11. ⏸️ AI-driven insights (anomaly detection)
12. ⏸️ Export to PDF/PNG (advanced)
13. ⏸️ Custom dashboards (user-configurable)

---

## 🔗 Liens & Références

### Documentation Interne

- EPIC-20: Observability (déjà brainstormed)
- EPIC-19: Load Testing (référence pour métriques)
- `docs/arch.md` : Architecture actuelle
- `CLAUDE.md` : §UI, §PRINCIPLES

### Librairies

- [Alpine.js Docs](https://alpinejs.dev/)
- [uPlot Docs](https://github.com/leeoniya/uPlot)
- [Apache ECharts Docs](https://echarts.apache.org/)
- [Prism.js Docs](https://prismjs.com/)
- [HTMX 2.0 Docs](https://htmx.org/)
- [Cytoscape.js Docs](https://js.cytoscape.org/)

### Design Inspiration

- SCADA HMI dashboards
- Grafana (metrics viz)
- Kibana (logs exploration)
- GitHub Code Search (filters, preview)
- Linear (modern UI patterns)

---

## 📝 Conclusion & Next Steps

### Résumé Exécutif

**Objectif atteint** : Plan complet pour moderniser l'UI/UX de MnemoLite tout en restant KISS et SCADA-themed.

**Stack technique** :
- HTMX 1.9 (déjà présent) + Alpine.js 3.x (15KB, reactive)
- Chart.js 4.4 (déjà présent) + uPlot 1.6 (45KB, timelines) + Apache ECharts 5.5 (900KB, advanced viz)
- Prism.js (2KB, syntax highlighting)
- **Total : ~1MB uncompressed, ~400KB gzipped**

**Features clés** :
1. Dashboard général refonte (KPIs, charts, real-time activity)
2. Code Search v2 (filtres avancés, preview, views)
3. Code Graph v2 (drill-down, filters, layouts, minimap)
4. Code Analytics (NEW : complexity, hotspots, trends)
5. Events Timeline (NEW : uPlot, scrubber, density heatmap)
6. Observability enhancements (heat maps, alerts, correlations)

**Estimation** : 15-17 jours, 39 points

**Philosophy** : EXTEND > REBUILD, SCADA aesthetic maintained, KISS approach

### Prochaines Étapes Recommandées

1. **Valider** : Review du plan avec l'équipe/user
2. **Prioriser** : Choisir MVP scope (Phases 1-3 recommandées)
3. **Prototyper** : Créer un prototype HTML statique pour valider l'UX
4. **Implémenter** : Suivre le plan phase par phase
5. **Tester** : User testing à chaque phase

### Questions Ouvertes

1. **Scope MVP** : Toutes les phases ou seulement 1-3 ?
2. **uPlot vs Chart.js** : Vaut-il la peine d'ajouter uPlot uniquement pour timelines ?
3. **ECharts** : 900KB est-il acceptable pour heat maps ? Alternatives ?
4. **Code Analytics** : Priorité haute ou post-MVP ?
5. **Mobile** : Quelle importance ? (actuellement desktop-first)

---

**Document créé** : 2025-10-23
**Version** : 1.0
**Statut** : BRAINSTORM / ULTRATHINK COMPLETE
**Auteur** : Claude Code (MnemoLite AI Assistant)

---

**Prêt à implémenter** ✅
