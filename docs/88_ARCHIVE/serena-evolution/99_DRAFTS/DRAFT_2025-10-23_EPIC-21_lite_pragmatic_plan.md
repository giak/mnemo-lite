# EPIC-21-LITE: UI/UX Pragmatic Enhancements

**Date**: 2025-10-23
**Status**: ✅ READY FOR IMPLEMENTATION
**Estimation**: 7-15 points (3-8 jours)
**Principe**: EXTEND > REBUILD, KISS, YAGNI

---

## 🎯 Vision

Améliorer **uniquement ce qui manque** à l'UI existante de MnemoLite, sans refaire ce qui fonctionne déjà (EPIC-14).

**Principes**:
- ✅ **EXTEND > REBUILD**: Améliorer l'existant, ne pas refaire
- ✅ **KISS**: Minimiser les dépendances (2-60KB vs 960KB proposé)
- ✅ **YAGNI**: Valider les besoins avant d'implémenter
- ✅ **DRY**: Ne pas dupliquer code_search, dashboard

---

## 📋 État des Lieux (Après Audit)

### ✅ Ce Qui Fonctionne Déjà (EPIC-14)

**Code Search**:
- ✅ 7 filtres avancés (language, type, return_type, param_type, repo, mode, limit)
- ✅ Card-based layout avec progressive disclosure
- ✅ Type badges color-coded (primitive=blue, complex=purple, etc.)
- ✅ LSP metadata (signatures, param types, docstrings)
- ✅ Copy-to-clipboard (shortcut: c)
- ✅ Keyboard navigation (j/k, Enter)
- ✅ Skeleton loading states
- ✅ Enhanced empty states
- ✅ Qualified names (name_path) - EPIC-11
- ✅ Performance metrics (execution time, fusion breakdown)

**Code Dashboard**:
- ✅ KPI cards (repos, files, functions, complexity)
- ✅ Chart.js 4.4.0 intégré
- ✅ SCADA theme (industrial, dark)

**Code Graph**:
- ✅ Cytoscape.js 3.28 intégré
- ✅ Repository selector
- ✅ Graph visualization (nodes, edges)

**Events System**:
- ✅ Dashboard avec KPIs
- ✅ Search avec filtres basiques
- ✅ Chart.js pour métriques

### ⚠️ Ce Qui Manque Vraiment

1. **Code Graph**: Pas d'interactivité (drill-down, path finder, filters)
2. **Syntax Highlighting**: Code brut sans coloration
3. **Events Timeline** (?)**: Timeline haute perf pour 50k+ events (besoin à valider)
4. **Alpine.js** (?)**: Interactions client simplifiées (besoin à valider)

---

## 🚀 Plan d'Implémentation

### Phase 1: Must-Have (7 points, 3-4 jours) ✅ APPROUVER

#### Story 21.1: Code Graph Interactivity (5 points, 2-3 jours)

**Objectif**: Ajouter drill-down, path finder, et filters au code graph existant

**Features**:
1. **Click handlers**: Click sur node → afficher panel de détails
2. **Path finder**: Trouver shortest path entre 2 nodes
3. **Filters**: Par complexity, par type (function/class/method)
4. **Layout switching**: Force-directed, hierarchical, circular

**Implémentation**:

**1.1 Modifier `static/js/components/code_graph.js`**:

