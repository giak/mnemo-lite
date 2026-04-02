# EPIC-12: Robustness & Error Handling - Comprehensive Analysis

**Date**: 2025-10-21 (Initial Analysis)
**Status**: ✅ PARTIALLY COMPLETE (Stories 12.1, 12.2, 12.3 DONE - 13/23 pts)
**Analyst**: Claude (Architecture Team)
**Epic Points**: 23 pts (updated from initial 18 pts - scope evolved)
**Depends On**: EPIC-10 (Cache layer ✅), EPIC-11 (Symbol paths ✅)

> **Note**: This is the initial comprehensive analysis. Story points and scope were adjusted during implementation:
> - Story 12.2 reduced from 5 to 3 pts (narrower scope - transaction boundaries only)
> - Story 12.3 increased from 3 to 5 pts (circuit breakers more complex than anticipated)
> - Stories 12.4 and 12.5 increased to 5 pts each (error tracking and retry logic)
> - See individual completion reports for actual implementation details

---

## 🎯 Executive Summary

EPIC-12 aims to transform MnemoLite from a development prototype to a **production-ready system** by implementing enterprise-grade robustness patterns. This analysis provides a comprehensive review of dependencies, technical feasibility, risks, and implementation strategy.

**Key Finding**: EPIC-12 is **READY FOR IMPLEMENTATION** with all dependencies satisfied. However, several **critical edge cases** and **integration challenges** have been identified that must be addressed.

---

## 📊 Part 1: Dependency Analysis

### ✅ Satisfied Dependencies

| Dependency | Status | Evidence |
|------------|--------|----------|
| **EPIC-10: Cache Layer** | ✅ COMPLETE | CascadeCache, RedisCache, CodeChunkCache implemented |
| **EPIC-11: Symbol Paths** | ✅ COMPLETE | name_path field, qualified search, 31/31 tests passing |
| **PostgreSQL 18** | ✅ DEPLOYED | pgvector, pg_partman, async support |
| **Redis 7** | ✅ DEPLOYED | 2GB cache, LRU eviction |
| **AsyncIO Infrastructure** | ✅ READY | SQLAlchemy 2.0+, asyncpg, FastAPI async |
| **Structured Logging** | ⚠️ PARTIAL | Using standard logging, not structlog yet |

### ⚠️ New Dependencies Required

| Dependency | Type | Purpose | Installation |
|------------|------|---------|--------------|
| **structlog** | Python | Structured logging for error tracking | `pip install structlog` |
| **tenacity** (optional) | Python | Alternative retry library | `pip install tenacity` |

### 🔍 Code Inventory - Current State

**Existing Robustness Patterns**:
```bash
# Transaction usage: 33 occurrences in api/db/
# Timeout usage: 2 occurrences (minimal)
# Error handling: Scattered, no centralized pattern
```

**Existing Cache Infrastructure**:
- ✅ `CascadeCache` (L1 + L2 redis)
- ✅ `RedisCache` with metrics
- ✅ `CodeChunkCache` (100MB LRU)
- ⚠️ **No circuit breaker** for Redis failures
- ⚠️ **No graceful degradation** if Redis down

**Existing Services Needing Robustness**:
1. `code_chunking_service.py` - Tree-sitter parsing (can hang)
2. `dual_embedding_service.py` - Embedding generation (can OOM)
3. `code_indexing_service.py` - Multi-step pipeline (needs transactions)
4. `hybrid_code_search_service.py` - Uses tree-sitter + embeddings
5. `graph_construction_service.py` - Graph building (can be slow)

---

## 🧠 Part 2: Deep Technical Analysis

### Story 12.1: Timeout-Based Execution (5 pts)

**Current State**: ❌ Almost no timeouts
```python
# api/services/code_chunking_service.py
async def chunk_code(self, source_code: str, language: str):
    tree = self.parser.parse(bytes(source_code, "utf8"))  # NO TIMEOUT
    # Pathological input → infinite loop possible
```

