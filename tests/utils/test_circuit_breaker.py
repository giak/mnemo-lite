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

from utils.circuit_breaker import (
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
            recovery_timeout=100,  # Long timeout so it doesn't immediately transition
            name="test"
        )

        # Open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Manually transition to HALF_OPEN (simulating timeout elapsed)
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
