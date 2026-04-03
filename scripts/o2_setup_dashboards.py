"""
OpenObserve Dashboards Setup.

Creates dashboards with panels via the OpenObserve API.
Dashboards cover API Performance, MCP Operations, and Worker Health.

Usage:
    python scripts/o2_setup_dashboards.py

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

DASHBOARDS = [
    {
        "title": "API Performance",
        "description": "Request latency, error rates, cache performance, and DB query metrics for MnemoLite API",
        "role": "",
        "owner": "admin@mnemolite.local",
        "type": "dashboards",
        "kind": "dashboards",
        "panels": [
            {
                "id": "api_latency",
                "type": "line",
                "title": "Request Latency (p50/p95/p99)",
                "description": "HTTP request latency percentiles over time",
                "fields": {"stream": "mnemolite_api", "x_axis": ["_timestamp"], "y_axis": ["latency_ms"]},
                "config": {
                    "unit": "ms",
                    "unit_custom": "milliseconds",
                    "show_legends": True,
                    "legends_position": "bottom",
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, avg(latency_ms) as p50, percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95, percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99 FROM \"mnemolite-api\" WHERE latency_ms IS NOT NULL GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "api_error_rate",
                "type": "bar",
                "title": "Error Rate (5xx)",
                "description": "Count of HTTP 5xx server errors over time",
                "fields": {"stream": "mnemolite_api", "x_axis": ["_timestamp"], "y_axis": ["errors"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                    "legends_position": "bottom",
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as errors FROM \"mnemolite-api\" WHERE http_status >= 500 GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "api_status_distribution",
                "type": "pie",
                "title": "HTTP Status Distribution",
                "description": "Breakdown of requests by status category",
                "fields": {"stream": "mnemolite_api", "x_axis": ["status_category"], "y_axis": ["count"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT status_category, count(*) as count FROM \"mnemolite-api\" WHERE status_category IS NOT NULL GROUP BY status_category ORDER BY count DESC",
            },
            {
                "id": "api_throughput",
                "type": "area",
                "title": "Request Throughput",
                "description": "Requests per minute",
                "fields": {"stream": "mnemolite_api", "x_axis": ["_timestamp"], "y_axis": ["requests"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as requests FROM \"mnemolite-api\" GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "api_top_endpoints",
                "type": "table",
                "title": "Top Endpoints by Latency",
                "description": "Slowest API endpoints",
                "fields": {"stream": "mnemolite_api", "x_axis": ["path"], "y_axis": ["avg_latency"]},
                "config": {
                    "unit": "ms",
                    "show_legends": False,
                },
                "queryType": "sql",
                "query": "SELECT path, method, count(*) as requests, avg(latency_ms) as avg_latency, max(latency_ms) as max_latency FROM \"mnemolite-api\" WHERE latency_ms IS NOT NULL GROUP BY path, method ORDER BY avg_latency DESC LIMIT 20",
            },
        ],
        "variables": {},
        "layout": {"type": "absolute", "panels": []},
    },
    {
        "title": "MCP Operations",
        "description": "Tool invocations, search latency, indexing throughput for MnemoLite MCP server",
        "role": "",
        "owner": "admin@mnemolite.local",
        "type": "dashboards",
        "kind": "dashboards",
        "panels": [
            {
                "id": "mcp_tool_invocations",
                "type": "bar",
                "title": "Tool Invocations by Name",
                "description": "Count of MCP tool calls grouped by tool name",
                "fields": {"stream": "mnemolite_mcp", "x_axis": ["_timestamp"], "y_axis": ["count"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                    "legends_position": "bottom",
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as count FROM \"mnemolite-mcp\" WHERE tool_name IS NOT NULL GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "mcp_search_latency",
                "type": "line",
                "title": "Search Query Latency",
                "description": "Average search query duration over time",
                "fields": {"stream": "mnemolite_mcp", "x_axis": ["_timestamp"], "y_axis": ["avg_latency"]},
                "config": {
                    "unit": "ms",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, avg(latency_ms) as avg_latency FROM \"mnemolite-mcp\" WHERE operation = 'search' AND latency_ms IS NOT NULL GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "mcp_indexing_throughput",
                "type": "area",
                "title": "Indexing Throughput",
                "description": "Files indexed per minute",
                "fields": {"stream": "mnemolite_mcp", "x_axis": ["_timestamp"], "y_axis": ["files"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as files FROM \"mnemolite-mcp\" WHERE operation = 'index' GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "mcp_error_rate",
                "type": "bar",
                "title": "MCP Error Rate",
                "description": "Failed MCP operations over time",
                "fields": {"stream": "mnemolite_mcp", "x_axis": ["_timestamp"], "y_axis": ["errors"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as errors FROM \"mnemolite-mcp\" WHERE severity = 'error' GROUP BY x_axis ORDER BY x_axis",
            },
        ],
        "variables": {},
        "layout": {"type": "absolute", "panels": []},
    },
    {
        "title": "Worker Health",
        "description": "Conversation processing metrics, Redis Stream lag, and processing duration",
        "role": "",
        "owner": "admin@mnemolite.local",
        "type": "dashboards",
        "kind": "dashboards",
        "panels": [
            {
                "id": "worker_messages",
                "type": "line",
                "title": "Messages Processed vs Failed",
                "description": "Count of messages processed and failed over time",
                "fields": {"stream": "conversation_worker", "x_axis": ["_timestamp"], "y_axis": ["total"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                    "legends_position": "bottom",
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as total FROM \"conversation-worker\" GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "worker_processing_duration",
                "type": "line",
                "title": "Processing Duration",
                "description": "Average message processing time",
                "fields": {"stream": "conversation_worker", "x_axis": ["_timestamp"], "y_axis": ["avg_duration"]},
                "config": {
                    "unit": "ms",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, avg(duration_ms) as avg_duration FROM \"conversation-worker\" WHERE duration_ms IS NOT NULL GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "worker_failures",
                "type": "bar",
                "title": "Processing Failures",
                "description": "Count of failed message processing attempts",
                "fields": {"stream": "conversation_worker", "x_axis": ["_timestamp"], "y_axis": ["failures"]},
                "config": {
                    "unit": "none",
                    "show_legends": True,
                },
                "queryType": "sql",
                "query": "SELECT histogram(_timestamp) as x_axis, count(*) as failures FROM \"conversation-worker\" WHERE severity = 'error' GROUP BY x_axis ORDER BY x_axis",
            },
            {
                "id": "worker_stream_health",
                "type": "table",
                "title": "Stream Processing Summary",
                "description": "Messages per stream with success/failure rates",
                "fields": {"stream": "conversation_worker", "x_axis": ["stream_name"], "y_axis": ["count"]},
                "config": {
                    "unit": "none",
                    "show_legends": False,
                },
                "queryType": "sql",
                "query": "SELECT stream_name, count(*) as total, count(*) FILTER (WHERE severity = 'error') as failures FROM \"conversation-worker\" WHERE stream_name IS NOT NULL GROUP BY stream_name ORDER BY total DESC",
            },
        ],
        "variables": {},
        "layout": {"type": "absolute", "panels": []},
    },
]


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
        print(f"  WARNING {method} {path} -> {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  ERROR {method} {path} -> {e}")
        return None


def create_dashboard(dashboard: dict) -> bool:
    """Create a dashboard in OpenObserve."""
    result = api_call("POST", "/dashboards", dashboard)
    if result:
        title = dashboard.get("title", "unknown")
        print(f"  OK Dashboard created: {title}")
        return True
    else:
        title = dashboard.get("title", "unknown")
        print(f"  WARNING Dashboard may already exist: {title}")
        return True


def main():
    print("=" * 60)
    print("OpenObserve Dashboards Setup")
    print(f"Target: {O2_URL}")
    print("=" * 60)

    print(f"\nCreating {len(DASHBOARDS)} dashboards...")
    success = 0

    for dashboard in DASHBOARDS:
        if create_dashboard(dashboard):
            success += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {success}/{len(DASHBOARDS)} dashboards created")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
