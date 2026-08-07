# Spec: Analyse et Roadmap des Idées zvec pour MnemoLite

**Date** : 2026-06-14
**Contexte** : Comparaison technique entre zvec (Alibaba v0.5.0) et MnemoLite v5.0.0-dev
**Document source** : `docs/superpowers/mnemo-vs-zvec.md`

---

## 1. Résumé des Décisions

| Décision | Idées | Justification |
|----------|-------|---------------|
| **Faire (P0-P2)** | 5, 7, 2, 1, 6 | Gain clair, risque données nul |
| **Faire (P4)** | 3, 4 | Utile, non urgent |
| **Skip** | 8, 9, 10, 11, 12 | Gain négligeable ou risque trop élevé |

---

## 2. P0 — FTS Hybride tsvector

### Objectif
Remplacer `pg_trgm` par `tsvector`/`tsquery` pour le full-text search, combiné au vector search via RRF 3-way.

### Architecture

```
Query → [Vector Search (HNSW)] → scores vector
      → [tsquery @@ search_vector] → scores textuels (ts_rank)
      → [RRF fusion à 3 bras] → résultat final
```

### Modifications base de données

**Nouvelle colonne** :
```sql
ALTER TABLE memories ADD COLUMN search_vector tsvector;
ALTER TABLE code_chunks ADD COLUMN search_vector tsvector;
```

**Trigger auto-sync** :
```sql
CREATE FUNCTION sync_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('french', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_search_vector
    BEFORE INSERT OR UPDATE OF content
    ON memories
    FOR EACH ROW
    EXECUTE FUNCTION sync_search_vector();
```

**Index GIN** :
```sql
CREATE INDEX idx_memories_search_vector ON memories USING GIN (search_vector);
CREATE INDEX idx_code_chunks_search_vector ON code_chunks USING GIN (search_vector);
```

### Migration données existantes
```sql
-- Batch UPDATE en dehors des transactions critiques
UPDATE memories SET search_vector = to_tsvector('french', content)
WHERE search_vector IS NULL;
```

### Modification services

- `hybrid_memory_search_service.py` : Ajouter bras tsvector → scores → RRF
- `rrf_fusion_service.py` : Étendre à 3-way fusion (vector + halfvec + tsvector) → pondéré
- Configurable : `fts_weight` dans les paramètres de requête

### Tokenisation
- Par défaut : `'french'` (PostgreSQL intègre un stemmer français)
- Configurable par requête : `search_config='english'`, `'simple'`, `'french'`
- Support future : dictionnaires personnalisés, jieba pour chinois

### RRF Fusion (3-way)

```python
# Actuel (2-way)
rrf_score = 1/(k + vector_rank) + 1/(k + halfvec_rank)

# Nouveau (3-way avec poids)
rrf_score = (
    w_vector * 1/(k + vector_rank) +
    w_halfvec * 1/(k + halfvec_rank) +
    w_fts * 1/(k + fts_rank)
)
# k=60 (inchangé)
```

