# MnemoLite MCP — 33 Tools

[![MCP](https://img.shields.io/badge/MCP-1.12.3-blue.svg)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v5.0.0--dev-orange.svg)](https://github.com/anomalyco/mnemolite)

MnemoLite exposes 33 MCP tools for LLM integration via Streamable HTTP transport (port 8002).

## Overview

MnemoLite provides a comprehensive code intelligence platform with hybrid lexical + vector search, semantic memory management, code graph traversal, and real-time indexing. All tools communicate via the MCP protocol over HTTP.

| Transport | Port | Protocol |
|-----------|------|----------|
| Streamable HTTP | 8002 | MCP 1.12.3 |

## Tools

### Memory (9 tools)

Semantic memory management with embeddings for persistent knowledge.

| Tool | Description | Latency |
|------|-------------|---------|
| `write_memory` | Create memory with semantic embedding | ~100ms |
| `read_memory` | Read memory content by UUID | ~10ms |
| `update_memory` | Partial update (regenerates embedding) | ~50ms |
| `delete_memory` | Soft delete (reversible) or hard delete | ~10ms |
| `search_memory` | Hybrid semantic search with filters | ~100ms |
| `get_system_snapshot` | Full boot context in one call (4x faster) | ~50ms |
| `mark_consumed` | Mark memories as processed by agent | ~10ms |
| `consolidate_memory` | Compress history into summary | ~100ms |
| `configure_decay` | Configure decay rules per tag pattern | ~10ms |

**Use cases:**
- Persistent knowledge base for agents
- Decision logging with semantic search
- History consolidation for long-running agents

### Indexing (7 tools)

Code indexing with tree-sitter parsing, LSP integration, and embeddings.

| Tool | Description | Latency |
|------|-------------|---------|
| `index_project` | Full project indexing (~5s/file) | ~5s/file |
| `index_incremental` | Changed files only (~50ms/file) | ~50ms/file |
| `index_markdown_workspace` | Markdown-only workspace (10x faster) | ~0.5s/file |
| `reindex_file` | Single file reindex after edits | ~100ms |
| `get_indexing_status` | Indexing progress and status | ~10ms |
| `get_indexing_errors` | Recent indexing errors | ~10ms |
| `retry_indexing` | Retry failed files after fixes | ~100ms/file |

**Performance:**
- Full project (782 files): ~6.5 hours → incremental: ~50 seconds
- Concurrent indexing prevented via Redis distributed lock

### Code Search (1 tool)

Hybrid lexical + vector search with RRF fusion.

| Tool | Description | Latency |
|------|-------------|---------|
| `search_code` | Hybrid lexical (pg_trgm) + vector (embeddings) | ~50-100ms |

**Features:**
- Keyword and natural language queries
- Filters: language, chunk_type, repository, file_path, LSP types
- Reciprocal Rank Fusion (RRF) ranking
- Configurable lexical/vector weights

### Analytics (4 tools)

System health, cache, and indexing statistics.

| Tool | Description | Latency |
|------|-------------|---------|
| `get_indexing_stats` | Stats per repository (files, chunks, nodes) | ~10ms |
| `get_memory_health` | Memory health (total, embeddings, consolidation) | ~10ms |
| `get_cache_stats` | L1/L2 cache hit rates and memory usage | ~10ms |
| `clear_cache` | Clear L1 (in-memory), L2 (Redis), or all | ~10ms |

### Graph (4 tools)

Code dependency graph traversal and analysis.

| Tool | Description | Latency |
|------|-------------|---------|
| `get_graph_stats` | Graph statistics (nodes, edges, modules) | ~10ms |
| `traverse_graph` | Graph traversal from node (in/out/both) | ~10ms |
| `find_path` | Shortest path between nodes (BFS) | ~10ms |
| `get_module_data` | Module details (nodes, connections) | ~10ms |

**Use cases:**
- Impact analysis
- Dependency tracking
- Call graph exploration

### Project (2 tools)

Multi-repository support and health checks.

| Tool | Description | Latency |
|------|-------------|---------|
| `switch_project` | Change active repository context | ~10ms |
| `ping` | Health check (pong response) | <1ms |

## Client Configuration

### OpenCode / KiloCode

```json
{
  "mcpServers": {
    "mnemolite": {
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mnemolite": {
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

### curl (Manual Testing)

```bash
# Initialize
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'

# List tools
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}'

# Call tool
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ping","arguments":{}},"id":3}'
```

## Protocol

### Handshake

```
Client → Server: initialize (protocolVersion, capabilities, clientInfo)
Server → Client: initialized (serverInfo, capabilities)
```

### Transport

- **Streamable HTTP** on port 8002
- Endpoint: `/mcp`
- Content-Type: `application/json` + `application/json-seq` for streaming

### Error Handling

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": "详细错误信息"
  },
  "id": null
}
```

## Deployment

### Docker Compose

```bash
# Start MCP server
docker compose up -d mcp

# Check status
docker compose ps

# Logs
docker logs mnemo-mcp -f

# Restart
docker compose restart mcp
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | 8002 | HTTP port |
| `DATABASE_URL` | postgresql://... | PostgreSQL connection |
| `REDIS_URL` | redis://... | Redis connection |
| `EMBEDDING_MODEL` | sentence-transformers/... | Embedding model |
| `LOG_LEVEL` | INFO | Logging level |

### Health Check

```bash
# MCP ping
curl http://localhost:8002/mcp -X POST \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ping","arguments":{}},"id":1}'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Client                          │
│  (Claude Desktop, OpenCode, KiloCode, Cursor, etc.)        │
└─────────────────────────┬───────────────────────────────────┘
                          │ Streamable HTTP (8002)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     MnemoLite MCP Server                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Memory   │  │   Indexing  │  │   Code Search       │  │
│  │   Service  │  │   Service   │  │   Service            │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │            │
│  ┌──────┴────────────────┴─────────────────────┴──────────┐ │
│  │              SQLAlchemy + PostgreSQL                   │ │
│  │         (memories, chunks, graph, config)              │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Quick Reference

| Category | Tools | Quick Start |
|----------|-------|-------------|
| Memory | 9 | `write_memory(title="...", content="...")` |
| Indexing | 7 | `index_project(project_path="/path")` |
| Search | 1 | `search_code(query="...")` |
| Analytics | 4 | `get_memory_health()` |
| Graph | 4 | `get_graph_stats(repository="default")` |
| Project | 2 | `ping()` |

---

**Version:** v5.0.0-dev | **MCP SDK:** 1.12.3 | **Transport:** Streamable HTTP