```javascript
// Ajouter après l'initialisation de Cytoscape

// ========================================
// 1. Click handlers pour drill-down
// ========================================
cy.on('tap', 'node', function(evt) {
  const node = evt.target;
  const data = node.data();

  showNodeDetailsPanel(data);

  // Highlight connected nodes
  cy.elements().removeClass('highlighted');
  node.addClass('highlighted');
  node.neighborhood().addClass('highlighted');
});

function showNodeDetailsPanel(nodeData) {
  const panel = document.getElementById('node-details-panel');
  const panelContent = document.getElementById('node-details-content');

  panelContent.innerHTML = `
    <div class="detail-header">
      <h3>${nodeData.label}</h3>
      <span class="badge">${nodeData.node_type}</span>
    </div>
    <div class="detail-body">
      <div class="detail-row">
        <span class="label">File:</span>
        <span class="value">${nodeData.file_path || 'N/A'}</span>
      </div>
      <div class="detail-row">
        <span class="label">Complexity:</span>
        <span class="value">${nodeData.complexity || 'N/A'}</span>
      </div>
      <div class="detail-row">
        <span class="label">Outgoing Calls:</span>
        <span class="value">${nodeData.outgoing_count || 0}</span>
      </div>
      <div class="detail-row">
        <span class="label">Incoming Calls:</span>
        <span class="value">${nodeData.incoming_count || 0}</span>
      </div>
    </div>
    <div class="detail-actions">
      <button class="btn btn-primary" onclick="viewCode('${nodeData.chunk_id}')">View Code</button>
      <button class="btn btn-secondary" onclick="openPathFinder('${nodeData.id}')">Find Path</button>
    </div>
  `;

  panel.hidden = false;
}

function viewCode(chunkId) {
  window.location.href = `/ui/code/search?chunk_id=${chunkId}`;
}

// ========================================
// 2. Path Finder
// ========================================
let pathFinderSourceId = null;

function openPathFinder(nodeId) {
  pathFinderSourceId = nodeId;

  const modal = document.getElementById('path-finder-modal');
  const sourceLabel = cy.getElementById(nodeId).data('label');

  document.getElementById('path-source-label').textContent = sourceLabel;

  // Populate target select
  const targetSelect = document.getElementById('path-target-select');
  targetSelect.innerHTML = '<option value="">Select target node...</option>';

  cy.nodes().forEach(node => {
    if (node.id() !== nodeId) {
      const option = document.createElement('option');
      option.value = node.id();
      option.textContent = node.data('label');
      targetSelect.appendChild(option);
    }
  });

  modal.hidden = false;
}

async function findPath() {
  const targetId = document.getElementById('path-target-select').value;
  if (!targetId) {
    alert('Please select a target node');
    return;
  }

  const repository = document.getElementById('repository-select').value;

  try {
    const response = await fetch(
      `/v1/code/graph/path?repository=${repository}&source=${pathFinderSourceId}&target=${targetId}`
    );
    const data = await response.json();

    if (data.path && data.path.length > 0) {
      highlightPath(data.path);
      displayPathResult(data.path);
    } else {
      alert('No path found between these nodes');
    }
  } catch (error) {
    console.error('Error finding path:', error);
    alert('Error finding path');
  }
}

function highlightPath(path) {
  // Remove existing highlights
  cy.elements().removeClass('highlighted path-node path-edge');

  // Highlight nodes in path
  path.forEach(nodeId => {
    cy.getElementById(nodeId).addClass('highlighted path-node');
  });

  // Highlight edges in path
  for (let i = 0; i < path.length - 1; i++) {
    const source = cy.getElementById(path[i]);
    const target = cy.getElementById(path[i + 1]);

    source.edgesTo(target).addClass('highlighted path-edge');
  }

  // Fit view to path
  const pathElements = cy.elements('.highlighted');
  cy.fit(pathElements, 50); // 50px padding
}

function displayPathResult(path) {
  const resultDiv = document.getElementById('path-result');

  resultDiv.innerHTML = `
    <h4>Path Found (${path.length} steps):</h4>
    <ol>
      ${path.map(nodeId => {
        const node = cy.getElementById(nodeId);
        return `<li>${node.data('label')} <span class="badge">${node.data('node_type')}</span></li>`;
      }).join('')}
    </ol>
  `;

  resultDiv.hidden = false;
}

function closePathFinderModal() {
  document.getElementById('path-finder-modal').hidden = true;
  document.getElementById('path-result').hidden = true;
}

// ========================================
// 3. Filters par Complexity et Type
// ========================================
function filterByComplexity(threshold) {
  cy.batch(() => {
    cy.nodes().forEach(node => {
      const complexity = node.data('complexity') || 0;

      if (complexity >= threshold) {
        node.show();
        node.removeClass('filtered-out');

        if (complexity >= 10) {
          node.addClass('high-complexity');
        } else {
          node.removeClass('high-complexity');
        }
      } else {
        node.hide();
        node.addClass('filtered-out');
      }
    });

    // Hide edges where both nodes are hidden
    cy.edges().forEach(edge => {
      if (edge.source().hidden() || edge.target().hidden()) {
        edge.hide();
      } else {
        edge.show();
      }
    });
  });

  document.getElementById('complexity-value').textContent = threshold;
}

function filterByType(type, show) {
  cy.batch(() => {
    cy.nodes().forEach(node => {
      if (node.data('node_type') === type) {
        if (show) {
          node.show();
          node.removeClass('filtered-out');
        } else {
          node.hide();
          node.addClass('filtered-out');
        }
      }
    });

    // Update edges visibility
    cy.edges().forEach(edge => {
      if (edge.source().hidden() || edge.target().hidden()) {
        edge.hide();
      } else {
        edge.show();
      }
    });
  });
}

function resetFilters() {
  cy.elements().show();
  cy.elements().removeClass('filtered-out high-complexity');

  document.getElementById('complexity-slider').value = 0;
  document.getElementById('complexity-value').textContent = '0';

  document.getElementById('filter-function').checked = true;
  document.getElementById('filter-class').checked = true;
  document.getElementById('filter-method').checked = true;
}

// ========================================
// 4. Layout Switching
// ========================================
function changeLayout(layoutName) {
  const layouts = {
    'cose': {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20,
      refresh: 20,
      fit: true,
      padding: 30,
      randomize: false,
      componentSpacing: 100,
      nodeRepulsion: 400000,
      edgeElasticity: 100,
      nestingFactor: 5,
      gravity: 80,
      numIter: 1000,
      initialTemp: 200,
      coolingFactor: 0.95,
      minTemp: 1.0
    },
    'breadthfirst': {
      name: 'breadthfirst',
      directed: true,
      padding: 30,
      spacingFactor: 1.5
    },
    'circle': {
      name: 'circle',
      padding: 30,
      radius: 300,
      startAngle: 0,
      sweep: undefined,
      clockwise: true,
      sort: undefined,
      animate: true,
      animationDuration: 500
    },
    'grid': {
      name: 'grid',
      padding: 30,
      rows: undefined,
      cols: undefined,
      position: function(node) {},
      sort: undefined,
      animate: true,
      animationDuration: 500
    },
    'concentric': {
      name: 'concentric',
      padding: 30,
      startAngle: 3 / 2 * Math.PI,
      sweep: undefined,
      clockwise: true,
      equidistant: false,
      minNodeSpacing: 10,
      concentric: function(node) {
        return node.degree();
      },
      levelWidth: function(nodes) {
        return 2;
      },
      animate: true,
      animationDuration: 500
    }
  };

  const layout = cy.layout(layouts[layoutName]);
  layout.run();
}

// ========================================
// 5. Zoom & Reset View
// ========================================
function resetView() {
  cy.fit(cy.elements(), 30); // 30px padding
  cy.center();
}

function zoomIn() {
  cy.zoom(cy.zoom() * 1.2);
  cy.center();
}

function zoomOut() {
  cy.zoom(cy.zoom() * 0.8);
  cy.center();
}
```

