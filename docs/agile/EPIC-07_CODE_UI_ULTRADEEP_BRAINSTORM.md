# EPIC-07 ULTRADEEP BRAINSTORM: Code Intelligence UI Extensions

**Date**: 2025-10-16
**Version**: 1.0 - ULTRADEEP THINKING
**Dependencies**: EPIC-06 (Code Intelligence) - COMPLETE ✅
**Approach**: Minimal extensions to existing UI, zero over-engineering

---

## 🧠 ULTRADEEP ANALYSIS: Current State

### Existing UI Infrastructure ✅

**Technology Stack** (Already in place):
- **Backend**: FastAPI + Jinja2 Templates
- **Frontend**: HTMX (dynamic updates without page reloads)
- **Styling**: Custom CSS (SCADA-style dark theme)
- **Graph Viz**: Cytoscape.js (already integrated!)
- **Components**: Modular JS (`static/js/components/`)

**Existing Pages**:
```
/ui/                    → Dashboard (events timeline)
/ui/search              → Semantic search (memories/events)
/ui/graph               → Graph visualization (events/entities/concepts)
/ui/monitoring          → Real-time monitoring dashboard
/ui/events/{id}         → Event detail view
```

**Existing Components**:
```javascript
static/js/components/
├── filters.js          (5.4 KB) - Dynamic filter management
├── graph.js            (16 KB)  - Cytoscape.js graph with minimap
└── monitoring.js       (12 KB)  - Real-time monitoring charts
```

### EPIC-06 API Endpoints (Code Intelligence) ✅

**Code Indexing**:
- `POST /v1/code/index` - Index files
- `GET /v1/code/index/repositories` - List repos
- `DELETE /v1/code/index/repositories/{repo}` - Delete repo
- `GET /v1/code/index/health` - Health check

**Code Search**:
- `POST /v1/code/search/hybrid` - Hybrid search (lexical + vector + RRF)
- `POST /v1/code/search/lexical` - Lexical only
- `POST /v1/code/search/vector` - Semantic only
- `GET /v1/code/search/health` - Health check

**Dependency Graph**:
- `POST /v1/code/graph/build` - Build graph from repository
- `POST /v1/code/graph/traverse` - Traverse from node
- `POST /v1/code/graph/path` - Find path between nodes
- `GET /v1/code/graph/stats/{repo}` - Graph statistics

---

## 🎯 CRITICAL INSIGHT: The Gap

**What exists**: UI for **memory/events** (dashboard, search, graph for events/entities)

**What's missing**: UI for **code intelligence** (code search, code graphs, code repos)

**The Problem**: EPIC-06's powerful code intelligence features are invisible to users!

---

## 💡 STRATEGY: Extend, Don't Rebuild

### Principle 1: REUSE EXISTING PATTERNS
- ✅ Keep HTMX + Jinja2 (no React!)
- ✅ Keep Cytoscape.js for graphs
- ✅ Keep SCADA dark theme
- ✅ Keep modular JS components

### Principle 2: MINIMAL NEW CODE
- ✅ Add new routes to `ui_routes.py`
- ✅ Create new templates (reusing `base.html`)
- ✅ Create new JS component (`code_graph.js`)
- ❌ NO new frameworks
- ❌ NO major refactoring

### Principle 3: PROGRESSIVE DISCLOSURE
- Start with basics (repo management, code search)
- Add advanced features later (graph viz, analytics)
- Each feature = standalone page

---

## 📋 EPIC-07 Stories: Surgical Extensions

### Story 1: Code Repository Manager (5 pts)
**Duration**: 2 days

**Goal**: UI to manage indexed code repositories

**What to Create**:
1. New template: `templates/code_repos.html`
2. New route in `ui_routes.py`: `@router.get("/code/repos")`
3. New partial: `templates/partials/repo_list.html`
4. Reuse: Existing table styles, HTMX patterns

