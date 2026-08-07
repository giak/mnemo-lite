# 🧹 EPIC-66 : Dette de tests isolée (memory_type_count, multi_watcher_daemon, lenteur tests/db)

> **Status:** DONE (implémenté le 2026-08-07 : 1 fix, 2 audits concluants sans action)
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
| S1. count enum | T1.1 `test_memory_type_count` : 6 → 8 (avec commentaire : 8 membres vérifiés dans `api/mnemo_mcp/models/memory_models.py:59`, ARTICLE/QUINTESSENCE ajoutés après le test initial) | ✅ |
| S2. multi_watcher_daemon | T2.1 Audit : **rien à corriger** : `scripts/multi-watcher-daemon.py` utilise `structlog.wrap_logger()` (config LOCALE) depuis la correction EPIC-57, jamais `structlog.configure()` global ni `logging.basicConfig` (commenté lignes 81-83 : « The global configure poisoned the structlog config ») ; `logger = _configure_logging()` au module-level est donc sans effet global ; les 54 tests passent ; le `pytestmark` skip n'est qu'un fallback sain si le script manque | ✅ |
| S3. Lenteur tests/db | T3.1 Mesure : **77 passed en 4.82 s** (setup max 0.38 s) : goulot déjà résorbé par les EPIC 57-61 (EMBEDDING_MODE=mock + fixtures DB) ; run combiné multi_watcher+db+memory_models : 165 passed en 5.65 s | ✅ |

## Fichiers

- `tests/mnemo_mcp/test_memory_models.py` (assert 6 → 8 + docstring)
- `tests/scripts/test_multi_watcher_daemon.py` + `scripts/multi-watcher-daemon.py` : audit seul, aucun changement
- `tests/db/` : mesure seule, aucun changement

## Preuves de validation (2026-08-07)

| Vérification | Résultat |
|---|---|
| `test_memory_models.py` | **34/34 passed** (avant : 1 F / 33 P) |
| Run combiné (multi_watcher 54 + db 77 + memory_models 34) | **165 passed en 5.65 s**, aucune pollution structlog croisée |
| `tests/db/` isolé | 77 passed en 4.82 s (setup max 0.38 s) |

## Validation

- `test_memory_models.py` : 34/34.
- `test_multi_watcher_daemon.py` : skip justifié documenté ou test déterministe.
- Collecte complète : 0 erreur.

## Régressions

- Le fix du count enum ne change que le test (le comportement réel à 8 types est correct, vérifié en base de code).
- Aucun changement du daemon ni de `tests/db/` : audits documentés, le risque structlog était déjà neutralisé par EPIC-57.
