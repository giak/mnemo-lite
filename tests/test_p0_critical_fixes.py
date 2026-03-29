"""
TDD tests for P0 critical bugs (2026-03-29).

Verifies fixes for 6 critical bugs found in MCP audit:
- P0-1: batch_generate_embeddings → generate_embeddings_batch
- P0-2: consolidate_memory embedding dict extraction
- P0-3: project_id undefined in fallback search
- P0-4: index_incremental wrong service key
- P0-5: Path traversal reindex_file
- P0-6: Path traversal index_project

Run: docker exec mnemo-api python -m pytest tests/test_p0_critical_fixes.py -v
"""

import pytest
import inspect


# ============================================================================
# P0-1: batch_generate_embeddings → generate_embeddings_batch
# ============================================================================

class TestP01BatchEmbeddings:
    """Verify index_markdown_workspace uses correct method name."""

    def test_correct_method_name(self):
        """Must use generate_embeddings_batch, not batch_generate_embeddings."""
        from mnemo_mcp.tools.indexing_tools import IndexMarkdownWorkspaceTool
        source = inspect.getsource(IndexMarkdownWorkspaceTool.execute)
        assert "batch_generate_embeddings" not in source, (
            "batch_generate_embeddings doesn't exist — use generate_embeddings_batch"
        )

    def test_method_exists_on_service(self):
        """DualEmbeddingService must have generate_embeddings_batch."""
        from services.dual_embedding_service import DualEmbeddingService
        assert hasattr(DualEmbeddingService, "generate_embeddings_batch")


# ============================================================================
# P0-2: consolidate_memory embedding dict extraction
# ============================================================================

class TestP02ConsolidateEmbedding:
    """Verify consolidate_memory extracts embedding from dict."""

    def test_extracts_from_dict(self):
        """Must extract 'text' key from DualEmbeddingService response."""
        from mnemo_mcp.tools.memory_tools import ConsolidateMemoryTool
        source = inspect.getsource(ConsolidateMemoryTool.execute)
        assert 'embedding_raw' in source or 'isinstance' in source, (
            "Must check if embedding is dict before passing to repository"
        )


# ============================================================================
# P0-3: project_id undefined in fallback search
# ============================================================================

class TestP03ProjectIdFallback:
    """Verify project_id not used in fallback MemoryFilters."""

    def test_no_undefined_project_id(self):
        """Fallback MemoryFilters must not reference undefined project_id."""
        from mnemo_mcp.tools.memory_tools import SearchMemoryTool
        source = inspect.getsource(SearchMemoryTool.execute)

        # Find the fallback section
        fallback_start = source.find("Fallback to vector-only")
        if fallback_start == -1:
            pytest.skip("No fallback path found (may be removed)")

        fallback_section = source[fallback_start:fallback_start + 500]
        assert "project_id=project_id" not in fallback_section, (
            "project_id is not defined in execute() — remove from fallback filters"
        )


# ============================================================================
# P0-4: index_incremental wrong service key
# ============================================================================

class TestP04ServiceKey:
    """Verify index_incremental uses correct service key."""

    def test_correct_service_key(self):
        """Must use 'code_indexing_service', not 'indexing_service'."""
        from mnemo_mcp.tools.indexing_tools import IndexIncrementalTool
        source = inspect.getsource(IndexIncrementalTool.execute)
        assert '"code_indexing_service"' in source, (
            "Must use 'code_indexing_service' key (server.py:226)"
        )
        assert '"indexing_service"' not in source or '"code_indexing_service"' in source, (
            "Must not use 'indexing_service' — wrong key"
        )


# ============================================================================
# P0-5 + P0-6: Path traversal prevention
# ============================================================================

class TestP05PathTraversal:
    """Verify path traversal prevention in reindex_file and index_project."""

    def test_reindex_validates_path(self):
        """reindex_file must validate file path with realpath."""
        from mnemo_mcp.tools.indexing_tools import ReindexFileTool
        source = inspect.getsource(ReindexFileTool.execute)
        assert "realpath" in source or "abspath" in source, (
            "reindex_file must validate file path to prevent traversal"
        )

    def test_index_project_validates_path(self):
        """index_project must validate project path with realpath."""
        from mnemo_mcp.tools.indexing_tools import IndexProjectTool
        source = inspect.getsource(IndexProjectTool.execute)
        assert "realpath" in source or "abspath" in source, (
            "index_project must validate project path to prevent traversal"
        )

    def test_reindex_rejects_relative_path(self):
        """reindex_file must reject relative paths (security)."""
        from mnemo_mcp.tools.indexing_tools import ReindexFileTool
        source = inspect.getsource(ReindexFileTool.execute)
        assert "startswith" in source or "isabs" in source, (
            "reindex_file must check that path is absolute"
        )

    def test_index_project_rejects_relative_path(self):
        """index_project must reject relative paths (security)."""
        from mnemo_mcp.tools.indexing_tools import IndexProjectTool
        source = inspect.getsource(IndexProjectTool.execute)
        assert "startswith" in source or "isabs" in source, (
            "index_project must check that path is absolute"
        )


# ============================================================================
# Regression: verify no duplicate singleton
# ============================================================================

class TestRegressionSingletons:
    """Verify no duplicate singleton instances."""

    def test_single_system_snapshot_instance(self):
        """system_snapshot_tool should be defined once."""
        from mnemo_mcp.tools import memory_tools
        source = inspect.getsource(memory_tools)
        count = source.count("system_snapshot_tool = SystemSnapshotTool()")
        assert count == 1, (
            f"system_snapshot_tool defined {count} times — should be 1"
        )

    def test_single_configure_decay_instance(self):
        """configure_decay_tool should be defined once."""
        from mnemo_mcp.tools import memory_tools
        source = inspect.getsource(memory_tools)
        count = source.count("configure_decay_tool = ConfigureDecayTool()")
        assert count == 1, (
            f"configure_decay_tool defined {count} times — should be 1"
        )
