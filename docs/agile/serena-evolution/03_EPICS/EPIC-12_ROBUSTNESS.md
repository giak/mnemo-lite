# EPIC-12: Robustness & Error Handling

**Status**: 🚧 IN PROGRESS (Stories 12.1, 12.2, 12.3 COMPLETE ✅)
**Priority**: P1 (High - Production Stability)
**Epic Points**: 23 pts (13/23 completed - 57%)
**Timeline**: Week 4 (Phase 2)
**Depends On**: EPIC-10 (Cache layer), EPIC-11 (Symbol paths)
**Related**: Serena Analysis (Timeout patterns, graceful degradation)
**Progress**:
- Story 12.1 (5 pts) ✅ COMPLETE - 2025-10-21 - Timeout-Based Execution
- Story 12.2 (3 pts) ✅ COMPLETE - 2025-10-21 - Transaction Boundaries
- Story 12.3 (5 pts) ✅ COMPLETE - 2025-10-21 - Circuit Breakers

---

## 🎯 Epic Goal

Implement production-grade robustness patterns to prevent:
- **Infinite hangs**: Timeout-based execution for all long-running operations
- **Resource leaks**: Graceful cleanup on errors
- **Cascading failures**: Circuit breakers for external dependencies
- **Silent errors**: Comprehensive error tracking and alerting
- **Data corruption**: Transactional integrity and rollback

This epic transforms MnemoLite from a development prototype to a production-ready system.

---

## 📊 Current State (v2.0.0)

**Pain Points**:
```python
# Problem 1: Infinite hangs
await tree_sitter_service.chunk_code(source_code)
# If source code has pathological structure → 5+ seconds hang
# No timeout → API thread blocked forever

# Problem 2: No cleanup on error
chunks = await chunking_service.chunk_code(source)
embeddings = await embedding_service.generate(chunks)  # FAILS HERE
# → chunks stored in cache, embeddings missing
# → Inconsistent state

# Problem 3: External dependency failures
lsp_result = await lsp_service.query(file_path)  # LSP crashed
# → Entire indexing pipeline fails
# → Should degrade gracefully

# Problem 4: Silent errors
try:
    await index_file(path)
except Exception:
    pass  # ❌ Silent failure, no logging
```

**Observed Issues** (from v2.0 usage):
- Tree-sitter parsing: 0.1% of files hang >5 seconds
- Embedding generation: Occasional OOM crashes
- LSP queries: 2-5% failure rate (process restart needed)
- Redis connection: Intermittent network errors

---

## 🚀 Target State (v3.0.0)

**Timeout Guarantees**:
```python
# All operations have max execution time
await with_timeout(tree_sitter_service.chunk_code(source), timeout=5.0)
# After 5s → TimeoutError raised → log error, skip file
```

**Transactional Integrity**:
```python
# Atomic operations
async with transaction():
    chunks = await store_chunks(...)
    embeddings = await store_embeddings(...)
    graph = await build_graph(...)
    # All succeed or all rollback
```

**Graceful Degradation**:
```python
# LSP failure → continue without type info
try:
    lsp_data = await lsp_service.query(file_path)
except LSPError:
    logger.warning("LSP unavailable, continuing with tree-sitter only")
    lsp_data = {}  # Empty metadata
# → Indexing still succeeds with reduced quality
```

**Comprehensive Error Tracking**:
```python
# Structured logging + error aggregation
logger.error("Indexing failed",
    file=file_path,
    error=str(e),
    error_type=type(e).__name__,
    repository=repository,
    traceback=traceback.format_exc()
)

# Errors stored in errors table for analysis
await error_repository.create(
    operation="index_file",
    file_path=file_path,
    error_message=str(e),
    error_type=type(e).__name__,
    metadata={"repository": repository}
)
```

---

## 📝 Stories Breakdown

### **Story 12.1: Timeout-Based Execution** (5 pts) ✅ COMPLETE

