"""
Service de traitement d'événements.
Implémente l'interface EventProcessorProtocol.
"""

import logging
from typing import Dict, Any, Optional, List
import json
from uuid import UUID
from datetime import datetime

from interfaces.services import EventProcessorProtocol, EmbeddingServiceProtocol
from interfaces.repositories import EventRepositoryProtocol
from models.event_models import EventModel
from models.memory_models import Memory, MemoryCreate

# Configuration du logger
logger = logging.getLogger(__name__)

class EventProcessor(EventProcessorProtocol):
    """
    Implémentation du service de traitement d'événements.
    """
    
    def __init__(
        self,
        event_repository: EventRepositoryProtocol,
        embedding_service: EmbeddingServiceProtocol
    ):
        """
        Initialise le processeur d'événements.
        
        Args:
            event_repository: Le repository d'événements
            embedding_service: Le service d'embeddings
        """
        self.event_repository = event_repository
        self.embedding_service = embedding_service
        logger.info("Initialisation du processeur d'événements")
    
    async def process_event(self, event: EventModel) -> Dict[str, Any]:
        """
        Traite un événement et enrichit ses métadonnées.
        
        Args:
            event: L'événement à traiter
            
        Returns:
            Les métadonnées enrichies
        """
        try:
            logger.info(f"Traitement de l'événement {event.id}")
            
            # Extraire les métadonnées existantes
            metadata = event.metadata.copy() if event.metadata else {}
            
            # Enrichir les métadonnées avec des informations sur le traitement
            metadata["processed_at"] = datetime.utcnow().isoformat()
            metadata["processor_version"] = "1.0.0"
            
            # Si l'événement n'a pas d'embedding, en générer un
            if not event.embedding:
                logger.info(f"Génération d'embedding pour l'événement {event.id}")
                try:
                    embedding = await self.embedding_service.generate_embedding(event.content)
                    # Mise à jour de l'événement avec l'embedding généré
                    updated_event = await self.event_repository.update_metadata(
                        event_id=event.id,
                        metadata={**metadata, "has_embedding": True}
                    )
                    if updated_event:
                        logger.info(f"Métadonnées de l'événement {event.id} mises à jour")
                    else:
                        logger.warning(f"Impossible de mettre à jour les métadonnées de l'événement {event.id}")
                    
                    # Ajouter l'information sur l'embedding aux métadonnées
                    metadata["has_embedding"] = True
                    metadata["embedding_dimension"] = len(embedding)
                except Exception as e:
                    logger.error(f"Erreur lors de la génération d'embedding: {str(e)}")
                    metadata["has_embedding"] = False
                    metadata["embedding_error"] = str(e)
            
            return metadata
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'événement {event.id}: {str(e)}")
            return {"error": str(e), "status": "failed"}
    
    async def generate_memory_from_event(self, event: EventModel) -> Optional[Memory]:
        """
        Génère une mémoire à partir d'un événement.
        
        Args:
            event: L'événement à partir duquel générer une mémoire
            
        Returns:
            La mémoire générée, ou None en cas d'erreur
        """
        try:
            logger.info(f"Génération de mémoire à partir de l'événement {event.id}")
            
            # Enrichir les métadonnées
            enriched_metadata = await self.process_event(event)
            
            # Créer une mémoire basée sur l'événement
            memory = Memory(
                id=str(event.id),  # Utilisation de l'ID de l'événement pour simplifier
                content=event.content,
                metadata={
                    **enriched_metadata,
                    "source_event_id": str(event.id),
                    "memory_created_at": datetime.utcnow().isoformat()
                },
                timestamp=event.timestamp
            )
            
            return memory
        except Exception as e:
            logger.error(f"Erreur lors de la génération de mémoire à partir de l'événement {event.id}: {str(e)}")
            return None 