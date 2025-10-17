"""
RRF (Reciprocal Rank Fusion) Service.

Implements Reciprocal Rank Fusion algorithm for combining search results
from multiple sources (lexical, vector, etc.) without requiring score
normalization.

Reference: Cormack, Clarke, Buettcher (2009)
"Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods"
"""

import logging
from typing import List, Dict, Any, TypeVar, Generic, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

# Generic type for search results
T = TypeVar('T')


@dataclass
class FusedResult(Generic[T]):
    """
    Result after RRF fusion.

    Contains the original result object plus RRF score and metadata.
    """
    chunk_id: str
    rrf_score: float
    rank: int  # Final rank after fusion (1-indexed)
    original_result: T  # Original search result object
    contribution: Dict[str, float] = field(default_factory=dict)  # Score breakdown by source


class RRFFusionService:
    """
    Reciprocal Rank Fusion (RRF) service.

    Combines search results from multiple methods using rank-based scoring.
    RRF is scale-invariant and requires no score normalization.

    Formula:
        RRF_score(doc) = Σ 1 / (k + rank_i(doc))
        where i ∈ search_methods

    Features:
    - Scale-invariant (no normalization needed)
    - Robust to score distribution differences
    - Simple and effective
    - Supports weighted fusion
    - Supports arbitrary number of search methods

    Industry standard: k=60 (good balance)
    """

    def __init__(self, k: int = 60):
        """
        Initialize RRF fusion service.

        Args:
            k: RRF constant (default: 60)
               - Lower k (10-30): Emphasizes top ranks more
               - k=60: Balanced (industry standard) ⭐
               - Higher k (80-100): More democratic weighting
        """
        if k <= 0:
            raise ValueError("k must be positive")

        self.k = k
        logger.info(f"RRF Fusion Service initialized with k={k}")

    def fuse(
        self,
        *result_lists: List[Any],
        k: Optional[int] = None,
    ) -> List[FusedResult]:
        """
        Fuse multiple result lists using RRF.

        Args:
            *result_lists: Variable number of result lists
                          Each list must have items with 'chunk_id' attribute
            k: Optional override for k parameter

        Returns:
            List of FusedResult ordered by RRF score DESC

        Example:
            lexical_results = [result1, result2, ...]
            vector_results = [result3, result1, ...]
            fused = rrf.fuse(lexical_results, vector_results)
        """
        k = k if k is not None else self.k

        # Build RRF scores
        rrf_scores: Dict[str, float] = defaultdict(float)
        all_docs: Dict[str, Any] = {}
        contributions: Dict[str, Dict[str, float]] = defaultdict(dict)

        for method_idx, results in enumerate(result_lists):
            method_name = f"method_{method_idx}"

            for rank, result in enumerate(results, start=1):
                chunk_id = result.chunk_id
                score_contribution = 1 / (k + rank)

                rrf_scores[chunk_id] += score_contribution
                all_docs[chunk_id] = result
                contributions[chunk_id][method_name] = score_contribution

        # Sort by RRF score
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda doc_id: rrf_scores[doc_id],
            reverse=True
        )

        # Build fused results
        fused = []
        for final_rank, chunk_id in enumerate(sorted_ids, start=1):
            fused.append(FusedResult(
                chunk_id=chunk_id,
                rrf_score=rrf_scores[chunk_id],
                rank=final_rank,
                original_result=all_docs[chunk_id],
                contribution=contributions[chunk_id],
            ))

        logger.info(
            f"RRF fusion: {len(result_lists)} methods, "
            f"{len(fused)} unique documents, k={k}"
        )

        return fused

    def fuse_with_weights(
        self,
        weighted_results: List[tuple[List[Any], float]],
        k: Optional[int] = None,
    ) -> List[FusedResult]:
        """
        Weighted RRF fusion.

        Allows different weights for different search methods.

        Args:
            weighted_results: List of (results, weight) tuples
                             Weights should sum to 1.0 (not enforced)
            k: Optional override for k parameter

        Returns:
            List of FusedResult ordered by weighted RRF score DESC

        Example:
            fused = rrf.fuse_with_weights([
                (lexical_results, 0.6),  # 60% weight
                (vector_results, 0.4),   # 40% weight
            ])
        """
        k = k if k is not None else self.k

        # Build weighted RRF scores
        rrf_scores: Dict[str, float] = defaultdict(float)
        all_docs: Dict[str, Any] = {}
        contributions: Dict[str, Dict[str, float]] = defaultdict(dict)

        for method_idx, (results, weight) in enumerate(weighted_results):
            method_name = f"method_{method_idx}(w={weight:.2f})"

            for rank, result in enumerate(results, start=1):
                chunk_id = result.chunk_id
                score_contribution = weight / (k + rank)

                rrf_scores[chunk_id] += score_contribution
                all_docs[chunk_id] = result
                contributions[chunk_id][method_name] = score_contribution

        # Sort by weighted RRF score
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda doc_id: rrf_scores[doc_id],
            reverse=True
        )

        # Build fused results
        fused = []
        for final_rank, chunk_id in enumerate(sorted_ids, start=1):
            fused.append(FusedResult(
                chunk_id=chunk_id,
                rrf_score=rrf_scores[chunk_id],
                rank=final_rank,
                original_result=all_docs[chunk_id],
                contribution=contributions[chunk_id],
            ))

        logger.info(
            f"Weighted RRF fusion: {len(weighted_results)} methods, "
            f"{len(fused)} unique documents, k={k}"
        )

        return fused

    def fuse_with_metadata(
        self,
        results_with_meta: List[tuple[List[Any], str, float]],
        k: Optional[int] = None,
    ) -> List[FusedResult]:
        """
        RRF fusion with method names and weights.

        Args:
            results_with_meta: List of (results, method_name, weight) tuples
            k: Optional override for k parameter

        Returns:
            List of FusedResult with named contributions

        Example:
            fused = rrf.fuse_with_metadata([
                (lexical_results, "lexical_trgm", 0.6),
                (vector_results, "vector_hnsw", 0.4),
            ])
        """
        k = k if k is not None else self.k

        # Build RRF scores with metadata
        rrf_scores: Dict[str, float] = defaultdict(float)
        all_docs: Dict[str, Any] = {}
        contributions: Dict[str, Dict[str, float]] = defaultdict(dict)

        for results, method_name, weight in results_with_meta:
            for rank, result in enumerate(results, start=1):
                chunk_id = result.chunk_id
                score_contribution = weight / (k + rank)

                rrf_scores[chunk_id] += score_contribution
                all_docs[chunk_id] = result
                contributions[chunk_id][method_name] = score_contribution

        # Sort by RRF score
        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda doc_id: rrf_scores[doc_id],
            reverse=True
        )

        # Build fused results
        fused = []
        for final_rank, chunk_id in enumerate(sorted_ids, start=1):
            fused.append(FusedResult(
                chunk_id=chunk_id,
                rrf_score=rrf_scores[chunk_id],
                rank=final_rank,
                original_result=all_docs[chunk_id],
                contribution=contributions[chunk_id],
            ))

        logger.info(
            f"RRF fusion with metadata: {len(results_with_meta)} methods, "
            f"{len(fused)} unique documents, k={k}"
        )

        return fused

    def set_k(self, k: int) -> None:
        """
        Update RRF k parameter.

        Args:
            k: New k value
               - k=10-30: Emphasize top ranks
               - k=60: Balanced ⭐
               - k=80-100: More democratic
        """
        if k <= 0:
            raise ValueError("k must be positive")

        self.k = k
        logger.info(f"RRF k parameter updated to {k}")

    @staticmethod
    def calculate_rrf_score(rank: int, k: int = 60) -> float:
        """
        Calculate RRF score for a single rank.

        Args:
            rank: Document rank (1-indexed)
            k: RRF constant (default: 60)

        Returns:
            RRF score contribution

        Example:
            >>> RRFFusionService.calculate_rrf_score(rank=1, k=60)
            0.01639...  # 1 / (60 + 1)
        """
        return 1 / (k + rank)
