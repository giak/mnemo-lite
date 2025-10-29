---
name: mnemolite-gotchas
description: MnemoLite debugging gotchas & critical patterns. Use for errors, failures, slow performance, test issues, database problems, crashes, hangs.
---

# MnemoLite Gotchas & Critical Patterns

**Version**: 2.1.0 (+ Claude Code JSONL Parsing Gotcha)
**Category**: Gotchas, Debugging, Patterns
**Last Updated**: 2025-10-29

---

## Purpose

Comprehensive catalog of MnemoLite-specific gotchas, pitfalls, critical patterns, and debugging knowledge. This skill prevents common errors and provides quick troubleshooting guidance.

**Structure**: This skill uses progressive disclosure. The index (this section) provides quick reference and pointers to detailed domain sections loaded on-demand.

---

## When to Use This Skill

Use this skill when:
- Encountering unexpected errors or failures
- Tests are failing or behaving unexpectedly
- Performance is degraded or queries are slow
- Database operations aren't working as expected
- Code changes break existing functionality
- Need to understand critical patterns to avoid violations

---

## Quick Reference by Symptom

| Symptom | Likely Cause | Domain | Quick Fix |
|---------|--------------|--------|-----------|
| Tests pollute dev DB | CRITICAL-01 | Critical | Set TEST_DATABASE_URL |
| `coroutine never awaited` | CRITICAL-02 | Critical | Add `await` to all DB calls |
| Partitioning breaks queries | CRITICAL-03 | Critical | Include timestamp in WHERE |
| **JSONL parser truncates 90% content** | **CODE-07 🔴** | **Code Intel** | **Filter tool_result messages (not real user!)** |
| Graph has Python builtins | CODE-05 | Code Intel | Filter builtins in graph construction |
| Embeddings fail validation | CRITICAL-04 | Critical | Store embeddings in dict before CodeChunkCreate |
| Method not found | CODE-03 | Code Intel | Check exact method name (build_graph_for_repository) |
| SQL query fails | DB-03 | Database | Check exact column names (properties NOT props) |
| Tests timeout | CRITICAL-05 | Critical | Check EMBEDDING_MODE=mock is set |
| Import errors in tests | TEST-01 | Testing | Use AsyncClient with ASGITransport |
| Cache not working | PERF-01 | Performance | Check Redis connection and TTL settings |
| UI changes don't appear | UI-01 | UI | Clear browser cache, check HTMX attrs |
| Docker build fails | DOCKER-01 | Docker | Check Dockerfile.db context and paths |

---

## Gotchas by Domain

### 🔴 Critical Gotchas (7 gotchas - MUST NEVER VIOLATE)

**Summary**: These gotchas will BREAK your application if violated. Always check these first.

1. **CRITICAL-01**: Test Database Configuration - `TEST_DATABASE_URL` must be set to separate test database
2. **CRITICAL-02**: Async/Await for All DB Operations - All database operations MUST use `await`
3. **CRITICAL-03**: Partitioning Query Patterns - Include timestamp in WHERE clause (POSTPONED until 500k events)
4. **CRITICAL-04**: Code Chunk Embeddings Storage - Store embeddings in dict BEFORE CodeChunkCreate
5. **CRITICAL-05**: Test Performance (Embedding Mode) - Set `EMBEDDING_MODE=mock` for tests
6. **CRITICAL-06**: L2 Cache Configuration - Redis must be 2GB with LRU eviction policy
7. **CRITICAL-07**: DualEmbedding Domain Selection - MUST use EmbeddingDomain.HYBRID for code chunks

**Details**: See Critical Domain section below

---

### 🔵 Database Gotchas (5 gotchas)

**Summary**: Database-specific patterns, schema gotchas, SQL query pitfalls

1. **DB-01**: JSONB Query Optimization - Use `jsonb_path_ops` NOT `jsonb_ops`
2. **DB-02**: Column Name Exactness - `properties` NOT `props`, `relation_type` NOT `relationship`
3. **DB-03**: SQL Complexity Calculations - Proper cast order: `((metadata->>'complexity')::jsonb->>'cyclomatic')::float`
4. **DB-04**: Connection Pool Sizing - 20 connections sufficient for 100 req/s, don't over-provision
5. **DB-05**: Foreign Key Resolution - Edges use NO FK constraints, resolution is best-effort

**Details**: See Database Domain section below

---

### 🟢 Code Intelligence Gotchas (6 gotchas + 1 CRITICAL JSONL parsing)

**Summary**: Code chunking, graph construction, symbol resolution, indexing patterns, LSP integration, JSONL parsing

