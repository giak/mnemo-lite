# EPIC-06 Story 3: Code Metadata Extraction - Brainstorm

**Date**: 2025-10-16
**Version**: 1.0.0
**Story Points**: 8
**Estimation**: 3-5 jours

---

## 🎯 Objectif Story 3

**User Story**:
> En tant qu'agent IA, je veux des **métadonnées riches** sur chaque chunk de code, afin de **filtrer/scorer intelligemment** (ex: "fonctions avec >5 paramètres", "code complexe", "fonctions appelées fréquemment").

**Contexte**:
- Phase 1 Stories 1 & 2bis: ✅ DONE (Chunking AST + Repository)
- Nous avons déjà: `code_chunks` table avec `metadata JSONB`
- Nous avons déjà: Tree-sitter parsing (Python)
- Story 3 = **enrichir** le metadata JSONB avec informations code-specific

---

## 📊 Métadonnées Cibles (Spécification)

### Métadonnées Définies (EPIC-06_Code_Intelligence.md)

```json
{
  "language": "python",
  "chunk_type": "function",
  "name": "calculate_total",
  "signature": "calculate_total(items: List[Item]) -> float",
  "parameters": ["items"],
  "returns": "float",
  "docstring": "Calculate total price from items list",
  "complexity": {
    "cyclomatic": 3,
    "lines_of_code": 12,
    "cognitive": 5
  },
  "imports": ["typing.List", "models.Item"],
  "calls": ["item.get_price", "sum"],
  "decorators": ["@staticmethod"],
  "has_tests": true,
  "test_files": ["tests/test_calculations.py"],
  "last_modified": "2025-10-15T10:30:00Z",
  "author": "john.doe",
  "usage_frequency": 42
}
```

---

## 🔍 Analyse: Métadonnées par Catégorie

### Catégorie 1: Identité Code (FACILE)
**Déjà disponibles via Story 1**:
- ✅ `language`: Via CodeChunkingService
- ✅ `chunk_type`: Via Tree-sitter (function, class, method)
- ✅ `name`: Via Tree-sitter node extraction

**Status**: ✅ DÉJÀ IMPLÉMENTÉ

---

### Catégorie 2: Signature & Types (MOYEN)

| Métadonnée | Difficulté | Outil | Notes |
|------------|-----------|-------|-------|
| `signature` | 🟡 Moyen | `ast.get_source_segment()` | Full signature string |
| `parameters` | 🟢 Facile | `ast` FunctionDef.args | List of param names |
| `returns` | 🟡 Moyen | `ast` FunctionDef.returns | Type annotation si présente |
| `decorators` | 🟢 Facile | `ast` FunctionDef.decorator_list | List decorator names |

**Python AST Nodes**:
```python
import ast

def extract_signature_metadata(node: ast.FunctionDef) -> dict:
    return {
        "signature": ast.get_source_segment(source_code, node),
        "parameters": [arg.arg for arg in node.args.args],
        "returns": ast.unparse(node.returns) if node.returns else None,
        "decorators": [ast.unparse(dec) for dec in node.decorator_list],
    }
```

**Complexité**: 🟢 **FAIBLE** (stdlib `ast` suffit)

---

### Catégorie 3: Documentation (FACILE)

| Métadonnée | Difficulté | Outil | Notes |
|------------|-----------|-------|-------|
| `docstring` | 🟢 Facile | `ast.get_docstring()` | First string literal in function body |

**Python AST**:
```python
docstring = ast.get_docstring(node)  # Returns None si absent
```

**Parsing Docstring Styles**:
- Google Style: `Args:`, `Returns:`, `Raises:`
- NumPy Style: `Parameters`, `Returns`
- Sphinx Style: `:param:`, `:returns:`

**Question**: Parser le docstring ou garder brut?

**Options**:
1. **Brut (string)** ⭐ RECOMMANDÉ Phase 1
   - Simple, pas de dépendances
   - Parsing possible en post-traitement

