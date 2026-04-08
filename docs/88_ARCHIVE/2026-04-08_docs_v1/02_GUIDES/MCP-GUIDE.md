# MnemoLite MCP — Guide Complet

> **Date :** 2026-03-29  
> **Version :** MnemoLite 1.12.3, MCP Spec 2025-03-26  
> **Couverture :** Architecture, outils, tests, déploiement, debug

---

## 1. Architecture

### Vue d'Ensemble

```
┌──────────────────────────────────────────────────────┐
│                    CLIENTS MCP                        │
│  KiloCode │ OpenCode │ Antigravity │ Claude Desktop  │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP POST (Streamable HTTP)
                       │ mcp-session-id header
                       ▼
┌──────────────────────────────────────────────────────┐
│              mnemo-mcp (Docker)                       │
│              Port 8002, uvicorn                       │
│                                                      │
│  FastMCP Server (mcp 1.12.3)                        │
│  ├── 17 outils MCP                                   │
│  ├── 12 ressources MCP                               │
│  ├── 6 prompts MCP                                   │
│  └── Lifespan (DI: DB, Redis, Embedding, Cache)     │
│                                                      │
│  Services :                                          │
│  ├── DualEmbeddingService (TEXT + CODE, lazy-load)  │
│  ├── HybridMemorySearchService (RRF + decay)        │
│  ├── HybridCodeSearchService (RRF + reranking)      │
│  ├── CodeIndexingService (chunking + embedding)     │
│  ├── CascadeCache (L1 memory → L2 Redis → L3 PG)   │
│  └── MemoryDecayService (DB config, tag-based)      │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  mnemo-postgres (5432)  │  mnemo-redis (6379)       │
│  19,531 chunks          │  Cache L2                 │
│  34,504 memories        │  Session state            │
│  11 decay configs       │  Distributed lock         │
└──────────────────────────────────────────────────────┘
```

### Services Injectés au Startup

```
Lifespan:
  1. asyncpg pool (min=2, max=10)
  2. Redis (graceful if unavailable)
  3. DualEmbeddingService (lazy-load, no preload)
  4. SQLAlchemy engine (pool_size=10)
  5. CodeIndexingService + dependencies
  6. MemoryRepository
  7. HybridMemorySearchService
  8. Graph services
  9. Metrics + Monitoring
```

**Point clé :** Les modèles d'embedding sont chargés **paresseusement** (lazy-load) au premier appel, pas au startup. Cela réduit le temps d'initialisation de 12.5s à 4.0s.

---

## 2. Outils MCP (17)

### Mémoire (8 outils)

| Outil | Description | Args Clés | Latence |
|-------|-------------|-----------|---------|
| `write_memory` | Créer mémoire avec embedding | title, content, tags, memory_type | ~100ms |
| `read_memory` | Lire mémoire par UUID | id | ~10ms |
| `update_memory` | Mise à jour partielle | id, (champs optionnels) | ~50ms |
| `delete_memory` | Soft/hard delete | id, permanent | ~10ms |
| `search_memory` | Recherche sémantique hybride | query, tags, consumed, lifecycle_state | ~100-200ms |
| `get_system_snapshot` | Boot contexte complet | repository | ~50ms |
| `mark_consumed` | Marquer mémoires traitées | memory_ids, consumed_by | ~10ms |
| `consolidate_memory` | Compresser historique | title, summary, source_ids | ~100ms |

### Indexation (4 outils)

| Outil | Description | Args Clés | Latence |
|-------|-------------|-----------|---------|
| `index_project` | Indexer répertoire complet | project_path, repository | ~5s/fichier |
| `index_incremental` | Re-index fichiers modifiés | project_path, repository | ~50ms/fichier |
| `index_markdown_workspace` | Indexer .md uniquement | root_path, repository | ~0.5s/fichier |
| `reindex_file` | Re-index 1 fichier | file_path, repository | ~100ms |

### Configuration & Cache (3 outils)

| Outil | Description | Args Clés | Latence |
|-------|-------------|-----------|---------|
| `configure_decay` | Configurer decay par tag | tag_pattern, decay_rate | ~10ms |
| `clear_cache` | Vider cache L1/L2/L2 | layer | ~10ms |
| `switch_project` | Changer projet actif | repository | ~10ms |

### Code (1 outil)

| Outil | Description | Args Clés | Latence |
|-------|-------------|-----------|---------|
| `search_code` | Recherche hybride code | query, filters, limit | ~50-100ms |

### Test (1 outil)

| Outil | Description | Args Clés | Latence |
|-------|-------------|-----------|---------|
| `ping` | Health check | (aucun) | <1ms |

---

## 3. Recherche Hybride — Sous le Capot

### Pipeline search_memory

