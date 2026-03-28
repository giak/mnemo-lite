#!/usr/bin/env python3
"""
MCP Proxy — Launches the MCP server inside Docker and proxies stdin/stdout.

This replaces the bash mcp_server.sh script to fix stdin/stdout forwarding
issues with docker exec -i.
"""
import subprocess
import sys
import os

def main():
    # Get DB URL from container
    try:
        db_url = subprocess.run(
            ["docker", "exec", "mnemo-api", "printenv", "DATABASE_URL"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        # Strip asyncpg prefix
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    except Exception:
        db_url = ""

    # Override with env var if set
    db_url = os.environ.get("MCP_DATABASE_URL", db_url)

    # Launch MCP server inside container
    proc = subprocess.Popen(
        [
            "docker", "exec", "-i",
            "-e", f"MCP_DATABASE_URL={db_url}",
            "mnemo-api",
            "python3", "-u", "-m", "mnemo_mcp.server"
        ],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=open("/tmp/mnemo_mcp.err", "a"),
    )

    # Wait for process to finish
    proc.wait()
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
