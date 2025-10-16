"""
Unit tests for DualEmbeddingService (Phase 0 Story 0.2).

Tests:
- Lazy loading (models load on-demand)
- Domain-specific generation (TEXT | CODE | HYBRID)
- Backward compatibility (generate_embedding_legacy)
- RAM monitoring
- Error handling
- Similarity computation
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np

from services.dual_embedding_service import (
    DualEmbeddingService,
    EmbeddingDomain,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer model."""
    mock_model = Mock()
    # encode() returns numpy array with 768 dimensions
    mock_model.encode = Mock(return_value=np.random.rand(768))
    return mock_model


@pytest.fixture
def dual_service():
    """Create DualEmbeddingService instance for testing."""
    return DualEmbeddingService(
        text_model_name="mock-text-model",
        code_model_name="mock-code-model",
        dimension=768,
        device="cpu",
    )


# ============================================================================
# Test: Initialization
# ============================================================================

def test_initialization():
    """Test DualEmbeddingService initialization."""
    service = DualEmbeddingService(
        text_model_name="test-text",
        code_model_name="test-code",
        dimension=768,
        device="cpu",
    )

    assert service.text_model_name == "test-text"
    assert service.code_model_name == "test-code"
    assert service.dimension == 768
    assert service.device == "cpu"
    assert service._text_model is None  # Lazy loading
    assert service._code_model is None  # Lazy loading
    assert service._text_load_attempted is False
    assert service._code_load_attempted is False


def test_initialization_with_env_defaults():
    """Test initialization with environment variable defaults."""
    with patch.dict("os.environ", {
        "EMBEDDING_MODEL": "env-text-model",
        "CODE_EMBEDDING_MODEL": "env-code-model",
    }):
        service = DualEmbeddingService(dimension=768, device="cpu")
        assert service.text_model_name == "env-text-model"
        assert service.code_model_name == "env-code-model"


# ============================================================================
# Test: Lazy Loading
# ============================================================================

@pytest.mark.anyio
async def test_lazy_loading_text_model(dual_service, mock_sentence_transformer):
    """Test TEXT model lazy loading on first use."""
    assert dual_service._text_model is None

    with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
        result = await dual_service.generate_embedding(
            "test text",
            domain=EmbeddingDomain.TEXT
        )

    # Model should be loaded now
    assert dual_service._text_model is not None
    assert dual_service._text_load_attempted is True
    assert "text" in result
    assert len(result["text"]) == 768


@pytest.mark.anyio
async def test_lazy_loading_code_model(dual_service, mock_sentence_transformer):
    """Test CODE model lazy loading on first use."""
    assert dual_service._code_model is None

    # Mock RAM check to allow loading
    with patch.object(dual_service, 'get_ram_usage_mb', return_value={'process_rss_mb': 500}):
        with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
            result = await dual_service.generate_embedding(
                "def test(): pass",
                domain=EmbeddingDomain.CODE
            )

    # Model should be loaded now
    assert dual_service._code_model is not None
    assert dual_service._code_load_attempted is True
    assert "code" in result
    assert len(result["code"]) == 768


@pytest.mark.anyio
async def test_lazy_loading_reuses_model(dual_service, mock_sentence_transformer):
    """Test that lazy loading reuses already-loaded model."""
    with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer) as mock_st:
        # First call loads model
        await dual_service.generate_embedding("text1", domain=EmbeddingDomain.TEXT)
        assert mock_st.call_count == 1

        # Second call reuses model
        await dual_service.generate_embedding("text2", domain=EmbeddingDomain.TEXT)
        assert mock_st.call_count == 1  # No additional loading


# ============================================================================
# Test: Domain-specific Generation
# ============================================================================

@pytest.mark.anyio
async def test_generate_embedding_text_domain(dual_service, mock_sentence_transformer):
    """Test TEXT domain embedding generation."""
    with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
        result = await dual_service.generate_embedding(
            "Hello world",
            domain=EmbeddingDomain.TEXT
        )

    assert "text" in result
    assert "code" not in result
    assert len(result["text"]) == 768
    assert all(isinstance(x, float) for x in result["text"])


@pytest.mark.anyio
async def test_generate_embedding_code_domain(dual_service, mock_sentence_transformer):
    """Test CODE domain embedding generation."""
    # Mock RAM check
    with patch.object(dual_service, 'get_ram_usage_mb', return_value={'process_rss_mb': 500}):
        with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
            result = await dual_service.generate_embedding(
                "def foo(): pass",
                domain=EmbeddingDomain.CODE
            )

    assert "code" in result
    assert "text" not in result
    assert len(result["code"]) == 768