**1.2 Modifier `templates/code_graph.html`**:

```html
<!-- Ajouter après le graph container -->

<!-- Toolbar (au-dessus du graph) -->
<div class="graph-toolbar">
  <!-- Layout Selector -->
  <div class="toolbar-group">
    <label>Layout</label>
    <select id="layout-select" class="filter-select" onchange="changeLayout(this.value)">
      <option value="cose" selected>Force-Directed</option>
      <option value="breadthfirst">Hierarchical</option>
      <option value="circle">Circular</option>
      <option value="grid">Grid</option>
      <option value="concentric">Concentric</option>
    </select>
  </div>

  <!-- Complexity Filter -->
  <div class="toolbar-group">
    <label>Complexity ≥ <span id="complexity-value">0</span></label>
    <input type="range"
           id="complexity-slider"
           min="0"
           max="20"
           value="0"
           oninput="filterByComplexity(this.value)">
  </div>

  <!-- Type Filters -->
  <div class="toolbar-group">
    <label>Type Filters</label>
    <label class="checkbox-label">
      <input type="checkbox" id="filter-function" checked
             onchange="filterByType('function', this.checked)">
      <span>Function</span>
    </label>
    <label class="checkbox-label">
      <input type="checkbox" id="filter-class" checked
             onchange="filterByType('class', this.checked)">
      <span>Class</span>
    </label>
    <label class="checkbox-label">
      <input type="checkbox" id="filter-method" checked
             onchange="filterByType('method', this.checked)">
      <span>Method</span>
    </label>
  </div>

  <!-- Actions -->
  <div class="toolbar-group">
    <button class="btn btn-secondary" onclick="resetFilters()">Reset Filters</button>
    <button class="btn btn-secondary" onclick="resetView()">Reset View</button>
    <button class="btn btn-secondary" onclick="zoomIn()">Zoom In</button>
    <button class="btn btn-secondary" onclick="zoomOut()">Zoom Out</button>
  </div>
</div>

<!-- Node Details Panel (side panel, initially hidden) -->
<div id="node-details-panel" class="side-panel" hidden>
  <div class="side-panel-header">
    <h2>Node Details</h2>
    <button class="btn-close" onclick="document.getElementById('node-details-panel').hidden = true">✕</button>
  </div>
  <div id="node-details-content" class="side-panel-content">
    <!-- Populated by JS -->
  </div>
</div>

<!-- Path Finder Modal -->
<div id="path-finder-modal" class="modal" hidden>
  <div class="modal-content">
    <div class="modal-header">
      <h2>Find Path</h2>
      <button class="btn-close" onclick="closePathFinderModal()">✕</button>
    </div>
    <div class="modal-body">
      <p>From: <strong id="path-source-label"></strong></p>

      <label for="path-target-select">To:</label>
      <select id="path-target-select" class="filter-select">
        <option value="">Select target node...</option>
      </select>

      <button class="btn btn-primary" onclick="findPath()">Find Path</button>

      <div id="path-result" hidden></div>
    </div>
  </div>
</div>

<style>
/* ========================================
   Graph Toolbar
   ======================================== */
.graph-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  margin-bottom: 16px;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-group label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 600;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
}

/* ========================================
   Side Panel (Node Details)
   ======================================== */
.side-panel {
  position: fixed;
  right: 0;
  top: 120px;
  width: 350px;
  max-height: calc(100vh - 140px);
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  border-right: none;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.3);
  overflow-y: auto;
  z-index: 100;
}

.side-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.side-panel-header h2 {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}

.side-panel-content {
  padding: 16px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.detail-header h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.detail-body {
  margin-bottom: 16px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-subtle);
  font-size: 12px;
}

.detail-row .label {
  color: var(--color-text-tertiary);
  font-weight: 600;
}

.detail-row .value {
  color: var(--color-text-primary);
  font-family: var(--font-mono);
}

.detail-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ========================================
   Modal (Path Finder)
   ======================================== */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 200;
}

.modal-content {
  width: 500px;
  max-height: 80vh;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}

.modal-body {
  padding: 16px;
}

.modal-body label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-tertiary);
}

.modal-body select {
  width: 100%;
  margin-bottom: 16px;
}

#path-result {
  margin-top: 16px;
  padding: 16px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
}

#path-result h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

#path-result ol {
  margin: 0;
  padding-left: 20px;
}

#path-result li {
  padding: 4px 0;
  font-size: 12px;
  font-family: var(--font-mono);
}

/* ========================================
   Cytoscape Styles (Updated)
   ======================================== */
.cy-node.highlighted {
  border-color: #00ff88 !important;
  border-width: 4px !important;
}

.cy-node.path-node {
  background-color: rgba(0, 255, 136, 0.3) !important;
}

.cy-edge.path-edge {
  line-color: #00ff88 !important;
  target-arrow-color: #00ff88 !important;
  width: 4px !important;
}

.cy-node.high-complexity {
  border-color: #ff4466 !important;
  background-color: rgba(255, 68, 102, 0.2) !important;
}
</style>
```

