"""
Routes pour la recherche de mémoires et d'événements.

EPIC-59 : unification des POST de recherche sur la logique hybride unique
(`_search_memories`, la même fonction que GET /api/v1/memories/search et
l'outil MCP `search_memory`). Les routes orphelines mortes (POST /content,
POST /similarity, GET /metadata) ont été supprimées en 2026-08-07.
"""

import logging
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from models.event_models import EventModel
from interfaces.services import MemorySearchServiceProtocol, EmbeddingServiceProtocol
from dependencies import (
    get_memory_search_service,
    get_embedding_service,
    get_db_engine,
)
from services.base import ServiceError
from routes.memories_routes import MemorySearchResponse, _search_memories

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


class SearchResponseMeta(BaseModel):
    """Méta-informations pour les réponses de recherche."""

    limit: int
    offset: int
    total_hits: int


class SearchResponse(BaseModel):
    """Modèle pour une réponse de recherche."""

    data: List[EventModel]
    meta: SearchResponseMeta


class SearchRequest(BaseModel):
    """Modèle pour une requête de recherche POST (recherche de mémoires).

    EPIC-59 : contrat aligné sur la voie fiable `_search_memories`.
    `query` est requis ; `metadata`/`ts_start`/`ts_end` (ancien contrat events)
    ne sont plus supportés : utiliser GET /v1/search/?filter_metadata=... pour
    le filtrage par métadonnées d'événements.
    """

    query: str = Field(..., min_length=1, max_length=500, description="Texte de recherche (requis)")
    memory_type: Optional[str] = Field(
        None,
        description="Filtre par type de mémoire (note, decision, task, reference, conversation, investigation)",
    )
    tags: List[str] = Field(default_factory=list, description="Filtre par tags (logique ET)")
    limit: int = Field(default=10, ge=1, le=100, description="Nombre maximum de résultats")
    offset: int = Field(default=0, ge=0, description="Décalage pour la pagination")


# POST route unifiée (EPIC-59) : délègue à _search_memories, la même fonction
# que GET /api/v1/memories/search et l'outil MCP search_memory.
@router.post("/", response_model=MemorySearchResponse)
async def search_post(
    request: SearchRequest,
    engine: AsyncEngine = Depends(get_db_engine),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
) -> MemorySearchResponse:
    """
    POST endpoint unifié sur la logique hybride des mémoires (EPIC-59).

    Retourne le même format et les mêmes résultats que
    GET /api/v1/memories/search?query=... : un seul code path, plus de
    divergence POST/GET.
    """
    return await _search_memories(
        query=request.query,
        memory_type=request.memory_type,
        tags=request.tags,
        limit=request.limit,
        offset=request.offset,
        engine=engine,
        embedding_service=embedding_service,
    )


# GET route historique (événements) : recherche par métadonnées + vectorielle
# sur la table `events` (legacy nomic-768). Conservée pour les clients
# existants et le filtrage par métadonnées d'événements.
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
    distance_threshold: Optional[float] = Query(
        1.0,
        ge=0.0,
        le=2.0,
        description=(
            "Distance L2 threshold for vector search (cosine distance range: 0-2). "
            "Lower = stricter. Recommended values: "
            "0.8 (strict, high precision), "
            "1.0 (balanced, default), "
            "1.2 (relaxed, high recall). "
            "Set to None or 2.0 to return top-K without distance filtering."
        )
    ),
):
    """
    Recherche hybride d'événements (métadonnées + vectorielle)

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
        except HTTPException:
            raise  # Re-raise HTTPExceptions (e.g. validation errors) as-is
        except Exception as e:
            logger.error(
                f"Erreur lors du traitement de la requête vectorielle: {str(e)}"
            )
            raise HTTPException(
                status_code=422,
                detail="Request failed",
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
        raise HTTPException(status_code=500, detail="Request failed")
    except Exception as e:
        logger.exception("Unexpected error during search", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search.")
