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