**1.3 Backend: Vérifier endpoint `/v1/code/graph/path`**

L'endpoint devrait déjà exister (à vérifier dans `api/routes/code_graph_routes.py`). Sinon, créer:

```python
# api/routes/code_graph_routes.py

@router.get("/path")
async def get_shortest_path(
    repository: str,
    source: str,
    target: str,
    graph_service: GraphTraversalService = Depends(get_graph_traversal_service)
):
    """
    Find shortest path between two nodes.

    Args:
        repository: Repository name
        source: Source node ID
        target: Target node ID

    Returns:
        List of node IDs representing the path
    """
    path = await graph_service.find_shortest_path(
        repository=repository,
        source_node_id=source,
        target_node_id=target
    )

    return {"path": path, "length": len(path)}
```

**Effort**: 2-3 jours

---

#### Story 21.2: Syntax Highlighting (Prism.js) (2 points, 0.5 jour)

**Objectif**: Ajouter coloration syntaxique au code affiché

**Implémentation**:

**2.1 Ajouter Prism.js à `templates/base.html`**:

```html
<!-- Avant </head> -->
<link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-okaidia.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-javascript.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-typescript.min.js"></script>

<script>
// Auto-highlight après HTMX swap
document.body.addEventListener('htmx:afterSwap', function(evt) {
  // Code search results
  if (evt.detail.target.id === 'code-results') {
    Prism.highlightAllUnder(evt.detail.target);
  }
});

// Initial highlight on page load
document.addEventListener('DOMContentLoaded', function() {
  Prism.highlightAll();
});
</script>

<style>
/* Override Prism theme pour SCADA */
code[class*="language-"],
pre[class*="language-"] {
  background: var(--color-bg-input) !important;
  color: var(--color-text-primary) !important;
  font-family: var(--font-mono) !important;
  font-size: 13px !important;
  line-height: 1.5 !important;
}

/* Token colors (SCADA theme) */
.token.keyword { color: #4a90e2 !important; } /* Blue */
.token.string { color: #20e3b2 !important; }  /* Cyan */
.token.function { color: #00f2fe !important; } /* Bright cyan */
.token.class-name { color: #9c27b0 !important; } /* Purple */
.token.comment { color: var(--color-text-dim) !important; }
.token.operator { color: #ff9800 !important; } /* Orange */
.token.number { color: #00ff88 !important; }  /* Green */
.token.boolean { color: #ff4466 !important; } /* Red */
.token.punctuation { color: var(--color-text-tertiary) !important; }
</style>
```

