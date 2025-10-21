---
name: mnemolite-gotchas
version: 2.0.0
category: debugging
auto_invoke:
  - error
  - fail
  - debug
  - gotcha
  - slow
  - crash
  - hang
priority: high
metadata:
  created: 2025-10-21
  updated: 2025-10-21
  purpose: MnemoLite-specific gotchas and pitfalls catalog
  structure: progressive_disclosure
  estimated_size_index: 150 lines
  estimated_size_full: 950 lines
  token_cost_index: ~3750 tokens
  token_cost_full: ~23750 tokens
  domains: 8
tags:
  - gotchas
  - debugging
  - troubleshooting
  - critical
---

# MnemoLite Gotchas & Critical Patterns

**Version**: 2.0.0 (Progressive Disclosure Structure)
**Category**: Gotchas, Debugging, Patterns
**Auto-invoke**: error, fail, debug, gotcha, slow, crash, hang

---

## Purpose

Comprehensive catalog of MnemoLite-specific gotchas, pitfalls, critical patterns, and debugging knowledge. This skill prevents common errors and provides quick troubleshooting guidance.

**Structure**: This skill uses progressive disclosure. The index (this file) provides quick reference and pointers to detailed domain files loaded on-demand.

---

## When to Use This Skill

Use this skill when:
- Encountering unexpected errors or failures
- Debugging code behavior
- Implementing new features (check for known pitfalls)
- Code review (verify patterns followed)
- Onboarding new developers

**Problem solved**: Prevents repeating past mistakes, accelerates debugging

---

## Quick Reference by Symptom

| Symptom | Likely Cause | Domain | Quick Fix |
|---------|--------------|--------|-----------|
| Tests pollute dev DB | CRITICAL-01 | @domains/critical.md | Set TEST_DATABASE_URL, `make db-test-reset` |
| App hangs on DB call | CRITICAL-02 | @domains/critical.md | Convert to async/await |
| Type checker errors | CRITICAL-03 | @domains/critical.md | Implement protocol |
| Slow JSONB queries | CRITICAL-04 | @domains/critical.md | Recreate index with jsonb_path_ops |
| Tests take 30s+ | CRITICAL-05 | @domains/critical.md | Set EMBEDDING_MODE=mock |
| Crash when Redis down | CRITICAL-06 | @domains/critical.md | Add graceful fallback |
| QueuePool limit exceeded | CRITICAL-07 | @domains/critical.md | Use `async with` for connections |
| Column does not exist | DB-04 | @domains/database.md | Check exact column names |
| Migration order issues | DB-05 | @domains/database.md | Apply migrations sequentially |
| Symbol paths backwards | CODE-03 | @domains/code-intel.md | Set reverse=True |
| Graph polluted with builtins | CODE-05 | @domains/code-intel.md | Filter PYTHON_BUILTINS |
| HTMX doesn't update | UI-02 | @domains/ui.md | Match hx-target to element ID |
| Git command hangs | GIT-02 | @domains/workflow.md | Remove -i flag |
| Vector query slow | PERF-03 | @domains/performance.md | Add LIMIT clause |

---

## Gotchas by Domain

### 🔴 Critical Gotchas (7 gotchas - MUST NEVER VIOLATE)

**File**: @domains/critical.md

These gotchas break code if violated. Always check before implementing features.

1. **CRITICAL-01**: Test Database Configuration - Separate TEST_DATABASE_URL required
2. **CRITICAL-02**: Async/Await for All DB Operations - ALL db calls must be awaited
3. **CRITICAL-03**: Protocol Implementation Required - DIP enforcement
4. **CRITICAL-04**: JSONB Operator Choice - Use jsonb_path_ops for @>
5. **CRITICAL-05**: Embedding Mode for Tests - EMBEDDING_MODE=mock required
6. **CRITICAL-06**: Cache Graceful Degradation - L1 → L2 → L3 cascade
7. **CRITICAL-07**: Connection Pool Limits - Respect 20+10 pool limit

**When to load**: Building features, debugging crashes, code review

---

### 🟡 Database Gotchas (5 gotchas)

**File**: @domains/database.md

Database-specific patterns, schema, migrations, and optimization.

