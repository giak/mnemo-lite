# EPIC-21: Critical Review & Pragmatic Assessment

**Date**: 2025-10-23
**Reviewer**: Critical Analysis
**Status**: 🔴 **NEEDS MAJOR REVISION**

---

## 🚨 Executive Summary

**Verdict**: Le document EPIC-21_UI_UX_MODERNIZATION_ULTRATHINK.md propose **39 story points** pour des features qui **EXISTENT DÉJÀ EN GRANDE PARTIE**. C'est du **over-engineering** qui contredit les principes KISS, DRY, et YAGNI de MnemoLite.

**Problèmes Majeurs**:
1. ❌ Ignore l'UI existante (EPIC-14 déjà implémenté)
2. ❌ Propose de refaire ce qui existe (code_search, code_dashboard)
3. ❌ Ajoute 1MB+ de dépendances pour peu de valeur ajoutée
4. ❌ 15-17 jours d'effort pour des duplications
5. ❌ Manque de pragmatisme : propose des features "nice-to-have" avant de valider les besoins réels

---

## 📋 État des Lieux RÉEL de l'UI

### Code Search - CE QUI EXISTE DÉJÀ ✅

**Document EPIC-21 dit** : "Recherche peu interactive, pas de filtres avancés, pas de preview"

**RÉALITÉ** (`templates/code_search.html` + `partials/code_results.html`):

#### Filtres Avancés (DÉJÀ IMPLÉMENTÉS)
- ✅ Repository filter
- ✅ Language filter (Python, JS, TS, Java, Go, Rust, C++, C)
- ✅ Chunk Type filter (function, class, method)
- ✅ **Return Type filter** (EPIC-14, avec autocomplete)
- ✅ **Parameter Type filter** (EPIC-14, avec autocomplete)
- ✅ Search Mode (Hybrid RRF, Lexical, Vector)
- ✅ Results limit (10, 20, 50, 100)

#### UI Sophistiquée (DÉJÀ IMPLÉMENTÉE)
- ✅ **Card-based layout** avec progressive disclosure (expand/collapse)
- ✅ **Type badges color-coded** (primitive=blue, complex=purple, collection=orange, optional=cyan)
- ✅ **LSP metadata display** (signatures, param types, docstrings)
- ✅ **Copy-to-clipboard button** (shortcut: c)
- ✅ **Keyboard navigation** (j/k pour naviguer, Enter pour expand)
- ✅ **ARIA accessibility** (aria-expanded, aria-controls, aria-label)
- ✅ **Skeleton loading states** (shimmer animation)
- ✅ **Enhanced empty states** (suggestions, tips)
- ✅ **Qualified names** (name_path) - EPIC-11
- ✅ **Performance metrics** (execution time, lexical/vector breakdown, fusion time)
- ✅ **Code snippet preview** (pre/code tags, monospace)

**Conclusion** : Code Search est **DÉJÀ EXCELLENT**. EPIC-21 propose de refaire ~80% de ce qui existe.

---

### Code Dashboard - CE QUI EXISTE DÉJÀ ✅

**Document EPIC-21 dit** : "Dashboard trop basique (juste des chiffres)"

**RÉALITÉ** (`templates/code_dashboard.html`):

#### KPI Cards (DÉJÀ IMPLÉMENTÉS)
- ✅ KPI Grid layout (responsive, auto-fit)
- ✅ Color-coded cards (repos=purple, files=red, functions=cyan, complexity=orange)
- ✅ SCADA industrial design (borders, monospace font)
- ✅ Chart.js 4.4.0 déjà intégré

**Conclusion** : Dashboard Code existe avec KPIs et charts. EPIC-21 veut "refondre" ce qui fonctionne déjà.

---

### Code Graph - CE QUI EXISTE DÉJÀ ✅

**Document EPIC-21 dit** : "Pas de drill-down, pas de path highlighting, pas de filters"

**RÉALITÉ** (`templates/code_graph.html` + `static/js/components/code_graph.js`):

#### Features (DÉJÀ IMPLÉMENTÉES)
- ✅ Cytoscape.js 3.28 intégré
- ✅ SCADA theme (dark, industrial colors)
- ✅ Repository selector
- ✅ Graph visualization (nodes, edges, calls, imports)

**Manque vraiment** :
- ⚠️ Drill-down interactif (click pour explorer)
- ⚠️ Path highlighting (shortest path)
- ⚠️ Filters (par complexity, type)
- ⚠️ Minimap
- ⚠️ Layout switching