**Proposed Solution**:
```python
@timeout_decorator(timeout=5.0, operation_name="tree_sitter_parse")
async def chunk_code(self, source_code: str, language: str):
    ...
```

**✅ Feasibility**: HIGH
- `asyncio.wait_for()` is battle-tested
- Decorator pattern clean and non-invasive
- Timeout values configurable

**⚠️ Challenges Identified**:

1. **Tree-sitter is CPU-bound, not async**
   - Problem: `tree_sitter.parse()` is **synchronous**
   - Solution: Wrap in `asyncio.to_thread()`:
   ```python
   async def chunk_code(self, source_code: str, language: str):
       tree = await asyncio.to_thread(
           self.parser.parse,
           bytes(source_code, "utf8")
       )
   ```
   - ⚠️ **Critical**: This requires testing - `to_thread()` creates thread pool overhead

2. **Embedding generation is also CPU-bound**
   - Sentence transformers use PyTorch/NumPy
   - Already async in current implementation (uses `asyncio.to_thread` internally?)
   - **Action**: Verify current async implementation

3. **Timeout granularity**
   - Question: Per-file or per-operation?
   - **Recommendation**: Both
     - Per-operation: `tree_sitter_parse: 5s`
     - Per-file total: `index_file: 30s` (cumulative)

**🎯 Implementation Priority**: **Story 12.1 = HIGHEST PRIORITY**
- Blocking risk: Infinite hangs can DoS the system
- Low complexity: Decorator pattern is simple
- High impact: Prevents production outages

---

### Story 12.2: Transactional Indexing (5 pts)

**Current State**: ⚠️ Partial transactions
```python
# api/services/code_indexing_service.py
async def index_file(self, ...):
    chunks = await self.chunking_service.chunk_code(...)
    embeddings = await self.embedding_service.generate(...)
    await self.chunk_repository.create_many(chunks, embeddings)  # ✅ Transaction here
    await self.graph_service.build_graph(...)  # ⚠️ Separate transaction!
```

**Problem**: Multi-transaction indexing → partial failures possible
- Chunks stored ✅
- Graph not built ❌
- Result: Inconsistent state

**Proposed Solution**:
```python
async with atomic_transaction(self.db_engine, self.cache) as tx:
    # All operations in same transaction
    chunks_db = await chunk_repo.create_many(..., tx=tx["connection"])
    await graph_service.build_graph(..., tx=tx["connection"])
    # Commit or rollback together
```

**✅ Feasibility**: HIGH
- SQLAlchemy `async with engine.begin()` supports nested transactions
- Context manager pattern is Pythonic

**⚠️ Challenges Identified**:

1. **Cache invalidation timing**
   - Question: When to invalidate cache on rollback?
   - Current proposal: Track `rollback_cache_keys` in transaction context
   - **Edge case**: What if cache invalidation itself fails?
   ```python
   try:
       await cache.invalidate(key)
   except RedisError:
       # Cache stale, but database rolled back
       # ⚠️ Cache-database inconsistency!
       logger.error("Failed to invalidate cache during rollback")
   ```
   - **Solution**: Best-effort invalidation + TTL expiry (cache will fix itself)

2. **Long-running transactions**
   - Embedding generation can take 5-10s
   - Graph construction can take 2-5s
   - Total transaction time: **15s+**
   - ⚠️ **Problem**: PostgreSQL lock contention
   - **Solution**:
     - Option A: Generate embeddings BEFORE transaction
     - Option B: Use `SELECT ... FOR UPDATE SKIP LOCKED` for concurrent access

   **Recommendation**: Option A (embeddings outside transaction)
   ```python
   # OUTSIDE transaction (can fail without DB impact)
   embeddings = await generate_embeddings(chunks)

   # INSIDE transaction (fast operations only)
   async with atomic_transaction(...) as tx:
       await store_chunks(chunks, embeddings, tx)
       await build_graph(chunks, tx)
   ```

