"""Tests for EPIC-32: GLiNER Service."""

import pytest
from unittest.mock import MagicMock, patch

from services.gliner_service import GLiNERService


class TestGLiNERService:
    """Tests for GLiNERService."""

    @patch("gliner.GLiNER")
    def test_load_model_success(self, mock_gliner_class):
        """Test successful model loading."""
        mock_gliner_class.from_pretrained.return_value = MagicMock()
        service = GLiNERService(model_path="/test/path")
        service._load_model()  # Force load since it's lazy

        assert service.model is not None
        mock_gliner_class.from_pretrained.assert_called_once_with("/test/path")

    def test_load_model_missing(self):
        """Test graceful handling of missing model."""
        service = GLiNERService(model_path="/nonexistent/path")

        assert service.model is None

    @patch("gliner.GLiNER")
    def test_extract_entities(self, mock_gliner_class):
        """Test entity extraction with post-processing."""
        mock_model = MagicMock()
        mock_model.predict_entities.return_value = [
            {"text": "Redis", "label": "technology", "start": 8, "end": 13},
            {"text": "PostgreSQL", "label": "technology", "start": 30, "end": 40},
            {"text": "Redis", "label": "technology", "start": 50, "end": 55},
        ]
        mock_gliner_class.from_pretrained.return_value = mock_model

        service = GLiNERService(model_path="/test/path")
        result = service.extract_entities("We use Redis and PostgreSQL. Redis is fast.")

        assert len(result) == 2
        names = [e["name"] for e in result]
        assert "Redis" in names
        assert "PostgreSQL" in names

    @patch("gliner.GLiNER")
    def test_extract_entities_filters_invalid(self, mock_gliner_class):
        """Test that entities not in text are filtered out."""
        mock_model = MagicMock()
        mock_model.predict_entities.return_value = [
            {"text": "MySQL", "label": "technology", "start": 0, "end": 5},
        ]
        mock_gliner_class.from_pretrained.return_value = mock_model

        service = GLiNERService(model_path="/test/path")
        result = service.extract_entities("We use Redis and PostgreSQL.")

        assert result == []

    def test_extract_entities_no_model(self):
        """Test returns empty list when model not loaded."""
        service = GLiNERService(model_path="/nonexistent")
        result = service.extract_entities("test")
        assert result == []

    @patch("gliner.GLiNER")
    def test_post_process_type_mapping(self, mock_gliner_class):
        """Test type mapping in post-processing."""
        mock_model = MagicMock()
        mock_model.predict_entities.return_value = [
            {"text": "Google", "label": "org", "start": 0, "end": 6},
            {"text": "John", "label": "per", "start": 10, "end": 14},
        ]
        mock_gliner_class.from_pretrained.return_value = mock_model

        service = GLiNERService(model_path="/test/path")
        result = service.extract_entities("Google John")

        assert result[0]["type"] == "organization"
        assert result[1]["type"] == "person"
