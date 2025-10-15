# EPIC-06: Plan d'Implémentation Détaillé - Code Intelligence

**Version**: 1.0.0
**Date**: 2025-10-15
**Statut**: 📋 PLANIFICATION APPROFONDIE
**Auteur**: Deep Analysis + Web Research 2024-2025

---

## 🎯 Executive Summary

**Objectif**: Ajouter capacités code intelligence à MnemoLite TOUT EN préservant use case principal (agent memory).

**Stratégie**: Architecture dual-purpose avec tables séparées (`events` + `code_chunks`) et dual embeddings (nomic-text + jina-code).

**Durée totale**: **13 semaines** (1 semaine Phase 0 + 12 semaines Phases 1-4)

**Story points total**: **74 points** (Phase 0: 8pts, Phase 1-4: 66pts)

**Complexité**: ⭐⭐⭐⭐⚪ (4/5 - HAUTE)

---

## ⚠️ Contraintes Critiques Validées

### Contraintes Techniques
- ✅ **PostgreSQL 18 only**: Pas d'autres DB, pas de services externes
- ✅ **100% local**: Aucune dépendance cloud/API (embeddings locaux)
- ✅ **CPU-friendly**: Déploiement sans GPU requis
- ✅ **RAM budget**: Total embeddings < 1 GB (target: ~700 MB)
- ✅ **768D embeddings**: Compatibilité infrastructure existante (pas de migration DB!)
- ✅ **Async-first**: SQLAlchemy 2.0 async, asyncpg
- ✅ **Backward compatible**: Table `events` intacte, API v1 sans breaking changes

### Contraintes Fonctionnelles
- ✅ **Use case principal**: Agent memory (conversations, docs) doit rester fonctionnel
- ✅ **Use case nouveau**: Code intelligence (indexation, search, graph)
- ✅ **Architecture**: Tables séparées pour séparation claire des concerns

---

## 🔬 Recherches & Validations Techniques

### 1. Tree-sitter Integration (Validé 2024)

**Package recommandé**: `tree-sitter-languages` (pre-compiled wheels)

**Avantages**:
- Pas de compilation manuelle requise
- Wheels pré-compilés pour toutes plateformes
- Support multi-langages out-of-the-box
- Utilisé par CodeTF (Salesforce) - production-ready

**Pattern d'intégration**:
```python
from tree_sitter_languages import get_parser, get_language

parser = get_parser('python')
tree = parser.parse(bytes(source_code, 'utf8'))
```

**Langages prioritaires**: Python, JavaScript, TypeScript, Go, Rust, Java

**Référence**: https://pypi.org/project/tree-sitter-languages/

---

### 2. Dual Embeddings Memory Management (Validé 2024)

**Stratégie**: Chargement simultané de 2 modèles sentence-transformers

**Modèles**:
1. `nomic-ai/nomic-embed-text-v1.5` (137M params, ~260 MB RAM)
2. `jinaai/jina-embeddings-v2-base-code` (161M params, ~400 MB RAM)

**Total RAM**: ~700 MB (sous budget 1 GB)

**Optimisations possibles**:
- FP16 precision: -50% RAM (non requis pour notre budget)
- Batch processing: 32-64 samples/batch (optimal CPU)
- Lazy loading: Charger modèles seulement quand nécessaire

**Pattern d'implémentation**:
```python
class EmbeddingService:
    def __init__(self):
        self.text_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5")
        self.code_model = SentenceTransformer("jinaai/jina-embeddings-v2-base-code")

    async def generate_embedding(self, text: str, domain: EmbeddingDomain):
        if domain == EmbeddingDomain.TEXT:
            return self.text_model.encode(text).tolist()
        elif domain == EmbeddingDomain.CODE:
            return self.code_model.encode(text).tolist()
        elif domain == EmbeddingDomain.HYBRID:
            return {
                'text': self.text_model.encode(text).tolist(),
                'code': self.code_model.encode(text).tolist()
            }
```

**Référence**: https://milvus.io/ai-quick-reference/how-can-you-reduce-the-memory-footprint-of-sentence-transformer-models

---

### 3. BM25-like Search PostgreSQL (⚠️ CRITIQUE)

**Découverte importante**: PostgreSQL natif **NE SUPPORTE PAS BM25**!

**Raison**: Algorithmes BM25/TF-IDF nécessitent statistiques globales (fréquence termes corpus) non disponibles dans ranking functions PostgreSQL.

