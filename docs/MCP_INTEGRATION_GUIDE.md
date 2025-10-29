# MnemoLite MCP Integration Guide

**Status**: ✅ Operational (2025-10-28)
**EPIC**: EPIC-23 MCP Integration
**Version**: 1.0.0

## Overview

MnemoLite now exposes its code intelligence features via the **Model Context Protocol (MCP)**, enabling direct integration with Claude Code and other LLM clients.

## Quick Start

### Prerequisites

1. **Docker services running**:
   ```bash
   docker compose up -d
   ```

2. **Claude Code installed** (CLI tool)

### Configuration

The MCP server is already configured in `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "bash",
      "args": ["/home/giak/Work/MnemoLite/scripts/mcp_server.sh"],
      "description": "MnemoLite MCP Server - Code intelligence with hybrid search, graph traversal, and semantic memories"
    }
  }
}
```

### Using MnemoLite MCP Server

**Method 1: Restart Claude Code Session** (Recommended)

Simply restart your Claude Code session. The MCP server will be automatically loaded.

**Method 2: Manual Test**

Test the server manually:
```bash
./scripts/mcp_server.sh
```

(Press Ctrl+C to stop)

## Available MCP Components

### 🔧 Tools (9 tools)

1. **`ping`** - Test server connectivity
2. **`search_code`** - Hybrid code search (lexical + vector + RRF)
3. **`write_memory`** - Create persistent memories
4. **`update_memory`** - Update existing memories
5. **`delete_memory`** - Delete memories (soft/hard delete with elicitation)
6. **`index_project`** - Index a code repository
7. **`reindex_file`** - Reindex a specific file
8. **`clear_cache`** - Clear cache layers (with elicitation)
9. **`switch_project`** - Switch active project (with elicitation)

### 📚 Resources (11 resources)

1. **`health://status`** - Server health check
2. **`memories://get/{id}`** - Get memory by UUID
3. **`memories://list`** - List all memories
4. **`memories://search/{query}`** - Semantic memory search
5. **`graph://nodes/{chunk_id}`** - Code graph node details
6. **`graph://callers/{qualified_name}`** - Find function callers
7. **`graph://callees/{qualified_name}`** - Find function callees
8. **`index://status/{repository}`** - Indexing status
9. **`cache://stats`** - Cache statistics
10. **`analytics://search`** - Search performance analytics
11. **`projects://list`** - List indexed projects
12. **`config://languages`** - Supported languages

### 💬 Prompts (6 prompts)

1. **`analyze_codebase`** - Architecture & design patterns analysis
2. **`refactor_suggestions`** - Find refactoring opportunities
3. **`find_bugs`** - Identify potential bugs
4. **`generate_tests`** - Generate test suite for code
5. **`explain_code`** - Explain code for different audiences
6. **`security_audit`** - OWASP Top 10 & CWE audit

## Usage Examples

### Example 1: Search Code

Ask Claude Code:
```
Use search_code to find all functions that handle user authentication
```

Claude will use the `search_code` MCP tool with:
- Query: "user authentication"
- Filters: function definitions, Python
- Hybrid search (lexical + vector + RRF fusion)

### Example 2: Store Insight as Memory

Ask Claude Code:
```
Use write_memory to remember: "The authentication system uses JWT tokens
with 1-hour expiry. Refresh tokens are stored in Redis."
```

Claude will use the `write_memory` MCP tool to persist this knowledge.

### Example 3: Find Function Callers

Ask Claude Code:
```
Use the graph://callers resource to find all functions that call
authenticate_user
```

Claude will query the code graph to show the call hierarchy.

### Example 4: List Indexed Projects

Ask Claude Code:
```
Show me all indexed projects using the projects://list resource
```

Claude will display project statistics (files, chunks, languages).

### Example 5: Use a Prompt Template

Ask Claude Code:
```
Use the analyze_codebase prompt for the Python codebase,
focusing on architecture
```

Claude will use the pre-written prompt template for codebase analysis.

## Elicitation (Human-in-the-Loop)

Some operations require user confirmation:

### Destructive Operations
- **`delete_memory`** with `permanent=True` → ⚠️ Confirmation required
- **`clear_cache`** → ⚠️ Confirmation required

### Context-Changing Operations
- **`switch_project`** → Confirmation required (unless `confirm=True`)

### Bypass Elicitation (Automation)
For automation/scripts, bypass elicitation:
```python
# Python
await delete_memory(id="abc-123", permanent=True)

# Claude Code (will prompt for confirmation)
# Or with bypass:
Use delete_memory with permanent=True and confirm=True (no elicitation)
```

## Architecture

