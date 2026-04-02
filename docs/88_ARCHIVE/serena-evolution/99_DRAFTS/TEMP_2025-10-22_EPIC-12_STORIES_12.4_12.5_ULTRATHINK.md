# EPIC-12 Stories 12.4 & 12.5: Deep Analysis and Implementation Plan

**Date**: 2025-10-22
**Status**: ULTRATHINK Analysis
**Scope**: Complete EPIC-12 (Stories 12.4 and 12.5, 10 pts remaining)
**Current EPIC-12 Status**: 13/23 pts complete (57%)

---

## Executive Summary

**Objective**: Complete EPIC-12 Production Readiness with comprehensive error tracking/alerting (12.4) and retry logic with backoff (12.5).

**Current State**:
- ✅ Story 12.1: Timeouts (5 pts) - Complete
- ✅ Story 12.2: Transactions (3 pts) - Complete (missing completion report)
- ✅ Story 12.3: Circuit Breakers (5 pts) - Complete
- ⏳ Story 12.4: Error Tracking & Alerting (5 pts) - TODO
- ⏳ Story 12.5: Retry Logic with Backoff (5 pts) - TODO

**Goal**: 23/23 pts complete (100%), production-ready error handling and resilience.

---

## Part 1: Story 12.4 - Error Tracking & Alerting (5 pts)

### 1.1 Current State Analysis

**Existing Error Handling**:
```bash
# Let me search for current error handling patterns
```

**Current Logging Infrastructure**:
- Using structlog (mentioned in CLAUDE.md: `Stack: ... structlog`)
- Structured logging available
- No centralized error aggregation
- No alerting mechanism
- No error dashboards

**Gap Analysis**:
| Capability | Current | Required | Gap |
|------------|---------|----------|-----|
| Structured logging | ✅ structlog | ✅ Enhanced | Minor |
| Error categorization | ❌ None | ✅ Severity levels | Major |
| Error aggregation | ❌ None | ✅ Dashboard | Major |
| Alerting | ❌ None | ✅ Thresholds | Major |
| Error tracking service | ❌ None | ✅ Sentry OR enhanced logging | Major |

### 1.2 Options Analysis

#### Option A: Sentry Integration
**Pros**:
- Industry-standard error tracking
- Built-in dashboards and alerting
- Automatic error grouping
- Performance monitoring included
- Stack trace analysis
- Release tracking
- User impact tracking

**Cons**:
- External dependency (SaaS or self-hosted)
- Cost implications (if using Sentry.io)
- Additional infrastructure if self-hosted
- Requires API key management
- Network dependency for error reporting

**Complexity**: Medium (integration straightforward, infrastructure decisions required)
**Cost**: $0 (self-hosted) or $26+/month (SaaS)
**Timeline**: 4-6 hours

#### Option B: Enhanced Structured Logging + Local Aggregation
**Pros**:
- No external dependencies
- Full control over data
- Zero cost
- Already using structlog
- Can store in PostgreSQL
- Leverage existing monitoring UI

**Cons**:
- Build dashboards ourselves
- Build alerting ourselves
- No out-of-the-box grouping
- More development time
- Maintenance burden

**Complexity**: Medium-High (more code to write)
**Cost**: $0
**Timeline**: 6-8 hours

#### Option C: Hybrid (Structured Logging + Simple Alerting)
**Pros**:
- Minimal external dependencies
- Structured logs to PostgreSQL
- Simple threshold-based alerting
- Can add Sentry later if needed
- Incremental approach

**Cons**:
- Limited initial capabilities
- May need replacement later

**Complexity**: Low-Medium
**Cost**: $0
**Timeline**: 4-5 hours

### 1.3 Recommendation: Option C (Hybrid)

**Rationale**:
1. **MnemoLite Context**: Self-hosted, dev tool, not production SaaS
2. **Cost**: $0 budget likely preferred
3. **Principles**: EXTEND>REBUILD - we have structlog, extend it
4. **Incremental**: Can add Sentry later if needed
5. **Timeline**: Fastest to production (4-5h vs 6-8h)

**Architecture**:
```
Error Occurs
    ↓
structlog (enhanced with severity, category)
    ↓
PostgreSQL errors table (aggregation)
    ↓
Monitoring UI (error dashboard)
    ↓
Alert Service (threshold-based)
    ↓
Notification (log, email stub, webhook)
```

### 1.4 Implementation Plan: Story 12.4

#### Step 1: Error Schema Design (30 min)
```sql
-- db/migrations/v5_to_v6_error_tracking.sql

CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity TEXT NOT NULL CHECK (severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    category TEXT NOT NULL, -- 'database', 'embedding', 'api', 'circuit_breaker', etc.
    service TEXT NOT NULL, -- Service name
    error_type TEXT NOT NULL, -- Exception class name
    message TEXT NOT NULL,
    stack_trace TEXT,
    context JSONB, -- Request ID, user, additional data
    count INTEGER DEFAULT 1, -- For aggregation
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for querying
CREATE INDEX idx_error_logs_timestamp ON error_logs(timestamp DESC);
CREATE INDEX idx_error_logs_severity ON error_logs(severity);
CREATE INDEX idx_error_logs_category ON error_logs(category);
CREATE INDEX idx_error_logs_service ON error_logs(service);
CREATE INDEX idx_error_logs_error_type ON error_logs(error_type);

-- View for error aggregation
CREATE OR REPLACE VIEW error_summary AS
SELECT
    category,
    service,
    error_type,
    severity,
    COUNT(*) as total_count,
    MAX(timestamp) as last_occurrence,
    MIN(timestamp) as first_occurrence
FROM error_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY category, service, error_type, severity
ORDER BY total_count DESC;

-- View for critical errors (last hour)
CREATE OR REPLACE VIEW critical_errors_recent AS
SELECT *
FROM error_logs
WHERE severity = 'CRITICAL'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
```

