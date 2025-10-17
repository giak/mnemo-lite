"""
Result pattern for clean error handling in MnemoLite.

Provides a functional approach to error handling without excessive try/except blocks.
Inspired by Rust's Result type and functional programming patterns.
"""

from typing import TypeVar, Generic, Optional, Callable, Union, Any
from dataclasses import dataclass
from enum import Enum

T = TypeVar("T")  # Success type
E = TypeVar("E")  # Error type


class ErrorType(Enum):
    """Common error types in the application."""
    DATABASE = "database"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    NETWORK = "network"
    PERMISSION = "permission"
    INTERNAL = "internal"
    TIMEOUT = "timeout"


@dataclass
class Error:
    """Structured error information."""
    message: str
    error_type: ErrorType
    details: Optional[dict] = None
    cause: Optional[Exception] = None

    def __str__(self) -> str:
        """String representation of the error."""
        base = f"[{self.error_type.value}] {self.message}"
        if self.details:
            base += f" - Details: {self.details}"
        return base


class Result(Generic[T, E]):
    """
    A Result type that can be either Success or Failure.

    Example:
        def divide(a: int, b: int) -> Result[float, str]:
            if b == 0:
                return Result.fail("Cannot divide by zero")
            return Result.ok(a / b)

        result = divide(10, 2)
        if result.is_ok():
            print(f"Result: {result.unwrap()}")
        else:
            print(f"Error: {result.error}")
    """

    def __init__(self, value: Optional[T] = None, error: Optional[E] = None):
        """
        Initialize a Result.

        Args:
            value: Success value (mutually exclusive with error)
            error: Error value (mutually exclusive with value)
        """
        if value is not None and error is not None:
            raise ValueError("Result cannot have both value and error")
        if value is None and error is None:
            raise ValueError("Result must have either value or error")

        self._value = value
        self._error = error

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        """
        Create a successful Result.

        Args:
            value: The success value

        Returns:
            A Result containing the value
        """
        return cls(value=value)

    @classmethod
    def fail(cls, error: E) -> "Result[T, E]":
        """
        Create a failed Result.

        Args:
            error: The error value

        Returns:
            A Result containing the error
        """
        return cls(error=error)

    def is_ok(self) -> bool:
        """Check if Result is successful."""
        return self._value is not None

    def is_err(self) -> bool:
        """Check if Result is an error."""
        return self._error is not None

    @property
    def value(self) -> Optional[T]:
        """Get the value if successful, None otherwise."""
        return self._value

    @property
    def error(self) -> Optional[E]:
        """Get the error if failed, None otherwise."""
        return self._error

    def unwrap(self) -> T:
        """
        Get the value, raising an exception if Result is an error.

        Returns:
            The success value

        Raises:
            ValueError: If Result is an error
        """
        if self.is_err():
            raise ValueError(f"Called unwrap on an error Result: {self._error}")
        return self._value

    def unwrap_or(self, default: T) -> T:
        """
        Get the value or return a default if Result is an error.

        Args:
            default: Default value to return if Result is an error

        Returns:
            The success value or default
        """
        return self._value if self.is_ok() else default

    def unwrap_or_else(self, f: Callable[[E], T]) -> T:
        """
        Get the value or compute it from the error.

        Args:
            f: Function to compute value from error

        Returns:
            The success value or computed value
        """
        return self._value if self.is_ok() else f(self._error)

    def expect(self, message: str) -> T:
        """
        Get the value, raising an exception with custom message if Result is an error.

        Args:
            message: Custom error message

        Returns:
            The success value

        Raises:
            ValueError: If Result is an error
        """
        if self.is_err():
            raise ValueError(f"{message}: {self._error}")
        return self._value

    def map(self, f: Callable[[T], Any]) -> "Result[Any, E]":
        """
        Transform the value if successful.

        Args:
            f: Function to transform the value

        Returns:
            A new Result with transformed value or same error
        """
        if self.is_ok():
            return Result.ok(f(self._value))
        return Result.fail(self._error)

    def map_err(self, f: Callable[[E], Any]) -> "Result[T, Any]":
        """
        Transform the error if failed.

        Args:
            f: Function to transform the error

        Returns:
            A new Result with same value or transformed error
        """
        if self.is_err():
            return Result.fail(f(self._error))
        return Result.ok(self._value)

    def and_then(self, f: Callable[[T], "Result[Any, E]"]) -> "Result[Any, E]":
        """
        Chain another operation that returns a Result.

        Args:
            f: Function that takes value and returns a Result

        Returns:
            The Result from f if successful, or the original error
        """
        if self.is_ok():
            return f(self._value)
        return Result.fail(self._error)

    def or_else(self, f: Callable[[E], "Result[T, Any]"]) -> "Result[T, Any]":
        """
        Provide an alternative Result if failed.

        Args:
            f: Function that takes error and returns a Result

        Returns:
            The original Result if successful, or the Result from f
        """
        if self.is_err():
            return f(self._error)
        return Result.ok(self._value)

    def __repr__(self) -> str:
        """String representation of Result."""
        if self.is_ok():
            return f"Result.ok({repr(self._value)})"
        return f"Result.fail({repr(self._error)})"

    def __bool__(self) -> bool:
        """Boolean evaluation - True if successful."""
        return self.is_ok()


# Type alias for common Result types
RepositoryResult = Result[T, Error]
ServiceResult = Result[T, Error]


def from_exception(func: Callable[..., T]) -> Callable[..., Result[T, Error]]:
    """
    Decorator to convert exceptions to Result.

    Example:
        @from_exception
        def risky_operation(x: int) -> int:
            if x < 0:
                raise ValueError("x must be positive")
            return x * 2

        result = risky_operation(-1)  # Returns Result.fail(Error(...))
    """
    def wrapper(*args, **kwargs) -> Result[T, Error]:
        try:
            value = func(*args, **kwargs)
            return Result.ok(value)
        except Exception as e:
            error = Error(
                message=str(e),
                error_type=ErrorType.INTERNAL,
                cause=e
            )
            return Result.fail(error)
    return wrapper


def collect_results(results: list[Result[T, E]]) -> Result[list[T], E]:
    """
    Collect a list of Results into a Result of list.

    Args:
        results: List of Result objects

    Returns:
        Result.ok with list of values if all successful,
        Result.fail with first error otherwise
    """
    values = []
    for result in results:
        if result.is_err():
            return Result.fail(result.error)
        values.append(result.value)
    return Result.ok(values)


# Example usage for repositories
class RepositoryResult(Result[T, Error]):
    """Specialized Result for repository operations."""

    @classmethod
    def not_found(cls, message: str = "Resource not found") -> "RepositoryResult[T]":
        """Create a NOT_FOUND error result."""
        error = Error(message=message, error_type=ErrorType.NOT_FOUND)
        return cls.fail(error)

    @classmethod
    def database_error(cls, message: str, cause: Optional[Exception] = None) -> "RepositoryResult[T]":
        """Create a DATABASE error result."""
        error = Error(
            message=message,
            error_type=ErrorType.DATABASE,
            cause=cause
        )
        return cls.fail(error)

    @classmethod
    def validation_error(cls, message: str, details: Optional[dict] = None) -> "RepositoryResult[T]":
        """Create a VALIDATION error result."""
        error = Error(
            message=message,
            error_type=ErrorType.VALIDATION,
            details=details
        )
        return cls.fail(error)