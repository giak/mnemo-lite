# EPIC-32: Search Performance & Quality

**Status**: DRAFT | **Created**: 2026-04-02 | **Effort**: ~24 points | **Stories**: 13

**Source**: Audit MCP Search System (`docs/plans/2026-04-02-mcp-search-audit.md`)

---

## Context

L'audit du système de recherche MCP a révélé **15 issues** (3 P0, 4 P1, 5 P2, 3 P3) impactant :
- **Correctness** : cache key mismatch pouvant retourner de mauvais résultats
- **Performance** : memory search non-caché, pagination inefficace, JSONB scans
- **Quality** : BM25 désactivé pour code search, pas d'analytics, TTL court

### État actuel

| Métrique | Valeur | Cible |
|----------|--------|-------|
| Code search (cached) | <10ms | <10ms ✅ |
| Code search (uncached) | 150-300ms | <100ms |
| Memory search (cached) | N/A (pas de cache) | <20ms |
| Memory search (uncached) | 100-200ms | <50ms |
| Tag-only search | <20ms | <10ms |
| BM25 code search | ❌ Disabled | ✅ Enabled |
| Search analytics | ❌ None | ✅ Structured logging |

---

## Stories

### Phase 1: Quick Wins (P0 fixes, ~4 pts)

#### Story 32.1: Unifier la stratégie de cache key
**Priority**: P0 | **Effort**: 1 pt | **Value**: Critical

**Problème** : Deux stratégies de cache key coexistent :
- `SearchCodeTool` génère SHA256 de TOUS les paramètres (correct)
- `HybridCodeSearchService` utilise `cache_keys.py` avec query+repo+limit seulement (incorrect)

**Impact** : Des requêtes avec des filtres différents peuvent retourner le même résultat caché.

**Fichiers à modifier** :
- `api/cache/cache_keys.py` — Ajouter tous les paramètres (filters, offset, weights, enable_lexical, enable_vector)
- `api/services/hybrid_code_search_service.py` — Utiliser la clé unifiée
- `api/mnemo_mcp/tools/search_tool.py` — Supprimer la génération de clé locale (doublon)

**Implémentation** :
```python
# cache_keys.py
def generate_search_cache_key(
    query: str,
    filters: dict,
    limit: int,
    offset: int,
    enable_lexical: bool,
    enable_vector: bool,
    lexical_weight: float,
    vector_weight: float,
) -> str:
    """Generate comprehensive cache key including ALL search parameters."""
    params = {
        "q": query,
        "f": filters or {},
        "l": limit,
        "o": offset,
        "el": enable_lexical,
        "ev": enable_vector,
        "lw": lexical_weight,
        "vw": vector_weight,
    }
    raw = json.dumps(params, sort_keys=True)
    return f"search:v2:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
```

**Critères de complétion** :
- [ ] Cache key inclut TOUS les paramètres de recherche
- [ ] Tests vérifient que deux requêtes avec filtres différents ont des clés différentes
- [ ] Pas de régression sur les hits de cache existants

---

#### Story 32.2: Ajouter le cache Redis pour memory search
**Priority**: P0 | **Effort**: 2 pts | **Value**: High

**Problème** : `search_memory` n'a AUCUN cache. Chaque requête frappe la DB.

**Solution** : Ajouter un cache Redis avec TTL différencié par type de requête.

**Fichiers à modifier** :
- `api/mnemo_mcp/tools/memory_tools.py` — Ajouter cache lookup/write
- `api/cache/cache_keys.py` — Ajouter `generate_memory_search_cache_key()`

**Implémentation** :
```python
# memory_tools.py — dans search_memory.execute()
async def execute(self, query, tags, ...):
    # 1. Generate cache key
    cache_key = generate_memory_search_cache_key(query, tags, memory_type, limit, offset)

    # 2. Check Redis cache
    if self.redis:
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

    # 3. Perform search (existing logic)
    result = await self._perform_search(...)

    # 4. Write to cache (TTL depends on query type)
    if self.redis:
        ttl = 300 if tags else 60  # 5min for tag queries, 1min for natural language
        await self.redis.setex(cache_key, ttl, json.dumps(result))

    return result
```