#### Step 2: Enhanced Logging Service (1 hour)
```python
# api/services/error_tracking_service.py

import structlog
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import traceback
import asyncio
from enum import Enum

from api.db.repositories.error_repository import ErrorRepository

logger = structlog.get_logger(__name__)

class ErrorSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorCategory(str, Enum):
    DATABASE = "database"
    EMBEDDING = "embedding"
    API = "api"
    CIRCUIT_BREAKER = "circuit_breaker"
    CACHE = "cache"
    GRAPH = "graph"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

class ErrorTrackingService:
    """
    Centralized error tracking and logging service.

    Responsibilities:
    - Log errors with structured metadata
    - Store errors in PostgreSQL for aggregation
    - Provide error analytics
    - Trigger alerts based on thresholds
    """

    def __init__(self, error_repository: ErrorRepository):
        self.error_repository = error_repository
        self.logger = structlog.get_logger(__name__)

    async def log_error(
        self,
        error: Exception,
        severity: ErrorSeverity,
        category: ErrorCategory,
        service: str,
        context: Optional[Dict[str, Any]] = None,
        include_traceback: bool = True
    ) -> None:
        """
        Log an error with full context and store in database.

        Args:
            error: The exception that occurred
            severity: Error severity level
            category: Error category for grouping
            service: Service name where error occurred
            context: Additional context (request_id, user, etc.)
            include_traceback: Whether to include full stack trace
        """
        error_type = type(error).__name__
        message = str(error)
        stack_trace = traceback.format_exc() if include_traceback else None

        # Structured logging
        self.logger.bind(
            severity=severity.value,
            category=category.value,
            service=service,
            error_type=error_type,
            context=context or {}
        ).error(message, exc_info=error)

        # Store in database (fire-and-forget to avoid blocking)
        asyncio.create_task(
            self._store_error(
                severity=severity.value,
                category=category.value,
                service=service,
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                context=context or {}
            )
        )

    async def _store_error(
        self,
        severity: str,
        category: str,
        service: str,
        error_type: str,
        message: str,
        stack_trace: Optional[str],
        context: Dict[str, Any]
    ) -> None:
        """Store error in database (internal, fire-and-forget)."""
        try:
            await self.error_repository.create_error(
                severity=severity,
                category=category,
                service=service,
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                context=context
            )
        except Exception as e:
            # Don't let error tracking fail the request
            self.logger.warning(f"Failed to store error in database: {e}")

    async def get_error_summary(self, hours: int = 24) -> list[Dict[str, Any]]:
        """Get error summary for last N hours."""
        return await self.error_repository.get_error_summary(hours=hours)

    async def get_critical_errors(self, hours: int = 1) -> list[Dict[str, Any]]:
        """Get critical errors from last N hours."""
        return await self.error_repository.get_critical_errors(hours=hours)

    async def check_alert_thresholds(self) -> list[str]:
        """
        Check if error thresholds exceeded, return alert messages.

        Thresholds:
        - CRITICAL: Any critical error triggers alert
        - ERROR: >10 errors in 1 hour triggers alert
        - WARNING: >50 warnings in 1 hour triggers alert
        """
        alerts = []

        # Check critical errors
        critical = await self.get_critical_errors(hours=1)
        if critical:
            alerts.append(f"🚨 CRITICAL: {len(critical)} critical errors in last hour")

        # Check error threshold
        summary = await self.get_error_summary(hours=1)
        error_count = sum(
            s['total_count'] for s in summary
            if s['severity'] == 'ERROR'
        )
        if error_count > 10:
            alerts.append(f"⚠️  ERROR: {error_count} errors in last hour (threshold: 10)")

        # Check warning threshold
        warning_count = sum(
            s['total_count'] for s in summary
            if s['severity'] == 'WARNING'
        )
        if warning_count > 50:
            alerts.append(f"⚠️  WARNING: {warning_count} warnings in last hour (threshold: 50)")

        return alerts
```

#### Step 3: Error Repository (45 min)
```python
# api/db/repositories/error_repository.py

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

class ErrorRepository:
    """Repository for error tracking operations."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def create_error(
        self,
        severity: str,
        category: str,
        service: str,
        error_type: str,
        message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create error log entry."""
        query = text("""
            INSERT INTO error_logs (
                severity, category, service, error_type,
                message, stack_trace, context
            )
            VALUES (
                :severity, :category, :service, :error_type,
                :message, :stack_trace, :context
            )
        """)

        async with self.engine.begin() as conn:
            await conn.execute(
                query,
                {
                    "severity": severity,
                    "category": category,
                    "service": service,
                    "error_type": error_type,
                    "message": message,
                    "stack_trace": stack_trace,
                    "context": context or {}
                }
            )

    async def get_error_summary(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get error summary for last N hours."""
        query = text("""
            SELECT
                category,
                service,
                error_type,
                severity,
                COUNT(*) as total_count,
                MAX(timestamp) as last_occurrence,
                MIN(timestamp) as first_occurrence
            FROM error_logs
            WHERE timestamp > NOW() - INTERVAL ':hours hours'
            GROUP BY category, service, error_type, severity
            ORDER BY total_count DESC
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"hours": hours})
            return [dict(row._mapping) for row in result]

    async def get_critical_errors(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get critical errors from last N hours."""
        query = text("""
            SELECT *
            FROM error_logs
            WHERE severity = 'CRITICAL'
              AND timestamp > NOW() - INTERVAL ':hours hours'
            ORDER BY timestamp DESC
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"hours": hours})
            return [dict(row._mapping) for row in result]
```

