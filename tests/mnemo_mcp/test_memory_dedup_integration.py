"""
Integration tests for find_potential_duplicates with real database.

Tests the two-stage duplicate detection pipeline:
  1. SQL: pg_trgm similarity on title (fast, GIN-indexed)
  2. Python: Jaccard similarity on title+content (confirmation)

Uses the clean_db fixture for test isolation with a real PostgreSQL instance.
Requires: pg_trgm extension and idx_memories_title_trgm GIN index (migration v9->v10).
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.memory_repository import MemoryRepository
from mnemo_mcp.models.memory_models import MemoryCreate, MemoryType


@pytest_asyncio.fixture
async def memory_repo(clean_db: AsyncEngine) -> MemoryRepository:
    """MemoryRepository with real test database engine."""
    return MemoryRepository(clean_db)


@pytest_asyncio.fixture
def sample_embedding():
    """Minimal embedding vector (dimension does not matter for dedup tests)."""
    return [0.1] * 768


async def _create_memory(
    repo: MemoryRepository,
    title: str,
    content: str,
    memory_type: MemoryType = MemoryType.NOTE,
    tags: list | None = None,
    author: str = "DedupTest",
    project_id: str | None = None,
    embedding: list | None = None,
) -> str:
    """Helper: create a memory and return its ID."""
    mc = MemoryCreate(
        title=title,
        content=content,
        memory_type=memory_type,
        tags=tags or ["dedup-test"],
        author=author,
        project_id=project_id,
    )
    memory = await repo.create(mc, embedding=embedding)
    return str(memory.id)


# ---------------------------------------------------------------------------
# Test: find_potential_duplicates with real DB
# ---------------------------------------------------------------------------


class TestFindPotentialDuplicatesIntegration:
    """Integration tests using real PostgreSQL with pg_trgm."""

    @pytest.mark.asyncio
    async def test_no_duplicates_on_empty_db(self, memory_repo):
        """With no existing memories, find_potential_duplicates returns []."""
        results = await memory_repo.find_potential_duplicates(
            title="Brand New Memory",
            content="Something completely original",
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_exact_duplicate_title_detected(self, memory_repo, sample_embedding):
        """An exact same title should be detected as duplicate (Jaccard=1.0)."""
        title = "Redis configuration for caching"
        content = "Use Redis as L2 cache with TTL 300s"

        # Create first memory
        await _create_memory(memory_repo, title, content, embedding=sample_embedding)

        # Check for duplicates with same title
        results = await memory_repo.find_potential_duplicates(
            title=title,
            content="Different content but same title",
        )

        assert len(results) >= 1
        dupe = results[0]
        assert dupe["is_duplicate"] is True
        assert dupe["jaccard_title"] == 1.0
        assert dupe["title"] == title

    @pytest.mark.asyncio
    async def test_near_duplicate_title_detected(self, memory_repo, sample_embedding):
        """Near-identical titles should be detected as near-matches.

        Two-stage pipeline: pg_trgm pre-filter (threshold 0.3) then Python
        Jaccard confirmation (kept if >= 0.7).  We use titles that differ
        by only one word so Jaccard_title >= 0.7 (6/8 = 0.75).
        """
        await _create_memory(
            memory_repo,
            title="Redis caching configuration for the production environment",
            content="Set pool_size=10, max_overflow=5",
            embedding=sample_embedding,
        )

        # Same title except one word: "production" -> "staging"
        # tokenize() keeps words > 2 chars: redis, caching, configuration, for, the, environment
        # intersection = 7, union = 9 (add production, staging)  =>  Jaccard = 7/9 ~ 0.778
        results = await memory_repo.find_potential_duplicates(
            title="Redis caching configuration for the staging environment",
            content="Adjust pool for staging workload",
        )

        assert len(results) >= 1, "Expected at least one candidate from pg_trgm pre-filter"
        assert results[0]["jaccard_title"] >= 0.7
        assert "id" in results[0]
        assert "title" in results[0]
        assert "jaccard_combined" in results[0]

    @pytest.mark.asyncio
    async def test_dissimilar_title_not_flagged(self, memory_repo, sample_embedding):
        """Completely unrelated titles should NOT be flagged as is_duplicate."""
        # Create existing memory
        await _create_memory(
            memory_repo,
            title="Docker compose setup for development",
            content="Use docker-compose.yml with 8 containers",
            embedding=sample_embedding,
        )

        # Check with completely different title
        results = await memory_repo.find_potential_duplicates(
            title="Git branching strategy for releases",
            content="Use trunk-based development with feature flags",
        )

        # pg_trgm threshold is 0.3, so very different titles may still appear
        # but Jaccard should be low - none should be flagged as is_duplicate
        for result in results:
            assert result["is_duplicate"] is False

    @pytest.mark.asyncio
    async def test_duplicate_content_detected(self, memory_repo, sample_embedding):
        """Same content but different titles - content Jaccard should catch it.

        Uses similar-enough titles (shared word) so pg_trgm surfaces the candidate,
        then Jaccard on identical content confirms is_duplicate=True.
        """
        content = "User prefers async/await over callback patterns in Python code"

        await _create_memory(
            memory_repo,
            title="Async code style preference",
            content=content,
            embedding=sample_embedding,
        )

        # Title shares "Async" so pg_trgm should catch it; exact same content
        results = await memory_repo.find_potential_duplicates(
            title="Async patterns preference note",
            content=content,
            title_similarity_threshold=0.1,  # Lower threshold to ensure pg_trgm catches it
        )

        assert len(results) >= 1, "Expected at least one candidate from pg_trgm pre-filter"
        # Content Jaccard should be 1.0 (exact same content)
        content_match = [r for r in results if r["jaccard_content"] == 1.0]
        assert len(content_match) >= 1, "Expected exact content match (Jaccard=1.0)"
        assert content_match[0]["is_duplicate"] is True

    @pytest.mark.asyncio
    async def test_combined_jaccard_flag(self, memory_repo, sample_embedding):
        """Combined title+content Jaccard >= 0.9 flags as duplicate."""
        title = "Decision: Use pgvector for vector search"
        content = (
            "After evaluating options (Weaviate, Milvus, pgvector), "
            "we chose pgvector for its PostgreSQL integration and HNSW support."
        )

        await _create_memory(memory_repo, title, content, embedding=sample_embedding)

        # Slightly rephrased but semantically identical
        results = await memory_repo.find_potential_duplicates(
            title="Decision: Use pgvector for vector search",
            content=(
                "After evaluating options (Weaviate, Milvus, pgvector), "
                "we selected pgvector for its PostgreSQL integration and HNSW indexing."
            ),
        )

        # Same title => jaccard_title = 1.0 => is_duplicate = True
        assert len(results) >= 1
        assert results[0]["is_duplicate"] is True
        assert results[0]["jaccard_title"] == 1.0

    @pytest.mark.asyncio
    async def test_project_id_scoping(self, memory_repo, sample_embedding, clean_db):
        """Duplicate check can be scoped to a specific project_id."""
        from sqlalchemy import text as sql_text

        title = "API authentication strategy"
        content = "Use JWT tokens with RS256 signing"

        # Create real project rows to satisfy FK constraint
        project_a_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        project_b_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        async with clean_db.begin() as conn:
            await conn.execute(sql_text(
                "INSERT INTO projects (id, name, display_name) VALUES "
                "(:a, 'project-a', 'Project A'), "
                "(:b, 'project-b', 'Project B')"
                " ON CONFLICT (id) DO NOTHING"
            ), {"a": project_a_id, "b": project_b_id})

        # Create in project A
        await _create_memory(
            memory_repo, title, content,
            project_id=project_a_id,
            embedding=sample_embedding,
        )

        # Check scoped to project B - should not find project A's memory
        results_b = await memory_repo.find_potential_duplicates(
            title=title,
            content=content,
            project_id=project_b_id,
        )
        assert results_b == []

        # Check scoped to project A - should find the memory
        results_a = await memory_repo.find_potential_duplicates(
            title=title,
            content=content,
            project_id=project_a_id,
        )
        assert len(results_a) >= 1
        assert results_a[0]["is_duplicate"] is True

    @pytest.mark.asyncio
    async def test_multiple_duplicates_returned(self, memory_repo, sample_embedding):
        """When multiple near-duplicates exist, all are returned sorted by Jaccard."""
        base_title = "Memory architecture overview"
        base_content = "MnemoLite uses dual embedding with pgvector halfvec for vector search"

        # Create 3 similar memories
        await _create_memory(
            memory_repo, base_title, base_content,
            embedding=sample_embedding,
        )
        await _create_memory(
            memory_repo,
            "Memory architecture design",
            "MnemoLite uses dual embedding with pgvector for efficient vector search",
            embedding=sample_embedding,
        )
        await _create_memory(
            memory_repo,
            "Memory architecture summary",
            "Dual embedding approach with pgvector halfvec in MnemoLite",
            embedding=sample_embedding,
        )

        results = await memory_repo.find_potential_duplicates(
            title=base_title,
            content=base_content,
            limit=10,
        )

        # Should find multiple candidates
        assert len(results) >= 2
        # Results sorted by jaccard_combined descending
        jaccards = [r["jaccard_combined"] for r in results]
        assert jaccards == sorted(jaccards, reverse=True)
        # First result should be the exact match (Jaccard=1.0)
        assert results[0]["jaccard_combined"] == 1.0

    @pytest.mark.asyncio
    async def test_soft_deleted_memories_excluded(self, memory_repo, sample_embedding):
        """Soft-deleted memories should not appear as potential duplicates."""
        title = "Deprecated pattern: callback style"
        content = "Old codebase uses callbacks instead of async/await"

        # Create and then soft-delete
        memory_id = await _create_memory(
            memory_repo, title, content, embedding=sample_embedding,
        )
        await memory_repo.soft_delete(memory_id)

        # Check for duplicates - should not find the soft-deleted memory
        results = await memory_repo.find_potential_duplicates(
            title=title,
            content=content,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_empty_title(self, memory_repo):
        """Empty title returns empty list without raising (no trigrams to match).

        Note: this tests the "no candidates" path, not the exception handler
        (except Exception: return []). Testing a true DB error would require
        disconnecting the engine, which is fragile in integration tests.
        """
        results = await memory_repo.find_potential_duplicates(
            title="",
            content="Some valid content here",
        )
        # Empty title => no trigram matches => empty list
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_result_structure(self, memory_repo, sample_embedding):
        """Verify the structure of returned duplicate dicts."""
        title = "Cache invalidation strategy"
        content = "Use Redis pub/sub for cache invalidation across instances"

        await _create_memory(memory_repo, title, content, embedding=sample_embedding)

        results = await memory_repo.find_potential_duplicates(
            title=title,
            content="Updated cache invalidation with Redis pub/sub",
        )

        assert len(results) >= 1, "Expected at least one candidate from pg_trgm pre-filter"
        dupe = results[0]
        # Required keys per the method contract
        assert "id" in dupe
        assert "title" in dupe
        assert "content_preview" in dupe
        assert "memory_type" in dupe
        assert "tags" in dupe
        assert "created_at" in dupe
        assert "jaccard_title" in dupe
        assert "jaccard_content" in dupe
        assert "jaccard_combined" in dupe
        assert "is_duplicate" in dupe

        # Types
        assert isinstance(dupe["id"], str)
        assert isinstance(dupe["jaccard_title"], float)
        assert isinstance(dupe["jaccard_content"], float)
        assert isinstance(dupe["jaccard_combined"], float)
        assert isinstance(dupe["is_duplicate"], bool)
        assert 0.0 <= dupe["jaccard_title"] <= 1.0
        assert 0.0 <= dupe["jaccard_content"] <= 1.0
        assert 0.0 <= dupe["jaccard_combined"] <= 1.0
