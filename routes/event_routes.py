import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body

from models.event_models import EventModel, EventCreate
from interfaces.repositories import EventRepositoryProtocol
from dependencies import get_event_repository

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

@router.post("/", response_model=EventModel, status_code=201)
async def create_event(
    event: EventCreate,
    repository: EventRepositoryProtocol = Depends(get_event_repository)
) -> EventModel:
    """
    Crée un nouvel événement.
    
    Args:
        event: Données de l'événement à créer
        repository: Repository injecté pour la gestion des événements
        
    Returns:
        L'événement créé
        
    Raises:
        HTTPException: En cas d'erreur lors de la création
    """
    try:
        return await repository.add(event)
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'événement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de l'événement: {str(e)}")

@router.get("/{event_id}", response_model=EventModel)
async def get_event(
    event_id: UUID,
    repository: EventRepositoryProtocol = Depends(get_event_repository)
) -> EventModel:
    """
    Récupère un événement par son ID.
    
    Args:
        event_id: ID de l'événement à récupérer
        repository: Repository injecté pour la gestion des événements
        
    Returns:
        L'événement demandé
        
    Raises:
        HTTPException: Si l'événement n'existe pas ou en cas d'erreur
    """
    try:
        event = await repository.get_by_id(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail=f"Événement avec ID {event_id} non trouvé")
        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'événement {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération de l'événement: {str(e)}")

@router.patch("/{event_id}/metadata", response_model=EventModel)
async def update_event_metadata(
    event_id: UUID,
    metadata: Dict[str, Any] = Body(...),
    repository: EventRepositoryProtocol = Depends(get_event_repository)
) -> EventModel:
    """
    Met à jour les métadonnées d'un événement existant.
    
    Args:
        event_id: ID de l'événement à mettre à jour
        metadata: Nouvelles métadonnées (fusionnées avec les existantes)
        repository: Repository injecté pour la gestion des événements
        
    Returns:
        L'événement mis à jour
        
    Raises:
        HTTPException: Si l'événement n'existe pas ou en cas d'erreur
    """
    try:
        updated_event = await repository.update_metadata(event_id, metadata)
        if updated_event is None:
            raise HTTPException(status_code=404, detail=f"Événement avec ID {event_id} non trouvé")
        return updated_event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des métadonnées de l'événement {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour des métadonnées: {str(e)}")

@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: UUID,
    repository: EventRepositoryProtocol = Depends(get_event_repository)
) -> None:
    """
    Supprime un événement existant.
    
    Args:
        event_id: ID de l'événement à supprimer
        repository: Repository injecté pour la gestion des événements
        
    Raises:
        HTTPException: Si l'événement n'existe pas ou en cas d'erreur
    """
    try:
        success = await repository.delete(event_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Événement avec ID {event_id} non trouvé")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'événement {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression de l'événement: {str(e)}")

@router.get("/filter/metadata", response_model=List[EventModel])
async def filter_events_by_metadata(
    metadata_filter: Dict[str, Any] = Body(...),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repository: EventRepositoryProtocol = Depends(get_event_repository)
) -> List[EventModel]:
    """
    Filtre les événements par métadonnées.
    
    Args:
        metadata_filter: Critères de filtrage (format: {"key": "value"})
        limit: Nombre maximum de résultats à retourner
        offset: Index de départ pour la pagination
        repository: Repository injecté pour la gestion des événements
        
    Returns:
        Liste des événements correspondant aux critères
        
    Raises:
        HTTPException: En cas d'erreur lors du filtrage
    """
    try:
        return await repository.filter_by_metadata(metadata_filter, limit, offset)
    except Exception as e:
        logger.error(f"Erreur lors du filtrage des événements par métadonnées: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du filtrage des événements: {str(e)}") 