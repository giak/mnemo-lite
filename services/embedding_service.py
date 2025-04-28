"""
Service de génération et manipulation d'embeddings.
Implémente l'interface EmbeddingServiceProtocol.
"""
import numpy as np
from typing import List, Optional
import logging

from interfaces.services import EmbeddingServiceProtocol

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service de génération et manipulation d'embeddings.
    Une implémentation concrète de EmbeddingServiceProtocol.
    """
    
    def __init__(self, model_name: str = "default", embedding_size: int = 384):
        """
        Initialise le service d'embeddings.
        
        Args:
            model_name: Nom du modèle à utiliser
            embedding_size: Taille des vecteurs d'embedding
        """
        self.model_name = model_name
        self.embedding_size = embedding_size
        self._model = None
        logger.info(f"EmbeddingService initialisé avec le modèle {model_name}")
    
    async def _load_model(self):
        """Charge le modèle d'embeddings si nécessaire."""
        if self._model is None:
            # Dans une implémentation réelle, on chargerait ici un modèle
            # comme SentenceTransformers ou un service externe
            logger.info(f"Chargement du modèle {self.model_name}")
            self._model = "MockModel"  # Placeholder
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Génère un embedding à partir d'un texte.
        
        Args:
            text: Le texte dont on veut générer l'embedding
            
        Returns:
            Le vecteur d'embedding du texte
        """
        await self._load_model()
        
        # Dans une implémentation réelle, on utiliserait le modèle pour générer
        # un véritable embedding. Ici, on génère un vecteur aléatoire.
        logger.debug(f"Génération d'un embedding pour un texte de {len(text)} caractères")
        
        # Utilisation d'une seed basée sur le texte pour simuler la cohérence
        # (mêmes entrées → mêmes sorties)
        text_hash = sum(ord(c) for c in text)
        np.random.seed(text_hash)
        
        embedding = np.random.normal(0, 1, self.embedding_size).tolist()
        embedding = self._normalize(embedding)
        
        return embedding
    
    async def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calcule la similarité entre deux embeddings (similarité cosinus).
        
        Args:
            embedding1: Premier vecteur d'embedding
            embedding2: Second vecteur d'embedding
            
        Returns:
            Valeur de similarité entre 0 et 1
        """
        # Vérifier que les embeddings ont la même dimension
        if len(embedding1) != len(embedding2):
            raise ValueError(
                f"Les embeddings doivent avoir la même dimension "
                f"({len(embedding1)} != {len(embedding2)})"
            )
        
        # Calculer la similarité cosinus
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5
        
        # Éviter la division par zéro
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Limiter la similarité entre 0 et 1
        return max(0.0, min(1.0, similarity))
    
    def _normalize(self, embedding: List[float]) -> List[float]:
        """Normalise un vecteur d'embedding (norme L2)."""
        norm = sum(x * x for x in embedding) ** 0.5
        if norm == 0:
            return embedding
        return [x / norm for x in embedding] 