import os
import psutil
import time
from fastapi import APIRouter, Depends, HTTPException
import httpx
import asyncpg
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Gauge, Histogram
from fastapi.responses import Response, JSONResponse
import datetime

router = APIRouter()

# Métriques Prometheus
api_requests_total = Counter('api_requests_total', 'Total number of API requests', ['endpoint', 'method', 'status'])
api_request_duration = Histogram('api_request_duration_seconds', 'API request duration in seconds', ['endpoint'])
api_memory_usage = Gauge('api_memory_usage_bytes', 'API memory usage in bytes')

# Récupération des variables d'environnement PostgreSQL
# Idéalement, utiliser DATABASE_URL fourni par docker-compose
DATABASE_URL = os.getenv("DATABASE_URL")

# Variables ChromaDB supprimées
# CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
# CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")


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

# Fonction check_chroma supprimée
# async def check_chroma(): ...


@router.get("/health")
async def health_check():
    """Endpoint de vérification de santé."""
    start_time = time.time()
    
    # Mise à jour des métriques
    api_requests_total.labels(endpoint="/health", method="GET", status="200").inc() # Statut 200 présumé initialement
    api_memory_usage.set(psutil.Process().memory_info().rss)
    
    # Vérification de la santé de PostgreSQL
    pg_status = await check_postgres()
    # Appel à check_chroma supprimé
    
    # Systèmes critiques fonctionnels?
    is_healthy = pg_status["status"] == "ok"
    http_status_code = 200 if is_healthy else 503 # Service Unavailable si PG est down
    
    # Calcul de la durée
    duration = time.time() - start_time
    api_request_duration.labels(endpoint="/health").observe(duration)
    
    # Mise à jour du statut dans le compteur de requêtes si erreur
    if not is_healthy:
        api_requests_total.labels(endpoint="/health", method="GET", status=str(http_status_code)).inc()
        api_requests_total.labels(endpoint="/health", method="GET", status="200").dec() # Décrémenter le 200 compté au début

    response_content = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "duration_ms": round(duration * 1000, 2),
        "services": {
            "postgres": pg_status,
            # Section chromadb supprimée
        }
    }
    
    return JSONResponse(status_code=http_status_code, content=response_content)


@router.get("/metrics")
async def metrics():
    """Endpoint pour les métriques Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Fin du fichier 