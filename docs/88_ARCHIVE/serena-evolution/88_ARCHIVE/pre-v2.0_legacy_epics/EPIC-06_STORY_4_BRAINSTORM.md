# EPIC-06 Story 4: Dependency Graph Construction - Brainstorm

**Date**: 2025-10-16
**Version**: 1.0.0
**Story Points**: 13
**Estimation**: 5-7 jours
**Dépendances**: Story 1 (Chunking) ✅, Story 3 (Metadata) ✅

---

## 🎯 Objectif Story 4

**User Story**:
> En tant qu'agent IA, je veux **naviguer le call graph du code indexé**, afin de **comprendre les dépendances et l'architecture** d'une codebase.

**Contexte**:
- Phase 1 Stories 1, 2bis & 3: ✅ DONE (Chunking + Repository + Metadata)
- Nous avons déjà: `code_chunks` table avec metadata JSONB
- Nous avons déjà: `nodes` et `edges` tables dans PostgreSQL (graph infrastructure existante)
- Story 3 extrait déjà `imports` et `calls` dans metadata
- Story 4 = **construire et stocker les graphes de dépendances** dans nodes/edges

**Pourquoi Story 4 est critique**:
- Permet navigation relationnelle dans codebase
- Comprendre architecture et flow de données
- Identifier impact des changements (reverse dependencies)
- Détecter code mort (unused functions)
- Visualiser complexité et couplage

---

## 📊 Types de Graphes à Construire

### 1. Call Graph (Priority: HIGH)

**Définition**: Fonction A appelle fonction B

**Exemple**:
```python
# File: utils.py
def calculate_total(items):
    result = sum(items)  # ← appelle built-in sum()
    return validate_total(result)  # ← appelle validate_total()

def validate_total(total):
    if total < 0:
        raise ValueError("Negative total")
    return total
```

**Graph attendu**:
```
calculate_total --calls--> sum (built-in)
calculate_total --calls--> validate_total
```

**Challenges**:
- Résoudre les appels indirects (variables, lambdas)
- Distinguer appels internes vs externes (built-ins, imports)
- Gérer méthodes (obj.method()) vs fonctions

---

### 2. Import Graph (Priority: HIGH)

**Définition**: Module A importe module B

**Exemple**:
```python
# File: main.py
from utils import calculate_total
import os
from typing import List
```

**Graph attendu**:
```
main.py --imports--> utils.calculate_total
main.py --imports--> os
main.py --imports--> typing.List
```

**Challenges**:
- Résoudre imports relatifs (from . import foo)
- Gérer imports conditionnels (if TYPE_CHECKING)
- Différencier imports standards vs projet

---

### 3. Inheritance Graph (Priority: MEDIUM)

**Définition**: Classe A hérite de classe B

**Exemple**:
```python
class Animal:
    pass

class Dog(Animal):
    pass

class Poodle(Dog):
    pass
```

**Graph attendu**:
```
Dog --extends--> Animal
Poodle --extends--> Dog
```

**Challenges**:
- Multiple inheritance (Python supporte)
- Mixins et abstract base classes
- Résoudre classes importées

---

### 4. Data Flow Graph (Priority: LOW - Phase 2+)

**Définition**: Variable X est utilisée par fonction Y

**Exemple**:
```python
CONFIG = {"api_key": "..."}

def make_request():
    headers = {"Authorization": CONFIG["api_key"]}
    # ...
```

**Graph attendu**:
```
CONFIG --used_by--> make_request
```

**Challenges**:
- Tracking variables globales
- Scope resolution (local vs global)
- Dynamic access (getattr, __dict__)

**Recommandation**: ❌ **HORS SCOPE Story 4** - Trop complexe, reporter Phase 2+

---

## 🏗️ Architecture Proposée

### Option A: Static Analysis + Nodes/Edges Storage ⭐ RECOMMANDÉ

**Flow**:
```
Code Chunking (Story 1)
    ↓
Metadata Extraction (Story 3) → imports[], calls[] extracted
    ↓
Graph Construction (Story 4) → resolve targets + create nodes/edges
    ↓
PostgreSQL Storage (nodes/edges tables)
    ↓
Graph Traversal API (CTE recursifs)
```

