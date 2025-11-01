# EPIC-25: UI/UX Refonte Complète

**Status**: 🟡 PLANNING
**Priority**: P1 (Critical - User Experience)
**Story Points**: 87 pts (estimé)
**Duration**: 3-4 mois (solo dev)
**Start Date**: TBD
**Target**: Q1 2026

---

## 📋 Vue d'Ensemble

### Objectif

Transformer l'interface actuelle (fragmentée, POC) en application professionnelle unifiée avec:
- Navigation claire entre features
- Dashboard complet avec monitoring temps réel
- Recherche unifiée (conversations + code)
- Graph avancé interactif
- Monitoring live (logs, métriques, alertes)

### Problème Actuel

- ❌ Pas de navbar → navigation par URL directe
- ❌ Pages isolées (pas de cohésion)
- ❌ Monitoring basique (statique, incomplet)
- ❌ Graph simple (pas de zoom/pan/filters)
- ❌ Pas de vue d'ensemble système
- ❌ **2 modèles embeddings** (TEXT: nomic-text-v1.5 | CODE: jina-code-v2) → pas de visibilité séparée

### Solution Proposée

Interface unifiée avec 5 pages principales:
1. **Dashboard** - Vue d'ensemble santé + métriques
2. **Search** - Recherche unifiée (all types)
3. **Graph** - Visualization avancée dépendances
4. **Monitoring** - Logs + métriques temps réel
5. **Settings** - Configuration système

---

## 🎯 Features Clés

### 1. Navigation Unifiée 🧭
- **Navbar sticky** avec tous les liens
- Active state (highlight page actuelle)
- Responsive (hamburger menu mobile)
- Dark mode toggle

### 2. Dashboard Principal 📊
- **Santé système**: CPU, RAM, Disk, Services status
- **Storage metrics**: 2 types embeddings (conversations + code)
- **Performance**: Search latency, graph render time, uptime
- **Activity chart**: API calls over time (live)
- **Recent alerts**: Critical/Warning display
- **Quick actions**: Search, Graph, Logs, Test

**Real-time**: SSE updates every 5s

### 3. Recherche Unifiée 🔍
- **Single search bar**: Conversations + Code + Functions
- **Hybrid search**: Lexical (BM25) + Vector (cosine)
- **Filters**: Type, scope, date, language
- **Results grouped**: Par type avec score
- **Instant preview**: Dropdown pendant typing
- **Highlighting**: Keywords surlignés

### 4. Graph Avancé 🕸️
- **Cytoscape.js** (vs D3.js actuel)
- **Layout algorithms**: Force, Hierarchical, Circular, Grid
- **Filters**: Type, depth, pattern
- **Node details**: Imports, used by, complexity, metrics
- **Path finding**: "Find path from A to B"
- **Export**: SVG, PNG, JSON

### 5. Monitoring Temps Réel ⚡
- **System metrics live**: CPU, RAM, Disk, Network (SSE)
- **Live charts**: CPU over time, request rate
- **Services health**: API, PostgreSQL, Redis, Embedding
- **Log streaming**: SSE avec filters (level, source, keyword)
- **Active alerts**: Critical/Warning avec actions
- **Auto-scroll logs** + pause/resume

### 6. Settings & Polish ⚙️
- **General**: Theme, language, timezone
- **Performance**: Cache TTL, timeouts, batch sizes
- **Monitoring**: Metrics retention, log level, alert thresholds
- **Embeddings**: Model params, HNSW config
- **Search**: Hybrid weights, RRF constant

---

## 📊 Décomposition en Stories (23 stories, 87 pts)

### Phase 1: Infrastructure & Navigation (13 pts)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| 25.1 | Navbar Unifiée + Routing | 5 pts | 🔴 PENDING |
| 25.2 | Dashboard Backend API | 3 pts | 🔴 PENDING |
| 25.3 | Dashboard Frontend (Layout + Cards) | 5 pts | 🔴 PENDING |

**Deliverables Phase 1**:
- ✅ Navbar sticky avec 5 liens
- ✅ Routing setup (React Router ou FastAPI)
- ✅ Dashboard skeleton (grid layout)
- ✅ 4 metric cards (santé, storage, perf, activity)

---