**TTL strategy** :
| Query type | TTL | Rationale |
|------------|-----|-----------|
| Tag-only (`sys:*`) | 5 min | Résultats stables, peu de changements |
| Natural language | 1 min | Résultats peuvent changer avec decay |
| With filters | 2 min | Intermédiaire |

**Critères de complétion** :
- [ ] Tag-only queries cached 5 min
- [ ] Natural language queries cached 1 min
- [ ] Cache invalidation on memory write/update/delete
- [ ] Graceful degradation si Redis indisponible

---

#### Story 32.3: Activer BM25 reranking pour code search
**Priority**: P0 | **Effort**: 0.5 pt | **Value**: High

**Problème** : `default_enable_reranking=False` dans `hybrid_code_search_service.py`.

**Solution** : Activer par défaut — overhead <2ms, +10-20% pertinence.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — `default_enable_reranking=False` → `True`

**Critères de complétion** :
- [ ] BM25 activé par défaut pour code search
- [ ] Tests passent
- [ ] Pas de régression de performance (<2ms overhead)

---

### Phase 2: Performance (P1 fixes, ~6 pts)

#### Story 32.4: Optimiser les filtres JSONB
**Priority**: P1 | **Effort**: 2 pts | **Value**: High

**Problème** : `metadata->>'repository'` et `jsonb_each_text` empêchent l'utilisation d'index. Full scan O(n).

**Solution** : Ajouter des colonnes computed + index GIN.

**Fichiers à modifier** :
- `api/alembic/versions/..._add_metadata_indexes.py` — nouvelle migration
- `api/services/lexical_search_service.py` — utiliser les colonnes computed
- `api/services/vector_search_service.py` — utiliser les colonnes computed

**Implémentation** :
```sql
-- Migration
ALTER TABLE code_chunks
  ADD COLUMN IF NOT EXISTS repository TEXT GENERATED ALWAYS AS (metadata->>'repository') STORED,
  ADD COLUMN IF NOT EXISTS file_path TEXT GENERATED ALWAYS AS (metadata->>'file_path') STORED;

CREATE INDEX IF NOT EXISTS idx_code_chunks_repository ON code_chunks(repository);
CREATE INDEX IF NOT EXISTS idx_code_chunks_file_path ON code_chunks(file_path);
CREATE INDEX IF NOT EXISTS idx_code_chunks_metadata_gin ON code_chunks USING GIN(metadata);
```

**Critères de complétion** :
- [ ] Colonnes computed créées
- [ ] Index GIN sur metadata
- [ ] Queries utilisent les colonnes au lieu de JSONB extraction
- [ ] EXPLAIN ANALYZE montre index scan au lieu de seq scan

---

#### Story 32.5: Fixer l'invalidation L1 per-repository
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : `cascade_cache.py:219` appelle `self.l1.clear()` — efface TOUT le cache L1, pas juste le repo ciblé.

**Solution** : Invalider par préfixe de file_path.

**Fichiers à modifier** :
- `api/cache/cascade_cache.py` — `invalidate_repository()` → filtrage par préfixe
- `api/cache/l1_cache.py` — Ajouter `invalidate_by_prefix()`

**Implémentation** :
```python
# l1_cache.py
def invalidate_by_prefix(self, prefix: str) -> int:
    """Remove all entries whose key starts with prefix."""
    keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
    for key in keys_to_remove:
        del self._cache[key]
    return len(keys_to_remove)

# cascade_cache.py
async def invalidate_repository(self, repository: str) -> int:
    """Invalidate cache for a specific repository only."""
    prefix = f"chunk:{repository}:"
    l1_count = self.l1.invalidate_by_prefix(prefix)
    l2_count = await self.l2.invalidate_by_pattern(f"chunk:{repository}:*")
    return l1_count + l2_count
```

