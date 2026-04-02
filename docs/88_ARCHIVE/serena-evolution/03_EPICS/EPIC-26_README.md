# EPIC-26: TypeScript/JavaScript Code Graph Support

**Status**: 🔴 PENDING (Not Started)
**Priority**: P1 (Critical - Blocks Graph Visualization)
**Story Points**: 10 pts
**Duration**: 3-4 semaines (solo dev)
**Dependencies**: EPIC-06 (Code Graph), EPIC-15 (tree-sitter), EPIC-25 (Dashboard UI)
**Blocked By**: Graph visualization non-fonctionnelle (0 edges pour TypeScript/JS)
**Created**: 2025-11-01
**Progress**: 0/10 pts (0%)

---

## 📋 Vue d'Ensemble

### Objectif

Étendre le système de métadonnées de code pour **supporter TypeScript et JavaScript**, permettant la construction complète de graphes de dépendances avec nodes ET edges.

**Impact Business**: Débloquer la visualisation de graphes pour **TOUS les projets TypeScript/JavaScript** (CVGenerator, frontend MnemoLite, etc.).

### Problème Actuel (CRITIQUE)

**Symptôme**: Graph visualization affiche 294 nodes mais **0 edges** pour le projet CVGenerator (TypeScript).

```json
{
  "repository": "CVGenerator",
  "total_nodes": 294,
  "total_edges": 0,          // ❌ PROBLÈME
  "nodes_by_type": {
    "class": 48,
    "method": 246
  },
  "edges_by_type": {}         // ❌ VIDE
}
```

**Conséquence**: Le graph est **complètement inutile** - les nodes existent mais aucune relation n'est détectée.

**Cas d'usage bloqués**:
- ❌ Impossible de visualiser les dépendances entre modules TypeScript
- ❌ Impossible de voir les appels de fonctions inter-classes
- ❌ Impossible de naviguer le code TypeScript/JavaScript via le graph
- ❌ Recherche sémantique moins précise (pas de context de dépendances)

---

### Important Clarification: Embeddings vs Metadata

**CRITIQUE**: EPIC-26 concerne l'extraction de métadonnées (imports/calls), PAS les embeddings.

**Embeddings déjà fonctionnels** ✅:
- MnemoLite utilise `CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code`
- Ce modèle est **multi-langage** (Python, TypeScript, JavaScript, Go, Rust, Java, C++)
- Les embeddings TypeScript/JavaScript fonctionnent DÉJÀ correctement
- La recherche sémantique fonctionne pour les projets TypeScript/JavaScript

**Deux pipelines indépendants**:

```
┌─────────────────────────────────────────────────────────┐
│ Pipeline 1: EMBEDDINGS (✅ FONCTIONNE DÉJÀ)            │
│                                                         │
│ Code chunks → jina-embeddings-v2-base-code → vectors   │
│            → Semantic search (RAG)                      │
│                                                         │
│ Support: Python, TypeScript, JavaScript, Go, Rust, ... │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Pipeline 2: METADATA EXTRACTION (❌ PROBLÈME EPIC-26)   │
│                                                         │
│ Code → tree-sitter parsing → imports/calls extraction  │
│     → Graph edges (dependencies)                        │
│                                                         │
│ Support: Python ✅ | TypeScript ❌ | JavaScript ❌      │
└─────────────────────────────────────────────────────────┘
```

**Conclusion**: EPIC-26 ne touche PAS au pipeline d'embeddings. Le problème est UNIQUEMENT l'extraction de métadonnées pour la construction du graph de dépendances.

---

### Root Cause Analysis

#### Investigation: Pourquoi 0 Edges?

**Diagnostic étape par étape**:

1. **Indexation réussie**: 294 nodes créés → Chunking fonctionne ✅
2. **Métadonnées vides**: `SELECT metadata FROM code_chunks WHERE repository = 'CVGenerator'` → `{}` (empty) ❌
3. **Code source identifié**: `api/services/metadata_extractor_service.py:72-75`

```python
# api/services/metadata_extractor_service.py:72-75
if language != "python":
    # ❌ Fallback: basic metadata only for non-Python
    self.logger.warning(f"Language '{language}' not supported, returning basic metadata")
    return self._extract_basic_metadata(node)
```

4. **Fallback retourne vide**: Lines 328-346

```python
def _extract_basic_metadata(self, node: ast.AST) -> dict[str, Any]:
    """Fallback for non-Python languages."""
    return {
        "signature": None,
        "parameters": [],
        "returns": None,
        "decorators": [],
        "docstring": None,
        "complexity": {"cyclomatic": None, "lines_of_code": 0},
        "imports": [],  # ❌ VIDE pour TypeScript
        "calls": []     # ❌ VIDE pour TypeScript
    }
```

