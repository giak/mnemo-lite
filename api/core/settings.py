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

    # === Entity extraction (GLiNER) ===
    GLINER_MODEL: str = "piEsposito/gliner-multi-v2.1"

    # === Base de donnees ===
    DATABASE_URL: str = ""  # Read from .env; validated at startup in main.py
    REDIS_URL: str = "redis://redis:6379/0"

    # === Environnement ===
    ENVIRONMENT: str = "development"

    @model_validator(mode="after")
    def validate_embedding_config(self):
        """Valide et auto-deduit la configuration d'embedding."""

        # 0. Validation EMBEDDING_MODE
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
