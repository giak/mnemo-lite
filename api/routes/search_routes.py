import os
import uuid
import asyncpg
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
import structlog
# import httpx # Plus nécessaire
import datetime
from pydantic import BaseModel, Field
import json
# from tenacity import retry, stop_after_attempt, wait_exponential # Plus nécessaire
import time

# Importer le repository Event et le modèle EventModel
from api.db.repositories.event_repository import EventRepository, EventModel
# Importer la dépendance pour le repository
from api.dependencies import get_event_repository

# Configuration du logger
logger = structlog.get_logger()

# --- Modèles Pydantic pour v1 (Réponse) --- 
class SearchMetadata(BaseModel):
    """Métadonnées de la recherche."""
    query_time_ms: Optional[float] = None
    total_hits: Optional[int] = None # Rendre optionnel si pas toujours calculé
    limit: Optional[int] = None
    offset: Optional[int] = None # Ou cursor si on implémente la pagination par curseur

class EventSearchResults(BaseModel):
    data: List[EventModel] # Renommé 'events' en 'data'
    meta: SearchMetadata # Ajout du champ meta

router = APIRouter() # Le préfixe /v1/search est défini dans main.py

# --- Route GET /v1/search --- 
@router.get("/", response_model=EventSearchResults)
async def search_events(
    filter_metadata: Optional[str] = Query(
        None, 
        description="Filtre JSON stringifié sur les métadonnées (ex: {\'key\': \'value\'})",
        examples=['{"source": "test"}']
    ),
    limit: int = Query(10, ge=1, le=100, description="Nombre maximum de résultats"),
    offset: int = Query(0, ge=0, description="Offset pour la pagination"),
    # Ajouter ici d'autres paramètres de recherche v1 plus tard
    
    repository: EventRepository = Depends(get_event_repository)
):
    """Recherche multi-critères d'événements (v1).
    
    Actuellement : supporte uniquement le filtrage par métadonnées via `filter_metadata`.
    """
    start_time = time.time() # Pour calculer la durée
    events = []
    total_hits = 0 # Initialiser total_hits

    if filter_metadata:
        try:
            metadata_criteria = json.loads(filter_metadata)
            if not isinstance(metadata_criteria, dict):
                raise ValueError("filter_metadata doit être un objet JSON (dict)")
            logger.info("search_events_metadata_filter", criteria=metadata_criteria)
            # TODO: Implémenter la pagination (limit/offset) dans le repository
            events = await repository.filter_by_metadata(metadata_criteria=metadata_criteria)
            # TODO: Obtenir le nombre total de hits (potentiellement via une autre requête COUNT)
            total_hits = len(events) # Approximation simple pour l'instant
            logger.info("search_events_metadata_results", count=len(events))
        except json.JSONDecodeError:
            logger.warn("search_events_invalid_json_filter", filter=filter_metadata)
            raise HTTPException(status_code=422, detail="Le paramètre 'filter_metadata' contient du JSON invalide.")
        except ValueError as e:
            logger.warn("search_events_invalid_filter_type", filter=filter_metadata, error=str(e))
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error("search_events_metadata_error", criteria=filter_metadata, error=str(e))
            # Ne pas retourner l'erreur brute en production
            error_detail = f"Erreur lors du filtrage par métadonnées: {type(e).__name__}"
            raise HTTPException(status_code=500, detail=error_detail)
    else:
        logger.info("search_events_no_criteria")
        # TODO: Implémenter le retour de tous les événements avec pagination?
        events = []
        total_hits = 0
        
    end_time = time.time()
    query_time_ms = round((end_time - start_time) * 1000, 2)
    
    # Construire l'objet meta
    search_meta = SearchMetadata(
        query_time_ms=query_time_ms,
        total_hits=total_hits,
        limit=limit,
        offset=offset
    )
    
    return EventSearchResults(data=events, meta=search_meta)

# === L'ANCIEN CODE v0 A ÉTÉ SUPPRIMÉ DE CE FICHIER === 