**Status**: ✅ COMPLETE - 2025-10-21
**User Story**: As a system, I want all long-running operations to have timeouts so that one slow file doesn't block the entire pipeline.

**Acceptance Criteria**:
- [x] Timeout decorator for async operations ✅ (`utils/timeout.py`)
- [x] All parsing/embedding/graph calls wrapped with timeout ✅ (5 services)
- [x] Configurable timeouts per operation type ✅ (13 operations in `config/timeouts.py`)
- [x] TimeoutError logged with full context ✅ (structured logging with context)
- [x] Tests: Timeout enforcement, error handling ✅ (26 unit + 12 integration tests)

**Deliverables**:
- ✅ `utils/timeout.py` (177 lines) - Core utilities
- ✅ `config/timeouts.py` (122 lines) - Centralized configuration
- ✅ 5 services protected: chunking, embedding, graph_construction, graph_traversal, indexing
- ✅ 26 unit tests passing (100%)
- ✅ 12 integration tests created
- ✅ Completion report: `EPIC-12_STORY_12.1_COMPLETION_REPORT.md`

**Performance**: <1ms overhead per operation, graceful fallback for chunking service

**Implementation Details** (Serena-inspired):

```python
# NEW: api/utils/timeout.py

import asyncio
import functools
import structlog
from typing import TypeVar, Callable, Any

logger = structlog.get_logger()

T = TypeVar('T')

class TimeoutError(Exception):
    """Operation exceeded timeout."""
    pass

async def with_timeout(
    coro,
    timeout: float,
    operation_name: str = "operation",
    context: dict = None
) -> Any:
    """
    Execute coroutine with timeout.

    Inspired by Serena's thread.py timeout pattern.

    Example:
        result = await with_timeout(
            tree_sitter_service.chunk_code(source),
            timeout=5.0,
            operation_name="tree_sitter_parse",
            context={"file": file_path}
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(
            "Operation timed out",
            operation=operation_name,
            timeout=timeout,
            **(context or {})
        )
        raise TimeoutError(f"{operation_name} exceeded {timeout}s timeout")

def timeout_decorator(timeout: float, operation_name: str = None):
    """
    Decorator for timeout enforcement.

    Example:
        @timeout_decorator(timeout=5.0, operation_name="chunk_code")
        async def chunk_code(self, source_code):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            return await with_timeout(
                func(*args, **kwargs),
                timeout=timeout,
                operation_name=op_name,
                context={"function": func.__qualname__}
            )
        return wrapper
    return decorator
```

```python
# MODIFY: api/services/code_chunking_service.py

from api.utils.timeout import timeout_decorator, TimeoutError

class CodeChunkingService:

    @timeout_decorator(timeout=5.0, operation_name="tree_sitter_parse")
    async def chunk_code(
        self,
        source_code: str,
        language: str
    ) -> List[CodeChunk]:
        """Parse source code with tree-sitter (5s timeout)."""

        # Existing implementation
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root = tree.root_node

        chunks = self._extract_chunks(root, source_code)
        return chunks
```

```python
# MODIFY: api/services/dual_embedding_service.py

class DualEmbeddingService:

    @timeout_decorator(timeout=10.0, operation_name="embedding_generation")
    async def generate_dual_embeddings(
        self,
        chunks: List[CodeChunk]
    ) -> Dict[str, np.ndarray]:
        """Generate embeddings with 10s timeout (for batch)."""

        # Existing implementation
        text_embeddings = await self._encode_texts([c.text for c in chunks])
        code_embeddings = await self._encode_texts([c.source_code for c in chunks])

        return {
            "text": text_embeddings,
            "code": code_embeddings
        }
```

```python
# NEW: api/config/timeouts.py

"""Centralized timeout configuration."""

TIMEOUTS = {
    "tree_sitter_parse": 5.0,  # seconds
    "embedding_generation": 10.0,
    "lsp_query": 3.0,
    "graph_traversal": 2.0,
    "vector_search": 5.0,
    "cache_operation": 1.0,
    "database_query": 10.0
}

def get_timeout(operation: str) -> float:
    """Get timeout for operation (with default fallback)."""
    return TIMEOUTS.get(operation, 30.0)  # Default 30s
```

