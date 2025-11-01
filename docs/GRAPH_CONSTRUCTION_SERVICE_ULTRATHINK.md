# GraphConstructionService ULTRATHINK
**Date:** 2025-11-01
**Context:** EPIC-25 Story 25.5 - Complete Code Graph with Relations
**Problem:** 2,946 nodes but only 11 edges (0.4% ratio) - Graph is essentially empty

---

## 🔍 Diagnostic Complet

### État Actuel de la Database

```
CODE CHUNKS (indexed code):
- epic18-stress-test: 834 chunks, 42 files
- CVGenerator: 430 chunks, 45 files  ← code_test repo
- MnemoLite: 120 chunks, 5 files

NODES (functions/classes):
- CVGenerator/method: 1,722 nodes
- MnemoLite/function: 720 nodes
- CVGenerator/class: 336 nodes
- MnemoLite/class: 168 nodes
Total: 2,946 nodes

EDGES (relationships):
- calls: 11 edges  ← CRITICAL PROBLEM!
Total: 11 edges (0.4% of nodes)
```

### Problème Racine

**GraphConstructionService existe mais ne fonctionne pas correctement:**
- Service importé dans `code_graph_routes.py` (ligne 15)
- Mais fichier `services/graph_construction_service.py` **n'existe pas**
- Ou existe mais logique d'extraction des relations défaillante
- Résultat: 99.6% des relations manquantes

### Ratio Attendu

Un code bien analysé devrait avoir:
- **Minimum**: 50% edges/nodes (1,500+ edges pour 3,000 nodes)
- **Normal**: 100-200% edges/nodes (3,000-6,000 edges)
- **Complexe**: 300%+ edges/nodes (9,000+ edges)

**Actuel**: 0.4% (11 edges) → **Quasi-aucune relation extraite**

---

## 🏗️ Architecture Requise

### Vue d'Ensemble du Pipeline

```
┌─────────────────┐
│  Code Chunks    │  ← Déjà indexé ✅
│  (Tree-sitter)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create Nodes    │  ← Fait partiellement ✅
│ (classes, funcs)│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ Extract Relations (MANQUANT)│  ← À IMPLÉMENTER ❌
│ • Function calls            │
│ • Imports                   │
│ • Class inheritance         │
│ • Interface implementation  │
│ • Method overrides          │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│  Create Edges   │  ← Ne fonctionne pas ❌
│  (relationships)│
└─────────────────┘
```

### Composants Nécessaires

#### 1. **Node Creator** (Partiellement Existant)
```python
class NodeCreator:
    """
    Creates nodes from code chunks.
    Status: EXISTS but incomplete
    """
    def create_nodes(chunks: List[CodeChunk]) -> List[Node]:
        # Extract functions, classes, methods
        # DONE: Creates ~3000 nodes ✅
        pass
```

#### 2. **Relation Extractor** (MANQUANT - À CRÉER)
```python
class RelationExtractor:
    """
    Extracts relationships between nodes.
    Status: MISSING - TO IMPLEMENT ❌
    """
    def extract_calls(chunks: List[CodeChunk]) -> List[CallRelation]:
        """
        Find function/method calls.
        Examples:
        - my_func() calls other_func()
        - obj.method() calls another.method()
        """
        pass

    def extract_imports(chunks: List[CodeChunk]) -> List[ImportRelation]:
        """
        Find import relationships.
        Examples:
        - from module import func
        - import MyClass from './file'
        """
        pass

    def extract_inheritance(chunks: List[CodeChunk]) -> List[InheritanceRelation]:
        """
        Find class inheritance.
        Examples:
        - class Child extends Parent
        - class Impl implements Interface
        """
        pass
```

#### 3. **Name Resolver** (CRITIQUE - MANQUANT)
```python
class NameResolver:
    """
    Resolves symbolic names to actual nodes.
    Status: MISSING - TO IMPLEMENT ❌

    Problem: Code has references like "MyClass.method()"
    but we need to find which node corresponds to that name.
    """
    def resolve_call(name: str, context: Context) -> Optional[UUID]:
        """
        Resolve a function/method call to a node ID.

        Challenge: Handle:
        - Qualified names (module.Class.method)
        - Relative imports
        - Aliasing (import X as Y)
        - Scoping (local vs global)
        """
        pass

    def build_symbol_table(chunks: List[CodeChunk]) -> SymbolTable:
        """
        Build a symbol table for name resolution.
        Maps: name -> node_id
        """
        pass
```

