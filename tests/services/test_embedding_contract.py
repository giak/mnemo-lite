"""
Tests de contrat de type pour le pipeline d'embedding.

Verifie que generate_embedding() retourne list, pas ndarray.
Verifie que format_vector_for_sql rejette ndarray.
"""

import importlib.util
import numpy as np
import pytest
from api.utils.sql_vector import format_vector_for_sql, format_halfvec_for_sql
from api.services.embedding_service import MockEmbeddingService


class TestFormatVectorForSqlContract:
    """format_vector_for_sql attend list/tuple, pas ndarray."""

    def test_accepts_list(self):
        result = format_vector_for_sql([0.1, 0.2, 0.3])
        assert isinstance(result, str)

    def test_accepts_tuple(self):
        result = format_vector_for_sql((0.1, 0.2, 0.3))
        assert isinstance(result, str)

    def test_rejects_ndarray(self):
        with pytest.raises(ValueError, match="Expected list/tuple"):
            format_vector_for_sql(np.array([0.1, 0.2, 0.3]))

    def test_rejects_ndarray_halfvec(self):
        with pytest.raises(ValueError, match="Expected list/tuple"):
            format_halfvec_for_sql(np.array([0.1, 0.2, 0.3]))


@pytest.mark.asyncio
class TestGenerateEmbeddingContract:
    """Toute implementation de generate_embedding doit retourner list."""

    async def test_mock_embedding_service_returns_list(self):
        service = MockEmbeddingService(dimension=8)
        result = await service.generate_embedding("hello")
        assert isinstance(result, list), (
            f"MockEmbeddingService a retourne {type(result).__name__}, attendu list"
        )
        assert len(result) == 8

    async def test_mock_embedding_service_empty_text(self):
        service = MockEmbeddingService(dimension=8)
        result = await service.generate_embedding("")
        assert isinstance(result, list), (
            f"Texte vide a retourne {type(result).__name__}, attendu list"
        )


@pytest.mark.skipif(
    not importlib.util.find_spec("sentence_transformers"),
    reason="sentence_transformers not installed (Docker-only dependency)"
)
class TestDualEmbeddingServiceContract:
    """Simule le vrai bug : model.encode() retourne ndarray,
    generate_embedding() doit retourner list."""

    @pytest.fixture
    def mock_sentence_transformer(self):
        import unittest.mock as mock
        model = mock.MagicMock()
        model.encode.return_value = np.array([0.1] * 8)
        model.get_sentence_embedding_dimension.return_value = 8
        model.device = "cpu"
        return model

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_dict_with_lists(
        self, mock_sentence_transformer
    ):
        from api.services.dual_embedding_service import DualEmbeddingService
        service = DualEmbeddingService(dimension=8, device="cpu")
        service.text_model = mock_sentence_transformer
        service.code_model = mock_sentence_transformer

        result = await service.generate_embedding("hello")
        assert isinstance(result, dict)
        for key in ("text", "code"):
            val = result.get(key)
            assert val is None or isinstance(val, list), (
                f"'{key}' est {type(val).__name__}, attendu list ou None"
            )

    @pytest.mark.asyncio
    async def test_generate_embedding_legacy_returns_list(
        self, mock_sentence_transformer
    ):
        from api.services.dual_embedding_service import DualEmbeddingService
        service = DualEmbeddingService(dimension=8, device="cpu")
        service.text_model = mock_sentence_transformer
        service.code_model = mock_sentence_transformer

        result = await service.generate_embedding_legacy("hello")
        assert isinstance(result, list), (
            f"generate_embedding_legacy a retourne {type(result).__name__}, "
            f"attendu list. Verifier la conversion encode_text_sync -> list."
        )

    @pytest.mark.asyncio
    async def test_encode_text_sync_output_is_list_compatible(
        self, mock_sentence_transformer
    ):
        from api.services.dual_embedding_service import DualEmbeddingService
        service = DualEmbeddingService(dimension=8, device="cpu")
        service.text_model = mock_sentence_transformer
        service.code_model = mock_sentence_transformer

        raw = service.encode_text_sync("hello")
        assert hasattr(raw, 'tolist') or isinstance(raw, (list, tuple)), (
            f"Type inattendu : {type(raw).__name__}"
        )
        as_list = raw.tolist() if hasattr(raw, 'tolist') else raw
        assert isinstance(as_list, list)
        assert len(as_list) == 8


@pytest.mark.skipif(
    not importlib.util.find_spec("structlog"),
    reason="structlog not installed (Docker-only dependency)"
)
class TestDualEncoderAdapterContract:
    """Teste le contrat de DualEncoderAdapter.generate_embedding()
    (dependencies.py) -- le site qui avait le bug.

    Le constructeur prend un DualEmbeddingService.
    On mocke generate_embedding_legacy() pour retourner ndarray
    et on verifie que l'adapter retourne list.
    """

    @pytest.fixture
    def mock_dual_service(self):
        """Mock de DualEmbeddingService dont generate_embedding_legacy
        retourne ndarray (simulant le vrai comportement du model.encode)."""
        import unittest.mock as mock
        svc = mock.AsyncMock()
        svc.generate_embedding_legacy.return_value = np.array([0.1] * 8)
        svc.encode_text_sync.return_value = np.array([0.1] * 8)
        return svc

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_list(self, mock_dual_service):
        """
        generate_embedding('hello') DOIT retourner list meme si
        le service sous-jacent retourne ndarray.

        C'est le contrat -> List[float] qui etait viole.
        """
        from api.dependencies import DualEncoderAdapter

        adapter = DualEncoderAdapter(dual_service=mock_dual_service)
        result = await adapter.generate_embedding("hello")

        assert isinstance(result, list), (
            f"DualEncoderAdapter.generate_embedding a retourne "
            f"{type(result).__name__}, attendu list. "
            f"Verifier la conversion ndarray -> list dans l'adapter."
        )
        assert len(result) == 8, "Dimension incorrecte"

    @pytest.mark.asyncio
    async def test_generate_embedding_ragged_text(self, mock_dual_service):
        """Texte avec espaces/tabulations ne doit pas briser le contrat."""
        from api.dependencies import DualEncoderAdapter

        adapter = DualEncoderAdapter(dual_service=mock_dual_service)
        for text in ["", "  ", "hello world", "a" * 1000]:
            result = await adapter.generate_embedding(text)
            assert isinstance(result, list), (
                f"generate_embedding({text!r}) a retourne "
                f"{type(result).__name__}, attendu list"
            )

    @pytest.mark.asyncio
    async def test_encode_sync_compatible(self, mock_dual_service):
        """encode_sync() retourne ndarray (attendu) mais doit etre
        list-compatible (pour le pattern hasattr(x, tolist))."""
        from api.dependencies import DualEncoderAdapter

        adapter = DualEncoderAdapter(dual_service=mock_dual_service)
        raw = adapter.encode_sync("hello")

        # encode_sync peut retourner ndarray -- c'est permis
        # (server.py en a besoin pour np.mean())
        assert hasattr(raw, 'tolist') or isinstance(raw, (list, tuple)), (
            f"encode_sync a retourne {type(raw).__name__}, "
            f"attendu ndarray ou list"
        )

        # Mais doit etre convertible en list
        as_list = raw.tolist() if hasattr(raw, 'tolist') else raw
        assert isinstance(as_list, list)
