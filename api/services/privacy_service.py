"""PrivacyService — Secret stripping & PII redaction for MnemoLite.

v1 MVP: 11 core patterns, stdlib re, zero new dependencies.
Inspired by AgentMemory privacy.ts, validated against gitleaks/detect-secrets.

EPIC-42: Secret Stripping & PII Redaction
"""

from api.core import get_settings
import re
import time
from typing import Dict, List, Tuple

import structlog

logger = structlog.get_logger()

# 11 core patterns — validated against gitleaks, detect-secrets, official docs
# Each entry: (name, raw_regex_string, flags)
_PATTERNS: List[Tuple[str, str, int]] = [
    # Cloud
    (
        "AWS_ACCESS_KEY",
        r"\b(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
        0,
    ),
    # AI Providers
    (
        "OPENAI_KEY",
        r"\b(sk-proj-|sk-svcacct-)[A-Za-z0-9_-]{20,}\b",
        0,
    ),
    (
        "ANTHROPIC_KEY",
        r"\bsk-ant-api03-[A-Za-z0-9_-]{20,}\b|\bapi-[a-z0-9]{40}\b",
        0,
    ),
    # DevEx
    (
        "GITHUB_TOKEN",
        r"\b(gh[pousr]_|github_pat_)[A-Za-z0-9_]{36,255}\b",
        0,
    ),
    (
        "GITLAB_TOKEN",
        r"\bglpat-[A-Za-z0-9\-_]{20,}\b",
        0,
    ),
    (
        "SLACK_TOKEN",
        r"\bxox[bpark]-[0-9]{10,13}-[0-9]{10,13}-[0-9a-zA-Z]{24,34}\b",
        0,
    ),
    # Auth
    (
        "BEARER_TOKEN",
        r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*",
        0,
    ),
    (
        "JWT",
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        0,
    ),
    # Generic
    (
        "GENERIC_SECRET",
        r"""(?i)(api[_-]?key|secret[_-]?key|password|passwd|pwd)[\s:=]{0,3}['"][0-9a-zA-Z\-_.]{16,}['"]""",
        0,  # IGNORECASE is embedded in the pattern via (?i)
    ),
    (
        "CONNECTION_STRING",
        r"(?i)(?:postgresql|postgres|mysql|mongodb|redis|amqp)://[^\s:]+:[^\s@]+@[^\s]+",
        0,  # IGNORECASE embedded via (?i)
    ),
    # Explicit tags
    (
        "PRIVATE_TAG",
        r"<private>[\s\S]*?</private>",
        re.DOTALL,
    ),
]


class PrivacyService:
    """Minimal secret stripping service. v1: 11 patterns, re module, zero new deps."""

    MAX_LENGTH = 1_000_000  # 1MB guard — skip larger texts to avoid CPU lock

    @property
    def pattern_count(self) -> int:
        """Number of compiled patterns (read-only)."""
        return len(self._compiled)

    def __init__(self) -> None:
        self.enabled = get_settings().MCP_PRIVACY_ENABLED
        self._compiled: List[Tuple[str, re.Pattern]] = []

        if self.enabled:
            for name, pattern_str, flags in _PATTERNS:
                try:
                    self._compiled.append((name, re.compile(pattern_str, flags)))
                except re.error as e:
                    logger.error("privacy_service.compile_error", name=name, error=str(e))

            logger.info("privacy_service.initialized", patterns=len(self._compiled))
        else:
            logger.info("privacy_service.disabled")

    def sanitize(self, text: str) -> Tuple[str, Dict[str, int]]:
        """Sanitize text, replacing secrets with [REDACTED: TYPE].

        Returns:
            Tuple of (clean_text, counts_by_type) — e.g. (clean, {"OPENAI_KEY": 1})
        """
        if not self.enabled or not text:
            return text, {}

        if len(text) > self.MAX_LENGTH:
            logger.warning("privacy_service.text_too_long", length=len(text))
            return text, {}

        start = time.time()
        clean_text = text
        counts: Dict[str, int] = {}

        for name, pattern in self._compiled:
            matches = list(pattern.finditer(clean_text))
            if not matches:
                continue

            counts[name] = len(matches)

            # Replace from end to preserve positions
            for m in reversed(matches):
                clean_text = clean_text[: m.start()] + f"[REDACTED: {name}]" + clean_text[m.end() :]

        if counts:
            elapsed_ms = (time.time() - start) * 1000
            logger.warning(
                "privacy_service.redacted",
                total=sum(counts.values()),
                types=counts,
                duration_ms=round(elapsed_ms, 2),
            )

        return clean_text, counts


# Module-level singleton — follows MnemoLite's _services_cache pattern
_privacy_service: PrivacyService | None = None


def get_privacy_service() -> PrivacyService:
    """Get or create the singleton PrivacyService."""
    global _privacy_service
    if _privacy_service is None:
        _privacy_service = PrivacyService()
    return _privacy_service
