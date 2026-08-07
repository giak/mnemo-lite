# 🛠 EPIC-51 : Réparation du worker de conversations (crash-loop)

> **Status:** DONE
> **Priority:** P0 : Critique (auto-save des conversations coupé)
> **Date:** 2026-08-07
> **Constat:** `mnemo-worker` en crash-loop, 1 506 redémarrages, `ModuleNotFoundError: No module named 'api'`
> **Effort:** ~15 min

## Problem Statement

`conversation_worker.py` importe `api.core.settings` (ligne 13) pour la configuration, mais `docker/Dockerfile.worker` ne copiait que `workers/`, jamais le package `api/`. Le conteneur tournait avec `WORKDIR /app` sans `/app/api` → crash à chaque démarrage. Conséquence : le pipeline d'auto-save des conversations (Redis Streams `conversations:autosave`) était à terre.

## Cause racine (vérifiée)

- `docker/Dockerfile.worker` : `COPY workers/ ./workers/` uniquement.
- 4 fichiers worker importent `api.core.settings` : `conversation_worker.py`, `utils/db.py`, `utils/embeddings.py`, `utils/redis_utils.py`.
- `workers/requirements.txt` avait `pydantic==2.5.3`, incompatible avec `pydantic-settings` 2.5.2 (exige `pydantic>=2.7.0`, vérifié via PyPI).
- `conversation_worker.py` n'importe AUCUN `workers.utils` → pas besoin d'asyncpg/numpy/sentence-transformers dans l'image worker.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Copier le package api dans l'image worker | T1.1 Ajouter `COPY api/ ./api/` dans `docker/Dockerfile.worker` | ✅ |
| S2. Aligner les dépendances Python du worker | T2.1 `pydantic==2.5.3` → `pydantic>=2.7.1` | ✅ |
| | T2.2 Ajouter `pydantic-settings>=2.5.2` | ✅ |
| S3. Reconstruire et valider | T3.1 `docker compose build worker` | ✅ |
| | T3.2 `docker compose up -d worker` | ✅ |
| | T3.3 Vérifier RestartCount = 0 et log `worker_started` | ✅ |

## Fichiers

- `docker/Dockerfile.worker` : +3 lignes.
- `workers/requirements.txt` : +2/-1 lignes.

## Validation

- Image construite : `Image mnemolite-worker Built`.
- Conteneur : `Up`, `RestartCount=0` (contre 1 506), log `worker_started` sur `conversations:autosave`.

## Régressions

- Test d'intégration : l'image worker se construit et démarre (à ajouter en CI).
- Le test worker unitaire passe avec `api/` présent (comme dans le conteneur fixé).
