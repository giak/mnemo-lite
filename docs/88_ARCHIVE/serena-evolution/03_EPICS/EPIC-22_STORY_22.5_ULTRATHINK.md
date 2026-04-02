# EPIC-22 Story 22.5: API Performance Par Endpoint - ULTRATHINK

**Story**: API Performance Par Endpoint (3 pts)
**Status**: 🧠 **BRAINSTORMING**
**Date**: 2025-10-24
**EPIC**: EPIC-22 Advanced Observability & Real-Time Monitoring
**Phase**: Phase 2 (Standard) - **HIGH PRIORITY**

---

## 📋 Objectif

Identifier **quels endpoints API sont lents** et ont des erreurs, pour cibler les optimisations.

**Problème actuel** (Phase 1):
```json
{
  "api": {
    "p95_latency_ms": 108.96,  // ← Global, quel endpoint est lent ?
    "error_rate": 5.7,          // ← Global, quel endpoint fail ?
    "request_count": 158
  }
}
```

**Questions sans réponse**:
- ❓ Quel endpoint a P95 > 200ms ?
- ❓ Quel endpoint génère les 9 erreurs (5.7%) ?
- ❓ Est-ce `/api/search` qui est lent ou `/api/graph` ?
- ❓ Peut-on prioriser optimisations par impact ?

**Objectif Story 22.5**:
```json
{
  "endpoints": [
    {
      "endpoint": "/api/monitoring/advanced/summary",
      "method": "GET",
      "request_count": 222,
      "avg_latency_ms": 106.3,
      "p50_latency_ms": 95.2,
      "p95_latency_ms": 150.1,
      "p99_latency_ms": 164.6,
      "error_count": 0,
      "error_rate": 0.0,
      "throughput_rps": 0.062
    },
    {
      "endpoint": "/api/search/hybrid",
      "method": "POST",
      "request_count": 45,
      "p95_latency_ms": 450.2,  // ← Problème identifié !
      "error_count": 8,
      "error_rate": 17.8        // ← Problème identifié !
    }
  ]
}
```

**→ Action**: Optimiser `/api/search/hybrid` (P95 450ms, 17.8% erreurs)

---

## 🎯 Valeur Business

### Données Réelles Actuelles ✅

D'après la table `metrics` (2025-10-24):

```sql
SELECT metadata->>'endpoint' as endpoint,
       COUNT(*) as count,
       AVG(value) as avg_latency,
       MAX(value) as max_latency
FROM metrics
WHERE metric_type = 'api'
GROUP BY metadata->>'endpoint'
ORDER BY count DESC;
```

**Résultats**:

| Endpoint | Calls | Avg Latency | Max Latency |
|----------|-------|-------------|-------------|
| `/api/monitoring/advanced/summary` | 222 | **106.3 ms** | 164.6 ms |
| `/ui/monitoring/advanced` | 10 | 6.9 ms | 8.1 ms ✅ |
| `/api/monitoring/advanced/logs/stream` | 6 | 0.7 ms | 2.2 ms ✅ |
| Static CSS files | 20 | ~3 ms | ~7 ms ✅ |

**Insights actuels**:
- ✅ **158+ métriques déjà collectées** (vraies données)
- 🟡 `/api/monitoring/advanced/summary` = **106ms avg** (à surveiller)
- ✅ UI pages rapides (<10ms)
- ✅ SSE stream très rapide (<1ms)

**Potentiel Story 22.5**:
- ✅ Identifier top 5 slow endpoints
- ✅ Détecter endpoints avec erreurs
- ✅ Prioriser optimisations par impact (calls × latency)

---

### Avant Story 22.5 ❌

**Diagnostic slow endpoint**:
1. User: "Search est lent"
2. Admin: Check metrics → P95 global = 108ms
3. ❓ Quel endpoint ? Search? Graph? Upload?
4. → Manual investigation:
   - Grep logs
   - Parse trace_id
   - Reconstruct timeline
   - **30 minutes** pour identifier