**⚠️ Note** : Les poids dynamiques (#2) et le multi-vecteurs (#6) ajouteront des bras supplémentaires. Le RRF doit être conçu pour N bras dès le départ, pas hardcodé à 3. Utiliser une liste de (score, rank, weight).

### Changements API MCP
- Paramètre optionnel `fts_weight` dans les outils de recherche
- Si `fts_weight=0` → comportement actuel (rétrocompatible)

### Interaction avec les autres idées
- **#2 (poids dynamiques)** remplacera les poids fixes `w_vector/w_halfvec/w_fts` par des poids calculés. Conçoir le RRF 3-way avec une architecture `List[(score, rank, weight)]` dès le départ.
- **#6 (multi-vecteurs)** ajoutera des bras supplémentaires (TEXT vs CODE). Le RRF 3-way doit supporter N bras.

### Sécurité données
- **Risque** : Aucun. Colonne AJOUTÉE, pas modifiée.
- **Rollback** : `DROP COLUMN search_vector`
- **Perf** : Index GIN peut ralentir les INSERT. Mesurer l'impact.

### Effort estimé : 5 jours
1. Migration DB + triggers (1j)
2. Migration données existantes (0.5j)
3. Modification hybrid_memory_search_service (1.5j)
4. Extension RRF fusion 3-way (1j)
5. Tests + validation recall (1j)

---

## 3. P1 — Benchmark INT8 vs halfvec

### Objectif
Mesurer recall@10, QPS, et taille index pour `vector_int8(1024/768)` vs `halfvec(1024/768)` vs `vector(1024/768)` FP32 sur les vraies données MnemoLite.

### Protocole

```
Jeu de test 1 : memories — 1024D, ~N lignes
Jeu de test 2 : code_chunks — 768D, ~M lignes

Métriques :
- recall@10 (vs FP32 ground truth)
- QPS (single-thread, 100 requêtes)
- Taille index HNSW
- Taille table (colonne seule)
```

### Implémentation du bench

```python
class QuantizationBench:
    def __init__(self, df: pd.DataFrame, dim: int):
        self.df = df
        self.fp32 = [vector_to_list(v) for v in df['embedding']]
        self.halfvec = [halfvec_to_list(v) for v in df['embedding_half']]
        self.int8 = [vector_to_int8(v) for v in df['embedding']]

    def recall_at_k(self, k=10):
        # ground truth = FP32 exact search
        # compare rankings for halfvec and int8
        ...

    def qps(self, n_queries=100):
        # measure queries per second for each type
        ...

    def index_size(self):
        # query pg_indexes_size for each HNSW index
        ...
```

### Critère de décision
- Si recall@10 ≥ 99% pour int8 vs FP32 → **Go** pour INT8 en prod
- Si recall < 99% → **No-go**, on garde halfvec

### Effort estimé : 1-2 jours
1. Script de benchmark (1j)
2. Exécution + analyse résultats (0.5j)
3. Rapport (0.5j)

---

## 4. P2 — Poids Dynamiques RRF

### Objectif
Remplacer les poids fixes (lexical=0.4, vector=0.6) par des poids adaptatifs selon la requête.

### Heuristiques

| Type de requête | Signal | Poids vector | Poids lexical |
|-----------------|--------|-------------|---------------|
| **Code-heavy** | Contient `def `, `fn `, `class `, `import `, `.py` | 0.3 | 0.7 |
| **Question** | Contient `?`, mot interrogatif (`comment`, `pourquoi`) | 0.7 | 0.3 |
| **Citation/terme exact** | Guillemets `"..."` ou terme rare (freq < 0.1%) | 0.2 | 0.8 |
| **Général** | Défaut | 0.6 | 0.4 |

### Normalisation des scores
- Min-max scaling par type de métrique avant fusion
- Fallback explicite : si un bras retourne 0 résultats, ignorer son poids

### Changements
- `rrf_fusion_service.py` : Fonction `detect_query_type(query: str) → str`
- `hybrid_memory_search_service.py` : Passage du type détecté au service RRF
- Poids stockés en configuration (modifiables sans redéploiement)

### Effort estimé : 2 jours
1. Détection type requête (0.5j)
2. Normalisation scores (0.5j)
3. Fallback bras vide (0.5j)
4. Tests (0.5j)

---

## 5. P2 — INT8 Quantization (si recall ≥ 99%)

### Objectif
Ajouter `vector_int8(1024)` pour memories et `vector_int8(768)` pour code_chunks en parallèle des colonnes existantes.

### Nouveau schéma

```sql
-- Memories
ALTER TABLE memories ADD COLUMN embedding_int8 vector_int8(1024);

-- Code chunks
ALTER TABLE code_chunks
    ADD COLUMN embedding_text_int8 vector_int8(768),
    ADD COLUMN embedding_code_int8 vector_int8(768);
```

### Trigger sync

```sql
CREATE FUNCTION sync_int8_embeddings() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.embedding IS NOT NULL THEN
        NEW.embedding_int8 := NEW.embedding::vector_int8(1024);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_memory_int8
    BEFORE INSERT OR UPDATE OF embedding
    ON memories
    FOR EACH ROW
    EXECUTE FUNCTION sync_int8_embeddings();
```

**Même pattern pour code_chunks avec 768D** (deux triggers distincts, un par dimension).

### Index HNSW sur int8

```sql
CREATE INDEX idx_memories_embedding_int8 ON memories
    USING hnsw (embedding_int8 vector_int8_cosine_ops)
    WITH (m = 24, ef_construction = 128);

CREATE INDEX idx_code_emb_text_int8 ON code_chunks
    USING hnsw (embedding_text_int8 vector_int8_cosine_ops)
    WITH (m = 16, ef_construction = 128);

CREATE INDEX idx_code_emb_code_int8 ON code_chunks
    USING hnsw (embedding_code_int8 vector_int8_cosine_ops)
    WITH (m = 16, ef_construction = 128);
```

### Modification chemins de recherche

Tous les services qui utilisent `embedding_half` doivent être mis à jour pour utiliser `embedding_int8` en priorité :
- `hybrid_memory_search_service.py`
- `code_search_service.py`
- `search_code` MCP tool

Stratégie : remplacer les références à `embedding_half` par `embedding_int8` dans les clauses `ORDER BY` et les index hints. Garder `embedding_half` et `embedding` comme fallbacks silencieux.

### Effort estimé : 3 jours
1. Migration DB + triggers (1j)
2. Migration données existantes (0.5j)
3. Mise à jour services recherche (1j)
4. Validation recall (0.5j)

---

## 6. P3 — Requête Multi-Vecteurs

### Objectif
Permettre la recherche simultanée sur TEXT embedding + CODE embedding + champs scalaires avec reranking combiné.

### API MCP

```
search_code(
    query="async def fetch_user",
    fields=["text", "code"],           # quels embeddings chercher
    weights=[0.5, 0.5],                # poids par champ
    topk=10,
    filters={"language": "python"}     # filtres scalaires
)
```

### Pipeline
```
Query → Embedding TEXT (BGE-M3 1024D)
     → Embedding CODE (Jina 768D)
     → Recherche TEXT dans code_chunks.embedding_text_half
     → Recherche CODE dans code_chunks.embedding_code_half
     → Fusion pondérée des scores
     → Top-K
```

### Changements
- `code_search_service.py` : Parcourir les champs demandés, fusionner les résultats
- `rrf_fusion_service.py` : Fusion pondérée multi-champs

### Effort estimé : 3 jours

---

## 7. P4 — Callback Reranker API

### Objectif
Exposer un hook de reranking dans le pipeline hybride.

### Interface

```python
class ReRanker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        topn: int,
    ) -> list[SearchResult]: ...
```

### Endpoint MCP
```
search_memory(query="...", reranker="my_reranker", ...)
```

Sécurité : timeout (5s max), isolation par process, erreur → fallback sur RRF standard.

### Effort estimé : 1 jour

---

## 8. P4 — EmbeddingProvider Abstrait

### Objectif
Remplacer l'appel direct à `sentence-transformers` par une interface `EmbeddingProvider`.

### Interface

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]: ...
    @abstractmethod
    async def embed_code(self, text: str) -> list[float]: ...