**2.2 Modifier `templates/partials/code_results.html`**:

```html
<!-- Ligne 163 -->
<!-- AVANT -->
<pre><code>{{ result.source_code or '(No code content)' }}</code></pre>

<!-- APRÈS -->
<pre><code class="language-{{ result.language }}">{{ result.source_code or '(No code content)' }}</code></pre>
```

**Effort**: 0.5 jour (4 heures)

---

### Phase 2: Should-Have (8 points, 3-4 jours) ⚠️ VALIDER D'ABORD

#### Story 21.3: Events Timeline (uPlot) (5 points, 2 jours)

**⚠️ Pré-requis**: Valider que MnemoLite a **réellement besoin** de visualiser 50k+ events en timeline

**Questions à poser**:
1. Combien d'events actuellement? (`SELECT COUNT(*) FROM events`)
2. Est-ce que Chart.js ne suffit pas pour quelques milliers?
3. Est-ce que les utilisateurs ont demandé une timeline?

**Si oui**, implémenter:

**3.1 Backend: Créer endpoint `/v1/events/timeline`**:

```python
# api/routes/events_routes.py

@router.get("/timeline")
async def get_events_timeline(
    start: Optional[str] = None,  # ISO date
    end: Optional[str] = None,
    aggregate_by: str = "hour",  # hour, day, week
    event_repo: EventRepository = Depends(get_event_repository)
):
    """
    Get aggregated event counts for timeline visualization.

    Args:
        start: Start date (ISO format)
        end: End date (ISO format)
        aggregate_by: Aggregation level (hour, day, week)

    Returns:
        {
          "timestamps": [unix_ts1, unix_ts2, ...],
          "counts": [count1, count2, ...]
        }
    """
    if aggregate_by == "hour":
        query = """
            SELECT
                date_trunc('hour', timestamp) AS bucket,
                COUNT(*) AS count
            FROM events
            WHERE timestamp >= $1 AND timestamp <= $2
            GROUP BY bucket
            ORDER BY bucket
        """
    # ... similar for day, week

    results = await event_repo.raw_query(query, start, end)

    timestamps = [int(r['bucket'].timestamp()) for r in results]
    counts = [r['count'] for r in results]

    return {
        "timestamps": timestamps,
        "counts": counts,
        "start": start,
        "end": end,
        "aggregate_by": aggregate_by
    }
```