**Files to Create/Modify**:
```
NEW: api/utils/timeout.py (100 lines)
NEW: api/config/timeouts.py (30 lines)
MODIFY: api/services/code_chunking_service.py (+2 lines decorator)
MODIFY: api/services/dual_embedding_service.py (+2 lines decorator)
MODIFY: api/services/graph_traversal_service.py (+2 lines decorator)
TEST: tests/utils/test_timeout.py (200 lines)
TEST: tests/integration/test_timeout_enforcement.py (150 lines)
```

**Testing Strategy**:
```python
# tests/utils/test_timeout.py

@pytest.mark.anyio
async def test_timeout_enforced():
    """Operation exceeding timeout raises TimeoutError."""

    async def slow_operation():
        await asyncio.sleep(10)  # 10 seconds
        return "done"

    with pytest.raises(TimeoutError):
        await with_timeout(slow_operation(), timeout=1.0)

@pytest.mark.anyio
async def test_timeout_not_reached():
    """Fast operation succeeds."""

    async def fast_operation():
        await asyncio.sleep(0.1)
        return "done"

    result = await with_timeout(fast_operation(), timeout=5.0)
    assert result == "done"

@pytest.mark.anyio
async def test_timeout_decorator():
    """Decorator enforces timeout."""

    @timeout_decorator(timeout=1.0)
    async def slow_func():
        await asyncio.sleep(10)
        return "done"

    with pytest.raises(TimeoutError):
        await slow_func()
```

**Success Metrics**:
- Zero infinite hangs in production
- <1% timeout errors (indicates reasonable limits)
- Timeouts logged with full context

---

### **Story 12.2: Transaction Boundaries** (3 pts) ✅ COMPLETE

**Status**: ✅ COMPLETE (2025-10-21)

**User Story**: As a system, I want all database operations wrapped in transactions so that partial failures don't leave corrupted data.

**Acceptance Criteria**:
- [x] Database transactions for multi-step operations
- [x] Rollback on any step failure
- [x] Cache invalidation coordinated with transactions
- [x] Tests: Rollback correctness, batch operations, graph construction
- [x] Backward compatible optional connection parameter

**Completed Deliverables**:
- ✅ 3 repositories modified (CodeChunk, Node, Edge) with transaction support
- ✅ 2 services wrapped in transactions (CodeIndexing, GraphConstruction)
- ✅ 1 route migrated to repository pattern (delete_repository)
- ✅ 3 dependency injection functions for repositories
- ✅ 4 integration tests passing (100%)
- ✅ 4 bulk delete methods for atomic operations

**Documentation**:
- [Analysis](EPIC-12_STORY_12.2_ANALYSIS.md)
- [Implementation Plan](EPIC-12_STORY_12.2_IMPLEMENTATION_PLAN.md)
- Completion Report (pending)

**Implementation Details**:

```python
# NEW: api/utils/transaction.py

from contextlib import asynccontextmanager
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def atomic_transaction(db_engine, cascade_cache=None):
    """
    Atomic transaction with cache invalidation on rollback.

    Example:
        async with atomic_transaction(db, cache) as tx:
            await chunk_repo.create(chunks, tx)
            await node_repo.create(nodes, tx)
            # Both succeed or both rollback
    """

    async with db_engine.begin() as connection:
        tx_context = {"connection": connection, "rollback_cache_keys": []}

        try:
            yield tx_context
            # Commit on success
            await connection.commit()
            logger.info("Transaction committed")

        except Exception as e:
            # Rollback database
            await connection.rollback()
            logger.warning("Transaction rolled back", error=str(e))

            # Invalidate caches that might have been populated
            if cascade_cache and tx_context["rollback_cache_keys"]:
                for key in tx_context["rollback_cache_keys"]:
                    await cascade_cache.invalidate(key)
                logger.info("Invalidated cache after rollback",
                           count=len(tx_context["rollback_cache_keys"]))

            raise
```

