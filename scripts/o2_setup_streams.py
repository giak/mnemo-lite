"""
OpenObserve Stream Settings Setup.

Configures stream settings (schema, indexes, retention) via the OpenObserve API.
Optimizes query performance for MnemoLite telemetry data.

Usage:
    python scripts/o2_setup_streams.py

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

STREAM_SETTINGS = {
    "mnemolite_api": {
        "partition_keys": {"set": ["service_name"]},
        "index_fields": {"set": ["http_status", "method", "path", "status_category"]},
        "full_text_search_keys": {"set": ["event", "message", "path"]},
        "bloom_filter_fields": {"set": ["trace_id", "span_id"]},
        "data_retention": 30,
        "flatten_level": 3,
        "defined_schema_fields": {
            "set": [
                "service_name", "severity", "environment", "component",
                "http_status", "method", "path", "status_category",
                "latency_ms", "duration", "trace_id", "span_id",
                "event", "message", "logger", "timestamp",
            ]
        },
        "max_query_range": 168,
        "store_original_data": True,
        "index_all_values": False,
    },
    "mnemolite_mcp": {
        "partition_keys": {"set": ["service_name"]},
        "index_fields": {"set": ["tool_name", "operation", "status_category"]},
        "full_text_search_keys": {"set": ["event", "message", "query"]},
        "bloom_filter_fields": {"set": ["trace_id", "span_id"]},
        "data_retention": 30,
        "flatten_level": 3,
        "defined_schema_fields": {
            "set": [
                "service_name", "severity", "environment", "component",
                "tool_name", "operation", "query", "status_category",
                "latency_ms", "duration", "trace_id", "span_id",
                "event", "message", "logger", "timestamp",
            ]
        },
        "max_query_range": 168,
        "store_original_data": True,
        "index_all_values": False,
    },
    "conversation_worker": {
        "partition_keys": {"set": ["service_name"]},
        "index_fields": {"set": ["status", "status_category", "stream_name"]},
        "full_text_search_keys": {"set": ["event", "message", "error"]},
        "bloom_filter_fields": {"set": ["trace_id", "message_id"]},
        "data_retention": 30,
        "flatten_level": 3,
        "defined_schema_fields": {
            "set": [
                "service_name", "severity", "environment", "component",
                "status", "status_category", "stream_name",
                "duration_ms", "processing_time", "trace_id", "message_id",
                "event", "message", "error", "logger", "timestamp",
            ]
        },
        "max_query_range": 168,
        "store_original_data": True,
        "index_all_values": False,
    },
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


def configure_stream_settings(stream_name: str, settings: dict) -> bool:
    """Create or update stream settings."""
    result = api_call("PUT", f"/streams/{stream_name}/settings", settings)
    if result and result.get("code") == 200:
        print(f"  OK Stream settings configured: {stream_name}")
        return True
    elif result:
        print(f"  WARNING Stream settings response: {stream_name} -> {result}")
        return True
    else:
        print(f"  FAIL Stream settings failed: {stream_name}")
        return False


def list_streams() -> list[str]:
    """List all existing streams."""
    result = api_call("GET", "/streams")
    if result and "list" in result:
        return [s.get("name", "") for s in result["list"]]
    return []


def main():
    print("=" * 60)
    print("OpenObserve Stream Settings Setup")
    print(f"Target: {O2_URL}")
    print("=" * 60)

    print("\nListing existing streams...")
    existing = list_streams()
    print(f"  Found {len(existing)} streams: {', '.join(existing) if existing else 'none'}")

    print("\nConfiguring stream settings...")
    success = 0
    skipped = 0
    failed = 0

    for stream_name, settings in STREAM_SETTINGS.items():
        if stream_name in existing:
            if configure_stream_settings(stream_name, settings):
                success += 1
            else:
                failed += 1
        else:
            print(f"  SKIP Stream not yet active: {stream_name} (will be created on first ingestion)")
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {success} configured, {skipped} skipped, {failed} failed")
    print(f"{'=' * 60}")

    if skipped > 0:
        print("\nNote: Skipped streams will be configured automatically")
        print("after their first log ingestion. Re-run this script later.")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