#### 4. **Edge Creator** (Existant mais inutilisé)
```python
class EdgeCreator:
    """
    Creates edge records in database.
    Status: EXISTS but not called properly ❌
    """
    def create_edge(
        source_id: UUID,
        target_id: UUID,
        relation_type: str
    ) -> Edge:
        # Insert into edges table
        pass
```

---

## 🔬 Algorithmes d'Extraction

### Algorithm 1: Extract Function Calls (Python)

**Input**: Code chunk with Tree-sitter AST
**Output**: List of (caller, callee) pairs

**Strategy**:
1. Find all `call_expression` nodes in AST
2. Extract callee name (e.g., `my_function` or `obj.method`)
3. Determine calling context (which function contains this call?)
4. Return (caller_node_id, callee_name) pairs

**Example Code**:
```python
def extract_calls_python(chunk: CodeChunk) -> List[Tuple[str, str]]:
    """
    Extract function calls from Python code chunk.
    """
    calls = []

    # Get Tree-sitter AST
    tree = parse_chunk(chunk)
    root = tree.root_node

    # Find current function/method name (context)
    caller_name = extract_function_name(chunk)

    # Query all call expressions
    call_query = "(call function: (identifier) @callee)"
    captures = query_ast(root, call_query)

    for capture in captures:
        callee_name = capture.text.decode()
        calls.append((caller_name, callee_name))

    # Handle method calls: obj.method()
    method_call_query = """
    (call
      function: (attribute
        object: (identifier) @object
        attribute: (identifier) @method))
    """
    captures = query_ast(root, method_call_query)

    for capture in captures:
        method_name = f"{capture['object']}.{capture['method']}"
        calls.append((caller_name, method_name))

    return calls
```

**Challenges**:
- ✅ Tree-sitter parsing → Already have AST
- ❌ Name resolution → Need NameResolver
- ❌ Qualified names → Need context tracking

### Algorithm 2: Extract Imports (TypeScript/Python)

**Input**: Code chunk
**Output**: List of (importer, imported) pairs

**Strategy**:
1. Find all `import_statement` nodes
2. Extract imported names
3. Resolve to actual file/module
4. Return (importer_node_id, imported_node_id) pairs

**Example Code**:
```python
def extract_imports_typescript(chunk: CodeChunk) -> List[Tuple[str, str]]:
    """
    Extract imports from TypeScript code chunk.
    """
    imports = []
    tree = parse_chunk(chunk)

    # Query: import { X } from './module'
    import_query = """
    (import_statement
      (import_clause
        (named_imports
          (import_specifier name: (identifier) @name)))
      source: (string) @source)
    """

    captures = query_ast(tree.root_node, import_query)

    for capture in captures:
        imported_name = capture['name'].text.decode()
        source_module = capture['source'].text.decode().strip('"\'')
        imports.append((chunk.file_path, source_module, imported_name))

    return imports
```

### Algorithm 3: Extract Inheritance (OOP)

**Input**: Code chunk with class definition
**Output**: List of (child, parent) pairs

**Strategy**:
1. Find all `class_definition` nodes
2. Extract extends/implements clauses
3. Return (child_class_id, parent_class_name) pairs

**Example Code**:
```python
def extract_inheritance_typescript(chunk: CodeChunk) -> List[Tuple[str, str]]:
    """
    Extract class inheritance from TypeScript.
    """
    inheritance = []
    tree = parse_chunk(chunk)

    # Query: class Child extends Parent
    class_query = """
    (class_declaration
      name: (identifier) @child
      (class_heritage
        (extends_clause
          (identifier) @parent)))
    """

    captures = query_ast(tree.root_node, class_query)

    for capture in captures:
        child_name = capture['child'].text.decode()
        parent_name = capture['parent'].text.decode()
        inheritance.append((child_name, parent_name))

    # Query: class Impl implements Interface
    interface_query = """
    (class_declaration
      name: (identifier) @impl
      (class_heritage
        (implements_clause
          (type_identifier) @interface)))
    """

    captures = query_ast(tree.root_node, interface_query)

    for capture in captures:
        impl_name = capture['impl'].text.decode()
        interface_name = capture['interface'].text.decode()
        inheritance.append((impl_name, interface_name))

    return inheritance
```

