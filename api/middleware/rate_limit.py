"""
Rate Limiting Middleware.

Simple in-memory rate limiter for MnemoLite API.
Tracks requests per IP address with configurable limits.

Usage:
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

Configuration:
    MNEMO_RATE_LIMIT=100/60 (100 requests per 60 seconds)
    MNEMO_RATE_LIMIT_ENABLED=true
"""

import logging
import os
import time
from collections import defaultdict
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory rate limiter by client IP.

    Tracks request counts in a sliding window per IP.
    Returns 429 Too Many Requests when limit exceeded.
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

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.enabled = enabled
        # {ip: [(timestamp, ...), ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

        if self.enabled:
            logger.info(
                f"RateLimitMiddleware: {max_requests} req/{window_seconds}s per IP"
            )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_old_entries(self):
        """Remove entries older than window (called periodically)."""
        now = time.time()
        if now - self._last_cleanup < self.window_seconds:
            return

        cutoff = now - self.window_seconds
        expired_ips = []
        for ip, timestamps in self._requests.items():
            self._requests[ip] = [t for t in timestamps if t > cutoff]
            if not self._requests[ip]:
                expired_ips.append(ip)

        for ip in expired_ips:
            del self._requests[ip]

        self._last_cleanup = now

    def _is_rate_limited(self, ip: str) -> tuple[bool, int, int]:
        """
        Check if IP is rate limited.

        Returns: (is_limited, current_count, remaining)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old entries for this IP
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

        current_count = len(self._requests[ip])
        remaining = max(0, self.max_requests - current_count)

        if current_count >= self.max_requests:
            return True, current_count, 0

        # Record this request
        self._requests[ip].append(now)

        # Periodic cleanup
        if time.time() - self._last_cleanup > self.window_seconds:
            self._cleanup_old_entries()

        return False, current_count + 1, remaining - 1

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)

        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        ip = self._get_client_ip(request)
        is_limited, count, remaining = self._is_rate_limited(ip)

        if is_limited:
            logger.warning(
                "rate_limit.exceeded",
                ip=ip,
                count=count,
                limit=self.max_requests,
                window=self.window_seconds,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Max {self.max_requests} requests per {self.window_seconds}s",
                    "retry_after": self.window_seconds,
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(self.window_seconds),
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
