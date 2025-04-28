"""
Package contenant les routes de l'API MnemoLite.
"""

from routes.memory_routes import router as memory_routes
from routes.event_routes import router as event_routes
from routes.search_routes import router as search_routes
# Importation du module health_routes (à créer s'il n'existe pas)
try:
    from routes.health_routes import router as health_routes
except ImportError:
    # Si le module n'existe pas encore, on définit un router vide
    from fastapi import APIRouter
    health_routes = APIRouter(prefix="/health", tags=["health"])
    health_routes.get("/")(lambda: {"status": "healthy"}) 