2. **Parsé (structured)**
   - Lib: `docstring-parser` (pypi)
   - Avantage: structured params/returns
   - Inconvénient: dépendance externe, parsing errors

**Recommandation**: Garder **brut** Phase 1, parser en Phase 2 si nécessaire.

---

### Catégorie 4: Complexité (MOYEN)

| Métadonnée | Difficulté | Outil | Notes |
|------------|-----------|-------|-------|
| `cyclomatic` | 🟡 Moyen | `radon` | Cyclomatic Complexity (McCabe) |
| `lines_of_code` | 🟢 Facile | `len(source.split('\n'))` | Simple line count |
| `cognitive` | 🟠 Difficile | `radon` (cognitive complexity) | Introduced radon 6.0+ |

**Radon Library**:
```bash
pip install radon==6.0.1
```

```python
from radon.complexity import cc_visit
from radon.metrics import mi_visit

# Cyclomatic Complexity
complexities = cc_visit(source_code)
for cc in complexities:
    print(f"{cc.name}: {cc.complexity}")  # cyclomatic

# Maintainability Index (alternative)
mi = mi_visit(source_code, multi=True)
```

**Radon Outputs**:
- Cyclomatic Complexity: 1-10 (simple), 11-20 (complex), 21+ (very complex)
- Cognitive Complexity: Similar scale, mais focus lisibilité humaine

**Question**: Inclure Maintainability Index (MI)?
- MI = index 0-100 (0 = unmaintainable, 100 = parfait)
- Formule: MI = max(0, (171 - 5.2*ln(V) - 0.23*G - 16.2*ln(LOC)) * 100 / 171)
- V = Halstead Volume, G = Cyclomatic, LOC = Lines of Code

**Recommandation**:
- ✅ `cyclomatic`: MUST-HAVE (standard industry)
- ✅ `lines_of_code`: MUST-HAVE (facile)
- ⚠️ `cognitive`: NICE-TO-HAVE si radon 6.0+ (check version)
- ⚠️ `maintainability_index`: NICE-TO-HAVE (utile pour scoring qualité)

---

### Catégorie 5: Dépendances Code (DIFFICILE)

| Métadonnée | Difficulté | Outil | Notes |
|------------|-----------|-------|-------|
| `imports` | 🟡 Moyen | `ast` ImportFrom, Import | Imports utilisés dans chunk |
| `calls` | 🟠 Difficile | `ast` Call nodes | Fonctions appelées |
| `usage_frequency` | 🔴 Très Difficile | Static analysis global | Combien de fois fonction appelée |

#### 5.1 Imports Extraction

**Python AST**:
```python
def extract_imports(node: ast.FunctionDef, tree: ast.AST) -> list[str]:
    """Extract imports used within function."""
    imports = []

    # Get all Import and ImportFrom nodes in module
    for module_node in ast.walk(tree):
        if isinstance(module_node, ast.Import):
            for alias in module_node.names:
                imports.append(alias.name)
        elif isinstance(module_node, ast.ImportFrom):
            module = module_node.module or ""
            for alias in module_node.names:
                imports.append(f"{module}.{alias.name}")

    # Filter: keep only imports referenced in function
    function_names = {node.id for node in ast.walk(node) if isinstance(node, ast.Name)}
    return [imp for imp in imports if imp.split('.')[-1] in function_names]
```

**Complexité**: 🟡 **MOYEN** (require traversal module-level + function-level)

#### 5.2 Calls Extraction

**Python AST**:
```python
def extract_calls(node: ast.FunctionDef) -> list[str]:
    """Extract function calls within function."""
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)  # Simple call: foo()
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)  # Method call: obj.foo()
    return list(set(calls))  # Deduplicate
```

**Complexité**: 🟡 **MOYEN** (AST traversal simple)

**Limitations**:
- Ne capture pas les appels indirects (via variables, lambdas)
- Ne résout pas les imports (ex: `from foo import bar; bar()` → capture "bar", pas "foo.bar")

#### 5.3 Usage Frequency (⚠️ HORS SCOPE Phase 1)