**Alternatives validées**:

#### Option A: pg_trgm Similarity (RECOMMANDÉ Phase 1-2)
```sql
-- Extension native PostgreSQL
CREATE EXTENSION pg_trgm;

-- Index trigram
CREATE INDEX idx_code_source_trgm ON code_chunks USING gin (source_code gin_trgm_ops);

-- Requête similarity
SELECT id, name, source_code,
       similarity(source_code, 'query text') AS score
FROM code_chunks
WHERE source_code % 'query text'  -- % operator = similarity match
ORDER BY score DESC
LIMIT 10;
```

**Avantages**:
- ✅ Extension native PostgreSQL (déjà disponible)
- ✅ Pas de dépendances externes
- ✅ Excellent pour fuzzy matching (typos)
- ✅ Performance correcte avec index GIN

**Limites**:
- ⚠️ Pas de TF-IDF (pas de poids par terme)
- ⚠️ Similarité simple (pas de ranking BM25)

#### Option B: PostgreSQL Full-Text Search (tsvector)
```sql
-- Index full-text
CREATE INDEX idx_code_source_fts ON code_chunks USING gin (to_tsvector('english', source_code));

-- Requête FTS
SELECT id, name, source_code,
       ts_rank(to_tsvector('english', source_code), to_tsquery('function & calculate')) AS rank
FROM code_chunks
WHERE to_tsvector('english', source_code) @@ to_tsquery('function & calculate')
ORDER BY rank DESC;
```

**Avantages**:
- ✅ Ranking natif (ts_rank, ts_rank_cd)
- ✅ Support opérateurs booléens (AND, OR, NOT)

**Limites**:
- ⚠️ Optimisé pour texte naturel (pas code)
- ⚠️ Stemming problématique pour code

#### Option C: Extensions BM25 Externes (Évaluation Phase 3)

1. **pg_search (ParadeDB)**: Extension Rust, vrai BM25 complet
   - Référence: https://blog.paradedb.com/pages/introducing_search
   - ⚠️ Dépendance externe (compilation Rust)
   - ⚠️ Intégration complète (BM25 + hybrid intégré)

2. **VectorChord-BM25 (TensorChord)**: Rust extension, vrai BM25 avec Block-WeakAnd
   - Référence: https://github.com/tensorchord/VectorChord
   - ⚠️ Dépendance externe (compilation Rust)
   - ✅ Performance excellente (Block-WeakAnd = early termination)
   - ⚠️ Moins mature que pgvector

3. **plpgsql_bm25**: Implémentation BM25 pure PL/pgSQL
   - Référence: https://github.com/paradedb/paradedb/discussions/1584
   - ✅ **Aucune compilation** (pure SQL)
   - ✅ **Aucune dépendance externe** (PostgreSQL natif uniquement)
   - ⚠️ Performance moyenne (PL/pgSQL plus lent que Rust)
   - ⚠️ Calcul TF/IDF manuel requis (tables statistiques)

**DÉCISION ARCHITECTURE**:
- **Phase 1-2**: Utiliser **pg_trgm similarity** (simple, natif, performant)
- **Phase 3 (v1.4.0)**: Hybrid search = pg_trgm (lexical) + pgvector (semantic) + RRF fusion
- **Post-Phase 3 Benchmark**: Évaluer alternatives BM25 si **Recall@10 < 80%**
  - **Option préférée**: plpgsql_bm25 (pur SQL, respect contrainte "PostgreSQL natif")
  - **Option performance**: VectorChord-BM25 (si dépendances externes acceptées)
  - **Option complète**: pg_search/ParadeDB (si BM25 + hybrid intégré souhaité)

**Références**:
- Hybrid Search PostgreSQL: https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/
- VectorChord-BM25: https://github.com/tensorchord/VectorChord
- plpgsql_bm25: https://github.com/paradedb/paradedb/discussions/1584
- pg_search: https://blog.paradedb.com/pages/introducing_search

---

### 4. Alembic Migrations Async (Validé 2024)

**Setup initial**:
```bash
# Initialiser avec template async
alembic init -t async migrations

# Configuration env.py
from sqlalchemy.ext.asyncio import create_async_engine

async def run_async_migrations():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

**Pattern ajout nouvelle table**:
```python
# alembic revision --autogenerate -m "Add code_chunks table"

