# ⚡ EPIC-68 : Optimisation du boot de l'API (8-13 min → cible < 2 min)

> **Status:** DONE (implémenté le 2026-08-07, piste B ; validation boot au prochain restart)
> **Priority:** P2 (confort de dev et de déploiement, aucun impact fonctionnel)
> **Date:** 2026-08-07
> **Effort:** 1-2 h

## Problem Statement

Le démarrage de `mnemo-api` prend **~8-13 minutes** (diagnostic EPIC-55) : préchargement des modèles d'embedding au boot (`EMBEDDING_MODE=real` → chargement CPU de bge-m3 torch + jina code ; premier boot avec téléchargement Hugging Face). L'API finit par être healthy, mais tout restart/redéploiement est très lent.

## Cause racine (diagnostic réel 2026-08-07)

`api/main.py` lifespan, bloc 2 : `await dual_service.preload_models()` (ligne ~135) charge **synchronement** les 2 modèles torch (bge-m3 + jina-code, ~5-10 min CPU chacun au premier chargement) : le boot entier attend. Le reste du startup (DB, Redis, LSP, monitoring) est rapide. `USE_ONNX` existe dans settings (`USE_ONNX: bool = False`) mais **n'est implémenté nulle part** dans `DualEmbeddingService`/`dependencies` : la piste A nécessiterait du code neuf (adaptateur ONNX) + risque de qualité d'embedding.

## Pistes documentées (EPIC-55, à évaluer)

| Piste | Description |
|---|---|
| A. `USE_ONNX=true` | Modèle bge-m3 ONNX int8 local monté (`./shared_volumes/models/bge-m3-onnx-int8`) : zéro téléchargement, chargement plus léger |
| B. Lazy-loading du préchargement | Charger les modèles au premier appel (déjà partiellement le cas à la demande) au lieu du boot, ou en arrière-plan non bloquant |
| C. Épingler la révision HF | Écarté en EPIC-56 (H2 fausse : le modèle réel sort du 768 conforme) : non retenu, documenté pour mémoire |

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Mesure | T1.1 Baseline : boot ~8-13 min (EPIC-55), goulot = `await dual_service.preload_models()` (chargement torch synchrone des 2 modèles) ; `USE_ONNX` non implémenté dans le service → piste A écartée (code neuf + risque qualité) | ✅ |
| S2. Optimisation | T2.1 Piste B : helper `_preload_embedding_models` (try/except log) + `asyncio.create_task` NON bloquant en dev/test ; **fail-fast conservé en production** (await synchrone, décision documentée) ; tâche stockée dans `app.state.embedding_preload_task` et annulée au shutdown (pattern `alert_monitoring_task`, review) | ✅ |
| S3. Validation | T3.1 Code : syntaxe OK, `test_api_flow.py` 18/18 (lifespan mock inchangé), impact tests zéro (fixtures real définissent `app.state.embedding_service` → skip) ; **boot < 2 min à mesurer au prochain restart** (différé : le backfill events EPIC-62 tourne, un recreate le tuerait) | ✅ (partiel) |
| | T3.2 Recherches (texte + code) : mêmes modèles torch, zéro changement de qualité ; validation empirique au prochain restart | ⬜ (différé) |

## Fichiers

- `api/main.py` (lifespan) : helper `_preload_embedding_models`, preload async dev/test, await prod, cleanup tâche au shutdown. `dual_embedding_service.py` et `docker-compose.yml` inchangés (piste A non retenue).

## Preuves de validation (2026-08-07)

| Vérification | Résultat |
|---|---|
| Syntaxe | `py_compile main.py` OK |
| `test_api_flow.py` (lifespan mock) | **18/18 passed** |
| Impact tests real embeddings | Zéro : fixture `test_client_with_real_embeddings` définit `app.state.embedding_service` → le lifespan saute le bloc real ; `test_full_pipeline` n'utilise pas le lifespan |
| Comportement prod | Inchangé : `ENVIRONMENT=production` → await synchrone (fail-fast) ; dev/test → boot immédiat + préchargement en fond |
| Boot réel (< 2 min) | **À mesurer au prochain restart du conteneur** (après fin du backfill events EPIC-62, ~1500 restants) |

## Validation

- `time` de boot (restart mnemo-api) : cible < 2 min.
- `GET /health` 200 ; aucune erreur de préchargement dans les logs ; recherches fonctionnelles.

## Régressions

- Aucun risque de qualité : mêmes modèles torch (la piste ONNX n'est pas retenue).
- Dev/test : le premier appel d'embedding après un boot peut attendre la fin du préchargement en fond (cold start ~5-10 min si un write arrive immédiatement) : compensé par le préchargement en tâche de fond, acceptable (boot rapide en échange).
- Production : comportement inchangé (fail-fast conservé).
- Action manuelle : au prochain `docker compose up -d --force-recreate api` (une fois le backfill events fini), mesurer le boot et vérifier health 200 + circuit breakers embedding à success_count > 0.
