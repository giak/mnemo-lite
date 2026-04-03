"""
OpenObserve VRL Functions Setup.

Creates Vector Remap Language (VRL) functions via the OpenObserve API.
These functions normalize and enrich log data during ingestion.

Usage:
    python scripts/o2_setup_functions.py

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

FUNCTIONS = [
    {
        "name": "normalize_log_level",
        "order": 1,
        "description": "Normalize log levels from various formats to standard OpenObserve levels",
        "vrl": r"""# Normalize log levels
# Handles: level, severity, _level, log_level, loglevel
if exists(.level) {
    .severity = to_string!(.level)
} else if exists(.log_level) {
    .severity = to_string!(.log_level)
} else if exists(.loglevel) {
    .severity = to_string!(.loglevel)
} else if exists(._level) {
    .severity = to_string!(._level)
}

# Normalize common variations
.severity = downcase!(.severity)
.severity = if contains!(.severity, "error") || contains!(.severity, "err") || contains!(.severity, "crit") || contains!(.severity, "fatal") || contains!(.severity, "emerg") || contains!(.severity, "panic") {
    "error"
} else if contains!(.severity, "warn") {
    "warning"
} else if contains!(.severity, "info") || contains!(.severity, "notice") {
    "info"
} else if contains!(.severity, "debug") || contains!(.severity, "trace") {
    "debug"
} else {
    "info"
}
""",
    },
    {
        "name": "enrich_service_metadata",
        "order": 2,
        "description": "Add service metadata and environment tags to all log entries",
        "vrl": r"""# Ensure service_name is always set
if !exists(.service_name) {
    .service_name = "unknown"
}

# Add environment tag
if !exists(.environment) {
    .environment = "development"
}

# Add component tag based on service name
.component = if contains!(to_string!(.service_name), "api") {
    "backend-api"
} else if contains!(to_string!(.service_name), "mcp") {
    "mcp-server"
} else if contains!(to_string!(.service_name), "worker") || contains!(to_string!(.service_name), "conversation") {
    "background-worker"
} else {
    .service_name
}
""",
    },
    {
        "name": "extract_http_fields",
        "order": 3,
        "description": "Extract HTTP-related fields from log entries for better querying",
        "vrl": r"""# Extract HTTP status code from various field names
if exists(.http_status_code) {
    .http_status = to_int!(.http_status_code)
} else if exists(.status_code) {
    .http_status = to_int!(.status_code)
} else if exists(.status) {
    .http_status = to_int!(.status)
}

# Categorize HTTP status
if exists(.http_status) {
    status = to_int!(.http_status)
    .status_category = if status >= 500 {
        "5xx"
    } else if status >= 400 {
        "4xx"
    } else if status >= 300 {
        "3xx"
    } else if status >= 200 {
        "2xx"
    } else {
        "other"
    }
}

# Extract HTTP method
if exists(.http_method) {
    .method = to_string!(.http_method)
} else if exists(.method) {
    .method = to_string!(.method)
}

# Extract path/URL
if exists(.http_path) {
    .path = to_string!(.http_path)
} else if exists(.path) {
    .path = to_string!(.path)
} else if exists(.url) {
    .path = to_string!(.url)
}

# Extract duration/latency
if exists(.duration_ms) {
    .latency_ms = to_float!(.duration_ms)
} else if exists(.duration) {
    .latency_ms = to_float!(.duration) * 1000.0
} else if exists(.latency) {
    .latency_ms = to_float!(.latency)
}
""",
    },
    {
        "name": "filter_noise_logs",
        "order": 4,
        "description": "Drop health check and favicon noise logs to reduce storage",
        "vrl": r"""# Drop health check logs from the main stream
if exists(.path) {
    if .path == "/health" || .path == "/healthz" || .path == "/ready" || .path == "/favicon.ico" {
        if exists(.http_status) && .http_status == 200 {
            abort
        }
    }
}

# Drop OPTIONS preflight requests
if exists(.method) && .method == "OPTIONS" {
    abort
}
""",
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
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            print(f"  WARNING {method} {path} -> {e.code}: {body[:200]}")
            return None
    except Exception as e:
        print(f"  ERROR {method} {path} -> {e}")
        return None


def create_function(name: str, vrl: str, order: int) -> bool:
    """Create or update a VRL function in OpenObserve."""
    payload = {
        "name": name,
        "function": vrl,
        "order": order,
    }
    result = api_call("POST", "/functions", payload)
    if result and result.get("code") == 200:
        print(f"  OK Function created: {name} (order={order})")
        return True
    elif result and "already" in json.dumps(result).lower():
        print(f"  SKIP Function already exists: {name}")
        return True
    else:
        print(f"  FAIL Function creation failed: {name}")
        return False


def main():
    print("=" * 60)
    print("OpenObserve VRL Functions Setup")
    print(f"Target: {O2_URL}")
    print("=" * 60)

    print("\nCreating VRL functions...")
    success = 0
    failed = 0

    for func in FUNCTIONS:
        if create_function(func["name"], func["vrl"], func["order"]):
            success += 1
        else:
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {success} created, {failed} failed")
    print(f"{'=' * 60}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
