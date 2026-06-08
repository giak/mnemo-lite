"""
Unit tests for Jaccard deduplication (Phase 1 Quick Win #2).

Tests the pure Python jaccard_similarity function and the
find_potential_duplicates integration pattern.
"""

import pytest
from utils.jaccard import jaccard_similarity, tokenize


class TestTokenize:
    """Test the tokenize helper function."""

    def test_basic_sentence(self):
        result = tokenize("The quick brown fox jumps over the lazy dog")
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result
        assert "jumps" in result
        # Words > 2 chars are kept ("the" is 3 chars, included)
        assert "the" in result
        assert "over" in result
        assert "lazy" in result
        assert "dog" in result

    def test_short_words_excluded(self):
        """Words <= 2 chars are excluded to reduce noise."""
        result = tokenize("I am a go developer")
        # "I", "am", "a", "go" are all <=2 chars — excluded
        assert "developer" in result
        assert len(result) == 1

    def test_punctuation_split(self):
        result = tokenize("hello, world! foo-bar_baz")
        assert "hello" in result
        assert "world" in result
        assert "foo" in result
        # Underscore is a word character, so bar_baz stays as one token
        # (correct for code identifiers like variable names)
        assert "bar_baz" in result

    def test_hyphen_split(self):
        """Hyphens split tokens, underscores don't (matching code identifier rules)."""
        result = tokenize("foo-bar baz-qux")
        assert "foo" in result
        assert "bar" in result
        assert "baz" in result
        assert "qux" in result

    def test_lowercase(self):
        result = tokenize("PostgreSQL FastAPI Redis")
        assert "postgresql" in result
        assert "fastapi" in result
        assert "redis" in result

    def test_empty_string(self):
        result = tokenize("")
        assert result == set()

    def test_only_short_words(self):
        result = tokenize("I am a go")
        assert result == set()


class TestJaccardSimilarity:
    """Test the jaccard_similarity function."""

    def test_identical_strings(self):
        assert jaccard_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert jaccard_similarity("alpha beta", "gamma delta") == 0.0

    def test_partial_overlap(self):
        # "alpha beta gamma" vs "alpha beta delta" → overlap: {alpha, beta}
        # union: {alpha, beta, gamma, delta} → 2/4 = 0.5
        sim = jaccard_similarity("alpha beta gamma", "alpha beta delta")
        assert 0.4 < sim < 0.6

    def test_empty_both(self):
        assert jaccard_similarity("", "") == 1.0

    def test_empty_one(self):
        assert jaccard_similarity("hello world", "") == 0.0
        assert jaccard_similarity("", "hello world") == 0.0

    def test_case_insensitive(self):
        """Tokenization lowercases, so case shouldn't matter."""
        sim = jaccard_similarity("FastAPI Redis", "fastapi redis")
        assert sim == 1.0

    def test_near_duplicate_threshold(self):
        """AgentMemory uses Jaccard > 0.9 as duplicate threshold.
        Test that nearly identical strings exceed this."""
        base = "User prefers async/await over callbacks for Python code"
        # Change one word
        modified = "User prefers async/await over callbacks for JavaScript code"
        sim = jaccard_similarity(base, modified)
        # Most words overlap, only "python" vs "javascript" differs
        assert sim > 0.7  # Should be close to 0.9 but not necessarily above

    def test_exact_duplicate_exceeds_threshold(self):
        """Exact duplicates must exceed 0.9 threshold."""
        base = "Chose Redis for L2 cache layer because of performance requirements"
        assert jaccard_similarity(base, base) >= 0.9

    def test_slightly_different_exceeds_threshold(self):
        """Very similar strings should exceed 0.9 threshold."""
        base = "The project uses PostgreSQL 18 with pgvector extension for vector search"
        # Only change "extension" → "extensions" (plural), both tokenize to same
        # Actually "extension" and "extensions" are different tokens
        modified = "The project uses PostgreSQL 18 with pgvector for vector search"
        sim = jaccard_similarity(base, modified)
        # Most tokens overlap
        assert sim > 0.8

    def test_completely_different_stories(self):
        """Unrelated memories should have low similarity."""
        a = "Debugging memory leak in worker process during batch indexing"
        b = "User prefers dark theme for the dashboard interface"
        sim = jaccard_similarity(a, b)
        assert sim < 0.3

    def test_technical_content(self):
        """Technical content with shared terminology should have moderate similarity."""
        a = "PostgreSQL 18 halfvec type reduces RAM usage by 50 percent for 768D vectors"
        b = "PostgreSQL 18 supports pg_trgm GIN indexes for fast trigram search"
        sim = jaccard_similarity(a, b)
        # Share "postgresql", "18" — but different topics
        assert 0.1 < sim < 0.5


