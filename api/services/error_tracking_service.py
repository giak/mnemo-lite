"""
Error Tracking Service for centralized error logging and alerting.

Story: EPIC-12 Story 12.4 - Error Tracking & Alerting
Author: Claude Code
Date: 2025-10-22
"""

import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import traceback
import asyncio
from enum import Enum

from db.repositories.error_repository import ErrorRepository

# Get structured logger
logger = structlog.get_logger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(str, Enum):
    """Error categories for grouping and analysis."""
    DATABASE = "database"
    EMBEDDING = "embedding"
    API = "api"
    CIRCUIT_BREAKER = "circuit_breaker"
    CACHE = "cache"
    GRAPH = "graph"
    TIMEOUT = "timeout"
    INDEXING = "indexing"
    SEARCH = "search"
    UNKNOWN = "unknown"


class ErrorTrackingService:
    """
    Centralized error tracking and logging service.

    Responsibilities:
    - Log errors with structured metadata
    - Store errors in PostgreSQL for aggregation
    - Provide error analytics and summaries
    - Check alert thresholds for monitoring

    Attributes:
        error_repository: Repository for error database operations
        logger: Structured logger for service operations
    """

    def __init__(self, error_repository: ErrorRepository):
        """
        Initialize error tracking service.

        Args:
            error_repository: Repository for error database operations
        """
        self.error_repository = error_repository
        self.logger = structlog.get_logger(__name__)
        self.logger.info("ErrorTrackingService initialized")

    async def log_error(
        self,
        error: Exception,
        severity: ErrorSeverity,
        category: ErrorCategory,
        service: str,
        context: Optional[Dict[str, Any]] = None,
        include_traceback: bool = True
    ) -> None:
        """
        Log an error with full context and store in database.

        This method:
        1. Logs to structlog for immediate visibility
        2. Stores in database for aggregation (fire-and-forget)

        Args:
            error: The exception that occurred
            severity: Error severity level
            category: Error category for grouping
            service: Service name where error occurred
            context: Additional context (request_id, user, etc.)
            include_traceback: Whether to include full stack trace

        Example:
            try:
                await some_operation()
            except TimeoutError as e:
                await error_tracking.log_error(
                    error=e,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.TIMEOUT,
                    service="EmbeddingService",
                    context={"operation": "generate_embeddings", "timeout": 5}
                )
                raise
        """
        error_type = type(error).__name__
        message = str(error)
        stack_trace = traceback.format_exc() if include_traceback else None

        # Structured logging for immediate visibility
        self.logger.bind(
            severity=severity.value,
            category=category.value,
            service=service,
            error_type=error_type,
            context=context or {}
        ).error(message, exc_info=error)

        # Store in database (fire-and-forget to avoid blocking)
        # If storage fails, we still have structlog output
        asyncio.create_task(
            self._store_error_safe(
                severity=severity.value,
                category=category.value,
                service=service,
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                context=context or {}
            )
        )

    async def _store_error_safe(
        self,
        severity: str,
        category: str,
        service: str,
        error_type: str,
        message: str,
        stack_trace: Optional[str],
        context: Dict[str, Any]
    ) -> None:
        """
        Store error in database with exception handling.

        This is an internal method called via fire-and-forget.
        If database storage fails, log warning but don't propagate.

        Args:
            severity: Error severity level
            category: Error category
            service: Service name
            error_type: Exception class name
            message: Error message
            stack_trace: Stack trace text
            context: Additional context
        """
        try:
            await self.error_repository.create_error(
                severity=severity,
                category=category,
                service=service,
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                context=context
            )
        except Exception as e:
            # Don't let error tracking fail the request
            # Just log to structlog and continue
            self.logger.warning(
                f"Failed to store error in database: {e}",
                original_error_type=error_type,
                storage_error=str(e)
            )

    async def get_error_summary(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get error summary for last N hours.

        Returns aggregated error counts grouped by category, service,
        error type, and severity.

        Args:
            hours: Number of hours to look back (default: 24)

        Returns:
            List of error summary dicts with:
                - category, service, error_type, severity
                - total_count, last_occurrence, first_occurrence

        Example:
            summary = await error_tracking.get_error_summary(hours=24)
            for error in summary:
                print(f"{error['error_type']}: {error['total_count']} occurrences")
        """
        return await self.error_repository.get_error_summary(hours=hours)

    async def get_critical_errors(self, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Get critical errors from last N hours.

        Returns all CRITICAL severity errors for immediate attention.

        Args:
            hours: Number of hours to look back (default: 1)

        Returns:
            List of critical error dicts with all fields

        Example:
            critical = await error_tracking.get_critical_errors(hours=1)
            if critical:
                print(f"⚠️ {len(critical)} critical errors in last hour!")
        """
        return await self.error_repository.get_critical_errors(hours=hours)

    async def get_errors_by_category(
        self,
        category: str,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get errors for a specific category.

        Useful for drilling down into specific error types.

        Args:
            category: Error category (database, embedding, api, etc.)
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of errors to return (default: 100)

        Returns:
            List of error dicts for the category

        Example:
            db_errors = await error_tracking.get_errors_by_category(
                category="database",
                hours=24
            )
        """
        return await self.error_repository.get_errors_by_category(
            category=category,
            hours=hours,
            limit=limit
        )

    async def check_alert_thresholds(self) -> List[str]:
        """
        Check if error thresholds exceeded, return alert messages.

        Alert Thresholds:
        - CRITICAL: Any critical error triggers alert
        - ERROR: >10 errors in 1 hour triggers alert
        - WARNING: >50 warnings in 1 hour triggers alert

        Returns:
            List of alert messages (empty if no thresholds exceeded)

        Example:
            alerts = await error_tracking.check_alert_thresholds()
            if alerts:
                for alert in alerts:
                    print(f"🚨 ALERT: {alert}")
        """
        alerts = []

        # Check critical errors
        critical = await self.get_critical_errors(hours=1)
        if critical:
            alerts.append(
                f"🚨 CRITICAL: {len(critical)} critical error(s) in last hour"
            )

        # Check error and warning counts
        try:
            counts = await self.error_repository.get_error_count_by_severity(hours=1)

            # Check error threshold (>10 in 1 hour)
            error_count = counts.get('ERROR', 0)
            if error_count > 10:
                alerts.append(
                    f"⚠️  ERROR: {error_count} errors in last hour (threshold: 10)"
                )

            # Check warning threshold (>50 in 1 hour)
            warning_count = counts.get('WARNING', 0)
            if warning_count > 50:
                alerts.append(
                    f"⚠️  WARNING: {warning_count} warnings in last hour (threshold: 50)"
                )

        except Exception as e:
            self.logger.error(f"Failed to check alert thresholds: {e}")

        return alerts

    async def get_error_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive error statistics.

        Returns:
            Dict with error statistics:
                - total_errors_24h: Total error count in last 24 hours
                - critical_errors_1h: Critical errors in last hour
                - top_error_types: Most common error types
                - alerts: Current alert messages

        Example:
            stats = await error_tracking.get_error_stats()
            print(f"Total errors (24h): {stats['total_errors_24h']}")
        """
        try:
            summary = await self.get_error_summary(hours=24)
            critical = await self.get_critical_errors(hours=1)
            alerts = await self.check_alert_thresholds()

            total_errors = sum(s['total_count'] for s in summary)

            # Get top 5 error types
            top_errors = sorted(
                summary,
                key=lambda x: x['total_count'],
                reverse=True
            )[:5]

            return {
                "total_errors_24h": total_errors,
                "critical_errors_1h": len(critical),
                "top_error_types": [
                    {
                        "error_type": e['error_type'],
                        "count": e['total_count'],
                        "service": e['service']
                    }
                    for e in top_errors
                ],
                "alerts": alerts,
                "summary_count": len(summary)
            }

        except Exception as e:
            self.logger.error(f"Failed to get error stats: {e}")
            return {
                "total_errors_24h": 0,
                "critical_errors_1h": 0,
                "top_error_types": [],
                "alerts": [],
                "error": str(e)
            }
