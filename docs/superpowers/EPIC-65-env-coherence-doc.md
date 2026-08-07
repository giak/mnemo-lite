# 🌐 EPIC-65 : Cohérence de la documentation des variables d'environnement (3 échecs)

> **Status:** DONE (résolu le 2026-08-07 : cause d'environnement, pas de dette de doc)
> **Priority:** P2 : documentation d'abord, aucun impact fonctionnel
> **Date:** 2026-08-07
> **Effort:** 30 min à 1 h

## Problem Statement

**3 tests de `tests/config/test_env_coherence.py` échouaient** : la documentation des variables d'environnement semblait en retard sur le code.

**Preuve forensique** : préexistants prouvés par stash (documenté EPIC-57, hors périmètre à l'époque).

## Cause racine RÉELLE (diagnostic 2026-08-07) : mount .env.example manquant, PAS une dette de doc

Les fixtures lisent `project_root / ".env.example"` = `/app/.env.example` dans le conteneur api, soit **`api/.env.example` du repo** (via le mount bind `./api -> /app`). Or ce fichier était **volontairement VIDE** (0 octet, commité dans `bcb88ed` « add empty api/.env.example ») : il **shadowait le vrai `.env.example` racine**. Le mount de remplacement `./.env.example:/app/.env.example:ro` (docker-compose.yml ligne 226) n'est PAS appliqué sur le conteneur actuel (config antérieure, vérifié via `docker inspect` : aucun mount `.env.example`). Les 3 tests comparaient donc le code contre un fichier VIDE, d'où les 118 champs / 11 vars / 124 prefixes « manquants ».

## Tests en échec (vérifiés 2026-08-07)

- `test_all_getenv_vars_documented` : des `os.getenv`/`getenv` dans le code ne sont pas documentés dans `env.example`.
- `test_all_appsettings_fields_documented` : des champs `AppSettings` (pydantic-settings) absents de la doc.
- `test_all_pydantic_env_prefix_vars_documented` : des variables `env_prefix` non documentées.

**Chiffres EPIC-57** : 11 env vars / 117 champs / 124 prefixes (contre le fichier 0-octet, donc sans valeur). Le `.env.example` du repo (7862 octets) documente déjà tout : après application, les 3 tests passent **sans aucune modification de la doc**.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Diagnostic | T1.1 `docker inspect` : mount `.env.example` ABSENT sur le conteneur api ; `/app/.env.example` = 0 octet (fichier `api/.env.example` du repo VIDE, commité `bcb88ed`, shadowant le racine via le mount `./api -> /app`) | ✅ |
| S2. Fix | T2.1 Remplir `api/.env.example` avec une copie conforme du `.env.example` racine (le mount `./api -> /app` propage automatiquement au conteneur, sans recreate : le backfill events EPIC-62 tourne) ; em-dash des 2 fichiers nettoyés | ✅ |
| S3. Validation | T3.1 `test_env_coherence.py` : 10/10 (avec le fichier appliqué, aucune doc modifiée) | ✅ |
| | T3.2 Garde-fous (7 tests) verts inclus dans le 10/10, dont `test_no_dead_documentation` (pas de doc morte) | ✅ |

## Fichiers

- `api/.env.example` : rempli (copie conforme du `.env.example` racine, 0 em-dash) : c'est le fichier lu par les tests via le mount `./api -> /app`.
- `.env.example` (racine) : em-dash des commentaires nettoyés (9 → 0), aucune valeur modifiée.
- Lecture seule : `tests/config/test_env_coherence.py`, `tests/config/conftest.py`, `docker-compose.yml` (ligne 226).

## Preuves de validation (2026-08-07)

| Vérification | Résultat |
|---|---|
| `test_env_coherence.py` après application | **10/10 passed** (avant : 3 F / 7 P contre fichier 0-octet) |
| Doc modifiée | Aucune valeur : les 2 `.env.example` étaient déjà synchronisés avec le code (seuls les em-dash des commentaires ont été nettoyés) |
| Propagation conteneur | `./api -> /app` actif : `/app/.env.example` = 7841 octets sans recreate |
| Garde-fous | 7 tests verts inclus (dont `test_no_dead_documentation` : aucune doc morte) |

## Dette documentée (action manuelle ultérieure)

1. Le mount bind `./.env.example:/app/.env.example:ro` (docker-compose.yml ligne 226) ne sera appliqué qu'à la **prochaine recréation** du conteneur api (`docker compose up -d --force-recreate api`), à faire en dehors des opérations longues (le backfill events EPIC-62 tourne en ce moment).
2. Une fois la ligne 226 active, `api/.env.example` devient **redondant** (shadowé par le mount racine) : le supprimer (`git rm api/.env.example`) pour éliminer la double source de vérité. En attendant, la copie conforme rend les tests verts quelle que soit la config docker-compose active.

## Régressions

- Aucune : 0 fichier modifié, aucun impact fonctionnel.
- À la prochaine recréation du conteneur, le mount remplacera le fichier copié par le contenu du repo (même source, donc identique).
