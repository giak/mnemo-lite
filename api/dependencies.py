"""
Module de gestion des dépendances pour l'API MnemoLite.
Fournit les fonctions d'injection pour les repositories et services.
Respecte le principe d'inversion des dépendances (DIP).
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncEngine

# Import des interfaces (protocols)
from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import (
    EmbeddingServiceProtocol,
    MemorySearchServiceProtocol,
    EventProcessorProtocol,
    NotificationServiceProtocol,
)

# Import des implémentations concrètes
from db.repositories.event_repository import EventRepository
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import MockEmbeddingService
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
from services.memory_search_service import MemorySearchService
from services.event_processor import EventProcessor
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Cache global pour singleton embedding service
_embedding_service_instance: Optional[EmbeddingServiceProtocol] = None


# Fonction pour récupérer le moteur de base de données
async def get_db_engine(request: Request) -> AsyncEngine:
    """
    Récupère le moteur de base de données à partir de l'état de l'application.

    Args:
        request: La requête HTTP

    Returns:
        Le moteur SQLAlchemy AsyncEngine

    Raises:
        HTTPException: Si le moteur n'est pas disponible
    """
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        logger.error("Database connection not available")
        raise HTTPException(
            status_code=503,
            detail="Database connection not available. Please try again later.",
        )
    return engine


# Fonction pour récupérer les paramètres de configuration
async def get_settings(request: Request) -> Dict[str, Any]:
    """
    Récupère les paramètres de configuration de l'application.

    Args:
        request: La requête HTTP

    Returns:
        Les paramètres de configuration

    Raises:
        HTTPException: Si les paramètres ne sont pas disponibles
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        logger.error("Application settings not available")
        raise HTTPException(
            status_code=503,
            detail="Application settings not available. Please try again later.",
        )
    return settings


# Fonction pour injecter le repository d'événements
async def get_event_repository(
    engine: AsyncEngine = Depends(get_db_engine),
) -> EventRepositoryProtocol:
    """
    Récupère une instance du repository d'événements.

    Args:
        engine: Le moteur de base de données

    Returns:
        Une instance du repository d'événements
    """
    return EventRepository(engine)


# Fonction pour injecter le repository de mémoires
async def get_memory_repository(
    engine: AsyncEngine = Depends(get_db_engine),
) -> MemoryRepositoryProtocol:
    """
    Récupère une instance du repository de mémoires.

    Args:
        engine: Le moteur de base de données

    Returns:
        Une instance du repository de mémoires
    """
    return MemoryRepository(engine)


# Fonction pour injecter le service d'embedding
async def get_embedding_service() -> EmbeddingServiceProtocol:
    """
    Récupère une instance du service d'embedding (mock ou real selon config).
    Utilise un singleton pour réutiliser l'instance (et le modèle chargé).

    Returns:
        Une instance du service d'embedding

    Raises:
        ValueError: Si EMBEDDING_MODE invalide
    """
    global _embedding_service_instance

    if _embedding_service_instance is not None:
        return _embedding_service_instance

    # Déterminer le mode
    embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()

    if embedding_mode == "mock":
        logger.warning(
            "🔶 EMBEDDING MODE: MOCK (development/testing only) 🔶",
            extra={"embedding_mode": "mock"}
        )
        _embedding_service_instance = MockEmbeddingService(
            model_name="mock-model",
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "768"))
        )

    elif embedding_mode == "real":
        logger.info(
            "✅ EMBEDDING MODE: REAL (Sentence-Transformers)",
            extra={"embedding_mode": "real"}
        )
        _embedding_service_instance = SentenceTransformerEmbeddingService(
            model_name=os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
            cache_size=int(os.getenv("EMBEDDING_CACHE_SIZE", "1000")),
            device=os.getenv("EMBEDDING_DEVICE", "cpu")
        )

    else:
        raise ValueError(
            f"Invalid EMBEDDING_MODE: '{embedding_mode}'. "
            f"Must be 'mock' or 'real'."
        )

    return _embedding_service_instance


# Fonction pour injecter le service de recherche de mémoires
async def get_memory_search_service(
    event_repository: EventRepositoryProtocol = Depends(get_event_repository),
    memory_repository: MemoryRepositoryProtocol = Depends(get_memory_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
) -> MemorySearchServiceProtocol:
    """
    Récupère une instance du service de recherche de mémoires.

    Args:
        event_repository: Le repository d'événements
        memory_repository: Le repository de mémoires
        embedding_service: Le service d'embedding

    Returns:
        Une instance du service de recherche de mémoires
    """
    return MemorySearchService(
        event_repository=event_repository,
        memory_repository=memory_repository,
        embedding_service=embedding_service,
    )


# Fonction pour injecter le processeur d'événements
async def get_event_processor(
    event_repository: EventRepositoryProtocol = Depends(get_event_repository),
    memory_repository: MemoryRepositoryProtocol = Depends(get_memory_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
) -> EventProcessorProtocol:
    """
    Récupère une instance du processeur d'événements.

    Args:
        event_repository: Le repository d'événements
        memory_repository: Le repository de mémoires
        embedding_service: Le service d'embedding

    Returns:
        Une instance du processeur d'événements
    """
    return EventProcessor(
        event_repository=event_repository,
        memory_repository=memory_repository,
        embedding_service=embedding_service,
    )


# Fonction pour injecter le service de notification
async def get_notification_service(
    settings: Dict[str, Any] = Depends(get_settings),
) -> NotificationServiceProtocol:
    """
    Récupère une instance du service de notification.

    Args:
        settings: Les paramètres de configuration

    Returns:
        Une instance du service de notification
    """
    return NotificationService(
        smtp_host=settings.get("SMTP_HOST", "localhost"),
        smtp_port=settings.get("SMTP_PORT", 25),
        smtp_user=settings.get("SMTP_USER", ""),
        smtp_password=settings.get("SMTP_PASSWORD", ""),
    )
