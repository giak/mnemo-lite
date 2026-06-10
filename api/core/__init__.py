"""Configuration centralisée de MnemoLite.

Modules:
- embedding_models: Registre statique des modeles (KNOWN_MODELS, ModelSpec)
- settings: Configuration validee Pydantic (AppSettings, get_settings)

Usage:
    from api.core import get_settings, KNOWN_MODELS
    settings = get_settings()
    print(settings.EMBEDDING_DIMENSION)  # 1024 (auto-deduit de BGE-M3)
"""

from api.core.embedding_models import KNOWN_MODELS, ModelSpec, get_model_spec
from api.core.settings import VALID_EMBEDDING_MODES, AppSettings, get_settings

__all__ = [
    "KNOWN_MODELS",
    "ModelSpec",
    "get_model_spec",
    "AppSettings",
    "VALID_EMBEDDING_MODES",
    "get_settings",
]