#### Step 4: Integration into Existing Services (1.5 hours)
```python
# Example: api/services/embedding_service.py

class EmbeddingService:
    def __init__(
        self,
        cache_service: CacheService,
        error_tracking_service: ErrorTrackingService  # NEW
    ):
        self.cache_service = cache_service
        self.error_tracking = error_tracking_service  # NEW
        ...

    async def generate_embeddings(
        self,
        texts: list[str],
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> list[list[float]]:
        try:
            # Existing implementation
            ...
        except TimeoutError as e:
            await self.error_tracking.log_error(
                error=e,
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.TIMEOUT,
                service="EmbeddingService",
                context={"domain": domain.value, "text_count": len(texts)}
            )
            raise
        except Exception as e:
            await self.error_tracking.log_error(
                error=e,
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.EMBEDDING,
                service="EmbeddingService",
                context={"domain": domain.value, "text_count": len(texts)}
            )
            raise
```

**Services to integrate** (grep for try/except blocks):
- EmbeddingService
- SearchService
- CodeIndexingService
- GraphConstructionService
- HybridCodeSearchService
- All repositories (database errors)

#### Step 5: Monitoring UI Routes (1 hour)
```python
# api/routes/ui_routes.py (add to existing routes)

@router.get("/monitoring/errors")
async def errors_dashboard(
    request: Request,
    error_tracking_service: ErrorTrackingService = Depends(get_error_tracking_service)
):
    """Error tracking dashboard."""
    summary = await error_tracking_service.get_error_summary(hours=24)
    critical = await error_tracking_service.get_critical_errors(hours=24)
    alerts = await error_tracking_service.check_alert_thresholds()

    return templates.TemplateResponse(
        "monitoring_errors.html",
        {
            "request": request,
            "error_summary": summary,
            "critical_errors": critical,
            "alerts": alerts,
            "active_page": "monitoring"
        }
    )
```

#### Step 6: Monitoring UI Template (30 min)
```html
<!-- templates/monitoring_errors.html -->

{% extends "base.html" %}

{% block title %}Error Tracking - MnemoLite{% endblock %}

{% block content %}
<div class="container">
    <h1>Error Tracking Dashboard</h1>

    {% if alerts %}
    <div class="alerts">
        {% for alert in alerts %}
        <div class="alert alert-{{ 'critical' if 'CRITICAL' in alert else 'warning' }}">
            {{ alert }}
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <section class="error-summary">
        <h2>Error Summary (Last 24 Hours)</h2>
        <table class="error-table">
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Service</th>
                    <th>Error Type</th>
                    <th>Severity</th>
                    <th>Count</th>
                    <th>Last Occurrence</th>
                </tr>
            </thead>
            <tbody>
                {% for error in error_summary %}
                <tr class="severity-{{ error.severity|lower }}">
                    <td>{{ error.category }}</td>
                    <td>{{ error.service }}</td>
                    <td>{{ error.error_type }}</td>
                    <td>{{ error.severity }}</td>
                    <td>{{ error.total_count }}</td>
                    <td>{{ error.last_occurrence|timeago }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="critical-errors">
        <h2>Critical Errors (Last 24 Hours)</h2>
        {% if critical_errors %}
        <div class="error-list">
            {% for error in critical_errors %}
            <div class="error-card critical">
                <div class="error-header">
                    <span class="error-type">{{ error.error_type }}</span>
                    <span class="error-time">{{ error.timestamp|timeago }}</span>
                </div>
                <div class="error-message">{{ error.message }}</div>
                <div class="error-meta">
                    <span>Service: {{ error.service }}</span>
                    <span>Category: {{ error.category }}</span>
                </div>
                {% if error.stack_trace %}
                <details class="stack-trace">
                    <summary>Stack Trace</summary>
                    <pre>{{ error.stack_trace }}</pre>
                </details>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p class="no-errors">✅ No critical errors in the last 24 hours</p>
        {% endif %}
    </section>
</div>
{% endblock %}
```

#### Step 7: Alert Service (Background Task) (45 min)
```python
# api/services/alert_service.py

import asyncio
from datetime import datetime
from typing import List

from api.services.error_tracking_service import ErrorTrackingService

class AlertService:
    """
    Background service for checking error thresholds and triggering alerts.

    Runs every 5 minutes, checks thresholds, logs alerts.
    Future: Email, Slack, webhook notifications.
    """

    def __init__(self, error_tracking_service: ErrorTrackingService):
        self.error_tracking = error_tracking_service
        self.logger = structlog.get_logger(__name__)
        self._task = None

    async def start(self):
        """Start alert monitoring task."""
        self._task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Alert service started")

    async def stop(self):
        """Stop alert monitoring task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("Alert service stopped")

    async def _monitor_loop(self):
        """Monitor errors and trigger alerts every 5 minutes."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes

                alerts = await self.error_tracking.check_alert_thresholds()

                if alerts:
                    for alert in alerts:
                        self.logger.warning(f"ALERT: {alert}")
                        # Future: Send email, Slack, webhook
                        await self._send_alert(alert)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in alert monitoring loop: {e}")

    async def _send_alert(self, message: str):
        """
        Send alert notification.
        Currently: Log only
        Future: Email, Slack, webhook
        """
        # Placeholder for future notification integrations
        pass
```

#### Step 8: Integration into main.py lifespan (15 min)
```python
# api/main.py

from contextlib import asynccontextmanager
from api.services.alert_service import AlertService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Existing startup
    ...

    # NEW: Start alert service
    error_tracking_service = ErrorTrackingService(error_repository)
    alert_service = AlertService(error_tracking_service)
    await alert_service.start()
    app.state.alert_service = alert_service

    yield

    # NEW: Stop alert service
    await alert_service.stop()

    # Existing shutdown
    ...
```