1. **CODE-01**: Embedding Domain Selection - Use HYBRID domain for code chunks (TEXT+CODE embeddings)
2. **CODE-02**: Code Chunk Embedding Storage Pattern - Create dict with embeddings BEFORE CodeChunkCreate
3. **CODE-03**: GraphService Method Naming - `build_graph_for_repository()` NOT `build_repository_graph()`
4. **CODE-04**: Symbol Resolution Scope - Local (same file) → Imports (tracked) → Best effort
5. **CODE-05**: Graph Builtin Filtering - Python builtins MUST be filtered to avoid graph pollution
6. **CODE-06**: TypeScript LSP Workspace Creation - Create workspace directory BEFORE starting LSP client
7. **CODE-07** 🔴: Claude Code JSONL Tool Results - `role="user"` includes tool_result (fake user messages, 90% data loss!)

**Details**: See Code Intelligence Domain section below

---

### 🟡 Testing Gotchas (3 gotchas)

**Summary**: Test setup, fixtures, async testing patterns

1. **TEST-01**: AsyncClient Transport - Use `ASGITransport(app)` NOT `app=app` in pytest fixture
2. **TEST-02**: Test Database Isolation - Always use TEST_DATABASE_URL, reset with `make db-test-reset`
3. **TEST-03**: Embedding Mock Mode - Set `EMBEDDING_MODE=mock` to avoid loading models in tests

**Details**: See Testing Domain section below

---

### 🟣 Architecture Gotchas (3 gotchas)

**Summary**: Architectural patterns, protocol implementations, DIP violations

1. **ARCH-01**: Protocol Implementation - New repos/services MUST implement Protocol interfaces
2. **ARCH-02**: EXTEND>REBUILD Philosophy - Copy existing patterns, adapt minimally (~10x faster)
3. **ARCH-03**: L1+L2 Cache Hierarchy - L1 (in-memory 100MB LRU) + L2 (Redis 2GB shared) + L3 (PG18)

**Details**: See Architecture Domain section below

---

### 🟠 Performance Gotchas (3 gotchas)

**Summary**: Caching, query optimization, performance patterns

1. **PERF-01**: Cache Stats Monitoring - `curl http://localhost:8001/v1/events/cache/stats | jq` for hit rates
2. **PERF-02**: Rollback Safety - `./apply_optimizations.sh rollback` provides 10s recovery
3. **PERF-03**: Vector Query Limits - ALWAYS use LIMIT on vector similarity queries to avoid full scan

**Details**: See Performance Domain section below

---

### 🔶 Workflow Gotchas (3 gotchas)

**Summary**: Git patterns, commit conventions, PR workflows

1. **WORKFLOW-01**: Commit Message Format - Use HEREDOC for multi-line messages with Co-Authored-By
2. **WORKFLOW-02**: Pre-commit Hook Handling - Amend ONLY if: (1) user requested OR (2) hook modified files
3. **WORKFLOW-03**: Interactive Git Commands - NEVER use `-i` flag (rebase -i, add -i) - not supported

**Details**: See Workflow Domain section below

---

### 🔷 UI Gotchas (3 gotchas)

**Summary**: HTMX patterns, SCADA theme, Cytoscape.js graph rendering

1. **UI-01**: HTMX Attribute Patterns - `hx-get`, `hx-target`, `hx-swap` must be exact
2. **UI-02**: EXTEND>REBUILD Pattern - Copy existing templates (e.g., graph.html → code_graph.html)
3. **UI-03**: Cytoscape.js Render Performance - Use debouncing for layout recalculations (<200ms target)

**Details**: See UI Domain section below

---

### 🐳 Docker Gotchas (3 gotchas)

**Summary**: Docker Compose, volumes, environment variables

1. **DOCKER-01**: Dockerfile Context Path - `db/Dockerfile` expects context from project root
2. **DOCKER-02**: Volume Mount Permissions - Ensure user:group matches container user
3. **DOCKER-03**: Environment Variable Precedence - .env < docker-compose.yml < command line

**Details**: See Docker Domain section below

---

---
# DOMAIN FILES (Progressive Disclosure - All Content Below)
---

## 🔴 CRITICAL DOMAIN: Critical Gotchas (7 Gotchas)

**Purpose**: Gotchas that WILL BREAK your application if violated. These are non-negotiable patterns that MUST be followed.

**When to Use**: Check these FIRST when encountering errors, test failures, or unexpected behavior.

---

### CRITICAL-01: Test Database Configuration

**Rule**: `TEST_DATABASE_URL` must ALWAYS be set to separate test database

**Why**: Without separate test DB, tests will:
- Delete/modify development data
- Create test fixtures in dev DB
- Cause unpredictable behavior
- Pollute dev database with test data

**How to Detect**:
```bash
# Check if TEST_DATABASE_URL is set
grep TEST_DATABASE_URL .env

# Symptom: Tests pollute dev database
# Symptom: Dev database has test_* tables
# Symptom: Random data appears in dev DB after tests
```

