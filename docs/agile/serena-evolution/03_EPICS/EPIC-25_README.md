# EPIC-25: UI/UX Refonte - MVP Simplifié

**Status**: 🚧 IN PROGRESS
**Priority**: P1 (Critical - User Experience)
**Story Points**: 23 pts (simplifié KISS/YAGNI)
**Duration**: 6-9 semaines (solo dev)
**Start Date**: 2025-11-01
**Completed Points**: 8/23 pts (35%)
**Target**: Q1 2026

---

## 📋 Vue d'Ensemble

### Objectif

Créer une interface unifiée simple et fonctionnelle pour MnemoLite avec navigation claire et features essentielles.

**Principe**: KISS (Keep It Simple, Stupid) + YAGNI (You Ain't Gonna Need It)

### Problème Actuel

- ❌ Pas de navbar → navigation par URL directe
- ❌ Pages isolées (pas de cohésion)
- ❌ Pas de vue d'ensemble système
- ❌ **2 modèles embeddings** (TEXT + CODE) → pas de visibilité séparée
- ❌ Graph basique (pas d'interactions)
- ❌ Pas de logs viewer

### Solution MVP

Interface unifiée avec **4 pages essentielles**:

1. **Dashboard** - Vue d'ensemble (embeddings + santé)
2. **Search** - Recherche simple (conversations + code)
3. **Graph** - Visualisation interactive (Cytoscape.js)
4. **Logs** - Viewer avec filtres

**Focus**: Valeur core, pas features flashy

---

## 🎯 Features Clés (SIMPLIFIÉES)

### 1. Navigation Unifiée 🧭
- Navbar sticky avec 4 liens (Dashboard, Search, Graph, Logs)
- Active state (highlight page actuelle)
- NO responsive mobile (desktop-first, MVP)
- NO dark mode toggle (post-MVP)

### 2. Dashboard Simple 📊
- **2 Embedding Cards**: TEXT + CODE (model, count, last indexed)
- **Services Health**: API, PostgreSQL, Redis (green/red badges)
- **Manual Refresh** button (NO SSE, NO live updates)
- NO activity charts
- NO alerts widget
- NO quick actions

### 3. Recherche Simple 🔍
- Single search bar
- Call existing `/api/v1/search` endpoint (already exists!)
- Results list (conversations + code)
- Filter by type (all/conversations/code)
- NO instant preview dropdown
- NO advanced filters

### 4. Graph Interactif 🕸️
- Cytoscape.js integration
- 1 layout algorithm (Force-directed)
- Zoom/pan controls
- Click node → show info panel
- NO multiple layouts
- NO path finding
- NO export SVG/PNG

### 5. Logs Viewer 📝
- Table view (timestamp, level, source, message)
- Filters: level (error/warn/info), source
- Pagination (50 logs/page)
- Manual refresh button
- NO live streaming (SSE)
- NO alerts system

---

## 📊 Décomposition en Stories (7 stories, 23 pts)

### Phase 1: Foundation (8 pts, 2-3 semaines)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| **25.1** | Navbar + Routing (Vue Router, 4 links) | 2 pts | ✅ COMPLETE (2025-11-01) |
| **25.2** | Dashboard Backend API (health + embeddings) | 2 pts | ✅ COMPLETE (2025-11-01) |
| **25.3** | Dashboard Page (2 cards + health badges) | 4 pts | ✅ COMPLETE (2025-11-01) |

**Deliverables Phase 1**:
- ✅ Navbar with 4 links (sticky, active state)
- ✅ Dashboard page:
  - 2 embedding cards (TEXT + CODE)
  - 3 health badges (API, PostgreSQL, Redis)
  - Manual refresh button
- ✅ Backend API: `/api/v1/dashboard/health`, `/api/v1/dashboard/embeddings/{text,code}`

#### Story 25.1.5: Dark Theme Design System (Bonus) ✅
**Status**: COMPLETE
**Completion Date**: 2025-11-01
**Story Points**: Unestimated (bonus work)

**Deliverables**:
- ✅ Comprehensive design system with Tailwind CSS v4
- ✅ @theme directive with OKLCH color tokens
- ✅ @layer components for reusable patterns (cards, buttons, navigation, alerts, forms, badges)
- ✅ Applied dark theme to all existing components
- ✅ Research via Context7 MCP for Tailwind CSS v4 best practices

**Files Created**:
- `frontend/src/styles/theme.css` (~390 lines)

**Files Modified**:
- `frontend/src/style.css` (added theme import)
- `frontend/src/components/Navbar.vue` (uses nav-bar, nav-link classes)
- `frontend/src/components/DashboardCard.vue` (uses card-* classes)
- `frontend/src/components/HelloWorld.vue` (removed .card reference)
- `frontend/src/pages/Search.vue` (dark theme)
- `frontend/src/pages/Graph.vue` (dark theme)
- `frontend/src/pages/Logs.vue` (dark theme)

**Design System Components**:
- Cards: card-success, card-warning, card-error, card-info, card-neutral
- Buttons: btn-primary, btn-success, btn-danger, btn-ghost
- Navigation: nav-bar, nav-link, nav-link-active
- Alerts: alert-error, alert-warning, alert-success, alert-info
- Forms: input, label
- Badges: badge-success, badge-warning, badge-error, badge-info
- Text: text-heading, text-subheading
- Layout: section

**Technical Achievements**:
- Used MCP Context7 to retrieve official Tailwind CSS v4 documentation
- Implemented design tokens following best practices
- Created single source of truth for design values
- Professional dark monitoring aesthetic (slate-950 background, sharp corners)
- All components now use consistent design system

**Report**: See `EPIC-25_PHASE1_COMPLETION_REPORT.md`

---

### Phase 2: Search & Graph (10 pts, 3-4 semaines)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| **25.4** | Search Page (frontend for existing API) | 5 pts | 🔴 PENDING |
| **25.5** | Graph Page (Cytoscape.js, 1 layout) | 5 pts | 🔴 PENDING |

**Deliverables Phase 2**:
- ✅ Search page:
  - Search bar + submit button
  - Results list (grouped by type)
  - Type filter (all/conversations/code)
  - Pagination
  - Uses existing `/api/v1/search` endpoint
- ✅ Graph page:
  - Cytoscape.js canvas
  - Force-directed layout
  - Zoom/pan controls
  - Click node → details panel
  - Uses existing `/api/v1/graph` endpoint

---

### Phase 3: Logs & Polish (5 pts, 1-2 semaines)

| Story | Description | Points | Status |
|-------|-------------|--------|--------|
| **25.6** | Logs Viewer (table + filters) | 3 pts | 🔴 PENDING |
| **25.7** | Testing + Polish | 2 pts | 🔴 PENDING |

**Deliverables Phase 3**:
- ✅ Logs page:
  - Table view (timestamp, level, source, message)
  - Filters (level, source)
  - Pagination (50/page)
  - Manual refresh
  - Backend: `/api/v1/logs?level=&source=&limit=50&offset=0`
- ✅ Testing:
  - Composables unit tests
  - Components tests
  - E2E smoke tests (basic navigation)
- ✅ Polish:
  - Loading states
  - Error handling
  - Responsive fixes (if critical)

---

## 🏗️ Architecture Technique

### Stack Frontend ✅ DÉCIDÉ

**Core**:
```yaml
Framework: Vue.js 3.5+ (Composition API + <script setup>)
Build: Vite 7.0.0
Language: TypeScript 5.7+
Package Manager: PNPM
Router: Vue Router 4
```

**UI**:
```yaml
CSS: TailwindCSS 3.4+
Icons: Heroicons
Graph: Cytoscape.js 3.32+
# NO Shadcn-Vue (YAGNI)
# NO Chart.js (no charts in MVP)
```

**State & Utils**:
```yaml
State: Pinia 2.3+ (if needed, otherwise use ref/reactive)
# NO VueUse (add only if specific need)
```

**Quality**:
```yaml
Testing: Vitest 3.0+
Linting: ESLint + Prettier
# NO Biome (keep standard tools)
```

**Total**: 8 core dependencies (simple, proven, stable)

### Architecture Pattern: Composables + Components

```
frontend/src/
├── composables/              # 🧠 BUSINESS LOGIC
│   ├── useDashboard.ts       # Dashboard refresh
│   ├── useEmbeddings.ts      # Fetch embeddings stats
│   ├── useHealth.ts          # Services health check
│   ├── useSearch.ts          # Search functionality
│   ├── useGraph.ts           # Graph data + Cytoscape
│   ├── useLogs.ts            # Logs fetching + filtering
│   └── useApi.ts             # API client wrapper
│
├── components/               # 🎨 PRESENTATION (dumb, props-based)
│   ├── Navbar.vue
│   ├── EmbeddingCard.vue
│   ├── HealthBadge.vue
│   ├── SearchBar.vue
│   ├── SearchResults.vue
│   ├── GraphCanvas.vue
│   ├── NodeDetailsPanel.vue
│   └── LogsTable.vue
│
├── pages/                    # 📄 ORCHESTRATION (smart)
│   ├── Dashboard.vue         # Uses composables + components
│   ├── Search.vue
│   ├── Graph.vue
│   └── Logs.vue
│
├── utils/
│   └── api.ts                # Axios/fetch wrapper
│
├── router.ts
├── App.vue
└── main.ts
```

**Best Practices**:
- ✅ Composables = ALL business logic (fetch, state, side effects)
- ✅ Components = ONLY presentation (props, emits, no logic)
- ✅ Pages = Orchestration (use composables + components)
- ✅ Flat structure (2 levels max)

### Stack Backend (Inchangé)

```yaml
FastAPI: Python 3.11+
Database: PostgreSQL 18 + pgvector 0.8.1
Cache: Redis
```

**Endpoints** (most already exist):
- `GET /api/v1/dashboard/health` - Services health (NEW)
- `GET /api/v1/dashboard/embeddings/text` - TEXT stats (NEW)
- `GET /api/v1/dashboard/embeddings/code` - CODE stats (NEW)
- `GET /api/v1/search` - Unified search (EXISTS - EPIC-14)
- `GET /api/v1/graph` - Graph data (EXISTS)
- `GET /api/v1/logs` - Logs with filters (NEW)

**New Endpoints**: Only 4 (dashboard health + embeddings + logs)

### Real-Time Strategy

**No SSE for MVP**:
- Manual refresh buttons
- Polling acceptable (every 30s if needed)
- SSE = post-MVP enhancement

**Reason**: KISS - SSE adds complexity (reconnect, buffering, error handling)

---

## 📈 Progression

### Points Tracking

| Phase | Stories | Points | Status | % |
|-------|---------|--------|--------|---|
| Phase 1 | 3/3 | 8/8 pts | ✅ COMPLETE | 100% |
| Phase 2 | 0/2 | 0/10 pts | 🔴 PENDING | 0% |
| Phase 3 | 0/2 | 0/5 pts | 🔴 PENDING | 0% |
| **TOTAL** | **3/7** | **8/23 pts** | 🚧 IN PROGRESS | **35%** |

**Velocity estimée**: 10-12 pts/mois (solo dev)
**Timeline**: 6-9 semaines

---

## 🚀 MVP Strategy

### MVP Focus

**Core Value**:
1. Navigation claire (navbar)
2. Vue d'ensemble (dashboard)
3. Recherche facile (search)
4. Exploration code (graph)
5. Debug info (logs)

**NOT in MVP** (post-EPIC-25):
- ❌ Dark mode
- ❌ Mobile responsive
- ❌ Live updates (SSE)
- ❌ Activity charts
- ❌ Alerts system
- ❌ Settings page
- ❌ Instant search preview
- ❌ Multiple graph layouts
- ❌ Path finding
- ❌ Export features

**Keep for EPIC-26**: Post-MVP enhancements

---

## ⚠️ Risques & Mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| **Cytoscape perf (>1000 nodes)** | Medium | Medium | Virtual rendering, lazy load |
| **Search API changes** | Low | Low | API already stable (EPIC-14) |
| **Scope creep** | High | Medium | Strict YAGNI enforcement |
| **Time estimation** | Medium | Medium | Buffer +20% built-in |

---

## 📝 Dépendances

### Backend Dependencies

- ✅ EPIC-23 (MCP Integration) - Complete
- ⚠️ EPIC-14 (Search) - Partial (need `/api/v1/search` endpoint)
- ⚠️ Code graph - Partial (need `/api/v1/graph` endpoint)

**Action**: Verify endpoints exist before Phase 2

### No Hard Blockers

All essential endpoints either exist or are simple additions (health, embeddings, logs).

---

## 🎯 Success Metrics

### User Experience

- **Navigation**: <2 clicks to any feature ✅
- **Dashboard load**: <1 second ✅
- **Search response**: <500ms ✅
- **Graph render**: <2 seconds (1000 nodes) ✅

### Technical

- **Test coverage**: >70% composables ✅
- **Build size**: <500 KB (gzipped) ✅
- **Zero TypeScript errors** ✅
- **Accessible**: Semantic HTML, keyboard nav ✅

### Business

- **Time to MVP**: 6-9 semaines ✅
- **Scope delivered**: 100% core features ✅
- **Tech debt**: Minimal (clean code, composables) ✅

---

## 📚 Documents Liés

- **[CRITICAL REVIEW]** `EPIC-25_CRITICAL_REVIEW.md` - KISS/YAGNI analysis
- **[BEST PRACTICES]** `EPIC-25_VUE3_BEST_PRACTICES.md` - Composables pattern
- **[TECH STACK]** `EPIC-25_TECH_STACK_ANALYSIS.md` - Vue.js 3 + Vite + PNPM research
- **[ARCHIVED FULL SCOPE]** `EPIC-25_FULL_SCOPE_ARCHIVED.md` - Original 87 pts scope
- **[COMPLETION REPORT]** `EPIC-25_PHASE1_COMPLETION_REPORT.md` - Phase 1 (Stories 25.1-25.3 + Design System)

---

## ✅ Acceptance Criteria (EPIC-25 MVP)

**Core Functionality**:
- [ ] Navbar unifiée sur toutes les pages (sticky, active state)
- [ ] Dashboard affiche 2 types embeddings (TEXT + CODE)
- [ ] Dashboard affiche services health (API, PostgreSQL, Redis)
- [ ] Search page fonctionne (appelle `/api/v1/search`)
- [ ] Graph interactif (Cytoscape, zoom, pan, click node)
- [ ] Logs viewer avec filtres (level, source, pagination)

**Quality**:
- [ ] Tests >70% coverage (composables)
- [ ] Zero TypeScript errors
- [ ] Loading states sur toutes les actions async
- [ ] Error handling sur tous les API calls
- [ ] Build bundle <500 KB (gzipped)

**Documentation**:
- [ ] README frontend (setup, dev, build, test)
- [ ] Composables documented (JSDoc)
- [ ] API endpoints documented (OpenAPI)

---

## 📅 Timeline Détaillé

### Semaine 1-2: Phase 1 (Foundation)

**Week 1**:
- Setup project (Vite + Vue.js 3 + TypeScript + PNPM)
- Configure TailwindCSS, Vue Router, ESLint, Prettier
- Create base components (Navbar, layouts)
- Story 25.1: Navbar + Routing ✅

**Week 2**:
- Story 25.2: Dashboard Backend API (health + embeddings) ✅
- Story 25.3: Dashboard Page (composables + components) ✅
- Tests: composables unit tests

**Deliverable**: Dashboard functional avec navigation

---

### Semaine 3-6: Phase 2 (Search & Graph)

**Week 3-4**:
- Story 25.4: Search Page
  - `useSearch` composable
  - SearchBar, SearchResults components
  - Wire up to existing `/api/v1/search`
- Tests: search composable + components

**Week 5-6**:
- Story 25.5: Graph Page
  - `useGraph` composable
  - GraphCanvas, NodeDetailsPanel components
  - Cytoscape.js integration
- Tests: graph interactions

**Deliverable**: Search + Graph functional

---

### Semaine 7-9: Phase 3 (Logs & Polish)

**Week 7**:
- Story 25.6: Logs Viewer
  - `useLogs` composable
  - LogsTable component
  - Backend: `/api/v1/logs` endpoint
- Tests: logs composable

**Week 8**:
- Story 25.7: Testing + Polish
  - E2E smoke tests
  - Error handling improvements
  - Loading states polish
  - Performance optimization

**Week 9**:
- Buffer week (bug fixes, documentation)
- Final testing
- Deployment prep

**Deliverable**: MVP complete, tested, documented

---

## 🔧 Implementation Roadmap

### Setup (Day 1-2)

```bash
# Create project
pnpm create vite@latest mnemolite-frontend --template vue-ts
cd mnemolite-frontend

# Install dependencies
pnpm install
pnpm add vue-router pinia cytoscape
pnpm add -D @types/node tailwindcss autoprefixer vitest @vue/test-utils

# Setup TailwindCSS
npx tailwindcss init -p

# Configure aliases, routing
```

### Development Workflow

```bash
# Dev server
pnpm dev          # → http://localhost:5173

# Testing
pnpm test         # Vitest watch mode
pnpm test:ci      # CI mode (run once)

# Linting
pnpm lint         # ESLint
pnpm format       # Prettier

# Build
pnpm build        # → dist/
pnpm preview      # Preview build
```

### Story Implementation Order

1. ✅ Navbar + Routing (Story 25.1)
2. ✅ Dashboard API (Story 25.2)
3. ✅ Dashboard Page (Story 25.3)
4. ✅ Search Page (Story 25.4)
5. ✅ Graph Page (Story 25.5)
6. ✅ Logs Viewer (Story 25.6)
7. ✅ Testing + Polish (Story 25.7)

---

## 🎓 Key Learnings from Critical Review

### What We Removed (YAGNI)

- ❌ 38 pts of YAGNI features (44% of original scope!)
- ❌ Shadcn-Vue (TailwindCSS suffices)
- ❌ VueUse (add only if needed)
- ❌ Biome (ESLint + Prettier standard)
- ❌ Chart.js (no charts in MVP)
- ❌ SSE streaming (manual refresh suffices)
- ❌ Settings page (.env config suffices)
- ❌ Dark mode, mobile responsive (post-MVP)

### What We Kept (Core Value)

- ✅ Navigation (navbar + routing)
- ✅ Dashboard (embeddings + health)
- ✅ Search (simple, functional)
- ✅ Graph (interactive, basic)
- ✅ Logs (viewer with filters)

**Result**: 73% scope reduction, 100% core value delivered

---

## 🔗 Liens Rapides

- **Repository**: `/home/giak/Work/MnemoLite`
- **Frontend**: `frontend/` (à créer)
- **Backend**: `api/`
- **Documentation**: `docs/agile/serena-evolution/03_EPICS/`

---

**Status**: 🚧 IN PROGRESS (Phase 1 Complete)
**Next Step**: Phase 2 - Search Page (Story 25.4)
**Owner**: Christophe Giacomel
**Support**: Claude Code

**Dernière mise à jour**: 2025-11-01
**Version**: 2.1 (Phase 1 Complete - 8/23 pts)ok, i
