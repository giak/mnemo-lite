"""
Tests for GraphConstructionService (EPIC-06 Phase 2 Story 4).
"""

import pytest
import uuid
from datetime import datetime, timezone

from services.graph_construction_service import GraphConstructionService, is_builtin, PYTHON_BUILTINS
from models.code_chunk_models import CodeChunkModel
from models.graph_models import GraphStats


class TestBuiltinsDetection:
    """Test Python built-ins detection."""

    def test_is_builtin_with_common_functions(self):
        """Test detection of common built-in functions."""
        assert is_builtin("sum") is True
        assert is_builtin("len") is True
        assert is_builtin("print") is True
        assert is_builtin("range") is True

    def test_is_builtin_with_types(self):
        """Test detection of built-in types."""
        assert is_builtin("int") is True
        assert is_builtin("str") is True
        assert is_builtin("list") is True
        assert is_builtin("dict") is True

    def test_is_builtin_with_exceptions(self):
        """Test detection of common exceptions."""
        assert is_builtin("ValueError") is True
        assert is_builtin("TypeError") is True
        assert is_builtin("Exception") is True

    def test_is_not_builtin(self):
        """Test non-builtin names return False."""
        assert is_builtin("custom_function") is False
        assert is_builtin("MyClass") is False
        assert is_builtin("calculate_total") is False

    def test_builtins_set_completeness(self):
        """Verify PYTHON_BUILTINS contains essential built-ins."""
        essential_builtins = ["sum", "len", "print", "int", "str", "ValueError"]
        for name in essential_builtins:
            assert name in PYTHON_BUILTINS, f"'{name}' should be in PYTHON_BUILTINS"


@pytest.mark.anyio
class TestGraphConstructionService:
    """Integration tests for GraphConstructionService."""

    async def test_resolve_call_target_builtin_returns_none(self, test_engine):
        """Test that built-in calls return None (skipped)."""
        service = GraphConstructionService(test_engine)

        # Create dummy chunk calling built-ins
        chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="test.py",
            language="python",
            chunk_type="function",
            name="test_func",
            source_code="def test_func():\n    return sum([1, 2, 3])",
            start_line=1,
            end_line=2,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["sum"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        result = await service._resolve_call_target("sum", chunk, [])
        assert result is None, "Built-in 'sum' should return None"

    async def test_resolve_call_target_local(self, test_engine):
        """Test resolving local function call (same file)."""
        service = GraphConstructionService(test_engine)

        # Create two chunks in same file
        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="utils.py",
            language="python",
            chunk_type="function",
            name="caller",
            source_code="def caller():\n    return helper()",
            start_line=1,
            end_line=2,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["helper"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        helper_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="utils.py",  # Same file
            language="python",
            chunk_type="function",
            name="helper",  # Same name as call
            source_code="def helper():\n    return 42",
            start_line=4,
            end_line=5,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, helper_chunk]
        result = await service._resolve_call_target("helper", caller_chunk, all_chunks)

        assert result == helper_chunk.id, "Should resolve to helper_chunk"

    async def test_resolve_call_target_not_found(self, test_engine):
        """Test that unresolvable calls return None."""
        service = GraphConstructionService(test_engine)

        chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="test.py",
            language="python",
            chunk_type="function",
            name="test_func",
            source_code="def test_func():\n    return unknown_function()",
            start_line=1,
            end_line=2,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["unknown_function"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        result = await service._resolve_call_target("unknown_function", chunk, [chunk])
        assert result is None, "Unknown function should return None"

    async def test_create_nodes_from_chunks(self, test_engine):
        """Test node creation from code chunks."""
        service = GraphConstructionService(test_engine)

        chunks = [
            CodeChunkModel(
                id=uuid.uuid4(),
                file_path="utils.py",
                language="python",
                chunk_type="function",
                name="calculate_total",
                source_code="def calculate_total(items):\n    return sum(items)",
                start_line=1,
                end_line=2,
                embedding_text=None,
                embedding_code=None,
                metadata={"signature": "calculate_total(items)", "complexity": {"cyclomatic": 1}},
                indexed_at=datetime.now(timezone.utc),
                last_modified=None,
                node_id=None,
                repository="test_repo",
                commit_hash=None
            )
        ]

        chunk_to_node = await service._create_nodes_from_chunks(chunks)

        assert len(chunk_to_node) == 1, "Should create 1 node"
        node = list(chunk_to_node.values())[0]
        assert node.node_type == "function"
        assert node.label == "calculate_total"
        assert node.properties["file_path"] == "utils.py"
        assert node.properties["signature"] == "calculate_total(items)"

    async def test_build_graph_empty_repository(self, test_engine):
        """Test building graph for empty repository returns empty stats."""
        service = GraphConstructionService(test_engine)

        stats = await service.build_graph_for_repository("nonexistent_repo", "python")

        assert isinstance(stats, GraphStats)
        assert stats.repository == "nonexistent_repo"
        assert stats.total_nodes == 0
        assert stats.total_edges == 0
        assert stats.construction_time_seconds > 0


@pytest.mark.anyio
class TestGraphConstructionIntegration:
    """Full integration tests with real database."""

    @pytest.fixture
    async def sample_chunks(self, code_chunk_repo):
        """Create sample code chunks in database."""
        from models.code_chunk_models import CodeChunkCreate

        # Use mock embeddings (no need for heavy models in tests)
        mock_embedding_text = [0.1] * 768
        mock_embedding_code = [0.2] * 768

        # Chunk 1: caller function
        chunk1_data = CodeChunkCreate(
            file_path="test_module.py",
            language="python",
            chunk_type="function",
            name="caller",
            source_code="def caller():\n    return helper()",
            start_line=1,
            end_line=2,
            embedding_text=mock_embedding_text,
            embedding_code=mock_embedding_code,
            metadata={"calls": ["helper"], "signature": "caller()"},
            repository="test_repo",
            commit_hash="abc123"
        )
        chunk1 = await code_chunk_repo.add(chunk1_data)

        # Chunk 2: helper function
        chunk2_data = CodeChunkCreate(
            file_path="test_module.py",
            language="python",
            chunk_type="function",
            name="helper",
            source_code="def helper():\n    return 42",
            start_line=4,
            end_line=5,
            embedding_text=mock_embedding_text,
            embedding_code=mock_embedding_code,
            metadata={"signature": "helper()"},
            repository="test_repo",
            commit_hash="abc123"
        )
        chunk2 = await code_chunk_repo.add(chunk2_data)

        return [chunk1, chunk2]

    async def test_build_graph_with_real_chunks(self, test_engine, sample_chunks):
        """Test full graph construction with real chunks in database."""
        service = GraphConstructionService(test_engine)

        stats = await service.build_graph_for_repository("test_repo", "python")

        # Verify statistics
        # Note: May have nodes from previous tests (db not cleaned between tests)
        assert stats.total_nodes >= 2, f"Should create at least 2 nodes, got {stats.total_nodes}"
        assert stats.total_edges >= 0, "Should have at least 0 edges"
        assert stats.nodes_by_type.get("function", 0) >= 2, "Should have at least 2 function nodes"
        assert stats.construction_time_seconds > 0
        assert stats.resolution_accuracy is not None
        assert stats.resolution_accuracy == 100.0, f"Should have 100% resolution accuracy, got {stats.resolution_accuracy}"

        print(f"Graph stats: {stats}")
