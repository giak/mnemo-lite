# 🔧 EPIC-80 : Clé cache `memsearch` — inclure `search_mode` et ne jamais cacher un résultat dégradé

> **Status:** DONE — implémenté, validé et commité (2026-08-09)
> **Priority:** P2 : caveat préexistant documenté à l'EPIC-79 Story 79.2 (correction du caveat)
> **Date:** 2026-08-09
> **Effort:** 1 h
> **Scope:** `api/mnemo_mcp/tools/memory_tools.py` + `tests/mnemo_mcp/test_memory_search_tool.py`

## Diagnostic forensique (vérifié en code, 2026-08-09)

**Caveat préexistant (documenté EPIC-79 Story 79.2)** : dans `SearchMemoryTool.execute` (`api/mnemo_mcp/tools/memory_tools.py`), la clé cache Redis `memsearch:{hash}` est construite depuis `cache_params` qui **n'inclut pas** `search_mode` :

```python
cache_params = {"q": ..., "t": ..., "tags": ..., "c": ..., "ls": ..., "l": ..., "o": ...}
```

**Conséquence exacte** : une recherche `search_mode="hybrid"` dont l'embedding échoue (cold start, service down) produit un résultat dégradé (`search_mode: text`) qui est **écrit en cache** sous une clé partagée par la requête et les filtres. Une recherche ultérieure de la même requête en mode `tag` (défaut) — ou tout autre mode — **tombait sur cette clé** et se voyait servir le résultat hybride dégradé.

**Deuxième trou (même classe)** : même avec `search_mode` dans la clé, un résultat dégradé écrit sous sa propre clé de mode (`sm:hybrid`) serait servi à une recherche ultérieure du **même mode** dont l'embedding aurait réussi. Le résultat dégradé est transitoire (cold start) : il ne doit **jamais** être caché.

## Décisions (KISS)

1. **`search_mode` demandé fait partie de la clé cache** : utiliser `requested_search_mode` (capturé avant toute réassignation, EPIC-79 Story 79.2) comme paramètre `sm` de `cache_params`. Une recherche `tag` et une recherche `hybrid` de même requête produisent désormais des clés distinctes.
2. **Un résultat dégradé (`embedding_failed`) n'est jamais écrit en cache** : le guard d'écriture passe de `if redis:` à `if redis and not embedding_failed:`. Le résultat reste retourné à l'appelant (résilience préservée), mais pas mis en cache.
3. **Pas de flush des entrées existantes** : les clés de l'ancien format n'incluent pas `sm` et ne seront plus jamais écrites (les nouvelles clés diffèrent) ; elles expirent naturellement (TTL 60-300 s). Zéro migration.

## Implémentation

### 1. `api/mnemo_mcp/tools/memory_tools.py` — clé cache

```python
cache_params = {
    "q": query_stripped,
    "t": memory_type,
    "tags": sorted(tags) if tags else [],
    "c": consumed,
    "ls": lifecycle_state,
    "l": limit,
    "o": offset,
    # EPIC-80: le mode demandé fait partie de la clé
    "sm": requested_search_mode,
}
```

### 2. `api/mnemo_mcp/tools/memory_tools.py` — écriture cache

```python
if redis and not embedding_failed:  # EPIC-80: jamais de résultat dégradé en cache
```

### 2bis. Review : `include_outcome` aussi dans la clé

Même classe de bug que `search_mode` (pointé par le reviewer) : `include_outcome` change le payload (champs `outcome_*` ajoutés à chaque mémoire) mais n'était pas dans `cache_params` — un résultat sans outcomes pouvait être servi à une requête avec `include_outcome=True`, et inversement. Ajouté : `"io": include_outcome`.

### 3. `tests/mnemo_mcp/test_memory_search_tool.py` — 2 nouveaux tests

- `test_cache_key_differs_by_search_mode` : même requête en mode `tag` puis `hybrid` (succès embedding + service hybrid) → 2 misses, 2 writes, **clés distinctes**. Vérifie que le résultat d'un mode ne peut pas être servi à l'autre.
- `test_degraded_hybrid_result_not_cached` : `hybrid` + embedding en échec → le fallback fonctionne et est signalé (`embedding_failed: true`, `search_mode: text`) mais **`setex` n'est jamais appelé**.

## Critères d'acceptation

- [x] `search_mode` demandé inclus dans la clé cache `memsearch` → clés distinctes par mode (test `test_cache_key_differs_by_search_mode`)
- [x] `include_outcome` inclus dans la clé (review : même classe de bug, payload différent)
- [x] Résultat dégradé (`embedding_failed`) jamais écrit en cache (test `test_degraded_hybrid_result_not_cached`)
- [x] Aucune régression : `pytest tests/mnemo_mcp/test_memory_search_tool.py` + `test_memory_tools.py` verts
- [x] Caveat EPIC-79 Story 79.2 mis à jour (corrigé, pointe vers EPIC-80)
- [x] Doc EPIC-80 DONE + commit conventionnel

## Notes

- **Cohérence avec le mode exécuté** : la clé porte le mode **demandé** (ce que l'appelant veut), pas le mode exécuté — c'est le paramètre de la requête. La dégradation éventuelle est gérée par le point 2 (pas de cache).
- **Consommateurs** : les réponses cache hit retournent le JSON tel quel ; les champs `metadata.embedding_failed` / `embedding_fallback_reason` (EPIC-79) ne sont présents que dans les réponses non cachées (les entrées écrites ne sont jamais dégradées). `.get()` défensif recommandé côté consommateurs.
- **KISS/YAGNI** : pas de versioning de clé, pas de flush, pas de changement de format de la valeur cachée.
