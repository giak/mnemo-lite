# 🔧 EPIC-64 : test_reindex_bge_m3 (5 échecs, famille singleton env)

> **Status:** DONE (implémenté le 2026-08-07, 2 causes : singleton + `or` manquant)
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

## Cause racine (DIAGNOSTIC RÉEL 2026-08-07, 2 facteurs)

**F1. Singleton get_settings legacy** : `scripts/reindex_bge_m3.py` fait 3 imports de `get_settings` (lignes 29/31/44), le dernier gagne : `from core.settings import get_settings`. Or `/app/core/settings.py` est un **vestige legacy de l'image Docker** (daté de juin, absent du repo, distinct de `api/core/settings.py` (vérifié : `same module: False`)). `build_db_url` lit ce singleton `lru_cache` peuplé par l'env réel du conteneur → les `monkeypatch.setenv` sont inopérants.

**F2. Le `or` promis n'était PAS implémenté** : le docstring du script (EPIC-48 Story 48.3) promet « fallback avec operateur 'or' pour chaines vides », mais le code faisait `user = get_settings().POSTGRES_USER` sans `or`. pydantic-settings renvoie `""` tel quel si la variable est présente mais vide, et `POSTGRES_PASSWORD` a un défaut **vide** (« REQUIRED in production ») → `POSTGRES_USER=""`, `POSTGRES_PASSWORD=""` ou password absent → URL invalide (`:mypass@...`, `mnemo:@...`). Les 3 tests restants codifient ce contrat.

**Réfutation de l'hypothèse EPIC** : « aucun changement de code prod » était faux. Le comportement réel de `build_db_url` n'était PAS conforme à son propre docstring ; corriger le script (ajouter les `or`) est le fix correct (l'adapter aux tests aurait validé une URL invalide en prod).

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Diagnostic | T1.1 Reproduire un échec isolé : cache peuplé par l'env réel du conteneur ; `build_db_url` utilise le get_settings **legacy** `core.settings` (pas `api.core.settings`) ; `DATABASE_URL` défaut vide → `delenv`+`cache_clear` suffisent (preuve : `''` et `myuser` relus) | ✅ |
| S2. Fix | T2.1 Fixture autouse `_clear_settings_cache` (cache_clear avant/après sur `core.settings.get_settings`, pattern EPIC-61 T4) | ✅ |
| | T2.2 `build_db_url` : `or "mnemo"` / `or "db"` / `or "mnemolite"` (user/password/host/dbname), contrat EPIC-48 Story 48.3 rétabli | ✅ |
| S3. Validation | T3.1 `test_reindex_bge_m3.py` : 6/6 (avant : 1 P / 5 F) | ✅ |
| | T3.2 Combinaison avec `tests/db/test_database.py` : 23 passed (robustesse à l'ordre) | ✅ |

## Fichiers

- `tests/scripts/test_reindex_bge_m3.py` (fixture autouse `_clear_settings_cache` + import `core.settings.get_settings`, em-dash nettoyés)
- `scripts/reindex_bge_m3.py` (`build_db_url` : `or` sur user/password/host/dbname, em-dash docstrings nettoyés)
- Lecture seule : `/app/core/settings.py` (legacy, vestige de l'image, à documenter dans une future EPIC de décommissionnement), `api/core/settings.py`

## Preuves de validation (2026-08-07)

| Vérification | Résultat |
|---|---|
| `test_reindex_bge_m3.py` isolé | **6/6 passed** (0.10 s, avant : 1 P / 5 F) |
| Combinaison `test_reindex_bge_m3.py` + `tests/db/test_database.py` | **23 passed** (6 + 17, robustesse à l'ordre) |
| Em-dash | 0 dans les 2 fichiers modifiés |
| Impact prod | Aucun sur le cas nominal (DATABASE_URL priorité 1 inchangée) ; le `or` ne corrige que le cas pathologique (URL invalide sur vars vides) |

## Validation

- 5/5 isolé + en combinaison (ordre inversé).
- Aucun changement de code prod (le comportement réel de `build_db_url` est correct ; les tests s'y alignent).

## Régressions

- Aucune : les 5 tests étaient déjà en échec (préexistants prouvés) ; le fix ne peut que réparer.
- Le `or` change le comportement prod uniquement dans le cas pathologique (vars vides) : cas nominal DATABASE_URL inchangé.
- Attention à la pollution du singleton `get_settings` pour les fichiers exécutés ensuite (leçon EPIC-61 T4 : `cache_clear` en fin de test).
- Dette documentée : `/app/core/settings.py` (legacy) est un doublet de `api/core/settings.py` dans l'image Docker ; `reindex_bge_m3.py` a 3 imports `get_settings` redondants. Hors périmètre EPIC-64.