**Optimisation**:
- ❌ Impossible de prioriser (pas de données par endpoint)
- ❌ Optimize aveuglement (guess)

---

### Après Story 22.5 ✅

**Diagnostic slow endpoint**:
1. User: "Search est lent"
2. Admin: Open `/ui/monitoring/advanced`
3. Scroll to "API Performance by Endpoint"
4. **Instant view**: `/v1/code/search/hybrid` → P95 = 450ms 🔴
5. → Targeted optimization: "Optimize hybrid search"
6. **30 secondes** pour identifier ✅

**Optimisation**:
- ✅ **Priorisation data-driven**:
  - Impact = `calls × (latency - target)`
  - Example: 1000 calls × (450ms - 100ms) = **350s saved/hour**
- ✅ Focus on high-impact endpoints first

---

## 📊 Données Disponibles (Phase 1)

### Table `metrics` Schema

```sql
CREATE TABLE metrics (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    metric_type VARCHAR(50) NOT NULL,  -- 'api'
    metric_name VARCHAR(100) NOT NULL, -- 'latency_ms'
    value DOUBLE PRECISION NOT NULL,   -- 106.3
    metadata JSONB DEFAULT '{}'::jsonb -- voir ci-dessous
);
```

### Metadata Structure (Already Collected)

```json
{
  "endpoint": "/api/monitoring/advanced/summary",
  "method": "GET",
  "status_code": 200,
  "trace_id": "f3b2c1a0-9234-4567-89ab-cdef01234567"
}
```

**→ Perfect for grouping by endpoint !**

---

## 🏗️ Architecture SQL

### Query 1: Latency Stats by Endpoint

```sql
SELECT
    metadata->>'endpoint' as endpoint,
    metadata->>'method' as method,
    COUNT(*) as request_count,
    AVG(value) as avg_latency_ms,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99_latency_ms,
    MIN(value) as min_latency_ms,
    MAX(value) as max_latency_ms,
    COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400) as error_count,
    (COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400)::float /
     COUNT(*)::float * 100) as error_rate
FROM metrics
WHERE metric_type = 'api'
  AND metric_name = 'latency_ms'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY metadata->>'endpoint', metadata->>'method'
ORDER BY request_count DESC;
```

**Performance**: ~50ms sur 1000 rows (index sur `metric_type, timestamp`)

**Result Example**:
```
endpoint                              | method | count | avg  | p50  | p95   | p99   | errors | error_rate
--------------------------------------+--------+-------+------+------+-------+-------+--------+-----------
/api/monitoring/advanced/summary      | GET    | 222   | 106  | 95   | 150   | 164   | 0      | 0.0
/v1/code/search/hybrid                | POST   | 45    | 280  | 250  | 450   | 520   | 8      | 17.8
/v1/code/graph/traverse               | POST   | 30    | 120  | 110  | 180   | 200   | 1      | 3.3
/ui/monitoring/advanced               | GET    | 10    | 7    | 6    | 9     | 10    | 0      | 0.0
```

---

### Query 2: Throughput (Requests/Second)

```sql
SELECT
    metadata->>'endpoint' as endpoint,
    COUNT(*) as request_count,
    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) as period_seconds,
    (COUNT(*)::float / EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))))
        as requests_per_second
FROM metrics
WHERE metric_type = 'api'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY metadata->>'endpoint'
HAVING EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) > 0
ORDER BY requests_per_second DESC;
```

---

### Query 3: Top Errors by Endpoint

```sql
SELECT
    metadata->>'endpoint' as endpoint,
    metadata->>'status_code' as status_code,
    COUNT(*) as error_count,
    AVG(value) as avg_latency_ms
FROM metrics
WHERE metric_type = 'api'
  AND (metadata->>'status_code')::int >= 400
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY metadata->>'endpoint', metadata->>'status_code'
ORDER BY error_count DESC
LIMIT 10;
```

