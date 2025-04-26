import os
import json
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
import structlog
from fastapi.routing import APIRoute
import pgvector.asyncpg

# Import des routes
from routes import memory_routes, search_routes, health_routes, event_routes

# Configuration de base
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Ajouter la lecture de TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage: Créer le pool de connexions
    logger.info(f"Starting MnemoLite API in {ENVIRONMENT} mode")
    
    # Choisir la bonne URL de DB
    db_url_to_use = None
    if ENVIRONMENT == "test":
        logger.info("Using TEST_DATABASE_URL for test environment.")
        db_url_to_use = TEST_DATABASE_URL
    else:
        db_url_to_use = DATABASE_URL
        
    if not db_url_to_use:
        logger.error(f"Database URL not set for environment '{ENVIRONMENT}'!")
        app.state.db_pool = None
    else:
        try:
            app.state.db_pool = await asyncpg.create_pool(
                dsn=db_url_to_use,
                min_size=1,
                max_size=10 # Ajuster selon les besoins
            )
            logger.info(f"Database connection pool created using: {db_url_to_use.split('@')[1] if '@' in db_url_to_use else '[URL hidden]'}") # Log safe part of URL
            
            # Enregistrer les codecs pgvector
            async with app.state.db_pool.acquire() as conn:
                await pgvector.asyncpg.register_vector(conn)
                logger.info("pgvector codecs registered for asyncpg connections.")
                
        except Exception as e:
            logger.error("Failed to create database connection pool or register codecs", error=str(e))
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


# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}, # Use standard FastAPI detail field
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the full error in debug mode or non-HTTP errors
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc) if DEBUG else "Internal Server Error"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG) 