#### Step 9: Tests (1 hour)
```python
# tests/test_error_tracking_service.py

import pytest
from api.services.error_tracking_service import (
    ErrorTrackingService,
    ErrorSeverity,
    ErrorCategory
)

@pytest.mark.anyio
async def test_log_error(error_tracking_service):
    """Test error logging."""
    try:
        raise ValueError("Test error")
    except ValueError as e:
        await error_tracking_service.log_error(
            error=e,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.API,
            service="TestService",
            context={"request_id": "123"}
        )

    # Verify stored in database
    summary = await error_tracking_service.get_error_summary(hours=1)
    assert len(summary) > 0
    assert summary[0]['error_type'] == 'ValueError'

@pytest.mark.anyio
async def test_alert_thresholds_critical(error_tracking_service):
    """Test critical error triggers alert."""
    # Create critical error
    try:
        raise RuntimeError("Critical error")
    except RuntimeError as e:
        await error_tracking_service.log_error(
            error=e,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.DATABASE,
            service="TestService"
        )

    alerts = await error_tracking_service.check_alert_thresholds()
    assert len(alerts) > 0
    assert "CRITICAL" in alerts[0]

@pytest.mark.anyio
async def test_alert_thresholds_error_count(error_tracking_service):
    """Test >10 errors triggers alert."""
    # Create 11 errors
    for i in range(11):
        try:
            raise ValueError(f"Error {i}")
        except ValueError as e:
            await error_tracking_service.log_error(
                error=e,
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.API,
                service="TestService"
            )

    alerts = await error_tracking_service.check_alert_thresholds()
    assert any("ERROR" in alert for alert in alerts)
```

### 1.5 Story 12.4 Success Criteria

✅ **Acceptance Criteria**:
1. All errors logged with severity, category, service
2. Errors stored in PostgreSQL for aggregation
3. Error dashboard displays summary and critical errors
4. Alert thresholds checked every 5 minutes
5. Alerts logged (email/Slack integration = future enhancement)
6. Tests cover error logging, aggregation, alerting

**Timeline**: 4-5 hours total

---

## Part 2: Story 12.5 - Retry Logic with Backoff (5 pts)

### 2.1 Current State Analysis

**Existing Retry Patterns**:
- Circuit breakers (EPIC-12 Story 12.3) handle open/closed state
- Timeouts (EPIC-12 Story 12.1) prevent indefinite waiting
- **No retry logic** for transient failures

**Operations Requiring Retry**:
1. **Redis cache operations** (network transient failures)
2. **PostgreSQL operations** (connection pool exhaustion, deadlocks)
3. **Embedding service** (model loading, temporary unavailability)
4. **External APIs** (future: if we add any)

**Gap Analysis**:
| Capability | Current | Required | Gap |
|------------|---------|----------|-----|
| Retry decorator | ❌ None | ✅ Yes | Major |
| Exponential backoff | ❌ None | ✅ Yes | Major |
| Jitter | ❌ None | ✅ Yes | Major |
| Configurable limits | ❌ None | ✅ Per operation | Major |
| Retryable error detection | ❌ None | ✅ Classification | Major |

### 2.2 Design: Retry Decorator with Exponential Backoff

**Algorithm**:
```
attempt = 0
max_attempts = 3
base_delay = 1.0  # seconds
max_delay = 30.0  # seconds

while attempt < max_attempts:
    try:
        return operation()
    except RetryableError as e:
        attempt += 1
        if attempt >= max_attempts:
            raise

        # Exponential backoff: delay = base * (2 ^ attempt)
        delay = min(base_delay * (2 ** attempt), max_delay)

        # Add jitter: random ±25% to prevent thundering herd
        jitter = delay * random.uniform(-0.25, 0.25)
        actual_delay = delay + jitter

        await asyncio.sleep(actual_delay)
```

**Example Delays** (base=1.0, max=30.0):
- Attempt 1: 1.0 * 2^0 = 1.0s ± 0.25s = [0.75s, 1.25s]
- Attempt 2: 1.0 * 2^1 = 2.0s ± 0.5s = [1.5s, 2.5s]
- Attempt 3: 1.0 * 2^2 = 4.0s ± 1.0s = [3.0s, 5.0s]
- Attempt 4: 1.0 * 2^3 = 8.0s ± 2.0s = [6.0s, 10.0s]

**Jitter Benefits**:
- Prevents thundering herd (multiple clients retrying simultaneously)
- Spreads load over time
- Industry best practice (AWS, Google recommendations)

### 2.3 Retryable vs Non-Retryable Errors

**Retryable** (Transient failures):
- `TimeoutError`: Operation timed out, might succeed if retried
- `ConnectionError`: Network issue, might be temporary
- `asyncpg.exceptions.TooManyConnectionsError`: Connection pool exhausted
- `asyncpg.exceptions.DeadlockDetectedError`: Database deadlock (auto-resolved)
- `redis.exceptions.ConnectionError`: Redis temporarily unavailable
- `redis.exceptions.TimeoutError`: Redis operation timed out
- Circuit breaker `CircuitBreakerOpen` in half-open state

**Non-Retryable** (Permanent failures):
- `ValueError`: Invalid input data
- `KeyError`: Missing required data
- `asyncpg.exceptions.UniqueViolationError`: Duplicate key constraint
- `asyncpg.exceptions.ForeignKeyViolationError`: Foreign key constraint
- `PermissionError`: Authorization failure
- `FileNotFoundError`: File doesn't exist