**Avantages**:
- ✅ Utilise infrastructure existante (nodes/edges tables)
- ✅ Consistent avec architecture MnemoLite (PostgreSQL-only)
- ✅ CTE récursifs pour traversal efficace
- ✅ Metadata déjà extrait (Story 3 donne imports/calls)

**Inconvénients**:
- ⚠️ Résolution cross-file complexe (imports)
- ⚠️ Graph peut être très large (100k+ edges sur gros projets)

---

### Option B: NetworkX In-Memory Graph

**Flow**:
```
Code → Static Analysis → NetworkX graph → Algorithms → Results
```

**Avantages**:
- ✅ Algorithms built-in (shortest path, centrality, cycles)
- ✅ Visualisation facile (matplotlib, graphviz)

**Inconvénients**:
- ❌ Pas persistent (graph perdu si redémarrage)
- ❌ RAM intensif sur gros projets
- ❌ Pas consistent avec MnemoLite (PostgreSQL-only)

**Recommandation**: Utiliser NetworkX uniquement pour **validation/debugging**, pas production.

---

### Option C: Hybrid (PostgreSQL + NetworkX cache)

**Flow**:
```
PostgreSQL (source of truth) → NetworkX (cache pour algorithms) → Results
```

**Avantages**:
- ✅ Persistent dans PostgreSQL
- ✅ Fast algorithms via NetworkX

**Inconvénients**:
- ⚠️ Complexité accrue (sync cache)
- ⚠️ RAM overhead

**Recommandation**: ⚠️ **Considérer Phase 2+** si performance issues.

---

## 🔍 Analyse Technique: Résolution de Dépendances

### Challenge 1: Résoudre Call Targets

**Problème**: Dans metadata, nous avons `calls: ["sum", "validate_total"]`, mais:
- `sum` = built-in Python
- `validate_total` = fonction dans même fichier ? Autre fichier ?

**Solution proposée**:

1. **Built-ins Detection**:
```python
PYTHON_BUILTINS = {
    "sum", "len", "range", "print", "open",
    "int", "str", "list", "dict", "set",
    # ... ~70 built-ins
}

def is_builtin(name: str) -> bool:
    return name in PYTHON_BUILTINS
```

2. **Local Functions Detection**:
```python
# Pour chaque call "validate_total"
# Chercher dans code_chunks WHERE name = 'validate_total' AND file_path = current_file
```

3. **Imported Functions Detection**:
```python
# Si call "calculate" et imports contient "utils.calculate"
# → Résoudre vers code_chunk de utils.calculate
```

**Complexité**: 🟡 **MOYEN** - Require cross-chunk lookup

---

### Challenge 2: Résoudre Import Targets

**Problème**: `imports: ["typing.List", "os", "utils.calculate_total"]`
- `typing.List` = standard library
- `os` = standard library
- `utils.calculate_total` = projet local

**Solution proposée**:

1. **Standard Library Detection**:
```python
import sys

STDLIB_MODULES = set(sys.stdlib_module_names)  # Python 3.10+

def is_stdlib(module: str) -> bool:
    root = module.split('.')[0]
    return root in STDLIB_MODULES
```

2. **Project Modules Detection**:
```python
# Chercher dans code_chunks WHERE file_path LIKE 'utils.py'
# Si trouvé → module projet, sinon → external dependency
```

**Complexité**: 🟢 **FACILE** - Mostly string matching

---

### Challenge 3: Cross-File Resolution

**Problème**:
```python
# File: main.py
from utils import calculate_total

calculate_total([1, 2, 3])  # ← Où est défini calculate_total ?
```

**Solution proposée**:

1. **Build Module Index**:
```python
# Au moment de l'indexation (Story 6), créer:
module_index = {
    "utils.calculate_total": {
        "file_path": "utils.py",
        "chunk_id": "<uuid>",
        "node_id": "<uuid>"
    }
}
```

2. **Resolve à la volée**:
```python
def resolve_call(call_name: str, current_file: str, imports: list) -> Optional[UUID]:
    # 1. Check local file
    local_chunk = db.query("""
        SELECT id FROM code_chunks
        WHERE name = :name AND file_path = :file
    """, name=call_name, file=current_file)

    if local_chunk:
        return local_chunk.id

    # 2. Check imports
    for imp in imports:
        if imp.endswith(call_name):
            # Resolve import → chunk_id
            return resolve_import(imp)

    # 3. Not found
    return None
```