1. **DB-01**: Partitioning Currently Disabled - Enable at 500k+ events
2. **DB-02**: Vector Index Tuning - m/ef_construction trade-offs
3. **DB-03**: SQL Complexity Calculation - Cast order for nested JSONB
4. **DB-04**: Column Name Exactness - properties NOT props, relation_type NOT relationship
5. **DB-05**: Migration Sequence - Apply in order: v2→v3→v4→v5

**When to load**: Working with PostgreSQL, migrations, database performance

---

### 🟡 Testing Gotchas (3 gotchas)

**File**: @domains/testing.md

Testing patterns, fixtures, and test configuration.

1. **TEST-01**: AsyncClient Configuration - Use ASGITransport(app)
2. **TEST-02**: Fixture Scope - Database fixtures should be function scope
3. **TEST-03**: Test Execution Order - Tests must pass in ANY order

**When to load**: Writing tests, debugging test failures, configuring test environment

---

### 🟡 Architecture Gotchas (3 gotchas)

**File**: @domains/architecture.md

Architectural patterns, DIP principles, and code organization.

1. **ARCH-01**: EXTEND > REBUILD Principle - Copy existing patterns (~10× faster)
2. **ARCH-02**: Service Method Naming - Match protocol method names exactly
3. **ARCH-03**: Repository Layer Boundaries - Use SQLAlchemy Core (NOT ORM)

**When to load**: Building new features, refactoring, ensuring pattern consistency

---

### 🟡 Code Intelligence Gotchas (5 gotchas)

**File**: @domains/code-intel.md

Code indexing, embeddings, symbol paths, and graph construction.

1. **CODE-01**: Embedding Storage Pattern - Store in dict BEFORE CodeChunkCreate
2. **CODE-02**: Dual Embedding Domain - Use EmbeddingDomain.HYBRID for code
3. **CODE-03**: Symbol Path Parent Context - reverse=True CRITICAL
4. **CODE-04**: Strict Containment Bounds - Use < and > (not ≤ and ≥)
5. **CODE-05**: Graph Builtin Filtering - Filter Python builtins

**When to load**: Working with code chunking, embeddings, dependency graphs

---

### 🟡 Git & Workflow Gotchas (3 gotchas)

**File**: @domains/workflow.md

Git patterns, commit conventions, and workflow.

1. **GIT-01**: Commit Message Pattern for EPICs - <type>(EPIC-XX): description
2. **GIT-02**: Interactive Commands Not Supported - Never use -i flag
3. **GIT-03**: Empty Commits - Don't create empty commits

**When to load**: Creating commits, managing branches, following EPIC workflow

---

### 🟡 Performance Gotchas (3 gotchas)

**File**: @domains/performance.md

Performance tuning, caching, and optimization.

1. **PERF-01**: Rollback Safety - ./apply_optimizations.sh rollback recovers in ~10s
2. **PERF-02**: Cache Hit Rate Monitoring - Target 80%+ hit rate
3. **PERF-03**: Vector Query Limits - ALWAYS use LIMIT with vector queries

**When to load**: Optimizing queries, tuning cache, debugging performance

---

### 🟡 UI Gotchas (3 gotchas)

**File**: @domains/ui.md

UI patterns, HTMX, templates, and frontend.

1. **UI-01**: Template Inheritance Pattern - base.html → page.html → partials/
2. **UI-02**: HTMX Partial Targets - Match hx-target to element ID
3. **UI-03**: Cytoscape.js Initialization - Wait for DOMContentLoaded

**When to load**: Building UI features, debugging HTMX, working with templates

---

### 🟡 Docker & Environment Gotchas (3 gotchas)

**File**: @domains/docker.md

Docker configuration, environment variables, and deployment.

1. **DOCKER-01**: Volume Mounting for Live Reload - Mount api/ AND tests/
2. **DOCKER-02**: Redis Memory Limit - 2GB max with LRU eviction
3. **DOCKER-03**: API Port Mapping - 8001:8000 (host:container)

**When to load**: Configuring Docker, debugging containers, managing environments

---

## How to Use Progressive Disclosure

**Level 1** (This index): Quick reference, symptom table, domain overview (~150 lines, ~3750 tokens)

**Level 2** (Domain files): Load specific domain when needed:
- Critical issues → @domains/critical.md
- Database work → @domains/database.md
- Testing → @domains/testing.md
- Architecture → @domains/architecture.md
- Code intelligence → @domains/code-intel.md
- Git/workflow → @domains/workflow.md
- Performance → @domains/performance.md
- UI work → @domains/ui.md
- Docker/env → @domains/docker.md

