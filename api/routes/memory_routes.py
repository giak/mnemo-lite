import os
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
import datetime
from typing import List, Optional, Dict, Any
import structlog

# Importer le repository et la dépendance
from db.repositories.memory_repository import MemoryRepository
from dependencies import get_memory_repository
# Importer les modèles depuis le nouveau fichier
from models.memory_models import Memory, MemoryCreate, MemoryUpdate, MemoryBase

# Configuration du logger
logger = structlog.get_logger()

router = APIRouter()

# Récupération des variables d'environnement PostgreSQL
# Utilisation de DATABASE_URL est préférée, mais garder ces variables
# pour la compatibilité avec le code existant get_db_connection pourrait être utile temporairement.
# Idéalement, get_db_connection devrait utiliser DATABASE_URL.
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")

# Variables ChromaDB supprimées
# CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
# CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")

# Fonctions helpers
async def get_db_connection():
    return await asyncpg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB
    )


# Routes
@router.post("/", response_model=Memory, status_code=201)
async def create_memory(
    memory: MemoryCreate, 
    repo: MemoryRepository = Depends(get_memory_repository)
):
    """
    Crée une nouvelle entrée de mémoire dans le système.
    """
    try:
        created_memory = await repo.add(memory)
        return created_memory
    except (ConnectionError, RuntimeError) as e:
        logger.error("create_memory_error", error=str(e))
        # Renvoyer une erreur 500 générique
        raise HTTPException(status_code=500, detail="Failed to create memory.")
    except Exception as e: # Catch unexpected errors
        logger.error("create_memory_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/{memory_id}", response_model=Memory)
async def get_memory(
    memory_id: uuid.UUID = Path(...),
    repo: MemoryRepository = Depends(get_memory_repository)
):
    """
    Récupère une mémoire spécifique par son ID.
    """
    try:
        memory = await repo.get_by_id(memory_id)
        if memory is None:
            logger.info("get_memory_not_found", memory_id=str(memory_id))
            raise HTTPException(status_code=404, detail="Memory not found")
        return memory
    except Exception as e: # Catch potential errors from repo (though it should return None)
        logger.error("get_memory_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail="Error retrieving memory.")


@router.put("/{memory_id}", response_model=Memory)
async def update_memory(
    memory_id: uuid.UUID = Path(...),
    memory_update: MemoryUpdate = Body(...),
    repo: MemoryRepository = Depends(get_memory_repository)
):
    """
    Met à jour une mémoire existante.
    """
    try:
        updated_memory = await repo.update(memory_id, memory_update)
        if updated_memory is None:
            logger.info("update_memory_not_found", memory_id=str(memory_id))
            raise HTTPException(status_code=404, detail="Memory not found for update")
        return updated_memory
    except ValueError as ve: # Catch mapping errors from repo.update
        logger.error("update_memory_mapping_error", memory_id=str(memory_id), error=str(ve))
        raise HTTPException(status_code=500, detail=f"Error processing updated memory: {ve}")
    except (ConnectionError, RuntimeError) as e:
        logger.error("update_memory_db_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update memory.")
    except Exception as e: # Catch unexpected errors
        logger.error("update_memory_unexpected_error", memory_id=str(memory_id), error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.delete("/{memory_id}", status_code=204) # Use 204 No Content for successful delete
async def delete_memory(
    memory_id: uuid.UUID = Path(...),
    repo: MemoryRepository = Depends(get_memory_repository)
):
    """
    Supprime une mémoire par son ID.
    """
    try:
        deleted = await repo.delete(memory_id)
        if not deleted:
            logger.info("delete_memory_not_found", memory_id=str(memory_id))
            raise HTTPException(status_code=404, detail="Memory not found for deletion")
        # No content to return on successful delete
        return None 
    except (ConnectionError, RuntimeError) as e:
        logger.error("delete_memory_db_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete memory.")
    except Exception as e: # Catch unexpected errors
        logger.error("delete_memory_unexpected_error", memory_id=str(memory_id), error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/", response_model=List[Memory])
async def list_memories(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    memory_type: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    role_id: Optional[int] = Query(None),
    session_id: Optional[str] = Query(None),
    repo: MemoryRepository = Depends(get_memory_repository)
):
    """
    Liste les mémoires avec filtrage et pagination.
    """
    try:
        memories = await repo.list_memories(
            limit=limit,
            offset=offset,
            memory_type=memory_type,
            event_type=event_type,
            role_id=role_id,
            session_id=session_id
        )
        return memories
    except (ConnectionError, RuntimeError) as e:
        logger.error("list_memories_db_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list memories.")
    except Exception as e: # Catch unexpected errors
        logger.error("list_memories_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") 