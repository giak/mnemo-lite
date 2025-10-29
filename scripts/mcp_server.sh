#!/bin/bash
# MnemoLite MCP Server Launcher for Claude Code
#
# This script launches the MnemoLite MCP server in Docker stdio mode
# for integration with Claude Code (CLI).

set -e

# Navigate to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check if Docker services are running
if ! docker compose ps | grep -q "Up"; then
    echo "Error: Docker services are not running. Start them with:" >&2
    echo "  docker compose up -d" >&2
    exit 1
fi

# Launch MCP server in stdio mode via Docker
exec docker compose exec -T api python3 -m mnemo_mcp.server
