"""
MCP Server Configuration

Pydantic Settings for MCP server configuration.
Loads from environment variables with MCP_ prefix.
"""

from typing import List, Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from api.core import get_settings


class MCPConfig(BaseSettings):
    """
    MCP Server Configuration.

    All settings can be overridden via environment variables with MCP_ prefix.
    Example: MCP_SERVER_NAME=mnemolite MCP_LOG_LEVEL=DEBUG

    Attributes:
        server_name: MCP server name (shown in Claude Desktop)
        server_version: Server version string
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        transport: Transport mode (stdio or http)
        http_host: HTTP server host (if transport=http)
        http_port: HTTP server port (if transport=http)
        auth_mode: Authentication mode (none, api_key, oauth)
        cors_origins: CORS allowed origins for HTTP transport
    """

    # Server identification
    server_name: str = "mnemolite"
    server_version: str = "1.0.0"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Transport
    transport: Literal["stdio", "http"] = "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8002

    # Authentication (HTTP transport only)
    auth_mode: Literal["none", "api_key", "oauth"] = "none"
    api_keys: dict[str, str] = Field(default_factory=dict)
    oauth_secret_key: str = ""

    # CORS (HTTP transport only)
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8001"])
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "OPTIONS"])
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["Authorization", "Content-Type"])

    # Database — SSOT via AppSettings; MCP_* env vars override from .env
    database_url: Optional[str] = None  # MCP_DATABASE_URL override
    test_database_url: Optional[str] = None  # MCP_TEST_DATABASE_URL override

    # Redis — SSOT via AppSettings; MCP_REDIS_URL override from .env
    redis_url: Optional[str] = None  # MCP_REDIS_URL override

    # Cache settings
    cache_ttl_code_search: int = 300  # 5 minutes
    cache_ttl_graph: int = 300  # 5 minutes
    cache_ttl_index_status: int = 60  # 1 minute
    cache_ttl_cache_stats: int = 10  # 10 seconds

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_config(self):
        """Validate config. DB/Redis SSOT via AppSettings with MCP_* overrides."""
        errors = []

        # Build database_url: MCP_DATABASE_URL field > AppSettings.DATABASE_URL
        db_field = self.database_url  # Loaded from .env via MCP_ prefix
        if db_field:
            db_url = db_field
        else:
            db_url = get_settings().DATABASE_URL
            if db_url:
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        if not db_url:
            errors.append(
                "DATABASE_URL (or MCP_DATABASE_URL) is required. "
                "Set in .env or as environment variable. "
                "Example: DATABASE_URL=postgresql://user:pass@host:5432/mnemolite"
            )
        elif not db_url.startswith("postgresql://"):
            errors.append(
                f"DATABASE_URL must start with 'postgresql://'. Got: {db_url[:20]}..."
            )
        else:
            # Store resolved URL so self.database_url returns the string
            object.__setattr__(self, 'database_url', db_url)

        # HTTP transport warns without auth (skip in Docker/local dev)
        if self.transport == "http" and self.auth_mode == "none":
            import os as _os
            if get_settings().ENVIRONMENT == "production":
                errors.append(
                    "HTTP transport without authentication is insecure. "
                    "Set MCP_AUTH_MODE=api_key and MCP_API_KEYS=key:owner"
                )

        # OAuth requires secret
        if self.auth_mode == "oauth" and not self.oauth_secret_key:
            errors.append(
                "MCP_OAUTH_SECRET_KEY is required when auth_mode=oauth. "
                "Generate a random key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Cache TTLs must be positive
        for field_name in ["cache_ttl_code_search", "cache_ttl_graph",
                           "cache_ttl_index_status", "cache_ttl_cache_stats"]:
            val = getattr(self, field_name)
            if val < 0:
                errors.append(f"{field_name} must be >= 0, got {val}")

        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        return self

    @property
    def resolved_database_url(self) -> str:
        """Resolved DB URL: MCP_DATABASE_URL (from .env) > get_settings().DATABASE_URL."""
        if self.database_url:
            return self.database_url
        db_url = get_settings().DATABASE_URL
        if db_url:
            return db_url.replace("postgresql+asyncpg://", "postgresql://")
        return ""

    @property
    def resolved_test_database_url(self) -> str:
        """Resolved test DB URL: MCP_TEST_DATABASE_URL (from .env) > TEST_DATABASE_URL."""
        if self.test_database_url:
            return self.test_database_url
        return get_settings().TEST_DATABASE_URL or ""

    @property
    def resolved_redis_url(self) -> str:
        """Resolved Redis URL: MCP_REDIS_URL (from .env) > REDIS_URL."""
        if self.redis_url:
            return self.redis_url
        return get_settings().REDIS_URL


# Global config instance
config = MCPConfig()
