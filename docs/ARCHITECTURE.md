# MnemoLite Architecture

**Version:** 5.0.0-dev | **Updated:** 2026-04-03

---

## 1. System Overview

MnemoLite is a PostgreSQL-native cognitive memory system with code intelligence and MCP integration. It runs as a Docker Compose stack of 7 services.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Vue 3 SPA  │───▶│  FastAPI    │───▶│ PostgreSQL  │
│  (port 3000)│    │  (port 8001)│    │   (port 5432)│
└─────────────┘    └──────┬──────┘    └─────────────┘
                          │
                    ┌─────┴─────┐    ┌─────────────┐
                    │    MCP    │    │   Redis 7   │
                    │(port 8002)│    │  (port 6379) │
                    └─────┬─────┘    └─────────────┘
                          │
                    ┌─────┴─────┐    ┌─────────────┐
                    │  Worker   │    │ OpenObserve │
                    │ (async)   │    │  (port 5080) │
                    └───────────┘    └─────────────┘
```

---

## 2. Service Topology

| Service | Container | Port | Dependencies | Purpose |
|---------|-----------|------|-------------|---------|
| **db** | mnemo-postgres | 5432 | — | PostgreSQL 18 + pgvector + pg_partman |
| **redis** | mnemo-redis | 6379 | — | L2 distributed cache |
| **api** | mnemo-api | 8001 | db, redis | FastAPI backend (main application) |
| **mcp** | mnemo-mcp | 8002 | db, redis | MCP server for LLM integration |
| **worker** | mnemo-worker | — | redis, api | Background conversation processing |
| **frontend** | mnemo-frontend | 3000 | api | Vue 3 dev server (dev profile) |
| **frontend-prod** | mnemo-frontend-prod | 80 | api | Nginx serving built SPA (prod profile) |
| **openobserve** | mnemo-openobserve | 5080 | — | Observability (logs, metrics, traces) |

**Docker Profiles:**
```bash
docker compose --profile dev up -d   # Dev: Vite HMR on :3000
docker compose --profile prod up -d  # Prod: Nginx on :80
```

---

## 3. API Architecture (FastAPI)

### Entry Point: `api/main.py`

The FastAPI app uses a **lifespan pattern** for async initialization:

1. **Database engine** — SQLAlchemy async with asyncpg, pool_size=20
2. **Embedding models** — DualEmbeddingService (TEXT + CODE, pre-loaded)
3. **Redis L2 cache** — Distributed cache with circuit breaker
4. **Error tracking** — Alert service for error pattern detection
5. **LSP managers** — Python + TypeScript language servers
6. **Monitoring** — Background task checking metrics every 60s

### Middleware Stack

```
Request → CORSMiddleware → MetricsMiddleware → RateLimitMiddleware → APIKeyMiddleware → Route → Response
```

### Route Structure (17 route modules)

| Route Module | Domain |
|-------------|--------|
| `event_routes` | Event CRUD |
| `search_routes` | Memory/event search |
| `code_search_routes` | Hybrid code search |
| `code_indexing_routes` | Code indexing operations |
| `code_graph_routes` | Code dependency graph |
| `cache_admin_routes` | Cache administration |
| `lsp_routes` | LSP type extraction |
| `health_routes` | Health checks |
| `graph_routes` | Conceptual graph |
| `monitoring_routes` | Metrics & alerts |
| `conversations_routes` | Auto-save conversations |
| `dashboard_routes` | Dashboard data |
| `batch_indexing_routes` | Redis Streams batch indexing |
| `indexing_error_routes` | Indexing error tracking |
| `memories_routes` | Memories monitoring |
| `projects_routes` | Projects management |
| `memories_routes` (MCP) | Memory CRUD + search |

---

## 4. MCP Architecture

### Server: `api/mnemo_mcp/server.py`

Built on **FastMCP** framework with two transports:
- **stdio** — for Claude Desktop / LLM integration
- **HTTP** (port 8002) — for web clients

### MCP Tools (28 tools)

| Category | Tools |
|----------|-------|
| **Code Search** | `search_code` — hybrid lexical+vector with RRF fusion |
| **Memory CRUD** | `write_memory`, `read_memory`, `update_memory`, `delete_memory` |
| **Memory Search** | `search_memory` — vector + lexical + tag-only optimization |
| **Memory Management** | `consolidate_memory`, `mark_consumed` |
| **Indexing** | `index_project`, `reindex_file`, `index_incremental`, `index_markdown_workspace` |
| **Indexing Observability** | `get_indexing_status`, `get_indexing_errors`, `retry_indexing` |
| **Analytics** | `get_indexing_stats`, `get_memory_health`, `get_cache_stats`, `clear_cache` |
| **Graph** | `get_graph_stats`, `traverse_graph`, `find_path`, `get_module_data` |
| **Configuration** | `switch_project`, `list_projects` |
| **System** | `system_snapshot`, `configure_decay`, `ping` |

### MCP Resources

| Resource URI | Purpose |
|-------------|---------|
| `health://status` | Server health (DB, Redis connectivity) |
| `memories://get/{id}` | Single memory by UUID |
| `memories://list` | List memories with filters |
| `memories://search/{query}` | Semantic memory search |
| `graph://nodes/{chunk_id}` | Node details with neighbors |
| `graph://callers/{qualified_name}` | Find all callers |
| `graph://callees/{qualified_name}` | Find all callees |
| `index://status/{repository}` | Indexing status |
| `cache://stats` | Cache statistics |
| `analytics://search` | Search analytics |
| `projects://list` | Available projects |
| `languages://supported` | Language support info |