**3.2 Frontend: Créer `templates/events_timeline.html`**:

```html
{% extends "base.html" %}

{% block extra_head %}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.min.css">
<script src="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.iife.min.js"></script>
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>📅 Events Timeline</h1>
    <p class="subtitle">High-performance timeline visualization</p>
</div>

<div class="timeline-controls">
  <div class="control-group">
    <label>Start Date</label>
    <input type="date" id="start-date" value="{{ start_date }}">
  </div>

  <div class="control-group">
    <label>End Date</label>
    <input type="date" id="end-date" value="{{ end_date }}">
  </div>

  <div class="control-group">
    <label>Aggregate By</label>
    <select id="aggregate-by">
      <option value="hour">Hour</option>
      <option value="day" selected>Day</option>
      <option value="week">Week</option>
    </select>
  </div>

  <button class="btn btn-primary" onclick="loadTimeline()">Load Timeline</button>
  <button class="btn btn-secondary" onclick="setRange('24h')">Last 24h</button>
  <button class="btn btn-secondary" onclick="setRange('7d')">Last 7d</button>
  <button class="btn btn-secondary" onclick="setRange('30d')">Last 30d</button>
</div>

<div id="timeline-loading" class="loading-indicator" hidden>
  <span class="spinner"></span> Loading timeline data...
</div>

<div id="events-timeline" class="timeline-chart"></div>

<div id="timeline-stats" class="stats-panel" hidden>
  <div class="stat-item">
    <span class="stat-label">Total Events:</span>
    <span class="stat-value" id="total-events">0</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Time Range:</span>
    <span class="stat-value" id="time-range"></span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Peak:</span>
    <span class="stat-value" id="peak-value">0</span>
  </div>
  <div class="stat-item">
    <span class="stat-label">Average:</span>
    <span class="stat-value" id="avg-value">0</span>
  </div>
</div>

<script>
let uplotInstance = null;

function setRange(range) {
  const end = new Date();
  const start = new Date(end);

  switch (range) {
    case '24h':
      start.setDate(start.getDate() - 1);
      break;
    case '7d':
      start.setDate(start.getDate() - 7);
      break;
    case '30d':
      start.setDate(start.getDate() - 30);
      break;
  }

  document.getElementById('start-date').value = start.toISOString().split('T')[0];
  document.getElementById('end-date').value = end.toISOString().split('T')[0];

  loadTimeline();
}

async function loadTimeline() {
  const start = document.getElementById('start-date').value;
  const end = document.getElementById('end-date').value;
  const aggregateBy = document.getElementById('aggregate-by').value;

  const loadingDiv = document.getElementById('timeline-loading');
  loadingDiv.hidden = false;

  try {
    const response = await fetch(
      `/v1/events/timeline?start=${start}&end=${end}&aggregate_by=${aggregateBy}`
    );
    const data = await response.json();

    renderTimeline(data);
    updateStats(data);
  } catch (error) {
    console.error('Error loading timeline:', error);
    alert('Error loading timeline data');
  } finally {
    loadingDiv.hidden = true;
  }
}

function renderTimeline(data) {
  const opts = {
    title: "Events Timeline",
    width: 1200,
    height: 400,
    series: [
      {},
      {
        label: "Events",
        stroke: "#00d4ff",
        width: 2,
        fill: "rgba(0, 212, 255, 0.1)",
        points: { show: false }
      }
    ],
    axes: [
      {
        space: 80,
        incrs: [
          60,        // 1m
          300,       // 5m
          900,       // 15m
          3600,      // 1h
          7200,      // 2h
          14400,     // 4h
          28800,     // 8h
          86400,     // 1d
          604800,    // 1w
        ],
        values: (self, ticks) => ticks.map(rawValue => {
          const date = new Date(rawValue * 1000);
          return date.toLocaleString();
        })
      },
      {
        label: "Count",
        labelSize: 20,
        space: 50
      }
    ],
    scales: {
      x: {
        time: true
      }
    },
    cursor: {
      lock: true,
      focus: {
        prox: 16,
      },
      sync: {
        key: "events",
      }
    }
  };

  const plotData = [data.timestamps, data.counts];

  const container = document.getElementById('events-timeline');
  container.innerHTML = ''; // Clear previous chart

  if (uplotInstance) {
    uplotInstance.destroy();
  }

  uplotInstance = new uPlot(opts, plotData, container);
}

function updateStats(data) {
  const totalEvents = data.counts.reduce((a, b) => a + b, 0);
  const peakValue = Math.max(...data.counts);
  const avgValue = (totalEvents / data.counts.length).toFixed(1);

  document.getElementById('total-events').textContent = totalEvents.toLocaleString();
  document.getElementById('peak-value').textContent = peakValue.toLocaleString();
  document.getElementById('avg-value').textContent = avgValue;

  const startDate = new Date(data.timestamps[0] * 1000).toLocaleDateString();
  const endDate = new Date(data.timestamps[data.timestamps.length - 1] * 1000).toLocaleDateString();
  document.getElementById('time-range').textContent = `${startDate} - ${endDate}`;

  document.getElementById('timeline-stats').hidden = false;
}

// Load initial timeline on page load
document.addEventListener('DOMContentLoaded', function() {
  setRange('7d');
});
</script>

<style>
.timeline-controls {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  padding: 16px;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  margin-bottom: 16px;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.control-group label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 600;
}

.timeline-chart {
  padding: 16px;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  margin-bottom: 16px;
}

.stats-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--color-text-primary);
}

/* uPlot SCADA theme overrides */
.u-legend {
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
}

.u-legend .u-series {
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>
{% endblock %}
```