3. **Idempotency**
   - Re-indexing same file → duplicate chunks?
   - **Current**: `code_chunks` has unique constraint on `(file_path, repository, commit_hash)`?
   - **Action**: Verify schema, add `ON CONFLICT DO UPDATE` if needed

**🎯 Implementation Priority**: **Story 12.2 = HIGH PRIORITY**
- Blocking risk: Data corruption in production
- Medium complexity: Transaction boundaries need careful design
- High impact: Data integrity critical

---

### Story 12.3: Graceful Degradation (3 pts)

**Current State**: ❌ No fallback mechanisms
```python
# If Redis down → entire app fails
cache_result = await redis_cache.get(key)  # Raises RedisConnectionError
```

**Proposed Solution**: Circuit breaker pattern

**✅ Feasibility**: HIGH
- Circuit breaker is well-understood pattern
- Clean separation of concerns

**⚠️ Challenges Identified**:

1. **Redis failure modes**
   - Connection timeout: Retry possible
   - Authentication failure: Not retryable
   - Network partition: Retry after delay
   - **Recommendation**: Circuit breaker + exponential backoff

2. **LSP service not yet implemented**
   - EPIC-12 spec mentions LSP degradation
   - **Status**: LSP is planned for EPIC-13
   - **Action**: Make Story 12.3 **LSP-agnostic** (future-proof)
   ```python
   # Generic pattern for external services
   @with_circuit_breaker(service="external_api")
   async def call_external_service(...):
       ...
   ```

3. **Embedding service degradation**
   - If embedding generation fails → what?
   - **Option A**: Store chunks without embeddings (⚠️ breaks vector search)
   - **Option B**: Fail indexing (❌ too aggressive)
   - **Option C**: Queue for retry (✅ best)

   **Recommendation**: Option C - Add to `failed_embeddings` table
   ```sql
   CREATE TABLE failed_embeddings (
       chunk_id UUID REFERENCES code_chunks(id),
       retry_count INT DEFAULT 0,
       last_error TEXT,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```
   - Background worker retries failed embeddings
   - Chunks searchable via lexical search immediately

4. **Health endpoint design**
   - Current `/health` → binary (up/down)
   - Proposed → **tristate** (healthy/degraded/unhealthy)
   ```json
   {
     "status": "degraded",  // overall
     "services": {
       "postgresql": "healthy",
       "redis": "degraded",  // circuit breaker OPEN
       "embedding": "healthy"
     }
   }
   ```

**🎯 Implementation Priority**: **Story 12.3 = MEDIUM PRIORITY**
- Not blocking: Can launch without LSP
- Medium complexity: Circuit breaker state machine
- High impact: Resilience to external failures

---

### Story 12.4: Error Tracking (3 pts)

**Current State**: ⚠️ Logging only, no aggregation
```python
logger.error(f"Indexing failed: {e}")  # Lost in logs
```

**Proposed Solution**: `errors` table + stats endpoint

**✅ Feasibility**: HIGH
- PostgreSQL table → simple
- Aggregation query → straightforward SQL

**⚠️ Challenges Identified**:

1. **Error table growth**
   - 1000 errors/day × 365 days = 365k rows/year
   - **Solution**: Partition by month + retention policy
   ```sql
   CREATE TABLE errors (
       id UUID,
       timestamp TIMESTAMPTZ,
       ...
   ) PARTITION BY RANGE (timestamp);

   -- Auto-drop partitions older than 90 days
   ```

2. **Performance impact**
   - Every error → INSERT into `errors` table
   - **Concern**: Error logging shouldn't slow down error recovery
   - **Solution**: Async fire-and-forget
   ```python
   asyncio.create_task(error_repo.create(...))  # Don't await
   ```