**Implementation**:
```python
RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    asyncpg.exceptions.TooManyConnectionsError,
    asyncpg.exceptions.DeadlockDetectedError,
    redis.exceptions.ConnectionError,
    redis.exceptions.TimeoutError,
)

NON_RETRYABLE_EXCEPTIONS = (
    ValueError,
    KeyError,
    asyncpg.exceptions.UniqueViolationError,
    asyncpg.exceptions.ForeignKeyViolationError,
    PermissionError,
    FileNotFoundError,
)
```

### 2.4 Implementation Plan: Story 12.5

#### Step 1: Retry Utilities Module (1 hour)
```python
# api/utils/retry.py

import asyncio
import random
from typing import Callable, TypeVar, Optional, Tuple, Type
from functools import wraps
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')

# Retryable exceptions
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    # Add asyncpg and redis exceptions when available
)

class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or RETRYABLE_EXCEPTIONS

def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    jitter: bool = True
) -> float:
    """
    Calculate retry delay with exponential backoff and optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter (±25%)

    Returns:
        Delay in seconds
    """
    # Exponential backoff: delay = base * (2 ^ attempt)
    delay = min(base_delay * (2 ** attempt), max_delay)

    if jitter:
        # Add jitter: random ±25%
        jitter_amount = delay * random.uniform(-0.25, 0.25)
        delay += jitter_amount

    return max(0, delay)  # Ensure non-negative

def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for async functions to add retry logic with exponential backoff.

    Usage:
        @with_retry(RetryConfig(max_attempts=5, base_delay=2.0))
        async def my_operation():
            ...

    Args:
        config: Retry configuration (uses defaults if None)
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            attempt = 0
            last_exception = None

            while attempt < config.max_attempts:
                try:
                    return await func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e
                    attempt += 1

                    if attempt >= config.max_attempts:
                        logger.error(
                            f"Max retry attempts ({config.max_attempts}) exceeded",
                            function=func.__name__,
                            error=str(e),
                            attempt=attempt
                        )
                        raise

                    delay = calculate_delay(
                        attempt - 1,
                        config.base_delay,
                        config.max_delay,
                        config.jitter
                    )

                    logger.warning(
                        f"Retryable error, retrying in {delay:.2f}s",
                        function=func.__name__,
                        error=str(e),
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay=delay
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            raise last_exception

        return wrapper
    return decorator
```

#### Step 2: Integration into Cache Service (30 min)
```python
# api/services/cache_service.py

from api.utils.retry import with_retry, RetryConfig
import redis.exceptions

# Configure retry for cache operations
CACHE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,  # Faster retries for cache
    max_delay=5.0,   # Max 5 seconds for cache
    retryable_exceptions=(
        redis.exceptions.ConnectionError,
        redis.exceptions.TimeoutError,
    )
)

class CacheService:
    """Redis-based caching service with L1 (in-memory) and L2 (Redis) layers."""

    @with_retry(CACHE_RETRY_CONFIG)
    async def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get value from cache with retry logic."""
        # Check L1 cache first
        l1_value = self._l1_cache.get(cache_key)
        if l1_value is not None:
            return l1_value

        # Check L2 cache (Redis) - THIS CAN FAIL AND RETRY
        try:
            value = await self.redis.get(cache_key)
            if value:
                # Deserialize and populate L1
                deserialized = self._deserialize(value)
                self._l1_cache[cache_key] = deserialized
                return deserialized
        except redis.exceptions.ConnectionError:
            # This will be caught by @with_retry and retried
            raise

        return None

    @with_retry(CACHE_RETRY_CONFIG)
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        namespace: str = "default"
    ) -> None:
        """Set value in cache with retry logic."""
        cache_key = f"{namespace}:{key}"

        # Set in L1
        self._l1_cache[cache_key] = value

        # Set in L2 (Redis) - THIS CAN FAIL AND RETRY
        try:
            serialized = self._serialize(value)
            await self.redis.setex(cache_key, ttl, serialized)
        except redis.exceptions.ConnectionError:
            # This will be caught by @with_retry and retried
            raise
```

#### Step 3: Integration into Repository Base (45 min)
```python
# api/db/repositories/base.py

from api.utils.retry import with_retry, RetryConfig
import asyncpg.exceptions

# Configure retry for database operations
DB_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    retryable_exceptions=(
        asyncpg.exceptions.TooManyConnectionsError,
        asyncpg.exceptions.DeadlockDetectedError,
        TimeoutError,
    )
)

class BaseRepository:
    """Base repository with retry logic."""

    @with_retry(DB_RETRY_CONFIG)
    async def execute_with_retry(self, query, params=None):
        """
        Execute database query with retry logic.

        Use this for operations that might fail due to:
        - Connection pool exhaustion
        - Deadlocks
        - Timeouts
        """
        async with self.engine.begin() as conn:
            result = await conn.execute(query, params or {})
            return result
```

#### Step 4: Integration into Embedding Service (30 min)
```python
# api/services/embedding_service.py

from api.utils.retry import with_retry, RetryConfig

# Configure retry for embedding operations
EMBEDDING_RETRY_CONFIG = RetryConfig(
    max_attempts=2,  # Only 1 retry for embeddings (slow operation)
    base_delay=2.0,
    max_delay=10.0,
    retryable_exceptions=(
        TimeoutError,
        ConnectionError,
    )
)

class EmbeddingService:
    """Embedding generation service with retry logic."""

    @with_retry(EMBEDDING_RETRY_CONFIG)
    async def generate_embeddings(
        self,
        texts: list[str],
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> list[list[float]]:
        """
        Generate embeddings with retry logic.

        Retries on:
        - TimeoutError (model temporarily unresponsive)
        - ConnectionError (network issues)
        """
        # Existing implementation
        ...
```

