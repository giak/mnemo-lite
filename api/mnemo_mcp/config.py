"""
MCP Server Configuration

Pydantic Settings for MCP server configuration.
Loads from environment variables with MCP_ prefix.
"""

from typing import List, Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database (must be set via MCP_DATABASE_URL env var)
    database_url: str = ""
    test_database_url: str = ""

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Cache settings
    cache_ttl_code_search: int = 300  # 5 minutes
    cache_ttl_graph: int = 300  # 5 minutes
    cache_ttl_index_status: int = 60  # 1 minute
    cache_ttl_cache_stats: int = 10  # 10 seconds

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @model_validator(mode="after")
    def validate_config(self):
        """Validate configuration at startup with clear error messages."""
        errors = []

        # Database URL — fall back to DATABASE_URL if MCP_DATABASE_URL not set
        if not self.database_url:
            import os as _os
            db_url = _os.getenv("DATABASE_URL", "")
            if db_url:
                # Strip asyncpg prefix if present
                self.database_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        # Database URL still required
        if not self.database_url:
            errors.append(
                "MCP_DATABASE_URL or DATABASE_URL is required. "
                "Set it in .env or as environment variable. "
                "Example: MCP_DATABASE_URL=postgresql://user:pass@host:5432/mnemolite"
            )
        elif not self.database_url.startswith("postgresql://"):
            errors.append(
                f"MCP_DATABASE_URL must start with 'postgresql://'. "
                f"Got: {self.database_url[:20]}..."
            )

        # HTTP transport warns without auth (skip in Docker/local dev)
        if self.transport == "http" and self.auth_mode == "none":
            import os as _os
            if _os.getenv("ENVIRONMENT", "development") == "production":
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


# Global config instance
config = MCPConfig()
