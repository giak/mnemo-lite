import asyncio
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

# EPIC-22: Metrics middleware for observability
from middleware.metrics_middleware import MetricsMiddleware

import structlog
from fastapi.routing import APIRoute
from api.core import get_settings
from datetime import datetime
from pydantic import BaseModel

# Import SQLAlchemy async engine creation
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.event import listen

# Import des routes
from routes import health_routes, event_routes, search_routes, ui_routes, graph_routes, monitoring_routes, code_graph_routes, code_search_routes, code_indexing_routes, cache_admin_routes, lsp_routes, monitoring_routes_advanced, conversations_routes, autosave_monitoring_routes, dashboard_routes, batch_indexing_routes, indexing_error_routes, memories_routes, projects_routes, memory_relationship_routes, memory_graph_routes

# Configuration de base
DATABASE_URL = get_settings().DATABASE_URL
ENVIRONMENT = get_settings().ENVIRONMENT
DEBUG = get_settings().DEBUG

# Ajouter la lecture de TEST_DATABASE_URL
TEST_DATABASE_URL = get_settings().TEST_DATABASE_URL

logger = structlog.get_logger()

# Models Pydantic pour les réponses d'erreur
class ErrorResponse(BaseModel):
    detail: str


async def _preload_embedding_models(dual_service) -> None:
    """Précharge les modèles d'embedding en arrière-plan (EPIC-68).

    Le boot ne doit plus attendre ~5-10 min de chargement CPU (bge-m3 +
    jina-code). La tâche tourne en fond ; le premier appel d'embedding
    attend le chargement via les locks du DualEmbeddingService au lieu du
    boot. Une erreur est loggée sans faire crasher l'app : le lazy-load du
    service prend le relais au premier usage.
    """
    try:
        await dual_service.preload_models()
        logger.info("Embedding models pre-loaded in background (EPIC-68)")
    except Exception as e:
        logger.error(
            "Background embedding preload failed",
            error=str(e),
            exc_info=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # EPIC-22 Story 22.6: Configure logging with trace_id propagation
    from utils.logging_config import configure_logging
    configure_logging()

    # OpenObserve: Configure OpenTelemetry (traces + metrics)
    from utils.otel_config import configure_otel, shutdown_otel
    from utils.otel_log_processor import get_log_processor

    otlp_enabled = get_settings().OTLP_ENABLED
    if otlp_enabled:
        configure_otel(
            service_name="mnemolite-api",
            environment=ENVIRONMENT,
        )

    log_processor = get_log_processor()
    if otlp_enabled:
        await log_processor.start()

    # Initialisation au démarrage: Créer le moteur SQLAlchemy
    logger.info(f"Starting MnemoLite API in {ENVIRONMENT} mode")

    # 1. Initialize database engine
    # Skip if already set by test fixtures — prevents overwriting the test engine
    # with a production engine when running via ASGITransport in tests.
    if getattr(app.state, "db_engine", None) is not None:
        logger.info("Database engine already set (likely by test fixture), skipping initialization")
    else:
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
                    pool_pre_ping=True,  # Verify connection alive before use (fixes Docker restart)
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
    # Skip if already set by test fixtures
    if getattr(app.state, "embedding_service", None) is not None:
        logger.info("Embedding service already set (likely by test fixture), skipping initialization")
    elif get_settings().EMBEDDING_MODE == "real":
        try:
            logger.info("⏳ Pre-loading embedding model during startup...")

            # Create DualEmbeddingService directly (can't use dependency injection here)
            from services.dual_embedding_service import DualEmbeddingService
            from dependencies import DualEmbeddingServiceAdapter

            settings = get_settings()
            dual_service = DualEmbeddingService(
                text_model_name=settings.EMBEDDING_MODEL,
                code_model_name=settings.CODE_EMBEDDING_MODEL,
                text_dimension=settings.EMBEDDING_DIMENSION,
                code_dimension=settings.CODE_EMBEDDING_DIMENSION,
                device=settings.EMBEDDING_DEVICE,
                cache_size=settings.EMBEDDING_CACHE_SIZE
            )

            # Wrap with adapter for backward compatibility
            embedding_service = DualEmbeddingServiceAdapter(dual_service)
            app.state.embedding_service = embedding_service

            if ENVIRONMENT == "production":
                # Fail-fast conservé en production (décision documentée) :
                # ne pas démarrer sans modèles d'embedding prêts.
                await dual_service.preload_models()
            else:
                # EPIC-68 : preload asynchrone NON bloquant (dev/test).
                # L'app (health) est disponible immédiatement ; les modèles
                # se chargent en tâche de fond et le premier appel
                # d'embedding attend cette tâche via les locks du service.
                app.state.embedding_preload_task = asyncio.create_task(
                    _preload_embedding_models(dual_service)
                )
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
    redis_url = get_settings().REDIS_URL
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
    typescript_lsp_enabled = get_settings().TYPESCRIPT_LSP_ENABLED
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

    # 7. Initialize Monitoring Alert Service (EPIC-22 Story 22.7)
    try:
        from services.monitoring_alert_service import MonitoringAlertService
        from services.metrics_collector import MetricsCollector
        import redis.asyncio as aioredis

        logger.info("⏳ Initializing monitoring alert service...")

        # Create Redis client for MetricsCollector
        redis_url = get_settings().REDIS_URL
        redis_client = aioredis.from_url(redis_url, decode_responses=False)

        # Create MetricsCollector and MonitoringAlertService
        metrics_collector = MetricsCollector(app.state.db_engine, redis_client)
        monitoring_alert_service = MonitoringAlertService(app.state.db_engine)

        # Store in app.state
        app.state.monitoring_alert_service = monitoring_alert_service
        app.state.metrics_redis_client = redis_client

        # Start background task to check thresholds every 60 seconds
        async def alert_monitoring_loop():
            logger.info("Alert monitoring loop started (60s interval)")
            while True:
                try:
                    await asyncio.sleep(60)  # Wait 1 minute
                    metrics = await metrics_collector.collect_all()
                    alerts = await monitoring_alert_service.check_thresholds(metrics)
                    if alerts:
                        logger.info(f"Created {len(alerts)} new alerts", alert_count=len(alerts))
                except asyncio.CancelledError:
                    logger.info("Alert monitoring loop cancelled")
                    break
                except Exception as e:
                    logger.error("Error in alert monitoring loop", error=str(e))

        app.state.alert_monitoring_task = asyncio.create_task(alert_monitoring_loop())
        logger.info("✅ Monitoring alert service started successfully")

    except Exception as e:
        logger.warning(
            "Monitoring alert service initialization failed - continuing without alerting",
            error=str(e)
        )
        app.state.monitoring_alert_service = None
        app.state.alert_monitoring_task = None

    yield

    # Nettoyage à l'arrêt: Disposer le moteur
    logger.info("Shutting down MnemoLite API")

    # Shutdown OpenTelemetry and log processor (same flag as startup)
    if otlp_enabled:
        shutdown_otel()
        await log_processor.shutdown()

    if hasattr(app.state, "db_engine") and app.state.db_engine:
        await app.state.db_engine.dispose()
        # Set to None so the next lifespan startup (e.g. in tests sharing
        # the same app instance) doesn't see a non-None disposed engine
        # and skip initialization. Routes are protected by dependency_overrides,
        # but MetricsMiddleware reads app.state.db_engine directly.
        app.state.db_engine = None
        logger.info("Database engine disposed.")

    # Cleanup embedding service
    if hasattr(app.state, "embedding_service") and app.state.embedding_service:
        del app.state.embedding_service
        logger.info("Embedding service cleaned up.")

    # Cancel background embedding preload (EPIC-68) : tâche non bloquante
    # en dev/test, annulée proprement au shutdown pour éviter les tâches
    # orphelines ("Task was destroyed but it is pending").
    if hasattr(app.state, "embedding_preload_task") and app.state.embedding_preload_task:
        try:
            app.state.embedding_preload_task.cancel()
            try:
                await app.state.embedding_preload_task
            except asyncio.CancelledError:
                pass
        except Exception as e:
            logger.warning("Error cancelling embedding preload task", error=str(e))
        finally:
            del app.state.embedding_preload_task

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

    # Cleanup Monitoring Alert Service (EPIC-22 Story 22.7)
    if hasattr(app.state, "alert_monitoring_task") and app.state.alert_monitoring_task:
        try:
            app.state.alert_monitoring_task.cancel()
            try:
                await app.state.alert_monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Monitoring alert task stopped.")
        except Exception as e:
            logger.warning("Error stopping monitoring alert task", error=str(e))
        finally:
            del app.state.alert_monitoring_task
            if hasattr(app.state, "monitoring_alert_service"):
                del app.state.monitoring_alert_service
            if hasattr(app.state, "metrics_redis_client"):
                try:
                    await app.state.metrics_redis_client.close()
                except Exception:
                    pass
                del app.state.metrics_redis_client

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
# Never use "*" in production — validate ENVIRONMENT
if ENVIRONMENT == "development":
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
    ]
