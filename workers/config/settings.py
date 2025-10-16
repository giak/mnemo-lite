"""
Worker configuration settings with Pydantic v2
Phase 0 Story 0.1 - Updated for dual embeddings support
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables with defaults"""

    # ========================================================================
    # PostgreSQL settings
    # ========================================================================
    postgres_host: str = Field(default="db", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="mnemo", description="PostgreSQL user")
    postgres_password: str = Field(default="mnemopass", description="PostgreSQL password")
    postgres_db: str = Field(default="mnemolite", description="PostgreSQL database name")

    # Full DATABASE_URL for SQLAlchemy/Alembic (async)
    database_url: Optional[str] = Field(
        default=None,
        description="Full PostgreSQL connection string (postgresql+asyncpg://...)"
    )

    # ========================================================================
    # Embedding settings - Text model (nomic-embed-text-v1.5)
    # ========================================================================
    embedding_model: str = Field(
        default="nomic-ai/nomic-embed-text-v1.5",
        description="Text embedding model (HuggingFace model ID)"
    )
    embedding_dimension: int = Field(
        default=768,
        description="Text embedding vector dimension"
    )

    # ========================================================================
    # Embedding settings - Code model (jina-embeddings-v2-base-code)
    # ========================================================================
    code_embedding_model: str = Field(
        default="jinaai/jina-embeddings-v2-base-code",
        description="Code embedding model (HuggingFace model ID)"
    )
    code_embedding_dimension: int = Field(
        default=768,
        description="Code embedding vector dimension (MUST match embedding_dimension)"
    )

    # ========================================================================
    # Worker settings
    # ========================================================================
    worker_poll_interval: int = Field(default=5, description="Polling interval in seconds")
    worker_batch_size: int = Field(default=50, description="Maximum batch size for processing")
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment (development, staging, production)")

    # ========================================================================
    # Redis settings (optional - for future PGMQ integration)
    # ========================================================================
    redis_host: str = Field(default="redis", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")

    # ========================================================================
    # Pydantic v2 validators
    # ========================================================================

    @field_validator("code_embedding_dimension")
    @classmethod
    def validate_same_dimension(cls, v, info):
        """
        CRITICAL: Validate that code_embedding_dimension matches embedding_dimension.
        MnemoLite uses 768D everywhere to avoid DB migration complexity.
        """
        text_dim = info.data.get("embedding_dimension", 768)
        if v != text_dim:
            raise ValueError(
                f"CODE_EMBEDDING_DIMENSION ({v}) must match "
                f"EMBEDDING_DIMENSION ({text_dim}). "
                f"MnemoLite requires same dimensions (768D) to avoid DB migration. "
                f"See EPIC-06_PHASE_0_CRITICAL_INSIGHTS.md for details."
            )
        return v

    # ========================================================================
    # Pydantic v2 configuration
    # ========================================================================

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore extra env vars
    }

    # ========================================================================
    # Helper methods
    # ========================================================================

    @property
    def sync_database_url(self) -> str:
        """
        Return sync database URL (psycopg2) for Alembic migrations.
        Converts postgresql+asyncpg:// to postgresql+psycopg2://
        """
        if self.database_url:
            return self.database_url.replace(
                "postgresql+asyncpg://",
                "postgresql+psycopg2://"
            )

        # Fallback: construct from individual settings
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        """
        Return async database URL (asyncpg) for runtime queries.
        """
        if self.database_url:
            return self.database_url

        # Fallback: construct from individual settings
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# Singleton instance
settings = Settings()