---

## 📋 Plan d'Implémentation Étape par Étape

### Phase 1: Créer l'Infrastructure (1-2h)

#### Story 1.1: Créer GraphConstructionService
**File**: `api/services/graph_construction_service.py`

```python
"""
GraphConstructionService for EPIC-25 Story 25.5.

Builds complete code dependency graph with all relationships.
"""

from typing import List, Dict, Set, Optional, Tuple
from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)


class GraphConstructionService:
    """
    Constructs code dependency graph from indexed chunks.

    Pipeline:
    1. Get all code chunks for repository
    2. Create nodes (functions, classes, methods)
    3. Extract relations (calls, imports, inheritance)
    4. Resolve symbolic names to node IDs
    5. Create edges in database
    6. Return statistics
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.relation_extractor = RelationExtractor()
        self.name_resolver = NameResolver()

    async def build_graph_for_repository(
        self,
        repository: str,
        languages: Optional[List[str]] = None
    ) -> GraphStats:
        """
        Build complete graph for repository.

        Returns:
            GraphStats with construction metrics
        """
        logger.info(f"Building graph for repository: {repository}")

        # 1. Get all chunks
        chunks = await self._get_chunks(repository, languages)
        logger.info(f"Found {len(chunks)} chunks")

        # 2. Create nodes (if not exist)
        nodes = await self._create_nodes(chunks)
        logger.info(f"Created/found {len(nodes)} nodes")

        # 3. Build symbol table for name resolution
        symbol_table = self.name_resolver.build_symbol_table(chunks, nodes)
        logger.info(f"Built symbol table with {len(symbol_table)} entries")

        # 4. Extract relations
        relations = self.relation_extractor.extract_all_relations(chunks)
        logger.info(f"Extracted {len(relations)} raw relations")

        # 5. Resolve names and create edges
        edges_created = await self._create_edges(relations, symbol_table)
        logger.info(f"Created {edges_created} edges")

        # 6. Return statistics
        return await self._get_stats(repository)
```

**Dependencies**:
- RelationExtractor (to create)
- NameResolver (to create)
- Tree-sitter queries (already available)

#### Story 1.2: Créer RelationExtractor
**File**: `api/services/relation_extractor.py`

```python
"""
RelationExtractor - Extracts relationships from code chunks.
"""

from dataclasses import dataclass
from typing import List
from models.code_chunk_models import CodeChunk

@dataclass
class Relation:
    """Raw relation before name resolution."""
    source_name: str  # Symbolic name (e.g., "MyClass.method")
    target_name: str  # Symbolic name (e.g., "other_function")
    relation_type: str  # "calls", "imports", "extends", "implements"
    source_chunk_id: str
    target_hint: Optional[str] = None  # File path or module hint


class RelationExtractor:
    """Extracts relationships from code chunks."""

    def extract_all_relations(self, chunks: List[CodeChunk]) -> List[Relation]:
        """Extract all types of relations."""
        relations = []

        for chunk in chunks:
            if chunk.language == "python":
                relations.extend(self._extract_python(chunk))
            elif chunk.language in ["typescript", "tsx", "javascript"]:
                relations.extend(self._extract_typescript(chunk))

        return relations

    def _extract_python(self, chunk: CodeChunk) -> List[Relation]:
        """Extract Python relations."""
        relations = []

        # Extract function calls
        relations.extend(self._extract_python_calls(chunk))

        # Extract imports
        relations.extend(self._extract_python_imports(chunk))

        # Extract class inheritance
        relations.extend(self._extract_python_inheritance(chunk))

        return relations

    def _extract_python_calls(self, chunk: CodeChunk) -> List[Relation]:
        """Extract function calls from Python code."""
        # Use Tree-sitter queries
        # Implementation in next phase
        pass
```

#### Story 1.3: Créer NameResolver
**File**: `api/services/name_resolver.py`

