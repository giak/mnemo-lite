"""
Timeout utilities for preventing infinite hangs.

Provides timeout enforcement for async operations using asyncio.wait_for()
with structured logging and error tracking.

EPIC-12 Story 12.1: Timeout-Based Execution
"""

import asyncio
import functools
import logging
from typing import TypeVar, Callable, Any, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Operation exceeded timeout limit."""

    def __init__(self, operation_name: str, timeout: float, context: Optional[dict] = None):
        self.operation_name = operation_name
        self.timeout = timeout
        self.context = context or {}

        message = f"{operation_name} exceeded {timeout}s timeout"
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            message += f" (context: {context_str})"
        super().__init__(message)


async def with_timeout(
    coro,
    timeout: float,
    operation_name: str = "operation",
    context: Optional[dict] = None,
    raise_on_timeout: bool = True
) -> Any:
    """
    Execute coroutine with timeout enforcement.

    Args:
        coro: Coroutine to execute
        timeout: Maximum execution time in seconds
        operation_name: Name for logging/error messages
        context: Additional context for logging (e.g., file_path, repository)
        raise_on_timeout: If True, raise TimeoutError; if False, return None

    Returns:
        Result of coroutine if successful, None if timeout and raise_on_timeout=False

    Raises:
        TimeoutError: If operation exceeds timeout and raise_on_timeout=True

    Example:
        >>> result = await with_timeout(
        ...     tree_sitter_service.chunk_code(source),
        ...     timeout=5.0,
        ...     operation_name="tree_sitter_parse",
        ...     context={"file": file_path}
        ... )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)

    except asyncio.TimeoutError:
        logger.error(
            f"⏱️ Timeout: {operation_name} exceeded {timeout}s",
            extra={
                "operation": operation_name,
                "timeout": timeout,
                "context": context or {}
            }
        )

        if raise_on_timeout:
            raise TimeoutError(operation_name, timeout, context)
        else:
            return None


def timeout_decorator(
    timeout: float,
    operation_name: Optional[str] = None,
    raise_on_timeout: bool = True
):
    """
    Decorator for timeout enforcement on async methods.

    Args:
        timeout: Maximum execution time in seconds
        operation_name: Name for logging (defaults to function name)
        raise_on_timeout: If True, raise TimeoutError; if False, return None

    Example:
        >>> @timeout_decorator(timeout=5.0, operation_name="chunk_code")
        >>> async def chunk_code(self, source_code: str):
        ...     ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            # Extract context from common kwargs
            context = {}
            if "file_path" in kwargs:
                context["file_path"] = kwargs["file_path"]
            if "repository" in kwargs:
                context["repository"] = kwargs["repository"]
            if "language" in kwargs:
                context["language"] = kwargs["language"]

            return await with_timeout(
                func(*args, **kwargs),
                timeout=timeout,
                operation_name=op_name,
                context=context,
                raise_on_timeout=raise_on_timeout
            )
        return wrapper
    return decorator


def cpu_bound_timeout(timeout: float, operation_name: Optional[str] = None):
    """
    Decorator for CPU-bound operations that need to run in thread pool.

    For synchronous CPU-bound operations (like tree-sitter parsing),
    wraps execution in asyncio.to_thread() then applies timeout.

    Args:
        timeout: Maximum execution time in seconds
        operation_name: Name for logging

    Example:
        >>> @cpu_bound_timeout(timeout=5.0, operation_name="tree_sitter_parse")
        >>> def parse_code(self, source_code: str):
        ...     # Synchronous tree-sitter parsing
        ...     tree = self.parser.parse(bytes(source_code, "utf8"))
        ...     return tree
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            # Extract context from kwargs
            context = {}
            if len(args) > 1 and hasattr(args[0], '__class__'):
                # Try to get file_path from method args (common pattern)
                for i, arg in enumerate(args[1:], start=1):
                    if isinstance(arg, str) and ('/' in arg or '.' in arg):
                        # Likely a file path
                        context["potential_file"] = arg[:100]  # Truncate
                        break

            # Run synchronous function in thread pool
            coro = asyncio.to_thread(func, *args, **kwargs)

            # Apply timeout
            return await with_timeout(
                coro,
                timeout=timeout,
                operation_name=op_name,
                context=context,
                raise_on_timeout=True
            )
        return wrapper
    return decorator
