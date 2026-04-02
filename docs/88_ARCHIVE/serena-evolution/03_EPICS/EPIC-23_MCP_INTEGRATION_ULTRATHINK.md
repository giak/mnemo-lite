# EPIC-23: MCP (Model Context Protocol) Integration - ULTRATHINK BRAINSTORM

**Date**: 2025-10-24
**Author**: Claude Code + Giak
**Status**: 🧠 DEEP BRAINSTORMING PHASE
**Inspiration**: serena-main MCP architecture

---

## 🎯 Vision Stratégique

**Objectif Global**: Transformer MnemoLite d'une API interne en un **MCP Server** accessible aux LLM (Claude, GPT, etc.) pour offrir une **mémoire cognitive augmentée** et des **capacités de recherche de code sémantique** via le protocole MCP.

**Positionnement**: MnemoLite MCP = "Serena pour la recherche sémantique" + "RAG pour code" + "PostgreSQL 18 cognitive memory"

---

## 🔍 Analyse de l'Existant: Serena MCP

### Architecture Serena (Référence)

**Composants Clés** (analysés depuis `serena-main/`):

1. **FastMCP Server** (`mcp.py`)
   - Basé sur `mcp.server.fastmcp.FastMCP`
   - Conversion `Tool` → `MCPTool` automatique
   - Support OpenAI-compatible schemas
   - Context/Mode system (ide-assistant, agent, desktop-app)

2. **Tools System** (~1800 lignes, 8 fichiers)
   - `tools_base.py`: Base class `Tool(Component)` + Markers
   - `memory_tools.py`: WriteMemory, ReadMemory, ListMemories, DeleteMemory (66 lignes)
   - `file_tools.py`: ListDir, FindFile, SearchPattern, ReplaceRegex
   - `symbol_tools.py`: FindSymbol, GetSymbolsOverview, ReplaceSymbolBody
   - `config_tools.py`: SwitchModes, RemoveProject, Onboarding
   - `workflow_tools.py`: Meta-operations, reflection tools

3. **Core Components**
   - `SerenaAgent`: Orchestrateur central (project, tools, config)
   - `SolidLanguageServer`: Wrapper LSP multi-langages
   - `MemoriesManager`: Stockage markdown dans `.serena/memories/`
   - `Project`: Per-project configuration

4. **Configuration Hierarchy**
   - Contexts (ide-assistant, agent, desktop-app)
   - Modes (planning, editing, interactive, one-shot)
   - Tool overrides per context/mode

### Leçons Clés de Serena

✅ **Modularité**: Chaque tool = classe indépendante héritant de `Tool`
✅ **Markers**: Catégorisation des outils (CanEdit, SymbolicRead, Optional)
✅ **Memory System**: Markdown-based, projet-specific, persistant
✅ **LSP Integration**: Language Server Protocol pour analyse symbolique
✅ **Context-aware**: Outils adaptés au contexte d'utilisation
✅ **OpenAI-compatible**: Schemas convertis pour compatibilité maximale
✅ **Async-first**: Architecture asynchrone native

---

## 🧠 Brainstorming: MnemoLite MCP Architecture

### 1. Core Value Proposition

**MnemoLite MCP = Code Intelligence Memory Server**

**Capacités Uniques vs Serena**:
- 🔍 **Recherche sémantique** (embeddings vectoriels)
- 🗄️ **PostgreSQL 18 + pgvector** (recherche hybride lexical+semantic)
- 📊 **Cache L1+L2+L3** (Redis, in-memory, PostgreSQL)
- 🔗 **Graphe de code** (relations entre chunks)
- 📈 **Observabilité avancée** (EPIC-22, métriques, alertes)
- 🎯 **Dual embeddings** (TEXT + CODE models)

**Positionnement**:
- Serena = **Symbol-level editing** (LSP-based, syntactic)
- MnemoLite = **Semantic search & memory** (embeddings-based, semantic)
- **Complémentaires**: Serena édite, MnemoLite recherche et mémorise

### 2. MnemoLite MCP Tools: Proposition Initiale

#### 📦 Catégorie 1: Code Search & Retrieval (Core Value)

