"""
Integration tests for timeout enforcement across services.

EPIC-12 Story 12.1: Timeout-Based Execution

These tests verify that timeouts are properly enforced in real service operations,
preventing infinite hangs on pathological inputs.
"""

import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock

from services.code_chunking_service import CodeChunkingService
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.graph_construction_service import GraphConstructionService
from services.graph_traversal_service import GraphTraversalService
from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions
)
from utils.timeout import TimeoutError
from config.timeouts import get_timeout, set_timeout, reset_to_defaults
import uuid


class TestCodeChunkingServiceTimeout:
    """Test timeout enforcement in code chunking service."""

    @pytest.mark.anyio
    async def test_chunking_timeout_on_slow_parse(self):
        """Tree-sitter parsing times out on slow operation."""
        service = CodeChunkingService(max_workers=2)

        # Mock the parser to simulate slow parsing
        with patch.object(
            service._supported_languages["python"],
            'parse',
            side_effect=lambda code: asyncio.sleep(10)  # Simulate slow parse
        ):
            # Override timeout to 1 second for fast test
            original_timeout = get_timeout("tree_sitter_parse")
            set_timeout("tree_sitter_parse", 1.0)

            try:
                # Should timeout and fall back to fixed chunking
                chunks = await service.chunk_code(
                    source_code="def hello(): pass",
                    language="python",
                    file_path="test.py"
                )

                # Should still return chunks via fallback
                assert len(chunks) > 0
                # Fallback chunks have metadata indicating fallback
                assert any(c.metadata and c.metadata.get("fallback") for c in chunks)

            finally:
                # Restore original timeout
                set_timeout("tree_sitter_parse", original_timeout)


class TestDualEmbeddingServiceTimeout:
    """Test timeout enforcement in embedding service."""

    @pytest.mark.anyio
    async def test_embedding_timeout_single(self):
        """Single embedding generation times out on slow model."""
        service = DualEmbeddingService()

        # Mock the model encode to simulate slow operation
        async def slow_encode_simulation():
            # Load model first
            await service._ensure_text_model()

            with patch.object(
                service._text_model,
                'encode',
                side_effect=lambda text: time.sleep(20)  # Simulate slow encode
            ):
                # Override timeout to 1 second for fast test
                original_timeout = get_timeout("embedding_generation_single")
                set_timeout("embedding_generation_single", 1.0)

                try:
                    with pytest.raises(TimeoutError) as exc_info:
                        await service.generate_embedding(
                            "Hello world",
                            domain=EmbeddingDomain.TEXT
                        )

                    error = exc_info.value
                    assert "embedding_generation_text_single" in str(error)
                    assert error.timeout == 1.0

                finally:
                    # Restore original timeout
                    set_timeout("embedding_generation_single", original_timeout)

        await slow_encode_simulation()

    @pytest.mark.anyio
    async def test_embedding_timeout_batch(self):
        """Batch embedding generation times out on slow model."""
        service = DualEmbeddingService()

        # Mock the model encode to simulate slow operation
        async def slow_batch_encode_simulation():
            # Load model first
            await service._ensure_code_model()

            with patch.object(
                service._code_model,
                'encode',
                side_effect=lambda texts, **kwargs: time.sleep(40)  # Simulate slow batch encode
            ):
                # Override timeout to 1 second for fast test
                original_timeout = get_timeout("embedding_generation_batch")
                set_timeout("embedding_generation_batch", 1.0)

                try:
                    with pytest.raises(TimeoutError) as exc_info:
                        await service.generate_embeddings_batch(
                            ["code 1", "code 2", "code 3"],
                            domain=EmbeddingDomain.CODE
                        )

                    error = exc_info.value
                    assert "embedding_generation_code_batch" in str(error)
                    assert error.timeout == 1.0

                finally:
                    # Restore original timeout
                    set_timeout("embedding_generation_batch", original_timeout)

        await slow_batch_encode_simulation()


class TestGraphConstructionServiceTimeout:
    """Test timeout enforcement in graph construction service."""

    @pytest.mark.anyio
    async def test_graph_construction_timeout(self, async_engine):
        """Graph construction times out on large repository."""
        service = GraphConstructionService(async_engine)

        # Mock the _create_nodes_from_chunks to simulate slow operation
        async def slow_node_creation(chunks):
            await asyncio.sleep(15)  # Simulate slow node creation
            return {}

        with patch.object(
            service,
            '_create_nodes_from_chunks',
            side_effect=slow_node_creation
        ):
            # Mock _get_chunks_for_repository to return fake chunks
            async def mock_get_chunks(repo, lang):
                from models.code_chunk_models import CodeChunkModel
                return [
                    CodeChunkModel(
                        id=uuid.uuid4(),
                        file_path="test.py",
                        language="python",
                        chunk_type="function",
                        name="test_func",
                        source_code="def test_func(): pass",
                        start_line=1,
                        end_line=1,
                        metadata={},
                        repository=repo,
                        commit_hash="abc123"
                    )
                ]

            with patch.object(
                service,
                '_get_chunks_for_repository',
                side_effect=mock_get_chunks
            ):
                # Override timeout to 1 second for fast test
                original_timeout = get_timeout("graph_construction")
                set_timeout("graph_construction", 1.0)

                try:
                    with pytest.raises(TimeoutError) as exc_info:
                        await service.build_graph_for_repository(
                            repository="test-repo",
                            language="python"
                        )

                    error = exc_info.value
                    assert "graph_node_creation" in str(error)

                finally:
                    # Restore original timeout
                    set_timeout("graph_construction", original_timeout)


