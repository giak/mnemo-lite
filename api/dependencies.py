from fastapi import Request, HTTPException, Depends
# Remove asyncpg import
# import asyncpg 
from contextlib import asynccontextmanager

# Import SQLAlchemy AsyncEngine
from sqlalchemy.ext.asyncio import AsyncEngine

# Importer le repository
from db.repositories.event_repository import EventRepository

# Rename and modify to get SQLAlchemy engine
async def get_db_engine(request: Request) -> AsyncEngine:
    """Récupère le moteur SQLAlchemy stocké dans l'état de l'application."""
    engine = request.app.state.db_engine # Expecting db_engine now
    if engine is None:
        # Ceci ne devrait pas arriver si le lifespan est correctement configuré
        raise HTTPException(status_code=503, detail="Database engine is not available.")
    return engine

# The context manager get_db_connection_context is no longer needed 
# as the repository manages connections via the engine.
# The simple get_db_connection function was also problematic and is removed.

# Update to depend on get_db_engine
async def get_event_repository(engine: AsyncEngine = Depends(get_db_engine)) -> EventRepository:
    """Injecte une instance de EventRepository avec le moteur SQLAlchemy."""
    # Pass the engine to the repository constructor
    return EventRepository(engine=engine) 