---
name: mnemolite-architecture
description: MnemoLite architecture patterns, stack details, file structure, DIP, CQRS, protocols, layering, cache architecture. Use for architecture questions, structure queries, design patterns.
---

# MnemoLite Architecture & Stack

**Purpose**: Complete reference for MnemoLite architecture, technology stack, file structure, design patterns, and architectural decisions.

---

## When to Use This Skill

Use this skill when:
- Understanding overall architecture
- Looking up technology stack details (versions, dependencies)
- Navigating file structure
- Understanding architectural patterns (DIP, CQRS, layering)
- Learning cache architecture (L1+L2+L3)
- Designing new features (what patterns to follow)

---

## Quick Reference

| Question | Answer | Section |
|----------|--------|---------|
| What's the stack? | FastAPI + PG18 + Redis + HTMX | Stack Details |
| Where are routes? | api/routes/ | File Structure |
| What's the layering? | routes → services → repos → DB | Layering |
| Cache strategy? | L1 (in-mem) + L2 (Redis) + L3 (PG18) | Cache Architecture |
| Dependency injection? | Protocol-based DIP | DIP & Protocols |
| CQRS implementation? | CQRS-inspired (commands + queries) | CQRS Pattern |

---

## Identity & Vision

**MnemoLite**: PostgreSQL-based cognitive memory system with code intelligence

**Core Capabilities**:
- Cognitive memory storage (events + embeddings)
- Code intelligence (chunking, search, graph analysis)
- Dual embedding system (text + code)
- Progressive disclosure UI
- Real-time caching (3-tier)

**Philosophy**:
- PostgreSQL-only (no hybrid DB)
- Async-first (SQLAlchemy 2.0 async)
- EXTEND > REBUILD (copy patterns, adapt)
- Protocol-based dependency injection
- Progressive disclosure (skills + cache)

---

## Technology Stack

### Backend

**Core Framework**:
- **FastAPI** 0.111+ (async web framework)
- **Python** 3.11+ (async/await native)
- **SQLAlchemy** 2.0+ (async ORM/Core)
- **asyncpg** (PostgreSQL async driver)

**Database**:
- **PostgreSQL** 18+ (cognitive memory + vector ops)
- **pgvector** (vector similarity search, HNSW indexes)
- **pg_partman** (table partitioning, deferred until 500k+ events)
- **tembo-pgmq** (message queue, infrastructure ready but not active)

**Caching**:
- **Redis** 7-alpine (L2 cache, 2GB max, LRU eviction)
- **redis[hiredis]** (Python client with C parser)

**Embeddings & AI**:
- **sentence-transformers** 2.7+ (embedding models)
- **nomic-ai/nomic-embed-text-v1.5** (text embeddings, 768D)
- **jinaai/jina-embeddings-v2-base-code** (code embeddings, 768D)
- **tree-sitter** (AST parsing for code chunking)

**Utilities**:
- **structlog** (structured logging)
- **pydantic** 2.0+ (data validation)

### Frontend

**UI Framework**:
- **HTMX** 1.9+ (hypermedia-driven interactions)
- **Jinja2** (server-side templating)

**Visualizations**:
- **Cytoscape.js** 3.28 (graph visualization)
- **Chart.js** 4.4 (analytics charts)

**Theme**:
- **SCADA Dark Theme** (custom CSS)
- Colors: bg:#0a0e27, accent:blue/green/red/cyan
- Font: SF Mono (monospace)

### Development

**Testing**:
- **pytest** (test framework)
- **pytest-asyncio** (async test support)
- **httpx** (async HTTP client for tests)

**Docker**:
- **PostgreSQL 18** (custom Dockerfile with pgvector + partman)
- **Redis 7-alpine** (official image, 2GB config)
- **Python 3.11-slim** (API container)

**Tools**:
- **Make** (task automation)
- **Docker Compose** (local development)

---

## File Structure