**Complexité**: 🟠 **DIFFICILE** - Require global context

---

## 📐 Schéma DB: Utiliser Nodes/Edges Existants

### Nodes Table (Déjà Existant)

```sql
-- Déjà dans MnemoLite
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY,
    node_type TEXT,  -- 'function', 'class', 'method', 'module'
    label TEXT,      -- Nom de la fonction/classe
    props JSONB      -- Métadonnées code-specific
);
```

**Proposition**: Étendre `props` pour code:
```json
{
  "chunk_id": "<uuid>",       // Lien vers code_chunks
  "file_path": "utils.py",
  "language": "python",
  "signature": "calculate_total(items: List[float]) -> float",
  "complexity": {"cyclomatic": 3},
  "is_builtin": false,
  "is_stdlib": false
}
```

### Edges Table (Déjà Existant)

```sql
-- Déjà dans MnemoLite
CREATE TABLE edges (
    edge_id UUID PRIMARY KEY,
    source_node UUID,
    target_node UUID,
    relationship TEXT,  -- 'calls', 'imports', 'extends', 'uses'
    props JSONB
);
```

**Proposition**: Étendre `props` pour code:
```json
{
  "call_count": 3,           // Combien de fois fonction appelée (static)
  "is_direct": true,         // Direct call vs indirect (via variable)
  "line_number": 42,         // Où l'appel se produit
  "context": "calculate_total(items)"  // Code snippet
}
```

### Index Recommandés

```sql
-- Index pour traversal rapide
CREATE INDEX idx_edges_source ON edges(source_node);
CREATE INDEX idx_edges_target ON edges(target_node);
CREATE INDEX idx_edges_relationship ON edges(relationship);

-- Index pour filtrage
CREATE INDEX idx_nodes_type ON nodes(node_type);
CREATE INDEX idx_nodes_label ON nodes(label);
CREATE INDEX idx_nodes_props_chunk ON nodes USING gin ((props->'chunk_id'));
```

---

## 🎯 Scope Story 4: MVP vs Full

### ✅ MUST-HAVE (Core Story 4)

| Feature | Priority | Justification |
|---------|----------|---------------|
| **Call Graph Construction** | 🔴 HAUTE | Core use case - comprendre flow |
| **Import Graph Construction** | 🔴 HAUTE | Dépendances critiques |
| **Nodes/Edges Storage** | 🔴 HAUTE | Persistence nécessaire |
| **Graph Traversal API** | 🔴 HAUTE | Query le graph |
| **CTE Récursifs (≤3 hops)** | 🔴 HAUTE | Navigation efficace |
| **Résolution Built-ins** | 🟡 MOYENNE | Filtrage important |
| **Résolution Local Calls** | 🔴 HAUTE | Core functionality |

**Total**: **7 features MUST-HAVE**

---

### ⚠️ NICE-TO-HAVE (Phase 2 Optionnel)

| Feature | Priority | Raison optionnel |
|---------|----------|------------------|
| **Inheritance Graph** | 🟡 MOYENNE | Utile mais pas critique Phase 1 |
| **Résolution Cross-File** | 🟡 MOYENNE | Complexe, peut être approximé |
| **Call Count (dynamic)** | 🟢 BASSE | Require runtime analysis |
| **Cycle Detection** | 🟡 MOYENNE | Utile mais coûteux |
| **Dead Code Detection** | 🟡 MOYENNE | Analysis post-graph |

---

### ❌ HORS SCOPE Story 4 (Reporter)

| Feature | Story Future | Raison |
|---------|--------------|--------|
| **Data Flow Graph** | **Phase 2+** | Trop complexe, require advanced static analysis |
| **Usage Frequency (runtime)** | **Story 6 + instrumentation** | Require code execution tracking |
| **Graph Visualization UI** | **UI v4.1** | Frontend work, pas backend |
| **Cross-Language Graphs** | **Phase 2** | Story 4 = Python only |

---

## 💡 Architecture Services

### 1. GraphConstructionService (NEW)