```python
# MODIFY: api/services/code_indexing_service.py

class CodeIndexingService:

    async def index_file(
        self,
        file_path: str,
        source_code: str,
        language: str,
        repository: str,
        commit_hash: Optional[str] = None
    ) -> List[CodeChunkModel]:
        """Atomic file indexing."""

        # Check cache BEFORE transaction
        cached_chunks = await self.cache.get_chunks(file_path, source_code)
        if cached_chunks:
            return cached_chunks

        # ATOMIC TRANSACTION
        async with atomic_transaction(self.db_engine, self.cache) as tx:
            # 1. Parse
            chunks = await with_timeout(
                self.chunking_service.chunk_code(source_code, language),
                timeout=5.0
            )

            # 2. Extract metadata
            for chunk in chunks:
                metadata = await self.metadata_extractor.extract(chunk, language)
                chunk.metadata = metadata

            # 3. Generate embeddings
            embeddings = await with_timeout(
                self.dual_embedding_service.generate_dual_embeddings(chunks),
                timeout=10.0
            )

            # 4. Store chunks (in transaction)
            chunk_models = await self.chunk_repository.create_many(
                chunks, embeddings, repository, commit_hash, tx=tx["connection"]
            )

            # 5. Build graph (in transaction)
            await self.graph_service.build_graph_for_repository(
                repository, chunks=chunk_models, tx=tx["connection"]
            )

            # Mark cache keys for invalidation if rollback
            tx["rollback_cache_keys"].append(file_path)

        # POPULATE CACHE AFTER successful commit
        await self.cache.put_chunks(file_path, source_code, chunk_models)

        return chunk_models
```

**Files to Create/Modify**:
```
NEW: api/utils/transaction.py (80 lines)
MODIFY: api/services/code_indexing_service.py (+15 lines transaction)
MODIFY: api/db/repositories/base_repository.py (add tx parameter support)
TEST: tests/utils/test_transaction.py (150 lines)
TEST: tests/integration/test_transactional_indexing.py (200 lines)
```

**Testing Strategy**:
```python
# tests/integration/test_transactional_indexing.py

@pytest.mark.anyio
async def test_rollback_on_embedding_failure():
    """If embedding fails, chunks NOT stored."""

    # Mock embedding to fail
    with patch.object(embedding_service, 'generate_dual_embeddings',
                     side_effect=Exception("OOM")):
        with pytest.raises(Exception):
            await indexing_service.index_file(
                "test.py", "def foo(): pass", "python", "test-repo"
            )

    # Verify chunks NOT in database
    chunks = await chunk_repository.find_by_file_path("test.py")
    assert len(chunks) == 0

@pytest.mark.anyio
async def test_cache_invalidated_on_rollback():
    """Cache invalidated if transaction rolls back."""

    # Populate cache
    await cache.put_chunks("test.py", "def foo(): pass", cached_chunks)

    # Index with failure (embedding error)
    with patch.object(embedding_service, 'generate_dual_embeddings',
                     side_effect=Exception("OOM")):
        with pytest.raises(Exception):
            await indexing_service.index_file(
                "test.py", "def bar(): pass",  # Different content
                "python", "test-repo"
            )

    # Cache should be invalidated
    result = await cache.get_chunks("test.py", "def bar(): pass")
    assert result is None
```

**Success Metrics**:
- Zero partial indexing states in production
- 100% rollback correctness
- Cache consistency maintained

---

### **Story 12.3: Circuit Breakers** (5 pts) ✅ COMPLETE

**Status**: ✅ COMPLETE - 2025-10-21
**User Story**: As a system, I want circuit breakers to prevent cascading failures from external dependencies so that the system degrades gracefully and recovers automatically.