```
MnemoLite/
├── api/                          # Backend application
│   ├── main.py                   # FastAPI entry point + lifespan
│   ├── dependencies.py           # Dependency injection
│   ├── config.py                 # Configuration settings
│   │
│   ├── db/                       # Database layer
│   │   ├── database.py           # Engine, session factory
│   │   └── repositories/         # Data access (SQLAlchemy Core async)
│   │       ├── base.py           # Base repository protocol
│   │       ├── event.py          # Event repository
│   │       ├── memory.py         # Memory repository
│   │       ├── code_chunk.py     # Code chunk repository
│   │       ├── node.py           # Graph node repository
│   │       └── edge.py           # Graph edge repository
│   │
│   ├── interfaces/               # Protocol definitions (DIP)
│   │   ├── repos.py              # Repository protocols
│   │   └── services.py           # Service protocols
│   │
│   ├── models/                   # Pydantic models
│   │   ├── event.py              # Event models
│   │   ├── memory.py             # Memory models
│   │   ├── embedding.py          # Embedding models
│   │   ├── code_chunk.py         # Code chunk models
│   │   └── graph.py              # Graph models (nodes, edges)
│   │
│   ├── routes/                   # API endpoints
│   │   ├── events.py             # Event routes (v1)
│   │   ├── search.py             # Search routes (v1)
│   │   ├── health.py             # Health check
│   │   ├── code_indexing.py      # Code indexing routes (v1)
│   │   ├── code_search.py        # Code search routes (v1)
│   │   ├── code_graph.py         # Code graph routes (v1)
│   │   └── ui_routes.py          # UI routes (15 endpoints)
│   │
│   ├── services/                 # Business logic
│   │   ├── embedding.py          # Text embedding service
│   │   ├── search.py             # Search service
│   │   ├── processor.py          # Event processor
│   │   ├── notification.py       # Notification service
│   │   │
│   │   ├── code_chunking.py      # Code chunking (tree-sitter AST)
│   │   ├── code_indexing.py      # Code indexing orchestration
│   │   ├── metadata_extractor.py # Code metadata extraction
│   │   ├── dual_embedding.py     # Dual embedding (text + code)
│   │   ├── symbol_path.py        # Symbol path generation (EPIC-11)
│   │   │
│   │   ├── graph_construction.py # Graph building
│   │   ├── graph_traversal.py    # Graph traversal
│   │   ├── hybrid_code_search.py # Hybrid search (RRF)
│   │   ├── lexical_search.py     # Lexical search (BM25)
│   │   ├── vector_search.py      # Vector search (cosine)
│   │   └── rrf_fusion.py         # Reciprocal Rank Fusion
│   │
│   └── utils/                    # Utilities
│       ├── cache.py              # L1+L2 cache
│       ├── timeouts.py           # Timeout decorators
│       └── circuit_breaker.py    # Circuit breaker (EPIC-12)
│
├── templates/                    # Jinja2 templates
│   ├── base.html                 # Base template
│   ├── dashboard.html            # Main dashboard
│   ├── search.html               # Search page
│   ├── graph.html                # Event graph
│   ├── monitoring.html           # Monitoring page
│   │
│   ├── code_dashboard.html       # Code intelligence dashboard
│   ├── code_repos.html           # Repository management
│   ├── code_search.html          # Code search
│   ├── code_graph.html           # Code dependency graph
│   ├── code_upload.html          # File upload
│   │
│   └── partials/                 # HTMX partials
│       ├── event_list.html       # Event list partial
│       ├── code_results.html     # Code search results
│       └── repo_list.html        # Repository list
│
├── static/                       # Static assets
│   ├── css/
│   │   ├── base.css              # Base styles
│   │   ├── scada.css             # SCADA theme
│   │   └── navbar.css            # Navigation
│   │
│   └── js/
│       └── components/
│           ├── graph.js          # Event graph (Cytoscape)
│           ├── code_graph.js     # Code graph (Cytoscape)
│           ├── filters.js        # Search filters
│           └── monitoring.js     # Monitoring charts (Chart.js)
│
├── db/                           # Database setup
│   ├── Dockerfile                # PostgreSQL 18 + extensions
│   ├── init/
│   │   ├── 01-extensions.sql    # Enable pgvector, partman
│   │   ├── 01-init.sql           # Schema creation
│   │   └── 02-partman.sql        # Partitioning setup (deferred)
│   │
│   ├── migrations/               # SQL migrations
│   │   ├── v2_to_v3.sql          # Add content_hash
│   │   ├── v3_to_v4.sql          # Add name_path (EPIC-11)
│   │   └── v4_to_v5_performance_indexes.sql  # Performance indexes
│   │
│   └── scripts/
│       └── enable_partitioning.sql  # Activate partitioning (future)
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures (async engine, client)
│   ├── test_routes.py            # Route tests
│   ├── test_services.py          # Service tests
│   ├── test_repositories.py      # Repository tests
│   │
│   └── db/
│       └── repositories/
│           ├── test_event.py     # Event repo tests
│           ├── test_code_chunk.py  # Code chunk repo tests
│           └── test_graph.py     # Graph repo tests
│
├── scripts/                      # Utility scripts
│   ├── generate_test_data.py    # Test data generator
│   └── benchmarks/               # Performance benchmarks
│
├── docs/                         # Documentation
│   ├── agile/                    # EPIC/Story docs
│   ├── architecture.md           # Architecture overview
│   ├── api_spec.md               # API specification
│   └── testing.md                # Testing guide
│
├── .claude/                      # Claude Code configuration
│   └── skills/                   # Skills (auto-invoked knowledge)
│       ├── mnemolite-gotchas/SKILL.md      # Debugging gotchas
│       ├── epic-workflow/SKILL.md          # EPIC workflow
│       ├── document-lifecycle/SKILL.md     # Doc management
│       └── mnemolite-architecture/SKILL.md # This file
│
├── CLAUDE.md                     # Cognitive engine (HOW TO THINK)
├── docker-compose.yml            # Docker orchestration
├── Makefile                      # Development commands
├── .env                          # Environment variables
└── requirements.txt              # Python dependencies
```

