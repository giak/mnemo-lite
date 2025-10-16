"""
NodeRepository for EPIC-06 Phase 2 Story 4.

Manages CRUD operations for code graph nodes.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql import text

from db.repositories.base import RepositoryError
from models.graph_models import NodeCreate, NodeModel

logger = logging.getLogger(__name__)


class NodeQueryBuilder:
    """Builds SQL queries for NodeRepository."""

    def build_create_query(self, node_data: NodeCreate) -> Tuple[TextClause, Dict[str, Any]]:
        """Build INSERT query for node."""
        query_str = text("""
            INSERT INTO nodes (
                node_id, node_type, label, properties, created_at
            )
            VALUES (
                :node_id, :node_type, :label, CAST(:properties AS JSONB), NOW()
            )
            RETURNING *
        """)

        node_id = str(uuid.uuid4())
        params = {
            "node_id": node_id,
            "node_type": node_data.node_type,
            "label": node_data.label,
            "properties": json.dumps(node_data.properties),
        }

        return query_str, params

    def build_get_by_id_query(self, node_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT by ID query."""
        query_str = text("SELECT * FROM nodes WHERE node_id = :node_id")
        params = {"node_id": str(node_id)}
        return query_str, params

    def build_get_by_chunk_id_query(self, chunk_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT by chunk_id (stored in properties)."""
        query_str = text("""
            SELECT * FROM nodes
            WHERE properties->>'chunk_id' = :chunk_id
        """)
        params = {"chunk_id": str(chunk_id)}
        return query_str, params

    def build_search_by_label_query(
        self,
        label: str,
        node_type: Optional[str] = None
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT by label with optional type filter."""
        conditions = ["label = :label"]
        params = {"label": label}

        if node_type:
            conditions.append("node_type = :node_type")
            params["node_type"] = node_type

        where_clause = " AND ".join(conditions)
        query_str = text(f"""
            SELECT * FROM nodes
            WHERE {where_clause}
        """)

        return query_str, params

    def build_delete_query(self, node_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build DELETE query."""
        query_str = text("DELETE FROM nodes WHERE node_id = :node_id")
        params = {"node_id": str(node_id)}
        return query_str, params


class NodeRepository:
    """Manages CRUD operations for code graph nodes."""

    def __init__(self, engine: AsyncEngine):
        """Initialize repository with AsyncEngine."""
        self.engine = engine
        self.query_builder = NodeQueryBuilder()
        self.logger = logging.getLogger(__name__)
        self.logger.info("NodeRepository initialized.")

    async def _execute_query(
        self,
        query: TextClause,
        params: Dict[str, Any],
        is_mutation: bool = False
    ) -> Result:
        """Execute query with connection and transaction management."""
        async with self.engine.connect() as connection:
            transaction = await connection.begin() if is_mutation else None
            try:
                self.logger.debug(f"Executing query: {str(query)}")
                self.logger.debug(f"With params: {params}")
                result = await connection.execute(query, params)

                if transaction:
                    await transaction.commit()
                return result
            except Exception as e:
                if transaction:
                    await transaction.rollback()
                self.logger.error(f"Query execution failed: {e}", exc_info=True)
                raise RepositoryError(f"Query execution failed: {e}") from e

    async def create(self, node_data: NodeCreate) -> NodeModel:
        """Create a new node."""
        query, params = self.query_builder.build_create_query(node_data)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            if not row:
                raise RepositoryError("Failed to create node: No data returned.")
            return NodeModel.from_db_record(row)
        except Exception as e:
            self.logger.error(f"Failed to create node: {e}", exc_info=True)
            raise RepositoryError(f"Failed to create node: {e}") from e

    async def create_code_node(
        self,
        node_type: str,
        label: str,
        chunk_id: uuid.UUID,
        file_path: str,
        metadata: Dict[str, Any]
    ) -> NodeModel:
        """
        Create node for code chunk.

        Convenience method that includes code-specific properties.
        """
        properties = {
            "chunk_id": str(chunk_id),
            "file_path": file_path,
            **metadata
        }

        node_data = NodeCreate(
            node_type=node_type,
            label=label,
            properties=properties
        )

        return await self.create(node_data)

    async def get_by_id(self, node_id: uuid.UUID) -> Optional[NodeModel]:
        """Get node by ID."""
        query, params = self.query_builder.build_get_by_id_query(node_id)
        try:
            db_result = await self._execute_query(query, params)
            row = db_result.mappings().first()
            return NodeModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get node {node_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get node {node_id}: {e}") from e

    async def get_by_chunk_id(self, chunk_id: uuid.UUID) -> Optional[NodeModel]:
        """Get node associated with code chunk."""
        query, params = self.query_builder.build_get_by_chunk_id_query(chunk_id)
        try:
            db_result = await self._execute_query(query, params)
            row = db_result.mappings().first()
            return NodeModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get node by chunk_id {chunk_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get node by chunk_id {chunk_id}: {e}") from e

    async def search_by_label(
        self,
        label: str,
        node_type: Optional[str] = None
    ) -> List[NodeModel]:
        """Search nodes by label (for resolution)."""
        query, params = self.query_builder.build_search_by_label_query(label, node_type)
        try:
            db_result = await self._execute_query(query, params)
            rows = db_result.mappings().all()
            return [NodeModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to search nodes by label '{label}': {e}", exc_info=True)
            raise RepositoryError(f"Failed to search nodes by label '{label}': {e}") from e

    async def delete(self, node_id: uuid.UUID) -> bool:
        """Delete node by ID."""
        query, params = self.query_builder.build_delete_query(node_id)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            return db_result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to delete node {node_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to delete node {node_id}: {e}") from e
