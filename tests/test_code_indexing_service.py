"""
Unit tests for CodeIndexingService (Story 6).

Tests the orchestration service that coordinates all building blocks
from previous stories to provide end-to-end code indexing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.code_indexing_service import (
    CodeIndexingService,
    FileInput,
    IndexingOptions,
    IndexingSummary,
    FileIndexingResult,
)
from models.code_chunk_models import CodeChunk, ChunkType


class TestCodeIndexingService:
    """Unit tests for CodeIndexingService"""

    @pytest.fixture
    def mock_services(self):
        """Create mock services"""
        return {
            "chunking": AsyncMock(),
            "metadata": AsyncMock(),
            "embedding": AsyncMock(),
            "graph": AsyncMock(),
            "repository": AsyncMock(),
        }

    @pytest.fixture
    def mock_engine(self):
        """Create mock async engine"""
        return AsyncMock()

    @pytest.fixture
    def indexing_service(self, mock_services, mock_engine):
        """Create indexing service with mocked dependencies"""
        return CodeIndexingService(
            engine=mock_engine,
            chunking_service=mock_services["chunking"],
            metadata_service=mock_services["metadata"],
            embedding_service=mock_services["embedding"],
            graph_service=mock_services["graph"],
            chunk_repository=mock_services["repository"],
        )

    # ========================================================================
    # Language Detection Tests
    # ========================================================================

    def test_language_detection_python(self, indexing_service):
        """Test language detection for Python file"""
        language = indexing_service._detect_language("main.py")
        assert language == "python"

    def test_language_detection_javascript(self, indexing_service):
        """Test language detection for JavaScript file"""
        language = indexing_service._detect_language("app.js")
        assert language == "javascript"

    def test_language_detection_typescript(self, indexing_service):
        """Test language detection for TypeScript file"""
        language = indexing_service._detect_language("component.ts")
        assert language == "typescript"

    def test_language_detection_go(self, indexing_service):
        """Test language detection for Go file"""
        language = indexing_service._detect_language("main.go")
        assert language == "go"

    def test_language_detection_rust(self, indexing_service):
        """Test language detection for Rust file"""
        language = indexing_service._detect_language("lib.rs")
        assert language == "rust"

    def test_language_detection_unknown(self, indexing_service):
        """Test language detection for unknown extension"""
        language = indexing_service._detect_language("file.xyz")
        assert language is None

    def test_language_detection_case_insensitive(self, indexing_service):
        """Test language detection is case-insensitive"""
        assert indexing_service._detect_language("main.PY") == "python"
        assert indexing_service._detect_language("APP.JS") == "javascript"

    # ========================================================================
    # Single File Indexing Tests
    # ========================================================================

    @pytest.mark.anyio
    async def test_index_file_success(
        self,
        indexing_service,
        mock_services,
    ):
        """Test successful file indexing"""
        # Setup mocks
        mock_chunk = MagicMock()
        mock_chunk.file_path = "test.py"
        mock_chunk.source_code = "def hello(): pass"
        mock_chunk.metadata = {"docstring": "Hello function"}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "hello"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }
        mock_services["repository"].add.return_value = AsyncMock()

        # Index file
        file_input = FileInput(
            path="test.py",
            content="def hello(): pass",
            language="python",
        )

        options = IndexingOptions(
            extract_metadata=True,
            generate_embeddings=True,
            build_graph=False,
            repository="test-repo",
        )

        result = await indexing_service._index_file(file_input, options)

        # Assertions
        assert result.success is True
        assert result.chunks_created == 1
        assert result.file_path == "test.py"
        assert result.error is None
        assert result.processing_time_ms >= 0

        # Verify service calls
        mock_services["chunking"].chunk_code.assert_called_once()
        mock_services["embedding"].generate_embedding.assert_called_once()
        mock_services["repository"].add.assert_called_once()

    @pytest.mark.anyio
    async def test_index_file_language_auto_detection(
        self,
        indexing_service,
        mock_services,
    ):
        """Test file indexing with automatic language detection"""
        mock_chunk = MagicMock()
        mock_chunk.file_path = "test.py"
        mock_chunk.source_code = "def hello(): pass"
        mock_chunk.metadata = {}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "hello"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }

        # Don't provide language - should auto-detect
        file_input = FileInput(
            path="test.py",
            content="def hello(): pass",
            language=None,  # Auto-detect
        )

        options = IndexingOptions(repository="test-repo")

        result = await indexing_service._index_file(file_input, options)

        # Should detect Python from .py extension
        assert result.success is True
        mock_services["chunking"].chunk_code.assert_called_once()
        call_args = mock_services["chunking"].chunk_code.call_args
        assert call_args[1]["language"] == "python"

    @pytest.mark.anyio
    async def test_index_file_no_language_detected(
        self,
        indexing_service,
        mock_services,
    ):
        """Test file indexing fails when language can't be detected"""
        file_input = FileInput(
            path="unknown.xyz",  # Unknown extension
            content="some content",
            language=None,
        )

        options = IndexingOptions(repository="test-repo")

        result = await indexing_service._index_file(file_input, options)

        # Should fail
        assert result.success is False
        assert "Unable to detect language" in result.error
        assert result.chunks_created == 0

    @pytest.mark.anyio
    async def test_index_file_parsing_error(
        self,
        indexing_service,
        mock_services,
    ):
        """Test file indexing with parsing error (no chunks)"""
        # Setup mock to return no chunks
        mock_services["chunking"].chunk_code.return_value = []

        file_input = FileInput(
            path="invalid.py",
            content="invalid python code {{{",
            language="python",
        )

        options = IndexingOptions(repository="test-repo")

        result = await indexing_service._index_file(file_input, options)

        # Assertions
        assert result.success is False
        assert result.chunks_created == 0
        assert "No chunks extracted" in result.error

    @pytest.mark.anyio
    async def test_index_file_embeddings_disabled(
        self,
        indexing_service,
        mock_services,
    ):
        """Test file indexing with embeddings disabled"""
        mock_chunk = MagicMock()
        mock_chunk.file_path = "test.py"
        mock_chunk.source_code = "def hello(): pass"
        mock_chunk.metadata = {}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "hello"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]

        file_input = FileInput(
            path="test.py",
            content="def hello(): pass",
            language="python",
        )

        options = IndexingOptions(
            generate_embeddings=False,  # Disabled
            repository="test-repo",
        )

        result = await indexing_service._index_file(file_input, options)

        # Should succeed without generating embeddings
        assert result.success is True
        mock_services["embedding"].generate_embedding.assert_not_called()

    @pytest.mark.anyio
    async def test_index_file_multiple_chunks(
        self,
        indexing_service,
        mock_services,
    ):
        """Test indexing file with multiple chunks"""
        # Create 3 mock chunks
        chunks = []
        for i in range(3):
            chunk = MagicMock()
            chunk.file_path = "test.py"
            chunk.source_code = f"def func{i}(): pass"
            chunk.metadata = {}
            chunk.chunk_type = ChunkType.FUNCTION
            chunk.name = f"func{i}"
            chunk.start_line = i * 2
            chunk.end_line = i * 2 + 1
            chunk.embedding_text = None
            chunk.embedding_code = None
            chunks.append(chunk)

        mock_services["chunking"].chunk_code.return_value = chunks
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }

        file_input = FileInput(
            path="test.py",
            content="def func0(): pass\ndef func1(): pass\ndef func2(): pass",
            language="python",
        )

        options = IndexingOptions(repository="test-repo")

        result = await indexing_service._index_file(file_input, options)

        # Should create 3 chunks
        assert result.success is True
        assert result.chunks_created == 3
        assert mock_services["repository"].add.call_count == 3

    # ========================================================================
    # Repository Indexing Tests
    # ========================================================================

    @pytest.mark.anyio
    async def test_index_repository_single_file(
        self,
        indexing_service,
        mock_services,
    ):
        """Test indexing repository with single file"""
        mock_chunk = MagicMock()
        mock_chunk.file_path = "test.py"
        mock_chunk.source_code = "def hello(): pass"
        mock_chunk.metadata = {}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "hello"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }
        mock_services["graph"].build_repository_graph.return_value = {
            "total_nodes": 1,
            "total_edges": 0,
        }

        files = [
            FileInput(path="test.py", content="def hello(): pass", language="python"),
        ]

        options = IndexingOptions(
            repository="test-repo",
            build_graph=True,
        )

        summary = await indexing_service.index_repository(files, options)

        # Assertions
        assert summary.indexed_files == 1
        assert summary.indexed_chunks == 1
        assert summary.indexed_nodes == 1
        assert summary.indexed_edges == 0
        assert summary.failed_files == 0
        assert len(summary.errors) == 0

    @pytest.mark.anyio
    async def test_index_repository_multiple_files(
        self,
        indexing_service,
        mock_services,
    ):
        """Test indexing repository with multiple files"""
        mock_chunk = MagicMock()
        mock_chunk.file_path = "test.py"
        mock_chunk.source_code = "def test(): pass"
        mock_chunk.metadata = {}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "test"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }
        mock_services["graph"].build_repository_graph.return_value = {
            "total_nodes": 10,
            "total_edges": 15,
        }

        # Index 3 files
        files = [
            FileInput(path="file1.py", content="code1", language="python"),
            FileInput(path="file2.py", content="code2", language="python"),
            FileInput(path="file3.py", content="code3", language="python"),
        ]

        options = IndexingOptions(
            repository="test-repo",
            build_graph=True,
        )

        summary = await indexing_service.index_repository(files, options)

        # Assertions
        assert summary.indexed_files == 3
        assert summary.indexed_chunks == 3
        assert summary.indexed_nodes == 10
        assert summary.indexed_edges == 15
        assert summary.failed_files == 0

    @pytest.mark.anyio
    async def test_index_repository_partial_failure(
        self,
        indexing_service,
        mock_services,
    ):
        """Test repository indexing with partial failures"""
        # First file succeeds
        mock_chunk = MagicMock()
        mock_chunk.file_path = "file1.py"
        mock_chunk.source_code = "def test(): pass"
        mock_chunk.metadata = {}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "test"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        # Second file fails (no chunks)
        async def chunk_code_side_effect(source_code, language, file_path, **kwargs):
            if "file1" in file_path:
                return [mock_chunk]
            else:
                return []  # Parsing failure

        mock_services["chunking"].chunk_code.side_effect = chunk_code_side_effect
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }
        mock_services["graph"].build_repository_graph.return_value = {
            "total_nodes": 1,
            "total_edges": 0,
        }

        files = [
            FileInput(path="file1.py", content="code1", language="python"),
            FileInput(path="file2.py", content="invalid", language="python"),
        ]

        options = IndexingOptions(repository="test-repo", build_graph=True)

        summary = await indexing_service.index_repository(files, options)

        # Assertions - partial success
        assert summary.indexed_files == 1
        assert summary.indexed_chunks == 1
        assert summary.failed_files == 1
        assert len(summary.errors) == 1
        assert "file2.py" in summary.errors[0]["file"]

    @pytest.mark.anyio
    async def test_index_repository_graph_disabled(
        self,
        indexing_service,
        mock_services,
    ):
        """Test repository indexing with graph construction disabled"""
        mock_chunk = MagicMock()
        mock_chunk.file_path = "test.py"
        mock_chunk.source_code = "def test(): pass"
        mock_chunk.metadata = {}
        mock_chunk.chunk_type = ChunkType.FUNCTION
        mock_chunk.name = "test"
        mock_chunk.start_line = 1
        mock_chunk.end_line = 1
        mock_chunk.embedding_text = None
        mock_chunk.embedding_code = None

        mock_services["chunking"].chunk_code.return_value = [mock_chunk]
        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }

        files = [
            FileInput(path="test.py", content="code", language="python"),
        ]

        options = IndexingOptions(
            repository="test-repo",
            build_graph=False,  # Disabled
        )

        summary = await indexing_service.index_repository(files, options)

        # Graph service should not be called
        assert summary.indexed_nodes == 0
        assert summary.indexed_edges == 0
        mock_services["graph"].build_repository_graph.assert_not_called()

    # ========================================================================
    # Embedding Generation Tests
    # ========================================================================

    @pytest.mark.anyio
    async def test_generate_embeddings_with_docstring(
        self,
        indexing_service,
        mock_services,
    ):
        """Test embedding generation uses docstring for TEXT embedding"""
        chunk = CodeChunk(
            file_path="test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name="test",
            source_code="def test():\n    '''Test function'''\n    pass",
            start_line=1,
            end_line=3,
            metadata={"docstring": "Test function"},
        )

        mock_services["embedding"].generate_embedding.return_value = {
            "text": [0.1] * 768,
            "code": [0.2] * 768,
        }

        result = await indexing_service._generate_embeddings_for_chunk(chunk)

        # Should return both embeddings
        assert result["text"] == [0.1] * 768
        assert result["code"] == [0.2] * 768

        # Should call embedding service with HYBRID domain
        mock_services["embedding"].generate_embedding.assert_called_once_with(
            text=chunk.source_code, domain="HYBRID"
        )

    @pytest.mark.anyio
    async def test_generate_embeddings_error_handling(
        self,
        indexing_service,
        mock_services,
    ):
        """Test embedding generation handles errors gracefully"""
        chunk = CodeChunk(
            file_path="test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name="test",
            source_code="def test(): pass",
            start_line=1,
            end_line=1,
            metadata={},
        )

        # Simulate embedding service failure
        mock_services["embedding"].generate_embedding.side_effect = Exception(
            "Embedding failed"
        )

        result = await indexing_service._generate_embeddings_for_chunk(chunk)

        # Should return None for both embeddings
        assert result["text"] is None
        assert result["code"] is None
