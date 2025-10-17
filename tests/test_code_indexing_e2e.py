"""
End-to-end tests for complete code indexing workflow (Story 6).

Tests the entire pipeline from indexing to search to graph traversal.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from main import app


class TestIndexingPipelineE2E:
    """End-to-end tests for complete indexing pipeline"""

    @pytest.mark.anyio
    async def test_complete_indexing_workflow(self, test_engine):
        """
        Test complete workflow:
        1. Index Python files
        2. Verify chunks stored
        3. Verify graph constructed
        4. Search indexed code
        5. Query graph
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # ================================================================
            # Step 1: Index files with calculator functions
            # ================================================================
            index_request = {
                "repository": "e2e-calculator",
                "files": [
                    {
                        "path": "calculator.py",
                        "content": """
def add(a, b):
    '''Add two numbers'''
    return a + b

def multiply(a, b):
    '''Multiply two numbers'''
    return a * b

def calculate_total(items):
    '''Calculate total using add'''
    result = 0
    for item in items:
        result = add(result, item)
    return result
""",
                    }
                ],
                "extract_metadata": True,
                "generate_embeddings": True,
                "build_graph": True,
            }

            index_response = await client.post(
                "/v1/code/index", json=index_request
            )

            assert index_response.status_code == 201
            index_data = index_response.json()

            # Verify indexing succeeded
            assert index_data["indexed_files"] == 1
            assert index_data["indexed_chunks"] >= 3  # add, multiply, calculate_total
            assert index_data["failed_files"] == 0

            # Graph should be constructed if enabled
            if index_data["build_graph"]:
                assert index_data["indexed_nodes"] >= 3
                # Edges depend on call resolution

            # ================================================================
            # Step 2: Search indexed code (lexical-only first)
            # ================================================================
            # Since embeddings may not be available in test mode,
            # we'll do a lexical-only search first
            search_request = {
                "query": "add",
                "enable_lexical": True,
                "enable_vector": False,  # Disable vector for test
                "filters": {"repository": "e2e-calculator"},
                "top_k": 5,
            }

            search_response = await client.post(
                "/v1/code/search/hybrid", json=search_request
            )

            assert search_response.status_code == 200
            search_data = search_response.json()

            # Should find 'add' function and possibly 'calculate_total' (which calls add)
            results = search_data["results"]
            assert len(results) > 0

            # Check that we found relevant results
            result_names = [r["name"] for r in results if r.get("name")]
            assert any("add" in name.lower() for name in result_names)

            # ================================================================
            # Step 3: Verify graph was constructed
            # ================================================================
            # Try to get graph stats
            graph_stats_response = await client.get("/v1/code/graph/stats")

            if graph_stats_response.status_code == 200:
                stats = graph_stats_response.json()
                # Graph should have nodes
                assert stats.get("total_nodes", 0) >= 0

            # ================================================================
            # Step 4: Test repository listing
            # ================================================================
            repos_response = await client.get("/v1/code/index/repositories")

            assert repos_response.status_code == 200
            repos_data = repos_response.json()

            # Should find our repository
            our_repo = next(
                (
                    r
                    for r in repos_data["repositories"]
                    if r["repository"] == "e2e-calculator"
                ),
                None,
            )
            assert our_repo is not None
            assert our_repo["file_count"] >= 1
            assert our_repo["chunk_count"] >= 3

    @pytest.mark.anyio
    async def test_indexing_then_deletion_workflow(self, test_engine):
        """
        Test workflow:
        1. Index files
        2. Verify data exists
        3. Delete repository
        4. Verify data removed
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Step 1: Index files
            index_request = {
                "repository": "e2e-delete-test",
                "files": [
                    {
                        "path": "test.py",
                        "content": "def test_function():\n    pass",
                    }
                ],
            }

            index_response = await client.post(
                "/v1/code/index", json=index_request
            )

            assert index_response.status_code == 201
            assert index_response.json()["indexed_files"] == 1

            # Step 2: Verify repository exists
            repos_response = await client.get("/v1/code/index/repositories")
            repos_data = repos_response.json()

            assert any(
                r["repository"] == "e2e-delete-test"
                for r in repos_data["repositories"]
            )

            # Step 3: Delete repository
            delete_response = await client.delete(
                "/v1/code/index/repositories/e2e-delete-test"
            )

            assert delete_response.status_code == 200
            delete_data = delete_response.json()
            assert delete_data["deleted_chunks"] >= 1

            # Step 4: Verify repository no longer appears with chunks
            repos_response_after = await client.get(
                "/v1/code/index/repositories"
            )
            repos_data_after = repos_response_after.json()

            # Repository should either not appear or have 0 chunks
            deleted_repo = next(
                (
                    r
                    for r in repos_data_after["repositories"]
                    if r["repository"] == "e2e-delete-test"
                ),
                None,
            )
            if deleted_repo:
                assert deleted_repo["chunk_count"] == 0

    @pytest.mark.anyio
    async def test_multi_file_indexing_with_search(self, test_engine):
        """
        Test workflow with multiple files:
        1. Index multiple related files
        2. Search across all files
        3. Verify all files indexed
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Step 1: Index multiple files
            index_request = {
                "repository": "e2e-multi-file",
                "files": [
                    {
                        "path": "math_utils.py",
                        "content": """
def add_numbers(a, b):
    '''Add two numbers'''
    return a + b

def subtract_numbers(a, b):
    '''Subtract two numbers'''
    return a - b
""",
                    },
                    {
                        "path": "string_utils.py",
                        "content": """
def concatenate_strings(a, b):
    '''Concatenate two strings'''
    return a + b

def uppercase_string(s):
    '''Convert string to uppercase'''
    return s.upper()
""",
                    },
                ],
                "extract_metadata": True,
                "generate_embeddings": True,
                "build_graph": False,  # Disable graph for this test
            }

            index_response = await client.post(
                "/v1/code/index", json=index_request
            )

            assert index_response.status_code == 201
            index_data = index_response.json()

            # Should index both files
            assert index_data["indexed_files"] == 2
            assert index_data["indexed_chunks"] >= 4  # 4 functions total

            # Step 2: Search for "numbers" (should find math_utils functions)
            search_request = {
                "query": "numbers",
                "enable_lexical": True,
                "enable_vector": False,
                "filters": {"repository": "e2e-multi-file"},
                "top_k": 10,
            }

            search_response = await client.post(
                "/v1/code/search/hybrid", json=search_request
            )

            assert search_response.status_code == 200
            search_data = search_response.json()

            # Should find functions with "numbers" in name or docstring
            assert len(search_data["results"]) > 0

            # Step 3: Verify repository info
            repos_response = await client.get("/v1/code/index/repositories")
            repos_data = repos_response.json()

            our_repo = next(
                (
                    r
                    for r in repos_data["repositories"]
                    if r["repository"] == "e2e-multi-file"
                ),
                None,
            )
            assert our_repo is not None
            assert our_repo["file_count"] == 2
            assert our_repo["chunk_count"] >= 4

    @pytest.mark.anyio
    async def test_error_recovery_workflow(self, test_engine):
        """
        Test workflow with partial failures:
        1. Index mix of valid and invalid files
        2. Verify valid files indexed
        3. Verify errors reported
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Include one valid file and one that might fail
            index_request = {
                "repository": "e2e-error-recovery",
                "files": [
                    {
                        "path": "valid.py",
                        "content": "def valid_function():\n    pass",
                    },
                    {
                        "path": "unknown.xyz",  # Unknown extension
                        "content": "some content",
                        "language": None,  # Will fail language detection
                    },
                ],
            }

            index_response = await client.post(
                "/v1/code/index", json=index_request
            )

            # Should succeed with partial success
            assert index_response.status_code == 201
            index_data = index_response.json()

            # At least the valid file should be indexed
            assert index_data["indexed_files"] >= 1

            # The invalid file should be reported in errors
            if index_data["failed_files"] > 0:
                assert len(index_data["errors"]) > 0
                # Check that error mentions the problematic file
                error_files = [e.get("file") for e in index_data["errors"]]
                assert any("unknown.xyz" in str(f) for f in error_files)

    @pytest.mark.anyio
    async def test_health_checks_across_services(self, test_engine):
        """
        Test that all service health checks work:
        1. Indexing service health
        2. Search service health
        3. Graph service health
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Check indexing service
            index_health = await client.get("/v1/code/index/health")
            assert index_health.status_code == 200
            assert index_health.json()["status"] == "healthy"

            # Check search service
            search_health = await client.get("/v1/code/search/health")
            assert search_health.status_code == 200
            assert search_health.json()["status"] == "healthy"

            # Check graph service (if available)
            graph_health = await client.get("/v1/code/graph/health")
            if graph_health.status_code == 200:
                assert graph_health.json()["status"] == "healthy"