### Phase 2: Dashboard Complet (18 pts)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| 25.4 | Embeddings Overview Cards | 3 pts | 🔴 PENDING |
| 25.5 | Activity Chart (Line Chart) | 5 pts | 🔴 PENDING |
| 25.6 | Recent Alerts Widget | 5 pts | 🔴 PENDING |
| 25.7 | Quick Actions Buttons | 2 pts | 🔴 PENDING |
| 25.8 | Real-Time Dashboard (SSE) | 3 pts | 🔴 PENDING |

**Deliverables Phase 2**:
- ✅ 2 embedding cards (conversations + code stats)
- ✅ Live activity chart (Chart.js)
- ✅ Alerts widget (last 5 alerts)
- ✅ Quick action buttons (4 actions)
- ✅ SSE streaming (auto-update every 5s)

---

### Phase 3: Recherche Unifiée (15 pts)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| 25.9 | Unified Search Backend | 8 pts | 🔴 PENDING |
| 25.10 | Unified Search Frontend | 5 pts | 🔴 PENDING |
| 25.11 | Search Instant Preview | 2 pts | 🔴 PENDING |

**Deliverables Phase 3**:
- ✅ `/api/v1/search/unified` endpoint
- ✅ Search across conversations + code + functions
- ✅ Faceted filters (type, scope, date)
- ✅ Results grouped par type
- ✅ Instant search (dropdown preview)

---

### Phase 4: Graph Avancé (13 pts)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| 25.12 | Cytoscape.js Integration | 5 pts | 🔴 PENDING |
| 25.13 | Graph Layout Algorithms | 3 pts | 🔴 PENDING |
| 25.14 | Graph Filters & Details Panel | 3 pts | 🔴 PENDING |
| 25.15 | Path Finding Feature | 2 pts | 🔴 PENDING |

**Deliverables Phase 4**:
- ✅ Cytoscape.js (replace D3.js)
- ✅ 4 layout algorithms (Force, Hierarchical, Circular, Grid)
- ✅ Filters (type, depth, pattern)
- ✅ Node details panel (imports, used by, metrics)
- ✅ Path finding algorithm

---

### Phase 5: Monitoring Temps Réel (20 pts)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| 25.16 | System Metrics Backend (SSE) | 5 pts | 🔴 PENDING |
| 25.17 | System Metrics Frontend (Live Charts) | 5 pts | 🔴 PENDING |
| 25.18 | Services Health Check | 3 pts | 🔴 PENDING |
| 25.19 | Live Logs Streaming (SSE) | 5 pts | 🔴 PENDING |
| 25.20 | Active Alerts System | 2 pts | 🔴 PENDING |

**Deliverables Phase 5**:
- ✅ SSE endpoint `/api/v1/monitoring/metrics/stream`
- ✅ Live charts (CPU, RAM, Disk, Network)
- ✅ Services health (API, PostgreSQL, Redis, Embedding)
- ✅ Log streaming SSE avec filters
- ✅ Active alerts system (trigger + display)

---

### Phase 6: Settings & Polish (8 pts)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| 25.21 | Settings Page (Backend + Frontend) | 5 pts | 🔴 PENDING |
| 25.22 | Dark Mode Toggle | 2 pts | 🔴 PENDING |
| 25.23 | Responsive Design (Mobile) | 1 pt | 🔴 PENDING |

**Deliverables Phase 6**:
- ✅ Settings page (6 sections)
- ✅ Dark mode toggle
- ✅ Mobile responsive (all pages)

---

## 🏗️ Architecture Technique

### Stack Frontend ✅ DÉCIDÉ

**Choix**: Vue.js 3 + Vite + PNPM (Modern Stack)

```
Frontend:
  Vue.js 3.5+ (Composition API + <script setup>)
  Vite 7.0.0 (build tool)
  TypeScript 5.7+
  PNPM (package manager)

UI/UX:
  TailwindCSS 3.4+
  Shadcn-Vue (component library)
  Chart.js 4.5+ (activity charts)
  Cytoscape.js 3.32+ (graph visualization)
  Heroicons (icons)

State:
  Pinia 2.3+ (state management)
  VueUse 11.5+ (composables library)

Testing:
  Vitest 3.0+ (unit tests)
  @vitest/ui (test UI)

Linting/Formatting:
  Biome 1.9+ (TypeScript/JSON/CSS)
  ESLint + eslint-plugin-vue (Vue SFC files)

Optional:
  Bun (faster dev scripts, optional)
```

**Performance Benefits**:
- Dev server: Instant start (<1s vs 15s Webpack)
- HMR: <50ms updates (vs 2-3s)
- Install: PNPM 3x faster than NPM (40s vs 120s)
- Bundle: ~300KB total (gzipped, excellent for rich dashboard)

