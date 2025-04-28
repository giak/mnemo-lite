"""
Service d'embedding pour la génération de représentations vectorielles de texte.
Ce module définit une interface abstraite et une implémentation concrète.
"""

import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Optional, Union

# Configuration du logger
logger = logging.getLogger(__name__)

class EmbeddingServiceInterface(ABC):
    """
    Interface abstraite pour les services d'embedding.
    Définit les méthodes que toute implémentation de service d'embedding doit fournir.
    """
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Génère un embedding vectoriel à partir d'un texte.
        
        Args:
            text: Le texte à transformer en vecteur
            
        Returns:
            Une liste de flottants représentant l'embedding
        """
        pass
    
    @abstractmethod
    async def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule la similarité entre deux textes en comparant leurs embeddings.
        
        Args:
            text1: Premier texte à comparer
            text2: Second texte à comparer
            
        Returns:
            Un score de similarité entre 0 et 1
        """
        pass


class SimpleEmbeddingService(EmbeddingServiceInterface):
    """
    Implémentation simple du service d'embedding utilisant un modèle basique.
    Pour un environnement de production, cette classe devrait être remplacée
    par une implémentation utilisant des modèles plus sophistiqués (OpenAI, Hugging Face, etc.)
    """
    
    def __init__(self, model_name: str = "simple-model", dimension: int = 384):
        """
        Initialise le service d'embedding.
        
        Args:
            model_name: Nom du modèle à utiliser (pour journalisation)
            dimension: Dimension des vecteurs d'embedding
        """
        self.model_name = model_name
        self.dimension = dimension
        logger.info(f"Initialisation du service d'embedding avec le modèle {model_name}")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Génère un embedding vectoriel à partir d'un texte.
        Cette implémentation simple utilise un hachage du texte pour créer un vecteur.
        
        Args:
            text: Le texte à transformer en vecteur
            
        Returns:
            Une liste de flottants représentant l'embedding
        """
        if not text or not text.strip():
            logger.warning("Tentative de génération d'embedding pour un texte vide")
            return [0.0] * self.dimension
        
        try:
            # Implémentation simple: utilisation d'un hachage du texte
            # Dans un environnement réel, utilisez un modèle d'embedding approprié
            text_hash = hash(text)
            np.random.seed(text_hash)
            
            # Génération d'un vecteur pseudo-aléatoire mais déterministe
            vector = np.random.normal(0, 1, self.dimension)
            
            # Normalisation du vecteur
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
                
            return vector.tolist()
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embedding: {str(e)}")
            raise ValueError(f"Impossible de générer l'embedding: {str(e)}")
    
    async def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule la similarité entre deux textes en utilisant la similarité cosinus.
        
        Args:
            text1: Premier texte à comparer
            text2: Second texte à comparer
            
        Returns:
            Un score de similarité entre 0 et 1
        """
        try:
            # Génération des embeddings pour les deux textes
            embedding1 = await self.generate_embedding(text1)
            embedding2 = await self.generate_embedding(text2)
            
            # Calcul de la similarité cosinus
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 > 0 and norm2 > 0:
                similarity = max(0.0, min(1.0, (dot_product / (norm1 * norm2) + 1) / 2))
            else:
                similarity = 0.0
                
            return float(similarity)
        except Exception as e:
            logger.error(f"Erreur lors du calcul de similarité: {str(e)}")
            raise ValueError(f"Impossible de calculer la similarité: {str(e)}") 