import os
import json
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog
from fastapi.routing import APIRoute
import uuid
from typing import Optional

# Import SQLAlchemy async engine creation
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Import direct des modules de routes pour contourner le problème d'importation
from routes.memory_routes import router as memory_routes
from routes.event_routes import router as event_routes
from routes.search_routes import router as search_routes
from routes.health_routes import router as health_routes

# Configuration de base
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Ajouter la lecture de TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage: Créer le moteur SQLAlchemy
    logger.info(f"Starting MnemoLite API in {ENVIRONMENT} mode")
    
    db_url_to_use = TEST_DATABASE_URL if ENVIRONMENT == "test" else DATABASE_URL
        
    if not db_url_to_use:
        logger.error(f"Database URL not set for environment '{ENVIRONMENT}'!")
        app.state.db_engine = None # Store None if no URL
    else:
        try:
            # Create SQLAlchemy Async Engine
            app.state.db_engine = create_async_engine(
                db_url_to_use,
                echo=DEBUG, # Log SQL queries if DEBUG is True
                pool_size=10, # Example pool size
                max_overflow=5  # Example overflow
            )
            logger.info(f"Database engine created successfully")
            
            # Optional: Test connection
            async with app.state.db_engine.connect() as conn:
                logger.info("Database connection test successful.")

        except Exception as e:
            logger.error("Failed to create database engine", error=str(e), exc_info=True)
            app.state.db_engine = None # Set to None on failure
    
    yield
    
    # Nettoyage à l'arrêt: Disposer le moteur
    logger.info("Shutting down MnemoLite API")
    if hasattr(app.state, 'db_engine') and app.state.db_engine:
        await app.state.db_engine.dispose()
        logger.info("Database engine disposed.")


# Création de l'application
app = FastAPI(
    title="MnemoLite API",
    description="API pour la gestion de la mémoire événementielle et vectorielle",
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan
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
app.include_router(memory_routes, prefix="/v0/memories", tags=["v0_memories (Legacy)"])
app.include_router(event_routes, prefix="/v1/events", tags=["v1_Events"])
app.include_router(search_routes, prefix="/v1/search", tags=["v1_Search"])
app.include_router(health_routes, prefix="/v1", tags=["v1_Health & Metrics"])

@app.get("/")
async def root():
    return {
        "name": "MnemoLite API",
        "version": "1.0.0",
        "status": "operational",
        "environment": ENVIRONMENT,
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Exception Handlers
class RouteErrorHandler(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except HTTPException as http_exc:
                logger.warning(f"HTTPException caught: {http_exc.status_code} {http_exc.detail}", request=request.url.path)
                raise http_exc # Re-raise FastAPI's HTTPException
            except Exception as exc:
                logger.exception("Unhandled exception in route handler", request=request.url.path)
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Internal Server Error"},
                )
        return custom_route_handler

app.router.route_class = RouteErrorHandler

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG) 