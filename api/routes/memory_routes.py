"""
Routes pour la gestion des mémoires.
"""
import logging
from typing import List, Optional, Dict, Any, Union, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body

from models.memory_models import Memory, MemoryCreate, MemoryUpdate
from interfaces.repositories import MemoryRepositoryProtocol
from dependencies import get_memory_repository

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["memories"])

@router.post("/", response_model=Memory, status_code=201)
async def create_memory(
    memory: MemoryCreate,
    repo: Annotated[MemoryRepositoryProtocol, Depends(get_memory_repository)]
) -> Memory:
    """
    Crée une nouvelle mémoire.
    
    Args:
        memory: Données de la mémoire à créer
        repo: Repository injecté pour la gestion des mémoires
        
    Returns:
        La mémoire créée
        
    Raises:
        HTTPException: En cas d'erreur lors de la création
    """
    try:
        created_memory = await repo.add(memory)
        return created_memory
    except Exception as e:
        logger.error(f"Erreur lors de la création de la mémoire: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la mémoire: {str(e)}")


@router.get("/{memory_id}", response_model=Memory)
async def get_memory(
    memory_id: UUID,
    repo: Annotated[MemoryRepositoryProtocol, Depends(get_memory_repository)]
) -> Memory:
    """
    Récupère une mémoire par son ID.
    
    Args:
        memory_id: ID de la mémoire à récupérer
        repo: Repository injecté pour la gestion des mémoires
        
    Returns:
        La mémoire demandée
        
    Raises:
        HTTPException: Si la mémoire n'existe pas ou en cas d'erreur
    """
    try:
        memory = await repo.get_by_id(memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail=f"Mémoire avec ID {memory_id} non trouvée")
        return memory
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la mémoire {memory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération de la mémoire: {str(e)}")


@router.put("/{memory_id}", response_model=Memory)
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    repo: Annotated[MemoryRepositoryProtocol, Depends(get_memory_repository)]
) -> Memory:
    """
    Met à jour une mémoire existante.
    
    Args:
        memory_id: ID de la mémoire à mettre à jour
        memory_update: Données de mise à jour
        repo: Repository injecté pour la gestion des mémoires
        
    Returns:
        La mémoire mise à jour
        
    Raises:
        HTTPException: Si la mémoire n'existe pas ou en cas d'erreur
    """
    try:
        updated_memory = await repo.update(memory_id, memory_update)
        if updated_memory is None:
            raise HTTPException(status_code=404, detail=f"Mémoire avec ID {memory_id} non trouvée")
        return updated_memory
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la mémoire {memory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour de la mémoire: {str(e)}")


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: UUID,
    repo: Annotated[MemoryRepositoryProtocol, Depends(get_memory_repository)]
) -> None:
    """
    Supprime une mémoire existante.
    
    Args:
        memory_id: ID de la mémoire à supprimer
        repo: Repository injecté pour la gestion des mémoires
        
    Raises:
        HTTPException: Si la mémoire n'existe pas ou en cas d'erreur
    """
    try:
        result = await repo.delete(memory_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Mémoire avec ID {memory_id} non trouvée")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la mémoire {memory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression de la mémoire: {str(e)}")


@router.get("/", response_model=List[Memory])
async def list_memories(
    repo: Annotated[MemoryRepositoryProtocol, Depends(get_memory_repository)],
    limit: int = Query(10, ge=1, le=100, description="Nombre maximum de résultats à retourner"),
    offset: int = Query(0, ge=0, description="Index de départ pour la pagination"),
    memory_type: Optional[str] = Query(None, description="Type de mémoire à filtrer"),
    event_type: Optional[str] = Query(None, description="Type d'événement associé"),
    role_id: Optional[int] = Query(None, description="ID du rôle associé"),
    session_id: Optional[str] = Query(None, description="ID de session associé")
) -> List[Memory]:
    """
    Liste les mémoires avec filtrage et pagination.
    
    Args:
        repo: Repository injecté pour la gestion des mémoires
        limit: Nombre maximum de résultats à retourner
        offset: Index de départ pour la pagination
        memory_type: Type de mémoire à filtrer
        event_type: Type d'événement associé
        role_id: ID du rôle associé
        session_id: ID de session associé
        
    Returns:
        Liste des mémoires correspondant aux critères
        
    Raises:
        HTTPException: En cas d'erreur lors de la récupération
    """
    try:
        # Construire les filtres de métadonnées
        metadata_filter = {}
        if memory_type:
            metadata_filter["memory_type"] = memory_type
        if event_type:
            metadata_filter["event_type"] = event_type
        if role_id:
            metadata_filter["role_id"] = role_id
        if session_id:
            metadata_filter["session_id"] = session_id
            
        memories, total_count = await repo.list_memories(
            limit=limit,
            offset=offset,
            memory_type=memory_type,
            event_type=event_type,
            role_id=role_id,
            session_id=session_id
        )
        return memories
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des mémoires: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des mémoires: {str(e)}") 