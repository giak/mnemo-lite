> **Date:** 2026-06-09
> **Feature:** Optimisation de la Recherche Sémantique
> **Inspired by:** Audit MnemoLite + Web Research 2026 (embedding models, RAG hybrid, pgvector)
> **Priority:** P0 (embedding) / P1 (query expansion)

## 1. Overview

### Problem

La recherche sémantique MnemoLite (`mnemo search` → `POST /api/v1/memories/search` → `HybridMemorySearchService`) retourne des resultats sous-optimaux pour le contenu francais a haute densite intellectuelle (articles 50K chars, investigations 200K chars).

Deux causes racines identifiees par l'audit du 2026-06-09 :

| Cause | Impact |
|-------|--------|
| **Modele d'embedding** : `nomic-embed-text-v1.5` (768D, 2024) — optimise anglais, sous-performant sur le francais | Recall degrade de ~15% vs BGE-M3 sur le francais |
| **Pas de query expansion** : une seule requete → un seul embedding. Les synonymes, reformulations, et angles semantiques alternatifs sont ignores. | Perte de ~15-25% de recall sur les requetes conceptuelles |
| **Documents longs non chunkes** : articles 54K chars → un seul embedding. Le signal semantique est dilue. | Embedding de qualite reduite pour les longs documents |

### Solution

Deux ameliorations complementaires, implementees sequentiellement :

1. **Upgrade embedding** : `nomic-v1.5` (768D) → `BAAI/bge-m3` (1024D, multilingue, MTEB French leader, dense+sparse+colbert)
2. **Query expansion** : generation LLM de 3-5 variations par requete → recherches paralleles → RRF fusion multi-requete

### Benefices attendus

| Metrique | Actuel | Cible |
|----------|--------|-------|
| Recall@10 (francais) | ~60% (estime) | ~80% |
| Diversite des resultats | Faible (memes documents dominent) | Haute (RRF multi-query) |
| Precision noms propres | Correcte (lexical pg_trgm) | Conservee |
| Latence P95 | ~80 ms | ~150 ms (expansion ON) / ~80 ms (OFF) |

### Contexte : ce qui est DEJA bon

| Composant | Implementation |
|-----------|---------------|
| Pipeline hybride | Lexical (pg_trgm ILIKE) + Vectoriel (HNSW cosine halfvec) + Entites (JSONB @>) + Tags (array) → RRF (k=60) → BM25 → Decay temporel |
| BM25 reranking | Integre et actif (`default_enable_reranking=True`), `BM25RerankService.rerank_with_ids()` |
| Half-precision | `embedding_half` (halfvec) avec index HNSW, utilise par la recherche vectorielle |
| RRF dynamique | k=20 (code), k=60 (default), k=80 (NL) selon le type de requete |
| Filtre `memory_type` | Applique dans toutes les branches de recherche (lexical, vectoriel, entites, tags) |
| CLI | `mnemo search` branche sur `POST /api/v1/memories/search` (HybridMemorySearchService) depuis commit `94459ef` |

## 2. Data Model

### 2.1 Migration vectorielle : 768D → 1024D

La colonne `embedding` est typee `vector(768)` et `embedding_half` est `halfvec(768)`. Le passage a BGE-M3 (1024D) necessite un ALTER TABLE. Les embeddings existants deviennent NULL — une reindexation complete est necessaire.

```sql
-- Fichier : db/migrations/v10_to_v11_bge_m3_1024d.sql

-- Etape 1 : Supprimer les indexes HNSW existants
DROP INDEX IF EXISTS idx_memories_embedding;
DROP INDEX IF EXISTS idx_memories_embedding_half;

-- Etape 2 : Changer la dimension des colonnes vectorielles
-- Les embeddings existants deviennent NULL
ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1024);
ALTER TABLE memories ALTER COLUMN embedding_half TYPE halfvec(1024);

-- Etape 3 : Recr eer les indexes HNSW avec parametres optimises
-- m=24 au lieu de m=16 pour meilleur recall sur 37K documents
-- ef_construction=128 pour meilleure precision a l'indexation
CREATE INDEX idx_memories_embedding ON memories 
  USING hnsw (embedding vector_cosine_ops) 
  WITH (m='24', ef_construction='128');

CREATE INDEX idx_memories_embedding_half ON memories 
  USING hnsw (embedding_half halfvec_cosine_ops) 
  WITH (m='24', ef_construction='128');

-- Etape 4 : Reinitialiser embedding_model
UPDATE memories SET embedding_model = NULL WHERE embedding_model IS NOT NULL;
```

