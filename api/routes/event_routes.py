import uuid
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
import structlog
from pydantic import BaseModel # Ajouter l'import pour BaseModel

# Importer le repository et les modèles Pydantic
# (Assumer qu'ils sont accessibles via le PYTHONPATH)
from api.db.repositories.event_repository import EventRepository, EventCreate, EventModel
# Importer la fonction de dépendance qu'on créera dans main.py (ou un fichier dédié)
from api.dependencies import get_event_repository # Chemin à confirmer/créer

logger = structlog.get_logger()

# --- Modèle pour la requête PATCH --- 
class MetadataUpdateRequest(BaseModel):
    metadata: Dict[str, Any]


router = APIRouter(
    prefix="/v1/events", # Déplacer le préfixe ici pour plus de clarté
    tags=["v1_Events"] # Mettre à jour le tag pour correspondre à main.py
)

@router.post("/", response_model=EventModel, status_code=201)
async def create_event(
    event_data: EventCreate, 
    repository: EventRepository = Depends(get_event_repository) # Injection de dépendance
):
    """Crée un nouvel événement dans la mémoire."""
    try:
        logger.info("create_event_request", content=event_data.content, metadata=event_data.metadata)
        created_event = await repository.add(event_data=event_data)
        logger.info("create_event_success", event_id=str(created_event.id))
        return created_event
    except Exception as e:
        # Convertir les données d'entrée en dict avant de logger
        input_data_dict = event_data.dict() if hasattr(event_data, 'dict') else str(event_data)
        logger.error("create_event_error", error=str(e), input_data=input_data_dict)
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create event: {str(e)}"
        )

@router.get("/{event_id}", response_model=EventModel)
async def get_event(
    event_id: uuid.UUID, # Récupère l'ID depuis le chemin
    repository: EventRepository = Depends(get_event_repository)
):
    """Récupère un événement spécifique par son ID."""
    logger.info("get_event_request", event_id=str(event_id))
    db_event = await repository.get_by_id(event_id=event_id)
    if db_event is None:
        logger.warn("get_event_not_found", event_id=str(event_id))
        raise HTTPException(status_code=404, detail="Event not found")
    logger.info("get_event_success", event_id=str(event_id))
    return db_event


@router.patch("/{event_id}", response_model=EventModel)
async def update_event_metadata(
    event_id: uuid.UUID,
    update_data: MetadataUpdateRequest,
    repository: EventRepository = Depends(get_event_repository)
):
    """Met à jour (fusionne) les métadonnées d'un événement spécifique."""
    logger.info("update_event_metadata_request", event_id=str(event_id), update_data=update_data.metadata)
    updated_event = await repository.update_metadata(
        event_id=event_id, 
        metadata_update=update_data.metadata
    )
    if updated_event is None:
        logger.warn("update_event_metadata_not_found", event_id=str(event_id))
        raise HTTPException(status_code=404, detail="Event not found")
    logger.info("update_event_metadata_success", event_id=str(event_id))
    return updated_event

@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    repository: EventRepository = Depends(get_event_repository)
):
    """Supprime un événement spécifique par son ID."""
    logger.info("delete_event_request", event_id=str(event_id))
    deleted = await repository.delete(event_id=event_id)
    if not deleted:
        logger.warn("delete_event_not_found", event_id=str(event_id))
        # Important: Lever une 404 si l'élément n'existait pas déjà
        raise HTTPException(status_code=404, detail="Event not found")
    
    logger.info("delete_event_success", event_id=str(event_id))
    # Si la suppression réussit, FastAPI retourne automatiquement
    # une réponse vide avec le status_code 204 (No Content)
    return None

# Ajouter ici plus tard les autres endpoints pour DELETE /events/{id} 