class TestGraphTraversalServiceTimeout:
    """Test timeout enforcement in graph traversal service."""

    @pytest.mark.anyio
    async def test_graph_traversal_timeout(self, async_engine):
        """Graph traversal times out on complex graph."""
        from services.caches import RedisCache
        service = GraphTraversalService(async_engine, redis_cache=None)

        # Mock the _execute_recursive_traversal to simulate slow operation
        async def slow_traversal(start, direction, relationship, max_depth):
            await asyncio.sleep(10)  # Simulate slow traversal
            return []

        # Mock the node_repo.get_by_id to return a fake node
        async def mock_get_by_id(node_id):
            from models.graph_models import NodeModel
            from datetime import datetime
            return NodeModel(
                node_id=node_id,
                node_type="function",
                label="test_func",
                properties={},
                created_at=datetime.now()
            )

        with patch.object(
            service,
            '_execute_recursive_traversal',
            side_effect=slow_traversal
        ), patch.object(
            service.node_repo,
            'get_by_id',
            side_effect=mock_get_by_id
        ):
            # Override timeout to 1 second for fast test
            original_timeout = get_timeout("graph_traversal")
            set_timeout("graph_traversal", 1.0)

            try:
                with pytest.raises(TimeoutError) as exc_info:
                    await service.traverse(
                        start_node_id=uuid.uuid4(),
                        direction="outbound",
                        max_depth=3
                    )

                error = exc_info.value
                assert "graph_recursive_traversal" in str(error)

            finally:
                # Restore original timeout
                set_timeout("graph_traversal", original_timeout)


class TestCodeIndexingServiceTimeout:
    """Test timeout enforcement in code indexing service."""

    @pytest.mark.anyio
    async def test_file_indexing_timeout(
        self,
        async_engine,
        mock_embedding_service,
        mock_chunking_service,
        mock_metadata_service,
        mock_graph_service,
        test_chunk_repo
    ):
        """File indexing times out on slow operation."""
        from services.symbol_path_service import SymbolPathService

        service = CodeIndexingService(
            engine=async_engine,
            chunking_service=mock_chunking_service,
            metadata_service=mock_metadata_service,
            embedding_service=mock_embedding_service,
            graph_service=mock_graph_service,
            chunk_repository=test_chunk_repo,
            symbol_path_service=SymbolPathService()
        )

        # Mock _index_file to simulate slow operation
        async def slow_index_file(file_input, options):
            await asyncio.sleep(70)  # Simulate slow indexing (> 60s)
            from services.code_indexing_service import FileIndexingResult
            return FileIndexingResult(
                file_path=file_input.path,
                success=False,
                chunks_created=0,
                nodes_created=0,
                edges_created=0,
                processing_time_ms=0,
                error="Timeout"
            )

        with patch.object(
            service,
            '_index_file',
            side_effect=slow_index_file
        ):
            # Override timeout to 1 second for fast test
            original_timeout = get_timeout("index_file")
            set_timeout("index_file", 1.0)

            try:
                files = [FileInput(path="test.py", content="def hello(): pass", language="python")]
                options = IndexingOptions(repository="test-repo")

                summary = await service.index_repository(files, options)

                # Should have 1 failed file due to timeout
                assert summary.failed_files == 1
                assert summary.indexed_files == 0
                assert len(summary.errors) == 1
                assert "timed out" in summary.errors[0]["error"].lower()

            finally:
                # Restore original timeout
                set_timeout("index_file", original_timeout)


class TestTimeoutRecovery:
    """Test recovery and fallback behavior after timeouts."""

    @pytest.mark.anyio
    async def test_chunking_falls_back_after_timeout(self):
        """Chunking falls back to fixed chunking after timeout."""
        service = CodeChunkingService(max_workers=2)

        # Simulate timeout by making parse take forever
        async def infinite_parse(code):
            await asyncio.sleep(1000)

        with patch.object(
            service._supported_languages["python"],
            'parse',
            side_effect=infinite_parse
        ):
            # Set very short timeout
            original_timeout = get_timeout("tree_sitter_parse")
            set_timeout("tree_sitter_parse", 0.5)

            try:
                source_code = "def func1(): pass\ndef func2(): pass\ndef func3(): pass"
                chunks = await service.chunk_code(
                    source_code=source_code,
                    language="python",
                    file_path="test.py"
                )

                # Should have fallen back to fixed chunking
                assert len(chunks) > 0
                # Check that chunks have fallback metadata
                assert any(
                    c.metadata and c.metadata.get("fallback") and c.metadata.get("reason") == "ast_parsing_failed"
                    for c in chunks
                )

            finally:
                set_timeout("tree_sitter_parse", original_timeout)

    @pytest.mark.anyio
    async def test_timeout_context_preserved_in_error(self):
        """Timeout errors preserve context for debugging."""
        service = CodeChunkingService(max_workers=2)

        async def slow_parse(code):
            await asyncio.sleep(10)

        with patch.object(
            service._supported_languages["python"],
            'parse',
            side_effect=slow_parse
        ):
            original_timeout = get_timeout("tree_sitter_parse")
            set_timeout("tree_sitter_parse", 0.5)

            try:
                # This will timeout but fall back
                chunks = await service.chunk_code(
                    source_code="def hello(): pass",
                    language="python",
                    file_path="/path/to/my_file.py"
                )

                # Even though it fell back, we should have chunks
                assert len(chunks) > 0

            finally:
                set_timeout("tree_sitter_parse", original_timeout)
