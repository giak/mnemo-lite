"""
Alembic environment configuration for MnemoLite
Phase 0 Story 0.1 - Async template with psycopg2 sync driver
"""
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from sqlalchemy.engine import Connection

from alembic import context

from api.core.settings import get_settings

# ========================================================================
# Alembic Config
# ========================================================================
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ========================================================================
# Helper: build sync database URL for Alembic (needs psycopg2, not asyncpg)
# ========================================================================
def _get_sync_db_url() -> str:
    """Return DATABASE_URL with +asyncpg replaced by +psycopg2 for Alembic sync driver."""
    return get_settings().DATABASE_URL.replace("+asyncpg", "+psycopg2")


# ========================================================================
# Set DATABASE_URL dynamically from environment
# ========================================================================
# Override sqlalchemy.url from alembic.ini with settings
# Use sync URL (psycopg2) for Alembic migrations
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", _get_sync_db_url())

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
        _get_sync_db_url(),
        poolclass=pool.NullPool,  # No pooling for migrations
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in "online" mode."""
    run_migrations_online_sync()


# ========================================================================
# Main Entry Point
# ========================================================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
