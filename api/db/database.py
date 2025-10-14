# api/db/database.py
"""
PostgreSQL database connection pool manager with pgvector support.

This module provides a Database class for managing asyncpg connection pools
with automatic pgvector type registration for vector similarity operations.
"""

import asyncpg
import os
from pgvector.asyncpg import register_vector


class Database:
    """
    Async PostgreSQL database connection pool manager.

    Features:
    - Lazy connection pool initialization
    - Automatic pgvector extension registration
    - Configurable pool sizing (min=5, max=10)
    - Connection lifecycle management

    The connection pool is created on first get_pool() call and reused
    for subsequent calls. Each connection automatically registers the
    pgvector type adapter for VECTOR column support.

    Example:
        >>> db = Database("postgresql://user:pass@localhost:5432/mydb")
        >>> pool = await db.get_pool()
        >>> async with pool.acquire() as conn:
        ...     result = await conn.fetchrow("SELECT 1")
        >>> await db.close_pool()
    """

    def __init__(self, dsn: str | None = None):
        """
        Initialize database manager with DSN.

        Args:
            dsn: PostgreSQL connection string. If None, reads from DATABASE_URL
                 environment variable. Falls back to default connection string
                 if not set.

        Example DSN formats:
            - "postgresql://user:password@localhost:5432/dbname"
            - "postgresql://user:password@localhost/dbname?sslmode=require"
        """
        # Utilise le DSN fourni ou celui de l'environnement
        self.dsn = dsn or os.environ.get(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/mnemolite_db"
        )
        self._pool: asyncpg.Pool | None = None
        print(f"[Database Class] Initialized with DSN: {self.dsn}")  # Debug print

    async def _init_connection(self, conn):
        """
        Initialize a new database connection with pgvector support.

        This is called automatically by asyncpg for each new connection
        in the pool. Registers the pgvector type adapter to enable
        VECTOR column operations.

        Args:
            conn: asyncpg Connection object to initialize

        Note:
            This is an internal callback. Do not call directly.
        """
        print(f"[Database Class] Registering pgvector adapter for connection {conn}")
        await register_vector(conn)
        print(f"[Database Class] pgvector adapter registered for connection {conn}")

    async def get_pool(self) -> asyncpg.Pool | None:
        """
        Get or create the connection pool (lazy initialization).

        Creates a new pool on first call with the following configuration:
        - min_size: 5 connections (kept alive)
        - max_size: 10 connections (maximum concurrent)
        - init: Automatic pgvector registration per connection

        Returns:
            asyncpg.Pool instance, or None if pool creation failed

        Raises:
            Exception: If pool creation fails and error handling is strict

        Example:
            >>> pool = await db.get_pool()
            >>> if pool:
            ...     async with pool.acquire() as conn:
            ...         await conn.execute("SELECT 1")
        """
        if self._pool is None:
            try:
                print("[Database Class] Creating connection pool...")  # Debug print
                # Ajuster min/max size si nécessaire
                self._pool = await asyncpg.create_pool(
                    dsn=self.dsn, min_size=5, max_size=10, init=self._init_connection
                )
                print(
                    "[Database Class] Connection pool created successfully with pgvector init."
                )  # Debug print
            except Exception as e:
                print(f"[Database Class] Error creating connection pool: {e}")
                # Retourner None ou lever une exception selon la gestion d'erreur souhaitée
                return None
        return self._pool

    async def close_pool(self):
        """
        Close the connection pool and release all connections.

        Gracefully closes all active and idle connections in the pool.
        Sets the pool to None to allow re-initialization if needed.

        This should be called during application shutdown to properly
        release database resources.

        Example:
            >>> await db.close_pool()  # Cleanup during shutdown
        """
        if self._pool:
            print("[Database Class] Closing connection pool...")  # Debug print
            await self._pool.close()
            self._pool = None
            print("[Database Class] Connection pool closed.")  # Debug print


# Optionnel: une instance globale si utilisée ailleurs dans l'API
# db = Database()