**UI Features**:
- Table showing all repositories (name, file count, chunk count, last indexed)
- "Delete" button per repository (with confirmation modal)
- "Reindex" button (future)
- Language distribution per repo (simple badges)
- Link to code search filtered by repo

**Endpoints Used**:
- `GET /v1/code/index/repositories`
- `DELETE /v1/code/index/repositories/{repo}`

**Complexity**: LOW (just CRUD table with HTMX)

**Mockup**:
```
┌────────────────────────────────────────────────────┐
│ Code Repositories                         [+ Add]  │
├────────────────────────────────────────────────────┤
│ Repository       Files  Chunks  Languages  Actions │
│ ─────────────────────────────────────────────────  │
│ my-project         127     543  🐍 Python   [🗑️]   │
│ other-repo          45     189  📜 JS       [🗑️]   │
│ test-code           12      38  🦀 Rust     [🗑️]   │
└────────────────────────────────────────────────────┘
```

---

### Story 2: Code Search Interface (8 pts)
**Duration**: 3-4 days

**Goal**: Search indexed code with hybrid/lexical/vector modes

**What to Create**:
1. New template: `templates/code_search.html`
2. New route: `@router.get("/code/search")`
3. New route: `@router.get("/code/search/results")` (HTMX target)
4. New partial: `templates/partials/code_results.html`
5. Extend: `static/js/components/filters.js` (add code filters)

**UI Features**:
- Search bar (like existing `/ui/search`)
- Mode selector: Hybrid / Lexical / Vector (radio buttons)
- Filters:
  - Repository (dropdown)
  - Language (checkboxes: Python, JS, etc.)
  - Complexity range (slider)
- Results display:
  - Function/class name (bold)
  - File path (breadcrumb)
  - Code snippet (syntax highlighted using Prism.js)
  - Relevance score (badge)
  - Metadata: complexity, parameters count
  - "View full file" button

**Endpoints Used**:
- `POST /v1/code/search/hybrid`
- `POST /v1/code/search/lexical`
- `POST /v1/code/search/vector`
- `GET /v1/code/index/repositories` (for repo filter)

**Complexity**: MEDIUM (search modes + syntax highlighting)

**Syntax Highlighting**: Use Prism.js (lightweight, 2KB)
```html
<link href="https://unpkg.com/prismjs@1.29.0/themes/prism-tomorrow.css" rel="stylesheet" />
<script src="https://unpkg.com/prismjs@1.29.0/prism.js"></script>
<script src="https://unpkg.com/prismjs@1.29.0/components/prism-python.min.js"></script>
```

**Mockup**:
```
┌────────────────────────────────────────────────────────┐
│ Code Search            [  Search query...  ] [Search] │
├────────────────────────────────────────────────────────┤
│ Mode: ◉ Hybrid  ○ Lexical  ○ Vector                   │
│                                                         │
│ Filters:  [Repository ▼] [Python ☑] [Complexity: 5▓░] │
├────────────────────────────────────────────────────────┤
│ Results (15)                                            │
│                                                         │
│ ┌─────────────────────────────────────────────────┐    │
│ │ ⭐ 0.95 - calculate_total(items)                │    │
│ │ src/utils.py:42                         C: 5    │    │
│ │ ┌───────────────────────────────────────────┐   │    │
│ │ │ def calculate_total(items):               │   │    │
│ │ │     """Calculate total of items"""        │   │    │
│ │ │     return sum(items)                     │   │    │
│ │ └───────────────────────────────────────────┘   │    │
│ │ Parameters: 1 | Returns: int | Calls: sum       │    │
│ │                             [View Full File]     │    │
│ └─────────────────────────────────────────────────┘    │
│                                                         │
│ [Page 1 of 2] →                                        │
└────────────────────────────────────────────────────────┘
```

---

### Story 3: Code Dependency Graph (13 pts)
**Duration**: 5-6 days

**Goal**: Visualize function/class dependencies using existing graph.js

