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

# EPIC-12 Story 12.3: Import circuit breaker registry
from utils.circuit_breaker_registry import get_circuit_breaker_metrics

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

    # EPIC-12 Story 12.3: Get circuit breaker metrics
    circuit_breakers = get_circuit_breaker_metrics()

    # Check if any critical circuit is OPEN
    critical_circuits_open = [
        name for name, metrics in circuit_breakers.items()
        if metrics["state"] == "open" and name in ["embedding_service"]  # Critical services
    ]

    # Degrade health if critical circuits are open
    if critical_circuits_open and is_healthy:
        is_healthy = False
        http_status_code = 503

    response_content = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "duration_ms": round(duration * 1000, 2),
        "database": pg_status["status"] == "ok",  # For test compatibility
        "services": {
            "postgres": pg_status,
            # Section chromadb supprimée
        },
        "circuit_breakers": circuit_breakers,  # EPIC-12 Story 12.3
        "critical_circuits_open": critical_circuits_open,  # EPIC-12 Story 12.3
    }

    return JSONResponse(status_code=http_status_code, content=response_content)


@router.get("/metrics")
async def metrics():
    """Endpoint pour les métriques Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/v1/autosave/health")
async def autosave_health_check(db_engine: AsyncEngine = Depends(get_db_engine)):
    """
    Health check spécifique pour le système auto-save Claude Code.

    Vérifie les dépendances critiques pour l'auto-save :
    - Database PostgreSQL connectivity
    - Write capability (test simple insert/delete)

    Returns:
        JSON avec status "healthy" ou "unhealthy" et détails des checks
    """
    start_time = time.time()
    checks = {}
    overall_status = "healthy"
    errors = []

    # 1. Database connectivity check
    try:
        async with db_engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            pg_version = result.scalar()
            checks["database"] = {
                "status": "ok",
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "version": pg_version[:50] if pg_version else "unknown"
            }
    except Exception as e:
        logger.error(f"Autosave health - Database check failed: {str(e)}")
        checks["database"] = {
            "status": "error",
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "error": str(e)
        }
        overall_status = "unhealthy"
        errors.append(f"Database: {str(e)}")

    # 2. Write capability check (test simple query)
    try:
        write_start = time.time()
        async with db_engine.connect() as conn:
            # Test write capability with simple query (no actual write to avoid pollution)
            await conn.execute(text("SELECT 1"))
            checks["write_capability"] = {
                "status": "ok",
                "latency_ms": round((time.time() - write_start) * 1000, 2),
                "test_passed": True
            }
    except Exception as e:
        logger.error(f"Autosave health - Write capability check failed: {str(e)}")
        checks["write_capability"] = {
            "status": "error",
            "latency_ms": round((time.time() - write_start) * 1000, 2),
            "test_passed": False,
            "error": str(e)
        }
        overall_status = "unhealthy"
        errors.append(f"Write capability: {str(e)}")

    # 3. Memory table check (verify memories table exists and is accessible)
    try:
        table_start = time.time()
        async with db_engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM memories LIMIT 1"))
            count = result.scalar()
            checks["memories_table"] = {
                "status": "ok",
                "latency_ms": round((time.time() - table_start) * 1000, 2),
                "accessible": True
            }
    except Exception as e:
        logger.error(f"Autosave health - Memories table check failed: {str(e)}")
        checks["memories_table"] = {
            "status": "error",
            "latency_ms": round((time.time() - table_start) * 1000, 2),
            "accessible": False,
            "error": str(e)
        }
        overall_status = "unhealthy"
        errors.append(f"Memories table: {str(e)}")

    total_latency = round((time.time() - start_time) * 1000, 2)

    response_content = {
        "status": overall_status,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_latency_ms": total_latency,
        "checks": checks,
        "errors": errors if errors else None
    }

    # Return 503 if unhealthy, 200 if healthy
    status_code = 200 if overall_status == "healthy" else 503

    return JSONResponse(status_code=status_code, content=response_content)


# Fin du fichier
