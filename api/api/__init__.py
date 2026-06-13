"""Re-export for api.* imports in Docker.
Volume mount ./api:/app puts api/ contents at /app/.
Symlinks create the api.* namespace.
"""
from core.settings import get_settings, AppSettings, VALID_EMBEDDING_MODES
from core.embedding_models import KNOWN_MODELS, ModelSpec, get_model_spec