5. **GraphConstructionService ne peut pas créer d'edges**: Sans `imports` et `calls`, impossible de construire les relations.

**Conclusion**: MetadataExtractorService utilise `ast` (Python AST module) qui ne supporte QUE Python. Pour TypeScript/JavaScript, il retourne des métadonnées vides.

---

### Découverte: Infrastructure Existe Déjà!

**Bonne nouvelle**: MnemoLite utilise DÉJÀ tree-sitter avec support TypeScript/JavaScript!

```python
# api/services/code_chunking_service.py:162-250
class TypeScriptParser(LanguageParser):
    """
    TypeScript/TSX AST parser using tree-sitter.

    Handles:
    - Function declarations (function)
    - Arrow functions (const x = () => {})
    - Class declarations
    - Interface declarations (TypeScript-specific)
    - Method definitions
    """
```

**Capacités existantes**:
- ✅ Parse TypeScript/TSX avec tree-sitter
- ✅ Extrait functions, classes, methods, interfaces
- ✅ Supporte arrow functions, async functions
- ✅ Infrastructure testée (EPIC-15)

**Ce qui manque**:
- ❌ Extraction des **imports** (import/export statements)
- ❌ Extraction des **calls** (call_expression, member_expression)
- ❌ Intégration avec MetadataExtractorService

---

### Solution Proposée

**Architecture**: Étendre MetadataExtractorService pour supporter tree-sitter queries.

```
┌────────────────────────────────────────────────────────┐
│        MetadataExtractorService (REFACTOR)            │
│  ┌──────────────────┐  ┌───────────────────────────┐  │
│  │ Python Extractor │  │ TypeScript/JS Extractor   │  │
│  │ (ast module)     │  │ (tree-sitter queries)     │  │
│  │ [EXISTING ✅]    │  │ [NEW ⭐]                  │  │
│  └──────────────────┘  └───────────────────────────┘  │
└────────────────────────────────────────────────────────┘
           │                        │
           ▼                        ▼
    ┌──────────────────────────────────────────────┐
    │    GraphConstructionService                  │
    │    - Nodes créés (✅ fonctionne)             │
    │    - Edges créés (⭐ va fonctionner)         │
    └──────────────────────────────────────────────┘
```

**Principe**: Réutiliser l'infrastructure tree-sitter existante sans tout reconstruire.

**Pattern**: Protocol-based dependency injection (DIP pattern MnemoLite)

```python
# Nouveau fichier: api/services/metadata_extractors/typescript_extractor.py

class TypeScriptMetadataExtractor:
    """
    Extract metadata from TypeScript/JavaScript using tree-sitter queries.

    Queries:
    - Imports: import_statement, export_statement
    - Calls: call_expression, member_expression, new_expression
    """

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """
        Extract import statements.

        Example TypeScript:
            import { MyClass } from './models'
            import * as utils from 'lodash'
            export { MyService } from './services'

        Returns:
            ['./models.MyClass', 'lodash', './services.MyService']
        """

    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function calls and method calls.

        Example TypeScript:
            const result = calculateTotal(items)
            this.service.fetchData()
            new DatabaseConnection()

        Returns:
            ['calculateTotal', 'service.fetchData', 'DatabaseConnection']
        """
```

---

## 🎯 Scope & Features

### In Scope

**Languages**:
- ✅ TypeScript (.ts, .tsx)
- ✅ JavaScript (.js, .jsx)

**Metadata Extraction**:
1. **Imports** (ESM):
   - `import { X } from 'module'` - Named imports
   - `import * as X from 'module'` - Namespace imports
   - `import X from 'module'` - Default imports
   - `export { X }` - Re-exports
   - `require('module')` - CommonJS (JavaScript only)

2. **Function Calls**:
   - `functionName()` - Direct function calls
   - `object.method()` - Method calls
   - `new ClassName()` - Constructor calls
   - `super.method()` - Super calls

3. **Member Expressions**:
   - `a.b.c()` - Chained method calls
   - `this.methodName()` - Instance method calls

**Integration Points**:
- ✅ MetadataExtractorService (routing par language)
- ✅ GraphConstructionService (création edges)
- ✅ Code chunking service (déjà intégré)

### Out of Scope (Post-EPIC-26)

**Advanced Features** (Future EPICs):
- ❌ Type inference (TypeScript types resolution)
- ❌ JSDoc parsing
- ❌ Complexity metrics (cyclomatic, cognitive)
- ❌ Docstring extraction
- ❌ Parameter/return type extraction
- ❌ Dynamic imports (`import()`)
- ❌ Webpack/Rollup alias resolution

**Other Languages**:
- ❌ Go, Rust, Java (Future EPICs)

**Reason**: YAGNI - Focus sur débloquer le graph pour TypeScript/JavaScript d'abord. Le reste peut attendre.

