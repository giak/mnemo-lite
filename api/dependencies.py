from fastapi import Request, HTTPException, Depends
import asyncpg

# Importer le repository
from api.db.repositories.event_repository import EventRepository

async def get_db_pool(request: Request) -> asyncpg.Pool:
    """Récupère le pool de connexions stocké dans l'état de l'application."""
    pool = request.app.state.db_pool
    if pool is None:
        # Ceci ne devrait pas arriver si le lifespan est correctement configuré
        raise HTTPException(status_code=503, detail="Database connection pool is not available.")
    return pool

async def get_event_repository(pool: asyncpg.Pool = Depends(get_db_pool)) -> EventRepository:
    """Injecte une instance de EventRepository avec le pool de connexions."""
    return EventRepository(pool=pool) 