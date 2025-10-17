"""
Integration tests for Hybrid Code Search.

Tests the complete hybrid search pipeline including:
- Lexical search (pg_trgm)
- Vector search (HNSW)
- RRF fusion
- API endpoints

Uses real database with test data.
"""

import pytest
import pytest_asyncio
import uuid
from typing import List
import numpy as np
from fastapi.testclient import TestClient

from main import app
from services.lexical_search_service import LexicalSearchService
from services.vector_search_service import VectorSearchService
from services.rrf_fusion_service import RRFFusionService
from services.hybrid_code_search_service import HybridCodeSearchService, SearchFilters


@pytest.fixture
def client():
    """Create FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.anyio
class TestHybridSearchIntegration:
    """Integration tests for hybrid code search pipeline."""

    async def test_lexical_search_basic(self, test_engine):
        """Test basic lexical search functionality."""
        service = LexicalSearchService(engine=test_engine)

        results = await service.search(query="function", limit=10)

        # Should return results without error
        assert isinstance(results, list)
        # Each result should have expected fields
        for result in results:
            assert hasattr(result, 'chunk_id')
            assert hasattr(result, 'similarity_score')
            assert hasattr(result, 'rank')

    async def test_vector_search_basic(self, test_engine):
        """Test basic vector search functionality."""
        service = VectorSearchService(engine=test_engine)

        # Create dummy embedding (768D)
        embedding = [0.1] * 768

        results = await service.search(embedding=embedding, limit=10)

        # Should complete without error
        assert isinstance(results, list)
        # Each result should have expected fields
        for result in results:
            assert hasattr(result, 'chunk_id')
            assert hasattr(result, 'similarity')
            assert hasattr(result, 'distance')
            assert hasattr(result, 'rank')

    async def test_hybrid_search_lexical_only(self, test_engine):
        """Test hybrid search (lexical-only)."""
        service = HybridCodeSearchService(engine=test_engine)

        response = await service.search(
            query="calculate total",
            enable_vector=False,
            top_k=10,
        )

        # Should complete successfully
        assert isinstance(response.results, list)
        assert response.metadata.lexical_enabled is True
        assert response.metadata.vector_enabled is False

    async def test_hybrid_search_vector_only(self, test_engine):
        """Test hybrid search (vector-only)."""
        service = HybridCodeSearchService(engine=test_engine)

        # Create dummy embedding
        embedding = [0.1] * 768

        response = await service.search(
            query="calculate total",
            embedding_text=embedding,
            enable_lexical=False,
            top_k=10,
        )

        # Should complete successfully
        assert isinstance(response.results, list)
        assert response.metadata.lexical_enabled is False
        assert response.metadata.vector_enabled is True

    async def test_hybrid_search_both_methods(self, test_engine):
        """Test hybrid search (both methods)."""
        service = HybridCodeSearchService(engine=test_engine)

        # Create dummy embedding
        embedding = [0.1] * 768

        response = await service.search(
            query="calculate total",
            embedding_text=embedding,
            top_k=10,
        )

        # Should complete successfully
        assert isinstance(response.results, list)
        assert response.metadata.lexical_enabled is True
        assert response.metadata.vector_enabled is True

    async def test_hybrid_search_with_auto_weights(self, test_engine):
        """Test hybrid search with automatic weight selection."""
        service = HybridCodeSearchService(engine=test_engine)

        embedding = [0.1] * 768

        # Code-heavy query (has operators)
        response = await service.search_with_auto_weights(
            query="function calculate(a, b) { return a + b; }",
            embedding_text=embedding,
            top_k=10,
        )

        # Should complete without error
        assert response.metadata.execution_time_ms > 0

    async def test_hybrid_search_invalid_inputs(self, test_engine):
        """Test hybrid search with invalid inputs."""
        service = HybridCodeSearchService(engine=test_engine)

        # Empty query
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await service.search(query="", enable_vector=False, top_k=10)

        # Both methods disabled
        with pytest.raises(ValueError, match="At least one search method must be enabled"):
            await service.search(
                query="test",
                enable_lexical=False,
                enable_vector=False,
                top_k=10,
            )

    async def test_hybrid_search_with_filters(self, test_engine):
        """Test hybrid search with filters."""
        service = HybridCodeSearchService(engine=test_engine)

        filters = SearchFilters(
            language="python",
            chunk_type="function",
        )

        response = await service.search(
            query="calculate",
            filters=filters,
            enable_vector=False,
            top_k=10,
        )

        # Should complete without error
        assert isinstance(response.results, list)

    async def test_vector_search_invalid_embedding_dimension(self, test_engine):
        """Test vector search with invalid embedding dimension."""
        service = VectorSearchService(engine=test_engine)

        # Invalid dimension (not 768)
        with pytest.raises(ValueError, match="768-dimensional vector"):
            await service.search(embedding=[0.1] * 100, limit=10)

    async def test_vector_search_invalid_embedding_domain(self, test_engine):
        """Test vector search with invalid embedding domain."""
        service = VectorSearchService(engine=test_engine)

        embedding = [0.1] * 768

        with pytest.raises(ValueError, match="embedding_domain must be"):
            await service.search(
                embedding=embedding,
                embedding_domain="INVALID",
                limit=10,
            )

    async def test_lexical_search_with_stats(self, test_engine):
        """Test lexical search with statistics."""
        service = LexicalSearchService(engine=test_engine)

        results, stats = await service.search_with_stats(
            query="calculate total",
            limit=10,
        )

        # Should return stats
        assert "total_candidates" in stats
        assert "avg_score" in stats
        assert "search_time_ms" in stats
        assert stats["search_time_ms"] > 0

    async def test_vector_search_with_stats(self, test_engine):
        """Test vector search with statistics."""
        service = VectorSearchService(engine=test_engine)

        embedding = [0.1] * 768

        results, stats = await service.search_with_stats(
            embedding=embedding,
            limit=10,
        )

        # Should return stats
        assert "total_results" in stats
        assert "avg_similarity" in stats
        assert "search_time_ms" in stats
        assert "ef_search" in stats
        assert stats["ef_search"] == 100  # Default

    async def test_vector_search_both_domains(self, test_engine):
        """Test searching both TEXT and CODE embeddings in parallel."""
        service = VectorSearchService(engine=test_engine)

        embedding_text = [0.1] * 768
        embedding_code = [0.2] * 768

        text_results, code_results = await service.search_both_domains(
            embedding_text=embedding_text,
            embedding_code=embedding_code,
            limit_per_domain=10,
        )

        # Should return results for both domains
        assert isinstance(text_results, list)
        assert isinstance(code_results, list)

    async def test_hybrid_search_performance(self, test_engine):
        """Test that hybrid search meets performance targets."""
        service = HybridCodeSearchService(engine=test_engine)

        embedding = [0.1] * 768

        response = await service.search(
            query="calculate total",
            embedding_text=embedding,
            top_k=10,
        )

        # Should meet performance target (P95 < 50ms)
        # Be lenient for test environment
        assert response.metadata.execution_time_ms < 500  # 500ms for test env

    async def test_lexical_search_threshold_setting(self, test_engine):
        """Test setting lexical search similarity threshold."""
        service = LexicalSearchService(engine=test_engine)

        # Test default threshold
        assert service.similarity_threshold == 0.1

        # Test setting valid threshold
        service.set_similarity_threshold(0.3)
        assert service.similarity_threshold == 0.3

        # Test invalid threshold
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            service.set_similarity_threshold(1.5)

    async def test_vector_search_ef_search_setting(self, test_engine):
        """Test setting HNSW ef_search parameter."""
        service = VectorSearchService(engine=test_engine)

        # Test default ef_search
        assert service.ef_search == 100

        # Test setting valid ef_search
        service.set_ef_search(200)
        assert service.ef_search == 200

        # Test invalid ef_search
        with pytest.raises(ValueError, match="must be between 10 and 1000"):
            service.set_ef_search(5)

        with pytest.raises(ValueError, match="must be between 10 and 1000"):
            service.set_ef_search(2000)


@pytest.mark.anyio
class TestHybridSearchAPI:
    """Integration tests for hybrid search API endpoints."""

    async def test_health_endpoint(self, client):
        """Test search service health endpoint."""
        response = client.get("/v1/code/search/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "services" in data

    async def test_hybrid_search_endpoint_lexical_only(self, client):
        """Test hybrid search endpoint with lexical-only search."""
        response = client.post(
            "/v1/code/search/hybrid",
            json={
                "query": "calculate total",
                "enable_vector": False,
                "top_k": 5,
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "metadata" in data
        assert data["metadata"]["lexical_enabled"] is True
        assert data["metadata"]["vector_enabled"] is False

    async def test_hybrid_search_endpoint_with_embedding(self, client):
        """Test hybrid search endpoint with embedding."""
        embedding = [0.1] * 768

        response = client.post(
            "/v1/code/search/hybrid",
            json={
                "query": "calculate total",
                "embedding_text": embedding,
                "top_k": 5,
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "metadata" in data

    async def test_hybrid_search_endpoint_invalid_query(self, client):
        """Test hybrid search endpoint with invalid query."""
        response = client.post(
            "/v1/code/search/hybrid",
            json={
                "query": "",
                "enable_vector": False,
                "top_k": 5,
            },
        )

        # Should return 422 Unprocessable Entity (Pydantic validation error)
        assert response.status_code == 422

    async def test_lexical_search_endpoint(self, client):
        """Test lexical-only search endpoint."""
        response = client.post(
            "/v1/code/search/lexical",
            json={
                "query": "calculate",
                "limit": 10,
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "total_results" in data

    async def test_vector_search_endpoint(self, client):
        """Test vector-only search endpoint."""
        embedding = [0.1] * 768

        response = client.post(
            "/v1/code/search/vector",
            json={
                "embedding": embedding,
                "embedding_domain": "TEXT",
                "limit": 10,
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "total_results" in data
        assert data["embedding_domain"] == "TEXT"

    async def test_vector_search_endpoint_invalid_domain(self, client):
        """Test vector search endpoint with invalid embedding domain."""
        embedding = [0.1] * 768

        response = client.post(
            "/v1/code/search/vector",
            json={
                "embedding": embedding,
                "embedding_domain": "INVALID",
                "limit": 10,
            },
        )

        # Should return 400 Bad Request
        assert response.status_code == 400
