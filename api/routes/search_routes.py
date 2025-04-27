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
from db.repositories.event_repository import EventRepository, EventModel
# Importer la dépendance pour le repository
from dependencies import get_event_repository

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
        description="Filtre JSON stringifié sur les métadonnées (ex: {'key': 'value'}).",
        examples=['{"source": "test"}']
    ),
    vector_query: Optional[str] = Query(
        None, 
        description="Vecteur de requête encodé en Base64.",
        examples=['WzAuMSwgMC4yLCAwLjNd'] # Exemple: base64 de [0.1, 0.2, 0.3]
    ),
    top_k: int = Query(
        10, 
        ge=1, 
        le=50, 
        description="Nombre de résultats similaires à viser avant filtrage."
    ),
    ts_start: Optional[datetime.datetime] = Query(
        None, 
        description="Timestamp de début ISO 8601 pour le filtre temporel."
    ),
    ts_end: Optional[datetime.datetime] = Query(
        None, 
        description="Timestamp de fin ISO 8601 pour le filtre temporel."
    ),
    limit: int = Query(50, ge=1, le=100, description="Nombre maximum de résultats finaux."),
    offset: int = Query(0, ge=0, description="Offset pour la pagination."),
    
    repository: EventRepository = Depends(get_event_repository)
):
    """Recherche multi-critères d'événements (v1).
    
    Supporte la recherche par similarité vectorielle (via `vector_query` en Base64),
    le filtrage par métadonnées (via `filter_metadata` JSON stringifié),
    le filtrage temporel (`ts_start`, `ts_end`) et la pagination (`limit`, `offset`).
    Utilise une recherche hybride si `vector_query` et des filtres sont fournis.
    """
    start_time = time.time() 
    events = []
    # total_hits = 0 # Le repository ne le retourne pas encore

    parsed_vector: Optional[List[float]] = None
    parsed_metadata: Optional[Dict[str, Any]] = None

    # --- Parsing et Validation des Paramètres --- 
    try:
        # 1. Parser vector_query (Base64 -> List[float])
        if vector_query:
            try:
                import base64
                vector_bytes = base64.b64decode(vector_query)
                vector_str = vector_bytes.decode('utf-8')
                parsed_vector = json.loads(vector_str)
                if not isinstance(parsed_vector, list) or not all(isinstance(x, (int, float)) for x in parsed_vector):
                    raise ValueError("Le vecteur décodé n'est pas une liste de nombres.")
                # Optionnel: Vérifier la dimension du vecteur si nécessaire (ex: 1536)
                # expected_dimension = 1536
                # if len(parsed_vector) != expected_dimension:
                #     raise ValueError(f"La dimension du vecteur ({len(parsed_vector)}) ne correspond pas à la dimension attendue ({expected_dimension}).")
            except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
                logger.warn("search_events_invalid_vector", query=vector_query, error=str(e))
                # Ajout d'un log explicite avant de lever l'exception
                logger.error("Raising 422 due to invalid vector_query format", error=str(e))
                raise HTTPException(status_code=422, detail=f"Paramètre 'vector_query' invalide: {e}")

        # 2. Parser filter_metadata (JSON String -> Dict)
        if filter_metadata:
            try:
                parsed_metadata = json.loads(filter_metadata)
                if not isinstance(parsed_metadata, dict):
                    raise ValueError("filter_metadata doit être un objet JSON (dict).")
            except json.JSONDecodeError:
                logger.warn("search_events_invalid_json_filter", filter=filter_metadata)
                raise HTTPException(status_code=422, detail="Le paramètre 'filter_metadata' contient du JSON invalide.")
            except ValueError as e: # Catch le cas où ce n'est pas un dict
                logger.warn("search_events_invalid_filter_type", filter=filter_metadata, error=str(e))
                raise HTTPException(status_code=422, detail=str(e))

        # 3. Validation de base (au moins un critère ?)
        # Si ni vecteur ni metadata, que faire ? Retourner une erreur ou les plus récents?
        # Pour l'instant, le repo gère ce cas (retourne les plus récents par défaut)
        # if not parsed_vector and not parsed_metadata and not ts_start and not ts_end:
        #     raise HTTPException(status_code=400, detail="Au moins un critère de recherche (vector, metadata, ts) doit être fourni.")

    except HTTPException: # Relancer les erreurs HTTP déjà formatées
        raise
    except Exception as e: # Catch générique pour erreurs de parsing inattendues
        logger.error("search_events_parsing_error", error=str(e))
        raise HTTPException(status_code=500, detail="Erreur interne lors du parsing des paramètres de recherche.")

    # --- Appel au Repository --- 
    try:
        logger.info(
            "search_events_calling_repo", 
            has_vector=bool(parsed_vector), 
            has_metadata=bool(parsed_metadata),
            top_k=top_k, 
            ts_start=ts_start, 
            ts_end=ts_end, 
            limit=limit, 
            offset=offset
        )
        events = await repository.search_vector(
            vector=parsed_vector,
            top_k=top_k,
            metadata=parsed_metadata,
            ts_start=ts_start,
            ts_end=ts_end,
            limit=limit,
            offset=offset
        )
        logger.info("search_events_repo_results", count=len(events))
        
    except (ConnectionError, RuntimeError) as repo_err: # Erreurs relancées par le repo
        logger.error("search_events_repository_error", error=str(repo_err), exc_info=True)
        # Ne pas retourner l'erreur brute en production
        raise HTTPException(status_code=500, detail="Erreur lors de l'exécution de la recherche.")
    except Exception as e: # Autres erreurs inattendues
        logger.error("search_events_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne inattendue lors de la recherche.")
        
    end_time = time.time()
    query_time_ms = round((end_time - start_time) * 1000, 2)
    
    # Construire l'objet meta
    search_meta = SearchMetadata(
        query_time_ms=query_time_ms,
        # total_hits=total_hits, # Non disponible pour l'instant
        limit=limit,
        offset=offset
    )
    
    return EventSearchResults(data=events, meta=search_meta)

# === L'ANCIEN CODE v0 A ÉTÉ SUPPRIMÉ DE CE FICHIER === 