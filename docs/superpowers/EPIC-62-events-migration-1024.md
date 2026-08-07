# 🗃️ EPIC-62 : Migration de la table `events` (vector 768) vers 1024 (bge-m3)

> **Status:** BACKLOG (créé le 2026-08-07, issu de la revue des EPIC 55-61)
> **Priority:** P1 : toute recherche vectorielle sur la voie `events` est cassée depuis le passage à bge-m3
> **Date:** 2026-08-07
> **Effort:** 1-2 h + décision produit sur le backfill des 3784 événements

## Problem Statement

La table legacy `events` (3784 lignes) est restée en `embedding vector(768)` (nomic-embed-text-v1.5) alors que l'écosystème est passé à bge-m3/1024. Toute recherche vectorielle sur la voie `events` échoue :

```
ValueError: Vector dimension mismatch. Expected 768, got 1024
File "api/db/query_builders/event_query_builder.py", line 285, in build_search_vector_query
```

**Impact réel (4 échecs de tests préexistants prouvés par stash + dégradation fonctionnelle) :**
- `tests/test_search_routes.py::test_search_vector_only_found` (EPIC-57/59/61)
- `tests/test_pgvector_optimizations.py::test_halfvec_search_returns_results` (EPIC-61)
- `tests/test_integration/test_api_flow.py::TestEmbeddingIntegration.test_auto_embedding_generation` et `test_vector_search_similarity` (EPIC-59)
- `GET /v1/search/?vector_query=...` (voie events conservée en EPIC-59) : recherche vectorielle inopérante
- `POST /v1/events/` avec embedding auto-généré (1024D) : DataError « expected 768 dimensions, not 1024 » à la création

## Cause racine (vérifiée)

- `api/db/query_builders/event_query_builder.py:23` : `vector_dimension: int = 768` codé en dur (legacy nomic).
- La colonne `events.embedding` est `vector(768)` (vérifié en base).
- `EventRepository.search_vector` génère des embeddings 1024D (service bge-m3 injecté) puis les compare à la dimension 768 attendue → mismatch.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Décision produit | T1.1 Trancher : réparer la voie `events` (migration 1024) OU décommissionner la table/les routes events legacy | ⬜ |
| S2. Migration | T2.1 (si réparation) `ALTER TABLE events ALTER COLUMN embedding TYPE vector(1024)` + migration propre | ⬜ |
| | T2.2 Backfill des embeddings des 3784 événements existants avec bge-m3 (pattern `backfill_memory_embeddings.py`, EPIC-58) ou accepter NULL (existant invisible du vectoriel events) | ⬜ |
| | T2.3 Aligner `event_query_builder.vector_dimension` sur la SSOT (`EMBEDDING_DIMENSION`) au lieu du hardcode 768 | ⬜ |
| S3. Tests | T3.1 Les 4 tests famille events passent (768 → 1024) | ⬜ |
| | T3.2 `test_build_search_vector_query_*` (EPIC-61) : asserts alignés sur la nouvelle dimension | ⬜ |
| S4. Nettoyage (DRY) | T4.1 Supprimer le code mort `MemorySearchService.search_by_content/similarity/metadata` + déclarations du protocole (orphelines depuis EPIC-59) une fois la voie stabilisée | ⬜ |

## Fichiers

- `api/db/query_builders/event_query_builder.py` (dimension SSOT)
- Migration DB `events.embedding` → `vector(1024)`
- Script backfill events (à créer, ou réutiliser le pattern EPIC-58)
- `tests/test_search_routes.py`, `tests/test_pgvector_optimizations.py`, `tests/test_integration/test_api_flow.py`
- `api/interfaces/services.py` + `api/services/memory_search_service.py` (nettoyage code mort, T4.1)

## Validation

- `test_search_vector_only_found`, `test_halfvec_search_returns_results`, `TestEmbeddingIntegration` ×2 : verts.
- `GET /v1/search/?vector_query=texte` : 200 avec résultats réels sur les events.
- `POST /v1/events/` avec embedding auto : 201 (plus de DataError 768).
- Collecte complète : 0 erreur, aucun F nouveau.

## Régressions

- Changement de dimension de colonne : les données existantes `vector(768)` ne sont pas lisibles par une colonne 1024 → nécessite ALTER avec validation (`USING embedding::vector(1024)` échoue si données 768 présentes ; le backfill doit passer par une colonne temporaire ou régénération).
- Les recherches vectorielles events en prod sont déjà cassées (500) : la migration ne peut que réparer.
- Dépend de la décision S1 (réparer vs décommissionner) : si décommission, les routes `/v1/events/*` et `GET /v1/search/?filter_metadata` (10 tests) sont concernées.