3. **PII/sensitive data in errors**
   - Tracebacks may contain file paths, repository names
   - **Action**: Add PII scrubbing
   ```python
   def sanitize_error(error_message: str) -> str:
       # Remove absolute paths, tokens, etc.
       return re.sub(r'/home/[^/]+', '/home/<user>', error_message)
   ```

4. **Error stats endpoint security**
   - `/v1/errors/stats` → exposes internal system state
   - **Recommendation**: Require authentication
   ```python
   @router.get("/stats", dependencies=[Depends(require_admin)])
   ```

**🎯 Implementation Priority**: **Story 12.4 = LOW PRIORITY**
- Not blocking: Can add post-launch
- Low complexity: Basic CRUD + aggregation
- Medium impact: Observability improves over time

---

### Story 12.5: Retry Logic (2 pts)

**Current State**: ❌ No automatic retries

**Proposed Solution**: Exponential backoff decorator

**✅ Feasibility**: HIGH
- Well-established pattern
- Libraries exist (`tenacity`) but custom implementation simple

**⚠️ Challenges Identified**:

1. **Idempotency requirement**
   - Only retry **idempotent** operations
   - Example: `cache.get(key)` → ✅ idempotent
   - Example: `chunk_repo.create(chunk)` → ❌ NOT idempotent (unless `ON CONFLICT`)

   **Recommendation**: Explicit decorator parameter
   ```python
   @retry_decorator(max_attempts=3, idempotent=True)  # Safety check
   async def get_from_cache(key):
       ...
   ```

2. **Retry storm**
   - All clients retry at same time → thundering herd
   - **Solution**: Add jitter to backoff
   ```python
   import random
   delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
   ```

3. **Retry + timeout interaction**
   - If operation has 5s timeout and 3 retries → total 15s?
   - **Action**: Clarify interaction
   ```python
   @retry_decorator(max_attempts=3)
   @timeout_decorator(timeout=5.0)  # Per-attempt timeout
   async def slow_operation():
       # Each retry has 5s timeout
       # Total possible time: 15s
   ```

4. **What errors are retryable?**
   - Network errors: ✅ Retryable
   - Timeout errors: ⚠️ Maybe (depends on operation)
   - Validation errors: ❌ NOT retryable

   **Recommendation**: Explicit exception whitelist
   ```python
   @retry_decorator(
       max_attempts=3,
       retryable_exceptions=(redis.ConnectionError, asyncio.TimeoutError)
   )
   ```

**🎯 Implementation Priority**: **Story 12.5 = MEDIUM PRIORITY**
- Not blocking: Nice-to-have for resilience
- Low complexity: Simple decorator
- Medium impact: Reduces transient failure rate

---

## 🎨 Part 3: Architecture Deep Dive

### Proposed Component Structure

```
api/
├── utils/                      # NEW: Robustness utilities
│   ├── timeout.py              # with_timeout(), timeout_decorator()
│   ├── transaction.py          # atomic_transaction() context manager
│   ├── circuit_breaker.py      # CircuitBreaker class
│   └── retry.py                # retry_with_backoff(), retry_decorator()
│
├── config/                     # NEW: Configuration
│   └── timeouts.py             # Centralized timeout values
│
├── db/
│   ├── repositories/
│   │   └── error_repository.py # NEW: Error tracking repository
│   └── init/
│       └── 01-init.sql         # MODIFY: Add errors table
│
├── routes/
│   ├── health.py               # MODIFY: Add degradation status
│   └── error_routes.py         # NEW: Error stats endpoint
│
└── services/
    ├── code_chunking_service.py         # MODIFY: Add @timeout_decorator
    ├── dual_embedding_service.py        # MODIFY: Add @timeout_decorator
    ├── code_indexing_service.py         # MODIFY: Add transaction, circuit breakers
    ├── graph_construction_service.py    # MODIFY: Add @timeout_decorator
    └── caches/
        └── redis_cache.py               # MODIFY: Add @retry_decorator
```

### Decorator Stacking Order

