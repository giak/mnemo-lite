"""
EPIC-22 Story 22.6: Logging Configuration with trace_id Propagation

Configures structlog with automatic trace_id injection using contextvars.

Features:
- contextvars for thread-safe trace_id storage
- Automatic trace_id injection in all logs
- Integration with LogsBuffer for SSE streaming

Usage:
    from utils.logging_config import configure_logging, trace_id_var

    # Configure at app startup
    configure_logging()

    # Set trace_id in middleware
    trace_id_var.set("a1b2c3d4-...")

    # All subsequent logs will have trace_id automatically
    logger.info("Processing request")  # → {trace_id: "a1b2c3d4-...", ...}
"""

import contextvars
import structlog
from typing import Any, Dict

# Global contextvar for trace_id (thread-safe, request-scoped)
trace_id_var = contextvars.ContextVar('trace_id', default=None)


def add_trace_id_processor(logger, method_name, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Structlog processor that adds trace_id to all log entries.

    Retrieves trace_id from contextvars (set by MetricsMiddleware) and
    injects it into event_dict so it appears in all logs.

    Args:
        logger: Structlog logger instance
        method_name: Log level method name (info, error, etc.)
        event_dict: Event dictionary to enrich

    Returns:
        Enriched event_dict with trace_id field

    Note:
        This processor runs for EVERY log call, so it must be fast.
        contextvars.ContextVar.get() is O(1) and thread-safe.
    """
    trace_id = trace_id_var.get()
    if trace_id:
        event_dict['trace_id'] = trace_id

    return event_dict


def configure_logging():
    """
    Configure structlog with trace_id propagation.

    Adds trace_id processor to structlog's processor chain.
    This should be called once at application startup (in main.py lifespan).

    Note:
        structlog uses a global configuration, so this only needs to be
        called once. All subsequent structlog.get_logger() calls will
        use this configuration.
    """
    # Import logs_buffer_processor to add logs to buffer
    from services.logs_buffer import logs_buffer_processor

    structlog.configure(
        processors=[
            # Add trace_id from contextvars (MUST be first to propagate to all processors)
            add_trace_id_processor,

            # Add logs to buffer for SSE streaming (before rendering)
            logs_buffer_processor,

            # Structlog default processors
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,

            # Renderer (last processor)
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
