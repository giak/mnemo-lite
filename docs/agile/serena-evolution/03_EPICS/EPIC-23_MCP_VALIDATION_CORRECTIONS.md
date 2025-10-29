# EPIC-23 MCP Integration - VALIDATION & CORRECTIONS

**Date**: 2025-10-24
**Status**: 🔍 DOUBLE-CHECK COMPLET via Web Research
**Sources**: Specs officielles MCP, SDK Python, FastMCP tutorials, Serena codebase

---

## ✅ CE QUI ÉTAIT CORRECT dans l'ULTRATHINK

### Architecture Générale ✓
- ✅ FastMCP comme base (confirmé: c'est dans le SDK officiel `mcp`)
- ✅ stdio transport pour Claude Desktop
- ✅ HTTP/SSE transport pour serveurs distants
- ✅ Réutilisation services backend existants
- ✅ Séparation processus REST API vs MCP Server
- ✅ Structure modulaire avec `api/mcp/tools/`

### Concepts Clés ✓
- ✅ MnemoLite = "Semantic search & memory" vs Serena = "Symbol editing"
- ✅ Positionnement complémentaire
- ✅ PostgreSQL 18 + pgvector + Redis cache
- ✅ Dual embeddings (TEXT + CODE)
- ✅ Integration EPIC-22 (observability)

### Dépendances ✓
- ✅ Installation: `uv add "mcp[cli]"` (correct, FastMCP inclus)
- ✅ MCP Inspector pour debug
- ✅ docstring-parser pour descriptions

---

## ❌ ERREURS & MANQUES CRITIQUES

### 🚨 ERREUR #1: Confusion Tools vs Resources vs Prompts

**Problème**: J'ai tout mis en "Tools" mais MCP a 3 types d'interactions distinctes!

**Spec MCP Officielle**:
```
- Tools: Model-controlled functions (POST-like, side effects)
- Resources: Application-controlled data (GET-like, no side effects)
- Prompts: User-controlled templates (UI elements)
```

**CORRECTION MAJEURE**:

#### 🔧 Tools (Write Operations, Side Effects)
```python
@mcp.tool()
def index_project(directory: str, ...) -> IndexResult:
    """Index a codebase (writes to PostgreSQL)."""

@mcp.tool()
def write_project_memory(memory_name: str, content: str) -> str:
    """Write project memory (database write)."""

@mcp.tool()
def clear_cache(layer: str) -> str:
    """Clear cache (side effect)."""

@mcp.tool()
def reindex_file(file_path: str) -> IndexResult:
    """Re-index single file (database write)."""
```

#### 📄 Resources (Read Operations, No Side Effects)
```python
@mcp.resource("code://search/{query}")
def search_code(query: str, mode: str, ...) -> List[CodeChunk]:
    """Search code semantically (read-only)."""

@mcp.resource("code://chunk/{chunk_id}")
def get_code_chunk(chunk_id: str) -> CodeChunkDetail:
    """Get code chunk by ID (read-only)."""

@mcp.resource("project://status")
def get_index_status() -> IndexStatus:
    """Get indexing status (read-only)."""

@mcp.resource("project://memories")
def list_project_memories(tags: Optional[List[str]]) -> List[Memory]:
    """List memories (read-only)."""

@mcp.resource("cache://stats")
def get_cache_stats() -> CacheStats:
    """Get cache statistics (read-only)."""

@mcp.resource("graph://nodes/{chunk_id}")
def get_code_graph(chunk_id: str, depth: int) -> CodeGraph:
    """Get code graph (read-only)."""
```

#### 💡 Prompts (User Templates, UI Elements)
```python
@mcp.prompt()
def analyze_codebase(language: str = "all") -> str:
    """Generate prompt to analyze codebase architecture."""
    return f"Analyze the {language} codebase structure and provide insights on:\n- Architecture patterns\n- Code organization\n- Potential improvements"

@mcp.prompt()
def find_refactoring_opportunities(focus: str = "all") -> str:
    """Generate prompt to find refactoring opportunities."""
    return f"Search for code that could benefit from refactoring, focusing on: {focus}"

@mcp.prompt()
def security_audit(severity: str = "high") -> str:
    """Generate prompt for security audit."""
    return f"Perform security audit and report {severity} severity issues"

@mcp.prompt()
def generate_tests_for(chunk_id: str) -> str:
    """Generate prompt to create tests for specific code."""
    return f"Generate comprehensive tests for code chunk {chunk_id}"
```

**Impact**:
- 📉 ~15 "tools" deviennent "resources"
- 📈 +4-6 nouveaux "prompts"
- 🎯 Plus conforme au design pattern MCP

---

### 🚨 ERREUR #2: Version Spec MCP Obsolète

**Problème**: J'ai mentionné spec `2025-03-26` mais la version actuelle est `2025-06-18`!

**Nouvelles Features 2025-06-18**:

#### 1. Elicitation (Human-in-the-Loop)
```python
# Example: Ask user for clarification during indexing
async def index_project(...):
    if ambiguous_file_detected:
        response = await elicit_from_user(
            prompt="This file could be Python or Ruby. Which is it?",
            options=["Python", "Ruby", "Skip"]
        )
```

**Usage MnemoLite**:
- Demander langage si ambigu
- Confirmer suppression mémoires
- Valider opérations sensibles (clear cache, reindex)

#### 2. Structured Tool Output
```python
from pydantic import BaseModel

class SearchResult(BaseModel):
    chunks: List[CodeChunk]
    total_found: int
    query_time_ms: float
    cache_hit: bool

@mcp.tool()
def search_code(...) -> SearchResult:  # Structured output!
    """Search returns structured Pydantic model."""
```

**Impact**: Tous nos tools/resources doivent retourner Pydantic models!

#### 3. Enhanced OAuth Authentication
```python
# For HTTP transport (production)
mcp = FastMCP(
    authentication={
        "oauth2": {
            "authorization_endpoint": "https://auth.mnemolite.io/authorize",
            "token_endpoint": "https://auth.mnemolite.io/token",
            "scopes": ["read:code", "write:memory", "admin:cache"]
        }
    }
)
```

**Usage**: Phase 3 (Story 23.8 - HTTP Transport)

#### 4. Resource Links in Tool Results
```python
@mcp.tool()
def index_project(...) -> IndexResult:
    return IndexResult(
        indexed_files=150,
        resource_links=[
            ResourceLink(uri="project://status", name="View Status"),
            ResourceLink(uri="cache://stats", name="Cache Stats")
        ]
    )
```

**Usage**: Navigation post-indexation, découverte resources

---

### 🚨 ERREUR #3: Serena N'utilise PAS Resources ni Prompts MCP

**Découverte**:
```python
# serena-main/src/serena/mcp.py ligne 233-240
def _set_mcp_tools(self, mcp: FastMCP, ...):
    mcp._tool_manager._tools = {}  # Only Tools!
    for tool in self._iter_tools():
        mcp_tool = self.make_mcp_tool(tool, ...)
        mcp._tool_manager._tools[tool.get_name()] = mcp_tool
```

Serena expose **SEULEMENT Tools**, pas Resources ni Prompts MCP!

**Implication**: MnemoLite peut être **plus conforme à MCP** que Serena en utilisant les 3 types.

**Avantage Compétitif**:
- ✅ Resources = meilleure performance (caching, pas d'exécution fonction)
- ✅ Prompts = meilleure UX (templates pré-définis dans Claude Desktop)
- ✅ Architecture plus propre (séparation read/write)

---

### 🚨 ERREUR #4: Migration SQL Memories Incomplète

**Problème**: Ma table `memories` manquait des champs importants.

**Table CORRIGÉE**:
```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Core fields
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(50) NOT NULL DEFAULT 'note',  -- NOUVEAU: note, decision, architecture, todo

    -- Metadata
    tags TEXT[] DEFAULT '{}',
    author VARCHAR(100),  -- NOUVEAU: qui a créé (user, llm, system)
    project_id UUID,  -- NOUVEAU: support multi-project

    -- Semantic search
    embedding VECTOR(768),  -- Optional pour semantic search
    embedding_model VARCHAR(100),  -- NOUVEAU: track model used

    -- Relations & links
    related_chunks UUID[],  -- NOUVEAU: liens vers code_chunks
    resource_links JSONB DEFAULT '[]'::jsonb,  -- NOUVEAU: MCP resource links

    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Soft delete
    deleted_at TIMESTAMPTZ,  -- NOUVEAU: soft delete

    -- Constraints
    CONSTRAINT unique_name_per_project UNIQUE (name, project_id),
    CONSTRAINT valid_memory_type CHECK (memory_type IN ('note', 'decision', 'architecture', 'todo', 'learning'))
);

-- Indexes
CREATE INDEX idx_memories_name ON memories(name);
CREATE INDEX idx_memories_project ON memories(project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_memories_type ON memories(memory_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_memories_tags ON memories USING GIN(tags);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat(embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX idx_memories_created ON memories(created_at DESC);
CREATE INDEX idx_memories_related ON memories USING GIN(related_chunks);
```

**Champs Ajoutés**:
- `memory_type`: Catégorisation (note, decision, architecture, todo, learning)
- `author`: Tracking qui a créé
- `project_id`: Multi-project support
- `embedding_model`: Traçabilité modèle
- `related_chunks`: Liens bidirectionnels code↔memory
- `resource_links`: MCP 2025-06-18 feature
- `deleted_at`: Soft delete (audit trail)

---

### 🚨 ERREUR #5: Pas de Mention du MCP Inspector

**Manque**: Tool de debug essentiel!

**MCP Inspector** (`http://127.0.0.1:6274`):
- Interface web pour tester tools/resources/prompts
- Validation schemas
- Test de connexions
- Debug messages MCP

**Integration**:
```bash
# Development mode (auto-lance Inspector)
uv run mcp dev api/mcp/server.py

# Standalone
mcp-inspector
```

**Story 23.1 doit inclure**: Setup MCP Inspector dans workflow dev

---

## 📊 CORRECTIONS PAR STORY

### Story 23.1: MCP Server Bootstrap (3 pts) - CORRECTIONS

**Avant**:
- ✓ FastMCP server bootstrap
- ✓ CLI entrypoint
- ✓ 1 test tool "ping"

**APRÈS (Corrigé)**:
- ✓ FastMCP server bootstrap (**spec 2025-06-18**)
- ✓ CLI entrypoint avec **MCP Inspector integration**
- ✓ 3 test items:
  - 1 Tool: `ping`
  - 1 Resource: `health://status`
  - 1 Prompt: `test_prompt`
- **NOUVEAU**: Structured output (Pydantic models)
- **NOUVEAU**: Lifespan management (startup/shutdown)

### Story 23.2: Core Search Tools (3 pts) - CORRECTIONS

**Avant**: 3 tools (search_code, find_similar_code, search_by_qualified_name)

**APRÈS**:
- ❌ ~~Tool~~ → ✅ **3 Resources** (read-only operations!)
  - `code://search/{query}`
  - `code://similar/{snippet_hash}`
  - `code://qualified/{name}`
- ✅ Structured output (CodeChunkResult Pydantic model)
- ✅ Resource links dans résultats
- **NOUVEAU**: Cache-Control headers pour resources
- **NOUVEAU**: Pagination support (offset/limit)

### Story 23.3: Project Memory System (2 pts) - CORRECTIONS

**Avant**: 3 tools (write, search, list)

**APRÈS**:
- ✅ **1 Tool**: `write_project_memory` (write operation)
- ✅ **2 Resources**:
  - `memories://search/{query}`
  - `memories://list`
- ✅ Migration SQL **complète** (voir ERREUR #4)
- **NOUVEAU**: Elicitation pour confirmation suppression
- **NOUVEAU**: Memory types (note, decision, architecture, todo)
- **NOUVEAU**: Bi-directional links (memory ↔ code_chunks)

### Story 23.4: Code Graph Tools (3 pts) - CORRECTIONS

**Avant**: 3 tools (get_code_graph, find_callers, find_callees)

**APRÈS**:
- ❌ ~~3 Tools~~ → ✅ **3 Resources** (read-only!)
  - `graph://nodes/{chunk_id}`
  - `graph://callers/{qualified_name}`
  - `graph://callees/{qualified_name}`
- ✅ Structured output (CodeGraph Pydantic model)
- **NOUVEAU**: Graph pagination (pour gros graphes)
- **NOUVEAU**: Filter par relation types

### Story 23.5: Project Indexing (2 pts) - CORRECTIONS

**Avant**: 3 tools

**APRÈS**:
- ✅ **2 Tools** (side effects):
  - `index_project` (database writes)
  - `reindex_file` (database writes)
- ✅ **1 Resource** (read-only):
  - `project://status`
- **NOUVEAU**: Elicitation pour confirmer force_reindex
- **NOUVEAU**: Resource links post-indexation
- **NOUVEAU**: Progress reporting (streaming)

### Story 23.6: Analytics & Observability (2 pts) - CORRECTIONS

**Avant**: 3 tools

**APRÈS**:
- ✅ **1 Tool** (side effect):
  - `clear_cache` (admin operation)
- ✅ **2 Resources** (read-only):
  - `analytics://search`
  - `cache://stats`
- **NOUVEAU**: EPIC-22 integration (metrics_collector)
- **NOUVEAU**: Real-time stats via SSE (optional)

### Story 23.7: Configuration & Utilities (1 pt) - CORRECTIONS

**Avant**: 3 tools

**APRÈS**:
- ✅ **1 Tool** (state change):
  - `switch_project` (change global state)
- ✅ **2 Resources** (read-only):
  - `projects://list`
  - `languages://supported`
- **NOUVEAU**: Multi-project config management

### Story 23.8: HTTP Transport Support (2 pts) - NOUVEAU CONTENU

**Ajouts**:
- ✅ OAuth 2.0 authentication (spec 2025-06-18)
- ✅ PKCE support (required by spec)
- ✅ Rate limiting (production requirement)
- ✅ CORS configuration
- ✅ Health checks endpoint
- ✅ API key fallback (simple auth)

### Story 23.9: Documentation & Examples (1 pt) - AJOUTS

**Nouveaux docs**:
- ✅ Migration guide 2025-03-26 → 2025-06-18
- ✅ Resources vs Tools decision tree
- ✅ Elicitation patterns & examples
- ✅ Structured output best practices
- ✅ MCP Inspector workflow
- ✅ Multi-project configuration guide

---

## 🆕 NOUVELLES STORIES PROPOSÉES

### Story 23.10: Prompts Library (2 pts) - NOUVEAU

**Objectif**: Ajouter prompts MCP pour templates utilisateur

**Prompts à Créer**:
```python
@mcp.prompt()
def analyze_codebase() -> str:
    """Analyze codebase architecture and patterns."""

@mcp.prompt()
def find_bugs(severity: str = "high") -> str:
    """Find potential bugs and code smells."""

@mcp.prompt()
def refactor_suggestions(focus: str = "all") -> str:
    """Suggest refactoring opportunities."""

@mcp.prompt()
def generate_tests(chunk_id: str) -> str:
    """Generate test suite for code chunk."""

@mcp.prompt()
def explain_code(chunk_id: str, level: str = "detailed") -> str:
    """Explain code chunk functionality."""

@mcp.prompt()
def security_audit(scope: str = "all") -> str:
    """Perform security audit."""
```

**Acceptance Criteria**:
- ✅ 6+ prompts exposés via MCP
- ✅ Visible dans Claude Desktop UI
- ✅ Paramètres utilisateur customisables
- ✅ Integration avec search/graph resources

### Story 23.11: Elicitation Flows (1 pt) - NOUVEAU

**Objectif**: Implémenter human-in-the-loop pour opérations critiques

**Use Cases**:
1. Confirmation `clear_cache` (demander quel layer)
2. Confirmation `delete_project_memory` (vraiment supprimer?)
3. Ambiguïté langage dans `index_project`
4. Choix mode search (semantic vs lexical vs hybrid)
5. Validation `reindex_file` si gros fichier

**Implementation**:
```python
from mcp.types import ElicitationRequest

async def clear_cache(ctx: Context, layer: str = None):
    if layer is None:
        # Elicit from user
        response = await ctx.elicit(
            prompt="Which cache layer to clear?",
            schema={"type": "string", "enum": ["L1", "L2", "L3", "all"]}
        )
        layer = response.value
    # Proceed with clearing
```

---

## 📈 ESTIMATION RÉVISÉE

### Avant (19 pts):
- Phase 1: 8 pts
- Phase 2: 7 pts
- Phase 3: 4 pts

### APRÈS Corrections (23 pts):
- **Phase 1: Foundation** (8 pts) - inchangé mais contenu enrichi
  - Story 23.1: 3 pts (+ MCP Inspector + structured output)
  - Story 23.2: 3 pts (→ Resources + cache-control)
  - Story 23.3: 2 pts (+ elicitation + bi-directional links)

- **Phase 2: Advanced** (9 pts) - +2 pts
  - Story 23.4: 3 pts (→ Resources + pagination)
  - Story 23.5: 2 pts (+ elicitation + progress)
  - Story 23.6: 2 pts (→ Resources + SSE)
  - Story 23.10: **2 pts (NOUVEAU - Prompts Library)**

- **Phase 3: Polish & Production** (6 pts) - +2 pts
  - Story 23.7: 1 pt (→ Resources)
  - Story 23.8: 2 pts (+ OAuth + PKCE)
  - Story 23.9: 1 pt (+ migration guide)
  - Story 23.11: **1 pt (NOUVEAU - Elicitation Flows)**
  - Story 23.12: **1 pt (NOUVEAU - MCP Inspector Integration)** [split from 23.1]

**Total: 23 story points** (+4 pts vs original)

---

## 🎯 DÉCISIONS ARCHITECTURALES MISES À JOUR

### 1. Spec MCP: 2025-06-18 (pas 2025-03-26)
**Raison**: Version actuelle avec elicitation, structured output, OAuth

### 2. 3 Types d'Interactions (pas juste Tools)
**Breakdown**:
- **8 Tools** (write ops): index, reindex, write_memory, clear_cache, switch_project, delete_memory, acknowledge_alert, create_project
- **15 Resources** (read ops): search, get_chunk, get_status, list_memories, search_memories, get_graph, find_callers, find_callees, get_cache_stats, get_analytics, list_projects, get_languages, get_health, get_metrics, get_alerts
- **6 Prompts** (templates): analyze, find_bugs, refactor, generate_tests, explain, security_audit

**Total: 29 interactions** (vs 25 tools initialement)

### 3. Structured Output Obligatoire
**Implementation**: Tous les tools/resources retournent Pydantic models
**Bénéfice**: Type safety, validation automatique, meilleure intégration LLM

### 4. Migration SQL Enrichie
**Table `memories` complète**: 15 colonnes (vs 8 initialement)
**Support**: Multi-project, soft delete, bi-directional links, resource links MCP

### 5. MCP Inspector dans Dev Workflow
**Usage**: Story 23.1 inclut setup Inspector
**Command**: `uv run mcp dev api/mcp/server.py`

### 6. Elicitation pour Ops Critiques
**Pattern**: clear_cache, delete_memory, force_reindex
**Implementation**: Story 23.11 dédiée

### 7. Resource Links Systématiques
**Usage**: index_project → resource links vers status/cache
**Spec**: MCP 2025-06-18 ResourceLinkBlock

---

## 📚 NOUVELLES RÉFÉRENCES

### Specs Officielles
- ✅ MCP Spec 2025-06-18: https://modelcontextprotocol.io/specification/2025-03-26
- ✅ Python SDK Official: https://github.com/modelcontextprotocol/python-sdk
- ✅ FastMCP Tutorial: https://www.firecrawl.dev/blog/fastmcp-tutorial-building-mcp-servers-python

### Nouveautés 2025-06-18
- ✅ Elicitation (human-in-the-loop)
- ✅ Structured tool output (Pydantic)
- ✅ OAuth 2.0 + PKCE authentication
- ✅ Resource links in tool results
- ✅ Enhanced `_meta` field extensibility

### Exemples & Patterns
- ✅ Document Reader MCP (FastMCP tutorial)
- ✅ Serena MCP (Tools-only, no Resources/Prompts)
- ✅ MCP Inspector workflow
- ✅ Multi-project configuration patterns

---

## ✅ CHECKLIST VALIDATION

### Corrections Appliquées
- [x] Séparer Tools / Resources / Prompts (29 interactions)
- [x] Mettre à jour vers spec 2025-06-18
- [x] Ajouter structured output (Pydantic) partout
- [x] Enrichir table `memories` (15 colonnes)
- [x] Ajouter elicitation patterns
- [x] Intégrer MCP Inspector dans workflow
- [x] Ajouter resource links dans résultats
- [x] Créer Story 23.10 (Prompts Library)
- [x] Créer Story 23.11 (Elicitation Flows)
- [x] Créer Story 23.12 (MCP Inspector Integration)
- [x] Mettre à jour estimation (23 pts)

### Nouvelles Recherches Nécessaires
- [ ] OAuth 2.0 implementation patterns pour MCP
- [ ] PKCE flow details
- [ ] Elicitation schema best practices
- [ ] Resource pagination standards
- [ ] SSE streaming pour real-time stats

---

## 🚀 PROCHAINES ÉTAPES RECOMMANDÉES

1. **Créer EPIC-23_README.md officiel** avec corrections
2. **Décomposer stories en tasks détaillées**
3. **Prioriser Phase 1** (Stories 23.1-23.3)
4. **Setup MCP Inspector** dès Story 23.1
5. **Valider architecture** avec Giak
6. **Commencer implémentation** Story 23.1

---

**Status**: ✅ VALIDATION COMPLÈTE - Architecture corrigée et enrichie
**Changements**: +4 story points, +11 Resources, +6 Prompts, spec 2025-06-18
**Prêt pour**: Création EPIC-23_README.md officiel et début implémentation

---

**Document créé par**: Claude Code (double-check via web research)
**Validation**: Specs MCP officielles + SDK Python + FastMCP tutorials + Serena codebase analysis
