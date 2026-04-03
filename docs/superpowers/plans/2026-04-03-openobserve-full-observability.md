# OpenObserve Full Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send logs, traces, and metrics from API, MCP, and Worker to OpenObserve via OTLP, with dashboards and alerts configured.

**Architecture:** OpenTelemetry SDK with OTLP HTTP exporters for traces and metrics, plus a custom structlog processor that batches logs and POSTs them to OpenObserve's log ingestion endpoint. All three backend processes (API, MCP, Worker) use the same observability pipeline.

**Tech Stack:** OpenTelemetry Python, structlog, FastAPI instrumentation, Docker Compose, OpenObserve

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `api/requirements.txt` | Modify | Add opentelemetry dependencies |
| `api/utils/otel_config.py` | Create | OpenTelemetry TracerProvider, MeterProvider, OTLP exporters for API |
| `api/utils/otel_log_processor.py` | Create | structlog processor that batches logs → OpenObserve HTTP POST |
| `api/utils/logging_config.py` | Modify | Add OTLP log processor to structlog chain |
| `api/main.py` | Modify | Call `configure_otel()` in lifespan |
| `api/mnemo_mcp/server.py` | Modify | Add OTLP config + log processor |
| `workers/conversation_worker.py` | Modify | Use env vars for credentials instead of hardcoded |
| `docker-compose.yml` | Modify | Add OTLP env vars to API, MCP, Worker; add ZO vars to OpenObserve |
| `scripts/setup_openobserve_dashboards.py` | Create | Script to create dashboards and alerts via OpenObserve API |

---

### Task 1: Add OpenTelemetry Dependencies

**Files:**
- Modify: `api/requirements.txt`

- [ ] **Step 1: Add OpenTelemetry packages to requirements.txt**

Read `api/requirements.txt` and add these lines at the end (before any existing comments):

```
# EPIC-Observability: OpenTelemetry for OpenObserve integration
opentelemetry-api>=1.24.0
opentelemetry-sdk>=1.24.0
opentelemetry-exporter-otlp-proto-http>=1.24.0
opentelemetry-instrumentation-fastapi>=0.45b0
opentelemetry-instrumentation-sqlalchemy>=0.45b0
opentelemetry-instrumentation-redis>=0.45b0
opentelemetry-semantic-conventions>=0.45b0
```

- [ ] **Step 2: Verify requirements.txt is valid**

Run: `pip install --dry-run -r api/requirements.txt` (outside container) or rebuild the container.

- [ ] **Step 3: Commit**

```bash
git add api/requirements.txt
git commit -m "feat: add OpenTelemetry dependencies for OpenObserve integration"
```

---

### Task 2: Create OpenTelemetry Config for API

**Files:**
- Create: `api/utils/otel_config.py`

- [ ] **Step 1: Create the OTLP configuration module**

Create `api/utils/otel_config.py`:

```python
"""
OpenTelemetry Configuration for OpenObserve Integration.

Configures TracerProvider, MeterProvider, and OTLP exporters
for sending traces and metrics to OpenObserve.

Usage:
    from utils.otel_config import configure_otel, shutdown_otel

    # At app startup
    configure_otel(service_name="mnemolite-api")

    # At app shutdown
    shutdown_otel()
"""

import os
import base64
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

from structlog import get_logger

logger = get_logger(__name__)

# Global providers for shutdown
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def _get_otlp_headers() -> dict:
    """Build Basic Auth headers for OpenObserve."""
    user = os.getenv("O2_USER", "admin@mnemolite.local")
    password = os.getenv("O2_PASSWORD", "Complexpass#123")
    auth_string = f"{user}:{password}"
    auth_bytes = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {auth_bytes}"}


def configure_otel(
    service_name: str = "mnemolite-api",
    environment: str = "development",
) -> bool:
    """
    Configure OpenTelemetry with OTLP exporters for OpenObserve.

    Sets up TracerProvider, MeterProvider, and auto-instrumentation
    for FastAPI, SQLAlchemy, and Redis.

    Args:
        service_name: Service name for OpenTelemetry resource
        environment: Deployment environment (development/production)

    Returns:
        True if configured successfully, False if OpenObserve is unreachable
    """
    global _tracer_provider, _meter_provider

    otlp_endpoint = os.getenv(
        "OTLP_ENDPOINT",
        "http://openobserve:5080/api/default/v1/traces"
    )
    otlp_metrics_endpoint = os.getenv(
        "OTLP_METRICS_ENDPOINT",
        "http://openobserve:5080/api/default/v1/metrics"
    )

    otlp_headers = _get_otlp_headers()

    # Create resource
    resource = Resource.create({
        "service.name": service_name,
        "deployment.environment": environment,
    })

    # Configure tracing
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers=otlp_headers,
            )
        )
    )
    trace.set_tracer_provider(_tracer_provider)

    # Configure metrics
    _meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=otlp_metrics_endpoint,
                    headers=otlp_headers,
                ),
                export_interval_millis=5000,
            )
        ],
    )
    metrics.set_meter_provider(_meter_provider)

    # Auto-instrument FastAPI
    try:
        FastAPIInstrumentor.instrument()
        logger.info("otel_fastapi_instrumented")
    except Exception as e:
        logger.warning("otel_fastapi_instrument_failed", error=str(e))

    # Auto-instrument SQLAlchemy
    try:
        SQLAlchemyInstrumentor().instrument()
        logger.info("otel_sqlalchemy_instrumented")
    except Exception as e:
        logger.warning("otel_sqlalchemy_instrument_failed", error=str(e))

    # Auto-instrument Redis
    try:
        RedisInstrumentor().instrument()
        logger.info("otel_redis_instrumented")
    except Exception as e:
        logger.warning("otel_redis_instrument_failed", error=str(e))

    logger.info(
        "opentelemetry_configured",
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
    )

    return True


def shutdown_otel() -> None:
    """
    Shutdown OpenTelemetry providers and flush pending data.

    Call this during application shutdown to ensure all
    telemetry is exported before process exit.
    """
    global _tracer_provider, _meter_provider

    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None

    if _meter_provider:
        _meter_provider.shutdown()
        _meter_provider = None

    logger.info("opentelemetry_shutdown")
```

- [ ] **Step 2: Commit**

```bash
git add api/utils/otel_config.py
git commit -m "feat: add OpenTelemetry configuration module for API"
```

---

### Task 3: Create structlog Processor for OpenObserve Logs

**Files:**
- Create: `api/utils/otel_log_processor.py`

- [ ] **Step 1: Create the log batching processor**

Create `api/utils/otel_log_processor.py`:

```python
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
        """
        Initialize log processor.

        Args:
            endpoint: OpenObserve log ingestion URL
            batch_size: Number of logs before forced flush
            flush_interval: Seconds between automatic flushes
        """
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

        # Build auth headers
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

        # Final flush
        await self._flush()

        if self._client:
            await self._client.aclose()

        logger.info("openobserve_log_processor_stopped")

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        structlog processor interface.

        Adds the log event to the buffer (non-blocking).
        The background task handles actual HTTP delivery.

        Returns event_dict unchanged (so it continues through the chain).
        """
        # Create a copy to avoid mutation issues
        log_entry = dict(event_dict)
        log_entry["_level"] = method_name

        # Schedule add to buffer (fire-and-forget)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._add_to_buffer(log_entry))
        except RuntimeError:
            # No running event loop (e.g., during shutdown) — skip
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
            # OpenObserve accepts JSON array of log objects
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
            # Silently drop logs if OpenObserve is unreachable
            logger.debug("openobserve_log_flush_failed", error=str(e))


# Singleton instance
_log_processor: Optional[OpenObserveLogProcessor] = None


def get_log_processor() -> OpenObserveLogProcessor:
    """Get or create the singleton log processor."""
    global _log_processor
    if _log_processor is None:
        _log_processor = OpenObserveLogProcessor()
    return _log_processor
```

- [ ] **Step 2: Commit**

```bash
git add api/utils/otel_log_processor.py
git commit -m "feat: add structlog processor for OpenObserve log ingestion"
```

---

### Task 4: Wire OTLP into API Lifespan

**Files:**
- Modify: `api/main.py`
- Modify: `api/utils/logging_config.py`

- [ ] **Step 1: Modify logging_config.py to include OTLP log processor**

Read `api/utils/logging_config.py`. Modify the `configure_logging()` function to add the OpenObserve log processor:

```python
def configure_logging():
    """
    Configure structlog with trace_id propagation and OpenObserve log ingestion.
    """
    from services.logs_buffer import logs_buffer_processor
    from utils.otel_log_processor import get_log_processor

    # Get singleton log processor and start it
    log_processor = get_log_processor()

    structlog.configure(
        processors=[
            # Add trace_id from contextvars
            add_trace_id_processor,

            # Add logs to buffer for SSE streaming
            logs_buffer_processor,

            # Send logs to OpenObserve (non-blocking, fire-and-forget)
            log_processor,

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
```