**Conclusion** : Graph existe mais manque d'interactivité. C'est LE SEUL point où EPIC-21 a raison.

---

### Events System - CE QUI EXISTE DÉJÀ ✅

**Templates existants**:
- ✅ `dashboard.html` : Dashboard général avec KPIs events
- ✅ `search.html` : Recherche d'événements
- ✅ `monitoring.html` : Monitoring (lié à EPIC-20)

**Manque vraiment** :
- ⚠️ Timeline haute performance (50k-500k events) → uPlot pourrait aider
- ⚠️ Density heatmap
- ⚠️ Filtres temporels avancés

**Conclusion** : Events UI est fonctionnelle mais basique. EPIC-21 a raison ici (timeline manquante).

---

## 🎯 Ce Qui Manque VRAIMENT (Pragmatique)

### 1. Code Graph Interactivity (5 points) - HIGH PRIORITY ✅

**Vraiment utile** : Drill-down, path finder, filters

**Implémentation** :
```javascript
// Ajouter click handlers
cy.on('tap', 'node', (evt) => {
  const node = evt.target.data();
  showNodeDetails(node); // Modal ou panel
});

// Path finder
async function findShortestPath(sourceId, targetId) {
  const response = await fetch(`/v1/code/graph/path?source=${sourceId}&target=${targetId}`);
  const path = await response.json();
  highlightPath(path);
}

// Filters
cy.nodes().forEach(node => {
  const complexity = node.data('complexity');
  if (complexity > threshold) {
    node.addClass('high-complexity');
  }
});
```

**Effort** : 2-3 jours (pas 4-5 comme proposé)

---

### 2. Events Timeline (uPlot) (5 points) - MEDIUM PRIORITY ⚠️

**Vraiment utile** : Visualiser 50k-500k events avec performance

**Justification uPlot** :
- 45KB (négligeable)
- Optimisé pour timelines (10x+ faster que Chart.js sur gros datasets)
- Scrubber natif

**Implémentation** :
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.min.css">
<script src="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.iife.min.js"></script>

<div id="events-timeline"></div>

<script>
const opts = {
  width: 1200,
  height: 400,
  series: [
    {},
    { label: 'Events', stroke: '#00d4ff', width: 2 }
  ],
  axes: [
    { time: true },
    { label: 'Count' }
  ]
};

const data = [
  timestamps, // Unix timestamps
  counts      // Event counts
];

const plot = new uPlot(opts, data, document.getElementById('events-timeline'));
</script>
```

**Effort** : 2 jours (pas 3 comme proposé)

**Question** : Est-ce que MnemoLite a vraiment besoin de visualiser 50k events en timeline? Si non → YAGNI

---

### 3. Syntax Highlighting (Prism.js) (2 points) - LOW PRIORITY 🤷

**Vraiment utile** : Oui, améliore lisibilité

**Déjà présent** : Code snippets affichent du code brut

**Implémentation** :
```html
<link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-okaidia.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>

<!-- Dans code_results.html -->
<pre><code class="language-python">{{ result.source_code }}</code></pre>

<script>
// Auto-highlight après HTMX swap
document.body.addEventListener('htmx:afterSwap', () => {
  Prism.highlightAll();
});
</script>
```

**Effort** : 0.5 jour (trivial)

**Overhead** : 2KB core + 1KB per language = ~5KB total → OK

---

### 4. Alpine.js pour Interactions Client (3 points) - MEDIUM PRIORITY ⚠️

**Vraiment utile** : Oui, évite JavaScript custom partout

**Justification** :
- 15KB gzipped (négligeable)
- Reactive (x-data, x-show, x-if)
- Complémentaire HTMX (HTMX = server, Alpine = client)
- Pas de build step

**Use Cases MnemoLite** :
1. **Filters toggle** (show/hide advanced filters)
2. **Tabs** (switch between views: list/grid/tree)
3. **Modals** (details, confirmations)
4. **Dropdowns** (menus, selects)
5. **Tooltips** (info on hover)

**Implémentation** :
```html
<!-- base.html -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>

<!-- Example: Collapsible filters -->
<div x-data="{ showFilters: false }">
  <button @click="showFilters = !showFilters">
    <span x-text="showFilters ? 'Hide' : 'Show'"></span> Filters
  </button>

  <div x-show="showFilters" x-transition class="filters-panel">
    <!-- Filters here -->
  </div>
