# EPIC-12 Story 12.3: Circuit Breakers - Technical Analysis

**Story**: Circuit Breakers (5 pts)
**Priority**: P1 (Required for cascade failure prevention)
**Status**: 📋 ANALYSIS COMPLETE
**Date**: 2025-10-21
**Author**: Claude Code + Giak

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [External Dependencies Identified](#3-external-dependencies-identified)
4. [Current Error Handling Patterns](#4-current-error-handling-patterns)
5. [Circuit Breaker Design](#5-circuit-breaker-design)
6. [Implementation Priorities](#6-implementation-priorities)
7. [Risk Assessment](#7-risk-assessment)
8. [Success Metrics](#8-success-metrics)
9. [Appendix](#9-appendix)

---

## 1. Executive Summary

### 1.1 Problem Statement

MnemoLite currently lacks circuit breaker protection for external dependencies (Redis, Embedding Service, PostgreSQL). When these services fail or degrade, the system continues to attempt connections/operations, leading to:

- **Thundering Herd**: All requests hammer failing service
- **Resource Exhaustion**: Connection pools depleted, threads blocked
- **Cascading Failures**: Slow/failing dependencies bring down entire system
- **Log Noise**: Thousands of error logs from repeated failures
- **Poor User Experience**: Slow responses instead of fast failures

### 1.2 Solution Overview

Implement circuit breaker pattern with 3 states (CLOSED/OPEN/HALF_OPEN) for external dependencies:

1. **Redis Cache**: Prevent thundering herd when cache unavailable
2. **Embedding Service**: Prevent repeated OOM/timeout failures
3. **PostgreSQL**: Health check caching for monitoring/alerting

### 1.3 Key Benefits

- **Fast Fail**: Immediate failure instead of waiting for timeout
- **Resource Protection**: Stop overwhelming failing services
- **Automatic Recovery**: Try again after recovery timeout
- **Better Observability**: Circuit state as first-class metric
- **Improved UX**: Predictable response times even during failures

### 1.4 Story Points Breakdown

- **Phase 1**: Circuit Breaker Foundation (2 pts) - Base class + tests
- **Phase 2**: Redis Circuit Breaker (2 pts) - Integration + tests
- **Phase 3**: Embedding Circuit Breaker (1 pt) - Integration + tests
- **Total**: 5 pts

---

## 2. Current State Analysis

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MnemoLite API Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Routes     │  │   Services   │  │ Repositories │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Redis Cache    │  │ Embedding Svc   │  │   PostgreSQL    │
│  (L2 Cache)     │  │ (AI Models)     │  │  (L3 Storage)   │
│                 │  │                 │  │                 │
│ ❌ No Circuit   │  │ ❌ No Circuit   │  │ ⚠️  Health OK   │
│    Breaker      │  │    Breaker      │  │ ❌ No Caching   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Current Protection**:
- ✅ **Timeouts**: EPIC-12 Story 12.1 added timeout protection
- ✅ **Transactions**: EPIC-12 Story 12.2 added atomic operations
- ✅ **Retry Logic**: Exponential backoff in CodeIndexingService
- ❌ **Circuit Breakers**: None implemented

**Gaps**:
- No protection against thundering herd
- No fast-fail for known-failing services
- No automatic recovery detection
- No circuit state monitoring

### 2.2 Current Error Handling Assessment

| Component | Timeout | Retry | Fallback | Circuit Breaker | Grade |
|-----------|---------|-------|----------|----------------|-------|
| Redis Cache | ✅ Implicit | ❌ No | ✅ L1→L3 | ❌ No | B+ |
| Embedding Svc | ✅ 10-30s | ✅ 3x exp | ⚠️ Partial | ❌ No | B |
| PostgreSQL | ✅ 60s | ❌ No | ❌ No | ❌ No | C+ |
| Tree-sitter | ✅ 5s | ❌ No | ✅ Fixed | ❌ No | B+ |

**Overall Grade**: **B-** (Good timeout/transaction protection, missing circuit breakers)

### 2.3 Existing Robustness Features

**From EPIC-12 Story 12.1 (Timeouts)**:
```python
# All long-running operations have strict time limits
result = await with_timeout(
    operation(),
    timeout=get_timeout("operation_name"),
    operation_name="operation_name",
    raise_on_timeout=True
)
```

**From EPIC-12 Story 12.2 (Transactions)**:
```python
# All multi-step operations are atomic
async with self.engine.begin() as conn:
    await chunk_repo.add_batch(chunks, connection=conn)
    await node_repo.create_nodes(nodes, connection=conn)
    # All or nothing - auto-rollback on exception
```

**From CodeIndexingService (Retry Logic)**:
```python
# Exponential backoff retry for transient failures
for attempt in range(max_retries):
    try:
        embeddings = await self._generate_embeddings_for_chunk(chunk)
        return embeddings
    except Exception as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
```

**Missing Piece**: Circuit breakers to prevent repeated attempts to known-failing services

---

## 3. External Dependencies Identified

### 3.1 Dependency #1: Redis Cache (L2)

#### Overview

**Purpose**: L2 distributed cache layer (2GB Redis)
**Location**: `api/services/caches/redis_cache.py`
**Criticality**: **MEDIUM** (Non-critical, graceful degradation exists)
**Call Frequency**: **HIGH** (Every cache operation ~100-1000 req/s)
**Network**: Yes (TCP connection to localhost:6379)

#### Current Implementation

```python
# Connection initialization (main.py:129-149)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_cache = RedisCache(redis_url=redis_url)
    await redis_cache.connect()
    app.state.redis_cache = redis_cache
    logger.info("✅ Redis L2 cache connected successfully")
except Exception as e:
    logger.warning(
        "Redis L2 cache connection failed - continuing with graceful degradation",
        error=str(e)
    )
    app.state.redis_cache = None  # ✅ Graceful degradation

# Operation phase (redis_cache.py:90-103)
async def get(self, key: str) -> Optional[Any]:
    if not self.client:
        return None  # ✅ Graceful degradation

    try:
        value = await self.client.get(key)
        if value:
            self.hits += 1
            return json.loads(value)
        else:
            self.misses += 1
            return None
    except Exception as e:
        self.errors += 1
        logger.warning("Redis GET error - fallback to L3", key=key[:50], error=str(e))
        return None  # ✅ Graceful fallback to PostgreSQL
```

#### Current Strengths

- ✅ **Graceful Degradation**: App continues if Redis unavailable
- ✅ **Fallback Path**: L1 (in-memory) → L2 (Redis) → L3 (PostgreSQL)
- ✅ **Metrics Tracking**: Tracks hits/misses/errors
- ✅ **Connection Pooling**: max_connections=20

#### Current Weaknesses

- ❌ **No Circuit Breaker**: Every operation attempts Redis connection even if down
- ❌ **Log Noise**: Warning logged on EVERY failed operation (could be 1000s/sec)
- ❌ **No Backoff**: Continuous retry attempts with no throttling
- ❌ **Thundering Herd**: All requests hammer failing Redis simultaneously

#### Failure Scenarios

**Scenario 1: Redis Process Crash**
```
Before Circuit Breaker:
T+0s:  Redis crashes
T+1s:  1000 requests → 1000 connection attempts → 1000 errors → 1000 log warnings
T+2s:  1000 requests → 1000 connection attempts → 1000 errors → 1000 log warnings
...continues until Redis restarts...

After Circuit Breaker:
T+0s:  Redis crashes
T+1s:  5 failures → Circuit OPEN → Subsequent requests fail fast (<1ms)
T+31s: Circuit HALF_OPEN → 1 test request → Success → Circuit CLOSED
```

**Scenario 2: Redis Network Partition**
```
Before Circuit Breaker:
Every request waits for connection timeout (~1-5s) → Slow responses

After Circuit Breaker:
5 failures → Circuit OPEN → Immediate failures → Fast responses
```

#### Recommended Circuit Breaker Configuration

```python
RedisCircuitBreaker(
    failure_threshold=5,        # Open after 5 consecutive failures
    recovery_timeout=30,        # Try to recover after 30 seconds
    half_open_max_calls=1,      # Only 1 test call in HALF_OPEN
    expected_exception=Exception,
    name="redis_cache"
)
```

**Rationale**:
- `failure_threshold=5`: Quick detection (5 failures = Redis likely down)
- `recovery_timeout=30s`: Balance between recovery detection and avoiding thundering herd
- `half_open_max_calls=1`: Single test call minimizes load on recovering Redis

---

### 3.2 Dependency #2: Embedding Service (AI Models)

#### Overview

**Purpose**: Generate TEXT and CODE embeddings for vector search
**Location**: `api/services/dual_embedding_service.py`
**Criticality**: **HIGH** (Core functionality depends on embeddings)
**Call Frequency**: **MEDIUM** (Per-file indexing, batch operations)
**Resource**: CPU/RAM intensive (660-700MB RAM for both models)

#### Current Implementation

```python
# Model loading (dual_embedding_service.py:194-228)
async def _ensure_text_model(self):
    if self._text_model is not None:
        return

    async with self._text_lock:  # Thread-safe
        if self._text_model is not None:
            return

        if self._text_load_attempted:
            raise RuntimeError(
                "Text model loading failed previously. Restart service."
            )  # ❌ FAIL-FOREVER: No recovery

        self._text_load_attempted = True

        try:
            loop = asyncio.get_running_loop()
            self._text_model = await loop.run_in_executor(
                None,
                self._load_text_model_sync
            )
        except Exception as e:
            logger.error(f"❌ Failed to load TEXT model: {e}", exc_info=True)
            self._text_model = None
            raise RuntimeError(f"Failed to load TEXT model: {e}") from e

# Embedding generation with timeout (lines 373-418)
try:
    text_emb = await with_timeout(
        encode_coro,
        timeout=get_timeout("embedding_generation_single"),  # 10s
        operation_name="embedding_generation_text_single",
        raise_on_timeout=True
    )
    result['text'] = text_emb.tolist()

except TimeoutError as e:
    logger.error(
        f"Text embedding generation timed out after {get_timeout('embedding_generation_single')}s"
    )
    raise  # ❌ NO FALLBACK: Timeout causes hard failure
```

#### Current Strengths

- ✅ **RAM Protection**: Refuses CODE model if RAM > 2.5GB
- ✅ **Mock Mode**: `EMBEDDING_MODE=mock` for testing
- ✅ **Timeout Protection**: 10s single, 30s batch (EPIC-12 Story 12.1)
- ✅ **Retry Logic**: CodeIndexingService retries with exponential backoff (3x)
- ✅ **Thread Safety**: Double-checked locking for model loading

#### Current Weaknesses

- ❌ **Fail-Forever**: Once `_text_load_attempted = True` and fails, never retries
- ❌ **No Circuit Breaker**: Every embedding call attempts model.encode() even if OOM recurring
- ❌ **No Degradation Path**: If embedding fails, entire file indexing fails
- ❌ **OOM Risk**: No protection against repeated OOM on pathological inputs

#### Failure Scenarios

**Scenario 1: Model Loading Failure (OOM)**
```
Before Circuit Breaker:
T+0s:  Model load fails (OOM)
T+1s:  Request 1 → Attempt load → OOM → Fail
T+2s:  Request 2 → Attempt load → OOM → Fail
...permanently fails, requires service restart...

After Circuit Breaker:
T+0s:  Model load fails (OOM)
T+1s:  Request 1 → Circuit OPEN (after 3 failures)
T+61s: Circuit HALF_OPEN → Retry load → Success/Fail
```

**Scenario 2: Pathological Input (Timeout)**
```
Before Circuit Breaker:
File 1 with huge docstring → Timeout after 10s
File 2 with huge docstring → Timeout after 10s
...continues timing out on every large file...

After Circuit Breaker:
3 timeouts → Circuit OPEN → Subsequent files fail fast
After 60s → Circuit HALF_OPEN → Retry
```

#### Recommended Circuit Breaker Configuration

```python
EmbeddingCircuitBreaker(
    failure_threshold=3,            # Open after 3 consecutive failures
    recovery_timeout=60,            # Try to recover after 60 seconds
    half_open_max_calls=1,          # Single test call
    expected_exception=(RuntimeError, TimeoutError, MemoryError),
    name="embedding_service"
)
```

**Rationale**:
- `failure_threshold=3`: Detect persistent failures quickly (3 OOMs = model won't load)
- `recovery_timeout=60s`: Give time for memory to be freed, GC to run
- `expected_exception`: Handle OOM, timeout, and model loading errors

---

### 3.3 Dependency #3: PostgreSQL Database

#### Overview

**Purpose**: Primary data store (L3 in cache cascade)
**Location**: All repositories, main.py
**Criticality**: **CRITICAL** (No PostgreSQL = No service)
**Call Frequency**: **HIGH** (Every database operation)
**Network**: Yes (TCP connection to localhost:5432)

#### Current Implementation

```python
# Engine creation (main.py:57-71)
app.state.db_engine: AsyncEngine = create_async_engine(
    db_url_to_use,
    echo=DEBUG,
    pool_size=20,              # ✅ Connection pooling
    max_overflow=10,           # ✅ Overflow connections
    pool_recycle=3600,         # ✅ Recycle connections after 1 hour
    connect_args={
        "command_timeout": 60,  # ✅ 60 seconds timeout
    }
)

# Health check (health_routes.py:39-48)
async def check_postgres_via_engine(engine: AsyncEngine):
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            return {"status": "ok", "version": version}
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {str(e)}")
        return {"status": "error", "message": str(e)}
```

#### Current Strengths

- ✅ **Connection Pooling**: 20 base + 10 overflow = 30 max connections
- ✅ **Pool Recycling**: Connections recycled after 1 hour
- ✅ **Command Timeout**: 60s timeout on all queries
- ✅ **Health Check**: `/health` endpoint checks DB connectivity
- ✅ **Transaction Support**: EPIC-12 Story 12.2 added atomic operations

#### Current Weaknesses

- ❌ **No Circuit Breaker**: Every request attempts DB even if down
- ❌ **No Health Check Caching**: Health endpoint queries DB on every call
- ❌ **No Connection Retry**: Startup fails permanently if DB unreachable
- ⚠️ **Connection Exhaustion**: No early warning if pool exhausting

#### Recommended Circuit Breaker Configuration

PostgreSQL circuit breaker is **LOW PRIORITY** because:
- App can't function without DB (no fallback)
- Circuit breaker adds minimal value for critical dependencies
- Better suited for monitoring/alerting than functionality

```python
PostgreSQLHealthCircuitBreaker(
    failure_threshold=3,
    recovery_timeout=10,        # Short timeout (DB should recover quickly)
    cache_ttl=10,               # Cache health check result for 10s
    name="postgresql_health"
)
```

**Use Case**: Health check endpoint caching + early warning system

---

### 3.4 Dependency #4: Tree-sitter Parser (Internal)

#### Overview

**Purpose**: Parse source code into AST
**Location**: `api/services/code_chunking_service.py`
**Criticality**: **HIGH** (Required for code chunking)
**Call Frequency**: **MEDIUM** (Per-file indexing)
**Resource**: CPU-bound (can hang on pathological input)

#### Current Protection

- ✅ **Timeout Protection**: 5s timeout (EPIC-12 Story 12.1)
- ✅ **Fallback Strategy**: Fixed-size chunking if parse times out
- ✅ **Language Detection**: Auto-detect from file extension

#### Recommendation

**NO CIRCUIT BREAKER NEEDED** because:
- Internal dependency (not external service)
- Already has timeout + fallback
- Per-file operation (not shared state)
- Circuit breaker adds no value

---

## 4. Current Error Handling Patterns

### 4.1 Pattern Analysis

#### Pattern 1: Graceful Degradation (Redis) ✅ GOOD

```python
try:
    cached_data = await redis_cache.get(key)
except Exception as e:
    logger.warning("Redis error - fallback to L3", error=str(e))
    cached_data = None  # Fallback to PostgreSQL
```

**Strengths**:
- Service continues without Redis
- Clear fallback path
- User impact: Performance only (not functionality)

**Weaknesses**:
- Warning logged on EVERY failure (log noise)
- No throttling of retry attempts
- No automatic recovery detection

**Circuit Breaker Enhancement**:
```python
if not redis_circuit_breaker.can_execute():
    return None  # Fail fast without attempting connection

try:
    cached_data = await redis_cache.get(key)
    redis_circuit_breaker.record_success()
    return cached_data
except Exception as e:
    redis_circuit_breaker.record_failure()
    if redis_circuit_breaker.state == CircuitState.OPEN:
        logger.warning("Redis circuit OPEN - skipping attempts")
    return None
```

---

#### Pattern 2: Fail-Forever (Embedding Service) ❌ PROBLEMATIC

```python
if self._text_load_attempted:
    raise RuntimeError("Model loading failed previously. Restart service.")
```

**Weaknesses**:
- No recovery without service restart
- Transient failures become permanent
- Poor user experience

**Circuit Breaker Enhancement**:
```python
if not embedding_circuit_breaker.can_execute():
    raise RuntimeError(
        f"Embedding circuit OPEN - will retry after {breaker.recovery_timeout}s"
    )

try:
    self._text_model = await loop.run_in_executor(None, self._load_text_model_sync)
    embedding_circuit_breaker.record_success()
except Exception as e:
    embedding_circuit_breaker.record_failure()
    raise
```

---

#### Pattern 3: Retry with Backoff (CodeIndexingService) ✅ GOOD

```python
for attempt in range(max_retries):
    try:
        embeddings = await self._generate_embeddings_for_chunk(chunk)
        return embeddings
    except Exception as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
```

**Strengths**:
- Handles transient failures
- Exponential backoff prevents thundering herd
- Eventually succeeds for recoverable errors

**Weaknesses**:
- Retries even if circuit breaker knows service is down
- No coordination across requests

**Circuit Breaker Enhancement**:
```python
for attempt in range(max_retries):
    # Check circuit breaker BEFORE attempting
    if not embedding_circuit_breaker.can_execute():
        raise CircuitBreakerOpen("Embedding service circuit is OPEN")

    try:
        embeddings = await self._generate_embeddings_for_chunk(chunk)
        embedding_circuit_breaker.record_success()
        return embeddings
    except Exception as e:
        embedding_circuit_breaker.record_failure()
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
```

---

#### Pattern 4: Timeout Protection (EPIC-12 Story 12.1) ✅ EXCELLENT

```python
result = await with_timeout(
    operation(),
    timeout=get_timeout("operation_name"),
    operation_name="operation_name",
    raise_on_timeout=True
)
```

**Strengths**:
- Prevents infinite hangs
- Configurable timeouts
- Comprehensive logging
- Already implemented across all services

**Circuit Breaker Synergy**:
```python
if not circuit_breaker.can_execute():
    raise CircuitBreakerOpen("Service circuit is OPEN")

result = await with_timeout(
    operation(),
    timeout=get_timeout("operation_name"),
    operation_name="operation_name",
    raise_on_timeout=True
)
circuit_breaker.record_success()
```

**Benefit**: Timeout and circuit breaker work together:
- Timeout: Prevents individual calls from hanging
- Circuit Breaker: Prevents repeated calls to known-slow service

---

### 4.2 Error Handling Gaps Summary

| Pattern | Implemented | Missing | Priority |
|---------|-------------|---------|----------|
| Timeout Protection | ✅ EPIC-12 Story 12.1 | - | - |
| Transaction Boundaries | ✅ EPIC-12 Story 12.2 | - | - |
| Retry with Backoff | ✅ CodeIndexingService | Circuit coordination | Medium |
| Graceful Degradation | ✅ Redis | Circuit breaker | High |
| Circuit Breakers | ❌ None | All dependencies | **High** |
| Health Check Caching | ❌ None | PostgreSQL | Medium |
| Fail-Forever Recovery | ❌ Embedding Service | Circuit breaker | High |

---

## 5. Circuit Breaker Design

### 5.1 State Machine

```
                    ┌─────────────────────────────────────┐
                    │          CLOSED                     │
                    │  (Normal operation)                 │
                    │  • Requests pass through            │
                    │  • Failures counted                 │
                    └──────────────┬──────────────────────┘
                                   │
                                   │ failure_count >= threshold
                                   ▼
                    ┌─────────────────────────────────────┐
                    │           OPEN                      │
                    │  (Service failing)                  │
                    │  • Requests fail immediately        │
                    │  • No calls to service              │
                    │  • Wait for recovery_timeout        │
                    └──────────────┬──────────────────────┘
                                   │
                                   │ After recovery_timeout
                                   ▼
                    ┌─────────────────────────────────────┐
                    │        HALF_OPEN                    │
                    │  (Testing recovery)                 │
                    │  • Limited test calls allowed       │
                    │  • If success → CLOSED              │
                    │  • If failure → OPEN                │
                    └─────────────────────────────────────┘
```

### 5.2 Core Circuit Breaker Class

```python
# api/utils/circuit_breaker.py

from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
import structlog

logger = structlog.get_logger()


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failure threshold reached
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for external dependencies.

    Pattern:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Failure threshold reached, fail fast
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

        if not breaker.can_execute():
            raise CircuitBreakerOpen("Service unavailable")

        try:
            result = await service.call()
            breaker.record_success()
            return result
        except Exception as e:
            breaker.record_failure()
            raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 1,
        name: str = "service"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            half_open_max_calls: Max calls allowed in HALF_OPEN state
            name: Service name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0

        logger.info(
            "Circuit breaker initialized",
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    def can_execute(self) -> bool:
        """
        Check if circuit allows execution.

        Returns:
            True if call should proceed, False if should fail fast
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if self.last_failure_time is None:
                return False

            elapsed = datetime.now() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                # Transition to HALF_OPEN
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info(
                    "Circuit breaker transitioning to HALF_OPEN",
                    name=self.name,
                    elapsed_seconds=elapsed.total_seconds()
                )
                return True
            else:
                # Still OPEN, fail fast
                return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited test calls
            if self.half_open_calls < self.half_open_max_calls:
                self.half_open_calls += 1
                return True
            else:
                # Max test calls reached, wait longer
                return False

        return False

    def record_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            # Success in HALF_OPEN → Transition to CLOSED
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            logger.info(
                "Circuit breaker recovered, transitioning to CLOSED",
                name=self.name
            )
        elif self.state == CircuitState.CLOSED:
            # Success in CLOSED → Reset failure count
            self.failure_count = 0
            self.success_count += 1

    def record_failure(self) -> None:
        """Record failed call."""
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            # Failure in HALF_OPEN → Back to OPEN
            self.state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker test call failed, returning to OPEN",
                name=self.name
            )
        elif self.state == CircuitState.CLOSED:
            # Failure in CLOSED → Increment count, maybe open
            self.failure_count += 1

            if self.failure_count >= self.failure_threshold:
                # Threshold reached → Transition to OPEN
                self.state = CircuitState.OPEN
                logger.error(
                    "Circuit breaker OPENED due to repeated failures",
                    name=self.name,
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold
                )

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_metrics(self) -> dict:
        """Get circuit breaker metrics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "half_open_calls": self.half_open_calls if self.state == CircuitState.HALF_OPEN else 0
        }

    def reset(self) -> None:
        """Manually reset circuit breaker (for testing/admin)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        logger.info("Circuit breaker manually reset", name=self.name)
```

### 5.3 Design Decisions

#### Decision 1: State-Based vs Call-Based

**Chosen**: State-Based (3 states: CLOSED/OPEN/HALF_OPEN)

**Rationale**:
- Clear state transitions
- Easy to monitor/visualize
- Matches industry standard (Netflix Hystrix, resilience4j)
- Better for observability

**Alternative**: Call-based (percentage of failures)
- More complex
- Harder to reason about
- Delayed reaction to failures

---

#### Decision 2: Failure Threshold

**Chosen**: Configurable per dependency
- Redis: 5 failures (high frequency, non-critical)
- Embedding: 3 failures (low frequency, critical)
- PostgreSQL: 3 failures (critical, low tolerance)

**Rationale**:
- Different dependencies have different failure characteristics
- Critical services need faster detection
- High-frequency services need more tolerance for transient errors

---

#### Decision 3: Recovery Timeout

**Chosen**: Configurable per dependency
- Redis: 30s (quick recovery expected)
- Embedding: 60s (model loading/OOM recovery needs time)
- PostgreSQL: 10s (should recover quickly or stay down)

**Rationale**:
- Different services have different recovery times
- Balance between quick recovery and avoiding thundering herd
- Embedding service needs longer for GC/memory cleanup

---

#### Decision 4: Half-Open Max Calls

**Chosen**: 1 test call for all dependencies

**Rationale**:
- Minimize load on recovering service
- Single test call sufficient to detect recovery
- Faster transition to CLOSED or OPEN

**Alternative**: Multiple test calls
- More confident recovery detection
- Higher load on recovering service
- Slower state transitions

---

### 5.4 Integration Points

```python
# Integration with Redis Cache
class RedisCache:
    def __init__(self, redis_url: str):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            name="redis_cache"
        )

    async def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None

        if not self.circuit_breaker.can_execute():
            logger.debug("Redis circuit OPEN - skipping", key=key[:50])
            self.misses += 1
            return None

        try:
            value = await self.client.get(key)
            self.circuit_breaker.record_success()
            # ... rest of implementation
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.warning("Redis error", error=str(e), circuit_state=self.circuit_breaker.state.value)
            return None
```

```python
# Integration with Embedding Service
class DualEmbeddingService:
    def __init__(self, ...):
        self.text_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            name="text_embedding"
        )

    async def _ensure_text_model(self):
        if self._text_model is not None:
            return

        if not self.text_circuit_breaker.can_execute():
            raise RuntimeError(
                f"Text model circuit OPEN - will retry after recovery timeout"
            )

        try:
            # ... model loading
            self.text_circuit_breaker.record_success()
        except Exception as e:
            self.text_circuit_breaker.record_failure()
            raise
```

---

## 6. Implementation Priorities

### 6.1 Priority Matrix

| Dependency | Priority | Effort | Impact | Risk | Score |
|------------|----------|--------|--------|------|-------|
| Redis Cache | **HIGH** | Low (2 pts) | Medium | Low | ⭐⭐⭐⭐⭐ |
| Embedding Service | **MEDIUM** | Medium (1 pt) | High | Medium | ⭐⭐⭐⭐ |
| PostgreSQL | **LOW** | Medium (1 pt) | Low | Low | ⭐⭐ |
| Tree-sitter | **NONE** | - | - | - | - |

### 6.2 Implementation Phases

#### Phase 1: Circuit Breaker Foundation (2 pts)

**Goal**: Create reusable circuit breaker infrastructure

**Tasks**:
1. Create `api/utils/circuit_breaker.py` with base class
2. Implement 3-state machine (CLOSED/OPEN/HALF_OPEN)
3. Add comprehensive unit tests (10+ test cases)
4. Integrate with structlog for monitoring
5. Add metrics endpoint for circuit states

**Files**:
- `NEW`: api/utils/circuit_breaker.py (~200 lines)
- `NEW`: tests/unit/utils/test_circuit_breaker.py (~300 lines)
- `MODIFY`: api/routes/health_routes.py (+30 lines - expose circuit metrics)

**Acceptance Criteria**:
- All unit tests passing (100% coverage)
- State transitions work correctly
- Metrics accessible via health endpoint
- Logging integrated with structlog

**Estimated Time**: 2-3 hours

---

#### Phase 2: Redis Circuit Breaker (2 pts)

**Goal**: Add circuit breaker protection to Redis cache

**Tasks**:
1. Integrate circuit breaker into `RedisCache` class
2. Update `CascadeCache` to respect circuit state
3. Add circuit state to cache metrics
4. Create integration tests (5+ scenarios)
5. Update documentation

**Files**:
- `MODIFY`: api/services/caches/redis_cache.py (+50 lines)
- `MODIFY`: api/services/caches/cascade_cache.py (+20 lines)
- `NEW`: tests/integration/test_redis_circuit_breaker.py (~200 lines)

**Acceptance Criteria**:
- Circuit opens after 5 Redis failures
- Circuit closes after successful recovery
- Graceful degradation still works
- Integration tests pass
- Log noise reduced (one log per state change, not per operation)

**Estimated Time**: 2-3 hours

---

#### Phase 3: Embedding Circuit Breaker (1 pt)

**Goal**: Add circuit breaker protection to embedding service

**Tasks**:
1. Integrate circuit breaker into `DualEmbeddingService`
2. Remove fail-forever behavior
3. Update retry logic to respect circuit state
4. Create integration tests (3+ scenarios)
5. Update documentation

**Files**:
- `MODIFY`: api/services/dual_embedding_service.py (+60 lines)
- `MODIFY`: api/services/code_indexing_service.py (+10 lines - check circuit before retry)
- `NEW`: tests/integration/test_embedding_circuit_breaker.py (~150 lines)

**Acceptance Criteria**:
- Circuit opens after 3 embedding failures
- Automatic recovery after 60s
- No more fail-forever behavior
- Integration tests pass
- Better error messages with circuit state

**Estimated Time**: 1-2 hours

---

### 6.3 Testing Strategy

#### Unit Tests (`tests/unit/utils/test_circuit_breaker.py`)

```python
@pytest.mark.anyio
async def test_circuit_opens_after_threshold():
    """Circuit opens after failure threshold reached."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True

    # Record 3 failures
    for i in range(3):
        breaker.record_failure()

    # Circuit should now be OPEN
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False


@pytest.mark.anyio
async def test_circuit_transitions_to_half_open():
    """Circuit transitions to HALF_OPEN after recovery timeout."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)  # 1 second

    # Open circuit
    for i in range(3):
        breaker.record_failure()

    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(1.1)

    # Next call should transition to HALF_OPEN
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.HALF_OPEN


@pytest.mark.anyio
async def test_circuit_closes_after_successful_half_open():
    """Circuit closes after successful call in HALF_OPEN."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    # Open circuit
    for i in range(3):
        breaker.record_failure()

    # Wait and transition to HALF_OPEN
    await asyncio.sleep(1.1)
    breaker.can_execute()

    # Successful call → Should close circuit
    breaker.record_success()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True


@pytest.mark.anyio
async def test_circuit_returns_to_open_after_failed_half_open():
    """Circuit returns to OPEN if HALF_OPEN call fails."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    # Open circuit
    for i in range(3):
        breaker.record_failure()

    # Wait and transition to HALF_OPEN
    await asyncio.sleep(1.1)
    breaker.can_execute()

    # Failed call → Should return to OPEN
    breaker.record_failure()

    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False
```

#### Integration Tests (`tests/integration/test_redis_circuit_breaker.py`)

```python
@pytest.mark.anyio
async def test_redis_circuit_opens_on_connection_failure():
    """Redis circuit breaker opens when connection fails."""
    # Create Redis cache with invalid URL
    redis_cache = RedisCache(redis_url="redis://invalid-host:6379/0")

    # Attempt connection
    with pytest.raises(Exception):
        await redis_cache.connect()

    # Try multiple get operations (should fail)
    for i in range(5):
        result = await redis_cache.get(f"test_key_{i}")
        assert result is None

    # Circuit should now be OPEN
    assert redis_cache.circuit_breaker.state == CircuitState.OPEN

    # Subsequent calls should fail fast (no connection attempt)
    start_time = time.time()
    result = await redis_cache.get("test_key_fast_fail")
    elapsed = time.time() - start_time

    assert result is None
    assert elapsed < 0.01  # Should be < 10ms (fail fast)


@pytest.mark.anyio
async def test_redis_circuit_recovers_after_timeout():
    """Redis circuit breaker recovers when service comes back online."""
    # Start with circuit OPEN (simulate previous failures)
    redis_cache = RedisCache(redis_url=os.getenv("REDIS_URL"))
    redis_cache.circuit_breaker.state = CircuitState.OPEN
    redis_cache.circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=31)

    # Redis is actually available, should recover
    result = await redis_cache.get("test_key")

    # Circuit should transition to HALF_OPEN, then CLOSED
    assert redis_cache.circuit_breaker.state in (CircuitState.HALF_OPEN, CircuitState.CLOSED)
```

---

## 7. Risk Assessment

### 7.1 Implementation Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Circuit too sensitive | Medium | Medium | Configurable thresholds, metrics monitoring |
| Circuit stuck OPEN | Low | High | Manual reset endpoint, alerting |
| False positives | Medium | Low | Higher threshold for critical services |
| Recovery detection delay | Medium | Medium | Shorter recovery timeout for non-critical |
| Breaking changes | Low | High | Backward compatible, optional feature |

### 7.2 Operational Risks

**Risk**: Circuit breaker masks underlying issues

**Mitigation**:
- Circuit state changes logged and alerted
- Metrics exposed on health endpoint
- Dashboard shows circuit states
- Open circuit triggers alert to ops team

**Risk**: Circuit stuck OPEN due to misconfiguration

**Mitigation**:
- Manual reset endpoint: `POST /admin/circuit-breaker/{name}/reset`
- Default configuration tested in staging
- Health check exposes circuit states

### 7.3 Backward Compatibility

**Guarantee**: 100% backward compatible

**Reason**:
- Circuit breaker wraps existing error handling
- No API changes required
- Graceful degradation still works
- Can be disabled via configuration

**Configuration**:
```python
# Disable circuit breakers (for rollback)
CIRCUIT_BREAKER_ENABLED = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"

if CIRCUIT_BREAKER_ENABLED:
    self.circuit_breaker = CircuitBreaker(...)
else:
    self.circuit_breaker = None  # Bypass circuit breaker
```

---

## 8. Success Metrics

### 8.1 Functional Metrics

- **Circuit Opens**: Circuit should open after N consecutive failures
- **Circuit Closes**: Circuit should close after successful recovery
- **Fast Fail**: OPEN circuit should fail in < 1ms (no service call)
- **Recovery Detection**: Circuit should detect recovery within recovery_timeout
- **State Transitions**: All state transitions logged and trackable

### 8.2 Performance Metrics

**Before Circuit Breaker** (Redis down):
```
Request 1: 5000ms (connection timeout)
Request 2: 5000ms (connection timeout)
Request 3: 5000ms (connection timeout)
...
Average: 5000ms per request
```

**After Circuit Breaker** (Redis down):
```
Request 1-5: 5000ms (connection timeout, accumulating failures)
Request 6+: <1ms (circuit OPEN, fail fast)
...
Average: ~50ms per request (10x improvement)
```

### 8.3 Observability Metrics

**Exposed via `/health` endpoint**:
```json
{
  "status": "healthy",
  "circuit_breakers": {
    "redis_cache": {
      "state": "closed",
      "failure_count": 0,
      "success_count": 1523,
      "last_failure_time": null
    },
    "text_embedding": {
      "state": "closed",
      "failure_count": 0,
      "success_count": 42
    },
    "code_embedding": {
      "state": "open",
      "failure_count": 5,
      "last_failure_time": "2025-10-21T11:30:00",
      "recovery_in": "45s"
    }
  }
}
```

### 8.4 Logging Improvements

**Before**:
```
2025-10-21 11:30:00 WARNING Redis GET error - fallback to L3, key=test_key, error=...
2025-10-21 11:30:00 WARNING Redis GET error - fallback to L3, key=test_key_2, error=...
2025-10-21 11:30:00 WARNING Redis GET error - fallback to L3, key=test_key_3, error=...
... (1000s of warnings)
```

**After**:
```
2025-10-21 11:30:00 ERROR Circuit breaker OPENED, name=redis_cache, failure_count=5
2025-10-21 11:30:30 INFO Circuit breaker transitioning to HALF_OPEN, name=redis_cache
2025-10-21 11:30:31 INFO Circuit breaker recovered, transitioning to CLOSED, name=redis_cache
... (3 logs total instead of 1000s)
```

**Improvement**: 99%+ reduction in log volume during outages

---

## 9. Appendix

### 9.1 Industry Standards

**Netflix Hystrix** (Inspiration):
- 3-state circuit breaker (CLOSED/OPEN/HALF_OPEN)
- Configurable failure threshold
- Sliding window for failure rate
- Thread isolation for bulkhead pattern

**resilience4j** (Java):
- Circuit breaker + rate limiter + retry
- Ring buffer for failure tracking
- Event-based monitoring
- Time-based failure rate

**MnemoLite Approach**: Simplified Hystrix pattern
- 3-state machine (CLOSED/OPEN/HALF_OPEN)
- Count-based threshold (simpler than sliding window)
- Single test call in HALF_OPEN (minimalist)
- Structlog integration for monitoring

### 9.2 Alternative Approaches Considered

#### Approach 1: Percentage-Based Circuit Breaker

```python
# Open if failure rate > 50% over last 100 requests
if (failures / total_requests) > 0.5:
    state = OPEN
```

**Pros**: More nuanced than count-based
**Cons**: More complex, harder to reason about, delayed reaction

**Decision**: Rejected (unnecessary complexity)

---

#### Approach 2: Token Bucket Rate Limiter

```python
# Allow N requests per second to failing service
if bucket.has_tokens(1):
    bucket.consume(1)
    call_service()
```

**Pros**: Gradual throttling instead of binary OPEN/CLOSED
**Cons**: Doesn't prevent thundering herd, more complex

**Decision**: Rejected (circuit breaker simpler and more effective)

---

#### Approach 3: Bulkhead Pattern (Thread/Connection Pools)

```python
# Isolate Redis calls in dedicated thread pool
redis_pool = ThreadPoolExecutor(max_workers=5)
await redis_pool.submit(redis.get, key)
```

**Pros**: Prevents Redis failures from blocking other operations
**Cons**: Already have connection pooling, adds complexity

**Decision**: Deferred to future story (not needed for Story 12.3)

---

### 9.3 Configuration Reference

```python
# api/config/circuit_breaker.py (NEW)

from dataclasses import dataclass

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breakers."""

    # Redis Cache Circuit Breaker
    REDIS_FAILURE_THRESHOLD: int = 5
    REDIS_RECOVERY_TIMEOUT: int = 30
    REDIS_HALF_OPEN_MAX_CALLS: int = 1

    # Embedding Service Circuit Breaker
    EMBEDDING_FAILURE_THRESHOLD: int = 3
    EMBEDDING_RECOVERY_TIMEOUT: int = 60
    EMBEDDING_HALF_OPEN_MAX_CALLS: int = 1

    # PostgreSQL Health Circuit Breaker
    POSTGRES_FAILURE_THRESHOLD: int = 3
    POSTGRES_RECOVERY_TIMEOUT: int = 10
    POSTGRES_HEALTH_CACHE_TTL: int = 10

    # Global Circuit Breaker Settings
    CIRCUIT_BREAKER_ENABLED: bool = True


def get_circuit_breaker_config() -> CircuitBreakerConfig:
    """Get circuit breaker configuration from environment."""
    return CircuitBreakerConfig(
        REDIS_FAILURE_THRESHOLD=int(os.getenv("REDIS_CB_THRESHOLD", "5")),
        REDIS_RECOVERY_TIMEOUT=int(os.getenv("REDIS_CB_TIMEOUT", "30")),
        # ... etc
    )
```

---

### 9.4 Monitoring & Alerting

**Prometheus Metrics** (Future Enhancement):
```python
circuit_breaker_state_gauge{name="redis_cache"} = 0  # CLOSED=0, OPEN=1, HALF_OPEN=2
circuit_breaker_failures_total{name="redis_cache"} = 42
circuit_breaker_successes_total{name="redis_cache"} = 10523
circuit_breaker_state_transitions_total{name="redis_cache", from="closed", to="open"} = 3
```

**Alert Rules**:
```yaml
- alert: CircuitBreakerOpen
  expr: circuit_breaker_state_gauge{name="redis_cache"} == 1
  for: 5m
  annotations:
    summary: "Redis circuit breaker has been OPEN for 5 minutes"

- alert: CircuitBreakerFlapping
  expr: rate(circuit_breaker_state_transitions_total[5m]) > 10
  annotations:
    summary: "Circuit breaker flapping (>10 transitions in 5m)"
```

---

### 9.5 References

- Netflix Hystrix: https://github.com/Netflix/Hystrix/wiki/How-it-Works
- resilience4j: https://resilience4j.readme.io/docs/circuitbreaker
- Martin Fowler - Circuit Breaker: https://martinfowler.com/bliki/CircuitBreaker.html
- Release It! (Book) by Michael Nygard - Chapter on Stability Patterns

---

**Document Status**: ✅ COMPLETE
**Ready for Implementation**: ✅ YES
**Next Step**: Create EPIC-12_STORY_12.3_IMPLEMENTATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