**Problème**: Nécessite analyse **globale** de la codebase:
- Parser TOUS les fichiers du projet
- Construire call graph complet
- Compter références à chaque fonction

**Options**:
1. **Analyse statique complète** (Story 4: Dependency Graph)
   - Construire call graph via AST
   - Compter in-edges vers chaque fonction
   - Stocker dans `edges` table

2. **Heuristique simple** (Phase 1)
   - Grep codebase pour nom fonction
   - Count occurrences (approximation)

3. **Reporter à Story 4** ⭐ RECOMMANDÉ
   - `usage_frequency` = extension naturelle de Story 4 (call graph)
   - Phase 1: Laisser `null` ou `0`

**Recommandation**: ❌ **HORS SCOPE Story 3**, déplacer vers Story 4.

---

### Catégorie 6: Tests (DIFFICILE)

| Métadonnée | Difficulté | Outil | Notes |
|------------|-----------|-------|-------|
| `has_tests` | 🟠 Difficile | Heuristique fichiers | Chercher `test_*.py` ou `*_test.py` |
| `test_files` | 🟠 Difficile | Pattern matching | Liste fichiers tests référençant fonction |

**Heuristiques**:

1. **Convention Naming**:
   - Fonction: `calculate_total` dans `src/utils/calc.py`
   - Test probable: `tests/test_calc.py` ou `tests/utils/test_calc.py`

2. **Grep Test Files**:
```python
import glob

def find_test_files(function_name: str, repo_path: str) -> list[str]:
    test_files = []
    test_patterns = [
        f"{repo_path}/tests/**/test_*.py",
        f"{repo_path}/**/tests/*_test.py",
    ]

    for pattern in test_patterns:
        for file in glob.glob(pattern, recursive=True):
            with open(file) as f:
                if function_name in f.read():
                    test_files.append(file)

    return test_files
```

**Complexité**: 🟠 **DIFFICILE** (I/O intensif, require repo access)

**Question**: Repository path disponible?
- `code_chunks.repository` = nom du repo (string)
- Pas de path absolu stocké
- Nécessite configuration `REPOSITORY_BASE_PATH` ou similaire

**Recommandation**:
- ✅ `has_tests`: NICE-TO-HAVE (booléen simple)
- ⚠️ `test_files`: OPTIONAL (liste paths, I/O coûteux)
- Alternative: Reporter extraction tests à **phase d'indexation** (Story 6), pas runtime

---

### Catégorie 7: Git Metadata (FACILE SI DISPONIBLE)

| Métadonnée | Difficulté | Outil | Notes |
|------------|-----------|-------|-------|
| `last_modified` | 🟢 Facile | `git log` | Timestamp dernier commit touchant fichier |
| `author` | 🟢 Facile | `git log` | Auteur dernier commit |

**Git Commands**:
```python
import subprocess

def get_git_metadata(file_path: str) -> dict:
    # Last modified timestamp
    result = subprocess.run(
        ["git", "log", "-1", "--format=%aI", "--", file_path],
        capture_output=True, text=True
    )
    last_modified = result.stdout.strip()

    # Author
    result = subprocess.run(
        ["git", "log", "-1", "--format=%an", "--", file_path],
        capture_output=True, text=True
    )
    author = result.stdout.strip()

    return {"last_modified": last_modified, "author": author}
```

**Complexité**: 🟢 **FACILE** (git commands simples)

**Question**: Git repo accessible lors de l'indexation?
- Phase 1 Story 3: Probablement **NON** (chunk extraction isolée)
- Phase 4 Story 6: **OUI** (indexing pipeline avec repo clone)

**Recommandation**: ⚠️ **REPORTER Story 6** (indexing pipeline)

---

## 🎯 Scope Story 3: MVP vs Full

### Proposition Scope MVP (Phase 1)

#### ✅ MUST-HAVE (Core Story 3)

