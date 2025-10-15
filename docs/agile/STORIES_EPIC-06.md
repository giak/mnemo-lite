# User Stories - EPIC-06: Code Intelligence

**Epic**: [EPIC-06_Code_Intelligence.md](EPIC-06_Code_Intelligence.md)
**Version MnemoLite**: v1.4.0+
**Date Création**: 2025-10-15

---

## Story 1: Tree-sitter Integration & AST Chunking

### US-06-1: Semantic Code Chunking via Abstract Syntax Tree

**Priority**: 🔴 HAUTE
**Story Points**: 13
**Complexité**: HAUTE
**Dépendances**: Aucune

#### Description

**En tant que** développeur agent IA utilisant MnemoLite,
**Je veux** que le code soit découpé en chunks sémantiques respectant les limites de fonctions/classes/méthodes,
**Afin de** rechercher du code sans couper arbitrairement le contexte d'une fonction.

**Contexte** :
- Actuellement, MnemoLite n'est pas code-aware
- Pas de découpage intelligent du code
- Si on indexait du code, ce serait par chunks de taille fixe → perte de contexte
- Research 2024 (cAST paper) démontre **82% amélioration précision** avec AST chunking

**Valeur Métier** :
- Agents IA comprennent mieux le code (fonctions complètes, pas fragmentées)
- Recherche sémantique plus précise (+40-80% recall selon research)
- Foundation pour toutes les autres stories de l'EPIC

---

#### Critères d'Acceptation

**Infrastructure & Setup**:
- ✅ Tree-sitter installé dans l'environnement Python
- ✅ Parsers disponibles pour au moins 3 langages : Python, JavaScript, TypeScript
- ✅ Service `CodeChunkingService` créé dans `api/services/`
- ✅ Tests unitaires avec fixtures de code réel pour chaque langage

**Fonctionnalités**:
- ✅ **Langage détection** : Auto-détection du langage via extension fichier ou heuristique
- ✅ **AST Parsing** : Parsing correct du code en AST via tree-sitter
- ✅ **Semantic Chunking** : Découpage aux limites de fonction/classe/méthode
- ✅ **Size Management** : Si fonction >2000 chars → split récursif intelligent
- ✅ **Merge Small Chunks** : Petits chunks adjacents (<100 chars) fusionnés si cohérents
- ✅ **Fallback** : Si parsing échoue → fallback sur chunking fixe (2000 chars)

**Qualité**:
- ✅ >80% des chunks sont des fonctions/classes complètes (pas de coupure mid-function)
- ✅ Gestion d'erreurs robuste (fichiers malformés, syntaxe invalide)
- ✅ Performance : <100ms par fichier Python moyen (300 LOC)
- ✅ Tests coverage >85% sur `CodeChunkingService`

**Documentation**:
- ✅ Docstrings complètes sur toutes les méthodes publiques
- ✅ README technique : comment ajouter support nouveau langage
- ✅ ADR (Architecture Decision Record) : pourquoi Tree-sitter vs alternatives

---

#### Tasks Techniques

**1. Setup & Dependencies** (2 points)
```bash
# requirements.txt
tree-sitter==0.20.4
tree-sitter-python==0.20.4
tree-sitter-javascript==0.20.3
tree-sitter-typescript==0.20.5
```

**Fichiers à créer**:
- `api/services/code_chunking_service.py`
- `api/models/code_chunk.py` (Pydantic model)
- `tests/services/test_code_chunking_service.py`

**2. Language Detection** (1 point)
```python
# api/services/code_chunking_service.py
def detect_language(self, file_path: str, content: str) -> str:
    """
    Détecte le langage du fichier.

    Priority:
    1. Extension fichier (.py → python, .js → javascript, .ts → typescript)
    2. Shebang (#!/usr/bin/env python3)
    3. Heuristique contenu (si ambiguë)
    """
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java'
    }

    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower(), 'unknown')
```

**3. Tree-sitter Parser Setup** (2 points)
```python
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts

class CodeChunkingService:
    def __init__(self):
        self.parsers = {}
        self._setup_parsers()

    def _setup_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        self.parsers['python'] = Parser()
        self.parsers['python'].set_language(Language(tspython.language()))

        self.parsers['javascript'] = Parser()
        self.parsers['javascript'].set_language(Language(tsjs.language()))

        self.parsers['typescript'] = Parser()
        self.parsers['typescript'].set_language(Language(tsts.language()))

    def parse_code(self, source_code: str, language: str) -> Tree:
        """Parse code into AST."""
        if language not in self.parsers:
            raise ValueError(f"Unsupported language: {language}")

        parser = self.parsers[language]
        tree = parser.parse(bytes(source_code, "utf8"))
        return tree
```

**4. AST Node Identification** (3 points)
```python
def identify_code_units(self, tree: Tree, language: str) -> list[CodeUnit]:
    """
    Identify functions, classes, methods in AST.

    Returns list of CodeUnit with:
    - type: 'function' | 'class' | 'method' | 'module'
    - name: str
    - start_line: int
    - end_line: int
    - start_byte: int
    - end_byte: int
    """
    root_node = tree.root_node

    # Language-specific queries
    queries = {
        'python': """
            (function_definition name: (identifier) @func_name) @function
            (class_definition name: (identifier) @class_name) @class
        """,
        'javascript': """
            (function_declaration name: (identifier) @func_name) @function
            (class_declaration name: (identifier) @class_name) @class
            (method_definition name: (property_identifier) @method_name) @method
        """,
        # etc.
    }

    # Execute query and extract code units
    query = Language.query(queries[language])
    captures = query.captures(root_node)

    code_units = []
    for node, capture_name in captures:
        unit = CodeUnit(
            type=capture_name,
            name=self._extract_name(node),
            start_line=node.start_point[0],
            end_line=node.end_point[0],
            start_byte=node.start_byte,
            end_byte=node.end_byte
        )
        code_units.append(unit)

    return code_units
```

**5. Split-then-Merge Algorithm (cAST inspired)** (5 points)
```python
async def chunk_code(
    self,
    source_code: str,
    language: str,
    max_chunk_size: int = 2000
) -> list[CodeChunk]:
    """
    Main chunking algorithm (inspired by cAST paper 2024).

    Algorithm:
    1. Parse code → AST
    2. Identify code units (functions, classes, methods)
    3. For each unit:
        - If size < max_chunk_size → create chunk
        - If size > max_chunk_size → split recursively
    4. Merge small adjacent chunks (<100 chars)
    5. Return list of CodeChunk
    """
    try:
        tree = self.parse_code(source_code, language)
        code_units = self.identify_code_units(tree, language)

        chunks = []
        for unit in code_units:
            unit_code = source_code[unit.start_byte:unit.end_byte]

            if len(unit_code) <= max_chunk_size:
                # Small enough → direct chunk
                chunks.append(self._create_chunk(
                    source_code=unit_code,
                    chunk_type=unit.type,
                    name=unit.name,
                    start_line=unit.start_line,
                    end_line=unit.end_line
                ))
            else:
                # Too large → recursive split
                sub_chunks = self._split_large_unit(
                    unit, source_code, max_chunk_size
                )
                chunks.extend(sub_chunks)

        # Merge small adjacent chunks
        merged_chunks = self._merge_small_chunks(chunks, min_size=100)

        return merged_chunks

    except Exception as e:
        logger.warning(f"AST chunking failed: {e}. Falling back to fixed chunking.")
        return self._fallback_fixed_chunking(source_code, max_chunk_size)

def _split_large_unit(
    self,
    unit: CodeUnit,
    source_code: str,
    max_chunk_size: int
) -> list[CodeChunk]:
    """
    Recursively split large code unit (e.g., long function).

    Strategy:
    - Try to split at statement boundaries (if-else, loops, etc.)
    - Preserve indentation and context
    - Last resort: split at line boundaries
    """
    # Implementation details...
    pass

def _merge_small_chunks(
    self,
    chunks: list[CodeChunk],
    min_size: int
) -> list[CodeChunk]:
    """
    Merge adjacent chunks if both are < min_size.

    Example:
    - Chunk A: short import (50 chars)
    - Chunk B: short constant (30 chars)
    → Merge into single chunk (80 chars)
    """
    merged = []
    i = 0
    while i < len(chunks):
        current = chunks[i]

        if len(current.source_code) < min_size and i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            if len(next_chunk.source_code) < min_size:
                # Merge
                merged_chunk = self._merge_two_chunks(current, next_chunk)
                merged.append(merged_chunk)
                i += 2
                continue

        merged.append(current)
        i += 1

    return merged

def _fallback_fixed_chunking(
    self,
    source_code: str,
    chunk_size: int
) -> list[CodeChunk]:
    """
    Fallback: fixed-size chunking if AST parsing fails.
    """
    chunks = []
    for i in range(0, len(source_code), chunk_size):
        chunk_text = source_code[i:i + chunk_size]
        chunks.append(CodeChunk(
            source_code=chunk_text,
            chunk_type='unknown',
            name=None,
            start_line=None,
            end_line=None
        ))
    return chunks
```

---

#### Tests

**Test 1: Python Function Chunking**
```python
# tests/services/test_code_chunking_service.py
import pytest
from api.services.code_chunking_service import CodeChunkingService

@pytest.mark.asyncio
async def test_python_function_chunking():
    service = CodeChunkingService()

    source_code = """
def calculate_total(items):
    '''Calculate total price.'''
    result = 0
    for item in items:
        result += item.price
    return result

def calculate_tax(total, rate=0.2):
    '''Calculate tax amount.'''
    return total * rate
"""

    chunks = await service.chunk_code(source_code, language='python')

    assert len(chunks) == 2
    assert chunks[0].chunk_type == 'function'
    assert chunks[0].name == 'calculate_total'
    assert 'def calculate_total' in chunks[0].source_code
    assert chunks[1].name == 'calculate_tax'

@pytest.mark.asyncio
async def test_large_function_split():
    """Test that large functions are split recursively."""
    service = CodeChunkingService()

    # Create a 3000-char function (exceeds max_chunk_size=2000)
    large_function = "def large_func():\n" + "    print('test')\n" * 150

    chunks = await service.chunk_code(large_function, language='python', max_chunk_size=2000)

    # Should be split into multiple chunks
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.source_code) <= 2000

@pytest.mark.asyncio
async def test_fallback_on_invalid_syntax():
    """Test fallback to fixed chunking when AST parsing fails."""
    service = CodeChunkingService()

    invalid_code = "def broken_func(\n    # missing closing paren"

    chunks = await service.chunk_code(invalid_code, language='python')

    # Should fallback to fixed chunking
    assert len(chunks) > 0
    assert chunks[0].chunk_type == 'unknown'  # Fallback marker
```