**How to Fix**:
```bash
# ✅ CORRECT - Add to .env
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mnemolite_test
EMBEDDING_MODE=mock

# Reset test database
make db-test-reset

# Verify separation
grep TEST_DATABASE_URL .env
```

**Example**:
```bash
# ❌ WRONG - Will pollute dev database
TEST_DATABASE_URL=<not set>  # Uses dev database!

# ✅ CORRECT - Separate test database
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mnemolite_test
```

---

### CRITICAL-02: Async/Await for All DB Operations

**Rule**: ALL database operations MUST use `async`/`await` - SQLAlchemy 2.0 async only

**Why**: MnemoLite uses SQLAlchemy 2.0 async exclusively. Synchronous DB calls will:
- Raise `RuntimeWarning: coroutine was never awaited`
- Fail silently or return None
- Block event loop
- Cause deadlocks

**How to Detect**:
```python
# Symptom: RuntimeWarning: coroutine 'fetch_one' was never awaited
# Symptom: DB operations return None unexpectedly
# Symptom: Tests hang or timeout
```

**How to Fix**:
```python
# ❌ WRONG - Missing await
async def get_event(event_id: UUID):
    result = session.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()

# ✅ CORRECT - Await all DB operations
async def get_event(event_id: UUID):
    result = await session.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()
```

**Pattern**:
```python
# All repository methods MUST be async
async def create_event(self, event: EventCreate) -> Event:
    result = await self.session.execute(insert(Event).values(...))
    await self.session.commit()
    return event

# All service methods calling repos MUST be async
async def process_event(self, event_data: dict) -> Event:
    event = await self.event_repo.create_event(event_data)
    return event
```

---

### CRITICAL-03: Partitioning Query Patterns (POSTPONED)

**Rule**: When partitioning enabled (at 500k+ events), ALL queries MUST include timestamp in WHERE clause

**Status**: ⚠️ POSTPONED until 500k events reached (partitioning currently DISABLED)

**Why**: Partitioning by timestamp requires partition key in WHERE for partition pruning:
- Without timestamp: Full table scan across ALL partitions (slow)
- With timestamp: Prunes to specific partition (fast)

**How to Detect** (when partitioning enabled):
```sql
-- Symptom: EXPLAIN shows "Seq Scan" across all partitions
-- Symptom: Queries slow despite indexes
-- Symptom: Query plan shows multiple partition scans
```

**How to Fix** (when partitioning enabled):
```python
# ❌ WRONG - No timestamp filter
query = select(Event).where(Event.id == event_id)

# ✅ CORRECT - Include timestamp for partition pruning
from datetime import datetime, timedelta
recent = datetime.utcnow() - timedelta(days=30)
query = select(Event).where(
    Event.id == event_id,
    Event.timestamp >= recent  # Enables partition pruning
)
```

**Current State**: Partitioning disabled, monitor via `db/init/03-monitoring-views.sql`, activate when ready with `db/scripts/enable_partitioning.sql`

---

### CRITICAL-04: Code Chunk Embeddings Storage

**Rule**: Store embeddings in dict BEFORE CodeChunkCreate - embeddings cannot be on base model

**Why**: Pydantic model validation fails if embeddings are in base model. Must use dict for embeddings.

**How to Detect**:
```python
# Symptom: ValidationError when creating CodeChunk
# Symptom: "embedding_text" field validation error
# Symptom: Pydantic raises error on model creation
```

**How to Fix**:
```python
# ❌ WRONG - Embeddings in base model
chunk = CodeChunkCreate(
    file_path="...",
    source_code="...",
    embedding_text=embedding_vec,  # FAILS validation
    embedding_code=code_vec
)

# ✅ CORRECT - Store embeddings in dict separately
chunk_data = {
    "file_path": "...",
    "source_code": "...",
    # ... other fields ...
}
embeddings = {
    "embedding_text": embedding_vec,
    "embedding_code": code_vec
}
# Pass embeddings separately to repository
```

**Pattern**:
```python
# In service layer
async def create_code_chunk(self, chunk: CodeChunkCreate, embeddings: dict):
    # Store embeddings separately from model
    chunk_id = await self.repo.create_chunk(chunk, embeddings)
    return chunk_id
```

---

### CRITICAL-05: Test Performance (Embedding Mode)

**Rule**: Set `EMBEDDING_MODE=mock` for tests to avoid loading embedding models

**Why**: Loading real embedding models in tests:
- Takes 30+ seconds per test run
- Consumes 2.5GB RAM
- Causes timeouts
- Makes tests unpredictably slow

**How to Detect**:
```bash
# Symptom: Tests take 30+ seconds
# Symptom: First test in suite very slow
# Symptom: RAM usage spikes during tests
# Symptom: Tests timeout
```

