import os
import json
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Remove asyncpg import
# import asyncpg
import structlog
from fastapi.routing import APIRoute
import uuid
from typing import Optional
import logging
import sys
from datetime import datetime
from pydantic import BaseModel, Field

# Import SQLAlchemy async engine creation
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.event import listen

# Import pgvector setup for SQLAlchemy (assuming a utility exists or needs creation)
# from db.utils import register_vector_sqlalchemy # Placeholder for pgvector setup
# import pgvector.asyncpg # Keep for potential raw connection access if needed?

# Import des routes
from routes import memory_routes, health_routes, event_routes, search_routes
from routes.health_routes import router as health_router

# Configuration de base
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Ajouter la lecture de TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

logger = structlog.get_logger()

# Placeholder: Function to register pgvector type handler on connect
# Needs to be implemented correctly based on sqlalchemy/pgvector interaction
# async def register_vector_on_connect(dbapi_connection, connection_record):
#    logger.info("Registering pgvector type for new SQLAlchemy connection...")
#    # This part depends on how pgvector integrates with SQLAlchemy's async driver
#    # Might involve registering type handlers on the raw DBAPI connection
#    # Or perhaps SQLAlchemy dialect handles it automatically? Needs verification.
#    # Example for asyncpg raw connection (if accessible):
#    # raw_conn = await dbapi_connection.get_raw_connection() # Hypothetical
#    # await pgvector.asyncpg.register_vector(raw_conn) # Using old asyncpg method as example
#    # Example based on psycopg: register_vector(dbapi_connection)
#    pass # Requires proper implementation


# Models Pydantic pour les réponses d'erreur
class ErrorResponse(BaseModel):
    detail: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage: Créer le moteur SQLAlchemy
    logger.info(f"Starting MnemoLite API in {ENVIRONMENT} mode")

    db_url_to_use = TEST_DATABASE_URL if ENVIRONMENT == "test" else DATABASE_URL

    if not db_url_to_use:
        logger.error(f"Database URL not set for environment '{ENVIRONMENT}'!")
        app.state.db_engine = None  # Store None if no URL
    else:
        try:
            # Create SQLAlchemy Async Engine
            app.state.db_engine: AsyncEngine = create_async_engine(
                db_url_to_use,
                echo=DEBUG,  # Log SQL queries if DEBUG is True
                pool_size=10,  # Example pool size
                max_overflow=5,  # Example overflow
                future=True,
                pool_pre_ping=True,
            )
            logger.info(
                f"Database engine created using: {db_url_to_use.split('@')[1] if '@' in db_url_to_use else '[URL hidden]'}"
            )

            # Register pgvector type handler listener (if needed)
            # This approach might need adjustment based on how pgvector works with SQLAlchemy async drivers
            # listen(app.state.db_engine.sync_engine, "connect", register_vector_on_connect) # Using sync_engine might be incorrect for async
            # TODO: Verify correct way to register pgvector types with SQLAlchemy async engine
            logger.warning(
                "pgvector type registration with SQLAlchemy async engine needs verification."
            )

            # Optional: Test connection
            async with app.state.db_engine.connect() as conn:
                logger.info("Database connection test successful.")

        except Exception as e:
            logger.error(
                "Failed to create database engine", error=str(e), exc_info=True
            )
            app.state.db_engine = None  # Set to None on failure

    yield

    # Nettoyage à l'arrêt: Disposer le moteur
    logger.info("Shutting down MnemoLite API")
    if hasattr(app.state, "db_engine") and app.state.db_engine:
        await app.state.db_engine.dispose()
        logger.info("Database engine disposed.")


# Création de l'application
app = FastAPI(
    title="MnemoLite API",
    description="API pour la gestion de la mémoire événementielle et vectorielle",
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan,
    responses={
        500: {"model": ErrorResponse, "description": "Erreur interne du serveur"},
        400: {"model": ErrorResponse, "description": "Requête invalide"},
        404: {"model": ErrorResponse, "description": "Ressource introuvable"},
    },
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if DEBUG else ["https://app.mnemolite.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routes
app.include_router(
    memory_routes.router, prefix="/v0/memories", tags=["v0_memories (Legacy)"]
)
app.include_router(event_routes.router, prefix="/v1/events", tags=["v1_Events"])
app.include_router(search_routes.router, prefix="/v1/search", tags=["v1_Search"])
app.include_router(health_router)
# app.include_router(embedding_routes.router)

# --- Endpoint pour la création d'événements PENDANT LES TESTS ---
# Ne devrait pas être exposé en production.
# Utilise l'injection de dépendance standard pour obtenir le repo.
from db.repositories.event_repository import EventRepository, EventCreate, EventModel
from dependencies import get_event_repository


@app.post(
    "/v1/_test_only/events/",
    response_model=EventModel,
    tags=["_Test Utilities"],
    include_in_schema=(ENVIRONMENT == "test" or DEBUG),  # Hide from prod docs
    summary="Create an event (for testing)",
)
async def create_event_for_testing(
    event_data: EventCreate, repo: EventRepository = Depends(get_event_repository)
):
    """Endpoint réservé aux tests pour créer un événement.
    Utilise le pool de connexion principal de l'application.
    """
    try:
        created_event = await repo.add(event_data)
        return created_event
    except Exception as e:
        logger.error("Error creating event via test endpoint", exc_info=True)
        # Lever une HTTPException pour que TestClient la capture correctement
        raise HTTPException(status_code=500, detail=f"Failed to create test event: {e}")


# --- Fin Endpoint de test ---

# --- Endpoint de Debug Temporaire ---
# @app.get("/debug/routes")
# async def list_routes():
#     """Liste toutes les routes enregistrées dans l'application."""
#     routes_info = []
#     for route in app.routes:
#         if isinstance(route, APIRoute):
#             routes_info.append({
#                 "path": route.path,
#                 "name": route.name,
#                 "methods": sorted(list(route.methods))
#             })
#     return routes_info
# --- Fin Endpoint de Debug ---

# --- Route de Test Temporaire ---
# @app.get("/v1/test")
# async def test_route():
#     return {"status": "test route ok"}
# --- Fin Route de Test ---


@app.get("/")
async def root():
    return {
        "name": "MnemoLite API",
        "version": "1.0.0",
        "status": "operational",
        "environment": ENVIRONMENT,
        "docs": "/docs",
        "redoc": "/redoc",
    }


# Exception Handlers
class RouteErrorHandler(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except HTTPException as http_exc:
                logger.warning(
                    f"HTTPException caught: {http_exc.status_code} {http_exc.detail}",
                    request=request.url.path,
                )
                raise http_exc  # Re-raise FastAPI's HTTPException
            except Exception as exc:
                logger.exception(
                    "Unhandled exception in route handler", request=request.url.path
                )
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Internal Server Error"},
                )

        return custom_route_handler


app.router.route_class = RouteErrorHandler

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG)
