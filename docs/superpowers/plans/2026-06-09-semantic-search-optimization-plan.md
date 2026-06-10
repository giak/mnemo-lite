# EPIC-48 — Optimisation de la Recherche Semantique

> **Status:** DRAFT | **Date:** 2026-06-09 | **Points:** ~18 | **Stories:** 7

## Contexte

### Audit du 2026-06-09

La recherche semantique MnemoLite a ete analysee en profondeur contre l'etat de l'art 2026 (embedding models, RAG hybride, pgvector tuning). Le pipeline hybride (lexical + vectoriel + entites + tags → RRF → BM25 → decay) est deja solide. Deux gaps majeurs subsistent.

### Etat actuel vs Cible

| Composant | Actuel | Cible |
|-----------|--------|-------|
| Modele embedding | `nomic-embed-text-v1.5` (768D, 2024) | `BAAI/bge-m3` (1024D, multilingue) |
| Query expansion | Regex + dico developpeur | LLM multi-query (3-5 variations) |
| HNSW index | m=16, ef_construction=64 | m=24, ef_construction=128 |
| BM25 | Integre et actif | Conserve |
| Half-precision | embedding_half (halfvec) | Conserve |
| CLI | POST /api/v1/memories/search | Conserve |

### Metriques cibles

| Metrique | Actuel | Cible |
|----------|--------|-------|
| Recall@10 (francais) | ~60% | ~80% |
| Diversite resultats | Faible | Haute (multi-query RRF) |
| Latence P95 | ~80 ms | ~150 ms (expansion) / ~80 ms (off) |
| Requetes de test (10) | ~6/10 | 10/10 |

---

## Stories

### Phase 1 : Embedding Model Upgrade (P0)

---

### Story 48.1 : Ajout de BGE-M3 au registre des modeles

**Priorite:** P0 | **Effort:** 2 pts | **Valeur:** Fondation

**Probleme:** Le modele `nomic-embed-text-v1.5` (768D, 2024) est optimise pour l'anglais. Les contenus francais (articles, investigations) ont un recall degrade. BGE-M3 est le leader MTEB pour le francais multilingue (1024D, dense+sparse+colbert, 8192 tokens context).

**Solution:** Ajouter `BAAI/bge-m3` au registre `EMBEDDING_MODELS` et le definir comme modele par defaut. Mettre a jour toutes les constantes de dimension (768 → 1024).

**Implementation:**

```python
# api/services/sentence_transformer_embedding_service.py
EMBEDDING_MODELS = {
    # ... existants ...
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

**Fichiers a modifier:**
- `api/services/sentence_transformer_embedding_service.py` — ajout modele
- `api/services/embedding_service.py` — `dimension: int = 1024`
- `api/services/dual_embedding_service.py` — `dimension: int = 1024`, modele par defaut
- `api/services/memory_search_service.py` — `EXPECTED_EMBEDDING_DIM = 1024`

**Criteres de completion:**
- [ ] BGE-M3 ajoute a `EMBEDDING_MODELS` avec `dimension: 1024`, prefixes BGE
- [ ] `dimension: int = 1024` dans `embedding_service.py` (ligne 62) et `dual_embedding_service.py` (ligne 102)
- [ ] `EXPECTED_EMBEDDING_DIM = 1024` dans `memory_search_service.py` (ligne 30)
- [ ] Modele par defaut change a `BAAI/bge-m3` dans `dual_embedding_service.py`
- [ ] Le modele se telecharge et s'initialise sans erreur

---

### Story 48.2 : Migration DB — 768D → 1024D

**Priorite:** P0 | **Effort:** 3 pts | **Valeur:** Bloquant

**Probleme:** Les colonnes `embedding` et `embedding_half` sont typees `vector(768)` et `halfvec(768)`. Le passage a 1024D necessite un ALTER TABLE. Les embeddings existants deviennent NULL.

**Solution:** Migration SQL avec suppression/recreration des indexes HNSW, ALTER TABLE, et parametres HNSW optimises (m=24, ef_construction=128).

**Implementation:**

```sql
-- Fichier: db/migrations/v10_to_v11_bge_m3_1024d.sql

DROP INDEX IF EXISTS idx_memories_embedding;
DROP INDEX IF EXISTS idx_memories_embedding_half;

ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1024);
ALTER TABLE memories ALTER COLUMN embedding_half TYPE halfvec(1024);

