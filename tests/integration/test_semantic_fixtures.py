"""
Tests sémantiques basés sur des fixtures validées par des humains.
Utilise semantic_test_cases.json pour des tests reproductibles.
"""

import pytest
import json
from pathlib import Path
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService


@pytest.fixture
def test_cases():
    """Charge les test cases depuis le fichier JSON."""
    test_file = Path(__file__).parent.parent / "fixtures" / "semantic_test_cases.json"
    with open(test_file) as f:
        return json.load(f)


@pytest.mark.integration
class TestHumanValidatedCases:
    """Tests basés sur des cas validés par des humains."""

    @pytest.mark.asyncio
    async def test_similarity_cases(self, test_cases):
        """
        Test tous les cas de similarité du fichier de fixtures.
        """
        service = SentenceTransformerEmbeddingService()

        for case in test_cases["similarity_tests"]:
            emb1 = await service.generate_embedding(case["text1"])
            emb2 = await service.generate_embedding(case["text2"])
            similarity = await service.compute_similarity(emb1, emb2)

            assert similarity >= case["expected_min_similarity"], (
                f"{case['text1']}/{case['text2']}: "
                f"Expected >={case['expected_min_similarity']}, got {similarity:.3f}. "
                f"Reason: {case['reason']}"
            )

            print(f"✓ {case['text1']} ↔ {case['text2']}: {similarity:.3f} "
                  f"(expected ≥{case['expected_min_similarity']})")

    @pytest.mark.asyncio
    async def test_dissimilarity_cases(self, test_cases):
        """
        Test tous les cas de dissimilarité du fichier de fixtures.
        """
        service = SentenceTransformerEmbeddingService()

        for case in test_cases["dissimilarity_tests"]:
            emb1 = await service.generate_embedding(case["text1"])
            emb2 = await service.generate_embedding(case["text2"])
            similarity = await service.compute_similarity(emb1, emb2)

            assert similarity <= case["expected_max_similarity"], (
                f"{case['text1']}/{case['text2']}: "
                f"Expected <={case['expected_max_similarity']}, got {similarity:.3f}. "
                f"Reason: {case['reason']}"
            )

            print(f"✓ {case['text1']} ↔ {case['text2']}: {similarity:.3f} "
                  f"(expected ≤{case['expected_max_similarity']})")

    @pytest.mark.asyncio
    async def test_search_ranking_cases(self, test_cases):
        """
        Test les cas de ranking de recherche.
        """
        service = SentenceTransformerEmbeddingService()

        for case in test_cases["search_tests"]:
            query = case["query"]
            documents = case["documents"]

            # Générer embeddings
            query_emb = await service.generate_embedding(query)
            doc_embeddings = []

            for doc in documents:
                emb = await service.generate_embedding(doc["text"])
                similarity = await service.compute_similarity(query_emb, emb)
                doc_embeddings.append({
                    "text": doc["text"],
                    "relevance": doc["relevance"],
                    "similarity": similarity
                })

            # Trier par similarité
            doc_embeddings.sort(key=lambda x: x["similarity"], reverse=True)

            # Vérifier top 2
            top_2_texts = [d["text"] for d in doc_embeddings[:2]]

            # Vérifier que les documents attendus sont dans top 2
            for expected_text in case["expected_top_2_contain"]:
                found = any(expected_text in text for text in top_2_texts)
                assert found, (
                    f"Query '{query}': Expected '{expected_text}' in top 2, "
                    f"got: {top_2_texts}"
                )

            # Vérifier que les documents non-pertinents ne sont PAS dans top 2
            for unexpected_text in case["expected_not_in_top_2"]:
                found = any(unexpected_text in text for text in top_2_texts)
                assert not found, (
                    f"Query '{query}': '{unexpected_text}' should NOT be in top 2, "
                    f"got: {top_2_texts}"
                )

            print(f"\n✓ Query: '{query}'")
            print(f"  Top 2: {top_2_texts}")
            for i, doc in enumerate(doc_embeddings[:3], 1):
                print(f"  {i}. {doc['text'][:50]}... "
                      f"(sim: {doc['similarity']:.3f}, relevance: {doc['relevance']})")

    @pytest.mark.asyncio
    async def test_robustness_cases(self, test_cases):
        """
        Test les cas de robustesse (variations de casse, ponctuation, etc).
        """
        service = SentenceTransformerEmbeddingService()

        for case in test_cases["robustness_tests"]:
            variants = case["variants"]

            # Générer embeddings pour toutes les variantes
            embeddings = []
            for variant in variants:
                emb = await service.generate_embedding(variant)
                embeddings.append(emb)

            # Toutes les variantes devraient être très similaires
            base_emb = embeddings[0]

            for i, emb in enumerate(embeddings[1:], 1):
                similarity = await service.compute_similarity(base_emb, emb)

                assert similarity >= case["expected_min_similarity"], (
                    f"{case['test_name']}: Variant '{variants[i]}' vs '{variants[0]}' "
                    f"Expected >={case['expected_min_similarity']}, got {similarity:.3f}. "
                    f"Reason: {case['reason']}"
                )

                print(f"✓ {case['test_name']}: '{variants[0]}' ↔ '{variants[i]}': "
                      f"{similarity:.3f}")
