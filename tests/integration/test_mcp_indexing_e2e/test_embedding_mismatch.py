"""
Tests for embedding service interface mismatch handling.

Verifies:
1. Legacy bridge handles SentenceTransformerEmbeddingService interface mismatch
2. DualEmbeddingService works directly with CodeIndexingService
"""

import uuid

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from api.services.code_indexing_service import CodeIndexingService
from api.services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from models.code_chunk_models import CodeChunk, ChunkType


@pytest_asyncio.fixture
async def code_indexing_service_with_dual(engine, test_repository):
    """Create CodeIndexingService with DualEmbeddingService."""
    from api.services.code_chunking_service import CodeChunkingService
    from api.services.metadata_extractor_service import (
        MetadataExtractorService,
    )
    from api.services.graph_construction_service import (
        GraphConstructionService,
    )
    from db.repositories.code_chunk_repository import CodeChunkRepository

    embedding_service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )

    service = CodeIndexingService(
        engine=engine,
        chunking_service=CodeChunkingService(),
        metadata_service=MetadataExtractorService(),
        embedding_service=embedding_service,
        graph_service=GraphConstructionService(engine=engine),
        chunk_repository=CodeChunkRepository(engine=engine),
        chunk_cache=None,
    )

    yield service


@pytest.mark.asyncio
async def test_legacy_embedding_service_bridge():
    """
    Test: When SentenceTransformerEmbeddingService is used (wrong interface),
    the legacy bridge handles it gracefully.

    The legacy bridge catches TypeError when 'domain' parameter is not
    supported and falls back to using 'text_type' parameter instead.
    """
    mock_legacy_result = [0.1, 0.2, 0.3] + [0.0] * 765

    async def mock_generate_embedding(text, **kwargs):
        if "domain" in kwargs:
            raise TypeError(
                "generate_embedding() got an unexpected keyword argument 'domain'"
            )
        return mock_legacy_result

    mock_embedding = AsyncMock()
    mock_embedding.generate_embedding = AsyncMock(side_effect=mock_generate_embedding)

    chunk = CodeChunk(
        id=uuid.uuid4(),
        source_code="def test_func():\n    pass",
        file_path="/test.py",
        language="python",
        chunk_type=ChunkType.FUNCTION,
        start_line=1,
        end_line=2,
        repository="test-repo"
    )

    code_indexing_service = MagicMock()
    code_indexing_service.embedding_service = mock_embedding
    code_indexing_service.logger = MagicMock()

    result = await CodeIndexingService._generate_embedding_legacy_bridge(
        code_indexing_service,
        chunk,
        EmbeddingDomain.CODE
    )

    assert result is not None
    assert "code" in result or "text" in result
    code_or_text = result.get("code") or result.get("text")
    assert code_or_text is not None, f"Expected embedding in result, got {result}"


@pytest.mark.asyncio
async def test_dual_embedding_service_works(engine, test_repository):
    """
    Test: DualEmbeddingService works directly with CodeIndexingService.

    Verify DualEmbeddingService returns correct format:
    - Dict[str, List[float]] with 'text' and/or 'code' keys
    - Not List[float] (old interface)
    """
    from api.services.code_chunking_service import CodeChunkingService
    from api.services.metadata_extractor_service import (
        MetadataExtractorService,
    )
    from api.services.graph_construction_service import (
        GraphConstructionService,
    )
    from db.repositories.code_chunk_repository import CodeChunkRepository

    embedding_service = DualEmbeddingService(
        device="cpu",
        dimension=768
    )

    service = CodeIndexingService(
        engine=engine,
        chunking_service=CodeChunkingService(),
        metadata_service=MetadataExtractorService(),
        embedding_service=embedding_service,
        graph_service=GraphConstructionService(engine=engine),
        chunk_repository=CodeChunkRepository(engine=engine),
        chunk_cache=None,
    )

    test_code = "def hello():\n    return 'world'"

    result = await service._generate_embeddings_for_chunk(
        chunk=CodeChunk(
            id=uuid.uuid4(),
            source_code=test_code,
            file_path="/test.py",
            language="python",
            chunk_type=ChunkType.FUNCTION,
            start_line=1,
            end_line=2,
            repository=test_repository,
            metadata={"docstring": None}
        )
    )

    assert result is not None
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "code" in result or "text" in result

    if "code" in result and result["code"] is not None:
        embedding = result["code"]
        assert isinstance(embedding, list), f"Expected list, got {type(embedding)}"
        assert len(embedding) == 768, f"Expected 768D, got {len(embedding)}"
    elif "text" in result and result["text"] is not None:
        embedding = result["text"]
        assert isinstance(embedding, list), f"Expected list, got {type(embedding)}"
        assert len(embedding) == 768, f"Expected 768D, got {len(embedding)}"