**Critical Decision**: How to stack multiple decorators?

```python
# CORRECT ORDER (innermost first):
@retry_decorator(max_attempts=3)         # Outermost: Retry wrapper
@timeout_decorator(timeout=5.0)          # Middle: Per-retry timeout
@circuit_breaker_decorator(service="lsp") # Innermost: Circuit breaker check
async def call_lsp_service():
    ...

# EXECUTION FLOW:
# 1. retry_decorator checks if should retry
# 2. timeout_decorator starts timer
# 3. circuit_breaker checks if circuit OPEN
# 4. If OPEN → raises immediately (skips timeout, retry continues)
# 5. If CLOSED → executes function with timeout
# 6. If timeout → retry may attempt again
```

**Rationale**: Circuit breaker should be **innermost** to short-circuit quickly.

---

## ⚠️ Part 4: Risk Analysis & Edge Cases

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Priority |
|------|-----------|--------|------------|----------|
| Timeout too aggressive | MEDIUM | HIGH | Configurable timeouts, monitoring | P0 |
| Transaction deadlocks | LOW | HIGH | Short transactions, timeouts | P1 |
| Circuit breaker false positives | MEDIUM | MEDIUM | Conservative thresholds | P2 |
| Error table growth | HIGH | LOW | Partitioning, retention | P3 |
| Cache-DB inconsistency | LOW | HIGH | Best-effort + TTL | P1 |
| Retry storm | LOW | MEDIUM | Jitter, exponential backoff | P2 |

### Critical Edge Cases

**Edge Case #1: Timeout during database commit**
```python
async with atomic_transaction(db) as tx:
    await store_chunks(tx)
    await tx.commit()  # ⏱️ What if timeout HERE?
```
- **Problem**: Timeout after commit started → may partially commit
- **Solution**: Commit operation excluded from timeout
```python
@timeout_decorator(timeout=30.0, exclude_commit=True)
async def index_file(...):
    async with atomic_transaction(db) as tx:
        ...
        # Commit happens outside timeout scope
```

**Edge Case #2: Circuit breaker during transaction**
```python
async with atomic_transaction(db) as tx:
    await store_chunks(tx)
    await cache.put(...)  # Circuit breaker OPENS here
    # Transaction rolls back, but chunks not cached
```
- **Problem**: Cache operation failure shouldn't rollback DB
- **Solution**: Cache operations **outside** transaction
```python
async with atomic_transaction(db) as tx:
    chunk_ids = await store_chunks(tx)
# Cache AFTER successful commit
await cache.put(chunk_ids)  # Failure here is OK
```

**Edge Case #3: Concurrent indexing of same file**
```python
# Thread A: Starts indexing file.py
# Thread B: Starts indexing file.py (same content)
# Both try to insert same chunks → conflict
```
- **Current**: `code_chunks` may have `(file_path, repository)` unique constraint
- **Solution**: `ON CONFLICT DO UPDATE SET indexed_at = NOW()`
```sql
INSERT INTO code_chunks (...) VALUES (...)
ON CONFLICT (file_path, repository, commit_hash)
DO UPDATE SET indexed_at = NOW(), ...
RETURNING id;
```

**Edge Case #4: Redis failover**
```python
# Redis primary goes down
# Sentinel promotes replica
# Circuit breaker sees failures → OPEN
# But Redis is now healthy (new primary)
```
- **Problem**: Circuit breaker doesn't know about failover
- **Solution**: Short timeout window (30-60s) + health checks
```python
CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=30,  # Quick recovery
    health_check=lambda: redis.ping()  # Active health check
)
```

**Edge Case #5: Out-of-order error logging**
```python
# Main thread: Starts indexing
# Error thread: Logs error async
# Main thread: Completes successfully
# Error log: Appears AFTER success log (confusing!)
```
- **Problem**: Async error logging → timing inconsistency
- **Solution**: Include correlation ID
```python
import uuid
request_id = str(uuid.uuid4())
logger.info("Starting indexing", request_id=request_id)
asyncio.create_task(log_error(request_id, error))  # Tagged
```