**Token savings**:
- Index only: ~3750 tokens (vs ~23750 for full monolithic)
- Index + 1 domain: ~6250 tokens (vs ~23750)
- **Savings**: 71-84% when not loading all domains

---

## Related Skills

- **epic-workflow**: EPIC implementation patterns, completion reports
- **document-lifecycle**: Document lifecycle (TEMP→DECISION→ARCHIVE)
- **mnemolite-testing**: Test patterns (references TEST-01 to TEST-03)
- **mnemolite-database**: Database patterns (references DB-01 to DB-05)
- **mnemolite-architecture**: Architecture principles (references ARCH-01 to ARCH-03)
- **mnemolite-code-intel**: Code intelligence patterns (references CODE-01 to CODE-05)
- **mnemolite-ui**: UI patterns (references UI-01 to UI-03)

---

## Version History

- **v2.0.0** (2025-10-21): Progressive disclosure structure, 8 domain files
- **v1.0** (2025-10-21): Initial skill creation, monolithic (920 lines, 31 gotchas)

---

**Total Gotchas**: 31 (7 Critical + 24 domain-specific)
**Structure**: Progressive disclosure (index + 8 domain files)
**Auto-invoke keywords**: error, fail, debug, gotcha, slow, crash, hang
**Maintained by**: Human + AI collaboration

---

# DOMAIN FILES (Progressive Disclosure - All Content Below)

---

# Critical Gotchas (Breaks Code if Violated)

**Purpose**: Critical patterns that MUST be followed to avoid breaking MnemoLite

**When to reference**: Building features, debugging crashes, code review

---

## 🔴 CRITICAL-01: Test Database Configuration

**Rule**: `TEST_DATABASE_URL` must ALWAYS be set to separate test database

```bash
# ✅ CORRECT
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mnemolite_test
EMBEDDING_MODE=mock

# ❌ WRONG - Will pollute dev database
TEST_DATABASE_URL=<not set>  # Uses dev database!
```

**Why**: Without separate test DB, tests will:
- Delete/modify development data
- Create test fixtures in dev DB
- Cause unpredictable behavior

**Detection**: Tests failing with "permission denied" or "relation already exists"

**Fix**:
```bash
# Reset test database
make db-test-reset

# Verify TEST_DATABASE_URL in .env
grep TEST_DATABASE_URL .env
```

---

## 🔴 CRITICAL-02: Async/Await for All Database Operations

**Rule**: ALL database operations MUST use async/await

```python
# ✅ CORRECT
async def get_chunk(chunk_id: UUID) -> Optional[CodeChunkModel]:
    async with self.engine.connect() as conn:
        result = await conn.execute(query)
        return result.fetchone()

# ❌ WRONG - Synchronous database call
def get_chunk(chunk_id: UUID):
    with self.engine.connect() as conn:  # Will hang!
        result = conn.execute(query)
        return result.fetchone()
```

**Why**: MnemoLite uses asyncpg, which requires async patterns. Sync calls will block event loop.

**Detection**: Application hangs, "RuntimeError: no running event loop"

**Fix**: Convert all DB methods to async/await

---

## 🔴 CRITICAL-03: Protocol Implementation Required

**Rule**: New repositories/services MUST implement their Protocol interface

```python
# ✅ CORRECT
from api.interfaces.repos import CodeChunkRepositoryProtocol

class CodeChunkRepository(CodeChunkRepositoryProtocol):
    # Implements all protocol methods
    async def get_by_id(self, chunk_id: UUID) -> Optional[CodeChunkModel]:
        ...

# ❌ WRONG - Missing protocol
class CodeChunkRepository:  # No protocol = architecture violation
    async def get_by_id(self, chunk_id: UUID):
        ...
```

**Why**: Protocols enforce Dependency Inversion Principle (DIP), enable testing, decouple layers

**Detection**: Type checker warnings, dependency injection fails

**Fix**: Import and implement appropriate protocol from `api/interfaces/`

---

## 🔴 CRITICAL-04: JSONB Operator Choice

**Rule**: Use `jsonb_path_ops` for containment (@>) queries, NOT `jsonb_ops`

```sql
-- ✅ CORRECT
CREATE INDEX idx_metadata ON events USING GIN (metadata jsonb_path_ops);
SELECT * FROM events WHERE metadata @> '{"language": "python"}';

-- ❌ WRONG - Much slower for @> queries
CREATE INDEX idx_metadata ON events USING GIN (metadata jsonb_ops);
```