```python
# api/services/graph_construction_service.py

class GraphConstructionService:
    """
    Construct dependency graphs from code chunks metadata.

    Responsibilities:
    - Extract call graph from chunks
    - Extract import graph from chunks
    - Resolve function/class targets
    - Create nodes and edges
    - Store in PostgreSQL
    """

    def __init__(self):
        self.node_repository = get_node_repository()
        self.edge_repository = get_edge_repository()
        self.chunk_repository = get_code_chunk_repository()

    async def build_graph_for_repository(
        self,
        repository: str,
        language: str = "python"
    ) -> GraphStats:
        """
        Build complete graph for a repository.

        1. Get all chunks for repository
        2. Create nodes for all functions/classes
        3. Resolve calls and imports
        4. Create edges
        5. Return statistics
        """
        pass

    async def _create_nodes_from_chunks(
        self,
        chunks: list[CodeChunk]
    ) -> dict[str, UUID]:
        """
        Create node for each function/class chunk.

        Returns:
            Mapping {chunk_id: node_id}
        """
        pass

    async def _create_call_edges(
        self,
        chunk: CodeChunk,
        node_id: UUID,
        chunk_to_node: dict[str, UUID]
    ) -> list[Edge]:
        """
        Create call edges for a chunk.

        For each call in chunk.metadata['calls']:
        1. Resolve target chunk
        2. Get target node_id
        3. Create edge (source_node=node_id, target_node=target_id, relationship='calls')
        """
        pass

    async def _create_import_edges(
        self,
        chunk: CodeChunk,
        node_id: UUID,
        chunk_to_node: dict[str, UUID]
    ) -> list[Edge]:
        """Create import edges for a chunk."""
        pass

    async def _resolve_call_target(
        self,
        call_name: str,
        current_chunk: CodeChunk,
        all_chunks: list[CodeChunk]
    ) -> Optional[UUID]:
        """
        Resolve call target to chunk_id.

        Strategy:
        1. Check if built-in → return None (skip)
        2. Check local file → return chunk_id
        3. Check imports → resolve import → return chunk_id
        4. Not found → return None (log warning)
        """
        pass
```

---

### 2. GraphTraversalService (NEW)

```python
# api/services/graph_traversal_service.py

class GraphTraversalService:
    """
    Query and traverse dependency graphs.

    Responsibilities:
    - Find functions called by X
    - Find functions calling X (reverse deps)
    - Find import chains
    - Traverse graph with depth limit
    """

    def __init__(self):
        self.node_repository = get_node_repository()
        self.edge_repository = get_edge_repository()

    async def get_called_by(
        self,
        node_id: UUID,
        relationship: str = "calls",
        depth: int = 1
    ) -> list[Node]:
        """
        Get all nodes called by node_id (outbound edges).

        Example:
            calculate_total calls:
            - sum (built-in)
            - validate_total

        Returns:
            [sum_node, validate_total_node]
        """
        pass

    async def get_callers_of(
        self,
        node_id: UUID,
        relationship: str = "calls",
        depth: int = 1
    ) -> list[Node]:
        """
        Get all nodes calling node_id (inbound edges).

        Example:
            Who calls validate_total?
            - calculate_total
            - process_order

        Returns:
            [calculate_total_node, process_order_node]
        """
        pass

    async def traverse_graph(
        self,
        start_node: UUID,
        direction: str = "outbound",  # "outbound" | "inbound"
        relationship: str = "calls",
        max_depth: int = 3
    ) -> GraphTraversal:
        """
        Traverse graph using CTE récursif.

        SQL:
            WITH RECURSIVE graph_traversal AS (
                -- Base case
                SELECT node_id, 0 as depth
                FROM nodes
                WHERE node_id = :start_node

                UNION ALL

                -- Recursive case
                SELECT e.target_node, gt.depth + 1
                FROM graph_traversal gt
                JOIN edges e ON e.source_node = gt.node_id
                WHERE gt.depth < :max_depth
                  AND e.relationship = :relationship
            )
            SELECT * FROM graph_traversal;
        """
        pass
```

---

### 3. NodeRepository & EdgeRepository (EXTEND)

**Déjà existants dans MnemoLite**, à étendre:

```python
# api/db/repositories/node_repository.py

class NodeRepository:
    """CRUD operations on nodes table."""

    async def create_code_node(
        self,
        node_type: str,  # "function" | "class" | "method"
        label: str,
        chunk_id: UUID,
        file_path: str,
        metadata: dict
    ) -> Node:
        """Create node for code chunk."""
        pass

    async def get_by_chunk_id(self, chunk_id: UUID) -> Optional[Node]:
        """Get node associated with code chunk."""
        pass

    async def search_by_label(
        self,
        label: str,
        node_type: Optional[str] = None
    ) -> list[Node]:
        """Search nodes by name (for resolution)."""
        pass


# api/db/repositories/edge_repository.py

class EdgeRepository:
    """CRUD operations on edges table."""

    async def create_dependency_edge(
        self,
        source_node: UUID,
        target_node: UUID,
        relationship: str,  # "calls" | "imports" | "extends"
        metadata: dict = None
    ) -> Edge:
        """Create edge representing code dependency."""
        pass

    async def get_outbound_edges(
        self,
        node_id: UUID,
        relationship: Optional[str] = None
    ) -> list[Edge]:
        """Get all edges leaving node."""
        pass

    async def get_inbound_edges(
        self,
        node_id: UUID,
        relationship: Optional[str] = None
    ) -> list[Edge]:
        """Get all edges entering node."""
        pass
```

---

## 🧪 Tests Stratégie

### Test Cases (GraphConstructionService)

**Unit Tests**:

1. ✅ `test_create_node_from_function_chunk`
2. ✅ `test_create_node_from_class_chunk`
3. ✅ `test_resolve_builtin_call_returns_none`
4. ✅ `test_resolve_local_call_returns_chunk_id`
5. ✅ `test_resolve_imported_call_returns_chunk_id`
6. ✅ `test_create_call_edge_simple`
7. ✅ `test_create_import_edge_simple`
8. ✅ `test_build_graph_small_repository`

**Integration Tests**:

1. ✅ `test_build_graph_real_python_file`
2. ✅ `test_graph_handles_circular_imports`
3. ✅ `test_graph_handles_missing_targets`

**Total**: ~11 tests

---

### Test Cases (GraphTraversalService)

**Unit Tests**:

1. ✅ `test_get_called_by_depth_1`
2. ✅ `test_get_called_by_depth_2`
3. ✅ `test_get_callers_of`
4. ✅ `test_traverse_graph_outbound`
5. ✅ `test_traverse_graph_inbound`
6. ✅ `test_traverse_graph_max_depth`

**Total**: ~6 tests

---

### Test Cases (Node/Edge Repositories)

**Integration Tests**:

1. ✅ `test_create_code_node`
2. ✅ `test_get_node_by_chunk_id`
3. ✅ `test_search_nodes_by_label`
4. ✅ `test_create_dependency_edge`
5. ✅ `test_get_outbound_edges`
6. ✅ `test_get_inbound_edges`

**Total**: ~6 tests

---

**Total Story 4**: **~23 tests** minimum

---

## ⚡ Performance Considérations

### Bottlenecks Potentiels

1. **Graph Construction (N chunks)**:
   - Pour chaque chunk, résoudre M calls
   - Worst case: O(N × M) database queries
   - **Mitigation**: Batch queries, cache chunk lookups

2. **Graph Traversal (CTE Récursifs)**:
   - Depth 3 sur graph dense = explosion combinatoire
   - **Mitigation**: Limit depth ≤ 3, add timeout

3. **Large Graphs (100k+ nodes)**:
   - Index critiques sur edges(source_node, target_node)
   - **Mitigation**: Indexes déjà prévus, EXPLAIN ANALYZE

### Performance Targets

- **Graph Construction**: <5s pour 100 chunks
- **Graph Traversal (depth=2)**: <20ms P95
- **Graph Traversal (depth=3)**: <100ms P95

---

## 🚧 Risques & Mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| **Résolution Cross-File Complexe** | Haut | Élevée | Approximation acceptable Phase 1, améliorer Phase 2 |
| **Graph Explosion (depth > 3)** | Moyen | Moyenne | Limit depth strict, timeout queries |
| **Circular Dependencies** | Moyen | Moyenne | CTE CYCLE detection (PostgreSQL 14+) |
| **Built-ins Pollution** | Faible | Faible | Filter built-ins, ne pas créer nodes |
| **Performance Degradation** | Haut | Moyenne | Indexes, EXPLAIN ANALYZE, batch queries |