#### Step 5: Configuration Management (30 min)
```python
# api/config.py (or create new file)

from api.utils.retry import RetryConfig
from typing import Dict

# Centralized retry configurations
RETRY_CONFIGS: Dict[str, RetryConfig] = {
    "cache": RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=5.0
    ),
    "database": RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0
    ),
    "embedding": RetryConfig(
        max_attempts=2,
        base_delay=2.0,
        max_delay=10.0
    ),
    "default": RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0
    )
}

def get_retry_config(operation_type: str) -> RetryConfig:
    """Get retry configuration for operation type."""
    return RETRY_CONFIGS.get(operation_type, RETRY_CONFIGS["default"])
```

#### Step 6: Tests (1.5 hours)
```python
# tests/test_retry.py

import pytest
import asyncio
from api.utils.retry import with_retry, RetryConfig, calculate_delay

def test_calculate_delay_exponential():
    """Test exponential backoff calculation."""
    assert calculate_delay(0, 1.0, 30.0, jitter=False) == 1.0
    assert calculate_delay(1, 1.0, 30.0, jitter=False) == 2.0
    assert calculate_delay(2, 1.0, 30.0, jitter=False) == 4.0
    assert calculate_delay(3, 1.0, 30.0, jitter=False) == 8.0

def test_calculate_delay_max():
    """Test max delay cap."""
    assert calculate_delay(10, 1.0, 30.0, jitter=False) == 30.0

def test_calculate_delay_jitter():
    """Test jitter adds randomness."""
    delays = [calculate_delay(1, 1.0, 30.0, jitter=True) for _ in range(100)]
    assert len(set(delays)) > 1  # Should have variation
    assert all(1.5 <= d <= 2.5 for d in delays)  # Within ±25% of 2.0

@pytest.mark.anyio
async def test_retry_success_first_attempt():
    """Test successful operation on first attempt."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3))
    async def operation():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await operation()
    assert result == "success"
    assert call_count == 1

@pytest.mark.anyio
async def test_retry_success_after_retries():
    """Test successful operation after retries."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.1))
    async def operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TimeoutError("Transient error")
        return "success"

    result = await operation()
    assert result == "success"
    assert call_count == 3

@pytest.mark.anyio
async def test_retry_max_attempts_exceeded():
    """Test max attempts exceeded raises exception."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.1))
    async def operation():
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Persistent error")

    with pytest.raises(TimeoutError):
        await operation()

    assert call_count == 3

@pytest.mark.anyio
async def test_retry_non_retryable_error():
    """Test non-retryable error raised immediately."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3))
    async def operation():
        nonlocal call_count
        call_count += 1
        raise ValueError("Non-retryable error")

    with pytest.raises(ValueError):
        await operation()

    assert call_count == 1  # No retries

@pytest.mark.anyio
async def test_retry_custom_exceptions():
    """Test custom retryable exceptions."""
    call_count = 0

    class CustomError(Exception):
        pass

    @with_retry(RetryConfig(
        max_attempts=3,
        base_delay=0.1,
        retryable_exceptions=(CustomError,)
    ))
    async def operation():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise CustomError("Retryable")
        return "success"

    result = await operation()
    assert result == "success"
    assert call_count == 2

@pytest.mark.anyio
async def test_retry_timing():
    """Test retry delays are exponential."""
    import time

    call_times = []

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.1, jitter=False))
    async def operation():
        call_times.append(time.time())
        if len(call_times) < 3:
            raise TimeoutError("Retry")
        return "success"

    await operation()

    # Check delays are approximately exponential
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]

    assert 0.08 <= delay1 <= 0.15  # ~0.1s (2^0 * 0.1)
    assert 0.18 <= delay2 <= 0.25  # ~0.2s (2^1 * 0.1)
```

#### Step 7: Integration Tests (45 min)
```python
# tests/integration/test_retry_integration.py

@pytest.mark.anyio
async def test_cache_retry_on_redis_failure(cache_service, monkeypatch):
    """Test cache service retries on Redis connection error."""
    call_count = 0
    original_get = cache_service.redis.get

    async def failing_get(key):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise redis.exceptions.ConnectionError("Transient failure")
        return await original_get(key)

    monkeypatch.setattr(cache_service.redis, "get", failing_get)

    # Should retry and succeed
    await cache_service.set("test_key", "test_value")
    value = await cache_service.get("test_key")

    assert value == "test_value"
    assert call_count == 2  # Failed once, retried and succeeded

@pytest.mark.anyio
async def test_database_retry_on_deadlock(event_repository):
    """Test database operation retries on deadlock."""
    # Simulate deadlock scenario
    # This is complex to test, might need manual testing or specific setup
    pass
```

#### Step 8: Documentation (30 min)
```markdown
# docs/retry_logic.md

# Retry Logic with Exponential Backoff

## Overview

MnemoLite implements retry logic with exponential backoff and jitter for handling transient failures.

## Configuration

Retry configurations are centralized in `api/config.py`:

- **Cache operations**: 3 attempts, 0.5s base delay, 5s max
- **Database operations**: 3 attempts, 1.0s base delay, 10s max
- **Embedding operations**: 2 attempts, 2.0s base delay, 10s max

## Usage

### Decorator Usage

```python
from api.utils.retry import with_retry, RetryConfig

@with_retry(RetryConfig(max_attempts=3, base_delay=1.0))
async def my_operation():
    # Operation that might fail transiently
    ...
