from fastapi import Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncEngine

# Import des repositories
from db.repositories.event_repository import EventRepository
from db.repositories.memory_repository import MemoryRepository

# Import des protocoles
from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import (
    EmbeddingServiceProtocol, 
    MemorySearchServiceProtocol, 
    EventProcessorProtocol, 
    NotificationServiceProtocol
)

# Import des services
from services.embedding_service import EmbeddingService
# Note: Ces imports seront actifs quand les services seront implémentés
from services.memory_search_service import MemorySearchService
# from services.event_processor import EventProcessor
# from services.notification_service import NotificationService

# === Injection des repositories ===

async def get_db_engine(request: Request) -> AsyncEngine:
    """Récupère le moteur SQLAlchemy stocké dans l'état de l'application."""
    engine = request.app.state.db_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Database engine is not available.")
    return engine

async def get_event_repository(engine: AsyncEngine = Depends(get_db_engine)) -> EventRepositoryProtocol:
    """Injecte une instance de EventRepository avec le moteur SQLAlchemy.
    
    Returns:
        Une implémentation du protocole EventRepositoryProtocol.
    """
    return EventRepository(engine=engine)

async def get_memory_repository(engine: AsyncEngine = Depends(get_db_engine)) -> MemoryRepositoryProtocol:
    """Injecte une instance de MemoryRepository avec le moteur SQLAlchemy.
    
    Returns:
        Une implémentation du protocole MemoryRepositoryProtocol.
    """
    return MemoryRepository(engine=engine)

# === Injection des services ===

async def get_embedding_service() -> EmbeddingServiceProtocol:
    """Injecte une instance du service d'embeddings.
    
    Returns:
        Une implémentation du protocole EmbeddingServiceProtocol.
    """
    return EmbeddingService(model_name="all-MiniLM-L6-v2", embedding_size=384)

async def get_memory_search_service(
    event_repo: EventRepositoryProtocol = Depends(get_event_repository),
    memory_repo: MemoryRepositoryProtocol = Depends(get_memory_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service)
) -> MemorySearchServiceProtocol:
    """Injecte une instance du service de recherche de mémoires.
    
    Returns:
        Une implémentation du protocole MemorySearchServiceProtocol.
    """
    # Remplacer l'exception par l'instanciation du service
    return MemorySearchService(
        event_repository=event_repo, 
        memory_repository=memory_repo, 
        embedding_service=embedding_service
    )

async def get_event_processor(
    event_repo: EventRepositoryProtocol = Depends(get_event_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service)
) -> EventProcessorProtocol:
    """Injecte une instance du service de traitement d'événements.
    
    Returns:
        Une implémentation du protocole EventProcessorProtocol.
    """
    # À implémenter quand le service sera disponible
    raise NotImplementedError("Le service de traitement d'événements n'est pas encore implémenté")
    # return EventProcessor(event_repo, embedding_service)

async def get_notification_service() -> NotificationServiceProtocol:
    """Injecte une instance du service de notifications.
    
    Returns:
        Une implémentation du protocole NotificationServiceProtocol.
    """
    # À implémenter quand le service sera disponible
    raise NotImplementedError("Le service de notifications n'est pas encore implémenté")
    # return NotificationService()

# Ce pattern permet de facilement changer d'implémentation, par exemple pour les tests
# Il suffit de créer une autre factory function qui retourne un mock ou une autre implémentation 