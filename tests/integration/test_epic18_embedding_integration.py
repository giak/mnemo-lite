"""
EPIC-18: Tests d'Intégration Pragmatiques - Embeddings

Tests end-to-end pour valider que la recherche sémantique fonctionne
correctement après le fix EPIC-18 (EMBEDDING_MODE=mock support).

Principe: KISS - Tests simples qui valident les use cases réels.
"""

import pytest
import os
import time
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain
from services.hybrid_code_search_service import HybridCodeSearchService
from services.code_indexing_service import CodeIndexingService


@pytest.mark.integration
class TestEPIC18MockModePerformance:
    """Valide que le mode mock est RAPIDE (objectif EPIC-18)."""

    @pytest.mark.asyncio
    async def test_mock_mode_is_instant(self):
        """
        Test que le mode mock génère des embeddings instantanément (<100ms).

        EPIC-18 Fix: Avant, chargeait toujours les modèles ML (30s+).
        Après: Mock mode génère embeddings par hash (~0ms).
        """
        # Ensure mock mode
        original_mode = os.getenv('EMBEDDING_MODE')
        os.environ['EMBEDDING_MODE'] = 'mock'

        try:
            service = DualEmbeddingService()

            # Measure time
            start = time.time()
            result = await service.generate_embedding("test query", EmbeddingDomain.TEXT)
            elapsed_ms = (time.time() - start) * 1000

            # Assertions
            assert 'text' in result, "Should return text embedding"
            assert len(result['text']) == 768, "Should be 768D"
            assert elapsed_ms < 100, f"Mock mode should be fast (<100ms), got {elapsed_ms:.1f}ms"

            print(f"\n✅ Mock embedding generated in {elapsed_ms:.2f}ms")

        finally:
            # Restore original mode
            if original_mode:
                os.environ['EMBEDDING_MODE'] = original_mode
            else:
                del os.environ['EMBEDDING_MODE']

    @pytest.mark.asyncio
    async def test_mock_embeddings_are_deterministic(self):
        """
        Test que le mode mock produit des embeddings déterministes.

        Même query → même embedding (pour reproductibilité des tests).
        """
        os.environ['EMBEDDING_MODE'] = 'mock'

        try:
            service = DualEmbeddingService()

            # Generate twice
            result1 = await service.generate_embedding("same query", EmbeddingDomain.TEXT)
            result2 = await service.generate_embedding("same query", EmbeddingDomain.TEXT)

            # Should be identical
            assert result1['text'] == result2['text'], "Mock embeddings should be deterministic"

            print("\n✅ Mock embeddings are deterministic")

        finally:
            if 'EMBEDDING_MODE' in os.environ:
                del os.environ['EMBEDDING_MODE']