**What to Create**:
1. New template: `templates/code_graph.html` (clone `graph.html`)
2. New route: `@router.get("/code/graph")`
3. New API endpoint in `ui_routes.py`: `@router.get("/code/graph/data")`
4. New JS component: `static/js/components/code_graph.js` (extend `graph.js`)

**CRITICAL REUSE**:
- ✅ Copy `templates/graph.html` → `templates/code_graph.html`
- ✅ Copy `static/js/components/graph.js` → `static/js/components/code_graph.js`
- ✅ Modify Cytoscape.js config for code nodes/edges
- ✅ Keep ALL existing SCADA styling

**UI Adaptations**:

**Node Types** (replace event/entity/concept):
- `function` (blue) - Function definitions
- `class` (red) - Class definitions
- `method` (cyan) - Class methods

**Node Data**:
```javascript
{
  id: 'func_calculate_total',
  label: 'calculate_total',
  type: 'function',
  complexity: 5,
  file: 'src/utils.py',
  line: 42,
  params: ['items'],
  calls: ['sum', 'add']
}
```

**Edge Data**:
```javascript
{
  source: 'func_calculate_total',
  target: 'func_add',
  type: 'calls'
}
```

**Left Sidebar Changes**:
- Replace "Node Types" filters:
  - ☑ Functions (blue)
  - ☑ Classes (red)
  - ☑ Methods (cyan)
- Add "Repository" filter (dropdown)
- Add "Complexity" filter (slider)
- Keep layout controls (unchanged)

**Right Sidebar (Node Detail)**:
- Function name
- File path + line number
- Complexity score
- Parameters list
- Return type
- Calls list (clickable to navigate)
- "View source" button → opens code search

**Endpoints Used**:
- `POST /v1/code/graph/build` - Build graph for repo
- `POST /v1/code/graph/traverse` - Expand node dependencies
- `GET /v1/code/graph/stats/{repo}` - Stats for KPI cards
- `GET /v1/code/index/repositories` - Repo filter

**Complexity**: MEDIUM-HIGH (reusing Cytoscape.js but adapting data structure)

**Key Code Changes in `code_graph.js`**:
```javascript
// Change API endpoint
const API_ENDPOINT = '/v1/code/graph/build';

// Change node colors
const NODE_COLORS = {
  function: '#667eea',  // blue
  class: '#f5576c',     // red
  method: '#00f2fe'     // cyan
};

// Change node size by complexity
node: {
  'width': 'mapData(complexity, 1, 20, 30, 60)',
  'height': 'mapData(complexity, 1, 20, 30, 60)',
  ...
}
```

**Mockup**: (Same as existing graph.html but with code nodes)

---

### Story 4: Code Upload Interface (8 pts)
**Duration**: 3-4 days

**Goal**: UI to upload code files for indexing

**What to Create**:
1. New template: `templates/code_upload.html`
2. New route: `@router.get("/code/upload")`
3. New route: `@router.post("/code/upload")` (handle file upload)
4. Progress indicator (HTMX + SSE for real-time updates - optional)

**UI Features**:
- Drag & drop area for files/folders
- File list preview (before indexing)
- Repository name input
- Language detection preview
- "Index" button
- Progress bar (files indexed / total)
- Success/error messages

**Options**:
- ☑ Extract metadata
- ☑ Generate embeddings
- ☑ Build graph

**Endpoints Used**:
- `POST /v1/code/index` - Index uploaded files

**Complexity**: MEDIUM (file handling + progress tracking)

**Implementation Notes**:
- Use `<input type="file" multiple accept=".py,.js,.ts,.go,.rs">`
- Read files with JavaScript FileReader API
- Send to backend as JSON (file path + content)
- Show progress with HTMX polling or WebSocket (phase 2)

