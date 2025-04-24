import os
import httpx
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
import json

# Configuration du logger
logger = structlog.get_logger()

# Variables d'environnement
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def get_embedding_openai(text):
    """
    Génère un embedding en utilisant l'API OpenAI.
    """
    if not OPENAI_API_KEY:
        logger.warning("openai_api_key_missing", environment=ENVIRONMENT)
        # En développement, générer un embedding aléatoire
        if ENVIRONMENT == "development":
            return np.random.rand(EMBEDDING_DIMENSION).tolist()
        else:
            raise ValueError("OpenAI API key is required in production environment")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        payload = {
            "input": text,
            "model": EMBEDDING_MODEL
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error("openai_api_error", 
                             status_code=response.status_code, 
                             response=response.text)
                raise Exception(f"OpenAI API error: {response.text}")
            
            result = response.json()
            embedding = result["data"][0]["embedding"]
            return embedding
            
    except Exception as e:
        logger.error("embedding_generation_error", error=str(e))
        raise e


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def get_embedding_local(text):
    """
    Génère un embedding en utilisant un modèle local (simulation).
    Dans une implémentation réelle, remplacez cette fonction par un appel
    à un modèle d'embedding local comme SentenceTransformers.
    """
    try:
        # Simuler le temps d'inférence
        import time
        import random
        time.sleep(random.uniform(0.05, 0.2))
        
        # Générer un embedding aléatoire de la dimension spécifiée
        return np.random.rand(EMBEDDING_DIMENSION).tolist()
        
    except Exception as e:
        logger.error("local_embedding_error", error=str(e))
        raise e


async def get_embedding(text):
    """
    Fonction principale pour obtenir un embedding.
    Utilise OpenAI en production et un modèle local (ou simulé) en développement.
    """
    if not text:
        logger.warning("empty_text_for_embedding")
        return np.zeros(EMBEDDING_DIMENSION).tolist()
        
    try:
        # Tronquer le texte si nécessaire (8k tokens max pour OpenAI)
        text = text[:32000]  # Approximation grossière
        
        if ENVIRONMENT == "production" and OPENAI_API_KEY:
            return await get_embedding_openai(text)
        else:
            return await get_embedding_local(text)
            
    except Exception as e:
        logger.error("get_embedding_error", error=str(e))
        # Fallback à un embedding aléatoire en cas d'erreur
        return np.random.rand(EMBEDDING_DIMENSION).tolist()


def cosine_similarity(embedding1, embedding2):
    """
    Calcule la similarité cosinus entre deux embeddings.
    """
    if not embedding1 or not embedding2:
        return 0.0
        
    try:
        a = np.array(embedding1)
        b = np.array(embedding2)
        
        # Normalisation
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        
        if a_norm == 0 or b_norm == 0:
            return 0.0
            
        # Similarité cosinus
        similarity = np.dot(a, b) / (a_norm * b_norm)
        return float(similarity)
        
    except Exception as e:
        logger.error("cosine_similarity_error", error=str(e))
        return 0.0 