"""
Hybrid Code Search Service.

Orchestrates a complete hybrid search pipeline combining:
- Lexical search (pg_trgm trigram similarity)
- Vector search (HNSW semantic similarity)
- RRF fusion (reciprocal rank fusion)
- Optional graph expansion (dependency traversal)
- L2 Redis caching for performance (EPIC-10 Story 10.2)

Designed for <50ms P95 on 10k chunks with parallel execution.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncEngine

from services.lexical_search_service import LexicalSearchService, LexicalSearchResult
from services.vector_search_service import VectorSearchService, VectorSearchResult
from services.rrf_fusion_service import RRFFusionService, FusedResult
from services.caches import RedisCache, cache_keys

logger = logging.getLogger(__name__)


@dataclass
class SearchFilters:
    """Filters for hybrid search."""
    language: Optional[str] = None
    chunk_type: Optional[str] = None
    repository: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class HybridSearchResult:
    """
    Result from hybrid search pipeline.

    Contains fused results with original search scores and metadata.
    """
    chunk_id: str
    rrf_score: float
    rank: int  # Final rank (1-indexed)

    # Source code and metadata (required fields first)
    source_code: str
    name: str
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]

    # Optional fields with defaults
    name_path: Optional[str] = None  # EPIC-11 Story 11.2: Hierarchical qualified name

    # Search scores breakdown
    lexical_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    vector_distance: Optional[float] = None

    # RRF contribution breakdown
    contribution: Dict[str, float] = field(default_factory=dict)

    # Optional graph expansion
    related_nodes: List[str] = field(default_factory=list)


@dataclass
class SearchMetadata:
    """Metadata about the search execution."""
    total_results: int
    lexical_count: int
    vector_count: int
    unique_after_fusion: int

    lexical_enabled: bool
    vector_enabled: bool
    graph_expansion_enabled: bool

    lexical_weight: float
    vector_weight: float

    execution_time_ms: float
    lexical_time_ms: Optional[float] = None
    vector_time_ms: Optional[float] = None
    fusion_time_ms: Optional[float] = None
    graph_time_ms: Optional[float] = None


@dataclass
class HybridSearchResponse:
    """Complete hybrid search response."""
    results: List[HybridSearchResult]
    metadata: SearchMetadata


class HybridCodeSearchService:
    """
    Hybrid code search service.

    Orchestrates a complete search pipeline with:
    1. Query analysis (determine search strategy)
    2. Parallel execution (lexical + vector searches)
    3. RRF fusion (combine results)
    4. Optional graph expansion (traverse dependencies)
    5. Result enrichment (add metadata and scores)

    Performance target: <50ms P95 on 10k chunks

    Architecture:
        Query
          ↓
        ┌─────────────┐
        │ HybridSearch│
        └──────┬──────┘
               │
        ┌──────┴──────┐
        ↓             ↓
    [Lexical]    [Vector]     ← Parallel execution
        ↓             ↓
        └──────┬──────┘
               ↓
          [RRF Fusion]
               ↓
         [Graph Expand] (optional)
               ↓
           Results
    """

    def __init__(
        self,
        engine: AsyncEngine,
        lexical_service: Optional[LexicalSearchService] = None,
        vector_service: Optional[VectorSearchService] = None,
        fusion_service: Optional[RRFFusionService] = None,
        redis_cache: Optional[RedisCache] = None,
    ):
        """
        Initialize hybrid search service.

        Args:
            engine: AsyncEngine for database connection
            lexical_service: Optional LexicalSearchService (created if not provided)
            vector_service: Optional VectorSearchService (created if not provided)
            fusion_service: Optional RRFFusionService (created if not provided)
            redis_cache: Optional RedisCache for L2 caching (EPIC-10 Story 10.2)
        """
        self.engine = engine

        # Initialize services (use provided or create new)
        self.lexical = lexical_service or LexicalSearchService(
            engine=engine,
            similarity_threshold=0.1,  # Low threshold for high recall
        )

        self.vector = vector_service or VectorSearchService(
            engine=engine,
            ef_search=100,  # Balanced speed/recall
        )

        self.fusion = fusion_service or RRFFusionService(
            k=60,  # Industry standard
        )

        # L2 Redis cache (optional - graceful degradation)
        self.redis_cache = redis_cache

        logger.info(f"Hybrid Code Search Service initialized (Redis cache: {'enabled' if redis_cache is not None else 'disabled'})")

    async def search(
        self,
        query: str,
        embedding_text: Optional[List[float]] = None,
        embedding_code: Optional[List[float]] = None,
        filters: Optional[SearchFilters] = None,
        top_k: int = 10,
        enable_lexical: bool = True,
        enable_vector: bool = True,
        lexical_weight: float = 0.4,
        vector_weight: float = 0.6,
        candidate_pool_size: int = 100,
    ) -> HybridSearchResponse:
        """
        Execute hybrid search pipeline.

        Args:
            query: Search query (keywords)
            embedding_text: Optional TEXT domain embedding (768D)
                           If not provided, lexical-only search
            embedding_code: Optional CODE domain embedding (768D)
                           Used if provided, otherwise TEXT embedding used
            filters: Optional SearchFilters
            top_k: Number of final results to return (default: 10)
            enable_lexical: Enable lexical search (default: True)
            enable_vector: Enable vector search (default: True)
            lexical_weight: Weight for lexical results in RRF (default: 0.4)
            vector_weight: Weight for vector results in RRF (default: 0.6)
            candidate_pool_size: Number of candidates from each method (default: 100)

        Returns:
            HybridSearchResponse with fused results and metadata

        Raises:
            ValueError: If both lexical and vector are disabled or invalid inputs
        """
        import time
        start_time = time.time()

        # Validation
        if not enable_lexical and not enable_vector:
            raise ValueError("At least one search method must be enabled")

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Convert filters to dict
        filters_dict = self._filters_to_dict(filters) if filters else None

        # L2 CACHE LOOKUP (EPIC-10 Story 10.2)
        if self.redis_cache:
            repository = filters.repository if filters else None
            cache_key = cache_keys.search_result_key(
                query=query,
                repository=repository,
                limit=top_k
            )
            cached_response = await self.redis_cache.get(cache_key)

            if cached_response:
                logger.info(
                    "L2 cache HIT for search",
                    query=query[:50],
                    repository=repository,
                )
                # Deserialize HybridSearchResponse
                return self._deserialize_search_response(cached_response)

            logger.debug(
                "L2 cache MISS for search",
                query=query[:50],
                repository=repository,
            )

        # Execute searches in parallel
        lexical_results = None
        vector_results = None
        lexical_time = None
        vector_time = None

        tasks = []

        if enable_lexical:
            tasks.append(self._timed_lexical_search(
                query=query,
                filters=filters_dict,
                limit=candidate_pool_size,
            ))

        if enable_vector:
            # Use CODE embedding if provided, otherwise TEXT
            embedding = embedding_code if embedding_code is not None else embedding_text

            if embedding is None:
                logger.warning("Vector search enabled but no embedding provided, using lexical-only")
                enable_vector = False
            else:
                embedding_domain = "CODE" if embedding_code is not None else "TEXT"
                tasks.append(self._timed_vector_search(
                    embedding=embedding,
                    embedding_domain=embedding_domain,
                    filters=filters_dict,
                    limit=candidate_pool_size,
                ))

        # Execute parallel searches
        if tasks:
            results = await asyncio.gather(*tasks)

            if enable_lexical and enable_vector:
                (lexical_results, lexical_time), (vector_results, vector_time) = results
            elif enable_lexical:
                lexical_results, lexical_time = results[0]
            elif enable_vector:
                vector_results, vector_time = results[0]

        # RRF Fusion
        fusion_start = time.time()
        fused_results = self._fuse_results(
            lexical_results=lexical_results,
            vector_results=vector_results,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )
        fusion_time = (time.time() - fusion_start) * 1000

        # Limit to top_k
        fused_results = fused_results[:top_k]

        # Build hybrid results
        hybrid_results = self._build_hybrid_results(
            fused_results=fused_results,
            lexical_results=lexical_results,
            vector_results=vector_results,
        )

        # Build metadata
        total_time = (time.time() - start_time) * 1000

        metadata = SearchMetadata(
            total_results=len(hybrid_results),
            lexical_count=len(lexical_results) if lexical_results else 0,
            vector_count=len(vector_results) if vector_results else 0,
            unique_after_fusion=len(fused_results),
            lexical_enabled=enable_lexical,
            vector_enabled=enable_vector,
            graph_expansion_enabled=False,  # Not yet implemented
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
            execution_time_ms=total_time,
            lexical_time_ms=lexical_time,
            vector_time_ms=vector_time,
            fusion_time_ms=fusion_time,
        )

        logger.info(
            f"Hybrid search completed: query='{query[:50]}...', "
            f"results={len(hybrid_results)}, time={total_time:.2f}ms, "
            f"lexical={len(lexical_results) if lexical_results else 0}, "
            f"vector={len(vector_results) if vector_results else 0}"
        )

        response = HybridSearchResponse(
            results=hybrid_results,
            metadata=metadata,
        )

        # POPULATE L2 CACHE (EPIC-10 Story 10.2)
        if self.redis_cache:
            repository = filters.repository if filters else None
            cache_key = cache_keys.search_result_key(
                query=query,
                repository=repository,
                limit=top_k
            )
            serialized = self._serialize_search_response(response)
            # Cache for 30 seconds (search results)
            await self.redis_cache.set(cache_key, serialized, ttl_seconds=30)
            logger.debug(
                "L2 cache populated for search",
                query=query[:50],
                repository=repository,
                ttl_seconds=30,
            )

        return response

    async def _timed_lexical_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
    ) -> tuple[List[LexicalSearchResult], float]:
        """Execute lexical search with timing."""
        import time
        start = time.time()
        results = await self.lexical.search(
            query=query,
            filters=filters,
            limit=limit,
        )
        elapsed = (time.time() - start) * 1000
        return results, elapsed

    async def _timed_vector_search(
        self,
        embedding: List[float],
        embedding_domain: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
    ) -> tuple[List[VectorSearchResult], float]:
        """Execute vector search with timing."""
        import time
        start = time.time()
        results = await self.vector.search(
            embedding=embedding,
            embedding_domain=embedding_domain,
            filters=filters,
            limit=limit,
        )
        elapsed = (time.time() - start) * 1000
        return results, elapsed

    def _fuse_results(
        self,
        lexical_results: Optional[List[LexicalSearchResult]],
        vector_results: Optional[List[VectorSearchResult]],
        lexical_weight: float,
        vector_weight: float,
    ) -> List[FusedResult]:
        """
        Fuse lexical and vector results using RRF.

        Uses weighted RRF fusion if both result lists provided,
        otherwise returns single result list (no fusion needed).
        """
        # Prepare weighted results for RRF
        weighted_results = []

        if lexical_results:
            weighted_results.append((lexical_results, lexical_weight))

        if vector_results:
            weighted_results.append((vector_results, vector_weight))

        # If only one method used, no fusion needed
        if len(weighted_results) == 1:
            results_list, weight = weighted_results[0]
            # Convert to FusedResult format
            return [
                FusedResult(
                    chunk_id=r.chunk_id,
                    rrf_score=1.0 / (60 + r.rank),  # Single method RRF score
                    rank=r.rank,
                    original_result=r,
                    contribution={"single_method": 1.0 / (60 + r.rank)},
                )
                for r in results_list
            ]

        # Both methods: use weighted RRF fusion
        return self.fusion.fuse_with_weights(weighted_results)

    def _build_hybrid_results(
        self,
        fused_results: List[FusedResult],
        lexical_results: Optional[List[LexicalSearchResult]],
        vector_results: Optional[List[VectorSearchResult]],
    ) -> List[HybridSearchResult]:
        """
        Build final hybrid results from fused results.

        Enriches each result with scores from both search methods.
        """
        # Build lookup dicts for scores
        lexical_scores = {}
        if lexical_results:
            for r in lexical_results:
                lexical_scores[r.chunk_id] = r.similarity_score

        vector_scores = {}
        vector_distances = {}
        if vector_results:
            for r in vector_results:
                vector_scores[r.chunk_id] = r.similarity
                vector_distances[r.chunk_id] = r.distance

        # Build hybrid results
        hybrid_results = []

        for fused in fused_results:
            # Get original result (prefer vector for richer metadata)
            original = fused.original_result

            # Extract common fields
            if isinstance(original, VectorSearchResult):
                source_code = original.source_code
                name = original.name
                name_path = original.name_path  # EPIC-11 Story 11.2: Now VectorSearchResult has name_path
                language = original.language
                chunk_type = original.chunk_type
                file_path = original.file_path
                metadata = original.metadata
            else:  # LexicalSearchResult
                source_code = original.source_code
                name = original.name
                name_path = original.name_path  # EPIC-11 Story 11.2
                language = original.language
                chunk_type = original.chunk_type
                file_path = original.file_path
                metadata = original.metadata

            hybrid_results.append(HybridSearchResult(
                chunk_id=fused.chunk_id,
                rrf_score=fused.rrf_score,
                rank=fused.rank,
                source_code=source_code,
                name=name,
                name_path=name_path,  # EPIC-11 Story 11.2
                language=language,
                chunk_type=chunk_type,
                file_path=file_path,
                metadata=metadata,
                lexical_score=lexical_scores.get(fused.chunk_id),
                vector_similarity=vector_scores.get(fused.chunk_id),
                vector_distance=vector_distances.get(fused.chunk_id),
                contribution=fused.contribution,
            ))

        return hybrid_results

    @staticmethod
    def _filters_to_dict(filters: SearchFilters) -> Dict[str, Any]:
        """Convert SearchFilters to dict for services."""
        result = {}
        if filters.language is not None:
            result["language"] = filters.language
        if filters.chunk_type is not None:
            result["chunk_type"] = filters.chunk_type
        if filters.repository is not None:
            result["repository"] = filters.repository
        if filters.file_path is not None:
            result["file_path"] = filters.file_path
        return result

    async def search_with_auto_weights(
        self,
        query: str,
        embedding_text: Optional[List[float]] = None,
        embedding_code: Optional[List[float]] = None,
        filters: Optional[SearchFilters] = None,
        top_k: int = 10,
    ) -> HybridSearchResponse:
        """
        Search with automatic weight selection based on query analysis.

        Heuristic:
        - Code-heavy queries (has operators, punctuation): 30% lexical, 70% vector
        - Natural language queries: 50% lexical, 50% vector
        - Balanced queries: 40% lexical, 60% vector (default)

        This is a simple heuristic. More sophisticated analysis could use:
        - Token analysis (percentage of code tokens)
        - Syntax detection (AST parsing)
        - ML classifier for query type
        """
        # Simple heuristic: count code indicators
        code_indicators = sum([
            query.count("("),
            query.count(")"),
            query.count("{"),
            query.count("}"),
            query.count("."),
            query.count("->"),
            query.count("::"),
        ])

        # Adjust weights based on code indicators
        if code_indicators >= 5:
            # Code-heavy: favor vector
            lexical_weight, vector_weight = 0.3, 0.7
            logger.info(f"Auto-weights (code-heavy): lexical=0.3, vector=0.7")
        elif code_indicators == 0 and len(query.split()) > 3:
            # Natural language: balanced
            lexical_weight, vector_weight = 0.5, 0.5
            logger.info(f"Auto-weights (natural language): lexical=0.5, vector=0.5")
        else:
            # Balanced: default
            lexical_weight, vector_weight = 0.4, 0.6
            logger.info(f"Auto-weights (balanced): lexical=0.4, vector=0.6")

        return await self.search(
            query=query,
            embedding_text=embedding_text,
            embedding_code=embedding_code,
            filters=filters,
            top_k=top_k,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )

    def _serialize_search_response(self, response: HybridSearchResponse) -> dict:
        """
        Serialize HybridSearchResponse for Redis caching.

        Converts dataclass objects to dict for JSON serialization.
        """
        return {
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "rrf_score": r.rrf_score,
                    "rank": r.rank,
                    "source_code": r.source_code,
                    "name": r.name,
                    "language": r.language,
                    "chunk_type": r.chunk_type,
                    "file_path": r.file_path,
                    "metadata": r.metadata,
                    "lexical_score": r.lexical_score,
                    "vector_similarity": r.vector_similarity,
                    "vector_distance": r.vector_distance,
                    "contribution": r.contribution,
                    "related_nodes": r.related_nodes,
                }
                for r in response.results
            ],
            "metadata": {
                "total_results": response.metadata.total_results,
                "lexical_count": response.metadata.lexical_count,
                "vector_count": response.metadata.vector_count,
                "unique_after_fusion": response.metadata.unique_after_fusion,
                "lexical_enabled": response.metadata.lexical_enabled,
                "vector_enabled": response.metadata.vector_enabled,
                "graph_expansion_enabled": response.metadata.graph_expansion_enabled,
                "lexical_weight": response.metadata.lexical_weight,
                "vector_weight": response.metadata.vector_weight,
                "execution_time_ms": response.metadata.execution_time_ms,
                "lexical_time_ms": response.metadata.lexical_time_ms,
                "vector_time_ms": response.metadata.vector_time_ms,
                "fusion_time_ms": response.metadata.fusion_time_ms,
                "graph_time_ms": response.metadata.graph_time_ms,
            },
        }

    def _deserialize_search_response(self, data: dict) -> HybridSearchResponse:
        """
        Deserialize cached data back to HybridSearchResponse.

        Reconstructs dataclass objects from dict.
        """
        results = [
            HybridSearchResult(
                chunk_id=r["chunk_id"],
                rrf_score=r["rrf_score"],
                rank=r["rank"],
                source_code=r["source_code"],
                name=r["name"],
                language=r["language"],
                chunk_type=r["chunk_type"],
                file_path=r["file_path"],
                metadata=r["metadata"],
                name_path=r.get("name_path"),  # EPIC-11 Story 11.2: Preserve name_path from cache
                lexical_score=r.get("lexical_score"),
                vector_similarity=r.get("vector_similarity"),
                vector_distance=r.get("vector_distance"),
                contribution=r.get("contribution", {}),
                related_nodes=r.get("related_nodes", []),
            )
            for r in data["results"]
        ]

        metadata = SearchMetadata(
            total_results=data["metadata"]["total_results"],
            lexical_count=data["metadata"]["lexical_count"],
            vector_count=data["metadata"]["vector_count"],
            unique_after_fusion=data["metadata"]["unique_after_fusion"],
            lexical_enabled=data["metadata"]["lexical_enabled"],
            vector_enabled=data["metadata"]["vector_enabled"],
            graph_expansion_enabled=data["metadata"]["graph_expansion_enabled"],
            lexical_weight=data["metadata"]["lexical_weight"],
            vector_weight=data["metadata"]["vector_weight"],
            execution_time_ms=data["metadata"]["execution_time_ms"],
            lexical_time_ms=data["metadata"].get("lexical_time_ms"),
            vector_time_ms=data["metadata"].get("vector_time_ms"),
            fusion_time_ms=data["metadata"].get("fusion_time_ms"),
            graph_time_ms=data["metadata"].get("graph_time_ms"),
        )

        return HybridSearchResponse(results=results, metadata=metadata)
