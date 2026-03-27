"""
TDD tests for Rate Limiting middleware.
"""

import pytest
import time
from middleware.rate_limit import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Verify rate limiting middleware."""

    def test_rate_limit_tracking(self):
        """Rate limiter should track requests per IP."""
        middleware = RateLimitMiddleware(app=None, max_requests=5, window_seconds=60, enabled=True)

        is_limited, count, remaining = middleware._is_rate_limited("192.168.1.1")
        assert is_limited is False
        assert count == 1
        assert remaining == 4

    def test_rate_limit_exceeded(self):
        """Rate limiter should block after max_requests."""
        middleware = RateLimitMiddleware(app=None, max_requests=3, window_seconds=60, enabled=True)

        middleware._is_rate_limited("10.0.0.1")  # 1
        middleware._is_rate_limited("10.0.0.1")  # 2
        middleware._is_rate_limited("10.0.0.1")  # 3

        is_limited, count, remaining = middleware._is_rate_limited("10.0.0.1")  # 4 → blocked
        assert is_limited is True
        assert remaining == 0

    def test_rate_limit_per_ip(self):
        """Different IPs should have separate limits."""
        middleware = RateLimitMiddleware(app=None, max_requests=2, window_seconds=60, enabled=True)

        middleware._is_rate_limited("1.1.1.1")  # 1
        middleware._is_rate_limited("1.1.1.1")  # 2
        is_limited_ip1, _, _ = middleware._is_rate_limited("1.1.1.1")  # 3 → blocked

        is_limited_ip2, _, _ = middleware._is_rate_limited("2.2.2.2")  # 1 → ok

        assert is_limited_ip1 is True
        assert is_limited_ip2 is False

    def test_disabled_middleware(self):
        """Disabled middleware should not block."""
        middleware = RateLimitMiddleware(app=None, enabled=False)
        assert middleware.enabled is False

    def test_exempt_paths(self):
        """Health and docs paths should be exempt."""
        middleware = RateLimitMiddleware(app=None, enabled=True)
        assert middleware.EXEMPT_PATHS.intersection({"/health", "/readiness", "/metrics", "/docs"}) == {"/health", "/readiness", "/metrics", "/docs"}
