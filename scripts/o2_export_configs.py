"""
OpenObserve Configuration Export.

Exports all OpenObserve configurations (dashboards, functions, stream settings)
to JSON files for version control and disaster recovery.

Usage:
    python scripts/o2_export_configs.py

Environment:
    O2_URL: OpenObserve base URL (default: http://localhost:5080)
    O2_USER: OpenObserve user email (default: admin@mnemolite.local)
    O2_PASSWORD: OpenObserve password (default: Complexpass#123)

Output:
    configs/openobserve/
    ├── dashboards/
    │   ├── <dashboard_id>.json
    ├── functions/
    │   ├── <function_name>.json
    └── streams/
        ├── <stream_name>_settings.json
"""

import os
import json
import sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from base64 import b64encode

O2_URL = os.getenv("O2_URL", "http://localhost:5080")
O2_USER = os.getenv("O2_USER", "admin@mnemolite.local")
O2_PASSWORD = os.getenv("O2_PASSWORD", "Complexpass#123")
ORG = "default"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "openobserve")

auth_string = f"{O2_USER}:{O2_PASSWORD}"
auth_bytes = b64encode(auth_string.encode("utf-8")).decode("utf-8")
HEADERS = {
    "Authorization": f"Basic {auth_bytes}",
    "Content-Type": "application/json",
}


def api_call(method: str, path: str) -> dict | None:
    """Make an authenticated API call to OpenObserve."""
    url = f"{O2_URL}/api/{ORG}{path}"
    req = Request(url, headers=HEADERS, method=method)
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


def save_json(data: dict, filepath: str) -> None:
    """Save data as formatted JSON."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  OK Saved: {filepath}")


def export_dashboards() -> int:
    """Export all dashboards."""
    print("\nExporting dashboards...")
    result = api_call("GET", "/dashboards")
    if not result or "dashboards" not in result:
        print("  No dashboards found")
        return 0

    count = 0
    for db in result["dashboards"]:
        dashboard_id = db.get("dashboard_id", db.get("title", "unknown"))
        filepath = os.path.join(OUTPUT_DIR, "dashboards", f"{dashboard_id}.json")
        save_json(db, filepath)
        count += 1

    return count


def export_functions() -> int:
    """Export all functions."""
    print("\nExporting functions...")
    result = api_call("GET", "/functions")
    if not result or "list" not in result:
        print("  No functions found")
        return 0

    count = 0
    for func in result["list"]:
        name = func.get("name", "unknown")
        filepath = os.path.join(OUTPUT_DIR, "functions", f"{name}.json")
        save_json(func, filepath)
        count += 1

    return count


def export_streams() -> int:
    """Export all stream metadata."""
    print("\nExporting stream metadata...")
    result = api_call("GET", "/streams")
    if not result or "list" not in result:
        print("  No streams found")
        return 0

    count = 0
    for stream in result["list"]:
        name = stream.get("name", "unknown")
        # Export stream metadata from list response
        filepath = os.path.join(OUTPUT_DIR, "streams", f"{name}_metadata.json")
        save_json(stream, filepath)
        count += 1

    return count


def main():
    print("=" * 60)
    print("OpenObserve Configuration Export")
    print(f"Target: {O2_URL}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    dashboards = export_dashboards()
    functions = export_functions()
    streams = export_streams()

    # Save export manifest
    manifest = {
        "exported_at": datetime.now().isoformat(),
        "o2_url": O2_URL,
        "organization": ORG,
        "dashboards": dashboards,
        "functions": functions,
        "streams": streams,
    }
    manifest_path = os.path.join(OUTPUT_DIR, "export_manifest.json")
    save_json(manifest, manifest_path)

    print(f"\n{'=' * 60}")
    print(f"Export complete:")
    print(f"  Dashboards: {dashboards}")
    print(f"  Functions:  {functions}")
    print(f"  Streams:    {streams}")
    print(f"  Manifest:   {manifest_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