**Critères de complétion** :
- [ ] `invalidate_repository()` ne touche que le repo ciblé
- [ ] Tests vérifient que les autres repos restent en cache
- [ ] Métriques d'invalidation loggées

---

#### Story 32.6: Ajouter le cache d'embeddings
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : Embeddings régénérés à chaque search. 80-200ms cold start.

**Solution** : Cache Redis des embeddings par hash de query text.

**Fichiers à modifier** :
- `api/services/dual_embedding_service.py` — Ajouter cache lookup/write
- `api/cache/cache_keys.py` — Ajouter `generate_embedding_cache_key()`

**Implémentation** :
```python
# dual_embedding_service.py
async def generate_embedding(self, text: str, domain: str = "text") -> dict:
    cache_key = f"embed:{domain}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"

    # Check cache
    if self.redis:
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

    # Generate
    result = await self._generate(text, domain)

    # Cache (5 min TTL)
    if self.redis:
        await self.redis.setex(cache_key, 300, json.dumps(result))

    return result
```

**Critères de complétion** :
- [ ] Embeddings cachés 5 min dans Redis
- [ ] Cache hit rate mesurable
- [ ] Graceful degradation si Redis indisponible

---

#### Story 32.7: Pagination par curseur (keyset)
**Priority**: P1 | **Effort**: 1 pt | **Value**: Medium

**Problème** : Pagination in-memory fetch `limit + offset` puis slice. offset=900 = 900 résultats gaspillés.

**Solution** : Pagination par curseur (keyset) — utilise le dernier ID vu.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — Ajouter `search_with_cursor()`
- `api/mnemo_mcp/tools/search_tool.py` — Supporter le paramètre `cursor`

**Implémentation** :
```python
# Au lieu de: LIMIT 10 OFFSET 900
# On fait: WHERE score < last_score ORDER BY score DESC LIMIT 10
async def search_with_cursor(self, query, cursor_score=None, limit=10):
    if cursor_score:
        query += " AND rrf_score < :cursor_score"
        params["cursor_score"] = cursor_score

    results = await conn.execute(query + f" ORDER BY rrf_score DESC LIMIT {limit}")
    # Retourner le dernier score comme next_cursor
    return results, results[-1].rrf_score if results else None
```

**Critères de complétion** :
- [ ] Pagination par curseur fonctionnelle
- [ ] Réponse inclut `next_cursor`
- [ ] Tests de pagination profonde (offset=1000+)

---

### Phase 3: Quality (P2 fixes, ~6 pts)

#### Story 32.8: Ajouter les analytics de recherche
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : Aucun tracking des patterns de requête, hit rates, ou qualité des résultats.

**Solution** : Logging structuré + endpoint analytics.

**Fichiers à créer** :
- `api/routes/search_analytics_routes.py` — Endpoints analytics
- `api/services/search_analytics_service.py` — Collecte et agrégation

**Fichiers à modifier** :
- `api/mnemo_mcp/tools/search_tool.py` — Ajouter logging de métriques
- `api/mnemo_mcp/tools/memory_tools.py` — Ajouter logging de métriques

**Implémentation** :
```python
# Structured logging à chaque search
logger.info(
    "search.executed",
    query_hash=sha256(query)[:16],
    result_count=len(results),
    execution_ms=elapsed_ms,
    cache_hit=cache_hit,
    reranking_applied=reranking,
    filters_applied=filters,
)
```

**Endpoints** :
- `GET /api/v1/search/analytics/summary` — Résumé des dernières 24h
- `GET /api/v1/search/analytics/popular` — Requêtes populaires
- `GET /api/v1/search/analytics/slow` — Requêtes lentes (>500ms)
- `GET /api/v1/search/analytics/zero-results` — Requêtes sans résultats

**Critères de complétion** :
- [ ] Logging structuré pour chaque search
- [ ] 4 endpoints analytics fonctionnels
- [ ] Dashboard frontend (optionnel)

---

#### Story 32.9: Augmenter le TTL du cache L2
**Priority**: P2 | **Effort**: 0.5 pt | **Value**: Medium

