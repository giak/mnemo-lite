# SPEC : Generalisation AppSettings — Design

**Date:** 2026-06-10
**Feature:** Configuration globale SSOT
**Priority:** P1
**Inspiration:** EPIC-49 (pattern prouve), pydantic-settings, 12-factor app

## 1. Overview

### 1.1 Probleme

50+ variables d'environnement lues via `os.getenv` dans 30+ fichiers. Aucune validation centralisee.

### 1.2 Solution

Etendre `AppSettings` a 62 champs couvrant 9 domaines. Tout le code (API, MCP, scripts) passe par `get_settings()`.

### 1.3 Benefices

| Metrique | Current | Target |
|----------|---------|--------|
| Fichiers a modifier pour changer DATABASE_URL | 15+ | 1 (.env) |
| Validation config | Embedding seulement | Toute l'app |
| Variables documentees | 17 | 62 |

## 2. AppSettings etendu

### 2.1 Nouveaux champs par domaine

```python
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # === Embedding (existant — 17 champs) ===
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: Optional[int] = None
    EMBEDDING_BACKEND: Optional[str] = None
    EMBEDDING_MODE: str = "real"
    CODE_EMBEDDING_MODEL: str = "jinaai/jina-embeddings-v2-base-code"
    CODE_EMBEDDING_DIMENSION: Optional[int] = None
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_CACHE_SIZE: int = 1000
    L1_CACHE_SIZE_MB: int = 100
    EMBEDDING_AUTO_GENERATE: bool = True
    EMBEDDING_FAIL_STRATEGY: str = "soft"
    EMBEDDING_SOURCE_FIELDS: str = "text,body,message,content,title"
    GLINER_MODEL_PATH: str = "/app/models/gliner_multi-v2.1"
    GLINER_MODEL: str = "piEsposito/gliner-multi-v2.1"

    # === Base de donnees (+10) ===
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = ""
    MCP_DATABASE_URL: str = ""
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    POSTGRES_USER: str = "mnemo"
    POSTGRES_PASSWORD: str = "mnemopass"
    POSTGRES_DB: str = "mnemolite"
    POSTGRES_PORT: int = 5432

    # === Application (+5) ===
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = ""
    API_PORT: int = 8001

    # === Auth & Rate Limiting (+5) ===
    MNEMO_AUTH_ENABLED: bool = False
    MNEMO_API_KEYS: str = ""
    MNEMO_RATE_LIMIT_ENABLED: bool = True
    MNEMO_RATE_LIMIT_MAX: int = 100
    MNEMO_RATE_LIMIT_WINDOW: int = 60

    # === Auto-Import / Watcher (+9) ===
    TYPESCRIPT_LSP_ENABLED: bool = True
    CLAUDE_PROJECTS_DIR: str = "/home/user/.claude/projects"
    CODEBUFF_DIR: str = "/home/user/.config/manicode/projects"
    OPENCODE_DIR: str = "/home/user/.local/share/opencode"
    ACTIVE_PROJECT: str = "mnemolite"
    ENABLE_AUTO_IMPORT: bool = False
    CONVERSATION_WATCHER_ENABLED: bool = True
    POLL_INTERVAL: int = 30
    IMPORT_HISTORICAL: bool = False
    WATCHER_LOG_FORMAT: str = "text"

    # === MCP Server (+5) ===
    MCP_PRIVACY_ENABLED: bool = True
    MCP_TRANSPORT: str = "http"
    MCP_HTTP_HOST: str = "0.0.0.0"
    MCP_HTTP_PORT: int = 8002
    MCP_AUTH_MODE: str = "none"

    # === Feature Flags (+4) ===
    ENTITY_EXTRACTION_ENABLED: bool = True
    ENTITY_EXTRACTION_MEMORY_TYPES: str = "decision,reference,note,investigation"
    ENTITY_EXTRACTION_SYSTEM_TAGS: str = "sys:core,sys:anchor,sys:pattern"
    QUERY_UNDERSTANDING_ENABLED: bool = False
    QUERY_UNDERSTANDING_FALLBACK: bool = True
    USE_ONNX: bool = False

    # === Upload (+2) ===
    UPLOAD_BATCH_SIZE: int = 10
    UPLOAD_INDEXING_TIMEOUT: int = 300

    # === Observabilite (+5) ===
    O2_URL: str = "http://openobserve:5080"
    O2_USER: str = ""
    O2_PASSWORD: str = ""
    OTLP_ENDPOINT: str = "http://openobserve:5080/api/default"
    OTLP_METRICS_ENDPOINT: str = "http://openobserve:5080/api/default"

    # === Frontend (+1) ===
    VITE_API_URL: str = "http://localhost:8001"
```

## 3. Pattern d'injection

### 3.1 API (FastAPI)

```python
# api/main.py
from api.core import get_settings

settings = get_settings()  # Singleton, valide au premier appel

app = FastAPI(
    debug=settings.DEBUG,
    ...
)
```

### 3.2 MCP Server

```python
# api/mnemo_mcp/server.py
from api.core import get_settings

settings = get_settings()
```

### 3.3 Scripts standalone

```python
# scripts/backfill_memory_relationships.py
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.core import get_settings
settings = get_settings()
```

## 4. Plan de migration par fichier

### Phase 1 : AppSettings (Story 50.1)
- **Creer** les 26 nouveaux champs dans `api/core/settings.py`
- **Verifier** que les defaults matchent les os.getenv actuels

### Phase 2 : Core API (Story 50.2)
- **Modifier** `api/main.py` : 11 os.getenv → get_settings()

### Phase 3 : Routes + Middleware (Story 50.3)
- **Modifier** `api/routes/ui_upload_handler.py` : 2
- **Modifier** `api/routes/ui_routes.py` : 1
- **Modifier** `api/routes/conversations_routes.py` : 4
- **Modifier** `api/middleware/auth.py` : 1

### Phase 4 : Services + MCP (Story 50.4)
- **Modifier** `api/services/optimization_helpers.py` : 1
- **Modifier** `api/services/batch_indexing_consumer.py` : 1
- **Modifier** `api/services/privacy_service.py` : 1
- **Modifier** `api/services/entity_extraction_service.py` : 1
- **Modifier** `api/mnemo_mcp/server.py` : 5
- **Modifier** `api/mnemo_mcp/config.py` : 2

### Phase 5 : Scripts (Story 50.5)
- 20+ scripts a migrer, priorite aux critiques

### Phase 6 : Cleanup (Story 50.6)
- **Modifier** `.env` : supprimer redondances
- **Modifier** `.env.example` : documenter tous les champs
- **Modifier** `docker-compose.yml` : supprimer defaults AppSettings

## 5. Retocompatibilite

- Les `.env` existants continuent de fonctionner (Pydantic lit .env)
- Les variables non definies prennent le defaut AppSettings
- `extra="ignore"` ignore les variables inconnues (pas de crash)
- Les scripts qui n'ont pas acces a `api.core` gardent temporairement `os.getenv`

## 6. Validation

```python
# Test: tous les champs ont un defaut coherent
s = AppSettings()
assert s.DATABASE_URL == ""  # Obligatoire dans .env
assert s.REDIS_URL == "redis://redis:6379/0"
assert s.ENVIRONMENT == "development"
```
