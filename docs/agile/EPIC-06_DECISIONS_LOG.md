# EPIC-06: Log des Décisions Techniques (ADR)

**Version**: 1.0.0
**Date**: 2025-10-15
**Format**: Architecture Decision Records (ADR)

---

## ADR-001: Architecture Dual-Purpose (Tables Séparées)

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

MnemoLite est actuellement une mémoire pour agents IA (conversations, documentation). EPIC-06 ajoute capacités code intelligence. Besoin d'architecture supportant les deux use cases sans conflit.

### Options Considérées

#### Option A: Extension Table Events
```sql
ALTER TABLE events ADD COLUMN embedding_code VECTOR(768);
ALTER TABLE events ADD COLUMN content_type TEXT;
```

**Avantages**:
- Simple (une seule table)
- Backward compatible

**Inconvénients**:
- ❌ Mixing concerns (events ≠ code chunks)
- ❌ Schema rigide
- ❌ `embedding_code` NULL pour 99% events (waste)
- ❌ Pas de metadata code spécifique

#### Option B: Tables Séparées ⭐ CHOISIE
```sql
-- events: agent memory (inchangé)
-- code_chunks: code intelligence (nouveau)
```

**Avantages**:
- ✅ Séparation claire des concerns
- ✅ Schemas optimisés par use case
- ✅ Backward compatibility totale
- ✅ Dual embeddings sur code seulement
- ✅ Évolutivité (facile ajouter: images, audio)

**Inconvénients**:
- ⚠️ Recherche unifiée = 2 requêtes + merge (acceptable)

#### Option C: Table Unifiée memory_items
```sql
CREATE TABLE memory_items (
    item_type TEXT,  -- 'event', 'code_chunk', ...
    embedding_text VECTOR(768),
    embedding_code VECTOR(768)
);
```

**Avantages**:
- ✅ Flexible (futurs types)

**Inconvénients**:
- ❌ Migration lourde (rewrite events)
- ❌ Breaking change majeur
- ❌ Schema generic = perte spécificité

### Décision

**Option B: Tables Séparées**

**Justification**:
- Preserve backward compatibility (critique)
- Séparation claire use cases
- Performance optimale (index HNSW dédiés)
- Évolutivité future

**Conséquences**:
- Besoin `UnifiedSearchService` pour merge résultats
- Migration Alembic simple (CREATE TABLE)
- Tests isolation (events vs code_chunks)

---

## ADR-002: Embeddings Code - jina-embeddings-v2-base-code

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

Besoin d'embeddings spécialisés code. Contraintes: 768D (pas de migration DB), RAM <1GB total, CPU-friendly, local.

### Options Considérées

#### Option A: nomic-embed-code
- **Params**: 7B
- **Dimensions**: 768D
- **RAM**: ~14 GB (full), ~7 GB (INT8 quantized)
- **Performance**: SOTA CodeSearchNet (ICLR 2025)
- **Verdict**: ❌ **Trop lourd** pour contraintes MnemoLite

#### Option B: jina-embeddings-v2-base-code ⭐ CHOISIE
- **Params**: 161M
- **Dimensions**: 768D (natif)
- **RAM**: ~400 MB
- **Performance**: Lead 9/15 CodeSearchNet benchmarks
- **Total système**: nomic-text (137M) + jina-code (161M) = ~700 MB
- **Verdict**: 🥇 **OPTIMAL** (performance/poids)

#### Option C: jina-code-embeddings-1.5b
- **Params**: 1.5B
- **Dimensions**: 1536D → 768D (Matryoshka truncation)
- **RAM**: ~3 GB
- **Performance**: 86.45% CodeSearchNet (SOTA 2025)
- **Verdict**: ⭐ Excellent, mais trop lourd pour v1.4.0 (considérer v1.5.0)

#### Option D: CodeBERT
- **Params**: 125M
- **Dimensions**: 768D
- **RAM**: ~300 MB
- **Performance**: ~65-68% CodeSearchNet
- **Verdict**: ✅ Fallback conservatif (si jina échoue)

### Décision

**Option B: jina-embeddings-v2-base-code (161M, 768D, Apache 2.0)**

