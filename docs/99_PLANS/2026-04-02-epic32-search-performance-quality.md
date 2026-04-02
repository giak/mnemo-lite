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
- `HybridCodeSearchService` utilise une clé simple avec query+repo+limit seulement (incorrect)

**Impact** : Des requêtes avec des filtres différents peuvent retourner le même résultat caché.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — Utiliser une clé complète
- `api/mnemo_mcp/tools/search_tool.py` — Supprimer la génération de clé locale (doublon)

**Implémentation** :
```python
# Nouvelle clé de cache complète
def generate_search_cache_key(
    query: str, filters: dict, limit: int, offset: int,
    enable_lexical: bool, enable_vector: bool,
    lexical_weight: float, vector_weight: float,
) -> str:
    params = {
        "q": query, "f": filters or {}, "l": limit, "o": offset,
        "el": enable_lexical, "ev": enable_vector,
        "lw": lexical_weight, "vw": vector_weight,
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
- `api/cache/cache_keys.py` — Créer (nouveau fichier)

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
- `api/services/hybrid_code_search_service.py` — `default_enable_reranking=True`

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
ALTER TABLE code_chunks
  ADD COLUMN IF NOT EXISTS repository TEXT
    GENERATED ALWAYS AS (metadata->>'repository') STORED,
  ADD COLUMN IF NOT EXISTS file_path TEXT
    GENERATED ALWAYS AS (metadata->>'file_path') STORED;

CREATE INDEX idx_code_chunks_repository ON code_chunks(repository);
CREATE INDEX idx_code_chunks_file_path ON code_chunks(file_path);
CREATE INDEX idx_code_chunks_metadata_gin ON code_chunks USING GIN(metadata);
```

**Critères de complétion** :
- [ ] Colonnes computed créées
- [ ] Index GIN sur metadata
- [ ] Queries utilisent les colonnes au lieu de JSONB extraction
- [ ] EXPLAIN ANALYZE montre index scan au lieu de seq scan

---

#### Story 32.5: Fixer l'invalidation L1 per-repository
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : `cascade_cache.py` appelle `self.l1.clear()` — efface TOUT le cache L1.

**Solution** : Invalider par préfixe de file_path.

**Fichiers à modifier** :
- `api/cache/cascade_cache.py` — `invalidate_repository()` → filtrage par préfixe
- `api/cache/l1_cache.py` — Ajouter `invalidate_by_prefix()`

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

**Critères de complétion** :
- [ ] Embeddings cachés 5 min dans Redis
- [ ] Cache hit rate mesurable
- [ ] Graceful degradation si Redis indisponible

---

#### Story 32.7: Pagination par curseur (keyset)
**Priority**: P1 | **Effort**: 1 pt | **Value**: Medium

**Problème** : Pagination in-memory fetch `limit + offset` puis slice.

**Solution** : Pagination par curseur — utilise le dernier score vu.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — Ajouter `search_with_cursor()`
- `api/mnemo_mcp/tools/search_tool.py` — Supporter le paramètre `cursor`

**Critères de complétion** :
- [ ] Pagination par curseur fonctionnelle
- [ ] Réponse inclut `next_cursor`
- [ ] Tests de pagination profonde

---

### Phase 3: Quality (P2 fixes, ~6 pts)

#### Story 32.8: Ajouter les analytics de recherche
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : Aucun tracking des patterns de requête, hit rates, ou qualité.

**Solution** : Logging structuré + endpoint analytics.

**Fichiers à créer** :
- `api/routes/search_analytics_routes.py`
- `api/services/search_analytics_service.py`

**Endpoints** :
- `GET /api/v1/search/analytics/summary` — Résumé 24h
- `GET /api/v1/search/analytics/popular` — Requêtes populaires
- `GET /api/v1/search/analytics/slow` — Requêtes lentes (>500ms)
- `GET /api/v1/search/analytics/zero-results` — Sans résultats

**Critères de complétion** :
- [ ] Logging structuré pour chaque search
- [ ] 4 endpoints analytics fonctionnels

---

#### Story 32.9: Augmenter le TTL du cache L2
**Priority**: P2 | **Effort**: 0.5 pt | **Value**: Medium

**Problème** : TTL de 30s trop court → cache misses fréquents.

**Solution** : Augmenter à 2-5 minutes.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — TTL 30s → 120s

**Critères de complétion** :
- [ ] TTL augmenté à 120s
- [ ] Pas de stale data observée

---

#### Story 32.10: Ajouter le mode OR pour les filtres de tags
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problème** : `search_by_tags` requiert TOUS les tags (AND).

**Solution** : Ajouter un paramètre `tag_mode: "and" | "or"`.

**Fichiers à modifier** :
- `api/db/repositories/memory_repository.py` — Ajouter `tag_mode`
- `api/mnemo_mcp/tools/memory_tools.py` — Exposer `tag_mode`

**Implémentation** :
```sql
-- OR: tags && ARRAY[:tag0, :tag1]  (PostgreSQL array overlap)
```

**Critères de complétion** :
- [ ] Mode OR fonctionnel
- [ ] Mode AND par défaut (backward compatible)

---

#### Story 32.11: Index GIN trigram sur memories.content
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : La recherche lexicale skip le contenu des memories.

**Solution** : Ajouter un index GIN trigram sur `content`.

**Fichiers à modifier** :
- `api/alembic/versions/..._add_memory_content_index.py`
- `api/services/hybrid_memory_search_service.py` — Inclure content

**Critères de complétion** :
- [ ] Index GIN créé sur content
- [ ] Lexical search inclut content

---

#### Story 32.12: Augmenter le threshold de similarité
**Priority**: P2 | **Effort**: 0.5 pt | **Value**: Low

**Problème** : Threshold de 0.1 trop bas — résultats peu pertinents.

**Solution** : 0.3 pour code, 0.2 pour memory.

**Fichiers à modifier** :
- `api/services/hybrid_code_search_service.py` — 0.1 → 0.3
- `api/services/hybrid_memory_search_service.py` — 0.1 → 0.2

---

### Phase 4: Features (P3, ~8 pts)

#### Story 32.13: Search result highlighting
**Priority**: P3 | **Effort**: 2 pts

Surligner les termes correspondants dans les résultats.

#### Story 32.14: Search result deduplication
**Priority**: P3 | **Effort**: 1.5 pts

Éviter qu'un même fichier apparaisse plusieurs fois.

#### Story 32.15: Query rewriting / synonym support
**Priority**: P3 | **Effort**: 2 pts

"auth" → "authentication", "db" → "database".

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

- [ ] 3 P0 fixes implémentés
- [ ] 4 P1 fixes implémentés
- [ ] 5 P2 fixes implémentés
- [ ] 3 P3 features implémentées
- [ ] 358+ tests MCP passing
- [ ] Code search <100ms uncached
- [ ] Memory search <50ms uncached
- [ ] Cache hit rate >50%

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