### 2.2 Colonnes impactees

| Colonne | Type actuel | Type cible | Contenu apres migration |
|---------|-------------|------------|------------------------|
| `embedding` | `vector(768)` | `vector(1024)` | NULL (a reindexer) |
| `embedding_half` | `halfvec(768)` | `halfvec(1024)` | NULL (a reindexer) |
| `embedding_model` | `nomic-ai/nomic-embed-text-v1.5` | `BAAI/bge-m3` (apres reindex) | NULL temporairement |

### 2.3 Trigger halfvec

Le trigger `trg_sync_memory_halfvec` synchronise automatiquement `embedding_half` a partir de `embedding`. Il utilise des casts implicites — verifier qu'il supporte le nouveau type `halfvec(1024)`.

### 2.4 Registre des modeles d'embedding

Ajout dans `api/services/sentence_transformer_embedding_service.py` :

```python
EMBEDDING_MODELS = {
    # ... modeles existants ...
    
    # BGE-M3 : multilingue, 1024D, dense+sparse+colbert
    # MTEB French leader, supporte 8192 tokens
    "BAAI/bge-m3": {
        "version": "bge-m3",
        "dimension": 1024,
        "uses_prompt_name": False,
        "uses_prefix": True,
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "document_prefix": "Represent this passage for retrieval: ",
    },
}
```

### 2.5 Constantes de dimension a mettre a jour

| Fichier | Ligne | Actuel | Cible |
|---------|-------|--------|-------|
| `api/services/embedding_service.py` | 62 | `dimension: int = 768` | `dimension: int = 1024` |
| `api/services/dual_embedding_service.py` | 102 | `dimension: int = 768` | `dimension: int = 1024` |
| `api/services/memory_search_service.py` | 30 | `EXPECTED_EMBEDDING_DIM = 768` | `EXPECTED_EMBEDDING_DIM = 1024` |

## 3. Architecture

### 3.1 Pipeline de recherche actuel

```
Query
  │
  ├─→ [Lexical] pg_trgm ILIKE (title + embedding_source)
  ├─→ [Vectoriel] HNSW cosine halfvec (embedding_half)
  ├─→ [Entites] JSONB @> entities
  └─→ [Tags] array match tags + auto_tags
  │
  └─→ RRF Fusion (k=60, lex=0.5, vec=0.5, ent=0.15, tag=0.15)
        │
        ├─→ BM25 Rerank (top 30 candidates)
        ├─→ Temporal Decay (exponential, presets par type)
        └─→ Pagination (offset/limit)
              │
              └─→ HybridMemorySearchResponse
```

### 3.2 Pipeline de recherche cible (avec Query Expansion)

```
Query: "Sumer bureaucratie"
  │
  ├─→ [QueryExpansionService] LLM → [
  │      "Sumer bureaucratie",
  │      "Mesopotamie antique administration",
  │      "tablettes cuneiformes gestion temples",
  │      "civilisation sumerienne fonctionnaires royaux"
  │    ]
  │
  ├─→ Pour chaque variation (parallele) :
  │     ├─→ [Lexical] pg_trgm ILIKE
  │     ├─→ [Vectoriel] HNSW cosine halfvec (BGE-M3 1024D)
  │     ├─→ [Entites] JSONB @>
  │     └─→ [Tags] array match
  │
  └─→ RRF Fusion (toutes variations, toutes methodes)
        │
        ├─→ BM25 Rerank
        ├─→ Temporal Decay
        └─→ Pagination
```

