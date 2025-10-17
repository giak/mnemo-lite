"""
Example of EventRepository using Result pattern.

This is an example showing how to refactor repository methods to use the Result pattern
for cleaner error handling. This can be gradually adopted in the codebase.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from models.event_models import EventModel, EventCreate
from db.query_builders import EventQueryBuilder
from db.result import RepositoryResult, Error, ErrorType
from utils.context_logger import get_repository_logger


class EventRepositoryWithResult:
    """
    Event repository with Result pattern for error handling.

    Example of cleaner error handling without excessive try/except blocks.
    """

    def __init__(self, engine: AsyncEngine):
        """Initialize repository."""
        self.engine = engine
        self.query_builder = EventQueryBuilder()
        self.logger = get_repository_logger("event_with_result")

    async def add(self, event_data: EventCreate) -> RepositoryResult[EventModel]:
        """
        Add a new event using Result pattern.

        Args:
            event_data: Event data to add

        Returns:
            RepositoryResult containing the created event or error
        """
        event_id = str(uuid.uuid4())
        log = self.logger.bind(method="add", event_id=event_id)

        # Validate input
        if not event_data.content:
            return RepositoryResult.validation_error(
                "Event content cannot be empty",
                details={"field": "content"}
            )

        # Build query
        try:
            query, params = self.query_builder.build_add_query(
                event_id=event_id,
                content=event_data.content,
                metadata=event_data.metadata,
                embedding=event_data.embedding,
                timestamp=event_data.timestamp
            )
        except Exception as e:
            log.error(f"Failed to build query: {e}")
            return RepositoryResult.database_error(
                "Failed to build insert query",
                cause=e
            )

        # Execute query
        try:
            async with self.engine.connect() as conn:
                async with conn.begin():
                    result = await conn.execute(query, params)
                    row = result.mappings().first()

                    if not row:
                        return RepositoryResult.database_error(
                            "No data returned from insert"
                        )

                    event = EventModel.from_db_record(row)
                    log.info("Event added successfully")
                    return RepositoryResult.ok(event)

        except Exception as e:
            log.error(f"Database error: {e}", exc_info=True)
            return RepositoryResult.database_error(
                f"Failed to add event: {str(e)}",
                cause=e
            )

    async def get_by_id(self, event_id: uuid.UUID) -> RepositoryResult[Optional[EventModel]]:
        """
        Get event by ID using Result pattern.

        Args:
            event_id: Event ID to search for

        Returns:
            RepositoryResult containing the event, None if not found, or error
        """
        log = self.logger.bind(method="get_by_id", event_id=str(event_id))

        # Build query
        query, params = self.query_builder.build_get_by_id_query(str(event_id))

        # Execute query
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query, params)
                row = result.mappings().first()

                if not row:
                    log.debug("Event not found")
                    return RepositoryResult.ok(None)

                event = EventModel.from_db_record(row)
                log.debug("Event retrieved successfully")
                return RepositoryResult.ok(event)

        except Exception as e:
            log.error(f"Database error: {e}", exc_info=True)
            return RepositoryResult.database_error(
                f"Failed to get event: {str(e)}",
                cause=e
            )

    async def update_metadata(
        self,
        event_id: uuid.UUID,
        metadata_update: Dict[str, Any]
    ) -> RepositoryResult[Optional[EventModel]]:
        """
        Update event metadata using Result pattern.

        Args:
            event_id: Event ID to update
            metadata_update: Metadata to merge

        Returns:
            RepositoryResult containing updated event or error
        """
        log = self.logger.bind(
            method="update_metadata",
            event_id=str(event_id),
            update_keys=list(metadata_update.keys())
        )

        # Validate input
        if not metadata_update:
            return RepositoryResult.validation_error(
                "Metadata update cannot be empty",
                details={"field": "metadata_update"}
            )

        # Build query
        query, params = self.query_builder.build_update_metadata_query(
            str(event_id),
            metadata_update
        )

        # Execute query
        try:
            async with self.engine.connect() as conn:
                async with conn.begin():
                    result = await conn.execute(query, params)
                    row = result.mappings().first()

                    if not row:
                        log.debug("Event not found for update")
                        return RepositoryResult.not_found(
                            f"Event {event_id} not found"
                        )

                    event = EventModel.from_db_record(row)
                    log.info("Metadata updated successfully")
                    return RepositoryResult.ok(event)

        except Exception as e:
            log.error(f"Database error: {e}", exc_info=True)
            return RepositoryResult.database_error(
                f"Failed to update metadata: {str(e)}",
                cause=e
            )

    async def delete(self, event_id: uuid.UUID) -> RepositoryResult[bool]:
        """
        Delete event using Result pattern.

        Args:
            event_id: Event ID to delete

        Returns:
            RepositoryResult containing True if deleted, False if not found, or error
        """
        log = self.logger.bind(method="delete", event_id=str(event_id))

        # Build query
        query, params = self.query_builder.build_delete_query(str(event_id))

        # Execute query
        try:
            async with self.engine.connect() as conn:
                async with conn.begin():
                    result = await conn.execute(query, params)
                    deleted = result.rowcount > 0

                    if deleted:
                        log.info("Event deleted successfully")
                    else:
                        log.debug("Event not found for deletion")

                    return RepositoryResult.ok(deleted)

        except Exception as e:
            log.error(f"Database error: {e}", exc_info=True)
            return RepositoryResult.database_error(
                f"Failed to delete event: {str(e)}",
                cause=e
            )

    async def search_with_filters(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> RepositoryResult[List[EventModel]]:
        """
        Search events with metadata filters using Result pattern.

        Args:
            metadata: Metadata filters
            limit: Maximum results
            offset: Pagination offset

        Returns:
            RepositoryResult containing list of events or error
        """
        log = self.logger.bind(
            method="search_with_filters",
            has_metadata=metadata is not None,
            limit=limit,
            offset=offset
        )

        # Build appropriate query
        if metadata:
            query, params = self.query_builder.build_filter_by_metadata_query(
                metadata,
                limit,
                offset
            )
        else:
            # Simple query without filters
            query, params = self.query_builder.build_search_vector_query(
                limit=limit,
                offset=offset
            )

        # Execute query
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query, params)
                rows = result.mappings().all()

                events = [EventModel.from_db_record(row) for row in rows]
                log.info(f"Found {len(events)} events")
                return RepositoryResult.ok(events)

        except Exception as e:
            log.error(f"Search failed: {e}", exc_info=True)
            return RepositoryResult.database_error(
                f"Search failed: {str(e)}",
                cause=e
            )


# Example usage in a service
class EventServiceWithResult:
    """Example service using repository with Result pattern."""

    def __init__(self, repository: EventRepositoryWithResult):
        self.repository = repository
        self.logger = get_repository_logger("event_service")

    async def create_event_with_validation(
        self,
        content: Dict[str, Any]
    ) -> RepositoryResult[EventModel]:
        """
        Create event with additional validation.

        This shows how Result pattern can be chained.
        """
        # Validate content has required fields
        if "type" not in content:
            return RepositoryResult.validation_error(
                "Content must have 'type' field",
                details={"missing_field": "type"}
            )

        # Create event data
        event_data = EventCreate(
            content=content,
            metadata={"created_by": "service", "validated": True}
        )

        # Add event and transform result
        result = await self.repository.add(event_data)

        # Chain additional processing if successful
        return result.map(lambda event: {
            **event.dict(),
            "processed": True
        })

    async def get_or_create_event(
        self,
        event_id: uuid.UUID,
        default_content: Dict[str, Any]
    ) -> RepositoryResult[EventModel]:
        """
        Get existing event or create new one.

        This shows how Result pattern handles fallback logic cleanly.
        """
        # Try to get existing event
        result = await self.repository.get_by_id(event_id)

        if result.is_err():
            return result  # Propagate error

        existing_event = result.unwrap()
        if existing_event:
            return RepositoryResult.ok(existing_event)

        # Event doesn't exist, create it
        event_data = EventCreate(content=default_content)
        return await self.repository.add(event_data)