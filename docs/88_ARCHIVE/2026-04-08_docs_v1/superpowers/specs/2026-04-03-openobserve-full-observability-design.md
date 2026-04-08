# OpenObserve Full Observability Design

> **Status:** DRAFT | **Date:** 2026-04-03 | **Author:** giak

## Problem Statement

MnemoLite has OpenObserve deployed but only the Worker sends telemetry to it. The API and MCP server have zero observability integration with OpenObserve. No dashboards, alerts, or pipelines are configured.

## Architecture

### Current State
- OpenObserve runs on `:5080` (docker-compose.yml)
- Worker sends traces + metrics via OTLP (conversation_worker.py)
- API uses structlog (JSONRenderer) but sends nothing to OpenObserve
- MCP uses structlog but sends nothing to OpenObserve
- No dashboards, alerts, or pipelines configured

### Target State
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Vue 3 SPA │───▶│  FastAPI    │───▶│ PostgreSQL  │
│  (port 3000)│    │  (port 8001)│    │   (port 5432)│
└─────────────┘    └──────┬──────┘    └─────────────┘
                          │
                    ┌─────┴─────┐    ┌─────────────┐
                    │    MCP    │    │   Redis 7   │
                    │(port 8002)│    │  (port 6379) │
                    └─────┬─────┘    └─────────────┘
                          │
                    ┌─────┴─────┐    ┌─────────────┐
                    │  Worker   │───▶│ OpenObserve │
                    │(Redis)    │    │  (port 5080) │
                    └───────────┘    └─────────────┘
```

All three backend processes (API, MCP, Worker) send logs, traces, and metrics to OpenObserve via OTLP.

## Components

### 1. API — OpenTelemetry Integration

#### 1.1 Dependencies (api/requirements.txt)
```
opentelemetry-api>=1.24.0
opentelemetry-sdk>=1.24.0
opentelemetry-exporter-otlp-proto-http>=1.24.0
opentelemetry-instrumentation-fastapi>=0.45b0
opentelemetry-instrumentation-sqlalchemy>=0.45b0
opentelemetry-instrumentation-redis>=0.45b0
```

#### 1.2 New File: api/utils/otel_config.py
- Configures TracerProvider, MeterProvider
- OTLP exporters for traces → `http://openobserve:5080/api/default/v1/traces`
- OTLP exporters for metrics → `http://openobserve:5080/api/default/v1/metrics`
- Auto-instrumentation: FastAPI, SQLAlchemy, Redis
- Resource: `service.name=mnemolite-api`, `deployment.environment=development|production`
- Auth: Basic auth from env vars `O2_USER` and `O2_PASSWORD`

#### 1.3 Logs → OpenObserve
- Add structlog processor that batches logs and POSTs to OpenObserve
- Endpoint: `http://openobserve:5080/api/default/logs/_json`
- Batch: 50 logs or 5s interval (async background task)
- Graceful degradation: if OpenObserve is down, logs are dropped (non-blocking)

#### 1.4 main.py lifespan
- Call `configure_otel()` at startup (before database initialization)
- Pass credentials from env vars

### 2. MCP — OpenTelemetry Integration

#### 2.1 api/mnemo_mcp/server.py
- Same OTLP config as Worker
- Resource: `service.name=mnemo-mcp`
- Traces + metrics → OpenObserve
- Logs via same structlog processor as API

### 3. docker-compose.yml — Environment Variables

#### 3.1 OpenObserve service
```yaml
environment:
  - ZO_ROOT_USER_EMAIL=admin@mnemolite.local
  - ZO_ROOT_USER_PASSWORD=Complexpass#123
  - ZO_DATA_DIR=/data
  - ZO_INGEST_ALLOWED_IPS=0.0.0.0/0
  - ZO_HTTP_PORT=5080
```

#### 3.2 API/MCP/Worker services
```yaml
environment:
  - OTLP_ENDPOINT=http://openobserve:5080/api/default/v1/traces
  - OTLP_METRICS_ENDPOINT=http://openobserve:5080/api/default/v1/metrics
  - OTLP_LOGS_ENDPOINT=http://openobserve:5080/api/default/logs/_json
  - O2_USER=admin@mnemolite.local
  - O2_PASSWORD=Complexpass#123
```

### 4. OpenObserve Dashboards & Alerts

#### 4.1 Dashboard: API Performance
- Request latency (p50, p95, p99) by endpoint
- Error rate (5xx responses)
- Cache hit rate (L1/L2/L3)
- Embedding generation duration
- Database query duration

#### 4.2 Dashboard: MCP Operations
- Tool invocation count and duration
- Search query latency
- Indexing throughput (files/minute)
- Memory usage by operation type

#### 4.3 Dashboard: Worker Health
- Messages processed/failed per minute
- Redis Stream lag
- Processing duration histogram
- API response time from worker perspective

#### 4.4 Alerts
| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | 5xx rate > 5% over 5 min | Critical |
| High Latency | p99 latency > 2s over 5 min | Warning |
| Low Cache Hit Rate | Combined cache hit < 80% over 15 min | Warning |
| Worker Failures | Failed messages > 10 over 5 min | Critical |
| DB Connection Pool | Active connections > 80% of pool | Warning |

## Error Handling

- **OpenObserve down:** OTLP exporters have built-in retry with exponential backoff. After max retries, telemetry is dropped (non-blocking).
- **Auth failure:** Log warning at startup, continue without telemetry.
- **Batch log processor:** If HTTP POST fails, logs are dropped (acceptable for observability).

## Testing

- Verify OTLP exporters connect to OpenObserve on startup
- Verify traces appear in OpenObserve UI after API requests
- Verify metrics appear in OpenObserve UI
- Verify logs appear in OpenObserve UI
- Test graceful degradation when OpenObserve is unavailable

## Rollout Plan

1. Add dependencies and OTLP config to API
2. Add OTLP config to MCP
3. Update docker-compose.yml with env vars
4. Test telemetry flow (API → OpenObserve)
5. Create dashboards in OpenObserve UI
6. Configure alerts in OpenObserve UI
7. Verify end-to-end observability