**How to Fix**:
```bash
# ✅ CORRECT - Add to .env
EMBEDDING_MODE=mock

# Or run tests with mock mode
EMBEDDING_MODE=mock pytest tests/

# Verify mock mode active
grep EMBEDDING_MODE .env
```

**Pattern**:
```python
# conftest.py handles mock mode automatically
# Just ensure EMBEDDING_MODE=mock in .env

# In code, check embedding mode:
if os.getenv("EMBEDDING_MODE") == "mock":
    return MockEmbedding()
else:
    return RealEmbedding()
```

---

### CRITICAL-06: L2 Cache Configuration

**Rule**: Redis MUST be configured with 2GB max memory and LRU eviction policy

**Why**: Without proper cache configuration:
- Redis runs out of memory
- Eviction policy missing causes errors
- Cache thrashing degrades performance
- OOM kills Redis process

**How to Detect**:
```bash
# Symptom: Redis crashes with OOM
# Symptom: Cache hit rate drops suddenly
# Symptom: Redis memory grows unbounded
```

**How to Fix**:
```yaml
# ✅ CORRECT - docker-compose.yml
redis:
  image: redis:7-alpine
  command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
  ports:
    - "6379:6379"
```

**Monitoring**:
```bash
# Check Redis memory config
docker exec mnemo-redis redis-cli CONFIG GET maxmemory

# Check eviction policy
docker exec mnemo-redis redis-cli CONFIG GET maxmemory-policy

# Monitor cache stats
curl http://localhost:8001/v1/events/cache/stats | jq
```

---

### CRITICAL-07: DualEmbedding Domain Selection

**Rule**: MUST use `EmbeddingDomain.HYBRID` for code chunks - NOT `TEXT` only

**Why**: Code chunks need BOTH text and code embeddings:
- TEXT domain: Only loads nomic-embed-text-v1.5 (semantic search)
- CODE domain: Only loads jina-embeddings-v2-base-code (code search)
- HYBRID domain: Loads BOTH models (required for dual embedding)

**How to Detect**:
```python
# Symptom: Missing code_embedding field
# Symptom: Only text_embedding populated
# Symptom: Hybrid search fails
```

**How to Fix**:
```python
# ❌ WRONG - TEXT domain only
embedding_service = DualEmbeddingService(EmbeddingDomain.TEXT)
embeddings = await embedding_service.generate_embeddings("code")
# Result: Only has embedding_text, missing embedding_code

# ✅ CORRECT - HYBRID domain for code chunks
embedding_service = DualEmbeddingService(EmbeddingDomain.HYBRID)
embeddings = await embedding_service.generate_embeddings("code")
# Result: Has both embedding_text AND embedding_code
```

**Pattern**:
```python
# For code chunks - ALWAYS use HYBRID
from api.services.dual_embedding_service import EmbeddingDomain

# Code indexing service
embedding_service = DualEmbeddingService(EmbeddingDomain.HYBRID)

# For regular events - TEXT is fine
embedding_service = DualEmbeddingService(EmbeddingDomain.TEXT)
```

---

## 🔵 DATABASE DOMAIN: Database Gotchas (5 Gotchas)

---

### DB-01: JSONB Query Optimization

**Rule**: Use `jsonb_path_ops` NOT `jsonb_ops` for JSONB GIN indexes

**Why**:
- `jsonb_ops`: Larger index, supports more operators (slower)
- `jsonb_path_ops`: Smaller index, optimized for `@>` containment (faster)
- MnemoLite uses `@>` for metadata queries → use `jsonb_path_ops`

**How to Detect**:
```sql
-- Check existing indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'events';

-- Symptom: Large index size
-- Symptom: Slow @> queries
```

**How to Fix**:
```sql
-- ❌ WRONG
CREATE INDEX idx_metadata ON events USING GIN(metadata jsonb_ops);

-- ✅ CORRECT
CREATE INDEX idx_metadata ON events USING GIN(metadata jsonb_path_ops);
```

**Usage**:
```python
# Optimized for this query pattern
query = select(Event).where(
    Event.metadata.op('@>')({"key": "value"})
)
```

---

### DB-02: Column Name Exactness

**Rule**: Use EXACT schema column names - `properties` NOT `props`, `relation_type` NOT `relationship`

**Why**: Schema defines exact column names, SQL is case-sensitive for column names in queries

**Common Mistakes**:
- `properties` → Writing `props`
- `relation_type` → Writing `relationship` or `type`
- `node_id` → Writing `id`

**How to Detect**:
```sql
-- Symptom: column "props" does not exist
-- Symptom: column "relationship" does not exist
```

**How to Fix**:
```python
# ❌ WRONG
query = select(Node.props)  # Column is "properties" not "props"

# ✅ CORRECT
query = select(Node.properties)
```

**Reference**:
```sql
-- Nodes schema
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY,  -- NOT "id"
    properties JSONB            -- NOT "props"
);

-- Edges schema
CREATE TABLE edges (
    edge_id UUID PRIMARY KEY,
    relation_type TEXT          -- NOT "relationship" or "type"
);
```