### 3.3 Nouveaux composants

#### LLM Client (`api/services/llm_client.py`)

Client OpenAI-compatible minimal. Supporte tout provider (OpenAI, Anthropic, Ollama, Groq, etc.).

```python
class LLMClient:
    """Client LLM OpenAI-compatible.
    
    Configuration via variables d'environnement :
    - LLM_API_KEY : cle API (si absente → client desactive)
    - LLM_BASE_URL : URL de base (default: https://api.openai.com/v1)
    - LLM_MODEL : modele (default: gpt-4o-mini)
    """
    
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.enabled = bool(self.api_key)
    
    async def complete(self, prompt: str, max_tokens: int = 200) -> str:
        """Appel LLM avec fallback silencieux si desactive."""
        if not self.enabled:
            return ""
        # ... appel HTTP POST /chat/completions ...
```

#### Query Expansion Service (`api/services/query_expansion_service.py`)

```python
class QueryExpansionService:
    """Genere 3-5 variations semantiques d'une requete.
    
    Utilise le LLM pour produire des synonymes, generalisations,
    et angles alternatifs. Les variations sont fusionnees via RRF.
    """
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def expand(self, query: str, n: int = 4) -> List[str]:
        """Retourne [query_originale] + n variations.
        
        Si LLM indisponible → retourne [query] uniquement.
        """
        if not self.llm.enabled:
            return [query]
        
        prompt = (f'Genere {n} reformulations de cette requete en francais.\n'
                  'Inclus : synonymes, termes connexes, angles differents, generalisations.\n'
                  'Retourne UNIQUEMENT une liste JSON.\n\n'
                  f'Requete : {query}\n\n'
                  'Format : ["variation1", "variation2", ...]')
        
        try:
            response = await self.llm.complete(prompt, max_tokens=300)
            variations = json.loads(response)
            return [query] + variations[:n]
        except Exception:
            return [query]
```

#### Integration dans HybridMemorySearchService

Modification de `search()` pour accepter un `query_expansion` optionnel :

```python
async def search(
    self,
    query: str,
    embedding: Optional[List[float]] = None,
    query_expansion: Optional[QueryExpansionService] = None,  # NOUVEAU
    ...
) -> HybridMemorySearchResponse:
    # Etape 0 : Query expansion (si disponible)
    if query_expansion:
        queries = await query_expansion.expand(query)
    else:
        queries = [query]
    
    # Etape 1 : Pour chaque variation, lancer les 4 recherches
    all_results = []
    for q in queries:
        embedding_q = await self.embedding_service.generate_embedding(q) if embedding else None
        tasks = [
            self._lexical_search(q, filters, candidate_pool_size),
            self._vector_search(embedding_q, filters, candidate_pool_size),
            self._entity_search(keywords, filters, candidate_pool_size),
            self._tag_search(keywords, filters, candidate_pool_size),
        ]
        results = await asyncio.gather(*tasks)
        all_results.extend(results)
    
    # Etape 2 : RRF fusion sur TOUS les resultats
    fused = self.fusion.fuse(*[r for r, _ in all_results if r])
    
    # Etape 3-5 : BM25 → Decay → Pagination (inchange)
    ...
```

### 3.4 Points d'injection (Dependencies)

```python
# api/dependencies.py

def get_llm_client() -> LLMClient:
    """Client LLM (singleton)."""
    return LLMClient()

def get_query_expansion_service(
    llm: LLMClient = Depends(get_llm_client)
) -> QueryExpansionService:
    """Service d'expansion de requetes."""
    return QueryExpansionService(llm)
```

```python
# api/routes/memories_routes.py — endpoint POST /search

@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    engine: AsyncEngine = Depends(get_db_engine),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
    query_expansion: QueryExpansionService = Depends(get_query_expansion_service),  # NOUVEAU
) -> MemorySearchResponse:
    ...
    response = await search_service.search(
        query=request.query,
        embedding=query_embedding,
        query_expansion=query_expansion,  # NOUVEAU
        filters=filters,
        limit=request.limit,
        offset=request.offset,
    )
```