CREATE INDEX idx_memories_embedding ON memories 
  USING hnsw (embedding vector_cosine_ops) 
  WITH (m='24', ef_construction='128');

CREATE INDEX idx_memories_embedding_half ON memories 
  USING hnsw (embedding_half halfvec_cosine_ops) 
  WITH (m='24', ef_construction='128');

UPDATE memories SET embedding_model = NULL WHERE embedding_model IS NOT NULL;
```

**Fichiers a modifier:**
- `db/migrations/v10_to_v11_bge_m3_1024d.sql` — **NOUVEAU**

**Criteres de completion:**
- [ ] Script SQL cree
- [ ] Applique sur la DB Docker
- [ ] Colonnes `embedding` et `embedding_half` sont NULL
- [ ] Indexes HNSW recrees avec m=24, ef_construction=128
- [ ] Recherche lexicale toujours fonctionnelle

---

### Story 48.3 : Script de reindexation BGE-M3

**Priorite:** P0 | **Effort:** 3 pts | **Valeur:** Critique

**Probleme:** 37K memoires sans embeddings apres la migration. La recherche vectorielle est inoperante tant que la reindexation n'est pas terminee.

**Solution:** Script Python `scripts/reindex_bge_m3.py` qui charge BGE-M3, parcourt les memoires par lots de 100, genere les embeddings 1024D, et met a jour les colonnes. Reprise automatique sur interruption (`WHERE embedding IS NULL`).

**Implementation:**

```python
# scripts/reindex_bge_m3.py
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
            texts = [f"Represent this passage for retrieval: {r[1] or ''}" for r in rows]
            embeddings = model.encode(texts, normalize_embeddings=True)
            
            async with conn.begin():
                for mem_id, emb in zip(ids, embeddings):
                    half = emb.astype('float16')
                    await conn.execute(
                        text("""UPDATE memories 
                            SET embedding = :emb::vector, embedding_half = :half::halfvec, 
                                embedding_model = :model WHERE id = :id"""),
                        {"emb": emb.tolist(), "half": half.tolist(), "model": MODEL, "id": mem_id}
                    )
            
            offset += BATCH_SIZE
            print(f"  {min(offset, total)}/{total} ({100*offset/total:.1f}%)")
```

**Fichiers a modifier:**
- `scripts/reindex_bge_m3.py` — **NOUVEAU**

**Criteres de completion:**
- [ ] Script cree et fonctionnel
- [ ] Execute : `docker exec mnemo-api python scripts/reindex_bge_m3.py`
- [ ] `SELECT COUNT(*) FROM memories WHERE embedding IS NULL` → 0
- [ ] `SELECT DISTINCT embedding_model FROM memories` → `BAAI/bge-m3`
- [ ] Recherche vectorielle fonctionnelle : `mnemo search "Sumer" --type article`

---

### Phase 2 : Query Expansion (P1)

---

### Story 48.4 : LLM Client minimal

**Priorite:** P1 | **Effort:** 2 pts | **Valeur:** Dependance

**Probleme:** Aucun client LLM n'existe dans MnemoLite. Le query expansion necessite un appel LLM.

**Solution:** Client OpenAI-compatible minimal supportant n'importe quel provider (OpenAI, Anthropic, Ollama, Groq). Configure via variables d'environnement. Fallback silencieux si `LLM_API_KEY` non definie.

**Implementation:**

```python
# api/services/llm_client.py
class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.enabled = bool(self.api_key)
    
    async def complete(self, prompt: str, max_tokens: int = 200) -> str:
        if not self.enabled:
            return ""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": 0.3}
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
```

**Fichiers a modifier:**
- `api/services/llm_client.py` — **NOUVEAU**
- `api/dependencies.py` — ajouter `get_llm_client()`

**Criteres de completion:**
- [ ] Client cree avec support OpenAI-compatible
- [ ] Fallback silencieux si `LLM_API_KEY` non definie (`self.enabled = False`)
- [ ] Test unitaire avec mock `aiohttp`

---

### Story 48.5 : Query Expansion Service

**Priorite:** P1 | **Effort:** 2 pts | **Valeur:** +15-25% recall

**Probleme:** Une seule requete → un seul embedding. Les variations semantiques (synonymes, reformulations) ne sont pas explorees.

**Solution:** Service qui genere 3-5 variations via LLM. Le prompt demande des synonymes, generalisations, et angles alternatifs en francais. Fallback vers `[query]` si LLM indisponible.

**Implementation:**

```python
# api/services/query_expansion_service.py
class QueryExpansionService:
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def expand(self, query: str, n: int = 4) -> List[str]:
        if not self.llm.enabled:
            return [query]
        
        prompt = (f"Genere {n} reformulations de cette requete en francais. "
                  "Inclus : synonymes, termes connexes, angles differents, generalisations. "
                  "Retourne UNIQUEMENT une liste JSON.\n\n"
                  f"Requete : {query}\n\n"
                  "Format : [\"variation1\", \"variation2\", ...]")
        
        try:
            response = await self.llm.complete(prompt, max_tokens=300)
            variations = json.loads(response)
            return [query] + variations[:n]
        except Exception:
            return [query]