**Key Directories**:
- `api/` - Backend (routes → services → repositories → DB)
- `templates/` - Frontend (Jinja2 + HTMX)
- `static/` - CSS/JS assets
- `db/` - Database setup + migrations
- `tests/` - Test suite
- `.claude/skills/` - Knowledge base (auto-invoked)

---

## Architectural Patterns

### Layering (Clean Architecture Inspired)

**Flow**: HTTP Request → Routes → Services → Repositories → Database

```
┌─────────────────────────────────────────────┐
│  Routes (API Layer)                         │  ← FastAPI endpoints
│  - Input validation (Pydantic)              │
│  - Dependency injection (Depends)           │
│  - HTTP response formatting                 │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  Services (Business Logic Layer)            │  ← Orchestration
│  - Business rules                           │
│  - Workflow orchestration                   │
│  - Calls multiple repositories              │
│  - Protocol-based (dependency injection)    │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  Repositories (Data Access Layer)           │  ← SQLAlchemy
│  - CRUD operations                          │
│  - Query composition                        │
│  - Protocol implementation                  │
│  - Async/await ALL operations               │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  Database (PostgreSQL 18)                   │  ← Storage
│  - Events, code chunks, nodes, edges        │
│  - HNSW vector indexes                      │
│  - JSONB metadata                           │
└─────────────────────────────────────────────┘
```

**Principles**:
- **Single Responsibility**: Each layer has one job
- **Dependency Rule**: Inner layers know nothing about outer layers
- **Protocol-based**: Dependencies are abstractions (interfaces), not implementations

---

### DIP (Dependency Inversion Principle)

**Pattern**: Depend on abstractions (Protocols), not concrete implementations

**Implementation**:

