"""
Error tracking service for batch indexing failures.

Provides:
- log_error(): Persist error to database
- get_errors(): Retrieve errors with filtering and pagination
- get_error_summary(): Get counts by error_type
"""

import logging
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy import text
from models.indexing_error_models import IndexingErrorCreate, IndexingErrorResponse


class IndexingErrorService:
    """Service for tracking and retrieving indexing errors."""

    def __init__(self, engine: AsyncEngine):
        """
        Initialize error tracking service.

        Args:
            engine: SQLAlchemy AsyncEngine for database access
        """
        self.engine = engine
        self.logger = logging.getLogger(__name__)
        self.logger.info("IndexingErrorService initialized")

    async def log_error(
        self,
        error: IndexingErrorCreate,
        connection: Optional[AsyncConnection] = None
    ) -> int:
        """
        Log an indexing error to the database.

        Args:
            error: IndexingErrorCreate model with error details
            connection: Optional existing connection (for transactions)

        Returns:
            error_id: ID of created error record
        """
        query = text("""
            INSERT INTO indexing_errors (
                repository, file_path, error_type, error_message,
                error_traceback, chunk_type, language
            )
            VALUES (
                :repository, :file_path, :error_type, :error_message,
                :error_traceback, :chunk_type, :language
            )
            RETURNING error_id
        """)

        params = {
            "repository": error.repository,
            "file_path": error.file_path,
            "error_type": error.error_type,
            "error_message": error.error_message,
            "error_traceback": error.error_traceback,
            "chunk_type": error.chunk_type,
            "language": error.language
        }

        if connection:
            # Use provided connection (already in transaction)
            result = await connection.execute(query, params)
            error_id = result.scalar()
        else:
            # Create new transaction
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                error_id = result.scalar()

        self.logger.info(f"Logged error {error_id} for {error.file_path} in {error.repository}")
        return error_id

    async def get_errors(
        self,
        repository: str,
        error_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[IndexingErrorResponse], int]:
        """
        Retrieve errors with filtering and pagination.

        Args:
            repository: Repository name to filter by
            error_type: Optional error type filter
            limit: Maximum number of errors to return (default: 100)
            offset: Number of errors to skip (default: 0)

        Returns:
            Tuple of (errors list, total count)
        """
        # Build query with optional error_type filter
        where_clause = "WHERE repository = :repository"
        params = {"repository": repository, "limit": limit, "offset": offset}

        if error_type:
            where_clause += " AND error_type = :error_type"
            params["error_type"] = error_type

        # Get total count
        count_query = text(f"""
            SELECT COUNT(*) FROM indexing_errors
            {where_clause}
        """)

        # Get paginated results
        select_query = text(f"""
            SELECT
                error_id, repository, file_path, error_type, error_message,
                error_traceback, chunk_type, language, occurred_at
            FROM indexing_errors
            {where_clause}
            ORDER BY occurred_at DESC
            LIMIT :limit OFFSET :offset
        """)

        async with self.engine.begin() as conn:
            # Get count
            count_result = await conn.execute(count_query, params)
            total = count_result.scalar()

            # Get errors
            errors_result = await conn.execute(select_query, params)
            rows = errors_result.fetchall()

        # Convert to Pydantic models
        errors = [
            IndexingErrorResponse(
                error_id=row.error_id,
                repository=row.repository,
                file_path=row.file_path,
                error_type=row.error_type,
                error_message=row.error_message,
                error_traceback=row.error_traceback,
                chunk_type=row.chunk_type,
                language=row.language,
                occurred_at=row.occurred_at
            )
            for row in rows
        ]

        return errors, total

    async def get_error_summary(self, repository: str) -> dict:
        """
        Get summary of errors grouped by error_type.

        Args:
            repository: Repository name

        Returns:
            Dict mapping error_type to count
        """
        query = text("""
            SELECT error_type, COUNT(*) as count
            FROM indexing_errors
            WHERE repository = :repository
            GROUP BY error_type
            ORDER BY count DESC
        """)

        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"repository": repository})
            rows = result.fetchall()

        return {row.error_type: row.count for row in rows}