| Métadonnée | Outil | Justification |
|------------|-------|---------------|
| `signature` | `ast` | Identité fonction critique |
| `parameters` | `ast` | Filtrage "fonctions avec N params" |
| `returns` | `ast` | Type hints utiles |
| `decorators` | `ast` | Filtrage "@staticmethod", "@cached" |
| `docstring` | `ast.get_docstring()` | Documentation présence |
| `cyclomatic` | `radon` | Complexité standard |
| `lines_of_code` | `len()` | Métrique base |
| `imports` | `ast` | Dépendances module |
| `calls` | `ast` | Fonctions utilisées |

**Total**: **9 métadonnées** (toutes extraites via `ast` + `radon`)

#### ⚠️ NICE-TO-HAVE (Phase 1 optionnel)

| Métadonnée | Outil | Raison optionnel |
|------------|-------|------------------|
| `cognitive` | `radon` | Dépend version radon 6.0+ |
| `maintainability_index` | `radon` | Métrique bonus |
| `has_tests` | Heuristique | I/O coûteux, besoin repo path |

#### ❌ HORS SCOPE Story 3 (Reporter)

| Métadonnée | Story Future | Raison |
|------------|--------------|--------|
| `usage_frequency` | **Story 4** | Require call graph global |
| `test_files` | **Story 6** | Require indexing pipeline |
| `last_modified` | **Story 6** | Require git access |
| `author` | **Story 6** | Require git access |

---

## 🏗️ Architecture Proposée

### 1. Service: MetadataExtractorService

```python
# api/services/metadata_extractor_service.py

import ast
from typing import Optional
from radon.complexity import cc_visit

class MetadataExtractorService:
    """
    Extract code metadata from AST nodes.

    Supports:
    - Signature, parameters, returns, decorators
    - Docstrings
    - Complexity metrics (cyclomatic, LOC)
    - Imports and calls
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def extract_metadata(
        self,
        source_code: str,
        node: ast.FunctionDef,  # or ClassDef
        tree: ast.AST,
        language: str = "python"
    ) -> dict:
        """
        Extract metadata from AST node.

        Args:
            source_code: Full source code (for radon)
            node: AST node (FunctionDef, ClassDef)
            tree: Full AST tree (for imports)
            language: Programming language

        Returns:
            Metadata dict matching schema
        """
        if language != "python":
            # Fallback: basic metadata only
            return self._extract_basic_metadata(node)

        metadata = {}

        # Category 2: Signature & Types
        metadata.update(self._extract_signature(node, source_code))

        # Category 3: Documentation
        metadata["docstring"] = ast.get_docstring(node)

        # Category 4: Complexity
        metadata.update(self._extract_complexity(source_code, node))

        # Category 5: Dependencies
        metadata["imports"] = self._extract_imports(node, tree)
        metadata["calls"] = self._extract_calls(node)

        return metadata

    def _extract_signature(self, node: ast.FunctionDef, source_code: str) -> dict:
        """Extract signature, parameters, returns, decorators."""
        return {
            "signature": ast.get_source_segment(source_code, node),
            "parameters": [arg.arg for arg in node.args.args],
            "returns": ast.unparse(node.returns) if node.returns else None,
            "decorators": [ast.unparse(dec) for dec in node.decorator_list],
        }

    def _extract_complexity(self, source_code: str, node: ast.FunctionDef) -> dict:
        """Extract complexity metrics via radon."""
        # Radon requires full source (can't analyze single node)
        # Extract node source for radon
        node_source = ast.get_source_segment(source_code, node)

        try:
            complexities = cc_visit(node_source)
            if complexities:
                cc = complexities[0]
                return {
                    "complexity": {
                        "cyclomatic": cc.complexity,
                        "lines_of_code": len(node_source.split('\n')),
                    }
                }
        except Exception as e:
            self.logger.warning(f"Radon complexity extraction failed: {e}")

        # Fallback
        return {
            "complexity": {
                "cyclomatic": None,
                "lines_of_code": len(ast.get_source_segment(source_code, node).split('\n')),
            }
        }

    def _extract_imports(self, node: ast.FunctionDef, tree: ast.AST) -> list[str]:
        """Extract imports used in function."""
        # Implementation as shown above
        pass

    def _extract_calls(self, node: ast.FunctionDef) -> list[str]:
        """Extract function calls."""
        # Implementation as shown above
        pass

    def _extract_basic_metadata(self, node) -> dict:
        """Fallback for non-Python languages."""
        return {
            "signature": None,
            "parameters": [],
            "returns": None,
            "decorators": [],
            "docstring": None,
            "complexity": {"cyclomatic": None, "lines_of_code": None},
            "imports": [],
            "calls": [],
        }
```