```python
# 1. Define Protocol (interface)
# api/interfaces/repos.py
from typing import Protocol
from uuid import UUID

class EventRepositoryProtocol(Protocol):
    async def create_event(self, event: EventCreate) -> Event: ...
    async def get_event(self, event_id: UUID) -> Event | None: ...
    async def list_events(self, limit: int) -> list[Event]: ...

# 2. Implement Protocol (concrete class)
# api/db/repositories/event.py
class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_event(self, event: EventCreate) -> Event:
        # Implementation using SQLAlchemy Core
        result = await self.session.execute(insert(Event).values(...))
        return result

    # ... other methods

# 3. Dependency Injection (FastAPI)
# api/dependencies.py
def get_event_repo(session: AsyncSession = Depends(get_session)) -> EventRepositoryProtocol:
    return EventRepository(session)

# 4. Use in route (depends on Protocol, not concrete class)
# api/routes/events.py
@router.post("/events")
async def create_event(
    event: EventCreate,
    repo: EventRepositoryProtocol = Depends(get_event_repo)  # Protocol type
):
    return await repo.create_event(event)
```

**Benefits**:
- Testability: Easy to mock repositories
- Flexibility: Swap implementations without changing routes
- Clear contracts: Protocol defines expected interface

**Protocols Available**:
- `EventRepositoryProtocol`
- `CodeChunkRepositoryProtocol`
- `GraphRepositoryProtocol`
- `SearchServiceProtocol`
- `EmbeddingServiceProtocol`

---

### CQRS (Command Query Responsibility Segregation)

**Pattern**: Separate read (queries) from write (commands)

**Implementation** (CQRS-inspired, not strict):

**Commands** (Write operations):
- Direct database writes
- Simple validation
- Fast execution

```python
# Command: Create event
async def create_event(event: EventCreate, repo: EventRepositoryProtocol):
    return await repo.create_event(event)  # Direct write
```

**Queries** (Read operations):
- Complex queries with multiple filters
- Caching (L1 + L2 + L3)
- Optimized for read performance

```python
# Query: Search events
async def search_events(
    query: str,
    filters: dict,
    search_service: SearchServiceProtocol,
    cache: CacheService
):
    # Check L1/L2 cache
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Query database (L3)
    results = await search_service.search(query, filters)

    # Cache for future
    await cache.set(cache_key, results, ttl=30)
    return results
```

**Future**: PGMQ infrastructure ready for async command processing
- Events written to queue
- Background workers process
- Decoupled write/read paths

**Current State**: CQRS-inspired (separation of concerns), not full CQRS

---

### Cache Architecture (L1 + L2 + L3)

**3-Tier Caching Strategy**:

```
┌──────────────────────────────────────────────┐
│  L1 Cache (In-Memory, Per-Process)           │  ← Fastest (<1ms)
│  - LRU cache (100MB max)                     │
│  - MD5-based cache keys                      │
│  - Code chunks, frequent queries             │
│  - Hit rate: 80%+                            │
└────────────────┬─────────────────────────────┘
                 │ Miss
┌────────────────▼─────────────────────────────┐
│  L2 Cache (Redis, Shared)                    │  ← Fast (~5ms)
│  - 2GB max memory, LRU eviction              │
│  - Shared across API instances               │
│  - Search results, graph data                │
│  - TTL: 30s (search), 120s (graph)           │
│  - Hit rate: 70%+                            │
└────────────────┬─────────────────────────────┘
                 │ Miss
┌────────────────▼─────────────────────────────┐
│  L3 Cache (PostgreSQL)                       │  ← Slower (~10-50ms)
│  - Source of truth                           │
│  - HNSW indexes for vector search            │
│  - GIN indexes for JSONB/text search         │
└──────────────────────────────────────────────┘
```

**Cache Flow**:
1. Check L1 (in-memory LRU)
2. If miss → Check L2 (Redis)
3. If miss → Query L3 (PostgreSQL)
4. Populate L2 and L1 on miss
5. Return result

**Cache Keys** (MD5-based):
- Code chunks: `md5(file_path + chunk_type + name)`
- Search: `md5(query + filters + timestamp_bucket)`
- Graph: `md5(repository + node_type)`

**TTL Strategy**:
- Events: 60s (frequently changing)
- Search: 30s (user-specific, varies)
- Graph: 120s (rarely changes)
- Code chunks: No TTL (invalidate on reindex)