---

### DB-03: SQL Complexity Calculations

**Rule**: Use proper cast order for nested JSONB: `((metadata->>'complexity')::jsonb->>'cyclomatic')::float`

**Why**: JSONB nested access requires correct casting order:
1. Extract 'complexity' as text: `metadata->>'complexity'`
2. Cast to JSONB: `::jsonb`
3. Extract 'cyclomatic' as text: `->>'cyclomatic'`
4. Cast to float: `::float`

**How to Detect**:
```sql
-- Symptom: ERROR: cannot cast type text to jsonb
-- Symptom: ERROR: operator does not exist: text -> unknown
```

**How to Fix**:
```sql
-- ❌ WRONG - Cast order incorrect
SELECT AVG((metadata->'complexity'->>'cyclomatic')::float)  -- Fails

-- ✅ CORRECT - Proper cast order
SELECT AVG(((metadata->>'complexity')::jsonb->>'cyclomatic')::float)
FROM nodes;
```

**Pattern**:
```python
# SQLAlchemy equivalent
from sqlalchemy import func, cast, Float

avg_complexity = func.avg(
    cast(
        cast(Node.properties['complexity'], JSONB)['cyclomatic'],
        Float
    )
)
```

---

### DB-04: Connection Pool Sizing

**Rule**: 20 connections sufficient for 100 req/s - DON'T over-provision

**Why**:
- Too few connections: Timeouts under load
- Too many connections: PG overhead, wasted resources
- Sweet spot: 20 connections + 10 overflow = 30 max

**How to Detect**:
```bash
# Symptom: TimeoutError acquiring connection
# Symptom: All connections in use
# Monitor pool stats
```

**How to Fix**:
```python
# ✅ CORRECT - Tested configuration
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # Normal connections
    max_overflow=10,     # Burst capacity
    pool_timeout=30,     # Wait 30s before timeout
    pool_pre_ping=True   # Test connection before use
)
```

**Monitoring**:
```python
# Check pool stats
pool = engine.pool
print(f"Size: {pool.size()}, Checked out: {pool.checkedout()}")
```

---

### DB-05: Foreign Key Resolution

**Rule**: Edges table uses NO FK constraints - resolution is best-effort

**Why**:
- Symbol resolution is imperfect (imports, external dependencies)
- FK constraints would fail on unresolved symbols
- Best-effort approach: Resolve what we can, store what we know

**Pattern**:
```sql
-- ❌ NOT USED - Would break on unresolved symbols
CREATE TABLE edges (
    source_node_id UUID REFERENCES nodes(node_id),  -- NOT USED
    target_node_id UUID REFERENCES nodes(node_id)   -- NOT USED
);

-- ✅ ACTUAL - No FK constraints
CREATE TABLE edges (
    source_node_id UUID,  -- No FK
    target_node_id UUID   -- No FK
);
```

**Resolution Scope**:
1. **Local (same file)**: High confidence, always resolved
2. **Imports (tracked)**: Medium confidence, resolved if file indexed
3. **External dependencies**: Best effort, may not resolve

---

## 🟢 CODE INTELLIGENCE DOMAIN: Code Intel Gotchas (5 Gotchas)

---

### CODE-01: Embedding Domain Selection

**Rule**: Use `EmbeddingDomain.HYBRID` for code chunks - requires TEXT + CODE embeddings

**Why**: Code needs dual embeddings:
- TEXT embedding (nomic-embed-text-v1.5): Semantic understanding
- CODE embedding (jina-embeddings-v2-base-code): Code structure

**How to Detect**:
```python
# Symptom: Only text_embedding populated
# Symptom: Hybrid search fails
# Symptom: Code search returns poor results
```

**How to Fix**:
```python
# ❌ WRONG
embedding_service = DualEmbeddingService(EmbeddingDomain.TEXT)

# ✅ CORRECT
embedding_service = DualEmbeddingService(EmbeddingDomain.HYBRID)
```

---

### CODE-02: Code Chunk Embedding Storage Pattern

**Rule**: Create dict with embeddings BEFORE CodeChunkCreate - embeddings cannot be in base model

**Pattern**:
```python
# ✅ CORRECT
chunk_data = {
    "file_path": path,
    "source_code": code,
    # ... other fields ...
}
embeddings = {
    "embedding_text": text_vec,
    "embedding_code": code_vec
}
await repo.create_chunk(chunk_data, embeddings)
```

---

### CODE-03: GraphService Method Naming

**Rule**: Method name is `build_graph_for_repository()` NOT `build_repository_graph()`

**Why**: Method names matter for dependency injection and service contracts

