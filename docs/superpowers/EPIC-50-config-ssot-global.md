# EPIC-50 : Generalisation AppSettings a toute la configuration MnemoLite

**Status:** DRAFT
**Points estimes:** 21
**Assignee:** TBD
**Pre-requis:** EPIC-49 (embedding SSOT) termine

## Problem Statement

EPIC-49 a cree une Single Source of Truth (SSOT) pour la configuration d'embedding (17 champs dans `api/core/settings.py`). Mais MnemoLite utilise encore **50+ variables d'environnement** eparpillees dans :

- **`.env`** : 7 variables hors SSOT (`TYPESCRIPT_LSP_ENABLED`, `CLAUDE_PROJECTS_DIR`, etc.)
- **`docker-compose.yml`** : 25+ variables hors SSOT (`POSTGRES_*`, `MCP_*`, `USE_ONNX`, etc.)
- **`api/main.py`** : 11 `os.getenv` non-embedding (`DATABASE_URL`, `DEBUG`, `MNEMO_AUTH_ENABLED`, etc.)
- **`api/routes/`** : 6 `os.getenv` (`REDIS_URL`, `REDIS_HOST`, `UPLOAD_BATCH_SIZE`, etc.)
- **`api/middleware/`** : 1 `os.getenv` (`MNEMO_API_KEYS`)
- **`api/services/`** : 4 `os.getenv` (`MCP_PRIVACY_ENABLED`, `ENTITY_EXTRACTION_ENABLED`, etc.)
- **`api/mnemo_mcp/`** : 7 `os.getenv` (`O2_USER`, `OTLP_ENDPOINT`, etc.)
- **`scripts/`** : 20+ `os.getenv` (`DATABASE_URL`, `O2_*`, etc.)

Consequences :
- Changer une variable necessite de modifier 3-5 fichiers (`.env`, `docker-compose`, le code)
- Aucune validation de coherence (ex: `REDIS_HOST` sans `REDIS_PORT`)
- `DATABASE_URL` est defini en dur dans `docker-compose.yml` mais lu via `os.getenv` dans 15+ fichiers
- Les scripts ont leurs propres defaults, differents de l'API
- Impossible de savoir quelles variables sont obligatoires vs optionnelles

## Target State

Un `AppSettings` etendu (62 champs au total) couvrant TOUTE la configuration de l'application. Une simple modification du `.env` propage automatiquement la valeur partout. Les scripts importent `get_settings()` comme l'API.

### Domaines de configuration

| Domaine | Champs | Nb |
|---------|--------|----|
| Embedding (existant) | EMBEDDING_MODEL, DIMENSION, BACKEND, MODE, CODE_*, DEVICE, CACHE_SIZE, AUTO_GENERATE, FAIL_STRATEGY, SOURCE_FIELDS, L1_CACHE_SIZE_MB, GLINER_* | 17 (dont 3 migrent vers DB/App) |
| Base de donnees | DATABASE_URL, TEST_DATABASE_URL, MCP_DATABASE_URL, REDIS_URL, REDIS_HOST, REDIS_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT | 10 |
| Application | ENVIRONMENT, DEBUG, LOG_LEVEL, SECRET_KEY, API_PORT | 5 |
| Auth & Rate Limit | MNEMO_AUTH_ENABLED, MNEMO_API_KEYS, MNEMO_RATE_LIMIT_ENABLED, MNEMO_RATE_LIMIT_MAX, MNEMO_RATE_LIMIT_WINDOW | 5 |
| Auto-Import | CLAUDE_PROJECTS_DIR, CODEBUFF_DIR (alias CODEBUFF_PROJECTS_DIR), OPENCODE_DIR, ACTIVE_PROJECT, ENABLE_AUTO_IMPORT, CONVERSATION_WATCHER_ENABLED, POLL_INTERVAL, IMPORT_HISTORICAL, TYPESCRIPT_LSP_ENABLED, WATCHER_LOG_FORMAT | 10 |
| MCP Server | MCP_PRIVACY_ENABLED, MCP_TRANSPORT, MCP_HTTP_HOST, MCP_HTTP_PORT, MCP_AUTH_MODE | 5 |
| Feature Flags | ENTITY_EXTRACTION_ENABLED, ENTITY_EXTRACTION_MEMORY_TYPES, ENTITY_EXTRACTION_SYSTEM_TAGS, QUERY_UNDERSTANDING_ENABLED, QUERY_UNDERSTANDING_FALLBACK, USE_ONNX | 6 |
| Upload | UPLOAD_BATCH_SIZE, UPLOAD_INDEXING_TIMEOUT | 2 |
| Observabilite | O2_URL, O2_USER, O2_PASSWORD, OTLP_ENDPOINT, OTLP_METRICS_ENDPOINT | 5 |
| Frontend | VITE_API_URL | 1 |

## Stories

- **Story 50.1 :** Etendre AppSettings avec les 45 nouveaux champs (5 pts)
- **Story 50.2 :** Migrer `api/main.py` (11 os.getenv) (3 pts)
- **Story 50.3 :** Migrer `api/routes/` + `api/middleware/` (7 os.getenv) (3 pts)
- **Story 50.4 :** Migrer `api/services/` + `api/mnemo_mcp/` (11 os.getenv) (4 pts)
- **Story 50.5 :** Migrer `scripts/` (20+ os.getenv) (4 pts)
- **Story 50.6 :** Nettoyage `.env`, `.env.example`, `docker-compose.yml` (2 pts)

## Success Criteria

1. Modifier une variable dans `.env` la propage a TOUS les consommateurs (API, MCP, scripts)
2. `AppSettings` contient TOUTES les variables de configuration (38 champs)
3. Zero `os.getenv`/`os.environ` hors modules de config legitimes (`timeouts.py`, `circuit_breakers.py`)
4. Le `.env.example` documente chaque variable avec son defaut
5. Les scripts importent `get_settings()` et beneficient de la validation
