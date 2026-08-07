# 🌐 EPIC-65 : Cohérence de la documentation des variables d'environnement (3 échecs)

> **Status:** BACKLOG (créé le 2026-08-07, issu de la revue des EPIC 55-61)
> **Priority:** P2 : documentation d'abord, aucun impact fonctionnel
> **Date:** 2026-08-07
> **Effort:** 30 min à 1 h

## Problem Statement

**3 tests de `tests/config/test_env_coherence.py` échouent** : la documentation des variables d'environnement (`env.example`/doc) est en retard sur le code.

**Preuve forensique** : préexistants prouvés par stash (documenté EPIC-57, hors périmètre à l'époque).

## Tests en échec (vérifiés 2026-08-07)

- `test_all_getenv_vars_documented` : des `os.getenv`/`getenv` dans le code ne sont pas documentés dans `env.example`.
- `test_all_appsettings_fields_documented` : des champs `AppSettings` (pydantic-settings) absents de la doc.
- `test_all_pydantic_env_prefix_vars_documented` : des variables `env_prefix` non documentées.

**Chiffres documentés (EPIC-57)** : 11 env vars non documentées ; 117 champs `AppSettings` ; 124 variables `env_prefix`. Les 7 autres tests du fichier (garde-fous : pas de `getenv` ad hoc hors settings, pas de hardcode localhost, pas de mot de passe en dur, cohérence des défauts) passent.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Diagnostic | T1.1 Lister les 11 vars manquantes et les champs/prefixes non documentés (output des 3 tests) | ⬜ |
| S2. Doc | T2.1 Compléter `env.example` (ou la doc de référence lue par les tests) : vars, champs AppSettings, prefixes | ⬜ |
| S3. Validation | T3.1 `test_env_coherence.py` : 10/10 | ⬜ |
| | T3.2 Vérifier que les 7 tests de garde-fou restent verts (aucune doc morte ajoutée) | ⬜ |

## Fichiers

- `tests/config/test_env_coherence.py` (3 tests) + `tests/config/conftest.py` (fixtures de lecture)
- Doc de référence : `.env.example` ou équivalent lu par les fixtures
- Lecture seule : `api/core/settings.py` (AppSettings), `docker-compose.yml`

## Validation

- 10/10 sur `tests/config/test_env_coherence.py`.
- Collecte complète : 0 erreur.

## Régressions

- La doc doit rester synchronisée avec le code : les tests de garde-fou (`test_no_dead_documentation`) échoueront si on documente des vars inexistantes.
- Aucun impact fonctionnel (documentation uniquement).