---

## 5. Frontend Architecture

### Stack

- **Vue 3.5** + Composition API (`<script setup>`)
- **TypeScript** — strict mode
- **Vite 8** — dev server with HMR
- **Tailwind CSS 4** — utility-first styling
- **Pinia 3** — state management
- **Vue Router 4** — client-side routing

### Pages (14 routes)

| Route | Page | Purpose |
|-------|------|---------|
| `/dashboard` | Dashboard.vue | System overview, health metrics |
| `/search` | Search.vue | Code + memory search |
| `/memories` | Memories.vue | Memory management (3-column view) |
| `/projects` | Projects.vue | Project management (SCADA style) |
| `/expanse` | Expanse.vue | Expanse agent interface |
| `/expanse-memory` | ExpanseMemory.vue | Expanse memory taxonomy + modal detail |
| `/monitoring` | Monitoring.vue | Latency charts, alert summary |
| `/alerts` | Alerts.vue | Alert dashboard with filters + ACK |
| `/brain` | Brain.vue | Knowledge visualization |
| `/graph` | Graph.vue | Code dependency graph (v-network-graph + G6) |
| `/orgchart` | Orgchart.vue | Organizational chart (5 views) |
| `/logs` | Logs.vue | Service health + OpenObserve links |
| `/search-analytics` | SearchAnalytics.vue | Search performance analytics |

### Composables (14)

`useBrain`, `useCodeGraph`, `useCodeSearch`, `useDashboard`, `useExpanse`, `useExpanseMemory`, `useFullscreenResize`, `useMarkdown`, `useMemories`, `useMemorySearch`, `useMonitoring`, `useProjects`

### API Configuration

```typescript
// frontend/src/config/api.ts
const VITE_API_URL = import.meta.env.VITE_API_URL || ''
export const API = VITE_API_URL ? `${VITE_API_URL}/api/v1` : '/api/v1'
export const API_V1 = VITE_API_URL ? `${VITE_API_URL}/v1` : '/v1'
```

In dev mode, Vite proxies `/api` and `/v1` to the API server.

---

## 6. Database Architecture

### PostgreSQL Extensions

