"""Tests for EPIC-32: Query Understanding Service (deterministic)."""

import pytest
from services.query_understanding_service import QueryUnderstandingService


class TestQueryUnderstandingService:
    """Tests for deterministic query understanding."""

    def test_extract_keywords_simple_query(self):
        """Test basic keyword extraction."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("how does Redis caching work?")
        
        assert "redis" in result.hl_keywords
        assert "caching" in result.hl_keywords
        assert "Redis" in result.ll_keywords

    def test_extract_keywords_with_acronym(self):
        """Test acronym detection."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("What is the EU DSA regulation?")
        
        assert "EU" in result.ll_keywords
        assert "DSA" in result.ll_keywords

    def test_extract_keywords_with_version(self):
        """Test version detection."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("PostgreSQL 18 with pgvector 0.8")
        
        assert "18" in result.ll_keywords or "0.8" in result.ll_keywords

    def test_extract_keywords_stopswords_filtered(self):
        """Test that stopwords are excluded from HL keywords."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("the quick brown fox jumps over the lazy dog")
        
        assert "the" not in result.hl_keywords
        assert "over" not in result.hl_keywords

    def test_extract_keywords_empty_query(self):
        """Test empty query returns empty keywords."""
        service = QueryUnderstandingService()
        result = service.extract_keywords("")
        
        assert result.hl_keywords == []
        assert result.ll_keywords == []
