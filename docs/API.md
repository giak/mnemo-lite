# MnemoLite API

> **Documentation complète et à jour:** [http://localhost:8001/docs](http://localhost:8001/docs) (Swagger/OpenAPI auto-généré)
> 
> Cette page résume les endpoints principaux. Pour la référence complète, utilisez Swagger UI.

## Base URL

```
http://localhost:8001
```

## Endpoints Principaux

### Memories (`/api/v1/memories`)

| Method | Path | Description |
|--------|------|-------------|
| GET | /stats | Memory statistics |
| POST | / | Create memory |
| GET | /{id} | Get memory |
| PUT | /{id} | Update memory |
| DELETE | /{id} | Delete memory |
| POST | /search | Search memories |
| GET | /recent | Recent memories |

### Code Indexing (`/v1/code/index`)

| Method | Path | Description |
|--------|------|-------------|
| POST | / | Index repository |
| GET | /status/{repository} | Indexing status |
| POST | /batch | Batch indexing |

### Code Search (`/v1/code/search`)

| Method | Path | Description |
|--------|------|-------------|
| POST | / | Hybrid search |
| POST | /content | Content search |

### Projects (`/api/v1/projects`)

| Method | Path | Description |
|--------|------|-------------|
| GET | / | List projects |
| POST | / | Create project |
| GET | /active | Active project |
| POST | /active | Set active project |
| DELETE | /{repository} | Delete project |

### Monitoring (`/api/monitoring`)

| Method | Path | Description |
|--------|------|-------------|
| GET | /status | System status |
| GET | /metrics | Prometheus metrics |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /api/v1/dashboard/health | Dashboard health |
| GET | /metrics | Prometheus metrics |

## Quick Examples

### Create Memory

```bash
curl -X POST http://localhost:8001/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Architecture Decision",
    "content": "Use Redis for L2 cache",
    "memory_type": "decision",
    "tags": ["architecture", "cache"]
  }'
```

### Search Memories

```bash
curl -X POST http://localhost:8001/api/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "limit": 10}'
```

### Index Code

```bash
curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/project", "repository": "my-repo"}'
```

### Search Code

```bash
curl -X POST http://localhost:8001/v1/code/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication function", "limit": 10}'
```

## Schemas

### Memory Types

| Type | Purpose |
|------|---------|
| note | General observations |
| decision | Architectural decisions |
| task | TODO items |
| reference | Documentation links |
| conversation | Dialogue context |
| investigation | Debug findings |

### Memory Schema

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| title | string | Memory title (max 200) |
| content | string | Memory content |
| memory_type | enum | See types above |
| tags | string[] | User-defined tags |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update |

---

**Note:** L'API complète (128+ endpoints) est documentée dans Swagger UI: [http://localhost:8001/docs](http://localhost:8001/docs)