```

**Fichiers a modifier:**
- `api/services/query_expansion_service.py` — **NOUVEAU**
- `api/dependencies.py` — ajouter `get_query_expansion_service()`

**Criteres de completion:**
- [ ] Service cree avec `expand(query, n)`
- [ ] Fallback vers `[query]` si LLM indisponible
- [ ] Test unitaire avec mock `LLMClient`

---

### Story 48.6 : Integration Query Expansion dans le pipeline

**Priorite:** P1 | **Effort:** 4 pts | **Valeur:** +15-25% recall

**Probleme:** Le `HybridMemorySearchService.search()` ne fait pas de query expansion. Il faut integrer le nouveau service dans le pipeline existant.

**Solution:** Ajouter un parametre `query_expansion` optionnel a `search()`. Si fourni, generer les variations, lancer les 4 methodes de recherche pour chaque variation en parallele, puis tout fusionner via RRF. Sans query expansion → comportement identique a l'actuel.

**Implementation:**

```python
# hybrid_memory_search_service.py — modification de search()
async def search(
    self,
    query: str,
    embedding: Optional[List[float]] = None,
    query_expansion: Optional[QueryExpansionService] = None,  # NOUVEAU
    ...
) -> HybridMemorySearchResponse:
    # Etape 0 : Expansion
    if query_expansion:
        queries = await query_expansion.expand(query)
        logger.info("Query expansion", original=query, variations=len(queries))
    else:
        queries = [query]
    
    # Etape 1 : Recherche parallele pour chaque variation
    all_search_results = []
    for q in queries:
        # Generer embedding pour cette variation
        emb = await self._generate_embedding(q) if enable_vector else None
        
        tasks = []
        if enable_lexical:
            tasks.append(self._lexical_search(q, filters, candidate_pool_size))
        if enable_vector and emb:
            tasks.append(self._vector_search(emb, filters, candidate_pool_size))
        # ... entites, tags ...
        
        variation_results = await asyncio.gather(*tasks)
        all_search_results.extend(variation_results)
    
    # Etape 2-5 : RRF → BM25 → Decay → Pagination (inchange)
    ...
```

```python
# api/routes/memories_routes.py — endpoint POST /search
query_expansion: QueryExpansionService = Depends(get_query_expansion_service),  # NOUVEAU