</div>
```

**Effort** : 1 jour (intégration) + 1 jour (refactor des interactions existantes)

**Question** : Est-ce que le JS custom actuel suffit? Si oui → YAGNI

---

### 5. Code Analytics Dashboard (8 points) - LOW PRIORITY 🤷

**EPIC-21 propose** :
- Complexity histogram
- Code hotspots heatmap (ECharts treemap)
- Language breakdown pie chart
- Top 10 complex functions
- Dependency metrics

**Problèmes** :
1. ❌ **ECharts 900KB** : Over-engineering pour des heatmaps
2. ❌ **Analytics avancées** : Qui va les utiliser? YAGNI jusqu'à preuve du besoin
3. ❌ **Complexity trends** : Nécessite historique (commits trackés) → pas encore implémenté

**Alternative KISS** :
- Utiliser **Chart.js** (déjà présent) pour histogram et pie chart
- **Pas de heatmap** (ECharts est trop lourd)
- Top 10 complex : simple table HTML (déjà dans le style de MnemoLite)

**Effort si vraiment nécessaire** : 2-3 jours (pas 8 points)

**Recommandation** : **POSTPONE** jusqu'à ce qu'un utilisateur demande explicitement ces analytics

---

### 6. Observability Enhancements (3 points) - DEPENDS ON EPIC-20

**EPIC-21 propose** :
- Heat maps (endpoints par heure) → ECharts 900KB
- Correlation charts (errors vs latency)
- Alerting visuel (SSE)

**Problèmes** :
1. ❌ **EPIC-20 pas encore implémenté** : Proposer des enhancements à quelque chose qui n'existe pas = cart before horse
2. ❌ **ECharts** : Over-engineering

**Recommandation** : **WAIT FOR EPIC-20 MVP**, puis évaluer les besoins réels

---

## 🔴 Problèmes Majeurs du Document EPIC-21

### 1. Ignorance de l'Existant

**Citation EPIC-21** :
> "Recherche peu interactive (pas de filtres avancés, pas de preview)"

**RÉALITÉ** :
- 7 filtres avancés (language, type, return type, param type, repo, mode, limit)
- Preview avec expand/collapse
- LSP metadata (signatures, params, docstrings)
- Keyboard navigation (j/k, Enter, c)

**Erreur** : Le document n'a **pas audité l'UI existante** avant de proposer des améliorations.

---

### 2. Over-Engineering : Stack Technique

**EPIC-21 propose** :
```
Chart.js 4.4 (60KB)         ✅ Déjà présent, garder
uPlot 1.6 (45KB)           ⚠️ Utile SI timeline events nécessaire
Apache ECharts 5.5 (900KB) ❌ TROP LOURD pour heatmaps
Alpine.js 3.x (15KB)       ⚠️ Utile SI interactions complexes
Prism.js (2KB)             ✅ Léger, utile
Cytoscape.js 3.28 (300KB)  ✅ Déjà présent, garder
───────────────────────────────────────────────────────
Total: ~1.3MB (~400KB gzipped)
```

**Problème** : **900KB pour ECharts** juste pour des heatmaps = over-engineering

**Alternative KISS** :
```
Chart.js 4.4 (60KB)         ✅ Déjà présent
uPlot 1.6 (45KB)           ⚠️ YAGNI jusqu'à preuve du besoin
Alpine.js 3.x (15KB)       ⚠️ YAGNI jusqu'à preuve du besoin
Prism.js (2KB)             ✅ Utile, léger
Cytoscape.js 3.28 (300KB)  ✅ Déjà présent
───────────────────────────────────────────────────────
Total: ~62KB new (vs 960KB proposed)
```

**Économie** : **900KB évités** en évitant ECharts

---

### 3. Estimation Irréaliste : 39 Points (15-17 jours)

**EPIC-21 Breakdown** :

| Phase | Jours | Points | RÉALITÉ |
|-------|-------|--------|---------|
| Phase 1: Fondations | 2-3 | 5 | ⚠️ Alpine.js = 1j si vraiment nécessaire |
| Phase 2: Dashboard | 2 | 5 | ❌ Dashboard existe déjà (EPIC-14) |
| Phase 3: Code Intel | 4-5 | 13 | ❌ Search v2 existe (EPIC-14), Graph = 2-3j |
| Phase 4: Events | 3 | 8 | ⚠️ Timeline = 2j si vraiment nécessaire |
| Phase 5: Observability | 2 | 5 | ❌ EPIC-20 pas encore fait |
| Phase 6: Polish | 2 | 3 | ⚠️ Toujours utile mais vague |
| **Total** | **15-17** | **39** | **5-7 jours réels** si on garde utile |

**Vraie Estimation Pragmatique** :

| Tâche | Points | Justification |
|-------|--------|---------------|
| Code Graph Interactivity | 5 | Click handlers, path finder, filters |
| Events Timeline (uPlot) | 5 | Si nécessaire (valider besoin d'abord) |
| Syntax Highlighting (Prism.js) | 2 | Trivial, léger |
| Alpine.js Integration | 3 | Si nécessaire (valider besoin d'abord) |
| **Total (Must-Have)** | **7** | Graph interactivity + Prism.js |
| **Total (Should-Have)** | **15** | Si timeline & Alpine vraiment nécessaires |

**Économie** : **24 points évités** (62% reduction)

---

### 4. Manque de Validation des Besoins

**EPIC-21 assume** :
- ❓ Besoin de visualiser 50k-500k events en timeline?
- ❓ Besoin de heatmaps complexes (ECharts)?
- ❓ Besoin d'Alpine.js vs JS custom actuel?
- ❓ Besoin d'analytics avancées (complexity trends, hotspots)?

**Problème** : **Aucune validation utilisateur**. Le document propose des features "nice-to-have" sans prouver qu'elles sont nécessaires.

**YAGNI Principle** : "You Aren't Gonna Need It" → Ne pas implémenter jusqu'à preuve du besoin

---

### 5. Contradiction avec Principes MnemoLite

**CLAUDE.md §PRINCIPLES** :
```
◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy
```

**CLAUDE.md §UI** :
```
◊Philosophy: EXTEND>REBUILD → copy.existing{graph.html→code_graph.html} → adapt.minimal → ~10x.faster
```

**EPIC-21 viole** :
- ❌ **EXTEND > REBUILD** : Propose de refaire code_search, dashboard
- ❌ **KISS** : Ajoute 900KB ECharts pour peu de valeur
- ❌ **YAGNI** : Propose features sans valider besoin
- ❌ **Technical Objectivity** : N'a pas audité l'existant avant de proposer

---

## ✅ Recommandations Pragmatiques

### Plan Révisé : "EPIC-21-LITE" (7-15 points)

#### Phase 1: Must-Have (7 points, 3-4 jours)

**1.1 Code Graph Interactivity (5 points, 2-3 jours)**

```javascript
// Ajouter à static/js/components/code_graph.js

