"""
CodeChunkRepository for EPIC-06 Phase 1 Story 2bis.

Manages CRUD operations and search for code chunks with dual embeddings.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import Column, Integer, MetaData, String, Table, TIMESTAMP, Text, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import delete, insert, select, text, update
from sqlalchemy.sql.elements import TextClause
from pgvector.sqlalchemy import Vector

from db.repositories.base import RepositoryError
from models.code_chunk_models import CodeChunkCreate, CodeChunkModel, CodeChunkUpdate

logger = logging.getLogger(__name__)

# Define code_chunks table for SQLAlchemy Core
metadata_obj = MetaData()
code_chunks_table = Table(
    "code_chunks",
    metadata_obj,
    Column("id", UUID, primary_key=True),
    Column("file_path", Text, nullable=False),
    Column("language", Text, nullable=False),
    Column("chunk_type", Text, nullable=False),
    Column("name", Text),
    Column("name_path", Text),  # EPIC-11: Hierarchical qualified name
    Column("source_code", Text, nullable=False),
    Column("start_line", Integer),
    Column("end_line", Integer),
    Column("embedding_text", Vector(768)),
    Column("embedding_code", Vector(768)),
    Column("metadata", JSONB, nullable=False),
    Column("indexed_at", TIMESTAMP(timezone=True), nullable=False),
    Column("last_modified", TIMESTAMP(timezone=True)),
    Column("node_id", UUID),
    Column("repository", Text),
    Column("commit_hash", Text),
)


class CodeChunkQueryBuilder:
    """Builds SQL queries for CodeChunkRepository using SQLAlchemy Core."""

    def build_add_query(self, chunk_data: CodeChunkCreate) -> Tuple[TextClause, Dict[str, Any]]:
        """Build INSERT query with JSONB casting."""
        query_str = text("""
            INSERT INTO code_chunks (
                id, file_path, language, chunk_type, name, name_path, source_code,
                start_line, end_line, embedding_text, embedding_code, metadata,
                indexed_at, last_modified, node_id, repository, commit_hash
            )
            VALUES (
                :id, :file_path, :language, :chunk_type, :name, :name_path, :source_code,
                :start_line, :end_line, :embedding_text, :embedding_code, CAST(:metadata AS JSONB),
                :indexed_at, :last_modified, :node_id, :repository, :commit_hash
            )
            RETURNING *
        """)

        chunk_id = str(uuid.uuid4())

        # Import CodeChunkModel to use _format_embedding_for_db
        from models.code_chunk_models import CodeChunkModel

        params = {
            "id": chunk_id,
            "file_path": chunk_data.file_path,
            "language": chunk_data.language,
            "chunk_type": chunk_data.chunk_type.value if hasattr(chunk_data.chunk_type, 'value') else chunk_data.chunk_type,
            "name": chunk_data.name,
            "name_path": getattr(chunk_data, 'name_path', None),  # EPIC-11: Hierarchical qualified name
            "source_code": chunk_data.source_code,
            "start_line": chunk_data.start_line,
            "end_line": chunk_data.end_line,
            "embedding_text": CodeChunkModel._format_embedding_for_db(chunk_data.embedding_text),
            "embedding_code": CodeChunkModel._format_embedding_for_db(chunk_data.embedding_code),
            "metadata": json.dumps(chunk_data.metadata),
            "indexed_at": datetime.now(timezone.utc),
            "last_modified": chunk_data.metadata.get("last_modified"),
            "node_id": None,
            "repository": chunk_data.repository,
            "commit_hash": chunk_data.commit_hash,
        }

        return query_str, params

    def build_get_by_id_query(self, chunk_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build SELECT by ID query."""
        query_str = text("SELECT * FROM code_chunks WHERE id = :chunk_id")
        params = {"chunk_id": str(chunk_id)}
        return query_str, params

    def build_update_query(self, chunk_id: uuid.UUID, update_data: CodeChunkUpdate) -> Tuple[TextClause, Dict[str, Any]]:
        """Build UPDATE query for partial updates."""
        updates = []
        params = {"chunk_id": str(chunk_id)}

        # Import CodeChunkModel to use _format_embedding_for_db
        from models.code_chunk_models import CodeChunkModel

        if update_data.source_code is not None:
            updates.append("source_code = :source_code")
            params["source_code"] = update_data.source_code

        if update_data.metadata is not None:
            updates.append("metadata = metadata || CAST(:metadata AS JSONB)")
            params["metadata"] = json.dumps(update_data.metadata)

        if update_data.embedding_text is not None:
            updates.append("embedding_text = :embedding_text")
            params["embedding_text"] = CodeChunkModel._format_embedding_for_db(update_data.embedding_text)

        if update_data.embedding_code is not None:
            updates.append("embedding_code = :embedding_code")
            params["embedding_code"] = CodeChunkModel._format_embedding_for_db(update_data.embedding_code)

        if update_data.last_modified is not None:
            updates.append("last_modified = :last_modified")
            params["last_modified"] = update_data.last_modified

        # EPIC-11: Support name_path updates
        if update_data.name_path is not None:
            updates.append("name_path = :name_path")
            params["name_path"] = update_data.name_path

        if not updates:
            raise ValueError("No fields to update")

        # Always update last_modified when updating other fields
        if "last_modified" not in [u.split("=")[0].strip() for u in updates]:
            updates.append("last_modified = NOW()")

        query_str = text(f"""
            UPDATE code_chunks
            SET {', '.join(updates)}
            WHERE id = :chunk_id
            RETURNING *
        """)

        return query_str, params

    def build_delete_query(self, chunk_id: uuid.UUID) -> Tuple[TextClause, Dict[str, Any]]:
        """Build DELETE query."""
        query_str = text("DELETE FROM code_chunks WHERE id = :chunk_id")
        params = {"chunk_id": str(chunk_id)}
        return query_str, params

    def build_add_batch_query(self, chunks_data: List[CodeChunkCreate]) -> Tuple[TextClause, List[Dict[str, Any]]]:
        """
        Build batch INSERT query for multiple chunks.

        PHASE 1 OPTIMIZATION: Replaces sequential inserts with bulk INSERT.
        This is 10-50× faster for large batches.
        """
        if not chunks_data:
            raise ValueError("chunks_data cannot be empty")

        # Import CodeChunkModel to use _format_embedding_for_db
        from models.code_chunk_models import CodeChunkModel

        # Build VALUES clause with placeholders for each chunk
        values_parts = []
        all_params = []

        for i, chunk_data in enumerate(chunks_data):
            chunk_id = str(uuid.uuid4())

            # Create parameter names with index suffix to avoid conflicts
            value_part = f"""(
                :id_{i}, :file_path_{i}, :language_{i}, :chunk_type_{i}, :name_{i}, :name_path_{i}, :source_code_{i},
                :start_line_{i}, :end_line_{i}, :embedding_text_{i}, :embedding_code_{i},
                CAST(:metadata_{i} AS JSONB), :indexed_at_{i}, :last_modified_{i},
                :node_id_{i}, :repository_{i}, :commit_hash_{i}
            )"""
            values_parts.append(value_part)

            params = {
                f"id_{i}": chunk_id,
                f"file_path_{i}": chunk_data.file_path,
                f"language_{i}": chunk_data.language,
                f"chunk_type_{i}": chunk_data.chunk_type.value if hasattr(chunk_data.chunk_type, 'value') else chunk_data.chunk_type,
                f"name_{i}": chunk_data.name,
                f"name_path_{i}": getattr(chunk_data, 'name_path', None),  # EPIC-11
                f"source_code_{i}": chunk_data.source_code,
                f"start_line_{i}": chunk_data.start_line,
                f"end_line_{i}": chunk_data.end_line,
                f"embedding_text_{i}": CodeChunkModel._format_embedding_for_db(chunk_data.embedding_text),
                f"embedding_code_{i}": CodeChunkModel._format_embedding_for_db(chunk_data.embedding_code),
                f"metadata_{i}": json.dumps(chunk_data.metadata),
                f"indexed_at_{i}": datetime.now(timezone.utc),
                f"last_modified_{i}": chunk_data.metadata.get("last_modified"),
                f"node_id_{i}": None,
                f"repository_{i}": chunk_data.repository,
                f"commit_hash_{i}": chunk_data.commit_hash,
            }
            all_params.append(params)

        # Combine all parameters into a single dict
        combined_params = {}
        for params_dict in all_params:
            combined_params.update(params_dict)

        values_clause = ",\n            ".join(values_parts)

        query_str = text(f"""
            INSERT INTO code_chunks (
                id, file_path, language, chunk_type, name, name_path, source_code,
                start_line, end_line, embedding_text, embedding_code, metadata,
                indexed_at, last_modified, node_id, repository, commit_hash
            )
            VALUES
            {values_clause}
            RETURNING id
        """)

        return query_str, combined_params

    def build_search_vector_query(
        self,
        embedding: List[float],
        embedding_type: Literal["text", "code"] = "code",
        language: Optional[str] = None,
        chunk_type: Optional[str] = None,
        repository: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build vector search query with dual embeddings support.

        embedding_type:
            - 'text': Search via embedding_text (docstrings, comments)
            - 'code': Search via embedding_code (code semantics)
        """
        embedding_col = "embedding_text" if embedding_type == "text" else "embedding_code"

        # Import CodeChunkModel to use _format_embedding_for_db
        from models.code_chunk_models import CodeChunkModel

        embedding_str = CodeChunkModel._format_embedding_for_db(embedding)

        conditions = []
        params = {
            "limit": limit,
            "offset": offset,
        }

        if language:
            conditions.append("language = :language")
            params["language"] = language

        if chunk_type:
            conditions.append("chunk_type = :chunk_type")
            params["chunk_type"] = chunk_type

        if repository:
            conditions.append("repository = :repository")
            params["repository"] = repository

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query_str = text(f"""
            SELECT *,
                   1 - ({embedding_col} <=> '{embedding_str}'::vector) AS similarity
            FROM code_chunks
            {where_clause}
            ORDER BY {embedding_col} <=> '{embedding_str}'::vector
            LIMIT :limit OFFSET :offset
        """)

        return query_str, params

    def build_search_similarity_query(
        self,
        query: str,
        language: Optional[str] = None,
        chunk_type: Optional[str] = None,
        threshold: float = 0.1,
        limit: int = 10,
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build trigram similarity search query (lexical, BM25-like).

        Uses pg_trgm extension for fuzzy/similarity matching.
        """
        conditions = ["source_code % :query"]  # Trigram operator
        params = {
            "query": query,
            "threshold": threshold,
            "limit": limit,
        }

        if language:
            conditions.append("language = :language")
            params["language"] = language

        if chunk_type:
            conditions.append("chunk_type = :chunk_type")
            params["chunk_type"] = chunk_type

        where_clause = "WHERE " + " AND ".join(conditions)

        query_str = text(f"""
            SELECT *,
                   similarity(source_code, :query) AS score
            FROM code_chunks
            {where_clause}
                   AND similarity(source_code, :query) >= :threshold
            ORDER BY score DESC
            LIMIT :limit
        """)

        return query_str, params


class CodeChunkRepository:
    """Manages CRUD and search operations for code chunks."""

    def __init__(self, engine: AsyncEngine):
        """Initialize repository with AsyncEngine."""
        self.engine = engine
        self.query_builder = CodeChunkQueryBuilder()
        self.logger = logging.getLogger(__name__)
        self.logger.info("CodeChunkRepository initialized.")

    async def _execute_query(self, query: TextClause, params: Dict[str, Any], is_mutation: bool = False) -> Result:
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

    async def add(self, chunk_data: CodeChunkCreate) -> CodeChunkModel:
        """Add a new code chunk."""
        query, params = self.query_builder.build_add_query(chunk_data)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            if not row:
                raise RepositoryError("Failed to add code chunk: No data returned.")
            return CodeChunkModel.from_db_record(row)
        except Exception as e:
            self.logger.error(f"Failed to add code chunk: {e}", exc_info=True)
            raise RepositoryError(f"Failed to add code chunk: {e}") from e

    async def add_batch(self, chunks_data: List[CodeChunkCreate]) -> int:
        """
        Add multiple code chunks in a single batch INSERT.

        PHASE 1 OPTIMIZATION: Replaces sequential inserts (N queries) with bulk INSERT (1 query).
        This is 10-50× faster for large batches.

        Args:
            chunks_data: List of CodeChunkCreate objects to insert

        Returns:
            Number of chunks successfully inserted

        Raises:
            RepositoryError: If batch insert fails
        """
        if not chunks_data:
            self.logger.warning("add_batch called with empty chunks_data")
            return 0

        query, params = self.query_builder.build_add_batch_query(chunks_data)
        try:
            self.logger.info(f"💾 Batch inserting {len(chunks_data)} chunks in single query")
            db_result = await self._execute_query(query, params, is_mutation=True)
            rows_affected = db_result.rowcount
            self.logger.info(f"✅ Batch insert complete: {rows_affected} chunks stored")
            return rows_affected
        except Exception as e:
            self.logger.error(f"Failed to batch insert {len(chunks_data)} chunks: {e}", exc_info=True)
            raise RepositoryError(f"Failed to batch insert chunks: {e}") from e

    async def get_by_id(self, chunk_id: uuid.UUID) -> Optional[CodeChunkModel]:
        """Get code chunk by ID."""
        query, params = self.query_builder.build_get_by_id_query(chunk_id)
        try:
            db_result = await self._execute_query(query, params)
            row = db_result.mappings().first()
            return CodeChunkModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get code chunk {chunk_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get code chunk {chunk_id}: {e}") from e

    async def update(self, chunk_id: uuid.UUID, update_data: CodeChunkUpdate) -> Optional[CodeChunkModel]:
        """Update code chunk (partial updates)."""
        query, params = self.query_builder.build_update_query(chunk_id, update_data)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            return CodeChunkModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to update code chunk {chunk_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to update code chunk {chunk_id}: {e}") from e

    async def delete(self, chunk_id: uuid.UUID) -> bool:
        """Delete code chunk by ID."""
        query, params = self.query_builder.build_delete_query(chunk_id)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            return db_result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to delete code chunk {chunk_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to delete code chunk {chunk_id}: {e}") from e

    async def search_vector(
        self,
        embedding: List[float],
        embedding_type: Literal["text", "code"] = "code",
        language: Optional[str] = None,
        chunk_type: Optional[str] = None,
        repository: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[CodeChunkModel]:
        """
        Vector search with dual embeddings support.

        Args:
            embedding: Embedding vector (768D)
            embedding_type: Which embedding to use ('text' or 'code')
            language: Filter by programming language
            chunk_type: Filter by chunk type
            repository: Filter by repository
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of CodeChunkModel with similarity scores
        """
        if len(embedding) != 768:
            raise ValueError(f"Embedding must be 768D, got {len(embedding)}")

        query, params = self.query_builder.build_search_vector_query(
            embedding=embedding,
            embedding_type=embedding_type,
            language=language,
            chunk_type=chunk_type,
            repository=repository,
            limit=limit,
            offset=offset,
        )

        try:
            db_result = await self._execute_query(query, params)
            rows = db_result.mappings().all()
            return [CodeChunkModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Vector search failed: {e}", exc_info=True)
            raise RepositoryError(f"Vector search failed: {e}") from e

    async def search_similarity(
        self,
        query: str,
        language: Optional[str] = None,
        chunk_type: Optional[str] = None,
        threshold: float = 0.1,
        limit: int = 10,
    ) -> List[CodeChunkModel]:
        """
        Trigram similarity search (lexical, BM25-like).

        Args:
            query: Search query string
            language: Filter by programming language
            chunk_type: Filter by chunk type
            threshold: Similarity threshold (0.0-1.0)
            limit: Maximum results

        Returns:
            List of CodeChunkModel with similarity scores
        """
        query_builder, params = self.query_builder.build_search_similarity_query(
            query=query,
            language=language,
            chunk_type=chunk_type,
            threshold=threshold,
            limit=limit,
        )

        try:
            db_result = await self._execute_query(query_builder, params)
            rows = db_result.mappings().all()
            return [CodeChunkModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Similarity search failed: {e}", exc_info=True)
            raise RepositoryError(f"Similarity search failed: {e}") from e
