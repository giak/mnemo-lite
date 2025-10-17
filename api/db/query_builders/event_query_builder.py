"""
Query builder for Event repository operations.

Extracts all query construction logic from EventRepository to simplify the repository class.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.sql import text
from sqlalchemy.sql.expression import TextClause

from .base_query_builder import BaseQueryBuilder


class EventQueryBuilder(BaseQueryBuilder):
    """Builds SQL queries for EventRepository using SQLAlchemy Core."""

    def __init__(self, vector_dimension: int = 768):
        """
        Initialize the event query builder.

        Args:
            vector_dimension: Expected dimension for embedding vectors (default: 768 for nomic-embed-text-v1.5)
        """
        super().__init__()
        self.vector_dimension = vector_dimension

    def _format_embedding_for_db(self, embedding: Optional[List[float]]) -> Optional[str]:
        """
        Format embedding for PostgreSQL.

        Args:
            embedding: List of floats or None

        Returns:
            Formatted string for pgvector or None
        """
        if embedding is None:
            return None

        if not isinstance(embedding, list):
            self.logger.warning(f"Expected list for embedding, got {type(embedding)}")
            return None

        # Format as PostgreSQL array literal
        return f"[{','.join(map(str, embedding))}]"

    def build_add_query(
        self,
        event_id: str,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        timestamp: Optional[datetime] = None
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build INSERT query for adding an event.

        Args:
            event_id: UUID string for the event
            content: Event content dictionary
            metadata: Optional metadata dictionary
            embedding: Optional embedding vector
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Query and parameters tuple
        """
        query_str = text("""
            INSERT INTO events (id, content, metadata, embedding, timestamp)
            VALUES (:id, CAST(:content AS JSONB), CAST(:metadata AS JSONB), :embedding, :timestamp)
            RETURNING id, content, metadata, embedding, timestamp
        """)

        params = {
            "id": event_id,
            "content": self._safe_json_dumps(content),
            "metadata": self._safe_json_dumps(metadata) if metadata else None,
            "embedding": self._format_embedding_for_db(embedding),
            "timestamp": timestamp if timestamp else datetime.now(timezone.utc)
        }

        self._log_query(query_str, params, "add event")
        return query_str, params

    def build_get_by_id_query(self, event_id: str) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build SELECT query to get event by ID.

        Args:
            event_id: Event ID to search for

        Returns:
            Query and parameters tuple
        """
        query_str = text("""
            SELECT id, timestamp, content, metadata, embedding
            FROM events
            WHERE id = :event_id
        """)

        params = {"event_id": event_id}

        self._log_query(query_str, params, "get by id")
        return query_str, params

    def build_update_metadata_query(
        self,
        event_id: str,
        metadata_update: Dict[str, Any]
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build UPDATE query to merge metadata.

        Args:
            event_id: Event ID to update
            metadata_update: Metadata to merge

        Returns:
            Query and parameters tuple
        """
        query_str = text("""
            UPDATE events
            SET metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:metadata_update AS jsonb)
            WHERE id = :event_id
            RETURNING id, timestamp, content, metadata, embedding
        """)

        params = {
            "event_id": event_id,
            "metadata_update": self._safe_json_dumps(metadata_update)
        }

        self._log_query(query_str, params, "update metadata")
        return query_str, params

    def build_delete_query(self, event_id: str) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build DELETE query by ID.

        Args:
            event_id: Event ID to delete

        Returns:
            Query and parameters tuple
        """
        query_str = text("DELETE FROM events WHERE id = :event_id")
        params = {"event_id": event_id}

        self._log_query(query_str, params, "delete event")
        return query_str, params

    def build_filter_by_metadata_query(
        self,
        metadata_criteria: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build SELECT query with metadata filters.

        Args:
            metadata_criteria: Metadata criteria to filter by
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Query and parameters tuple

        Raises:
            ValueError: If metadata_criteria is empty
        """
        if not metadata_criteria:
            raise ValueError("Metadata criteria cannot be empty")

        query_str = text("""
            SELECT id, content, metadata, embedding, timestamp
            FROM events
            WHERE metadata @> CAST(:criteria AS jsonb)
            ORDER BY timestamp DESC
            LIMIT :lim OFFSET :off
        """)

        params = {
            "criteria": self._safe_json_dumps(metadata_criteria),
            "lim": limit,
            "off": offset
        }

        self._log_query(query_str, params, "filter by metadata")
        return query_str, params

    def build_search_vector_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = None
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build combined search query (vector, metadata, time).

        Args:
            vector: Embedding vector for semantic search
            metadata: Metadata filters
            ts_start: Start timestamp
            ts_end: End timestamp
            limit: Maximum results
            offset: Pagination offset
            distance_threshold: L2 distance threshold

        Returns:
            Query and parameters tuple

        Raises:
            ValueError: If vector dimension mismatch
        """
        params_dict: Dict[str, Any] = {
            "lim": limit,
            "off": offset
        }

        select_parts = ["id", "timestamp", "content", "metadata", "embedding"]
        conditions = []
        order_by_clause = "ORDER BY timestamp DESC"

        # Handle vector search
        if vector is not None:
            if len(vector) != self.vector_dimension:
                raise ValueError(
                    f"Vector dimension mismatch. Expected {self.vector_dimension}, got {len(vector)}"
                )

            select_parts.append("embedding <-> :vec_query AS similarity_score")
            params_dict["vec_query"] = self._format_embedding_for_db(vector)

            if distance_threshold is not None:
                conditions.append("embedding <-> :vec_query <= :dist_threshold")
                params_dict["dist_threshold"] = distance_threshold

            order_by_clause = "ORDER BY similarity_score ASC"
        else:
            select_parts.append("NULL AS similarity_score")

        # Handle metadata filter
        if metadata:
            conditions.append("metadata @> :md_filter ::jsonb")
            params_dict["md_filter"] = self._safe_json_dumps(metadata)

        # Handle time filters
        if ts_start:
            conditions.append("timestamp >= :ts_start")
            params_dict["ts_start"] = ts_start
        if ts_end:
            conditions.append("timestamp <= :ts_end")
            params_dict["ts_end"] = ts_end

        # Build query
        select_clause = "SELECT " + ", ".join(select_parts)
        from_clause = "FROM events"
        where_clause = self._build_where_clause(conditions)
        pagination_clause = self._build_pagination(limit, offset)

        query_str = f"{select_clause} {from_clause} {where_clause} {order_by_clause} {pagination_clause}"
        query = text(query_str)

        self._log_query(query, params_dict, "search vector")
        return query, params_dict

    def build_count_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
        distance_threshold: Optional[float] = None
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build COUNT query for total results.

        Uses same conditions as build_search_vector_query but without ORDER BY or LIMIT.

        Args:
            vector: Embedding vector for semantic search
            metadata: Metadata filters
            ts_start: Start timestamp
            ts_end: End timestamp
            distance_threshold: L2 distance threshold

        Returns:
            Query and parameters tuple

        Raises:
            ValueError: If vector dimension mismatch
        """
        params_dict: Dict[str, Any] = {}
        conditions = []

        # Handle vector filter
        if vector is not None:
            if len(vector) != self.vector_dimension:
                raise ValueError(
                    f"Vector dimension mismatch. Expected {self.vector_dimension}, got {len(vector)}"
                )

            params_dict["vec_query"] = self._format_embedding_for_db(vector)

            if distance_threshold is not None:
                conditions.append("embedding <-> :vec_query <= :dist_threshold")
                params_dict["dist_threshold"] = distance_threshold

        # Handle metadata filter
        if metadata:
            conditions.append("metadata @> :md_filter ::jsonb")
            params_dict["md_filter"] = self._safe_json_dumps(metadata)

        # Handle time filters
        if ts_start:
            conditions.append("timestamp >= :ts_start")
            params_dict["ts_start"] = ts_start
        if ts_end:
            conditions.append("timestamp <= :ts_end")
            params_dict["ts_end"] = ts_end

        # Build query
        select_clause = "SELECT COUNT(*) as total"
        from_clause = "FROM events"
        where_clause = self._build_where_clause(conditions)

        query_str = f"{select_clause} {from_clause} {where_clause}"
        query = text(query_str)

        self._log_query(query, params_dict, "count query")
        return query, params_dict

    def build_update_embedding_query(
        self,
        event_id: str,
        embedding: List[float]
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build UPDATE query to set embedding.

        Args:
            event_id: Event ID to update
            embedding: New embedding vector

        Returns:
            Query and parameters tuple
        """
        query_str = text("""
            UPDATE events
            SET embedding = :embedding
            WHERE id = :event_id
            RETURNING id
        """)

        params = {
            "event_id": event_id,
            "embedding": self._format_embedding_for_db(embedding)
        }

        self._log_query(query_str, params, "update embedding")
        return query_str, params