```

### Retryable Exceptions

The following exceptions trigger retries:
- `TimeoutError`
- `ConnectionError`
- `asyncpg.exceptions.TooManyConnectionsError`
- `asyncpg.exceptions.DeadlockDetectedError`
- `redis.exceptions.ConnectionError`
- `redis.exceptions.TimeoutError`

### Non-Retryable Exceptions

The following exceptions are raised immediately:
- `ValueError`, `KeyError` (invalid input)
- `asyncpg.exceptions.UniqueViolationError` (constraint violation)
- `PermissionError` (authorization failure)

## Algorithm

1. **Exponential Backoff**: delay = base_delay * (2 ^ attempt)
2. **Jitter**: ±25% randomness to prevent thundering herd
3. **Max Delay Cap**: Prevents unbounded delays

Example delays (base=1.0s):
- Attempt 1: ~1.0s (0.75-1.25s with jitter)
- Attempt 2: ~2.0s (1.5-2.5s with jitter)
- Attempt 3: ~4.0s (3.0-5.0s with jitter)
```

### 2.5 Story 12.5 Success Criteria

✅ **Acceptance Criteria**:
1. Retry decorator with exponential backoff implemented
2. Jitter (±25%) prevents thundering herd
3. Configurable retry limits per operation type
4. Retryable vs non-retryable errors classified
5. Integrated into cache, database, embedding services
6. Tests cover retry behavior, delays, max attempts
7. Integration tests verify retry on real failures

**Timeline**: 4-6 hours total

---

## Part 3: Combined Strategy and Sequencing

### 3.1 Recommended Execution Order

**Phase 1: Story 12.4 - Error Tracking (4-5 hours)**
1. Create error schema and migration (30 min)
2. Implement ErrorTrackingService (1 hour)
3. Implement ErrorRepository (45 min)
4. Integrate into existing services (1.5 hours)
5. Create monitoring UI routes and templates (1.5 hours)
6. Implement AlertService (45 min)
7. Write tests (1 hour)

**Phase 2: Story 12.5 - Retry Logic (4-6 hours)**
1. Implement retry utilities (1 hour)
2. Integrate into CacheService (30 min)
3. Integrate into BaseRepository (45 min)
4. Integrate into EmbeddingService (30 min)
5. Create retry configurations (30 min)
6. Write unit tests (1.5 hours)
7. Write integration tests (45 min)
8. Documentation (30 min)

**Phase 3: Completion Reports (1.5 hours)**
1. Story 12.2 completion report (optional, 30 min)
2. Story 12.4 completion report (30 min)
3. Story 12.5 completion report (30 min)
4. EPIC-12 final completion report (30 min)

**Total Estimated Time**: 10-12.5 hours

### 3.2 Why This Order?

1. **Error Tracking First**:
   - Retry logic will generate logs we want to track
   - Error tracking provides observability for retry behavior
   - Can monitor if retries are working effectively

2. **Retry Logic Second**:
   - Can leverage error tracking to log retry attempts
   - Error dashboard will show retry failures
   - Better debugging experience

3. **Completion Reports Last**:
   - Full implementation done
   - Can report accurate metrics
   - Can document lessons learned

### 3.3 Integration Points

**Error Tracking ⊕ Retry Logic**:
```python
# Example: Retry decorator logs to error tracking

@with_retry(CACHE_RETRY_CONFIG)
async def cache_operation():
    try:
        # Operation
        ...
    except Exception as e:
        # Error tracking service logs this
        await error_tracking.log_error(
            error=e,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.CACHE,
            service="CacheService",
            context={"retry_attempt": attempt}
        )
        raise
```

**Benefits**:
- See retry patterns in error dashboard
- Track if specific errors retry successfully
- Alert if retry exhaustion happens frequently

### 3.4 Testing Strategy

**Unit Tests** (Stories 12.4 + 12.5):
- Test error logging and aggregation
- Test retry delays (exponential + jitter)
- Test max attempts enforcement
- Test retryable vs non-retryable classification

**Integration Tests**:
- Test error tracking across services
- Test retry on real Redis/PostgreSQL failures
- Test alert thresholds trigger correctly

**Manual Testing**:
- Simulate Redis failure (stop container)
- Verify cache operations retry
- Check error dashboard shows retries
- Verify alerts trigger at thresholds

### 3.5 Success Metrics

**Story 12.4 Metrics**:
- ✅ All errors logged to database
- ✅ Error dashboard accessible at `/monitoring/errors`
- ✅ Alert service checks thresholds every 5 minutes
- ✅ Test coverage >80% for error tracking

**Story 12.5 Metrics**:
- ✅ Retry decorator implemented and tested
- ✅ Exponential backoff + jitter working
- ✅ Cache, database, embedding services use retry
- ✅ Test coverage >80% for retry logic

**EPIC-12 Final Metrics**:
- ✅ 23/23 points complete (100%)
- ✅ 5/5 stories complete
- ✅ Production-ready error handling
- ✅ Production-ready resilience patterns

---

## Part 4: Risk Analysis and Mitigation

### 4.1 Technical Risks

**Risk 1: Error tracking performance overhead**
- **Impact**: Error logging adds latency to every operation
- **Likelihood**: Low (fire-and-forget async)
- **Mitigation**:
  - Use `asyncio.create_task()` for fire-and-forget
  - Don't block on error storage
  - If error storage fails, log warning but continue

**Risk 2: Retry logic increases latency**
- **Impact**: Operations take longer due to retries
- **Likelihood**: Medium (retries happen on failures)
- **Mitigation**:
  - Configure aggressive timeouts (fail fast)
  - Limit max attempts (2-3)
  - Use fast base delays (0.5-1.0s for cache)
  - User experiences delay only on failure (rare)

**Risk 3: Database schema migration**
- **Impact**: Adding error_logs table might fail
- **Likelihood**: Low (simple table creation)
- **Mitigation**:
  - Test migration on test database first
  - Create migration script with rollback
  - Run migration during low-traffic window