**Problème** : TTL de 30s pour les résultats de search → cache misses fréquents.

**Solution** : Augmenter à 2-5 minutes pour les codebases stables.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — TTL 30s → 120s
- `api/mnemo_mcp/tools/search_tool.py` — TTL cohérent

**Critères de complétion** :
- [ ] TTL augmenté à 120s (2 min)
- [ ] Tests passent
- [ ] Pas de stale data observée

---

#### Story 32.10: Ajouter le mode OR pour les filtres de tags
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problème** : `search_by_tags` requiert TOUS les tags (AND). Pas de mode OR.

**Solution** : Ajouter un paramètre `tag_mode: "and" | "or"`.

**Fichiers à modifier** :
- `api/db/repositories/memory_repository.py` — Ajouter `tag_mode` parameter
- `api/mnemo_mcp/tools/memory_tools.py` — Exposer `tag_mode` dans l'API

**Implémentation** :
```sql
-- AND (actuel)
WHERE :tag0 = ANY(tags) AND :tag1 = ANY(tags)

-- OR (nouveau)
WHERE tags && ARRAY[:tag0, :tag1]  -- PostgreSQL array overlap operator
```

**Critères de complétion** :
- [ ] Mode OR fonctionnel (`tags && ARRAY[...]`)
- [ ] Mode AND par défaut (backward compatible)
- [ ] Tests pour les deux modes

---

#### Story 32.11: Index GIN trigram sur memories.content
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : La recherche lexicale skip le contenu des memories (trop lent sans index).

**Solution** : Ajouter un index GIN trigram sur `content`.

**Fichiers à modifier** :
- `api/alembic/versions/..._add_memory_content_index.py` — nouvelle migration
- `api/services/hybrid_memory_search_service.py` — Inclure content dans lexical search

**Implémentation** :
```sql
CREATE INDEX IF NOT EXISTS idx_memories_content_trgm
  ON memories USING GIN (content gin_trgm_ops);
```

**Critères de complétion** :
- [ ] Index GIN créé sur content
- [ ] Lexical search inclut content
- [ ] EXPLAIN ANALYZE montre index scan

---

#### Story 32.12: Augmenter le threshold de similarité vectorielle
**Priority**: P2 | **Effort**: 0.5 pt | **Value**: Low

**Problème** : Threshold de 0.1 trop bas — retourne des résultats peu pertinents.

**Solution** : Augmenter à 0.3 pour code, 0.2 pour memory.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — threshold 0.1 → 0.3
- `api/services/hybrid_memory_search_service.py` — threshold 0.1 → 0.2

**Critères de complétion** :
- [ ] Threshold augmenté
- [ ] Tests passent
- [ ] Moins de faux positifs dans les résultats

---

### Phase 4: Features (P3, ~8 pts)

#### Story 32.13: Search result highlighting
**Priority**: P3 | **Effort**: 2 pts | **Value**: Medium

**Fonctionnalité** : Surligner les termes correspondants dans les résultats.

**Fichiers à créer** :
- `api/services/highlight_service.py` — Extraction des spans correspondants

**Fichiers à modifier** :
- `api/mnemo_mcp/tools/search_tool.py` — Ajouter `highlights` dans la réponse

**Implémentation** :
```python
def highlight_matches(text: str, query: str, max_highlights: int = 3) -> list[dict]:
    """Find matching spans in text for query terms."""
    tokens = re.findall(r'\w+', query.lower())
    matches = []
    for token in tokens:
        for match in re.finditer(re.escape(token), text, re.IGNORECASE):
            matches.append({
                "start": match.start(),
                "end": match.end(),
                "text": match.group(),
            })
    return matches[:max_highlights]
```

**Critères de complétion** :
- [ ] Highlights retournés dans la réponse
- [ ] Frontend peut les afficher (optionnel)

---

#### Story 32.14: Search result deduplication
**Priority**: P3 | **Effort**: 1.5 pts | **Value**: Medium