---

## 🔬 Part 5: Implementation Strategy

### Phase 1: Foundations (Week 1)
**Stories**: 12.1 (Timeouts), 12.5 (Retry)
**Rationale**: Independent utilities, no complex integration

1. Create `api/utils/timeout.py` with `with_timeout()` and `timeout_decorator()`
2. Create `api/utils/retry.py` with `retry_with_backoff()` and `retry_decorator()`
3. Create `api/config/timeouts.py` with timeout configuration
4. **Testing**: Unit tests for timeout and retry logic
5. **Validation**: Apply to ONE service (e.g., `code_chunking_service.py`)

**Deliverables**:
- ✅ Timeout utilities working
- ✅ Retry utilities working
- ✅ 20+ unit tests passing

### Phase 2: Transactions (Week 2)
**Stories**: 12.2 (Transactional Indexing)
**Rationale**: Builds on Phase 1 timeouts

1. Create `api/utils/transaction.py` with `atomic_transaction()` context manager
2. Modify `code_indexing_service.py` to use transactions
3. Add cache invalidation logic on rollback
4. **Testing**: Integration tests for rollback scenarios
5. **Validation**: Verify cache consistency after failures

**Deliverables**:
- ✅ Atomic indexing working
- ✅ Rollback + cache invalidation tested
- ✅ 15+ integration tests passing

### Phase 3: Degradation (Week 3)
**Stories**: 12.3 (Graceful Degradation)
**Rationale**: Requires transaction foundation

1. Create `api/utils/circuit_breaker.py` with `CircuitBreaker` class
2. Integrate circuit breakers into `code_indexing_service.py` for Redis
3. Modify `/health` endpoint to show degradation status
4. **Testing**: Chaos testing (kill Redis, verify degradation)
5. **Validation**: Manual testing with Redis failures

**Deliverables**:
- ✅ Circuit breaker working
- ✅ Health endpoint accurate
- ✅ System functional with Redis down

### Phase 4: Observability (Week 4)
**Stories**: 12.4 (Error Tracking)
**Rationale**: Orthogonal to other stories, can be last

1. Add `errors` table to `db/init/01-init.sql`
2. Create `error_repository.py`
3. Create `/v1/errors/stats` endpoint
4. Integrate error logging into all services
5. **Testing**: Verify error aggregation queries
6. **Validation**: Trigger errors, check stats endpoint

**Deliverables**:
- ✅ Error tracking functional
- ✅ Stats endpoint working
- ✅ Error patterns visible

---

## 🎯 Part 6: Testing Strategy

### Test Categories

**1. Unit Tests (80 tests total)**
```python
tests/utils/
├── test_timeout.py (20 tests)
│   ├── test_timeout_enforced()
│   ├── test_timeout_not_reached()
│   ├── test_timeout_decorator()
│   ├── test_nested_timeouts()
│   └── ...
├── test_transaction.py (15 tests)
├── test_circuit_breaker.py (25 tests)
└── test_retry.py (20 tests)
```

**2. Integration Tests (40 tests total)**
```python
tests/integration/
├── test_timeout_enforcement.py (15 tests)
│   ├── test_tree_sitter_timeout()
│   ├── test_embedding_timeout()
│   └── ...
├── test_transactional_indexing.py (15 tests)
│   ├── test_rollback_on_embedding_failure()
│   ├── test_cache_invalidated_on_rollback()
│   └── ...
└── test_graceful_degradation.py (10 tests)
```

**3. Chaos Tests (10 tests)**
```python
tests/chaos/
└── test_failure_scenarios.py (10 tests)
    ├── test_redis_failure_during_indexing()
    ├── test_concurrent_indexing_same_file()
    ├── test_database_connection_loss()
    └── ...
```

