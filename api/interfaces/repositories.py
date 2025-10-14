"""
Interfaces pour les repositories selon le Dependency Inversion Principle (DIP).
Ces protocoles définissent les contrats que les implémentations concrètes doivent respecter.

Phase 3.4: Removed MemoryRepositoryProtocol entirely.
Memory operations are handled by EventRepository + conversion to Memory model when needed.
"""

from typing import Protocol, Optional, List, Dict, Any
from uuid import UUID

from models.event_models import EventModel, EventCreate


class EventRepositoryProtocol(Protocol):
    """Interface définissant les opérations possibles sur les événements.

    Phase 3.3: Removed deprecated search_by_embedding() and search_hybrid().
    EventRepository only implements search_vector() for unified search interface.

    Phase 3.4: This is now the ONLY repository protocol.
    For Memory objects, use EventRepository + convert EventModel -> Memory.
    """

    async def add(self, event: EventCreate) -> EventModel:
        """Ajoute un nouvel événement."""
        ...

    async def get_by_id(self, event_id: UUID) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        ...

    async def update_metadata(
        self, event_id: UUID, metadata: Dict[str, Any]
    ) -> Optional[EventModel]:
        """Met à jour les métadonnées d'un événement."""
        ...

    async def delete(self, event_id: UUID) -> bool:
        """Supprime un événement par son ID."""
        ...

    async def filter_by_metadata(
        self, metadata_filter: Dict[str, Any], limit: int = 10, offset: int = 0
    ) -> List[EventModel]:
        """Filtre les événements par métadonnées."""
        ...