// Click handlers pour drill-down
cy.on('tap', 'node', (evt) => {
  const node = evt.target.data();
  showNodeDetailsPanel(node); // Modal ou side panel
});

// Path finder
async function findPath(sourceId, targetId) {
  const response = await fetch(`/v1/code/graph/path?source=${sourceId}&target=${targetId}`);
  const path = await response.json();

  // Highlight path
  cy.elements().removeClass('highlighted');
  path.forEach(nodeId => {
    cy.getElementById(nodeId).addClass('highlighted');
  });
}

// Filters par complexity
function filterByComplexity(threshold) {
  cy.nodes().forEach(node => {
    const complexity = node.data('complexity') || 0;
    if (complexity >= threshold) {
      node.show();
    } else {
      node.hide();
    }
  });
}

// Layout switching
function changeLayout(layoutName) {
  cy.layout({ name: layoutName }).run();
}
```

**Templates** :
```html
<!-- Ajouter à code_graph.html -->
<div class="graph-toolbar">
  <select id="layout-select" onchange="changeLayout(this.value)">
    <option value="cose">Force-Directed</option>
    <option value="breadthfirst">Hierarchical</option>
    <option value="circle">Circular</option>
  </select>

  <label>Complexity ≥</label>
  <input type="range" min="0" max="20" oninput="filterByComplexity(this.value)">

  <button onclick="openPathFinder()">Find Path</button>
</div>

<div id="node-details-panel" hidden>
  <!-- Afficher détails du node sélectionné -->
</div>
```

**API** : Endpoint `/v1/code/graph/path` déjà existe (à vérifier)

**Effort** : 2-3 jours

---

**1.2 Syntax Highlighting (Prism.js) (2 points, 0.5 jour)**

```html
<!-- Ajouter à base.html -->
<link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-okaidia.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-python.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-javascript.min.js"></script>