**Fonctionnalité** : Éviter qu'un même fichier apparaisse plusieurs fois.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — Ajouter `deduplicate_by_file`
- `api/mnemo_mcp/tools/search_tool.py` — Exposer `deduplicate` parameter

**Implémentation** :
```python
def deduplicate_by_file(results: list, keep_best: bool = True) -> list:
    """Remove duplicate file paths, keeping the best-scoring chunk."""
    seen = {}
    for r in results:
        fp = r.get("file_path")
        if fp not in seen or r.get("score", 0) > seen[fp].get("score", 0):
            seen[fp] = r
    return list(seen.values())
```

**Critères de complétion** :
- [ ] Deduplication fonctionnelle
- [ ] Paramètre `deduplicate` exposé
- [ ] Par défaut: désactivé (backward compatible)

---

#### Story 32.15: Query rewriting / synonym support
**Priority**: P3 | **Effort**: 2 pts | **Value**: Medium

**Fonctionnalité** : "auth" → "authentication", "db" → "database".

**Fichiers à créer** :
- `api/services/query_rewriter.py` — Dictionnaire de synonymes + expansion

**Fichiers à modifier** :
- `api/mnemo_mcp/tools/search_tool.py` — Appliquer query rewriting avant search

**Implémentation** :
```python
# query_rewriter.py
SYNONYMS = {
    "auth": ["authentication", "authorization", "login"],
    "db": ["database", "db", "postgres", "postgresql"],
    "cache": ["cache", "redis", "memcached"],
    "api": ["api", "endpoint", "route", "handler"],
}

def rewrite_query(query: str) -> str:
    """Expand query with synonyms."""
    tokens = query.lower().split()
    expanded = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(SYNONYMS.get(token, []))
    return " ".join(expanded)
```

**Critères de complétion** :
- [ ] Dictionnaire de synonymes (min 20 entrées)
- [ ] Query rewriting appliqué avant search
- [ ] Paramètre `rewrite` pour activer/désactiver

---

## Ordre d'exécution

```
Phase 1 (Quick Wins, ~4h)
  32.1 → Cache key unifiée
  32.2 → Cache memory search
  32.3 → BM25 code search

Phase 2 (Performance, ~6h)
  32.4 → Index JSONB
  32.5 → L1 invalidation per-repo
  32.6 → Cache embeddings
  32.7 → Pagination par curseur

Phase 3 (Quality, ~6h)
  32.8 → Search analytics
  32.9 → TTL L2 augmenté
  32.10 → Mode OR pour tags
  32.11 → Index content trigram
  32.12 → Threshold similarité

Phase 4 (Features, ~8h)
  32.13 → Highlighting
  32.14 → Deduplication
  32.15 → Query rewriting
```

---

## Critères de complétion

- [ ] 3 P0 fixes implémentés (cache key, memory cache, BM25)
- [ ] 4 P1 fixes implémentés (JSONB index, L1 per-repo, embedding cache, cursor pagination)
- [ ] 5 P2 fixes implémentés (analytics, TTL, OR tags, content index, threshold)
- [ ] 3 P3 features implémentées (highlighting, dedup, rewriting)
- [ ] 358+ tests MCP passing
- [ ] Performance target: code search <100ms uncached, memory search <50ms uncached
- [ ] Cache hit rate >50% pour les requêtes répétées
- [ ] Search analytics endpoint fonctionnel

---

## Métriques de succès

| Métrique | Avant | Après | Cible |
|----------|-------|-------|-------|
| Code search (cached) | <10ms | <10ms | <10ms ✅ |
| Code search (uncached) | 150-300ms | 50-100ms | <100ms |
| Memory search (cached) | N/A | <20ms | <20ms |
| Memory search (uncached) | 100-200ms | 30-50ms | <50ms |
| Cache hit rate | ~30% | >50% | >50% |
| BM25 code search | ❌ | ✅ | ✅ |
| Search analytics | ❌ | ✅ | ✅ |
| Tests passing | 358/358 | 358+/358+ | 100% |