## 4. Script de Reindexation

### 4.1 Architecture

```python
# scripts/reindex_bge_m3.py

"""
Reindexe toutes les memoires avec BGE-M3 (1024D).

Workflow:
1. Charge BGE-M3 via SentenceTransformer
2. Parcourt les memoires par lots de 100 (WHERE embedding IS NULL)
3. Genere embeddings 1024D + halfvec
4. UPDATE memories SET embedding = ..., embedding_half = ..., embedding_model = 'BAAI/bge-m3'
5. Log progression toutes les 1000 memoires

Performance:
- 37K memoires × 100/batch × ~2s/batch (encodage + UPDATE) ≈ 12-15 minutes
- Modele BGE-M3 : ~2.2 GB, temps de chargement ~30s
"""

MODEL = "BAAI/bge-m3"
BATCH_SIZE = 100

async def main():
    model = SentenceTransformer(MODEL)
    engine = create_async_engine(DB_URL)
    
    async with engine.connect() as conn:
        total = (await conn.execute(
            text("SELECT COUNT(*) FROM memories WHERE embedding IS NULL")
        )).scalar()
        
        offset = 0
        while offset < total:
            rows = (await conn.execute(
                text("SELECT id, content FROM memories WHERE embedding IS NULL LIMIT :limit OFFSET :offset"),
                {"limit": BATCH_SIZE, "offset": offset}
            )).fetchall()
            
            if not rows:
                break
            
            ids = [r[0] for r in rows]
            texts = [
                f"Represent this passage for retrieval: {r[1] or ''}" 
                for r in rows
            ]
            
            embeddings = model.encode(texts, normalize_embeddings=True)
            
            async with conn.begin():
                for mem_id, emb in zip(ids, embeddings):
                    half = emb.astype('float16')
                    await conn.execute(
                        text("""
                            UPDATE memories 
                            SET embedding = :emb::vector, 
                                embedding_half = :half::halfvec, 
                                embedding_model = :model 
                            WHERE id = :id
                        """),
                        {"emb": emb.tolist(), "half": half.tolist(), 
                         "model": MODEL, "id": mem_id}
                    )
            
            offset += BATCH_SIZE
            pct = min(100, 100 * offset / total)
            print(f"  {min(offset, total)}/{total} ({pct:.1f}%)")
    
    print(f"Reindexation terminee : {total} memoires")
```

### 4.2 Reprise sur interruption

Le script utilise `WHERE embedding IS NULL` — il peut etre relance sans risque de double indexation. Les memoires deja indexees sont ignorees.

## 5. Migration

### 5.1 Ordre des operations

```
1. CODE  : Ajouter BGE-M3 au registre + mettre a jour les dimensions
2. CODE  : Ajouter LLM Client + Query Expansion Service + integration pipeline
3. BUILD : docker compose build api
4. DB    : Appliquer v10_to_v11_bge_m3_1024d.sql
5. START : docker compose up -d api
6. INDEX : docker exec mnemo-api python scripts/reindex_bge_m3.py (~15 min)
7. TEST  : mnemo search "Sumer" --type article
```

### 5.2 Etat intermediaire

Entre l'etape 4 (DB migration) et l'etape 6 (reindexation) :
- **Recherche lexicale** : ✅ Fonctionnelle (pg_trgm)
- **Recherche vectorielle** : ❌ Inoperante (embeddings NULL)
- **Recherche entites/tags** : ✅ Fonctionnelle

La recherche lexicale seule donne des resultats corrects pour les noms propres et termes exacts.

### 5.3 Rollback

```sql
-- Revenir a nomic-v1.5 :
-- 1. ALTER TABLE pour vector(768) et halfvec(768)
-- 2. Relancer reindexation avec l'ancien modele
-- 3. La recherche lexicale reste fonctionnelle pendant toute l'operation
```

## 6. Error Handling

