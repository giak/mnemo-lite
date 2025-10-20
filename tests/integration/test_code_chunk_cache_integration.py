"""
Integration tests for L1 CodeChunkCache (EPIC-10 Story 10.1).

Tests cache integration with CodeIndexingService and API endpoints.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text

from services.caches import CodeChunkCache


@pytest_asyncio.fixture
async def cleanup_test_repository_cache(clean_db):
    """Clean up test repository data after cache tests."""
    test_repo_name = "cache-test-repo"

    yield test_repo_name

    # Clean up code_chunks for test repository
    async with clean_db.begin() as conn:
        await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repository"),
            {"repository": test_repo_name},
        )


@pytest.mark.anyio
class TestCodeChunkCacheIntegration:
    """Integration tests for L1 cache with CodeIndexingService."""

    async def test_cache_stats_endpoint(self, test_client):
        """Test /v1/code/index/cache/stats endpoint."""
        # Get or create cache
        if not hasattr(test_client.app.state, "code_chunk_cache"):
            cache = CodeChunkCache(max_size_mb=50)
            test_client.app.state.code_chunk_cache = cache
        else:
            cache = test_client.app.state.code_chunk_cache
            cache.clear()  # Clear for clean test

        # Populate cache
        cache.put(
            "file1.py",
            "code1",
            [{"name": "chunk1", "source_code": "code1"}],
        )
        cache.put(
            "file2.py",
            "code2",
            [{"name": "chunk2", "source_code": "code2"}],
        )

        # Hit cache
        cache.get("file1.py", "code1")

        # Miss cache
        cache.get("file3.py", "code3")

        # Call stats endpoint
        response = await test_client.get("/v1/code/index/cache/stats")

        assert response.status_code == 200
        stats = response.json()

        # Verify stats structure
        assert stats["type"] == "L1_memory"
        assert "max_size_mb" in stats
        assert stats["entries"] == 2
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert "hit_rate_percent" in stats
        assert "size_mb" in stats
        assert "utilization_percent" in stats

    async def test_cache_integration_with_indexing(
        self, test_client, cleanup_test_repository_cache
    ):
        """Test cache is used during repeat indexing operations."""
        # Get or create cache
        if not hasattr(test_client.app.state, "code_chunk_cache"):
            cache = CodeChunkCache(max_size_mb=10)
            test_client.app.state.code_chunk_cache = cache
        else:
            cache = test_client.app.state.code_chunk_cache

        file_path = "test_integration.py"
        source_code = "def test_function():\n    return 42"

        # First indexing
        response1 = await test_client.post(
            "/v1/code/index",
            json={
                "repository": cleanup_test_repository_cache,
                "files": [
                    {
                        "path": file_path,
                        "content": source_code,
                        "language": "python",
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False,
            },
        )

        assert response1.status_code == 201
        result1 = response1.json()
        assert result1["indexed_chunks"] > 0

        initial_hits = cache.hits

        # Second indexing (should use cache)
        response2 = await test_client.post(
            "/v1/code/index",
            json={
                "repository": cleanup_test_repository_cache,
                "files": [
                    {
                        "path": file_path,
                        "content": source_code,
                        "language": "python",
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False,
            },
        )

        assert response2.status_code == 201

        # Cache should have hits now
        assert cache.hits > initial_hits

    async def test_cache_invalidation_on_content_change(
        self, test_client, cleanup_test_repository_cache
    ):
        """Test cache invalidates when file content changes."""
        if not hasattr(test_client.app.state, "code_chunk_cache"):
            cache = CodeChunkCache(max_size_mb=10)
            test_client.app.state.code_chunk_cache = cache
        else:
            cache = test_client.app.state.code_chunk_cache

        file_path = "test_change.py"
        source_v1 = "def version_one():\n    return 1"
        source_v2 = "def version_two():\n    return 2"

        # Index version 1
        response1 = await test_client.post(
            "/v1/code/index",
            json={
                "repository": cleanup_test_repository_cache,
                "files": [
                    {"path": file_path, "content": source_v1, "language": "python"}
                ],
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False,
            },
        )

        assert response1.status_code == 201

        # Index version 2 (content changed)
        response2 = await test_client.post(
            "/v1/code/index",
            json={
                "repository": cleanup_test_repository_cache,
                "files": [
                    {"path": file_path, "content": source_v2, "language": "python"}
                ],
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False,
            },
        )

        assert response2.status_code == 201

        # Cache should have evicted old entry (hash mismatch)
        assert cache.evictions >= 1

    async def test_cache_with_multiple_files(
        self, test_client, cleanup_test_repository_cache
    ):
        """Test cache handles multiple files correctly."""
        if not hasattr(test_client.app.state, "code_chunk_cache"):
            cache = CodeChunkCache(max_size_mb=30)
            test_client.app.state.code_chunk_cache = cache
        else:
            cache = test_client.app.state.code_chunk_cache

        files = [
            {
                "path": f"file{i}.py",
                "content": f"def function_{i}():\n    return {i}",
                "language": "python",
            }
            for i in range(5)
        ]

        # Index all files
        response1 = await test_client.post(
            "/v1/code/index",
            json={
                "repository": cleanup_test_repository_cache,
                "files": files,
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False,
            },
        )

        assert response1.status_code == 201
        assert response1.json()["indexed_files"] == 5

        # Re-index same files (should use cache)
        initial_hits = cache.hits

        response2 = await test_client.post(
            "/v1/code/index",
            json={
                "repository": cleanup_test_repository_cache,
                "files": files,
                "extract_metadata": True,
                "generate_embeddings": False,
                "build_graph": False,
            },
        )

        assert response2.status_code == 201

        # Cache should have hits for all 5 files
        assert cache.hits >= initial_hits + 5