**Mockup**:
```
┌────────────────────────────────────────────────────┐
│ Upload Code for Indexing                          │
├────────────────────────────────────────────────────┤
│                                                     │
│  ┌───────────────────────────────────────────┐    │
│  │  📂 Drag & drop files here                │    │
│  │     or click to browse                    │    │
│  │                                            │    │
│  │  Supported: .py .js .ts .go .rs .java ... │    │
│  └───────────────────────────────────────────┘    │
│                                                     │
│  Repository name: [my-project            ]         │
│                                                     │
│  Files (3):                                        │
│  ☑ main.py         (Python)   342 lines            │
│  ☑ utils.py        (Python)   128 lines            │
│  ☑ config.js       (JS)        45 lines            │
│                                                     │
│  Options:                                          │
│  ☑ Extract metadata  ☑ Generate embeddings         │
│  ☑ Build dependency graph                          │
│                                                     │
│  [Cancel]                      [Index Files]       │
│                                                     │
└────────────────────────────────────────────────────┘
```

---

### Story 5: Code Analytics Dashboard (5 pts)
**Duration**: 2 days

**Goal**: Visual metrics for indexed code

**What to Create**:
1. New template: `templates/code_dashboard.html`
2. New route: `@router.get("/code/")`
3. Reuse: KPI cards from `monitoring.html`
4. Add: Simple charts (Chart.js - lightweight)

**UI Features**:
- Summary cards:
  - Total repositories
  - Total files indexed
  - Total functions/classes
  - Average complexity
- Language distribution (pie chart)
- Complexity distribution (histogram)
- Top 10 most complex functions (table)
- Recent indexing activity (timeline)

**Endpoints Used**:
- `GET /v1/code/index/repositories`
- `GET /v1/code/graph/stats/{repo}` (for each repo)
- Custom aggregation in route handler

**Complexity**: LOW-MEDIUM (mostly data aggregation + charts)

**Charts**: Use Chart.js (35 KB, already similar to monitoring.js approach)

**Mockup**:
```
┌────────────────────────────────────────────────────┐
│ Code Intelligence Dashboard                       │
├────────────────────────────────────────────────────┤
│                                                     │
│ [Repos: 5]  [Files: 312]  [Functions: 1,234]      │
│ [Avg Complexity: 6.2]  [Last Indexed: 2h ago]     │
│                                                     │
│ ┌────────────┐  ┌──────────────────────────────┐  │
│ │ Languages  │  │ Complexity Distribution      │  │
│ │            │  │                              │  │
│ │ 🐍 45%     │  │  █                           │  │
│ │ 📜 30%     │  │  █                           │  │
│ │ 🦀 15%     │  │ ██                           │  │
│ │ ☕ 10%     │  │███                           │  │
│ │            │  │ 0  5  10  15  20             │  │
│ └────────────┘  └──────────────────────────────┘  │
│                                                     │
│ Top 10 Most Complex Functions:                    │
│ 1. parse_ast() - parser.py:145 - C: 18            │
│ 2. render_graph() - viz.py:89 - C: 15             │
│ ...                                                │
└────────────────────────────────────────────────────┘
```

---

### Story 6: Navigation Integration (2 pts)
**Duration**: 1 day

**Goal**: Add code intelligence to main navigation

**What to Modify**:
1. Update `templates/base.html` navigation
2. Add "Code" section in navbar

**Navigation Structure**:
```
MnemoLite
├── Memory (existing)
│   ├── Dashboard
│   ├── Search
│   ├── Graph
│   └── Monitoring
└── Code (NEW)
    ├── Dashboard     → /ui/code/
    ├── Repositories  → /ui/code/repos
    ├── Search        → /ui/code/search
    ├── Graph         → /ui/code/graph
    └── Upload        → /ui/code/upload
```

**Complexity**: TRIVIAL (just nav links)

---

## 📊 Total Estimation

