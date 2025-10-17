"""
Base query builder class for shared functionality.

Provides common methods and patterns for building SQL queries.
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.sql.expression import TextClause
from sqlalchemy.sql import text
import logging


class BaseQueryBuilder:
    """Base class for query builders with common functionality."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the base query builder.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def _validate_params(self, params: Dict[str, Any], required: List[str]) -> None:
        """
        Validate that required parameters are present.

        Args:
            params: Parameters dictionary
            required: List of required parameter names

        Raises:
            ValueError: If any required parameter is missing
        """
        missing = [p for p in required if p not in params or params[p] is None]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

    def _build_where_clause(self, conditions: List[str]) -> str:
        """
        Build a WHERE clause from a list of conditions.

        Args:
            conditions: List of SQL conditions

        Returns:
            WHERE clause string or empty string if no conditions
        """
        if not conditions:
            return ""
        return "WHERE " + " AND ".join(conditions)

    def _build_pagination(self, limit: Optional[int] = None, offset: Optional[int] = None) -> str:
        """
        Build LIMIT/OFFSET clause.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Pagination clause string
        """
        parts = []
        if limit is not None:
            parts.append(f"LIMIT :lim")
        if offset is not None:
            parts.append(f"OFFSET :off")
        return " ".join(parts)

    def _safe_json_dumps(self, data: Any) -> Optional[str]:
        """
        Safely convert data to JSON string.

        Args:
            data: Data to convert

        Returns:
            JSON string or None if data is None
        """
        if data is None:
            return None

        import json
        try:
            return json.dumps(data)
        except (TypeError, ValueError) as e:
            self.logger.warning(f"Failed to serialize to JSON: {e}")
            return None

    def _log_query(self, query: TextClause, params: Dict[str, Any], operation: str = "query") -> None:
        """
        Log query and parameters for debugging.

        Args:
            query: SQL query
            params: Query parameters
            operation: Operation name for logging
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Building {operation}:")
            self.logger.debug(f"  Query: {str(query)}")
            self.logger.debug(f"  Params: {params}")

    def build_exists_query(self, table: str, column: str, value: Any) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Build a simple EXISTS query.

        Args:
            table: Table name
            column: Column name to check
            value: Value to look for

        Returns:
            Query and parameters tuple
        """
        query_str = f"""
            SELECT EXISTS (
                SELECT 1 FROM {table}
                WHERE {column} = :value
            ) as exists
        """
        params = {"value": value}

        query = text(query_str)
        self._log_query(query, params, f"exists check for {table}.{column}")
        return query, params