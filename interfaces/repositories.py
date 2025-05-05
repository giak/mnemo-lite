"""
Interfaces pour les repositories selon le Dependency Inversion Principle (DIP).
Ces protocoles définissent les contrats que les implémentations concrètes doivent respecter.
"""
from typing import Protocol, Optional, List, Dict, Any, Union, Tuple
from uuid import UUID

from models.event_models import EventModel, EventCreate
from models.memory_models import Memory, MemoryCreate, MemoryUpdate


class EventRepositoryProtocol(Protocol):
    """Interface définissant les opérations possibles sur les événements."""
    
    async def add(self, event: EventCreate) -> EventModel:
        """Ajoute un nouvel événement."""
        ...
    
    async def get_by_id(self, event_id: UUID) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        ...
    
    async def update_metadata(self, event_id: UUID, metadata: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour les métadonnées d'un événement."""
        ...
    
    async def delete(self, event_id: UUID) -> bool:
        """Supprime un événement par son ID."""
        ...
    
    async def search_by_embedding(self, embedding: List[float], limit: int = 5) -> List[EventModel]:
        """Recherche les événements similaires à un embedding."""
        ...
    
    async def filter_by_metadata(self, metadata_filter: Dict[str, Any], limit: int = 10, offset: int = 0) -> List[EventModel]:
        """Filtre les événements par métadonnées."""
        ...


class MemoryRepositoryProtocol(Protocol):
    """Interface définissant les opérations possibles sur les mémoires."""
    
    async def add(self, memory: MemoryCreate) -> Memory:
        """Ajoute une nouvelle mémoire."""
        ...
    
    async def get_by_id(self, memory_id: Union[UUID, str]) -> Optional[Memory]:
        """Récupère une mémoire par son ID."""
        ...
    
    async def update(self, memory_id: Union[UUID, str], memory_update: MemoryUpdate) -> Optional[Memory]:
        """Met à jour une mémoire existante."""
        ...
    
    async def delete(self, memory_id: Union[UUID, str]) -> bool:
        """Supprime une mémoire par son ID."""
        ...
    
    async def list_memories(
        self, 
        limit: int = 10, 
        offset: int = 0,
        memory_type: Optional[str] = None,
        event_type: Optional[str] = None,
        role_id: Optional[int] = None,
        session_id: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        ts_start: Optional[Any] = None,
        ts_end: Optional[Any] = None,
        skip: Optional[int] = None
    ) -> Tuple[List[Memory], int]:
        """Liste les mémoires avec pagination et filtrage optionnel.
        
        Returns:
            Tuple contenant (liste des mémoires, nombre total)
        """
        ...
    
    async def search_by_embedding(
        self,
        embedding: List[float],
        limit: int = 10,
        skip: int = 0,
        ts_start: Optional[Any] = None,
        ts_end: Optional[Any] = None
    ) -> Tuple[List[Memory], int]:
        """Recherche les mémoires par similarité d'embedding.
        
        Returns:
            Tuple contenant (liste des mémoires, nombre total)
        """
        ... 