| Story | Description | Points | Days | Type |
|-------|-------------|--------|------|------|
| **1** | Repository Manager | 5 | 2 | CRUD Table |
| **2** | Code Search | 8 | 3-4 | Search + Filters |
| **3** | Dependency Graph | 13 | 5-6 | Graph Viz |
| **4** | Code Upload | 8 | 3-4 | File Upload |
| **5** | Analytics Dashboard | 5 | 2 | Charts |
| **6** | Navigation | 2 | 1 | UI Polish |
| **TOTAL** | **EPIC-07** | **41 pts** | **16-19 days** | - |

**Velocity**: ~2.5 pts/day (conservative)

---

## 🎨 Design System Reuse

### Colors (SCADA Theme - Already defined)
```css
Background:     #0a0e27, #0d1117, #161b22
Borders:        #21262d, #30363d
Primary:        #20e3b2 (green)
Secondary:      #4a90e2 (blue)
Accent:         #667eea (violet), #f5576c (red), #00f2fe (cyan)
Text:           #c9d1d9 (light), #6e7681 (muted)
```

### Components (Already built)
- KPI Cards (from monitoring.html)
- Filter sidebar (from graph.html)
- Search bar (from search.html)
- Table styles (from dashboard.html)
- HTMX partials pattern (from all pages)

### Fonts (Already loaded)
```css
font-family: 'SF Mono', Consolas, monospace; /* Code */
font-family: -apple-system, BlinkMacSystemFont, sans-serif; /* UI */
```

---

## 🔧 Technical Implementation Plan

### Phase 1: Foundation (Story 6 + 1)
**Duration**: 3 days
1. Add navigation links
2. Create repository manager
3. Test EPIC-06 API integration

### Phase 2: Search (Story 2)
**Duration**: 4 days
1. Create search page
2. Add syntax highlighting
3. Implement filters
4. Test all 3 search modes

### Phase 3: Advanced (Story 3 + 5)
**Duration**: 8 days
1. Adapt graph visualization for code
2. Add code analytics dashboard
3. Integration testing

### Phase 4: Upload & Polish (Story 4)
**Duration**: 4 days
1. Build upload interface
2. End-to-end testing
3. Documentation

---

## 💾 Files to Create/Modify

### New Templates (6 files)
```
templates/
├── code_dashboard.html       (Story 5)
├── code_repos.html           (Story 1)
├── code_search.html          (Story 2)
├── code_graph.html           (Story 3)
├── code_upload.html          (Story 4)
└── partials/
    ├── code_results.html     (Story 2)
    └── repo_list.html        (Story 1)
```

### Modified Templates (1 file)
```
templates/base.html           (Story 6 - add nav)
```

### New JavaScript (1 file)
```
static/js/components/
└── code_graph.js             (Story 3 - clone graph.js)
```

### Modified Python (1 file)
```
api/routes/ui_routes.py       (All stories - add routes)
```

**Total New Files**: 8
**Total Modified Files**: 2
**Total Lines of Code**: ~1,500 (mostly HTML/CSS reuse)

---

## 🚨 Critical Success Factors

### 1. REUSE EXISTING PATTERNS ✅
- **DO**: Copy graph.html → code_graph.html
- **DON'T**: Build new graph from scratch

### 2. MINIMAL BACKEND CHANGES ✅
- **DO**: Add routes to ui_routes.py
- **DON'T**: Modify EPIC-06 services

### 3. PROGRESSIVE DISCLOSURE ✅
- **DO**: Ship Story 1-2 early (80% value)
- **DON'T**: Wait for all stories

### 4. HTMX CONSISTENCY ✅
- **DO**: Use HTMX for all dynamic updates
- **DON'T**: Mix HTMX + vanilla AJAX

### 5. SCADA THEME ADHERENCE ✅
- **DO**: Reuse existing CSS classes
- **DON'T**: Invent new color schemes

---

## 🎯 MVP Definition (Minimum Viable Product)

**MVP = Stories 1, 2, 6** (15 pts, ~7 days)

**What's included**:
- ✅ Repository management
- ✅ Code search (hybrid/lexical/vector)
- ✅ Navigation integration

