"""
EPIC-22 Story 22.3: Real-Time Logs Buffer Service

Circular buffer for storing recent log entries to stream via SSE.

Features:
- Thread-safe circular buffer (max 1000 logs)
- Automatic trimming when full
- Format: {"timestamp": ISO, "level": str, "message": str, "metadata": dict}
- Singleton pattern for global access
"""

import structlog
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading

logger = structlog.get_logger()


class LogsBuffer:
    """Thread-safe circular buffer for application logs."""

    def __init__(self, max_size: int = 1000):
        """
        Initialize logs buffer.

        Args:
            max_size: Maximum number of logs to store (default 1000)
        """
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        # BUGFIX: Don't log during initialization to avoid circular dependency with structlog configuration
        # logger.info("LogsBuffer initialized", max_size=max_size)

    def add_log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a log entry to the buffer.

        Args:
            level: Log level (error, warning, info, debug)
            message: Log message
            metadata: Optional metadata dict
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.lower(),
            "message": message,
            "metadata": metadata or {}
        }

        with self.lock:
            self.buffer.append(log_entry)

    def get_recent_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Get the most recent N logs.

        Args:
            count: Number of logs to retrieve (default 100)

        Returns:
            List of log entries (newest first)
        """
        with self.lock:
            # Get last N entries and reverse (newest first)
            logs = list(self.buffer)[-count:]
            logs.reverse()
            return logs

    def get_all_logs(self) -> List[Dict[str, Any]]:
        """
        Get all logs in the buffer.

        Returns:
            List of all log entries (newest first)
        """
        with self.lock:
            logs = list(self.buffer)
            logs.reverse()
            return logs

    def clear(self):
        """Clear all logs from the buffer."""
        with self.lock:
            self.buffer.clear()
            # Note: Logging here is safe after initialization, but commented for consistency
            # logger.info("LogsBuffer cleared")

    def get_size(self) -> int:
        """Get current number of logs in buffer."""
        with self.lock:
            return len(self.buffer)


# Global singleton instance
_logs_buffer_instance: Optional[LogsBuffer] = None
_instance_lock = threading.Lock()


def get_logs_buffer() -> LogsBuffer:
    """
    Get the global LogsBuffer singleton instance.

    Returns:
        LogsBuffer instance
    """
    global _logs_buffer_instance

    if _logs_buffer_instance is None:
        with _instance_lock:
            # Double-check locking
            if _logs_buffer_instance is None:
                _logs_buffer_instance = LogsBuffer(max_size=1000)
                # BUGFIX: Don't log during initialization to avoid circular dependency with structlog configuration
                # logger.info("Global LogsBuffer instance created")

    return _logs_buffer_instance


# Custom structlog processor to feed logs into buffer
def logs_buffer_processor(logger, method_name, event_dict):
    """
    Structlog processor that adds logs to the global buffer.

    This processor should be added to structlog's processor chain to
    automatically capture all application logs.
    """
    # Map structlog log level to our format
    level_map = {
        "debug": "debug",
        "info": "info",
        "warning": "warning",
        "error": "error",
        "critical": "error"
    }

    level = level_map.get(method_name, "info")
    message = event_dict.get("event", "")

    # Extract metadata (all keys except 'event')
    metadata = {k: v for k, v in event_dict.items() if k != "event"}

    # Add to buffer
    buffer = get_logs_buffer()
    buffer.add_log(level=level, message=message, metadata=metadata)

    # Return event_dict unchanged (don't modify logging flow)
    return event_dict