- [ ] **Step 2: Modify main.py lifespan to configure OTEL**

In `api/main.py`, add OTLP configuration at the start of lifespan (right after `configure_logging()`):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # EPIC-22 Story 22.6: Configure logging with trace_id propagation
    from utils.logging_config import configure_logging
    configure_logging()

    # OpenObserve: Configure OpenTelemetry (traces + metrics)
    from utils.otel_config import configure_otel, shutdown_otel
    from utils.otel_log_processor import get_log_processor

    configure_otel(
        service_name="mnemolite-api",
        environment=ENVIRONMENT,
    )

    # Start log processor background task
    log_processor = get_log_processor()
    await log_processor.start()

    # ... rest of existing lifespan code ...
```

- [ ] **Step 3: Modify main.py shutdown to flush OTLP**

In the shutdown section of lifespan (the `except`/`finally` block after `yield`), add:

```python
    # Shutdown OpenTelemetry
    shutdown_otel()

    # Stop log processor
    log_processor = get_log_processor()
    await log_processor.shutdown()
```

Find the existing cleanup code (where `alert_monitoring_task` is cancelled, engine is disposed, etc.) and add the OTLP shutdown calls before the existing cleanup.

- [ ] **Step 4: Commit**

```bash
git add api/utils/logging_config.py api/main.py
git commit -m "feat: wire OpenTelemetry and OpenObserve log processor into API lifespan"
```

---

### Task 5: Add OTLP to MCP Server

**Files:**
- Modify: `api/mnemo_mcp/server.py`

- [ ] **Step 1: Add OTLP imports and configuration to MCP server**

In `api/mnemo_mcp/server.py`, after the existing structlog configuration (around line 96), add OTLP imports:

```python
import os
import base64
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
```

- [ ] **Step 2: Add OTLP config function to MCP server**

Add this function before `server_lifespan`:

```python
def _configure_mcp_otel():
    """Configure OpenTelemetry for MCP server."""
    otlp_endpoint = os.getenv(
        "OTLP_ENDPOINT",
        "http://openobserve:5080/api/default/v1/traces"
    )
    otlp_metrics_endpoint = os.getenv(
        "OTLP_METRICS_ENDPOINT",
        "http://openobserve:5080/api/default/v1/metrics"
    )

    user = os.getenv("O2_USER", "admin@mnemolite.local")
    password = os.getenv("O2_PASSWORD", "Complexpass#123")
    auth_string = f"{user}:{password}"
    auth_bytes = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
    otlp_headers = {"Authorization": f"Basic {auth_bytes}"}

    resource = Resource.create({
        "service.name": "mnemolite-mcp",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    trace.set_tracer_provider(TracerProvider(resource=resource))
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_endpoint, headers=otlp_headers)
        )
    )

    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=otlp_metrics_endpoint,
                    headers=otlp_headers,
                ),
                export_interval_millis=5000,
            )
        ],
    ))

    logger.info("mcp_opentelemetry_configured", otlp_endpoint=otlp_endpoint)
```

- [ ] **Step 3: Call OTLP config in server_lifespan**

In `server_lifespan`, at the very start (before database initialization), add:

```python
@asynccontextmanager
async def server_lifespan(mcp: FastMCP) -> AsyncGenerator[None, None]:
    # Configure OpenTelemetry
    _configure_mcp_otel()

    # ... rest of existing startup code ...
```

- [ ] **Step 4: Add OTLP shutdown at end of lifespan**

In the shutdown section of `server_lifespan` (after `yield`, in the cleanup block):

```python
    # Shutdown OpenTelemetry
    try:
        trace.get_tracer_provider().shutdown()
        metrics.get_meter_provider().shutdown()
        logger.info("mcp_opentelemetry_shutdown")
    except Exception as e:
        logger.warning("mcp_otel_shutdown_error", error=str(e))
```

- [ ] **Step 5: Commit**

```bash
git add api/mnemo_mcp/server.py
git commit -m "feat: add OpenTelemetry to MCP server for OpenObserve integration"
```

---

### Task 6: Fix Worker Credentials (use env vars)

**Files:**
- Modify: `workers/conversation_worker.py`

- [ ] **Step 1: Replace hardcoded credentials with env vars**

In `workers/conversation_worker.py`, find lines 294-298:

```python
    # OpenObserve authentication
    import base64
    auth_string = "admin@mnemolite.local:Complexpass#123"
    auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    otlp_headers = {"Authorization": f"Basic {auth_bytes}"}