**Test 2: JavaScript Class Chunking**
```python
@pytest.mark.asyncio
async def test_javascript_class_chunking():
    service = CodeChunkingService()

    source_code = """
class Calculator {
    constructor() {
        this.result = 0;
    }

    add(value) {
        this.result += value;
        return this;
    }

    subtract(value) {
        this.result -= value;
        return this;
    }
}
"""

    chunks = await service.chunk_code(source_code, language='javascript')

    assert len(chunks) >= 1
    assert chunks[0].chunk_type == 'class'
    assert chunks[0].name == 'Calculator'
```

**Test 3: Performance Test**
```python
@pytest.mark.asyncio
async def test_chunking_performance():
    """Test chunking performance on realistic file size."""
    service = CodeChunkingService()

    # Load real Python file (~300 LOC)
    with open('tests/fixtures/sample_module.py', 'r') as f:
        source_code = f.read()

    import time
    start = time.time()
    chunks = await service.chunk_code(source_code, language='python')
    elapsed = time.time() - start

    # Should process in < 100ms
    assert elapsed < 0.1, f"Chunking took {elapsed*1000}ms (target: <100ms)"
    assert len(chunks) > 0
```

---

#### Acceptance Criteria Détaillés

**AC-1: Language Detection**
- GIVEN un fichier "main.py"
- WHEN je détecte le langage
- THEN le résultat est "python"

**AC-2: AST Parsing Success**
- GIVEN du code Python valide
- WHEN je parse le code avec tree-sitter
- THEN j'obtiens un AST sans erreur
- AND je peux extraire les fonctions/classes

**AC-3: Semantic Chunking Quality**
- GIVEN un fichier avec 5 fonctions
- WHEN je découpe le code
- THEN j'obtiens 5 chunks (un par fonction)
- AND chaque chunk contient la fonction complète (pas de coupure)

**AC-4: Large Function Splitting**
- GIVEN une fonction de 3000 caractères
- AND max_chunk_size = 2000
- WHEN je découpe le code
- THEN la fonction est splitée en 2+ chunks
- AND chaque chunk ≤ 2000 caractères

**AC-5: Small Chunk Merging**
- GIVEN deux petites fonctions adjacentes (50 chars chacune)
- WHEN je découpe le code avec min_size=100
- THEN les deux fonctions sont mergées en un seul chunk

**AC-6: Fallback on Error**
- GIVEN du code Python avec syntaxe invalide
- WHEN je tente de découper le code
- THEN le système fallback sur chunking fixe (pas de crash)

**AC-7: Multi-Language Support**
- GIVEN des fichiers Python, JavaScript, TypeScript
- WHEN je découpe chaque fichier
- THEN tous les fichiers sont correctement chunked
- AND les résultats sont cohérents entre langages

**AC-8: Performance**
- GIVEN un fichier Python de 300 LOC
- WHEN je mesure le temps de chunking
- THEN le traitement prend < 100ms

---

#### Definition of Done

- ✅ Code implémenté et review passée
- ✅ Tests unitaires écrits et passent (coverage >85%)
- ✅ Tests d'intégration sur fichiers réels Python/JS/TS
- ✅ Performance validée (<100ms pour fichier 300 LOC)
- ✅ Documentation technique complète (docstrings + README)
- ✅ ADR rédigé (pourquoi Tree-sitter, alternatives considérées)
- ✅ Pas de régression sur tests existants

---

## Story 2: Dual Embeddings (Text + Code) - RÉVISÉ

### US-06-2: Code-Specialized Embeddings with Dual-Purpose Architecture

**Priority**: 🟡 MOYENNE
**Story Points**: 5 (RÉDUIT de 8)
**Complexité**: MOYENNE
**Dépendances**: Story 1 (chunking)

#### Description

**En tant que** système MnemoLite,
**Je veux** supporter dual embeddings (texte général + code spécialisé) avec architecture dual-purpose,
**Afin de** maintenir la mémoire agent TOUT EN ajoutant capacités code.

**⚠️ Contrainte Critique** :
- ✅ **Use case principal** : MnemoLite reste une mémoire pour conversations avec Claude/GPT, notes de dev, ADRs, documentation
- ✅ **Use case nouveau** : Indexation et recherche de code (complémentaire, pas remplacement)
- ✅ **Architecture** : Dual-purpose (texte général + code spécialisé)
- ✅ **Backward compatibility** : Table `events` inchangée, API v1 intacte

**Contexte** :
- Actuellement, MnemoLite utilise `nomic-embed-text-v1.5` (137M params, 768D, généraliste)
- Pour le code, on ajoute `jina-embeddings-v2-base-code` (161M params, 768D, Apache 2.0)
- **MÊME dimensionnalité 768D** → **PAS de migration DB!**
- Research: jina-code lead 9/15 benchmarks CodeSearchNet, 43× plus léger que nomic-code (7B)

**Valeur Métier** :
- Précision recherche code améliorée (+15-30% vs embeddings généralistes)
- **RAM léger** : ~700 MB total (nomic-text 137M + jina-code 161M) vs 14 GB avec nomic-code
- Compatibilité dimensions (768 = nomic-text) → pas de migration DB lourde
- Architecture dual-purpose : agent memory + code intelligence simultanés

---

#### Critères d'Acceptation

**Infrastructure**:
- ✅ **jina-embeddings-v2-base-code** téléchargé et accessible localement
- ✅ Configuration `.env` avec `CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code`
- ✅ `EmbeddingService` étendu avec paramètre `domain: 'text'|'code'|'hybrid'`
- ✅ **Backward compatibility** : Table `events` intacte, embeddings texte inchangés

**Fonctionnalités**:
- ✅ Nouveau enum `EmbeddingDomain(TEXT, CODE, HYBRID)` dans `EmbeddingService`
- ✅ Dual embeddings sur `code_chunks` : `embedding_text` + `embedding_code` (768D chacun)
- ✅ Table `events` : continue d'utiliser `nomic-text` uniquement (backward compatibility)
- ✅ Auto-détection : si chunk type='function' → domain=CODE ou HYBRID
- ✅ Migration douce : pas de réindexation forcée des anciens events
- ✅ API transparente : pas de breaking changes sur `/v1/events`

**Qualité**:
- ✅ Benchmark: jina-code vs nomic-text sur CodeSearchNet subset
- ✅ Précision +X% sur recherche code (documenter X vs embeddings généralistes)
- ✅ Performance : génération embeddings < 50ms/chunk
- ✅ **Validation** : 768D identiques (nomic-text == jina-code), HNSW index compatible
- ✅ **RAM total** : < 1 GB (nomic-text + jina-code = ~700 MB)

**Documentation**:
- ✅ Guide architecture : tables séparées (`events` vs `code_chunks`)
- ✅ Guide utilisation : quand utiliser TEXT vs CODE vs HYBRID
- ✅ Benchmark report : jina-code vs nomic-text (CodeSearchNet, latence, RAM)
- ✅ `.env.example` mis à jour avec `CODE_EMBEDDING_MODEL`
- ✅ ADR : pourquoi jina-code (161M) au lieu de nomic-code (7B)

---

#### Tasks Techniques

**1. Setup jina-embeddings-v2-base-code** (1 point - SIMPLIFIÉ)
```python
# requirements.txt (déjà présent, sentence-transformers download auto)
# sentence-transformers==2.7.0

# .env.example
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5          # Texte général (inchangé)
CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code  # Code spécialisé (nouveau)
EMBEDDING_DIMENSION=768  # Identique pour les deux (critique!)
```

**2. Extend EmbeddingService with Dual Embeddings** (2 points - SIMPLIFIÉ)
```python
# api/services/embedding_service.py
from sentence_transformers import SentenceTransformer
from enum import Enum

class EmbeddingDomain(str, Enum):
    TEXT = "text"      # Conversations, docs, general text
    CODE = "code"      # Code snippets, functions, classes
    HYBRID = "hybrid"  # Generate both (for code with docstrings)

class EmbeddingService:
    def __init__(self):
        self.text_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.code_model = SentenceTransformer(settings.CODE_EMBEDDING_MODEL)

    async def generate_embedding(
        self,
        text: str,
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> dict[str, list[float]]:
        """
        Generate embedding(s) based on domain.

        Args:
            text: Text or code to embed
            domain: TEXT (texte général), CODE (code only), HYBRID (both)

        Returns:
            Dict with 'text' and/or 'code' keys containing 768D embeddings
            - TEXT domain: {'text': [...]}
            - CODE domain: {'code': [...]}
            - HYBRID domain: {'text': [...], 'code': [...]}
        """
        result = {}

        if domain in [EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID]:
            embedding = self.text_model.encode(text, convert_to_tensor=False)
            result['text'] = embedding.tolist()

        if domain in [EmbeddingDomain.CODE, EmbeddingDomain.HYBRID]:
            embedding = self.code_model.encode(text, convert_to_tensor=False)
            result['code'] = embedding.tolist()

        return result

    def auto_detect_domain(self, chunk_type: str) -> EmbeddingDomain:
        """
        Auto-detect embedding domain based on chunk type.

        Args:
            chunk_type: 'function', 'class', 'method', 'text', 'unknown'

        Returns:
            EmbeddingDomain.CODE if code-related, EmbeddingDomain.TEXT otherwise
        """
        code_types = {'function', 'class', 'method', 'module'}
        return EmbeddingDomain.CODE if chunk_type in code_types else EmbeddingDomain.TEXT
```

**3. Dual Embeddings Storage for code_chunks** (1 point - SIMPLIFIÉ)
```python
# Architecture: Tables séparées
# - Table events: INCHANGÉE (embedding VECTOR(768) avec nomic-text uniquement)
# - Table code_chunks: NOUVELLE (embedding_text + embedding_code, 768D chacun)

# In CodeIndexingService:
async def index_code_chunk(self, chunk: CodeChunk):
    """Index code chunk with dual embeddings (text + code)."""

    # Generate BOTH embeddings for code chunks (HYBRID domain)
    embeddings = await self.embedding_service.generate_embedding(
        text=chunk.source_code,
        domain=EmbeddingDomain.HYBRID
    )
    # embeddings = {'text': [...768D...], 'code': [...768D...]}

    # Store in code_chunks table with dual embeddings
    await self.code_chunk_repo.create(
        source_code=chunk.source_code,
        embedding_text=embeddings['text'],  # nomic-text (docstrings, comments)
        embedding_code=embeddings['code'],  # jina-code (code sémantique)
        metadata={
            'text_model': 'nomic-ai/nomic-embed-text-v1.5',
            'code_model': 'jinaai/jina-embeddings-v2-base-code',
            ...
        }
    )

# In EventService (INCHANGÉ):
async def create_event(self, content: str):
    """Create event with text embedding only (backward compatibility)."""

    # Use TEXT domain only (agent memory use case)
    embeddings = await self.embedding_service.generate_embedding(
        text=content,
        domain=EmbeddingDomain.TEXT
    )
    # embeddings = {'text': [...768D...]}

    await self.event_repo.create(
        content=content,
        embedding=embeddings['text'],  # nomic-text uniquement
        ...
    )
```