@pytest.mark.anyio
async def test_generate_embedding_hybrid_domain(dual_service, mock_sentence_transformer):
    """Test HYBRID domain generates both embeddings."""
    # Mock RAM check
    with patch.object(dual_service, 'get_ram_usage_mb', return_value={'process_rss_mb': 500}):
        with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
            result = await dual_service.generate_embedding(
                "def foo():\n    '''Docstring'''",
                domain=EmbeddingDomain.HYBRID
            )

    assert "text" in result
    assert "code" in result
    assert len(result["text"]) == 768
    assert len(result["code"]) == 768


@pytest.mark.anyio
async def test_generate_embedding_empty_text(dual_service):
    """Test empty text returns zero vector."""
    result = await dual_service.generate_embedding("", domain=EmbeddingDomain.TEXT)

    assert "text" in result
    assert len(result["text"]) == 768
    assert all(x == 0.0 for x in result["text"])


@pytest.mark.anyio
async def test_generate_embedding_whitespace_only(dual_service):
    """Test whitespace-only text returns zero vector."""
    result = await dual_service.generate_embedding("   \n\t  ", domain=EmbeddingDomain.TEXT)

    assert "text" in result
    assert len(result["text"]) == 768
    assert all(x == 0.0 for x in result["text"])


@pytest.mark.anyio
async def test_generate_embedding_empty_hybrid_returns_both_keys(dual_service):
    """Test empty text with HYBRID domain returns both 'text' and 'code' keys."""
    result = await dual_service.generate_embedding("", domain=EmbeddingDomain.HYBRID)

    # Must have both keys
    assert "text" in result
    assert "code" in result
    # Both should be zero vectors
    assert len(result["text"]) == 768
    assert len(result["code"]) == 768
    assert all(x == 0.0 for x in result["text"])
    assert all(x == 0.0 for x in result["code"])


# ============================================================================
# Test: Backward Compatibility
# ============================================================================

@pytest.mark.anyio
async def test_generate_embedding_legacy(dual_service, mock_sentence_transformer):
    """Test backward compatible generate_embedding_legacy() method."""
    with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
        result = await dual_service.generate_embedding_legacy("Test text")

    # Should return list directly (not dict)
    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(x, float) for x in result)


@pytest.mark.anyio
async def test_legacy_method_uses_text_domain(dual_service, mock_sentence_transformer):
    """Test legacy method uses TEXT domain internally."""
    with patch.object(dual_service, 'generate_embedding') as mock_gen:
        mock_gen.return_value = {"text": [0.1] * 768}

        await dual_service.generate_embedding_legacy("Test")

        # Verify TEXT domain was used
        mock_gen.assert_called_once()
        call_args = mock_gen.call_args
        assert call_args[0][0] == "Test"
        assert call_args[1]["domain"] == EmbeddingDomain.TEXT


# ============================================================================
# Test: RAM Monitoring
# ============================================================================

def test_get_ram_usage_mb(dual_service):
    """Test RAM usage monitoring."""
    ram = dual_service.get_ram_usage_mb()

    assert "process_rss_mb" in ram
    assert "process_vms_mb" in ram
    assert "text_model_loaded" in ram
    assert "code_model_loaded" in ram
    assert "estimated_models_mb" in ram

    assert isinstance(ram["process_rss_mb"], float)
    assert ram["process_rss_mb"] > 0
    assert ram["text_model_loaded"] is False  # Not loaded yet
    assert ram["code_model_loaded"] is False
    assert ram["estimated_models_mb"] == 0  # No models loaded


@pytest.mark.anyio
async def test_ram_usage_after_text_load(dual_service, mock_sentence_transformer):
    """Test RAM usage after TEXT model loading."""
    with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
        await dual_service.generate_embedding("test", domain=EmbeddingDomain.TEXT)

    ram = dual_service.get_ram_usage_mb()
    assert ram["text_model_loaded"] is True
    assert ram["estimated_models_mb"] == 260  # TEXT model estimate


@pytest.mark.anyio
async def test_ram_budget_safeguard_blocks_code_model(dual_service, mock_sentence_transformer):
    """Test RAM budget safeguard prevents CODE model loading when budget exceeded."""
    # Mock high RAM usage
    with patch.object(dual_service, 'get_ram_usage_mb', return_value={'process_rss_mb': 950}):
        with pytest.raises(RuntimeError, match="RAM budget exceeded"):
            await dual_service.generate_embedding(
                "def test(): pass",
                domain=EmbeddingDomain.CODE
            )

    # CODE model should not be loaded
    assert dual_service._code_model is None