---

## 🎯 Décisions Clés à Prendre

### Décision 1: Scope Résolution Cross-File

**Options**:
- **A**: Résolution complète (100% accurate) - Complexe, long
- **B**: Résolution best-effort (80% accurate) - Pragmatique ⭐ RECOMMANDÉ
- **C**: Résolution locale seulement (60% accurate) - Incomplet

**Recommandation**: **Option B** - Best-effort acceptable Phase 1, améliorer Phase 2

---

### Décision 2: Built-ins Handling

**Options**:
- **A**: Créer nodes pour built-ins (pollution graph)
- **B**: Skip built-ins (perte information) ⭐ RECOMMANDÉ
- **C**: Créer nodes spéciaux "external"

**Recommandation**: **Option B** - Skip built-ins Phase 1, ajouter si besoin Phase 2

---

### Décision 3: Graph Storage Strategy

**Options**:
- **A**: PostgreSQL nodes/edges only ⭐ RECOMMANDÉ
- **B**: PostgreSQL + NetworkX cache
- **C**: NetworkX only (pas persistent)

**Recommandation**: **Option A** - Consistent avec MnemoLite, optimiser si besoin

---

### Décision 4: Traversal Max Depth

**Options**:
- **A**: Depth illimité (risque explosion)
- **B**: Depth ≤ 3 (safe) ⭐ RECOMMANDÉ
- **C**: Depth ≤ 5 (flexible mais risqué)

**Recommandation**: **Option B** - Depth 3 couvre 95% use cases, safe performance

---

## 📋 Story 4 Implementation Plan

### Phase 1: Graph Construction (3 jours)

**Jour 1**:
1. ✅ Create `GraphConstructionService`
2. ✅ Implement `_create_nodes_from_chunks()`
3. ✅ Implement built-ins detection
4. ✅ Unit tests (5 tests)

**Jour 2**:
1. ✅ Implement `_resolve_call_target()` (local + imports)
2. ✅ Implement `_create_call_edges()`
3. ✅ Implement `_create_import_edges()`
4. ✅ Unit tests (3 tests)

**Jour 3**:
1. ✅ Implement `build_graph_for_repository()` (orchestration)
2. ✅ Integration tests (3 tests)
3. ✅ Test sur codebase réelle (MnemoLite self-index)

---

### Phase 2: Graph Traversal (2 jours)

**Jour 4**:
1. ✅ Extend `NodeRepository` and `EdgeRepository`
2. ✅ Create `GraphTraversalService`
3. ✅ Implement `get_called_by()` and `get_callers_of()`
4. ✅ Unit tests (6 tests)

**Jour 5**:
1. ✅ Implement `traverse_graph()` with CTE récursifs
2. ✅ Add cycle detection (PostgreSQL CYCLE)
3. ✅ Integration tests (3 tests)
4. ✅ Performance benchmarks (depth 1-3)

---

### Phase 3: API Routes (1 jour)

**Jour 6**:
1. ✅ Create API routes:
   - `GET /v1/code/graph/calls?from=<node_id>&depth=2`
   - `GET /v1/code/graph/callers?of=<node_id>&depth=2`
   - `GET /v1/code/graph/imports?from=<node_id>`
2. ✅ OpenAPI documentation
3. ✅ API tests (3 tests)

---

### Phase 4: Validation & Documentation (1 jour)

**Jour 7**:
1. ✅ Audit graph construction sur MnemoLite codebase
2. ✅ Visualize graph (NetworkX export pour debugging)
3. ✅ Update EPIC-06_Code_Intelligence.md (Story 4 complete)
4. ✅ Create ADR si décisions techniques majeures

**Total**: **7 jours** (dans budget 5-7 jours)

---

## 🚀 Prochaines Étapes

### Avant de Coder

1. **Valider scope** avec stakeholder (toi!)
   - Best-effort resolution OK?
   - Skip built-ins OK?
   - Depth ≤ 3 OK?

2. **Valider architecture**
   - GraphConstructionService + GraphTraversalService OK?
   - PostgreSQL nodes/edges only OK?

