"""
Service de recherche de mémoires.
Implémente l'interface MemorySearchServiceProtocol.
"""

import logging
from typing import List, Dict, Any, Optional
import json

from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol, MemorySearchServiceProtocol
from models.memory_models import Memory

# Configuration du logger
logger = logging.getLogger(__name__)

class MemorySearchService(MemorySearchServiceProtocol):
    """
    Implémentation du service de recherche de mémoires.
    """
    
    def __init__(
        self,
        event_repository: EventRepositoryProtocol,
        memory_repository: MemoryRepositoryProtocol,
        embedding_service: EmbeddingServiceProtocol
    ):
        """
        Initialise le service de recherche de mémoires.
        
        Args:
            event_repository: Le repository d'événements
            memory_repository: Le repository de mémoires
            embedding_service: Le service d'embeddings
        """
        self.event_repository = event_repository
        self.memory_repository = memory_repository
        self.embedding_service = embedding_service
        logger.info("Initialisation du service de recherche de mémoires")
    
    async def search_by_content(self, query: str, limit: int = 5) -> List[Memory]:
        """
        Recherche des mémoires par leur contenu textuel.
        
        Args:
            query: Le texte à rechercher
            limit: Le nombre maximum de résultats à retourner
            
        Returns:
            Une liste de mémoires correspondant à la recherche
        """
        try:
            logger.info(f"Recherche de mémoires par contenu: '{query}'")
            # Ici, on pourrait implémenter une recherche full-text
            # Pour simplifier, on utilise une recherche basée sur les embeddings
            return await self.search_by_similarity(query, limit)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par contenu: {str(e)}")
            return []
    
    async def search_by_metadata(self, metadata_filter: Dict[str, Any], limit: int = 10) -> List[Memory]:
        """
        Recherche des mémoires par leurs métadonnées.
        
        Args:
            metadata_filter: Les critères de filtrage sur les métadonnées
            limit: Le nombre maximum de résultats à retourner
            
        Returns:
            Une liste de mémoires correspondant aux critères
        """
        try:
            logger.info(f"Recherche de mémoires par métadonnées: {json.dumps(metadata_filter)}")
            # Délégation au repository de mémoires
            memories = await self.memory_repository.list_memories(
                metadata_filter=metadata_filter,
                limit=limit
            )
            return memories
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par métadonnées: {str(e)}")
            return []
    
    async def search_by_similarity(self, query: str, limit: int = 5) -> List[Memory]:
        """
        Recherche des mémoires par similarité sémantique.
        
        Args:
            query: Le texte de référence pour la recherche
            limit: Le nombre maximum de résultats à retourner
            
        Returns:
            Une liste de mémoires triées par similarité
        """
        try:
            logger.info(f"Recherche de mémoires par similarité: '{query}'")
            
            # Génération de l'embedding pour la requête
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            # Recherche d'événements similaires
            similar_events = await self.event_repository.search_by_embedding(
                embedding=query_embedding,
                limit=limit
            )
            
            # Conversion des événements en mémoires
            # Dans une implémentation réelle, on utiliserait une méthode plus sophistiquée
            # ou on rechercherait directement dans les mémoires
            memories = []
            for event in similar_events:
                # Création d'une mémoire à partir de l'événement
                memory = Memory(
                    id=str(event.id),  # Utilisation de l'ID de l'événement pour simplifier
                    content=event.content,
                    metadata=event.metadata,
                    timestamp=event.timestamp
                )
                memories.append(memory)
            
            return memories
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par similarité: {str(e)}")
            return [] 