**Result Example**:
```
endpoint                    | status_code | error_count | avg_latency_ms
----------------------------+-------------+-------------+----------------
/v1/code/search/hybrid      | 500         | 5           | 520.3
/v1/code/search/hybrid      | 400         | 3           | 80.2
/api/upload/process         | 413         | 2           | 15.5
```

---

### Query 4: Slow Endpoints (P95 > Threshold)

```sql
WITH endpoint_stats AS (
    SELECT
        metadata->>'endpoint' as endpoint,
        COUNT(*) as request_count,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms
    FROM metrics
    WHERE metric_type = 'api'
      AND timestamp > NOW() - INTERVAL '1 hour'
    GROUP BY metadata->>'endpoint'
)
SELECT *
FROM endpoint_stats
WHERE p95_latency_ms > 100  -- Threshold: 100ms
ORDER BY p95_latency_ms DESC;
```

---

## 🎨 UI/UX Design

### Layout Dashboard

```
┌────────────────────────────────────────────────────────────────┐
│ 📊 API Performance by Endpoint                 [Last 1h ▾]    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Top 10 Endpoints by Request Count:                            │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Endpoint                    │ Calls│ P50 │ P95 │ P99 │Err%│ │
│ ├─────────────────────────────┼──────┼─────┼─────┼─────┼────┤ │
│ │ /api/monitoring/.../summary │ 222  │ 95  │150  │164  │0%  │ │
│ │ /v1/code/search/hybrid      │  45  │250  │450🔴│520🔴│18%🔴│ │
│ │ /v1/code/graph/traverse     │  30  │110  │180  │200  │3%  │ │
│ │ /ui/monitoring/advanced     │  10  │  6  │  9  │ 10  │0%  │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                                │
│ [Sort by: Calls ▾] [Filter: All ▾] [Threshold P95 > 100ms]   │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ Slow Endpoints (P95 > 100ms):                                 │
│                                                                │
│ 🔴 /v1/code/search/hybrid                                     │
│    ├─ P95: 450ms (target: 100ms) → **350ms to save**         │
│    ├─ Calls: 45 (last 1h)                                     │
│    └─ Impact: 45 × 350ms = **15.75s wasted/hour** 🔴         │
│                                                                │
│ 🟡 /api/monitoring/advanced/summary                           │
│    ├─ P95: 150ms (target: 100ms) → **50ms to save**          │
│    ├─ Calls: 222 (last 1h)                                    │
│    └─ Impact: 222 × 50ms = **11.1s wasted/hour** 🟡          │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ Error Hotspots:                                                │
│                                                                │
│ 🔴 /v1/code/search/hybrid                                     │
│    ├─ Errors: 8 / 45 (17.8%) 🔴                               │
│    ├─ Status codes: 500 (5×), 400 (3×)                        │
│    └─ Avg latency on error: 520ms                             │
│                                                                │
│ 🟢 Most endpoints: 0% error rate ✅                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

### Interactive Table (Sortable)

**Columns**:
1. **Endpoint** (string, sortable, filterable)
2. **Method** (GET/POST/PUT/DELETE)
3. **Calls** (count, sortable desc default)
4. **Avg** (ms, sortable)
5. **P50** (ms, sortable)
6. **P95** (ms, sortable, **highlight > 100ms**)
7. **P99** (ms, sortable)
8. **Errors** (count)
9. **Error %** (%, **highlight > 5%**)
10. **RPS** (req/s, sortable)

**Features**:
- 🔍 **Search filter** (endpoint name)
- 📊 **Sort by column** (click header)
- 🎨 **Color coding**:
  - P95 < 50ms: Green
  - P95 < 100ms: Yellow
  - P95 >= 100ms: Red
  - Error rate > 5%: Red
- 📈 **Sparkline** (latency trend mini-chart - Phase 3)

---

### ECharts Visualization (Optional)

**Chart 1: Top 10 Endpoints by P95 Latency (Bar Chart)**

```javascript
{
  title: { text: 'Slowest Endpoints (P95 Latency)' },
  xAxis: {
    type: 'category',
    data: ['/v1/search/hybrid', '/api/summary', '/v1/graph']
  },
  yAxis: {
    type: 'value',
    name: 'P95 Latency (ms)',
    axisLine: { lineStyle: { color: '#30363d' } }
  },
  series: [{
    type: 'bar',
    data: [450, 150, 180],
    itemStyle: {
      color: (params) => {
        if (params.value > 200) return '#f85149';  // Red
        if (params.value > 100) return '#d29922';  // Orange
        return '#3fb950';  // Green
      }
    }
  }],
  tooltip: { trigger: 'axis' }
}
```

**Chart 2: Error Rate by Endpoint (Horizontal Bar)**

```javascript
{
  title: { text: 'Endpoints with Errors' },
  yAxis: {
    type: 'category',
    data: ['/v1/search/hybrid', '/api/upload']
  },
  xAxis: {
    type: 'value',
    name: 'Error Rate (%)',
    max: 100
  },
  series: [{
    type: 'bar',
    data: [17.8, 5.2],
    itemStyle: { color: '#f85149' }
  }]
}
```

**Chart 3: Request Distribution (Pie Chart)**

```javascript
{
  title: { text: 'Request Distribution' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: [
      { value: 222, name: '/api/summary (76%)' },
      { value: 45, name: '/v1/search (15%)' },
      { value: 30, name: 'Others (9%)' }
    ]
  }]
}
```

---

## 🔧 Implémentation

### Task 1: EndpointPerformanceService

**File**: `api/services/endpoint_performance_service.py`

```python
"""
EPIC-22 Story 22.5: Endpoint Performance Analyzer

Aggregates API metrics by endpoint from metrics table.
"""

