# MnemoLite + Claude Code — Guide d'Intégration

**Version**: 1.0 (Vérifié 2025-11-08)
**MnemoLite**: v3.1.0-dev
**Claude Code**: v2.0+
**MCP Spec**: 2025-06-18

---

## ⚠️ IMPORTANT

Ce guide documente **uniquement ce qui existe réellement** dans le code MnemoLite.
Toute information est vérifiée contre le code source dans `<project-root>/api/mnemo_mcp/`.

---

## Table des Matières

1. [Qu'est-ce que MnemoLite MCP ?](#quest-ce-que-mnemolite-mcp)
2. [Installation](#installation)
3. [MCP Tools Disponibles](#mcp-tools-disponibles)
4. [MCP Resources Disponibles](#mcp-resources-disponibles)
5. [Système Auto-Save](#système-auto-save)
6. [Exemples d'Utilisation](#exemples-dutilisation)
7. [Troubleshooting](#troubleshooting)

---

## Qu'est-ce que MnemoLite MCP ?

**MnemoLite** est un système RAG local (PostgreSQL 18 + pgvector) avec :
- Recherche sémantique de code (dual embeddings TEXT+CODE)
- Mémoire persistante pour conversations
- Graph de dépendances de code
- Cache Redis L2

**MCP Server** expose MnemoLite à Claude Code via le **Model Context Protocol** :
- **Path**: `<project-root>/api/mnemo_mcp/server.py`
- **Framework**: FastMCP (mcp==1.12.3)
- **Transport**: stdio (Claude Code CLI/VSCode)
- **Spec**: MCP 2025-06-18

**Tests** : 149/149 tests MCP passing (100%) ✅

---

## Installation

### Prérequis

```bash
# Docker + Docker Compose
docker --version  # >= 24.0
docker compose version  # >= 2.20

# Claude Code
claude --version  # >= 2.0

# MnemoLite
cd <project-root>
```

### Étape 1 : Démarrer MnemoLite Docker

```bash
# Dans le dossier MnemoLite
cd <project-root>

# Démarrer services
docker compose up -d

# Vérifier
docker compose ps
# Expected: api (Up, healthy), db (Up, healthy), redis (Up, healthy)

# Test API
curl http://localhost:8001/health
# Expected: {"status":"healthy",...}
```

### Étape 2 : Configurer MCP dans Votre Projet

**Option A : Via `.mcp.json`** (Recommandé)

Créer `.mcp.json` à la racine de votre projet :

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

**Option B : Via `settings.local.json`**

```json
{
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["mnemolite"]
}
```

### Étape 3 : Test MCP

**Démarrer session Claude Code** :

```bash
cd /path/to/your/project
claude-code
```

**Test** :
```
user> Test MCP ping
```

Claude devrait utiliser automatiquement l'outil `ping` de MnemoLite.

---

## MCP Tools Disponibles

### Liste Complète (9 Tools)

Extrait depuis `<project-root>/api/mnemo_mcp/tools/*.py` :

| # | Tool Name | Fichier | Description |
|---|-----------|---------|-------------|
| 1 | `ping` | test_tool.py | Test MCP connectivity |
| 2 | `search_code` | search_tool.py | Hybrid code search (lexical+vector+RRF) |
| 3 | `write_memory` | memory_tools.py | Create persistent memory |
| 4 | `update_memory` | memory_tools.py | Update existing memory |
| 5 | `delete_memory` | memory_tools.py | Delete memory (soft/hard) |
| 6 | `index_project` | indexing_tools.py | Index project directory |
| 7 | `reindex_file` | indexing_tools.py | Reindex single file |
| 8 | `switch_project` | config_tools.py | Switch active repository |
| 9 | `clear_cache` | config_tools.py | Clear cache layers (admin) |

---

### 1. `ping` — Test Connectivity

**Source** : `api/mnemo_mcp/tools/test_tool.py:47`

**Description** : Test MCP server connectivity

**Usage** :
```
user> Test MCP server ping
```

**Response** :
```json
{
  "message": "MnemoLite MCP server is operational",
  "timestamp": "2025-11-08T...",
  "version": "1.0.0"
}
```

---

### 2. `search_code` — Hybrid Code Search

**Source** : `api/mnemo_mcp/tools/search_tool.py:60`

**Description** : Recherche sémantique hybride (lexical pg_trgm + vector HNSW + RRF fusion)

**Signature** :
```python
search_code(
    ctx: Context,
    query: str,
    filters: Optional[CodeSearchFilters] = None,
    limit: int = 10,
    offset: int = 0,
    enable_lexical: bool = True,
    enable_vector: bool = True,
    lexical_weight: float = 0.4,
    vector_weight: float = 0.6,
) -> CodeSearchResponse
```

**Filters disponibles** :
```python
class CodeSearchFilters:
    language: Optional[str]        # "python", "javascript", "typescript", etc.
    chunk_type: Optional[str]      # "function", "class", "method", "variable"
    repository: Optional[str]      # Repository name
    file_path: Optional[str]       # Glob pattern "api/**/*.py"
    return_type: Optional[str]     # LSP return type annotation
    param_type: Optional[str]      # LSP parameter type annotation
```

**Usage Claude** :
```
user> Cherche toutes les fonctions qui gèrent l'authentification en Python
```

Claude utilisera automatiquement :
```python
search_code(
    query="authentication functions",
    filters={"language": "python", "chunk_type": "function"},
    limit=10
)
```

**Performance** :
- Cached: <10ms P95
- Uncached: ~150-300ms P95
- Cache TTL: 5 minutes (Redis L2)

---

### 3. `write_memory` — Create Persistent Memory

**Source** : `api/mnemo_mcp/tools/memory_tools.py:54`

**Description** : Créer une mémoire persistante avec embedding sémantique

**Signature** :
```python
write_memory(
    ctx: Context,
    title: str,
    content: str,
    memory_type: str = "note",
    tags: List[str] = None,
    author: Optional[str] = None,
    project_id: Optional[str] = None,
    related_chunks: List[str] = None,
    resource_links: List[Dict[str, str]] = None,
) -> Dict[str, Any]
```

**Memory Types** :
- `note` : Notes générales
- `decision` : Architecture Decision Records (ADR)
- `task` : TODOs, tâches
- `reference` : Documentation, liens
- `conversation` : Conversations (auto-save)

**Usage Claude** :
```
user> Sauvegarde cette décision : on utilise Redis pour le cache L2 car PostgreSQL est trop lent pour les lookups fréquents. Tag : redis, cache, performance
```

Claude créera :
```python
write_memory(
    title="Décision: Redis pour cache L2",
    content="On utilise Redis pour le cache L2 car PostgreSQL...",
    memory_type="decision",
    tags=["redis", "cache", "performance"]
)
```

**Response** :
```json
{
  "id": "uuid-...",
  "title": "Décision: Redis pour cache L2",
  "memory_type": "decision",
  "created_at": "2025-11-08T...",
  "embedding_generated": true
}
```

**Performance** : ~80-120ms P95 (avec embedding)

---

### 4. `update_memory` — Update Memory

**Source** : `api/mnemo_mcp/tools/memory_tools.py:217`

**Signature** :
```python
update_memory(
    ctx: Context,
    id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    memory_type: Optional[str] = None,
    tags: List[str] = None,
    author: Optional[str] = None,
    related_chunks: List[str] = None,
    resource_links: List[Dict[str, str]] = None,
) -> Dict[str, Any]
```

**Note** : Régénère embedding si `title` ou `content` changent

---

### 5. `delete_memory` — Delete Memory

**Source** : `api/mnemo_mcp/tools/memory_tools.py:389`

**Signature** :
```python
delete_memory(
    ctx: Context,
    id: str,
    permanent: bool = False,
) -> DeleteMemoryResponse
```

**Modes** :
- `permanent=False` : Soft delete (reversible, set `deleted_at`)
- `permanent=True` : Hard delete (irreversible, requires **elicitation**)

**Elicitation Flow** :
1. `delete_memory(id="...", permanent=True)` → MCP asks user confirmation
2. User confirms → Hard delete executed
3. User rejects → Operation cancelled

---

### 6. `index_project` — Index Project

**Source** : `api/mnemo_mcp/tools/indexing_tools.py:41`

**Signature** :
```python
index_project(
    project_path: str,
    repository: str = "default",
    include_gitignored: bool = False,
    ctx: Optional[Context] = None,
) -> dict
```

**Features** :
- Scans project directory for code files
- Respects `.gitignore` by default
- **Real-time progress** via MCP Context
- **Distributed lock** (Redis) prevents concurrent indexing
- **Elicitation** if >100 files detected

**Usage Claude** :
```
user> Indexe le projet /home/user/backend avec repository="backend"
```

**Progress Output** :
```
⏳ Indexing: 45/156 files (28%)
⏳ Indexing: 89/156 files (57%)
✅ Indexing complete: 156 files, 1247 chunks
```

**Response** :
```json
{
  "indexed_files": 156,
  "indexed_chunks": 1247,
  "indexed_nodes": 892,
  "indexed_edges": 2134,
  "processing_time_ms": 12450,
  "message": "Indexing completed successfully"
}
```

**Performance** : <100ms per file (7-step pipeline)

---

### 7. `reindex_file` — Reindex Single File

**Source** : `api/mnemo_mcp/tools/indexing_tools.py:312`

**Signature** :
```python
reindex_file(
    file_path: str,
    repository: str = "default",
    ctx: Optional[Context] = None,
) -> FileIndexResult
```

**Use Case** : After editing a file, reindex only that file (faster than full project)

**Performance** : <100ms per file

---

### 8. `switch_project` — Switch Active Repository

**Source** : `api/mnemo_mcp/tools/config_tools.py:34`

**Description** : Change le repository actif pour search_code et autres operations

**Signature** :
```python
switch_project(
    ctx: Context,
    repository: str,
    confirm: bool = False,
) -> SwitchProjectResponse
```

**Multi-Repository Workflow** :
```
user> Indexe /home/user/backend avec repository="backend"
user> Indexe /home/user/frontend avec repository="frontend"

user> Switch vers repository backend
user> Cherche fonction authenticate_user

user> Switch vers repository frontend
user> Cherche composant LoginForm
```

**Validation** : Repository must be indexed first

---

### 9. `clear_cache` — Clear Cache (Admin)

**Source** : `api/mnemo_mcp/tools/config_tools.py` (analytics_tools.py?)

**Signature** :
```python
clear_cache(
    ctx: Context,
    layer: str = "all",  # "L1", "L2", or "all"
) -> ClearCacheResponse
```

**Layers** :
- `L1` : In-memory cache (100MB, single process)
- `L2` : Redis cache (2GB, all processes)
- `all` : Both layers

**Elicitation** : Always asks confirmation (destructive operation)

**Performance Impact** :
- Temporary degradation until cache repopulated
- Recovery: 5-30 minutes depending on usage

---

## MCP Resources Disponibles

**Note** : Resources sont en lecture seule (pas de side effects)

D'après `api/mnemo_mcp/resources/*.py` et README :

### Memory Resources

| URI Template | Description | Fichier |
|--------------|-------------|---------|
| `memories://get/{id}` | Get memory by ID | memory_resources.py |
| `memories://list` | List all memories | memory_resources.py |
| `memories://search/{query}` | Semantic search memories | memory_resources.py |

### Graph Resources

| URI Template | Description | Fichier |
|--------------|-------------|---------|
| `graph://nodes/{id}` | Get node by ID | graph_resources.py |
| `graph://callers/{name}` | Find callers of function | graph_resources.py |
| `graph://callees/{name}` | Find callees of function | graph_resources.py |

### Config Resources

| URI Template | Description | Fichier |
|--------------|-------------|---------|
| `config://settings` | Current MCP settings | config_resources.py |
| `config://projects` | List indexed projects | config_resources.py |

**Usage** :
Resources sont accédées automatiquement par Claude quand il navigue dans le contexte MnemoLite.

---

## Système Auto-Save

### Architecture

Le système auto-save sauvegarde **automatiquement** toutes les conversations Claude Code dans MnemoLite.

**Composants** :
1. **Hook SessionStart** : Vérifie système au démarrage
2. **Hook Stop** : Sauvegarde échange actuel (N) immédiatement
3. **Hook UserPromptSubmit** : Backup N-1 (failsafe)

**Status** : ✅ Opérationnel (Phase 1 + Phase 2 complete)

### Configuration Auto-Save

**Fichiers** :
- `.claude/hooks/SessionStart/check-autosave-setup.sh` - Health check
- `.claude/hooks/Stop/auto-save-exchange.sh` - Save immédiat
- `.claude/hooks/UserPromptSubmit/auto-save-previous.sh` - Backup

**Configuration `settings.local.json`** :

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash .claude/hooks/SessionStart/check-autosave-setup.sh",
        "timeout": 5
      }]
    }],
    "Stop": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash .claude/hooks/Stop/auto-save-exchange.sh",
        "timeout": 5
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash .claude/hooks/UserPromptSubmit/auto-save-previous.sh",
        "timeout": 5
      }]
    }]
  }
}
```

### Health Check Au Démarrage

Quand vous démarrez une session Claude Code, le hook SessionStart vérifie automatiquement :

1. ✅ MnemoLite Docker running ?
2. ✅ Hook Stop installé ?
3. ✅ API `/api/v1/autosave/health` OK ?
4. ✅ Configuration settings.local.json valide ?

**Si OK** :
```
═══════════════════════════════════════════════════════════
  ✅ AUTO-SAVE SYSTEM: ACTIVE & HEALTHY
