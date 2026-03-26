"""
TDD Tests for Expanse .md indexing pipeline.

Tests:
1. Markdown chunking splits by ## headers
2. Scanner picks up .md files (not dot-prefixed dirs)
3. Language detection returns "markdown" for .md
4. Full pipeline: scan → chunk → embed → store (integration)
5. Defensive fallback when embedding service has mismatched interface
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.code_chunking_service import CodeChunkingService
from services.code_indexing_service import CodeIndexingService, FileInput
from services.dual_embedding_service import EmbeddingDomain
from mnemo_mcp.utils.project_scanner import ProjectScanner
from models.code_chunk_models import ChunkType, CodeChunk


# ============================================================================
# Unit Tests (no DB required)
# ============================================================================

class TestMarkdownChunking:
    """Test markdown files are chunked by ## headers."""

    @pytest.fixture
    def chunker(self):
        return CodeChunkingService(max_workers=2)

    @pytest.mark.asyncio
    async def test_splits_by_headers(self, chunker):
        """Markdown with ## headers → one chunk per section."""
        source = "## Alpha\n\nContent A.\n\n## Beta\n\nContent B.\n"
        chunks = await chunker.chunk_code(source, "markdown", "test.md")
        assert len(chunks) == 2
        assert chunks[0].name == "Alpha"
        assert chunks[1].name == "Beta"

    @pytest.mark.asyncio
    async def test_chunk_type_is_markdown(self, chunker):
        """All chunks have MARKDOWN_SECTION type."""
        source = "## Test\n\nContent.\n"
        chunks = await chunker.chunk_code(source, "markdown", "test.md")
        assert chunks[0].chunk_type == ChunkType.MARKDOWN_SECTION

    @pytest.mark.asyncio
    async def test_no_headers_single_chunk(self, chunker):
        """No ## headers → single chunk."""
        source = "Just plain text.\n"
        chunks = await chunker.chunk_code(source, "markdown", "test.md")
        assert len(chunks) == 1


class TestLanguageDetection:
    """Test .md files are detected as markdown."""

    @pytest.fixture
    def service(self):
        mock_engine = AsyncMock()
        return CodeIndexingService(
            engine=mock_engine,
            chunking_service=AsyncMock(),
            metadata_service=AsyncMock(),
            embedding_service=AsyncMock(),
            graph_service=AsyncMock(),
            chunk_repository=AsyncMock(),
        )

    def test_markdown_detected(self, service):
        assert service._detect_language("KERNEL.md") == "markdown"

    def test_python_detected(self, service):
        assert service._detect_language("main.py") == "python"


class TestScannerDotPrefix:
    """Test scanner skips dot-prefixed directories."""

    @pytest.mark.asyncio
    async def test_skips_dot_dirs(self, tmp_path):
        """Files in .hidden/ directories are skipped."""
        (tmp_path / "visible.md").write_text("# Visible")
        dot_dir = tmp_path / ".hidden"
        dot_dir.mkdir()
        (dot_dir / "secret.md").write_text("# Secret")

        scanner = ProjectScanner()
        files = await scanner.scan(str(tmp_path), respect_gitignore=False)

        paths = [f.path for f in files]
        assert any("visible.md" in p for p in paths)
        assert not any(".hidden" in p for p in paths)


class TestEmbeddingServiceMismatch:
    """Test defensive fallback when embedding service has mismatched interface."""

    @pytest.fixture
    def legacy_embedding_service(self):
        """Mock embedding service with SentenceTransformerEmbeddingService interface.

        SentenceTransformerEmbeddingService uses:
            generate_embedding(text, text_type=TextType) → List[float]
        But CodeIndexingService expects:
            generate_embedding(text, domain=EmbeddingDomain) → Dict[str, List[float]]

        The mock raises TypeError on 'domain=' (primary call) but succeeds
        on 'text_type=' (legacy bridge call) returning List[float].
        """
        service = AsyncMock()

        async def mock_generate_embedding(text, **kwargs):
            if "domain" in kwargs:
                raise TypeError(
                    "generate_embedding() got an unexpected keyword argument 'domain'"
                )
            # Legacy call with text_type= succeeds
            assert "text_type" in kwargs
            return [0.1] * 768  # Return mock embedding vector

        service.generate_embedding = mock_generate_embedding
        service.generate_embeddings_batch = AsyncMock(
            side_effect=TypeError(
                "generate_embeddings_batch() got an unexpected keyword argument 'domain'"
            )
        )
        return service

    @pytest.mark.asyncio
    async def test_mismatched_domain_param_uses_legacy_bridge(self, legacy_embedding_service):
        """TypeError on 'domain' param triggers legacy bridge fallback returning CODE embedding."""
        mock_engine = AsyncMock()
        indexing_service = CodeIndexingService(
            engine=mock_engine,
            chunking_service=AsyncMock(),
            metadata_service=AsyncMock(),
            embedding_service=legacy_embedding_service,
            graph_service=AsyncMock(),
            chunk_repository=AsyncMock(),
        )

        chunk = CodeChunk(
            file_path="test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            name="test_func",
            source_code="def test(): pass",
            start_line=1,
            end_line=2,
            metadata={}  # No docstring → CODE embedding
        )

        result = await indexing_service._generate_embeddings_for_chunk(chunk)

        # Should return dict with CODE embedding (legacy bridge succeeded)
        assert isinstance(result, dict)
        assert "code" in result
        assert result["code"] is not None
        assert len(result["code"]) == 768
        assert result["text"] is None
