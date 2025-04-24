import os
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
from pydantic import BaseModel, Field
import datetime
from typing import List, Optional, Dict, Any
import chromadb
from chromadb.config import Settings
import structlog

# Configuration du logger
logger = structlog.get_logger()

router = APIRouter()

# Récupération des variables d'environnement
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")

# Modèles de données
class MemoryBase(BaseModel):
    memory_type: str = Field(..., description="Type de mémoire (episodic, semantic, etc)")
    event_type: str = Field(..., description="Type d'événement (prompt, response, etc)")
    role_id: int = Field(..., description="ID du rôle")
    content: Dict[str, Any] = Field(..., description="Contenu de la mémoire")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Métadonnées")


class MemoryCreate(MemoryBase):
    expiration: Optional[datetime.datetime] = Field(None, description="Date d'expiration")


class Memory(MemoryBase):
    id: uuid.UUID = Field(..., description="ID unique")
    timestamp: datetime.datetime = Field(..., description="Date de création")
    expiration: Optional[datetime.datetime] = Field(None, description="Date d'expiration")


class MemoryUpdate(BaseModel):
    memory_type: Optional[str] = None
    event_type: Optional[str] = None
    role_id: Optional[int] = None
    content: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    expiration: Optional[datetime.datetime] = None


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
@router.post("/", response_model=Memory)
async def create_memory(memory: MemoryCreate):
    """
    Crée une nouvelle entrée de mémoire dans le système.
    """
    try:
        conn = await get_db_connection()
        
        # Génération d'un UUID pour la nouvelle mémoire
        memory_id = uuid.uuid4()
        
        # Insertion dans la base de données
        query = """
        INSERT INTO events 
        (id, timestamp, expiration, memory_type, event_type, role_id, content, metadata)
        VALUES ($1, NOW(), $2, $3, $4, $5, $6, $7)
        RETURNING id, timestamp, expiration, memory_type, event_type, role_id, content, metadata
        """
        
        record = await conn.fetchrow(
            query, 
            memory_id,
            memory.expiration,
            memory.memory_type,
            memory.event_type,
            memory.role_id,
            memory.content,
            memory.metadata
        )
        
        # Fermeture de la connexion
        await conn.close()
        
        # Construction de la réponse
        result = {
            "id": record["id"],
            "timestamp": record["timestamp"],
            "expiration": record["expiration"],
            "memory_type": record["memory_type"],
            "event_type": record["event_type"],
            "role_id": record["role_id"],
            "content": record["content"],
            "metadata": record["metadata"]
        }
        
        logger.info("memory_created", memory_id=str(memory_id), memory_type=memory.memory_type)
        return result
        
    except Exception as e:
        logger.error("create_memory_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error creating memory: {str(e)}")


