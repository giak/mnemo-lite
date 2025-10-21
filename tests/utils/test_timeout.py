"""
Unit tests for timeout utilities.

EPIC-12 Story 12.1: Timeout-Based Execution
"""

import pytest
import asyncio
import time
from utils.timeout import (
    with_timeout,
    timeout_decorator,
    cpu_bound_timeout,
    TimeoutError
)
from config.timeouts import (
    get_timeout,
    set_timeout,
    get_all_timeouts,
    reset_to_defaults
)


class TestWithTimeout:
    """Test with_timeout() function."""

    @pytest.mark.anyio
    async def test_timeout_enforced(self):
        """Operation exceeding timeout raises TimeoutError."""

        async def slow_operation():
            await asyncio.sleep(10)  # 10 seconds
            return "done"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow_operation(), timeout=1.0)

        error = exc_info.value
        assert "1.0s" in str(error)
        assert error.timeout == 1.0

    @pytest.mark.anyio
    async def test_timeout_not_reached(self):
        """Fast operation succeeds."""

        async def fast_operation():
            await asyncio.sleep(0.1)
            return "done"

        result = await with_timeout(fast_operation(), timeout=5.0)
        assert result == "done"

    @pytest.mark.anyio
    async def test_timeout_with_context(self):
        """Context included in error message."""

        async def slow_operation():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(
                slow_operation(),
                timeout=1.0,
                operation_name="test_op",
                context={"file": "test.py"}
            )

        error = exc_info.value
        assert error.operation_name == "test_op"
        assert error.context["file"] == "test.py"
        assert "test.py" in str(error)

    @pytest.mark.anyio
    async def test_timeout_no_raise(self):
        """With raise_on_timeout=False, returns None."""

        async def slow_operation():
            await asyncio.sleep(10)
            return "done"

        result = await with_timeout(
            slow_operation(),
            timeout=1.0,
            raise_on_timeout=False
        )

        assert result is None

    @pytest.mark.anyio
    async def test_timeout_zero(self):
        """Zero timeout immediately times out."""

        async def instant_operation():
            return "done"

        # Even instant operations may timeout with 0s timeout
        with pytest.raises(TimeoutError):
            await with_timeout(instant_operation(), timeout=0.0)

    @pytest.mark.anyio
    async def test_timeout_preserves_return_value(self):
        """Return value is preserved when no timeout."""

        async def operation_with_value():
            await asyncio.sleep(0.1)
            return {"data": [1, 2, 3], "count": 3}

        result = await with_timeout(operation_with_value(), timeout=5.0)
        assert result == {"data": [1, 2, 3], "count": 3}


class TestTimeoutDecorator:
    """Test timeout_decorator()."""

    @pytest.mark.anyio
    async def test_decorator_enforces_timeout(self):
        """Decorator enforces timeout."""

        @timeout_decorator(timeout=1.0)
        async def slow_func():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(TimeoutError):
            await slow_func()

    @pytest.mark.anyio
    async def test_decorator_preserves_function_name(self):
        """Decorator preserves __name__ and __doc__."""

        @timeout_decorator(timeout=5.0)
        async def my_function():
            """My docstring."""
            return "done"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    @pytest.mark.anyio
    async def test_decorator_extracts_file_path_context(self):
        """Decorator extracts file_path from kwargs."""

        @timeout_decorator(timeout=1.0, operation_name="test_op")
        async def func_with_file_path(file_path: str):
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await func_with_file_path(file_path="test.py")

        error = exc_info.value
        assert error.context.get("file_path") == "test.py"

    @pytest.mark.anyio
    async def test_decorator_extracts_repository_context(self):
        """Decorator extracts repository from kwargs."""

        @timeout_decorator(timeout=1.0)
        async def func_with_repo(repository: str, language: str):
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await func_with_repo(repository="my-repo", language="python")

        error = exc_info.value
        assert error.context.get("repository") == "my-repo"
        assert error.context.get("language") == "python"

    @pytest.mark.anyio
    async def test_decorator_with_args_and_kwargs(self):
        """Decorator works with both args and kwargs."""

        @timeout_decorator(timeout=5.0)
        async def func_with_mixed(a, b, c=None):
            await asyncio.sleep(0.1)
            return (a, b, c)

        result = await func_with_mixed(1, 2, c=3)
        assert result == (1, 2, 3)

    @pytest.mark.anyio
    async def test_decorator_no_raise(self):
        """Decorator with raise_on_timeout=False returns None."""

        @timeout_decorator(timeout=1.0, raise_on_timeout=False)
        async def slow_func():
            await asyncio.sleep(10)
            return "done"

        result = await slow_func()
        assert result is None


