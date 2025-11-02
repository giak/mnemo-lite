"""
Repository for edge_weights table operations.
"""
import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from models.metadata_models import EdgeWeight

logger = logging.getLogger(__name__)


class EdgeWeightsRepository:
    """Repository for edge weight and importance metrics."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def create_or_update(
        self,
        edge_id: UUID,
        call_count: int = 1,
        importance_score: float = 1.0,
        is_critical_path: bool = False,
        version: int = 1,
        connection=None
    ) -> EdgeWeight:
        """
        Create or update edge weight entry.

        Args:
            edge_id: Edge UUID
            call_count: Number of unique calls
            importance_score: Importance score (0-1)
            is_critical_path: Whether edge is on critical path
            version: Version number
            connection: Optional external connection for transaction

        Returns:
            EdgeWeight instance
        """
        # Use UPSERT to handle create or update
        query = text("""
            INSERT INTO edge_weights (edge_id, call_count, importance_score, is_critical_path, version)
            VALUES (:edge_id, :call_count, :importance, :is_critical, :version)
            ON CONFLICT (edge_id, version) DO UPDATE SET
                call_count = :call_count,
                importance_score = :importance,
                is_critical_path = :is_critical,
                updated_at = NOW()
            RETURNING weight_id, edge_id, call_count, importance_score, is_critical_path, version, updated_at
        """)

        params = {
            "edge_id": str(edge_id),
            "call_count": call_count,
            "importance": importance_score,
            "is_critical": is_critical_path,
            "version": version
        }

        if connection:
            result = await connection.execute(query, params)
            row = result.fetchone()
        else:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

        return EdgeWeight(
            weight_id=row[0],
            edge_id=row[1],
            call_count=row[2],
            importance_score=row[3],
            is_critical_path=row[4],
            version=row[5],
            updated_at=row[6]
        )

    async def get_by_edge(self, edge_id: UUID, version: int = 1) -> Optional[EdgeWeight]:
        """
        Get edge weight by edge ID.

        Args:
            edge_id: Edge UUID
            version: Version number (default 1)

        Returns:
            EdgeWeight instance or None
        """
        query = text("""
            SELECT weight_id, edge_id, call_count, importance_score, is_critical_path, version, updated_at
            FROM edge_weights
            WHERE edge_id = :edge_id AND version = :version
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"edge_id": str(edge_id), "version": version})
            row = result.fetchone()

        if not row:
            return None

        return EdgeWeight(
            weight_id=row[0],
            edge_id=row[1],
            call_count=row[2],
            importance_score=row[3],
            is_critical_path=row[4],
            version=row[5],
            updated_at=row[6]
        )

    async def get_by_repository(self, repository: str, version: int = 1) -> List[EdgeWeight]:
        """
        Get all edge weights for a repository.

        Args:
            repository: Repository name
            version: Version number (default 1)

        Returns:
            List of EdgeWeight instances
        """
        query = text("""
            SELECT ew.weight_id, ew.edge_id, ew.call_count, ew.importance_score,
                   ew.is_critical_path, ew.version, ew.updated_at
            FROM edge_weights ew
            JOIN edges e ON ew.edge_id = e.edge_id
            JOIN nodes n ON e.source_node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND ew.version = :version
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"repository": repository, "version": version})
            rows = result.fetchall()

        return [
            EdgeWeight(
                weight_id=row[0],
                edge_id=row[1],
                call_count=row[2],
                importance_score=row[3],
                is_critical_path=row[4],
                version=row[5],
                updated_at=row[6]
            )
            for row in rows
        ]
