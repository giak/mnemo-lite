"""
Memory Repository - CRUD operations for memories table.

EPIC-23 Story 23.3: Database operations for persistent memory storage.
Implements create, read, update, delete (soft and hard), list, and search operations.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
import json

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
import structlog

from db.repositories.base import RepositoryError
from mnemo_mcp.models.memory_models import (
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoryFilters,
)


class MemoryRepository:
    """Repository for memory database operations using SQLAlchemy Core."""

    def __init__(self, engine: AsyncEngine):
        """
        Initialize the memory repository.

        Args:
            engine: SQLAlchemy async engine for database operations
        """
        self.engine = engine
        self.logger = structlog.get_logger("memory_repository")
        self.logger.info("MemoryRepository initialized")

    async def create(
        self,
        memory_create: MemoryCreate,
        embedding: Optional[List[float]] = None
    ) -> Memory:
        """
        Create a new memory in the database.

        Args:
            memory_create: Memory creation data
            embedding: Optional embedding vector (768D)

        Returns:
            Created Memory object with generated ID and timestamps

        Raises:
            RepositoryError: If creation fails (e.g., duplicate title+project_id)
        """
        try:
            memory_id = uuid.uuid4()
            now = datetime.now(timezone.utc)

            # Convert arrays and JSONB for PostgreSQL
            tags_array = f"ARRAY{memory_create.tags}::TEXT[]" if memory_create.tags else "ARRAY[]::TEXT[]"
            related_chunks_array = f"ARRAY[{','.join(str(c) for c in memory_create.related_chunks)}]::UUID[]" if memory_create.related_chunks else "ARRAY[]::UUID[]"
            resource_links_json = json.dumps(memory_create.resource_links)

            # Format embedding for pgvector
            embedding_str = f"'[{','.join(map(str, embedding))}]'::vector" if embedding else "NULL"

            query = text(f"""
                INSERT INTO memories (
                    id, title, content, created_at, updated_at,
                    memory_type, tags, author, project_id,
                    embedding, embedding_model,
                    related_chunks, resource_links
                )
                VALUES (
                    :id, :title, :content, :created_at, :updated_at,
                    :memory_type, {tags_array}, :author, :project_id,
                    {embedding_str}, :embedding_model,
                    {related_chunks_array}, :resource_links
                )
                RETURNING *
            """)

            params = {
                "id": str(memory_id),
                "title": memory_create.title,
                "content": memory_create.content,
                "created_at": now,
                "updated_at": now,
                "memory_type": memory_create.memory_type.value,
                "author": memory_create.author,
                "project_id": str(memory_create.project_id) if memory_create.project_id else None,
                "embedding_model": "nomic-embed-text-v1.5" if embedding else None,
                "resource_links": resource_links_json,
            }

            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

            if not row:
                raise RepositoryError("Failed to create memory (no row returned)")

            self.logger.info(
                "Memory created",
                memory_id=str(memory_id),
                title=memory_create.title,
                memory_type=memory_create.memory_type.value
            )

            return self._row_to_memory(row)

        except Exception as e:
            if "unique_title_per_project" in str(e):
                raise RepositoryError(
                    f"Memory with title '{memory_create.title}' already exists in this project"
                ) from e
            raise RepositoryError(f"Failed to create memory: {e}") from e

    async def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """
        Get a memory by UUID.

        Args:
            memory_id: Memory UUID as string

        Returns:
            Memory object if found and not deleted, None otherwise
        """
        try:
            query = text("""
                SELECT * FROM memories
                WHERE id = :memory_id AND deleted_at IS NULL
            """)

            async with self.engine.begin() as conn:
                result = await conn.execute(query, {"memory_id": memory_id})
                row = result.fetchone()

            if not row:
                return None

            return self._row_to_memory(row)

        except Exception as e:
            self.logger.error("Failed to get memory", memory_id=memory_id, error=str(e))
            raise RepositoryError(f"Failed to get memory: {e}") from e

    async def update(
        self,
        memory_id: str,
        memory_update: MemoryUpdate,
        regenerate_embedding: bool = False,
        new_embedding: Optional[List[float]] = None
    ) -> Optional[Memory]:
        """
        Update an existing memory (partial update).

        Args:
            memory_id: Memory UUID to update
            memory_update: Fields to update (only non-None fields updated)
            regenerate_embedding: Whether embedding was regenerated
            new_embedding: New embedding vector if regenerated

        Returns:
            Updated Memory object, or None if not found

        Raises:
            RepositoryError: If update fails
        """
        try:
            # Build dynamic UPDATE query based on provided fields
            update_fields = []
            params = {"memory_id": memory_id, "updated_at": datetime.now(timezone.utc)}

            if memory_update.title is not None:
                update_fields.append("title = :title")
                params["title"] = memory_update.title

            if memory_update.content is not None:
                update_fields.append("content = :content")
                params["content"] = memory_update.content

            if memory_update.memory_type is not None:
                update_fields.append("memory_type = :memory_type")
                params["memory_type"] = memory_update.memory_type.value

            if memory_update.tags is not None:
                tags_array = f"ARRAY{memory_update.tags}::TEXT[]" if memory_update.tags else "ARRAY[]::TEXT[]"
                update_fields.append(f"tags = {tags_array}")

            if memory_update.author is not None:
                update_fields.append("author = :author")
                params["author"] = memory_update.author

            if memory_update.related_chunks is not None:
                if memory_update.related_chunks:
                    chunks_array = f"ARRAY[{','.join(str(c) for c in memory_update.related_chunks)}]::UUID[]"
                else:
                    chunks_array = "ARRAY[]::UUID[]"
                update_fields.append(f"related_chunks = {chunks_array}")

            if memory_update.resource_links is not None:
                update_fields.append("resource_links = :resource_links::jsonb")
                params["resource_links"] = json.dumps(memory_update.resource_links)

            if regenerate_embedding and new_embedding:
                embedding_str = f"'[{','.join(map(str, new_embedding))}]'::vector"
                update_fields.append(f"embedding = {embedding_str}")
                update_fields.append("embedding_model = :embedding_model")
                params["embedding_model"] = "nomic-embed-text-v1.5"

            # Always update updated_at
            update_fields.append("updated_at = :updated_at")

            if not update_fields:
                # No fields to update
                return await self.get_by_id(memory_id)

            query = text(f"""
                UPDATE memories
                SET {', '.join(update_fields)}
                WHERE id = :memory_id AND deleted_at IS NULL
                RETURNING *
            """)

            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

            if not row:
                return None

            self.logger.info(
                "Memory updated",
                memory_id=memory_id,
                fields_updated=len(update_fields)
            )

            return self._row_to_memory(row)

        except Exception as e:
            if "unique_title_per_project" in str(e):
                raise RepositoryError(
                    f"Memory with title '{memory_update.title}' already exists in this project"
                ) from e
            raise RepositoryError(f"Failed to update memory: {e}") from e

    async def soft_delete(self, memory_id: str) -> bool:
        """
        Soft delete a memory (set deleted_at timestamp).

        Args:
            memory_id: Memory UUID to soft delete

        Returns:
            True if deleted, False if not found

        Raises:
            RepositoryError: If deletion fails
        """
        try:
            query = text("""
                UPDATE memories
                SET deleted_at = :deleted_at
                WHERE id = :memory_id AND deleted_at IS NULL
                RETURNING id
            """)

            params = {
                "memory_id": memory_id,
                "deleted_at": datetime.now(timezone.utc)
            }

            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

            success = row is not None

            if success:
                self.logger.info("Memory soft deleted", memory_id=memory_id)

            return success

        except Exception as e:
            raise RepositoryError(f"Failed to soft delete memory: {e}") from e

    async def delete_permanently(self, memory_id: str) -> bool:
        """
        Permanently delete a memory (hard delete from database).

        ⚠️ WARNING: This is irreversible. Should only be called after elicitation.

        Args:
            memory_id: Memory UUID to permanently delete

        Returns:
            True if deleted, False if not found

        Raises:
            RepositoryError: If deletion fails
        """
        try:
            query = text("""
                DELETE FROM memories
                WHERE id = :memory_id
                RETURNING id
            """)

            async with self.engine.begin() as conn:
                result = await conn.execute(query, {"memory_id": memory_id})
                row = result.fetchone()

            success = row is not None

            if success:
                self.logger.warning("Memory permanently deleted", memory_id=memory_id)

            return success

        except Exception as e:
            raise RepositoryError(f"Failed to permanently delete memory: {e}") from e

    async def list_memories(
        self,
        filters: Optional[MemoryFilters] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Memory], int]:
        """
        List memories with optional filters and pagination.

        Args:
            filters: Optional filters (project_id, memory_type, tags, etc.)
            limit: Max results to return (1-100)
            offset: Pagination offset

        Returns:
            Tuple of (list of Memory objects, total count)

        Raises:
            RepositoryError: If query fails
        """
        try:
            # Build WHERE clauses
            where_clauses = []
            params: Dict[str, Any] = {"limit": limit, "offset": offset}

            if not filters or not filters.include_deleted:
                where_clauses.append("deleted_at IS NULL")

            if filters:
                if filters.project_id:
                    where_clauses.append("project_id = :project_id")
                    params["project_id"] = str(filters.project_id)

                if filters.memory_type:
                    where_clauses.append("memory_type = :memory_type")
                    params["memory_type"] = filters.memory_type.value

                if filters.tags:
                    # tags array contains all specified tags (AND logic)
                    tag_conditions = [f":tag{i} = ANY(tags)" for i in range(len(filters.tags))]
                    where_clauses.append(f"({' AND '.join(tag_conditions)})")
                    for i, tag in enumerate(filters.tags):
                        params[f"tag{i}"] = tag

                if filters.author:
                    where_clauses.append("author = :author")
                    params["author"] = filters.author

                if filters.created_after:
                    where_clauses.append("created_at >= :created_after")
                    params["created_after"] = filters.created_after

                if filters.created_before:
                    where_clauses.append("created_at <= :created_before")
                    params["created_before"] = filters.created_before

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Count query
            count_query = text(f"""
                SELECT COUNT(*) as total
                FROM memories
                {where_sql}
            """)

            # Data query (exclude embeddings for bandwidth)
            list_query = text(f"""
                SELECT
                    id, title, content, created_at, updated_at,
                    memory_type, tags, author, project_id,
                    embedding_model, related_chunks, resource_links,
                    deleted_at
                FROM memories
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)

            async with self.engine.begin() as conn:
                # Get total count
                count_result = await conn.execute(count_query, params)
                total_row = count_result.fetchone()
                total_count = total_row[0] if total_row else 0

                # Get data
                result = await conn.execute(list_query, params)
                rows = result.fetchall()

            memories = [self._row_to_memory(row, exclude_embedding=True) for row in rows]

            self.logger.info(
                "Memories listed",
                count=len(memories),
                total=total_count,
                limit=limit,
                offset=offset
            )

            return memories, total_count

        except Exception as e:
            raise RepositoryError(f"Failed to list memories: {e}") from e

    async def search_by_vector(
        self,
        vector: List[float],
        filters: Optional[MemoryFilters] = None,
        limit: int = 5,
        offset: int = 0,
        distance_threshold: float = 1.0
    ) -> Tuple[List[Memory], int]:
        """
        Search memories by vector similarity.

        Args:
            vector: Query embedding vector (768D)
            filters: Optional filters
            limit: Max results (1-50)
            offset: Pagination offset
            distance_threshold: Max cosine distance (0.0-2.0, lower = more similar)

        Returns:
            Tuple of (list of Memory objects with similarity_score, total count)

        Raises:
            RepositoryError: If search fails
        """
        try:
            # Build WHERE clauses
            where_clauses = ["deleted_at IS NULL"]
            params: Dict[str, Any] = {
                "limit": limit,
                "offset": offset,
                "threshold": distance_threshold
            }

            if filters:
                if filters.project_id:
                    where_clauses.append("project_id = :project_id")
                    params["project_id"] = str(filters.project_id)

                if filters.memory_type:
                    where_clauses.append("memory_type = :memory_type")
                    params["memory_type"] = filters.memory_type.value

                if filters.tags:
                    tag_conditions = [f":tag{i} = ANY(tags)" for i in range(len(filters.tags))]
                    where_clauses.append(f"({' AND '.join(tag_conditions)})")
                    for i, tag in enumerate(filters.tags):
                        params[f"tag{i}"] = tag

            where_sql = " AND ".join(where_clauses)

            # Format vector for pgvector
            vector_str = f"'[{','.join(map(str, vector))}]'::vector"

            # Search query with cosine distance
            query = text(f"""
                SELECT
                    id, title, content, created_at, updated_at,
                    memory_type, tags, author, project_id,
                    embedding, embedding_model, related_chunks, resource_links,
                    deleted_at,
                    (embedding <=> {vector_str}) as distance,
                    (1 - (embedding <=> {vector_str})) as similarity_score
                FROM memories
                WHERE {where_sql}
                    AND embedding IS NOT NULL
                    AND (embedding <=> {vector_str}) <= :threshold
                ORDER BY distance ASC
                LIMIT :limit OFFSET :offset
            """)

            # Count query
            count_query = text(f"""
                SELECT COUNT(*) as total
                FROM memories
                WHERE {where_sql}
                    AND embedding IS NOT NULL
                    AND (embedding <=> {vector_str}) <= :threshold
            """)

            async with self.engine.begin() as conn:
                # Get total count
                count_result = await conn.execute(count_query, params)
                total_row = count_result.fetchone()
                total_count = total_row[0] if total_row else 0

                # Get data
                result = await conn.execute(query, params)
                rows = result.fetchall()

            memories = [self._row_to_memory(row, include_similarity=True) for row in rows]

            self.logger.info(
                "Vector search completed",
                count=len(memories),
                total=total_count,
                threshold=distance_threshold
            )

            return memories, total_count

        except Exception as e:
            raise RepositoryError(f"Failed to search memories by vector: {e}") from e

    def _row_to_memory(
        self,
        row,
        exclude_embedding: bool = False,
        include_similarity: bool = False
    ) -> Memory:
        """
        Convert database row to Memory Pydantic model.

        Args:
            row: SQLAlchemy row object
            exclude_embedding: Exclude embedding vector (for bandwidth savings)
            include_similarity: Include similarity_score field (for search results)

        Returns:
            Memory object
        """
        # Convert row to dict
        row_dict = dict(row._mapping)

        # Parse PostgreSQL arrays
        if isinstance(row_dict.get("tags"), str):
            # PostgreSQL returns arrays as strings like "{tag1,tag2}"
            tags_str = row_dict["tags"]
            if tags_str == "{}":
                row_dict["tags"] = []
            else:
                row_dict["tags"] = tags_str.strip("{}").split(",")

        if isinstance(row_dict.get("related_chunks"), str):
            chunks_str = row_dict["related_chunks"]
            if chunks_str == "{}":
                row_dict["related_chunks"] = []
            else:
                row_dict["related_chunks"] = [
                    uuid.UUID(c.strip()) for c in chunks_str.strip("{}").split(",") if c.strip()
                ]

        # Parse JSONB
        if isinstance(row_dict.get("resource_links"), str):
            row_dict["resource_links"] = json.loads(row_dict["resource_links"])

        # Parse embedding if present
        if "embedding" in row_dict and row_dict["embedding"]:
            if isinstance(row_dict["embedding"], str):
                # Parse "[0.1,0.2,...]" to list
                embedding_str = row_dict["embedding"].strip("[]")
                if embedding_str:
                    row_dict["embedding"] = [float(x) for x in embedding_str.split(",")]
                else:
                    row_dict["embedding"] = None

        # Exclude embedding if requested
        if exclude_embedding:
            row_dict["embedding"] = None

        # Add similarity_score if present
        if include_similarity and "similarity_score" in row_dict:
            pass  # Already in row_dict
        else:
            row_dict["similarity_score"] = None

        return Memory(**row_dict)
