# EPIC-12 Story 12.3: Circuit Breakers - Implementation Plan

**Status**: 📋 READY FOR IMPLEMENTATION
**Story Points**: 5 pts (2 + 2 + 1)
**Dependencies**: Story 12.1 (Timeouts) ✅, Story 12.2 (Transactions) ✅
**Created**: 2025-10-21
**Target**: Production-grade fault tolerance

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Prerequisites](#prerequisites)
3. [Implementation Phases](#implementation-phases)
   - [Phase 1: Circuit Breaker Foundation (2 pts)](#phase-1-circuit-breaker-foundation-2-pts)
   - [Phase 2: Redis Circuit Breaker (2 pts)](#phase-2-redis-circuit-breaker-2-pts)
   - [Phase 3: Embedding Circuit Breaker (1 pt)](#phase-3-embedding-circuit-breaker-1-pt)
4. [Testing Strategy](#testing-strategy)
5. [Verification Checklist](#verification-checklist)
6. [Rollback Plan](#rollback-plan)

---

## Executive Summary

**Goal**: Implement circuit breakers to prevent cascading failures from external dependencies.

**What We're Building**:
- Generic circuit breaker utility class with 3 states (CLOSED/OPEN/HALF_OPEN)
- Circuit breaker integration for Redis cache (high priority)
- Circuit breaker integration for embedding service (medium priority)
- Health check endpoints exposing circuit breaker state
- Comprehensive test coverage (unit + integration)

**Success Criteria**:
- ✅ Circuit breaker state machine implemented with all 3 states
- ✅ Configurable failure threshold and recovery timeout
- ✅ Redis operations protected with circuit breaker
- ✅ Embedding service protected with circuit breaker
- ✅ Health endpoints expose circuit breaker metrics
- ✅ 100% test coverage for circuit breaker logic
- ✅ Integration tests verify behavior under failure conditions

**Timeline**: 3-4 hours (2h foundation + 1h Redis + 1h embedding)

---

## Prerequisites

**Required Story Completion**:
- ✅ Story 12.1 (Timeouts) - Circuit breakers will use timeout utilities
- ✅ Story 12.2 (Transactions) - No direct dependency

**Environment Setup**:
```bash
# Ensure services are running
make up

# Verify Redis is accessible
make db-shell
# Then test Redis connection

# Run existing tests to ensure baseline
make api-test
```

**Required Knowledge**:
- Circuit breaker pattern (see EPIC-12_STORY_12.3_ANALYSIS.md)
- AsyncIO patterns in Python
- Structlog for logging
- pytest-asyncio for testing

---

## Implementation Phases

### Phase 1: Circuit Breaker Foundation (2 pts)

**Goal**: Create generic circuit breaker utility that can be reused for any external dependency.

**Estimated Time**: 2 hours

---

#### Step 1.1: Create Circuit Breaker State Enum

**File**: `api/utils/circuit_breaker.py` (new file)

```python
"""
Circuit Breaker utility for fault tolerance.

Implements the circuit breaker pattern to prevent cascading failures
from external dependencies.

Pattern:
- CLOSED: Normal operation, calls pass through
- OPEN: Failure threshold reached, fail fast
- HALF_OPEN: Testing if service recovered

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Callable, Any, TypeVar, Generic
from dataclasses import dataclass
import structlog
import asyncio
from functools import wraps

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        half_open_max_calls: Max calls allowed in HALF_OPEN state
        name: Service name for logging
    """
    failure_threshold: int = 5
    recovery_timeout: int = 30
    half_open_max_calls: int = 1
    name: str = "service"
```

**Verification**:
```python
# Test import works
from api.utils.circuit_breaker import CircuitState, CircuitBreakerConfig
assert CircuitState.CLOSED == "closed"
```

---

#### Step 1.2: Implement Circuit Breaker Core Class

**File**: `api/utils/circuit_breaker.py` (continued)

```python
class CircuitBreakerError(Exception):
    """Raised when circuit breaker is OPEN and rejects calls."""
    def __init__(self, service_name: str, state: CircuitState):
        self.service_name = service_name
        self.state = state
        super().__init__(
            f"Circuit breaker for '{service_name}' is {state.value}. "
            f"Service unavailable, failing fast."
        )


class CircuitBreaker:
    """
    Circuit breaker for external dependencies.

    Usage:
        breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            name="redis"
        )

        # Option 1: Manual check
        if breaker.can_execute():
            try:
                result = await external_call()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
        else:
            raise CircuitBreakerError(breaker.name, breaker.state)

        # Option 2: Decorator
        @breaker.protect
        async def call_external():
            return await external_call()
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
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds to wait in OPEN state before testing recovery
            half_open_max_calls: Max calls in HALF_OPEN before deciding state
            name: Service name for logging and metrics
        """
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            name=name
        )

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._state_changed_at = datetime.now()

        self.logger = logger.bind(circuit_breaker=name)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def name(self) -> str:
        """Get service name."""
        return self.config.name

    def can_execute(self) -> bool:
        """
        Check if circuit allows execution.

        Returns:
            True if execution is allowed, False if circuit is OPEN
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time is None:
                return True  # Should not happen, but safe default

            elapsed = datetime.now() - self._last_failure_time
            recovery_delta = timedelta(seconds=self.config.recovery_timeout)

            if elapsed >= recovery_delta:
                # Transition to HALF_OPEN
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_calls = 0
                return True

            return False  # Still in OPEN state

        if self._state == CircuitState.HALF_OPEN:
            # Allow limited calls to test recovery
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False  # Unknown state, fail safe

    def record_success(self) -> None:
        """
        Record successful operation.

        Behavior by state:
        - CLOSED: Increment success count (no-op, already working)
        - OPEN: Should not happen (can_execute should return False)
        - HALF_OPEN: Close circuit after success
        """
        self._success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            # Service recovered, close circuit
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._half_open_calls = 0

        elif self._state == CircuitState.CLOSED:
            # Normal operation
            pass

        elif self._state == CircuitState.OPEN:
            # Should not happen, but log warning
            self.logger.warning(
                "success_recorded_while_open",
                state=self._state.value,
                message="Success recorded while circuit is OPEN (unexpected)"
            )

    def record_failure(self) -> None:
        """
        Record failed operation.

        Behavior by state:
        - CLOSED: Increment failure count, open if threshold reached
        - OPEN: Update last failure time
        - HALF_OPEN: Open circuit (service still failing)
        """
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                # Threshold reached, open circuit
                self._transition_to(CircuitState.OPEN)

        elif self._state == CircuitState.HALF_OPEN:
            # Service still failing, reopen circuit
            self._transition_to(CircuitState.OPEN)
            self._half_open_calls = 0

        elif self._state == CircuitState.OPEN:
            # Already open, just update timestamp
            pass

    def _transition_to(self, new_state: CircuitState) -> None:
        """
        Transition to new state and log event.

        Args:
            new_state: Target state
        """
        old_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.now()

        self.logger.info(
            "circuit_breaker_state_change",
            old_state=old_state.value,
            new_state=new_state.value,
            failure_count=self._failure_count,
            success_count=self._success_count,
            service=self.config.name
        )

    def get_metrics(self) -> dict:
        """
        Get circuit breaker metrics for monitoring.

        Returns:
            Dict with current state, counts, and timestamps
        """
        return {
            "service": self.config.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "state_changed_at": self._state_changed_at.isoformat(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "half_open_max_calls": self.config.half_open_max_calls
            }
        }

    def reset(self) -> None:
        """
        Reset circuit breaker to initial state.

        Use with caution - typically for testing or manual intervention.
        """
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        self._state_changed_at = datetime.now()

        self.logger.warning(
            "circuit_breaker_reset",
            old_state=old_state.value,
            message="Circuit breaker manually reset"
        )

    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to protect async functions with circuit breaker.

        Usage:
            breaker = CircuitBreaker(name="my_service")

            @breaker.protect
            async def call_external():
                return await external_api()

        Args:
            func: Async function to protect

        Returns:
            Wrapped function that checks circuit breaker
        """
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not self.can_execute():
                raise CircuitBreakerError(self.name, self.state)

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        return wrapper
```

**Verification**:
```python
# Test basic instantiation
from api.utils.circuit_breaker import CircuitBreaker
breaker = CircuitBreaker(name="test")
assert breaker.state == CircuitState.CLOSED
assert breaker.can_execute() == True
```

---

#### Step 1.3: Create Unit Tests for Circuit Breaker

**File**: `tests/unit/utils/test_circuit_breaker.py` (new file)

```python
"""
Unit tests for circuit breaker utility.

Tests all state transitions, edge cases, and decorator functionality.

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import asyncio

from api.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerError
)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30
        assert config.half_open_max_calls == 1
        assert config.name == "service"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
            half_open_max_calls=2,
            name="redis"
        )
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 60
        assert config.half_open_max_calls == 2
        assert config.name == "redis"


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test circuit starts in CLOSED state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    def test_closed_to_open_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            name="test"
        )

        # Record failures
        for i in range(2):
            breaker.record_failure()
            assert breaker.state == CircuitState.CLOSED

        # Third failure should open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

    def test_open_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=1,  # 1 second for fast test
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

        # Wait for recovery timeout
        import time
        time.sleep(1.1)

        # Should transition to HALF_OPEN
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self):
        """Test circuit closes after successful call in HALF_OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0,  # Immediate recovery for test
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Transition to HALF_OPEN
        breaker._transition_to(CircuitState.HALF_OPEN)
        assert breaker.state == CircuitState.HALF_OPEN

        # Success should close circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    def test_half_open_to_open_on_failure(self):
        """Test circuit reopens on failure in HALF_OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0,
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Transition to HALF_OPEN
        breaker._transition_to(CircuitState.HALF_OPEN)
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure should reopen circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False

    def test_half_open_max_calls_limit(self):
        """Test HALF_OPEN state limits calls."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            half_open_max_calls=2,
            name="test"
        )

        # Transition to HALF_OPEN
        breaker._transition_to(CircuitState.HALF_OPEN)

        # First two calls should be allowed
        assert breaker.can_execute() is True
        assert breaker.can_execute() is True

        # Third call should be rejected
        assert breaker.can_execute() is False


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics and monitoring."""

    def test_get_metrics(self):
        """Test metrics include all relevant data."""
        breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            name="test"
        )

        # Record some activity
        breaker.record_success()
        breaker.record_failure()

        metrics = breaker.get_metrics()

        assert metrics["service"] == "test"
        assert metrics["state"] == CircuitState.CLOSED.value
        assert metrics["failure_count"] == 1
        assert metrics["success_count"] == 1
        assert metrics["last_failure_time"] is not None
        assert metrics["state_changed_at"] is not None
        assert metrics["config"]["failure_threshold"] == 5
        assert metrics["config"]["recovery_timeout"] == 30

    def test_reset(self):
        """Test reset clears all state."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._success_count == 0
        assert breaker._last_failure_time is None
        assert breaker.can_execute() is True


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator functionality."""

    @pytest.mark.anyio
    async def test_decorator_allows_call_when_closed(self):
        """Test decorator allows calls when circuit is CLOSED."""
        breaker = CircuitBreaker(name="test")

        @breaker.protect
        async def successful_call():
            return "success"

        result = await successful_call()
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.anyio
    async def test_decorator_blocks_call_when_open(self):
        """Test decorator blocks calls when circuit is OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        @breaker.protect
        async def blocked_call():
            return "should not execute"

        with pytest.raises(CircuitBreakerError) as exc_info:
            await blocked_call()

        assert exc_info.value.service_name == "test"
        assert exc_info.value.state == CircuitState.OPEN

    @pytest.mark.anyio
    async def test_decorator_records_success(self):
        """Test decorator records success."""
        breaker = CircuitBreaker(name="test")

        @breaker.protect
        async def successful_call():
            return "success"

        await successful_call()
        assert breaker._success_count == 1

    @pytest.mark.anyio
    async def test_decorator_records_failure(self):
        """Test decorator records failure and propagates exception."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            name="test"
        )

        @breaker.protect
        async def failing_call():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await failing_call()

        assert breaker._failure_count == 1
        assert breaker.state == CircuitState.CLOSED  # Not threshold yet

    @pytest.mark.anyio
    async def test_decorator_opens_after_threshold(self):
        """Test decorator opens circuit after failure threshold."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            name="test"
        )

        @breaker.protect
        async def failing_call():
            raise ValueError("test error")

        # First failure
        with pytest.raises(ValueError):
            await failing_call()
        assert breaker.state == CircuitState.CLOSED

        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await failing_call()
        assert breaker.state == CircuitState.OPEN

        # Third call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerError):
            await failing_call()


class TestCircuitBreakerEdgeCases:
    """Test edge cases and error handling."""

    def test_can_execute_with_no_last_failure(self):
        """Test can_execute handles None last_failure_time."""
        breaker = CircuitBreaker(name="test")
        breaker._state = CircuitState.OPEN
        breaker._last_failure_time = None

        # Should allow (safe default)
        assert breaker.can_execute() is True

    def test_success_while_open_logs_warning(self):
        """Test recording success while OPEN logs warning."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Record success (should log warning)
        with patch.object(breaker.logger, 'warning') as mock_log:
            breaker.record_success()
            mock_log.assert_called_once()
```

**Run Tests**:
```bash
# Run circuit breaker unit tests
pytest tests/unit/utils/test_circuit_breaker.py -v

# Expected: 100% pass (18+ tests)
```

---

#### Step 1.4: Add Circuit Breaker Metrics to Health Endpoint

**File**: `api/routes/health_routes.py`

**Current Code** (find this section):
```python
@router.get("/")
async def health_check(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Dict with service health status
    """
    # ... existing code ...
```

**Add Circuit Breaker Registry** at the top of the file:
```python
# Add to imports
from typing import Dict, Any, Optional

# Add global registry for circuit breakers
_circuit_breakers: Dict[str, "CircuitBreaker"] = {}


def register_circuit_breaker(breaker: "CircuitBreaker") -> None:
    """
    Register circuit breaker for health monitoring.

    Args:
        breaker: Circuit breaker instance to register
    """
    _circuit_breakers[breaker.name] = breaker


def get_circuit_breaker_metrics() -> Dict[str, Any]:
    """
    Get metrics for all registered circuit breakers.

    Returns:
        Dict mapping service names to circuit breaker metrics
    """
    return {
        name: breaker.get_metrics()
        for name, breaker in _circuit_breakers.items()
    }
```

**Modify Health Endpoint**:
```python
@router.get("/")
async def health_check(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Dict with service health status including circuit breaker states
    """
    try:
        # Test database connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()

        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Get circuit breaker metrics
    circuit_breakers = get_circuit_breaker_metrics()

    # Determine overall health
    overall_healthy = db_status == "healthy"

    # Check if any critical circuit is OPEN
    critical_circuits_open = [
        name for name, metrics in circuit_breakers.items()
        if metrics["state"] == "open" and name in ["embedding"]  # Critical services
    ]

    if critical_circuits_open:
        overall_healthy = False

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "circuit_breakers": circuit_breakers,
        "critical_circuits_open": critical_circuits_open
    }
```

**Verification**:
```bash
# Start services
make up

# Test health endpoint
curl http://localhost:8001/health | jq

# Should see circuit_breakers in response
```

---

#### Step 1.5: Create Configuration File for Circuit Breakers

**File**: `api/config/circuit_breakers.py` (new file)

```python
"""
Circuit breaker configuration.

Centralized configuration for all circuit breakers in the application.

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

from dataclasses import dataclass
import os


@dataclass
class ServiceCircuitConfig:
    """Configuration for a specific service's circuit breaker."""
    failure_threshold: int
    recovery_timeout: int
    half_open_max_calls: int = 1


# Redis Cache Circuit Breaker
REDIS_CIRCUIT_CONFIG = ServiceCircuitConfig(
    failure_threshold=int(os.getenv("REDIS_CIRCUIT_FAILURE_THRESHOLD", "5")),
    recovery_timeout=int(os.getenv("REDIS_CIRCUIT_RECOVERY_TIMEOUT", "30")),
    half_open_max_calls=int(os.getenv("REDIS_CIRCUIT_HALF_OPEN_CALLS", "1"))
)

# Embedding Service Circuit Breaker
EMBEDDING_CIRCUIT_CONFIG = ServiceCircuitConfig(
    failure_threshold=int(os.getenv("EMBEDDING_CIRCUIT_FAILURE_THRESHOLD", "3")),
    recovery_timeout=int(os.getenv("EMBEDDING_CIRCUIT_RECOVERY_TIMEOUT", "60")),
    half_open_max_calls=int(os.getenv("EMBEDDING_CIRCUIT_HALF_OPEN_CALLS", "1"))
)

# PostgreSQL Circuit Breaker (for health checks only)
DATABASE_CIRCUIT_CONFIG = ServiceCircuitConfig(
    failure_threshold=int(os.getenv("DATABASE_CIRCUIT_FAILURE_THRESHOLD", "3")),
    recovery_timeout=int(os.getenv("DATABASE_CIRCUIT_RECOVERY_TIMEOUT", "10")),
    half_open_max_calls=int(os.getenv("DATABASE_CIRCUIT_HALF_OPEN_CALLS", "1"))
)
```

**Verification**:
```python
from api.config.circuit_breakers import REDIS_CIRCUIT_CONFIG
assert REDIS_CIRCUIT_CONFIG.failure_threshold == 5
```

---

#### Phase 1 Completion Checklist

**Files Created**:
- ✅ `api/utils/circuit_breaker.py` (~400 lines)
- ✅ `api/config/circuit_breakers.py` (~50 lines)
- ✅ `tests/unit/utils/test_circuit_breaker.py` (~350 lines)

**Files Modified**:
- ✅ `api/routes/health_routes.py` (+40 lines)

**Tests**:
```bash
# Run unit tests
pytest tests/unit/utils/test_circuit_breaker.py -v

# Expected: 18+ tests passing, 100% coverage
```

**Verification**:
```bash
# Test health endpoint includes circuit breakers
curl http://localhost:8001/health | jq '.circuit_breakers'

# Should return: {}  (no breakers registered yet)
```

---

### Phase 2: Redis Circuit Breaker (2 pts)

**Goal**: Protect Redis cache operations with circuit breaker, enabling graceful degradation to L1+L3 cache cascade.

**Estimated Time**: 1 hour

---

#### Step 2.1: Add Circuit Breaker to RedisCache

**File**: `api/services/caches/redis_cache.py`

**Current Code** (find the `__init__` method):
```python
class RedisCache:
    """Redis-based L2 cache implementation."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[Redis] = None
        self.logger = structlog.get_logger(__name__)
```

**Modify to Add Circuit Breaker**:
```python
# Add to imports at top of file
from api.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError
from api.config.circuit_breakers import REDIS_CIRCUIT_CONFIG
from api.routes.health_routes import register_circuit_breaker

class RedisCache:
    """Redis-based L2 cache implementation with circuit breaker."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[Redis] = None
        self.logger = structlog.get_logger(__name__)

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=REDIS_CIRCUIT_CONFIG.failure_threshold,
            recovery_timeout=REDIS_CIRCUIT_CONFIG.recovery_timeout,
            half_open_max_calls=REDIS_CIRCUIT_CONFIG.half_open_max_calls,
            name="redis_cache"
        )

        # Register for health monitoring
        register_circuit_breaker(self.circuit_breaker)
```

**Modify `get()` Method**:
```python
async def get(self, key: str) -> Optional[Any]:
    """
    Get value from Redis cache.

    Returns None if:
    - Circuit breaker is OPEN (fail fast)
    - Redis connection failed
    - Key not found

    Args:
        key: Cache key

    Returns:
        Cached value or None
    """
    # Check circuit breaker
    if not self.circuit_breaker.can_execute():
        self.logger.debug(
            "redis_circuit_open",
            circuit_state=self.circuit_breaker.state.value,
            message="Circuit breaker OPEN, skipping Redis"
        )
        return None

    if self.client is None:
        await self._connect()

    if self.client is None:
        # Connection failed, record and return None
        self.circuit_breaker.record_failure()
        return None

    try:
        value = await self.client.get(key)
        if value:
            self.circuit_breaker.record_success()
            return json.loads(value)
        return None
    except Exception as e:
        self.circuit_breaker.record_failure()
        self.logger.warning(
            "redis_get_failed",
            error=str(e),
            circuit_state=self.circuit_breaker.state.value
        )
        return None
```

**Modify `set()` Method**:
```python
async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
    """
    Set value in Redis cache.

    Returns False if:
    - Circuit breaker is OPEN (fail fast)
    - Redis connection failed
    - Set operation failed

    Args:
        key: Cache key
        value: Value to cache
        ttl: Time to live in seconds

    Returns:
        True if set succeeded, False otherwise
    """
    # Check circuit breaker
    if not self.circuit_breaker.can_execute():
        self.logger.debug(
            "redis_circuit_open",
            circuit_state=self.circuit_breaker.state.value,
            message="Circuit breaker OPEN, skipping Redis"
        )
        return False

    if self.client is None:
        await self._connect()

    if self.client is None:
        self.circuit_breaker.record_failure()
        return False

    try:
        await self.client.setex(key, ttl, json.dumps(value))
        self.circuit_breaker.record_success()
        return True
    except Exception as e:
        self.circuit_breaker.record_failure()
        self.logger.warning(
            "redis_set_failed",
            error=str(e),
            circuit_state=self.circuit_breaker.state.value
        )
        return False
```

**Modify `delete()` Method**:
```python
async def delete(self, key: str) -> bool:
    """
    Delete key from Redis cache.

    Returns False if circuit breaker is OPEN or operation fails.

    Args:
        key: Cache key to delete

    Returns:
        True if delete succeeded, False otherwise
    """
    # Check circuit breaker
    if not self.circuit_breaker.can_execute():
        self.logger.debug(
            "redis_circuit_open",
            circuit_state=self.circuit_breaker.state.value,
            message="Circuit breaker OPEN, skipping Redis"
        )
        return False

    if self.client is None:
        await self._connect()

    if self.client is None:
        self.circuit_breaker.record_failure()
        return False

    try:
        await self.client.delete(key)
        self.circuit_breaker.record_success()
        return True
    except Exception as e:
        self.circuit_breaker.record_failure()
        self.logger.warning(
            "redis_delete_failed",
            error=str(e),
            circuit_state=self.circuit_breaker.state.value
        )
        return False
```

**Verification**:
```python
# Test circuit breaker is registered
from api.routes.health_routes import get_circuit_breaker_metrics
metrics = get_circuit_breaker_metrics()
assert "redis_cache" in metrics
```

---

#### Step 2.2: Update CascadeCache to Handle Circuit Breaker

**File**: `api/services/caches/cascade_cache.py`

**Current Code** finds this pattern in `get()` method:
```python
# Try L2 (Redis)
l2_value = await self.l2_cache.get(cache_key)
if l2_value is not None:
    # L2 hit - populate L1
    await self.l1_cache.set(cache_key, l2_value)
    # ...
```

**No changes needed** - CascadeCache already handles `None` returns gracefully. The circuit breaker integration in RedisCache will automatically cascade to L1+L3 when circuit is OPEN.

**Add Logging** (optional enhancement):
```python
async def get(self, key: str, context: str = "cache") -> Optional[Any]:
    """Get from cascade: L1 -> L2 -> L3."""
    cache_key = self._make_key(key, context)

    # Try L1 (in-memory)
    l1_value = await self.l1_cache.get(cache_key)
    if l1_value is not None:
        self.logger.debug("cache_hit", level="L1", key=cache_key[:50])
        return l1_value

    # Try L2 (Redis)
    l2_value = await self.l2_cache.get(cache_key)
    if l2_value is not None:
        # L2 hit - populate L1
        await self.l1_cache.set(cache_key, l2_value)
        self.logger.debug("cache_hit", level="L2", key=cache_key[:50])
        return l2_value

    # Check if L2 circuit is open
    if hasattr(self.l2_cache, 'circuit_breaker'):
        if not self.l2_cache.circuit_breaker.can_execute():
            self.logger.info(
                "cache_cascade_degraded",
                reason="redis_circuit_open",
                state=self.l2_cache.circuit_breaker.state.value,
                message="Operating on L1+L3 only (Redis circuit OPEN)"
            )

    # L1 and L2 miss
    self.logger.debug("cache_miss", levels="L1+L2", key=cache_key[:50])
    return None
```

---

#### Step 2.3: Create Integration Tests for Redis Circuit Breaker

**File**: `tests/integration/test_redis_circuit_breaker.py` (new file)

```python
"""
Integration tests for Redis circuit breaker.

Tests verify that Redis circuit breaker:
1. Opens after failure threshold
2. Closes after successful recovery
3. Enables graceful degradation to L1+L3 cache

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

import pytest
from unittest.mock import AsyncMock, patch
import asyncio

from api.services.caches.redis_cache import RedisCache
from api.services.caches.cascade_cache import CascadeCache
from api.services.caches.lru_cache import LRUCache
from api.utils.circuit_breaker import CircuitState


@pytest.mark.anyio
async def test_redis_circuit_opens_after_failures():
    """
    Test Redis circuit breaker opens after failure threshold.

    EPIC-12 Story 12.3: Circuit should open after N consecutive failures.
    """
    # Create RedisCache with unreachable Redis
    redis_cache = RedisCache(redis_url="redis://unreachable:6379/0")

    # Verify initial state
    assert redis_cache.circuit_breaker.state == CircuitState.CLOSED

    # Attempt operations to trigger failures
    for i in range(5):  # Default threshold is 5
        result = await redis_cache.get("test_key")
        assert result is None

    # Circuit should now be OPEN
    assert redis_cache.circuit_breaker.state == CircuitState.OPEN

    # Subsequent calls should fail fast (not attempt connection)
    result = await redis_cache.get("test_key")
    assert result is None

    # Verify no connection attempt was made (circuit blocked it)
    # This would be instant if circuit breaker worked
    import time
    start = time.time()
    await redis_cache.get("test_key")
    elapsed = time.time() - start
    assert elapsed < 0.1, "Should fail fast, not wait for connection timeout"


@pytest.mark.anyio
async def test_redis_circuit_closes_after_recovery():
    """
    Test Redis circuit breaker closes after successful recovery.

    EPIC-12 Story 12.3: Circuit should close after successful test in HALF_OPEN.
    """
    # Create RedisCache
    redis_cache = RedisCache(redis_url="redis://unreachable:6379/0")

    # Open circuit by recording failures
    for _ in range(5):
        redis_cache.circuit_breaker.record_failure()

    assert redis_cache.circuit_breaker.state == CircuitState.OPEN

    # Wait for recovery timeout (1 second for test)
    redis_cache.circuit_breaker.config.recovery_timeout = 1
    await asyncio.sleep(1.1)

    # Next can_execute should transition to HALF_OPEN
    can_exec = redis_cache.circuit_breaker.can_execute()
    assert can_exec is True
    assert redis_cache.circuit_breaker.state == CircuitState.HALF_OPEN

    # Record success to close circuit
    redis_cache.circuit_breaker.record_success()
    assert redis_cache.circuit_breaker.state == CircuitState.CLOSED


@pytest.mark.anyio
async def test_cascade_cache_degrades_gracefully_when_redis_open():
    """
    Test cascade cache operates on L1+L3 when Redis circuit is OPEN.

    EPIC-12 Story 12.3: Application should degrade gracefully when L2 fails.
    """
    # Create cascade cache with unreachable Redis
    l1_cache = LRUCache(max_size_mb=10)
    redis_cache = RedisCache(redis_url="redis://unreachable:6379/0")

    cascade = CascadeCache(
        l1_cache=l1_cache,
        l2_cache=redis_cache
    )

    # Open Redis circuit
    for _ in range(5):
        redis_cache.circuit_breaker.record_failure()

    assert redis_cache.circuit_breaker.state == CircuitState.OPEN

    # Set value in L1
    await cascade.set("test_key", {"data": "test"}, context="test")

    # Get should work from L1 (Redis circuit is open)
    result = await cascade.get("test_key", context="test")
    assert result == {"data": "test"}

    # Verify Redis was not called (circuit blocked it)
    # L1 cache should have served the request


@pytest.mark.anyio
async def test_redis_circuit_metrics_in_health_endpoint():
    """
    Test circuit breaker metrics appear in health endpoint.

    EPIC-12 Story 12.3: Health endpoint should expose circuit breaker state.
    """
    from api.routes.health_routes import get_circuit_breaker_metrics

    # Create RedisCache (registers itself)
    redis_cache = RedisCache(redis_url="redis://localhost:6379/0")

    # Get metrics
    metrics = get_circuit_breaker_metrics()

    assert "redis_cache" in metrics
    assert metrics["redis_cache"]["service"] == "redis_cache"
    assert metrics["redis_cache"]["state"] == "closed"
    assert "failure_count" in metrics["redis_cache"]
    assert "success_count" in metrics["redis_cache"]
    assert "config" in metrics["redis_cache"]


@pytest.mark.anyio
async def test_redis_circuit_set_operation():
    """
    Test Redis circuit breaker protects set operations.

    EPIC-12 Story 12.3: Circuit should protect all Redis operations.
    """
    redis_cache = RedisCache(redis_url="redis://unreachable:6379/0")

    # Verify initial state
    assert redis_cache.circuit_breaker.state == CircuitState.CLOSED

    # Attempt set operations to trigger failures
    for i in range(5):
        result = await redis_cache.set(f"key_{i}", {"value": i})
        assert result is False  # Should fail

    # Circuit should be OPEN
    assert redis_cache.circuit_breaker.state == CircuitState.OPEN

    # Subsequent set should fail fast
    result = await redis_cache.set("key_6", {"value": 6})
    assert result is False


@pytest.mark.anyio
async def test_redis_circuit_delete_operation():
    """
    Test Redis circuit breaker protects delete operations.

    EPIC-12 Story 12.3: Circuit should protect all Redis operations.
    """
    redis_cache = RedisCache(redis_url="redis://unreachable:6379/0")

    # Open circuit
    for _ in range(5):
        redis_cache.circuit_breaker.record_failure()

    assert redis_cache.circuit_breaker.state == CircuitState.OPEN

    # Delete should fail fast
    result = await redis_cache.delete("test_key")
    assert result is False
```

**Run Tests**:
```bash
# Run Redis circuit breaker integration tests
pytest tests/integration/test_redis_circuit_breaker.py -v

# Expected: 6+ tests passing
```

---

#### Phase 2 Completion Checklist

**Files Modified**:
- ✅ `api/services/caches/redis_cache.py` (+50 lines)
- ✅ `api/services/caches/cascade_cache.py` (+15 lines, optional logging)

**Files Created**:
- ✅ `tests/integration/test_redis_circuit_breaker.py` (~200 lines)

**Tests**:
```bash
# Run all Redis circuit tests
pytest tests/integration/test_redis_circuit_breaker.py -v

# Expected: 6+ tests passing
```

**Verification**:
```bash
# Start services
make up

# Test health endpoint
curl http://localhost:8001/health | jq '.circuit_breakers.redis_cache'

# Should show redis_cache circuit breaker metrics
```

---

### Phase 3: Embedding Circuit Breaker (1 pt)

**Goal**: Protect embedding service with circuit breaker to remove fail-forever behavior and enable automatic recovery.

**Estimated Time**: 1 hour

---

#### Step 3.1: Add Circuit Breaker to DualEmbeddingService

**File**: `api/services/dual_embedding_service.py`

**Current Code** (find `__init__` method):
```python
class DualEmbeddingService:
    """Dual embedding service using separate models for text and code."""

    def __init__(
        self,
        text_model_name: str,
        code_model_name: str,
        dimension: int = 768,
        use_mock: bool = False,
    ):
        self.text_model_name = text_model_name
        self.code_model_name = code_model_name
        self.dimension = dimension
        self.use_mock = use_mock

        self._text_model = None
        self._code_model = None
        self._text_load_attempted = False
        self._code_load_attempted = False

        self.logger = structlog.get_logger(__name__)
```

**Modify to Add Circuit Breaker**:
```python
# Add to imports
from api.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError
from api.config.circuit_breakers import EMBEDDING_CIRCUIT_CONFIG
from api.routes.health_routes import register_circuit_breaker

class DualEmbeddingService:
    """Dual embedding service with circuit breaker for fault tolerance."""

    def __init__(
        self,
        text_model_name: str,
        code_model_name: str,
        dimension: int = 768,
        use_mock: bool = False,
    ):
        self.text_model_name = text_model_name
        self.code_model_name = code_model_name
        self.dimension = dimension
        self.use_mock = use_mock

        self._text_model = None
        self._code_model = None
        # REMOVED: self._text_load_attempted = False  (fail-forever flag)
        # REMOVED: self._code_load_attempted = False  (fail-forever flag)

        self.logger = structlog.get_logger(__name__)

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=EMBEDDING_CIRCUIT_CONFIG.failure_threshold,
            recovery_timeout=EMBEDDING_CIRCUIT_CONFIG.recovery_timeout,
            half_open_max_calls=EMBEDDING_CIRCUIT_CONFIG.half_open_max_calls,
            name="embedding_service"
        )

        # Register for health monitoring
        register_circuit_breaker(self.circuit_breaker)
```

**Modify `_ensure_text_model_loaded()` Method**:
```python
async def _ensure_text_model_loaded(self) -> bool:
    """
    Ensure text embedding model is loaded.

    Returns:
        True if model loaded successfully, False otherwise
    """
    # Check circuit breaker
    if not self.circuit_breaker.can_execute():
        self.logger.warning(
            "embedding_circuit_open",
            model="text",
            circuit_state=self.circuit_breaker.state.value,
            message="Circuit breaker OPEN, model loading skipped"
        )
        return False

    if self.use_mock:
        self.logger.info("using_mock_embeddings", model="text")
        return True

    if self._text_model is not None:
        return True

    # REMOVED: fail-forever check
    # if self._text_load_attempted:
    #     return False

    try:
        self.logger.info(
            "loading_embedding_model",
            model="text",
            model_name=self.text_model_name
        )

        self._text_model = SentenceTransformer(self.text_model_name)

        self.circuit_breaker.record_success()
        self.logger.info(
            "embedding_model_loaded",
            model="text",
            model_name=self.text_model_name
        )
        return True

    except Exception as e:
        # REMOVED: self._text_load_attempted = True
        self.circuit_breaker.record_failure()

        self.logger.error(
            "embedding_model_load_failed",
            model="text",
            error=str(e),
            circuit_state=self.circuit_breaker.state.value,
            message="Model loading failed, circuit breaker will allow retry after timeout"
        )
        return False
```

**Modify `_ensure_code_model_loaded()` Method** (same pattern):
```python
async def _ensure_code_model_loaded(self) -> bool:
    """
    Ensure code embedding model is loaded.

    Returns:
        True if model loaded successfully, False otherwise
    """
    # Check circuit breaker
    if not self.circuit_breaker.can_execute():
        self.logger.warning(
            "embedding_circuit_open",
            model="code",
            circuit_state=self.circuit_breaker.state.value,
            message="Circuit breaker OPEN, model loading skipped"
        )
        return False

    if self.use_mock:
        self.logger.info("using_mock_embeddings", model="code")
        return True

    if self._code_model is not None:
        return True

    # REMOVED: fail-forever check

    try:
        self.logger.info(
            "loading_embedding_model",
            model="code",
            model_name=self.code_model_name
        )

        self._code_model = SentenceTransformer(self.code_model_name)

        self.circuit_breaker.record_success()
        self.logger.info(
            "embedding_model_loaded",
            model="code",
            model_name=self.code_model_name
        )
        return True

    except Exception as e:
        self.circuit_breaker.record_failure()

        self.logger.error(
            "embedding_model_load_failed",
            model="code",
            error=str(e),
            circuit_state=self.circuit_breaker.state.value,
            message="Model loading failed, circuit breaker will allow retry after timeout"
        )
        return False
```

**Verification**:
```python
# Test circuit breaker is registered
from api.routes.health_routes import get_circuit_breaker_metrics
metrics = get_circuit_breaker_metrics()
assert "embedding_service" in metrics
```

---

#### Step 3.2: Create Integration Tests for Embedding Circuit Breaker

**File**: `tests/integration/test_embedding_circuit_breaker.py` (new file)

```python
"""
Integration tests for embedding service circuit breaker.

Tests verify that embedding circuit breaker:
1. Removes fail-forever behavior
2. Allows automatic recovery after timeout
3. Protects against repeated model loading failures

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from api.services.dual_embedding_service import DualEmbeddingService
from api.utils.circuit_breaker import CircuitState


@pytest.mark.anyio
async def test_embedding_circuit_opens_after_model_load_failures():
    """
    Test embedding circuit breaker opens after model loading failures.

    EPIC-12 Story 12.3: Circuit should open after N consecutive failures.
    """
    service = DualEmbeddingService(
        text_model_name="invalid/model",
        code_model_name="invalid/model",
        use_mock=False
    )

    # Verify initial state
    assert service.circuit_breaker.state == CircuitState.CLOSED

    # Mock SentenceTransformer to raise exception
    with patch('api.services.dual_embedding_service.SentenceTransformer') as mock_st:
        mock_st.side_effect = RuntimeError("Model not found")

        # Attempt to load model multiple times (threshold is 3)
        for i in range(3):
            result = await service._ensure_text_model_loaded()
            assert result is False

        # Circuit should now be OPEN
        assert service.circuit_breaker.state == CircuitState.OPEN


@pytest.mark.anyio
async def test_embedding_circuit_allows_retry_after_recovery():
    """
    Test embedding circuit breaker allows retry after recovery timeout.

    EPIC-12 Story 12.3: Circuit should allow retry after timeout (not fail-forever).
    """
    service = DualEmbeddingService(
        text_model_name="test/model",
        code_model_name="test/model",
        use_mock=False
    )

    # Open circuit by recording failures
    for _ in range(3):
        service.circuit_breaker.record_failure()

    assert service.circuit_breaker.state == CircuitState.OPEN

    # Set short recovery timeout for test
    service.circuit_breaker.config.recovery_timeout = 1

    # Wait for recovery timeout
    await asyncio.sleep(1.1)

    # Circuit should allow execution again (HALF_OPEN)
    can_exec = service.circuit_breaker.can_execute()
    assert can_exec is True
    assert service.circuit_breaker.state == CircuitState.HALF_OPEN


@pytest.mark.anyio
async def test_embedding_no_fail_forever_behavior():
    """
    Test embedding service no longer has fail-forever behavior.

    EPIC-12 Story 12.3: Remove _text_load_attempted flag, use circuit breaker.
    """
    service = DualEmbeddingService(
        text_model_name="test/model",
        code_model_name="test/model",
        use_mock=False
    )

    # Verify fail-forever flags removed
    assert not hasattr(service, '_text_load_attempted')
    assert not hasattr(service, '_code_load_attempted')

    # Mock first attempt to fail, second to succeed
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Transient error")
        return MagicMock()  # Success on second call

    with patch('api.services.dual_embedding_service.SentenceTransformer', side_effect=side_effect):
        # First attempt fails
        result1 = await service._ensure_text_model_loaded()
        assert result1 is False

        # Reset circuit to allow retry
        service.circuit_breaker.reset()

        # Second attempt succeeds (proves no fail-forever)
        result2 = await service._ensure_text_model_loaded()
        assert result2 is True
        assert service._text_model is not None


@pytest.mark.anyio
async def test_embedding_circuit_metrics():
    """
    Test embedding circuit breaker metrics in health endpoint.

    EPIC-12 Story 12.3: Health endpoint should expose embedding circuit state.
    """
    from api.routes.health_routes import get_circuit_breaker_metrics

    service = DualEmbeddingService(
        text_model_name="test/model",
        code_model_name="test/model",
        use_mock=True
    )

    # Get metrics
    metrics = get_circuit_breaker_metrics()

    assert "embedding_service" in metrics
    assert metrics["embedding_service"]["service"] == "embedding_service"
    assert metrics["embedding_service"]["state"] == "closed"
    assert "config" in metrics["embedding_service"]
    assert metrics["embedding_service"]["config"]["failure_threshold"] == 3


@pytest.mark.anyio
async def test_embedding_circuit_protects_both_models():
    """
    Test circuit breaker protects both text and code model loading.

    EPIC-12 Story 12.3: Single circuit should protect both models.
    """
    service = DualEmbeddingService(
        text_model_name="invalid/model",
        code_model_name="invalid/model",
        use_mock=False
    )

    with patch('api.services.dual_embedding_service.SentenceTransformer') as mock_st:
        mock_st.side_effect = RuntimeError("Model not found")

        # Fail text model loading twice
        await service._ensure_text_model_loaded()
        await service._ensure_text_model_loaded()

        # Fail code model loading once (should open circuit at 3 total)
        await service._ensure_code_model_loaded()

        # Circuit should be OPEN
        assert service.circuit_breaker.state == CircuitState.OPEN

        # Both methods should fail fast now
        result_text = await service._ensure_text_model_loaded()
        result_code = await service._ensure_code_model_loaded()

        assert result_text is False
        assert result_code is False
```

**Run Tests**:
```bash
# Run embedding circuit breaker integration tests
pytest tests/integration/test_embedding_circuit_breaker.py -v

# Expected: 5+ tests passing
```

---

#### Step 3.3: Update CodeIndexingService Error Handling

**File**: `api/services/code_indexing_service.py`

**Current Code** (find error handling for embedding failures):
```python
# Typically in index_file or similar method
try:
    embeddings = await self.embedding_service.generate_embeddings(...)
except Exception as e:
    self.logger.error("embedding_failed", error=str(e))
    # ...
```

**Add Circuit Breaker Context**:
```python
try:
    embeddings = await self.embedding_service.generate_embeddings(...)
except Exception as e:
    # Check if failure was due to circuit breaker
    circuit_state = "unknown"
    if hasattr(self.embedding_service, 'circuit_breaker'):
        circuit_state = self.embedding_service.circuit_breaker.state.value

    self.logger.error(
        "embedding_failed",
        error=str(e),
        circuit_state=circuit_state,
        message="Embedding generation failed" + (
            " (circuit breaker OPEN)" if circuit_state == "open" else ""
        )
    )
    # ... existing error handling ...
```

**Verification**:
```bash
# Run indexing with circuit breaker
make api-test-file file=tests/integration/test_code_indexing.py
```

---

#### Phase 3 Completion Checklist

**Files Modified**:
- ✅ `api/services/dual_embedding_service.py` (+60 lines, removed fail-forever flags)
- ✅ `api/services/code_indexing_service.py` (+10 lines, optional logging)

**Files Created**:
- ✅ `tests/integration/test_embedding_circuit_breaker.py` (~150 lines)

**Tests**:
```bash
# Run all embedding circuit tests
pytest tests/integration/test_embedding_circuit_breaker.py -v

# Expected: 5+ tests passing
```

**Verification**:
```bash
# Test health endpoint
curl http://localhost:8001/health | jq '.circuit_breakers'

# Should show both redis_cache and embedding_service
```

---

## Testing Strategy

### Unit Tests (Phase 1)

**File**: `tests/unit/utils/test_circuit_breaker.py`

**Coverage**:
- ✅ State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- ✅ Failure threshold enforcement
- ✅ Recovery timeout behavior
- ✅ Half-open max calls limit
- ✅ Decorator functionality
- ✅ Metrics collection
- ✅ Reset functionality
- ✅ Edge cases

**Run**:
```bash
pytest tests/unit/utils/test_circuit_breaker.py -v --cov=api/utils/circuit_breaker
```

**Expected**: 18+ tests passing, 100% coverage

---

### Integration Tests (Phase 2 & 3)

**Redis Circuit Breaker** (`tests/integration/test_redis_circuit_breaker.py`):
- ✅ Circuit opens after Redis connection failures
- ✅ Circuit closes after successful recovery
- ✅ Cascade cache degrades gracefully when Redis circuit is OPEN
- ✅ Health endpoint exposes Redis circuit metrics
- ✅ All Redis operations (get/set/delete) protected

**Embedding Circuit Breaker** (`tests/integration/test_embedding_circuit_breaker.py`):
- ✅ Circuit opens after model loading failures
- ✅ Circuit allows retry after recovery timeout
- ✅ No fail-forever behavior (flags removed)
- ✅ Health endpoint exposes embedding circuit metrics
- ✅ Both text and code models protected by single circuit

**Run All Integration Tests**:
```bash
pytest tests/integration/test_redis_circuit_breaker.py \
       tests/integration/test_embedding_circuit_breaker.py \
       -v
```

**Expected**: 11+ tests passing

---

### Manual Testing

**Test 1: Redis Circuit Breaker**
```bash
# Stop Redis
docker stop mnemo-redis

# Make requests that use cache
curl "http://localhost:8001/v1/code/search/hybrid?query=function&limit=5"

# Check health endpoint
curl http://localhost:8001/health | jq '.circuit_breakers.redis_cache'

# Should show circuit opening after 5 failures

# Restart Redis
docker start mnemo-redis

# Wait 30 seconds (recovery timeout)
sleep 30

# Make request again
curl "http://localhost:8001/v1/code/search/hybrid?query=function&limit=5"

# Check health endpoint
curl http://localhost:8001/health | jq '.circuit_breakers.redis_cache'

# Should show circuit HALF_OPEN, then CLOSED after success
```

**Test 2: Embedding Circuit Breaker**
```bash
# Restart API with invalid embedding models
# (Edit docker-compose.yml temporarily)
EMBEDDING_MODEL: "invalid/model"
CODE_EMBEDDING_MODEL: "invalid/model"

make restart

# Attempt to index code
curl -X POST "http://localhost:8001/v1/code/index" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "test.py", "content": "def test(): pass"}'

# Check circuit state
curl http://localhost:8001/health | jq '.circuit_breakers.embedding_service'

# Should show circuit opening after 3 failures

# Restore correct models
# Edit docker-compose.yml back
make restart

# Wait 60 seconds (recovery timeout)
sleep 60

# Try indexing again
curl -X POST "http://localhost:8001/v1/code/index" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "test.py", "content": "def test(): pass"}'

# Should succeed (proves no fail-forever)
```

**Test 3: Health Endpoint**
```bash
# Check all circuit breakers
curl http://localhost:8001/health | jq

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-10-21T...",
  "database": "healthy",
  "circuit_breakers": {
    "redis_cache": {
      "service": "redis_cache",
      "state": "closed",
      "failure_count": 0,
      "success_count": 42,
      "last_failure_time": null,
      "state_changed_at": "2025-10-21T...",
      "config": {
        "failure_threshold": 5,
        "recovery_timeout": 30,
        "half_open_max_calls": 1
      }
    },
    "embedding_service": {
      "service": "embedding_service",
      "state": "closed",
      "failure_count": 0,
      "success_count": 15,
      ...
    }
  },
  "critical_circuits_open": []
}
```

---

## Verification Checklist

### Phase 1: Foundation
- [ ] ✅ `api/utils/circuit_breaker.py` created (~400 lines)
- [ ] ✅ `api/config/circuit_breakers.py` created (~50 lines)
- [ ] ✅ `tests/unit/utils/test_circuit_breaker.py` created (~350 lines)
- [ ] ✅ `api/routes/health_routes.py` modified (+40 lines)
- [ ] ✅ Unit tests passing (18+ tests, 100% coverage)
- [ ] ✅ Health endpoint exposes circuit breaker metrics
- [ ] ✅ Circuit breaker registry works

### Phase 2: Redis Circuit Breaker
- [ ] ✅ `api/services/caches/redis_cache.py` modified (+50 lines)
- [ ] ✅ Circuit breaker registered for Redis
- [ ] ✅ All Redis operations (get/set/delete) protected
- [ ] ✅ `tests/integration/test_redis_circuit_breaker.py` created (~200 lines)
- [ ] ✅ Integration tests passing (6+ tests)
- [ ] ✅ Cascade cache degrades gracefully when circuit is OPEN
- [ ] ✅ Manual test: Stop Redis, verify circuit opens, restart Redis, verify recovery

### Phase 3: Embedding Circuit Breaker
- [ ] ✅ `api/services/dual_embedding_service.py` modified (+60 lines)
- [ ] ✅ Fail-forever flags removed (`_text_load_attempted`, `_code_load_attempted`)
- [ ] ✅ Circuit breaker registered for embedding service
- [ ] ✅ Both text and code model loading protected
- [ ] ✅ `tests/integration/test_embedding_circuit_breaker.py` created (~150 lines)
- [ ] ✅ Integration tests passing (5+ tests)
- [ ] ✅ Manual test: Invalid models trigger circuit, recovery works after timeout

### Overall
- [ ] ✅ All unit tests passing
- [ ] ✅ All integration tests passing
- [ ] ✅ Health endpoint shows all circuit breakers
- [ ] ✅ Manual tests verify behavior under failure conditions
- [ ] ✅ Documentation updated (EPIC-12_README.md)
- [ ] ✅ Completion report created

---

## Rollback Plan

**If issues arise during implementation:**

### Phase 1 Rollback
```bash
# Remove circuit breaker files
rm api/utils/circuit_breaker.py
rm api/config/circuit_breakers.py
rm tests/unit/utils/test_circuit_breaker.py

# Revert health routes
git checkout api/routes/health_routes.py

# Run tests to verify
make api-test
```

### Phase 2 Rollback
```bash
# Revert Redis cache changes
git checkout api/services/caches/redis_cache.py
git checkout api/services/caches/cascade_cache.py

# Remove integration tests
rm tests/integration/test_redis_circuit_breaker.py

# Restart services
make restart

# Verify functionality
curl http://localhost:8001/health
```

### Phase 3 Rollback
```bash
# Revert embedding service changes
git checkout api/services/dual_embedding_service.py
git checkout api/services/code_indexing_service.py

# Remove integration tests
rm tests/integration/test_embedding_circuit_breaker.py

# Restart services
make restart

# Verify functionality
curl -X POST "http://localhost:8001/v1/code/index" ...
```

**Complete Rollback** (all phases):
```bash
# Revert all changes
git checkout api/
git checkout tests/

# Remove new files
rm api/utils/circuit_breaker.py
rm api/config/circuit_breakers.py
rm tests/unit/utils/test_circuit_breaker.py
rm tests/integration/test_redis_circuit_breaker.py
rm tests/integration/test_embedding_circuit_breaker.py

# Restart services
make restart

# Verify baseline functionality
make api-test
```

---

## Success Metrics

**Code Metrics**:
- ✅ New files created: 5 (circuit_breaker.py, config, 3 test files)
- ✅ Files modified: 4 (health_routes, redis_cache, cascade_cache, dual_embedding)
- ✅ Total lines added: ~1,200 lines
- ✅ Test coverage: 100% (circuit breaker utilities)

**Functional Metrics**:
- ✅ Circuit breaker opens after N failures (N=3 for embedding, N=5 for Redis)
- ✅ Circuit breaker closes after successful recovery
- ✅ Fast fail: <1ms when circuit is OPEN (vs 5000ms connection timeout)
- ✅ Automatic recovery: Circuit attempts recovery after timeout
- ✅ Log noise reduction: 99%+ reduction during outages (only state changes logged)

**Acceptance Criteria**:
- ✅ Circuit breaker implemented with 3 states (CLOSED/OPEN/HALF_OPEN)
- ✅ Configurable failure threshold via environment variables
- ✅ Health check endpoints expose circuit breaker state
- ✅ Tests verify failure threshold, recovery behavior, graceful degradation
- ✅ Redis operations protected
- ✅ Embedding service protected
- ✅ Fail-forever behavior removed

---

## Configuration Reference

**Environment Variables**:

```bash
# Redis Circuit Breaker
REDIS_CIRCUIT_FAILURE_THRESHOLD=5       # Default: 5 failures
REDIS_CIRCUIT_RECOVERY_TIMEOUT=30       # Default: 30 seconds
REDIS_CIRCUIT_HALF_OPEN_CALLS=1        # Default: 1 call

# Embedding Circuit Breaker
EMBEDDING_CIRCUIT_FAILURE_THRESHOLD=3   # Default: 3 failures
EMBEDDING_CIRCUIT_RECOVERY_TIMEOUT=60   # Default: 60 seconds
EMBEDDING_CIRCUIT_HALF_OPEN_CALLS=1    # Default: 1 call

# Database Circuit Breaker (future)
DATABASE_CIRCUIT_FAILURE_THRESHOLD=3
DATABASE_CIRCUIT_RECOVERY_TIMEOUT=10
DATABASE_CIRCUIT_HALF_OPEN_CALLS=1
```

**Usage in Code**:

```python
# Create circuit breaker
from api.utils.circuit_breaker import CircuitBreaker
from api.config.circuit_breakers import REDIS_CIRCUIT_CONFIG

breaker = CircuitBreaker(
    failure_threshold=REDIS_CIRCUIT_CONFIG.failure_threshold,
    recovery_timeout=REDIS_CIRCUIT_CONFIG.recovery_timeout,
    name="my_service"
)

# Option 1: Manual protection
if breaker.can_execute():
    try:
        result = await external_call()
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        raise
else:
    raise CircuitBreakerError(breaker.name, breaker.state)

# Option 2: Decorator protection
@breaker.protect
async def call_external():
    return await external_call()
```

---

## Next Steps After Implementation

1. **Monitor Circuit Breaker Metrics**
   ```bash
   # Check health endpoint regularly
   watch -n 5 'curl -s http://localhost:8001/health | jq .circuit_breakers'
   ```

2. **Tune Thresholds** based on production data
   - Adjust `failure_threshold` if too sensitive/insensitive
   - Adjust `recovery_timeout` based on actual service recovery times
   - Monitor false positives (circuit opening unnecessarily)

3. **Story 12.4: Error Tracking** (next story)
   - Integrate circuit breaker state changes with error tracking
   - Alert on critical circuits opening
   - Dashboard for circuit breaker metrics

4. **Story 12.5: Retry Logic** (future story)
   - Combine circuit breaker with exponential backoff
   - Retry transient failures before opening circuit
   - Jitter implementation to prevent thundering herd

---

## Related Documentation

- **Analysis**: `EPIC-12_STORY_12.3_ANALYSIS.md` (this document's companion)
- **Epic Overview**: `EPIC-12_README.md`
- **Story 12.1**: `EPIC-12_STORY_12.1_COMPLETION_REPORT.md` (Timeouts)
- **Story 12.2**: `EPIC-12_STORY_12.2_COMPLETION_REPORT.md` (Transactions)
- **Architecture**: `docs/arch/circuit_breakers.md` (to be created)

---

**Created**: 2025-10-21
**Author**: Claude Code
**Epic**: EPIC-12 Story 12.3 (5 pts)
**Status**: 📋 READY FOR IMPLEMENTATION

🤖 Generated with [Claude Code](https://claude.com/claude-code)