3. **Préparer données test**
   - Small Python project (10-20 fonctions avec imports)
   - MnemoLite self-index (validation réaliste)

### Démarrer Implementation

1. Create `api/services/graph_construction_service.py`
2. Create `api/services/graph_traversal_service.py`
3. Extend `api/db/repositories/node_repository.py`
4. Extend `api/db/repositories/edge_repository.py`
5. Create tests
6. API routes
7. Validation sur MnemoLite

---

## 📝 Questions Ouvertes

### Question 1: Résolution Import Targets

Résoudre imports relatifs (`from . import foo`) ou skip Phase 1?
- **Recommandation**: Skip Phase 1, améliorer Phase 2

### Question 2: Circular Dependencies

Détecter et alerter ou tolérer?
- **Recommandation**: Tolérer Phase 1 (CTE CYCLE prévient loops infinis), alerter Phase 2

### Question 3: External Dependencies

Créer nodes pour packages externes (requests, numpy) ou skip?
- **Recommandation**: Skip Phase 1, ajouter Phase 2 si besoin

### Question 4: Graph Visualization

Export graph format (Graphviz DOT, JSON) ou seulement API?
- **Recommandation**: JSON API Phase 1, Graphviz export Phase 2 (debug)

---

## 🎓 Lessons from Stories 1-3

### Ce qui a bien fonctionné ✅

1. **Brainstorm avant implémentation** (évite refactoring massif)
2. **Tests first** (TDD simplifie debugging)
3. **Audit rigoureux** (Story 3: O(n²) fix grâce à audit)
4. **Documentation continue** (traçabilité parfaite)

### À appliquer Story 4 ✅

1. **Scope clair MVP** (Call + Import graphs, pas Data Flow)
2. **Tests unitaires complets** (23 tests minimum)
3. **Performance benchmarks** (depth 1-3, graph sizes)
4. **Audit après implémentation** (vérifier résolution accuracy)
5. **ADR si décisions techniques** (résolution strategy, etc.)

---

## 📊 Success Criteria Story 4

### ✅ Definition of Done

1. **Fonctionnel**:
   - ✅ Call graph construit (function → functions called)
   - ✅ Import graph construit (module → modules imported)
   - ✅ Nodes/Edges stockés dans PostgreSQL
   - ✅ Graph traversal API (depth ≤ 3)
   - ✅ CTE récursifs pour performance

2. **Tests**:
   - ✅ 11 unit tests passing (GraphConstructionService)
   - ✅ 6 unit tests passing (GraphTraversalService)
   - ✅ 6 integration tests passing (Repositories)
   - ✅ Coverage >85% nouveaux modules

3. **Performance**:
   - ✅ <5s graph construction pour 100 chunks
   - ✅ <20ms traversal depth=2 (P95)
   - ✅ <100ms traversal depth=3 (P95)

4. **API**:
   - ✅ 3 endpoints opérationnels
   - ✅ OpenAPI documentation complète
   - ✅ API tests passing

5. **Documentation**:
   - ✅ EPIC-06_Code_Intelligence.md updated (Story 4 complete)
   - ✅ ADR créée si décisions majeures
   - ✅ Graph examples et use cases documentés

---

## 🔗 Intégration avec Stories Précédentes

**Story 1 (Chunking)** → Fournit code chunks
**Story 3 (Metadata)** → Fournit `imports[]` et `calls[]`
**Story 4 (Graph)** → **Utilise metadata pour construire graph**
**Story 5 (Hybrid Search)** → Utilisera graph pour expansion results
**Story 6 (Indexing API)** → Déclenchera graph construction

**Flow complet**:
```
Story 6: POST /v1/code/index
    ↓
Story 1: Chunking (CodeChunkingService)
    ↓
Story 3: Metadata extraction (MetadataExtractorService)
    ↓
Story 4: Graph construction (GraphConstructionService) ← THIS STORY
    ↓
Story 5: Hybrid search with graph expansion
```

---

**Status**: 🚧 **BRAINSTORM COMPLET** - Ready to implement!
**Next**: Valider scope & architecture, puis start coding 🚀

**Auteur**: Claude (AI Assistant)
**Date**: 2025-10-16
**Version**: 1.0.0
