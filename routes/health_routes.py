import os
import psutil
import time
from fastapi import APIRouter, Depends, HTTPException
import httpx
import asyncpg
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Gauge, Histogram
from fastapi.responses import Response, JSONResponse
import datetime
from sqlalchemy.ext.asyncio import AsyncEngine
from api.dependencies import get_db_engine

router = APIRouter(prefix="/health", tags=["health"])

# Métriques Prometheus
api_requests_total = Counter('api_requests_total', 'Total number of API requests', ['endpoint', 'method', 'status'])
api_request_duration = Histogram('api_request_duration_seconds', 'API request duration in seconds', ['endpoint'])
api_memory_usage = Gauge('api_memory_usage_bytes', 'API memory usage in bytes')

# Récupération des variables d'environnement PostgreSQL
# Idéalement, utiliser DATABASE_URL fourni par docker-compose
DATABASE_URL = os.getenv("DATABASE_URL")

async def check_postgres():
    """Vérifie la connexion à la base de données PostgreSQL."""
    if not DATABASE_URL:
        return {"status": "error", "message": "DATABASE_URL not set"}
    try:
        # Utilisation de DATABASE_URL pour la connexion
        conn = await asyncpg.connect(DATABASE_URL)
        version = await conn.fetchval("SELECT version();")
        await conn.close()
        return {"status": "ok", "version": version}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/")
async def health_check():
    """Endpoint de vérification de santé."""
    start_time = time.time()
    
    try:
        # Mise à jour des métriques - ne pas incrémenter ici, attendre de connaître le vrai statut
    api_memory_usage.set(psutil.Process().memory_info().rss)
    
        try:
    # Vérification de la santé de PostgreSQL
    pg_status = await check_postgres()
    
    # Systèmes critiques fonctionnels?
    is_healthy = pg_status["status"] == "ok"
    http_status_code = 200 if is_healthy else 503 # Service Unavailable si PG est down
    
    # Calcul de la durée
    duration = time.time() - start_time
    api_request_duration.labels(endpoint="/health").observe(duration)
    
            # Mise à jour du statut dans le compteur de requêtes - incrémenter avec le vrai code HTTP
        api_requests_total.labels(endpoint="/health", method="GET", status=str(http_status_code)).inc()

    response_content = {
        "status": "healthy" if is_healthy else "degraded",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "duration_ms": round(duration * 1000, 2),
        "services": {
            "postgres": pg_status,
        }
    }
    
    return JSONResponse(status_code=http_status_code, content=response_content)
            
        except Exception as e:
            # Gestion des exceptions lors de la vérification de PostgreSQL
            duration = time.time() - start_time
            # Mise à jour du compteur pour le code 500
            api_requests_total.labels(endpoint="/health", method="GET", status="500").inc()
            api_request_duration.labels(endpoint="/health").observe(duration)
            
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "duration_ms": round(duration * 1000, 2),
                    "detail": f"Error checking database: {str(e)}"
                }
            )
            
    except Exception as e:
        # Gestion des autres exceptions inattendues
        duration = time.time() - start_time
        # Mise à jour du compteur pour le code 500
        api_requests_total.labels(endpoint="/health", method="GET", status="500").inc()
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "duration_ms": round(duration * 1000, 2),
                "detail": f"Unexpected error in health check: {str(e)}"
            }
        )

@router.get("/metrics")
async def metrics():
    """Endpoint pour les métriques Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST) 

@router.get("/readiness")
async def readiness_check(db_engine: AsyncEngine = Depends(get_db_engine)):
    """
    Endpoint de vérification de disponibilité pour l'API.
    Vérifie que la base de données est accessible.
    """
    try:
        # Vérifier la connexion à la base de données
        async with db_engine.connect() as conn:
            # Exécuter une requête simple pour vérifier que la connexion fonctionne
            await conn.execute("SELECT 1")
        
        return {
            "status": "ok",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checks": {
                "database": True
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "checks": {
                    "database": False
                },
                "details": str(e)
            }
        ) 