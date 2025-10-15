# EPIC-06: Deep Analysis - Code Intelligence + Mémoire Assistant

**Date**: 2025-10-15
**Statut**: 🔬 ANALYSE APPROFONDIE
**Context**: Double-check suite à contrainte critique découverte

---

## ⚠️ CONTRAINTE CRITIQUE IDENTIFIÉE

**MnemoLite doit CONTINUER à être une mémoire pour assistant (conversations, documentation texte) TOUT EN AJOUTANT les capacités code.**

**Problème** :
- EPIC-06 initial se concentrait uniquement sur code intelligence
- Risque de casser le use case principal actuel (agent memory)
- Besoin d'architecture **dual-purpose** : texte général + code

**Solution** : Architecture unifiée avec dual embeddings.

---

## 🔬 Ultra-Brainstorming: Analyse Comparative Embeddings

### Nomic Embed Code - Analyse Détaillée

**Specs réelles** (recherche 2024-2025) :

| Propriété | Valeur | Source |
|-----------|--------|--------|
| **Paramètres** | **7B** | Hugging Face (confirmé) |
| **Architecture** | Qwen2-based | Nomic AI blog |
| **Dimensions** | 768D (probable, Qwen2 standard) | Inference |
| **Context Length** | 32,768 tokens | Hugging Face |
| **Langages** | Python, Java, Ruby, PHP, JS, Go | Hugging Face |
| **Performance** | State-of-the-art CodeSearchNet | Paper ICLR 2025 |
| **Licence** | Apache 2.0 | Hugging Face |
| **GGUF** | Oui (quantization disponible) | lmstudio-community |

**⚠️ PROBLÈME MAJEUR** :
```
nomic-embed-text-v1.5  : 137M params (~262 MB VRAM)
nomic-embed-code       : 7B params   (~13-14 GB VRAM full precision)

Ratio: 51× plus lourd!
```

**Implications** :
- CPU-only deployment difficile (7B params)
- Latence plus élevée
- RAM requirements significatifs (>4GB)
- Pas idéal pour déploiement local léger

---

### 🥇 MEILLEURE ALTERNATIVE : Jina Code Embeddings

#### Option 1: jina-embeddings-v2-base-code (RECOMMANDÉ)

| Propriété | Valeur | Avantage MnemoLite |
|-----------|--------|-------------------|
| **Paramètres** | 161M | 43× plus léger que nomic-code |
| **Architecture** | BERT-based | Éprouvé, stable |
| **Dimensions** | **768D** | ✅ IDENTIQUE nomic-text! |
| **Context Length** | 8192 tokens | Suffisant pour fonctions |
| **Langages** | 30+ programming languages | Très complet |
| **Performance** | Lead 9/15 CodeSearchNet benchmarks | Très bon |
| **Licence** | Apache 2.0 | Compatible |
| **RAM** | ~300-400 MB | Léger |
| **Latence** | <50ms/batch | Rapide |

**🎯 PERFECT FIT** :
- **Même dimensionnalité (768D)** que nomic-text → pas de migration DB!
- Léger (161M) → déploiement facile
- Performance excellente (mieux que Microsoft/Salesforce)
- Multi-langages (30+)

#### Option 2: jina-code-embeddings-1.5b (SOTA 2025)

| Propriété | Valeur | Trade-off |
|-----------|--------|-----------|
| **Paramètres** | 1.5B | 10× plus léger que nomic-code, mais 10× plus lourd que jina-v2 |
| **Dimensions** | 1536D (défaut) | ⚠️ Incompatible 768D actuel |
| **Matryoshka Truncation** | Oui (768D possible) | ✅ Performance loss minimal |
| **Performance** | 79.04% avg (25 benchmarks) | State-of-the-art 2025 |
| **CodeSearchNet** | 86.45% | Excellent |
| **Context Length** | 8192 tokens | OK |

