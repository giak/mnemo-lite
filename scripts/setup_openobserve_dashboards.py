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
        print(f"  WARNING {method} {path} -> {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  ERROR {method} {path} -> {e}")
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
        print(f"  OK Dashboard created: {name}")
    else:
        print(f"  WARNING Dashboard may already exist: {name}")


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
        print(f"  OK Alert created: {name}")
    else:
        print(f"  WARNING Alert may already exist: {name}")


def main():
    print("=" * 60)
    print("OpenObserve Dashboard & Alert Setup")
    print(f"Target: {O2_URL}")
    print("=" * 60)

    # Dashboard 1: API Performance
    print("\nCreating dashboards...")
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
    print("\nCreating alerts...")
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
