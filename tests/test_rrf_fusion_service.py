"""
Unit tests for RRFFusionService.

Tests the Reciprocal Rank Fusion algorithm implementation
including weighted fusion and metadata tracking.
"""

import pytest
from dataclasses import dataclass

from services.rrf_fusion_service import RRFFusionService, FusedResult


# Mock result class for testing
@dataclass
class MockSearchResult:
    """Mock search result for testing."""
    chunk_id: str


class TestRRFFusionService:
    """Tests for RRFFusionService."""

    def test_service_initialization_default_k(self):
        """Test service initialization with default k=60."""
        service = RRFFusionService()
        assert service.k == 60

    def test_service_initialization_custom_k(self):
        """Test service initialization with custom k."""
        service = RRFFusionService(k=100)
        assert service.k == 100

    def test_service_initialization_invalid_k(self):
        """Test service initialization with invalid k raises error."""
        with pytest.raises(ValueError, match="k must be positive"):
            RRFFusionService(k=0)

        with pytest.raises(ValueError, match="k must be positive"):
            RRFFusionService(k=-10)

    def test_fuse_single_result_list(self):
        """Test fusion with single result list."""
        service = RRFFusionService(k=60)

        results1 = [
            MockSearchResult(chunk_id="A"),  # rank 1 (position 0)
            MockSearchResult(chunk_id="B"),  # rank 2 (position 1)
            MockSearchResult(chunk_id="C"),  # rank 3 (position 2)
        ]

        fused = service.fuse(results1)

        assert len(fused) == 3
        assert fused[0].chunk_id == "A"
        assert fused[1].chunk_id == "B"
        assert fused[2].chunk_id == "C"

        # Check RRF scores (should be 1/(k+rank))
        assert abs(fused[0].rrf_score - (1/61)) < 1e-6
        assert abs(fused[1].rrf_score - (1/62)) < 1e-6
        assert abs(fused[2].rrf_score - (1/63)) < 1e-6

    def test_fuse_two_result_lists_no_overlap(self):
        """Test fusion with two result lists without overlap."""
        service = RRFFusionService(k=60)

        results1 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="B"),
        ]

        results2 = [
            MockSearchResult(chunk_id="C"),
            MockSearchResult(chunk_id="D"),
        ]

        fused = service.fuse(results1, results2)

        assert len(fused) == 4

        # All documents appear only once
        chunk_ids = [r.chunk_id for r in fused]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_fuse_two_result_lists_with_overlap(self):
        """Test fusion with two result lists with overlapping documents."""
        service = RRFFusionService(k=60)

        # Document A appears in both lists (rank 1 in both)
        # Document B appears only in list 1 (rank 2)
        # Document C appears only in list 2 (rank 2)
        results1 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="B"),
        ]

        results2 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="C"),
        ]

        fused = service.fuse(results1, results2)

        assert len(fused) == 3

        # Document A should rank first (appears in both)
        assert fused[0].chunk_id == "A"
        # A's score = 2 * 1/(60+1) = 2/61
        expected_a_score = 2 / 61
        assert abs(fused[0].rrf_score - expected_a_score) < 1e-6

    def test_fuse_overlap_different_ranks(self):
        """Test fusion where same document has different ranks in different methods."""
        service = RRFFusionService(k=60)

        # Document A: rank 1 in method1, rank 3 in method2
        # Document B: rank 2 in method1, rank 1 in method2
        # Document C: rank 3 in method1, rank 2 in method2
        results1 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="B"),
            MockSearchResult(chunk_id="C"),
        ]

        results2 = [
            MockSearchResult(chunk_id="B"),
            MockSearchResult(chunk_id="C"),
            MockSearchResult(chunk_id="A"),
        ]

        fused = service.fuse(results1, results2)

        # All 3 documents should appear
        assert len(fused) == 3

        # Calculate expected scores
        score_a = 1/61 + 1/63  # rank 1 in method1, rank 3 in method2
        score_b = 1/62 + 1/61  # rank 2 in method1, rank 1 in method2
        score_c = 1/63 + 1/62  # rank 3 in method1, rank 2 in method2

        # B should rank first (1/62 + 1/61 = highest)
        assert fused[0].chunk_id == "B"
        assert abs(fused[0].rrf_score - score_b) < 1e-6

    def test_weighted_fusion_equal_weights(self):
        """Test weighted fusion with equal weights (should be same as unweighted)."""
        service = RRFFusionService(k=60)

        results1 = [MockSearchResult(chunk_id="A")]
        results2 = [MockSearchResult(chunk_id="B")]

        # Unweighted
        fused_unweighted = service.fuse(results1, results2)

        # Weighted with equal weights
        fused_weighted = service.fuse_with_weights([
            (results1, 0.5),
            (results2, 0.5),
        ])

        # Scores should be proportional (weighted has 0.5 multiplier)
        assert len(fused_weighted) == len(fused_unweighted)

    def test_weighted_fusion_different_weights(self):
        """Test weighted fusion with different weights."""
        service = RRFFusionService(k=60)

        results1 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="B"),
        ]

        results2 = [
            MockSearchResult(chunk_id="B"),
            MockSearchResult(chunk_id="A"),
        ]

        # Give more weight to method 1 (0.7 vs 0.3)
        fused = service.fuse_with_weights([
            (results1, 0.7),
            (results2, 0.3),
        ])

        # Calculate expected scores
        # A: 0.7/(60+1) + 0.3/(60+2) = 0.7/61 + 0.3/62
        score_a = 0.7/61 + 0.3/62
        # B: 0.7/(60+2) + 0.3/(60+1) = 0.7/62 + 0.3/61
        score_b = 0.7/62 + 0.3/61

        # A should rank first (higher weight on rank 1)
        assert fused[0].chunk_id == "A"
        assert abs(fused[0].rrf_score - score_a) < 1e-6

        assert fused[1].chunk_id == "B"
        assert abs(fused[1].rrf_score - score_b) < 1e-6

    def test_fuse_with_metadata(self):
        """Test fusion with method names and weights."""
        service = RRFFusionService(k=60)

        results1 = [MockSearchResult(chunk_id="A")]
        results2 = [MockSearchResult(chunk_id="B")]

        fused = service.fuse_with_metadata([
            (results1, "lexical_trgm", 0.4),
            (results2, "vector_hnsw", 0.6),
        ])

        assert len(fused) == 2

        # Check that contributions have named methods
        assert "lexical_trgm" in fused[0].contribution or "vector_hnsw" in fused[0].contribution

    def test_fuse_empty_result_lists(self):
        """Test fusion with empty result lists."""
        service = RRFFusionService(k=60)

        fused = service.fuse([], [])

        assert len(fused) == 0

    def test_fuse_one_empty_one_full(self):
        """Test fusion with one empty and one full result list."""
        service = RRFFusionService(k=60)

        results1 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="B"),
        ]

        fused = service.fuse(results1, [])

        assert len(fused) == 2
        assert fused[0].chunk_id == "A"

    def test_fuse_with_custom_k_parameter(self):
        """Test fusion with custom k parameter override."""
        service = RRFFusionService(k=60)

        results1 = [MockSearchResult(chunk_id="A")]

        # Use default k
        fused_default = service.fuse(results1)

        # Override k
        fused_custom = service.fuse(results1, k=100)

        # Scores should be different
        assert fused_default[0].rrf_score != fused_custom[0].rrf_score

        # Custom k should produce lower score (1/101 vs 1/61)
        assert fused_custom[0].rrf_score < fused_default[0].rrf_score

    def test_set_k(self):
        """Test updating k parameter."""
        service = RRFFusionService(k=60)

        service.set_k(100)
        assert service.k == 100

        # Test invalid k
        with pytest.raises(ValueError, match="k must be positive"):
            service.set_k(0)

    def test_calculate_rrf_score_static_method(self):
        """Test static RRF score calculation."""
        # Rank 1, k=60 → 1/61
        score = RRFFusionService.calculate_rrf_score(rank=1, k=60)
        assert abs(score - (1/61)) < 1e-6

        # Rank 10, k=60 → 1/70
        score = RRFFusionService.calculate_rrf_score(rank=10, k=60)
        assert abs(score - (1/70)) < 1e-6

    def test_fuse_preserves_original_results(self):
        """Test that fusion preserves original result objects."""
        service = RRFFusionService(k=60)

        original_result = MockSearchResult(chunk_id="A")
        results1 = [original_result]

        fused = service.fuse(results1)

        # Original result should be preserved
        assert fused[0].original_result is original_result

    def test_fuse_rank_assignment(self):
        """Test that final ranks are assigned correctly (1-indexed)."""
        service = RRFFusionService(k=60)

        results1 = [
            MockSearchResult(chunk_id="A"),
            MockSearchResult(chunk_id="B"),
            MockSearchResult(chunk_id="C"),
        ]

        fused = service.fuse(results1)

        # Check ranks are 1-indexed and sequential
        assert fused[0].rank == 1
        assert fused[1].rank == 2
        assert fused[2].rank == 3

    def test_fuse_contribution_tracking(self):
        """Test that contribution tracking works correctly."""
        service = RRFFusionService(k=60)

        # A is at position 0 (rank 1) in both lists
        results1 = [MockSearchResult(chunk_id="A")]
        results2 = [MockSearchResult(chunk_id="A")]

        fused = service.fuse(results1, results2)

        # Document A should have contributions from both methods
        assert len(fused[0].contribution) == 2

        # Check contribution values
        method_0_contribution = fused[0].contribution.get("method_0")
        method_1_contribution = fused[0].contribution.get("method_1")

        assert method_0_contribution is not None
        assert method_1_contribution is not None

        # Both methods have A at rank 1 (position 0), so both contribute 1/61
        assert abs(method_0_contribution - (1/61)) < 1e-6
        assert abs(method_1_contribution - (1/61)) < 1e-6

    def test_fuse_three_methods(self):
        """Test fusion with three different search methods."""
        service = RRFFusionService(k=60)

        # A is at position 0 (rank 1) in all three lists
        results1 = [MockSearchResult(chunk_id="A")]
        results2 = [MockSearchResult(chunk_id="A")]
        results3 = [MockSearchResult(chunk_id="A")]

        fused = service.fuse(results1, results2, results3)

        # All three methods should contribute
        assert len(fused) == 1
        assert len(fused[0].contribution) == 3

        # Score should be sum of 3 * 1/61 (all at rank 1)
        expected_score = 3 * (1/61)
        assert abs(fused[0].rrf_score - expected_score) < 1e-6

    def test_fuse_many_results(self):
        """Test fusion with many results in list."""
        service = RRFFusionService(k=60)

        # Create 100 results
        results1 = [MockSearchResult(chunk_id=f"doc_{i}") for i in range(100)]

        fused = service.fuse(results1)

        # Should handle many results correctly
        assert len(fused) == 100
        assert fused[0].chunk_id == "doc_0"  # First result (rank 1)
        assert fused[99].chunk_id == "doc_99"  # Last result (rank 100)

        # Score decreases with rank
        assert fused[0].rrf_score > fused[99].rrf_score

        # Score for rank 100 should be 1/160
        assert abs(fused[99].rrf_score - (1/160)) < 1e-6
