# Documentation v2 — Plan d'Implémentation

> **Pour agents:** Utiliser superpowers:subagent-driven-development ou superpowers:executing-plans pour exécuter ce plan tâche par tâche.

**Goal:** Réécrire entièrement la documentation MnemoLite avec 5 fichiers focalisés, archiver l'existant.

**Architecture:** Approche minimaliste — README comme hub, 4 fichiers de contenu, archivage complet de l'ancien.

**Tech Stack:** Markdown, Git

---

## Phase 1: Archivage

### Task 1: Archiver l'ancien docs/

**Files:**
- Create: `docs/88_ARCHIVE/2026-04-08_docs_v1/` (répertoire destination)
- Modify: `docs/` (déplacer tout sauf 88_ARCHIVE/)

- [ ] **Step 1: Lister le contenu actuel de docs/**

```bash
ls -la docs/
# Vérifier: README.md, 00_CONTROL/, 01_DECISIONS/, 02_GUIDES/, etc.
```

- [ ] **Step 2: Créer le répertoire d'archive**

```bash
mkdir -p docs/88_ARCHIVE/2026-04-08_docs_v1
```

- [ ] **Step 3: Déplacer tout SAUF 88_ARCHIVE/ vers l'archive**

```bash
cd docs
# Déplacer les fichiers et répertoires (sauf 88_ARCHIVE/)
git mv README.md 88_ARCHIVE/2026-04-08_docs_v1/
git mv 00_CONTROL/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv 01_DECISIONS/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv 02_GUIDES/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv 03_FEATURES/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv 04_MCP/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv 05_EXAMPLES/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv 99_PLANS/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv agile/ 88_ARCHIVE/2026-04-08_docs_v1/
git mv ARCHITECTURE.md 88_ARCHIVE/2026-04-08_docs_v1/
git mv AUDIT-MCP-P2026-03-29.md 88_ARCHIVE/2026-04-08_docs_v1/
git mv EPIC-25_STORY_25.5_GRAPH_RELATIONS_FIX.md 88_ARCHIVE/2026-04-08_docs_v1/
git mv O2_SETUP_GUIDE.md 88_ARCHIVE/2026-04-08_docs_v1/
git mv CONTRIBUTING.md 88_ARCHIVE/2026-04-08_docs_v1/
git mv deployment/ 88_ARCHIVE/2026-04-08_docs_v1/
```

- [ ] **Step 4: Créer README dans l'archive**

```bash
echo '# Archive: MnemoLite Documentation v1 (2026-04-08)
Cette archive contient l\'ancienne documentation (avant refonte v2).
Voir ../README.md pour la documentation actuelle.
' > docs/88_ARCHIVE/2026-04-08_docs_v1/README.md
```

- [ ] **Step 5: Commit archivage**

```bash
git add docs/88_ARCHIVE/2026-04-08_docs_v1/
git commit -m "docs: archive v1 documentation (2026-04-08)"
```

---

## Phase 2: Création des Fichiers

### Task 2: Créer README.md

**Files:**
- Create: `docs/README.md`

**Content:** Badge + features + services + liens + make commands (~100 lignes)

- [ ] **Step 1: Créer README.md complet**

```markdown
# MnemoLite: PostgreSQL-Native Cognitive Memory

[![Version](https://img.shields.io/badge/version-5.0.0--dev-blue.svg)](https://github.com/giak/MnemoLite)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/postgres-18-blue.svg)](https://postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.8.1-brightgreen.svg)](https://github.com/pgvector/pgvector)

**MnemoLite** is a high-performance, locally deployable cognitive memory system built on PostgreSQL 18. Zero external vector databases. Zero API dependencies. Zero cost.

## Features

- **Cognitive Memory** — Semantic search, time-aware storage, hybrid RRF fusion
- **Code Intelligence** — AST-based indexing, dependency graphs, 15+ languages
- **MCP Integration** — 33 tools for LLM integration
- **Triple-Layer Cache** — L1 (memory) → L2 (Redis) → L3 (PostgreSQL)

## Quick Start

```bash
git clone https://github.com/giak/MnemoLite.git
cd MnemoLite
docker compose --profile dev up -d
```

## Services

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:8001 |
| MCP | http://localhost:8002 |
| OpenObserve | http://localhost:5080 |

## Documentation

- [QUICKSTART.md](QUICKSTART.md) — Setup en 5 minutes
- [MCP.md](MCP.md) — Intégration MCP (33 outils)
- [API.md](API.md) — Endpoints REST
- [ARCHITECTURE.md](ARCHITECTURE.md) — Vue technique

## Development

```bash
make up          # Start all services
make down        # Stop all services
make test        # Run tests
make api-shell   # Shell in API container
make db-shell    # psql shell
```

## Architecture

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

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add docs/README.md
git commit -m "docs: add README.md (v2)"
```

---

### Task 3: Créer QUICKSTART.md

**Files:**
- Create: `docs/QUICKSTART.md`

**Content:** Setup rapide + MCP config + test (~150 lignes)

- [ ] **Step 1: Créer QUICKSTART.md complet**

```markdown
# MnemoLite Quick Start

**Setup en 5 minutes.**

## 1. Démarrer MnemoLite

```bash
cd <project-root>
docker compose --profile dev up -d

# Vérifier
docker compose ps
# Expected: api, db, redis, mcp all "Up (healthy)"
```

## 2. Configurer MCP

Créer `.mcp.json` dans votre projet:

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "bash",
      "args": ["<project-root>/scripts/mcp_server.sh"],
      "env": {
        "DOCKER_COMPOSE_PROJECT": "mnemolite"
      }
    }
  }
}
```

## 3. Tester

```bash
# Ping
curl http://localhost:8001/health

# Ou via MCP (dans Claude Code):
# "Test MCP ping"
# Expected: pong
```

## 4. Premier Usage

```bash
# Indexer un projet
# "Indexe /path/to/project avec repository='my-project'"

# Rechercher du code
# "Cherche les fonctions d'authentification"
# → search_code retourne les chunks pertinents

# Sauvegarder une mémoire
# "Sauvegarde: le projet utilise FastAPI + PostgreSQL"
# → write_memory crée une mémoire avec embedding
```

## Troubleshooting

**MCP not available?**
```bash
docker compose ps | grep mcp
# Si down: docker compose up -d mcp
```

**Connection refused?**
```bash
docker compose logs api --tail 20
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/QUICKSTART.md
git commit -m "docs: add QUICKSTART.md (v2)"
```

---

### Task 4: Créer MCP.md

**Files:**
- Create: `docs/MCP.md`

**Content:** 33 outils + protocole + config clients + tests (~300 lignes)

- [ ] **Step 1: Créer MCP.md (version nettoyée de MCP-GUIDE.md)**

Basé sur `docs/88_ARCHIVE/.../02_GUIDES/MCP-GUIDE.md` mais:
- Mettre à jour nombre d'outils: 17 → 33
- Supprimer toutes références HTMX (s'il y en a)
- Mettre à jour versions: v1.12.3 → 5.0.0-dev
- Utiliser `<project-root>` au lieu de chemins absolus

Structure:
```markdown
# MnemoLite MCP — 33 Tools

## Overview

33 MCP tools organized in 5 categories.

## Memory (9 tools)

| Tool | Description |
|------|-------------|
| write_memory | Create memory with embedding |
| read_memory | Read memory by UUID |
| update_memory | Partial update |
| delete_memory | Soft/hard delete |
| search_memory | Hybrid semantic search |
| get_system_snapshot | Full boot context |
| mark_consumed | Mark memories processed |
| consolidate_memory | Compress history |
| configure_decay | Configure decay rules |

## Indexing (6 tools)

| Tool | Description |
|------|-------------|
| index_project | Full project indexing |
| index_incremental | Changed files only |
| index_markdown_workspace | Markdown only |
| reindex_file | Single file reindex |
| get_indexing_status | Indexing progress |
| get_indexing_errors | Recent errors |

## Code Search (1 tool)

| Tool | Description |
|------|-------------|
| search_code | Hybrid lexical + vector |

## Analytics (4 tools)

| Tool | Description |
|------|-------------|
| get_indexing_stats | Stats per repository |
| get_memory_health | Memory system health |
| get_cache_stats | Cache hit rates |
| clear_cache | Clear L1/L2/L3 |

## Graph (4 tools)

| Tool | Description |
|------|-------------|
| get_graph_stats | Graph statistics |
| traverse_graph | Graph traversal |
| find_path | Shortest path |
| get_module_data | Module details |

## Configuration (2 tools)

| Tool | Description |
|------|-------------|
| switch_project | Change active repository |
| ping | Health check |

[... reste du contenu: protocole, config clients, tests, paramètres ...]
```

- [ ] **Step 2: Commit**

```bash
git add docs/MCP.md
git commit -m "docs: add MCP.md (v2, 33 tools)"
```

---

### Task 5: Créer API.md

**Files:**
- Create: `docs/API.md`

**Content:** Endpoints REST + schemas (~200 lignes)

- [ ] **Step 1: Créer API.md (basé sur DECISION_api_specification.md)**

Structure:
```markdown
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
| GET | /code/stats | Repository stats |
| GET | /code/graph/stats | Graph stats |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |

## Examples

```bash
# Create memory
curl -X POST http://localhost:8001/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "content": "Content"}'

# Search
curl "http://localhost:8001/v1/memories/search?q=authentication"
```

[... schemas Pydantic ...]
```

- [ ] **Step 2: Commit**

```bash
git add docs/API.md
git commit -m "docs: add API.md (v2)"
```

---

### Task 6: Créer ARCHITECTURE.md

**Files:**
- Create: `docs/ARCHITECTURE.md`

**Content:** Stack + pipeline + cache + DB schema (~250 lignes)

- [ ] **Step 1: Créer ARCHITECTURE.md (version nettoyée)**

Basé sur `docs/88_ARCHIVE/.../ARCHITECTURE.md` mais:
- Supprimer références HTMX
- Mettre à jour versions
- Ajouter schéma DB simplifié
- Ajouter pipeline indexation

Structure:
```markdown
# MnemoLite Architecture

## Technology Stack

- **Database:** PostgreSQL 18 + pgvector 0.8.1 + pg_trgm + pg_partman
- **API:** FastAPI + AsyncPG (Python 3.12+)
- **Cache:** Redis 7 (L2) + In-memory (L1)
- **Frontend:** Vue 3 SPA + Tailwind + SCADA design
- **MCP:** FastMCP 1.12.3

## Indexing Pipeline (7 steps)

1. File detection
2. Language identification
3. AST parsing (tree-sitter)
4. Chunking
5. Metadata extraction (LSP)
6. Dual embedding (TEXT + CODE)
7. Graph construction

## Triple-Layer Cache

```
L1 (In-Memory) → L2 (Redis) → L3 (PostgreSQL)
```

## Database Schema

### memories
| Column | Type |
|--------|------|
| id | UUID |
| title | VARCHAR(200) |
| content | TEXT |
| memory_type | VARCHAR(50) |
| embedding | halfvec(768) |
| created_at | TIMESTAMPTZ |
| deleted_at | TIMESTAMPTZ |

### code_chunks
| Column | Type |
|--------|------|
| id | UUID |
| repository | VARCHAR(100) |
| file_path | TEXT |
| chunk_type | VARCHAR(50) |
| source_code | TEXT |
| embedding | halfvec(768) |

[... continue ...]
```

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md (v2)"
```

---

## Phase 3: Validation

### Task 7: Vérifier cohérence

- [ ] **Step 1: Vérifier structure**

```bash
ls -la docs/
# Expected: README.md, QUICKSTART.md, MCP.md, API.md, ARCHITECTURE.md, 88_ARCHIVE/
```

- [ ] **Step 2: Vérifier 0 HTMX**

```bash
grep -r "hx-" docs/*.md || echo "0 HTMX references"
# Expected: nothing (ou message "0 HTMX references")
```

- [ ] **Step 3: Vérifier versions**

```bash
grep -h "v[0-9]" docs/*.md | head -20
# Expected: v5.0.0-dev, 33 tools, pgvector 0.8.1
```

- [ ] **Step 4: Vérifier 0 chemins hardcodés**

```bash
grep -r "/home/giak" docs/*.md || echo "0 hardcoded paths"
# Expected: nothing (ou message "0 hardcoded paths")
```

- [ ] **Step 5: Vérifier liens résolvent**

```bash
# Liens dans README.md
grep -oE '\[.*\]\((.*)\)' docs/README.md
# Vérifier chaque cible existe
```

- [ ] **Step 6: Commit validation**

```bash
git add docs/
git commit -m "docs: finalize v2 documentation"
```

---

## Critères de Succès

- [ ] 5 fichiers dans `docs/`
- [ ] 0 HTMX references
- [ ] Versions exactes (v5.0.0-dev, 33 tools)
- [ ] 0 lien cassé
- [ ] 0 chemin hardcodé
- [ ] README pointe vers les 4 autres