**Why**:
- `jsonb_path_ops` optimized for @> operator (containment)
- Smaller index size (~30% reduction)
- Faster query performance (~2-3× for typical queries)

**Detection**: Slow JSONB queries, large index sizes

**Fix**: Recreate indexes with `jsonb_path_ops`

---

## 🔴 CRITICAL-05: Embedding Mode for Tests

**Rule**: ALWAYS set `EMBEDDING_MODE=mock` when running tests

```bash
# ✅ CORRECT
EMBEDDING_MODE=mock pytest tests/

# ❌ WRONG - Loads actual models (~2GB RAM, slow)
pytest tests/  # Will load sentence-transformers models!
```

**Why**:
- Actual embedding models require ~2.5GB RAM
- Model loading takes ~10-30s per test run
- Tests should be fast (<1s per test)

**Detection**: Tests slow (>30s startup), high memory usage

**Fix**: Set environment variable before running tests

---

## 🔴 CRITICAL-06: Cache Graceful Degradation

**Rule**: Code MUST handle cache failures gracefully (L1 → L2 → L3 cascade)

```python
# ✅ CORRECT
cached = await cache.get(key)
if cached is None:
    # Cache miss or failure - fetch from DB
    result = await self.db_repo.get(key)
    await cache.set(key, result)  # Best effort
    return result
return cached

# ❌ WRONG - Raises exception if cache fails
cached = await cache.get(key)
if not cached:
    raise CacheError("Cache required!")  # System becomes brittle!
```

**Why**: Cache (especially Redis L2) can fail. System must degrade gracefully to L1 + L3 (DB).

**Detection**: System crashes when Redis unavailable

**Fix**: Treat cache as optimization, not requirement. Always fallback to DB.

---

## 🔴 CRITICAL-07: Connection Pool Limits

**Rule**: Respect pool size limits (20 connections max, 10 overflow)

```python
# ✅ CORRECT - Uses connection from pool
async with engine.connect() as conn:
    result = await conn.execute(query)

# ❌ WRONG - Holds connection too long
conn = await engine.connect()  # Leaks connection if not released!
# ... long-running operation ...
await conn.close()  # Might exhaust pool
```

**Why**:
- Pool configured for 20 connections + 10 overflow = 30 max
- Exhausting pool causes "TimeoutError: QueuePool limit exceeded"
- System can handle ~100 req/s with proper pooling

**Detection**: "QueuePool limit exceeded", slow response times

**Fix**: Always use context manager (`async with`) for connections

---

**Total Critical Gotchas**: 7 (must never be violated)

---

# Database Gotchas

**Purpose**: Database-specific patterns, schema, migrations, and optimization gotchas

**When to reference**: Working with PostgreSQL, migrations, or database performance

---

## 🟡 DB-01: Partitioning Currently Disabled

**Status**: Partitioning POSTPONED until 500k+ events

**Why**: Overhead > benefit at current scale (~50k events)

**When to enable**:
```bash
# Monitor events table size
SELECT count(*) FROM events;  # Enable at 500k+

# Activate partitioning
psql < db/scripts/enable_partitioning.sql
```

**Important**: After enabling partitioning:
1. Update PK to composite: `(id, timestamp)`
2. Create vector indexes per partition (not global)
3. Queries will auto-prune partitions (faster)

**Migration**: `db/scripts/enable_partitioning.sql` handles migration

---

## 🟡 DB-02: Vector Index Tuning

**Current**: HNSW indexes use `m=16, ef_construction=64`

**Tuning guidance**:
```sql
-- For recall > performance (research, high-quality results)
CREATE INDEX idx_embedding_high_recall ON events
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);

-- For performance > recall (production, fast results)
CREATE INDEX idx_embedding_fast ON events
USING hnsw (embedding vector_cosine_ops)
WITH (m = 8, ef_construction = 32);

-- Current (balanced)
m=16, ef_construction=64
```

**Trade-off**:
- Higher `m` = better recall, larger index, slower build
- Higher `ef_construction` = better recall, much slower build
- Adjust based on use case

---

## 🟡 DB-03: SQL Complexity Calculation

**Rule**: Cast order matters for JSONB nested numeric extraction

