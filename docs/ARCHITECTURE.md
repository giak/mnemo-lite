# MnemoLite Architecture

## Technology Stack

| Component | Technology |
|-----------|------------|
| Database | PostgreSQL 18 + pgvector 0.8.1 |
| API | FastAPI + AsyncPG |
| Cache | Redis 7 (L2) + In-memory (L1) |
| Frontend | Vue 3 SPA + Tailwind + SCADA design |
| MCP | FastMCP 1.12.3 |
| Indexing | tree-sitter (15+ languages) |

## Architecture Diagram

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Vue 3 SPA │───▶│  FastAPI    │───▶│ PostgreSQL  │
│  (port 3000)│    │  (port 8001)│    │   (port 5432)│
└─────────────┘    └──────┬──────┘    └─────────────┘
                         │
                   ┌─────┴─────┐    ┌─────────────┐
                   │    MCP    │    │   Redis 7   │
                   │(port 8002)│    │  (port 6379) │
                   └───────────┘    └─────────────┘
```

## Triple-Layer Cache

```
┌─────────────────────────────────────────────┐
│                    Cache                     │
├─────────────┬─────────────┬────────────────┤
│ L1 (Memory) │ L2 (Redis)  │ L3 (PostgreSQL)│
│    ~1ms     │   ~10ms     │    ~50ms       │
│  Per-process│  Distributed │     Disk       │
└─────────────┴─────────────┴────────────────┘
```

## Indexing Pipeline (7 Steps)

1. **File Detection** — Scan project for supported files
2. **Language Identification** — Detect language (Python, JS, TS, etc.)
3. **AST Parsing** — Parse with tree-sitter
4. **Chunking** — Split into semantic chunks (functions, classes)
5. **Metadata Extraction** — LSP for types, signatures
6. **Dual Embedding** — TEXT + CODE vectors (768D each)
7. **Graph Construction** — Build dependency graph

## Database Schema

### memories

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | VARCHAR(200) | Memory title |
| content | TEXT | Full content |
| memory_type | VARCHAR(50) | Type: note, decision, task |
| tags | TEXT[] | Array of tags |
| embedding | halfvec(768) | Vector embedding |
| author | VARCHAR(100) | Author |
| project_id | UUID | Project scope (nullable) |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last update |
| deleted_at | TIMESTAMPTZ | Soft delete |

### code_chunks

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| repository | VARCHAR(100) | Repository name |
| file_path | TEXT | File path |
| chunk_type | VARCHAR(50) | function, class, method |
| name | VARCHAR(200) | Chunk name |
| source_code | TEXT | Code content |
| embedding_text | halfvec(768) | TEXT embedding |
| embedding_code | halfvec(768) | CODE embedding |
| language | VARCHAR(20) | Programming language |
| metadata | JSONB | LSP metadata |
| created_at | TIMESTAMPTZ | Creation time |

### graph_nodes

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| repository | VARCHAR(100) | Repository name |
| node_type | VARCHAR(50) | function, class, module |
| name | VARCHAR(200) | Node name |
| file_path | TEXT | Location |
| metadata | JSONB | Additional data |

### graph_edges

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| source_id | UUID | Source node |
| target_id | UUID | Target node |
| edge_type | VARCHAR(50) | calls, imports, inherits |

## Hybrid Search

MnemoLite combines multiple search strategies:

1. **Lexical** — pg_trgm trigram matching
2. **Vector** — pgvector HNSW (ef_search=100)
3. **RRF Fusion** — Reciprocal Rank Fusion
4. **BM25 Reranking** — Optional reranking

```sql
-- Example: Hybrid search
SELECT * FROM memories
WHERE deleted_at IS NULL
ORDER BY 
  0.4 * similarity(title, query) +
  0.6 * (1 - embedding <=> query::vector)