**Trade-offs** :
- ✅ Meilleure performance 2025 (SOTA)
- ✅ Match voyage-code-3 (79.23%)
- ✅ Truncation 768D possible via Matryoshka
- ⚠️ Plus lourd que jina-v2 (1.5B vs 161M)
- ⚠️ Needs quantization pour CPU léger

#### Option 3: jina-code-embeddings-0.5b (Ultra-léger)

| Propriété | Valeur | Trade-off |
|-----------|--------|-----------|
| **Paramètres** | 500M | 14× plus léger que nomic-code |
| **Dimensions** | 896D (défaut) | ⚠️ Incompatible 768D |
| **Matryoshka Truncation** | Oui (64D minimum) | ✅ 768D possible |
| **Performance** | 78.41% avg | Très bon pour la taille |
| **Outperforms** | Qwen3-0.6B (-20% params) | Efficient |

**Trade-offs** :
- ✅ Ultra-léger (500M)
- ✅ Performance correcte
- ⚠️ Moins bon que 1.5B version
- ⚠️ Truncation 768D nécessaire

---

### 📊 Benchmark Comparatif Final

| Modèle | Params | Dims | CodeSearchNet | RAM | Latence | Compatibilité 768D | Verdict |
|--------|--------|------|---------------|-----|---------|-------------------|---------|
| **nomic-embed-code** | 7B | 768 | SOTA | ~14 GB | Lent | ✅ Natif | ❌ Trop lourd |
| **jina-code-1.5B** | 1.5B | 1536→768 | 86.45% | ~3 GB | Moyen | ✅ Truncation | ⭐ SOTA 2025 |
| **jina-v2-base-code** | 161M | 768 | ~75%* | ~400 MB | Rapide | ✅ Natif | 🥇 RECOMMANDÉ |
| **jina-code-0.5B** | 500M | 896→768 | 78.41% | ~1 GB | Rapide | ✅ Truncation | ⚡ Ultra-léger |

*Estimation basée sur "lead 9/15 benchmarks"

---

## 🏗️ Architecture Unifiée: Dual-Purpose Memory

### Use Cases à Supporter

```
┌─────────────────────────────────────────────────────┐
│          MnemoLite v1.4.0 Use Cases                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. AGENT MEMORY (Actuel - À PRÉSERVER)            │
│     • Conversations avec Claude/GPT                 │
│     • Documentation technique (ADRs, RFCs)          │
│     • Notes de développement                        │
│     • Décisions architecturales                     │
│     → Embeddings: TEXTE GÉNÉRAL                     │
│                                                     │
│  2. CODE INTELLIGENCE (Nouveau - À AJOUTER)         │
│     • Indexation codebase                           │
│     • Recherche sémantique de code                  │
│     • Navigation call graph                         │
│     • Documentation code inline                     │
│     → Embeddings: CODE SPÉCIALISÉ                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Stratégie: Dual Embeddings, Unified Schema

**Architecture proposée** :

```sql
-- Option A: Extension table events (backward compatible)
ALTER TABLE events ADD COLUMN embedding_code VECTOR(768);
ALTER TABLE events ADD COLUMN content_type TEXT DEFAULT 'text';
-- content_type: 'text', 'code', 'conversation', 'documentation'

-- Option B: Table dédiée code (séparation propre)
CREATE TABLE code_chunks (
    id UUID PRIMARY KEY,
    source_code TEXT NOT NULL,
    language TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    embedding_text VECTOR(768),   -- Embedding texte général (pour docstrings, comments)
    embedding_code VECTOR(768),   -- Embedding code spécialisé
    metadata JSONB NOT NULL,
    ...
);