**`search_code`** (Priority: CRITICAL)
```python
def search_code(
    query: str,
    mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
    language: str | None = None,
    limit: int = 10,
    min_score: float = 0.7
) -> List[CodeChunkResult]:
    """
    Search code semantically or lexically.

    Returns:
        List of code chunks with:
        - source_code, file_path, line_start/end
        - chunk_type (function, class, method, etc.)
        - language, name_path (qualified name)
        - score (relevance), metadata
    """
```

**`find_similar_code`** (Priority: HIGH)
```python
def find_similar_code(
    code_snippet: str,
    threshold: float = 0.8,
    exclude_file: str | None = None,
    limit: int = 5
) -> List[CodeChunkResult]:
    """
    Find code similar to a given snippet (duplication detection, refactoring opportunities).
    Uses semantic embeddings for deep similarity.
    """
```

**`search_by_qualified_name`** (Priority: HIGH)
```python
def search_by_qualified_name(
    qualified_name: str,
    fuzzy: bool = True
) -> List[CodeChunkResult]:
    """
    Search by qualified name (e.g., "MyClass.myMethod", "module.function").
    Leverages EPIC-11 name_path generation.
    """
```

**`get_code_chunk_by_id`** (Priority: MEDIUM)
```python
def get_code_chunk_by_id(chunk_id: str) -> CodeChunkDetail:
    """Retrieve full code chunk details by UUID."""
```

#### 📊 Catégorie 2: Code Graph & Relationships

**`get_code_graph`** (Priority: HIGH)
```python
def get_code_graph(
    chunk_id: str | None = None,
    depth: int = 1,
    relation_types: List[str] | None = None
) -> CodeGraph:
    """
    Get code graph (calls, imports, inheritance, etc.).

    Args:
        chunk_id: Starting node (if None, returns project overview)
        depth: Graph depth (1 = direct neighbors, 2 = neighbors of neighbors)
        relation_types: Filter by ["calls", "imports", "inherits", "uses"]

    Returns:
        Graph with nodes (code chunks) and edges (relationships).
    """
```

**`find_callers`** (Priority: MEDIUM)
```python
def find_callers(qualified_name: str, limit: int = 20) -> List[CodeChunkResult]:
    """Find all code chunks that call/reference the given symbol."""
```

**`find_callees`** (Priority: MEDIUM)
```python
def find_callees(qualified_name: str, limit: int = 20) -> List[CodeChunkResult]:
    """Find all symbols called by the given code chunk."""
```

#### 🗄️ Catégorie 3: Project Memory & Context

**`write_project_memory`** (Priority: HIGH)
```python
def write_project_memory(
    memory_name: str,
    content: str,
    tags: List[str] | None = None,
    embedding: bool = True
) -> str:
    """
    Write project-specific memory (decisions, architecture notes, TODO, etc.).

    Stored in PostgreSQL `memories` table with optional embeddings for semantic retrieval.
    """
```

**`search_project_memory`** (Priority: HIGH)
```python
def search_project_memory(
    query: str,
    mode: Literal["semantic", "lexical"] = "semantic",
    tags: List[str] | None = None,
    limit: int = 5
) -> List[MemoryResult]:
    """
    Search project memories semantically or by tags.
    Useful for retrieving past decisions, architecture notes, etc.
    """
```

**`list_project_memories`** (Priority: MEDIUM)
```python
def list_project_memories(tags: List[str] | None = None) -> List[MemoryMetadata]:
    """List all project memories with metadata (name, created_at, size, tags)."""
```

**`delete_project_memory`** (Priority: LOW)
```python
def delete_project_memory(memory_name: str) -> str:
    """Delete a project memory (only if explicitly requested by user)."""
```

#### 📁 Catégorie 4: Project Indexing & Management

**`index_project`** (Priority: CRITICAL)
```python
def index_project(
    directory: str,
    languages: List[str] | None = None,
    exclude_patterns: List[str] | None = None,
    force_reindex: bool = False
) -> IndexResult:
    """
    Index a codebase (parse, chunk, embed, store in PostgreSQL).

    Returns:
        - total_files, total_chunks, duration
        - languages detected
        - indexed_at timestamp
    """
```

