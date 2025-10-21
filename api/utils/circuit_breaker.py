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
from typing import Optional, Callable, Any, TypeVar
from dataclasses import dataclass
import structlog
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