class TestCPUBoundTimeout:
    """Test cpu_bound_timeout() for synchronous operations."""

    @pytest.mark.anyio
    async def test_cpu_bound_timeout_enforced(self):
        """CPU-bound operation times out."""

        @cpu_bound_timeout(timeout=1.0, operation_name="slow_cpu")
        def slow_cpu_operation():
            time.sleep(10)  # Synchronous sleep
            return "done"

        with pytest.raises(TimeoutError) as exc_info:
            await slow_cpu_operation()

        error = exc_info.value
        assert "slow_cpu" in str(error)

    @pytest.mark.anyio
    async def test_cpu_bound_success(self):
        """Fast CPU-bound operation succeeds."""

        @cpu_bound_timeout(timeout=5.0)
        def fast_cpu_operation():
            time.sleep(0.1)
            return "done"

        result = await fast_cpu_operation()
        assert result == "done"

    @pytest.mark.anyio
    async def test_cpu_bound_with_arguments(self):
        """CPU-bound decorator preserves function arguments."""

        @cpu_bound_timeout(timeout=5.0)
        def cpu_operation_with_args(a, b, c=None):
            time.sleep(0.1)
            return (a, b, c)

        result = await cpu_operation_with_args(1, 2, c=3)
        assert result == (1, 2, 3)

    @pytest.mark.anyio
    async def test_cpu_bound_preserves_exceptions(self):
        """CPU-bound decorator preserves non-timeout exceptions."""

        @cpu_bound_timeout(timeout=5.0)
        def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_operation()


class TestTimeoutConfiguration:
    """Test timeout configuration utilities."""

    def test_get_timeout_existing(self):
        """Get existing timeout value."""
        timeout = get_timeout("tree_sitter_parse")
        assert timeout == 5.0

    def test_get_timeout_missing_uses_default(self):
        """Missing timeout uses default value."""
        timeout = get_timeout("non_existent_operation")
        assert timeout == 30.0  # default

        timeout = get_timeout("non_existent_operation", default=15.0)
        assert timeout == 15.0

    def test_set_timeout(self):
        """Set timeout updates configuration."""
        original = get_timeout("tree_sitter_parse")

        set_timeout("tree_sitter_parse", 10.0)
        assert get_timeout("tree_sitter_parse") == 10.0

        # Restore original
        set_timeout("tree_sitter_parse", original)

    def test_set_timeout_negative_raises(self):
        """Setting negative timeout raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            set_timeout("test_op", -1.0)

    def test_set_timeout_zero_raises(self):
        """Setting zero timeout raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            set_timeout("test_op", 0.0)

    def test_get_all_timeouts(self):
        """Get all timeouts returns dict copy."""
        timeouts = get_all_timeouts()

        assert isinstance(timeouts, dict)
        assert "tree_sitter_parse" in timeouts
        assert "embedding_generation_batch" in timeouts
        assert len(timeouts) >= 10  # At least 10 configured timeouts

        # Verify it's a copy (mutation doesn't affect original)
        timeouts["tree_sitter_parse"] = 999.0
        assert get_timeout("tree_sitter_parse") != 999.0

    def test_reset_to_defaults(self):
        """Reset to defaults restores original values."""
        # Modify a timeout
        set_timeout("tree_sitter_parse", 100.0)
        assert get_timeout("tree_sitter_parse") == 100.0

        # Reset
        reset_to_defaults()
        assert get_timeout("tree_sitter_parse") == 5.0


class TestTimeoutErrorClass:
    """Test custom TimeoutError exception."""

    def test_timeout_error_message(self):
        """TimeoutError has informative message."""
        error = TimeoutError("test_operation", 5.0)
        assert "test_operation" in str(error)
        assert "5.0s" in str(error)

    def test_timeout_error_with_context(self):
        """TimeoutError includes context in message."""
        error = TimeoutError(
            "test_operation",
            5.0,
            context={"file": "test.py", "line": 42}
        )

        error_str = str(error)
        assert "test_operation" in error_str
        assert "test.py" in error_str
        assert "42" in error_str

    def test_timeout_error_attributes(self):
        """TimeoutError exposes attributes."""
        error = TimeoutError(
            "my_op",
            10.0,
            context={"key": "value"}
        )

        assert error.operation_name == "my_op"
        assert error.timeout == 10.0
        assert error.context == {"key": "value"}