**Rationale**:
- ✅ User preference: Vue.js 3
- ✅ Simpler than React (Composition API vs hooks)
- ✅ Excellent SSE support (native EventSource)
- ✅ Production-proven (Vite used by Next.js, Nuxt, Astro)
- ✅ Fast development (instant HMR, 85% time savings)

**Documentation**: See `EPIC-25_TECH_STACK_ANALYSIS.md` for full research

### Stack Backend (Inchangé)

```
FastAPI (Python 3.11+)
PostgreSQL 18 + pgvector 0.8.1
Redis (cache + SSE queue)
```

**Nouveaux endpoints**:
- `/api/v1/dashboard/*` (summary, health, stream)
- `/api/v1/search/unified` (search all types)
- `/api/v1/graph/*` (full, path)
- `/api/v1/monitoring/*` (metrics/stream, logs/stream, alerts)
- `/api/v1/settings` (GET/PUT)

### Real-Time Strategy

**Server-Sent Events (SSE)**:
- Metrics stream (update every 2-5s)
- Logs stream (live append)
- Alerts stream (push on trigger)

**Why SSE** (vs WebSocket):
- Simpler (HTTP)
- Auto-reconnect (browser)
- Server→Client only (our use case)

---

## 📈 Progression

### Points Complétés

| Phase | Stories | Points | % |
|-------|---------|--------|---|
| Phase 1 | 0/3 | 0/13 pts | 0% |
| Phase 2 | 0/5 | 0/18 pts | 0% |
| Phase 3 | 0/3 | 0/15 pts | 0% |
| Phase 4 | 0/4 | 0/13 pts | 0% |
| Phase 5 | 0/5 | 0/20 pts | 0% |
| Phase 6 | 0/3 | 0/8 pts | 0% |
| **TOTAL** | **0/23** | **0/87 pts** | **0%** |

**Date de début**: TBD
**Date estimée fin**: TBD + 3-4 mois

---

## 🎨 Wireframes & Maquettes

Voir: `EPIC-25_UI_UX_REFONTE_ULTRATHINK.md` section "Wireframes (ASCII)"

**Pages clés**:
1. Dashboard Principal (grids + charts + alerts)
2. Search Unifiée (single bar + grouped results)
3. Graph Avancé (cytoscape + controls + details)
4. Monitoring Live (metrics + logs stream + alerts)
5. Settings (6 sections tabs)

---

## 🚀 MVP Strategy

### MVP1 (4-6 semaines) - Foundation

**Stories**: 25.1-25.8 (Phase 1 + 2)
**Points**: 31 pts
**Focus**: Navigation + Dashboard complet

**Value**:
- Navbar → navigation facile
- Dashboard → vue d'ensemble instantanée
- SSE → monitoring temps réel basic

### MVP2 (6-8 semaines) - Core Features

**Stories**: 25.9-25.11, 25.16-25.20 (Phase 3 + 5)
**Points**: 35 pts
**Focus**: Search unifiée + Monitoring live

**Value**:
- Unified search → find anything fast
- Live logs → debug temps réel
- Alerts → proactive monitoring

### MVP3 (8-12 semaines) - Polish

**Stories**: 25.12-25.15, 25.21-25.23 (Phase 4 + 6)
**Points**: 21 pts
**Focus**: Graph avancé + Settings

**Value**:
- Graph interactif → code exploration
- Settings → configuration facile
- Dark mode + responsive → UX premium

---

## ⚠️ Risques & Mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| **SSE complexity** | High | Medium | POC early, test reconnect scenarios |
| **Chart perf (large data)** | Medium | High | Pagination, data sampling |
| **Graph slow (>1000 nodes)** | High | Medium | Virtual rendering, lazy load |
| **React learning curve** | Medium | High | Tutorials, small POCs first |
| **Responsive break** | Medium | Medium | Test early, use Tailwind defaults |
| **Scope creep** | High | High | Stick to MVP phases, no extras |

---

## 📝 Dépendances

### Hard Dependencies
- ❌ EPIC-23 (MCP Integration) → Must be complete
- ❌ EPIC-22 (Observability) → Partial (need `/monitoring/metrics` endpoint)

### Soft Dependencies
- ⚠️ EPIC-24 (Auto-save) → Nice to have stats on dashboard
- ⚠️ Code graph existing → Will be enhanced (not replaced)

---

## 🎯 Success Metrics

