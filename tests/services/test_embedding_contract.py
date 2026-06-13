"""
Tests de contrat de type pour le pipeline d'embedding.

Ces tests vérifient que les fonctions du pipeline respectent
leurs annotations de type (-> List[float]), et échoueront
immédiatement si une implémentation retourne np.ndarray
à la place d'une list Python.

La violation de contrat la plus fréquente :
  model.encode(convert_to_numpy=True) -> np.ndarray
  generate_embedding() annote -> List[float] mais retourne ndarray
  -> crash sur format_vector_for_sql(), if not embedding(), etc.
"""

import numpy as np
import pytest
from utils.sql_vector import format_vector_for_sql, format_halfvec_for_sql
from services.embedding_service import MockEmbeddingService


class TestFormatVectorForSqlContract:
    """format_vector_for_sql attend list/tuple -- pas ndarray."""

    def test_accepts_list(self):
        emb = [0.1, 0.2, 0.3]
        result = format_vector_for_sql(emb)
        assert isinstance(result, str)

    def test_accepts_tuple(self):
        emb = (0.1, 0.2, 0.3)
        result = format_vector_for_sql(emb)
        assert isinstance(result, str)

    def test_rejects_ndarray(self):
        emb = np.array([0.1, 0.2, 0.3])
        with pytest.raises(ValueError, match="Expected list/tuple"):
            format_vector_for_sql(emb)

    def test_rejects_ndarray_halfvec(self):
        emb = np.array([0.1, 0.2, 0.3])
        with pytest.raises(ValueError, match="Expected list/tuple"):
            format_halfvec_for_sql(emb)


class TestGenerateEmbeddingContract:
    """Toute implementation de generate_embedding doit retourner list."""

    @pytest.mark.asyncio
    async def test_mock_embedding_service_returns_list(self):
        service = MockEmbeddingService(dimension=8)
        result = await service.generate_embedding("hello")
        assert isinstance(result, list), (
            f"MockEmbeddingService a retourne {type(result).__name__}, attendu list"
        )
        assert len(result) == 8

    @pytest.mark.asyncio
    async def test_mock_embedding_service_empty_text(self):
        service = MockEmbeddingService(dimension=8)
        result = await service.generate_embedding("")
        assert isinstance(result, list), (
            f"Texte vide a retourne {type(result).__name__}, attendu list"
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
        from services.dual_embedding_service import DualEmbeddingService
        service = DualEmbeddingService(text_dimension=8, code_dimension=8, device="cpu")
        service._text_model = mock_sentence_transformer
        service._code_model = mock_sentence_transformer

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
        from services.dual_embedding_service import DualEmbeddingService
        service = DualEmbeddingService(text_dimension=8, code_dimension=8, device="cpu")
        service._text_model = mock_sentence_transformer
        service._code_model = mock_sentence_transformer

        result = await service.generate_embedding_legacy("hello")
        assert isinstance(result, list), (
            f"generate_embedding_legacy a retourne {type(result).__name__}, "
            f"attendu list. Verifier la conversion encode_text_sync -> list."
        )

    @pytest.mark.asyncio
    async def test_encode_text_sync_output_is_list_compatible(
        self, mock_sentence_transformer
    ):
        """encode_text_sync() peut retourner ndarray (pour server.py),
        mais doit etre convertible en list sans perte."""
        from services.dual_embedding_service import DualEmbeddingService
        service = DualEmbeddingService(text_dimension=8, code_dimension=8, device="cpu")
        service._text_model = mock_sentence_transformer
        service._code_model = mock_sentence_transformer

        raw = service.encode_text_sync("hello")
        assert hasattr(raw, 'tolist') or isinstance(raw, (list, tuple)), (
            f"Type inattendu : {type(raw).__name__}"
        )

        as_list = raw.tolist() if hasattr(raw, 'tolist') else raw
        assert isinstance(as_list, list)
        assert len(as_list) == 8
