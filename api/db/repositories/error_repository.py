"""
Error Repository for error tracking operations.

Story: EPIC-12 Story 12.4 - Error Tracking & Alerting
Author: Claude Code
Date: 2025-10-22
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from sqlalchemy.engine import Result

# Import RepositoryError from base
from db.repositories.base import RepositoryError

# Import ContextLogger for better logging
from utils.context_logger import get_repository_logger


class ErrorRepository:
    """
    Repository for error tracking database operations.

    Handles CRUD operations for error logs, aggregation queries,
    and alert threshold checks using SQLAlchemy Core with async support.

    Attributes:
        engine: SQLAlchemy async engine for database connections
        logger: Context-aware logger for operation tracking
    """

    def __init__(self, engine: AsyncEngine) -> None:
        """
        Initialize the error repository.

        Args:
            engine: SQLAlchemy async engine for database operations
        """
        self.engine: AsyncEngine = engine
        self.logger = get_repository_logger("error")
        self.logger.info("ErrorRepository initialized")

    async def create_error(
        self,
        severity: str,
        category: str,
        service: str,
        error_type: str,
        message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> uuid.UUID:
        """
        Create error log entry.

        Args:
            severity: Error severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            category: Error category for grouping (database, embedding, api, etc.)
            service: Service name where error occurred
            error_type: Exception class name (e.g., 'ValueError')
            message: Error message
            stack_trace: Full stack trace (optional)
            context: Additional context dict (request_id, user, etc.)

        Returns:
            UUID of created error log entry

        Raises:
            RepositoryError: If error creation fails
        """
        query = text("""
            INSERT INTO error_logs (
                severity, category, service, error_type,
                message, stack_trace, context
            )
            VALUES (
                :severity, :category, :service, :error_type,
                :message, :stack_trace, CAST(:context AS jsonb)
            )
            RETURNING id
        """)

        try:
            import json
            async with self.engine.begin() as conn:
                result = await conn.execute(
                    query,
                    {
                        "severity": severity,
                        "category": category,
                        "service": service,
                        "error_type": error_type,
                        "message": message,
                        "stack_trace": stack_trace,
                        "context": json.dumps(context or {})
                    }
                )
                error_id = result.scalar_one()
                self.logger.info(
                    f"Error logged: {severity} - {error_type} [{service}]"
                )
                return error_id

        except Exception as e:
            self.logger.error(f"Failed to create error log: {e}")
            raise RepositoryError(f"Failed to create error log: {e}") from e

    async def get_error_summary(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get error summary for last N hours.

        Groups errors by category, service, error_type, and severity.

        Args:
            hours: Number of hours to look back (default: 24)

        Returns:
            List of error summary dicts with:
                - category, service, error_type, severity
                - total_count, last_occurrence, first_occurrence

        Raises:
            RepositoryError: If query fails
        """
        query = text(f"""
            SELECT
                category,
                service,
                error_type,
                severity,
                COUNT(*) as total_count,
                MAX(timestamp) as last_occurrence,
                MIN(timestamp) as first_occurrence
            FROM error_logs
            WHERE timestamp > NOW() - INTERVAL '{hours} hours'
            GROUP BY category, service, error_type, severity
            ORDER BY total_count DESC
        """)

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()

                return [
                    {
                        "category": row.category,
                        "service": row.service,
                        "error_type": row.error_type,
                        "severity": row.severity,
                        "total_count": row.total_count,
                        "last_occurrence": row.last_occurrence,
                        "first_occurrence": row.first_occurrence
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"Failed to get error summary: {e}")
            raise RepositoryError(f"Failed to get error summary: {e}") from e

    async def get_critical_errors(
        self,
        hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get critical errors from last N hours.

        Args:
            hours: Number of hours to look back (default: 1)

        Returns:
            List of critical error dicts with all fields

        Raises:
            RepositoryError: If query fails
        """
        query = text(f"""
            SELECT
                id,
                timestamp,
                severity,
                category,
                service,
                error_type,
                message,
                stack_trace,
                context
            FROM error_logs
            WHERE severity = 'CRITICAL'
              AND timestamp > NOW() - INTERVAL '{hours} hours'
            ORDER BY timestamp DESC
        """)

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()

                return [
                    {
                        "id": str(row.id),
                        "timestamp": row.timestamp,
                        "severity": row.severity,
                        "category": row.category,
                        "service": row.service,
                        "error_type": row.error_type,
                        "message": row.message,
                        "stack_trace": row.stack_trace,
                        "context": row.context
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"Failed to get critical errors: {e}")
            raise RepositoryError(f"Failed to get critical errors: {e}") from e

    async def get_error_count_by_severity(
        self,
        hours: int = 1
    ) -> Dict[str, int]:
        """
        Get error counts by severity for last N hours.

        Used for alert threshold checking.

        Args:
            hours: Number of hours to look back (default: 1)

        Returns:
            Dict mapping severity to count:
                {"CRITICAL": 2, "ERROR": 15, "WARNING": 45}

        Raises:
            RepositoryError: If query fails
        """
        query = text(f"""
            SELECT
                severity,
                COUNT(*) as count
            FROM error_logs
            WHERE timestamp > NOW() - INTERVAL '{hours} hours'
            GROUP BY severity
        """)

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()

                return {row.severity: row.count for row in rows}

        except Exception as e:
            self.logger.error(f"Failed to get error counts: {e}")
            raise RepositoryError(f"Failed to get error counts: {e}") from e

    async def get_errors_by_category(
        self,
        category: str,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get errors for a specific category.

        Args:
            category: Error category (database, embedding, api, etc.)
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of errors to return (default: 100)

        Returns:
            List of error dicts

        Raises:
            RepositoryError: If query fails
        """
        query = text(f"""
            SELECT
                id,
                timestamp,
                severity,
                category,
                service,
                error_type,
                message,
                context
            FROM error_logs
            WHERE category = :category
              AND timestamp > NOW() - INTERVAL '{hours} hours'
            ORDER BY timestamp DESC
            LIMIT :limit
        """)

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(
                    query,
                    {"category": category, "hours": hours, "limit": limit}
                )
                rows = result.fetchall()

                return [
                    {
                        "id": str(row.id),
                        "timestamp": row.timestamp,
                        "severity": row.severity,
                        "category": row.category,
                        "service": row.service,
                        "error_type": row.error_type,
                        "message": row.message,
                        "context": row.context
                    }
                    for row in rows
                ]

        except Exception as e:
            self.logger.error(f"Failed to get errors by category: {e}")
            raise RepositoryError(f"Failed to get errors by category: {e}") from e