**4. Benchmark jina-code vs nomic-text** (1 point)
```python
# scripts/benchmarks/benchmark_code_embeddings.py
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import time

async def benchmark_code_embeddings():
    """
    Benchmark nomic-text vs jina-code on CodeSearchNet subset.

    Metrics:
    - Recall@10 (précision retrieval)
    - MRR (Mean Reciprocal Rank)
    - Latency (génération embeddings)
    - RAM (memory footprint)
    """
    # Load CodeSearchNet test queries
    queries = load_codesearchnet_queries(limit=100)

    results_text = []
    results_code = []
    latency_text = []
    latency_code = []

    for query in queries:
        # Generate embeddings with both models (mesurer latence)
        start = time.time()
        emb_text = await embedding_service.generate_embedding(
            query, domain=EmbeddingDomain.TEXT
        )
        latency_text.append(time.time() - start)

        start = time.time()
        emb_code = await embedding_service.generate_embedding(
            query, domain=EmbeddingDomain.CODE
        )
        latency_code.append(time.time() - start)

        # Search in index (assuming code corpus indexed)
        results_text.append(await search(emb_text['text']))
        results_code.append(await search(emb_code['code']))

    # Calculate metrics
    recall_text = calculate_recall_at_k(results_text, k=10)
    recall_code = calculate_recall_at_k(results_code, k=10)

    print(f"Recall@10 (nomic-text): {recall_text:.2%}")
    print(f"Recall@10 (jina-code): {recall_code:.2%}")
    print(f"Improvement: +{(recall_code - recall_text):.2%}")
    print(f"Latency nomic-text: {np.mean(latency_text)*1000:.2f}ms")
    print(f"Latency jina-code: {np.mean(latency_code)*1000:.2f}ms")
    print(f"RAM total: ~700 MB (nomic-text 137M + jina-code 161M)")
```

---

#### Tests

**Test 1: Model Loading & Dimensions Validation**
```python
@pytest.mark.asyncio
async def test_both_models_load():
    """Verify both models load and produce 768D embeddings."""
    service = EmbeddingService()

    assert service.text_model is not None
    assert service.code_model is not None

    # Check dimensions (critical: both must be 768D)
    test_text = "Hello world"
    emb_text = await service.generate_embedding(test_text, domain=EmbeddingDomain.TEXT)
    emb_code = await service.generate_embedding(test_text, domain=EmbeddingDomain.CODE)
    emb_hybrid = await service.generate_embedding(test_text, domain=EmbeddingDomain.HYBRID)

    # TEXT domain: dict with 'text' key
    assert 'text' in emb_text
    assert len(emb_text['text']) == 768

    # CODE domain: dict with 'code' key
    assert 'code' in emb_code
    assert len(emb_code['code']) == 768

    # HYBRID domain: dict with both 'text' and 'code' keys
    assert 'text' in emb_hybrid and 'code' in emb_hybrid
    assert len(emb_hybrid['text']) == 768
    assert len(emb_hybrid['code']) == 768
```

**Test 2: Domain Auto-Detection**
```python
def test_auto_detect_domain():
    """Verify auto-detection of domain based on chunk type."""
    service = EmbeddingService()

    assert service.auto_detect_domain('function') == EmbeddingDomain.CODE
    assert service.auto_detect_domain('class') == EmbeddingDomain.CODE
    assert service.auto_detect_domain('method') == EmbeddingDomain.CODE
    assert service.auto_detect_domain('module') == EmbeddingDomain.CODE
    assert service.auto_detect_domain('text') == EmbeddingDomain.TEXT
    assert service.auto_detect_domain('unknown') == EmbeddingDomain.TEXT
```

**Test 3: Code vs Text Embeddings Quality**
```python
@pytest.mark.asyncio
async def test_code_embedding_better_for_code():
    """Verify jina-code embeddings are more precise for code snippets than nomic-text."""
    service = EmbeddingService()

    code_query = "def calculate total price from items list"
    code_snippet = "def calculate_total(items):\n    return sum(item.price for item in items)"

    # Generate embeddings
    query_emb_text = await service.generate_embedding(code_query, domain=EmbeddingDomain.TEXT)
    query_emb_code = await service.generate_embedding(code_query, domain=EmbeddingDomain.CODE)
    snippet_emb = await service.generate_embedding(code_snippet, domain=EmbeddingDomain.CODE)

    # Calculate similarities
    sim_text = cosine_similarity([query_emb_text['text']], [snippet_emb['code']])[0][0]
    sim_code = cosine_similarity([query_emb_code['code']], [snippet_emb['code']])[0][0]

    # Code embedding should be more similar
    assert sim_code > sim_text, f"Code similarity ({sim_code}) should be > text similarity ({sim_text})"

**Test 4: RAM Footprint Validation**
```python
@pytest.mark.asyncio
async def test_ram_footprint():
    """Verify total RAM usage < 1 GB (nomic-text + jina-code)."""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    # Load both models
    service = EmbeddingService()

    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    mem_used = mem_after - mem_before

    # Should be < 1000 MB (target: ~700 MB)
    assert mem_used < 1000, f"RAM usage {mem_used}MB exceeds 1GB limit"
    print(f"✅ Total RAM: {mem_used:.0f} MB (target: ~700 MB)")
```

---

#### Definition of Done

- ✅ **jina-embeddings-v2-base-code** intégré et opérationnel
- ✅ Dual model support (nomic-text + jina-code) implémenté avec `EmbeddingDomain` enum
- ✅ Dual embeddings sur `code_chunks` (embedding_text + embedding_code, 768D chacun)
- ✅ Auto-detection domain basée sur chunk_type (TEXT/CODE/HYBRID)
- ✅ **Backward compatibility** validée : table `events` intacte, API v1 sans breaking changes
- ✅ **Validation 768D** : dimensions identiques pour nomic-text et jina-code
- ✅ Benchmark nomic-text vs jina-code exécuté et documenté (Recall@10, latence, RAM)
- ✅ **RAM total < 1 GB** : validé (~700 MB pour nomic-text + jina-code)
- ✅ Tests unitaires + intégration passent (coverage >85%)
- ✅ Documentation `.env.example` + guide architecture dual-purpose
- ✅ ADR rédigé : pourquoi jina-code (161M) au lieu de nomic-code (7B)

---

## Story 3: Code Metadata Extraction

### US-06-3: Rich Code Metadata for Filtering & Ranking

**Priority**: 🟡 MOYENNE
**Story Points**: 8
**Complexité**: MOYENNE
**Dépendances**: Story 1 (chunking)

#### Description

**En tant qu'** agent IA,
**Je veux** des métadonnées riches sur chaque chunk de code (complexité, paramètres, docstring, etc.),
**Afin de** filtrer/scorer intelligemment les résultats de recherche.

**Exemples use cases** :
- "Trouver fonctions avec >5 paramètres" (complexité)
- "Fonctions sans docstring" (qualité code)
- "Méthodes testées" (has_tests=true)
- "Code modifié récemment" (last_modified)

**Valeur Métier** :
- Recherche plus fine (filtrage sur métadonnées)
- Scoring amélioré (complexité, tests, documentation)
- Insights sur qualité codebase

---

#### Critères d'Acceptation

**Métadonnées à Extraire** (pour Python minimum) :
- ✅ **Signature** : nom, paramètres, type hints, return type
- ✅ **Docstring** : extractio et parsing (Google/NumPy/Sphinx styles)
- ✅ **Complexité** : cyclomatic (via `radon`), lines of code, cognitive
- ✅ **Imports** : modules importés par ce chunk
- ✅ **Calls** : fonctions appelées dans ce chunk
- ✅ **Decorators** : @property, @staticmethod, @classmethod, custom
- ✅ **Tests** : détection si tests existent (`has_tests`, `test_files`)

**Storage** :
- ✅ Métadonnées stockées dans `code_chunks.metadata` (JSONB)
- ✅ Index GIN sur métadonnées pour requêtes rapides
- ✅ Schema validation (Pydantic model pour metadata structure)

**Qualité** :
- ✅ Extraction réussie sur >90% des fonctions Python réelles
- ✅ Performance : <20ms extraction metadata par chunk
- ✅ Tests sur fichiers Python réels (stdlib, popular libs)

---

#### Metadata Schema

```python
# api/models/code_metadata.py
from pydantic import BaseModel, Field
from typing import Optional

class CodeComplexity(BaseModel):
    cyclomatic: int = Field(..., description="Cyclomatic complexity (McCabe)")
    lines_of_code: int
    cognitive: Optional[int] = None  # Cognitive complexity (if available)

class FunctionSignature(BaseModel):
    name: str
    parameters: list[str]
    parameter_types: dict[str, str] = {}  # {param_name: type_hint}
    returns: Optional[str] = None  # Return type hint
    is_async: bool = False

class CodeMetadata(BaseModel):
    """Rich metadata for code chunks."""

    # Basic info
    language: str  # 'python', 'javascript', etc.
    chunk_type: str  # 'function', 'class', 'method', 'module'
    name: str

    # Signature (for functions/methods)
    signature: Optional[FunctionSignature] = None

    # Documentation
    docstring: Optional[str] = None
    docstring_summary: Optional[str] = None  # First line
    docstring_style: Optional[str] = None  # 'google', 'numpy', 'sphinx'

    # Complexity metrics
    complexity: CodeComplexity

    # Dependencies
    imports: list[str] = []  # ['typing.List', 'os.path']
    calls: list[str] = []    # ['sum', 'item.get_price']

    # Decorators (Python)
    decorators: list[str] = []  # ['@staticmethod', '@property']

    # Testing
    has_tests: bool = False
    test_files: list[str] = []  # Paths to test files

    # VCS (if available)
    last_modified: Optional[str] = None  # ISO datetime
    author: Optional[str] = None
    commit_hash: Optional[str] = None

    # Usage (static analysis)
    usage_frequency: int = 0  # Number of call sites
    is_public_api: bool = False  # Exported in __all__ or public module
```

---

#### Tasks Techniques

**1. Complexity Extraction** (2 points)
```python
# api/services/code_metadata_service.py
import radon.complexity as radon_cc
import radon.metrics as radon_metrics

