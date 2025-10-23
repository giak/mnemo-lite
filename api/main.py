import os
import json
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

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

# Import des routes
from routes import health_routes, event_routes, search_routes, ui_routes, graph_routes, monitoring_routes, code_graph_routes, code_search_routes, code_indexing_routes, cache_admin_routes, lsp_routes

# Configuration de base
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Ajouter la lecture de TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

logger = structlog.get_logger()

# Models Pydantic pour les réponses d'erreur
class ErrorResponse(BaseModel):
    detail: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage: Créer le moteur SQLAlchemy
    logger.info(f"Starting MnemoLite API in {ENVIRONMENT} mode")

    # 1. Initialize database engine
    db_url_to_use = TEST_DATABASE_URL if ENVIRONMENT == "test" else DATABASE_URL

    if not db_url_to_use:
        logger.error(f"Database URL not set for environment '{ENVIRONMENT}'!")
        app.state.db_engine = None  # Store None if no URL
    else:
        try:
            # Create SQLAlchemy Async Engine optimized for local usage
            # Local apps don't need large connection pools
            app.state.db_engine: AsyncEngine = create_async_engine(
                db_url_to_use,
                echo=DEBUG,  # Log SQL queries if DEBUG is True
                pool_size=20,  # Reduced from 10 - sufficient for local app
                max_overflow=10,  # Reduced from 5 - minimal overflow needed
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_pre_ping=False,  # Not needed for local PostgreSQL
                future=True,
                connect_args={
                    "server_settings": {
                        "jit": "off"  # Disable JIT for small queries (local usage)
                    },
                    "command_timeout": 60,  # 60 seconds timeout
                }
            )
            logger.info(
                f"Database engine created using: {db_url_to_use.split('@')[1] if '@' in db_url_to_use else '[URL hidden]'}"
            )

            # Optional: Test connection
            async with app.state.db_engine.connect() as conn:
                logger.info("Database connection test successful.")

        except Exception as e:
            logger.error(
                "Failed to create database engine", error=str(e), exc_info=True
            )
            app.state.db_engine = None  # Set to None on failure

    # 2. Pre-load embedding model (si mode=real)
    embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()
    if embedding_mode == "real":
        try:
            logger.info("⏳ Pre-loading embedding model during startup...")

            # Create DualEmbeddingService directly (can't use dependency injection here)
            from services.dual_embedding_service import DualEmbeddingService
            from dependencies import DualEmbeddingServiceAdapter

            dual_service = DualEmbeddingService(
                text_model_name=os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
                code_model_name=os.getenv("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code"),
                dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
                device=os.getenv("EMBEDDING_DEVICE", "cpu"),
                cache_size=int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
            )

            # Wrap with adapter for backward compatibility
            embedding_service = DualEmbeddingServiceAdapter(dual_service)

            # Pre-load BOTH models at startup (TEXT + CODE)
            await dual_service.preload_models()

            logger.info("✅ Both embedding models pre-loaded successfully")
            app.state.embedding_service = embedding_service
        except Exception as e:
            logger.error(
                "❌ Failed to pre-load embedding model",
                error=str(e),
                exc_info=True
            )
            # Décision: Fail fast (recommandé pour production)
            # Pour développement, on peut continuer avec le mode mock
            if ENVIRONMENT == "production":
                raise RuntimeError(f"Failed to load embedding model: {e}")
            else:
                logger.warning("Continuing in development mode without pre-loaded model")
                app.state.embedding_service = None
    else:
        logger.info("Using mock embeddings, no model pre-loading needed")
        app.state.embedding_service = None

    # 3. Initialize Redis L2 cache (EPIC-10 Story 10.2)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        from services.caches import RedisCache

        logger.info("⏳ Connecting to Redis L2 cache...", redis_url=redis_url)

        redis_cache = RedisCache(redis_url=redis_url)
        await redis_cache.connect()

        app.state.redis_cache = redis_cache
        logger.info("✅ Redis L2 cache connected successfully")
    except Exception as e:
        logger.warning(
            "Redis L2 cache connection failed - continuing with graceful degradation",
            error=str(e),
            redis_url=redis_url
        )
        # Graceful degradation: continue without L2 cache
        app.state.redis_cache = None

    # 4. Initialize Error Tracking and Alert Service (EPIC-12 Story 12.4)
    try:
        from db.repositories.error_repository import ErrorRepository
        from services.error_tracking_service import ErrorTrackingService
        from services.alert_service import AlertService

        logger.info("⏳ Initializing error tracking system...")

        # Create error repository and tracking service
        error_repository = ErrorRepository(app.state.db_engine)
        error_tracking_service = ErrorTrackingService(error_repository)

        # Create and start alert service
        alert_service = AlertService(
            error_tracking_service=error_tracking_service,
            check_interval=300  # 5 minutes
        )
        await alert_service.start()

        # Store in app.state for access in routes
        app.state.error_tracking_service = error_tracking_service
        app.state.alert_service = alert_service

        logger.info("✅ Error tracking and alert service started successfully")
    except Exception as e:
        logger.warning(
            "Error tracking system initialization failed - continuing without error tracking",
            error=str(e)
        )
        app.state.error_tracking_service = None
        app.state.alert_service = None

    # 5. Initialize LSP Lifecycle Manager (EPIC-13 Story 13.3)
    try:
        from services.lsp import LSPLifecycleManager

        logger.info("⏳ Starting Python LSP Lifecycle Manager...")

        # Create and start Python LSP lifecycle manager
        lsp_lifecycle_manager = LSPLifecycleManager(
            workspace_root="/tmp/lsp_workspace",
            max_restart_attempts=3
        )
        await lsp_lifecycle_manager.start()

        # Store in app.state for access in routes and dependencies
        app.state.lsp_lifecycle_manager = lsp_lifecycle_manager

        logger.info(
            "✅ Python LSP Lifecycle Manager started successfully",
            pid=lsp_lifecycle_manager.client.process.pid if lsp_lifecycle_manager.client and lsp_lifecycle_manager.client.process else None
        )
    except Exception as e:
        logger.warning(
            "Python LSP Lifecycle Manager initialization failed - continuing without Python LSP type extraction",
            error=str(e)
        )
        app.state.lsp_lifecycle_manager = None

    # 6. Initialize TypeScript LSP Client (EPIC-16 Story 16.3)
    typescript_lsp_enabled = os.getenv("TYPESCRIPT_LSP_ENABLED", "true").lower() == "true"
    if typescript_lsp_enabled:
        try:
            from services.lsp.typescript_lsp_client import TypeScriptLSPClient

            logger.info("⏳ Starting TypeScript LSP client...")

            # Create workspace directory if it doesn't exist
            ts_workspace_root = "/tmp/ts_lsp_workspace"
            Path(ts_workspace_root).mkdir(parents=True, exist_ok=True)

            # Create and start TypeScript LSP client
            typescript_lsp = TypeScriptLSPClient(workspace_root=ts_workspace_root)
            await typescript_lsp.start()

            # Store in app.state for access in routes and dependencies
            app.state.typescript_lsp = typescript_lsp

            logger.info(
                "✅ TypeScript LSP client started successfully",
                pid=typescript_lsp.process.pid if typescript_lsp.process else None
            )
        except Exception as e:
            logger.warning(
                "TypeScript LSP client initialization failed - continuing without TypeScript LSP type extraction",
                error=str(e)
            )
            # Graceful degradation: continue without TypeScript LSP
            app.state.typescript_lsp = None
    else:
        logger.info("TypeScript LSP disabled via TYPESCRIPT_LSP_ENABLED=false")
        app.state.typescript_lsp = None

    yield

    # Nettoyage à l'arrêt: Disposer le moteur
    logger.info("Shutting down MnemoLite API")
    if hasattr(app.state, "db_engine") and app.state.db_engine:
        await app.state.db_engine.dispose()
        logger.info("Database engine disposed.")

    # Cleanup embedding service
    if hasattr(app.state, "embedding_service") and app.state.embedding_service:
        del app.state.embedding_service
        logger.info("Embedding service cleaned up.")

    # Cleanup Redis L2 cache (EPIC-10 Story 10.2)
    if hasattr(app.state, "redis_cache") and app.state.redis_cache:
        try:
            await app.state.redis_cache.disconnect()
            logger.info("Redis L2 cache disconnected.")
        except Exception as e:
            logger.warning("Error disconnecting Redis cache", error=str(e))
        finally:
            del app.state.redis_cache

    # Cleanup Alert Service (EPIC-12 Story 12.4)
    if hasattr(app.state, "alert_service") and app.state.alert_service:
        try:
            await app.state.alert_service.stop()
            logger.info("Alert service stopped.")
        except Exception as e:
            logger.warning("Error stopping alert service", error=str(e))
        finally:
            del app.state.alert_service
            if hasattr(app.state, "error_tracking_service"):
                del app.state.error_tracking_service

    # Cleanup TypeScript LSP Client (EPIC-16 Story 16.3)
    if hasattr(app.state, "typescript_lsp") and app.state.typescript_lsp:
        try:
            await app.state.typescript_lsp.shutdown()
            logger.info("TypeScript LSP client shut down gracefully.")
        except Exception as e:
            logger.warning("Error shutting down TypeScript LSP client", error=str(e))
        finally:
            del app.state.typescript_lsp

    # Cleanup Python LSP Lifecycle Manager (EPIC-13 Story 13.3)
    if hasattr(app.state, "lsp_lifecycle_manager") and app.state.lsp_lifecycle_manager:
        try:
            await app.state.lsp_lifecycle_manager.shutdown()
            logger.info("Python LSP Lifecycle Manager shut down gracefully.")
        except Exception as e:
            logger.warning("Error shutting down LSP Lifecycle Manager", error=str(e))
        finally:
            del app.state.lsp_lifecycle_manager


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

