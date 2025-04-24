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

# Récupération des variables d'environnement
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")


async def check_postgres():
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        version = await conn.fetchval("SELECT version();")
        await conn.close()
        return {"status": "ok", "version": version}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def check_chroma():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{CHROMA_HOST}:{CHROMA_PORT}/api/v1/heartbeat")
            resp.raise_for_status()
            return {"status": "ok", "heartbeat": resp.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/health")
async def health_check():
    start_time = time.time()
    
    # Mise à jour des métriques
    api_requests_total.labels(endpoint="/health", method="GET", status="200").inc()
    api_memory_usage.set(psutil.Process().memory_info().rss)
    
    # Vérification de la santé de chaque dépendance
    pg_status = await check_postgres()
    chroma_status = await check_chroma()
    
    # Systèmes critiques fonctionnels?
    is_healthy = pg_status["status"] == "ok"
    
    # Calcul de la durée
    duration = time.time() - start_time
    api_request_duration.labels(endpoint="/health").observe(duration)
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "duration_ms": round(duration * 1000, 2),
        "services": {
            "postgres": pg_status,
            "chromadb": chroma_status
        }
    }


@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST) 