**Justification**:
- 43× plus léger que nomic-code
- Même dimensionnalité 768D → **PAS de migration DB!**
- RAM total ~700 MB (sous budget 1 GB)
- Performance excellente (lead 9/15 benchmarks)
- 30+ langages supportés
- CPU-friendly (pas de GPU requis)

**Trade-off accepté**:
- ⚠️ Pas le SOTA 2025 absolu (-11 pts vs jina-1.5b)
- ✅ Ratio performance/poids optimal pour MnemoLite

**Conséquences**:
- Dual models loading (nomic-text + jina-code)
- Total RAM ~700 MB (monitoring requis)
- Configuration `.env`: `CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code`

**Référence**: Rapport Perplexity.ai confirme choix (score 8.5/10)

---

## ADR-003: BM25 Search - pg_trgm vs Extensions

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE (avec réserve)
**Décideurs**: Équipe MnemoLite

### Contexte

Hybrid search nécessite composante lexicale. PostgreSQL natif **NE SUPPORTE PAS BM25** (pas de statistiques globales corpus).

### Options Considérées

#### Option A: pg_trgm Similarity ⭐ CHOISIE (Phase 1-3)
```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_code_trgm ON code_chunks USING gin (source_code gin_trgm_ops);

SELECT id, similarity(source_code, 'query') AS score
FROM code_chunks
WHERE source_code % 'query'
ORDER BY score DESC;
```

**Avantages**:
- ✅ Extension native PostgreSQL
- ✅ Pas de dépendances externes
- ✅ Excellent fuzzy matching (typos)
- ✅ Performance correcte (index GIN)

**Inconvénients**:
- ⚠️ Pas de TF-IDF (pas de poids par terme)
- ⚠️ Similarité simple (pas de ranking BM25)

#### Option B: PostgreSQL Full-Text Search (tsvector)
```sql
CREATE INDEX idx_code_fts ON code_chunks USING gin (to_tsvector('english', source_code));

SELECT id, ts_rank(to_tsvector('english', source_code), query) AS rank
FROM code_chunks
WHERE to_tsvector('english', source_code) @@ query;
```

**Avantages**:
- ✅ Ranking natif (ts_rank)
- ✅ Opérateurs booléens (AND, OR, NOT)

**Inconvénients**:
- ⚠️ Optimisé pour texte naturel (pas code)
- ⚠️ Stemming problématique (`calculate` → `calcul`)

#### Option C: pg_search Extension (ParadeDB)
- Extension Rust, vrai BM25
- **Inconvénients**: Dépendance externe, compilation Rust requise
- **Verdict**: Évaluer post-v1.4.0 si qualité insuffisante

#### Option D: VectorChord-BM25 (TensorChord)
```sql
CREATE EXTENSION vectorchord_bm25;
SELECT id, bm25_score(document, query) FROM table WHERE bm25_match(document, query);
```

**Avantages**:
- ✅ Vrai BM25 avec Block-WeakAnd algorithm
- ✅ Optimisé pour PostgreSQL (Rust extension)
- ✅ Performance excellente (Block-WeakAnd = early termination)

**Inconvénients**:
- ❌ Dépendance externe (TensorChord)
- ❌ Compilation Rust requise
- ⚠️ Moins mature que pgvector

**Verdict**: Excellente alternative si BM25 requis, mais dépendance externe

#### Option E: plpgsql_bm25 (Pure PL/pgSQL)
```sql
-- Installation: script SQL uniquement
\i plpgsql_bm25.sql

-- Utilisation
SELECT id, bm25_score(document, query, tf, df, N) FROM table;
```

**Avantages**:
- ✅ **Pas de compilation** (pure PL/pgSQL)
- ✅ **Aucune dépendance externe** (PostgreSQL natif uniquement)
- ✅ Vrai BM25 (TF-IDF avec saturation)
- ✅ Contrôle total (code inspectable)

**Inconvénients**:
- ⚠️ Performance moyenne (PL/pgSQL plus lent que Rust)
- ⚠️ Calcul TF/IDF manuel requis (tables statistiques)
- ⚠️ Moins optimisé que VectorChord

**Verdict**: **Meilleur compromis** pour contrainte "PostgreSQL natif" si pg_trgm insuffisant

### Décision