response = await search_service.search(
    query=request.query,
    embedding=query_embedding,
    query_expansion=query_expansion,  # NOUVEAU
    filters=filters,
    limit=request.limit,
    offset=request.offset,
)
```

**Fichiers a modifier:**
- `api/services/hybrid_memory_search_service.py` — `search()` + `_generate_embedding()`
- `api/routes/memories_routes.py` — injection `query_expansion`
- `api/dependencies.py` — `get_query_expansion_service()`

**Criteres de completion:**
- [ ] Query expansion integre dans `search()`
- [ ] Sans LLM configure → comportement inchange (1 requete)
- [ ] Avec LLM configure → 4-5 variations → RRF fusion multi-requete
- [ ] Latence additionnelle < 500 ms par rapport a sans expansion
- [ ] Test : `mnemo search "Sumer bureaucratie" --type article` retourne des resultats diversifies

---

### Phase 3 : Validation (P2)

---

### Story 48.7 : Tests de qualite de recherche

**Priorite:** P2 | **Effort:** 2 pts | **Valeur:** Confiance

**Probleme:** Pas de metriques quantitatives sur la qualite de recherche avant/apres.

**Solution:** Tests manuels sur 10 requetes representatives du corpus Truth Engine avec verification des Top-3.

**Requetes de test:**

| # | Requete | Document attendu (Top-3) |
|---|---------|--------------------------|
| 1 | "Sumer bureaucratie" | `sumer_france_bureaucratie_ARTICLE` |
| 2 | "dette publique francaise" | Articles dette |
| 3 | "Lyhanna assassinat justice" | `lyhanna_systeme_protection_pedocriminalite_ARTICLE` |
| 4 | "andurarum" | `andurarum_autopsy_INVESTIGATION` |
| 5 | "feodalite financiarisee" | Article feodalite |
| 6 | "justice fantome" | `C9_justice_fantome_INVESTIGATION` |
| 7 | "capture administrative" | Articles capture |
| 8 | "souverainete petrodollar" | Article agonie du souverain |
| 9 | "ecole sans transmission" | Article ecole |
| 10 | "19 civilisations" | `19_civilisations_ARTICLE` |

**Criteres de completion:**
- [ ] 10/10 requetes retournent le document attendu dans le Top-3
- [ ] Les scores de pertinence sont > 0.02
- [ ] La diversite est amelioree (le meme document n'est pas systematiquement #1)
- [ ] La latence P95 reste < 200 ms

---

## Ordre d'execution

```
Phase 1 (P0) : Embedding Model Upgrade (~8h)
  48.1 → 48.2 → 48.3
  SEQUENTIEL : modele → migration → reindexation
  La reindexation (48.3) tourne ~15 min en background

Phase 2 (P1) : Query Expansion (~6h)
  48.4 → 48.5 → 48.6
  SEQUENTIEL : client → service → integration
  Peut etre faite en parallele de la reindexation 48.3

Phase 3 (P2) : Validation (~2h)
  48.7
  Apres 48.3 ET 48.6 termines
```

**Effort total:** ~18 points (~16h de travail effectif)

---

## Completion Criteria

- [ ] BGE-M3 est le modele d'embedding par defaut
- [ ] Toutes les memoires ont un embedding BGE-M3 1024D
- [ ] Indexes HNSW optimises (m=24, ef_construction=128)
- [ ] LLM Client fonctionnel (si `LLM_API_KEY` configuree)
- [ ] Query expansion integre avec fallback silencieux
- [ ] 10/10 requetes de test passent
- [ ] `mnemo search` fonctionnel avec pertinence amelioree
- [ ] Pas de regression sur la recherche lexicale
- [ ] Commits atomiques par story

## Success Metrics

| Metrique | Avant | Apres |
|----------|-------|-------|
| Recall@10 (francais) | ~60% | ≥80% |
| Requetes de test reussies | ~6/10 | 10/10 |
| Score pertinence median | ~0.016 | ≥0.025 |
| Diversite (entropie Top-5) | Basse | Haute |
| Latence P95 | ~80 ms | ≤200 ms |

## Notes

- **BM25** est deja integre et actif — verifie dans le code (`default_enable_reranking=True`)
- **Le fix CLI** (`mnemo search` → `POST /api/v1/memories/search`) est deja commite (`94459ef`)
- **La contrainte CHECK** `chk_memory_type` inclut deja `article` et `quintessence` (`fbca886`)
- **Half-precision** (`embedding_half`) est deja utilise par le `HybridMemorySearchService`
- La reindexation est interruptible et reprenable (`WHERE embedding IS NULL`)
- Sans LLM configure, le query expansion est desactive — aucune degradation

## References

- Spec: `docs/superpowers/specs/2026-06-09-semantic-search-optimization-design.md`
- Modele: `api/services/sentence_transformer_embedding_service.py`
- Pipeline: `api/services/hybrid_memory_search_service.py`
- BM25: `api/services/bm25_rerank_service.py`
- RRF: `api/services/rrf_fusion_service.py`
- Decay: `api/services/memory_decay_service.py`
- Endpoint: `api/routes/memories_routes.py`
- DI: `api/dependencies.py`
- CLI: `scripts/mnemo.py`
- Web research 2026-06-09: MTEB leaderboard, BGE-M3, RRF best practices, pgvector HNSW tuning