---

### 2. Intégration avec CodeChunkingService

**Option A: Enrichir après chunking** ⭐ RECOMMANDÉ

```python
# api/services/code_chunking_service.py

class CodeChunkingService:
    def __init__(self, max_workers: int = 4):
        self._parsers = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._metadata_extractor = MetadataExtractorService()  # NEW

    async def chunk_code(
        self,
        source_code: str,
        language: str,
        file_path: str = "<unknown>",
        extract_metadata: bool = True,  # NEW parameter
        max_chunk_size: int = 2000,
        min_chunk_size: int = 100
    ) -> list[CodeChunk]:
        """Chunk code with optional metadata extraction."""

        # ... existing chunking logic ...

        # NEW: Enrich chunks with metadata
        if extract_metadata:
            tree = parser.parse(source_code)
            for chunk in chunks:
                if chunk.chunk_type in [ChunkType.FUNCTION, ChunkType.CLASS, ChunkType.METHOD]:
                    # Find corresponding AST node
                    node = self._find_node_for_chunk(chunk, tree)
                    if node:
                        metadata = await self._metadata_extractor.extract_metadata(
                            source_code, node, tree, language
                        )
                        chunk.metadata.update(metadata)

        return chunks
```

**Avantages**:
- ✅ Séparation concerns (chunking vs metadata)
- ✅ Metadata extraction optionnelle (performance)
- ✅ Facile tester séparément

**Option B: Extraction inline pendant chunking**

Moins modulaire, couplage fort. ❌ Pas recommandé.

---

### 3. Stockage Metadata JSONB

**Schema code_chunks.metadata**:

```json
{
  // Metadata from Story 3
  "signature": "calculate_total(items: List[Item]) -> float",
  "parameters": ["items"],
  "returns": "float",
  "decorators": ["@staticmethod"],
  "docstring": "Calculate total price from items list",
  "complexity": {
    "cyclomatic": 3,
    "lines_of_code": 12
  },
  "imports": ["typing.List", "models.Item"],
  "calls": ["item.get_price", "sum"],

  // Future metadata (Story 6)
  "has_tests": true,
  "last_modified": "2025-10-15T10:30:00Z",
  "author": "john.doe"
}
```

**GIN Index** (déjà créé Story 2bis):
```sql
CREATE INDEX idx_code_metadata ON code_chunks USING gin (metadata jsonb_path_ops);
```

**Queries supportées**:
```sql
-- Fonctions avec >5 params
SELECT * FROM code_chunks WHERE jsonb_array_length(metadata->'parameters') > 5;

-- Fonctions complexes (cyclomatic > 10)
SELECT * FROM code_chunks WHERE (metadata->'complexity'->>'cyclomatic')::int > 10;

-- Fonctions avec decorator spécifique
SELECT * FROM code_chunks WHERE metadata->'decorators' ? '@cached_property';
```

---

## 🧪 Tests Stratégie

### Test Cases

**Unit Tests (MetadataExtractorService)**:

1. ✅ `test_extract_signature_simple_function`
2. ✅ `test_extract_signature_with_type_hints`
3. ✅ `test_extract_parameters_multiple`
4. ✅ `test_extract_returns_type_hint`
5. ✅ `test_extract_decorators_multiple`
6. ✅ `test_extract_docstring_google_style`
7. ✅ `test_extract_docstring_none`
8. ✅ `test_extract_complexity_cyclomatic`
9. ✅ `test_extract_complexity_lines_of_code`
10. ✅ `test_extract_imports_used_in_function`
11. ✅ `test_extract_calls_simple`
12. ✅ `test_extract_calls_method_calls`