| Extension | Purpose |
|-----------|---------|
| **pgvector** | 768D vector embeddings with HNSW/IVFFlat indexes |
| **pg_partman** | Table partitioning (monthly, for events) |
| **pgcrypto** | `gen_random_uuid()` |
| **pg_trgm** | Trigram similarity for lexical search |

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `events` | Primary event/memory store | id, timestamp, content (JSONB), embedding (VECTOR 768), metadata (JSONB) |
| `memories` | Persistent memory store | id, title, content, tags[], memory_type, embedding, created_at |
| `code_chunks` | AST-parsed code units | id, file_path, content, text_embedding, code_embedding, metadata |
| `graph_nodes` | Code dependency graph | id, name, module, language, file_path, node_type |
| `graph_edges` | Code dependency edges | id, source_id, target_id, type, repository |
| `nodes` / `edges` | Conceptual graph | node_id, node_type, label, properties |
| `metrics` | System metrics | id, name, value, timestamp |
| `alerts` | Monitoring alerts | id, alert_type, severity, message, acknowledged |
| `memory_decay_config` | Tag decay rules | tag_pattern, decay_rate, half_life_days, priority_boost |

### Key Indexes

| Index | Table | Type | Purpose |
|-------|-------|------|---------|
| `idx_events_embedding` | events | HNSW | Vector similarity search |
| `idx_events_metadata_gin` | events | GIN (jsonb_path_ops) | Metadata filtering |
| `idx_memories_content_trgm` | memories | GIN (trigram) | Full-text lexical search |
| `idx_memories_title_trgm` | memories | GIN (trigram) | Title search |
| `idx_code_chunks_repository` | code_chunks | B-tree | Repository filtering |
| `idx_code_chunks_metadata_gin` | code_chunks | GIN | Metadata filtering |

---

## 7. Cache Architecture (3-Layer)

```
Request → L1 (In-Memory LRU, 100MB)
  HIT → return (<0.01ms)
  MISS → L2 (Redis, 2GB)
    HIT → promote to L1 → return (1-5ms)
    MISS → L3 (PostgreSQL)
      → populate L1+L2 → return (100-200ms)
```

| Layer | Location | Size | Strategy | Latency |
|-------|----------|------|----------|---------|
| **L1** | Process memory | 100MB | LRU + MD5 validation | <0.01ms |
| **L2** | Redis 7 | 2GB | TTL-based (30s-120s) | 1-5ms |
| **L3** | PostgreSQL | Unlimited | Source of truth | 100-200ms |

### Features

- **MD5 content validation** — zero stale data
- **Circuit breaker** — auto-recovers after Redis failures
- **Retry with backoff** — 3 attempts, 0.5s-5s
- **Graceful degradation** — continues without cache if Redis down
- **Per-repository invalidation** — only clears matching prefix

---

## 8. Data Flow

### Code Search Request

```
Client (Vue/MCP)
    ↓ HTTP POST /v1/code/search/hybrid
FastAPI Route (code_search_routes.py)
    ↓
HybridCodeSearchService.search()
    ├── L2 Cache Check → HIT? return cached
    ├── LexicalSearchService (pg_trgm) ← parallel
    ├── VectorSearchService (HNSW) ← parallel
    ├── RRFFusionService (RRF fusion, k=60)
    ├── BM25RerankService (rerank top 30)
    └── L2 Cache Population (TTL=120s)
    ↓
JSON Response
```

### Memory Search

```
Client
    ↓
FastAPI Route (search_routes.py)
    ↓
DualEmbeddingService.generate_embedding(query)
    ↓
MemorySearchService.search_hybrid()
    ├── Lexical (ILIKE + pg_trgm on title/content)
    ├── Vector (HNSW cosine similarity)
    ├── RRF fusion
    └── BM25 reranking
    ↓
JSON Response
```

### Code Indexing

```
index_project() MCP Tool
    ↓
CodeIndexingService.index_project()
    ├── Scan files (respect .gitignore)
    ├── CodeChunkingService (tree-sitter AST, 15+ languages)
    ├── CascadeCache check (skip if cached)
    ├── MetadataExtractorService (complexity, params, calls)
    ├── DualEmbeddingService (TEXT + CODE, 768D each)
    ├── GraphConstructionService (call/import graph)
    └── CodeChunkRepository (upsert to PostgreSQL)
```