else:
    allowed_origins = [
        "https://app.mnemolite.com",
    ]
logger.info("cors.origins", environment=ENVIRONMENT, origins=allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# EPIC-22 Story 22.1: Metrics middleware for observability
app.add_middleware(MetricsMiddleware)

# API Key authentication middleware
from middleware.auth import APIKeyMiddleware
from middleware.rate_limit import RateLimitMiddleware
_auth_enabled = get_settings().MNEMO_AUTH_ENABLED
_rate_limit_enabled = get_settings().MNEMO_RATE_LIMIT_ENABLED
_rate_limit_max = get_settings().MNEMO_RATE_LIMIT_MAX
_rate_limit_window = get_settings().MNEMO_RATE_LIMIT_WINDOW

app.add_middleware(RateLimitMiddleware, max_requests=_rate_limit_max, window_seconds=_rate_limit_window, enabled=_rate_limit_enabled)
app.add_middleware(APIKeyMiddleware, enabled=_auth_enabled)
logger.info(
    "auth.middleware",
    enabled=_auth_enabled,
    rate_limit=f"{_rate_limit_max}/{_rate_limit_window}s",
)

# EPIC-21: Disable browser cache in development for instant UI reload
@app.middleware("http")
async def disable_cache_in_development(request: Request, call_next):
    response = await call_next(request)

    if ENVIRONMENT == "development":
        # Disable caching for HTML responses (templates)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

    return response

# Configuration UI: Templates et Static Files
BASE_DIR = Path(__file__).parent  # /app in Docker

# EPIC-21: Disable Jinja2 cache in development for instant template reload
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
if ENVIRONMENT == "development":
    templates.env.auto_reload = True
    templates.env.cache = None  # Disable template cache
    logger.info("Jinja2 template caching DISABLED (development mode)")

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
app.include_router(monitoring_routes.router_v1)  # Metrics & Alerts API v1
app.include_router(monitoring_routes_advanced.router)  # EPIC-22 Story 22.1
app.include_router(conversations_routes.router, tags=["v1_Conversations"])  # EPIC-24: Auto-Save
app.include_router(autosave_monitoring_routes.router, tags=["v1_AutoSave_Monitoring"])  # EPIC-24: Auto-Save Monitoring UI
app.include_router(dashboard_routes.router, tags=["v1_Dashboard"])  # EPIC-25: Dashboard Backend API
app.include_router(batch_indexing_routes.router)  # EPIC-27: Batch Indexing with Redis Streams
app.include_router(indexing_error_routes.router)  # EPIC-27: Indexing Error Tracking
app.include_router(memories_routes.router)  # EPIC-26: Memories Monitor

# EPIC-27: Projects Management
app.include_router(projects_routes.router)
# EPIC-29: Memory Relationships
app.include_router(memory_relationship_routes.router)
# EPIC-31: Memory Graph and Consolidation
app.include_router(memory_graph_routes.router)
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
