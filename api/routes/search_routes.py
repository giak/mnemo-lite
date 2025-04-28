"""
Routes pour la recherche de mémoires et d'événements.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from models.memory_models import Memory
from models.event_models import EventModel
from interfaces.services import MemorySearchServiceProtocol, EmbeddingServiceProtocol
from dependencies import get_memory_search_service, get_embedding_service

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

class SearchTextQuery(BaseModel):
    """Modèle pour une requête de recherche textuelle."""
    query: str
    limit: int = 10

class SearchResponse(BaseModel):
    """Modèle pour une réponse de recherche."""
    results: List[Memory]
    query: str

@router.post("/content", response_model=SearchResponse)
async def search_by_content(
    query: SearchTextQuery,
    search_service: MemorySearchServiceProtocol = Depends(get_memory_search_service)
) -> SearchResponse:
    """
    Recherche des mémoires par leur contenu textuel.
    
    Args:
        query: La requête de recherche
        search_service: Le service de recherche injecté
        
    Returns:
        Les résultats de la recherche
    """
    try:
        logger.info(f"Recherche par contenu: '{query.query}'")
        results = await search_service.search_by_content(query.query, query.limit)
        return SearchResponse(results=results, query=query.query)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par contenu: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@router.post("/similarity", response_model=SearchResponse)
async def search_by_similarity(
    query: SearchTextQuery,
    search_service: MemorySearchServiceProtocol = Depends(get_memory_search_service)
) -> SearchResponse:
    """
    Recherche des mémoires par similarité sémantique.
    
    Args:
        query: La requête de recherche
        search_service: Le service de recherche injecté
        
    Returns:
        Les résultats de la recherche
    """
    try:
        logger.info(f"Recherche par similarité: '{query.query}'")
        results = await search_service.search_by_similarity(query.query, query.limit)
        return SearchResponse(results=results, query=query.query)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par similarité: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@router.get("/metadata", response_model=SearchResponse)
async def search_by_metadata(
    metadata_filter: str = Query(..., description="Filtre JSON pour les métadonnées"),
    limit: int = Query(10, description="Nombre maximum de résultats"),
    search_service: MemorySearchServiceProtocol = Depends(get_memory_search_service)
) -> SearchResponse:
    """
    Recherche des mémoires par leurs métadonnées.
    
    Args:
        metadata_filter: Filtre JSON pour les métadonnées
        limit: Nombre maximum de résultats
        search_service: Le service de recherche injecté
        
    Returns:
        Les résultats de la recherche
    """
    try:
        # Conversion du filtre JSON en dictionnaire
        metadata_filter_dict = json.loads(metadata_filter)
        logger.info(f"Recherche par métadonnées: {metadata_filter}")
        results = await search_service.search_by_metadata(metadata_filter_dict, limit)
        return SearchResponse(results=results, query=metadata_filter)
    except json.JSONDecodeError:
        logger.error(f"Format JSON invalide pour le filtre: {metadata_filter}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format JSON invalide pour le filtre de métadonnées"
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par métadonnées: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        ) 