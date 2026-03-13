#!/bin/bash
# MnemoLite MCP Server Launcher (Antifragile Edition)
#
# 1. We redirect stderr to a file (>> /tmp/mnemo_mcp.err) to keep stdout 100% pure JSON.
# 2. We use 'exec' to handle signals correctly.
# 3. We use python -u for unbuffered output.
# 4. We rely on the Lazy Import fix in the python code for speed.

# Rotate log file slightly (keep last 1MB)
if [ -f /tmp/mnemo_mcp.err ]; then
    tail -c 1000000 /tmp/mnemo_mcp.err > /tmp/mnemo_mcp.err.tmp && mv /tmp/mnemo_mcp.err.tmp /tmp/mnemo_mcp.err
fi

echo "[$(date)] MCP Connection Started" >> /tmp/mnemo_mcp.err

# Execute the server
# Note: No EMBEDDING_MODE=mock here, we are using the Lazy Import fix in code.
exec docker exec -i mnemo-api python3 -u -m mnemo_mcp.server 2>> /tmp/mnemo_mcp.err
