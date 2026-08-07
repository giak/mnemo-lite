# 🔀 EPIC-59 : REST, unifier les POST de recherche morts sur la logique hybride unique

> **Status:** ✅ DONE (2026-08-07)
> **Priority:** P2 : le GET fonctionne, mais des endpoints trompeurs restaient exposés
> **Date:** 2026-08-07
> **Effort:** ~2 h

## Problem Statement

Trois voies de recherche REST étaient mortes ou trompeuses alors qu'une seule fonction hybride fiable existe :

- `POST /v1/search/` → `{"detail": "Search failed"}` (500).
- `POST /v1/search/content`, `POST /v1/search/similarity` → `{"data": []}` même sur requête existante.
- `POST /api/v1/memories/search` (body JSON) : déléguait déjà à `_search_memories` (rien à faire).
- **Seule voie fiable** : `GET /api/v1/memories/search?query=...` qui délègue à `_search_memories`, la même logique que `search_memory` MCP.

## Cause racine (prouvée forensiquement le 2026-08-07)

Le log serveur montre l'erreur exacte du `POST /v1/search/` :

```
ValueError: Vector dimension mismatch. Expected 768, got 1024
File "db/query_builders/event_query_builder.py", line 285, in build_search_vector_query
```

Deux voies de recherche divergentes coexistent :

1. **Voie legacy `events`** : `MemorySearchService` → `EventRepository.search_vector` → table `events` (`embedding vector(768)`, 3784 lignes, legacy nomic-768). Le query builder attend 768 mais l'embedding service injecté produit 1024 (bge-m3) → toute recherche vectorielle échoue en 500.
2. **Voie fiable `memories`** : `HybridMemorySearchService` (bge-m3 1024) via `_search_memories` (GET/POST `/api/v1/memories/search` + MCP).

## Décisions (KISS / DRY / YAGNI)

| Story | Task | Décision | Statut |
|---|---|---|---|
| S1. Unification | T1.1 Inventorier les routes | Fait : 5 routes dans `search_routes.py` (monté en `api/main.py:537`), 3 dans `memories_routes.py` | ✅ |
| | T1.2 Faire déléguer les POST à `_search_memories` | `POST /v1/search/` réécrit : délègue à `_search_memories` (query requis, memory_type, tags, limit, offset). Réponse `MemorySearchResponse` (format fiable unique). `POST /api/v1/memories/search` déléguait déjà | ✅ |
| | T1.3 Chemin divergent | `GET /v1/search/` conservé intact (voie events legacy, 10 tests + clients) ; `search_by_content`/`similarity`/`metadata` du service deviennent du code mort documenté (nettoyage futur, YAGNI). Migration de la table `events` vers 1024 = EPIC dédiée | ✅ |
| S2. Tests | T2.1 POST == GET | `test_post_search_returns_same_as_get` : mêmes ids et ordre, mémoire de test trouvée | ✅ |
| | T2.2 body vide 422 | `test_post_search_empty_body_422` : `{}` et sans query → 422 (validation pydantic) | ✅ |
| | T2.3 body JSON filtres | `test_post_search_json_body_filters` : memory_type + tags filtrent correctement | ✅ |

### Routes supprimées (orphelines vérifiées : 0 client, 0 test)

- `POST /v1/search/content`, `POST /v1/search/similarity` (renvoyaient `[]`),
- `GET /v1/search/metadata` (doublon de `GET /v1/search/?filter_metadata=`).
- Modèles supprimés : `SearchTextQuery`, `TestSearchResponse`.

### Clients mis à jour (contrat `results` au lieu de `events`)

- `tests/load/locust_test.py` : `search_code` vérifie `"results"` ; `filter_by_repository` (metadata-only, serait 422) remplacé par `search_with_tags` (query + tags). Les TaskSet `rapid_search`/`surge_traffic` envoyaient déjà `query` valide → inchangés.
- `scripts/testing/test_application.sh` : `.events | length` → `.results | length`.
- `scripts/performance/apply_optimizations.sh` : body `{"limit": 5}` (sans query → 422) → `{"query": "perf test", "limit": 5}`.
- `tests/test_integration/test_api_flow.py` : la recherche d'événements par métadonnées passe par `GET /v1/search/?filter_metadata=...` (voie events conservée), format `data`.

## Validation (preuves)

| Vérification | Résultat |
|---|---|
| `tests/test_search_routes.py` | 13 passed, 1 failed (`test_search_vector_only_found`, préexistant EPIC-57) |
| `tests/test_integration/test_api_flow.py` | 16 passed, 2 failed (TestEmbeddingIntegration, préexistants, famille events 768 vs 1024 ; prouvé par stash HEAD : 2 failed identiques) |
| Collecte complète | 1651 tests (avant 1648, +3), 0 erreur |
| Preuve prod (restart mnemo-api) | `POST /v1/search/` {"query":"parrainages"} → 200 avec résultats réels (mémoire « Parrainages présidentielle 2022 » trouvée) ; `{}` → 422 ; `POST /v1/search/content` → 404 |
| Cycle d'import | Aucun : `memories_routes` n'importe jamais `search_routes` |

## Régressions

- Unification = un seul code path pour les POST : les divergences GET/POST disparaissent par construction.
- `GET /v1/search/` (events) : comportement conservé à l'identique (10 tests intacts).
- Préexistants hors périmètre (documentés EPIC-57/61) : `test_search_vector_only_found`, `TestEmbeddingIntegration.test_auto_embedding_generation` et `test_vector_search_similarity` (table `events` encore en 768, embedding service en 1024). Migration de la table `events` = EPIC dédiée.