# Configuration UI: Templates et Static Files
BASE_DIR = Path(__file__).parent  # /app in Docker
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Custom Jinja2 filter for French date formatting
def format_date_french(value) -> str:
    """
    Format datetime to French format: 'lundi 12 septembre 15h 12min 35s'

    Args:
        value: datetime object or ISO string

    Returns:
        French formatted date string
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return value

    if not isinstance(value, datetime):
        return str(value)

    # French day names
    days_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

    # French month names
    months_fr = [
        'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
        'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
    ]

    day_name = days_fr[value.weekday()]
    day_num = value.day
    month_name = months_fr[value.month - 1]
    hour = value.hour
    minute = value.minute
    second = value.second

    return f"{day_name} {day_num} {month_name} {hour}h {minute}min {second}s"

# Register the filter
templates.env.filters['date_fr'] = format_date_french

# Inject templates instance into ui_routes
ui_routes.set_templates(templates)

logger.info("UI configured: templates and static files mounted")

# Enregistrement des routes
app.include_router(event_routes.router, prefix="/v1/events", tags=["v1_Events"])
app.include_router(search_routes.router, prefix="/v1/search", tags=["v1_Search"])
app.include_router(code_graph_routes.router, prefix="/v1", tags=["v1_Code_Graph"])
app.include_router(code_search_routes.router, tags=["v1_Code_Search"])
app.include_router(code_indexing_routes.router, tags=["v1_Code_Indexing"])
app.include_router(cache_admin_routes.router, tags=["v1_Cache_Admin"])
app.include_router(lsp_routes.router, tags=["v1_LSP"])
app.include_router(health_routes.router)
app.include_router(ui_routes.router)
app.include_router(graph_routes.router)
app.include_router(monitoring_routes.router)
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