**How to Fix**:
```python
# ❌ WRONG
graph_service.build_repository_graph(repo_name)

# ✅ CORRECT
graph_service.build_graph_for_repository(repo_name)
```

---

### CODE-04: Symbol Resolution Scope

**Rule**: Resolution scope: Local (same file) → Imports (tracked) → Best effort

**Confidence Levels**:
1. **Local symbols (same file)**: 95%+ confidence, always resolved
2. **Imported symbols (tracked)**: 70%+ confidence, resolved if file indexed
3. **External dependencies**: Best effort, may not resolve

**Pattern**:
```python
# Local symbol (high confidence)
def foo():
    bar()  # Resolved: bar in same file

# Import symbol (medium confidence)
from models import User
User.validate()  # Resolved if models.py indexed

# External dependency (best effort)
import numpy as np
np.array()  # May not resolve (external package)
```

---

### CODE-05: Graph Builtin Filtering

**Rule**: Python builtins MUST be filtered to avoid graph pollution

**Why**: Python builtins (print, len, range, etc.) create noise in dependency graph

**How to Detect**:
```python
# Symptom: Graph shows edges to "print", "len", "range"
# Symptom: Dependency count inflated
```

**How to Fix**:
```python
# ✅ CORRECT - Filter builtins
import builtins
BUILTINS = set(dir(builtins))

def resolve_symbol(name: str):
    if name in BUILTINS:
        return None  # Skip builtins
    # ... resolve other symbols
```

---

### CODE-06: TypeScript LSP Workspace Creation

**Rule**: Create LSP workspace directory BEFORE starting TypeScript LSP client

**Why**: TypeScript Language Server requires workspace directory to exist during initialization

**Error Symptom**:
```
LSPInitializationError: Initialization failed:
{'code': -32603, 'message': "Request initialize failed with message:
ENOENT: no such file or directory, stat '/tmp/ts_lsp_workspace'"}
```

**How to Fix**:
```python
# ❌ WRONG - No workspace directory creation
typescript_lsp = TypeScriptLSPClient(workspace_root="/tmp/ts_lsp_workspace")
await typescript_lsp.start()  # Fails: directory doesn't exist

# ✅ CORRECT - Create directory first
from pathlib import Path

ts_workspace_root = "/tmp/ts_lsp_workspace"
Path(ts_workspace_root).mkdir(parents=True, exist_ok=True)  # Create directory
typescript_lsp = TypeScriptLSPClient(workspace_root=ts_workspace_root)
await typescript_lsp.start()  # Success
```

**Impact**:
- Without fix: TypeScript LSP fails to start, graceful degradation to heuristic extraction
- With fix: TypeScript LSP starts successfully, 95%+ type accuracy

---

## 🟡 TESTING DOMAIN: Testing Gotchas (3 Gotchas)

---

### TEST-01: AsyncClient Transport

**Rule**: Use `ASGITransport(app)` NOT `app=app` in pytest AsyncClient fixture

**Why**: Direct app passing doesn't work with async in newer versions

**How to Fix**:
```python
# ❌ WRONG
@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# ✅ CORRECT
from httpx import ASGITransport

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
```

---

### TEST-02: Test Database Isolation

**Rule**: ALWAYS use TEST_DATABASE_URL, reset with `make db-test-reset`

**Pattern**:
```bash
# Before running tests
make db-test-reset

# Run tests
EMBEDDING_MODE=mock pytest tests/

# Verify isolation
grep TEST_DATABASE_URL .env
```

---

### TEST-03: Embedding Mock Mode

**Rule**: Set `EMBEDDING_MODE=mock` to avoid loading embedding models in tests (30s+ overhead)

**Pattern**:
```bash
# ✅ CORRECT
EMBEDDING_MODE=mock pytest tests/

# Add to .env
EMBEDDING_MODE=mock
```

---

## 🟣 ARCHITECTURE DOMAIN: Architecture Gotchas (3 Gotchas)

---

### ARCH-01: Protocol Implementation

**Rule**: New repositories/services MUST implement Protocol interfaces from `api/interfaces/`

**Why**: Enables dependency injection and loose coupling

**Pattern**:
```python
# Define protocol
class EventRepositoryProtocol(Protocol):
    async def create_event(self, event: EventCreate) -> Event: ...

# Implement protocol
class EventRepository:
    async def create_event(self, event: EventCreate) -> Event:
        # Implementation
        pass
```

---

### ARCH-02: EXTEND>REBUILD Philosophy

**Rule**: Copy existing patterns, adapt minimally - ~10x faster than rebuilding

**Pattern**:
```bash
# ✅ CORRECT - Extend existing
cp templates/graph.html templates/code_graph.html
# Adapt: Change title, endpoint, data source
# Result: ~10min vs ~2h rebuilding from scratch
```

---

### ARCH-03: L1+L2 Cache Hierarchy