class CodeMetadataService:
    def extract_complexity(self, source_code: str) -> CodeComplexity:
        """
        Extract complexity metrics using radon.

        Args:
            source_code: Python source code

        Returns:
            CodeComplexity with cyclomatic, LOC, cognitive
        """
        # Cyclomatic complexity
        cc_results = radon_cc.cc_visit(source_code)
        cyclomatic = cc_results[0].complexity if cc_results else 1

        # Lines of code
        loc = len([line for line in source_code.split('\n') if line.strip()])

        return CodeComplexity(
            cyclomatic=cyclomatic,
            lines_of_code=loc,
            cognitive=None  # TODO: implement if needed
        )
```

**2. Signature Extraction via AST** (2 points)
```python
import ast

def extract_signature(self, node: ast.FunctionDef) -> FunctionSignature:
    """
    Extract function signature from AST node.

    Args:
        node: ast.FunctionDef or ast.AsyncFunctionDef

    Returns:
        FunctionSignature with params, types, returns
    """
    parameters = [arg.arg for arg in node.args.args]

    # Extract type hints
    parameter_types = {}
    for arg in node.args.args:
        if arg.annotation:
            parameter_types[arg.arg] = ast.unparse(arg.annotation)

    # Extract return type
    returns = ast.unparse(node.returns) if node.returns else None

    # Check if async
    is_async = isinstance(node, ast.AsyncFunctionDef)

    return FunctionSignature(
        name=node.name,
        parameters=parameters,
        parameter_types=parameter_types,
        returns=returns,
        is_async=is_async
    )
```

**3. Docstring Parsing** (1 point)
```python
def extract_docstring(self, node: ast.FunctionDef) -> tuple[Optional[str], Optional[str]]:
    """
    Extract and parse docstring.

    Returns:
        (full_docstring, summary_first_line)
    """
    docstring = ast.get_docstring(node)
    if not docstring:
        return None, None

    # Extract first line as summary
    summary = docstring.split('\n')[0].strip()

    return docstring, summary
```

**4. Import & Call Extraction** (2 points)
```python
def extract_imports_and_calls(self, source_code: str) -> tuple[list[str], list[str]]:
    """
    Extract imports and function calls via AST.

    Returns:
        (imports, calls)
    """
    tree = ast.parse(source_code)

    imports = []
    calls = []

    for node in ast.walk(tree):
        # Extract imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

        # Extract function calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(ast.unparse(node.func))

    return imports, calls
```

**5. Test Detection** (1 point)
```python
def detect_tests(
    self,
    chunk_name: str,
    file_path: str,
    repository_path: str
) -> tuple[bool, list[str]]:
    """
    Detect if tests exist for this code chunk.

    Strategy:
    1. Look for test_<name>.py or <name>_test.py
    2. Search for test methods containing chunk_name
    3. Check pytest/unittest patterns

    Returns:
        (has_tests, test_file_paths)
    """
    # Heuristic: search for test files
    test_patterns = [
        f"test_{chunk_name}.py",
        f"{chunk_name}_test.py",
        "test_*.py"
    ]

    test_files = []
    # Search in tests/ directory
    tests_dir = os.path.join(repository_path, 'tests')
    if os.path.exists(tests_dir):
        for root, dirs, files in os.walk(tests_dir):
            for file in files:
                if file.endswith('_test.py') or file.startswith('test_'):
                    # Check if file contains reference to chunk_name
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if chunk_name in content:
                            test_files.append(file_path)

    has_tests = len(test_files) > 0
    return has_tests, test_files
```

---

#### Tests

**Test 1: Complexity Extraction**
```python
def test_extract_complexity():
    service = CodeMetadataService()

    source_code = """
def simple_function(x):
    return x * 2
"""

    complexity = service.extract_complexity(source_code)

    assert complexity.cyclomatic == 1  # No branches
    assert complexity.lines_of_code == 2

def test_complex_function_complexity():
    service = CodeMetadataService()

    source_code = """
def complex_function(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x - y
    else:
        return 0
"""

    complexity = service.extract_complexity(source_code)

    assert complexity.cyclomatic >= 3  # Multiple branches
```

**Test 2: Signature Extraction**
```python
def test_extract_signature_with_type_hints():
    service = CodeMetadataService()

    source_code = """
def calculate_total(items: List[Item], tax_rate: float = 0.2) -> float:
    total = sum(item.price for item in items)
    return total * (1 + tax_rate)
"""

    tree = ast.parse(source_code)
    func_node = tree.body[0]

    signature = service.extract_signature(func_node)

    assert signature.name == 'calculate_total'
    assert signature.parameters == ['items', 'tax_rate']
    assert signature.parameter_types['items'] == 'List[Item]'
    assert signature.parameter_types['tax_rate'] == 'float'
    assert signature.returns == 'float'
    assert signature.is_async is False
```

**Test 3: Docstring Parsing**
```python
def test_extract_docstring():
    service = CodeMetadataService()

    source_code = """
def my_function():
    '''
    This is a summary.

    This is a longer description
    with multiple lines.
    '''
    pass
"""

    tree = ast.parse(source_code)
    func_node = tree.body[0]

    docstring, summary = service.extract_docstring(func_node)

    assert summary == 'This is a summary.'
    assert 'longer description' in docstring
```

**Test 4: Complete Metadata Extraction**
```python
@pytest.mark.asyncio
async def test_complete_metadata_extraction():
    service = CodeMetadataService()

    source_code = """
from typing import List

def calculate_total(items: List[dict]) -> float:
    '''Calculate total price from items.'''
    return sum(item['price'] for item in items)
"""

    metadata = await service.extract_metadata(
        source_code=source_code,
        language='python',
        chunk_type='function',
        file_path='src/calculations.py'
    )

    assert metadata.name == 'calculate_total'
    assert metadata.signature is not None
    assert metadata.signature.parameters == ['items']
    assert metadata.docstring_summary == 'Calculate total price from items.'
    assert metadata.complexity.cyclomatic >= 1
    assert 'typing.List' in metadata.imports
    assert 'sum' in metadata.calls
```

---

#### Definition of Done

- ✅ `CodeMetadataService` implémenté avec toutes méthodes extraction
- ✅ Metadata schema (Pydantic) défini et validé
- ✅ Extraction réussie sur >90% fonctions Python réelles
- ✅ Performance <20ms par chunk
- ✅ Tests unitaires sur tous extractors
- ✅ Tests intégration avec fichiers stdlib Python
- ✅ Documentation complète (docstrings + README)
- ✅ Integration avec `CodeIndexingService` (Story 6)

---

## Story 4: Dependency Graph Construction

### US-06-4: Navigate Code via Call Graph & Dependency Graph

**Priority**: 🟡 MOYENNE
**Story Points**: 13
**Complexité**: HAUTE
**Dépendances**: Story 1 (chunking), Story 3 (metadata)

#### Description

**En tant qu'** agent IA,
**Je veux** naviguer le call graph et le dependency graph du code indexé,
**Afin de** comprendre les relations entre fonctions/classes et l'architecture globale.

**Use Cases** :
- "Quelles fonctions appellent `calculate_total` ?" (inbound call graph)
- "Quels modules importe `main.py` ?" (import graph)
- "Quelle est la chaîne d'appels de `api_endpoint` jusqu'aux fonctions DB ?" (transitive)
- "Trouver tous les usages d'une classe" (data flow)

**Valeur Métier** :
- Compréhension architecture : agents voient structure codebase
- Navigation contextuelle : enrichir résultats search avec dependencies
- Impact analysis : "Si je modifie cette fonction, qu'est-ce qui casse ?"

---

#### Critères d'Acceptation

**Types de Relations** :
- ✅ `calls` : fonction A appelle fonction B
- ✅ `imports` : module A importe module B
- ✅ `extends` : classe A hérite de classe B (Python, TS)
- ✅ `implements` : classe A implémente interface B (TS, Java)
- ✅ `uses` : fonction A utilise variable/type B

**Storage** :
- ✅ Stockage dans tables `nodes` + `edges` (déjà existantes)
- ✅ Extension schema : `nodes.code_metadata` (JSONB)
- ✅ Extension schema : `edges.call_frequency` (INT)

**Graph Queries** :
- ✅ Requêtes CTE récursives pour traversal (≤3 hops)
- ✅ API `GET /v1/code/graph` avec paramètres (from, relationship, direction, depth)
- ✅ Performance : <20ms pour depth=2

**Visualisation** :
- ✅ Format JSON compatible avec UI v4.0 graph visualization
- ✅ Métadonnées nodes/edges pour rendering (labels, colors)

---

#### Graph Schema Extension

```sql
-- Extend existing nodes table for code
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS code_metadata JSONB;

-- Index for code queries
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_code_metadata ON nodes USING gin (code_metadata jsonb_path_ops);

-- Extend edges for call frequency
ALTER TABLE edges ADD COLUMN IF NOT EXISTS call_frequency INT DEFAULT 0;
ALTER TABLE edges ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Example node for function:
INSERT INTO nodes (node_id, node_type, label, props, code_metadata) VALUES (
    gen_random_uuid(),
    'function',
    'calculate_total',
    '{"file": "src/calc.py", "line": 10}'::jsonb,
    '{
        "signature": "calculate_total(items: List[Item]) -> float",
        "complexity": 3,
        "is_public": true
    }'::jsonb
);

-- Example edge (call relationship):
INSERT INTO edges (edge_id, source_node, target_node, relationship, call_frequency, metadata) VALUES (
    gen_random_uuid(),
    '<uuid_func_a>',
    '<uuid_func_b>',
    'calls',
    5,  -- Function A calls B 5 times in its body
    '{"call_sites": [{"line": 15}, {"line": 23}]}'::jsonb
);
```

---

#### Tasks Techniques

**1. Static Analysis for Call Graph** (4 points)
```python
# api/services/graph_analysis_service.py
import ast
from typing import Dict, Set

