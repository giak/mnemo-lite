# 🔄 EPIC-58 : Backfill des embeddings manquants (861 mémoires) + P4-c rétroactif

> **Status:** BACKLOG (proposé le 2026-08-07)
> **Priority:** P1 : 2,2 % du corpus invisible du vectoriel + cohérence avec EPIC-53
> **Date:** 2026-08-07
> **Effort:** 1-2 h

## Problem Statement

1. **861 mémoires sur 39 634 sans `embedding_half` (2,2 %)** (vérifié en base le 2026-08-07). L'embedding async échoue (timeout, service down au moment du write) et **n'est jamais retenté** : aucune politique de retry ni de backfill. Ces mémoires sont invisibles de toute recherche vectorielle et du RRF hybride.
2. **Portée de l'EPIC-53 (P4-c) limitée aux futurs writes** : le texte vectorisé inclut désormais le titre, mais l'existant n'a pas été régénéré. Un backfill cohérent avec P4-c maximise la retrouvabilité sur tout le corpus.

## Cause racine (vérifiée dans le code le 2026-08-07)

- `scripts/` ne contient que `backfill_memory_relationships.py` et `migrate_v2_to_v3.py` : **aucun backfill d'embeddings**.
- `_trigger_async_embedding` (EPIC-53) s'exécute au write ; en cas d'échec (timeout, service down), rien ne retente : `embedding_half` reste NULL.
- Un outil MCP `retry_indexing` existe pour le **code** (indexation code), pas pour les **mémoires**.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Outil de backfill | T1.1 Requête SQL `SELECT id, title, content, embedding_source FROM memories WHERE embedding_half IS NULL` | ⬜ |
| | T1.2 Régénération avec retry/backoff (tenacity, comme le worker) et texte `title + embedding_source or content` (cohérent EPIC-53) | ⬜ |
| | T1.3 Idempotence : relancer ne régénère pas l'existant (WHERE embedding_half IS NULL) | ⬜ |
| S2. Exposition | T2.1 Route admin REST (`POST /api/v1/admin/backfill-embeddings`) OU outil MCP (`backfill_memories_embeddings`) : choisir le plus KISS | ⬜ |
| | T2.2 Rapport : nombre traité, nombre en échec (après retries), durée | ⬜ |
| S3. Tests | T3.1 `test_backfill_missing_only` : seules les mémoires `embedding_half IS NULL` sont traitées | ⬜ |
| | T3.2 `test_backfill_retry_on_failure` : échec embedding → retry avec backoff, pas d'abandon | ⬜ |
| | T3.3 `test_backfill_idempotent` : relancer ne régénère pas l'existant | ⬜ |

## Fichiers

- `scripts/backfill_memory_embeddings.py` (nouveau) ou route dans `api/routes/`.
- `api/mnemo_mcp/tools/indexing_tools.py` (si outil MCP retenu) ou `api/routes/memories_routes.py`.
- `tests/mnemo_mcp/test_indexing_tools.py` ou `tests/api/test_memories_routes.py`.

## Validation

- Après exécution : requête `SELECT count(*) FROM memories WHERE embedding_half IS NULL` → proche de 0 (hors échecs résiduels rapportés).
- Une mémoire précédemment invisible (ex. consolidée `58cc0e69`) retrouvée par une recherche vectorielle.

## Régressions

- Le backfill n'écrit que la colonne embedding : aucun risque sur le contenu, les tags ou les relations.
- Idempotent par construction (WHERE embedding_half IS NULL) : relance sans danger.
- La route admin doit être protégée (auth) ou en tout cas documentée comme opération de maintenance.