**Rule**: L1 (in-memory 100MB LRU) + L2 (Redis 2GB shared) + L3 (PG18)

**Cache Flow**:
1. Check L1 (in-memory, <1ms)
2. Check L2 (Redis, ~5ms)
3. Query L3 (PG18, ~10-50ms)
4. Populate L2 and L1 on miss

**TTL Strategy**:
- Events: 60s (frequently changing)
- Search: 30s (user-specific)
- Graph: 120s (rarely changes)

---

## 🟠 PERFORMANCE DOMAIN: Performance Gotchas (3 Gotchas)

---

### PERF-01: Cache Stats Monitoring

**Rule**: Monitor cache hit rates with `curl http://localhost:8001/v1/events/cache/stats | jq`

**Target Metrics**:
- L1 hit rate: 80%+
- L2 hit rate: 70%+
- Combined hit rate: 85%+

**Pattern**:
```bash
# Monitor cache stats
curl http://localhost:8001/v1/events/cache/stats | jq

# Expected output
{
  "l1_hits": 850,
  "l1_misses": 150,
  "l1_hit_rate": 0.85,
  "l2_hits": 700,
  "l2_misses": 300
}
```

---

### PERF-02: Rollback Safety

**Rule**: `./apply_optimizations.sh rollback` provides 10s recovery with automatic backups

**Pattern**:
```bash
# Test optimization
./apply_optimizations.sh test

# Apply if good
./apply_optimizations.sh apply

# Rollback if issues
./apply_optimizations.sh rollback  # 10s recovery
```

---

### PERF-03: Vector Query Limits

**Rule**: ALWAYS use LIMIT on vector similarity queries to avoid full table scan

**Why**: Without LIMIT, PG scans entire vector index (slow, expensive)

**How to Fix**:
```python
# ❌ WRONG - No limit (scans all vectors)
query = select(Event).order_by(
    Event.embedding.cosine_distance(query_vec)
)

# ✅ CORRECT - With limit
query = select(Event).order_by(
    Event.embedding.cosine_distance(query_vec)
).limit(10)  # Only compute top-10
```

---

## 🔶 WORKFLOW DOMAIN: Workflow Gotchas (3 Gotchas)

---

### WORKFLOW-01: Commit Message Format

**Rule**: Use HEREDOC for multi-line commit messages with Co-Authored-By

**Pattern**:
```bash
# ✅ CORRECT - HEREDOC format
git commit -m "$(cat <<'EOF'
feat(scope): Short description

Detailed explanation of changes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### WORKFLOW-02: Pre-commit Hook Handling

**Rule**: Amend commits ONLY if: (1) User requested OR (2) Hook modified files

**Pattern**:
```bash
# Check authorship before amending
git log -1 --format='%an %ae'

# Check not pushed
git status  # Should show "Your branch is ahead"

# Only amend if safe
git commit --amend
```

---

### WORKFLOW-03: Interactive Git Commands

**Rule**: NEVER use `-i` flag (rebase -i, add -i) - not supported in non-interactive environment

**How to Fix**:
```bash
# ❌ WRONG - Interactive mode not supported
git rebase -i HEAD~3
git add -i

# ✅ CORRECT - Use non-interactive alternatives
git rebase HEAD~3
git add <file>
```

---

## 🔷 UI DOMAIN: UI Gotchas (3 Gotchas)

---

### UI-01: HTMX Attribute Patterns

**Rule**: HTMX attributes must be exact - `hx-get`, `hx-target`, `hx-swap`

**Common Mistakes**:
- `hx-url` → Should be `hx-get` or `hx-post`
- `hx-replace` → Should be `hx-swap="outerHTML"`
- `hx-selector` → Should be `hx-target`

**How to Fix**:
```html
<!-- ❌ WRONG -->
<button hx-url="/api" hx-replace="#result">Click</button>

<!-- ✅ CORRECT -->
<button hx-get="/api" hx-target="#result" hx-swap="innerHTML">Click</button>
```

---

### UI-02: EXTEND>REBUILD Pattern

**Rule**: Copy existing templates (graph.html → code_graph.html), adapt minimally

**Pattern**:
```bash
# ✅ CORRECT - ~10min
cp templates/graph.html templates/code_graph.html
# Change: title, endpoint (/api/v1/code/graph), data source

# ❌ WRONG - ~2h
# Write code_graph.html from scratch
```

---

### UI-03: Cytoscape.js Render Performance

**Rule**: Use debouncing for layout recalculations (<200ms target)

**Pattern**:
```javascript
// ✅ CORRECT - Debounced layout
let layoutTimeout;
function updateGraph(data) {
    clearTimeout(layoutTimeout);
    layoutTimeout = setTimeout(() => {
        cy.layout({name: 'cose'}).run();
    }, 200);
}
```

---

## 🐳 DOCKER DOMAIN: Docker Gotchas (3 Gotchas)

---

### DOCKER-01: Dockerfile Context Path

**Rule**: `db/Dockerfile` expects build context from project root

**Pattern**:
```bash
# ❌ WRONG - Context from db/
cd db && docker build -f Dockerfile .

