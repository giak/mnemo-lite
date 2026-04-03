# MnemoLite MCP Server - Getting Started

## Quick Start Guide

This guide walks you through setting up and testing the MnemoLite MCP server with Desktop.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 18 with pgvector extension
- Redis 7.x
- Desktop (for testing)

---

## Installation

### 1. Install MCP Dependencies

```bash
# Option A: Using pip (in virtual environment)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Option B: Using Docker (rebuild API container)
docker compose build api
docker compose up -d
```

### 2. Configure Environment

Create `.env` file with:

```bash
# Database
MCP_DATABASE_URL=postgresql://mnemo:mnemopass@localhost:5432/mnemolite
MCP_TEST_DATABASE_URL=postgresql://mnemo:mnemopass@localhost:5432/mnemolite_test

# Redis
MCP_REDIS_URL=redis://localhost:6379/0

# MCP Server
MCP_SERVER_NAME=mnemolite
MCP_LOG_LEVEL=INFO
MCP_TRANSPORT=stdio  # stdio for Desktop, http for web
```

---

## Desktop Configuration

### 1. Locate Config File

Desktop config is at:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 2. Add MnemoLite MCP Server

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "python",
      "args": ["-m", "api.mcp.server"],
      "cwd": "<project-root>",
      "env": {
        "MCP_DATABASE_URL": "postgresql://mnemo:mnemopass@localhost:5432/mnemolite",
        "MCP_REDIS_URL": "redis://localhost:6379/0",
        "MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Important**: Replace `<project-root>` with your actual project path.

### 3. Restart Desktop

Close and reopen Desktop to load the new MCP server configuration.

---

## Testing the MCP Server

### Option 1: Smoke Test with Python

Before configuring Desktop, test the server directly:

```bash
# Activate virtual environment (if using)
source venv/bin/activate

# Run MCP server in stdio mode
python -m api.mcp.server
```

Expected output:
```json
{"timestamp":"2025-01-15T10:00:00Z","level":"info","event":"mcp.server.startup","name":"mnemolite","version":"1.0.0","transport":"stdio"}
{"timestamp":"2025-01-15T10:00:00Z","level":"info","event":"mcp.db.connecting","url":"localhost:5432/mnemolite"}
{"timestamp":"2025-01-15T10:00:00Z","level":"info","event":"mcp.db.connected","postgres_version":"PostgreSQL 18.1"}
{"timestamp":"2025-01-15T10:00:00Z","level":"info","event":"mcp.redis.connected"}
{"timestamp":"2025-01-15T10:00:00Z","level":"info","event":"mcp.services.initialized","services":["db","redis"]}
{"timestamp":"2025-01-15T10:00:00Z","level":"info","event":"mcp.components.test.registered","tools":["ping"],"resources":["health://status"]}
```

Server is now waiting for JSON-RPC commands on stdin. Press `Ctrl+C` to stop.

### Option 2: Test in Desktop

Once Desktop is configured:

1. Open Desktop
2. Start a new conversation
3. Look for the "MCP" or "Tools" icon (usually bottom-right)
4. Verify `mnemolite` server appears in the list

#### Test Ping Tool

In Desktop chat:

```
User: Use the mnemolite ping tool to test connectivity

Claude: [Calls ping tool]
{
  "success": true,
  "message": "pong",
  "timestamp": "2025-01-15T10:00:00Z",
  "latency_ms": 0.1,
  "metadata": {
    "server_name": "mnemolite",
    "mcp_spec": "2025-06-18"
  }
}

The MnemoLite MCP server is responding correctly!
```

#### Test Health Resource

```
User: Check the health://status resource from mnemolite

Claude: [Gets health://status resource]
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:00:00Z",
  "database_connected": true,
  "redis_connected": true,
  "uptime_seconds": 123.4,
  "version": "1.0.0"
}

All services are healthy:
✓ PostgreSQL connected
✓ Redis connected
✓ Server uptime: 2 minutes
```

---

## Troubleshooting

### Server Won't Start

**Problem**: `ModuleNotFoundError: No module named 'mcp'`

**Solution**:
```bash
pip install mcp==1.12.3 pydantic-settings sse-starlette pyjwt
```

---

**Problem**: `Database connection failed`

**Solution**:
```bash
# Check PostgreSQL is running
docker compose ps

# Verify connection
psql postgresql://mnemo:mnemopass@localhost:5432/mnemolite -c "SELECT version();"
```

---

**Problem**: `Redis connection failed`

**Solution**:
```bash
# Check Redis is running
docker compose ps

# Test connection
redis-cli ping  # Should return PONG
```

---

### Desktop Not Seeing Server

**Problem**: MnemoLite doesn't appear in Desktop

**Solutions**:

1. Check config file path is correct
2. Verify JSON syntax is valid (use https://jsonlint.com/)
3. Check logs in Desktop:
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Linux: `~/.cache/claude/logs/mcp*.log`
4. Restart Desktop completely (quit, not just close window)

---

### Server Starts But Tools Don't Work

**Problem**: `ping` tool returns error

**Check**:
1. Server logs (stdout from `python -m api.mcp.server`)
2. Database connection (health://status should show `database_connected: true`)
3. Redis connection (health://status should show `redis_connected: true`)

---

## Next Steps

Once the smoke test passes:

1. **Story 23.2**: Implement code search resources (`code://search`)
2. **Story 23.3**: Implement memory tools (`write_memory`, `memories://list`)
3. **Story 23.4**: Implement code graph resources (`graph://nodes`)

See `docs/agile/serena-evolution/03_EPICS/EPIC-23_README.md` for full roadmap.

---

## Development Tips

### View MCP Server Logs

```bash
# Run with DEBUG logging
MCP_LOG_LEVEL=DEBUG python -m api.mcp.server
```

### Test Without Desktop

Use MCP Inspector (http://127.0.0.1:6274):

```bash
# Install MCP Inspector
pip install mcp

# Start Inspector
mcp-inspector

# Add mnemolite server in UI
# Then test tools/resources interactively
```

### Run Unit Tests

```bash
# Test MCP components
pytest tests/mcp/ -v

# Test specific component
pytest tests/mcp/test_test_tool.py -v
```

---

## Support

For issues or questions:
- Check `docs/mcp/TROUBLESHOOTING.md`
- Review EPIC-23 stories in `docs/agile/serena-evolution/03_EPICS/`
- Search logs for error messages