```python
"""
NameResolver - Resolves symbolic names to node IDs.
"""

from typing import Dict, Optional
from uuid import UUID

class SymbolTable:
    """Symbol table for name resolution."""

    def __init__(self):
        self._exact_matches: Dict[str, UUID] = {}  # "module.Class.method" -> node_id
        self._fuzzy_matches: Dict[str, List[UUID]] = {}  # "method" -> [possible node_ids]

    def add_symbol(self, full_name: str, node_id: UUID):
        """Add symbol to table."""
        self._exact_matches[full_name] = node_id

        # Also index by simple name for fuzzy matching
        simple_name = full_name.split('.')[-1]
        if simple_name not in self._fuzzy_matches:
            self._fuzzy_matches[simple_name] = []
        self._fuzzy_matches[simple_name].append(node_id)

    def resolve_exact(self, name: str) -> Optional[UUID]:
        """Resolve exact match."""
        return self._exact_matches.get(name)

    def resolve_fuzzy(self, name: str) -> List[UUID]:
        """Resolve fuzzy match (may return multiple)."""
        return self._fuzzy_matches.get(name, [])


class NameResolver:
    """Resolves symbolic names to node IDs."""

    def build_symbol_table(
        self,
        chunks: List[CodeChunk],
        nodes: List[Node]
    ) -> SymbolTable:
        """
        Build symbol table from chunks and nodes.

        Strategy:
        1. For each node, construct its fully qualified name
        2. Index by: module.Class.method, Class.method, method
        3. Handle aliasing and imports
        """
        table = SymbolTable()

        for node in nodes:
            # Construct fully qualified name
            full_name = self._construct_fqn(node)
            table.add_symbol(full_name, node.node_id)

        return table

    def _construct_fqn(self, node: Node) -> str:
        """Construct fully qualified name for node."""
        parts = []

        # Add file path (as module)
        if 'file_path' in node.properties:
            file_path = node.properties['file_path']
            module = file_path.replace('/', '.').replace('.py', '').replace('.ts', '')
            parts.append(module)

        # Add class name (if method)
        if node.node_type == 'method' and 'class_name' in node.properties:
            parts.append(node.properties['class_name'])

        # Add function/method name
        parts.append(node.properties.get('name', ''))

        return '.'.join(parts)
```

### Phase 2: Implémenter Extraction des Relations (3-4h)

#### Story 2.1: Python Function Calls
**Tree-sitter queries**:
```python
# Query: Simple function call
PYTHON_CALL_QUERY = """
(call
  function: (identifier) @function_name)
"""

# Query: Method call
PYTHON_METHOD_CALL_QUERY = """
(call
  function: (attribute
    object: (identifier) @object
    attribute: (identifier) @method))
"""
```

#### Story 2.2: Python Imports
```python
# Query: from X import Y
PYTHON_IMPORT_FROM_QUERY = """
(import_from_statement
  module_name: (dotted_name) @module
  (dotted_name) @imported_name)
"""

# Query: import X
PYTHON_IMPORT_QUERY = """
(import_statement
  (dotted_name) @module)
"""
```

#### Story 2.3: TypeScript Function Calls
```typescript
// Query: Function call
TYPESCRIPT_CALL_QUERY = """
(call_expression
  function: (identifier) @function_name)
"""

// Query: Method call
TYPESCRIPT_METHOD_CALL_QUERY = """
(call_expression
  function: (member_expression
    object: (identifier) @object
    property: (property_identifier) @method))
"""
```

#### Story 2.4: TypeScript Imports
```typescript
// Query: import { X } from 'Y'
TYPESCRIPT_IMPORT_QUERY = """
(import_statement
  (import_clause
    (named_imports
      (import_specifier
        name: (identifier) @imported_name)))
  source: (string) @source_module)
"""
```

#### Story 2.5: Class Inheritance (Python & TypeScript)
```python
# Python: class Child(Parent)
PYTHON_INHERITANCE_QUERY = """
(class_definition
  name: (identifier) @child_class
  bases: (argument_list
    (identifier) @parent_class))
"""

# TypeScript: class Child extends Parent
TYPESCRIPT_EXTENDS_QUERY = """
(class_declaration
  name: (identifier) @child_class
  (class_heritage
    (extends_clause
      (identifier) @parent_class)))
"""
```

### Phase 3: Résolution des Noms (2-3h)

#### Story 3.1: Stratégie de Résolution

**Priority Order**:
1. **Exact match** (fully qualified name)
2. **Same file match** (same file_path)
3. **Same class match** (for methods)
4. **Import match** (imported from same module)
5. **Fuzzy match** (name match only - least reliable)

