"""Configuration centralisee de l'application.

Single Source of Truth pour toutes les variables d'environnement.
Lit .env, valide la coherence, auto-deduit les dimensions.
Crash au demarrage si config incoherente.

Usage:
    from api.core import get_settings
    settings = get_settings()
    print(settings.EMBEDDING_DIMENSION)  # Auto-deduit du modele
"""

from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.core.embedding_models import KNOWN_MODELS, ModelSpec


VALID_EMBEDDING_MODES = {"real", "stub", "mock"}

class AppSettings(BaseSettings):
    """Configuration centralisee de MnemoLite.
    
    Lit .env, valide la coherence entre les modeles et leurs dimensions.
    Crash immediatement si la config est contradictoire.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # === Timeouts (secondes, tous optionnels) ===
    # Tous les timeouts sont lus depuis api/config/timeouts.py
    TIMEOUT_TREE_SITTER: float = 5.0
    TIMEOUT_EMBEDDING_SINGLE: float = 30.0
    TIMEOUT_EMBEDDING_BATCH: float = 60.0
    TIMEOUT_GRAPH_CONSTRUCTION: float = 300.0
    TIMEOUT_GRAPH_TRAVERSAL: float = 5.0
    TIMEOUT_VECTOR_SEARCH: float = 5.0
    TIMEOUT_LEXICAL_SEARCH: float = 3.0
    TIMEOUT_HYBRID_SEARCH: float = 10.0
    TIMEOUT_CACHE_GET: float = 1.0
    TIMEOUT_CACHE_PUT: float = 2.0
    TIMEOUT_DATABASE_QUERY: float = 10.0
    TIMEOUT_DATABASE_TRANSACTION: float = 30.0
    TIMEOUT_INDEX_FILE: float = 60.0

    # === Circuit Breakers (seuils, tous optionnels) ===
    REDIS_CIRCUIT_FAILURE_THRESHOLD: int = 5
    REDIS_CIRCUIT_RECOVERY_TIMEOUT: int = 30
    REDIS_CIRCUIT_HALF_OPEN_CALLS: int = 1
    EMBEDDING_CIRCUIT_FAILURE_THRESHOLD: int = 3
    EMBEDDING_CIRCUIT_RECOVERY_TIMEOUT: int = 60
    EMBEDDING_CIRCUIT_HALF_OPEN_CALLS: int = 1
    DATABASE_CIRCUIT_FAILURE_THRESHOLD: int = 3
    DATABASE_CIRCUIT_RECOVERY_TIMEOUT: int = 10
    DATABASE_CIRCUIT_HALF_OPEN_CALLS: int = 1

    # === Modele d'embedding texte (principal) ===
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: Optional[int] = None  # Auto-deduit si None
    EMBEDDING_BACKEND: Optional[str] = None  # Auto-deduit du registre; fallback pytorch
    EMBEDDING_MODE: str = "real"

    # === Modele d'embedding code (DualEmbeddingService) ===
    CODE_EMBEDDING_MODEL: str = "jinaai/jina-embeddings-v2-base-code"
    CODE_EMBEDDING_DIMENSION: Optional[int] = None

    # === Device et cache ===
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_CACHE_SIZE: int = 1000
    L1_CACHE_SIZE_MB: int = 100

    # === Comportement embedding (EventService) ===
    EMBEDDING_AUTO_GENERATE: bool = True
    EMBEDDING_FAIL_STRATEGY: str = "soft"
    EMBEDDING_SOURCE_FIELDS: str = "text,body,message,content,title"

    # === Chunking et limites d'embedding ===
    EMBEDDING_PREFIX: str = "Represent this passage for retrieval: "
    EMBEDDING_MAX_TOKENS: int = 8192  # Limite native BGE-M3
    EMBEDDING_CHUNK_SIZE: int = 8000  # Taille des chunks (tokens) pour textes > MAX_TOKENS
    EMBEDDING_CHUNK_OVERLAP: int = 256  # Overlap entre chunks consecutifs
    EMBEDDING_MAX_CONTENT_LENGTH: int = 100_000  # Hard RAM safety limit (pas une limite semantique)

    # === Entity extraction (GLiNER) ===
    GLINER_MODEL_PATH: str = "/app/models/gliner_multi-v2.1"
    GLINER_MODEL: str = "piEsposito/gliner-multi-v2.1"

    # === Base de donnees ===
    DATABASE_URL: str = ""  # Read from .env; validated at startup in main.py
    REDIS_URL: str = "redis://redis:6379/0"

    # === Environnement ===
    ENVIRONMENT: str = "development"

    # === Base de donnees (etendu) ===
    TEST_DATABASE_URL: str = ""
    MCP_DATABASE_URL: str = ""
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    POSTGRES_USER: str = "mnemo"
    POSTGRES_PASSWORD: str = "mnemopass"
    POSTGRES_DB: str = "mnemolite"
    POSTGRES_PORT: int = 5432

    # === Application ===
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = ""
    API_PORT: int = 8001

    # === Auth & Rate Limiting ===
    MNEMO_AUTH_ENABLED: bool = False
    MNEMO_API_KEYS: str = ""
    MNEMO_RATE_LIMIT_ENABLED: bool = True
    MNEMO_RATE_LIMIT_MAX: int = 100
    MNEMO_RATE_LIMIT_WINDOW: int = 60

    # === Auto-Import / Watcher ===
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

    # === MCP Server ===
    MCP_PRIVACY_ENABLED: bool = True
    MCP_TRANSPORT: str = "http"
    MCP_HTTP_HOST: str = "0.0.0.0"
    MCP_HTTP_PORT: int = 8002
    MCP_AUTH_MODE: str = "none"

    # === Feature Flags ===
    ENTITY_EXTRACTION_ENABLED: bool = True
    ENTITY_EXTRACTION_MEMORY_TYPES: str = "decision,reference,note,investigation"
    ENTITY_EXTRACTION_SYSTEM_TAGS: str = "sys:core,sys:anchor,sys:pattern"
    QUERY_UNDERSTANDING_ENABLED: bool = False
    QUERY_UNDERSTANDING_FALLBACK: bool = True
    USE_ONNX: bool = False

    # === Upload ===
    UPLOAD_BATCH_SIZE: int = 10
    UPLOAD_INDEXING_TIMEOUT: int = 300

    # === Observabilite (OpenObserve) ===
    O2_URL: str = "http://openobserve:5080"
    O2_USER: str = ""
    O2_PASSWORD: str = ""
    OTLP_ENDPOINT: str = "http://openobserve:5080/api/default"
    OTLP_METRICS_ENDPOINT: str = "http://openobserve:5080/api/default"

    # === Frontend ===
    VITE_API_URL: str = "http://localhost:8001"

    @model_validator(mode="after")
    def validate_embedding_config(self):
        """Valide et auto-deduit la configuration d'embedding."""

        # 0. Validation EMBEDDING_MODE (case-insensitive, backward compat)
        self.EMBEDDING_MODE = self.EMBEDDING_MODE.lower()
        if self.EMBEDDING_MODE not in VALID_EMBEDDING_MODES:
            raise ValueError(
                f"INVALID EMBEDDING_MODE: '{self.EMBEDDING_MODE}'. "
                f"Must be one of: {', '.join(sorted(VALID_EMBEDDING_MODES))}"
            )

        # 1. Validation modele texte principal
        text_spec = KNOWN_MODELS.get(self.EMBEDDING_MODEL)
        if text_spec:
            if self.EMBEDDING_DIMENSION is not None:
                if self.EMBEDDING_DIMENSION != text_spec.dimension:
                    raise ValueError(
                        f"CONFIG CONFLICT: {self.EMBEDDING_MODEL} expects "
                        f"{text_spec.dimension}D, but EMBEDDING_DIMENSION is "
                        f"set to {self.EMBEDDING_DIMENSION} in .env/docker-compose. "
                        f"Fix: remove EMBEDDING_DIMENSION (auto-inferred) or "
                        f"change EMBEDDING_MODEL."
                    )
            else:
                self.EMBEDDING_DIMENSION = text_spec.dimension

            if self.EMBEDDING_BACKEND is not None:
                if self.EMBEDDING_BACKEND != text_spec.backend:
                    raise ValueError(
                        f"CONFIG CONFLICT: {self.EMBEDDING_MODEL} uses "
                        f"backend '{text_spec.backend}', but "
                        f"EMBEDDING_BACKEND is '{self.EMBEDDING_BACKEND}'"
                    )
            else:
                self.EMBEDDING_BACKEND = text_spec.backend
        else:
            if self.EMBEDDING_DIMENSION is None:
                raise ValueError(
                    f"UNKNOWN MODEL: '{self.EMBEDDING_MODEL}' is not in "
                    f"KNOWN_MODELS. You MUST set EMBEDDING_DIMENSION in .env. "
                    f"Known models: {', '.join(sorted(KNOWN_MODELS.keys()))}"
                )

        # Fallback: si le modele est inconnu, EMBEDDING_BACKEND peut etre None
        if self.EMBEDDING_BACKEND is None:
            self.EMBEDDING_BACKEND = "pytorch"

        # 2. Validation modele code
        code_spec = KNOWN_MODELS.get(self.CODE_EMBEDDING_MODEL)
        if code_spec:
            if self.CODE_EMBEDDING_DIMENSION is None:
                self.CODE_EMBEDDING_DIMENSION = code_spec.dimension
            elif self.CODE_EMBEDDING_DIMENSION != code_spec.dimension:
                raise ValueError(
                    f"CONFIG CONFLICT: {self.CODE_EMBEDDING_MODEL} expects "
                    f"{code_spec.dimension}D, but CODE_EMBEDDING_DIMENSION is "
                    f"{self.CODE_EMBEDDING_DIMENSION}"
                )
        elif self.CODE_EMBEDDING_DIMENSION is None:
            raise ValueError(
                f"UNKNOWN CODE MODEL: '{self.CODE_EMBEDDING_MODEL}'. "
                f"Set CODE_EMBEDDING_DIMENSION in .env. "
                f"Known models: {', '.join(sorted(KNOWN_MODELS.keys()))}"
            )

        return self

    @property
    def text_spec(self) -> Optional[ModelSpec]:
        """Retourne la spec complete du modele texte."""
        return KNOWN_MODELS.get(self.EMBEDDING_MODEL)

    @property
    def code_spec(self) -> Optional[ModelSpec]:
        """Retourne la spec complete du modele code."""
        return KNOWN_MODELS.get(self.CODE_EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Singleton de configuration.

    Calcule une seule fois au premier appel (lru_cache).
    Crash immediatement si la config est incoherente (fail fast).

    Usage:
        from api.core import get_settings
        settings = get_settings()
        dim = settings.EMBEDDING_DIMENSION  # 1024 (auto-deduit)

    Pour les tests (reset le cache si vous mockez os.environ apres import):
        from api.core.settings import get_settings
        get_settings.cache_clear()
    """
    return AppSettings()
