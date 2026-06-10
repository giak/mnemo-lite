# EPIC-50 — Plan : Generalisation AppSettings globale

**Status:** DRAFT
**Date:** 2026-06-10
**Points:** 21
**Stories:** 6

## Contexte

EPIC-49 a prouve le pattern : SSOT Pydantic → validation → injection. Il couvre 17 champs embedding. Reste : 50+ variables eparpillees dans 30+ fichiers.

## Current vs Target

| Metrique | Current | Target |
|----------|---------|--------|
| Champs dans SSOT | 17 (embedding) | 38 (tout) |
| Fichiers avec os.getenv | 30+ | 2 (timeouts, circuit_breakers) |
| Sources de verite pour DATABASE_URL | 3 (.env, docker-compose, os.getenv) | 1 (AppSettings) |
| Validation config | Embedding seulement | Toute l'app |

## Stories detaillees

### Story 50.1 : Etendre AppSettings (5 pts)

Ajouter 26 champs repartis en 9 groupes :

| Groupe | Champs |
|--------|--------|
| DB | `DATABASE_URL`, `TEST_DATABASE_URL`, `MCP_DATABASE_URL`, `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` |
| App | `ENVIRONMENT`, `DEBUG`, `LOG_LEVEL`, `SECRET_KEY`, `API_PORT` |
| Auth | `MNEMO_AUTH_ENABLED`, `MNEMO_API_KEYS`, `MNEMO_RATE_LIMIT_ENABLED`, `MNEMO_RATE_LIMIT_MAX`, `MNEMO_RATE_LIMIT_WINDOW` |
| Auto-Import | `CLAUDE_PROJECTS_DIR`, `CODEBUFF_DIR`, `OPENCODE_DIR`, `ACTIVE_PROJECT`, `ENABLE_AUTO_IMPORT`, `CONVERSATION_WATCHER_ENABLED`, `POLL_INTERVAL`, `IMPORT_HISTORICAL`, `TYPESCRIPT_LSP_ENABLED`, `WATCHER_LOG_FORMAT` |
| MCP | `MCP_PRIVACY_ENABLED`, `MCP_TRANSPORT`, `MCP_HTTP_HOST`, `MCP_HTTP_PORT`, `MCP_AUTH_MODE` |
| Features | `ENTITY_EXTRACTION_ENABLED`, `ENTITY_EXTRACTION_MEMORY_TYPES`, `ENTITY_EXTRACTION_SYSTEM_TAGS`, `QUERY_UNDERSTANDING_ENABLED`, `QUERY_UNDERSTANDING_FALLBACK`, `USE_ONNX` |
| Upload | `UPLOAD_BATCH_SIZE`, `UPLOAD_INDEXING_TIMEOUT` |
| Obs. | `O2_URL`, `O2_USER`, `O2_PASSWORD`, `OTLP_ENDPOINT`, `OTLP_METRICS_ENDPOINT` |
| Frontend | `VITE_API_URL` |

Chaque champ herite du defaut actuel (celui dans `os.getenv("VAR", "default")`).

### Story 50.2 : Migrer api/main.py (3 pts)

Remplacer 11 `os.getenv` par `get_settings()` :
- Lignes 33-38 : `DATABASE_URL`, `ENVIRONMENT`, `DEBUG`, `TEST_DATABASE_URL`
- Lignes 160, 282 : `REDIS_URL`
- Ligne 240 : `TYPESCRIPT_LSP_ENABLED`
- Lignes 452-455 : `MNEMO_AUTH_ENABLED`, `MNEMO_RATE_LIMIT_*`

### Story 50.3 : Migrer routes + middleware (3 pts)

- `ui_upload_handler.py` : `UPLOAD_BATCH_SIZE`, `UPLOAD_INDEXING_TIMEOUT`
- `ui_routes.py` : `REDIS_URL`
- `conversations_routes.py` : `REDIS_HOST`, `REDIS_PORT` (x2)
- `auth.py` : `MNEMO_API_KEYS`

### Story 50.4 : Migrer services + MCP (4 pts)

- `optimization_helpers.py` : `ENVIRONMENT`
- `batch_indexing_consumer.py` : `DATABASE_URL`
- `privacy_service.py` : `MCP_PRIVACY_ENABLED`
- `entity_extraction_service.py` : `ENTITY_EXTRACTION_ENABLED`
- `mnemo_mcp/server.py` : `OTLP_*`, `O2_*`, `ENVIRONMENT`
- `mnemo_mcp/config.py` : `DATABASE_URL`, `ENVIRONMENT`

### Story 50.5 : Migrer scripts/ (4 pts)

20+ scripts utilisent `os.getenv`. Approche :
1. Ajouter `sys.path` setup pour permettre `from api.core import get_settings`
2. Remplacer `os.getenv` par `get_settings()`
3. Priorite aux scripts critiques (migration DB, reindex, watcher)

### Story 50.6 : Nettoyage (2 pts)

- `.env` : supprimer les variables deja dans les defaults AppSettings
- `.env.example` : documenter chaque variable avec son defaut
- `docker-compose.yml` : supprimer les defaults redondants avec AppSettings
- Verifier qu'aucun `os.getenv` hors timeouts/circuit_breakers ne subsiste

## Risques

| Risque | Probabilite | Mitigation |
|--------|------------|------------|
| Changement de defaut REDIS_URL (docker vs localhost) | Moyenne | Utiliser le defaut Docker (redis:6379) ; local dev utilise .env |
| Scripts hors PYTHONPATH ne trouvent pas api.core | Moyenne | Ajouter sys.path.insert(0, ...) dans chaque script |
| MCP server importe api.core → dependance lourde | Faible | api.core n'importe que pydantic + KNOWN_MODELS (leger) |
| Regression sur les tests (cache_clear) | Faible | Conftest.py existant gere deja le cache |

## Ordre d'execution

```
50.1 (AppSettings) → 50.2 (main.py) → 50.3 (routes) → 50.4 (services+MCP) → 50.5 (scripts) → 50.6 (cleanup)
```

Les stories 50.2-50.5 sont partiellement parallelisables une fois 50.1 terminee.
