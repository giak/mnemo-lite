"""
Lexical Search Service using PostgreSQL pg_trgm similarity.

Provides keyword-based search with fuzzy matching capabilities using
trigram similarity indexes. Optimized for fast candidate retrieval
in hybrid search pipelines.
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class LexicalSearchResult:
    """Result from lexical search."""
    chunk_id: str
    similarity_score: float
    source_code: str
    name: str
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]
    rank: int  # 1-indexed rank in results
    name_path: Optional[str] = None  # EPIC-11 Story 11.2: Hierarchical qualified name (must be last)


class LexicalSearchService:
    """
    Lexical search service using pg_trgm similarity.

    Uses PostgreSQL's trigram similarity for fuzzy keyword matching.
    Optimized for fast candidate retrieval (5-15ms for 10k chunks).

    Features:
    - Trigram similarity on source_code and name columns
    - Fuzzy matching (typo-tolerant)
    - Metadata filtering (language, chunk_type, etc.)
    - Configurable similarity threshold
    - Early LIMIT for performance
    """

    def __init__(
        self,
        engine: AsyncEngine,
        similarity_threshold: float = 0.1,  # Low threshold for recall
    ):
        """
        Initialize lexical search service.

        Args:
            engine: AsyncEngine for database connection
            similarity_threshold: Minimum similarity score (0.0-1.0)
                                 Default 0.1 = low threshold for high recall
        """
        self.engine = engine
        self.similarity_threshold = similarity_threshold

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        search_in_name: bool = True,
        search_in_source: bool = True,
        search_in_name_path: bool = False,  # EPIC-11 Story 11.2: Search qualified names
    ) -> List[LexicalSearchResult]:
        """
        Search code chunks using pg_trgm similarity.

        Args:
            query: Search query (keywords or qualified names like 'models.User')
            filters: Optional filters:
                - language: str (e.g., "python")
                - chunk_type: str (e.g., "function")
                - repository: str
                - file_path: str (partial match)
            limit: Maximum number of results (default: 100)
            search_in_name: Search in name column (default: True)
            search_in_source: Search in source_code column (default: True)
            search_in_name_path: Search in name_path column (default: False).
                                 Auto-enabled if query contains dots.
                                 EPIC-11 Story 11.2: Enables qualified name search.

        Returns:
            List of LexicalSearchResult ordered by similarity DESC

        Raises:
            ValueError: If query is empty or all search fields disabled
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        query = query.strip()

        # EPIC-11 Story 11.2: Auto-detection of qualified queries
        # If query contains dots (e.g., "models.User"), auto-enable name_path search
        if "." in query and not search_in_name_path:
            search_in_name_path = True
            logger.debug(f"Auto-detected qualified query: '{query}' → enabled name_path search")

        if not search_in_name and not search_in_source and not search_in_name_path:
            raise ValueError("At least one search field must be enabled")

        # Build WHERE clauses
        where_clauses = []
        params = {"query": query, "threshold": self.similarity_threshold}

        # Trigram similarity conditions
        similarity_conditions = []
        if search_in_name:
            similarity_conditions.append("name % :query")
        if search_in_source:
            similarity_conditions.append("source_code % :query")
        if search_in_name_path:  # EPIC-11 Story 11.2
            similarity_conditions.append("name_path % :query")

        if similarity_conditions:
            where_clauses.append(f"({' OR '.join(similarity_conditions)})")

        # Apply filters
        if filters:
            if "language" in filters:
                where_clauses.append("language = :language")
                params["language"] = filters["language"]

            if "chunk_type" in filters:
                where_clauses.append("chunk_type = :chunk_type")
                params["chunk_type"] = filters["chunk_type"]

            if "repository" in filters:
                where_clauses.append("metadata->>'repository' = :repository")
                params["repository"] = filters["repository"]

            if "file_path" in filters:
                where_clauses.append("file_path LIKE :file_path")
                params["file_path"] = f"%{filters['file_path']}%"

        where_clause = " AND ".join(where_clauses)

        # Calculate similarity scores (max of name, source, and name_path)
        # Use GREATEST to combine scores from all enabled fields
        similarity_expr_parts = []
        if search_in_name:
            similarity_expr_parts.append("similarity(name, :query)")
        if search_in_source:
            similarity_expr_parts.append("similarity(source_code, :query)")
        if search_in_name_path:  # EPIC-11 Story 11.2
            similarity_expr_parts.append("similarity(name_path, :query)")

        if len(similarity_expr_parts) > 1:
            similarity_expr = f"GREATEST({', '.join(similarity_expr_parts)})"
        else:
            similarity_expr = similarity_expr_parts[0]

        # Build query
        query_sql = f"""
            SELECT
                id::TEXT as chunk_id,
                {similarity_expr} as similarity_score,
                source_code,
                name,
                name_path,
                language,
                chunk_type,
                file_path,
                metadata
            FROM code_chunks
            WHERE {where_clause}
              AND {similarity_expr} > :threshold
            ORDER BY similarity_score DESC
            LIMIT :limit
        """

        params["limit"] = limit

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text(query_sql), params)
                rows = result.fetchall()

            # Convert to LexicalSearchResult objects
            results = []
            for rank, row in enumerate(rows, start=1):
                results.append(LexicalSearchResult(
                    chunk_id=row.chunk_id,
                    similarity_score=row.similarity_score,
                    source_code=row.source_code,
                    name=row.name,
                    name_path=row.name_path,  # EPIC-11 Story 11.2
                    language=row.language,
                    chunk_type=row.chunk_type,
                    file_path=row.file_path,
                    metadata=row.metadata or {},
                    rank=rank,
                ))

            logger.info(
                f"Lexical search: query='{query}', results={len(results)}, "
                f"top_score={results[0].similarity_score if results else 0:.3f}"
            )

            return results

        except Exception as e:
            logger.error(f"Lexical search failed: {e}", exc_info=True)
            raise

    async def search_with_stats(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> tuple[List[LexicalSearchResult], Dict[str, Any]]:
        """
        Search with additional statistics.

        Returns:
            Tuple of (results, stats) where stats contains:
            - total_candidates: Total matches before limit
            - avg_score: Average similarity score
            - min_score: Minimum score
            - max_score: Maximum score
            - search_time_ms: Execution time
        """
        import time
        start = time.time()

        results = await self.search(query, filters, limit)

        stats = {
            "total_candidates": len(results),
            "avg_score": sum(r.similarity_score for r in results) / len(results) if results else 0,
            "min_score": min(r.similarity_score for r in results) if results else 0,
            "max_score": max(r.similarity_score for r in results) if results else 0,
            "search_time_ms": (time.time() - start) * 1000,
        }

        return results, stats

    def set_similarity_threshold(self, threshold: float) -> None:
        """
        Update similarity threshold.

        Args:
            threshold: New threshold (0.0-1.0)
                      Lower = more results (high recall)
                      Higher = fewer results (high precision)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")

        self.similarity_threshold = threshold
        logger.info(f"Similarity threshold updated to {threshold}")