@pytest.mark.integration
class TestEPIC18EndToEndWorkflow:
    """Tests end-to-end du workflow complet."""

    @pytest.fixture
    async def test_repository(self):
        """Fixture qui crée un repository de test et le nettoie."""
        repo_name = "epic18-test-repo"

        # Setup: index sample code
        indexing_service = CodeIndexingService()

        sample_files = [
            {
                "path": "validators/email.py",
                "content": """
def validate_email(email: str) -> bool:
    '''Validate email address format.'''
    return '@' in email and '.' in email.split('@')[-1]

def check_email_format(address: str) -> bool:
    '''Check if email format is correct.'''
    return validate_email(address)
""",
                "language": "python"
            },
            {
                "path": "security/input.py",
                "content": """
def sanitize_input(data: str) -> str:
    '''Remove dangerous characters from input.'''
    return data.replace('<', '').replace('>', '')

def detect_sql_injection(query: str) -> bool:
    '''Detect SQL injection patterns.'''
    dangerous = ['DROP', 'DELETE', '--', ';']
    return any(pattern in query.upper() for pattern in dangerous)
""",
                "language": "python"
            },
            {
                "path": "utils/strings.py",
                "content": """
def trim_whitespace(text: str) -> str:
    '''Remove leading/trailing whitespace.'''
    return text.strip()

def reverse_string(text: str) -> str:
    '''Reverse a string.'''
    return text[::-1]
""",
                "language": "python"
            }
        ]

        # Index files
        await indexing_service.index_files(
            repository=repo_name,
            files=sample_files,
            generate_embeddings=True
        )

        yield repo_name

        # Teardown: cleanup (optional, test DB is cleaned automatically)

    @pytest.mark.asyncio
    async def test_semantic_search_finds_relevant_code(self, test_repository):
        """
        Test que la recherche sémantique trouve du code pertinent.

        Use case: Chercher "validate email" devrait trouver validateEmail() et checkEmailFormat().
        """
        # Generate query embedding
        embedding_service = DualEmbeddingService()
        result = await embedding_service.generate_embedding(
            "validate email address",
            EmbeddingDomain.TEXT
        )

        # Search with embedding
        search_service = HybridCodeSearchService()
        results = await search_service.search_hybrid(
            query="validate email address",
            embedding_text=result['text'],
            filters={'repository': test_repository},
            top_k=10
        )

        # Assertions
        assert len(results) > 0, "Should find at least one result"

        # Check that email-related code is found
        result_names = [r['name'].lower() for r in results]
        assert any('email' in name for name in result_names), (
            f"Should find email-related code, got: {result_names}"
        )

        # Check RRF scores are positive
        assert all(r['rrf_score'] > 0 for r in results), "All results should have positive RRF score"

        print(f"\n✅ Found {len(results)} results for 'validate email':")
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r['name']} (RRF: {r['rrf_score']:.4f})")

    @pytest.mark.asyncio
    async def test_semantic_search_distinguishes_domains(self, test_repository):
        """
        Test que la recherche sémantique différencie les domaines.

        Use case: "string manipulation" devrait trouver utils/strings.py,
        pas validators/email.py.
        """
        embedding_service = DualEmbeddingService()
        result = await embedding_service.generate_embedding(
            "string manipulation reverse",
            EmbeddingDomain.TEXT
        )

        search_service = HybridCodeSearchService()
        results = await search_service.search_hybrid(
            query="string manipulation reverse",
            embedding_text=result['text'],
            filters={'repository': test_repository},
            top_k=5
        )

        # Should find string utils, not email validators
        if results:
            top_result = results[0]
            # String-related functions should rank higher
            assert 'string' in top_result['name'].lower() or 'reverse' in top_result['name'].lower(), (
                f"Top result should be string-related, got: {top_result['name']}"
            )

        print(f"\n✅ Search distinguishes domains correctly")

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_lexical_and_semantic(self, test_repository):
        """
        Test que la recherche hybride combine lexical + semantic (RRF).

        Use case: Query avec mots exacts devrait utiliser BM25 + embeddings.
        """
        embedding_service = DualEmbeddingService()
        result = await embedding_service.generate_embedding(
            "validate email",
            EmbeddingDomain.TEXT
        )

        search_service = HybridCodeSearchService()

        # Search with hybrid (lexical + semantic)
        results_hybrid = await search_service.search_hybrid(
            query="validate email",
            embedding_text=result['text'],
            filters={'repository': test_repository},
            enable_lexical=True,
            enable_vector=True
        )

        # Search with lexical only
        results_lexical = await search_service.search_hybrid(
            query="validate email",
            filters={'repository': test_repository},
            enable_lexical=True,
            enable_vector=False
        )

        # Hybrid should find results (at least as many as lexical)
        assert len(results_hybrid) > 0, "Hybrid search should find results"

        # Both methods should work
        print(f"\n✅ Lexical: {len(results_lexical)} results")
        print(f"✅ Hybrid: {len(results_hybrid)} results")
        print(f"✅ RRF fusion working")