**`get_index_status`** (Priority: MEDIUM)
```python
def get_index_status() -> IndexStatus:
    """
    Get indexing status for current project.

    Returns:
        - total_chunks, total_files, languages
        - last_indexed_at, cache_stats
        - embedding_model used
    """
```

**`reindex_file`** (Priority: MEDIUM)
```python
def reindex_file(file_path: str) -> IndexResult:
    """Re-index a single file (useful after edits)."""
```

#### 📈 Catégorie 5: Analytics & Observability

**`get_search_analytics`** (Priority: LOW)
```python
def get_search_analytics(period_hours: int = 24) -> SearchAnalytics:
    """
    Get search performance analytics (EPIC-22 integration).

    Returns:
        - query_count, avg_latency, cache_hit_rate
        - popular_queries, slow_queries
    """
```

**`get_cache_stats`** (Priority: MEDIUM)
```python
def get_cache_stats() -> CacheStats:
    """
    Get L1/L2/L3 cache statistics.

    Returns:
        - hit_rate, memory_usage, eviction_count
        - per-layer breakdown
    """
```

**`clear_cache`** (Priority: LOW)
```python
def clear_cache(layer: Literal["L1", "L2", "L3", "all"] = "all") -> str:
    """Clear cache layers (admin operation)."""
```

#### 🔧 Catégorie 6: Configuration & Utilities

**`switch_project`** (Priority: MEDIUM)
```python
def switch_project(project_name: str) -> str:
    """Switch to a different indexed project."""
```

**`list_projects`** (Priority: LOW)
```python
def list_projects() -> List[ProjectInfo]:
    """List all indexed projects with metadata."""
```

**`get_supported_languages`** (Priority: LOW)
```python
def get_supported_languages() -> List[LanguageInfo]:
    """List supported languages with parser info."""
```

### 3. Architecture Technique MnemoLite MCP

#### Stack Proposé

```
┌─────────────────────────────────────────────────────────┐
│  LLM Client (Claude, GPT, etc.)                         │
│  via MCP Protocol (stdio/http)                          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  MnemoLite MCP Server (FastAPI/FastMCP)                 │
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Tools Layer (25+ MCP Tools)                    │    │
│  │  - search_code, find_similar_code               │    │
│  │  - get_code_graph, find_callers/callees         │    │
│  │  - write/search_project_memory                  │    │
│  │  - index_project, reindex_file                  │    │
│  │  - get_cache_stats, get_search_analytics        │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                     │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  Services Layer (Existing)                      │    │
│  │  - HybridCodeSearchService                      │    │
│  │  - CodeChunkRepository                          │    │
│  │  - DualEmbeddingService                         │    │
│  │  - CodeGraphService (EPIC-14)                   │    │
│  │  - MetricsCollector (EPIC-22)                   │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                     │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  Data Layer                                      │    │
│  │  - PostgreSQL 18 (code_chunks, memories, ...)   │    │
│  │  - Redis L2 Cache                               │    │
│  │  - Dual Embeddings (TEXT + CODE)                │    │
│  └──────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

#### Fichiers Proposés (Nouveau Module `api/mcp/`)

```
api/
├── mcp/                          # NOUVEAU MODULE
│   ├── __init__.py
│   ├── server.py                 # FastMCP server initialization
│   ├── tools/                    # MCP Tools
│   │   ├── __init__.py
│   │   ├── base.py               # BaseMCPTool, markers, utilities
│   │   ├── search_tools.py       # search_code, find_similar_code, etc.
│   │   ├── graph_tools.py        # get_code_graph, find_callers/callees
│   │   ├── memory_tools.py       # write/search/list/delete_project_memory
│   │   ├── indexing_tools.py     # index_project, get_index_status, reindex_file
│   │   ├── analytics_tools.py    # get_search_analytics, get_cache_stats
│   │   └── config_tools.py       # switch_project, list_projects, get_supported_languages
│   ├── models.py                 # Pydantic models for MCP responses
│   ├── context.py                # MCP context management (project state, config)
│   └── cli.py                    # CLI entrypoint: `mnemolite-mcp-server`
├── main.py                       # Existing FastAPI app (REST API)
├── services/                     # Existing services (reused by MCP tools)
├── routes/                       # Existing REST routes
└── ...
```

#### Dépendances Nouvelles

```toml
# pyproject.toml additions
[project.dependencies]
fastmcp = "^0.4.0"              # FastMCP server (Anthropic's official library)
docstring-parser = "^0.16"       # Parse docstrings for tool descriptions
```

#### Transport Layer: stdio vs HTTP

**Option 1: stdio (Recommandé pour Claude Desktop/Code)**
```bash
# Configuration Claude Desktop (~/.config/claude/claude_desktop_config.json)
{
  "mcpServers": {
    "mnemolite": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/user/mnemolite", "mnemolite-mcp-server", "--project", "/path/to/project"]
    }
  }
}
```

**Option 2: HTTP/SSE (Pour serveurs distants, scaling)**
```bash
# Server mode
uvicorn api.mcp.server:mcp_app --host 0.0.0.0 --port 8002