**4. Performance Tests**
```python
tests/performance/
└── test_overhead.py
    ├── test_timeout_overhead()        # <1% overhead
    ├── test_transaction_overhead()    # <5% overhead
    └── test_error_logging_overhead()  # <0.1% overhead
```

### Test Environment Setup

**Docker Compose chaos testing**:
```yaml
services:
  test-redis:
    image: redis:7-alpine
    # Add chaos-monkey sidecar
    command: redis-server --save "" --appendonly no
    networks:
      - chaos-net

  chaos-proxy:
    image: shopify/toxiproxy
    # Inject latency, failures
```

---

## 📚 Part 7: Migration & Rollout Plan

### Database Migration

**Migration script**: `db/migrations/v4_to_v5_robustness.sql`

```sql
-- Add errors table
CREATE TABLE errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    operation TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    file_path TEXT,
    repository TEXT,
    metadata JSONB,
    traceback TEXT
) PARTITION BY RANGE (timestamp);

-- Create initial partition (current month)
CREATE TABLE errors_2025_10 PARTITION OF errors
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

-- Indexes
CREATE INDEX idx_errors_timestamp ON errors(timestamp DESC);
CREATE INDEX idx_errors_operation ON errors(operation);
CREATE INDEX idx_errors_type ON errors(error_type);
CREATE INDEX idx_errors_metadata_gin ON errors USING gin(metadata);

-- Add circuit breaker state table (optional)
CREATE TABLE circuit_breaker_state (
    service_name TEXT PRIMARY KEY,
    state TEXT CHECK (state IN ('closed', 'open', 'half_open')),
    failure_count INT DEFAULT 0,
    last_failure_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Feature Flags

**Gradual rollout**:
```python
# api/config/features.py
FEATURE_FLAGS = {
    "ENABLE_TIMEOUTS": os.getenv("ENABLE_TIMEOUTS", "false") == "true",
    "ENABLE_CIRCUIT_BREAKERS": os.getenv("ENABLE_CIRCUIT_BREAKERS", "false") == "true",
    "ENABLE_ERROR_TRACKING": os.getenv("ENABLE_ERROR_TRACKING", "true") == "true",  # Safe
}

# Usage:
if FEATURE_FLAGS["ENABLE_TIMEOUTS"]:
    result = await with_timeout(operation(), timeout=5.0)
else:
    result = await operation()
