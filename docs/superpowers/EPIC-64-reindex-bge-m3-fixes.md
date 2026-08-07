# 🔧 EPIC-64 : test_reindex_bge_m3 (5 échecs, famille singleton env)

> **Status:** BACKLOG (créé le 2026-08-07, issu de la revue des EPIC 55-61)
> **Priority:** P2 : 5 tests scripts en échec, famille connue et déjà traitée en EPIC-61
> **Date:** 2026-08-07
> **Effort:** 30 min

## Problem Statement

**5 tests de `tests/scripts/test_reindex_bge_m3.py` échouent** (classe `TestBuildDbUrl`) : ils testent la construction de l'URL de base de données (`build_db_url`) en patchant des variables d'environnement, mais le singleton de configuration (ou l'env réel du conteneur) interfère avec les valeurs patchées.

**Preuve forensique** : `git stash` complet → **5 failed identiques** (documenté EPIC-58, hors périmètre à l'époque). Reproductibles isolés.

## Tests en échec (vérifiés 2026-08-07)

- `TestBuildDbUrl::test_datatable_url_priority`
- `TestBuildDbUrl::test_postgres_vars_individual`
- `TestBuildDbUrl::test_empty_user_string_falls_back_to_default`
- `TestBuildDbUrl::test_empty_password_falls_back`
- `TestBuildDbUrl::test_all_defaults_when_no_env`

## Cause racine (hypothèse documentée)

Même famille que EPIC-61 : `get_settings()` est un singleton `lru_cache` instancié avant le test ; les `monkeypatch.setenv`/`patch.dict(os.environ, ...)` sont inopérants sur la valeur déjà lue. À confirmer par diagnostic réel dans le conteneur (pattern EPIC-61 T1 : `get_settings.cache_clear()` après mutation d'env).

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Diagnostic | T1.1 Reproduire un échec isolé et confirmer la cause (singleton vs autre) | ⬜ |
| S2. Fix | T2.1 Appliquer le pattern EPIC-61 : `cache_clear()` après mutation d'env, restauration en fin de test (anti-pollution inter-fichiers) | ⬜ |
| S3. Validation | T3.1 `test_reindex_bge_m3.py` : 5/5 | ⬜ |
| | T3.2 Le fichier passe aussi exécuté en combinaison avec `tests/db/test_database.py` (robustesse à l'ordre, leçon EPIC-61 T4) | ⬜ |

## Fichiers

- `tests/scripts/test_reindex_bge_m3.py` (5 tests)
- Lecture seule : `scripts/reindex_bge_m3.py` (`build_db_url`), `api/core/settings.py`

## Validation

- 5/5 isolé + en combinaison (ordre inversé).
- Aucun changement de code prod (le comportement réel de `build_db_url` est correct ; les tests s'y alignent).

## Régressions

- Aucune : les 5 tests sont déjà en échec (préexistants prouvés).
- Attention à la pollution du singleton `get_settings` pour les fichiers exécutés ensuite (leçon EPIC-61 T4 : `patch.dict(clear=True)` + restauration du cache).
