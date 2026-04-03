"""
structlog Processor for OpenObserve Log Ingestion.

Batches structured logs and sends them to OpenObserve via HTTP POST.
Runs as a background asyncio task to avoid blocking request handling.

Usage:
    from utils.otel_log_processor import OpenObserveLogProcessor

    # Create processor (called once at startup)
    processor = OpenObserveLogProcessor()

    # Add to structlog processor chain
    structlog.configure(processors=[processor, ...])

    # Shutdown at app exit
    await processor.shutdown()
"""

import asyncio
import os
import base64
import json
from typing import Any, Dict, List, Optional

import httpx
from structlog import get_logger

logger = get_logger(__name__)


class OpenObserveLogProcessor:
    """
    Batches structlog events and sends them to OpenObserve.

    Collects log events and flushes them in batches to OpenObserve's
    log ingestion endpoint. Non-blocking: runs a background task
    that flushes every 5 seconds or when batch size reaches 50.

    If OpenObserve is unreachable, logs are silently dropped
    (observability should never break the application).
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        batch_size: int = 50,
        flush_interval: float = 5.0,
    ):
        self.endpoint = endpoint or os.getenv(
            "OTLP_LOGS_ENDPOINT",
            "http://openobserve:5080/api/default/logs/_json",
        )
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer: List[Dict[str, Any]] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

        user = os.getenv("O2_USER", "admin@mnemolite.local")
        password = os.getenv("O2_PASSWORD", "Complexpass#123")
        auth_string = f"{user}:{password}"
        auth_bytes = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        self._headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Content-Type": "application/json",
        }

    async def start(self) -> None:
        """Start the background flush task."""
        if self._running:
            return

        self._running = True
        self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("openobserve_log_processor_started", endpoint=self.endpoint)

    async def shutdown(self) -> None:
        """Stop the flush task and send remaining logs."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._flush()

        if self._client:
            await self._client.aclose()

        logger.info("openobserve_log_processor_stopped")

    def __call__(
        self,
        logger_instance: Any,
        method_name: str,
        event_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        structlog processor interface.

        Adds the log event to the buffer (non-blocking).
        The background task handles actual HTTP delivery.

        Returns event_dict unchanged (so it continues through the chain).
        """
        log_entry = dict(event_dict)
        log_entry["_level"] = method_name

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._add_to_buffer(log_entry))
        except RuntimeError:
            pass

        return event_dict

    async def _add_to_buffer(self, log_entry: Dict[str, Any]) -> None:
        """Add log entry to buffer and flush if batch is full."""
        async with self._lock:
            self._buffer.append(log_entry)
            if len(self._buffer) >= self.batch_size:
                await self._flush()

    async def _flush_loop(self) -> None:
        """Background loop that flushes the buffer periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                if self._buffer:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("openobserve_log_flush_error", error=str(e))

    async def _flush(self) -> None:
        """Send buffered logs to OpenObserve."""
        async with self._lock:
            if not self._buffer:
                return

            batch = self._buffer[:]
            self._buffer.clear()

        if not self._client:
            return

        try:
            payload = json.dumps(batch)
            response = await self._client.post(
                self.endpoint,
                content=payload,
                headers=self._headers,
            )
            if response.status_code not in (200, 201, 204):
                logger.warning(
                    "openobserve_log_ingest_error",
                    status=response.status_code,
                    body=response.text[:200],
                )
        except Exception as e:
            logger.debug("openobserve_log_flush_failed", error=str(e))


_log_processor: Optional[OpenObserveLogProcessor] = None


def get_log_processor() -> OpenObserveLogProcessor:
    """Get or create the singleton log processor."""
    global _log_processor
    if _log_processor is None:
        _log_processor = OpenObserveLogProcessor()
    return _log_processor