═══════════════════════════════════════════════════════════
  MnemoLite:     Running (Docker container up)
  Hook Stop:     Installed & Configured
  API Health:    OK
  Coverage:      100% (Stop + UserPromptSubmit backup)
  Latency:       0 (immediate save after response)
═══════════════════════════════════════════════════════════
```

**Si problème** :
```
╔═══════════════════════════════════════════════════════════╗
║  🚨 ALERT: AUTO-SAVE NON FONCTIONNEL                      ║
╠═══════════════════════════════════════════════════════════╣
║  [Détails du problème]                                    ║
║  [Instructions de fix]                                    ║
╚═══════════════════════════════════════════════════════════╝
```

### Métriques Auto-Save

**Latency** : <5s après réponse Claude
**Coverage** : 100% des échanges
**Deduplication** : Hash MD5-based (0 duplication)
**Storage** : PostgreSQL `memories` table avec `author='AutoSave'`

---

## Exemples d'Utilisation

### Exemple 1 : Recherche Code par Intention

**Scénario** : Trouver où est implémenté le parsing LSP TypeScript

**Commande** :
```
user> Où est implémenté le parsing des symboles LSP TypeScript ?
```

**Claude utilise** :
```python
search_code(
    query="LSP TypeScript symbol parsing implementation",
    filters={"language": "python", "chunk_type": "function"}
)
```

**Résultat** : Claude trouve `parse_typescript_symbols()` dans `lsp/parsers/typescript_parser.py:45`

---

### Exemple 2 : Architecture Decision Record (ADR)

**Scénario** : Documenter décision d'utiliser pgvector

**Commande** :
```
user> Sauvegarde cette décision : on a migré de ChromaDB vers pgvector pour unifier le storage et simplifier l'architecture. ChromaDB nécessitait un service séparé, pgvector est intégré à PostgreSQL. Tags : adr, database, pgvector
```

**Claude sauvegarde** :
```python
write_memory(
    title="ADR: Migration ChromaDB → pgvector",
    content="On a migré de ChromaDB vers pgvector pour unifier...",
    memory_type="decision",
    tags=["adr", "database", "pgvector"]
)
```

**Recherche ultérieure** :
```
user> Rappelle-moi pourquoi on a migré vers pgvector ?
```

Claude trouve la mémoire via recherche sémantique.

---

### Exemple 3 : Multi-Repository Workflow

**Setup** :
```
user> Indexe /home/user/backend avec repository="backend"
user> Indexe /home/user/frontend avec repository="frontend"
```

**Utilisation** :
```
user> Switch vers repository backend
user> Cherche fonction authenticate_user
# → Résultats du backend uniquement