**Integration Tests (CodeChunkingService + Metadata)**:

1. ✅ `test_chunk_with_metadata_extraction`
2. ✅ `test_metadata_stored_in_chunk_model`
3. ✅ `test_metadata_optional_parameter`

**Total**: ~15 tests

---

## ⚡ Performance Considérations

### Bottlenecks Potentiels

1. **Radon Complexity**:
   - Radon parse AST à nouveau (duplication avec tree-sitter?)
   - Peut être lent sur large functions
   - Mitigation: Cache radon results, ou skip si chunk > threshold

2. **Import Resolution**:
   - Require module-level AST traversal
   - O(n) où n = nb imports module
   - Mitigation: Une seule traversal, cache imports

3. **Metadata Extraction par Chunk**:
   - Si 100 functions → 100 metadata extractions
   - Mitigation: Parallel extraction (ThreadPoolExecutor)

### Performance Target

- **<50ms** per function metadata extraction
- **<5s** for 100 functions (with parallelization)

---

## 🔄 Extensibilité Future

### JavaScript/TypeScript (Phase 2)

**Défis**:
- Pas de `ast` stdlib (Python-specific)
- Tree-sitter queries plus complexes
- Type annotations optionnelles (TypeScript)

**Approche**:
1. Create `JavaScriptMetadataExtractor` subclass
2. Use Tree-sitter queries for signature/params
3. Parse JSDoc comments for docstrings
4. Use `eslint` complexity plugin ou `plato` pour complexity

**Estimation**: +3-5 jours (Phase 2)

---

## 🎯 Décisions Clés à Prendre

### Décision 1: Scope Metadata Phase 1

**Options**:
- **A**: MVP (9 métadonnées core) ⭐ RECOMMANDÉ
- **B**: Full (inclure `has_tests`, `cognitive`, etc.)
- **C**: Minimal (5 métadonnées: signature, params, docstring, cyclomatic, LOC)

**Recommandation**: **Option A (MVP)** - équilibre fonctionnalité/complexité

---

### Décision 2: Radon Dependency

**Question**: Ajouter `radon` comme dépendance?

**Options**:
- **A**: Oui, utiliser `radon` ⭐ RECOMMANDÉ
  - Avantage: Complexity standard (McCabe)
  - Inconvénient: Dépendance externe

- **B**: Implémenter cyclomatic complexity manuellement
  - Avantage: Pas de dépendance
  - Inconvénient: Complexe, reinventing wheel

**Recommandation**: **Option A** - `radon` est lightweight, well-maintained

---

### Décision 3: Metadata Extraction Timing

**Options**:
- **A**: Pendant chunking (CodeChunkingService.chunk_code) ⭐ RECOMMANDÉ
- **B**: Après chunking (séparé, via MetadataEnrichmentService)
- **C**: Lors de l'insertion DB (CodeChunkRepository.add)

**Recommandation**: **Option A** - plus logique, tree/node déjà disponibles

---

### Décision 4: Error Handling Metadata

**Question**: Que faire si metadata extraction échoue?

**Options**:
- **A**: Continue avec metadata partielle (log warning) ⭐ RECOMMANDÉ
- **B**: Fail chunk creation (raise exception)
- **C**: Retry avec fallback basic metadata

**Recommandation**: **Option A** - robustesse, chunk créé même si metadata partielle

---

## 📋 Story 3 Implementation Plan

### Phase 1: Core Metadata Extraction (2 jours)

**Jour 1**:
1. ✅ Create `MetadataExtractorService`
2. ✅ Implement signature/params/returns/decorators extraction
3. ✅ Implement docstring extraction
4. ✅ Unit tests (8 tests)

**Jour 2**:
1. ✅ Install `radon`, implement complexity extraction
2. ✅ Implement imports/calls extraction
3. ✅ Unit tests (4 tests)
4. ✅ Integration avec CodeChunkingService

### Phase 2: Integration & Tests (1 jour)