# ✅ CORRECT - Context from root
docker build -f db/Dockerfile -t mnemo-postgres .
```

---

### DOCKER-02: Volume Mount Permissions

**Rule**: Ensure host user:group matches container user to avoid permission errors

**Pattern**:
```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - ./api:/app
    user: "${UID}:${GID}"  # Match host user
```

---

### DOCKER-03: Environment Variable Precedence

**Rule**: .env < docker-compose.yml < command line

**Precedence**:
1. Command line: `docker-compose up -e VAR=value`
2. docker-compose.yml: `environment: VAR=value`
3. .env file: `VAR=value`

**Pattern**:
```bash
# .env file (lowest priority)
DATABASE_URL=postgresql://localhost

# docker-compose.yml (medium priority)
environment:
  DATABASE_URL: postgresql://db:5432

# Command line (highest priority)
docker-compose up -e DATABASE_URL=postgresql://prod:5432
```

---

---

## 🟢 Code Intel: Parsing & JSONL

### Gotcha #37: Claude Code JSONL Tool Results as Fake User Messages 🔴 CRITICAL

**Symptom**: Parser captures only first assistant message block, truncating 90% of content

**Context**: Claude Code transcripts (JSONL format) use `role="user"` for BOTH:
- Real user messages: `content` = string or `[{"type":"text","text":"..."}]`
- Tool results: `content` = `[{"type":"tool_result",...}]`

**Root Cause**:
- Parser treats tool_result messages as real user messages
- Stops collecting assistant messages prematurely at first tool_result
- Result: Only captures first assistant block, loses all subsequent responses

**Example JSONL Structure**:
```jsonl
# Line 3595 - REAL USER MESSAGE
{"message": {"role": "user", "content": "vérifie maintenant"}}

# Line 3596 - Assistant block 1
{"message": {"role": "assistant", "content": [{"type": "text", "text": "Je vais vérifier..."}]}}

# Line 3597 - Tool use
{"message": {"role": "assistant", "content": [{"type": "tool_use", ...}]}}

# Line 3598 - FAKE USER MESSAGE (tool_result!)
{"message": {"role": "user", "content": [{"type": "tool_result", ...}]}}

# Line 3603 - Assistant block 2 (LOST by naive parser!)
{"message": {"role": "assistant", "content": [{"type": "text", "text": "..."}]}}
```

**Solution**: Filter tool_result messages when identifying user messages

```python
# Check if "user" message is actually a tool_result
if messages[i].get('role') == 'user':
    content = messages[i].get('content', '')

    # FILTER: Skip tool_result messages (not real user messages)
    is_tool_result = False
    if isinstance(content, list):
        is_tool_result = any(
            isinstance(item, dict) and item.get('type') == 'tool_result'
            for item in content
        )

    if is_tool_result:
        continue  # Skip fake user message

# Continue collecting assistant messages through tool_result
while j < len(messages):
    if messages[j].get('role') == 'user':
        # Check if real user or tool_result
        next_content = messages[j].get('content', '')
        is_next_tool_result = False

        if isinstance(next_content, list):
            is_next_tool_result = any(
                isinstance(item, dict) and item.get('type') == 'tool_result'
                for item in next_content
            )

        if not is_next_tool_result:
            break  # Real user message - stop
        else:
            j += 1  # Tool result - skip and continue
            continue

    # Collect assistant message
    if messages[j].get('role') == 'assistant':
        assistant_contents.append(messages[j].get('content', ''))

    j += 1
```

**Impact**: 🔴 CRITICAL - 90% content loss
**Detection**: Conversations <500 chars despite long responses
**Prevention**: Always validate parser on real JSONL before deploying
**Reference**: `EPIC-24_BUGFIX_CRITICAL_COMPLETION_REPORT.md`
**Date Discovered**: 2025-10-29
**Improvement After Fix**: +530% content captured (245 chars → 12,782 chars)

---

## Summary

**Total**: 37 gotchas across 9 domains
- 🔴 Critical: 8 gotchas (MUST NEVER VIOLATE) (+1 Claude Code JSONL parsing)
- 🔵 Database: 5 gotchas
- 🟢 Code Intel: 6 gotchas (+1 JSONL parsing)
- 🟡 Testing: 3 gotchas
- 🟣 Architecture: 3 gotchas
- 🟠 Performance: 3 gotchas
- 🔶 Workflow: 3 gotchas
- 🔷 UI: 3 gotchas
- 🐳 Docker: 3 gotchas

**Progressive Disclosure**: This skill loads only needed sections. Reference table at top provides quick navigation to relevant domains.