class GraphAnalysisService:
    async def build_call_graph(
        self,
        source_code: str,
        file_path: str,
        language: str
    ) -> tuple[list[Node], list[Edge]]:
        """
        Build call graph from source code via static analysis.

        Returns:
            (nodes, edges) representing functions and their calls
        """
        if language == 'python':
            return await self._build_python_call_graph(source_code, file_path)
        elif language == 'javascript':
            return await self._build_js_call_graph(source_code, file_path)
        else:
            raise ValueError(f"Unsupported language: {language}")

    async def _build_python_call_graph(
        self,
        source_code: str,
        file_path: str
    ) -> tuple[list[Node], list[Edge]]:
        """
        Build call graph for Python code.

        Algorithm:
        1. Parse code → AST
        2. Extract all function definitions → nodes
        3. For each function, analyze body for function calls → edges
        4. Track call frequency (how many times called in body)
        """
        tree = ast.parse(source_code)

        nodes = []
        edges = []
        function_map = {}  # {func_name: node_id}

        # Step 1: Create nodes for all functions/classes
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                node_id = uuid.uuid4()
                function_map[node.name] = node_id

                nodes.append(Node(
                    node_id=node_id,
                    node_type='function',
                    label=node.name,
                    props={'file': file_path, 'line': node.lineno},
                    code_metadata={
                        'signature': self._extract_signature(node),
                        'is_async': isinstance(node, ast.AsyncFunctionDef)
                    }
                ))

            elif isinstance(node, ast.ClassDef):
                node_id = uuid.uuid4()
                function_map[node.name] = node_id

                nodes.append(Node(
                    node_id=node_id,
                    node_type='class',
                    label=node.name,
                    props={'file': file_path, 'line': node.lineno},
                    code_metadata={'bases': [ast.unparse(b) for b in node.bases]}
                ))

        # Step 2: Create edges for function calls
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                caller_id = function_map.get(node.name)
                if not caller_id:
                    continue

                # Analyze function body for calls
                calls = self._extract_calls_from_function(node)

                for called_func, call_count in calls.items():
                    callee_id = function_map.get(called_func)
                    if callee_id:
                        edges.append(Edge(
                            edge_id=uuid.uuid4(),
                            source_node=caller_id,
                            target_node=callee_id,
                            relationship='calls',
                            call_frequency=call_count,
                            metadata={}
                        ))

        return nodes, edges

    def _extract_calls_from_function(self, func_node: ast.FunctionDef) -> Dict[str, int]:
        """
        Extract all function calls from function body.

        Returns:
            {function_name: call_count}
        """
        calls = {}

        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # Direct function call: foo()
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    calls[func_name] = calls.get(func_name, 0) + 1

                # Method call: obj.method()
                elif isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    calls[method_name] = calls.get(method_name, 0) + 1

        return calls
```

**2. Import Graph** (2 points)
```python
async def build_import_graph(
    self,
    source_code: str,
    file_path: str,
    language: str
) -> tuple[list[Node], list[Edge]]:
    """
    Build import/dependency graph.

    Returns:
        Nodes for modules, edges for imports
    """
    tree = ast.parse(source_code)

    # Create node for current module
    current_module_id = uuid.uuid4()
    nodes = [Node(
        node_id=current_module_id,
        node_type='module',
        label=file_path,
        props={'file': file_path}
    )]

    edges = []

    # Extract imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported_modules = self._extract_imports(node)

            for module_name in imported_modules:
                # Create node for imported module
                imported_id = uuid.uuid4()
                nodes.append(Node(
                    node_id=imported_id,
                    node_type='module',
                    label=module_name,
                    props={}
                ))

                # Create edge: current_module imports imported_module
                edges.append(Edge(
                    edge_id=uuid.uuid4(),
                    source_node=current_module_id,
                    target_node=imported_id,
                    relationship='imports'
                ))

    return nodes, edges
```

**3. Graph Traversal Queries** (3 points)
```python
# api/repositories/graph_repository.py
class GraphRepository:
    async def traverse_graph(
        self,
        from_node_id: UUID,
        relationship: str,
        direction: Literal['inbound', 'outbound', 'both'],
        depth: int = 1
    ) -> list[GraphPath]:
        """
        Traverse graph using recursive CTE.

        Args:
            from_node_id: Starting node
            relationship: Type of edge ('calls', 'imports', etc.)
            direction: 'inbound' (who calls me), 'outbound' (who do I call), 'both'
            depth: Max traversal depth (1-3)

        Returns:
            List of graph paths with nodes and edges
        """
        if depth > 3:
            raise ValueError("Max depth is 3 to prevent performance issues")

        # Build recursive CTE query
        if direction == 'outbound':
            query = text("""
                WITH RECURSIVE graph_traversal AS (
                    -- Base case: starting node
                    SELECT
                        e.source_node,
                        e.target_node,
                        e.relationship,
                        e.call_frequency,
                        1 AS depth,
                        ARRAY[e.edge_id] AS path
                    FROM edges e
                    WHERE e.source_node = :start_node
                      AND e.relationship = :relationship

                    UNION ALL

                    -- Recursive case: follow edges
                    SELECT
                        e.source_node,
                        e.target_node,
                        e.relationship,
                        e.call_frequency,
                        gt.depth + 1,
                        gt.path || e.edge_id
                    FROM edges e
                    INNER JOIN graph_traversal gt ON e.source_node = gt.target_node
                    WHERE gt.depth < :max_depth
                      AND e.relationship = :relationship
                      AND NOT (e.edge_id = ANY(gt.path))  -- Avoid cycles
                )
                SELECT * FROM graph_traversal;
            """)

        elif direction == 'inbound':
            query = text("""
                WITH RECURSIVE graph_traversal AS (
                    -- Base case: who calls me
                    SELECT
                        e.source_node,
                        e.target_node,
                        e.relationship,
                        e.call_frequency,
                        1 AS depth,
                        ARRAY[e.edge_id] AS path
                    FROM edges e
                    WHERE e.target_node = :start_node
                      AND e.relationship = :relationship

                    UNION ALL

                    -- Recursive case: follow inbound edges
                    SELECT
                        e.source_node,
                        e.target_node,
                        e.relationship,
                        e.call_frequency,
                        gt.depth + 1,
                        gt.path || e.edge_id
                    FROM edges e
                    INNER JOIN graph_traversal gt ON e.target_node = gt.source_node
                    WHERE gt.depth < :max_depth
                      AND e.relationship = :relationship
                      AND NOT (e.edge_id = ANY(gt.path))
                )
                SELECT * FROM graph_traversal;
            """)

        # Execute query
        result = await self.db.execute(query, {
            'start_node': from_node_id,
            'relationship': relationship,
            'max_depth': depth
        })

        # Fetch nodes details
        paths = []
        for row in result:
            path = await self._build_graph_path(row)
            paths.append(path)

        return paths
```

**4. API Endpoints** (2 points)
```python
# api/routes/code_routes.py
from fastapi import APIRouter, Depends
from api.services.graph_analysis_service import GraphAnalysisService

router = APIRouter(prefix="/v1/code", tags=["code"])

@router.get("/graph")
async def get_code_graph(
    from_node: UUID,
    relationship: str = 'calls',
    direction: Literal['inbound', 'outbound', 'both'] = 'outbound',
    depth: int = Query(1, ge=1, le=3),
    graph_service: GraphAnalysisService = Depends(get_graph_service)
):
    """
    Navigate code graph.

    Examples:
    - GET /v1/code/graph?from_node=<uuid>&relationship=calls&direction=outbound&depth=2
      → "What functions does this function call (up to 2 hops)?"

    - GET /v1/code/graph?from_node=<uuid>&relationship=calls&direction=inbound&depth=1
      → "What functions call this function?"

    - GET /v1/code/graph?from_node=<uuid>&relationship=imports&direction=outbound&depth=1
      → "What modules does this module import?"
    """
    paths = await graph_service.traverse_graph(
        from_node_id=from_node,
        relationship=relationship,
        direction=direction,
        depth=depth
    )

    return {
        "from_node": from_node,
        "relationship": relationship,
        "direction": direction,
        "depth": depth,
        "paths": paths,
        "total_paths": len(paths)
    }
```

**5. Visualisation JSON Format** (2 points)
```python
# Output format compatible with UI v4.0
{
  "from_node": "<uuid>",
  "relationship": "calls",
  "direction": "outbound",
  "depth": 2,
  "paths": [
    {
      "nodes": [
        {
          "id": "<uuid>",
          "type": "function",
          "label": "calculate_total",
          "metadata": {
            "file": "src/calc.py",
            "line": 10,
            "signature": "calculate_total(items: List[Item]) -> float"
          }
        },
        {
          "id": "<uuid>",
          "type": "function",
          "label": "sum_prices",
          "metadata": {
            "file": "src/utils.py",
            "line": 45
          }
        }
      ],
      "edges": [
        {
          "id": "<uuid>",
          "source": "<uuid>",
          "target": "<uuid>",
          "relationship": "calls",
          "call_frequency": 1,
          "metadata": {}
        }
      ]
    }
  ],
  "total_paths": 1
}
```

---

#### Tests

**Test 1: Call Graph Construction**
```python
@pytest.mark.asyncio
async def test_build_call_graph():
    service = GraphAnalysisService()

    source_code = """
def main():
    result = calculate_total([1, 2, 3])
    print_result(result)

def calculate_total(items):
    return sum(items)

def print_result(value):
    print(f"Result: {value}")
"""

    nodes, edges = await service.build_call_graph(source_code, 'test.py', 'python')

    # Should have 3 function nodes
    assert len(nodes) == 3
    assert {n.label for n in nodes} == {'main', 'calculate_total', 'print_result'}

    # Should have 2 call edges (main → calculate_total, main → print_result)
    assert len(edges) == 2
    call_targets = [e.target_node for e in edges if e.relationship == 'calls']
    assert len(call_targets) == 2

@pytest.mark.asyncio
async def test_graph_traversal_outbound():
    """Test traversing call graph outbound (who do I call)."""
    repo = GraphRepository(db_engine)

    # Setup: insert test graph
    # main → func_a → func_b
    main_id = await repo.create_node('function', 'main', {})
    func_a_id = await repo.create_node('function', 'func_a', {})
    func_b_id = await repo.create_node('function', 'func_b', {})

    await repo.create_edge(main_id, func_a_id, 'calls')
    await repo.create_edge(func_a_id, func_b_id, 'calls')

    # Traverse from main, depth=2
    paths = await repo.traverse_graph(
        from_node_id=main_id,
        relationship='calls',
        direction='outbound',
        depth=2
    )

    # Should find path: main → func_a → func_b
    assert len(paths) >= 1
    assert any(p.depth == 2 for p in paths)

@pytest.mark.asyncio
async def test_graph_traversal_inbound():
    """Test traversing call graph inbound (who calls me)."""
    repo = GraphRepository(db_engine)

    # Setup: main → func_a
    main_id = await repo.create_node('function', 'main', {})
    func_a_id = await repo.create_node('function', 'func_a', {})
    await repo.create_edge(main_id, func_a_id, 'calls')

    # Traverse from func_a inbound
    paths = await repo.traverse_graph(
        from_node_id=func_a_id,
        relationship='calls',
        direction='inbound',
        depth=1
    )

    # Should find: main calls func_a
    assert len(paths) >= 1
    assert paths[0].source_node == main_id