**Jour 3**:
1. ✅ Add `extract_metadata` parameter to `chunk_code()`
2. ✅ Update CodeChunkCreate model si nécessaire
3. ✅ Integration tests (3 tests)
4. ✅ End-to-end test (chunking + metadata + repository)

### Phase 3: Validation & Documentation (0.5 jour)

**Jour 3 PM**:
1. ✅ Audit metadata extraction sur fichiers réels
2. ✅ Update EPIC-06_Code_Intelligence.md (Story 3 complete)
3. ✅ Create ADR si décisions techniques majeures
4. ✅ Update requirements.txt (radon)

**Total**: **3-3.5 jours** (dans budget 3-5 jours)

---

## 🚀 Prochaines Étapes

### Avant de Coder

1. **Valider scope** avec stakeholder (toi!)
   - MVP 9 métadonnées OK?
   - Reporter tests/git metadata à Story 6 OK?

2. **Valider architecture**
   - MetadataExtractorService séparé OK?
   - Intégration dans CodeChunkingService OK?

3. **Installer radon**
   ```bash
   docker exec mnemo-api pip install radon==6.0.1
   ```

### Démarrer Implementation

1. Create `api/services/metadata_extractor_service.py`
2. Create `tests/services/test_metadata_extractor_service.py`
3. Implement + test itérativement (TDD)
4. Integrate with CodeChunkingService
5. Integration tests
6. Validation sur fichiers réels

---

## 📝 Questions Ouvertes

### Question 1: Docstring Parsing
Parser docstrings en structured format (Google/NumPy) ou garder brut?
- **Recommandation**: Brut Phase 1, parser Phase 2 si nécessaire

### Question 2: Radon Version
Quelle version radon? 6.0.1 (latest) ou 5.x (stable)?
- **Recommandation**: 6.0.1 (cognitive complexity support)

### Question 3: Import Resolution Depth
Résoudre imports qualifiés (ex: `from typing import List` → "typing.List")?
- **Recommandation**: Oui, mais sans résolution cross-file (trop complexe Phase 1)

### Question 4: Metadata Schema Validation
Valider metadata schema avec Pydantic model?
- **Recommandation**: Non Phase 1 (JSONB flexible), considérer Phase 2

---

## 🎓 Lessons from Stories 1 & 2bis

### Ce qui a bien fonctionné ✅
1. **Brainstorm avant implémentation** (évite refactoring)
2. **Tests first** (TDD simplifie debugging)
3. **Audit rigoureux** (6 issues fixées Story 2bis)
4. **Documentation continue** (ADRs à chaque décision)

### À appliquer Story 3 ✅
1. **Scope clair MVP** (9 métadonnées, pas plus)
2. **Tests unitaires complets** (15 tests minimum)
3. **Audit après implémentation** (vérifier robustesse)
4. **ADR si décisions techniques** (radon, scope, etc.)

---

## 📊 Success Criteria Story 3

### ✅ Definition of Done

1. **Fonctionnel**:
   - ✅ 9 métadonnées extraites (signature, params, returns, decorators, docstring, cyclomatic, LOC, imports, calls)
   - ✅ Metadata stockée dans code_chunks.metadata JSONB
   - ✅ Integration avec CodeChunkingService

2. **Tests**:
   - ✅ 12 unit tests passing (MetadataExtractorService)
   - ✅ 3 integration tests passing (CodeChunkingService)
   - ✅ Coverage >85% nouveaux modules

3. **Performance**:
   - ✅ <50ms per function metadata extraction
   - ✅ <5s for 100 functions (parallelized)

4. **Documentation**:
   - ✅ EPIC-06_Code_Intelligence.md updated (Story 3 complete)
   - ✅ ADR créée si décisions majeures
   - ✅ requirements.txt updated (radon)

---

**Status**: 🚧 **BRAINSTORM COMPLET** - Ready to implement!
**Next**: Valider scope & architecture, puis start coding 🚀

**Auteur**: Claude (AI Assistant)
**Date**: 2025-10-16
**Version**: 1.0.0