**Option A: pg_trgm similarity (Phases 1-3)**

**Stratégie Progressive**:
1. **Phase 3 (v1.4.0)**: Implémenter pg_trgm + pgvector + RRF fusion
2. **Post-Phase 3**: Benchmark qualité (Recall@10, Precision, Precision@10)
3. **Si Recall@10 < 80%**: Évaluer alternatives BM25 pour v1.5.0
   - **Option préférée**: plpgsql_bm25 (pur SQL, respect contrainte natif)
   - **Option performance**: VectorChord-BM25 (si dépendances externes acceptées)
   - **Option complète**: pg_search/ParadeDB (si BM25 + hybrid intégré souhaité)

**Justification**:
- **Phase 1-3**: pg_trgm simple, natif, performant
- **Contrainte critique**: Pas de dépendances externes (PostgreSQL 17 only)
- **Acceptable v1.4.0**: pg_trgm suffisant pour MVP
- **Upgrade path v1.5.0**:
  - plpgsql_bm25 = meilleur respect contraintes (pur SQL)
  - VectorChord-BM25 = meilleure performance (si contraintes assouplies)

**Conséquences**:
- Documentation: encourager queries sémantiques (vector) vs lexicales (pg_trgm)
- Monitoring recall/precision hybrid search
- Plan B: désactiver pg_trgm, vector-only search

**Références**:
- Hybrid Search PostgreSQL: https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/
- VectorChord-BM25: https://github.com/tensorchord/VectorChord (Rust extension, Block-WeakAnd)
- plpgsql_bm25: https://github.com/paradedb/paradedb/discussions/1584 (Pure PL/pgSQL BM25)
- pg_search (ParadeDB): https://blog.paradedb.com/pages/introducing_search

---

## ADR-004: Tree-sitter Integration - tree-sitter-languages

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

Semantic chunking nécessite AST parsing. Plusieurs options pour intégrer tree-sitter en Python.

### Options Considérées

#### Option A: py-tree-sitter (bindings officiels)
- Bindings Python officiels
- **Inconvénients**: Nécessite compilation grammars manuellement

#### Option B: tree-sitter-languages ⭐ CHOISIE
- Package pré-compilé avec wheels pour toutes plateformes
- Grammars pré-compilés pour 50+ langages
- **Avantages**: Pas de compilation manuelle, production-ready

#### Option C: CodeTF
- Framework Salesforce utilisant tree-sitter
- **Inconvénients**: Trop heavy (dépendances transformers, etc.)

### Décision

**Option B: tree-sitter-languages**

**Justification**:
- Wheels pré-compilés (pas de compilation manuelle)
- 50+ langages disponibles
- Léger (pas de dépendances lourdes)
- Utilisé par CodeTF en backend

**Implémentation**:
```python
from tree_sitter_languages import get_parser

parser = get_parser('python')
tree = parser.parse(bytes(source_code, 'utf8'))
```

**Langages prioritaires**:
1. Python (Must-have)
2. JavaScript / TypeScript (Should-have)
3. Go, Rust, Java (Nice-to-have)

**Conséquences**:
- Installation simple: `pip install tree-sitter-languages`
- Pas de setup compilation
- Fallback chunking fixe si langage non supporté

**Référence**: https://pypi.org/project/tree-sitter-languages/

---

## ADR-005: Migration Strategy - Alembic Async

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

MnemoLite utilise SQLAlchemy 2.0 async. Besoin de migrations DB pour table `code_chunks`. Alembic supporte async depuis template `-t async`.

### Options Considérées

#### Option A: Migrations SQL Manuelles
- Scripts SQL dans `db/init/`
- **Inconvénients**: Pas de versioning, pas de rollback, erreur-prone

#### Option B: Alembic avec Template Async ⭐ CHOISIE
```bash
alembic init -t async alembic
```

**Avantages**:
- ✅ Versioning migrations
- ✅ Rollback support (downgrade)
- ✅ Autogenerate (--autogenerate)
- ✅ Compatible SQLAlchemy 2.0 async

### Décision

**Option B: Alembic Async Template**

