"""
Alembic environment configuration for MnemoLite
Phase 0 Story 0.1 - Async template with psycopg2 sync driver
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ========================================================================
# Add parent directory to path for imports
# ========================================================================
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ========================================================================
# Import Settings
# ========================================================================
try:
    from workers.config.settings import settings
except ImportError:
    # Fallback if workers/config not in path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from workers.config.settings import settings

# ========================================================================
# Alembic Config
# ========================================================================
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ========================================================================
# Set DATABASE_URL dynamically from environment
# ========================================================================
# Override sqlalchemy.url from alembic.ini with settings
# Use sync URL (psycopg2) for Alembic migrations
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.sync_database_url)

# ========================================================================
# Target Metadata (for autogenerate support)
# ========================================================================
# Phase 0: No ORM models yet, just baseline NO-OP migration
# Phase 1+: Will import metadata from SQLAlchemy Core Table definitions
target_metadata = None

# Future Phase 1+ (Story 2bis):
# from api.db.models import metadata as target_metadata

# ========================================================================
# Offline Migrations
# ========================================================================
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # PostgreSQL 18 + pgvector compatibility
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


# ========================================================================
# Online Migrations (Sync version - preferred for Alembic)
# ========================================================================
def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # PostgreSQL 18 + pgvector compatibility
        render_as_batch=False,
        # Compare types for vector columns
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online_sync() -> None:
    """Run migrations in 'online' mode using sync engine (psycopg2).

    This is the RECOMMENDED approach for MnemoLite because:
    1. Alembic migrations are inherently sync operations
    2. Avoids asyncpg connection pool issues
    3. Uses psycopg2 which is compatible with SQLAlchemy Core
    4. NullPool prevents connection pooling during migrations
    """
    connectable = create_engine(
        settings.sync_database_url,
        poolclass=pool.NullPool,  # No pooling for migrations
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


# ========================================================================
# Online Migrations (Async version - optional, for future use)
# ========================================================================
async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine.

    NOTE: This is NOT recommended for Phase 0 because it requires
    asyncpg which may conflict with psycopg2 in the same process.

    Use run_migrations_online_sync() instead.
    """
    # Use sync URL even for async engine to avoid asyncpg conflicts
    # This converts postgresql+asyncpg:// to postgresql+psycopg2://
    sync_url = settings.sync_database_url

    # Create engine config from sync URL
    engine_config = config.get_section(config.config_ini_section, {})
    engine_config["sqlalchemy.url"] = sync_url

    connectable = create_engine(
        sync_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Phase 0: Use SYNC engine (psycopg2) to avoid asyncpg conflicts.
    """
    # Use SYNC version (recommended)
    run_migrations_online_sync()

    # Async version disabled for Phase 0
    # asyncio.run(run_async_migrations())


# ========================================================================
# Main Entry Point
# ========================================================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