**Risk 4: Thundering herd despite jitter**
- **Impact**: Multiple clients retry simultaneously
- **Likelihood**: Low (jitter prevents this)
- **Mitigation**:
  - Verify jitter implementation (±25%)
  - Test with multiple concurrent clients
  - Monitor retry patterns in error dashboard

### 4.2 Scope Risks

**Risk 1: Integration into all services takes longer than estimated**
- **Impact**: Timeline extends beyond 10-12 hours
- **Likelihood**: Medium
- **Mitigation**:
  - Prioritize critical services (cache, database, embedding)
  - Defer non-critical integrations to future
  - Create helper functions to simplify integration

**Risk 2: Test coverage incomplete**
- **Impact**: Bugs in production
- **Likelihood**: Low (comprehensive test plan)
- **Mitigation**:
  - Write tests alongside implementation
  - Use TDD approach where possible
  - Manual testing checklist for integration

### 4.3 User Experience Risks

**Risk 1: Error dashboard overwhelming with too much data**
- **Impact**: Users can't find relevant errors
- **Likelihood**: Low (filtered views)
- **Mitigation**:
  - Default to last 24 hours
  - Separate critical errors view
  - Implement filtering and search (future)

**Risk 2: Retry delays frustrate users**
- **Impact**: Operations feel slow
- **Likelihood**: Low (only on failures)
- **Mitigation**:
  - Clear logging shows retry progress
  - Fast base delays (0.5-1.0s)
  - Circuit breakers prevent excessive retries

---

## Part 5: Recommendations and Next Steps

### 5.1 Immediate Recommendations

**Option A: Full Implementation (RECOMMENDED)**
- Complete Stories 12.4 and 12.5 as designed
- Timeline: 10-12 hours
- Result: EPIC-12 100% complete, production-ready

**Option B: Minimal Viable Implementation**
- Story 12.4: Error logging only (no dashboard, no alerts)
- Story 12.5: Retry decorator for cache only
- Timeline: 6-8 hours
- Result: Partial EPIC-12, defer remainder

**Option C: Story 12.5 Only**
- Skip Story 12.4 (error tracking)
- Implement retry logic only
- Timeline: 4-6 hours
- Result: Resilience improved, no observability

### 5.2 Why Option A (Full Implementation)?

1. **Completeness**: EPIC-12 100% done, clean closure
2. **Synergy**: Error tracking + retry logic complement each other
3. **Production Readiness**: Both are critical for production
4. **Observability**: Error dashboard provides visibility into system health
5. **MnemoLite Philosophy**: "Production-ready" is a core value

### 5.3 Post-EPIC-12 Enhancements (Future)

**Not in scope, but valuable**:
1. **Email/Slack Alerting**: Currently logs only, add integrations
2. **Error Grouping**: Group similar errors (like Sentry)
3. **Error Search**: Full-text search on error messages
4. **Retry Metrics**: Track retry success rate, average attempts
5. **Dashboard Filters**: Filter by service, category, severity
6. **Sentry Integration**: If error volume grows, migrate to Sentry

---

## Part 6: Implementation Checklist

### Story 12.4 Checklist

- [ ] Create `db/migrations/v5_to_v6_error_tracking.sql`
- [ ] Create `api/services/error_tracking_service.py`
- [ ] Create `api/db/repositories/error_repository.py`
- [ ] Integrate into `EmbeddingService`
- [ ] Integrate into `CacheService`
- [ ] Integrate into `SearchService`
- [ ] Integrate into database repositories
- [ ] Create `/monitoring/errors` route
- [ ] Create `templates/monitoring_errors.html`
- [ ] Create `api/services/alert_service.py`
- [ ] Integrate AlertService into `main.py` lifespan
- [ ] Write tests for `ErrorTrackingService`
- [ ] Write tests for `ErrorRepository`
- [ ] Write tests for `AlertService`
- [ ] Manual testing: Trigger errors, verify dashboard
- [ ] Create Story 12.4 completion report

### Story 12.5 Checklist

- [ ] Create `api/utils/retry.py`
- [ ] Implement `calculate_delay()` function
- [ ] Implement `with_retry()` decorator
- [ ] Create `api/config.py` retry configurations
- [ ] Integrate into `CacheService.get()`
- [ ] Integrate into `CacheService.set()`
- [ ] Integrate into `BaseRepository`
- [ ] Integrate into `EmbeddingService`
- [ ] Write tests for `calculate_delay()`
- [ ] Write tests for `with_retry()` decorator
- [ ] Write tests for retry timing
- [ ] Write tests for max attempts
- [ ] Write integration tests for cache retry
- [ ] Write integration tests for database retry
- [ ] Create `docs/retry_logic.md`
- [ ] Create Story 12.5 completion report

### EPIC-12 Final Checklist

- [ ] All 5 stories complete (12.1-12.5)
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Manual testing complete
- [ ] Create EPIC-12 completion report
- [ ] Update EPIC-12 README status
- [ ] Commit and push
- [ ] Celebrate! 🎉

---

## Part 7: Conclusion

**EPIC-12 Completion**: Stories 12.4 and 12.5 will bring EPIC-12 to 100% completion, providing production-ready error handling and resilience.

**Key Innovations**:
1. **Error Tracking**: PostgreSQL-based, zero cost, integrated with existing monitoring UI
2. **Retry Logic**: Industry best practices (exponential backoff + jitter)
3. **Synergy**: Error tracking provides observability for retry behavior
4. **Incrementality**: Can add Sentry/email/Slack later without refactoring

**Timeline**: 10-12 hours total for both stories + completion reports

**Recommendation**: Proceed with **Option A (Full Implementation)** for complete EPIC-12 closure.

---

**Ready to begin?** Let's start with Story 12.4 - Error Tracking & Alerting.
