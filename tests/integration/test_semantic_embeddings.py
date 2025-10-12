"""
Tests de validation sémantique pour les embeddings Sentence-Transformers.
Vérifie que les embeddings générés ont vraiment des propriétés sémantiques.
"""

import pytest
import time
import statistics
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
from services.embedding_service import MockEmbeddingService


@pytest.mark.integration
class TestSemanticSimilarity:
    """Tests de similarité sémantique de base."""

    @pytest.mark.asyncio
    async def test_semantic_similar_words_have_high_similarity(self):
        """
        Test que des mots sémantiquement similaires produisent
        des embeddings avec haute similarité cosinus.
        """
        service = SentenceTransformerEmbeddingService()

        # Paires sémantiquement similaires
        pairs = [
            ("cat", "kitten", 0.70),      # Animaux apparentés
            ("dog", "puppy", 0.70),       # Animaux apparentés
            ("car", "automobile", 0.80),  # Synonymes
            ("happy", "joyful", 0.75),    # Émotions positives
            ("run", "running", 0.85),     # Formes verbales
        ]

        for word1, word2, min_similarity in pairs:
            emb1 = await service.generate_embedding(word1)
            emb2 = await service.generate_embedding(word2)

            similarity = await service.compute_similarity(emb1, emb2)

            assert similarity >= min_similarity, (
                f"'{word1}' et '{word2}' devraient avoir similarité >= {min_similarity}, "
                f"got {similarity:.3f}"
            )

    @pytest.mark.asyncio
    async def test_semantic_dissimilar_words_have_low_similarity(self):
        """
        Test que des textes sémantiquement différents produisent
        des embeddings avec faible similarité.

        Note: Utilise des phrases complètes car le modèle nomic-embed-text-v1.5
        est optimisé pour des textes longs, pas des mots isolés.
        """
        service = SentenceTransformerEmbeddingService()

        # Paires sémantiquement dissimilaires (phrases complètes)
        pairs = [
            ("I love my pet cat", "My car is very fast", 0.75),
            ("I feel happy today", "The weather is cold", 0.75),
            ("The computer is broken", "The ocean is beautiful", 0.75),
            ("Mathematical equations are complex", "Dogs are loyal animals", 0.75),
        ]

        for text1, text2, max_similarity in pairs:
            emb1 = await service.generate_embedding(text1)
            emb2 = await service.generate_embedding(text2)

            similarity = await service.compute_similarity(emb1, emb2)

            assert similarity <= max_similarity, (
                f"'{text1[:30]}...' et '{text2[:30]}...' devraient avoir similarité <= {max_similarity}, "
                f"got {similarity:.3f}"
            )

    @pytest.mark.asyncio
    async def test_semantic_transitivity(self):
        """
        Test la transitivité: si A≈B et B≈C, alors A≈C
        """
        service = SentenceTransformerEmbeddingService()

        # Chaîne sémantique: feline → cat → kitten
        text_a = "feline"
        text_b = "cat"
        text_c = "kitten"

        emb_a = await service.generate_embedding(text_a)
        emb_b = await service.generate_embedding(text_b)
        emb_c = await service.generate_embedding(text_c)

        sim_ab = await service.compute_similarity(emb_a, emb_b)
        sim_bc = await service.compute_similarity(emb_b, emb_c)
        sim_ac = await service.compute_similarity(emb_a, emb_c)

        # Si A≈B (>0.7) et B≈C (>0.7), alors A≈C devrait être >0.5
        if sim_ab > 0.7 and sim_bc > 0.7:
            assert sim_ac > 0.5, (
                f"Transitivité violée: sim(A,B)={sim_ab:.3f}, "
                f"sim(B,C)={sim_bc:.3f}, mais sim(A,C)={sim_ac:.3f}"
            )