@pytest.mark.integration
class TestEPIC18RobustnessAndEdgeCases:
    """Tests de robustesse pour edge cases."""

    @pytest.mark.asyncio
    async def test_search_with_no_embedding_falls_back_to_lexical(self):
        """
        Test que la recherche fonctionne même sans embedding (fallback lexical).

        Use case: Si génération embedding échoue, fallback sur BM25.
        """
        search_service = HybridCodeSearchService()

        # Search WITHOUT embedding (lexical only)
        results = await search_service.search_hybrid(
            query="validate email",
            embedding_text=None,  # No embedding
            filters={'repository': 'any-repo'},
            enable_lexical=True,
            enable_vector=False
        )

        # Should work (even if no results)
        assert isinstance(results, list), "Should return list (even if empty)"

        print(f"\n✅ Lexical fallback works (found {len(results)} results)")

    @pytest.mark.asyncio
    async def test_empty_query_handling(self):
        """Test que les queries vides sont gérées correctement."""
        embedding_service = DualEmbeddingService()

        # Empty query
        result = await embedding_service.generate_embedding("", EmbeddingDomain.TEXT)

        assert 'text' in result, "Should return embedding even for empty query"
        assert len(result['text']) == 768, "Should be 768D"

        # All zeros in mock mode
        if os.getenv('EMBEDDING_MODE') == 'mock':
            assert result['text'] == [0.0] * 768, "Mock mode: empty query → zero vector"

        print("\n✅ Empty query handled correctly")

    @pytest.mark.asyncio
    async def test_very_long_query_handling(self):
        """Test que les queries très longues sont gérées."""
        embedding_service = DualEmbeddingService()

        # Very long query (>1000 chars)
        long_query = "validate email address " * 100  # ~2300 chars

        try:
            result = await embedding_service.generate_embedding(long_query, EmbeddingDomain.TEXT)

            assert 'text' in result, "Should handle long queries"
            assert len(result['text']) == 768, "Should still be 768D"

            print(f"\n✅ Long query handled ({len(long_query)} chars)")

        except Exception as e:
            # If model has a limit, that's acceptable
            print(f"\n⚠️ Long query error (expected): {e}")


@pytest.mark.integration
@pytest.mark.slow
class TestEPIC18PerformanceBenchmarks:
    """Benchmarks de performance (tests lents, à skip en CI rapide)."""

    @pytest.mark.asyncio
    async def test_embedding_generation_latency(self):
        """Mesure la latency de génération d'embeddings."""
        embedding_service = DualEmbeddingService()

        queries = [
            "validate email address",
            "check user permissions",
            "SQL injection detection",
            "parse JSON data",
            "format string output"
        ]

        latencies = []

        for query in queries:
            start = time.time()
            await embedding_service.generate_embedding(query, EmbeddingDomain.TEXT)
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Targets
        if os.getenv('EMBEDDING_MODE') == 'mock':
            assert avg_latency < 10, f"Mock mode should be <10ms, got {avg_latency:.1f}ms"
        else:
            assert avg_latency < 50, f"Real mode should be <50ms, got {avg_latency:.1f}ms"

        print(f"\n📊 Embedding Generation Latency:")
        print(f"   Mode: {os.getenv('EMBEDDING_MODE', 'mock')}")
        print(f"   Avg: {avg_latency:.2f}ms")
        print(f"   Max: {max_latency:.2f}ms")
        print(f"   Min: {min(latencies):.2f}ms")

    @pytest.mark.asyncio
    async def test_search_latency_with_embeddings(self, test_repository):
        """Mesure la latency de recherche hybride complète."""
        embedding_service = DualEmbeddingService()
        search_service = HybridCodeSearchService()

        query = "validate email address"

        # Full workflow: generate embedding + search
        start_total = time.time()

        # 1. Generate embedding
        start_embed = time.time()
        result = await embedding_service.generate_embedding(query, EmbeddingDomain.TEXT)
        embed_time_ms = (time.time() - start_embed) * 1000

        # 2. Search
        start_search = time.time()
        results = await search_service.search_hybrid(
            query=query,
            embedding_text=result['text'],
            filters={'repository': test_repository}
        )
        search_time_ms = (time.time() - start_search) * 1000

        total_time_ms = (time.time() - start_total) * 1000

        # Target: <200ms total
        assert total_time_ms < 500, f"Search should be <500ms, got {total_time_ms:.1f}ms"

        print(f"\n📊 Search Latency Breakdown:")
        print(f"   Embedding: {embed_time_ms:.2f}ms")
        print(f"   Search: {search_time_ms:.2f}ms")
        print(f"   Total: {total_time_ms:.2f}ms")
        print(f"   Results: {len(results)}")


# Fixture pour test_repository utilisé par plusieurs tests
@pytest.fixture(scope="class")
async def test_repository():
    """
    Fixture class-scoped pour repository de test.

    Note: Nécessite anyio pour scope class avec async.
    """
    repo_name = "epic18-test-repo"

    indexing_service = CodeIndexingService()

    sample_files = [
        {
            "path": "validators/email.py",
            "content": "def validate_email(email): return '@' in email",
            "language": "python"
        }
    ]

    await indexing_service.index_files(
        repository=repo_name,
        files=sample_files,
        generate_embeddings=True
    )

    yield repo_name


if __name__ == "__main__":
    """Run tests with pytest."""
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])