**What's deferred**:
- ⏳ Graph visualization (Story 3)
- ⏳ Upload interface (Story 4)
- ⏳ Analytics dashboard (Story 5)

**Why this MVP**:
- Delivers 80% of user value
- Proves EPIC-06 integration
- Fast feedback loop (1 week)
- Low risk (reuses all patterns)

---

## 📈 Success Metrics

### Functional
- ✅ All EPIC-06 endpoints accessible via UI
- ✅ Code search returns results < 2 seconds
- ✅ Syntax highlighting renders correctly
- ✅ Graph displays 100+ nodes smoothly

### Non-Functional
- ✅ Consistent with existing UI design
- ✅ No new framework dependencies
- ✅ Mobile-friendly (responsive)
- ✅ Keyboard navigation works

### Business
- ✅ Developers can find code 10x faster than grep
- ✅ Dependency visualization reveals hidden connections
- ✅ Complexity metrics guide refactoring priorities

---

## 🔮 Future Enhancements (Post-EPIC-07)

### Phase 2 Features
1. **Real-time Indexing Progress**: WebSocket for live updates
2. **Git Integration**: Auto-index on `git push`
3. **Diff View**: Compare indexed versions
4. **Code Annotations**: Add comments to functions
5. **Export**: Download search results / graphs

### Advanced Analytics
1. **Complexity Trends**: Track over time
2. **Code Churn Heatmap**: Most edited files
3. **Dead Code Detection**: Unused functions
4. **Circular Dependency Detection**: Highlight in red

### AI Features (Future)
1. **AI Code Explanations**: GPT-4 integration
2. **Similar Code Search**: "Find code like this"
3. **Refactoring Suggestions**: Based on complexity
4. **Auto-tagging**: ML-based categorization

---

## ❓ Open Questions

### Q1: Syntax Highlighting Library?
**Options**:
- Prism.js (2 KB, simple)
- Highlight.js (23 KB, more languages)
- Monaco Editor (500 KB, full editor)

**Recommendation**: Prism.js (sufficient for code snippets)

### Q2: Real-time Progress for Upload?
**Options**:
- Polling (simple, works everywhere)
- WebSocket (complex, better UX)
- Server-Sent Events (middle ground)

**Recommendation**: Polling for MVP, WebSocket in phase 2

### Q3: Authentication?
**Current**: No auth on `/ui/` routes
**Future**: Add auth in separate EPIC?

**Recommendation**: Defer to EPIC-08 (Security & Auth)

---

## 🎬 Next Steps

### Option A: Start MVP (Stories 1, 2, 6)
**Duration**: 7 days
**ROI**: High (80% value, 37% effort)

### Option B: Design First
**Duration**: 2 days (Figma mockups)
**ROI**: Medium (reduces rework)

### Option C: Prototype Story 3 Only
**Duration**: 6 days (prove graph visualization)
**ROI**: Medium (validates hardest part)

---

## 📝 Summary: The Ultradeep Truth

**What we have**:
- ✅ Solid UI foundation (HTMX + Jinja2 + Cytoscape.js)
- ✅ Complete EPIC-06 backend APIs
- ✅ SCADA design system
- ✅ Modular JS components

**What we need**:
- 📄 8 new template files
- 🔧 1 new JS file (copy of graph.js)
- 🔌 ~15 new routes in ui_routes.py
- 🎨 Zero new CSS (reuse existing)

**What we DON'T need**:
- ❌ React/Vue/Svelte
- ❌ New CSS framework
- ❌ Major refactoring
- ❌ New graph library
- ❌ Backend changes

**The Philosophy**:
> "The best code is no code. The best UI is the one you already have."

**EPIC-07 = EPIC-06 made visible, using what MnemoLite already has.**

---

**Document Status**: ✅ READY FOR IMPLEMENTATION
**Next Action**: Choose MVP path (Option A recommended)
**Estimated Completion**: 7 days (MVP) or 19 days (full EPIC)

