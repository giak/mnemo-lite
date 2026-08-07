# ⚡ EPIC-68 : Optimisation du boot de l'API (8-13 min → cible < 2 min)

> **Status:** BACKLOG (créé le 2026-08-07, issu de la revue des EPIC 55-61)
> **Priority:** P2 (confort de dev et de déploiement, aucun impact fonctionnel)
> **Date:** 2026-08-07
> **Effort:** 1-2 h

## Problem Statement

Le démarrage de `mnemo-api` prend **~8-13 minutes** (diagnostic EPIC-55) : préchargement des modèles d'embedding au boot (`EMBEDDING_MODE=real` → chargement CPU de bge-m3 torch + jina code ; premier boot avec téléchargement Hugging Face). L'API finit par être healthy, mais tout restart/redéploiement est très lent.

## Pistes documentées (EPIC-55, à évaluer)

| Piste | Description |
|---|---|
| A. `USE_ONNX=true` | Modèle bge-m3 ONNX int8 local monté (`./shared_volumes/models/bge-m3-onnx-int8`) : zéro téléchargement, chargement plus léger |
| B. Lazy-loading du préchargement | Charger les modèles au premier appel (déjà partiellement le cas à la demande) au lieu du boot, ou en arrière-plan non bloquant |
| C. Épingler la révision HF | Écarté en EPIC-56 (H2 fausse : le modèle réel sort du 768 conforme) : non retenu, documenté pour mémoire |

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Mesure | T1.1 Chronométrer le boot actuel (baseline) et identifier le goulot (bge-m3 vs jina, téléchargement vs chargement) | ⬜ |
| S2. Optimisation | T2.1 Appliquer la piste retenue (A et/ou B) sans changer la qualité des embeddings | ⬜ |
| S3. Validation | T3.1 Boot < 2 min ; health 200 ; circuit breakers embedding text/code à success_count > 0 | ⬜ |
| | T3.2 Recherches (texte + code) : résultats identiques à la baseline | ⬜ |

## Fichiers

- `api/main.py` (lifespan, préchargement)
- `api/services/dual_embedding_service.py` (chargement)
- `docker-compose.yml` (env USE_ONNX si retenu)

## Validation

- `time` de boot (restart mnemo-api) : cible < 2 min.
- `GET /health` 200 ; aucune erreur de préchargement dans les logs ; recherches fonctionnelles.

## Régressions

- Risque principal : qualité/récupération des embeddings différente entre torch et ONNX (à valider par échantillon de recherche).
- Le lazy-loading peut introduire un premier appel lent (cold start) : à compenser ou à accepter (le boot reste plus rapide).