@router.get("/{memory_id}", response_model=Memory)
async def get_memory(memory_id: uuid.UUID):
    """
    Récupère une mémoire spécifique par son ID.
    """
    try:
        conn = await get_db_connection()
        
        query = """
        SELECT id, timestamp, expiration, memory_type, event_type, role_id, content, metadata
        FROM events 
        WHERE id = $1
        """
        
        record = await conn.fetchrow(query, memory_id)
        
        await conn.close()
        
        if not record:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {
            "id": record["id"],
            "timestamp": record["timestamp"],
            "expiration": record["expiration"],
            "memory_type": record["memory_type"],
            "event_type": record["event_type"],
            "role_id": record["role_id"],
            "content": record["content"],
            "metadata": record["metadata"]
        }
        
    except asyncpg.exceptions.PostgresError as e:
        logger.error("get_memory_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error("get_memory_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error retrieving memory: {str(e)}")


@router.put("/{memory_id}", response_model=Memory)
async def update_memory(memory_id: uuid.UUID, memory: MemoryUpdate):
    """
    Met à jour une mémoire existante.
    """
    try:
        conn = await get_db_connection()
        
        # Vérifier si la mémoire existe
        check_query = "SELECT id FROM events WHERE id = $1"
        exists = await conn.fetchval(check_query, memory_id)
        
        if not exists:
            await conn.close()
            raise HTTPException(status_code=404, detail="Memory not found")
        
        # Construire la requête de mise à jour dynamiquement
        update_fields = []
        update_values = [memory_id]  # Premier paramètre est l'ID
        param_index = 2  # Démarre à 2 car $1 est utilisé pour l'ID
        
        update_dict = memory.dict(exclude_unset=True)
        
        for field, value in update_dict.items():
            if value is not None:
                update_fields.append(f"{field} = ${param_index}")
                update_values.append(value)
                param_index += 1
        
        if not update_fields:
            await conn.close()
            return await get_memory(memory_id)
        
        # Construire et exécuter la requête
        update_query = f"""
        UPDATE events 
        SET {', '.join(update_fields)}
        WHERE id = $1
        RETURNING id, timestamp, expiration, memory_type, event_type, role_id, content, metadata
        """
        
        updated = await conn.fetchrow(update_query, *update_values)
        await conn.close()
        
        logger.info("memory_updated", memory_id=str(memory_id))
        
        return {
            "id": updated["id"],
            "timestamp": updated["timestamp"],
            "expiration": updated["expiration"],
            "memory_type": updated["memory_type"],
            "event_type": updated["event_type"],
            "role_id": updated["role_id"],
            "content": updated["content"],
            "metadata": updated["metadata"]
        }
        
    except Exception as e:
        logger.error("update_memory_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error updating memory: {str(e)}")


@router.delete("/{memory_id}")
async def delete_memory(memory_id: uuid.UUID):
    """
    Supprime une mémoire par son ID.
    """
    try:
        conn = await get_db_connection()
        
        # Vérifier si la mémoire existe
        check_query = "SELECT id FROM events WHERE id = $1"
        exists = await conn.fetchval(check_query, memory_id)
        
        if not exists:
            await conn.close()
            raise HTTPException(status_code=404, detail="Memory not found")
        
        # Supprimer la mémoire
        delete_query = "DELETE FROM events WHERE id = $1"
        await conn.execute(delete_query, memory_id)
        
        await conn.close()
        
        logger.info("memory_deleted", memory_id=str(memory_id))
        
        return {"status": "success", "message": f"Memory {memory_id} deleted successfully"}
        
    except Exception as e:
        logger.error("delete_memory_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error deleting memory: {str(e)}")


@router.get("/", response_model=List[Memory])
async def list_memories(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    memory_type: Optional[str] = None,
    event_type: Optional[str] = None,
    role_id: Optional[int] = None,
    session_id: Optional[str] = None
):
    """
    Liste les mémoires avec filtrage et pagination.
    """
    try:
        conn = await get_db_connection()
        
        # Construction de la requête dynamique avec les filtres
        where_clauses = []
        query_params = []
        param_index = 1
        
        if memory_type:
            where_clauses.append(f"memory_type = ${param_index}")
            query_params.append(memory_type)
            param_index += 1
            
        if event_type:
            where_clauses.append(f"event_type = ${param_index}")
            query_params.append(event_type)
            param_index += 1
            
        if role_id:
            where_clauses.append(f"role_id = ${param_index}")
            query_params.append(role_id)
            param_index += 1
            
        if session_id:
            where_clauses.append(f"metadata->>'session_id' = ${param_index}")
            query_params.append(session_id)
            param_index += 1
        
        # Clause WHERE complète
        where_clause = " AND ".join(where_clauses)
        where_sql = f"WHERE {where_clause}" if where_clause else ""
        
        # Requête finale avec pagination
        query = f"""
        SELECT id, timestamp, expiration, memory_type, event_type, role_id, content, metadata
        FROM events 
        {where_sql}
        ORDER BY timestamp DESC
        LIMIT ${param_index} OFFSET ${param_index + 1}
        """
        
        query_params.extend([limit, offset])
        
        records = await conn.fetch(query, *query_params)
        await conn.close()
        
        # Construction de la réponse
        result = []
        for record in records:
            result.append({
                "id": record["id"],
                "timestamp": record["timestamp"],
                "expiration": record["expiration"],
                "memory_type": record["memory_type"],
                "event_type": record["event_type"],
                "role_id": record["role_id"],
                "content": record["content"],
                "metadata": record["metadata"]
            })
        
        return result
        
    except Exception as e:
        logger.error("list_memories_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error listing memories: {str(e)}") 