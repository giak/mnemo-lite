"""
Service layer for event business logic.
Orchestrates event creation with auto-embedding generation.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from uuid import UUID

from models.event_models import EventModel, EventCreate
from interfaces.repositories import EventRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol


logger = logging.getLogger(__name__)


class EventService:
    """
    Service for event business logic.

    Responsibilities:
    - Auto-generate embeddings from content if not provided
    - Orchestrate repository operations
    - Handle business rules and validation
    """

    def __init__(
        self,
        repository: EventRepositoryProtocol,
        embedding_service: EmbeddingServiceProtocol,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize EventService.

        Args:
            repository: Event repository for data access
            embedding_service: Embedding service for vector generation
            config: Optional configuration dict
        """
        self.repo = repository
        self.embedding_svc = embedding_service
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.auto_generate = self.config.get("auto_generate_embeddings", True)
        self.fail_strategy = self.config.get("embedding_fail_strategy", "soft")  # soft | hard
        self.source_fields = self.config.get("embedding_source_fields", [
            "text", "body", "message", "content", "title"
        ])

        self.logger.info(
            f"EventService initialized (auto_generate={self.auto_generate}, "
            f"fail_strategy={self.fail_strategy}, "
            f"source_fields={self.source_fields})"
        )

    async def create_event(self, event_data: EventCreate) -> EventModel:
        """
        Create an event with auto-generated embedding if needed.

        Logic:
        1. If embedding provided → use as-is (skip generation)
        2. If no embedding + text present → auto-generate
        3. If generation fails:
           - soft: log warning, continue without embedding
           - hard: raise exception, event not created

        Args:
            event_data: Event creation data

        Returns:
            Created event model

        Raises:
            Exception: If embedding generation fails with hard strategy
        """
        # Skip if embedding already provided
        if event_data.embedding:
            self.logger.debug(
                "Embedding already provided, skipping generation",
                extra={"embedding_length": len(event_data.embedding)}
            )
            return await self.repo.add(event_data)

        # Skip if auto-generation disabled
        if not self.auto_generate:
            self.logger.debug("Auto-generation disabled, creating event without embedding")
            return await self.repo.add(event_data)

        # Extract text from content
        text = self._extract_text_for_embedding(event_data.content)

        if text:
            try:
                self.logger.info(
                    f"Generating embedding for text",
                    extra={"text_length": len(text), "text_preview": text[:50]}
                )
                event_data.embedding = await self.embedding_svc.generate_embedding(text)
                self.logger.info(
                    "✅ Embedding generated successfully",
                    extra={"embedding_length": len(event_data.embedding)}
                )
            except Exception as e:
                error_msg = f"Failed to generate embedding: {e}"

                if self.fail_strategy == "hard":
                    self.logger.error(error_msg, exc_info=True)
                    raise  # Re-raise exception, event not created
                else:
                    # Fail soft: log warning and continue
                    self.logger.warning(
                        f"{error_msg}. Event will be created without embedding."
                    )
        else:
            self.logger.debug(
                "No text found in content for embedding generation",
                extra={"content_keys": list(event_data.content.keys())}
            )

        return await self.repo.add(event_data)

    def _extract_text_for_embedding(self, content: Dict[str, Any]) -> Optional[str]:
        """
        Extract text from content dict for embedding generation.

        Tries source fields in priority order (configurable).
        Default priority: text > body > message > content > title

        Args:
            content: Content dictionary

        Returns:
            First non-empty text field found, or None
        """
        for field in self.source_fields:
            if value := content.get(field):
                if isinstance(value, str) and value.strip():
                    self.logger.debug(
                        f"Extracted text from field '{field}'",
                        extra={"field": field, "length": len(value)}
                    )
                    return value.strip()

        return None

    async def get_event(self, event_id: UUID) -> Optional[EventModel]:
        """
        Get event by ID.

        Args:
            event_id: Event UUID

        Returns:
            Event model or None if not found
        """
        return await self.repo.get_by_id(event_id)

    async def update_event_metadata(
        self,
        event_id: UUID,
        metadata: Dict[str, Any]
    ) -> Optional[EventModel]:
        """
        Update event metadata.

        Args:
            event_id: Event UUID
            metadata: New metadata to merge

        Returns:
            Updated event model or None if not found
        """
        return await self.repo.update_metadata(event_id, metadata)

    async def delete_event(self, event_id: UUID) -> bool:
        """
        Delete event by ID.

        Args:
            event_id: Event UUID

        Returns:
            True if deleted, False if not found
        """
        return await self.repo.delete(event_id)

    async def filter_events_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> List[EventModel]:
        """
        Filter events by metadata criteria.

        Args:
            metadata_filter: Metadata filter criteria
            limit: Max results
            offset: Pagination offset

        Returns:
            List of matching events
        """
        return await self.repo.filter_by_metadata(metadata_filter, limit, offset)

    async def search_events_by_embedding(
        self,
        embedding: List[float],
        limit: int = 5
    ) -> List[EventModel]:
        """
        Search events by embedding similarity.

        Phase 3.3: Fixed to use EventRepository.search_vector() instead of non-existent search_by_embedding()

        Args:
            embedding: Query embedding vector
            limit: Max results

        Returns:
            List of similar events
        """
        # Use unified search_vector interface
        events, _ = await self.repo.search_vector(
            vector=embedding,
            limit=limit,
            offset=0
        )
        return events
