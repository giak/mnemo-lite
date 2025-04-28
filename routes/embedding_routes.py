"""
Routes pour les opérations liées aux embeddings.
Ces routes démontrent l'utilisation de l'injection de dépendances pour les services.
"""
import logging
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from interfaces.services import EmbeddingServiceProtocol
from dependencies import get_embedding_service

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

# Modèles Pydantic pour les requêtes et réponses
class TextEmbeddingRequest(BaseModel):
    text: str

class TextEmbeddingResponse(BaseModel):
    text: str
    embedding: List[float]
    dimension: int

class SimilarityRequest(BaseModel):
    text1: str
    text2: str

class SimilarityResponse(BaseModel):
    text1: str
    text2: str
    similarity: float
    embedding1: List[float]
    embedding2: List[float]

@router.post("/generate", response_model=TextEmbeddingResponse)
async def generate_embedding(
    request: TextEmbeddingRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service)
) -> TextEmbeddingResponse:
    """
    Génère un embedding à partir d'un texte.
    
    Args:
        request: Requête contenant le texte à transformer
        embedding_service: Service d'embeddings injecté
        
    Returns:
        L'embedding généré et les métadonnées associées
    """
    try:
        embedding = await embedding_service.generate_embedding(request.text)
        return TextEmbeddingResponse(
            text=request.text,
            embedding=embedding,
            dimension=len(embedding)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'embedding: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération de l'embedding: {str(e)}")

@router.post("/similarity", response_model=SimilarityResponse)
async def compute_similarity(
    request: SimilarityRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service)
) -> SimilarityResponse:
    """
    Calcule la similarité entre deux textes.
    
    Args:
        request: Requête contenant les deux textes à comparer
        embedding_service: Service d'embeddings injecté
        
    Returns:
        La similarité entre les deux textes et leurs embeddings
    """
    try:
        # Générer les embeddings pour les deux textes
        embedding1 = await embedding_service.generate_embedding(request.text1)
        embedding2 = await embedding_service.generate_embedding(request.text2)
        
        # Calculer la similarité entre les embeddings
        similarity = await embedding_service.compute_similarity(embedding1, embedding2)
        
        return SimilarityResponse(
            text1=request.text1,
            text2=request.text2,
            similarity=similarity,
            embedding1=embedding1,
            embedding2=embedding2
        )
    except Exception as e:
        logger.error(f"Erreur lors du calcul de la similarité: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul de la similarité: {str(e)}") 