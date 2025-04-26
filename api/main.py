import os
import json
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
import structlog
from fastapi.routing import APIRoute

# Import des routes
from routes import memory_routes, search_routes, health_routes, event_routes

# Configuration de base
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage: Créer le pool de connexions
    logger.info(f"Starting MnemoLite API in {ENVIRONMENT} mode")
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set!")
        # On pourrait lever une exception ici pour empêcher le démarrage
        # raise RuntimeError("DATABASE_URL not set") 
        app.state.db_pool = None # Indiquer que le pool n'est pas dispo
    else:
        try:
            app.state.db_pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=1,
                max_size=10 # Ajuster selon les besoins
            )
            logger.info("Database connection pool created.")
        except Exception as e:
            logger.error("Failed to create database connection pool", error=str(e))
            app.state.db_pool = None
    
    yield
    
    # Nettoyage à l'arrêt: Fermer le pool
    logger.info("Shutting down MnemoLite API")
    if app.state.db_pool:
        await app.state.db_pool.close()
        logger.info("Database connection pool closed.")


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
app.include_router(memory_routes.router, prefix="/v0/memories", tags=["v0_memories (Legacy)"])
app.include_router(event_routes.router, prefix="/v1/events", tags=["v1_Events"])
app.include_router(search_routes.router, prefix="/v1/search", tags=["v1_Search"])
app.include_router(health_routes.router, prefix="/v1", tags=["v1_Health & Metrics"])


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
        "redoc": "/redoc"
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if DEBUG else "An error occurred processing your request"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG) 