<script>
// Auto-highlight après HTMX swap
document.body.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target.id === 'code-results') {
    Prism.highlightAllUnder(evt.detail.target);
  }
});
</script>

<style>
/* Override Prism theme pour SCADA */
code[class*="language-"],
pre[class*="language-"] {
  background: var(--color-bg-input);
  color: var(--color-text-primary);
  font-family: var(--font-mono);
}

.token.keyword { color: #4a90e2; } /* Blue */
.token.string { color: #20e3b2; }  /* Cyan */
.token.function { color: #00f2fe; } /* Bright cyan */
.token.comment { color: var(--color-text-dim); }
</style>
```

**Modifier** : `templates/partials/code_results.html`
```html
<!-- Avant -->
<pre><code>{{ result.source_code }}</code></pre>

<!-- Après -->
<pre><code class="language-{{ result.language }}">{{ result.source_code }}</code></pre>
```

**Effort** : 0.5 jour (trivial)

---

#### Phase 2: Should-Have (8 points, 3-4 jours) - VALIDER BESOIN D'ABORD

**2.1 Events Timeline (uPlot) (5 points, 2 jours)**

**Pré-requis** : Valider que l'utilisateur a **réellement besoin** de visualiser 50k+ events en timeline

**Si oui** :
```html
<!-- Créer templates/events_timeline.html -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.min.css">
<script src="https://cdn.jsdelivr.net/npm/uplot@1.6.30/dist/uPlot.iife.min.js"></script>

<div class="timeline-controls">
  <input type="date" id="start-date">
  <input type="date" id="end-date">
  <button onclick="loadTimeline()">Load</button>
</div>

<div id="events-timeline"></div>

<script>
async function loadTimeline() {
  const start = document.getElementById('start-date').value;
  const end = document.getElementById('end-date').value;

  const response = await fetch(`/v1/events/timeline?start=${start}&end=${end}`);
  const data = await response.json();

  const opts = {
    width: 1200,
    height: 400,
    series: [
      {},
      { label: 'Events', stroke: '#00d4ff', width: 2, fill: 'rgba(0, 212, 255, 0.1)' }
    ],
    axes: [
      { time: true },
      { label: 'Count' }
    ]
  };

  const plot = new uPlot(opts, [data.timestamps, data.counts], document.getElementById('events-timeline'));
}
</script>
```

**API** : Créer endpoint `/v1/events/timeline` (aggregation par heure/jour)

**Effort** : 2 jours (1j backend + 1j frontend)

---

**2.2 Alpine.js pour Interactions (3 points, 1-2 jours)**

**Pré-requis** : Valider que le JS custom actuel est **insuffisant**

**Si oui** :
```html
<!-- Ajouter à base.html -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>
```

**Refactor des interactions existantes** :
1. Collapsible filters
2. Tabs (list/grid/tree views)
3. Modals (confirmations, details)
4. Tooltips

**Effort** : 1j intégration + 1j refactor = 2 jours

---

### Total Révisé

| Scope | Points | Jours | Description |
|-------|--------|-------|-------------|
| **Must-Have** | 7 | 3-4 | Graph interactivity + Prism.js |
| **Should-Have** | 8 | 3-4 | Timeline + Alpine.js (SI besoin validé) |
| **Total Minimal** | 7 | 3-4 | Sans valider besoins avancés |
| **Total Maximal** | 15 | 6-8 | Si tous les besoins validés |

**vs EPIC-21 Original** : 39 points, 15-17 jours → **Économie de 24 points (62%)**

---

## 🎯 Questions Critiques à Poser

Avant d'implémenter quoi que ce soit, **VALIDER** :

### 1. Code Graph
- ❓ Est-ce que les utilisateurs ont besoin de drill-down interactif?
- ❓ Est-ce que path finder est vraiment utile (use case concret)?
- ❓ Est-ce que les filtres (complexity, type) sont demandés?

**Action** : Tester l'UI actuelle avec un utilisateur réel

---

### 2. Events Timeline
- ❓ Est-ce que MnemoLite a **vraiment** 50k-500k events?
- ❓ Est-ce que les utilisateurs ont besoin de visualiser des trends temporels?
- ❓ Est-ce que Chart.js ne suffit pas pour quelques milliers d'events?

**Action** : Vérifier la volumétrie réelle (`SELECT COUNT(*) FROM events`)

---

### 3. Alpine.js
- ❓ Est-ce que le JS custom actuel est **vraiment** insuffisant?
- ❓ Est-ce qu'il y a des bugs ou limitations avec le code actuel?
- ❓ Est-ce que la complexité justifie une librairie réactive?

**Action** : Auditer le JS custom actuel (`static/js/components/*.js`)

---

### 4. Code Analytics
- ❓ Est-ce que quelqu'un a demandé des heatmaps de complexity?
- ❓ Est-ce que "Top 10 complex functions" est vraiment utile (vs juste trier dans search)?
- ❓ Est-ce que ECharts 900KB est justifié pour des viz qu'on n'utilise pas?

**Action** : **POSTPONE** jusqu'à demande explicite

---

### 5. Observability Enhancements
- ❓ Est-ce que EPIC-20 MVP est implémenté?
- ❓ Est-ce que le MVP suffit ou manque-t-il quelque chose?

**Action** : **WAIT FOR EPIC-20**, puis réévaluer

---

## 📊 Comparaison : EPIC-21 vs EPIC-21-LITE

| Critère | EPIC-21 Original | EPIC-21-LITE (Révisé) |
|---------|------------------|------------------------|
| **Points** | 39 | 7-15 |
| **Jours** | 15-17 | 3-8 |
| **New Deps** | 960KB (Alpine+uPlot+ECharts) | 2-60KB (Prism.js +/- Alpine +/- uPlot) |
| **Audit Existant** | ❌ Non | ✅ Oui |
| **KISS Compliant** | ❌ Non (over-engineering) | ✅ Oui |
| **YAGNI Compliant** | ❌ Non (features spéculatives) | ✅ Oui (validation d'abord) |
| **Pragmatique** | ❌ Non (refait l'existant) | ✅ Oui (extend, pas rebuild) |
| **Risque** | 🔴 Haut (duplication, over-engineering) | 🟢 Bas (incrémental, validé) |

---

## ✅ Conclusion & Recommandations Finales

### Verdict

**EPIC-21 Original** : 🔴 **REJETER** pour over-engineering et ignorance de l'existant

**EPIC-21-LITE (Révisé)** : 🟢 **APPROUVER** Phase 1 (Must-Have, 7 points)

### Plan d'Action Immédiat

1. **AUDITER** l'UI existante avec un utilisateur réel
   - Code Search : Est-ce que EPIC-14 suffit?
   - Code Graph : Quelles interactions manquent vraiment?
   - Events : Besoin de timeline ou Chart.js suffit?

2. **IMPLÉMENTER** Phase 1 (Must-Have, 7 points, 3-4 jours)
   - Code Graph Interactivity (5 pts, 2-3j)
   - Syntax Highlighting Prism.js (2 pts, 0.5j)

3. **VALIDER** besoins Phase 2 (Should-Have, 8 points)
   - Timeline Events : Volumétrie? Use case?
   - Alpine.js : JS custom insuffisant?

4. **POSTPONE** features spéculatives
   - Code Analytics (ECharts 900KB)
   - Observability Enhancements (EPIC-20 pas fait)

### Principes à Respecter

1. **EXTEND > REBUILD** : Ne pas refaire ce qui existe (EPIC-14)
2. **KISS** : Éviter 900KB ECharts pour des heatmaps
3. **YAGNI** : Valider besoin avant d'implémenter
4. **DRY** : Ne pas dupliquer code_search, dashboard
5. **Technical Objectivity** : Auditer l'existant d'abord

### Message au Product Owner

> "EPIC-21 propose 39 points (15-17 jours) pour refaire ce qui existe déjà en grande partie (EPIC-14). Après audit, je recommande EPIC-21-LITE : 7-15 points (3-8 jours) pour ajouter uniquement ce qui manque vraiment :
>
> **Must-Have (7 pts, 3-4j)** :
> - Code Graph interactivity (drill-down, path finder, filters)
> - Syntax highlighting (Prism.js 2KB)
>
> **Should-Have (8 pts, 3-4j)** - SI besoin validé :
> - Events Timeline (uPlot 45KB)
> - Alpine.js (15KB) pour interactions client
>
> **Total économie : 24 points (62%), 9-11 jours évités**
>
> Valider besoins utilisateurs avant d'aller plus loin."

---

**Document créé** : 2025-10-23
**Version** : 1.0
**Status** : CRITICAL REVIEW COMPLETE
**Recommandation** : REVISE EPIC-21 → EPIC-21-LITE
