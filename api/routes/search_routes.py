import os
import uuid
import asyncpg
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
import structlog
import httpx
import datetime
from pydantic import BaseModel, Field
import json
from tenacity import retry, stop_after_attempt, wait_exponential

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

# Modèles pour la recherche
class SearchQuery(BaseModel):
    query: str = Field(..., description="Requête de recherche textuelle")
    limit: int = Field(10, ge=1, le=50, description="Nombre maximum de résultats")
    memory_type: Optional[str] = Field(None, description="Type de mémoire à filtrer")
    event_type: Optional[str] = Field(None, description="Type d'événement à filtrer")
    role_id: Optional[int] = Field(None, description="ID du rôle à filtrer")
    start_date: Optional[datetime.datetime] = Field(None, description="Date de début de recherche")
    end_date: Optional[datetime.datetime] = Field(None, description="Date de fin de recherche")


class SearchResult(BaseModel):
    id: uuid.UUID
    timestamp: datetime.datetime
    memory_type: str
    event_type: str
    role_id: int
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    similarity: float


# Fonctions helpers
async def get_db_connection():
    return await asyncpg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def get_embedding(text: str):
    """
    Génère un embedding pour le texte donné en utilisant un service externe.
    Cette fonction peut être remplacée par une implémentation locale.
    """
    try:
        # Ici, on pourrait appeler un service externe comme OpenAI
        # Pour l'instant, on simule un embedding
        
        # En production, utilisez quelque chose comme:
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         "https://api.openai.com/v1/embeddings",
        #         headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        #         json={"input": text, "model": "text-embedding-ada-002"}
        #     )
        #     return response.json()["data"][0]["embedding"]
        
        # Simulation d'un embedding aléatoire de dimension 1536
        import numpy as np
        embedding = np.random.rand(1536).tolist()
        return embedding
        
    except Exception as e:
        logger.error("embedding_generation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")


# Routes
@router.post("/semantic", response_model=List[SearchResult])
async def semantic_search(search_query: SearchQuery):
    """
    Effectue une recherche sémantique basée sur une requête textuelle.
    """
    try:
        # Générer l'embedding pour la requête
        embedding = await get_embedding(search_query.query)
        
        # Connexion à la base de données
        conn = await get_db_connection()
        
        # Appel à la fonction de recherche vectorielle
        query = """
        SELECT * FROM search_memories($1, $2, $3, $4, $5, $6, $7)
        """
        
        records = await conn.fetch(
            query, 
            embedding,
            search_query.limit,
            search_query.memory_type,
            search_query.event_type,
            search_query.role_id,
            search_query.start_date,
            search_query.end_date
        )
        
        await conn.close()
        
        # Construction des résultats
        results = []
        for record in records:
            results.append({
                "id": record["id"],
                "timestamp": record["timestamp"],
                "memory_type": record["memory_type"],
                "event_type": record["event_type"],
                "role_id": record["role_id"],
                "content": record["content"],
                "metadata": record["metadata"],
                "similarity": record["similarity"]
            })
        
        logger.info("semantic_search_completed", query=search_query.query, results_count=len(results))
        return results
        
    except Exception as e:
        logger.error("semantic_search_error", query=search_query.query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error during semantic search: {str(e)}")


@router.get("/related/{memory_id}", response_model=List[Dict[str, Any]])
async def get_related_memories(
    memory_id: uuid.UUID,
    relation_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50)
):
    """
    Récupère les mémoires liées à une mémoire spécifique.
    """
    try:
        conn = await get_db_connection()
        
        query = """
        SELECT * FROM get_related_events($1, $2, $3)
        """
        
        records = await conn.fetch(query, memory_id, relation_type, limit)
        await conn.close()
        
        results = []
        for record in records:
            results.append({
                "relation_id": record["id"],
                "source_id": record["source_id"],
                "target_id": record["target_id"],
                "relation_type": record["relation_type"],
                "target_timestamp": record["target_timestamp"],
                "target_memory_type": record["target_memory_type"],
                "target_event_type": record["target_event_type"],
                "target_role_id": record["target_role_id"],
                "target_content": record["target_content"]
            })
        
        return results
        
    except Exception as e:
        logger.error("get_related_memories_error", memory_id=str(memory_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error retrieving related memories: {str(e)}")


@router.get("/sessions", response_model=List[Dict[str, Any]])
async def get_recent_sessions(limit: int = Query(10, ge=1, le=50)):
    """
    Récupère la liste des sessions récentes.
    """
    try:
        conn = await get_db_connection()
        
        query = """
        SELECT * FROM recent_sessions LIMIT $1
        """
        
        records = await conn.fetch(query, limit)
        await conn.close()
        
        results = []
        for record in records:
            results.append({
                "session_id": record["session_id"],
                "started_at": record["started_at"],
                "last_activity": record["last_activity"],
                "event_count": record["event_count"]
            })
        
        return results
        
    except Exception as e:
        logger.error("get_recent_sessions_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error retrieving recent sessions: {str(e)}")


@router.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session_summary(session_id: str, limit: int = Query(100, ge=1, le=500)):
    """
    Récupère un résumé détaillé d'une session spécifique.
    """
    try:
        conn = await get_db_connection()
        
        query = """
        SELECT * FROM summarize_session($1, $2)
        """
        
        record = await conn.fetchrow(query, session_id, limit)
        await conn.close()
        
        if not record:
            raise HTTPException(status_code=404, detail="Session not found")
        
        result = {
            "session_id": record["session_id"],
            "started_at": record["started_at"],
            "last_activity": record["last_activity"],
            "event_count": record["event_count"],
            "recent_events": record["recent_events"]
        }
        
        return result
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("get_session_summary_error", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error retrieving session summary: {str(e)}")


@router.delete("/sessions/{session_id}")
async def forget_session(session_id: str):
    """
    Supprime toutes les mémoires associées à une session spécifique.
    """
    try:
        conn = await get_db_connection()
        
        query = """
        SELECT forget_session($1) as deleted_count
        """
        
        result = await conn.fetchval(query, session_id)
        await conn.close()
        
        return {
            "status": "success", 
            "message": f"Session {session_id} forgotten successfully",
            "deleted_memories_count": result
        }
        
    except Exception as e:
        logger.error("forget_session_error", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error forgetting session: {str(e)}") 