```sql
-- ✅ CORRECT - Cast order: jsonb -> text -> numeric
SELECT AVG(((metadata->>'complexity')::jsonb->>'cyclomatic')::float)
FROM code_chunks;

-- ❌ WRONG - Will fail with type errors
SELECT AVG((metadata->>'complexity')->>'cyclomatic')::float)
```

**Why**: PostgreSQL requires explicit type conversions for nested JSONB

**Pattern**:
1. Extract with `->>` (returns text)
2. Cast to `::jsonb` if nested
3. Extract nested with `->>`
4. Cast final value to target type (`::float`, `::int`, etc.)

---

## 🟡 DB-04: Column Name Exactness

**Rule**: Schema column names must match EXACTLY (no abbreviations)

```sql
-- ✅ CORRECT
SELECT properties, relation_type FROM edges;

-- ❌ WRONG - Will fail
SELECT props, relationship FROM edges;
```

**Schema reference**:
- `nodes.properties` (NOT `props`)
- `edges.relation_type` (NOT `relationship` or `type`)
- `code_chunks.name_path` (NOT `qualified_name`)

**Detection**: "column does not exist" errors

**Fix**: Check schema in `db/init/01-init.sql` or `docs/bdd_schema.md`

---

## 🟡 DB-05: Migration Sequence

**Rule**: Migrations must be applied in order

**Current migration path**:
```
v1 (initial) → v2_to_v3.sql (content_hash) → v3_to_v4.sql (name_path) → v4_to_v5.sql (performance indexes)
```

**How to apply**:
```bash
# Check current version
psql -d mnemolite -c "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1;"

# Apply next migration
psql -d mnemolite < db/migrations/v3_to_v4.sql

# Verify
psql -d mnemolite -c "SELECT version, applied_at FROM schema_version;"
```

**Important**: Migrations are backward-compatible (can rollback)

---

**Total Database Gotchas**: 5

---

# Testing Gotchas

**Purpose**: Testing patterns, fixtures, and test configuration gotchas

**When to reference**: Writing tests, debugging test failures, or configuring test environment

---

## 🟡 TEST-01: AsyncClient Configuration

**Rule**: Use `ASGITransport(app)` for pytest AsyncClient, NOT `app=app`

```python
# ✅ CORRECT
from httpx import AsyncClient, ASGITransport
from api.main import app

async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.get("/health")

# ❌ WRONG - Deprecated, may fail
async with AsyncClient(app=app, base_url="http://test") as client:
    response = await client.get("/health")
```

**Why**: Newer HTTPX versions require explicit transport

**Detection**: Deprecation warnings, test failures

---

## 🟡 TEST-02: Fixture Scope

**Rule**: Database fixtures should be `function` scope for isolation

```python
# ✅ CORRECT - Each test gets clean DB
@pytest.fixture(scope="function")
async def async_engine():
    # Create engine for this test
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()

# ❌ WRONG - Tests share state, cause flaky failures
@pytest.fixture(scope="module")  # Shared across tests!
async def async_engine():
    ...
```

**Why**: Tests should be isolated. Shared DB state causes flaky tests.

**Exception**: Read-only fixtures can use `session` or `module` scope for performance

---

## 🟡 TEST-03: Test Execution Order

**Rule**: Tests must pass in ANY order (no dependencies)

```python
# ✅ CORRECT - Self-contained test
async def test_create_chunk():
    chunk = await create_test_chunk()  # Creates its own data
    assert chunk.id is not None

# ❌ WRONG - Depends on other test running first
async def test_update_chunk():
    chunk = await get_chunk_from_db()  # Assumes chunk exists!
    # Fails if test_create_chunk didn't run first
```

**Detection**: Tests pass when run individually, fail when run together

**Fix**: Each test creates its own fixtures, cleans up after

---

**Total Testing Gotchas**: 3

---

# Architecture Gotchas

**Purpose**: Architectural patterns, DIP principles, and code organization gotchas

**When to reference**: Building new features, refactoring, or ensuring pattern consistency

---

## 🟡 ARCH-01: EXTEND > REBUILD Principle

