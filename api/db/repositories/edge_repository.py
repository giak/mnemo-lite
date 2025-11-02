"""
EdgeRepository for EPIC-06 Phase 2 Story 4.

Manages CRUD operations for code dependency edges.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql import text

from db.repositories.base import RepositoryError
from models.graph_models import EdgeCreate, EdgeModel

logger = logging.getLogger(__name__)


class EdgeQueryBuilder:
    """Builds SQL queries for EdgeRepository."""

    def build_create_query(self, edge_data: EdgeCreate) -> Tuple[TextClause, Dict[str, Any]]:
        """Build INSERT query for edge."""
        query_str = text("""
            INSERT INTO edges (
                edge_id, source_node_id, target_node_id, relation_type, properties, created_at
            )
            VALUES (
                :edge_id, :source_node_id, :target_node_id, :relation_type, CAST(:properties AS JSONB), NOW()
            )
            RETURNING *
        """)

        edge_id = str(uuid.uuid4())
        params = {
            "edge_id": edge_id,
            "source_node_id": str(edge_data.source_node_id),
            "target_node_id": str(edge_data.target_node_id),
            "relation_type": edge_data.relation_type,
            "properties": json.dumps(edge_data.properties),
        }

        return query_str, params

    def build_get_by_id_query(self, edge_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT by ID query."""
        query_str = text("SELECT * FROM edges WHERE edge_id = :edge_id")
        params = {"edge_id": str(edge_id)}
        return query_str, params

    def build_get_outbound_query(
        self,
        node_id: uuid.UUID,
        relationship: Optional[str] = None
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT outbound edges query."""
        conditions = ["source_node_id = :node_id"]
        params = {"node_id": str(node_id)}

        if relationship:
            conditions.append("relation_type = :relation_type")
            params["relation_type"] = relationship

        where_clause = " AND ".join(conditions)
        query_str = text(f"""
            SELECT * FROM edges
            WHERE {where_clause}
        """)

        return query_str, params

    def build_get_inbound_query(
        self,
        node_id: uuid.UUID,
        relationship: Optional[str] = None
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT inbound edges query."""
        conditions = ["target_node_id = :node_id"]
        params = {"node_id": str(node_id)}

        if relationship:
            conditions.append("relation_type = :relation_type")
            params["relation_type"] = relationship

        where_clause = " AND ".join(conditions)
        query_str = text(f"""
            SELECT * FROM edges
            WHERE {where_clause}
        """)

        return query_str, params

    def build_delete_query(self, edge_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build DELETE query."""
        query_str = text("DELETE FROM edges WHERE edge_id = :edge_id")
        params = {"edge_id": str(edge_id)}
        return query_str, params


class EdgeRepository:
    """Manages CRUD operations for code dependency edges."""

    def __init__(self, engine: AsyncEngine):
        """Initialize repository with AsyncEngine."""
        self.engine = engine
        self.query_builder = EdgeQueryBuilder()
        self.logger = logging.getLogger(__name__)
        self.logger.info("EdgeRepository initialized.")

    async def _execute_query(
        self,
        query: TextClause,
        params: Dict[str, Any],
        is_mutation: bool = False,
        connection: Optional[AsyncConnection] = None,
    ) -> Result:
        """
        Execute query with connection and transaction management.

        EPIC-12 Story 12.2: Added connection parameter for external transaction support.
        """
        if connection:
            # Use provided connection (caller manages transaction)
            try:
                self.logger.debug(f"Executing query with external connection: {str(query)}")
                self.logger.debug(f"With params: {params}")
                result = await connection.execute(query, params)
                return result
            except Exception as e:
                # Don't rollback - caller manages transaction
                self.logger.error(f"Query execution failed: {e}", exc_info=True)
                raise RepositoryError(f"Query execution failed: {e}") from e
        else:
            # Create own connection and transaction (backward compatible)
            async with self.engine.connect() as conn:
                transaction = await conn.begin() if is_mutation else None
                try:
                    self.logger.debug(f"Executing query: {str(query)}")
                    self.logger.debug(f"With params: {params}")
                    result = await conn.execute(query, params)

                    if transaction:
                        await transaction.commit()
                    return result
                except Exception as e:
                    if transaction:
                        await transaction.rollback()
                    self.logger.error(f"Query execution failed: {e}", exc_info=True)
                    raise RepositoryError(f"Query execution failed: {e}") from e

    async def create(
        self,
        edge_data: EdgeCreate,
        connection: Optional[AsyncConnection] = None,
    ) -> EdgeModel:
        """
        Create a new edge.

        EPIC-12 Story 12.2: Added connection parameter for transaction support.
        """
        query, params = self.query_builder.build_create_query(edge_data)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True, connection=connection)
            row = db_result.mappings().first()
            if not row:
                raise RepositoryError("Failed to create edge: No data returned.")
            return EdgeModel.from_db_record(row)
        except Exception as e:
            self.logger.error(f"Failed to create edge: {e}", exc_info=True)
            raise RepositoryError(f"Failed to create edge: {e}") from e

    async def create_dependency_edge(
        self,
        source_node: uuid.UUID,
        target_node: uuid.UUID,
        relationship: str,
        metadata: Optional[Dict[str, Any]] = None,
        connection: Optional[AsyncConnection] = None,
    ) -> EdgeModel:
        """
        Create edge representing code dependency.

        Convenience method for code graphs.

        EPIC-12 Story 12.2: Added connection parameter for transaction support.
        """
        edge_data = EdgeCreate(
            source_node_id=source_node,
            target_node_id=target_node,
            relation_type=relationship,
            properties=metadata if metadata else {}
        )

        return await self.create(edge_data, connection=connection)

    async def get_by_id(self, edge_id: uuid.UUID) -> Optional[EdgeModel]:
        """Get edge by ID."""
        query, params = self.query_builder.build_get_by_id_query(edge_id)
        try:
            db_result = await self._execute_query(query, params)
            row = db_result.mappings().first()
            return EdgeModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get edge {edge_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get edge {edge_id}: {e}") from e

    async def get_by_repository(self, repository: str) -> List[EdgeModel]:
        """
        Get all edges for a repository.

        Args:
            repository: Repository name

        Returns:
            List of edges for the repository
        """
        from sqlalchemy import text
        query = text("""
            SELECT e.* FROM edges e
            JOIN nodes n ON e.source_node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
            ORDER BY e.created_at
        """)
        params = {"repository": repository}

        try:
            db_result = await self._execute_query(query, params)
            rows = db_result.mappings().all()
            return [EdgeModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get edges for repository '{repository}': {e}", exc_info=True)
            raise RepositoryError(f"Failed to get edges for repository '{repository}': {e}") from e

    async def get_outbound_edges(
        self,
        node_id: uuid.UUID,
        relationship: Optional[str] = None
    ) -> List[EdgeModel]:
        """Get all edges leaving node (outbound)."""
        query, params = self.query_builder.build_get_outbound_query(node_id, relationship)
        try:
            db_result = await self._execute_query(query, params)
            rows = db_result.mappings().all()
            return [EdgeModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get outbound edges for node {node_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get outbound edges for node {node_id}: {e}") from e

    async def get_inbound_edges(
        self,
        node_id: uuid.UUID,
        relationship: Optional[str] = None
    ) -> List[EdgeModel]:
        """Get all edges entering node (inbound)."""
        query, params = self.query_builder.build_get_inbound_query(node_id, relationship)
        try:
            db_result = await self._execute_query(query, params)
            rows = db_result.mappings().all()
            return [EdgeModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to get inbound edges for node {node_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get inbound edges for node {node_id}: {e}") from e

    async def delete(
        self,
        edge_id: uuid.UUID,
        connection: Optional[AsyncConnection] = None,
    ) -> bool:
        """
        Delete edge by ID.

        EPIC-12 Story 12.2: Added connection parameter for transaction support.
        """
        query, params = self.query_builder.build_delete_query(edge_id)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True, connection=connection)
            return db_result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to delete edge {edge_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to delete edge {edge_id}: {e}") from e

    async def delete_by_source_node(
        self,
        source_node_id: uuid.UUID,
        connection: Optional[AsyncConnection] = None,
    ) -> int:
        """
        Delete all edges originating from a node.

        EPIC-12 Story 12.2: New bulk delete method for atomic multi-step operations.

        Args:
            source_node_id: Node ID to delete edges from
            connection: Optional external connection for transaction support

        Returns:
            Number of deleted edges
        """
        query = text("""
            DELETE FROM edges
            WHERE source_node_id = :source_node_id
        """)
        params = {"source_node_id": str(source_node_id)}

        try:
            self.logger.info(f"Deleting all edges from node: {source_node_id}")
            db_result = await self._execute_query(query, params, is_mutation=True, connection=connection)
            rows_affected = db_result.rowcount
            self.logger.info(f"Deleted {rows_affected} edges from node {source_node_id}")
            return rows_affected
        except Exception as e:
            self.logger.error(f"Failed to delete edges from node {source_node_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to delete edges from node {source_node_id}: {e}") from e