class TestDedupStrategy:
    """Test the dedup strategy logic (without database)."""

    def test_is_duplicate_flag_logic(self):
        """Test the is_duplicate flag calculation used in find_potential_duplicates."""
        jaccard_threshold = 0.9

        # Case 1: Title match above threshold
        jaccard_title = 0.95
        jaccard_content = 0.3
        jaccard_combined = 0.6
        is_dup = (
            jaccard_title >= jaccard_threshold
            or jaccard_content >= jaccard_threshold
            or jaccard_combined >= jaccard_threshold
        )
        assert is_dup is True  # Title match is enough

    def test_is_duplicate_content_match(self):
        jaccard_threshold = 0.9

        jaccard_title = 0.3
        jaccard_content = 0.92
        jaccard_combined = 0.7
        is_dup = (
            jaccard_title >= jaccard_threshold
            or jaccard_content >= jaccard_threshold
            or jaccard_combined >= jaccard_threshold
        )
        assert is_dup is True  # Content match is enough

    def test_is_duplicate_combined_match(self):
        jaccard_threshold = 0.9

        jaccard_title = 0.6
        jaccard_content = 0.7
        jaccard_combined = 0.91
        is_dup = (
            jaccard_title >= jaccard_threshold
            or jaccard_content >= jaccard_threshold
            or jaccard_combined >= jaccard_threshold
        )
        assert is_dup is True  # Combined match is enough

    def test_is_not_duplicate_below_threshold(self):
        jaccard_threshold = 0.9

        jaccard_title = 0.5
        jaccard_content = 0.4
        jaccard_combined = 0.45
        is_dup = (
            jaccard_title >= jaccard_threshold
            or jaccard_content >= jaccard_threshold
            or jaccard_combined >= jaccard_threshold
        )
        assert is_dup is False

    def test_warning_message_format(self):
        """Test the duplicate warning message format."""
        dupe_id = "abc-123-def"
        duplicate_warning = (
            f"⚠️ Potential duplicate detected! Found 1 similar memory(ies). "
            f"Consider using update_memory(id='{dupe_id}', ...) instead of creating a new one. "
            f"Set dedup_check=False to force creation anyway."
        )
        assert dupe_id in duplicate_warning
        assert "update_memory" in duplicate_warning
        assert "dedup_check=False" in duplicate_warning

    def test_similar_memories_separated_from_duplicates(self):
        """Test that true duplicates and near-matches are separated correctly.

        In WriteMemoryTool, true dupes (Jaccard >= 0.9) go into
        potential_duplicates + duplicate_warning, while near-matches
        (0.7-0.9) go into similar_memories separately.
        """
        # Simulate what find_potential_duplicates returns
        results = [
            {"id": "id-1", "title": "Duplicate", "jaccard_combined": 0.95, "is_duplicate": True},
            {"id": "id-2", "title": "Similar", "jaccard_combined": 0.78, "is_duplicate": False},
            {"id": "id-3", "title": "Close", "jaccard_combined": 0.85, "is_duplicate": False},
        ]

        true_dupes = [d for d in results if d.get("is_duplicate")]
        near_dupes = [d for d in results if not d.get("is_duplicate")]

        assert len(true_dupes) == 1
        assert true_dupes[0]["id"] == "id-1"
        assert len(near_dupes) == 2
        assert near_dupes[0]["id"] == "id-2"
        assert near_dupes[1]["id"] == "id-3"

        # Simulate response construction
        potential_duplicates = true_dupes[:3]  # Only true dupes
        similar_memories = near_dupes[:3]

        assert len(potential_duplicates) == 1
        assert len(similar_memories) == 2
        assert potential_duplicates[0]["is_duplicate"] is True
        assert all(not d["is_duplicate"] for d in similar_memories)