def upgrade() -> None:
    op.create_table(
        'code_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('language', sa.Text(), nullable=False),
        sa.Column('source_code', sa.Text(), nullable=False),
        sa.Column('embedding_text', pgvector.sqlalchemy.Vector(768)),
        sa.Column('embedding_code', pgvector.sqlalchemy.Vector(768)),
        sa.Column('metadata', postgresql.JSONB()),
        sa.PrimaryKeyConstraint('id')
    )

    # Index HNSW
    op.execute("""
        CREATE INDEX idx_code_embedding_text ON code_chunks
        USING hnsw (embedding_text vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    op.execute("""
        CREATE INDEX idx_code_embedding_code ON code_chunks
        USING hnsw (embedding_code vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

def downgrade() -> None:
    op.drop_table('code_chunks')
```

**⚠️ ATTENTION**: Toujours **review manually** les migrations autogenerées!

**Référence**: https://testdriven.io/blog/fastapi-sqlmodel/

---

## 📊 Architecture Finale Validée

### Schéma DB

```sql
-- Table 1: events (INCHANGÉE - agent memory)
CREATE TABLE events (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    content JSONB NOT NULL,
    embedding VECTOR(768),  -- nomic-embed-text-v1.5 uniquement
    metadata JSONB
);

-- Index existants (pas de changement)
CREATE INDEX idx_events_embedding ON events
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_events_metadata_gin ON events USING gin (metadata jsonb_path_ops);
CREATE INDEX idx_events_timestamp ON events (timestamp);

---

-- Table 2: code_chunks (NOUVELLE - code intelligence)
CREATE TABLE code_chunks (
    -- Identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,  -- 'python', 'javascript', 'typescript', etc.
    chunk_type TEXT NOT NULL,  -- 'function', 'class', 'method', 'module'
    name TEXT,  -- Nom fonction/classe

    -- Contenu
    source_code TEXT NOT NULL,
    start_line INT,
    end_line INT,

    -- Dual embeddings (768D chacun!)
    embedding_text VECTOR(768),  -- nomic-text (docstrings, comments)
    embedding_code VECTOR(768),  -- jina-code (code sémantique)

    -- Métadonnées code
    metadata JSONB NOT NULL,  -- {complexity, params, returns, docstring, tests, etc.}

    -- Timestamps
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    last_modified TIMESTAMPTZ,

    -- Relations
    node_id UUID,  -- Lien vers nodes table (graph)
    repository TEXT,
    commit_hash TEXT
);

-- Index HNSW pour dual embeddings
CREATE INDEX idx_code_embedding_text ON code_chunks
USING hnsw (embedding_text vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_code_embedding_code ON code_chunks
USING hnsw (embedding_code vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Index GIN métadonnées
CREATE INDEX idx_code_metadata ON code_chunks USING gin (metadata jsonb_path_ops);

-- Index B-tree filtrage
CREATE INDEX idx_code_language ON code_chunks (language);
CREATE INDEX idx_code_type ON code_chunks (chunk_type);
CREATE INDEX idx_code_file ON code_chunks (file_path);
CREATE INDEX idx_code_indexed_at ON code_chunks (indexed_at);

-- Index trigram pour pg_trgm similarity search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_code_source_trgm ON code_chunks USING gin (source_code gin_trgm_ops);
CREATE INDEX idx_code_name_trgm ON code_chunks USING gin (name gin_trgm_ops);
```

### Services Layer

```python
# api/services/embedding_service.py
from enum import Enum
from sentence_transformers import SentenceTransformer

class EmbeddingDomain(str, Enum):
    TEXT = "text"      # Conversations, docs, general text
    CODE = "code"      # Code snippets, functions, classes
    HYBRID = "hybrid"  # Generate both (for code with docstrings)

class EmbeddingService:
    def __init__(self, settings):
        # Model 1: General text (existing, ~260 MB)
        self.text_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        # "nomic-ai/nomic-embed-text-v1.5"

        # Model 2: Code specialized (new, ~400 MB)
        self.code_model = SentenceTransformer(settings.CODE_EMBEDDING_MODEL)
        # "jinaai/jina-embeddings-v2-base-code"

        logger.info(f"Dual embeddings loaded: ~{self._estimate_ram()}MB total")

    def _estimate_ram(self) -> int:
        """Estimate total RAM usage (MB)."""
        return 260 + 400  # ~700 MB

    async def generate_embedding(
        self,
        text: str,
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> dict[str, list[float]]:
        """
        Generate embedding(s) based on domain.

        Returns:
            - TEXT domain: {'text': [...768D...]}
            - CODE domain: {'code': [...768D...]}
            - HYBRID domain: {'text': [...768D...], 'code': [...768D...]}
        """
        result = {}

        if domain in [EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID]:
            emb = self.text_model.encode(text, convert_to_tensor=False)
            result['text'] = emb.tolist()

        if domain in [EmbeddingDomain.CODE, EmbeddingDomain.HYBRID]:
            emb = self.code_model.encode(text, convert_to_tensor=False)
            result['code'] = emb.tolist()

        return result
```

```python
# api/services/code_chunking_service.py
from tree_sitter_languages import get_parser, get_language

class CodeChunkingService:
    def __init__(self):
        self.parsers = {
            'python': get_parser('python'),
            'javascript': get_parser('javascript'),
            'typescript': get_parser('typescript'),
            'go': get_parser('go'),
            'rust': get_parser('rust'),
            'java': get_parser('java')
        }

    async def chunk_code(
        self,
        source_code: str,
        language: str,
        max_chunk_size: int = 2000
    ) -> list[CodeChunk]:
        """
        Semantic chunking via AST (cAST algorithm inspired).

        Algorithm:
        1. Parse code → AST
        2. Identify code units (functions, classes, methods)
        3. Split large units recursively
        4. Merge small adjacent chunks
        5. Fallback to fixed chunking if parsing fails
        """
        try:
            parser = self.parsers.get(language)
            if not parser:
                logger.warning(f"No parser for {language}, falling back to fixed chunking")
                return self._fallback_chunking(source_code, max_chunk_size)

            tree = parser.parse(bytes(source_code, 'utf8'))
            code_units = self._identify_code_units(tree, language)

            chunks = []
            for unit in code_units:
                if unit.size <= max_chunk_size:
                    chunks.append(self._create_chunk(unit))
                else:
                    # Split recursively
                    sub_chunks = self._split_large_unit(unit, max_chunk_size)
                    chunks.extend(sub_chunks)

            # Merge small adjacent chunks
            merged = self._merge_small_chunks(chunks, min_size=100)
            return merged

        except Exception as e:
            logger.error(f"AST chunking failed: {e}, fallback to fixed")
            return self._fallback_chunking(source_code, max_chunk_size)
```

---

## 📋 Plan d'Implémentation Détaillé

### **PHASE 0: Infrastructure Setup (1 semaine)**

**Objectif**: Préparer infrastructure sans casser l'existant

**Story Points**: 8

#### Story 0.1: Alembic Async Setup (3 points)

**Tasks**:
1. ✅ Initialiser Alembic avec template async
   ```bash
   cd /home/giak/Work/MnemoLite
   alembic init -t async alembic
   ```

2. ✅ Configurer `alembic.ini`
   - `sqlalchemy.url` = DATABASE_URL async (postgresql+asyncpg)
   - Script location
   - File template

3. ✅ Configurer `alembic/env.py`
   - Import `AsyncEngine`
   - Pattern `run_sync` pour migrations
   - Import metadata `Base.metadata`

4. ✅ Créer migration initiale baseline
   ```bash
   alembic revision --autogenerate -m "Baseline: existing events table"
   ```

5. ✅ Tester migration up/down
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

**Acceptance Criteria**:
- ✅ Alembic initialisé avec template async
- ✅ Migration baseline créée et appliquée
- ✅ Tests migration up/down passent
- ✅ Pas de régression sur table `events` existante

**Dépendances**:
- SQLAlchemy 2.0 async (déjà installé)
- asyncpg (déjà installé)
- alembic (à ajouter requirements.txt)

---

#### Story 0.2: Dual Embeddings Service (5 points)

**Tasks**:
1. ✅ Ajouter dépendances `requirements.txt`
   ```
   sentence-transformers>=2.7.0
   tree-sitter-languages>=1.10.0  # Pour Phase 1
   ```

2. ✅ Étendre `EmbeddingService` avec dual models
   - Créer enum `EmbeddingDomain(TEXT, CODE, HYBRID)`
   - Ajouter `self.code_model`
   - Méthode `generate_embedding(text, domain)`
   - Méthode `_estimate_ram()`

3. ✅ Ajouter variables environnement `.env.example`
   ```env
   # Embeddings (existing)
   EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
   EMBEDDING_DIMENSION=768

   # Code embeddings (new)
   CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
   ```

4. ✅ Tests unitaires dual embeddings
   - Test chargement 2 modèles
   - Test dimensions 768D identiques
   - Test domains TEXT/CODE/HYBRID
   - Test RAM usage < 1 GB

5. ✅ Benchmark local
   - Latence génération (TEXT vs CODE vs HYBRID)
   - RAM usage réel (psutil)
   - Comparer similarity (text vs code embeddings sur code snippet)

**Acceptance Criteria**:
- ✅ `EmbeddingService` supporte dual models
- ✅ Enum `EmbeddingDomain` implémenté
- ✅ Tests unitaires passent (coverage >85%)
- ✅ Benchmark: RAM < 1 GB, latence < 100ms
- ✅ Documentation `.env.example` mise à jour

**Dépendances**:
- sentence-transformers 2.7+
- Variables environnement CODE_EMBEDDING_MODEL

---

### **PHASE 1: Foundation Code (4 semaines)**

**Objectif**: Chunking + Dual Embeddings + Metadata + Table code_chunks

**Story Points**: 31 (13 + 5 + 8 + 5)

#### Story 1: Tree-sitter Integration & AST Chunking (13 points)

**Complexité**: HAUTE
**Durée estimée**: 2 semaines

**Tasks**:
1. ✅ Setup tree-sitter-languages
   - Installation `tree-sitter-languages`
   - Vérification parsers disponibles (Python, JS, TS, Go, Rust, Java)

2. ✅ Implémenter `CodeChunkingService`
   - Détection langage (extension fichier)
   - Parsing AST via tree-sitter
   - Identification code units (functions, classes, methods)
   - Algorithme split-then-merge (inspiré cAST paper)
   - Fallback chunking fixe si parsing échoue

3. ✅ Créer modèles Pydantic
   - `CodeChunk` (source_code, chunk_type, name, start_line, end_line, etc.)
   - `CodeUnit` (intermédiaire AST)

4. ✅ Tests unitaires
   - Test Python function chunking
   - Test JavaScript class chunking
   - Test TypeScript methods
   - Test large function split (>2000 chars)
   - Test small chunks merge (<100 chars)
   - Test fallback on invalid syntax
   - Test performance (<100ms pour 300 LOC)

5. ✅ Documentation technique
   - Docstrings complètes
   - README: comment ajouter nouveau langage
   - ADR: pourquoi tree-sitter vs alternatives

**Acceptance Criteria**:
- ✅ Tree-sitter intégré (6+ langages)
- ✅ >80% chunks = fonctions/classes complètes
- ✅ Performance <100ms pour fichier 300 LOC
- ✅ Tests coverage >85%
- ✅ Fallback robuste sur erreurs parsing

**Dépendances**:
- tree-sitter-languages 1.10+

**Références**:
- cAST paper (arxiv 2024): 82% amélioration précision
- CodeTF: utilise tree-sitter comme core parser

---

#### Story 2: Dual Embeddings Integration (5 points - RÉDUIT)

**Complexité**: MOYENNE
**Durée estimée**: 1 semaine

**Tasks**:
1. ✅ Validation Setup Phase 0
   - Vérifier dual models chargés
   - Vérifier RAM < 1 GB

2. ✅ Benchmark production
   - CodeSearchNet subset (100 queries)
   - Comparer nomic-text vs jina-code sur code
   - Mesurer Recall@10, latence, RAM

3. ✅ Documentation
   - Guide utilisation domains (TEXT/CODE/HYBRID)
   - Benchmark report (résultats chiffrés)
   - ADR: pourquoi jina-code vs nomic-code

**Acceptance Criteria**:
- ✅ Benchmark nomic-text vs jina-code documenté
- ✅ RAM total < 1 GB validé
- ✅ Dimensions 768D identiques validées
- ✅ Documentation complète

**Dépendances**:
- Phase 0 Story 0.2 complétée

---

#### Story 2bis: Code Chunks Table & Repository (5 points)

**Complexité**: MOYENNE
**Durée estimée**: 1 semaine

**Tasks**:
1. ✅ Migration Alembic `code_chunks` table
   ```bash
   alembic revision --autogenerate -m "Add code_chunks table"
   ```
   - Review manual migration
   - Ajouter index HNSW (embedding_text, embedding_code)
   - Ajouter index GIN (metadata)
   - Ajouter index B-tree (language, chunk_type, file_path)
   - Ajouter index trigram (source_code, name)

2. ✅ Implémenter `CodeChunkRepository`
   - CRUD operations (create, get_by_id, update, delete)
   - `filter_by_metadata()`
   - `search_vector()` avec support dual embeddings
   - `search_similarity()` avec pg_trgm

3. ✅ Créer modèles Pydantic
   - `CodeChunkModel` (DB representation)
   - `CodeChunkCreate` (input)
   - `CodeChunkUpdate` (patch)

4. ✅ Tests intégration PostgreSQL
   - Test CRUD operations
   - Test vector search (embedding_text vs embedding_code)
   - Test metadata filtering
   - Test pg_trgm similarity

**Acceptance Criteria**:
- ✅ Table `code_chunks` créée via migration
- ✅ Repository implémenté (coverage >85%)
- ✅ Tests intégration PostgreSQL passent
- ✅ Index HNSW opérationnels (vérifier EXPLAIN ANALYZE)

**Dépendances**:
- Phase 0 Story 0.1 (Alembic setup)
- pgvector extension (déjà installé)
- pg_trgm extension

---

#### Story 3: Code Metadata Extraction (8 points)

**Complexité**: MOYENNE
**Durée estimée**: 1-2 semaines

**Tasks**:
1. ✅ Implémenter `CodeMetadataService`
   - Extraction signature (params, returns, type hints)
   - Extraction docstring (Google/NumPy/Sphinx styles)
   - Calcul complexité (cyclomatic via `radon`, LOC, cognitive)
   - Extraction imports
   - Extraction calls (fonctions appelées)
   - Extraction decorators
   - Détection tests (has_tests, test_files)

2. ✅ Ajouter dépendance `radon`
   ```
   radon>=6.0.1  # Complexité Python
   ```

3. ✅ Créer modèle `CodeMetadata` (Pydantic)
   ```python
   class CodeMetadata(BaseModel):
       language: str
       chunk_type: str
       name: str
       signature: Optional[str]
       parameters: list[str]
       returns: Optional[str]
       docstring: Optional[str]
       complexity: dict  # {cyclomatic, lines_of_code, cognitive}
       imports: list[str]
       calls: list[str]
       decorators: list[str]
       has_tests: bool
       test_files: list[str]
       last_modified: Optional[datetime]
   ```

4. ✅ Tests unitaires
   - Test Python function metadata
   - Test JavaScript class metadata
   - Test complexity calculation
   - Test docstring parsing (Google style)
   - Test decorator extraction

**Acceptance Criteria**:
- ✅ Métadonnées extraites sur >90% fonctions Python
- ✅ Performance <20ms par chunk
- ✅ Tests coverage >85%
- ✅ Support multi-langages (Python prioritaire)

**Dépendances**:
- Story 1 (chunking)
- radon 6.0+

---

### **PHASE 2: Graph Intelligence (3 semaines)**

**Objectif**: Call graph + dependency analysis

**Story Points**: 13

#### Story 4: Dependency Graph Construction (13 points)

**Complexité**: HAUTE
**Durée estimée**: 3 semaines

**Tasks**:
1. ✅ Implémenter `GraphAnalysisService`
   - Static analysis call graph (Python via `ast`)
   - Import graph
   - Extraction data flow (variable usages)

2. ✅ Extension tables `nodes` / `edges`
   - `ALTER TABLE nodes ADD COLUMN code_metadata JSONB`
   - `ALTER TABLE edges ADD COLUMN call_frequency INT DEFAULT 0`

3. ✅ Repository `GraphRepository`
   - `create_node()`
   - `create_edge()`
   - `get_graph(from_node, relationship, direction, depth)`
   - Requêtes CTE récursives (≤3 hops)

4. ✅ API endpoints
   - `GET /v1/code/graph?from=<uuid>&relationship=calls&direction=outbound&depth=2`

5. ✅ Tests
   - Test call graph Python (~500 functions)
   - Test import graph
   - Test CTE récursifs (depth 1, 2, 3)
   - Test visualisation JSON

**Acceptance Criteria**:
- ✅ Call graph extraction opérationnel
- ✅ CTE récursifs ≤3 hops
- ✅ API endpoint fonctionnel
- ✅ Tests avec codebase réelle

**Dépendances**:
- Story 2bis (code_chunks table)
- Tables nodes/edges existantes

**Références**:
- Python `ast` module (stdlib)
- Tree-sitter queries pour autres langages

---

### **PHASE 3: Hybrid Search (3 semaines)**

**Objectif**: pg_trgm + Vector + RRF fusion

**Story Points**: 21

#### Story 5: Hybrid Search (BM25-like + Vector + Graph) (21 points)

**Complexité**: HAUTE
**Durée estimée**: 3 semaines

**Tasks**:
1. ✅ Setup pg_trgm
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   CREATE INDEX idx_code_source_trgm ON code_chunks USING gin (source_code gin_trgm_ops);
   ```

2. ✅ Implémenter `HybridCodeSearchService`
   - `_pg_trgm_search()` (lexical similarity)
   - `_vector_search()` (semantic via HNSW)
   - `_rrf_fusion()` (Reciprocal Rank Fusion, k=60)
   - `_expand_with_graph()` (optionnel, depth 0-3)

3. ✅ Méthode RRF
   ```python
   def _rrf_fusion(self, list1, list2, k=60) -> list:
       """
       RRF score = 1 / (rank + k)
       Combine scores from multiple result lists.
       """
       scores = {}
       for rank, item in enumerate(list1, 1):
           scores[item.id] = scores.get(item.id, 0) + 1 / (rank + k)
       for rank, item in enumerate(list2, 1):
           scores[item.id] = scores.get(item.id, 0) + 1 / (rank + k)

       sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
       return [self._get_item(id) for id, score in sorted_items]
   ```

4. ✅ API endpoint
   - `POST /v1/code/search`
   - Paramètres: query, language, chunk_type, use_trgm, use_vector, use_graph, limit

5. ✅ Benchmark
   - Recall pg_trgm vs vector vs hybrid
   - Latency P95 (<50ms target)

6. ✅ Tests
   - Test pg_trgm search
   - Test vector search
   - Test RRF fusion
   - Test graph expansion
   - Test end-to-end hybrid

**Acceptance Criteria**:
- ✅ pg_trgm search opérationnel
- ✅ Vector search via HNSW
- ✅ RRF fusion implémenté
- ✅ Graph expansion optionnel
- ✅ Benchmark recall +X% vs vector-only
- ✅ Latency P95 <50ms (10k chunks)

**Dépendances**:
- Story 2bis (code_chunks table)
- Story 4 (graph)
- pg_trgm extension

**⚠️ NOTE CRITIQUE**: Pas de vrai BM25, utiliser pg_trgm similarity comme proxy lexical. Évaluer extensions BM25 (pg_search, VectorChord) post-v1.4.0 si qualité insuffisante.

**Références**:
- https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/
- RRF algorithm: 1/(rank+k)

---

### **PHASE 4: API & Integration (2 semaines)**

**Objectif**: Pipeline complet + documentation

**Story Points**: 13

#### Story 6: Code Indexing Pipeline & API (13 points)

**Complexité**: HAUTE
**Durée estimée**: 2 semaines

**Tasks**:
1. ✅ Implémenter `CodeIndexingService`
   - Pipeline: Language Detection → AST Parsing → Chunking → Metadata Extraction → Dependency Analysis → Embedding Generation → DB Storage
   - Batch processing (plusieurs fichiers)
   - Error handling robuste
   - Progress tracking

2. ✅ API endpoints
   ```python
   # POST /v1/code/index
   {
     "repository": "my-project",
     "files": [
       {"path": "src/main.py", "content": "..."},
       {"path": "src/utils.py", "content": "..."}
     ],
     "options": {
       "language": "python",
       "analyze_dependencies": true,
       "extract_metadata": true,
       "generate_embeddings": true
     }
   }

   # Response
   {
     "indexed_chunks": 127,
     "indexed_nodes": 89,
     "indexed_edges": 243,
     "processing_time_ms": 4523,
     "repository_id": "<uuid>"
   }
   ```

3. ✅ Documentation OpenAPI
   - `/v1/code/index` (POST)
   - `/v1/code/search` (GET)
   - `/v1/code/graph` (GET)

4. ✅ Tests end-to-end
   - Test indexing repo réel (~100 fichiers Python)
   - Test error handling (fichiers invalides)
   - Test rate limiting

5. ✅ UI v4.0 integration
   - Page code search
   - Page graph visualization

**Acceptance Criteria**:
- ✅ Endpoint `/v1/code/index` opérationnel
- ✅ Support batch indexing
- ✅ Error handling robuste
- ✅ Documentation OpenAPI complète
- ✅ Tests end-to-end passent

**Dépendances**:
- Stories 1-5 complétées

---

## 📊 Métriques de Succès

### Performance

| Métrique | Baseline | Target Phase 4 | Mesure |
|----------|----------|----------------|---------|
| **Indexing** | N/A | <500ms/file (300 LOC) | P95 |
| **Search hybrid** | N/A | <50ms | P95 (10k chunks) |
| **Graph traversal** | N/A | <20ms (depth=2) | P95 |
| **RAM embeddings** | 262 MB | <1 GB | Total (nomic-text + jina-code) |

### Qualité

| Métrique | Target | Mesure |
|----------|--------|--------|
| **Code chunking quality** | >80% fonctions complètes | % chunks sémantiques valides |
| **Search recall** | >85% | Recall@10 sur CodeSearchNet |
| **Metadata extraction** | >90% | % fonctions avec metadata complète |
| **Tests coverage** | >85% | pytest-cov sur nouveaux modules |

### Backward Compatibility

| Métrique | Target | Validation |
|----------|--------|------------|
| **Events API** | 0 breaking changes | Tests regression v1 API |
| **Events search** | Performance maintenue | Latency ≤ baseline |
| **Database migrations** | Réversibles | Alembic downgrade fonctionne |

---

## 🚧 Risques & Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Tree-sitter complexité** | Moyen | Haut | PoC Python d'abord, fallback chunking fixe |
| **Dual embeddings RAM overflow** | Faible | Moyen | Monitoring RAM, quantization si besoin |
| **pg_trgm insuffisant** | Moyen | Moyen | Benchmark vs vector, évaluer pg_search extension |
| **Graph traversal lent** | Moyen | Moyen | Limiter depth ≤3, index sur edges, CTE optimisés |
| **Breaking changes accidentels** | Faible | Haut | Tests regression automatiques, review PRs |
| **Scope creep** | Haut | Moyen | Stick to 6 stories, reporter features v1.5.0 |

---

## ✅ Checklist Pre-Implementation

### Infrastructure
- [ ] Alembic initialisé avec template async
- [ ] Dual embeddings service testé (RAM < 1 GB)
- [ ] Variables environnement configurées
- [ ] Extensions PostgreSQL vérifiées (pgvector, pg_trgm)

### Code Quality
- [ ] Tests coverage target défini (>85%)
- [ ] Linters configurés (ruff, mypy)
- [ ] Pre-commit hooks actifs
- [ ] CI/CD pipeline prêt

### Documentation
- [ ] README mis à jour (section Code Intelligence)
- [ ] API docs OpenAPI prêtes
- [ ] ADRs rédigées (tree-sitter, jina-code, pg_trgm)

### Team Alignment
- [ ] Plan validé par stakeholders
- [ ] Ressources allouées (13 semaines)
- [ ] Priorités claires (backward compatibility critical)

---

## 📚 Références Clés

### Papers & Research
- cAST: Chunking via Abstract Syntax Trees (arxiv 2024, ICLR 2025)
- jina-embeddings-v2-base-code (Jina AI, Lead 9/15 CodeSearchNet)
- Hybrid Search with PostgreSQL and pgvector (Jonathan Katz, 2024)

### Libraries & Tools
- tree-sitter-languages: https://pypi.org/project/tree-sitter-languages/
- sentence-transformers: https://huggingface.co/sentence-transformers
- radon: https://github.com/rubik/radon
- alembic: https://alembic.sqlalchemy.org/

### PostgreSQL Extensions
- pgvector: https://github.com/pgvector/pgvector
- pg_trgm: https://www.postgresql.org/docs/current/pgtrgm.html
- (Évaluation future) pg_search: https://blog.paradedb.com/pages/introducing_search

---

**Date**: 2025-10-15
**Version**: 1.0.0
**Statut**: ✅ PLAN VALIDÉ - PRÊT POUR KICKOFF PHASE 0

**Prochaine Action**: Validation stakeholders → Kickoff Phase 0 Story 0.1 (Alembic Setup)
