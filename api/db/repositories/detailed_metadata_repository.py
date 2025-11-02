"""
Repository for detailed_metadata table operations.
"""
import logging
import json
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from models.metadata_models import DetailedMetadata

logger = logging.getLogger(__name__)


class DetailedMetadataRepository:
    """Repository for CRUD operations on detailed_metadata table."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def create(
        self,
        node_id: UUID,
        chunk_id: UUID,
        metadata: dict,
        version: int = 1,
        connection=None
    ) -> DetailedMetadata:
        """
        Create detailed metadata entry.

        Args:
            node_id: Node UUID
            chunk_id: Code chunk UUID
            metadata: Metadata payload (calls, imports, signature, context)
            version: Version number (default 1)
            connection: Optional external connection for transaction

        Returns:
            DetailedMetadata instance
        """
        query = text("""
            INSERT INTO detailed_metadata (node_id, chunk_id, metadata, version)
            VALUES (:node_id, :chunk_id, CAST(:metadata AS JSONB), :version)
            RETURNING metadata_id, node_id, chunk_id, metadata, version, created_at, updated_at
        """)

        params = {
            "node_id": str(node_id),
            "chunk_id": str(chunk_id),
            "metadata": json.dumps(metadata),  # Proper JSON serialization
            "version": version
        }

        if connection:
            result = await connection.execute(query, params)
            row = result.fetchone()
        else:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

        return DetailedMetadata(
            metadata_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            metadata=row[3],
            version=row[4],
            created_at=row[5],
            updated_at=row[6]
        )

    async def get_latest_by_node(self, node_id: UUID) -> Optional[DetailedMetadata]:
        """
        Get latest version of metadata for a node.

        Args:
            node_id: Node UUID

        Returns:
            DetailedMetadata instance or None
        """
        query = text("""
            SELECT metadata_id, node_id, chunk_id, metadata, version, created_at, updated_at
            FROM detailed_metadata
            WHERE node_id = :node_id
            ORDER BY version DESC
            LIMIT 1
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"node_id": str(node_id)})
            row = result.fetchone()

        if not row:
            return None

        return DetailedMetadata(
            metadata_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            metadata=row[3],
            version=row[4],
            created_at=row[5],
            updated_at=row[6]
        )

    async def get_by_repository(self, repository: str, version: int = 1) -> List[DetailedMetadata]:
        """
        Get all metadata entries for a repository.

        Args:
            repository: Repository name
            version: Version number (default 1 = latest indexed version)

        Returns:
            List of DetailedMetadata instances
        """
        query = text("""
            SELECT dm.metadata_id, dm.node_id, dm.chunk_id, dm.metadata, dm.version, dm.created_at, dm.updated_at
            FROM detailed_metadata dm
            JOIN nodes n ON dm.node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND dm.version = :version
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"repository": repository, "version": version})
            rows = result.fetchall()

        return [
            DetailedMetadata(
                metadata_id=row[0],
                node_id=row[1],
                chunk_id=row[2],
                metadata=row[3],
                version=row[4],
                created_at=row[5],
                updated_at=row[6]
            )
            for row in rows
        ]