**Setup**:
```bash
# Initialisation
alembic init -t async alembic

# Configuration env.py
async def run_async_migrations():
    engine = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)

# Créer migration
alembic revision --autogenerate -m "Add code_chunks table"

# Appliquer
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Pattern Migration**:
```python
def upgrade() -> None:
    op.create_table('code_chunks', ...)
    op.execute("CREATE INDEX ... USING hnsw ...")

def downgrade() -> None:
    op.drop_table('code_chunks')
```

**Conséquences**:
- Toutes migrations versionnées (alembic/versions/)
- Tests migration up/down obligatoires
- Review manual migrations autogenerées (⚠️ CRITIQUE)

**Référence**: https://alembic.sqlalchemy.org/en/latest/cookbook.html

---

## ADR-006: Hybrid Search Fusion - Reciprocal Rank Fusion (RRF)

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

Hybrid search combine pg_trgm (lexical) + pgvector (semantic). Besoin d'algorithme fusion pour merger résultats.

### Options Considérées

#### Option A: Score Normalization + Weighted Sum
```python
score_hybrid = alpha * score_vector + (1-alpha) * score_trgm
```
- **Inconvénients**: Scaling problématique (scores différentes échelles)

#### Option B: Reciprocal Rank Fusion (RRF) ⭐ CHOISIE
```python
score_rrf = 1 / (rank + k)  # k=60 standard
```
- **Avantages**: Pas de scaling requis, robust, standard industry

### Décision

**Option B: RRF (k=60)**

**Algorithme**:
```python
def rrf_fusion(list1, list2, k=60):
    scores = {}
    for rank, item in enumerate(list1, 1):
        scores[item.id] = scores.get(item.id, 0) + 1/(rank + k)
    for rank, item in enumerate(list2, 1):
        scores[item.id] = scores.get(item.id, 0) + 1/(rank + k)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**Justification**:
- Standard industry (Elasticsearch, etc.)
- Pas de tuning hyperparamètres (k=60 universellement bon)
- Robust (pas de scaling issues)

**Paramètre k**:
- k=60 (standard, recommandé)
- k faible (ex: 10) → favorise top results
- k élevé (ex: 100) → lisse ranking

**Conséquences**:
- Implémentation simple
- Tests: vérifier items présents dans les 2 listes rankés plus haut

**Référence**: https://medium.com/@richardhightower/stop-the-hallucinations-hybrid-retrieval-with-bm25-pgvector

---

## ADR-007: Graph Traversal Depth Limit

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

Call graph navigation via CTE récursifs. Besoin de limiter profondeur pour éviter explosion combinatoire.

### Options Considérées

#### Option A: depth ≤ 2
- Conservatif, rapide
- **Inconvénients**: Limite cas d'usage

#### Option B: depth ≤ 3 ⭐ CHOISIE
- Équilibre performance/utilité
- Cover 95% cas d'usage

#### Option C: depth ≤ 5
- Flexible
- **Inconvénients**: Risque explosion requêtes

### Décision

**Option B: depth ≤ 3**

**Justification**:
- Call chains >3 niveaux rares
- CTE récursifs performants jusqu'à depth=3
- Cas d'usage couverts:
  - depth=1: direct calls (fonction → ses appels)
  - depth=2: transitive calls (A → B → C)
  - depth=3: call chain analysis (A → B → C → D)

**Implémentation CTE**:
```sql
WITH RECURSIVE chain AS (
    -- Base: direct calls
    SELECT source_node_id, target_node_id, 1 AS depth
    FROM edges
    WHERE source_node_id = :from_node AND relationship = 'calls'

    UNION ALL

    -- Recursive: suivre chaîne
    SELECT e.source_node_id, e.target_node_id, c.depth + 1
    FROM edges e
    JOIN chain c ON e.source_node_id = c.target_node_id
    WHERE c.depth < 3 AND e.relationship = 'calls'
)
SELECT * FROM chain;
```

**Conséquences**:
- API parameter: `depth` (1, 2, 3) avec default=2
- Validation: `if depth > 3: raise ValueError`
- Benchmark: latency P95 <20ms (depth=3, ~500 functions)

---

## ADR-008: Metadata Extraction Prioritization

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

Metadata extraction complexe. Plusieurs langages à supporter. Ressources limitées (Phase 1: 1-2 semaines).

### Priorités Définies