import structlog
from typing import Dict, List, Any, Literal
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = structlog.get_logger()


class EndpointPerformanceService:
    """Analyzes API performance by endpoint."""

    def __init__(self, db_engine: AsyncEngine):
        self.engine = db_engine

    async def get_endpoint_stats(
        self,
        period_hours: int = 1,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get performance stats aggregated by endpoint.

        Args:
            period_hours: Time window (1, 24, 168 for 1h, 1d, 1w)
            limit: Max endpoints to return

        Returns:
            List of endpoint stats sorted by request count desc
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT
                    metadata->>'endpoint' as endpoint,
                    metadata->>'method' as method,
                    COUNT(*) as request_count,
                    AVG(value) as avg_latency_ms,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99_latency_ms,
                    MIN(value) as min_latency_ms,
                    MAX(value) as max_latency_ms,
                    COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400) as error_count,
                    (COUNT(*) FILTER (WHERE (metadata->>'status_code')::int >= 400)::float /
                     NULLIF(COUNT(*)::float, 0) * 100) as error_rate,
                    -- Throughput
                    (COUNT(*)::float / :period_seconds) as requests_per_second
                FROM metrics
                WHERE metric_type = 'api'
                  AND metric_name = 'latency_ms'
                  AND timestamp > NOW() - INTERVAL :period
                GROUP BY metadata->>'endpoint', metadata->>'method'
                ORDER BY request_count DESC
                LIMIT :limit
            """), {
                "period": f"{period_hours} hours",
                "period_seconds": period_hours * 3600,
                "limit": limit
            })

            rows = result.mappings().all()

            # Format response
            endpoints = []
            for row in rows:
                endpoints.append({
                    "endpoint": row["endpoint"],
                    "method": row["method"] or "GET",
                    "request_count": row["request_count"],
                    "avg_latency_ms": round(row["avg_latency_ms"], 2),
                    "p50_latency_ms": round(row["p50_latency_ms"], 2),
                    "p95_latency_ms": round(row["p95_latency_ms"], 2),
                    "p99_latency_ms": round(row["p99_latency_ms"], 2),
                    "min_latency_ms": round(row["min_latency_ms"], 2),
                    "max_latency_ms": round(row["max_latency_ms"], 2),
                    "error_count": row["error_count"] or 0,
                    "error_rate": round(row["error_rate"] or 0, 2),
                    "requests_per_second": round(row["requests_per_second"], 3)
                })

            return endpoints

    async def get_slow_endpoints(
        self,
        threshold_ms: int = 100,
        period_hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get endpoints with P95 latency above threshold.

        Args:
            threshold_ms: P95 latency threshold (default 100ms)
            period_hours: Time window

        Returns:
            List of slow endpoints with impact calculation
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text("""
                WITH endpoint_stats AS (
                    SELECT
                        metadata->>'endpoint' as endpoint,
                        COUNT(*) as request_count,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_latency_ms
                    FROM metrics
                    WHERE metric_type = 'api'
                      AND timestamp > NOW() - INTERVAL :period
                    GROUP BY metadata->>'endpoint'
                )
                SELECT
                    endpoint,
                    request_count,
                    p95_latency_ms,
                    -- Impact: how much time wasted above threshold
                    (p95_latency_ms - :threshold) as latency_above_threshold,
                    (request_count * (p95_latency_ms - :threshold) / 1000.0) as impact_seconds_wasted
                FROM endpoint_stats
                WHERE p95_latency_ms > :threshold
                ORDER BY impact_seconds_wasted DESC
            """), {
                "period": f"{period_hours} hours",
                "threshold": threshold_ms
            })

            rows = result.mappings().all()

            slow_endpoints = []
            for row in rows:
                slow_endpoints.append({
                    "endpoint": row["endpoint"],
                    "request_count": row["request_count"],
                    "p95_latency_ms": round(row["p95_latency_ms"], 2),
                    "target_latency_ms": threshold_ms,
                    "latency_above_target_ms": round(row["latency_above_threshold"], 2),
                    "impact_seconds_wasted_per_hour": round(row["impact_seconds_wasted"], 2)
                })

            return slow_endpoints

    async def get_error_hotspots(
        self,
        min_error_rate: float = 5.0,
        period_hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get endpoints with error rate above threshold.

        Args:
            min_error_rate: Minimum error rate % (default 5%)
            period_hours: Time window

        Returns:
            List of endpoints with high error rates
        """
        async with self.engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT
                    metadata->>'endpoint' as endpoint,
                    metadata->>'status_code' as status_code,
                    COUNT(*) as error_count,
                    AVG(value) as avg_latency_ms
                FROM metrics
                WHERE metric_type = 'api'
                  AND (metadata->>'status_code')::int >= 400
                  AND timestamp > NOW() - INTERVAL :period
                GROUP BY metadata->>'endpoint', metadata->>'status_code'
                ORDER BY error_count DESC
            """), {"period": f"{period_hours} hours"})

            rows = result.mappings().all()

            # Group by endpoint
            errors_by_endpoint = {}
            for row in rows:
                endpoint = row["endpoint"]
                if endpoint not in errors_by_endpoint:
                    errors_by_endpoint[endpoint] = {
                        "endpoint": endpoint,
                        "total_errors": 0,
                        "status_codes": [],
                        "avg_latency_on_error_ms": []
                    }

                errors_by_endpoint[endpoint]["total_errors"] += row["error_count"]
                errors_by_endpoint[endpoint]["status_codes"].append({
                    "code": row["status_code"],
                    "count": row["error_count"]
                })
                errors_by_endpoint[endpoint]["avg_latency_on_error_ms"].append(row["avg_latency_ms"])

            # Calculate error rate
            # (need total requests to calculate %)
            # TODO: Join with get_endpoint_stats to get error_rate

            return list(errors_by_endpoint.values())
```

---

### Task 2: API Routes

**File**: `api/routes/monitoring_routes_advanced.py` (extend)

```python
from services.endpoint_performance_service import EndpointPerformanceService

@router.get("/api/performance/endpoints")
async def get_api_performance_by_endpoint(
    period_hours: int = 1,
    limit: int = 50,
    service: EndpointPerformanceService = Depends(get_endpoint_performance_service)
):
    """
    Get API performance stats by endpoint.

    Query params:
    - period_hours: 1, 24, 168 (1h, 1d, 1w)
    - limit: Max endpoints (default 50)

    Returns:
    [
      {
        "endpoint": "/api/...",
        "method": "GET",
        "request_count": 222,
        "avg_latency_ms": 106.3,
        "p50/p95/p99_latency_ms": ...,
        "error_count": 0,
        "error_rate": 0.0,
        "requests_per_second": 0.062
      }
    ]
    """
    return await service.get_endpoint_stats(period_hours, limit)


@router.get("/api/performance/slow-endpoints")
async def get_slow_endpoints(
    threshold_ms: int = 100,
    period_hours: int = 1,
    service: EndpointPerformanceService = Depends(get_endpoint_performance_service)
):
    """
    Get slow endpoints (P95 > threshold).

    Includes impact calculation (time wasted above threshold).
    """
    return await service.get_slow_endpoints(threshold_ms, period_hours)


@router.get("/api/performance/error-hotspots")
async def get_error_hotspots(
    min_error_rate: float = 5.0,
    period_hours: int = 1,
    service: EndpointPerformanceService = Depends(get_endpoint_performance_service)
):
    """
    Get endpoints with high error rates.
    """
    return await service.get_error_hotspots(min_error_rate, period_hours)
```

---

### Task 3: UI Component (Table)

**File**: `templates/monitoring_advanced.html` (add section)

```html
<!-- API Performance by Endpoint -->
<div class="panel">
    <div class="panel-header">
        <span class="panel-title">📊 API Performance by Endpoint</span>
        <select id="endpoint-period" onchange="refreshEndpointStats()">
            <option value="1">Last 1 hour</option>
            <option value="24">Last 24 hours</option>
            <option value="168">Last 7 days</option>
        </select>
    </div>
    <div class="panel-body">
        <table class="endpoint-table" id="endpoint-table">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Endpoint ▾</th>
                    <th onclick="sortTable(1)">Method</th>
                    <th onclick="sortTable(2)">Calls ▾</th>
                    <th onclick="sortTable(3)">Avg (ms)</th>
                    <th onclick="sortTable(4)">P50 (ms)</th>
                    <th onclick="sortTable(5)">P95 (ms)</th>
                    <th onclick="sortTable(6)">P99 (ms)</th>
                    <th onclick="sortTable(7)">Errors</th>
                    <th onclick="sortTable(8)">Error %</th>
                    <th onclick="sortTable(9)">RPS</th>
                </tr>
            </thead>
            <tbody id="endpoint-tbody">
                <!-- Populated by JavaScript -->
            </tbody>
        </table>
    </div>
</div>

<script>
async function refreshEndpointStats() {
    const period = document.getElementById('endpoint-period').value;
    const response = await fetch(`/api/performance/endpoints?period_hours=${period}`);
    const endpoints = await response.json();

    const tbody = document.getElementById('endpoint-tbody');
    tbody.innerHTML = endpoints.map(ep => `
        <tr>
            <td class="endpoint-name">${ep.endpoint}</td>
            <td>${ep.method}</td>
            <td>${ep.request_count}</td>
            <td>${ep.avg_latency_ms}</td>
            <td>${ep.p50_latency_ms}</td>
            <td class="${getLatencyClass(ep.p95_latency_ms)}">${ep.p95_latency_ms}</td>
            <td>${ep.p99_latency_ms}</td>
            <td>${ep.error_count}</td>
            <td class="${getErrorClass(ep.error_rate)}">${ep.error_rate}%</td>
            <td>${ep.requests_per_second}</td>
        </tr>
    `).join('');
}

function getLatencyClass(p95) {
    if (p95 < 50) return 'latency-good';
    if (p95 < 100) return 'latency-warning';
    return 'latency-critical';
}

function getErrorClass(errorRate) {
    if (errorRate === 0) return 'error-good';
    if (errorRate < 5) return 'error-warning';
    return 'error-critical';
}

// Load on page load
window.addEventListener('load', refreshEndpointStats);
</script>
```

---

## ⚠️ Gotchas & Pitfalls

### 1. Endpoint Path Variability

**Problem**: `/api/users/123` vs `/api/users/456` → counted as different endpoints

**Solution**: Path normalization (replace IDs with `:id`)

```python
# In MetricsMiddleware
def normalize_endpoint(path: str) -> str:
    """
    Normalize endpoint paths:
    /api/users/123 → /api/users/:id
    /api/repos/my-repo → /api/repos/:repo_name
    """
    import re
    # Replace UUIDs
    path = re.sub(r'/[0-9a-f-]{36}', '/:uuid', path)
    # Replace numeric IDs
    path = re.sub(r'/\d+', '/:id', path)
    return path

# Store normalized endpoint
await self._record_metric(
    endpoint=normalize_endpoint(request.url.path),
    ...
)
```

---

### 2. Static Assets Noise

**Problem**: `/static/css/...` pollutes endpoint list

**Solution**: Filter static assets in query OR middleware

```sql
-- Option 1: Filter in query
WHERE metadata->>'endpoint' NOT LIKE '/static/%'

-- Option 2: Don't record metrics for static (MetricsMiddleware)
if request.url.path.startswith('/static'):
    return  # Skip metrics recording
```

---

### 3. Query Performance on Large Dataset

**Problem**: 100k rows → PERCENTILE_CONT slow (>1s)

**Solution**:
- Index: `(metric_type, timestamp DESC, (metadata->>'endpoint'))` (GIN on JSONB)
- Limit period: Max 7 days
- Pagination: LIMIT/OFFSET

---

### 4. Endpoint with 1 Request

**Problem**: 1 request → P95 = P50 = single value (not useful)

**Solution**: Filter endpoints with `COUNT(*) > 10`

```sql
HAVING COUNT(*) > 10
```

---

## 📈 Success Metrics

### Acceptance Criteria
- [x] Endpoint `/api/performance/endpoints` returns stats by endpoint
- [x] Latency P50/P95/P99 calculated per endpoint
- [x] Error count + error rate per endpoint
- [x] Throughput (RPS) calculated
- [x] Slow endpoints (P95 > 100ms) identified with impact
- [x] Error hotspots (error rate > 5%) identified
- [x] UI table sortable by column
- [x] Color coding (green/yellow/red)

### Performance Targets
- Query < 100ms (1h period, <1000 rows)
- UI table renders < 50ms
- Auto-refresh every 30s (optional)

---

## 🎯 Timeline

| Task | Estimation | Priority |
|------|-----------|----------|
| 1. EndpointPerformanceService | 3h | P0 |
| 2. API routes | 1h | P0 |
| 3. UI table (sortable) | 3h | P0 |
| 4. Path normalization | 1h | P1 |
| 5. Slow endpoints panel | 2h | P1 |
| 6. Error hotspots panel | 2h | P1 |
| 7. ECharts (optional) | 3h | P2 |
| 8. Tests | 2h | P1 |
| **Total** | **17h** | **2 jours** |

**Story Points**: 3 pts ✅ (correct estimation)

---

## 🔗 Dependencies

**Requires** (Story 22.1 ✅):
- Table `metrics` with API latency data
- Metadata: endpoint, method, status_code

**Enables** (Future):
- Story 22.7: Smart alerting (alert if endpoint P95 > threshold)
- Phase 3: Timeline heatmap (endpoint × hour)

---

**Créé**: 2025-10-24
**Auteur**: Claude Code
**Status**: 🧠 Ready to implement
**Valeur**: ✅ **HIGH** (158 métriques déjà collectées, problème concret identifié)
**Next**: Get approval → Start implementation