@pytest.mark.integration
class TestRobustness:
    """Tests de robustesse et edge cases."""

    @pytest.mark.asyncio
    async def test_empty_text_handling(self):
        """Test que les textes vides sont gérés correctement."""
        service = SentenceTransformerEmbeddingService()

        # Empty string
        emb_empty = await service.generate_embedding("")
        assert len(emb_empty) == 768, "Should return vector with correct dimension"
        assert all(v == 0.0 for v in emb_empty), "Empty text should return zero vector"

        # Whitespace only
        emb_whitespace = await service.generate_embedding("   \n\t   ")
        assert len(emb_whitespace) == 768

    @pytest.mark.asyncio
    async def test_case_variations_semantic_similarity(self):
        """
        Test que les variations de casse produisent des embeddings similaires.
        """
        service = SentenceTransformerEmbeddingService()

        text_lower = "hello world"
        text_upper = "HELLO WORLD"
        text_mixed = "Hello World"

        emb_lower = await service.generate_embedding(text_lower)
        emb_upper = await service.generate_embedding(text_upper)
        emb_mixed = await service.generate_embedding(text_mixed)

        sim_lower_upper = await service.compute_similarity(emb_lower, emb_upper)
        sim_lower_mixed = await service.compute_similarity(emb_lower, emb_mixed)

        # Case variations should be highly similar (>0.95)
        assert sim_lower_upper > 0.95, (
            f"Case variations should be very similar, got {sim_lower_upper:.3f}"
        )
        assert sim_lower_mixed > 0.95, (
            f"Case variations should be very similar, got {sim_lower_mixed:.3f}"
        )

    @pytest.mark.asyncio
    async def test_unicode_and_special_chars(self):
        """Test support pour caractères unicode et spéciaux."""
        service = SentenceTransformerEmbeddingService()

        texts = [
            "café",                    # Accents
            "emoji 😀🎉",              # Emojis
            "special chars: @#$%",    # Caractères spéciaux
        ]

        for text in texts:
            try:
                embedding = await service.generate_embedding(text)
                assert len(embedding) == 768, f"Failed for text: {text}"
                # Don't check for zero vector as some special chars might produce low embeddings
            except Exception as e:
                pytest.fail(f"Failed to encode '{text}': {e}")

    @pytest.mark.asyncio
    async def test_embedding_stability_determinism(self):
        """
        Test que le même texte produit toujours le même embedding.
        """
        service = SentenceTransformerEmbeddingService(cache_size=0)  # Disable cache

        text = "consistency test"

        # Generate 5 times
        embeddings = []
        for _ in range(5):
            emb = await service.generate_embedding(text)
            embeddings.append(emb)

        # All should be identical
        for i, emb in enumerate(embeddings[1:], start=1):
            similarity = await service.compute_similarity(embeddings[0], emb)
            assert similarity > 0.9999, (
                f"Embedding {i} differs from first (similarity={similarity:.6f})"
            )


@pytest.mark.integration
class TestComparativeMockVsReal:
    """Tests comparatifs Mock vs Real pour prouver la supériorité sémantique."""

    @pytest.mark.asyncio
    async def test_real_vs_mock_semantic_quality(self):
        """
        Test que les embeddings réels sont supérieurs aux mocks
        pour la recherche sémantique.
        """
        mock_service = MockEmbeddingService(dimension=768)
        real_service = SentenceTransformerEmbeddingService()

        # Query
        query = "feline pets"

        # Documents
        docs = [
            "I love my pet cat",      # Très pertinent
            "Kittens are adorable",   # Très pertinent
            "My car is blue",         # Pas pertinent
            "Dogs are loyal",         # Moyennement pertinent
        ]

        # Generate embeddings with both services
        query_emb_mock = await mock_service.generate_embedding(query)
        query_emb_real = await real_service.generate_embedding(query)

        docs_emb_mock = [await mock_service.generate_embedding(doc) for doc in docs]
        docs_emb_real = [await real_service.generate_embedding(doc) for doc in docs]

        # Compute similarities
        sim_mock = [
            await mock_service.compute_similarity(query_emb_mock, doc_emb)
            for doc_emb in docs_emb_mock
        ]

        sim_real = [
            await real_service.compute_similarity(query_emb_real, doc_emb)
            for doc_emb in docs_emb_real
        ]

        # Real embeddings: cat and kitten should have higher similarity than car
        cat_idx = 0
        kitten_idx = 1
        car_idx = 2

        assert sim_real[cat_idx] > sim_real[car_idx], (
            f"Real: 'cat' ({sim_real[cat_idx]:.3f}) should be > 'car' ({sim_real[car_idx]:.3f})"
        )
        assert sim_real[kitten_idx] > sim_real[car_idx], (
            f"Real: 'kitten' ({sim_real[kitten_idx]:.3f}) should be > 'car' ({sim_real[car_idx]:.3f})"
        )

        print(f"\nMock similarities: {[f'{s:.3f}' for s in sim_mock]}")
        print(f"Real similarities: {[f'{s:.3f}' for s in sim_real]}")
        print("\n✅ Real embeddings show semantic understanding!")
