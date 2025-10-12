"""
Tests end-to-end de recherche sémantique avec base de données.
Valide que la recherche vectorielle retourne des résultats pertinents.
"""

import pytest
from datetime import datetime, timezone
from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
from db.repositories.event_repository import EventRepository, EventCreate


@pytest.mark.integration
@pytest.mark.asyncio
class TestSemanticSearchEndToEnd:
    """Tests end-to-end de recherche sémantique."""

    async def test_semantic_search_returns_relevant_results(
        self,
        async_engine,
        event_repository
    ):
        """
        Test end-to-end: recherche sémantique retourne résultats pertinents.
        """
        # Setup: Insérer événements avec contenu varié
        events_data = [
            {"text": "I love my pet cat", "category": "pets"},
            {"text": "Kittens are adorable animals", "category": "pets"},
            {"text": "My car is blue and fast", "category": "vehicles"},
            {"text": "Dogs are loyal companions", "category": "pets"},
            {"text": "Mathematics is fascinating", "category": "education"},
        ]

        # Générer embeddings et insérer
        service = SentenceTransformerEmbeddingService()
        inserted_ids = []

        for event_data in events_data:
            text = event_data["text"]
            embedding = await service.generate_embedding(text)

            event_create = EventCreate(
                content={"text": text},
                metadata={"category": event_data["category"]},
                embedding=embedding,
                timestamp=datetime.now(timezone.utc)
            )

            created_event = await event_repository.add(event_create)
            inserted_ids.append(created_event.id)

        # Query: Rechercher "feline pets"
        query = "feline pets"
        query_embedding = await service.generate_embedding(query)

        # Search
        results = await event_repository.search_vector(
            vector=query_embedding,
            limit=3
        )

        # Assertions
        assert len(results) >= 2, "Should return at least 2 results"

        # Top results devraient être cat/kitten events
        top_texts = [r.content.get("text", "") for r in results[:2]]

        assert any("cat" in text.lower() or "kitten" in text.lower() for text in top_texts), (
            f"Top results should mention cat/kitten, got: {top_texts}"
        )

        # Car event ne devrait PAS être dans top 2
        car_in_top2 = any("car" in text.lower() for text in top_texts)
        assert not car_in_top2, "Car event should not be in top 2 results for 'feline pets'"

        # Vérifier scores de similarité
        if hasattr(results[0], 'similarity_score'):
            assert results[0].similarity_score > 0.5, (
                f"Top result should have decent similarity, got {results[0].similarity_score:.3f}"
            )

        print(f"\n✅ Semantic search working!")
        print(f"Query: '{query}'")
        print(f"Top results:")
        for i, result in enumerate(results[:3], 1):
            text = result.content.get("text", "")
            score = getattr(result, 'similarity_score', 'N/A')
            print(f"  {i}. {text[:50]}... (score: {score})")

    async def test_hybrid_search_vector_plus_metadata(
        self,
        async_engine,
        event_repository
    ):
        """
        Test recherche hybride: vector + metadata filters.
        """
        # Setup: Insérer événements
        events_data = [
            {"text": "Cat playing", "category": "pets", "type": "video"},
            {"text": "Kitten sleeping", "category": "pets", "type": "image"},
            {"text": "Dog running", "category": "pets", "type": "video"},
            {"text": "Car racing", "category": "vehicles", "type": "video"},
        ]

        service = SentenceTransformerEmbeddingService()

        for event_data in events_data:
            embedding = await service.generate_embedding(event_data["text"])
            event_create = EventCreate(
                content={"text": event_data["text"]},
                metadata={
                    "category": event_data["category"],
                    "type": event_data["type"]
                },
                embedding=embedding,
                timestamp=datetime.now(timezone.utc)
            )
            await event_repository.add(event_create)

        # Query: "feline" + metadata: category=pets AND type=video
        query_embedding = await service.generate_embedding("feline")

        results = await event_repository.search_vector(
            vector=query_embedding,
            metadata={"category": "pets", "type": "video"},
            limit=5
        )

        # Assertions
        assert len(results) >= 1, "Should find at least 1 result"

        # Devrait retourner "Cat playing" (pets + video + sémantiquement proche)
        result_texts = [r.content.get("text", "") for r in results]
        assert "Cat playing" in result_texts, (
            f"Should find 'Cat playing', got: {result_texts}"
        )

        # Ne devrait PAS retourner "Kitten sleeping" (pets mais type=image)
        assert "Kitten sleeping" not in result_texts, (
            "Should NOT find 'Kitten sleeping' (wrong type)"
        )

        # Ne devrait PAS retourner "Car racing" (mauvaise catégorie)
        assert "Car racing" not in result_texts, (
            "Should NOT find 'Car racing' (wrong category)"
        )

        print(f"\n✅ Hybrid search (vector + metadata) working!")
        print(f"Results: {result_texts}")

    async def test_semantic_search_with_synonyms(
        self,
        async_engine,
        event_repository
    ):
        """
        Test que la recherche sémantique comprend les synonymes.
        """
        # Setup
        events_data = [
            "automobile driving fast",
            "vehicle on highway",
            "cat meowing loudly",
        ]

        service = SentenceTransformerEmbeddingService()

        for text in events_data:
            embedding = await service.generate_embedding(text)
            event_create = EventCreate(
                content={"text": text},
                metadata={},
                embedding=embedding,
                timestamp=datetime.now(timezone.utc)
            )
            await event_repository.add(event_create)

        # Query avec synonyme: "car" devrait trouver "automobile" et "vehicle"
        query = "car transportation"
        query_embedding = await service.generate_embedding(query)

        results = await event_repository.search_vector(
            vector=query_embedding,
            limit=3
        )

        assert len(results) >= 2, "Should find at least 2 results"

        # Top 2 devraient être automobile/vehicle, pas cat
        top_texts = [r.content.get("text", "") for r in results[:2]]

        car_related = any(
            "automobile" in text.lower() or "vehicle" in text.lower()
            for text in top_texts
        )
        assert car_related, (
            f"Top results should mention automobile/vehicle, got: {top_texts}"
        )

        cat_in_top2 = any("cat" in text.lower() for text in top_texts)
        assert not cat_in_top2, (
            "Cat event should not be in top 2 for car query"
        )

        print(f"\n✅ Synonym understanding working!")
        print(f"Query: '{query}'")
        print(f"Top results: {top_texts}")

    async def test_semantic_search_ranking_quality(
        self,
        async_engine,
        event_repository
    ):
        """
        Test que le ranking des résultats est de bonne qualité.
        """
        # Setup: Créer gradient de pertinence
        events_data = [
            "Persian cat breed information",      # Très pertinent
            "Cats and kittens playing together", # Très pertinent
            "Pet care tips for animals",         # Moyennement pertinent
            "Dog training methods",              # Peu pertinent
            "Computer programming tutorial",     # Pas pertinent
        ]

        service = SentenceTransformerEmbeddingService()

        for text in events_data:
            embedding = await service.generate_embedding(text)
            event_create = EventCreate(
                content={"text": text},
                metadata={},
                embedding=embedding,
                timestamp=datetime.now(timezone.utc)
            )
            await event_repository.add(event_create)

        # Query
        query = "information about cats"
        query_embedding = await service.generate_embedding(query)

        results = await event_repository.search_vector(
            vector=query_embedding,
            limit=5
        )

        # Les 2 premiers résultats devraient mentionner explicitement "cat"
        top_2_texts = [r.content.get("text", "") for r in results[:2]]

        cat_mentions = sum(1 for text in top_2_texts if "cat" in text.lower())
        assert cat_mentions >= 1, (
            f"At least 1 of top 2 should mention cats, got: {top_2_texts}"
        )

        # "Computer programming" ne devrait pas être dans top 3
        top_3_texts = [r.content.get("text", "") for r in results[:3]]
        programming_in_top3 = any("programming" in text.lower() for text in top_3_texts)
        assert not programming_in_top3, (
            "Programming tutorial should not be in top 3 for cat query"
        )

        print(f"\n✅ Ranking quality validated!")
        print(f"Query: '{query}'")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.content.get('text', '')}")