---

## 📊 Story Breakdown (5 stories, 10 pts)

### Phase 1: Core TypeScript Support (5 pts, 2 semaines)

#### Story 26.1: TypeScript Import Extraction (2 pts, 6h)

**Description**: Extraire les imports TypeScript avec tree-sitter queries.

**Sub-tasks**:
- 26.1.1: Create `TypeScriptMetadataExtractor` class (1.5h)
- 26.1.2: Implement `extract_imports()` with tree-sitter queries (2h)
- 26.1.3: Handle ESM imports (named, default, namespace) (1h)
- 26.1.4: Handle re-exports (1h)
- 26.1.5: Unit tests (10 test cases) (0.5h)

**Acceptance Criteria**:
- [x] `import { X } from 'module'` → returns `['module.X']`
- [x] `import * as X from 'module'` → returns `['module']`
- [x] `import X from 'module'` → returns `['module']`
- [x] `export { X } from 'module'` → returns `['module.X']`
- [x] Tests: 10/10 passing

**Tree-sitter Query**:
```python
query = tree_sitter.Query(
    ts_language,
    """
    (import_statement
      source: (string) @import_source
    ) @import

    (import_clause
      (named_imports
        (import_specifier
          name: (identifier) @import_name
        )
      )
    ) @named_import

    (export_statement
      source: (string) @export_source
    ) @export
    """
)
```

**Files Modified**:
- `api/services/metadata_extractors/typescript_extractor.py` (NEW, ~200 lines)
- `tests/services/test_typescript_extractor.py` (NEW, ~150 lines)

---

#### Story 26.2: TypeScript Call Extraction (2 pts, 6h)

**Description**: Extraire les appels de fonctions/méthodes TypeScript.

**Sub-tasks**:
- 26.2.1: Implement `extract_calls()` with tree-sitter queries (2h)
- 26.2.2: Handle direct function calls (0.5h)
- 26.2.3: Handle method calls & chained calls (1h)
- 26.2.4: Handle constructor calls (`new X()`) (0.5h)
- 26.2.5: Handle `this` and `super` calls (1h)
- 26.2.6: Unit tests (15 test cases) (1h)

**Acceptance Criteria**:
- [x] `functionName()` → returns `['functionName']`
- [x] `object.method()` → returns `['object.method']`
- [x] `this.methodName()` → returns `['methodName']`
- [x] `new ClassName()` → returns `['ClassName']`
- [x] `a.b.c()` → returns `['a.b.c']`
- [x] Tests: 15/15 passing

**Tree-sitter Query**:
```python
query = tree_sitter.Query(
    ts_language,
    """
    (call_expression
      function: [
        (identifier) @function_name
        (member_expression
          object: (identifier) @object
          property: (property_identifier) @method
        )
      ]
    ) @call

    (new_expression
      constructor: (identifier) @constructor
    ) @new_call
    """
)
```

**Files Modified**:
- `api/services/metadata_extractors/typescript_extractor.py` (+150 lines)
- `tests/services/test_typescript_extractor.py` (+200 lines)

---

#### Story 26.3: MetadataExtractorService Integration (1 pt, 4h)

**Description**: Intégrer TypeScriptMetadataExtractor dans MetadataExtractorService.

**Sub-tasks**:
- 26.3.1: Refactor MetadataExtractorService (routing par language) (1.5h)
- 26.3.2: Wire up TypeScriptMetadataExtractor (0.5h)
- 26.3.3: Update GraphConstructionService (handle TypeScript metadata) (1h)
- 26.3.4: Integration tests (1h)

**Acceptance Criteria**:
- [x] `MetadataExtractorService.extract_metadata(language='typescript')` → calls TypeScriptMetadataExtractor
- [x] Returns metadata with `imports: [...]` and `calls: [...]`
- [x] GraphConstructionService creates edges from TypeScript metadata
- [x] Tests: Integration tests passing (5 tests)

**Architecture Change**:
```python
# BEFORE (api/services/metadata_extractor_service.py)
class MetadataExtractorService:
    async def extract_metadata(self, source_code: str, node: ast.AST, tree: ast.AST, language: str = "python"):
        if language != "python":
            return self._extract_basic_metadata(node)  # ❌ Returns empty

# AFTER
class MetadataExtractorService:
    def __init__(self):
        self.extractors = {
            "python": PythonMetadataExtractor(),
            "typescript": TypeScriptMetadataExtractor(),
            "javascript": JavaScriptMetadataExtractor(),
        }

    async def extract_metadata(self, source_code: str, node: Node, tree: Tree, language: str = "python"):
        extractor = self.extractors.get(language)
        if not extractor:
            return self._extract_basic_metadata(node)
        return await extractor.extract(source_code, node, tree)
```

