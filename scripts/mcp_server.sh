#!/bin/bash
# MnemoLite MCP Server Launcher
#
# Launches the MCP server inside Docker with reliable stdin/stdout forwarding.
# Compatible with: Claude Desktop, Kilo, VS Code, any MCP client.
#
# Uses Python subprocess with direct stdin/stdout pipes for reliable
# bidirectional communication (bash exec + docker exec -i loses data).

CONTAINER_DB_URL=$(docker exec mnemo-api printenv DATABASE_URL 2>/dev/null || echo "")
MCP_DB_URL="${MCP_DATABASE_URL:-$(echo "$CONTAINER_DB_URL" | sed 's/postgresql+asyncpg/postgresql/')}"

# Python proxy: directly connects stdin/stdout to docker exec subprocess
# This avoids the bash exec → docker exec pipe forwarding issues
exec python3 -u -c "
import subprocess, sys
proc = subprocess.Popen(
    ['docker', 'exec', '-i',
     '-e', 'MCP_DATABASE_URL=$MCP_DB_URL',
     'mnemo-api',
     'python3', '-u', '-m', 'mnemo_mcp.server'],
    stdin=sys.stdin,
    stdout=sys.stdout,
    stderr=open('/tmp/mnemo_mcp.err', 'a'),
    bufsize=0
)
proc.wait()
sys.exit(proc.returncode)
"