### User Experience
- **Navigation**: <2 clicks to any feature
- **Dashboard load**: <1 second
- **Search latency**: <500ms (instant preview <300ms)
- **Graph render**: <2 seconds (1000 nodes)
- **Log streaming**: <100ms delay

### Technical
- **SSE uptime**: >99.9%
- **Mobile responsive**: 100% pages
- **Dark mode**: All components support
- **Test coverage**: >80% components

### Business
- **User satisfaction**: Survey >8/10
- **Feature usage**: Dashboard #1 visited page
- **Time saved**: -30% time to find info

---

## 📚 Documents Liés

- **[ULTRATHINK]** `EPIC-25_UI_UX_REFONTE_ULTRATHINK.md` - Analyse approfondie
- **[TECH STACK]** `EPIC-25_TECH_STACK_ANALYSIS.md` ✅ - Analyse Vue.js 3 + Vite + PNPM
- **[VALIDATION]** `EPIC-25_VALIDATION_EMBEDDING_MODELS.md` ✅ - Validation TEXT vs CODE
- **[WIREFRAMES]** TBD - Maquettes Figma/Sketch
- **[API SPEC]** TBD - Spec OpenAPI nouveaux endpoints

---

## 🤔 Décisions à Prendre

### 1. Tech Stack Frontend ✅ DÉCIDÉ
**Choix**: Vue.js 3 + Vite + PNPM
**Date décision**: 2025-11-01
**Rationale**:
- User preference: Vue.js 3
- Simpler than React (Composition API < hooks complexity)
- Excellent SSE support (native EventSource)
- Vite 7.0.0: Instant dev server, <50ms HMR
- PNPM: 3x faster installs, 75% disk space savings
- Production-proven: Next.js, Nuxt, Astro all use Vite

**Documentation**: `EPIC-25_TECH_STACK_ANALYSIS.md`

### 2. Dark Mode Priorité
**Options**: Phase 1 (high priority) vs Phase 6 (polish)
**Impact**: User experience (many devs prefer dark)
**Recommandation**: Phase 6 (not blocking MVP)

### 3. Mobile Support
**Options**: Must-have (Phase 1) vs Nice-to-have (Phase 6)
**Stats**: % users mobile? (check analytics)
**Recommandation**: Phase 6 (desktop first, responsive later)

### 4. Embeddings Visualizer
**Options**: Include (new stories) vs Separate EPIC
**Complexity**: t-SNE + 3D viz = +8 pts
**Recommandation**: Separate EPIC-26 (not MVP)

---

## 📅 Timeline Estimé

```
Semaine 1-2:   Phase 1 (Navigation)          → MVP0
Semaine 3-6:   Phase 2 (Dashboard)           → MVP1 ✅
Semaine 7-10:  Phase 3 + 5 (Search + Monitor)→ MVP2 ✅
Semaine 11-13: Phase 4 + 6 (Graph + Settings)→ MVP3 ✅
```

**Total**: 13 semaines (3 mois) si aucun blocage

**Buffer**: +20% pour bugs imprévus → **16 semaines (4 mois)**

---

## ✅ Acceptance Criteria (EPIC-25)

- [ ] Navbar unifiée sur toutes les pages (sticky)
- [ ] Dashboard affiche métriques temps réel (SSE)
- [ ] 2 types embeddings visibles (conversations + code)
- [ ] Recherche unifiée fonctionne (conversations + code + functions)
- [ ] Graph interactif avec filters et path finding
- [ ] Monitoring affiche logs live (SSE stream)
- [ ] Alerts système fonctionnelles (trigger + display)
- [ ] Settings page permet configuration
- [ ] Dark mode toggle functional
- [ ] Responsive sur mobile (toutes pages)
- [ ] Tests >80% coverage (nouveaux components)
- [ ] Documentation complète (README + API spec)

---

## 🔗 Liens Rapides

- **ULTRATHINK**: [EPIC-25_UI_UX_REFONTE_ULTRATHINK.md](./EPIC-25_UI_UX_REFONTE_ULTRATHINK.md)
- **Repo**: `/home/giak/Work/MnemoLite`
- **Frontend**: `TBD (React ou HTMX)`
- **Backend**: `api/`

---

**Status**: 🟡 PLANNING (waiting user validation)
**Next Step**: Tech stack decision + Phase 1 kick-off
**Owner**: Claude Code + Christophe Giacomel

**Dernière mise à jour**: 2025-11-01