**Acceptance Criteria**:
- [x] Circuit breaker foundation with 3-state machine (CLOSED/OPEN/HALF_OPEN) ✅
- [x] Redis circuit breaker (threshold=5, recovery=30s) ✅
- [x] Embedding service circuit breaker (threshold=3, recovery=60s) ✅
- [x] Health endpoint exposes circuit state ✅
- [x] Fast fail when circuit OPEN (<1ms vs 5000ms timeout) ✅
- [x] Automatic recovery attempts after timeout ✅
- [x] Tests: 17 unit + 9 integration tests passing ✅

**Deliverables**:
- ✅ `utils/circuit_breaker.py` (400 lines) - Core circuit breaker with state machine
- ✅ `config/circuit_breakers.py` (50 lines) - Configuration for each service
- ✅ `utils/circuit_breaker_registry.py` (40 lines) - Registry for health monitoring
- ✅ Redis cache protection with graceful degradation to L1+L3
- ✅ Embedding service protection with automatic recovery from OOM
- ✅ Health endpoint integration showing circuit state
- ✅ 26 tests passing (17 unit + 9 integration)
- ✅ Completion report: `EPIC-12_STORY_12.3_COMPLETION_REPORT.md`

**Performance Impact**:
- Redis outage: 5000x faster response (5000ms → <1ms fast fail)
- Log noise reduction: 99.9% during outages
- Embedding failures: Automatic recovery (no manual restart)

**Key Features**:
- 3-state machine: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing) → CLOSED/OPEN
- Configurable thresholds per service
- Health endpoint shows circuit state for observability
- Critical circuits (embedding_service) affect health status (503)

See detailed completion report: [`EPIC-12_STORY_12.3_COMPLETION_REPORT.md`](EPIC-12_STORY_12.3_COMPLETION_REPORT.md)

**Implementation completed - see completion report for full details including:**
- Circuit breaker state machine implementation
- Redis and Embedding service integration
- Health endpoint integration
- Complete test suite (26 tests)
- Performance benchmarks


### **Story 12.4: Error Tracking & Aggregation** (3 pts)

**User Story**: As a DevOps engineer, I want all errors logged and aggregated so that I can identify patterns and fix root causes.

**Acceptance Criteria**:
- [ ] Structured error logging
- [ ] Errors table in database
- [ ] Error aggregation endpoint: `GET /v1/errors/stats`
- [ ] Top errors by count/frequency
- [ ] Tests: Error logging, aggregation

**Implementation Details**:

```sql
-- MODIFY: db/init/01-init.sql

CREATE TABLE errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    operation TEXT NOT NULL,  -- e.g., "index_file", "search"
    error_type TEXT NOT NULL,  -- e.g., "TimeoutError", "LSPError"
    error_message TEXT,
    file_path TEXT,
    repository TEXT,
    metadata JSONB,
    traceback TEXT
);

CREATE INDEX idx_errors_timestamp ON errors(timestamp DESC);
CREATE INDEX idx_errors_operation ON errors(operation);
CREATE INDEX idx_errors_type ON errors(error_type);
```

```python
# NEW: api/db/repositories/error_repository.py

class ErrorRepository:
    """Repository for error tracking."""

    async def create(
        self,
        operation: str,
        error_type: str,
        error_message: str,
        file_path: Optional[str] = None,
        repository: Optional[str] = None,
        metadata: Optional[dict] = None,
        traceback: Optional[str] = None
    ):
        """Log error to database."""

        sql = """
        INSERT INTO errors
            (operation, error_type, error_message, file_path, repository, metadata, traceback)
        VALUES
            (:operation, :error_type, :error_message, :file_path, :repository, :metadata, :traceback)
        """

        await self.db.execute(sql, {
            "operation": operation,
            "error_type": error_type,
            "error_message": error_message,
            "file_path": file_path,
            "repository": repository,
            "metadata": json.dumps(metadata) if metadata else None,
            "traceback": traceback
        })

    async def get_stats(
        self,
        since: datetime,
        group_by: str = "error_type"
    ) -> List[dict]:
        """Get error statistics."""

        sql = f"""
        SELECT
            {group_by},
            COUNT(*) as count,
            MIN(timestamp) as first_seen,
            MAX(timestamp) as last_seen,
            ARRAY_AGG(DISTINCT operation) as operations
        FROM errors
        WHERE timestamp >= :since
        GROUP BY {group_by}
        ORDER BY count DESC
        LIMIT 20
        """

        results = await self.db.fetch_all(sql, {"since": since})
        return [dict(r) for r in results]
```