# Configuration Claude Desktop (HTTP transport)
{
  "mcpServers": {
    "mnemolite": {
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

---

## 🎯 EPIC-23: Stories Proposées

### Phase 1: Foundation (8 pts)

**Story 23.1: MCP Server Bootstrap** (3 pts)
- Fichiers: `api/mcp/server.py`, `api/mcp/cli.py`, `api/mcp/tools/base.py`
- Objectif: FastMCP server fonctionnel avec 1 tool de test
- AC:
  - ✅ `mnemolite-mcp-server` CLI lancé sans erreur
  - ✅ Connexion via Claude Desktop réussie
  - ✅ 1 tool de test (`ping`) appelle et retourne "pong"

**Story 23.2: Core Search Tools** (3 pts)
- Fichiers: `api/mcp/tools/search_tools.py`
- Tools: `search_code`, `find_similar_code`, `search_by_qualified_name`
- Objectif: Capacités de recherche sémantique via MCP
- AC:
  - ✅ `search_code` retourne résultats pertinents (hybrid mode)
  - ✅ `find_similar_code` détecte code similaire
  - ✅ `search_by_qualified_name` utilise EPIC-11 name_path

**Story 23.3: Project Memory System** (2 pts)
- Fichiers: `api/mcp/tools/memory_tools.py`, nouvelle table `memories`
- Tools: `write_project_memory`, `search_project_memory`, `list_project_memories`
- Objectif: Mémoire persistante projet-specific
- AC:
  - ✅ Mémoires stockées en PostgreSQL avec embeddings
  - ✅ Recherche sémantique dans mémoires fonctionnelle
  - ✅ Tags et métadonnées supportés

### Phase 2: Advanced Features (7 pts)

**Story 23.4: Code Graph Tools** (3 pts)
- Fichiers: `api/mcp/tools/graph_tools.py`
- Tools: `get_code_graph`, `find_callers`, `find_callees`
- Objectif: Navigation relationnelle via MCP
- AC:
  - ✅ Graphe retourné avec nodes/edges
  - ✅ Depth et relation_types filtering fonctionnels
  - ✅ Intégration EPIC-14 code graph

**Story 23.5: Project Indexing** (2 pts)
- Fichiers: `api/mcp/tools/indexing_tools.py`
- Tools: `index_project`, `get_index_status`, `reindex_file`
- Objectif: Gestion indexation via MCP
- AC:
  - ✅ Indexation complète projet depuis MCP
  - ✅ Statut indexation visible
  - ✅ Réindexation fichier individuel

**Story 23.6: Analytics & Observability** (2 pts)
- Fichiers: `api/mcp/tools/analytics_tools.py`
- Tools: `get_search_analytics`, `get_cache_stats`, `clear_cache`
- Objectif: Monitoring via MCP (intégration EPIC-22)
- AC:
  - ✅ Analytics search visibles via MCP
  - ✅ Cache stats retournées
  - ✅ Clear cache fonctionnel

### Phase 3: Polish & Integration (4 pts)

**Story 23.7: Configuration & Utilities** (1 pt)
- Fichiers: `api/mcp/tools/config_tools.py`
- Tools: `switch_project`, `list_projects`, `get_supported_languages`
- AC:
  - ✅ Switch project fonctionnel
  - ✅ Liste projets avec métadonnées
  - ✅ Langages supportés listés

**Story 23.8: HTTP Transport Support** (2 pts)
- Fichiers: `api/mcp/server.py` (HTTP mode)
- Objectif: Support transport HTTP/SSE pour serveurs distants
- AC:
  - ✅ MCP server accessible via HTTP
  - ✅ SSE events pour streaming
  - ✅ Authentication support (token-based)

**Story 23.9: Documentation & Examples** (1 pt)
- Fichiers: `docs/mcp/`, `examples/mcp/`
- Objectif: Documentation complète MCP usage
- AC:
  - ✅ Guide installation Claude Desktop
  - ✅ Exemples d'usage pour chaque tool
  - ✅ Troubleshooting guide

**Total EPIC-23**: 19 story points

---

## 🚀 Avantages MnemoLite MCP

### Pour les Utilisateurs

1. **LLM-Native Code Search**
   - Claude/GPT peuvent rechercher code sémantiquement
   - Pas besoin de UI, tout via conversation naturelle
   - Contexte projet automatique

2. **Memory Augmentation**
   - LLM peut écrire/lire mémoires projet
   - Persistance décisions architecturales
   - Continuité entre sessions

3. **Code Understanding**
   - Graphe de code explorable via LLM
   - Relations automatiques (calls, imports, etc.)
   - Navigation contextuelle

### Pour les Développeurs

1. **API Unifiée**
   - REST API (existing) + MCP (new)
   - Même services backend réutilisés
   - Zero duplication

2. **Observabilité**
   - EPIC-22 metrics automatiques
   - Monitoring usage MCP tools
   - Performance analytics

3. **Extensibilité**
   - Facile d'ajouter nouveaux tools
   - Base class `BaseMCPTool` réutilisable
   - Markers pour catégorisation

---

## 🤔 Questions Ouvertes & Décisions Architecturales

### Q1: Migrations SQL pour `memories` table?

**Option A: Nouvelle table dédiée**
```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name VARCHAR(255) NOT NULL UNIQUE,
    content TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    embedding VECTOR(768),  -- Optional embedding pour semantic search
    metadata JSONB DEFAULT '{}'::jsonb
);
```

**Option B: Réutiliser table existante (events? custom?)**
- Avantage: Pas de migration
- Inconvénient: Structure pas optimale

**Recommandation**: Option A (table dédiée, clean separation)

### Q2: FastMCP vs Implémentation Custom?

**FastMCP Pros**:
- ✅ Officiel Anthropic
- ✅ Moins de code boilerplate
- ✅ Schemas Pydantic automatiques
- ✅ Support stdio + HTTP

**Custom Implementation Pros**:
- ✅ Contrôle total
- ✅ Optimisations spécifiques

**Recommandation**: FastMCP (rapid prototyping, standard)

### Q3: Séparation MCP Server vs REST API?

**Option A: Processus séparés**
```bash
# Terminal 1: REST API (existing)
uvicorn api.main:app --port 8001

# Terminal 2: MCP Server (new)
mnemolite-mcp-server --project /path/to/project
```

**Option B: Même processus, 2 transports**
```python
# api/main.py
app = FastAPI()  # REST API
mcp_app = FastMCP()  # MCP Server

# Shared services layer
```

**Recommandation**: Option A (séparation processus, plus flexible)

### Q4: Authentication pour MCP HTTP transport?

**Options**:
1. Token-based (JWT)
2. API key
3. No auth (localhost only)

**Recommandation**: API key simple pour MVP, JWT pour production

### Q5: Caching Strategy pour MCP Tools?

**Problème**: MCP tools appelés fréquemment, latence critique

**Solution**: Réutiliser L1/L2/L3 cache existant
- L1: In-memory (tool results caching)
- L2: Redis (search results, graph queries)
- L3: PostgreSQL (persistent)

**Implémentation**: Décorateur `@mcp_cache(ttl=300)` sur tools

---

## 📋 Checklist Implémentation

### Prerequisites
- [ ] Lire spec MCP officielle: https://modelcontextprotocol.io/specification/2025-06-18
- [ ] Analyser code Serena MCP en détail (fait ✅)
- [ ] Tester FastMCP hello-world
- [ ] Configurer Claude Desktop avec MCP test

### Phase 1: Bootstrap (Week 1)
- [ ] Story 23.1: MCP Server Bootstrap
  - [ ] `api/mcp/server.py` avec FastMCP
  - [ ] `api/mcp/cli.py` entrypoint
  - [ ] `api/mcp/tools/base.py` base classes
  - [ ] Test connexion Claude Desktop

- [ ] Story 23.2: Core Search Tools
  - [ ] `search_code` tool
  - [ ] `find_similar_code` tool
  - [ ] `search_by_qualified_name` tool
  - [ ] Tests intégration

- [ ] Story 23.3: Project Memory
  - [ ] Migration SQL `memories` table
  - [ ] `write_project_memory` tool
  - [ ] `search_project_memory` tool
  - [ ] Tests CRUD memories

### Phase 2: Advanced (Week 2)
- [ ] Story 23.4: Code Graph Tools
- [ ] Story 23.5: Project Indexing
- [ ] Story 23.6: Analytics & Observability

### Phase 3: Polish (Week 3)
- [ ] Story 23.7: Configuration & Utilities
- [ ] Story 23.8: HTTP Transport
- [ ] Story 23.9: Documentation & Examples

---

## 🎓 Références & Ressources

### Model Context Protocol (MCP)
- **Spec officielle**: https://modelcontextprotocol.io/specification/2025-06-18
- **FastMCP docs**: https://github.com/jlowin/fastmcp (ou repo Anthropic officiel)
- **MCP Registry**: https://mcp.so/

### Serena MCP (Inspiration)
- **GitHub**: https://github.com/oraios/serena
- **Code local**: `/home/giak/Work/MnemoLite/serena-main/`
- **Docs**: `serena-main/src/serena/mcp.py`, `tools/*.py`

### MnemoLite (Base)
- **EPIC-11**: name_path generation (qualified names)
- **EPIC-14**: Code graph (relations)
- **EPIC-18**: Dual embeddings (TEXT + CODE)
- **EPIC-22**: Observabilité avancée (metrics, alerts)

---

## 💡 Idées Futures (Post-MVP)

### Advanced Tools
- `refactor_code`: Suggest refactoring based on similar code detection
- `detect_code_smells`: Analyze code quality (duplication, complexity)
- `generate_tests`: Auto-generate tests for code chunks
- `explain_code`: LLM-friendly code explanations with context

### Integrations
- **GitHub**: PR analysis, code review suggestions
- **VSCode Extension**: MnemoLite MCP directly in IDE
- **Agno Framework**: Multi-agent orchestration
- **Langchain/LlamaIndex**: RAG integration

### Multi-Project Support
- Cross-project code search
- Shared memories (organization-level)
- Project similarity analysis

### Performance Optimizations
- Incremental indexing (watch file changes)
- Distributed embeddings generation
- PostgreSQL read replicas for scaling

---

## 🎯 Critères de Succès EPIC-23

### Metrics Quantitatifs
- ✅ 25+ MCP tools fonctionnels
- ✅ <100ms latency moyenne (search_code)
- ✅ >90% cache hit rate (L2 Redis)
- ✅ 19 story points completed
- ✅ 0 breaking changes API REST existante

### Metrics Qualitatifs
- ✅ Claude Desktop integration smooth
- ✅ Documentation complète et claire
- ✅ Developer experience excellent (easy to add tools)
- ✅ Production-ready (error handling, logging)

### User Acceptance
- ✅ LLM peut rechercher code en langage naturel
- ✅ Memories persistantes entre sessions
- ✅ Graphe de code navigable via conversation
- ✅ Indexation projet simple et rapide

---

**Status**: 🧠 ULTRATHINK COMPLET - Prêt pour validation et EPIC creation
**Next Steps**:
1. Review avec Giak
2. Créer EPIC-23_README.md officiel
3. Décomposer en stories détaillées
4. Commencer Story 23.1 (Bootstrap)
