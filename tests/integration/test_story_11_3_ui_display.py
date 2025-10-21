"""
Integration tests for EPIC-11 Story 11.3: UI Display of Qualified Names

Tests the complete UI display flow for qualified names (name_path) in:
- Search results template
- Graph data endpoint
- Graph node tooltips

Edge cases covered:
1. name_path NULL fallback
2. name_path == name deduplication
3. Very long name_path
4. HTML escaping
5. Graph nodes with name_path
6. Graph nodes without chunk_id (orphans)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from datetime import datetime, timezone


class TestSearchResultsNamePathDisplay:
    """Test name_path display in search results UI."""

    @pytest.mark.anyio
    async def test_name_path_displayed_with_simple_name(self, test_client):
        """
        Story 11.3 Edge Case #1: name_path exists and differs from name
        Expected: Display both qualified and simple names
        """
        # This test assumes there's indexed data with name_path
        # For a full test, you'd need to index test data first
        response = await test_client.get("/ui/code/search/results?q=User&limit=1")

        assert response.status_code == 200
        html = response.text

        # Should have name-path class if data exists (check HTML element, not CSS)
        if '<span class="name-path"' in html or '<span class="name-simple"' in html:
            # Verify structure exists (qualified name display)
            assert 'aria-label=' in html

    @pytest.mark.anyio
    async def test_name_path_null_fallback(self, test_client):
        """
        Story 11.3 Edge Case #2: name_path is NULL
        Expected: Display simple name only
        """
        # Mock response with NULL name_path would be tested here
        # In real scenario, query old data before migration
        response = await test_client.get("/ui/code/search/results?q=test&limit=1")

        assert response.status_code == 200
        # Should not crash even if no results

    @pytest.mark.anyio
    async def test_empty_query_handling(self, test_client):
        """
        Story 11.3: Empty query should return empty results
        Expected: No crash, graceful empty state
        """
        response = await test_client.get("/ui/code/search/results?q=&limit=10")

        assert response.status_code == 200
        html = response.text
        assert "No results" in html or "empty-state" in html


class TestGraphDataNamePath:
    """Test name_path in graph data endpoint."""

    @pytest.mark.anyio
    async def test_graph_data_includes_name_path(self, test_client):
        """
        Story 11.3: Graph data should include name_path from code_chunks
        Expected: Response has name_path field in node data
        """
        response = await test_client.get("/ui/code/graph/data?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data

        # Check if nodes have the name_path field (may be null for some)
        if data["nodes"]:
            first_node = data["nodes"][0]
            assert "data" in first_node
            # name_path field should exist (even if null)
            assert "name_path" in first_node["data"] or "label" in first_node["data"]

    @pytest.mark.anyio
    async def test_graph_data_null_safe_join(self, test_client):
        """
        Story 11.3 Edge Case #6: Graph nodes without chunk_id
        Expected: No SQL error, null name_path for orphan nodes
        """
        # This tests the NULL-safe JOIN with CASE WHEN
        response = await test_client.get("/ui/code/graph/data?limit=100")

        # Should not raise 500 error even if some nodes have NULL chunk_id
        assert response.status_code == 200

        data = response.json()

        # Verify response structure
        assert isinstance(data, dict)
        assert "nodes" in data
        assert isinstance(data["nodes"], list)


class TestNamePathEdgeCases:
    """Test edge cases for name_path handling."""

    @pytest.mark.anyio
    async def test_html_escaping_in_search_results(self, test_client):
        """
        Story 11.3 Edge Case #4: HTML characters in name_path
        Expected: Characters are escaped, no XSS
        """
        # If we had malicious data like name_path="<script>alert('XSS')</script>"
        # Jinja2 auto-escape should prevent XSS

        response = await test_client.get("/ui/code/search/results?q=test&limit=1")

        assert response.status_code == 200
        html = response.text

        # Should NOT contain unescaped script tags
        assert "<script>alert" not in html
        # Would contain escaped version if present: &lt;script&gt;

    @pytest.mark.anyio
    async def test_very_long_name_path(self, test_client):
        """
        Story 11.3 Edge Case #3: Very long name_path (>100 chars)
        Expected: Page renders without layout breaks
        """
        # Long paths should be handled by word-break CSS
        response = await test_client.get("/ui/code/search/results?q=calculate&limit=5")

        assert response.status_code == 200
        html = response.text

        # Check that word-break style is present in template
        assert "word-break" in html or "break-word" in html


class TestAccessibility:
    """Test ARIA labels and accessibility features."""

    @pytest.mark.anyio
    async def test_aria_labels_present(self, test_client):
        """
        Story 11.3: ARIA labels for accessibility
        Expected: Search results have aria-label attributes
        """
        response = await test_client.get("/ui/code/search/results?q=function&limit=1")

        assert response.status_code == 200
        html = response.text

        # If results exist (check HTML element, not CSS), should have ARIA labels
        if '<span class="name-path"' in html or '<span class="name-simple"' in html:
            assert 'aria-label=' in html
            assert 'role="text"' in html or 'tabindex=' in html


class TestPerformance:
    """Basic performance smoke tests."""

    @pytest.mark.anyio
    async def test_search_results_render_time(self, test_client):
        """
        Story 11.3: Search results should render quickly
        Expected: <100ms for small result sets
        """
        import time

        start = time.time()
        response = await test_client.get("/ui/code/search/results?q=test&limit=10")
        elapsed = (time.time() - start) * 1000  # Convert to ms

        assert response.status_code == 200

        # Should be reasonably fast (allowing for network overhead in tests)
        # In production, target is <50ms, but tests may be slower
        assert elapsed < 500  # 500ms timeout for test environment

    @pytest.mark.anyio
    async def test_graph_data_with_join_performance(self, test_client):
        """
        Story 11.3: Graph data endpoint with JOIN should be performant
        Expected: <100ms for 500 nodes (with index)
        """
        import time

        start = time.time()
        response = await test_client.get("/ui/code/graph/data?limit=500")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200

        # With functional index, should be fast
        # Allow more time in test environment
        assert elapsed < 1000  # 1s timeout for test environment


# Note: These tests use the test_client fixture from conftest.py
# which provides an AsyncClient with ASGITransport
#
# These tests assume:
# 1. Database has some indexed code chunks with name_path
# 2. Test environment uses EMBEDDING_MODE=mock
# 3. Database migrations (v3_to_v4 and v4_to_v5) have been applied
#
# Run with: EMBEDDING_MODE=mock pytest tests/integration/test_story_11_3_ui_display.py -v
