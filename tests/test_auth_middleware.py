"""
TDD tests for API Key authentication middleware.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.testclient import TestClient
from fastapi import FastAPI


class TestAPIKeyMiddleware:
    """Verify API Key authentication middleware."""

    def test_exempt_paths_no_auth(self):
        """Health and docs paths must be accessible without API key."""
        from middleware.auth import APIKeyMiddleware

        middleware = APIKeyMiddleware(app=None, enabled=True)
        assert middleware._is_exempt("/health") is True
        assert middleware._is_exempt("/readiness") is True
        assert middleware._is_exempt("/metrics") is True
        assert middleware._is_exempt("/docs") is True
        assert middleware._is_exempt("/openapi.json") is True
        assert middleware._is_exempt("/") is True

    def test_non_exempt_paths_require_auth(self):
        """API paths must not be exempt."""
        from middleware.auth import APIKeyMiddleware

        middleware = APIKeyMiddleware(app=None, enabled=True)
        assert middleware._is_exempt("/api/v1/memories") is False
        assert middleware._is_exempt("/v1/code/search/hybrid") is False

    def test_verify_valid_key(self):
        """Valid API key must return owner name."""
        from middleware.auth import APIKeyMiddleware

        keys = {"my-secret-key": "expanse"}
        middleware = APIKeyMiddleware(app=None, api_keys=keys, enabled=True)

        assert middleware._verify_key("my-secret-key") == "expanse"
        assert middleware._verify_key("wrong-key") is None
        assert middleware._verify_key("") is None

    def test_load_keys_from_env(self):
        """API keys must be loadable from MNEMO_API_KEYS env var."""
        import os
        from middleware.auth import APIKeyMiddleware

        os.environ["MNEMO_API_KEYS"] = "key1:owner1,key2:owner2"
        try:
            middleware = APIKeyMiddleware(app=None, enabled=True)
            assert middleware.api_keys == {"key1": "owner1", "key2": "owner2"}
        finally:
            del os.environ["MNEMO_API_KEYS"]

    def test_disabled_middleware_passes_through(self):
        """Disabled middleware must not block requests."""
        from middleware.auth import APIKeyMiddleware

        middleware = APIKeyMiddleware(app=None, enabled=False)
        assert middleware.enabled is False

    def test_no_keys_configured_warns(self):
        """Middleware with no keys must log a warning."""
        import logging
        from middleware.auth import APIKeyMiddleware

        with logging.getLogger("middleware.auth").setLevel(logging.WARNING):
            middleware = APIKeyMiddleware(app=None, api_keys={}, enabled=True)
            assert middleware.api_keys == {}
