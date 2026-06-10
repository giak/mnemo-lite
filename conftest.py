"""Fixtures globales pour les tests MnemoLite."""

import pytest

from api.core.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Reset le cache de get_settings() avant chaque test.

    Sans cette fixture, les tests qui modifient os.environ apres le premier
    appel a get_settings() utiliseraient la config en cache (obsolete).
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
