# 🧹 EPIC-66 : Dette de tests isolée (memory_type_count, multi_watcher_daemon, lenteur tests/db)

> **Status:** BACKLOG (créé le 2026-08-07, issu de la revue des EPIC 55-61)
> **Priority:** P3 : petits correctifs isolés, aucun impact fonctionnel
> **Date:** 2026-08-07
> **Effort:** 30 min

## Problem Statement

Trois points de dette de tests isolés, sans lien entre eux, documentés dans les EPIC 57/60 :

1. **`test_memory_type_count` (1 F)** : `tests/mnemo_mcp/test_memory_models.py` attend `len(list(MemoryType)) == 6` alors que l'enum en a **8** (ARTICLE, QUINTESSENCE ajoutés sans MAJ du test). Fix trivial : 6 → 8. Préexistant prouvé par stash (EPIC-60).
2. **`test_multi_watcher_daemon.py` (skip fragile)** : le module `scripts/multi-watcher-daemon.py` est chargé via `importlib.exec_module` dans le test (même si skippé), ce qui charge son code au niveau module et peut empoisonner l'état (config structlog, cf. EPIC-57 S1). À revisiter : le skip masque un état de chargement fragile.
3. **Lenteur `tests/db/`** : les tests DB réels (TRUNCATE + TestClient avec LSP/Redis) ralentissent le run complet (documenté EPIC-57, hors périmètre).

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. count enum | T1.1 `test_memory_type_count` : 6 → 8 (avec commentaire) | ⬜ |
| S2. multi_watcher_daemon | T2.1 Auditer le skip : le test doit-il charger le module ? Peut-on le rendre déterministe (isolation structlog/exec_module) ? | ⬜ |
| S3. Lenteur tests/db (optionnel) | T3.1 Identifier le goulot (TRUNCATE réels vs TestClient LSP/Redis) et réduire le temps | ⬜ |

## Fichiers

- `tests/mnemo_mcp/test_memory_models.py` (1 ligne)
- `tests/scripts/test_multi_watcher_daemon.py` + `scripts/multi-watcher-daemon.py` (audit)
- `tests/db/` (optionnel)

## Validation

- `test_memory_models.py` : 34/34.
- `test_multi_watcher_daemon.py` : skip justifié documenté ou test déterministe.
- Collecte complète : 0 erreur.

## Régressions

- Le fix du count enum ne change que le test (le comportement réel à 8 types est correct).
- Ne pas toucher au daemon en prod sans besoin (EPIC-57 a déjà corrigé son crash structlog).