LIMIT 10;
```

## Memory Management

MnemoLite uses semantic memory with decay-based relevance:

### Memory Types

| Type | Purpose | Auto-expire |
|------|---------|-------------|
| note | General notes | 30 days |
| decision | Architectural decisions | Never |
| task | Track TODOs | Until completed |
| reference | Code references | 90 days |
| conversation | Chat history | 14 days |
| investigation | Debug findings | 45 days |

### Decay Configuration

Each tag can have custom decay:
- `decay_rate`: Exponential decay (0.0 = permanent, 0.1 ≈ 7 days half-life)
- `auto_consolidate_threshold`: Consolidate when count exceeds limit
- `priority_boost`: Score adjustment (+0.5 important, -0.1 deprioritize)

### Consolidation Workflow

When `sys:history` count > 20, oldest 10 memories are consolidated into 1 summary:
1. Search oldest 10 `sys:history` memories
2. Generate LLM summary
3. Create new `sys:history:summary` memory
4. Soft-delete source memories

## MCP Tools

### Search Tools

| Tool | Description |
|------|-------------|
| search_code | Hybrid lexical + vector search |
| search_memory | Semantic memory search |

### Memory Tools

| Tool | Description |
|------|-------------|
| write_memory | Create new memory |
| update_memory | Partial update |
| delete_memory | Soft/hard delete |
| consolidate_memory | Merge multiple memories |
| mark_consumed | Mark as processed |

### Graph Tools

| Tool | Description |
|------|-------------|
| get_graph_stats | Repository statistics |
| traverse_graph | Navigate dependencies |
| find_path | Shortest path BFS |
| get_module_data | Module details |

### Indexing Tools

| Tool | Description |
|------|-------------|
| index_project | Full project index |
| index_incremental | Changed files only |
| reindex_file | Single file update |
| get_indexing_status | Progress/status |

## API Endpoints

### FastAPI (port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check |
| /search | POST | Code search |
| /memories | GET/POST | Memory CRUD |
| /memories/{id} | GET/PUT/DELETE | Single memory |
| /graph/stats | GET | Graph statistics |
| /graph/traverse | POST | Graph navigation |
| /index | POST | Start indexing |
| /index/status | GET | Indexing status |

### MCP Protocol (port 8002)

MCP exposes tools via JSON-RPC 2.0:
- Tools registered at server startup
- Request/response via stdin/stdout
- Notifications for progress updates

## Graph Traversal

The code graph represents:
- **Nodes**: Functions, classes, modules
- **Edges**: calls, imports, inherits relationships

### Traversal Types

| Direction | Description |
|-----------|-------------|
| outgoing | callees, imports |
| incoming | callers, referencers |
| both | Full neighborhood |

### BFS Path Finding

Finds shortest path between two nodes:
- Max depth configurable (default: 5)
- Returns nodes and edges along path
- Used for "how does X reach Y?" queries

## Deployment

### Production Ports

| Service | Port | Protocol |
|---------|------|----------|
| Frontend Vue 3 | 3000 | HTTP |
| FastAPI | 8001 | HTTP/HTTPS |
| MCP | 8002 | stdin/stdout |
| PostgreSQL | 5432 | TCP |
| Redis | 6379 | TCP |

### Distributed Architecture

```
                    ┌──────────────────┐
                    │   Load Balancer   │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
 ┌──────┴──────┐     ┌──────┴──────┐     ┌──────┴──────┐
 │  Worker 1   │     │  Worker 2   │     │  Worker N   │
 │  (port 8001)│     │  (port 8001)│     │  (port 8001)│
 └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │         PostgreSQL            │
              │         (port 5432)            │
              └──────────────┬──────────────┘
                             │
              ┌──────────────┴──────────────┐
              │           Redis             │
              │         (port 6379)          │
              └─────────────────────────────┘
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql://localhost:5432/mnemo | Database connection |
| REDIS_URL | redis://localhost:6379 | Redis connection |
| MCP_PORT | 8002 | MCP server port |
| API_PORT | 8001 | API server port |
| FRONTEND_PORT | 3000 | Frontend port |

## Performance

| Metric | Value |
|--------|-------|
| Search latency (cached) | <10ms |
| Search latency (uncached) | ~100ms |
| Indexing speed | ~5s per file |
| Graph traversal (3 hops) | ~0.15ms |
| Cache hit rate | 80%+ |