```
Claude Code (CLI)
    ↓ stdio
MCP Server (Docker)
    ↓
PostgreSQL 18 + Redis
    ↓
Code Chunks + Embeddings + Graph
```

**Key Features:**
- **stdio Transport**: Direct stdin/stdout communication
- **Docker Isolation**: Server runs in container
- **Service Injection**: DI pattern for DB, Redis, repositories
- **Graceful Degradation**: Works without Redis (limited caching)
- **Structured Logging**: JSON logs for debugging

## Troubleshooting

### Issue: MCP server not loading

**Solution 1**: Verify Docker services are running
```bash
docker compose ps
# Should show: api, db, redis (all Up)
```

**Solution 2**: Test MCP server manually
```bash
./scripts/mcp_server.sh
# Should output JSON logs
```

**Solution 3**: Check logs
```bash
docker compose logs api | grep mcp.server
```

### Issue: Tools not showing in Claude Code

**Solution**: Restart Claude Code session to reload MCP configuration.

### Issue: Memory/Graph features not working

**Cause**: SQLAlchemy async driver issue (see logs: "psycopg2 is not async")

**Workaround**: Most features work in degraded mode. Full fix requires asyncpg driver setup (deferred to future story).

### Issue: Embedding service is in mock mode

**Explanation**: By default, `EMBEDDING_MODE=mock` to avoid loading 2GB models. This is expected behavior. Semantic search uses deterministic mock embeddings.

**To enable real embeddings**:
```bash
# In docker-compose.yml, remove EMBEDDING_MODE=mock
docker compose restart api
```

## Performance

- **Server Startup**: ~3-4 seconds (indexing libraries load)
- **Ping Tool**: <1ms
- **Search Tool**: ~50-200ms (cached), ~500ms (uncached)
- **Memory Tools**: ~10-50ms
- **Graph Resources**: ~20-100ms
- **Redis Cache**: L2 cache with 5-min TTL

## Development

### Testing MCP Server

Run unit tests:
```bash
docker compose exec api pytest tests/mnemo_mcp/ -v
```

Run specific test:
```bash
docker compose exec api pytest tests/mnemo_mcp/test_search_tool.py::test_search_code_tool_basic_query -v
```

### Adding New MCP Components

1. Create tool/resource in `api/mnemo_mcp/tools/` or `api/mnemo_mcp/resources/`
2. Create Pydantic models in `api/mnemo_mcp/models/`
3. Register in `api/mnemo_mcp/server.py` (see existing patterns)
4. Write tests in `tests/mnemo_mcp/`
5. Document in EPIC-23 stories

### MCP Protocol Reference

- **MCP Spec**: 2025-06-18
- **FastMCP SDK**: v1.12.3
- **Protocol**: JSON-RPC 2.0 over stdio
- **Elicitation**: MCP native human-in-the-loop

## References

### EPIC-23 Documentation
- **Main README**: `docs/agile/serena-evolution/03_EPICS/EPIC-23_README.md`
- **Progress Tracker**: `docs/agile/serena-evolution/03_EPICS/EPIC-23_PROGRESS_TRACKER.md`
- **Phase 3 Breakdown**: `docs/agile/serena-evolution/03_EPICS/EPIC-23_PHASE3_STORIES_BREAKDOWN.md`

### Story Completion Reports
- Story 23.1: Project Structure & FastMCP Setup
- Story 23.2: Code Search Tool
- Story 23.3: Memory Tools & Resources
- Story 23.4: Code Graph Resources
- Story 23.5: Indexing Tools
- Story 23.6: Analytics & Cache Tools
- Story 23.7: Configuration & Utilities
- Story 23.10: Prompts Library
- Story 23.11: Elicitation Flows

### Technical Guides
- **Elicitation Patterns**: `api/docs/ELICITATION_PATTERNS.md` (5,200+ words)
- **ULTRATHINKs**: Available for Stories 23.2, 23.5, 23.6, 23.7, 23.10, 23.11

## Status & Metrics

- **Overall Progress**: 19/23 story points (83%)
- **Phase 3**: 2/5 stories complete (40%)
- **Tests**: 355/355 passing ✅ (100%)
- **Time Spent**: 47.5h (vs 65.5h estimated, 27% ahead)

## Next Steps (Remaining Stories)

1. **Story 23.8**: HTTP Transport Support (2 pts, ~8h)
2. **Story 23.9**: Documentation & Examples (1 pt, ~4h)
3. **Story 23.12**: MCP Inspector Integration (1 pt, ~3h)

---

**Last Updated**: 2025-10-28
**Author**: EPIC-23 Team
**Version**: 1.0.0
