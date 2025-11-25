"""
Hybrid Memory Search Service.

EPIC-24 P0: Combines lexical (pg_trgm) and vector (pgvector) search for memories
using RRF (Reciprocal Rank Fusion) for optimal retrieval.

EPIC-24 P2: Optional cross-encoder reranking for +20-30% quality improvement.

Performance target: <100ms P95 (without reranking), <200ms P95 (with reranking)

Architecture:
    Query
      ↓
    ┌─────────────────┐
    │ HybridMemSearch │
    └────────┬────────┘
             │
    ┌────────┴────────┐
    ↓                 ↓
[Lexical/TRGM]  [Vector/HNSW]   ← Parallel execution
    ↓                 ↓
    └────────┬────────┘
             ↓
       [RRF Fusion]
             ↓
    [Cross-Encoder Rerank] (optional, P2)
             ↓
         Results
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
import structlog

from services.rrf_fusion_service import RRFFusionService
from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType

logger = structlog.get_logger()


@dataclass
class MemorySearchResult:
    """Base result for memory search (used by both lexical and vector)."""
    memory_id: str  # For RRF fusion (uses chunk_id internally)
    title: str
    content_preview: str  # First 500 chars
    memory_type: str
    tags: List[str]
    created_at: str
    author: Optional[str] = None
    similarity_score: Optional[float] = None  # For vector search
    trgm_score: Optional[float] = None  # For lexical search

    # RRF compatibility
    @property
    def chunk_id(self) -> str:
        """RRF fusion expects chunk_id attribute."""
        return self.memory_id

    @property
    def rank(self) -> int:
        """RRF fusion expects rank attribute (set during search)."""
        return getattr(self, '_rank', 0)

    @rank.setter
    def rank(self, value: int):
        self._rank = value


@dataclass
class HybridMemorySearchResult:
    """Result from hybrid memory search with RRF fusion."""
    memory_id: str
    rrf_score: float
    rank: int

    # Memory fields
    title: str
    content_preview: str
    memory_type: str
    tags: List[str]
    created_at: str
    author: Optional[str] = None

    # Score breakdown
    lexical_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    rerank_score: Optional[float] = None  # EPIC-24 P2: Cross-encoder score
    contribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class HybridMemorySearchMetadata:
    """Metadata about the hybrid search execution."""
    # Required fields (no defaults) - must come first
    total_results: int
    lexical_count: int
    vector_count: int
    unique_after_fusion: int

    lexical_enabled: bool
    vector_enabled: bool

    lexical_weight: float
    vector_weight: float
    execution_time_ms: float

    # Optional fields (with defaults)
    reranking_enabled: bool = False  # EPIC-24 P2
    lexical_time_ms: Optional[float] = None
    vector_time_ms: Optional[float] = None
    fusion_time_ms: Optional[float] = None
    reranking_time_ms: Optional[float] = None  # EPIC-24 P2


@dataclass
class HybridMemorySearchResponse:
    """Complete hybrid memory search response."""
    results: List[HybridMemorySearchResult]
    metadata: HybridMemorySearchMetadata


class HybridMemorySearchService:
    """
    Hybrid memory search service using pg_trgm + pgvector + RRF fusion.

    Combines:
    - Lexical search: pg_trgm trigram similarity on title + content
    - Vector search: pgvector HNSW cosine distance on embeddings
    - RRF fusion: Reciprocal Rank Fusion for combining results
    - Cross-encoder reranking (optional, EPIC-24 P2): +20-30% quality

    Benefits:
    - Lexical catches exact matches (proper nouns like "Bardella")
    - Vector catches semantic similarity (synonyms, paraphrases)
    - RRF combines both without score normalization issues
    - Cross-encoder reranking provides fine-grained relevance scoring
    """

    def __init__(
        self,
        engine: AsyncEngine,
        fusion_service: Optional[RRFFusionService] = None,
        reranker_service: Optional["CrossEncoderRerankService"] = None,
        default_lexical_weight: float = 0.5,
        default_vector_weight: float = 0.5,
        default_enable_reranking: bool = False,
    ):
        """
        Initialize hybrid memory search service.

        Args:
            engine: SQLAlchemy async engine
            fusion_service: Optional RRF fusion service (created if not provided)
            reranker_service: Optional cross-encoder reranker (EPIC-24 P2)
            default_lexical_weight: Default weight for lexical results (0.5)
            default_vector_weight: Default weight for vector results (0.5)
            default_enable_reranking: Enable cross-encoder reranking by default (False)
        """
        self.engine = engine
        self.fusion = fusion_service or RRFFusionService(k=60)
        self.reranker = reranker_service  # Lazy-loaded on first use if None
        self.default_lexical_weight = default_lexical_weight
        self.default_vector_weight = default_vector_weight
        self.default_enable_reranking = default_enable_reranking

        logger.info(
            "HybridMemorySearchService initialized",
            lexical_weight=default_lexical_weight,
            vector_weight=default_vector_weight,
            reranking_enabled=default_enable_reranking,
        )

    async def search(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        filters: Optional[MemoryFilters] = None,
        limit: int = 10,
        offset: int = 0,
        enable_lexical: bool = True,
        enable_vector: bool = True,
        enable_reranking: Optional[bool] = None,
        lexical_weight: Optional[float] = None,
        vector_weight: Optional[float] = None,
        candidate_pool_size: int = 50,
        rerank_pool_size: int = 30,
        vector_similarity_threshold: float = 0.1,
    ) -> HybridMemorySearchResponse:
        """
        Execute hybrid memory search.

        Args:
            query: Search query text
            embedding: Optional query embedding vector (768D)
                      If not provided, lexical-only search
            filters: Optional memory filters
            limit: Number of final results (default: 10)
            offset: Pagination offset (default: 0)
            enable_lexical: Enable lexical/trigram search (default: True)
            enable_vector: Enable vector search (default: True)
            enable_reranking: Enable cross-encoder reranking (EPIC-24 P2)
                            If None, uses default_enable_reranking
            lexical_weight: Weight for lexical in RRF (default: 0.5)
            vector_weight: Weight for vector in RRF (default: 0.5)
            candidate_pool_size: Candidates from each method (default: 50)
            rerank_pool_size: Number of RRF results to rerank (default: 30)
                            Reranking is expensive, so we limit candidates
            vector_similarity_threshold: Minimum similarity for vector results (default: 0.1)
                - Filters out low-quality vector results that would pollute fusion
                - Prevents semantic noise from dominating exact lexical matches

        Returns:
            HybridMemorySearchResponse with fused results and metadata
        """
        start_time = time.time()

        # Use default weights if not specified
        lexical_weight = lexical_weight or self.default_lexical_weight
        vector_weight = vector_weight or self.default_vector_weight

        # Validation
        if not enable_lexical and not enable_vector:
            raise ValueError("At least one search method must be enabled")

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if enable_vector and embedding is None:
            logger.warning("Vector search enabled but no embedding provided, using lexical-only")
            enable_vector = False

        # Execute searches in parallel
        tasks = []
        lexical_results = None
        vector_results = None
        lexical_time = None
        vector_time = None

        if enable_lexical:
            tasks.append(self._lexical_search(
                query=query,
                filters=filters,
                limit=candidate_pool_size,
            ))

        if enable_vector:
            tasks.append(self._vector_search(
                embedding=embedding,
                filters=filters,
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

        # Filter low-quality vector results to prevent semantic noise
        # from dominating exact lexical matches
        if vector_results and vector_similarity_threshold > 0:
            original_count = len(vector_results)
            vector_results = [
                r for r in vector_results
                if r.similarity_score and r.similarity_score >= vector_similarity_threshold
            ]
            # Re-assign ranks after filtering
            for i, r in enumerate(vector_results, start=1):
                r.rank = i

            if len(vector_results) < original_count:
                logger.debug(
                    "Vector results filtered by threshold",
                    original=original_count,
                    filtered=len(vector_results),
                    threshold=vector_similarity_threshold
                )

        # RRF Fusion
        fusion_start = time.time()
        fused_results = self._fuse_results(
            lexical_results=lexical_results,
            vector_results=vector_results,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )
        fusion_time = (time.time() - fusion_start) * 1000

        # EPIC-24 P2: Cross-encoder reranking (optional)
        reranking_time = None
        rerank_scores = {}  # memory_id -> rerank_score
        should_rerank = enable_reranking if enable_reranking is not None else self.default_enable_reranking

        if should_rerank and fused_results:
            # Limit reranking candidates for performance
            rerank_candidates = fused_results[:rerank_pool_size]

            try:
                reranking_start = time.time()

                # Lazy-load reranker
                await self._ensure_reranker_loaded()

                # Prepare documents for reranking (use content preview)
                documents = [
                    (f.chunk_id, f.original_result.content_preview or f.original_result.title)
                    for f in rerank_candidates
                ]

                # Rerank
                reranked = await self.reranker.rerank_with_ids(
                    query=query,
                    documents=documents,
                    top_k=len(documents),
                )

                # Store rerank scores and reorder fused_results
                for memory_id, score, _ in reranked:
                    rerank_scores[memory_id] = score

                # Sort by rerank score
                rerank_candidates.sort(
                    key=lambda f: rerank_scores.get(f.chunk_id, -999),
                    reverse=True
                )

                # Merge back: reranked candidates first, then any remaining
                remaining = [f for f in fused_results[rerank_pool_size:]]
                fused_results = rerank_candidates + remaining

                reranking_time = (time.time() - reranking_start) * 1000

                logger.debug(
                    "Cross-encoder reranking completed",
                    candidates=len(rerank_candidates),
                    time_ms=f"{reranking_time:.2f}",
                )

            except Exception as e:
                logger.warning(
                    "Cross-encoder reranking failed, using RRF order",
                    error=str(e),
                )
                should_rerank = False

        # Apply offset and limit (after reranking)
        fused_results = fused_results[offset:offset + limit]

        # Build hybrid results
        hybrid_results = self._build_hybrid_results(
            fused_results=fused_results,
            lexical_results=lexical_results,
            vector_results=vector_results,
            rerank_scores=rerank_scores,
        )

        # Build metadata
        total_time = (time.time() - start_time) * 1000

        metadata = HybridMemorySearchMetadata(
            total_results=len(hybrid_results),
            lexical_count=len(lexical_results) if lexical_results else 0,
            vector_count=len(vector_results) if vector_results else 0,
            unique_after_fusion=len(fused_results),
            lexical_enabled=enable_lexical,
            vector_enabled=enable_vector,
            reranking_enabled=should_rerank,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
            execution_time_ms=total_time,
            lexical_time_ms=lexical_time,
            vector_time_ms=vector_time,
            fusion_time_ms=fusion_time,
            reranking_time_ms=reranking_time,
        )

        logger.info(
            "Hybrid memory search completed",
            query=query[:50],
            results=len(hybrid_results),
            time_ms=f"{total_time:.2f}",
            lexical_count=len(lexical_results) if lexical_results else 0,
            vector_count=len(vector_results) if vector_results else 0,
            reranking=should_rerank,
        )

        return HybridMemorySearchResponse(
            results=hybrid_results,
            metadata=metadata,
        )

    async def _ensure_reranker_loaded(self):
        """Lazy-load the cross-encoder reranker on first use."""
        if self.reranker is None:
            from services.cross_encoder_rerank_service import CrossEncoderRerankService
            self.reranker = CrossEncoderRerankService()

    async def _lexical_search(
        self,
        query: str,
        filters: Optional[MemoryFilters],
        limit: int,
    ) -> Tuple[List[MemorySearchResult], float]:
        """
        Execute lexical search using hybrid ILIKE + pg_trgm approach.

        Strategy for optimal performance:
        1. ILIKE for exact substring matching (fast, catches proper nouns like "Bardella")
        2. Trigram similarity on title + embedding_source only (not full content - too slow)
        3. Content is already covered by vector search via embedding_source

        This avoids the slow trigram scan on full content while still catching exact matches.
        """
        start_time = time.time()

        # Build WHERE clauses
        where_clauses = ["deleted_at IS NULL"]
        params: Dict[str, Any] = {"query": query, "limit": limit}

        # For ILIKE pattern
        ilike_pattern = f"%{query}%"
        params["ilike_pattern"] = ilike_pattern

        if filters:
            if filters.project_id:
                where_clauses.append("project_id = :project_id")
                params["project_id"] = str(filters.project_id)

            if filters.memory_type:
                where_clauses.append("memory_type = :memory_type")
                params["memory_type"] = filters.memory_type.value

            if filters.tags:
                for i, tag in enumerate(filters.tags):
                    where_clauses.append(f":tag{i} = ANY(tags)")
                    params[f"tag{i}"] = tag

        where_sql = " AND ".join(where_clauses)

        # Optimized approach: ILIKE + trigram on title/embedding_source ONLY
        # Skip content entirely - too slow without proper index
        # Content is covered by vector search via embedding_source
        query_sql = text(f"""
            SELECT
                id::text as memory_id,
                title,
                LEFT(content, 500) as content_preview,
                memory_type,
                tags,
                created_at::text,
                author,
                GREATEST(
                    similarity(title, :query),
                    COALESCE(similarity(embedding_source, :query), 0),
                    CASE WHEN title ILIKE :ilike_pattern THEN 1.0
                         WHEN embedding_source ILIKE :ilike_pattern THEN 0.95
                         ELSE 0.0 END
                ) as trgm_score
            FROM memories
            WHERE {where_sql}
                AND (
                    title ILIKE :ilike_pattern
                    OR embedding_source ILIKE :ilike_pattern
                    OR title % :query
                    OR embedding_source % :query
                )
            ORDER BY trgm_score DESC
            LIMIT :limit
        """)

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query_sql, params)
                rows = result.fetchall()

            results = []
            for rank, row in enumerate(rows, start=1):
                r = MemorySearchResult(
                    memory_id=row[0],
                    title=row[1],
                    content_preview=row[2],
                    memory_type=row[3],
                    tags=self._parse_pg_array(row[4]),
                    created_at=row[5],
                    author=row[6],
                    trgm_score=float(row[7]) if row[7] else 0.0,
                )
                r.rank = rank
                results.append(r)

            elapsed = (time.time() - start_time) * 1000

            logger.debug(
                "Lexical search completed",
                query=query[:30],
                results=len(results),
                time_ms=f"{elapsed:.2f}"
            )

            return results, elapsed

        except Exception as e:
            logger.error("Lexical search failed", error=str(e), query=query[:30])
            return [], (time.time() - start_time) * 1000

    async def _vector_search(
        self,
        embedding: List[float],
        filters: Optional[MemoryFilters],
        limit: int,
    ) -> Tuple[List[MemorySearchResult], float]:
        """Execute vector search using pgvector HNSW."""
        start_time = time.time()

        # Build WHERE clauses
        where_clauses = ["deleted_at IS NULL", "embedding IS NOT NULL"]
        params: Dict[str, Any] = {"limit": limit}

        if filters:
            if filters.project_id:
                where_clauses.append("project_id = :project_id")
                params["project_id"] = str(filters.project_id)

            if filters.memory_type:
                where_clauses.append("memory_type = :memory_type")
                params["memory_type"] = filters.memory_type.value

            if filters.tags:
                for i, tag in enumerate(filters.tags):
                    where_clauses.append(f":tag{i} = ANY(tags)")
                    params[f"tag{i}"] = tag

        where_sql = " AND ".join(where_clauses)

        # Format vector for pgvector
        vector_str = f"'[{','.join(map(str, embedding))}]'::vector"

        query_sql = text(f"""
            SELECT
                id::text as memory_id,
                title,
                LEFT(content, 500) as content_preview,
                memory_type,
                tags,
                created_at::text,
                author,
                (1 - (embedding <=> {vector_str})) as similarity_score
            FROM memories
            WHERE {where_sql}
            ORDER BY embedding <=> {vector_str}
            LIMIT :limit
        """)

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query_sql, params)
                rows = result.fetchall()

            results = []
            for rank, row in enumerate(rows, start=1):
                r = MemorySearchResult(
                    memory_id=row[0],
                    title=row[1],
                    content_preview=row[2],
                    memory_type=row[3],
                    tags=self._parse_pg_array(row[4]),
                    created_at=row[5],
                    author=row[6],
                    similarity_score=float(row[7]) if row[7] else 0.0,
                )
                r.rank = rank
                results.append(r)

            elapsed = (time.time() - start_time) * 1000

            logger.debug(
                "Vector search completed",
                results=len(results),
                time_ms=f"{elapsed:.2f}"
            )

            return results, elapsed

        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            return [], (time.time() - start_time) * 1000

    def _fuse_results(
        self,
        lexical_results: Optional[List[MemorySearchResult]],
        vector_results: Optional[List[MemorySearchResult]],
        lexical_weight: float,
        vector_weight: float,
    ) -> List:
        """Fuse lexical and vector results using weighted RRF."""
        weighted_results = []

        if lexical_results:
            weighted_results.append((lexical_results, lexical_weight))

        if vector_results:
            weighted_results.append((vector_results, vector_weight))

        if len(weighted_results) == 0:
            return []

        if len(weighted_results) == 1:
            # No fusion needed
            results_list, weight = weighted_results[0]
            from services.rrf_fusion_service import FusedResult
            return [
                FusedResult(
                    chunk_id=r.memory_id,
                    rrf_score=1.0 / (60 + r.rank),
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
        fused_results: List,
        lexical_results: Optional[List[MemorySearchResult]],
        vector_results: Optional[List[MemorySearchResult]],
        rerank_scores: Optional[Dict[str, float]] = None,
    ) -> List[HybridMemorySearchResult]:
        """Build final hybrid results from fused results."""
        # Build score lookup dicts
        lexical_scores = {}
        if lexical_results:
            for r in lexical_results:
                lexical_scores[r.memory_id] = r.trgm_score

        vector_scores = {}
        if vector_results:
            for r in vector_results:
                vector_scores[r.memory_id] = r.similarity_score

        rerank_scores = rerank_scores or {}

        # Build hybrid results
        hybrid_results = []

        for rank, fused in enumerate(fused_results, start=1):
            original = fused.original_result

            hybrid_results.append(HybridMemorySearchResult(
                memory_id=fused.chunk_id,
                rrf_score=fused.rrf_score,
                rank=rank,  # Use current position (may be reranked)
                title=original.title,
                content_preview=original.content_preview,
                memory_type=original.memory_type,
                tags=original.tags,
                created_at=original.created_at,
                author=original.author,
                lexical_score=lexical_scores.get(fused.chunk_id),
                vector_similarity=vector_scores.get(fused.chunk_id),
                rerank_score=rerank_scores.get(fused.chunk_id),  # EPIC-24 P2
                contribution=fused.contribution,
            ))

        return hybrid_results

    @staticmethod
    def _parse_pg_array(value) -> List[str]:
        """Parse PostgreSQL array to Python list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            if value == "{}":
                return []
            return value.strip("{}").split(",")
        return []
