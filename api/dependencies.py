"""
Module de gestion des dépendances pour l'API MnemoLite.
Fournit les fonctions d'injection pour les repositories et services.
Respecte le principe d'inversion des dépendances (DIP).
"""

import os
import structlog
from typing import Dict, Any, Optional, List
from fastapi import Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncEngine

# Import des interfaces (protocols)
from interfaces.repositories import EventRepositoryProtocol
from interfaces.services import (
    EmbeddingServiceProtocol,
    MemorySearchServiceProtocol,
    EventProcessorProtocol,
    NotificationServiceProtocol,
)

# Import des implémentations concrètes
from db.repositories.event_repository import EventRepository
from services.embedding_service import MockEmbeddingService
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.memory_search_service import MemorySearchService
from services.event_processor import EventProcessor
from services.notification_service import NotificationService
from services.event_service import EventService
from services.caches import CodeChunkCache, RedisCache, CascadeCache

logger = structlog.get_logger()


# ============================================================================
# Adapter pour backward compatibility DualEmbeddingService
# ============================================================================
class DualEmbeddingServiceAdapter:
    """
    Adapter pour rendre DualEmbeddingService compatible avec EmbeddingServiceProtocol.

    Phase 0 Story 0.2 - Assure backward compatibility complète:
    - generate_embedding(text) → génère embedding TEXT uniquement
    - compute_similarity() → supporte str et List[float]

    Permet au code existant (EventService, MemorySearchService) de fonctionner
    sans changement avec le nouveau DualEmbeddingService.
    """

    def __init__(self, dual_service: DualEmbeddingService):
        """
        Initialize adapter with DualEmbeddingService instance.

        Args:
            dual_service: Instance de DualEmbeddingService à wrapper
        """
        self._dual_service = dual_service

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Génère un embedding TEXT à partir d'un texte (backward compatible).

        Utilise generate_embedding_legacy() qui retourne uniquement
        l'embedding TEXT (nomic-embed-text-v1.5).

        Args:
            text: Texte à embedder

        Returns:
            Embedding TEXT (list de 768 floats)
        """
        return await self._dual_service.generate_embedding_legacy(text)

    async def compute_similarity(
        self,
        item1: Any,  # Union[str, List[float]]
        item2: Any   # Union[str, List[float]]
    ) -> float:
        """
        Calcule la similarité entre deux éléments (textes ou embeddings).

        Args:
            item1: Premier élément (str ou List[float])
            item2: Deuxième élément (str ou List[float])

        Returns:
            Score de similarité cosinus (0.0 à 1.0)
        """
        # Convert str to embeddings if needed
        emb1 = item1
        if isinstance(item1, str):
            emb1 = await self.generate_embedding(item1)

        emb2 = item2
        if isinstance(item2, str):
            emb2 = await self.generate_embedding(item2)

        # Compute similarity using dual service
        return await self._dual_service.compute_similarity(emb1, emb2)


# Note: Singleton is now managed via app.state.embedding_service in main.py


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


# EPIC-12 Story 12.2: Dependency functions for graph repositories
async def get_chunk_repository(
    engine: AsyncEngine = Depends(get_db_engine),
):
    """
    Récupère une instance du repository de code chunks.

    Args:
        engine: Le moteur de base de données

    Returns:
        Une instance du repository de code chunks
    """
    from db.repositories.code_chunk_repository import CodeChunkRepository
    return CodeChunkRepository(engine)


async def get_node_repository(
    engine: AsyncEngine = Depends(get_db_engine),
):
    """
    Récupère une instance du repository de graph nodes.

    Args:
        engine: Le moteur de base de données

    Returns:
        Une instance du repository de graph nodes
    """
    from db.repositories.node_repository import NodeRepository
    return NodeRepository(engine)


async def get_edge_repository(
    engine: AsyncEngine = Depends(get_db_engine),
):
    """
    Récupère une instance du repository de graph edges.

    Args:
        engine: Le moteur de base de données

    Returns:
        Une instance du repository de graph edges
    """
    from db.repositories.edge_repository import EdgeRepository
    return EdgeRepository(engine)


# Fonction pour injecter le service d'embedding
async def get_embedding_service(request: Request) -> EmbeddingServiceProtocol:
    """
    Récupère une instance du service d'embedding depuis app.state.
    Le service est initialisé une seule fois au démarrage dans main.py lifespan.

    Args:
        request: La requête HTTP pour accéder à app.state

    Returns:
        Une instance du service d'embedding

    Raises:
        HTTPException: Si le service n'est pas disponible
    """
    # Try to get from app.state first
    embedding_service = getattr(request.app.state, "embedding_service", None)

    if embedding_service is not None:
        return embedding_service

    # Fallback: create service on demand if not in app.state
    # This can happen during tests or if startup failed
    logger.warning("Embedding service not in app.state, creating on demand")

    # Déterminer le mode
    embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()

    if embedding_mode == "mock":
        logger.warning(
            "🔶 EMBEDDING MODE: MOCK (development/testing only) 🔶",
            extra={"embedding_mode": "mock"}
        )
        embedding_service = MockEmbeddingService(
            model_name="mock-model",
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "768"))
        )

    elif embedding_mode == "real":
        logger.info(
            "✅ EMBEDDING MODE: DUAL (TEXT + CODE) - Phase 0 Story 0.2",
            extra={
                "embedding_mode": "dual",
                "text_model": os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
                "code_model": os.getenv("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code")
            }
        )

        # Create DualEmbeddingService (supports TEXT + CODE domains)
        dual_service = DualEmbeddingService(
            text_model_name=os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5"),
            code_model_name=os.getenv("CODE_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-code"),
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "768")),
            device=os.getenv("EMBEDDING_DEVICE", "cpu"),
            cache_size=int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))
        )

        # Wrap with adapter for backward compatibility
        embedding_service = DualEmbeddingServiceAdapter(dual_service)

    else:
        raise ValueError(
            f"Invalid EMBEDDING_MODE: '{embedding_mode}'. "
            f"Must be 'mock' or 'real'."
        )

    # Store in app.state for next time
    request.app.state.embedding_service = embedding_service
    return embedding_service


# Fonction pour injecter le service d'embedding avec cache
async def get_cached_embedding_service(request: Request) -> EmbeddingServiceProtocol:
    """
    Récupère une instance du service d'embedding avec cache intégré.
    Améliore les performances en évitant de recalculer les embeddings identiques.

    Args:
        request: La requête HTTP pour accéder à app.state

    Returns:
        Une instance du service d'embedding avec cache

    Note:
        Le cache est partagé au niveau de l'application (app.state.embedding_cache)
        pour maximiser le hit rate entre les requêtes.
    """
    # Get base embedding service
    base_service = await get_embedding_service(request)

    # Get or create cache from app.state
    if not hasattr(request.app.state, "embedding_cache"):
        from services.simple_cache_service import SimpleMemoryCache

        logger.info("Creating embedding cache (10000 entries max, 1 hour TTL)")
        request.app.state.embedding_cache = SimpleMemoryCache(
            max_size=10000,  # 10k embeddings = ~30MB
            ttl_seconds=3600,  # 1 hour TTL
            enable_stats=True
        )

    # Check if service is already wrapped with cache
    if hasattr(request.app.state, "cached_embedding_service"):
        return request.app.state.cached_embedding_service

    # Wrap with cache
    from services.simple_cache_service import CachedEmbeddingService

    cached_service = CachedEmbeddingService(
        embedding_service=base_service,
        cache=request.app.state.embedding_cache
    )

    # Store for reuse
    request.app.state.cached_embedding_service = cached_service

    logger.info("Embedding service wrapped with cache")
    return cached_service


# Fonction pour injecter le cache L1 de code chunks (EPIC-10 Story 10.1)
async def get_code_chunk_cache(request: Request) -> CodeChunkCache:
    """
    Récupère l'instance singleton du cache L1 de code chunks.

    Le cache est initialisé une seule fois au démarrage et stocké dans app.state.
    Il utilise une stratégie LRU avec validation MD5 pour garantir la cohérence.

    Args:
        request: La requête HTTP pour accéder à app.state

    Returns:
        Instance singleton du CodeChunkCache

    Note:
        Configuration:
        - max_size_mb: 100MB (configurable via L1_CACHE_SIZE_MB)
        - Eviction policy: LRU (Least Recently Used)
        - Validation: MD5 content hash (zero-trust)
    """
    # Check if cache already exists in app.state
    if hasattr(request.app.state, "code_chunk_cache"):
        return request.app.state.code_chunk_cache

    # Create cache singleton
    cache_size_mb = int(os.getenv("L1_CACHE_SIZE_MB", "100"))
    code_chunk_cache = CodeChunkCache(max_size_mb=cache_size_mb)

    # Store in app.state for singleton pattern
    request.app.state.code_chunk_cache = code_chunk_cache

    logger.info(
        "L1 Code Chunk Cache initialized",
        max_size_mb=cache_size_mb,
        eviction_policy="LRU",
        validation="MD5"
    )

    return code_chunk_cache


# Fonction pour injecter le service de recherche de mémoires
async def get_memory_search_service(
    event_repository: EventRepositoryProtocol = Depends(get_event_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
) -> MemorySearchServiceProtocol:
    """
    Récupère une instance du service de recherche de mémoires.

    Phase 3.3: Removed memory_repository injection as it's no longer used by MemorySearchService.
    All search operations now use event_repository.search_vector() (since Phase 3.2).

    Args:
        event_repository: Le repository d'événements
        embedding_service: Le service d'embedding

    Returns:
        Une instance du service de recherche de mémoires
    """
    return MemorySearchService(
        event_repository=event_repository,
        embedding_service=embedding_service,
    )


# Fonction pour injecter le processeur d'événements
async def get_event_processor(
    event_repository: EventRepositoryProtocol = Depends(get_event_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
) -> EventProcessorProtocol:
    """
    Récupère une instance du processeur d'événements.

    Phase 3.3: Removed memory_repository injection as EventProcessor doesn't use it.
    EventProcessor only uses event_repository and embedding_service.

    Args:
        event_repository: Le repository d'événements
        embedding_service: Le service d'embedding

    Returns:
        Une instance du processeur d'événements
    """
    return EventProcessor(
        event_repository=event_repository,
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


# Fonction pour injecter le service d'événements
async def get_event_service(
    event_repository: EventRepositoryProtocol = Depends(get_event_repository),
    embedding_service: EmbeddingServiceProtocol = Depends(get_embedding_service),
) -> EventService:
    """
    Récupère une instance du service d'événements.

    Args:
        event_repository: Le repository d'événements
        embedding_service: Le service d'embedding

    Returns:
        Une instance du service d'événements
    """
    # Configuration depuis env vars
    config = {
        "auto_generate_embeddings": os.getenv("EMBEDDING_AUTO_GENERATE", "true").lower() == "true",
        "embedding_fail_strategy": os.getenv("EMBEDDING_FAIL_STRATEGY", "soft"),  # soft | hard
        "embedding_source_fields": os.getenv(
            "EMBEDDING_SOURCE_FIELDS",
            "text,body,message,content,title"
        ).split(",")
    }

    return EventService(
        repository=event_repository,
        embedding_service=embedding_service,
        config=config
    )


# Fonction pour injecter le cache L2 Redis (EPIC-10 Story 10.2)
async def get_redis_cache(request: Request) -> RedisCache:
    """
    Récupère l'instance singleton du cache L2 Redis.

    Le cache est initialisé une seule fois au démarrage et stocké dans app.state.
    Il permet le partage de cache entre instances API via Redis.

    Args:
        request: La requête HTTP pour accéder à app.state

    Returns:
        Instance singleton du RedisCache

    Note:
        Configuration:
        - Redis URL: configurable via REDIS_URL (default: redis://localhost:6379/0)
        - Connection pooling: max 20 connections
        - Graceful degradation: continue sans cache si Redis indisponible
        - TTL par type: search=30s, graph=120s

    Raises:
        None - graceful degradation if Redis unavailable
    """
    # Check if cache already exists in app.state
    if hasattr(request.app.state, "redis_cache"):
        return request.app.state.redis_cache

    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Create RedisCache singleton
    redis_cache = RedisCache(redis_url=redis_url)

    # Note: Connection is established in main.py lifespan
    # This allows proper async initialization and cleanup

    # Store in app.state for singleton pattern
    request.app.state.redis_cache = redis_cache

    logger.info(
        "L2 Redis Cache singleton created",
        redis_url=redis_url,
        connection_pool_max=20,
        graceful_degradation=True
    )

    return redis_cache



# Fonction pour injecter le cascade cache L1/L2 (EPIC-10 Story 10.3)
async def get_cascade_cache(request: Request) -> CascadeCache:
    """
    Récupère l'instance singleton du cascade cache L1/L2.
    
    Le cascade cache coordonne L1 (in-memory) et L2 (Redis) avec promotion automatique:
    - L1 hit → retourne immédiatement (< 0.01ms)
    - L1 miss → check L2 → promote to L1 on hit (1-5ms)
    - L1/L2 miss → query L3 (PostgreSQL) → populate both layers (100-200ms)
    
    Args:
        request: La requête HTTP pour accéder à app.state
    
    Returns:
        Instance singleton du CascadeCache
    
    Note:
        Configuration:
        - L1: In-memory LRU cache (100MB, MD5 validation)
        - L2: Redis distributed cache (2GB, shared across instances)
        - Strategy: Write-through (populate both on miss)
        - Promotion: L2 hit → auto-promote to L1 (warm → hot migration)
    """
    # Check if cascade cache already exists in app.state
    if hasattr(request.app.state, "cascade_cache"):
        return request.app.state.cascade_cache
    
    # Get L1 and L2 caches (already initialized via their own dependency functions)
    l1_cache = await get_code_chunk_cache(request)
    l2_cache = await get_redis_cache(request)
    
    # Create CascadeCache that coordinates L1 and L2
    cascade_cache = CascadeCache(l1_cache=l1_cache, l2_cache=l2_cache)
    
    # Store in app.state for singleton pattern
    request.app.state.cascade_cache = cascade_cache
    
    logger.info(
        "Cascade Cache (L1/L2) initialized",
        l1_max_mb=l1_cache.max_size_bytes / (1024 * 1024),
        l2_connected=l2_cache.client is not None,
        strategy="L1 → L2 → L3 (PostgreSQL)",
        promotion="automatic"
    )
    
    return cascade_cache


# ============================================================================
# EPIC-12 Story 12.4: Error Tracking Dependencies
# ============================================================================

async def get_error_repository(
    engine: AsyncEngine = Depends(get_db_engine),
):
    """
    Récupère une instance du repository d'erreurs.

    Args:
        engine: Le moteur de base de données

    Returns:
        Une instance du repository d'erreurs
    """
    from db.repositories.error_repository import ErrorRepository
    return ErrorRepository(engine)


async def get_error_tracking_service(
    error_repository = Depends(get_error_repository),
):
    """
    Récupère une instance du service de suivi d'erreurs.

    Args:
        error_repository: Le repository d'erreurs

    Returns:
        Une instance du service de suivi d'erreurs
    """
    from services.error_tracking_service import ErrorTrackingService
    return ErrorTrackingService(error_repository)
