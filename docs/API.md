# MnemoLite API

## Base URL

```
http://localhost:8001/v1
```

## Endpoints

### Memory

| Method | Path | Description |
|--------|------|-------------|
| POST | /memories | Create memory |
| GET | /memories/{id} | Get memory |
| PATCH | /memories/{id} | Update memory |
| DELETE | /memories/{id} | Delete memory |
| GET | /memories/search | Search memories |

### Code

| Method | Path | Description |
|--------|------|-------------|
| POST | /code/index | Index repository |
| POST | /code/search | Hybrid search |
| POST | /code/search/hybrid | Hybrid search (explicit) |
| GET | /code/stats | Repository stats |
| GET | /code/graph/stats | Graph stats |
| POST | /code/graph/traverse | Traverse graph |
| POST | /code/graph/path | Find path |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | /projects | List projects |
| GET | /projects/{id} | Get project |
| POST | /projects | Create project |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |

## Examples

### Create Memory

```bash
curl -X POST http://localhost:8001/v1/memories \
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
curl "http://localhost:8001/v1/memories/search?q=authentication"
```

### Index Code

```bash
curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/project",
    "repository": "my-repo"
  }'
```

### Search Code

```bash
curl -X POST http://localhost:8001/v1/code/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication function",
    "limit": 10
  }'
```

## Schemas

### Memory

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| title | string | Memory title (max 200) |
| content | string | Memory content |
| memory_type | enum | note, decision, task, reference |
| tags | string[] | User-defined tags |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update |

### CodeSearch

| Field | Type | Description |
|-------|------|-------------|
| query | string | Search query |
| repository | string | Filter by repository |
| language | string | Filter by language |
| limit | int | Max results (default 10) |