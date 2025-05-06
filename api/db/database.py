# api/db/database.py
import asyncpg
import os
from pgvector.asyncpg import register_vector


class Database:
    def __init__(self, dsn: str | None = None):
        # Utilise le DSN fourni ou celui de l'environnement
        self.dsn = dsn or os.environ.get(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/mnemolite_db"
        )
        self._pool: asyncpg.Pool | None = None
        print(f"[Database Class] Initialized with DSN: {self.dsn}")  # Debug print

    # Function to register the vector type adapter
    async def _init_connection(self, conn):
        print(f"[Database Class] Registering pgvector adapter for connection {conn}")
        await register_vector(conn)
        print(f"[Database Class] pgvector adapter registered for connection {conn}")

    async def get_pool(self) -> asyncpg.Pool | None:
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
        if self._pool:
            print("[Database Class] Closing connection pool...")  # Debug print
            await self._pool.close()
            self._pool = None
            print("[Database Class] Connection pool closed.")  # Debug print


# Optionnel: une instance globale si utilisée ailleurs dans l'API
# db = Database()
