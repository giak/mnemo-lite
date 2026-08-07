# 🔄 EPIC-58 : Backfill des embeddings manquants (861 mémoires) + P4-c rétroactif

> **Status:** ✅ DONE (implémenté et validé le 2026-08-07 : tests 5/5, dry-run réel OK)
> **Priority:** P1 : 2,2 % du corpus invisible du vectoriel + cohérence avec EPIC-53
> **Date:** 2026-08-07
> **Effort:** 1-2 h (réalisé en session)

## Problem Statement

1. **861 mémoires sur 39 634 sans `embedding_half` (2,2 %)** (vérifié en base le 2026-08-07). L'embedding async échoue (timeout, service down au moment du write) et **n'est jamais retenté** : aucune politique de retry ni de backfill. Ces mémoires sont invisibles de toute recherche vectorielle et du RRF hybride.
2. **Portée de l'EPIC-53 (P4-c) limitée aux futurs writes** : le texte vectorisé inclut désormais le titre, mais l'existant n'a pas été régénéré. Un backfill cohérent avec P4-c maximise la retrouvabilité sur tout le corpus.

## Cause racine (vérifiée dans le code le 2026-08-07)

- `_trigger_async_embedding` (EPIC-53) s'exécute au write ; en cas d'échec (timeout, service down), rien ne retente : `embedding_half` reste NULL.
- Le POC `scripts/backfill_memory_embeddings.py` existant était obsolète : colonne `embedding` seule (pas `embedding_half`), modèle nomic-768 (pas bge-m3), pas d'`embedding_source`, pas de retry.
- Un outil MCP `retry_indexing` existe pour le **code**, pas pour les **mémoires**.

## Implémentation (2026-08-07)

**Choix KISS pour T2.1** : script CLI (pas de route admin ni d'outil MCP), c'est une opération de maintenance one-shot, cohérente avec `backfill_memory_relationships.py` et `backfill_name_path.py`. `--limit N` (0 = tout) + `--dry-run`.

`scripts/backfill_memory_embeddings.py` (réécrit, POC → production) :
- **T1.1** : `SELECT id, title, content, embedding_source FROM memories WHERE embedding_half IS NULL AND deleted_at IS NULL ORDER BY created_at DESC`
- **T1.2** : texte vectorisé `title. {embedding_source or content}` (contrat EPIC-53 exact, `_build_embedding_text`) ; service réel `DualEmbeddingServiceAdapter` (bge-m3, même config que le boot API) ; retry backoff exponentiel `2**attempt` (pattern `_generate_embedding_with_retry`, pas tenacity, cohérent avec le repo)
- **T1.3** : idempotent par construction (`WHERE embedding_half IS NULL`)
- **T2.2** : rapport `{total, processed, failed, duration_seconds}` + logs par mémoire + RESTE à la fin
- Écriture : `embedding ::vector`, `embedding_half ::halfvec`, `embedding_model = EMBEDDING_MODEL` (contrat EPIC-53)

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Outil de backfill | T1.1 Requête SQL `WHERE embedding_half IS NULL` | ✅ |
| | T1.2 Retry/backoff exponentiel + texte EPIC-53 (`title. source-or-content`) | ✅ |
| | T1.3 Idempotence (WHERE embedding_half IS NULL) | ✅ |
| S2. Exposition | T2.1 Script CLI `--limit` / `--dry-run` (choix KISS vs route/MCP) | ✅ |
| | T2.2 Rapport traité/échec/durée/restant | ✅ |
| S3. Tests | T3.1 `test_backfill_missing_only` | ✅ |
| | T3.2 `test_backfill_retry_on_failure` (fail_first=1 → 2 appels, failed=0) | ✅ |
| | T3.3 `test_backfill_idempotent` (2e run : 0 appel) | ✅ |
| S4. Bonus | T4.1 `test_backfill_dry_run_writes_nothing` + `test_build_embedding_text_contract_epic53` | ✅ |

## Fichiers

- `scripts/backfill_memory_embeddings.py` (réécrit : POC → production)
- `tests/scripts/test_backfill_memory_embeddings.py` (nouveau, 5 tests, DB de test réelle)

## Validation (résultats réels 2026-08-07)

1. ✅ Tests : **5/5 passed** (`tests/scripts/test_backfill_memory_embeddings.py`), avec cleanup autouse inter-tests.
2. ✅ Dry-run réel sur la DB prod : **861 mémoires sans embedding_half** confirmées, embedding **1024D (bge-m3)** généré correctement, 0 échec.
3. ⚠️ Exécution complète (861 mémoires) : **non lancée en session** (opération de maintenance longue, à lancer par l'opérateur : `docker compose exec api python scripts/backfill_memory_embeddings.py`).
4. ⚠️ Préexistant documenté : `test_reindex_bge_m3.py` 5 F (même famille singleton `get_settings`, prouvé par stash), hors périmètre.

## Régressions

- Le backfill n'écrit que les colonnes embedding : aucun risque sur le contenu, les tags ou les relations.
- Idempotent par construction : relance sans danger.
- Script CLI : aucune surface d'attaque réseau (pas de route admin à protéger).
