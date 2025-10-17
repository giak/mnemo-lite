"""
Context-aware logger for MnemoLite.

Provides structured logging with context without external dependencies.
Simple, pragmatic approach for local applications.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime


class ContextLogger:
    """
    Lightweight context logger that adds contextual information to log messages.

    Example:
        logger = ContextLogger(logging.getLogger(__name__))
        logger = logger.bind(service="embedding", model="nomic")
        logger.info("Processing request")  # Logs: "Processing request [service=embedding model=nomic]"
    """

    def __init__(self, base_logger: logging.Logger, **default_context):
        """
        Initialize context logger.

        Args:
            base_logger: The underlying Python logger
            **default_context: Default context key-value pairs
        """
        self._logger = base_logger
        self._context = default_context or {}

    def bind(self, **kwargs) -> "ContextLogger":
        """
        Create a new logger with additional context.

        Args:
            **kwargs: Additional context key-value pairs

        Returns:
            New ContextLogger instance with merged context
        """
        new_context = {**self._context, **kwargs}
        return ContextLogger(self._logger, **new_context)

    def unbind(self, *keys: str) -> "ContextLogger":
        """
        Create a new logger with specified keys removed from context.

        Args:
            *keys: Context keys to remove

        Returns:
            New ContextLogger instance with keys removed
        """
        new_context = {k: v for k, v in self._context.items() if k not in keys}
        return ContextLogger(self._logger, **new_context)

    def _format_message(self, msg: str) -> str:
        """
        Format message with context.

        Args:
            msg: Original message

        Returns:
            Message with context appended
        """
        if not self._context:
            return msg

        # Format context as key=value pairs
        context_parts = []
        for key, value in sorted(self._context.items()):
            # Handle different value types
            if value is None:
                formatted_value = "null"
            elif isinstance(value, bool):
                formatted_value = "true" if value else "false"
            elif isinstance(value, (int, float)):
                formatted_value = str(value)
            elif isinstance(value, datetime):
                formatted_value = value.isoformat()
            else:
                # String values - quote if contains spaces
                str_value = str(value)
                if " " in str_value or "=" in str_value:
                    formatted_value = f'"{str_value}"'
                else:
                    formatted_value = str_value

            context_parts.append(f"{key}={formatted_value}")

        context_str = " ".join(context_parts)
        return f"{msg} [{context_str}]"

    def _log(self, level: int, msg: str, *args, **kwargs):
        """
        Internal log method.

        Args:
            level: Log level
            msg: Message to log
            *args: Positional arguments for logger
            **kwargs: Keyword arguments for logger
        """
        # Extract exc_info if present
        exc_info = kwargs.pop("exc_info", False)
        extra = kwargs.pop("extra", {})

        # Add context to extra
        extra.update(self._context)

        formatted_msg = self._format_message(msg)
        self._logger.log(level, formatted_msg, *args, exc_info=exc_info, extra=extra, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with context."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message with context."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with context."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message with context."""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with context."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Log exception with context (includes traceback)."""
        kwargs["exc_info"] = True
        self.error(msg, *args, **kwargs)

    def with_time(self, msg: str, start_time: float) -> None:
        """
        Log message with elapsed time.

        Args:
            msg: Message to log
            start_time: Start time from time.time()
        """
        import time
        elapsed_ms = (time.time() - start_time) * 1000
        self.info(f"{msg} [elapsed_ms={elapsed_ms:.2f}]")

    def get_context(self) -> Dict[str, Any]:
        """
        Get current context.

        Returns:
            Current context dictionary
        """
        return self._context.copy()


def get_context_logger(
    name: Optional[str] = None,
    **default_context
) -> ContextLogger:
    """
    Get a context logger instance.

    Args:
        name: Logger name (defaults to __name__ of caller)
        **default_context: Default context for this logger

    Returns:
        ContextLogger instance
    """
    base_logger = logging.getLogger(name or __name__)
    return ContextLogger(base_logger, **default_context)


# Example usage for repositories
def get_repository_logger(repository_name: str) -> ContextLogger:
    """
    Get a logger configured for repository operations.

    Args:
        repository_name: Name of the repository

    Returns:
        Configured ContextLogger
    """
    return get_context_logger(
        f"repository.{repository_name}",
        component="repository",
        repository=repository_name
    )


# Example usage for services
def get_service_logger(service_name: str) -> ContextLogger:
    """
    Get a logger configured for service operations.

    Args:
        service_name: Name of the service

    Returns:
        Configured ContextLogger
    """
    return get_context_logger(
        f"service.{service_name}",
        component="service",
        service=service_name
    )


# Example usage for routes
def get_route_logger(route_name: str, method: str, path: str) -> ContextLogger:
    """
    Get a logger configured for route operations.

    Args:
        route_name: Name of the route/endpoint
        method: HTTP method
        path: URL path

    Returns:
        Configured ContextLogger
    """
    return get_context_logger(
        f"route.{route_name}",
        component="route",
        route=route_name,
        method=method,
        path=path
    )