**3.3 Ajouter route dans `api/routes/ui_routes.py`**:

```python
@router.get("/events/timeline")
async def events_timeline_page(request: Request):
    """Events timeline page."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    return templates.TemplateResponse(
        "events_timeline.html",
        {
            "request": request,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    )
```

**Effort**: 2 jours (1j backend + 1j frontend)

---

#### Story 21.4: Alpine.js Integration (3 points, 1-2 jours)

**⚠️ Pré-requis**: Valider que le JS custom actuel est **insuffisant**

**Questions à poser**:
1. Est-ce que le JS custom a des bugs?
2. Est-ce que les interactions sont complexes à maintenir?
3. Est-ce que Alpine.js simplifie vraiment le code?

**Si oui**, implémenter:

**4.1 Ajouter Alpine.js à `templates/base.html`**:

```html
<!-- Avant </head> -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>
```

**4.2 Refactor interactions existantes**:

**Exemple 1: Collapsible Filters**

```html
<!-- AVANT (JS custom) -->
<button onclick="toggleFilters()">Show Filters</button>
<div id="filters-panel" hidden>
  <!-- Filters -->
</div>

<script>
function toggleFilters() {
  const panel = document.getElementById('filters-panel');
  panel.hidden = !panel.hidden;
}
</script>

<!-- APRÈS (Alpine.js) -->
<div x-data="{ showFilters: false }">
  <button @click="showFilters = !showFilters">
    <span x-text="showFilters ? 'Hide' : 'Show'"></span> Filters
  </button>

  <div x-show="showFilters" x-transition class="filters-panel">
    <!-- Filters -->
  </div>
</div>
```

**Exemple 2: Tabs (Views Switching)**