**Example**:
```python
# Code: MyClass.my_method() calls helper_function()

# Symbol table:
{
  "src.models.MyClass.my_method": UUID_A,
  "src.utils.helper_function": UUID_B,
  "src.models.helper_function": UUID_C
}

# Resolution for "helper_function" call:
# 1. Exact match? No ("helper_function" vs "src.utils.helper_function")
# 2. Same file? Check if there's a helper_function in src/models.py
#    → Found UUID_C ✅
# 3. Return UUID_C
```

#### Story 3.2: Handle Imports for Resolution

```python
# Track imports per file
imports_map = {
  "src/models.py": {
    "helper_function": "src/utils.py"  # from utils import helper_function
  }
}

# When resolving "helper_function" in src/models.py:
# 1. Check imports_map → points to src/utils.py
# 2. Look up "src.utils.helper_function" in symbol table
# 3. Return UUID_B ✅
```

### Phase 4: Tests de Validation (2h)

#### Test 1: Simple Function Call
```python
# Code:
def caller():
    callee()

def callee():
    pass

# Expected:
# - 2 nodes (caller, callee)
# - 1 edge (caller --calls--> callee)
```

#### Test 2: Method Call
```python
# Code:
class MyClass:
    def method_a(self):
        self.method_b()

    def method_b(self):
        pass

# Expected:
# - 1 node (class MyClass)
# - 2 nodes (method_a, method_b)
# - 1 edge (method_a --calls--> method_b)
```

#### Test 3: Import Relationship
```python
# File: module_a.py
from module_b import my_function

def use_import():
    my_function()

# File: module_b.py
def my_function():
    pass

# Expected:
# - 2 nodes (use_import, my_function)
# - 1 edge (module_a --imports--> module_b)
# - 1 edge (use_import --calls--> my_function)
```

#### Test 4: Class Inheritance
```python
# Code:
class Parent:
    pass

class Child(Parent):
    pass

# Expected:
# - 2 nodes (Parent, Child)
# - 1 edge (Child --extends--> Parent)
```

---

## 🎯 Validation Metrics

### Success Criteria

After implementation, run on CVGenerator (code_test):
- **Current**: 2,058 nodes, 11 edges (0.5%)
- **Target**: 2,058 nodes, 1,000+ edges (50%+)

**Breakdown**:
- Function calls: 600-800 edges (most common)
- Imports: 200-300 edges
- Inheritance: 50-100 edges
- Method overrides: 50-100 edges

### Validation Queries

```sql
-- Check edge distribution
SELECT relation_type, COUNT(*) as count
FROM edges e
JOIN nodes n ON e.source_node_id = n.node_id
WHERE n.properties->>'repository' = 'CVGenerator'
GROUP BY relation_type;

-- Expected output:
-- calls      | 700
-- imports    | 250
-- extends    | 80
-- implements | 50
```

### Visual Validation

After rebuild, the graph UI should show:
- ✅ Nodes with multiple connections
- ✅ Visible arrows between related nodes
- ✅ Clear hierarchies (classes → methods → callees)

---

## 🚀 Execution Plan

### Sprint Breakdown (Total: 8-11h)

**Day 1** (4h):
- ✅ Phase 1.1: Create GraphConstructionService skeleton
- ✅ Phase 1.2: Create RelationExtractor skeleton
- ✅ Phase 1.3: Create NameResolver skeleton
- ✅ Wire everything together

**Day 2** (4h):
- ✅ Phase 2.1-2.2: Implement Python extraction
- ✅ Phase 2.3-2.4: Implement TypeScript extraction
- ✅ Test extraction on sample files

**Day 3** (3h):
- ✅ Phase 3.1-3.2: Implement name resolution
- ✅ Phase 4: Write validation tests
- ✅ Run on CVGenerator and validate metrics
- ✅ Debug and fix issues

### Next Steps

1. **Review this document** - Validate approach
2. **Implement Phase 1** - Create service skeleton
3. **Test incrementally** - Validate each phase
4. **Iterate** - Refine based on real data

---

## 📚 References

- Tree-sitter Python grammar: https://github.com/tree-sitter/tree-sitter-python
- Tree-sitter TypeScript grammar: https://github.com/tree-sitter/tree-sitter-typescript
- Existing code chunking service: `services/code_chunking_service.py`
- Database schema: `db/schema.sql` (nodes and edges tables)

---

**Status**: READY FOR IMPLEMENTATION
**Estimated Time**: 8-11 hours
**Risk Level**: Medium (name resolution is complex)
**Blockers**: None - all dependencies exist