**Graceful Degradation**:
- L2 (Redis) down → Fall back to L3 (PostgreSQL)
- Performance degrades but system functional

**Monitoring**:
```bash
# Check cache stats
curl http://localhost:8001/v1/events/cache/stats | jq
```

**Target Metrics**:
- L1 hit rate: 80%+
- L2 hit rate: 70%+
- Combined hit rate: 85%+
- L1 latency: <1ms
- L2 latency: <5ms

---

## Database Schema

### Events Table

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    content JSONB NOT NULL,
    embedding VECTOR(768),  -- pgvector
    metadata JSONB,
    content_hash TEXT,      -- Deduplication (v3)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_events_timestamp ON events USING BTREE(timestamp);
CREATE INDEX idx_events_metadata ON events USING GIN(metadata jsonb_path_ops);
CREATE INDEX idx_events_embedding ON events USING HNSW(embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Key Points**:
- HNSW index for vector similarity (m=16, ef_construction=64)
- GIN index with `jsonb_path_ops` (smaller, optimized for `@>` operator)
- Partitioning DEFERRED until 500k+ events (overhead > benefit currently)

### Code Chunks Table

```sql
CREATE TABLE code_chunks (
    id UUID PRIMARY KEY,
    file_path TEXT NOT NULL,
    language TEXT,
    chunk_type TEXT,  -- function, class, method, module
    source_code TEXT NOT NULL,
    name TEXT,
    name_path TEXT,   -- Hierarchical qualified name (EPIC-11)
    start_line INT,
    end_line INT,
    embedding_text VECTOR(768),   -- Text embedding (nomic)
    embedding_code VECTOR(768),   -- Code embedding (jina)
    metadata JSONB,
    repository TEXT,
    commit_hash TEXT,
    indexed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_code_chunks_name_path ON code_chunks USING BTREE(name_path);
CREATE INDEX idx_code_chunks_name_path_trgm ON code_chunks USING GIN(name_path gin_trgm_ops);
CREATE INDEX idx_code_chunks_metadata ON code_chunks USING GIN(metadata jsonb_path_ops);
CREATE INDEX idx_code_chunks_embedding_text ON code_chunks USING HNSW(embedding_text vector_cosine_ops);
CREATE INDEX idx_code_chunks_embedding_code ON code_chunks USING HNSW(embedding_code vector_cosine_ops);
```

**Key Points**:
- Dual embeddings (text + code) for hybrid search
- `name_path` with Btree + trigram for qualified name search (EPIC-11)
- HNSW indexes for both embedding types

### Graph Tables (Nodes + Edges)

```sql
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY,
    node_type TEXT,  -- function, class, method
    label TEXT,
    properties JSONB,  -- {chunk_id, file_path, complexity, signature}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE edges (
    edge_id UUID PRIMARY KEY,
    source_node_id UUID,  -- NO FK constraint
    target_node_id UUID,  -- NO FK constraint
    relation_type TEXT,   -- calls, imports
    properties JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Key Points**:
- No FK constraints (symbol resolution is best-effort)
- Resolution scope: local (same file) → imports (tracked) → external (best effort)
- Python builtins filtered to avoid graph pollution

---

## Design Patterns & Principles

### EXTEND > REBUILD

**Principle**: Copy existing patterns and adapt, don't rebuild from scratch

**Why**: ~10x faster development, maintains consistency

**Example**:
```bash
# ✅ CORRECT - Extend existing
cp templates/graph.html templates/code_graph.html
# Then adapt: change title, endpoint, data source
# Result: ~10 minutes vs ~2 hours rebuilding

# ❌ WRONG - Rebuild from scratch
# Write code_graph.html completely new
# Result: ~2 hours + likely inconsistencies
```

**Application**:
- UI pages: Copy similar page, adapt
- Services: Copy similar service, modify
- Routes: Copy similar route pattern, adjust
- Tests: Copy similar test, change fixtures

### Test-First Development

**Pattern**: Write tests before implementation

**Workflow**:
1. Write failing test (defines expected behavior)
2. Implement minimal code to pass test
3. Refactor if needed
4. Verify test still passes

**Example**:
```python
# 1. Write test first
async def test_create_event():
    event = EventCreate(content={"test": "data"})
    result = await repo.create_event(event)
    assert result.id is not None
    assert result.content == {"test": "data"}

# 2. Implement to pass test
async def create_event(self, event: EventCreate) -> Event:
    # Minimal implementation
    return Event(id=uuid4(), content=event.content)

# 3. Test passes → Done
```

### Async-First

**Principle**: ALL database operations MUST be async/await

**Why**: MnemoLite uses SQLAlchemy 2.0 async exclusively

**Pattern**:
```python
# ✅ CORRECT - Async all the way
async def get_event(self, event_id: UUID) -> Event | None:
    result = await self.session.execute(
        select(Event).where(Event.id == event_id)
    )
    return result.scalar_one_or_none()

# ❌ WRONG - Missing await
async def get_event(self, event_id: UUID) -> Event | None:
    result = self.session.execute(  # Missing await!
        select(Event).where(Event.id == event_id)
    )
    return result.scalar_one_or_none()
```

**Critical**: See skill:mnemolite-gotchas/CRITICAL-02 for details

### Minimal Change

**Principle**: Smallest change that solves the problem

**Why**: Reduces risk, easier to review, faster to implement

**Example**:
```python
# Need to add caching to one endpoint

# ✅ CORRECT - Minimal change
@router.get("/events")
async def list_events(cache: CacheService = Depends(get_cache)):
    cached = await cache.get("events_list")
    if cached:
        return cached
    # ... existing code ...

# ❌ WRONG - Refactor everything
# Rewrite entire route, change all patterns, add unnecessary features
```

---

## Performance Characteristics

### Throughput (Local, ~50k events + 14 code chunks)

**API**:
- Sustained: 100 req/s (10x improvement from EPIC-08)
- Burst: 150 req/s
- Connection pool: 20 connections + 10 overflow

**Events**:
- Vector search (HNSW): ~12ms
- Hybrid search: ~11ms (cached: ~5ms, -88%)
- Metadata + time filter: ~3ms

**Code Intelligence**:
- Indexing: <100ms per file
- Hybrid search: <200ms
- Lexical search: <50ms
- Vector search: <100ms
- Graph traversal (≤3 hops): <1ms

**UI**:
- Page load: <100ms
- HTMX partial: <50ms
- Cytoscape render: <200ms

**Cache Performance**:
- L1 hit: <1ms
- L2 hit: ~5ms
- L3 query: ~10-50ms
- Hit rate: 80%+ (L1), 70%+ (L2), 85%+ combined

### Scalability Thresholds

**Current**: Single-instance, local development
- Events: ~50k indexed
- Code chunks: ~14 indexed
- Throughput: 100 req/s sustained

**Partitioning Threshold**: 500k+ events
- **Current decision**: DEFERRED (overhead > benefit)
- **Trigger**: When queries slow despite indexes
- **Activation**: `db/scripts/enable_partitioning.sql`
- **Monitoring**: `db/init/03-monitoring-views.sql`

**Horizontal Scaling** (future):
- Multiple API instances (Redis L2 shared)
- Read replicas (PostgreSQL)
- CDN for static assets

---

## Configuration & Environment

### Required Environment Variables

```bash
# Database (Development)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mnemolite

# Database (Testing) - CRITICAL!
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mnemolite_test

# Redis
REDIS_URL=redis://redis:6379/0

# Embeddings
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
EMBEDDING_DIMENSION=768
EMBEDDING_MODE=real  # or 'mock' for tests

# Environment
ENVIRONMENT=dev  # or 'test', 'prod'
API_PORT=8001
POSTGRES_PORT=5432
```

### Docker Compose Services

```yaml
services:
  db:
    image: mnemo-postgres:latest  # Custom PG18 + pgvector + partman
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    ports: ["6379:6379"]

  api:
    build: .
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    ports: ["8001:8000"]
    volumes:
      - ./api:/app/api
      - ./tests:/app/tests
    environment:
      - DATABASE_URL
      - TEST_DATABASE_URL  # CRITICAL
      - REDIS_URL
      - EMBEDDING_MODE
```

### Make Commands

```bash
# Development
make up          # Start all services
make down        # Stop all services
make restart     # Restart all services
make logs        # View logs

# Database
make db-shell    # PostgreSQL shell
make db-backup   # Backup database
make db-restore  # Restore from backup

# Testing
make api-test           # Run all tests
make api-test-file      # Run specific test file
make api-coverage       # Coverage report

# Quality
make lint          # Run linters
make lint-fix      # Auto-fix linting issues
```

---

## API Endpoints

### v1 API

**Events**:
- `POST /v1/events` - Create event
- `GET /v1/events` - List events
- `GET /v1/events/{id}` - Get event
- `GET /v1/events/cache/stats` - Cache statistics

**Search**:
- `POST /v1/search` - Hybrid search (vector + metadata + time)

**Code Intelligence**:
- `POST /v1/code/index` - Index files
- `POST /v1/code/search/hybrid` - Hybrid code search
- `POST /v1/code/search/lexical` - Lexical search (BM25)
- `POST /v1/code/search/vector` - Vector similarity search
- `POST /v1/code/graph/build` - Build dependency graph
- `GET /v1/code/graph/traverse` - Traverse graph
- `GET /v1/code/graph/path` - Find path between nodes
- `GET /v1/code/graph/stats` - Graph statistics

**Health**:
- `GET /health` - Health check

### UI Routes

**Main Pages**:
- `GET /` - Dashboard (KPIs + charts)
- `GET /ui/search` - Event search
- `GET /ui/graph` - Event graph visualization
- `GET /ui/monitoring` - System monitoring

**Code Intelligence Pages**:
- `GET /ui/code/dashboard` - Code dashboard
- `GET /ui/code/repos` - Repository management
- `GET /ui/code/search` - Code search UI
- `GET /ui/code/graph` - Code dependency graph
- `GET /ui/code/upload` - File upload

**API Documentation**:
- `GET /docs` - Swagger UI (interactive API docs)

---

## Future Architecture Considerations

### Partitioning (Deferred until 500k+ events)

**When to activate**:
- Event count > 500k
- Query performance degrades despite indexes
- Partition pruning would provide measurable benefit

**Activation**:
```bash
# Run partitioning script
psql < db/scripts/enable_partitioning.sql

# Verify partitions
psql -c "SELECT * FROM partman.show_partitions('events');"
```

**Impact**:
- PK must be composite: `(id, timestamp)`
- Vector indexes per partition (not global)
- Query patterns must include timestamp for pruning

### Message Queue (PGMQ Infrastructure Ready)

**Current**: Infrastructure ready but not active

**Use cases** (future):
- Async event processing
- Background embedding generation
- Batch indexing
- Deferred graph construction

**Activation**: Enable PGMQ service in docker-compose.yml

### Horizontal Scaling

**API Instances**:
- Multiple FastAPI instances behind load balancer
- Redis L2 cache shared across instances
- L1 cache per instance (some duplication acceptable)

**Database**:
- Read replicas for queries
- Write to primary
- Replication lag acceptable for non-critical reads

---

## Related Skills

- **mnemolite-gotchas**: Common pitfalls, debugging (references architecture gotchas)
- **epic-workflow**: EPIC/Story management (references architecture in analysis phase)
- **document-lifecycle**: Document management (architecture decisions in RESEARCH phase)

---

## Version History

- **v1.0** (2025-10-21): Initial skill creation, migrated from CLAUDE.md v2.4

---

**Skill maintained by**: Human + AI collaboration
**Auto-invoke keywords**: architecture, stack, structure, DIP, CQRS, protocols, layering, cache, design patterns
**Content source**: Extracted from CLAUDE.md + project documentation + implementation