```

**Rollout stages**:
1. **Week 1**: Error tracking only (observability, no behavior change)
2. **Week 2**: Timeouts + retry (start conservative, 10x normal values)
3. **Week 3**: Circuit breakers (monitor false positive rate)
4. **Week 4**: Transactions (high-risk, careful monitoring)

### Rollback Plan

**If critical issue found**:
1. Set `ENABLE_*` env vars to `false`
2. Restart services
3. Database changes are additive only (no data loss)
4. Analyze error logs, fix issue
5. Re-enable features

---

## ✅ Part 8: Success Criteria

### Quantitative Metrics

| Metric | Baseline (v2.0) | Target (v3.0) | Measurement |
|--------|-----------------|---------------|-------------|
| Infinite hangs | Possible | 0 | Monitor timeout errors |
| Partial indexing | 5% | 0% | Check transaction rollbacks |
| Redis failure uptime | 0% | 80%+ | Health endpoint |
| Error visibility | 20% | 100% | Errors table coverage |
| Timeout error rate | N/A | <1% | Error stats endpoint |
| Circuit breaker false positives | N/A | <5% | Manual review |

### Qualitative Checks

- [ ] No infinite hangs in 10,000-file stress test
- [ ] Chaos testing passes (Redis down, concurrent indexing)
- [ ] Error stats endpoint shows meaningful patterns
- [ ] Health endpoint accurately reflects degradation
- [ ] Documentation complete (all decorators, all utilities)

---

## 🚀 Part 9: Recommendations

### Must-Have (Blocking for v3.0)

1. **Story 12.1 (Timeouts)** - CRITICAL: Prevents DoS
2. **Story 12.2 (Transactions)** - CRITICAL: Prevents data corruption

### Should-Have (High Value, Low Risk)

3. **Story 12.5 (Retry)** - Easy win, high resilience improvement
4. **Story 12.4 (Error Tracking)** - Observability critical for production

### Could-Have (Defer if Timeline Tight)

5. **Story 12.3 (Circuit Breakers)** - Complex, LSP not yet implemented
   - **Recommendation**: Implement **only for Redis** in v3.0
   - **Defer**: LSP circuit breaker to EPIC-13

### Additional Recommendations

1. **Add correlation IDs** - Track requests across logs
2. **Add distributed tracing** - Consider OpenTelemetry (future)
3. **Add rate limiting** - Prevent abuse (future)
4. **Add request timeouts** - FastAPI middleware (easy add)

---

## 🎓 Part 10: Lessons from EPIC-11 Audit

### What Went Well in EPIC-11
- ✅ Comprehensive testing (31/31 tests)
- ✅ Systematic bug fixing (5 bugs documented)
- ✅ Good documentation (4 completion reports + audit)

### Apply to EPIC-12
1. **Test FIRST**: Write chaos tests before implementation
2. **Audit BEFORE launch**: Comprehensive review before marking COMPLETE
3. **Document edge cases**: Capture all edge cases in completion reports

---

## 📋 Part 11: Action Items

### Before Implementation Starts

- [ ] Install `structlog` dependency
- [ ] Create `tests/chaos/` directory
- [ ] Set up toxiproxy for chaos testing
- [ ] Review transaction boundaries in existing code
- [ ] Identify all CPU-bound operations (tree-sitter, embeddings)

### During Implementation

- [ ] Create timeout decorator with `asyncio.to_thread()` support
- [ ] Test timeout on actual tree-sitter parsing (verify no deadlocks)
- [ ] Implement transaction context manager
- [ ] Add `ON CONFLICT DO UPDATE` to chunk insertion
- [ ] Test cache invalidation on rollback
- [ ] Implement circuit breaker state machine
- [ ] Add health endpoint degradation status
- [ ] Create errors table with partitioning
- [ ] Implement async error logging (fire-and-forget)
- [ ] Add correlation IDs to all log statements

### After Implementation

- [ ] Run chaos tests (10,000-file stress test)
- [ ] Monitor timeout error rate (<1% target)
- [ ] Monitor circuit breaker false positives (<5% target)
- [ ] Review error stats for patterns
- [ ] Write EPIC-12 completion report
- [ ] Update CLAUDE.md

---

## 🎯 Conclusion

**EPIC-12 is READY FOR IMPLEMENTATION** with the following caveats:

1. ✅ **All dependencies satisfied** (EPIC-10, EPIC-11 complete)
2. ⚠️ **CPU-bound operations need special handling** (`asyncio.to_thread()`)
3. ⚠️ **Transaction boundaries need careful design** (embeddings outside transactions)
4. ⚠️ **Circuit breaker scope should be limited** (Redis only in v3.0, defer LSP)
5. ✅ **Risk level is ACCEPTABLE** with proper testing and gradual rollout

**Estimated Timeline**: 4 weeks (18 pts / 4-5 pts per week)

**Recommended Priority Order**:
1. Story 12.1 (Timeouts) - Week 1
2. Story 12.5 (Retry) - Week 1
3. Story 12.2 (Transactions) - Week 2
4. Story 12.3 (Circuit Breakers, Redis only) - Week 3
5. Story 12.4 (Error Tracking) - Week 4

**GO / NO-GO**: ✅ **GO FOR IMPLEMENTATION**

---

**Prepared by**: Claude (Architecture Team)
**Review Status**: Awaiting Team Review
**Next Step**: Create Story 12.1 Implementation Plan