```python
# MODIFY: api/services/code_indexing_service.py

class CodeIndexingService:

    def __init__(self, ..., error_repository: ErrorRepository):
        # ... existing
        self.error_repo = error_repository

    async def index_file(self, ...):
        try:
            # ... existing implementation

        except TimeoutError as e:
            # Log timeout error
            await self.error_repo.create(
                operation="index_file",
                error_type="TimeoutError",
                error_message=str(e),
                file_path=file_path,
                repository=repository,
                metadata={"language": language},
                traceback=traceback.format_exc()
            )
            logger.error("File indexing timed out", file=file_path, error=str(e))
            raise

        except Exception as e:
            # Log generic error
            await self.error_repo.create(
                operation="index_file",
                error_type=type(e).__name__,
                error_message=str(e),
                file_path=file_path,
                repository=repository,
                traceback=traceback.format_exc()
            )
            logger.error("File indexing failed", file=file_path, error=str(e))
            raise
```

```python
# NEW: api/routes/error_routes.py

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/v1/errors", tags=["Errors"])

@router.get("/stats")
async def get_error_stats(
    since_hours: int = Query(24, description="Lookback window in hours"),
    group_by: str = Query("error_type", description="Group by: error_type, operation, repository"),
    error_repo: ErrorRepository = Depends(get_error_repository)
):
    """Get error statistics."""

    since = datetime.now() - timedelta(hours=since_hours)
    stats = await error_repo.get_stats(since, group_by)

    return {
        "since": since.isoformat(),
        "count": len(stats),
        "errors": stats
    }
```

**Files to Create/Modify**:
```
MODIFY: db/init/01-init.sql (+15 lines errors table)
NEW: api/db/repositories/error_repository.py (100 lines)
NEW: api/routes/error_routes.py (50 lines)
MODIFY: api/services/code_indexing_service.py (+25 lines error logging)
TEST: tests/db/repositories/test_error_repository.py (100 lines)
```

**Success Metrics**:
- 100% errors logged
- Error stats endpoint functional
- Pattern identification possible (top 10 errors visible)

---

### **Story 12.5: Retry Logic with Exponential Backoff** (2 pts)

**User Story**: As a system, I want transient failures to be retried so that temporary network issues don't cause permanent failures.

**Acceptance Criteria**:
- [ ] Retry decorator with exponential backoff
- [ ] Configurable max retries
- [ ] Only retry idempotent operations
- [ ] Tests: Retry behavior, max attempts

**Implementation Details**:

```python
# NEW: api/utils/retry.py

import asyncio
import functools
import structlog

logger = structlog.get_logger()

async def retry_with_backoff(
    func,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Retry with exponential backoff.

    Delays: 1s, 2s, 4s, 8s, ...
    """

    for attempt in range(1, max_attempts + 1):
        try:
            return await func()

        except retryable_exceptions as e:
            if attempt == max_attempts:
                logger.error("Max retry attempts reached", attempts=attempt, error=str(e))
                raise

            # Calculate delay
            delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)

            logger.warning(
                "Retrying after failure",
                attempt=attempt,
                max_attempts=max_attempts,
                delay=delay,
                error=str(e)
            )

            await asyncio.sleep(delay)

def retry_decorator(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple = (Exception,)
):
    """Decorator for retry with backoff."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_attempts=max_attempts,
                base_delay=base_delay,
                retryable_exceptions=retryable_exceptions
            )
        return wrapper
    return decorator
```

