"""Tests for PrivacyService — EPIC-42: Secret Stripping & PII Redaction.

v1 MVP: 11 core patterns, stdlib re, zero new dependencies.
"""

import os
import pytest

import sys
sys.path.insert(0, "/app")

from services.privacy_service import PrivacyService, get_privacy_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton between tests."""
    import services.privacy_service as _mod
    _mod._privacy_service = None
    yield
    _mod._privacy_service = None


@pytest.fixture
def privacy(monkeypatch):
    """Create a PrivacyService with MCP_PRIVACY_ENABLED=true."""
    monkeypatch.setenv("MCP_PRIVACY_ENABLED", "true")
    return PrivacyService()


@pytest.fixture
def privacy_disabled(monkeypatch):
    """Create a PrivacyService with MCP_PRIVACY_ENABLED=false."""
    monkeypatch.setenv("MCP_PRIVACY_ENABLED", "false")
    return PrivacyService()


# ---------------------------------------------------------------------------
# Pattern tests — one per pattern
# ---------------------------------------------------------------------------

class TestAWSAccessKey:
    def test_akia_prefix(self, privacy):
        text = "My key is AKIAIOSFODNN7EXAMPLE"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: AWS_ACCESS_KEY]" in clean
        assert "AKIAIOSFODNN7EXAMPLE" not in clean
        assert counts.get("AWS_ACCESS_KEY") == 1

    def test_a3t_prefix(self, privacy):
        text = "Found A3T4ZFGCR6ALV2HXOQBR in logs"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: AWS_ACCESS_KEY]" in clean
        assert "A3T4ZFGCR6ALV2HXOQBR" not in clean
        assert counts.get("AWS_ACCESS_KEY") == 1

    def test_asia_prefix(self, privacy):
        text = "Temp cred ASIAIOSFODNN7EXAMPLE is active"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: AWS_ACCESS_KEY]" in clean
        assert counts.get("AWS_ACCESS_KEY") == 1

    def test_no_false_positive(self, privacy):
        text = "The AKIA is a prefix used in AWS keys"
        clean, counts = privacy.sanitize(text)
        # "AKIA" alone (4 chars) doesn't match — needs 16 more chars after prefix
        assert "AKIA" in clean
        assert counts == {}


class TestOpenAIKey:
    def test_sk_proj(self, privacy):
        text = "export OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: OPENAI_KEY]" in clean
        assert "abc123def456" not in clean
        assert counts.get("OPENAI_KEY") == 1

    def test_sk_svcacct(self, privacy):
        text = "Service account key: sk-svcacct-abcdefghijklmnopqrstuv"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: OPENAI_KEY]" in clean
        assert counts.get("OPENAI_KEY") == 1

    def test_short_key_not_matched(self, privacy):
        # Keys shorter than 20 chars after prefix should not match
        text = "sk-proj-short"
        clean, counts = privacy.sanitize(text)
        assert counts.get("OPENAI_KEY", 0) == 0


class TestAnthropicKey:
    def test_sk_ant_api03(self, privacy):
        text = "Anthropic key: sk-ant-api03-abcdefghijklmnopqrstuvwx"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: ANTHROPIC_KEY]" in clean
        assert counts.get("ANTHROPIC_KEY") == 1

    def test_api_40hex(self, privacy):
        text = "Direct API key: api-abcdef1234567890abcdef1234567890abcdef12"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: ANTHROPIC_KEY]" in clean
        assert counts.get("ANTHROPIC_KEY") == 1

    def test_short_api_not_matched(self, privacy):
        text = "api-shortkey"
        clean, counts = privacy.sanitize(text)
        assert counts.get("ANTHROPIC_KEY", 0) == 0


class TestGitHubToken:
    def test_ghp(self, privacy):
        text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwx1234567890ab"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GITHUB_TOKEN]" in clean
        assert counts.get("GITHUB_TOKEN") == 1

    def test_gho(self, privacy):
        text = "OAuth: gho_abcdefghijklmnopqrstuvwx1234567890ab"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GITHUB_TOKEN]" in clean
        assert counts.get("GITHUB_TOKEN") == 1

    def test_github_pat(self, privacy):
        text = "Fine-grained: github_pat_abcdefghijklmnopqrstuvwx1234567890abcd"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GITHUB_TOKEN]" in clean
        assert counts.get("GITHUB_TOKEN") == 1

    def test_short_token_not_matched(self, privacy):
        text = "ghp_short"
        clean, counts = privacy.sanitize(text)
        assert counts.get("GITHUB_TOKEN", 0) == 0


class TestGitLabToken:
    def test_glpat(self, privacy):
        text = "GITLAB_TOKEN=glpat-abcdefghijklmnopqrst"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GITLAB_TOKEN]" in clean
        assert counts.get("GITLAB_TOKEN") == 1


class TestSlackToken:
    def test_xoxb(self, privacy):
        text = "SLACK_BOT_TOKEN=xoxb-1234567890-0987654321-abcdefghijklmnopqrstuvwxyz"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: SLACK_TOKEN]" in clean
        assert counts.get("SLACK_TOKEN") == 1

    def test_xoxp(self, privacy):
        text = "SLACK_USER_TOKEN=xoxp-1234567890-0987654321-abcdefghijklmnopqrstuvwxyz12"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: SLACK_TOKEN]" in clean
        assert counts.get("SLACK_TOKEN") == 1


class TestBearerToken:
    def test_bearer(self, privacy):
        text = "Authorization: Bearer abc123tokenXYZ456def"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: BEARER_TOKEN]" in clean
        assert "abc123tokenXYZ456def" not in clean
        assert counts.get("BEARER_TOKEN") == 1

    def test_bearer_with_padding(self, privacy):
        text = "Auth: Bearer abc123+def456/ghi=="
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: BEARER_TOKEN]" in clean
        assert counts.get("BEARER_TOKEN") == 1


class TestJWT:
    def test_jwt_three_parts(self, privacy):
        text = "Token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456ghi789jkl"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: JWT]" in clean
        assert counts.get("JWT") == 1

    def test_no_false_positive_short_jwt(self, privacy):
        # Too short to be a real JWT
        text = "eyJ.x.y"
        clean, counts = privacy.sanitize(text)
        assert counts.get("JWT", 0) == 0


class TestGenericSecret:
    def test_api_key_quoted(self, privacy):
        text = 'api_key="abcdefghijklmnop123456"'
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GENERIC_SECRET]" in clean
        assert counts.get("GENERIC_SECRET") == 1

    def test_secret_key_equals(self, privacy):
        text = "secret_key='abcdefghijklmnop12345678'"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GENERIC_SECRET]" in clean
        assert counts.get("GENERIC_SECRET") == 1

    def test_password_quoted(self, privacy):
        text = 'password="mySecretPassword12345"'
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GENERIC_SECRET]" in clean
        assert counts.get("GENERIC_SECRET") == 1

    def test_pwd_quoted(self, privacy):
        text = "pwd='mySecretPassword123456'"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: GENERIC_SECRET]" in clean
        assert counts.get("GENERIC_SECRET") == 1

    def test_short_value_not_matched(self, privacy):
        text = 'api_key="short"'
        clean, counts = privacy.sanitize(text)
        assert counts.get("GENERIC_SECRET", 0) == 0

    def test_unquoted_not_matched(self, privacy):
        text = "api_key=abcdefghijklmnop123456"
        clean, counts = privacy.sanitize(text)
        # Without quotes, should not match
        assert counts.get("GENERIC_SECRET", 0) == 0


class TestConnectionString:
    def test_postgresql(self, privacy):
        text = "DB_URL=postgresql://admin:S3cret!@db.prod.example.com:5432/mydb"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: CONNECTION_STRING]" in clean
        assert "S3cret!" not in clean
        assert counts.get("CONNECTION_STRING") == 1

    def test_mysql(self, privacy):
        text = "DATABASE_URL=mysql://root:password@localhost:3306/test"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: CONNECTION_STRING]" in clean
        assert counts.get("CONNECTION_STRING") == 1

    def test_redis(self, privacy):
        text = "redis://user:pass123@redis-host:6379/0"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: CONNECTION_STRING]" in clean
        assert counts.get("CONNECTION_STRING") == 1

    def test_mongodb(self, privacy):
        text = "mongodb://admin:secret@mongo.example.com:27017"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: CONNECTION_STRING]" in clean
        assert counts.get("CONNECTION_STRING") == 1


class TestPrivateTag:
    def test_private_tag(self, privacy):
        text = "Here is my note <private>super secret data</private> and more text"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: PRIVATE_TAG]" in clean
        assert "super secret data" not in clean
        assert "and more text" in clean
        assert counts.get("PRIVATE_TAG") == 1

    def test_multiline_private_tag(self, privacy):
        text = "Before <private>line1\nline2\nline3</private> After"
        clean, counts = privacy.sanitize(text)
        assert "[REDACTED: PRIVATE_TAG]" in clean
        assert "line1" not in clean
        assert "After" in clean
        assert counts.get("PRIVATE_TAG") == 1


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_disabled(self, privacy_disabled):
        text = "My AWS key is AKIAIOSFODNN7EXAMPLE"
        clean, counts = privacy_disabled.sanitize(text)
        assert clean == text
        assert counts == {}

    def test_empty_text(self, privacy):
        clean, counts = privacy.sanitize("")
        assert clean == ""
        assert counts == {}

    def test_none_text(self, privacy):
        # sanitize() is typed as str but handles None gracefully (falsy)
        clean, counts = privacy.sanitize(None)  # type: ignore[arg-type]
        assert clean is None
        assert counts == {}

    def test_no_secrets(self, privacy):
        text = "Hello world, this is a normal text without any secrets"
        clean, counts = privacy.sanitize(text)
        assert clean == text
        assert counts == {}

    def test_max_length_skip(self, privacy):
        text = "AKIAIOSFODNN7EXAMPLE" + "x" * (PrivacyService.MAX_LENGTH)
        clean, counts = privacy.sanitize(text)
        # Text > 1MB should be skipped entirely
        assert clean == text
        assert counts == {}

    def test_multiple_secrets(self, privacy):
        text = (
            "AWS key AKIAIOSFODNN7EXAMPLE and "
            "GitHub token ghp_abcdefghijklmnopqrstuvwx1234567890ab and "
            "Bearer abc123tokenXYZ456def"
        )
        clean, counts = privacy.sanitize(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in clean
        assert "ghp_abcdefghijklmnopqrstuvwx1234567890" not in clean
        assert "abc123tokenXYZ456def" not in clean
        assert counts.get("AWS_ACCESS_KEY") == 1
        assert counts.get("GITHUB_TOKEN") == 1
        assert counts.get("BEARER_TOKEN") == 1
        assert sum(counts.values()) == 3

    def test_no_false_positives_code(self, privacy):
        """Normal code should not be stripped."""
        text = """
        def authenticate(user, pw_hash):
            if verify_password(pw_hash, stored_hash):
                return create_session(user)
            return None
        """
        clean, counts = privacy.sanitize(text)
        assert clean == text
        assert counts == {}

    def test_no_false_positives_vars(self, privacy):
        """Variable names with 'password' in them should not be redacted."""
        text = "password_changed_at = datetime.now()"
        clean, counts = privacy.sanitize(text)
        # No quotes around the value → should not match GENERIC_SECRET
        assert "password_changed_at" in clean
        assert counts.get("GENERIC_SECRET", 0) == 0

    def test_get_privacy_service_singleton(self, monkeypatch):
        """get_privacy_service should return same instance on repeated calls."""
        monkeypatch.setenv("MCP_PRIVACY_ENABLED", "true")
        svc1 = get_privacy_service()
        svc2 = get_privacy_service()
        assert svc1 is svc2


# ---------------------------------------------------------------------------
# Integration-style tests (no DB, just tool logic)
# ---------------------------------------------------------------------------

class TestMemoryToolIntegration:
    """Test that the sanitize logic works correctly in the context of memory tools."""

    def test_write_memory_sanitize_title_and_content(self, privacy):
        """Simulate what write_memory does: sanitize title + content."""
        title = "AWS credentials for prod"
        content = "The DB is at postgresql://admin:S3cret!@db.prod:5432 and key AKIAIOSFODNN7EXAMPLE"

        title_clean, title_counts = privacy.sanitize(title)
        content_clean, content_counts = privacy.sanitize(content)

        assert title_clean == "AWS credentials for prod"  # No secrets in title
        assert title_counts == {}
        assert "[REDACTED: CONNECTION_STRING]" in content_clean
        assert "[REDACTED: AWS_ACCESS_KEY]" in content_clean
        assert "S3cret!" not in content_clean
        assert "AKIAIOSFODNN7EXAMPLE" not in content_clean
        assert "CONNECTION_STRING" in content_counts
        assert "AWS_ACCESS_KEY" in content_counts

    def test_update_memory_sanitize_optional_fields(self, privacy):
        """Simulate update_memory where only content is updated."""
        title = None
        content = "My OpenAI key is sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234"

        # Only sanitize non-None fields
        title_counts = {}
        content_counts = {}
        if title is not None:
            title, title_counts = privacy.sanitize(title)
        if content is not None:
            content, content_counts = privacy.sanitize(content)

        assert title is None
        assert title_counts == {}
        assert "[REDACTED: OPENAI_KEY]" in content
        assert content_counts.get("OPENAI_KEY") == 1

    def test_graceful_degradation(self, privacy):
        """If sanitize raises, the tool should still continue."""
        # PrivacyService itself shouldn't raise, but the pattern is:
        # try: sanitize; except: continue
        # We test the contract by verifying sanitize never raises on valid input
        for text in ["", "normal text", "AKIAIOSFODNN7EXAMPLE", None]:
            try:
                result = privacy.sanitize(text or "")
                assert isinstance(result, tuple)
                assert len(result) == 2
            except Exception:
                pytest.fail(f"sanitize raised on input: {text!r}")
