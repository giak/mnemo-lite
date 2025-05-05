"""
Service de recherche de mémoires.
Implémente l'interface MemorySearchServiceProtocol.
"""

import logging
from typing import List, Dict, Any, Optional, Union
import json
from datetime import datetime

from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol, MemorySearchServiceProtocol
from models.memory_models import Memory
from models.event_models import EventModel

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
    
    async def search_by_metadata(
        self, 
        metadata_filter: Dict[str, Any], 
        limit: int = 10,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """
        Recherche des mémoires par leurs métadonnées.
        
        Args:
            metadata_filter: Les critères de filtrage sur les métadonnées
            limit: Le nombre maximum de résultats à retourner
            offset: Le décalage pour la pagination
            ts_start: Timestamp de début pour filtrer par date
            ts_end: Timestamp de fin pour filtrer par date
            
        Returns:
            Une liste de mémoires correspondant aux critères
        """
        try:
            logger.info(f"Recherche de mémoires par métadonnées: {json.dumps(metadata_filter)}")
            # Délégation au repository de mémoires
            memories = await self.memory_repository.list_memories(
                metadata_filter=metadata_filter,
                limit=limit,
                skip=offset,
                ts_start=ts_start,
                ts_end=ts_end
            )
            return memories
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par métadonnées: {str(e)}")
            return []
    
    async def search_by_similarity(
        self, 
        query: str, 
        limit: int = 5,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """
        Recherche des mémoires par similarité sémantique.
        
        Args:
            query: Le texte de référence pour la recherche
            limit: Le nombre maximum de résultats à retourner
            offset: Le décalage pour la pagination
            ts_start: Timestamp de début pour filtrer par date
            ts_end: Timestamp de fin pour filtrer par date
            
        Returns:
            Une liste de mémoires triées par similarité
        """
        try:
            logger.info(f"Recherche de mémoires par similarité: '{query}'")
            
            # Génération de l'embedding pour la requête
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            return await self.search_by_vector(
                embedding=query_embedding,
                limit=limit,
                offset=offset,
                ts_start=ts_start,
                ts_end=ts_end
            )
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par similarité: {str(e)}")
            return []
            
    async def search_by_vector(
        self, 
        embedding: List[float], 
        top_k: int = 10,
        limit: int = 5,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """
        Recherche des mémoires par similarité vectorielle.
        
        Args:
            embedding: Le vecteur d'embedding pour la recherche
            top_k: Nombre maximum de résultats vectoriels à considérer
            limit: Le nombre maximum de résultats à retourner
            offset: Le décalage pour la pagination
            ts_start: Timestamp de début pour filtrer par date
            ts_end: Timestamp de fin pour filtrer par date
            
        Returns:
            Une liste de mémoires triées par similarité
        """
        try:
            logger.info(f"Recherche de mémoires par vecteur de dimension {len(embedding)}")
            
            # Recherche d'événements similaires
            similar_events = await self.event_repository.search_by_embedding(
                embedding=embedding,
                limit=top_k,
                skip=offset,
                ts_start=ts_start,
                ts_end=ts_end
            )
            
            # Limitation du nombre de résultats après tri
            if len(similar_events) > limit:
                similar_events = similar_events[:limit]
            
            # Conversion des événements en mémoires
            memories = []
            for event in similar_events:
                # Création d'une mémoire à partir de l'événement
                memory = Memory(
                    id=str(event.id),  # Utilisation de l'ID de l'événement pour simplifier
                    content=event.content,
                    metadata=event.metadata,
                    timestamp=event.timestamp,
                    embedding=event.embedding,
                    similarity_score=event.similarity_score if hasattr(event, 'similarity_score') else None
                )
                memories.append(memory)
            
            return memories
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par vecteur: {str(e)}")
            return []
    
    async def search_hybrid(
        self,
        query: str = None,
        embedding: List[float] = None,
        metadata_filter: Dict[str, Any] = None,
        limit: int = 10,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> tuple[List[Union[Memory, EventModel]], int]:
        """
        Effectue une recherche hybride (texte + vecteur) sur les mémoires.
        
        Args:
            query: Requête textuelle (pour recherche par similarité)
            embedding: Vecteur d'embedding pour recherche par similarité
            metadata_filter: Filtre sur les métadonnées
            limit: Nombre maximum de résultats à retourner
            offset: Décalage pour la pagination
            ts_start: Date de début pour filtrer par date
            ts_end: Date de fin pour filtrer par date
            
        Returns:
            Tuple contenant (liste des mémoires trouvées, nombre total de résultats)
        """
        try:
            results = []
            total_count = 0
            
            # Si un embedding n'est pas fourni mais que query l'est, générer l'embedding
            if not embedding and query:
                try:
                    embedding = await self.embedding_service.generate_embedding(query)
                    logger.info(f"Embedding généré à partir de la requête texte: '{query}'")
                except Exception as e:
                    logger.error(f"Erreur lors de la génération de l'embedding pour '{query}': {str(e)}")
                    embedding = None
            
            # Si un embedding est fourni, faire une recherche par similarité
            if embedding:
                try:
                    # Vérifier que nous avons un embedding valide
                    if not isinstance(embedding, list) or len(embedding) == 0:
                        logger.warning("Embedding invalide ou vide fourni à search_hybrid")
                    else:
                        logger.info(f"Recherche vectorielle avec dimension {len(embedding)}")
                        
                        # Ensure embedding has the correct dimension (1536 for OpenAI models typically)
                        expected_dim = 1536  # This should match your database schema
                        
                        # If dimensions don't match, log warning but proceed (the DB will likely return no results)
                        if len(embedding) != expected_dim:
                            logger.warning(f"Dimension mismatch: expected {expected_dim}, got {len(embedding)}. Proceeding anyway.")
                        
                        vector_results, vector_count = await self.memory_repository.search_by_embedding(
                            embedding=embedding,
                            limit=limit,
                            skip=offset,
                            ts_start=ts_start,
                            ts_end=ts_end
                        )
                        results.extend(vector_results)
                        total_count = vector_count
                        logger.info(f"Recherche vectorielle: {vector_count} résultats trouvés")
                except Exception as e:
                    logger.error(f"Erreur lors de la recherche par embedding: {str(e)}")
                    # Ne pas échouer complètement si la recherche vectorielle échoue,
                    # continuez avec la recherche par métadonnées si disponible
            
            # Si un filtre de métadonnées est fourni, faire une recherche par métadonnées
            if metadata_filter:
                try:
                    metadata_results, metadata_count = await self.memory_repository.list_memories(
                        limit=limit,
                        skip=offset,
                        metadata_filter=metadata_filter,
                        ts_start=ts_start,
                        ts_end=ts_end
                    )
                    
                    # Si nous avons déjà des résultats de recherche vectorielle, fusionner
                    if embedding and results:
                        # Logique de fusion simple - en pratique, une approche plus sophistiquée serait nécessaire
                        # Par exemple, un score combiné normalisé
                        combined_results = list({str(memory.id): memory for memory in results + metadata_results}.values())
                        results = combined_results
                        # Le total reste le maximum des deux pour éviter double-comptage
                        total_count = max(total_count, metadata_count)
                    else:
                        # Si pas de recherche vectorielle, utiliser directement les résultats par métadonnées
                        results = metadata_results
                        total_count = metadata_count
                    
                    logger.info(f"Recherche par métadonnées: {metadata_count} résultats trouvés")
                except Exception as e:
                    logger.error(f"Erreur lors de la recherche par métadonnées: {str(e)}")
            
            return results, total_count
        except Exception as e:
            logger.error(f"Erreur lors de la recherche hybride: {str(e)}")
            return [], 0 