```python
# MODIFY: api/services/caches/redis_cache.py

from api.utils.retry import retry_decorator

class RedisCache:

    @retry_decorator(max_attempts=3, base_delay=0.5, retryable_exceptions=(redis.ConnectionError,))
    async def get(self, key: str) -> Optional[Any]:
        """Get with retry on connection errors."""

        if not self.client:
            return None

        value = await self.client.get(key)
        if value:
            self.hits += 1
            return json.loads(value)
        else:
            self.misses += 1
            return None
```

**Files to Create/Modify**:
```
NEW: api/utils/retry.py (100 lines)
MODIFY: api/services/caches/redis_cache.py (+1 line decorator)
TEST: tests/utils/test_retry.py (150 lines)
```

**Success Metrics**:
- <5% failures due to transient network issues
- Retry logs visible for debugging

---

## 📈 Epic Success Metrics

### Robustness Targets

| Metric | v2.0 (Current) | v3.0 (Target) | Improvement |
|--------|----------------|---------------|-------------|
| Infinite hangs | Possible | Zero (timeouts) | Eliminated |
| Partial indexing states | Possible | Zero (transactions) | Eliminated |
| Redis failure impact | Service down | Degraded (functional) | 100% → 80% uptime |
| LSP failure impact | Indexing fails | Degraded quality | 0% → 95% success |
| Error visibility | Poor (logs only) | Excellent (DB + stats) | Qualitative |

### Quality Metrics

- **Zero infinite hangs**: 100% timeout enforcement
- **Zero data corruption**: 100% transactional integrity
- **High availability**: >99% uptime with degradation
- **Error tracking**: 100% errors logged

---

## 🎯 Validation Plan

### Chaos Testing

```python
# tests/chaos/test_failure_scenarios.py

@pytest.mark.anyio
async def test_redis_failure_during_indexing():
    """Redis fails mid-indexing → degrades gracefully."""

    # Start indexing
    task = asyncio.create_task(index_large_repo(1000))

    # Kill Redis after 50 files
    await asyncio.sleep(5)
    await redis_client.shutdown()

    # Wait for completion
    result = await task

    # Should complete with degraded performance
    assert result.status == "completed"
    assert result.indexed_files == 1000
    # No cache hits, but all files indexed

@pytest.mark.anyio
async def test_lsp_crash_during_indexing():
    """LSP crashes → continues without type info."""

    # Kill LSP process
    lsp_service.process.kill()

    # Index files
    result = await index_files(["test1.py", "test2.py"])

    # Should succeed (degraded quality)
    assert result.status == "completed"
    assert result.indexed_files == 2

    # Chunks stored but without LSP metadata
    chunks = await chunk_repository.find_by_file_path("test1.py")
    assert chunks[0].metadata.get("return_type") is None  # Missing LSP data
```

---

## 🚧 Risks & Mitigations

### Risk 1: Timeouts Too Aggressive

**Impact**: Valid slow files rejected

**Mitigation**:
- Monitor timeout rates (should be <1%)
- Configurable timeouts per repository
- Manual override for known slow files

### Risk 2: Circuit Breaker False Positives

**Impact**: Service marked down when actually healthy

**Mitigation**:
- Conservative thresholds (5+ failures before open)
- Short timeout windows (60s auto-retry)
- Manual circuit reset endpoint

---

## 📚 References

- **Serena Analysis**: Timeout pattern (thread.py), lock management (ls_handler.py)
- **Circuit Breaker Pattern**: Martin Fowler - https://martinfowler.com/bliki/CircuitBreaker.html

---

## ✅ Definition of Done

**Epic is complete when**:
- [ ] All 5 stories completed and tested
- [ ] Zero infinite hangs in 10,000-file stress test
- [ ] Chaos testing passes (Redis down, LSP crash)
- [ ] Error tracking functional (stats endpoint)
- [ ] Circuit breakers functional (auto-recovery)
- [ ] Documentation updated

**Ready for EPIC-13 (LSP Integration)**: ✅

---

**Created**: 2025-10-19
**Author**: Architecture Team
**Reviewed**: Pending
**Approved**: Pending
