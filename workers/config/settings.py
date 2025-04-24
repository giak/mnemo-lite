"""
Worker configuration settings
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables with defaults"""
    
    # PostgreSQL settings
    postgres_host: str = Field(default="postgres", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="mnemo", description="PostgreSQL user")
    postgres_password: str = Field(default="mnemopass", description="PostgreSQL password")
    postgres_db: str = Field(default="mnemolite", description="PostgreSQL database name")
    
    # ChromaDB settings
    chromadb_host: str = Field(default="chromadb", description="ChromaDB host")
    chromadb_port: int = Field(default=8000, description="ChromaDB port")
    chromadb_token: Optional[str] = Field(default=None, description="ChromaDB authentication token")
    
    # Redis settings
    redis_host: str = Field(default="redis", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")
    
    # Worker settings
    worker_poll_interval: int = Field(default=5, description="Polling interval in seconds")
    worker_batch_size: int = Field(default=50, description="Maximum batch size for processing")
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    
    # Embedding model settings
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="SentenceTransformer model to use")
    
    class Config:
        env_prefix = ""
        case_sensitive = False 