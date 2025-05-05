"""
Interfaces pour les services selon le Dependency Inversion Principle (DIP).
Ces protocoles définissent les contrats que les implémentations concrètes doivent respecter.
"""
from typing import Protocol, Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import datetime

from models.event_models import EventModel
from models.memory_models import Memory


class EmbeddingServiceProtocol(Protocol):
    """Interface définissant un service de génération d'embeddings."""
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Génère un embedding à partir d'un texte."""
        ...
    
    async def compute_similarity(self, item1: Union[str, List[float]], item2: Union[str, List[float]]) -> float:
        """Calcule la similarité entre deux éléments (textes ou embeddings)."""
        ...


class MemorySearchServiceProtocol(Protocol):
    """Interface définissant un service de recherche de mémoires."""
    
    async def search_by_content(
        self, 
        query: str, 
        limit: int = 5,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """Recherche des mémoires par leur contenu textuel."""
        ...
    
    async def search_by_metadata(
        self, 
        metadata_filter: Dict[str, Any], 
        limit: int = 10,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """Recherche des mémoires par leurs métadonnées."""
        ...
    
    async def search_by_similarity(
        self, 
        query: str, 
        limit: int = 5,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """Recherche des mémoires par similarité sémantique."""
        ...
        
    async def search_hybrid(
        self,
        embedding: List[float],
        metadata_filter: Dict[str, Any],
        top_k: int = 10,
        limit: int = 5,
        offset: int = 0,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None
    ) -> List[Memory]:
        """Recherche hybride combinant filtrage par métadonnées et similarité vectorielle."""
        ...


class EventProcessorProtocol(Protocol):
    """Interface définissant un service de traitement d'événements."""
    
    async def process_event(self, event: EventModel) -> Dict[str, Any]:
        """Traite un événement et retourne des métadonnées enrichies."""
        ...
    
    async def generate_memory_from_event(self, event: EventModel) -> Optional[Memory]:
        """Génère une mémoire à partir d'un événement."""
        ...


class NotificationServiceProtocol(Protocol):
    """Interface définissant un service de notifications."""
    
    async def send_notification(self, user_id: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Envoie une notification à un utilisateur."""
        ...
    
    async def broadcast_notification(self, message: str, user_ids: Optional[List[str]] = None) -> Dict[str, bool]:
        """Envoie une notification à plusieurs utilisateurs."""
