"""
MCP Server Configuration

Pydantic Settings for MCP server configuration.
Loads from environment variables with MCP_ prefix.
"""

from typing import List, Literal
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
    api_keys: dict[str, str] = {
        "dev-key-12345": "developer",
        "test-key-67890": "tester"
    }
    oauth_secret_key: str = "change-me-in-production"

    # CORS (HTTP transport only)
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8001"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "OPTIONS"]
    cors_allow_headers: List[str] = ["Authorization", "Content-Type"]

    # Database (use Docker service names in containers, localhost for host)
    database_url: str = "postgresql://mnemo:mnemopass@db:5432/mnemolite"
    test_database_url: str = "postgresql://mnemo:mnemopass@db:5432/mnemolite_test"

    # Redis (use Docker service name in containers, localhost for host)
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


# Global config instance
config = MCPConfig()