**Rule**: When adding features, COPY existing pattern and adapt (don't rebuild)

```python
# ✅ CORRECT - Copy graph.html → code_graph.html
# File: templates/code_graph.html
{% extends "base.html" %}
<!-- Copied from graph.html, adapted for code -->

# ❌ WRONG - Rebuild from scratch
# File: templates/code_graph.html
<!-- New implementation, different patterns -->
```

**Why**:
- ~10× faster development
- Consistent patterns across codebase
- Easier maintenance (familiar structure)

**Examples**:
- `graph.html` → `code_graph.html` (UI)
- `event_repository.py` → `code_chunk_repository.py` (Backend)
- `test_event_routes.py` → `test_code_routes.py` (Tests)

---

## 🟡 ARCH-02: Service Method Naming

**Rule**: Service method names must match conventions (not arbitrary)

```python
# ✅ CORRECT
class GraphConstructionService:
    async def build_graph_for_repository(self, repo: str):
        ...

# ❌ WRONG - Wrong method name
class GraphConstructionService:
    async def build_repository_graph(self, repo: str):  # Breaks DI!
        ...
```

**Why**: Dependency injection expects specific method names from protocol

**Detection**: `AttributeError: 'GraphConstructionService' object has no attribute 'build_graph_for_repository'`

**Fix**: Check protocol definition, match method name exactly

---

## 🟡 ARCH-03: Repository Layer Boundaries

**Rule**: Repositories use SQLAlchemy Core (NOT ORM)

```python
# ✅ CORRECT - Core (text + execute)
from sqlalchemy import text

async with conn.execute(text("""
    SELECT * FROM code_chunks WHERE id = :chunk_id
"""), {"chunk_id": chunk_id}) as result:
    row = result.fetchone()

# ❌ WRONG - ORM (Session, declarative models)
from sqlalchemy.orm import Session
session.query(CodeChunkORM).filter_by(id=chunk_id).first()
```

**Why**:
- Core = explicit SQL, better performance, async-first
- ORM = implicit SQL, more overhead, sync-biased

**Exception**: None. MnemoLite uses Core exclusively.

---

**Total Architecture Gotchas**: 3

---

# Code Intelligence Gotchas

**Purpose**: Code indexing, embeddings, symbol paths, and graph construction gotchas

**When to reference**: Working with code chunking, embeddings, or dependency graphs

---

## 🟡 CODE-01: Embedding Storage Pattern

**Rule**: Store embeddings in dict BEFORE creating `CodeChunkCreate` model

```python
# ✅ CORRECT
embeddings = {
    "embedding_text": text_vector,
    "embedding_code": code_vector
}
chunk = CodeChunkCreate(
    file_path=path,
    source_code=code,
    **embeddings  # Add embeddings to dict
)

# ❌ WRONG - Cannot assign to Pydantic model after creation
chunk = CodeChunkCreate(file_path=path, source_code=code)
chunk.embedding_text = text_vector  # Pydantic error!
```

**Why**: Pydantic models are immutable after creation

**Detection**: `ValidationError: "CodeChunkCreate" object has no field "embedding_text"`

---

## 🟡 CODE-02: Dual Embedding Domain

**Rule**: Code chunks MUST use `EmbeddingDomain.HYBRID` (not TEXT only)

```python
# ✅ CORRECT
from api.models.embedding import EmbeddingDomain

embeddings = await embedding_service.generate_embeddings(
    texts=[chunk.source_code],
    domain=EmbeddingDomain.HYBRID  # Loads both TEXT + CODE models
)

# ❌ WRONG - Missing code embedding
embeddings = await embedding_service.generate_embeddings(
    texts=[chunk.source_code],
    domain=EmbeddingDomain.TEXT  # Only text model!
)
```

**Why**:
- Code search requires dual embeddings (text + code)
- CODE model: `jina-embeddings-v2-base-code`
- TEXT model: `nomic-embed-text-v1.5`
- RAM usage: ~2.5GB for both models

**Detection**: Code search returns poor results, only text embedding populated

---

## 🟡 CODE-03: Symbol Path Parent Context

**Rule**: `reverse=True` is CRITICAL when extracting parent context

```python
# ✅ CORRECT - Outermost to innermost
parents = extract_parent_context(
    parent_nodes,
    chunk_start=chunk.start_line,
    chunk_end=chunk.end_line,
    reverse=True  # CRITICAL!
)
# Result: ["OuterClass", "MiddleClass", "InnerClass"]

# ❌ WRONG - Innermost to outermost (backwards!)
parents = extract_parent_context(..., reverse=False)
# Result: ["InnerClass", "MiddleClass", "OuterClass"]  # Wrong order!
```

**Why**: Symbol paths are hierarchical, must be outermost-first for correctness

**Example**: `models.user.User.validate` (NOT `validate.User.user.models`)

**Detection**: Symbol search fails, name_path looks backwards

---

## 🟡 CODE-04: Strict Containment Bounds

**Rule**: Use `<` and `>` (strict), NOT `≤` and `≥` for containment checks

```python
# ✅ CORRECT - Strict containment
def is_contained(parent_start, parent_end, chunk_start, chunk_end):
    return parent_start < chunk_start and chunk_end < parent_end

# ❌ WRONG - Boundary false positives
def is_contained(parent_start, parent_end, chunk_start, chunk_end):
    return parent_start <= chunk_start and chunk_end <= parent_end
```

**Why**: Prevents false positives when chunk boundary equals parent boundary

**Example**:
- Parent: lines 10-20
- Chunk: lines 10-15
- With `<=`: FALSE POSITIVE (chunk starts at same line as parent)
- With `<`: CORRECT (chunk must start AFTER parent)

**Detection**: Incorrect parent context, symbol paths include siblings

---

## 🟡 CODE-05: Graph Builtin Filtering

**Rule**: Filter Python builtins when building dependency graph

```python
# ✅ CORRECT
PYTHON_BUILTINS = {"print", "len", "range", "list", "dict", ...}

if target_name not in PYTHON_BUILTINS:
    edges.append(Edge(source=source_id, target=target_id, relation="calls"))

# ❌ WRONG - Graph polluted with builtins
edges.append(Edge(source=source_id, target=target_id, relation="calls"))
# Results in edges to "print", "len", etc. (noise!)
```

**Why**: Builtins are not interesting for dependency analysis, pollute graph

**Detection**: Graph has thousands of edges to "print", "len", etc.

**Builtin lists**: Available in `api/services/graph_construction_service.py`

---

**Total Code Intelligence Gotchas**: 5

---

# Git & Workflow Gotchas

**Purpose**: Git patterns, commit conventions, and workflow gotchas

**When to reference**: Creating commits, managing branches, or following EPIC workflow

---

## 🟡 GIT-01: Commit Message Pattern for EPICs

**Rule**: EPIC commits follow specific pattern

```bash
# ✅ CORRECT
git commit -m "feat(EPIC-12): Implement Story 12.3 - Circuit Breakers (5 pts)"
git commit -m "docs(EPIC-11): Update Story 11.2 completion report"
git commit -m "fix(EPIC-10): Correct cache TTL calculation"

# ❌ WRONG - No EPIC reference
git commit -m "Add circuit breakers"
git commit -m "Update docs"
```

**Pattern**: `<type>(EPIC-XX): <description>`

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

**Why**: Easy to track EPIC progress, filter commits by EPIC

---

## 🟡 GIT-02: Interactive Commands Not Supported

**Rule**: NEVER use `-i` flag with git commands (not supported in Docker)

```bash
# ✅ CORRECT
git add file1.py file2.py

# ❌ WRONG - Will hang
git add -i  # Interactive mode not supported!
git rebase -i HEAD~3  # Will hang!
```

**Why**: Docker exec doesn't support interactive TTY for git

**Detection**: Command hangs indefinitely

**Fix**: Use non-interactive alternatives

---

## 🟡 GIT-03: Empty Commits

**Rule**: If no changes to commit, don't create empty commit

```bash
# Check if changes exist
git status

# If "nothing to commit", skip commit
# DON'T: git commit --allow-empty
```

**Why**: Empty commits pollute history, provide no value

**Detection**: `git log` shows commits with no diff

---

**Total Git & Workflow Gotchas**: 3

---

# Performance & Optimization Gotchas

**Purpose**: Performance tuning, caching, and optimization gotchas

**When to reference**: Optimizing queries, tuning cache, or debugging performance issues

---

## 🟡 PERF-01: Rollback Safety

**Rule**: `./apply_optimizations.sh rollback` recovers system in ~10s

```bash
# Apply optimizations
./apply_optimizations.sh apply

# Benchmark
./apply_optimizations.sh benchmark

# If slower, rollback
./apply_optimizations.sh rollback  # ~10s recovery
```

**Why**: Backups created automatically, safe to experiment

**Backups location**: `backups/YYYY-MM-DD_HH-MM-SS/`

---

## 🟡 PERF-02: Cache Hit Rate Monitoring

**Rule**: Monitor cache hit rate, adjust TTL if <80%

```bash
# Check cache stats
curl http://localhost:8001/v1/events/cache/stats | jq

# Adjust TTL if hit rate low
# See api/services/caches/redis_cache.py
```

**Target**: 80%+ hit rate

**TTL values**:
- Events: 60s
- Search: 30s
- Graph: 120s

**Tuning**: Increase TTL if hit rate low, decrease if stale data problem

---

## 🟡 PERF-03: Vector Query Limits

**Rule**: ALWAYS use `LIMIT` with vector similarity queries

```sql
-- ✅ CORRECT
SELECT * FROM events
ORDER BY embedding <=> :query_vector
LIMIT 20;  -- CRITICAL!

-- ❌ WRONG - Scans entire table!
SELECT * FROM events
ORDER BY embedding <=> :query_vector;
```

**Why**: Without LIMIT, HNSW index not used efficiently. Scans all vectors.

**Detection**: Slow vector queries (>500ms), high CPU usage

**Typical limits**: 10-50 results (user-facing), 100-200 (internal)

---

**Total Performance Gotchas**: 3

---

# UI Gotchas

**Purpose**: UI patterns, HTMX, templates, and frontend gotchas

**When to reference**: Building UI features, debugging HTMX, or working with templates

---

## 🟡 UI-01: Template Inheritance Pattern

**Rule**: Follow `base.html` → `page.html` → `partials/*.html` hierarchy

```html
<!-- ✅ CORRECT -->
<!-- templates/code_search.html -->
{% extends "base.html" %}
{% block content %}
  {% include "partials/code_results.html" %}
{% endblock %}

<!-- ❌ WRONG - Skips base -->
<!-- templates/code_search.html -->
<!DOCTYPE html>
<html>
  <!-- Rebuilds everything! -->
</html>
```

**Why**: Consistent layout, shared navbar/footer, DRY principle

---

## 🟡 UI-02: HTMX Partial Targets

**Rule**: HTMX partials must have target IDs matching hx-target

```html
<!-- ✅ CORRECT -->
<div hx-get="/api/search" hx-target="#results">Search</div>
<div id="results"><!-- Partial loaded here --></div>

<!-- ❌ WRONG - Target mismatch -->
<div hx-get="/api/search" hx-target="#results">Search</div>
<div id="search-results"><!-- Won't update! --></div>
```

**Detection**: HTMX request succeeds but UI doesn't update

---

## 🟡 UI-03: Cytoscape.js Initialization

**Rule**: Wait for DOM ready before initializing Cytoscape

```javascript
// ✅ CORRECT
document.addEventListener('DOMContentLoaded', function() {
    const cy = cytoscape({ container: document.getElementById('cy'), ... });
});

// ❌ WRONG - Container not ready
const cy = cytoscape({ container: document.getElementById('cy'), ... });
// Runs before DOM loads!
```

**Detection**: "Container not found" error, graph doesn't render

---

**Total UI Gotchas**: 3

---

# Docker & Environment Gotchas

**Purpose**: Docker configuration, environment variables, and deployment gotchas

**When to reference**: Configuring Docker, debugging container issues, or managing environments

---

## 🟡 DOCKER-01: Volume Mounting for Live Reload

**Rule**: API and tests directories mounted for live reload

```yaml
# ✅ CORRECT - docker-compose.yml
volumes:
  - ./api:/app
  - ./tests:/app/tests  # Tests also mounted!

# ❌ WRONG - Tests not mounted
volumes:
  - ./api:/app
```

**Why**: Without test volume, changes to tests require rebuild

---

## 🟡 DOCKER-02: Redis Memory Limit

**Rule**: Redis configured with 2GB max memory + LRU eviction

```yaml
# docker-compose.yml
redis:
  command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

**Why**: Prevents Redis from consuming all system memory

**Monitoring**:
```bash
docker exec mnemo-redis redis-cli INFO memory | grep maxmemory
```

---

## 🟡 DOCKER-03: API Port Mapping

**Rule**: External port 8001, internal port 8000

```yaml
# docker-compose.yml
api:
  ports:
    - "8001:8000"  # Host:Container
```

**Access**:
- From host: `http://localhost:8001`
- From container: `http://api:8000`
- Docs: `http://localhost:8001/docs`

---

**Total Docker Gotchas**: 3