---

## 9. Design Patterns

| Pattern | Implementation |
|---------|---------------|
| **Repository** | All DB access through repositories (EventRepository, CodeChunkRepository, MemoryRepository, etc.) |
| **DIP** | Protocol interfaces in `api/interfaces/` — concrete implementations depend on abstractions |
| **Adapter** | DualEmbeddingServiceAdapter wraps dual-domain service for legacy single-domain code |
| **Cascade** | CascadeCache coordinates L1→L2→L3 with automatic promotion |
| **Circuit Breaker** | Wraps Redis operations — CLOSED → OPEN → HALF_OPEN |
| **CQRS** | Separate read (search) and write (CRUD) paths |
| **Strategy** | Embedding mode (mock/real), search weights, adaptive RRF k |
| **Singleton** | Services in app.state / mcp._services |
| **Observer** | Background monitoring loop (60s interval) |
| **Decorator** | @with_retry() for Redis, CachedEmbeddingService wrapper |

---

## 10. Project Structure

```
MnemoLite/
├── api/                          # FastAPI backend
│   ├── main.py                   # Application entry point
│   ├── dependencies.py           # FastAPI dependency injection
│   ├── routes/                   # REST API endpoints (17 modules)
│   ├── services/                 # Business logic (39 modules)
│   │   ├── caches/               # L1/L2/L3 cache implementation
│   │   ├── hybrid_code_search_service.py
│   │   ├── hybrid_memory_search_service.py
│   │   ├── bm25_rerank_service.py
│   │   ├── dual_embedding_service.py
│   │   └── ...
│   ├── db/                       # Database layer
│   │   ├── repositories/         # Repository pattern implementations
│   │   └── query_builders/       # SQL query construction
│   ├── interfaces/               # Protocol interfaces (DIP)
│   └── mnemo_mcp/                # MCP server
│       ├── server.py             # FastMCP server entry point
│       ├── tools/                # MCP tools (9 modules, 28 tools)
│       ├── resources/            # MCP resources (6 modules)
│       └── models/               # Pydantic models
├── frontend/                     # Vue 3 SPA
│   ├── src/
│   │   ├── pages/                # 14 pages
│   │   ├── components/           # Reusable components
│   │   ├── composables/          # Vue composables (14)
│   │   ├── config/               # API configuration
│   │   └── types/                # TypeScript types
│   └── vite.config.ts            # Vite config with API proxy
├── tests/                        # All tests (consolidated)
│   ├── mnemo_mcp/                # MCP tests (356/358 passing)
│   ├── integration/              # Integration tests
│   ├── services/                 # Service tests
│   └── db/                       # Database tests
├── docs/                         # Documentation
│   ├── 00_CONTROL/               # Project control docs
│   ├── 01_DECISIONS/             # Architecture decision records
│   ├── 02_GUIDES/                # User guides
│   ├── 03_FEATURES/              # Feature documentation
│   ├── 04_MCP/                   # MCP documentation
│   ├── 05_EXAMPLES/              # Usage examples
│   ├── 88_ARCHIVE/               # Historical docs
│   ├── 99_PLANS/                 # EPIC plans
│   ├── deployment/               # Deployment guide
│   └── README.md                 # Documentation index
├── docker/                       # Docker configs
│   ├── Dockerfile.frontend       # Dev Dockerfile
│   ├── Dockerfile.frontend.prod  # Prod Dockerfile (Nginx)
│   ├── Dockerfile.worker         # Worker Dockerfile
│   └── nginx.conf                # Nginx configuration
├── db/                           # PostgreSQL Docker setup
├── scripts/                      # Utility scripts
├── workers/                      # Background workers
├── docker-compose.yml            # Service orchestration
├── Makefile                      # Development commands
├── README.md                     # Project overview
└── CONTRIBUTING.md               # Contribution guidelines
```
