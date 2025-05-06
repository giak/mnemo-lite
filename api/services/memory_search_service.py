"""
Service de recherche de mémoires.
Implémente l'interface MemorySearchServiceProtocol.
"""

import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import json
from datetime import datetime
import uuid
import inspect
import traceback
import sys

from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol, MemorySearchServiceProtocol
from models.memory_models import Memory
from models.event_models import EventModel
from db.repositories.base import RepositoryError
from .base import ServiceError

# Configuration du logger
logger = logging.getLogger(__name__)


class MemorySearchService(MemorySearchServiceProtocol):
    """
    Implémentation du service de recherche de mémoires.
    """

    # Constante pour la dimension attendue des vecteurs
    EXPECTED_EMBEDDING_DIM = 384  # Align with MiniLM

    def __init__(
        self,
        event_repository: EventRepositoryProtocol,
        memory_repository: MemoryRepositoryProtocol,
        embedding_service: EmbeddingServiceProtocol,
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
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialisation du service de recherche de mémoires")

    def _event_to_memory(self, event: EventModel) -> Memory:
        """
        Convertit un EventModel en un objet Memory.
        
        Args:
            event: L'événement à convertir
            
        Returns:
            L'objet Memory correspondant
        """
        metadata = event.metadata or {}
        return Memory(
            id=event.id,
            content=event.content,
            metadata=metadata,
            timestamp=event.timestamp,
            embedding=event.embedding,
            similarity_score=getattr(event, "similarity_score", None),
            memory_type=metadata.get("memory_type", "event"),
            event_type=metadata.get("event_type", "log"),
            role_id=metadata.get("role_id", 1),
            expiration=metadata.get("expiration")
        )

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

    async def search_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        limit: int = 10,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
    ) -> List[Memory]:
        """
        Recherche des mémoires par métadonnées.
        
        Args:
            metadata_filter: Dictionnaire de critères de métadonnées
            limit: Nombre maximum de résultats
            offset: Décalage pour la pagination
            ts_start: Timestamp de début pour filtrer par date
            ts_end: Timestamp de fin pour filtrer par date
            
        Returns:
            Liste de mémoires correspondant aux critères
        """
        try:
            self.logger.info(f"Recherche par métadonnées avec filtres: {metadata_filter}")
            
            # Appeler list_memories une seule fois avec gestion du résultat
            result = await self.memory_repository.list_memories(
                metadata_filter=metadata_filter,
                limit=limit,
                skip=offset,
                ts_start=ts_start,
                ts_end=ts_end
            )
            
            # Vérifier si le résultat est un tuple (nouvelle interface) ou une liste (ancienne interface)
            if isinstance(result, tuple) and len(result) == 2:
                memories, _ = result
            else:
                memories = result
            
            self.logger.info(f"Recherche par métadonnées: {len(memories)} résultats trouvés")
            return memories
            
        except Exception as e:
            self.logger.error(f"Erreur dans search_by_metadata: {str(e)}", exc_info=True)
            return []

    async def search_by_similarity(
        self,
        query: str,
        limit: int = 5,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
    ) -> List[Memory]:
        """
        Recherche des mémoires par similarité sémantique.
        
        Args:
            query: La requête textuelle
            limit: Le nombre maximum de résultats
            offset: Le décalage de pagination
            ts_start: Timestamp de début pour filtrer par date
            ts_end: Timestamp de fin pour filtrer par date
            
        Returns:
            Liste de mémoires triées par similarité
        """
        try:
            self.logger.info(f"Recherche de mémoires par similarité: '{query}'")
            
            # Génération de l'embedding pour la requête
            embedding = await self.embedding_service.generate_embedding(query)
            
            # Recherche par vecteur
            vector_result = await self.search_by_vector(
                vector=embedding,
                limit=limit,
                offset=offset,
                ts_start=ts_start,
                ts_end=ts_end
            )
            
            # Les tests attendent juste la liste, pas le tuple
            if isinstance(vector_result, tuple) and len(vector_result) == 2:
                results, _ = vector_result
            else:
                results = vector_result
                
            return results
            
        except Exception as e:
            self.logger.error(f"Erreur dans search_by_similarity: {str(e)}", exc_info=True)
            return []

    async def search_by_vector(
        self,
        vector: List[float],
        limit: int = 10,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        top_k: int = None,  # Pour compatibilité avec les tests
    ) -> Tuple[List[Memory], int]:
        """
        Recherche les mémoires les plus proches d'un vecteur d'embedding.
        
        Args:
            vector: Le vecteur d'embedding à rechercher
            limit: Nombre maximum de résultats
            offset: Décalage pour la pagination
            ts_start: Timestamp de début pour filtrer par date
            ts_end: Timestamp de fin pour filtrer par date
            metadata_filter: Filtre sur les métadonnées
            top_k: Alias pour limit (pour compatibilité avec les tests)
            
        Returns:
            Liste de mémoires triées par similarité et nombre total de résultats
        """
        try:
            # Utiliser top_k s'il est fourni (pour compatibilité API)
            if top_k is not None and limit == 10:
                limit = top_k
                
            self.logger.info(f"Recherche vectorielle avec dimension {len(vector)}")
            
            # Utiliser le repository d'événements pour la recherche vectorielle
            # unified call to search_vector
            events, total_hits = await self.event_repository.search_vector(
                vector=vector, # Use original vector
                metadata=metadata_filter,
                limit=limit,
                offset=offset,
                ts_start=ts_start,
                ts_end=ts_end
            )
            
            # Convertir les événements en mémoires
            memories = [self._event_to_memory(event) for event in events]
            
            self.logger.info(f"Recherche vectorielle: {len(memories)} résultats trouvés, total estimé: {total_hits}")
            return memories, total_hits
                
        except Exception as e:
            # Log general errors in search_by_vector
            self.logger.error(f"Erreur générale dans search_by_vector: {str(e)}", exc_info=True)
            return [], 0

    async def search_hybrid(
        self,
        query: str,
        metadata_filter: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = 0.5,
    ) -> Tuple[List[EventModel], int]:
        """
        Effectue une recherche hybride: embedding + filtres metadata/timestamp.
        Returns a tuple: (list of matching events, total potential hit count).
        """
        self.logger.info(
            f"Performing hybrid search with query: '{query}', metadata_filter: {metadata_filter}, limit: {limit}, offset: {offset}"
        )
        try:
            # Obtenir l'embedding pour la query texte
            query_embedding = None
            if query: # Only generate if query is not empty
                query_embedding = await self.embedding_service.generate_embedding(query)
            
            if not query_embedding:
                self.logger.info("No query text provided or embedding generation failed. Performing metadata/time search only.")

            
            # Appeler la méthode du repository qui gère tout (vector + filtres)
            # It now returns a tuple (events, total_hits)
            events, total_hits = await self.event_repository.search_vector(
                vector=query_embedding, # Pass the direct embedding or None
                metadata=metadata_filter,
                ts_start=ts_start,
                ts_end=ts_end,
                limit=limit,
                offset=offset,
                distance_threshold=distance_threshold
            )
            self.logger.info(f"Hybrid search found {len(events)} events (total potential: {total_hits}).")
            return events, total_hits # Return the tuple

        except RepositoryError as e:
            self.logger.error(f"Repository error during hybrid search: {e}", exc_info=True)
            raise ServiceError(f"Search failed due to repository error: {e}") from e
        except Exception as e:
            self.logger.exception("Unexpected error during hybrid search", exc_info=e)
            raise ServiceError(f"Unexpected error during search: {e}") from e
