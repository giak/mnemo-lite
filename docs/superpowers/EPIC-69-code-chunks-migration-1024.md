# 🧩 EPIC-69 : Migration `code_chunks` - colonnes TEXT 768 → 1024 (CODE reste 768)

> **Status:** BACKLOG (créé le 2026-08-07, issu du résidu documenté EPIC-62)
> **Priority:** P2 : la voie TEXT de code_chunks est cassée depuis le passage à bge-m3 (insertions 1024D dans colonnes 768D)
> **Date:** 2026-08-07
> **Effort:** 2-3 h + backfill des embeddings TEXT

## Problem Statement

La table `code_chunks` (53 268 lignes, 451 MB) a **4 colonnes d'embedding toutes en 768D** :
`embedding_text`, `embedding_text_half`, `embedding_code`, `embedding_code_half`.

Or les modèles actuels (SSOT `api/core/embedding_models.py`) produisent :
- **TEXT** : `BAAI/bge-m3` → **1024D**
- **CODE** : `jinaai/jina-embeddings-v2-base-code` → **768D**

**Preuve forensique en base prod** (incohérence TEXT) :
```
total=53268 | avec_text=120 | avec_code=19348 | avec_text_half=120 | avec_code_half=19348
```
Seulement **120** chunks ont un `embedding_text` : les insertions TEXT récentes (1024D via `CodeIndexingService.generate_embeddings_batch(domain=TEXT)`) échouent sur la colonne `vector(768)` (DataError dimension), alors que CODE (768D) passe (19 348 remplis).

**Impact** :
- Toute indexation de chunks à docstring (domaine TEXT) perd son embedding → chunk invisible de la recherche vectorielle TEXT.
- `GET .../search` mode `vector`/`hybrid` avec `embedding_domain="TEXT"` (ui_routes) : le vecteur de requête est généré en 1024D → mismatch contre la colonne 768.
- `VectorSearchService._expected_dim_for_domain` (EPIC-62) renvoie 768 pour les deux domaines : correct pour CODE, mais verrouille TEXT à 768 tant que le schéma n'est pas migré.

## Cause racine (vérifiée)

- Même famille que l'EPIC-62 : la migration v10→v11 (bge-m3/1024) a migré `memories` mais **jamais `code_chunks`** (resté 768 pour les 4 colonnes).
- `CodeIndexingService` (api/services/code_indexing_service.py:491-515) génère les embeddings avec `generate_embeddings_batch(domain=TEXT|CODE)` → le domaine TEXT produit 1024D inséré dans `vector(768)` → DataError silencieux (l'embedding est perdu, le chunk reste sans embedding_text).
- `code_chunks` est alimenté via le MCP (`api/mnemo_mcp/tools/indexing_tools.py`, `CodeIndexingService`), vivant.

## Décision S1 : RÉPARER (voie vivante, migration par domaine)

`code_chunks` est vivante : 53 268 chunks, indexée via le MCP, utilisée par `hybrid_code_search_service` et `ui_routes` (mode vector/hybrid). Décommissionner n'a pas de sens (c'est le socle de la recherche de code).

**Spécificité vs EPIC-62 : migration DIFFÉRENCIÉE par domaine** :
- `embedding_text` + `embedding_text_half` : 768 → **1024** (bge-m3)
- `embedding_code` + `embedding_code_half` : **reste 768** (jina-code) : pas de migration

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Décision | T1.1 Réparer par domaine (TEXT 1024, CODE 768) | ⬜ |
| S2. Migration SQL | T2.1 `db/migrations/v12_to_v13_code_chunks_text_1024d.sql` : DROP index HNSW text (`idx_code_embedding_text`, `idx_code_emb_text_half`), DROP+RECREATE `embedding_text`/`embedding_text_half` en 1024 (pattern v10→v11 : un vecteur 768 ne peut pas etre ALTER TYPEd), recréer index HNSW cosine (m=16, ef_construction=128 pour halfvec, cohérent avec l'existant) | ⬜ |
| | T2.2 Index CODE intacts (768) : vérifier qu'aucun DROP global ne les touche | ⬜ |
| S3. Code | T3.1 `VectorSearchService._expected_dim_for_domain` : TEXT → `EMBEDDING_DIMENSION` (1024), CODE → `CODE_EMBEDDING_DIMENSION` (768), soit l'inverse du compromis EPIC-62 une fois le schéma migré ; mise à jour du docstring (supprime la note « schema legacy 768 ») | ⬜ |
| S4. Backfill | T4.1 Script `scripts/backfill_code_chunks_text_embeddings.py` (pattern EPIC-62/58) : régénère `embedding_text` + `embedding_text_half` pour les chunks de domaine TEXT (`WHERE embedding_text IS NULL AND embedding_code IS NULL` à valider contre la logique has_docstring du service), dry-run + limit | ⬜ |
| S5. Tests | T5.1 Adapter `tests/test_pgvector_optimizations.py` : asserts SQL `halfvec(768)` → `halfvec(1024)` pour text (l.321-323, 341), vecteurs `[0.1] * 768` → 1024 pour les tests de domaine TEXT (l.90, 111, 128, 379) ; CODE reste 768 | ⬜ |
| | T5.2 Vérifier `tests/e2e/test_batch_indexing_full.py:127` (compte chunks avec embedding_code, non impacté) et le run de `test_halfvec_search_returns_results` (domaine CODE, inchangé) | ⬜ |
| | T5.3 Collecte complète : aucun F nouveau | ⬜ |

## Fichiers

- `db/migrations/v12_to_v13_code_chunks_text_1024d.sql` (nouveau)
- `scripts/backfill_code_chunks_text_embeddings.py` (nouveau, pattern EPIC-62)
- `api/services/vector_search_service.py` (`_expected_dim_for_domain`)
- `tests/test_pgvector_optimizations.py`
- SQL de test : vérifier `db/scripts/setup.sql` / fixtures qui créent `code_chunks` (768 → 1024 pour text)

## Validation

- `test_halfvec_search_returns_results` : toujours vert (CODE 768 inchangé).
- `test_pgvector_optimizations.py` : asserts alignés sur la dimension par domaine.
- Insertion réelle d'un chunk TEXT via `CodeIndexingService` : embedding 1024D écrit sans DataError.
- Migration prod appliquée : `embedding_text` = vector(1024), `embedding_code` = vector(768).
- Backfill prod : chunks TEXT sans embedding régénérés, 0 échec.

## Régressions

- **Data loss** : les 120 `embedding_text` 768D existants sont perdus par le DROP COLUMN → backfill requis (pattern EPIC-62).
- **Différenciation par domaine** : si un fix global aligne les 4 colonnes sur 1024, CODE casserait (jina-code = 768). Restreindre la migration aux colonnes TEXT.
- **`_expected_dim_for_domain`** : le changement TEXT→1024 doit être atomique avec la migration SQL (sinon la recherche TEXT casse entre les deux).
- Dépend du backfill `events` EPIC-62 en cours (ressource CPU partagée) : séquencer les backfills.