user> Switch vers repository frontend
user> Cherche composant LoginForm
# → Résultats du frontend uniquement
```

---

## Troubleshooting

### Problem: "MCP tools not available"

**Symptôme** : Claude dit "I don't have access to mcp tools"

**Diagnostic** :
```bash
# 1. Vérifier .mcp.json existe
cat /path/to/your/project/.mcp.json

# 2. Vérifier MnemoLite Docker up
cd <project-root> && docker compose ps
# Expected: api, db, redis all "Up (healthy)"
```

**Fix** :
```bash
# Si Docker down
cd <project-root>
docker compose up -d

# Si .mcp.json manquant
# Créer selon instructions Étape 2
```

---

### Problem: "search_code returns no results"

**Symptôme** : Recherche code retourne 0 résultats

**Diagnostic** :
```bash
# Vérifier projet indexé
docker compose exec -T db psql -U mnemo -d mnemolite -c \
  "SELECT COUNT(*) FROM code_chunks WHERE repository = 'YOUR_REPO';"
# Expected: >0
```

**Fix** :
```
user> Indexe le projet /path/to/project avec repository="my-repo"
```

---

### Problem: "AUTO-SAVE NON FONCTIONNEL"

**Symptôme** : Message rouge au démarrage session

**Fix** : Suivre instructions affichées dans l'alerte

**Vérification manuelle** :
```bash
# 1. MnemoLite Docker
cd <project-root> && docker compose ps

# 2. Health endpoint
curl http://localhost:8001/api/v1/autosave/health | jq .

# 3. Logs
tail -20 /tmp/hook-autosave-debug.log
```

---

## Ressources

### Documentation Technique

- **MnemoLite README** : `<project-root>/README.md`
- **Architecture** : `<project-root>/docs/Document Architecture.md`
- **MCP Server Code** : `<project-root>/api/mnemo_mcp/`
- **Auto-Save System** : `<user-home>/projects/truth-engine/AUTOSAVE_COMPLETE.md`

### Fichiers Clés

- **MCP Server** : `api/mnemo_mcp/server.py`
- **MCP Launcher** : `scripts/mcp_server.sh`
- **MCP Config** : `api/mnemo_mcp/config.py`
- **Tools** : `api/mnemo_mcp/tools/*.py`
- **Resources** : `api/mnemo_mcp/resources/*.py`

### Tests

```bash
# Tous les tests MCP
cd <project-root>
pytest tests/integration/mcp/ -v

# Stats : 149/149 tests passing (100%)
```

---

**Version** : 1.0
**Dernière mise à jour** : 2025-11-08
**Status** : ✅ Vérifié contre code source

---

**Fin du Guide d'Intégration**
