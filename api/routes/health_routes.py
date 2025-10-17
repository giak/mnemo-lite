import os
import psutil
import time
from fastapi import APIRouter, Depends, HTTPException
import httpx
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
)
from fastapi.responses import Response, JSONResponse
import datetime
import logging
from typing import Dict, Any, List
import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from dependencies import get_db_engine

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Métriques Prometheus
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["endpoint", "method", "status"],
)
api_request_duration = Histogram(
    "api_request_duration_seconds", "API request duration in seconds", ["endpoint"]
)
api_memory_usage = Gauge("api_memory_usage_bytes", "API memory usage in bytes")


async def check_postgres_via_engine(engine: AsyncEngine):
    """Vérifie la connexion à la base de données PostgreSQL via SQLAlchemy engine."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            return {"status": "ok", "version": version}
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {str(e)}")
        return {"status": "error", "message": str(e)}


# Fonction check_chroma supprimée
# async def check_chroma(): ...


@router.get("/readiness", response_model=Dict[str, Any])
async def readiness(db_engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Vérifie si l'API est prête à recevoir du trafic.

    Args:
        db_engine: Moteur de base de données injecté

    Returns:
        État de préparation de l'application
    """
    try:
        # Vérifier la connexion à la base de données
        async with db_engine.connect() as conn:
            # Simple requête pour tester la connexion
            await conn.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "message": "API is ready to receive traffic",
            "checks": {"database": True},
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "API is not ready to receive traffic",
                "checks": {"database": False},
                "details": str(e),
            },
        )


@router.get("/health")
async def health_check(db_engine: AsyncEngine = Depends(get_db_engine)):
    """Endpoint de vérification de santé."""
    start_time = time.time()

    # Mise à jour des métriques - ne pas incrémenter ici, attendre de
    # connaître le vrai statut
    api_memory_usage.set(psutil.Process().memory_info().rss)

    # Vérification de la santé de PostgreSQL via engine
    pg_status = await check_postgres_via_engine(db_engine)

    # Systèmes critiques fonctionnels?
    is_healthy = pg_status["status"] == "ok"
    # Service Unavailable si PG est down
    http_status_code = 200 if is_healthy else 503

    # Calcul de la durée
    duration = time.time() - start_time
    api_request_duration.labels(endpoint="/health").observe(duration)

    # Mise à jour du statut dans le compteur de requêtes - incrémenter avec le
    # vrai code HTTP
    api_requests_total.labels(
        endpoint="/health", method="GET", status=str(http_status_code)
    ).inc()

    response_content = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "duration_ms": round(duration * 1000, 2),
        "database": pg_status["status"] == "ok",  # For test compatibility
        "services": {
            "postgres": pg_status,
            # Section chromadb supprimée
        },
    }

    return JSONResponse(status_code=http_status_code, content=response_content)


@router.get("/metrics")
async def metrics():
    """Endpoint pour les métriques Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Fin du fichier