```

---

#### Definition of Done

- ✅ `GraphAnalysisService` implémenté (call graph + import graph)
- ✅ Static analysis Python opérationnel (call extraction via AST)
- ✅ Schéma DB étendu (`nodes.code_metadata`, `edges.call_frequency`)
- ✅ Graph traversal queries (CTE récursifs) performantes (<20ms depth=2)
- ✅ API `/v1/code/graph` opérationnelle avec tous paramètres
- ✅ Format JSON visualisation compatible UI v4.0
- ✅ Tests unitaires + intégration sur graphes réels
- ✅ Documentation API (OpenAPI) complète

---

## Story 5: Hybrid Search (BM25 + Vector + Graph)

### US-06-5: Multi-Strategy Code Search with Fusion

**Priority**: 🔴 HAUTE
**Story Points**: 21
**Complexité**: TRÈS HAUTE
**Dépendances**: Story 2 (embeddings), Story 4 (graph)

#### Description

**En tant qu'** agent IA,
**Je veux** rechercher du code avec hybrid search combinant BM25 (lexical), vector (semantic), et graph (relational),
**Afin d'** obtenir les résultats les plus pertinents en fusionnant différentes stratégies.

**Architecture** :
```
Query → [BM25 Search] → Results A
     → [Vector Search] → Results B
     → RRF Fusion → Combined Results
     → [Graph Expansion (optional)] → Enriched Results
     → Final Ranking
```

**Valeur Métier** :
- Recall amélioré (+25-40% vs vector-only selon research)
- Lexical + Semantic : combine exact matching et similarité sémantique
- Graph expansion : enrichit résultats avec dependencies

---

#### Critères d'Acceptation

**Composants** :
- ✅ **BM25 Search** : Lexical search via `pg_trgm` (trigram similarity)
- ✅ **Vector Search** : Semantic search via HNSW (déjà existant)
- ✅ **RRF Fusion** : Reciprocal Rank Fusion pour combiner scores
- ✅ **Graph Expansion** : Optionnel, enrichir avec dependencies
- ✅ **API unified** : `/v1/code/search` avec tous paramètres

**Performance** :
- ✅ Hybrid search (BM25+Vector) : <50ms P95 sur 10k chunks
- ✅ With graph expansion (depth=1) : <80ms P95
- ✅ Recall@10 : +25% vs vector-only (benchmark sur CodeSearchNet)

**Qualité** :
- ✅ Tests sur corpus code réel (~1000 chunks Python)
- ✅ A/B testing : hybrid vs vector-only vs BM25-only
- ✅ Tuning RRF parameter k (default=60)

---

#### Tasks Techniques

**1. BM25 Implementation (PostgreSQL pg_trgm)** (5 points)
```sql
-- Enable pg_trgm extension (already installed)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Trigram index on source_code (already created in Story 1)
-- CREATE INDEX idx_code_chunks_source_trgm ON code_chunks USING gin (source_code gin_trgm_ops);

-- BM25-like query using similarity()
SELECT
    id,
    name,
    source_code,
    file_path,
    chunk_type,
    similarity(source_code, :query) AS bm25_score
FROM code_chunks
WHERE
    source_code % :query  -- Trigram similarity operator (threshold default 0.3)
    AND (:language IS NULL OR language = :language)
    AND (:chunk_type IS NULL OR chunk_type = :chunk_type)
ORDER BY bm25_score DESC
LIMIT 100;  -- Overfetch for fusion
```

**Python implementation** :
```python
# api/repositories/code_chunk_repository.py
async def bm25_search(
    self,
    query: str,
    language: Optional[str] = None,
    chunk_type: Optional[str] = None,
    limit: int = 100
) -> list[CodeChunk]:
    """
    BM25-like lexical search using pg_trgm.

    Args:
        query: Search query
        language: Filter by language
        chunk_type: Filter by chunk type
        limit: Max results (overfetch for fusion)

    Returns:
        List of code chunks with bm25_score
    """
    sql = text("""
        SELECT
            id,
            name,
            source_code,
            file_path,
            chunk_type,
            embedding,
            metadata,
            similarity(source_code, :query) AS bm25_score
        FROM code_chunks
        WHERE
            source_code % :query
            AND (:language::text IS NULL OR language = :language)
            AND (:chunk_type::text IS NULL OR chunk_type = :chunk_type)
        ORDER BY bm25_score DESC
        LIMIT :limit;
    """)

    result = await self.db.execute(sql, {
        'query': query,
        'language': language,
        'chunk_type': chunk_type,
        'limit': limit
    })

    chunks = []
    for row in result:
        chunk = CodeChunk(
            id=row.id,
            name=row.name,
            source_code=row.source_code,
            file_path=row.file_path,
            chunk_type=row.chunk_type,
            metadata=row.metadata,
            score=row.bm25_score  # BM25 score
        )
        chunks.append(chunk)

    return chunks
```

**2. RRF (Reciprocal Rank Fusion)** (3 points)
```python
# api/services/hybrid_code_search_service.py
from collections import defaultdict

class HybridCodeSearchService:
    def rrf_fusion(
        self,
        result_lists: list[list[CodeChunk]],
        k: int = 60
    ) -> list[CodeChunk]:
        """
        Combine multiple result lists using Reciprocal Rank Fusion.

        Formula: RRF_score(chunk) = Σ 1 / (rank + k)
        where rank is the position of chunk in each result list.

        Args:
            result_lists: Multiple ranked lists (e.g., [bm25_results, vector_results])
            k: Constant for RRF (default 60, typical value)

        Returns:
            Fused list sorted by combined RRF score
        """
        rrf_scores = defaultdict(float)
        chunk_map = {}  # {chunk_id: chunk_object}

        for result_list in result_lists:
            for rank, chunk in enumerate(result_list, start=1):
                chunk_id = chunk.id
                rrf_scores[chunk_id] += 1.0 / (rank + k)
                chunk_map[chunk_id] = chunk

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Build final list with RRF scores
        fused_results = []
        for chunk_id, rrf_score in sorted_ids:
            chunk = chunk_map[chunk_id]
            chunk.score = rrf_score  # Update with RRF score
            fused_results.append(chunk)

        return fused_results
```

**3. Hybrid Search Service** (8 points)
```python
class HybridCodeSearchService:
    def __init__(
        self,
        code_chunk_repo: CodeChunkRepository,
        embedding_service: EmbeddingService,
        graph_service: GraphAnalysisService
    ):
        self.code_chunk_repo = code_chunk_repo
        self.embedding_service = embedding_service
        self.graph_service = graph_service

    async def search(
        self,
        query: str,
        language: Optional[str] = None,
        chunk_type: Optional[str] = None,
        use_bm25: bool = True,
        use_vector: bool = True,
        use_graph: bool = False,
        expand_graph_depth: int = 0,
        rrf_k: int = 60,
        limit: int = 10
    ) -> SearchResults:
        """
        Hybrid code search with multiple strategies.

        Strategies:
        1. BM25 (lexical): exact token matching
        2. Vector (semantic): similarity in embedding space
        3. Graph (relational): expand results with dependencies

        Fusion:
        - RRF (Reciprocal Rank Fusion) to combine BM25 + Vector
        - Graph expansion optional (enriches top-K results)

        Args:
            query: Search query
            language: Filter by language
            chunk_type: Filter by chunk type
            use_bm25: Enable BM25 search
            use_vector: Enable vector search
            use_graph: Enable graph expansion
            expand_graph_depth: Depth for graph expansion (0-2)
            rrf_k: RRF constant (default 60)
            limit: Max results to return

        Returns:
            SearchResults with ranked code chunks
        """
        result_lists = []

        # Strategy 1: BM25 Search (lexical)
        if use_bm25:
            logger.info(f"Running BM25 search for: {query}")
            bm25_results = await self.code_chunk_repo.bm25_search(
                query=query,
                language=language,
                chunk_type=chunk_type,
                limit=100  # Overfetch
            )
            result_lists.append(bm25_results)
            logger.info(f"BM25 returned {len(bm25_results)} results")

        # Strategy 2: Vector Search (semantic)
        if use_vector:
            logger.info(f"Running vector search for: {query}")
            query_embedding = await self.embedding_service.generate_embedding(
                text=query,
                model_type=ModelType.CODE
            )
            vector_results = await self.code_chunk_repo.vector_search(
                embedding=query_embedding,
                language=language,
                chunk_type=chunk_type,
                limit=100  # Overfetch
            )
            result_lists.append(vector_results)
            logger.info(f"Vector search returned {len(vector_results)} results")

        # Fusion: RRF
        if len(result_lists) == 0:
            # No search strategy enabled
            return SearchResults(data=[], meta={'total': 0})

        elif len(result_lists) == 1:
            # Single strategy, no fusion needed
            fused_results = result_lists[0][:limit]

        else:
            # Multiple strategies, apply RRF
            logger.info("Applying RRF fusion")
            fused_results = self.rrf_fusion(result_lists, k=rrf_k)
            fused_results = fused_results[:limit]

        # Strategy 3: Graph Expansion (optional)
        if use_graph and expand_graph_depth > 0:
            logger.info(f"Expanding results with graph (depth={expand_graph_depth})")
            fused_results = await self._expand_with_graph(
                results=fused_results,
                depth=expand_graph_depth
            )

        return SearchResults(
            data=fused_results,
            meta={
                'total': len(fused_results),
                'strategies': {
                    'bm25': use_bm25,
                    'vector': use_vector,
                    'graph': use_graph
                },
                'rrf_k': rrf_k if len(result_lists) > 1 else None
            }
        )

    async def _expand_with_graph(
        self,
        results: list[CodeChunk],
        depth: int
    ) -> list[CodeChunk]:
        """
        Expand search results with graph dependencies.

        For each result chunk:
        1. Traverse graph (calls, imports) up to depth
        2. Add related chunks to results
        3. Preserve original ranking order

        Args:
            results: Initial search results
            depth: Graph traversal depth (1-2)

        Returns:
            Expanded results with dependencies
        """
        expanded = []

        for chunk in results:
            expanded.append(chunk)  # Original result

            if chunk.node_id:
                # Traverse graph from this chunk
                paths = await self.graph_service.traverse_graph(
                    from_node_id=chunk.node_id,
                    relationship='calls',
                    direction='both',  # Inbound + outbound
                    depth=depth
                )

                # Add related chunks
                for path in paths:
                    for node in path.nodes:
                        related_chunk = await self.code_chunk_repo.get_by_node_id(node.id)
                        if related_chunk and related_chunk.id not in [c.id for c in expanded]:
                            related_chunk.score = chunk.score * 0.8  # Penalize related
                            related_chunk.metadata['relation'] = 'graph_expanded'
                            expanded.append(related_chunk)

        return expanded