#### Priorité 1 (Must-Have) - Python
**Métadonnées**:
- ✅ Signature (params, returns, type hints)
- ✅ Docstring (Google/NumPy/Sphinx styles)
- ✅ Complexity (cyclomatic via `radon`, LOC, cognitive)
- ✅ Imports
- ✅ Calls (fonctions appelées)
- ✅ Decorators

**Outils**: `ast` (stdlib) + `radon` (pypi)

#### Priorité 2 (Should-Have) - JavaScript / TypeScript
**Métadonnées**:
- ⚠️ Signature (params, returns via JSDoc)
- ⚠️ Imports (ES6 modules)
- ⚠️ Calls (partial)

**Outils**: Tree-sitter queries

#### Priorité 3 (Nice-to-Have) - Go, Rust, Java
**Métadonnées**: Basiques (signature, imports)
**Timeline**: v1.5.0 (post-EPIC-06)

### Décision

**Phase 1: Python uniquement (P1)**
**Phase 2-3**: JS/TS si temps permet (P2)
**v1.5.0**: Go/Rust/Java (P3)

**Justification**:
- Python = langage prioritaire équipe
- `radon` mature pour complexity
- Temps limité Phase 1 (1-2 semaines)

**Conséquences**:
- Tests Phase 1: Python uniquement
- Documentation: "Currently supports Python metadata extraction"
- Fallback: metadata basiques pour JS/TS/Go/Rust/Java (name, signature only)

---

## ADR-009: Test Strategy - Isolation DB

**Date**: 2025-10-15
**Statut**: ✅ ACCEPTÉE
**Décideurs**: Équipe MnemoLite

### Contexte

Tests intégration nécessitent DB. MnemoLite utilise déjà `mnemolite_test` (séparée de `mnemolite`).

### Stratégie

**DB Test Isolation**:
- ✅ DB test séparée: `mnemolite_test`
- ✅ Schema identique (via même init scripts)
- ✅ Reset entre tests (fixtures pytest)

**Pattern Fixtures**:
```python
@pytest.fixture
async def test_db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    # Setup schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

**Tests Code Intelligence**:
- Repository tests: `tests/db/repositories/test_code_chunk_repository.py`
- Service tests: `tests/services/test_code_chunking_service.py`
- Integration tests: `tests/test_code_integration.py`

**Conséquences**:
- Pas de pollution DB dev
- Tests isolés (parallel safe)
- CI/CD: setup DB test automatique

---

## 📊 Récapitulatif Décisions

| ADR | Sujet | Décision | Impact |
|-----|-------|----------|--------|
| 001 | Architecture | Tables séparées (events + code_chunks) | ⭐⭐⭐ Critique |
| 002 | Embeddings | jina-embeddings-v2-base-code (161M, 768D) | ⭐⭐⭐ Critique |
| 003 | Search Lexical | pg_trgm (Phase 1-3), pg_search (éval future) | ⭐⭐ Haut |
| 004 | AST Parsing | tree-sitter-languages (pré-compilé) | ⭐⭐ Haut |
| 005 | Migrations | Alembic async template | ⭐⭐ Haut |
| 006 | Fusion Search | RRF (k=60) | ⭐⭐ Haut |
| 007 | Graph Depth | depth ≤ 3 | ⭐ Moyen |
| 008 | Metadata Langs | Python (P1), JS/TS (P2), Go/Rust/Java (P3) | ⭐ Moyen |
| 009 | Tests DB | mnemolite_test (isolation) | ⭐ Moyen |

---

## 🔄 Processus de Révision

**Quand réviser une ADR**:
- Nouvelle information critique (research, benchmarks)
- Problème implementation (risque matérialisé)
- Feedback utilisateurs (post-release)

**Comment réviser**:
1. Créer ADR-XXX-REVISION
2. Documenter raison changement
3. Valider équipe
4. Mettre à jour code/docs

**Statuts ADR**:
- ✅ ACCEPTÉE
- 🔄 EN RÉVISION
- ❌ REJETÉE
- ⏸️ SUSPENDUE

---

**Date**: 2025-10-15
**Version**: 1.0.0
**Statut**: ✅ LOG VALIDÉ

**Maintenu par**: Équipe MnemoLite
