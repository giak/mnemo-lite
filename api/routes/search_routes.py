"""
Routes pour la recherche de mémoires et d'événements.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import base64

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from models.event_models import EventModel
from interfaces.services import MemorySearchServiceProtocol, EmbeddingServiceProtocol
from dependencies import get_memory_search_service, get_embedding_service
from services.base import ServiceError

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


class SearchTextQuery(BaseModel):
    """Modèle pour une requête de recherche textuelle."""

    query: str
    limit: int = 10


class SearchResponseMeta(BaseModel):
    """Méta-informations pour les réponses de recherche."""

    limit: int
    offset: int
    total_hits: int


class SearchResponse(BaseModel):
    """Modèle pour une réponse de recherche."""

    data: List[EventModel]
    meta: SearchResponseMeta


# Nouvelle route principale qui supporte à la fois la recherche par métadonnées et la recherche vectorielle
@router.get("/", response_model=SearchResponse)
async def search(
    filter_metadata: Optional[str] = Query(
        None, description="Filtre JSON sur les métadonnées"
    ),
    vector_query: Optional[str] = Query(
        None, description="Requête textuelle pour recherche vectorielle"
    ),
    limit: int = Query(10, ge=1, le=100, description="Nombre maximum de résultats"),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination"),
    ts_start: Optional[str] = Query(
        None, description="Timestamp de début (format ISO)"
    ),
    ts_end: Optional[str] = Query(None, description="Timestamp de fin (format ISO)"),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
    memory_search_service: MemorySearchServiceProtocol = Depends(
        get_memory_search_service
    ),
    distance_threshold: float = Query(0.5, description="Seuil de distance pour la recherche vectorielle"),
):
    """
    Recherche hybride de mémoires (métadonnées + vectorielle)

    - **filter_metadata**: Filtre JSON sur les métadonnées
    - **vector_query**: Texte de requête pour recherche vectorielle
    - **limit**: Nombre maximum de résultats
    - **offset**: Décalage pour pagination
    - **ts_start**: Timestamp de début au format ISO
    - **ts_end**: Timestamp de fin au format ISO
    """
    # Traitement des timestamps
    ts_start_dt = None
    ts_end_dt = None

    try:
        if ts_start:
            ts_start_dt = datetime.fromisoformat(ts_start)
        if ts_end:
            ts_end_dt = datetime.fromisoformat(ts_end)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Format de date invalide. Utilisez le format ISO (YYYY-MM-DDTHH:MM:SS+00:00)",
        )

    # Traitement du filtre de métadonnées
    metadata_dict = {}
    if filter_metadata:
        try:
            metadata_dict = json.loads(filter_metadata)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Format JSON invalide pour le filtre de métadonnées",
            )

    # Traitement de la requête vectorielle
    embedding = None
    if vector_query:
        try:
            # Si c'est un texte (et non un vecteur JSON), utiliser le service d'embedding
            # pour générer le vecteur d'embedding
            if not vector_query.startswith("["):
                embedding = await embedding_service.generate_embedding(vector_query)
            else:
                # Si c'est un vecteur JSON, essayer de le parser
                try:
                    embedding = json.loads(vector_query)
                    if not isinstance(embedding, list) or not all(
                        isinstance(x, (int, float)) for x in embedding
                    ):
                        raise HTTPException(
                            status_code=422,
                            detail="Le vecteur de recherche doit être une liste de nombres",
                        )
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=422,
                        detail="Format JSON invalide pour le vecteur de recherche",
                    )
        except Exception as e:
            logger.error(
                f"Erreur lors du traitement de la requête vectorielle: {str(e)}"
            )
            raise HTTPException(
                status_code=422,
                detail=f"Erreur lors du traitement de la requête vectorielle: {str(e)}",
            )

    # Effectuer la recherche en utilisant le service approprié
    try:
        results, total_count = await memory_search_service.search_hybrid(
            query=vector_query if vector_query and not vector_query.startswith("[") else "",
            metadata_filter=metadata_dict,
            limit=limit,
            offset=offset,
            ts_start=ts_start_dt,
            ts_end=ts_end_dt,
            distance_threshold=distance_threshold
        )

        # Build response
        response_meta = SearchResponseMeta(
            limit=limit, offset=offset, total_hits=total_count
        )
        return SearchResponse(data=results, meta=response_meta)
    
    except ServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during search", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search.")


@router.post("/content", response_model=SearchResponse)
async def search_by_content(
    query: SearchTextQuery,
    search_service: MemorySearchServiceProtocol = Depends(get_memory_search_service),
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
        return SearchResponse(
            data=results,
            meta=SearchResponseMeta(
                limit=query.limit, offset=0, total_hits=len(results)
            ),
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par contenu: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}",
        )


@router.post("/similarity", response_model=SearchResponse)
async def search_by_similarity(
    query: SearchTextQuery,
    search_service: MemorySearchServiceProtocol = Depends(get_memory_search_service),
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
        return SearchResponse(
            data=results,
            meta=SearchResponseMeta(
                limit=query.limit, offset=0, total_hits=len(results)
            ),
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par similarité: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}",
        )


@router.get("/metadata", response_model=SearchResponse)
async def search_by_metadata(
    metadata_filter: str = Query(..., description="Filtre JSON pour les métadonnées"),
    limit: int = Query(10, description="Nombre maximum de résultats"),
    search_service: MemorySearchServiceProtocol = Depends(get_memory_search_service),
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
        return SearchResponse(
            data=results,
            meta=SearchResponseMeta(limit=limit, offset=0, total_hits=len(results)),
        )
    except json.JSONDecodeError:
        logger.error(f"Format JSON invalide pour le filtre: {metadata_filter}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format JSON invalide pour le filtre de métadonnées",
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche par métadonnées: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}",
        )