```

**4. API Endpoint** (3 points)
```python
# api/routes/code_routes.py
@router.post("/search")
async def search_code(
    request: CodeSearchRequest,
    hybrid_search: HybridCodeSearchService = Depends(get_hybrid_search_service)
):
    """
    Hybrid code search endpoint.

    Body:
    {
        "query": "function that calculates totals",
        "language": "python",  // optional
        "chunk_type": "function",  // optional
        "use_bm25": true,
        "use_vector": true,
        "use_graph": false,
        "expand_graph_depth": 0,
        "rrf_k": 60,
        "limit": 10
    }

    Returns:
    {
        "data": [
            {
                "id": "<uuid>",
                "name": "calculate_total",
                "source_code": "def calculate_total(...):\n    ...",
                "file_path": "src/calc.py",
                "chunk_type": "function",
                "score": 0.85,
                "metadata": {...}
            }
        ],
        "meta": {
            "total": 10,
            "strategies": {
                "bm25": true,
                "vector": true,
                "graph": false
            },
            "rrf_k": 60
        }
    }
    """
    results = await hybrid_search.search(
        query=request.query,
        language=request.language,
        chunk_type=request.chunk_type,
        use_bm25=request.use_bm25,
        use_vector=request.use_vector,
        use_graph=request.use_graph,
        expand_graph_depth=request.expand_graph_depth,
        rrf_k=request.rrf_k,
        limit=request.limit
    )

    return results
```

**5. Benchmark & Tuning** (2 points)
```python
# scripts/benchmarks/benchmark_hybrid_search.py
async def benchmark_hybrid_search():
    """
    Benchmark hybrid search strategies on CodeSearchNet subset.

    Metrics:
    - Recall@10: % of relevant results in top-10
    - MRR (Mean Reciprocal Rank): average 1/rank of first relevant result
    - Latency P50/P95

    Strategies:
    - BM25 only
    - Vector only
    - Hybrid (BM25+Vector)
    - Hybrid + Graph
    """
    queries = load_codesearchnet_queries(limit=100)

    strategies = [
        {'name': 'BM25', 'use_bm25': True, 'use_vector': False, 'use_graph': False},
        {'name': 'Vector', 'use_bm25': False, 'use_vector': True, 'use_graph': False},
        {'name': 'Hybrid', 'use_bm25': True, 'use_vector': True, 'use_graph': False},
        {'name': 'Hybrid+Graph', 'use_bm25': True, 'use_vector': True, 'use_graph': True, 'expand_graph_depth': 1},
    ]

    for strategy in strategies:
        recall_scores = []
        latencies = []

        for query in queries:
            start = time.time()
            results = await hybrid_search.search(query=query.text, **strategy)
            latency = time.time() - start

            recall = calculate_recall_at_k(results, query.relevant_chunks, k=10)
            recall_scores.append(recall)
            latencies.append(latency)

        print(f"\nStrategy: {strategy['name']}")
        print(f"  Recall@10: {np.mean(recall_scores):.2%}")
        print(f"  Latency P50: {np.percentile(latencies, 50)*1000:.1f}ms")
        print(f"  Latency P95: {np.percentile(latencies, 95)*1000:.1f}ms")
```

---

#### Tests

**Test 1: RRF Fusion**
```python
def test_rrf_fusion():
    service = HybridCodeSearchService(mock_repo, mock_emb, mock_graph)

    # Two result lists with partial overlap
    list1 = [
        CodeChunk(id='A', name='func_a', score=0.9),
        CodeChunk(id='B', name='func_b', score=0.8),
        CodeChunk(id='C', name='func_c', score=0.7),
    ]

    list2 = [
        CodeChunk(id='B', name='func_b', score=0.95),  # Also in list1
        CodeChunk(id='D', name='func_d', score=0.85),
        CodeChunk(id='A', name='func_a', score=0.75),  # Also in list1
    ]

    fused = service.rrf_fusion([list1, list2], k=60)

    # 'B' should rank first (appears in both lists at top ranks)
    assert fused[0].id == 'B'

    # 'A' should be high (appears in both lists)
    assert fused[1].id == 'A'

@pytest.mark.asyncio
async def test_hybrid_search_bm25_only():
    """Test hybrid search with BM25 only."""
    service = HybridCodeSearchService(repo, embedding_service, graph_service)

    results = await service.search(
        query="calculate total",
        use_bm25=True,
        use_vector=False,
        use_graph=False,
        limit=5
    )

    assert len(results.data) > 0
    assert results.meta['strategies']['bm25'] is True
    assert results.meta['strategies']['vector'] is False

@pytest.mark.asyncio
async def test_hybrid_search_fusion():
    """Test hybrid search with BM25+Vector fusion."""
    service = HybridCodeSearchService(repo, embedding_service, graph_service)

    results = await service.search(
        query="function that calculates total price",
        use_bm25=True,
        use_vector=True,
        use_graph=False,
        rrf_k=60,
        limit=10
    )

    assert len(results.data) > 0
    assert results.meta['strategies']['bm25'] is True
    assert results.meta['strategies']['vector'] is True
    assert results.meta['rrf_k'] == 60

    # Check results are ranked
    for i in range(len(results.data) - 1):
        assert results.data[i].score >= results.data[i+1].score

@pytest.mark.asyncio
async def test_hybrid_search_with_graph_expansion():
    """Test hybrid search with graph expansion."""
    service = HybridCodeSearchService(repo, embedding_service, graph_service)

    results = await service.search(
        query="calculate total",
        use_bm25=True,
        use_vector=True,
        use_graph=True,
        expand_graph_depth=1,
        limit=10
    )

    assert len(results.data) > 0
    assert results.meta['strategies']['graph'] is True

    # Check some results are graph-expanded
    expanded_results = [r for r in results.data if r.metadata.get('relation') == 'graph_expanded']
    assert len(expanded_results) > 0
```

---

#### Definition of Done

- ✅ BM25 search via pg_trgm opérationnel
- ✅ RRF fusion implémenté et testé
- ✅ `HybridCodeSearchService` complet (BM25+Vector+Graph)
- ✅ API `/v1/code/search` avec tous paramètres
- ✅ Benchmark exécuté : hybrid vs strategies individuelles
- ✅ Recall@10 : +25% vs vector-only (documenté)
- ✅ Performance : <50ms P95 (hybrid), <80ms (hybrid+graph)
- ✅ Tests unitaires + intégration sur corpus réel
- ✅ Documentation API (OpenAPI) complète

---

## Story 6: Code Indexing Pipeline & API

### US-06-6: Batch Code Indexing with Full Pipeline

**Priority**: 🔴 HAUTE
**Story Points**: 13
**Complexité**: HAUTE
**Dépendances**: Stories 1-4 (tous composants)

#### Description

**En tant que** développeur,
**Je veux** indexer une codebase complète via API (batch de fichiers),
**Afin que** MnemoLite ingère tout mon projet et permette la recherche.

**Pipeline complet** :
```
Input: Files[] →
  1. Language Detection
  2. Tree-sitter Parsing (Story 1)
  3. Semantic Chunking (Story 1)
  4. Metadata Extraction (Story 3)
  5. Dependency Analysis (Story 4)
  6. Embedding Generation (Story 2)
  7. PostgreSQL Storage (code_chunks + nodes + edges)
Output: Indexed Repository
```

**Valeur Métier** :
- API simple pour indexer projets entiers
- Processing batch efficient (parallèle)
- Progress tracking pour UX
- Foundation pour agents IA travaillant sur codebases

---

#### Critères d'Acceptation

**API** :
- ✅ `POST /v1/code/index` : Batch indexing de fichiers
- ✅ `GET /v1/code/index/status/<job_id>` : Progress tracking
- ✅ Support multi-fichiers (jusqu'à 100 fichiers par batch)
- ✅ Async processing avec job queue

**Pipeline** :
- ✅ Processing parallèle (async workers)
- ✅ Error handling robuste (fichiers invalides → skip + log)
- ✅ Transaction DB : rollback si erreur critique
- ✅ Idempotency : ré-indexation = update (pas de doublons)

**Performance** :
- ✅ <500ms par fichier Python moyen (300 LOC)
- ✅ Batch 10 fichiers : <5s total (parallèle)
- ✅ Progress updates : chaque 10% ou 5 secondes

**Documentation** :
- ✅ OpenAPI complète avec exemples
- ✅ Guide utilisateur : comment indexer un projet
- ✅ Error codes documentés

---

#### Tasks Techniques

**1. Code Indexing Service (Orchestrator)** (5 points)
```python
# api/services/code_indexing_service.py
from asyncio import gather

class CodeIndexingService:
    def __init__(
        self,
        chunking_service: CodeChunkingService,
        metadata_service: CodeMetadataService,
        graph_service: GraphAnalysisService,
        embedding_service: EmbeddingService,
        code_chunk_repo: CodeChunkRepository,
        graph_repo: GraphRepository
    ):
        self.chunking_service = chunking_service
        self.metadata_service = metadata_service
        self.graph_service = graph_service
        self.embedding_service = embedding_service
        self.code_chunk_repo = code_chunk_repo
        self.graph_repo = graph_repo

    async def index_repository(
        self,
        repository_name: str,
        files: list[FileInput],
        options: IndexingOptions
    ) -> IndexingResult:
        """
        Index a complete repository (batch of files).

        Pipeline:
        1. Language detection
        2. Chunking (Story 1)
        3. Metadata extraction (Story 3)
        4. Dependency analysis (Story 4)
        5. Embedding generation (Story 2)
        6. Storage

        Args:
            repository_name: Name of the repository
            files: List of files to index
            options: Indexing options

        Returns:
            IndexingResult with stats
        """
        logger.info(f"Starting indexing for repository: {repository_name}")
        start_time = time.time()

        # Process files in parallel
        tasks = [
            self._index_file(file, repository_name, options)
            for file in files
        ]

        results = await gather(*tasks, return_exceptions=True)

        # Aggregate results
        indexed_chunks = 0
        indexed_nodes = 0
        indexed_edges = 0
        errors = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                indexed_chunks += result['chunks']
                indexed_nodes += result['nodes']
                indexed_edges += result['edges']

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(f"Indexing completed: {indexed_chunks} chunks, {indexed_nodes} nodes, {indexed_edges} edges")

        return IndexingResult(
            repository=repository_name,
            indexed_chunks=indexed_chunks,
            indexed_nodes=indexed_nodes,
            indexed_edges=indexed_edges,
            processing_time_ms=processing_time_ms,
            errors=errors
        )

    async def _index_file(
        self,
        file: FileInput,
        repository: str,
        options: IndexingOptions
    ) -> dict:
        """
        Index a single file through complete pipeline.

        Returns:
            {'chunks': int, 'nodes': int, 'edges': int}
        """
        try:
            # Step 1: Language detection
            language = self.chunking_service.detect_language(file.path, file.content)

            # Step 2: Chunking
            chunks = await self.chunking_service.chunk_code(
                source_code=file.content,
                language=language
            )

            # Step 3-6: Process each chunk
            indexed_chunks = 0
            indexed_nodes = 0
            indexed_edges = 0

            for chunk in chunks:
                # Extract metadata
                if options.extract_metadata:
                    metadata = await self.metadata_service.extract_metadata(
                        source_code=chunk.source_code,
                        language=language,
                        chunk_type=chunk.chunk_type,
                        file_path=file.path
                    )
                else:
                    metadata = None

                # Generate embedding
                if options.generate_embeddings:
                    model_type = self.embedding_service.auto_detect_model_type(chunk.chunk_type)
                    embedding = await self.embedding_service.generate_embedding(
                        text=chunk.source_code,
                        model_type=model_type
                    )
                else:
                    embedding = None

                # Store chunk
                stored_chunk = await self.code_chunk_repo.create(
                    file_path=file.path,
                    language=language,
                    chunk_type=chunk.chunk_type,
                    name=chunk.name,
                    source_code=chunk.source_code,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    embedding=embedding,
                    metadata=metadata.dict() if metadata else {},
                    repository=repository
                )

                indexed_chunks += 1

            # Step 7: Dependency analysis (graph)
            if options.analyze_dependencies:
                nodes, edges = await self.graph_service.build_call_graph(
                    source_code=file.content,
                    file_path=file.path,
                    language=language
                )

                # Store graph
                for node in nodes:
                    await self.graph_repo.create_node(node)
                    indexed_nodes += 1

                for edge in edges:
                    await self.graph_repo.create_edge(edge)
                    indexed_edges += 1

            return {
                'chunks': indexed_chunks,
                'nodes': indexed_nodes,
                'edges': indexed_edges
            }

        except Exception as e:
            logger.error(f"Error indexing file {file.path}: {e}")
            raise