```html
<!-- AVANT (JS custom) -->
<button onclick="setView('list')">List</button>
<button onclick="setView('grid')">Grid</button>

<div id="list-view">...</div>
<div id="grid-view" hidden>...</div>

<script>
function setView(view) {
  document.getElementById('list-view').hidden = view !== 'list';
  document.getElementById('grid-view').hidden = view !== 'grid';
}
</script>

<!-- APRÈS (Alpine.js) -->
<div x-data="{ view: 'list' }">
  <button @click="view = 'list'" :class="{ active: view === 'list' }">List</button>
  <button @click="view = 'grid'" :class="{ active: view === 'grid' }">Grid</button>

  <div x-show="view === 'list'" x-transition>...</div>
  <div x-show="view === 'grid'" x-transition>...</div>
</div>
```

**4.3 Créer composants réutilisables**:

```html
<!-- templates/components/modal.html -->
<template x-if="open">
  <div class="modal-overlay" @click.self="open = false">
    <div class="modal-content">
      <div class="modal-header">
        <h2 x-text="title"></h2>
        <button @click="open = false">✕</button>
      </div>
      <div class="modal-body">
        <!-- Slot content -->
      </div>
    </div>
  </div>
</template>
```

**Effort**: 1j intégration + 1j refactor = 2 jours

---

## 📊 Estimation Finale

| Phase | Stories | Points | Jours | Status |
|-------|---------|--------|-------|--------|
| **Phase 1: Must-Have** | 2 | **7** | **3-4** | ✅ READY |
| - Story 21.1: Code Graph Interactivity | | 5 | 2-3 | Click, path, filters |
| - Story 21.2: Syntax Highlighting (Prism.js) | | 2 | 0.5 | Trivial |
| **Phase 2: Should-Have** | 2 | **8** | **3-4** | ⚠️ VALIDATE FIRST |
| - Story 21.3: Events Timeline (uPlot) | | 5 | 2 | IF 50k+ events |
| - Story 21.4: Alpine.js Integration | | 3 | 2 | IF JS custom insufficient |
| **Total Minimal** | 2 | **7** | **3-4** | Phase 1 only |
| **Total Maximal** | 4 | **15** | **6-8** | If all validated |

---

## ✅ Checklist Avant Implémentation

### Phase 1 (Must-Have) - NO VALIDATION NEEDED ✅

- [x] Code Graph manque interactivité → **CONFIRMED**
- [x] Code snippets sans coloration → **CONFIRMED**
- [x] Prism.js est léger (2KB) → **CONFIRMED**
- [x] Pas de dépendances lourdes → **CONFIRMED**

### Phase 2 (Should-Have) - VALIDATION REQUIRED ⚠️

#### Story 21.3: Events Timeline
- [ ] **Vérifier volumétrie**: `SELECT COUNT(*) FROM events` → combien?
- [ ] **Vérifier besoin**: Est-ce que les utilisateurs ont demandé une timeline?
- [ ] **Chart.js suffit?**: Tester Chart.js avec données actuelles
- [ ] **uPlot justifié?**: 45KB OK SI vraiment 50k+ events

#### Story 21.4: Alpine.js
- [ ] **Auditer JS custom**: Y a-t-il des bugs ou limitations?
- [ ] **Complexité**: Est-ce que le code actuel est difficile à maintenir?
- [ ] **ROI**: Est-ce que Alpine.js simplifie vraiment (2j de refactor)?
- [ ] **15KB justifié?**: Alternative = continuer avec JS custom

---

## 🎯 Décision Finale

**RECOMMANDATION**:

1. **IMPLÉMENTER Phase 1** (7 points, 3-4 jours) immédiatement
   - Code Graph Interactivity
   - Syntax Highlighting (Prism.js)

2. **VALIDER Phase 2** avant d'implémenter
   - Vérifier volumétrie events (SELECT COUNT)
   - Auditer JS custom
   - Si validé → implémenter (8 points, 3-4 jours)
   - Sinon → POSTPONE jusqu'à demande explicite

**Total conservateur**: 7 points (3-4 jours)
**Total optimiste** (si validé): 15 points (6-8 jours)

**Économie vs EPIC-21 Original**:
- **24 points évités** (62%)
- **9-11 jours évités** (59%)
- **900KB évités** (ECharts)

---

**Document créé**: 2025-10-23
**Version**: 1.0
**Status**: ✅ READY FOR IMPLEMENTATION (Phase 1)
**Next Steps**: Implémenter Phase 1, puis valider Phase 2