```

Replace with:

```python
    # OpenObserve authentication
    import base64
    o2_user = os.getenv("O2_USER", "admin@mnemolite.local")
    o2_password = os.getenv("O2_PASSWORD", "Complexpass#123")
    auth_string = f"{o2_user}:{o2_password}"
    auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    otlp_headers = {"Authorization": f"Basic {auth_bytes}"}
```

- [ ] **Step 2: Commit**

```bash
git add workers/conversation_worker.py
git commit -m "fix: use env vars for OpenObserve credentials in worker"
```

---

### Task 7: Update docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add OTLP environment variables to API service**

In the `api` service's `environment` block, add:

```yaml
      - OTLP_ENDPOINT=http://openobserve:5080/api/default/v1/traces
      - OTLP_METRICS_ENDPOINT=http://openobserve:5080/api/default/v1/metrics
      - OTLP_LOGS_ENDPOINT=http://openobserve:5080/api/default/logs/_json
      - O2_USER=${O2_USER:-admin@mnemolite.local}
      - O2_PASSWORD=${O2_PASSWORD:-Complexpass#123}
```

- [ ] **Step 2: Add OTLP environment variables to MCP service**

In the `mcp` service's `environment` block, add:

```yaml
      - OTLP_ENDPOINT=http://openobserve:5080/api/default/v1/traces
      - OTLP_METRICS_ENDPOINT=http://openobserve:5080/api/default/v1/metrics
      - OTLP_LOGS_ENDPOINT=http://openobserve:5080/api/default/logs/_json
      - O2_USER=${O2_USER:-admin@mnemolite.local}
      - O2_PASSWORD=${O2_PASSWORD:-Complexpass#123}
```

- [ ] **Step 3: Add OTLP environment variables to Worker service**

In the `worker` service's `environment` block, add:

```yaml
      - OTLP_ENDPOINT=http://openobserve:5080/api/default/v1/traces
      - OTLP_METRICS_ENDPOINT=http://openobserve:5080/api/default/v1/metrics
      - OTLP_LOGS_ENDPOINT=http://openobserve:5080/api/default/logs/_json
      - O2_USER=${O2_USER:-admin@mnemolite.local}
      - O2_PASSWORD=${O2_PASSWORD:-Complexpass#123}
```

- [ ] **Step 4: Add OpenObserve configuration variables**

In the `openobserve` service's `environment` block, add:

```yaml
      - ZO_INGEST_ALLOWED_IPS=0.0.0.0/0
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add OTLP environment variables to all services"
```

---

### Task 8: Build and Test Telemetry Flow

**Files:**
- No file changes — this is a verification task

- [ ] **Step 1: Rebuild containers**

```bash
make build
```

- [ ] **Step 2: Start services**

```bash
make up
```

- [ ] **Step 3: Verify OpenObserve is running**

```bash
curl -u "admin@mnemolite.local:Complexpass#123" http://localhost:5080/config
```

Expected: JSON response with OpenObserve configuration.

- [ ] **Step 4: Check API startup logs for OTLP confirmation**

```bash
docker logs mnemo-api 2>&1 | grep -i "opentelemetry_configured"
```

Expected: Log entry showing `opentelemetry_configured` with endpoint.

- [ ] **Step 5: Check MCP startup logs for OTLP confirmation**

```bash
docker logs mnemo-mcp 2>&1 | grep -i "opentelemetry_configured"
```

Expected: Log entry showing `mcp_opentelemetry_configured`.

- [ ] **Step 6: Generate some traffic**

```bash
curl http://localhost:8001/health
curl http://localhost:8001/api/v1/memories
```

- [ ] **Step 7: Verify traces in OpenObserve**

Open http://localhost:5080 in browser, login with `admin@mnemolite.local` / `Complexpass#123`, navigate to Traces, and verify traces from `mnemolite-api` and `mnemolite-mcp` appear.

- [ ] **Step 8: Verify logs in OpenObserve**

In OpenObserve UI, navigate to Logs, select stream `default`, and verify log entries from the API and MCP appear.

- [ ] **Step 9: Verify metrics in OpenObserve**

In OpenObserve UI, navigate to Metrics, and verify metrics from all three services appear.

- [ ] **Step 10: Commit (no changes needed if all passes)**

---

### Task 9: Create OpenObserve Dashboards Setup Script

**Files:**
- Create: `scripts/setup_openobserve_dashboards.py`

- [ ] **Step 1: Create the dashboard setup script**

Create `scripts/setup_openobserve_dashboards.py`:

```python
"""
OpenObserve Dashboard & Alert Setup Script.

Creates dashboards and alerts in OpenObserve via its REST API.
Run after OpenObserve is up and running.

Usage:
    python scripts/setup_openobserve_dashboards.py

Environment:
    O2_URL: OpenObserve base URL (default: http://localhost:5080)
    O2_USER: OpenObserve user email (default: admin@mnemolite.local)
    O2_PASSWORD: OpenObserve password (default: Complexpass#123)
"""

import os
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from base64 import b64encode

O2_URL = os.getenv("O2_URL", "http://localhost:5080")
O2_USER = os.getenv("O2_USER", "admin@mnemolite.local")
O2_PASSWORD = os.getenv("O2_PASSWORD", "Complexpass#123")
ORG = "default"

auth_string = f"{O2_USER}:{O2_PASSWORD}"
auth_bytes = b64encode(auth_string.encode("utf-8")).decode("utf-8")
HEADERS = {
    "Authorization": f"Basic {auth_bytes}",
    "Content-Type": "application/json",
}


def api_call(method: str, path: str, payload: dict | None = None) -> dict | None:
    """Make an authenticated API call to OpenObserve."""
    url = f"{O2_URL}/api/{ORG}{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ⚠ {method} {path} → {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  ✗ {method} {path} → {e}")
        return None


def create_dashboard(name: str, description: str, panels: list[dict]) -> None:
    """Create a dashboard in OpenObserve."""
    payload = {
        "title": name,
        "description": description,
        "role": "",
        "owner": "admin@mnemolite.local",
        "created": "2026-04-03T00:00:00Z",
        "updated": "2026-04-03T00:00:00Z",
        "type": "dashboards",
        "kind": "dashboards",
        "panels": panels,
        "variables": {},
        "layout": {"type": "absolute", "panels": []},
    }
    result = api_call("POST", "/dashboards", payload)
    if result:
        print(f"  ✓ Dashboard created: {name}")
    else:
        print(f"  ⚠ Dashboard may already exist: {name}")


def create_alert(name: str, query: str, condition: str, severity: str, cooldown: int) -> None:
    """Create an alert in OpenObserve."""
    payload = {
        "name": name,
        "stream_type": "logs",
        "stream_name": "default",
        "is_real_time": True,
        "query_condition": {
            "conditions": [
                {
                    "column": "_timestamp",
                    "operator": ">=",
                    "value": 5,
                }
            ],
            "sql": query,
        },
        "trigger_condition": {
            "period": 5,
            "threshold": int(condition.split(">")[1]) if ">" in condition else 1,
            "silence": cooldown,
            "operator": ">=",
        },
        "alert_type": "alert",
        "enabled": True,
        "severity": severity,
    }
    result = api_call("POST", "/alerts", payload)
    if result:
        print(f"  ✓ Alert created: {name}")
    else:
        print(f"  ⚠ Alert may already exist: {name}")


def main():
    print("=" * 60)
    print("OpenObserve Dashboard & Alert Setup")
    print(f"Target: {O2_URL}")
    print("=" * 60)

    # Dashboard 1: API Performance
    print("\n📊 Creating dashboards...")
    create_dashboard(
        name="API Performance",
        description="Request latency, error rates, and cache performance for MnemoLite API",
        panels=[
            {
                "id": "panel_1",
                "type": "line",
                "title": "Request Latency (p50/p95/p99)",
                "query": "SELECT histogram(_timestamp) as x_axis, avg(duration) as p50, percentile_cont(0.95) WITHIN GROUP (ORDER BY duration) as p95, percentile_cont(0.99) WITHIN GROUP (ORDER BY duration) as p99 FROM \"mnemolite-api\" WHERE http_method IS NOT NULL GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "panel_2",
                "type": "bar",
                "title": "Error Rate (5xx)",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as errors FROM \"mnemolite-api\" WHERE http_status_code >= 500 GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "panel_3",
                "type": "gauge",
                "title": "Cache Hit Rate",
                "query": "SELECT avg(cache_hit) * 100 as hit_rate FROM \"mnemolite-api\" WHERE cache_hit IS NOT NULL",
            },
        ],
    )

    # Dashboard 2: MCP Operations
    create_dashboard(
        name="MCP Operations",
        description="Tool invocations, search latency, and indexing throughput",
        panels=[
            {
                "id": "panel_1",
                "type": "bar",
                "title": "Tool Invocations by Name",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as count FROM \"mnemolite-mcp\" WHERE tool_name IS NOT NULL GROUP BY x_axis, tool_name ORDER BY x_axis",
            },
            {
                "id": "panel_2",
                "type": "line",
                "title": "Search Query Latency",
                "query": "SELECT histogram(_timestamp) as x_axis, avg(duration) as avg_latency FROM \"mnemolite-mcp\" WHERE operation = 'search' GROUP BY x_axis ORDER BY x_axis",
            },
        ],
    )

    # Dashboard 3: Worker Health
    create_dashboard(
        name="Worker Health",
        description="Conversation processing metrics and Redis Stream lag",
        panels=[
            {
                "id": "panel_1",
                "type": "line",
                "title": "Messages Processed vs Failed",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as total FROM \"conversation-worker\" GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "panel_2",
                "type": "line",
                "title": "Processing Duration",
                "query": "SELECT histogram(_timestamp) as x_axis, avg(duration_ms) as avg_duration FROM \"conversation-worker\" WHERE duration_ms IS NOT NULL GROUP BY x_axis ORDER BY x_axis",
            },
        ],
    )

    # Alerts
    print("\n🔔 Creating alerts...")
    create_alert(
        name="High API Error Rate",
        query="SELECT count(*) as error_count FROM \"mnemolite-api\" WHERE http_status_code >= 500",
        condition="error_count > 10",
        severity="critical",
        cooldown=300,
    )

    create_alert(
        name="High API Latency",
        query="SELECT avg(duration) as avg_latency FROM \"mnemolite-api\" WHERE http_method IS NOT NULL",
        condition="avg_latency > 2000",
        severity="warning",
        cooldown=300,
    )

    create_alert(
        name="Low Cache Hit Rate",
        query="SELECT avg(cache_hit) * 100 as hit_rate FROM \"mnemolite-api\" WHERE cache_hit IS NOT NULL",
        condition="hit_rate < 80",
        severity="warning",
        cooldown=900,
    )

    create_alert(
        name="Worker Processing Failures",
        query="SELECT count(*) as failures FROM \"conversation-worker\" WHERE status = 'failed'",
        condition="failures > 10",
        severity="critical",
        cooldown=300,
    )

    print("\n" + "=" * 60)
    print("Setup complete! Check OpenObserve UI at " + O2_URL)
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

```bash
docker compose exec api python scripts/setup_openobserve_dashboards.py
```

Or from host:
```bash
O2_URL=http://localhost:5080 python scripts/setup_openobserve_dashboards.py
```

- [ ] **Step 3: Verify in OpenObserve UI**

Open http://localhost:5080, navigate to Dashboards and Alerts, verify all dashboards and alerts were created.

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_openobserve_dashboards.py
git commit -m "feat: add OpenObserve dashboard and alert setup script"
```

---

### Task 10: Final Verification & Cleanup

**Files:**
- No new files — verification task

- [ ] **Step 1: Run full rebuild**

```bash
make down && make build && make up
```

- [ ] **Step 2: Verify all services healthy**

```bash
docker compose ps
curl http://localhost:8001/health
```

- [ ] **Step 3: Generate traffic across all services**

```bash
# API
curl http://localhost:8001/health
curl http://localhost:8001/api/v1/memories?limit=1

# MCP
curl http://localhost:8002/mcp
```

- [ ] **Step 4: Verify telemetry in OpenObserve**

Check OpenObserve UI (http://localhost:5080):
- Logs: Should see entries from `mnemolite-api`, `mnemolite-mcp`, `conversation-worker`
- Traces: Should see spans from API requests and MCP tool invocations
- Metrics: Should see custom metrics from all three services
- Dashboards: 3 dashboards created (API Performance, MCP Operations, Worker Health)
- Alerts: 4 alerts created (High Error Rate, High Latency, Low Cache Hit Rate, Worker Failures)

- [ ] **Step 5: Final commit (if any cleanup needed)**

```bash
git status
# If any changes needed, commit them
```