**Files Modified**:
- `api/services/metadata_extractor_service.py` (~100 lines changes)
- `api/services/graph_construction_service.py` (~20 lines changes)
- `tests/integration/test_typescript_graph.py` (NEW, ~150 lines)

---

### Phase 2: JavaScript Support & Validation (5 pts, 1-2 semaines)

#### Story 26.4: JavaScript Support (2 pts, 6h)

**Description**: Étendre le support à JavaScript (CommonJS + ESM).

**Sub-tasks**:
- 26.4.1: Create `JavaScriptMetadataExtractor` (reuse TypeScript code) (1.5h)
- 26.4.2: Handle CommonJS (`require()`, `module.exports`) (2h)
- 26.4.3: Handle ESM (same as TypeScript) (1h)
- 26.4.4: Unit tests (15 test cases) (1.5h)

**Acceptance Criteria**:
- [x] `require('module')` → returns `['module']`
- [x] `module.exports = X` → handled
- [x] ESM imports work (same as TypeScript)
- [x] Tests: 15/15 passing

**Tree-sitter Query (CommonJS)**:
```python
query = tree_sitter.Query(
    js_language,
    """
    (call_expression
      function: (identifier) @require_fn (#eq? @require_fn "require")
      arguments: (arguments (string) @module_name)
    ) @require_call

    (assignment_expression
      left: (member_expression
        object: (identifier) @module (#eq? @module "module")
        property: (property_identifier) @exports (#eq? @exports "exports")
      )
    ) @exports
    """
)
```

**Files Created**:
- `api/services/metadata_extractors/javascript_extractor.py` (~250 lines)
- `tests/services/test_javascript_extractor.py` (~200 lines)

---

#### Story 26.5: Testing & Validation (2 pts, 8h)

**Description**: Tester avec de vrais projets et valider le graph.

**Sub-tasks**:
- 26.5.1: Re-index CVGenerator project (294 nodes) (0.5h)
- 26.5.2: Validate edges created (expect >100 edges) (1h)
- 26.5.3: Test graph visualization (Graph.vue) (1h)
- 26.5.4: Test with MnemoLite frontend (Vue.js 3 codebase) (1.5h)
- 26.5.5: Performance testing (1000+ files) (2h)
- 26.5.6: Documentation (EPIC completion report) (2h)

**Acceptance Criteria**:
- [x] CVGenerator: 294 nodes, **>100 edges** (currently 0)
- [x] Graph visualization shows connected nodes (no isolated nodes)
- [x] MnemoLite frontend: nodes + edges detected
- [x] Performance: <2s for 1000 files indexing
- [x] Documentation: Completion report + ULTRATHINK

**Success Metrics**:
```json
{
  "repository": "CVGenerator",
  "total_nodes": 294,
  "total_edges": 150,         // ✅ > 100 (GOAL)
  "nodes_by_type": {
    "class": 48,
    "method": 246
  },
  "edges_by_type": {
    "calls": 120,              // ✅ Function calls
    "imports": 30              // ✅ Import relationships
  }
}
```

**Files Modified**:
- `index_cv_project.py` (re-run with new extractor)
- `frontend/src/pages/Graph.vue` (visual validation)
- `docs/agile/serena-evolution/03_EPICS/EPIC-26_COMPLETION_REPORT.md` (NEW)

---

#### Story 26.6: Documentation & Best Practices (1 pt, 4h)

**Description**: Documenter le système d'extraction de métadonnées.

**Sub-tasks**:
- 26.6.1: Update README with TypeScript/JavaScript support (1h)
- 26.6.2: Document tree-sitter queries (reference guide) (1.5h)
- 26.6.3: Create developer guide for adding new languages (1h)
- 26.6.4: Update CLAUDE.md gotchas if needed (0.5h)

**Deliverables**:
- `docs/CODE_GRAPH_METADATA_EXTRACTION.md` (NEW, ~800 lines)
- `docs/ADDING_LANGUAGE_SUPPORT.md` (NEW, ~400 lines)
- Updated `README.md`

---

## 🏗️ Architecture Technique

### File Structure (New Files)

```
api/services/metadata_extractors/      # ⭐ NEW Package
├── __init__.py
├── base.py                             # MetadataExtractor Protocol (DIP)
├── python_extractor.py                 # Extract from existing code
├── typescript_extractor.py             # ⭐ NEW (Story 26.1, 26.2)
└── javascript_extractor.py             # ⭐ NEW (Story 26.4)

tests/services/
├── test_typescript_extractor.py        # ⭐ NEW (25 tests)
└── test_javascript_extractor.py        # ⭐ NEW (15 tests)

tests/integration/
└── test_typescript_graph.py            # ⭐ NEW (5 tests)

docs/
├── CODE_GRAPH_METADATA_EXTRACTION.md   # ⭐ NEW
└── ADDING_LANGUAGE_SUPPORT.md          # ⭐ NEW
```

