"""
Tests for retry utilities with exponential backoff and jitter.

Story: EPIC-12 Story 12.5 - Retry Logic with Backoff
Author: Claude Code
Date: 2025-10-22
"""

import pytest
import asyncio
import time
from utils.retry import (
    with_retry,
    RetryConfig,
    calculate_delay,
    CACHE_RETRY_CONFIG,
    DATABASE_RETRY_CONFIG,
    EMBEDDING_RETRY_CONFIG,
    get_retry_config
)


def test_calculate_delay_exponential():
    """Test exponential backoff calculation without jitter."""
    assert calculate_delay(0, 1.0, 30.0, jitter=False) == 1.0  # 1.0 * 2^0
    assert calculate_delay(1, 1.0, 30.0, jitter=False) == 2.0  # 1.0 * 2^1
    assert calculate_delay(2, 1.0, 30.0, jitter=False) == 4.0  # 1.0 * 2^2
    assert calculate_delay(3, 1.0, 30.0, jitter=False) == 8.0  # 1.0 * 2^3


def test_calculate_delay_max_cap():
    """Test that delay is capped at max_delay."""
    # 1.0 * 2^10 = 1024, but capped at 30
    assert calculate_delay(10, 1.0, 30.0, jitter=False) == 30.0


def test_calculate_delay_jitter():
    """Test that jitter adds randomness within ±25%."""
    delays = [calculate_delay(1, 1.0, 30.0, jitter=True) for _ in range(100)]

    # Should have variation
    assert len(set(delays)) > 1, "Jitter should produce different delays"

    # All delays should be within ±25% of 2.0 (base * 2^1)
    for delay in delays:
        assert 1.5 <= delay <= 2.5, f"Delay {delay} out of jitter range [1.5, 2.5]"


@pytest.mark.anyio
async def test_retry_success_first_attempt():
    """Test successful operation on first attempt (no retries)."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3))
    async def operation():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await operation()
    assert result == "success"
    assert call_count == 1, "Should succeed on first attempt"


@pytest.mark.anyio
async def test_retry_success_after_failures():
    """Test successful operation after retryable failures."""
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
    assert call_count == 3, "Should succeed on 3rd attempt after 2 failures"


@pytest.mark.anyio
async def test_retry_max_attempts_exceeded():
    """Test that max attempts are enforced and exception is raised."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.1))
    async def operation():
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Persistent error")

    with pytest.raises(TimeoutError, match="Persistent error"):
        await operation()

    assert call_count == 3, "Should attempt exactly 3 times"


@pytest.mark.anyio
async def test_retry_non_retryable_error():
    """Test that non-retryable errors are raised immediately."""
    call_count = 0

    @with_retry(RetryConfig(max_attempts=3))
    async def operation():
        nonlocal call_count
        call_count += 1
        raise ValueError("Non-retryable error")

    with pytest.raises(ValueError, match="Non-retryable error"):
        await operation()

    assert call_count == 1, "Should not retry non-retryable error"


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
    assert call_count == 2, "Should retry CustomError"


@pytest.mark.anyio
async def test_retry_delay_timing():
    """Test that retry delays are approximately correct."""
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

    # ~0.1s (2^0 * 0.1) with small tolerance
    assert 0.08 <= delay1 <= 0.15, f"First retry delay {delay1} not ~0.1s"

    # ~0.2s (2^1 * 0.1) with small tolerance
    assert 0.18 <= delay2 <= 0.25, f"Second retry delay {delay2} not ~0.2s"


def test_retry_config_presets():
    """Test that retry config presets are correctly defined."""
    assert CACHE_RETRY_CONFIG.max_attempts == 3
    assert CACHE_RETRY_CONFIG.base_delay == 0.5
    assert CACHE_RETRY_CONFIG.max_delay == 5.0

    assert DATABASE_RETRY_CONFIG.max_attempts == 3
    assert DATABASE_RETRY_CONFIG.base_delay == 1.0
    assert DATABASE_RETRY_CONFIG.max_delay == 10.0

    assert EMBEDDING_RETRY_CONFIG.max_attempts == 2
    assert EMBEDDING_RETRY_CONFIG.base_delay == 2.0
    assert EMBEDDING_RETRY_CONFIG.max_delay == 10.0


def test_get_retry_config():
    """Test getting retry config by operation type."""
    assert get_retry_config("cache") == CACHE_RETRY_CONFIG
    assert get_retry_config("database") == DATABASE_RETRY_CONFIG
    assert get_retry_config("embedding") == EMBEDDING_RETRY_CONFIG
    assert get_retry_config("unknown").max_attempts == 3  # default
