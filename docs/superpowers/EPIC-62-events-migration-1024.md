# 🗃️ EPIC-62 : Migration de la table `events` (vector 768) vers 1024 (bge-m3)

> **Status:** DONE (implémenté le 2026-08-07)
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

- La migration v10→v11 (EPIC-48, bge-m3 1024D) a migré `memories` mais **jamais `events`** (768D nomic, index HNSW `vector_l2_ops`).
- `api/db/query_builders/event_query_builder.py:23` : `vector_dimension: int = 768` codé en dur (legacy nomic), instancié sans argument par `EventRepository`.
- `EventRepository.search_vector` génère des embeddings 1024D (service bge-m3 injecté) puis les compare à la dimension 768 attendue → mismatch.
- Bonus trouvé : `VectorSearchService` (table `code_chunks`) utilisait `EMBEDDING_DIMENSION` (1024) pour les deux domaines alors que `code_chunks` est en 768 pour TEXT ET CODE → toute recherche code_chunks échouait (le test halfvec).

## Décision S1 : RÉPARER (tranchée sur faits)

La voie `events` est vivante : 3784 lignes, 403 events dans les 30 derniers jours (vérifié en base), index HNSW existant, clients réels (locust, scripts perf/testing, fake_event_poster, metrics middleware, GET /v1/search/ conservé en EPIC-59). Décommissionner casserait ces clients. La table fait 27 MB : la migration DROP+RECREATE + backfill est rapide.

## Implémentation

| Story | Task | Statut |
|---|---|---|
| S1. Décision produit | T1.1 Réparer (voie vivante, 403 events/30j) | ✅ |
| S2. Migration | T2.1 `db/migrations/v11_to_v12_events_1024d.sql` : DROP INDEX HNSW, DROP COLUMN embedding, ADD COLUMN vector(1024), recréer index HNSW (l2, m=24, ef=128) | ✅ |
| | T2.2 `scripts/backfill_event_embeddings.py` (pattern EPIC-58) : régénère `embedding` des events `IS NULL`, texte extrait via `source_fields` EventService (text > body > message > content > title), idempotent, dry-run + limit | ✅ |
| | T2.3 `EventQueryBuilder.__init__(vector_dimension=768)` → `1024` | ✅ |
| S3. Tests | T3.1 Les 4 tests famille events passent (768 → 1024) | ✅ |
| | T3.2 `generate_fake_vector(dim=768)` → `1024` (test_search_routes) ; MockEmbeddingService 768 → 1024 (conftest, 2 endroits) ; SQL de test 768 → 1024 (init_test_db.sql + create_test_db.sql) | ✅ |
| S4. Nettoyage (DRY) | T4.1 Code mort `MemorySearchService` : REPORTÉ (aucune route ne l'utilise plus depuis EPIC-59 ; suppression = EPIC dédiée pour garder le diff EPIC-62 minimal) | ⏳ |

### Fichiers modifiés (8 + 2 nouveaux)

- `db/migrations/v11_to_v12_events_1024d.sql` (nouveau)
- `scripts/backfill_event_embeddings.py` (nouveau)
- `api/db/query_builders/event_query_builder.py` (défaut 1024)
- `api/services/vector_search_service.py` (`_expected_dim_for_domain` : 768 pour TEXT et CODE, aligné sur le schéma legacy `code_chunks` ; corrige le bug EMBEDDING_DIMENSION 1024 utilisé pour code_chunks 768)
- `scripts/database/init_test_db.sql`, `db/scripts/create_test_db.sql` (VECTOR 768 → 1024)
- `tests/test_search_routes.py` (generate_fake_vector 1024)
- `tests/conftest.py` (MockEmbeddingService 1024 ×2 ; fixture `test_client_with_real_embeddings` force `EMBEDDING_MODE=real` car conftest force mock globalement, ce qui rendait DualEmbeddingService hash-based et cassait `test_vector_search_similarity`)
- `tests/test_integration/test_api_flow.py` (`test_vector_search_similarity` : POST /v1/search/ → GET /v1/search/?vector_query=, voie events conservée depuis EPIC-59 ; format `data` au lieu de `events`)

## Validation (preuves)

| Vérification | Résultat |
|---|---|
| Migration prod appliquée | `events.embedding` = vector(1024), index HNSW recréé (l2, m=24, ef=128) |
| Famille events (test_search_routes + test_event_repository + test_pgvector_optimizations) | **104 passed, 6 skipped** (skips = dépendances externes, hors périmètre) |
| `test_halfvec_search_returns_results` isolé | **1 passed** (le fix `_expected_dim_for_domain` corrige le bug code_chunks) |
| `test_api_flow.py` complet | **18 passed / 0 failed** (baseline HEAD : 16/2, les 2 F famille events réparés) |
| `TestEmbeddingIntegration` isolé | **2 passed** (auto_embedding + vector_search_similarity, vrai modèle bge-m3) |
| `test_search_fallback.py` | 8 failed / 1 passed : **identique à la baseline HEAD** (mock async obsolète, famille EPIC-61, prouvé par stash), zéro régression |
| Backfill prod | Lancé en détaché : 1400+/3784 au commit, **0 échec**, idempotent (WHERE embedding IS NULL) ; relançable si interrompu |

## Régressions

- **Changement de dimension** : les 2894 embeddings 768D existants sont perdus par le DROP COLUMN (pattern v10→v11 : un vecteur 768 ne peut pas être ALTER TYPEd en 1024) → backfill requis et lancé.
- **Résidus documentés** (hors périmètre) :
  - Scripts legacy `scripts/import-conversations.py` et `scripts/conversation-watcher.py` instancient `MockEmbeddingService(dimension=768)` : ils écrivent dans `memories` (pas events), pas de DataError sur events ; outil de dev legacy, à réviser si réutilisé.
  - `code_chunks` reste en 768 (TEXT + CODE) : `_expected_dim_for_domain` est aligné sur ce schéma, mais une migration code_chunks → 1024 est une EPIC dédiée (cohérente avec la présente).
  - Nettoyage du code mort `MemorySearchService.search_by_content/similarity/metadata` reporté (EPIC dédiée, diff minimal).