```

**2. API Endpoints** (4 points)
```python
# api/routes/code_routes.py
from fastapi import BackgroundTasks

@router.post("/index")
async def index_code(
    request: CodeIndexRequest,
    background_tasks: BackgroundTasks,
    indexing_service: CodeIndexingService = Depends(get_indexing_service)
):
    """
    Index code files (batch).

    Body:
    {
        "repository": "my-project",
        "files": [
            {
                "path": "src/main.py",
                "content": "def main():\n    ..."
            },
            {
                "path": "src/utils.py",
                "content": "def helper():\n    ..."
            }
        ],
        "options": {
            "language": "python",  // optional, auto-detect if null
            "analyze_dependencies": true,
            "extract_metadata": true,
            "generate_embeddings": true
        }
    }

    Returns:
    {
        "repository": "my-project",
        "indexed_chunks": 127,
        "indexed_nodes": 89,
        "indexed_edges": 243,
        "processing_time_ms": 4523,
        "errors": []
    }
    """
    # Validate request
    if len(request.files) > 100:
        raise HTTPException(400, "Max 100 files per batch")

    # Process indexing (async in background for large batches)
    if len(request.files) > 10:
        # Background processing
        job_id = uuid.uuid4()
        background_tasks.add_task(
            _index_in_background,
            job_id,
            request,
            indexing_service
        )
        return {"job_id": job_id, "status": "processing"}

    else:
        # Sync processing (small batches)
        result = await indexing_service.index_repository(
            repository_name=request.repository,
            files=request.files,
            options=request.options
        )
        return result

async def _index_in_background(
    job_id: UUID,
    request: CodeIndexRequest,
    service: CodeIndexingService
):
    """Background task for large indexing jobs."""
    # Store job status in cache/DB
    await redis.set(f"job:{job_id}", json.dumps({"status": "processing"}))

    result = await service.index_repository(
        repository_name=request.repository,
        files=request.files,
        options=request.options
    )

    # Update job status
    await redis.set(f"job:{job_id}", json.dumps({
        "status": "completed",
        "result": result.dict()
    }))

@router.get("/index/status/{job_id}")
async def get_indexing_status(job_id: UUID):
    """
    Get status of background indexing job.

    Returns:
    {
        "job_id": "<uuid>",
        "status": "processing" | "completed" | "failed",
        "result": {...}  // If completed
    }
    """
    status_json = await redis.get(f"job:{job_id}")
    if not status_json:
        raise HTTPException(404, "Job not found")

    status = json.loads(status_json)
    return {"job_id": job_id, **status}
```

**3. Error Handling** (2 points)
```python
class IndexingError(Exception):
    """Base exception for indexing errors."""
    pass

class FileParsingError(IndexingError):
    """Error parsing file (invalid syntax, unsupported language)."""
    pass

class EmbeddingError(IndexingError):
    """Error generating embeddings."""
    pass

# In CodeIndexingService:
async def _index_file(self, file: FileInput, ...) -> dict:
    try:
        # ... indexing pipeline ...
        pass

    except FileParsingError as e:
        logger.warning(f"Skipping file {file.path} due to parsing error: {e}")
        # Continue with other files (don't fail entire batch)
        return {'chunks': 0, 'nodes': 0, 'edges': 0}

    except EmbeddingError as e:
        logger.error(f"Embedding generation failed for {file.path}: {e}")
        # Store chunk without embedding (can regenerate later)
        return {'chunks': 1, 'nodes': 0, 'edges': 0}

    except Exception as e:
        logger.error(f"Critical error indexing {file.path}: {e}")
        raise  # Re-raise for transaction rollback
```

**4. Idempotency (Re-indexation)** (2 points)
```python
# In CodeChunkRepository:
async def upsert_chunk(
    self,
    file_path: str,
    chunk_name: str,
    **kwargs
) -> CodeChunk:
    """
    Upsert chunk: insert if new, update if exists.

    Uniqueness: (file_path, chunk_name, start_line)
    """
    # Check if chunk exists
    existing = await self.get_by_file_and_name(file_path, chunk_name)

    if existing:
        # Update
        await self.update(existing.id, **kwargs)
        return existing
    else:
        # Insert
        return await self.create(file_path=file_path, name=chunk_name, **kwargs)
```

---

#### Tests

**Test 1: Single File Indexing**
```python
@pytest.mark.asyncio
async def test_index_single_file():
    service = CodeIndexingService(...)

    file = FileInput(
        path="test.py",
        content="""
def hello():
    print("Hello")

def world():
    print("World")
"""
    )

    result = await service.index_repository(
        repository_name="test-repo",
        files=[file],
        options=IndexingOptions(
            analyze_dependencies=True,
            extract_metadata=True,
            generate_embeddings=True
        )
    )

    assert result.indexed_chunks == 2  # Two functions
    assert result.indexed_nodes >= 2
    assert result.errors == []

@pytest.mark.asyncio
async def test_index_batch_parallel():
    """Test batch indexing processes files in parallel."""
    service = CodeIndexingService(...)

    files = [
        FileInput(path=f"file_{i}.py", content=f"def func_{i}(): pass")
        for i in range(10)
    ]

    start = time.time()
    result = await service.index_repository("test-repo", files, IndexingOptions())
    elapsed = time.time() - start

    # Should be faster than sequential (10 * 500ms = 5s)
    assert elapsed < 3.0, f"Parallel indexing took {elapsed}s (expected <3s)"
    assert result.indexed_chunks == 10

@pytest.mark.asyncio
async def test_index_with_invalid_file():
    """Test that invalid files are skipped without failing batch."""
    service = CodeIndexingService(...)

    files = [
        FileInput(path="valid.py", content="def valid(): pass"),
        FileInput(path="invalid.py", content="def broken(\n  # missing closing paren"),
        FileInput(path="valid2.py", content="def valid2(): pass"),
    ]

    result = await service.index_repository("test-repo", files, IndexingOptions())

    # Should index 2 valid files, skip 1 invalid
    assert result.indexed_chunks == 2
    assert len(result.errors) == 1

@pytest.mark.asyncio
async def test_reindexing_updates_existing():
    """Test that re-indexing same file updates chunks (no duplicates)."""
    service = CodeIndexingService(...)

    file = FileInput(path="test.py", content="def func(): pass")

    # Index once
    result1 = await service.index_repository("test-repo", [file], IndexingOptions())
    assert result1.indexed_chunks == 1

    # Re-index (update content)
    file.content = "def func():\n    print('updated')\n    pass"
    result2 = await service.index_repository("test-repo", [file], IndexingOptions())

    # Should update, not duplicate
    chunks = await code_chunk_repo.list_by_file("test.py")
    assert len(chunks) == 1  # Still 1 chunk (updated)
    assert "updated" in chunks[0].source_code
```

---

#### Definition of Done

- ✅ `CodeIndexingService` orchestrator complet
- ✅ Pipeline end-to-end : detection → chunking → metadata → graph → embedding → storage
- ✅ API `/v1/code/index` opérationnelle (batch + async)
- ✅ API `/v1/code/index/status/<job_id>` pour progress tracking
- ✅ Error handling robuste (skip invalid files, log errors)
- ✅ Idempotency : re-indexation = update (pas de doublons)
- ✅ Performance : <500ms/file, batch 10 files <5s
- ✅ Tests end-to-end avec repo réel (~100 fichiers Python)
- ✅ Documentation OpenAPI + guide utilisateur
- ✅ Integration avec UI v4.0 (page d'indexation)

---

## 📊 Epic Summary

### Total Story Points: 74

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| US-06-1: Tree-sitter Chunking | 13 | HAUTE | - |
| US-06-2: Nomic Embed Code | 8 | MOYENNE | Story 1 |
| US-06-3: Metadata Extraction | 8 | MOYENNE | Story 1 |
| US-06-4: Dependency Graph | 13 | MOYENNE | Stories 1, 3 |
| US-06-5: Hybrid Search | 21 | HAUTE | Stories 2, 4 |
| US-06-6: Indexing Pipeline | 13 | HAUTE | Stories 1-4 |

### Estimation Timeline

- **Phase 1** (Stories 1-3): 4 semaines
- **Phase 2** (Story 4): 3 semaines
- **Phase 3** (Story 5): 3 semaines
- **Phase 4** (Story 6): 2 semaines

**Total**: 12 semaines (3 mois)

### Success Metrics

- ✅ Précision recherche code : >85% (vs ~60% baseline)
- ✅ Chunking qualité : >80% fonctions complètes
- ✅ Latency hybrid search : <50ms P95
- ✅ Coverage langages : 6+ (Python, JS, TS, Go, Rust, Java)
- ✅ Graph traversal : <20ms depth=2

---

**Date Dernière Mise à Jour**: 2025-10-15
**Statut**: 📋 PLANIFICATION
**Prochaine Action**: Validation stakeholders → Go/No-Go Phase 1
