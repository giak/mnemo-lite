"""
MCP Code Search Tool

Tool for semantic hybrid code search combining lexical (pg_trgm) and
vector (HNSW embeddings) search with RRF fusion.

Story 23.2.2 - Sub-story: Implement search_code tool.
"""

import time
import hashlib
import json
from typing import Optional, List
from mcp.server.fastmcp import Context

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.search_models import (
    CodeSearchQuery,
    CodeSearchResponse,
    CodeSearchResult,
    CodeSearchMetadata,
    CodeSearchFilters,
)
from services.hybrid_code_search_service import (
    HybridCodeSearchService,
    SearchFilters,
    HybridSearchResponse,
    HybridSearchResult,
)
from services.embedding_service import EmbeddingServiceInterface
import structlog

logger = structlog.get_logger()


class SearchCodeTool(BaseMCPComponent):
    """
    Semantic hybrid code search tool for MCP.

    Searches code chunks using:
    - Lexical search (pg_trgm trigram similarity)
    - Vector search (HNSW semantic embeddings)
    - RRF fusion (reciprocal rank fusion)

    Supports filters (language, chunk_type, repository, file_path, LSP types)
    and pagination (offset-based).

    Results are cached in Redis L2 for 5 minutes.

    Usage in Claude Desktop:
        "Search for authentication functions in Python"
        → Tool call: search_code(query="authentication function", filters={language: "python"})

    Performance:
        - Cached: <10ms P95
        - Uncached (lexical+vector): ~150-300ms P95
        - Lexical-only (embedding failure): ~50ms P95
    """

    def get_name(self) -> str:
        return "search_code"

    async def execute(
        self,
        ctx: Context,
        query: str,
        filters: Optional[CodeSearchFilters] = None,
        limit: int = 10,
        offset: int = 0,
        enable_lexical: bool = True,
        enable_vector: bool = True,
        lexical_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> CodeSearchResponse:
        """
        Execute code search with hybrid lexical+vector search.

        Args:
            ctx: MCP context
            query: Search query (keywords or natural language)
            filters: Optional filters (language, chunk_type, repository, etc.)
            limit: Maximum results to return (1-100)
            offset: Pagination offset (0-1000)
            enable_lexical: Enable lexical search
            enable_vector: Enable vector search
            lexical_weight: Weight for lexical results in RRF fusion (0.0-1.0)
            vector_weight: Weight for vector results in RRF fusion (0.0-1.0)

        Returns:
            CodeSearchResponse with results, metadata, and pagination info

        Raises:
            ValueError: Invalid query parameters
        """
        start_time = time.time()

        # Validate query
        if not query or len(query) > 500:
            raise ValueError("Query must be 1-500 characters")

        if limit < 1 or limit > 100:
            raise ValueError("Limit must be 1-100")

        if offset < 0 or offset > 1000:
            raise ValueError("Offset must be 0-1000")

        logger.info(
            "search_code.execute",
            query=query,
            filters=filters.model_dump() if filters else None,
            limit=limit,
            offset=offset,
            enable_lexical=enable_lexical,
            enable_vector=enable_vector,
        )

        # Get services
        db_pool = self._services.get("db")
        redis_client = self._services.get("redis")
        embedding_service = self._services.get("embedding_service")

        if not db_pool:
            raise RuntimeError("Database service not available")

        # Check cache
        cache_key = self._generate_cache_key(
            query=query,
            filters=filters,
            limit=limit,
            offset=offset,
            enable_lexical=enable_lexical,
            enable_vector=enable_vector,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )

        cached_result = None
        if redis_client:
            try:
                cached_result = await redis_client.get(cache_key)
                if cached_result:
                    logger.info("search_code.cache_hit", cache_key=cache_key)
                    # Deserialize and return cached result
                    cached_data = json.loads(cached_result)
                    cached_data["metadata"]["cache_hit"] = True
                    return CodeSearchResponse(**cached_data)
            except Exception as e:
                logger.warning(
                    "search_code.cache_read_failed",
                    error=str(e),
                    cache_key=cache_key
                )

        # Generate embeddings if vector search enabled
        embedding_text = None
        embedding_code = None

        if enable_vector and embedding_service:
            try:
                # Generate embedding for query
                # Note: Current MockEmbeddingService doesn't distinguish CODE vs TEXT domains
                # but HybridCodeSearchService prefers CODE embedding if available
                embedding_code = await embedding_service.generate_embedding(query)
                logger.info(
                    "search_code.embedding_generated",
                    dimension=len(embedding_code) if embedding_code else 0
                )
            except Exception as e:
                logger.warning(
                    "search_code.embedding_failed",
                    error=str(e),
                    fallback="lexical-only"
                )
                # Graceful degradation: continue with lexical-only
                enable_vector = False

        # Convert filters to SearchFilters dataclass
        search_filters = None
        if filters:
            search_filters = SearchFilters(
                language=filters.language,
                chunk_type=filters.chunk_type,
                repository=filters.repository,
                file_path=filters.file_path,
                return_type=filters.return_type,
                param_type=filters.param_type,
            )

        # Execute hybrid search
        try:
            # Get SQLAlchemy engine from services (not asyncpg pool)
            engine = self._services.get("engine")
            if not engine:
                raise RuntimeError("SQLAlchemy engine not available")

            hybrid_service = HybridCodeSearchService(engine=engine)

            hybrid_response: HybridSearchResponse = await hybrid_service.search(
                    query=query,
                    embedding_text=embedding_text,
                    embedding_code=embedding_code,
                    filters=search_filters,
                    top_k=limit + offset,  # Get enough for pagination
                    enable_lexical=enable_lexical,
                    enable_vector=enable_vector,
                    lexical_weight=lexical_weight,
                    vector_weight=vector_weight,
                )

            # Apply pagination
            paginated_results = hybrid_response.results[offset : offset + limit]

            # Convert HybridSearchResult to CodeSearchResult
            mcp_results = [
                self._convert_result(result) for result in paginated_results
            ]

            # Build response
            total = len(hybrid_response.results)
            has_next = (offset + limit) < total
            next_offset = offset + limit if has_next else None

            response = CodeSearchResponse(
                results=mcp_results,
                metadata=CodeSearchMetadata(
                    total_results=total,
                    lexical_count=hybrid_response.metadata.lexical_count,
                    vector_count=hybrid_response.metadata.vector_count,
                    unique_after_fusion=hybrid_response.metadata.unique_after_fusion,
                    lexical_enabled=hybrid_response.metadata.lexical_enabled,
                    vector_enabled=hybrid_response.metadata.vector_enabled,
                    graph_expansion_enabled=hybrid_response.metadata.graph_expansion_enabled,
                    lexical_weight=hybrid_response.metadata.lexical_weight,
                    vector_weight=hybrid_response.metadata.vector_weight,
                    execution_time_ms=hybrid_response.metadata.execution_time_ms,
                    lexical_time_ms=hybrid_response.metadata.lexical_time_ms,
                    vector_time_ms=hybrid_response.metadata.vector_time_ms,
                    fusion_time_ms=hybrid_response.metadata.fusion_time_ms,
                    graph_time_ms=hybrid_response.metadata.graph_time_ms,
                    cache_hit=False,
                ),
                total=total,
                limit=limit,
                offset=offset,
                has_next=has_next,
                next_offset=next_offset,
                error=None,
            )

            # Cache result for 5 minutes
            if redis_client:
                try:
                    cache_ttl_seconds = 300  # 5 minutes
                    await redis_client.set(
                        cache_key,
                        json.dumps(response.model_dump()),
                        ex=cache_ttl_seconds,
                    )
                    logger.info(
                        "search_code.cache_write",
                        cache_key=cache_key,
                        ttl_seconds=cache_ttl_seconds
                    )
                except Exception as e:
                    logger.warning(
                        "search_code.cache_write_failed",
                        error=str(e)
                    )

            execution_time_ms = (time.time() - start_time) * 1000
            logger.info(
                "search_code.complete",
                total_results=total,
                returned_results=len(mcp_results),
                execution_time_ms=execution_time_ms,
            )

            return response

        except ValueError as e:
            # User error - re-raise
            raise

        except Exception as e:
            # Service error - graceful degradation
            logger.error(
                "search_code.service_failed",
                error=str(e),
                query=query
            )

            # Return empty results with error message
            execution_time_ms = (time.time() - start_time) * 1000
            return CodeSearchResponse(
                results=[],
                metadata=CodeSearchMetadata(
                    total_results=0,
                    lexical_count=0,
                    vector_count=0,
                    unique_after_fusion=0,
                    lexical_enabled=enable_lexical,
                    vector_enabled=enable_vector,
                    graph_expansion_enabled=False,
                    lexical_weight=lexical_weight,
                    vector_weight=vector_weight,
                    execution_time_ms=execution_time_ms,
                    cache_hit=False,
                ),
                total=0,
                limit=limit,
                offset=offset,
                has_next=False,
                next_offset=None,
                error=f"Search service temporarily unavailable: {str(e)}",
            )

    def _generate_cache_key(
        self,
        query: str,
        filters: Optional[CodeSearchFilters],
        limit: int,
        offset: int,
        enable_lexical: bool,
        enable_vector: bool,
        lexical_weight: float,
        vector_weight: float,
    ) -> str:
        """
        Generate SHA256 cache key for search parameters.

        Format: search:v1:<sha256_hash>

        Args:
            All search parameters

        Returns:
            Redis cache key
        """
        # Build deterministic string representation
        cache_params = {
            "query": query,
            "filters": filters.model_dump() if filters else None,
            "limit": limit,
            "offset": offset,
            "enable_lexical": enable_lexical,
            "enable_vector": enable_vector,
            "lexical_weight": lexical_weight,
            "vector_weight": vector_weight,
        }

        # Sort keys for deterministic JSON
        cache_str = json.dumps(cache_params, sort_keys=True)

        # Generate SHA256 hash (first 16 chars for brevity)
        hash_digest = hashlib.sha256(cache_str.encode()).hexdigest()[:16]

        return f"search:v1:{hash_digest}"

    def _convert_result(self, result: HybridSearchResult) -> CodeSearchResult:
        """
        Convert HybridSearchResult (dataclass) to CodeSearchResult (Pydantic).

        Args:
            result: HybridSearchResult from search service

        Returns:
            CodeSearchResult for MCP response
        """
        return CodeSearchResult(
            chunk_id=result.chunk_id,
            rrf_score=result.rrf_score,
            rank=result.rank,
            source_code=result.source_code,
            name=result.name,
            name_path=result.name_path,
            language=result.language,
            chunk_type=result.chunk_type,
            file_path=result.file_path,
            metadata=result.metadata,
            lexical_score=result.lexical_score,
            vector_similarity=result.vector_similarity,
            vector_distance=result.vector_distance,
            contribution=result.contribution,
            related_nodes=result.related_nodes,
        )


# Singleton instance for registration
search_code_tool = SearchCodeTool()
