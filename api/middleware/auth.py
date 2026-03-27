"""
API Key Authentication Middleware.

Simple API key authentication for MnemoLite HTTP API.
Validates X-API-Key header against configured keys.

Usage:
    app.add_middleware(APIKeyMiddleware)

Configuration:
    MNEMO_API_KEYS=key1:owner1,key2:owner2
    MNEMO_AUTH_ENABLED=true (default: false for backward compat)
"""

import logging
import os
from typing import Optional, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API Key authentication middleware.

    Exempt paths (no auth required):
        /, /health, /readiness, /metrics, /docs, /openapi.json, /redoc
    """

    EXEMPT_PATHS = {
        "/",
        "/health",
        "/readiness",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    def __init__(self, app, api_keys: Optional[Dict[str, str]] = None, enabled: bool = True):
        """
        Initialize middleware.

        Args:
            app: ASGI application
            api_keys: Dict mapping API key → owner name
            enabled: If False, passes all requests through (dev mode)
        """
        super().__init__(app)
        self.enabled = enabled
        self.api_keys = api_keys or self._load_keys_from_env()

        if self.enabled:
            if not self.api_keys:
                logger.warning(
                    "APIKeyMiddleware enabled but no API keys configured. "
                    "Set MNEMO_API_KEYS=key1:owner1,key2:owner2"
                )
            else:
                logger.info(f"APIKeyMiddleware: {len(self.api_keys)} API key(s) configured")

    def _load_keys_from_env(self) -> Dict[str, str]:
        """Load API keys from MNEMO_API_KEYS env var."""
        keys_str = os.getenv("MNEMO_API_KEYS", "")
        if not keys_str:
            return {}

        keys = {}
        for entry in keys_str.split(","):
            entry = entry.strip()
            if ":" in entry:
                key, owner = entry.split(":", 1)
                keys[key.strip()] = owner.strip()
            elif entry:
                keys[entry] = "unknown"
        return keys

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from auth."""
        if path in self.EXEMPT_PATHS:
            return True
        # Static files and docs
        if path.startswith("/static/"):
            return True
        return False

    def _verify_key(self, api_key: str) -> Optional[str]:
        """
        Verify API key and return owner name.

        Returns:
            Owner name if valid, None if invalid
        """
        if not self.api_keys:
            # No keys configured = all keys valid (dev mode)
            return "unconfigured"

        return self.api_keys.get(api_key)

    async def dispatch(self, request: Request, call_next):
        """Process request with API key validation."""
        # Skip auth if disabled
        if not self.enabled:
            return await call_next(request)

        # Skip exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Extract API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Missing API key",
                    "detail": "Provide X-API-Key header"
                }
            )

        # Verify key
        owner = self._verify_key(api_key)
        if owner is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid API key",
                    "detail": "The provided API key is not valid"
                }
            )

        # Add owner info to request state
        request.state.api_key_owner = owner

        return await call_next(request)