-- Option C: Unified table avec dual vectors (flexible)
CREATE TABLE memory_items (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    item_type TEXT NOT NULL,  -- 'event', 'code_chunk', 'conversation', 'document'
    embedding_text VECTOR(768),  -- Always populated (texte général)
    embedding_code VECTOR(768),  -- Populated only if item_type='code_chunk'
    metadata JSONB NOT NULL,
    indexed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index HNSW pour les deux embeddings
CREATE INDEX idx_memory_embedding_text ON memory_items
USING hnsw (embedding_text vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_memory_embedding_code ON memory_items
USING hnsw (embedding_code vector_cosine_ops) WITH (m = 16, ef_construction = 64)
WHERE embedding_code IS NOT NULL;  -- Partial index (code only)
```

---

## 🎯 RECOMMANDATION FINALE

### Stratégie Recommandée: "Dual Lightweight"

**Embeddings Models** :

1. **Texte/Conversations** (existant) :
   - **nomic-embed-text-v1.5**
   - 137M params, 768D
   - ✅ Déjà en production
   - ✅ Performant sur texte général
   - ✅ Léger, rapide

2. **Code** (nouveau) :
   - **jina-embeddings-v2-base-code**
   - 161M params, 768D
   - ✅ Même dimensionnalité (pas de migration!)
   - ✅ Léger (300M total avec nomic-text)
   - ✅ Excellent performance (lead 9/15 benchmarks)
   - ✅ 30+ langages
   - ✅ Déploiement facile (sentence-transformers compatible)

**Total RAM** : ~300M + ~400M = **~700 MB** (vs 14 GB nomic-code!)

---

### Architecture DB: Option B (Tables Séparées)

**Justification** :
- ✅ Séparation claire use cases (events vs code)
- ✅ Schemas optimisés par type
- ✅ Backward compatibility totale (table events intacte)
- ✅ Dual embeddings sur code_chunks seulement (économie mémoire)
- ✅ Évolutivité (facile ajouter autres types: images, audio, etc.)

**Schema final** :

```sql
-- Table 1: events (INCHANGÉE - agent memory)
CREATE TABLE events (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    content JSONB NOT NULL,
    embedding VECTOR(768),  -- nomic-embed-text-v1.5
    metadata JSONB
);

-- Table 2: code_chunks (NOUVELLE - code intelligence)
CREATE TABLE code_chunks (
    id UUID PRIMARY KEY,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    name TEXT,
    source_code TEXT NOT NULL,
    start_line INT,
    end_line INT,

    -- Dual embeddings
    embedding_text VECTOR(768),  -- nomic-text (docstrings, comments)
    embedding_code VECTOR(768),  -- jina-code (code sémantique)

    metadata JSONB NOT NULL,
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    node_id UUID,
    repository TEXT
);

-- Index HNSW distincts
CREATE INDEX idx_events_embedding ON events
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_code_embedding_text ON code_chunks
USING hnsw (embedding_text vector_cosine_ops);

CREATE INDEX idx_code_embedding_code ON code_chunks
USING hnsw (embedding_code vector_cosine_ops);
```

---

### EmbeddingService: Dual Model Support

```python
# api/services/embedding_service.py
from sentence_transformers import SentenceTransformer
from enum import Enum

class EmbeddingDomain(str, Enum):
    TEXT = "text"        # Conversations, docs, general text
    CODE = "code"        # Code snippets, functions, classes
    HYBRID = "hybrid"    # Generate both (for code with docstrings)

class EmbeddingService:
    def __init__(self):
        # Model 1: General text (existing)
        self.text_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        # "nomic-ai/nomic-embed-text-v1.5"

        # Model 2: Code specialized (new)
        self.code_model = SentenceTransformer(settings.CODE_EMBEDDING_MODEL)
        # "jinaai/jina-embeddings-v2-base-code"

    async def generate_embedding(
        self,
        text: str,
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> dict[str, list[float]]:
        """
        Generate embedding(s) based on domain.

        Args:
            text: Text or code to embed
            domain: TEXT, CODE, or HYBRID

        Returns:
            {'text': [...], 'code': [...]} or {'text': [...]} or {'code': [...]}
        """
        result = {}

        if domain in [EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID]:
            emb_text = self.text_model.encode(text, convert_to_tensor=False)
            result['text'] = emb_text.tolist()

        if domain in [EmbeddingDomain.CODE, EmbeddingDomain.HYBRID]:
            emb_code = self.code_model.encode(text, convert_to_tensor=False)
            result['code'] = emb_code.tolist()

        return result

    def auto_detect_domain(self, content_type: str) -> EmbeddingDomain:
        """
        Auto-detect embedding domain from content type.

        Args:
            content_type: 'event', 'code_chunk', 'conversation', 'documentation'

        Returns:
            EmbeddingDomain
        """
        if content_type == 'code_chunk':
            return EmbeddingDomain.HYBRID  # Code + docstrings
        else:
            return EmbeddingDomain.TEXT  # General text
```

---

### Search Service: Unified Hybrid Search

```python
# api/services/unified_search_service.py
class UnifiedSearchService:
    async def search(
        self,
        query: str,
        search_in: list[str] = ['events', 'code'],
        use_bm25: bool = True,
        use_vector: bool = True,
        limit: int = 10
    ) -> SearchResults:
        """
        Unified search across events (agent memory) and code.

        Args:
            query: Search query
            search_in: ['events'], ['code'], or ['events', 'code']
            use_bm25: Enable BM25 lexical search
            use_vector: Enable vector semantic search
            limit: Max results

        Returns:
            Unified SearchResults
        """
        results = []

        # Search in events (agent memory)
        if 'events' in search_in:
            event_results = await self._search_events(
                query, use_bm25, use_vector
            )
            results.extend(event_results)

        # Search in code
        if 'code' in search_in:
            code_results = await self._search_code(
                query, use_bm25, use_vector
            )
            results.extend(code_results)

        # Merge and rank (RRF if multiple sources)
        if len(results) > 0:
            ranked = self._rank_unified_results(results)
            return SearchResults(
                data=ranked[:limit],
                meta={
                    'sources': search_in,
                    'total': len(ranked)
                }
            )

        return SearchResults(data=[], meta={'total': 0})

    async def _search_events(self, query, use_bm25, use_vector):
        """Search in events table (agent memory)."""
        # Generate text embedding
        query_emb = await self.embedding_service.generate_embedding(
            query, domain=EmbeddingDomain.TEXT
        )

        # Vector search
        if use_vector:
            results = await self.event_repo.vector_search(
                embedding=query_emb['text'],
                limit=100
            )

        # BM25 search (if enabled)
        if use_bm25:
            bm25_results = await self.event_repo.bm25_search(query, limit=100)
            # Merge with RRF...

        return results

    async def _search_code(self, query, use_bm25, use_vector):
        """Search in code_chunks table."""
        # Generate code embedding
        query_emb = await self.embedding_service.generate_embedding(
            query, domain=EmbeddingDomain.CODE
        )

        # Vector search on embedding_code
        if use_vector:
            results = await self.code_chunk_repo.vector_search(
                embedding=query_emb['code'],
                embedding_field='embedding_code',  # Specify which vector
                limit=100
            )

        # BM25 search on source_code
        if use_bm25:
            bm25_results = await self.code_chunk_repo.bm25_search(query, limit=100)
            # Merge with RRF...

        return results
```

---

## 📊 Comparaison Options Architecture

### Option A: Extension Table Events

```sql
ALTER TABLE events ADD COLUMN embedding_code VECTOR(768);
ALTER TABLE events ADD COLUMN content_type TEXT;
```

**Avantages** :
- ✅ Simple (une seule table)
- ✅ Backward compatible

**Inconvénients** :
- ❌ Mixing concerns (events ≠ code chunks)
- ❌ Schema rigide (doit fitter les deux use cases)
- ❌ embedding_code NULL pour 99% des events (waste)
- ❌ Pas de metadata spécifique code (complexity, signature, etc.)

**Verdict** : ❌ Pas recommandé (mixing incompatible use cases)

---

### Option B: Tables Séparées ⭐ RECOMMANDÉ

```sql
-- events: agent memory (inchangé)
-- code_chunks: code intelligence (nouveau)
```

**Avantages** :
- ✅ Séparation claire des concerns
- ✅ Schemas optimisés par use case
- ✅ Backward compatibility totale
- ✅ Dual embeddings sur code seulement (économie mémoire)
- ✅ Metadata spécifique par type
- ✅ Index HNSW optimisés séparément
- ✅ Évolutivité (facile ajouter autres types: images, audio)

**Inconvénients** :
- ⚠️ Recherche unifiée = 2 requêtes + merge (acceptable)
- ⚠️ Légère complexité service layer

**Verdict** : 🥇 **RECOMMANDÉ** (best practices, évolutif)

---

### Option C: Table Unifiée memory_items

```sql
CREATE TABLE memory_items (
    item_type TEXT,  -- 'event', 'code_chunk', 'conversation', ...
    embedding_text VECTOR(768),
    embedding_code VECTOR(768),
    ...
);
```

**Avantages** :
- ✅ Flexible (supporte futurs types: images, audio)
- ✅ Recherche unifiée simple (une table)
- ✅ Dual embeddings natifs

**Inconvénients** :
- ❌ Migration lourde (rewrite table events)
- ❌ Breaking change majeur
- ❌ Schema generic = perte de spécificité
- ❌ embedding_code NULL pour events (waste)
- ❌ Complexité metadata (JSONB très hétérogène)

**Verdict** : ⚠️ Trop disruptif pour v1.4.0, considérer v2.0.0

---

## 🎯 Plan d'Implémentation Révisé

### Phase 0: Préparation (1 semaine)

**Objectif** : Setup dual embeddings sans casser existant

1. **Setup jina-embeddings-v2-base-code**
   ```bash
   pip install sentence-transformers
   # Auto-download jinaai/jina-embeddings-v2-base-code
   ```

2. **Extend EmbeddingService**
   - Ajouter `self.code_model`
   - Méthode `generate_embedding(text, domain='text'|'code'|'hybrid')`
   - Tests unitaires dual embeddings

3. **Benchmark local**
   - Comparer latence nomic-text vs jina-code
   - Vérifier RAM usage (<1GB total)
   - Valider dimensions 768D identiques

**Livrable** : Dual embeddings opérationnel, testé, backward compatible

---

### Phase 1: Foundation Code (4 semaines) - RÉVISÉ

**Stories inchangées** :
- ✅ Story 1: Tree-sitter Chunking (13 pts)
- ✅ Story 3: Metadata Extraction (8 pts)

**Story 2 RÉVISÉE** : Dual Embeddings Setup (5 pts) ← RÉDUIT
- Setup jina-embeddings-v2-base-code (pas nomic-code)
- Dual model dans EmbeddingService
- Tests benchmark local
- Documentation migration

**Story 2bis NOUVELLE** : Code Chunks Table & Repo (5 pts)
- Création table `code_chunks`
- Repository pattern `CodeChunkRepository`
- CRUD operations
- Tests intégration PostgreSQL

**Livrable Phase 1** :
- Chunking sémantique ✅
- Dual embeddings (text + code) ✅
- Metadata extraction ✅
- Table code_chunks créée ✅

---

### Phase 2-4: Inchangées

- Phase 2: Graph Intelligence (3 semaines)
- Phase 3: Hybrid Search (3 semaines)
- Phase 4: Integration (2 semaines)

**Total** : 12 semaines (identique)

---

## 📊 Métriques de Succès RÉVISÉES

### Performance

| Métrique | Baseline | Target | Stratégie |
|----------|----------|--------|-----------|
| **Events search (texte)** | 12ms | <15ms | Inchangé (nomic-text) |
| **Code search (sémantique)** | N/A | <30ms | jina-code (léger) |
| **Unified search (both)** | N/A | <50ms | Parallel queries + merge |
| **RAM usage** | 262 MB | <1 GB | ~700 MB (nomic-text + jina-code) |
| **Latence embedding gen** | 20-50ms | <100ms | Dual lightweight models |

### Quality

| Métrique | Target | Mesure |
|----------|--------|--------|
| **Events recall** | >90% | Maintain actuel |
| **Code precision** | >80% | jina-v2 benchmarks |
| **Unified relevance** | >85% | RRF fusion |

---

## 🚧 Risques Révisés

| Risque | Probabilité | Impact | Mitigation RÉVISÉE |
|--------|-------------|--------|-------------------|
| **Dual embeddings trop lents** | Faible | Moyen | jina-v2 léger (161M), batch processing |
| **RAM overflow CPU** | Faible | Moyen | Total <1GB (700MB), quantization possible |
| **Unified search complexe** | Moyen | Moyen | Tables séparées = queries simples |
| **Breaking changes** | Faible | Haut | Table events intacte, code_chunks nouvelle |
| **Maintenance dual models** | Moyen | Faible | sentence-transformers handles updates |

---

## ✅ Validation Finale

### Checklist Contraintes MnemoLite

- ✅ **PostgreSQL 17 Only** : Tables séparées, indexes HNSW natifs
- ✅ **Local deployment** : jina-v2 + nomic-text = 300M+400M, CPU-friendly
- ✅ **Async-first** : SQLAlchemy 2.0 async, compatible architecture
- ✅ **Backward compatible** : Table events intacte, API v1 inchangée
- ✅ **768D embeddings** : jina-v2 natif 768D, pas de migration DB
- ✅ **Léger** : Total ~700 MB RAM (vs 14 GB nomic-code)
- ✅ **Mémoire assistant** : Events table préservée, use case intact
- ✅ **Code intelligence** : code_chunks table ajoutée, dual embeddings

### Checklist Use Cases

- ✅ **Agent conversations** : Events table, nomic-text embeddings
- ✅ **Documentation technique** : Events table, texte général
- ✅ **Code indexing** : code_chunks table, jina-code embeddings
- ✅ **Code search** : Hybrid search sur embedding_code
- ✅ **Unified search** : Merge events + code_chunks via RRF
- ✅ **Graph navigation** : nodes/edges pour code dependencies

---

## 🎉 Conclusion

### Recommandation Finale: Option B + jina-v2-base-code

**Architecture** :
- ✅ Tables séparées (`events` + `code_chunks`)
- ✅ Dual embeddings (nomic-text 137M + jina-code 161M)
- ✅ Unified search service (merge résultats)
- ✅ 768D partout (pas de migration DB)

**Avantages** :
- ✅ **Léger** : ~700 MB total (vs 14 GB nomic-code)
- ✅ **Performant** : jina-v2 excellent (lead 9/15 benchmarks)
- ✅ **Compatible** : 768D, backward compatible
- ✅ **Évolutif** : Architecture dual-purpose claire
- ✅ **Préserve use case actuel** : Agent memory intact

**Trade-off accepté** :
- ⚠️ Pas le SOTA 2025 absolu (jina-code-1.5B meilleur)
- ✅ Mais performance excellente + déploiement facile
- ✅ Ratio performance/poids optimal pour MnemoLite

**Alternative future (v1.5.0)** :
- Upgrade vers jina-code-embeddings-1.5B avec truncation Matryoshka 768D
- Si besoin SOTA absolu + si déploiement plus puissant (GPU)

---

**Prochaine Action** :
- Mise à jour EPIC-06.md avec stratégie dual embeddings
- Mise à jour STORIES_EPIC-06.md Story 2 (remplacer nomic-code par jina-v2)
- Validation stakeholders avant Phase 0 kickoff

---

**Date**: 2025-10-15
**Statut**: ✅ ANALYSE COMPLÈTE
**Décision**: **jina-embeddings-v2-base-code** (161M, 768D) + architecture tables séparées
