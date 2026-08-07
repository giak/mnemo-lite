# 📡 EPIC-55 : Correction des endpoints OTLP OpenObserve

> **Status:** DONE
> **Priority:** P1 : Observabilité (traces/metrics/logs) réparée
> **Date:** 2026-08-07
> **Effort:** 30 min (diagnostic) + 5 min (fix)

## Problem Statement

Erreurs d'ingestion en continu (401/404 toutes les 5 s) sur traces, métriques et logs : l'observabilité openobserve était morte. L'hypothèse initiale d'un « blocage du lifespan sur l'init OpenTelemetry » s'est révélée fausse (voir Diagnostic).

## Diagnostic (vérité forensique)

1. **Le lifespan ne bloquait pas sur OTel** : le démarrage de `mnemo-api` prend ~8-13 min à cause du préchargement des modèles d'embedding au boot (`EMBEDDING_MODE=real` → téléchargement Hugging Face de bge-m3 torch + jina code, chargement CPU). L'api finit par être healthy et fonctionnelle (`GET /api/v1/memories/search` → HTTP 200).
2. **Bug 1 (corrigé) : endpoints OTLP doublés.** `OTLP_ENDPOINT` contenait déjà `/api/default/v1/traces` alors que `configure_otel` ajoute `/v1/traces` et que le log processor ajoute `/logs/_json`, d'où des chemins invalides (`.../v1/traces/v1/traces`, `.../v1/traces/logs/_json`).
3. **Credentials openobserve valides** : 200 avec auth sur `_bulk` et `/logs/_json` (les 401 venaient du mauvais chemin, pas de l'auth).
4. **Bug 2 (préexistant, documenté, non corrigé)** : le préchargement du modèle CODE échoue à chaque boot : `CODE model dimension mismatch: expected 1024, got 768` (jina-embeddings-v2-base-code, version HF flottante). Non bloquant en dev (fallback à la demande), les recherches de code seraient affectées.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Corriger la base des endpoints | T1.1 `OTLP_ENDPOINT` → `http://openobserve:5080/api/default` (3 services : api, worker, mcp) | ✅ |
| | T1.2 `OTLP_METRICS_ENDPOINT` → idem | ✅ |
| S2. Valider | T2.1 Tester `_bulk`, `/logs/_json`, `/v1/traces` avec auth → 200/400 (chemin + auth OK) | ✅ |
| | T2.2 Recréer api + mcp → **0 erreur d'ingestion** dans les logs | ✅ |

## Fichiers

- `docker-compose.yml` : 6 lignes (2 variables × 3 services).

## Validation

- MCP : 0 occurrence `openobserve_log_ingest_error`/`Failed to export span` après recréation (avant : flux continu).
- API : idem.
- Services sains : api healthy (HTTP 200), mcp healthy, worker stable.

## Suites possibles (hors périmètre, documentées)

- Boot lent : `USE_ONNX=true` (modèle bge-m3 local monté, zéro téléchargement), lazy-loading du préchargement, ou épingler la révision HF du modèle code.
- `OTLP_LOGS_ENDPOINT` : non utilisé par le code (le log processor construit son endpoint depuis `OTLP_ENDPOINT`), laissé tel quel.