```
Query → Auto-génération embedding (nomic-embed-text-v1.5, ~5ms)
  → Parallel [Lexical + Vector]
  │
  ├─ Lexical (pg_trgm ILIKE + trigram)
  │    WHERE deleted_at IS NULL
  │      AND tags @> ARRAY['sys:pattern']
  │      AND consumed_at IS NULL
  │      AND lifecycle filter (sealed/candidate/doubt)
  │    Score: GREATEST(similarity(title), similarity(embedding_source))
  │
  ├─ Vector (pgvector HNSW halfvec)
  │    SET hnsw.ef_search = 100 (~97% recall)
  │    SET hnsw.iterative_scan = 'relaxed_order'
  │    Score: 1 - (embedding_half <=> query::halfvec)
  │
  ├─ RRF Fusion (k adaptatif)
  │    k=20 si code-heavy (3+ indicators: (){}.→::)
  │    k=80 si natural language (0 indicators, >5 words)
  │    k=60 défaut
  │
  ├─ Cross-Encoder Reranking (BAAI/bge-reranker-base, +20-30%)
  │    Top-30 candidats → re-rank
  │
  └─ Temporal Decay (tag-based, exp decay)
       final_score = rrf_score × exp(-decay_rate × age_days)
```

### Pipeline search_code (Vessel)

```
Query → Auto-génération embedding CODE (jina-embeddings-v2-base-code)
  → Parallel [Lexical + Vector]
  │
  ├─ Lexical (pg_trgm on code_chunks.name + source_code)
  │    WHERE repository = 'expanse'
  │
  ├─ Vector (pgvector HNSW halfvec)
  │    WHERE repository = 'expanse'
  │
  └─ RRF Fusion → Rerank → Top-K
```

---

## 4. Session MCP — Protocole

### Handshake (obligatoire)

```json
// 1. Initialize (première requête)
{"jsonrpc":"2.0","method":"initialize","params":{
  "protocolVersion":"2025-03-26",
  "capabilities":{},
  "clientInfo":{"name":"client","version":"1.0"}
},"id":1}

// Réponse :
// Header: mcp-session-id: xxx-xxx-xxx
// Body: {"result":{"serverInfo":{"name":"mnemolite","version":"1.12.3"}}}

// 2. Initialized notification (obligatoire)
{"jsonrpc":"2.0","method":"notifications/initialized"}

// 3. Tool calls (avec session header)
// Header: mcp-session-id: xxx-xxx-xxx
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ping","arguments":{}},"id":2}
```

### Points Importants

- Chaque requête POST doit inclure le header `mcp-session-id`
- Le header `Accept: application/json, text/event-stream` est obligatoire
- Les réponses sont au format SSE (`event: message\ndata: {...}`)
- Le `notifications/initialized` est obligatoire après `initialize`

---

## 5. Configuration Clients

### KiloCode / OpenCode

```json
// .kilocode/mcp.json
{
  "mcpServers": {
    "mnemolite": {
      "type": "streamable-http",
      "url": "http://localhost:8002/mcp",
      "alwaysAllow": ["search_memory", "write_memory", "get_system_snapshot"]
    }
  }
}
```

### Antigravity IDE

```json
// ~/.gemini/antigravity/mcp_config.json
{
  "mcpServers": {
    "mnemolite": {
      "type": "streamable-http",
      "serverURL": "http://localhost:8002/mcp",
      "alwaysAllow": ["search_memory", "write_memory", "get_system_snapshot"]
    }
  }
}
```

**Note :** Antigravity utilise `serverURL` (camelCase) au lieu de `url`.