# ============================================================================
# Test: Similarity Computation
# ============================================================================

@pytest.mark.anyio
async def test_compute_similarity_identical_vectors():
    """Test similarity of identical vectors is 1.0."""
    service = DualEmbeddingService(dimension=768, device="cpu")
    emb = [1.0] * 768

    similarity = await service.compute_similarity(emb, emb)
    assert pytest.approx(similarity, abs=0.01) == 1.0


@pytest.mark.anyio
async def test_compute_similarity_orthogonal_vectors():
    """Test similarity of orthogonal vectors is 0.0."""
    service = DualEmbeddingService(dimension=768, device="cpu")
    emb1 = [1.0] + [0.0] * 767
    emb2 = [0.0, 1.0] + [0.0] * 766

    similarity = await service.compute_similarity(emb1, emb2)
    assert pytest.approx(similarity, abs=0.01) == 0.0


@pytest.mark.anyio
async def test_compute_similarity_opposite_vectors():
    """Test similarity of opposite vectors is 0.0 (clipped from -1.0)."""
    service = DualEmbeddingService(dimension=768, device="cpu")
    emb1 = [1.0] * 768
    emb2 = [-1.0] * 768

    similarity = await service.compute_similarity(emb1, emb2)
    # Cosine similarity is -1.0, but clipped to 0.0
    assert pytest.approx(similarity, abs=0.01) == 0.0


@pytest.mark.anyio
async def test_compute_similarity_zero_vectors():
    """Test similarity with zero vectors returns 0.0."""
    service = DualEmbeddingService(dimension=768, device="cpu")
    emb_zero = [0.0] * 768
    emb_normal = [1.0] * 768

    similarity = await service.compute_similarity(emb_zero, emb_normal)
    assert similarity == 0.0


# ============================================================================
# Test: Error Handling
# ============================================================================

@pytest.mark.anyio
async def test_dimension_mismatch_detection(mock_sentence_transformer):
    """Test dimension mismatch is detected during model loading."""
    # Mock model returns wrong dimension
    mock_sentence_transformer.encode = Mock(return_value=np.random.rand(512))  # Wrong: 512 instead of 768

    service = DualEmbeddingService(
        text_model_name="test",
        dimension=768,
        device="cpu"
    )

    with patch("services.dual_embedding_service.SentenceTransformer", return_value=mock_sentence_transformer):
        with pytest.raises(RuntimeError, match="dimension mismatch"):
            await service.generate_embedding("test", domain=EmbeddingDomain.TEXT)


@pytest.mark.anyio
async def test_model_loading_failure_text(dual_service):
    """Test TEXT model loading failure is handled."""
    with patch("services.dual_embedding_service.SentenceTransformer", side_effect=Exception("Model not found")):
        with pytest.raises(RuntimeError, match="Failed to load TEXT model"):
            await dual_service.generate_embedding("test", domain=EmbeddingDomain.TEXT)

    # Second attempt should fail immediately (load_attempted = True)
    with pytest.raises(RuntimeError, match="Text model loading failed previously"):
        await dual_service.generate_embedding("test", domain=EmbeddingDomain.TEXT)


@pytest.mark.anyio
async def test_model_loading_failure_code(dual_service):
    """Test CODE model loading failure is handled."""
    # Mock RAM check to allow loading
    with patch.object(dual_service, 'get_ram_usage_mb', return_value={'process_rss_mb': 500}):
        with patch("services.dual_embedding_service.SentenceTransformer", side_effect=Exception("Model not found")):
            with pytest.raises(RuntimeError, match="Failed to load CODE model"):
                await dual_service.generate_embedding("def test(): pass", domain=EmbeddingDomain.CODE)

    # Second attempt should fail immediately
    with pytest.raises(RuntimeError, match="Code model loading failed previously"):
        await dual_service.generate_embedding("def test(): pass", domain=EmbeddingDomain.CODE)


# ============================================================================
# Test: Stats
# ============================================================================

def test_get_stats(dual_service):
    """Test get_stats() returns complete information."""
    stats = dual_service.get_stats()

    assert "text_model_name" in stats
    assert "code_model_name" in stats
    assert "dimension" in stats
    assert "device" in stats
    assert "text_model_loaded" in stats
    assert "code_model_loaded" in stats
    assert "process_rss_mb" in stats

    assert stats["dimension"] == 768
    assert stats["device"] == "cpu"
    assert stats["text_model_loaded"] is False
    assert stats["code_model_loaded"] is False