```

### Implémentations
- `LocalSentenceTransformerProvider` (actuel, refactoré)
- `OpenAIProvider` (opt-in, clé API)
- `HTTPProvider` (API custom)

### Effort estimé : 2 jours

---

## 9. Skip — Idées Exclues

| # | Idée | Raison |
|---|------|--------|
| 8 | Memory Limit + Heuristics | Cache L1/L2 gère déjà. Gain négligeable. |
| 9 | WAL batch | PostgreSQL a déjà son WAL. Risque perte données. |
| 10 | Remplacer pgvector par zvec | Perte ACID. 4 semaines. Pas de bottleneck actuel. |
| 11 | SQL Engine MCP | YAGNI. 34 outils MCP couvrent tout. 2 semaines. |
| 12 | RaBitQ research | Pas compatible pgvector. Dépend du choix #10. |

---

## 10. Roadmap

| Phase | Idées | Durée | Dépendances |
|-------|-------|-------|-------------|
| **1** | 7. Benchmark INT8 | 1-2j | Aucune |
| **2** | 5. FTS tsvector | 5j | Aucune |
| **3** | 2. Poids RRF | 2j | #5 (doit avoir RRF 3-way d'abord) |
| **4** | 1. INT8 (si recall ≥99%) | 3j | #7 |
| **5** | 6. Multi-vecteurs | 3j | #5 (fusion multi-bras) |
| **6** | 3. Callback reranker | 1j | Aucune |
| **7** | 4. EmbeddingProvider | 2j | Aucune |

**Total estimé** : 17-19 jours de développement.

---

## 11. Critères d'Arrêt

Chaque idée a un critère d'arrêt explicite :
- **#5** : Si tsvector ajoute >10% de latence aux requêtes → reverter
- **#1** : Si recall <99% vs FP32 → ne pas déployer
- **#2** : Si les heuristiques dégradent la pertinence sur les requêtes tests → retomber aux poids fixes
- **#3** : Si l'API callback >2j d'implémentation → simplifier