### Dependency Injection Pattern

**Protocol-Based Design** (DIP principle):

```python
# api/services/metadata_extractors/base.py
from typing import Protocol, Any
from tree_sitter import Node, Tree

class MetadataExtractor(Protocol):
    """
    Protocol for language-specific metadata extractors.

    DIP Pattern: MetadataExtractorService depends on abstraction (Protocol),
    not concrete implementations (PythonExtractor, TypeScriptExtractor).
    """

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """Extract import/require statements."""
        ...

    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """Extract function/method calls."""
        ...

    async def extract_metadata(self, source_code: str, node: Node, tree: Tree) -> dict[str, Any]:
        """Extract all metadata (imports + calls + other)."""
        ...
```

**Benefits**:
- ✅ Easy to add new languages (implement Protocol)
- ✅ Testable (mock extractors)
- ✅ No tight coupling (MetadataExtractorService doesn't know about concrete types)
- ✅ Consistent with MnemoLite architecture patterns

---

### Tree-sitter Query Design

**Query Pattern 1: Import Statements (TypeScript/JavaScript)**

```python
# Matches:
#   import { MyClass, MyFunction } from './models'
#   import * as utils from 'lodash'
#   export { MyService } from './services'

query = tree_sitter.Query(
    language,
    """
    ; Named imports
    (import_statement
      (import_clause
        (named_imports
          (import_specifier
            name: (identifier) @import_name
          )
        )
      )
      source: (string) @import_source
    ) @import

    ; Namespace imports
    (import_statement
      (import_clause
        (namespace_import
          (identifier) @namespace_name
        )
      )
      source: (string) @import_source
    ) @namespace_import

    ; Default imports
    (import_statement
      (import_clause
        (identifier) @default_name
      )
      source: (string) @import_source
    ) @default_import

    ; Re-exports
    (export_statement
      (export_clause
        (export_specifier
          name: (identifier) @export_name
        )
      )
      source: (string) @export_source
    ) @export
    """
)

# Usage
cursor = tree_sitter.QueryCursor(query)
matches = cursor.matches(tree.root_node)

imports = []
for pattern_index, captures_dict in matches:
    source = captures_dict.get('import_source', [])
    names = captures_dict.get('import_name', [])
    for name_node in names:
        name = source_code[name_node.start_byte:name_node.end_byte]
        imports.append(name)
```

**Query Pattern 2: Function Calls (TypeScript/JavaScript)**

```python
# Matches:
#   calculateTotal(items)
#   this.service.fetchData()
#   new DatabaseConnection()

query = tree_sitter.Query(
    language,
    """
    ; Direct function calls
    (call_expression
      function: (identifier) @function_name
    ) @call

    ; Method calls (including chained)
    (call_expression
      function: (member_expression
        object: (_) @object
        property: (property_identifier) @method
      )
    ) @method_call

    ; Constructor calls
    (new_expression
      constructor: (identifier) @constructor
    ) @new_call
    """
)
```

---

### Integration with GraphConstructionService

**Current Flow** (Python only):

```
CodeIndexingService
    ↓ (chunks code)
CodeChunkingService
    ↓ (creates chunks with metadata)
MetadataExtractorService ← 🔴 ONLY PYTHON
    ↓ (metadata = {"imports": [...], "calls": [...]})
GraphConstructionService
    ↓ (creates nodes + edges)
PostgreSQL (nodes, edges tables)
```

**New Flow** (Python + TypeScript + JavaScript):

```
CodeIndexingService
    ↓ (chunks code, detects language)
CodeChunkingService
    ↓ (creates chunks, routes by language)
MetadataExtractorService ← 🟢 MULTI-LANGUAGE
    ├─ PythonExtractor (ast module)
    ├─ TypeScriptExtractor (tree-sitter) ⭐ NEW
    └─ JavaScriptExtractor (tree-sitter) ⭐ NEW
    ↓ (metadata = {"imports": [...], "calls": [...]})
GraphConstructionService
    ↓ (creates nodes + edges FOR ALL LANGUAGES)
PostgreSQL (nodes, edges tables)
```

**Code Changes** (minimal):

```python
# api/services/graph_construction_service.py

# BEFORE
async def _create_edges_from_metadata(self, chunk: CodeChunk) -> list[Edge]:
    metadata = chunk.metadata  # Assumes Python metadata
    # ... create edges from imports/calls

# AFTER (no change needed!)
async def _create_edges_from_metadata(self, chunk: CodeChunk) -> list[Edge]:
    metadata = chunk.metadata  # Works for ANY language now!
    # ... create edges from imports/calls
```

**Reason**: GraphConstructionService is **language-agnostic**. It only needs `imports: [...]` and `calls: [...]`, regardless of how they were extracted.

---

## 📈 Estimation & Timeline

### Story Points Breakdown

| Story | Description | Points | Hours | Risk |
|-------|-------------|--------|-------|------|
| 26.1 | TypeScript Import Extraction | 2 pts | 6h | Low |
| 26.2 | TypeScript Call Extraction | 2 pts | 6h | Low |
| 26.3 | MetadataExtractorService Integration | 1 pt | 4h | Medium |
| 26.4 | JavaScript Support | 2 pts | 6h | Low |
| 26.5 | Testing & Validation | 2 pts | 8h | Medium |
| 26.6 | Documentation | 1 pt | 4h | Low |
| **TOTAL** | **6 stories** | **10 pts** | **34h** | - |

**Velocity**: 12-14 pts/mois (solo dev) → **3-4 semaines**

**Buffer**: +20% → **40-42h** (5-6 jours de dev pur)

---

### Implementation Roadmap

#### Week 1: TypeScript Core (Stories 26.1, 26.2)

**Day 1-2**: Story 26.1 (Import Extraction)
- Setup metadata_extractors package
- Implement TypeScriptMetadataExtractor
- Write tree-sitter queries for imports
- Unit tests (10 tests)

**Day 3-4**: Story 26.2 (Call Extraction)
- Implement extract_calls() with tree-sitter queries
- Handle method calls, chained calls, constructors
- Unit tests (15 tests)
- **Milestone**: TypeScriptMetadataExtractor functional

---

#### Week 2: Integration & JavaScript (Stories 26.3, 26.4)

**Day 5-6**: Story 26.3 (Integration)
- Refactor MetadataExtractorService (routing)
- Wire up TypeScriptMetadataExtractor
- Update GraphConstructionService (if needed)
- Integration tests (5 tests)
- **Milestone**: CVGenerator shows >100 edges

**Day 7-8**: Story 26.4 (JavaScript Support)
- Create JavaScriptMetadataExtractor
- Handle CommonJS (require, module.exports)
- Unit tests (15 tests)
- **Milestone**: JavaScript projects supported

---

#### Week 3: Validation & Documentation (Stories 26.5, 26.6)

**Day 9-10**: Story 26.5 (Testing & Validation)
- Re-index CVGenerator, verify edges
- Test MnemoLite frontend (Vue.js)
- Performance testing (1000+ files)
- Graph visualization validation

**Day 11**: Story 26.6 (Documentation)
- Write CODE_GRAPH_METADATA_EXTRACTION.md
- Write ADDING_LANGUAGE_SUPPORT.md
- Update README
- EPIC completion report

**Day 12**: Buffer & Polish
- Fix bugs discovered in testing
- Performance optimization if needed
- Final validation
- **Production Ready** 🎉

---

## ⚠️ Risks & Mitigations

### Risk 1: tree-sitter Query Complexity (Medium)

**Description**: tree-sitter queries peuvent être difficiles à écrire/déboguer pour des patterns complexes.

**Impact**: Délais si les queries ne matchent pas correctement les nodes.

**Mitigation**:
- ✅ tree-sitter playground pour tester les queries (https://tree-sitter.github.io/tree-sitter/playground)
- ✅ Référence: tree-sitter-typescript grammar (https://github.com/tree-sitter/tree-sitter-typescript)
- ✅ Unit tests exhaustifs (10+ test cases per query)
- ✅ Fallback: Si query échoue, log warning mais continue (graceful degradation)

**Example Testing Strategy**:
```python
def test_import_extraction():
    test_cases = [
        ("import { X } from 'mod'", ['mod.X']),
        ("import * as Y from 'mod'", ['mod']),
        ("import Z from 'mod'", ['mod']),
        # ... 7 more cases
    ]
    for code, expected in test_cases:
        result = extractor.extract_imports(code)
        assert result == expected
```

---

### Risk 2: Performance Degradation (Low-Medium)

**Description**: tree-sitter queries peuvent être plus lentes que Python `ast` module.

**Impact**: Indexation plus lente pour grands projets TypeScript.

**Mitigation**:
- ✅ Benchmark: Comparer performance Python vs TypeScript extraction
- ✅ Objectif: <5% slowdown acceptable
- ✅ Cache: Métadonnées déjà mises en cache (pas ré-extrait à chaque recherche)
- ✅ Optimisation: tree-sitter est très performant (C library)

**Baseline**: Python indexing ~100 files/s → Acceptable si TypeScript ~90 files/s

---

### Risk 3: Edge Case Coverage (Medium)

**Description**: TypeScript/JavaScript ont de nombreux patterns (dynamic imports, destructuring, etc.).

**Impact**: Certains imports/calls non détectés → Graph incomplet.

**Mitigation**:
- ✅ Focus MVP: Patterns les plus communs (90% des cas)
- ✅ Logging: Log warning si pattern non-supporté
- ✅ Iteration: Améliorer coverage dans future EPICs
- ✅ Tests: Tester avec de vrais codebases (CVGenerator, MnemoLite frontend)

**Out of Scope Phase 1**:
- ❌ Dynamic imports (`import('module')`)
- ❌ Destructuring imports (`import { a: { b } } from 'mod'`)
- ❌ Webpack aliases (`import 'src/models'` → résolution)

---

### Risk 4: Breaking Changes in tree-sitter Grammar (Low)

**Description**: tree-sitter-typescript grammar peut changer (node types renommés).

**Impact**: Queries ne matchent plus, extraction échoue.

**Mitigation**:
- ✅ Pin tree-sitter versions dans requirements.txt
- ✅ Integration tests: Catch breaking changes rapidement
- ✅ Fallback: Si extraction échoue, retourne métadonnées partielles

---

## ✅ Success Metrics

### Phase 1: TypeScript Support (Week 1-2)

**Functional**:
- [x] CVGenerator: 294 nodes, **>100 edges** (currently 0)
- [x] Graph visualization: Nodes connected (no isolated nodes)
- [x] Import extraction: >90% coverage for common patterns
- [x] Call extraction: >85% coverage for common patterns

**Technical**:
- [x] Tests: 50+ tests passing (100% success rate)
- [x] Performance: <5% slowdown vs Python indexing
- [x] Code quality: Zero TypeScript/mypy errors

---

### Phase 2: JavaScript Support (Week 2-3)

**Functional**:
- [x] JavaScript projects: Nodes + edges detected
- [x] CommonJS: `require()` and `module.exports` handled
- [x] ESM: Same support as TypeScript

**Technical**:
- [x] Tests: 65+ total tests passing
- [x] Performance: <2s for 1000 files indexing

---

### Phase 3: Production Ready (Week 3)

**Quality**:
- [x] Documentation: 100% coverage (user guide + developer guide)
- [x] Real-world validation: 3+ projects tested (CVGenerator, MnemoLite frontend, etc.)
- [x] Zero P0/P1 bugs

**User Experience**:
- [x] Graph visualization functional for TypeScript/JavaScript projects
- [x] Developers can add new languages easily (guide provided)
- [x] MCP integration: Metadata available for LLM queries

---

## 🔗 Dependencies

### Upstream Dependencies (Blockers)

**Hard Dependencies**:
- ✅ EPIC-06: Code graph (GraphConstructionService exists)
- ✅ EPIC-15: tree-sitter (TypeScriptParser exists)
- ⚠️ EPIC-25: Dashboard UI (Graph page created but non-functional)

**Status**: **NO BLOCKERS** - All infrastructure exists!

---

### Downstream Dependencies (Enables)

**EPICs Unlocked by EPIC-26**:
- 🔓 EPIC-25 Story 25.5: Graph visualization becomes functional
- 🔓 EPIC-27: Advanced graph analytics (path finding, centrality)
- 🔓 EPIC-28: Multi-language support (Go, Rust, Java)

---

## 📝 Acceptance Criteria (EPIC-26 Complete)

### Functional Requirements

**Core Features**:
- [x] TypeScript import extraction (ESM: import, export)
- [x] TypeScript call extraction (functions, methods, constructors)
- [x] JavaScript import extraction (ESM + CommonJS)
- [x] JavaScript call extraction (same as TypeScript)
- [x] MetadataExtractorService routes by language
- [x] GraphConstructionService creates edges from TypeScript/JS metadata

**Validation**:
- [x] CVGenerator: **>100 edges** (from 0)
- [x] MnemoLite frontend: Nodes + edges detected
- [x] Graph visualization: Connected graph (no isolated nodes)

---

### Technical Requirements

**Code Quality**:
- [x] 65+ tests passing (100% success rate)
- [x] Zero TypeScript/mypy errors
- [x] Test coverage: >80% for new code
- [x] Performance: <5% slowdown vs Python

**Architecture**:
- [x] DIP pattern: MetadataExtractor Protocol implemented
- [x] No breaking changes to existing code (Python extractor intact)
- [x] Extensible: New languages easy to add

---

### Documentation Requirements

**Deliverables**:
- [x] CODE_GRAPH_METADATA_EXTRACTION.md (~800 lines)
- [x] ADDING_LANGUAGE_SUPPORT.md (~400 lines)
- [x] EPIC-26_COMPLETION_REPORT.md
- [x] Updated README.md with TypeScript/JavaScript support
- [x] tree-sitter queries documented (reference guide)

---

## 📚 References

### tree-sitter Resources

**Official Docs**:
- tree-sitter Query Syntax: https://tree-sitter.github.io/tree-sitter/using-parsers/queries
- tree-sitter Playground: https://tree-sitter.github.io/tree-sitter/playground

**Grammars**:
- tree-sitter-typescript: https://github.com/tree-sitter/tree-sitter-typescript
- tree-sitter-javascript: https://github.com/tree-sitter/tree-sitter-javascript

### MnemoLite Architecture

**Related Services**:
- `api/services/code_chunking_service.py` - TypeScriptParser (lines 162-250)
- `api/services/metadata_extractor_service.py` - Current Python-only extractor
- `api/services/graph_construction_service.py` - Edge creation logic

**Related EPICs**:
- EPIC-06: Code graph construction
- EPIC-15: tree-sitter integration
- EPIC-25: Dashboard UI (Graph page)

### Debugging Tools

**tree-sitter CLI**:
```bash
# Install tree-sitter CLI
npm install -g tree-sitter-cli

# Parse TypeScript file and inspect AST
tree-sitter parse file.ts

# Test queries
tree-sitter query path/to/queries.scm file.ts
```

---

## 🎓 Key Learnings from Previous EPICs

### EPIC-23: MCP Integration

**Lesson**: Infrastructure réutilisation → 71% faster than estimated (Story 23.11)
**Applied**: Réutiliser tree-sitter existant au lieu de rebuilder tout

### EPIC-25: Dashboard UI

**Lesson**: YAGNI - 73% scope reduction, 100% core value delivered
**Applied**: Focus sur imports/calls seulement, pas type inference/complexity

### EPIC-15: tree-sitter Integration

**Lesson**: tree-sitter queries sont puissantes mais nécessitent testing exhaustif
**Applied**: 10+ test cases per query, fallback si query échoue

---

## 📅 Milestones

### Milestone 1: TypeScript Extraction Works (Week 1)

**Date**: 2025-11-08 (estimated)
**Criteria**:
- [x] TypeScriptMetadataExtractor implemented
- [x] 25+ tests passing
- [x] Imports + calls extracted correctly

---

### Milestone 2: Integration Complete (Week 2)

**Date**: 2025-11-15 (estimated)
**Criteria**:
- [x] MetadataExtractorService refactored
- [x] CVGenerator shows >100 edges
- [x] Graph visualization functional

---

### Milestone 3: Production Ready (Week 3)

**Date**: 2025-11-22 (estimated)
**Criteria**:
- [x] JavaScript support complete
- [x] 3+ real projects validated
- [x] Documentation complete
- [x] EPIC-26 COMPLETE 🎉

---

## 🚀 Next Steps After EPIC-26

### EPIC-27: Advanced Graph Analytics (Future)

**Features**:
- Path finding (shortest path between nodes)
- Centrality metrics (identify critical functions)
- Community detection (module clustering)
- Impact analysis (change propagation)

**Estimated**: 15 pts, 4-5 semaines

---

### EPIC-28: Multi-Language Support (Future)

**Languages**:
- Go (tree-sitter-go)
- Rust (tree-sitter-rust)
- Java (tree-sitter-java)

**Estimated**: 12 pts per language, 3-4 semaines each

**Prerequisite**: EPIC-26 pattern proven → easy to replicate

---

## 📊 Progress Tracking

### Story Status

| Story | Description | Points | Status | % |
|-------|-------------|--------|--------|---|
| 26.1 | TypeScript Import Extraction | 2 pts | 🔴 PENDING | 0% |
| 26.2 | TypeScript Call Extraction | 2 pts | 🔴 PENDING | 0% |
| 26.3 | MetadataExtractorService Integration | 1 pt | 🔴 PENDING | 0% |
| 26.4 | JavaScript Support | 2 pts | 🔴 PENDING | 0% |
| 26.5 | Testing & Validation | 2 pts | 🔴 PENDING | 0% |
| 26.6 | Documentation | 1 pt | 🔴 PENDING | 0% |
| **TOTAL** | **6 stories** | **10 pts** | 🔴 PENDING | **0%** |

**Start Date**: TBD
**Target Completion**: TBD (3-4 semaines after start)

---

**END OF EPIC-26 README**

**Status**: 🔴 PENDING (Not Started)
**Priority**: P1 (Critical - Blocks Graph Visualization)
**Next Action**: Review & approve EPIC scope, then start Story 26.1

**Questions?** Voir:
- `frontend/GRAPH_AUDIT_REPORT.md` (problème identifié)
- `docs/CODE_GRAPH_METADATA_EXTRACTION.md` (après Story 26.6)
- CLAUDE.md skill: `mnemolite-architecture` (architecture patterns)

**Dernière mise à jour**: 2025-11-01
**Version**: 1.0 (Initial scope)