| Scenario | Comportement |
|----------|-------------|
| BGE-M3 indisponible (download fail) | Fallback silencieux vers nomic-v1.5 (deja en cache). Log WARNING. |
| LLM_API_KEY non definie | `LLMClient.enabled = False`. Query Expansion retourne `[query]`. Aucune erreur. |
| LLM timeout | `QueryExpansionService.expand()` catch l'exception → retourne `[query]`. Log WARNING. |
| LLM retourne JSON invalide | `json.loads()` fail → catch → retourne `[query]`. Log WARNING. |
| Reindexation interrompue | Relancer le script. `WHERE embedding IS NULL` ignore les memoires deja indexees. |
| Embedding NULL pendant reindex | `WHERE embedding_half IS NOT NULL` dans la recherche vectorielle. Les memoires sans embedding sont ignorees. |
| HNSW index corrompu | `DROP INDEX ... ; CREATE INDEX ...` reconstruit l'index. |

## 7. Metriques de qualite

### 7.1 Requetes de test

10 requetes representant le corpus Truth Engine (articles, investigations, quintessences) :

| # | Requete | Document attendu dans le Top-3 |
|---|---------|-------------------------------|
| 1 | "Sumer bureaucratie" | `2026-06-06_07-49_sumer_france_bureaucratie_ARTICLE` |
| 2 | "dette publique francaise" | Articles sur la dette |
| 3 | "Lyhanna assassinat justice" | `2026-06-08_22-30_lyhanna_systeme_protection_pedocriminalite_ARTICLE` |
| 4 | "andurarum" | `2026-06-04_14-30_andurarum_autopsy_INVESTIGATION` |
| 5 | "feodalite financiarisee" | `France 2025 : anatomie d'une feodalite` |
| 6 | "justice fantome" | `C9_justice_fantome_INVESTIGATION` |
| 7 | "capture administrative" | Articles sur la capture |
| 8 | "souverainete petrodollar" | `L'agonie du souverain` |
| 9 | "ecole sans transmission" | `ecole_sans_transmission` |
| 10 | "19 civilisations" | `2026-06-07_19_civilisations_ARTICLE` |

### 7.2 Criteres de succes

- [ ] 10/10 requetes retournent le document attendu dans le Top-3
- [ ] Les scores de pertinence sont > 0.02
- [ ] La diversite est amelioree (le meme document n'est pas systematiquement #1)
- [ ] La latence P95 reste < 200 ms (avec query expansion si LLM configure)

## 8. Implementation Checklist

- [ ] 48.1 : Ajout BGE-M3 au registre `EMBEDDING_MODELS` + dimensions 1024
- [ ] 48.2 : Migration SQL `v10_to_v11_bge_m3_1024d.sql` + application DB
- [ ] 48.3 : Script `reindex_bge_m3.py` + execution
- [ ] 48.4 : LLM Client (`api/services/llm_client.py`) + `get_llm_client()`
- [ ] 48.5 : Query Expansion Service (`api/services/query_expansion_service.py`)
- [ ] 48.6 : Integration dans `HybridMemorySearchService.search()` + `POST /search`
- [ ] 48.7 : Tests de qualite sur les 10 requetes

## 9. References

- `api/services/sentence_transformer_embedding_service.py` — registre `EMBEDDING_MODELS`
- `api/services/hybrid_memory_search_service.py` — pipeline de recherche hybride
- `api/services/bm25_rerank_service.py` — BM25 (deja integre, `rerank_with_ids`)
- `api/services/rrf_fusion_service.py` — RRF k=60 avec `fuse_with_weights`
- `api/services/memory_decay_service.py` — temporal decay exponentiel
- `api/routes/memories_routes.py` — endpoint `POST /api/v1/memories/search`
- `api/dependencies.py` — injection de dependances FastAPI
- `db/migrations/` — migrations SQL
- `scripts/mnemo.py` — CLI (deja migre vers `/api/v1/memories/search`)
- Web research 2026-06-09 : MTEB leaderboard, BGE-M3, Jina-v3, RRF best practices, pgvector HNSW tuning

*End of SPEC*