### Claude Desktop

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "mnemolite": {
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

---

## 6. Tests

### Tests Unitaires (dans le container)

```bash
# Tous les tests
docker exec mnemo-api python -m pytest tests/ -q --ignore=tests/performance --ignore=tests/integration

# Tests MCP optimisations (57 tests)
docker exec mnemo-api python -m pytest tests/test_pgvector_optimizations.py -v

# Tests auth middleware (6 tests)
docker exec mnemo-api python -m pytest tests/test_auth_middleware.py -v

# Tests rate limit (5 tests)
docker exec mnemo-api python -m pytest tests/test_rate_limit_middleware.py -v
```

### Tests MCP E2E (via HTTP)

```python
# Script de test MCP complet
import json, requests

BASE = 'http://localhost:8002/mcp'
H = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
s = requests.Session()

# Init
r = s.post(BASE, json={'jsonrpc':'2.0','method':'initialize',
    'params':{'protocolVersion':'2025-03-26','capabilities':{},
    'clientInfo':{'name':'test','version':'1.0'}},'id':1}, headers=H)
sid = r.headers.get('mcp-session-id')
H['mcp-session-id'] = sid

# Notification
s.post(BASE, json={'jsonrpc':'2.0','method':'notifications/initialized'}, headers=H)

# Ping
r = s.post(BASE, json={'jsonrpc':'2.0','method':'tools/call',
    'params':{'name':'ping','arguments':{}},'id':2}, headers=H)
# → {"result":{"content":[{"text":"{\"message\":\"pong\"}"}]}}
```

### Résultats Dernier Audit (2026-03-29)

```
✅ ping → pong
✅ get_system_snapshot → core=13, traces=16
✅ search_memory (tags string) → 1 results
✅ search_memory (tags list) → 1 results
✅ search_memory (consumed=false) → OK
✅ search_memory (lifecycle=sealed) → 3 results
✅ write_memory → id=..., emb=true
✅ read_memory → title match
✅ update_memory → tags updated
✅ delete_memory → success
✅ search_code → vector=true
✅ configure_decay → rate=0.01

Score: 11/11 (100%)
```

---

## 7. Pipeline Recherche — Paramètres

### pgvector

| Paramètre | Valeur | Effet |
|-----------|--------|-------|
| `hnsw.ef_search` | 100 | Recall ~97% (vs 92% au défaut 40) |
| `hnsw.iterative_scan` | `relaxed_order` | Fix overfiltering avec WHERE filters |
| Stockage | halfvec (float16) | -50% mémoire, 99.2% recall |
| Index | HNSW (m=16, ef_construction=128) | Production-ready |

### RRF

| Paramètre | Valeur | Effet |
|-----------|--------|-------|
| k adaptatif | 20/60/80 | Code→précision, NL→recall |
| Weights (code) | lexical=0.3, vector=0.7 | Favorise vector pour code |
| Weights (NL) | lexical=0.5, vector=0.5 | Équilibré |

### Decay

| Tag | Rate | Half-life | Boost |
|-----|------|-----------|-------|
| sys:core | 0.000 | ∞ | +0.5 |
| sys:anchor | 0.000 | ∞ | +0.5 |
| sys:pattern | 0.005 | 140j | +0.2 |
| sys:extension | 0.010 | 70j | 0.0 |
| sys:drift | 0.020 | 35j | +0.3 |
| sys:history | 0.050 | 14j | -0.1 |
| TRACE:FRESH | 0.100 | 7j | +0.4 |

---

## 8. Déploiement

### Docker Compose

```yaml
# 6 services
mnemo-api       :8001  REST API (FastAPI)
mnemo-mcp       :8002  MCP Server (Streamable HTTP)
mnemo-postgres  :5432  PostgreSQL 18 + pgvector 0.8.1
mnemo-redis     :6379  Cache L2 + session state
mnemo-worker    —      Background tasks
mnemo-openobserve:5080  Monitoring
```

### Commandes

```bash
# Démarrer
make restart

# Arrêter
make stop

# Reconstruire (après changement de code)
make build && docker compose up -d --force-recreate mcp

# Tests MCP
docker exec mnemo-api python -m pytest tests/test_pgvector_optimizations.py -v

# Logs MCP
docker logs mnemo-mcp -f

# Health
curl http://localhost:8001/health | python3 -m json.tool
```

---

## 9. Troubleshooting

| Symptôme | Cause | Solution |
|----------|-------|---------|
| "connection closed: EOF" | MCP non démarré | `docker ps \| grep mcp` → `make restart` |
| "Invalid request parameters" | Session non initialisée | Envoyer `initialize` + `notifications/initialized` |
| "tags must be a list" | Ancienne version MCP | Rebuild: `make build && docker compose up -d mcp` |
| "embedding circuit breaker open" | Modèle non chargé | Attendre 60s (recovery automatique) |
| "unexpected keyword argument" | API tool différente de la signature | Vérifier `server.py` tool signature |
| "peft not found" | Modèle jina-v5 sans peft | `EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5` |
| Response vide | Header Accept manquant | Ajouter `Accept: application/json, text/event-stream` |

---

## 10. Métriques

| Métrique | Valeur |
|----------|--------|
| Outils MCP | 17 |
| Ressources MCP | 12 |
| Prompts MCP | 6 |
| Chunks code | 19,531 |
| Mémoires | 34,504 |
| Decay configs | 11 |
| Extensions supportées | 21 |
| Langages parsés | 5 (Python, TS, JS, TSX, Markdown) |
| Temps init MCP | ~4s |
| Temps ping | <1ms |
| Temps snapshot | ~50ms |
| Temps search (1er) | ~100-200ms |
| Temps search (suivant) | ~50-100ms |
| RAM MCP container | ~1.6GB |
| Score audit | 11/11 (100%) |

---

*Guide généré le 2026-03-29 01:14 — MnemoLite v1.12.3*
