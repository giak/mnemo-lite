"""
Tests pour le service de recherche de mémoires.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Assuming the test runs from the /app directory inside Docker
# Adjust imports based on the actual project structure if needed
from services.memory_search_service import MemorySearchService
from models.memory_models import Memory
from models.event_models import EventModel
# Correct the imports for the protocols
from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol


# Fixtures
@pytest.fixture
def mock_event_repo():
    repo = AsyncMock(spec=EventRepositoryProtocol)
    # Mock the method used by search_hybrid
    repo.search_vector = AsyncMock(return_value=[]) 
    return repo


@pytest.fixture
def mock_memory_repo():
    repo = AsyncMock(spec=MemoryRepositoryProtocol)
    # Mock methods that might be called directly (though we aim to reduce this)
    repo.search_by_embedding = AsyncMock(return_value=([], 0))
    repo.list_memories = AsyncMock(return_value=([], 0))
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_embedding_service():
    """Fixture pour créer un mock du service d'embeddings."""
    mock_service = AsyncMock()
    # Configuration du mock pour renvoyer un embedding de test
    # Generate 768 dimensions (e.g., repeat a small pattern)
    pattern = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8] # 8 elements
    mock_service.generate_embedding.return_value = pattern * 96 # 8 * 96 = 768
    return mock_service


@pytest.fixture
def search_service(mock_event_repo, mock_memory_repo, mock_embedding_service):
    """Fixture pour créer une instance du MemorySearchService avec des mocks."""
    return MemorySearchService(mock_event_repo, mock_memory_repo, mock_embedding_service)


# Données de test
@pytest.fixture
def sample_memory():
    return Memory(
        id=str(uuid.uuid4()),
        memory_type="episodic",
        event_type="test_event",
        role_id=999,
        content={"text": "Contenu de test"},
        metadata={"tag": "test", "category": "recherche"},
        timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def sample_memories():
    return [
        Memory(
            id=str(uuid.uuid4()),
            memory_type="episodic",
            event_type="test_event",
            role_id=999,
            content={"text": f"Contenu de test {i}"},
            metadata={"tag": "test", "category": "recherche", "index": i},
            timestamp=datetime.now(tz=timezone.utc),
        )
        for i in range(3)
    ]


@pytest.fixture
def sample_event():
    return EventModel(
        id=uuid.uuid4(),  # Changed to UUID object
        content={"text": "Événement de test"},
        metadata={"tag": "test", "category": "événement"},
        timestamp=datetime.now(tz=timezone.utc),
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
    )


@pytest.fixture
def sample_events():
    return [
        EventModel(
            id=uuid.uuid4(),  # Changed to UUID object
            content={"text": f"Événement de test {i}"},
            metadata={"tag": "test", "category": "événement", "index": i},
            timestamp=datetime.now(tz=timezone.utc),
            embedding=[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i, 0.5 * i],
        )
        for i in range(3)
    ]


# Tests
@pytest.mark.asyncio
async def test_search_by_content(
    search_service, mock_embedding_service, sample_memories
):
    """Test de la recherche par contenu."""
    # Configuration du mock
    mock_embedding_service.generate_embedding.return_value = [
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
    ] * 154  # 770 elements (close to 768 for testing)

    # Appel de la méthode à tester avec espionnage (spy)
    with patch.object(
        search_service, "search_by_similarity", AsyncMock()
    ) as mock_search_similarity:
        mock_search_similarity.return_value = sample_memories

        # Exécution de la méthode à tester
        result = await search_service.search_by_content("Test query", 5)

        # Vérifications
        mock_search_similarity.assert_called_once_with("Test query", 5)
        assert result == sample_memories
        assert len(result) == 3


@pytest.mark.asyncio
async def test_search_by_metadata(
    search_service, mock_memory_repo, sample_memories
):
    """Test de la recherche par métadonnées."""
    # Configuration du mock
    mock_memory_repo.list_memories.return_value = sample_memories

    # Exécution de la méthode à tester
    result = await search_service.search_by_metadata(
        {"tag": "test", "category": "recherche"}, 10
    )

    # Vérifications
    # Vérifier que les paramètres corrects ont été passés, y compris les valeurs par défaut
    mock_memory_repo.list_memories.assert_called_once_with(
        metadata_filter={"tag": "test", "category": "recherche"},
        limit=10,
        skip=0,  # Valeur par défaut
        ts_start=None,  # Valeur par défaut
        ts_end=None,  # Valeur par défaut
    )
    assert result == sample_memories
    assert len(result) == 3


@pytest.mark.asyncio
async def test_search_by_similarity(
    search_service, mock_event_repo, mock_embedding_service, sample_events
):
    """Test de la recherche par similarité."""
    # Préparer des échantillons de Memory avec les champs requis
    sample_memories = []
    for i, event in enumerate(sample_events):
        memory = Memory(
            id=str(event.id),
            content=event.content,
            metadata=event.metadata,
            timestamp=event.timestamp,
            memory_type="episodic",  # Ajouter les champs requis
            event_type="user_input",
            role_id=1,  # Valeur arbitraire pour les tests
        )
        sample_memories.append(memory)

    # Configuration des mocks
    test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 154  # 770 elements (close to 768 for testing)
    mock_embedding_service.generate_embedding.return_value = test_embedding

    # Patcher la méthode search_by_vector pour retourner notre liste de mémoires
    with patch.object(
        search_service, "search_by_vector", AsyncMock()
    ) as mock_search_by_vector:
        mock_search_by_vector.return_value = sample_memories

        # Exécution de la méthode à tester
        result = await search_service.search_by_similarity("Test query", 5)

        # Vérifications
        mock_embedding_service.generate_embedding.assert_called_once_with("Test query")
        mock_search_by_vector.assert_called_once()

        # Vérifier que le résultat contient les mémoires attendues
        assert len(result) == len(sample_memories)
        assert result == sample_memories


@pytest.mark.anyio
async def test_search_by_vector(
    search_service: MemorySearchService, 
    mock_event_repo: AsyncMock, # Use the correct event repo mock fixture
    sample_events: List[EventModel]
):
    """Test de la recherche par vecteur."""
    # Création d'un faux embedding
    test_embedding = [0.1] * 768 # Correct dimension
    # Prepare mock events that EventModel.from_db_record can handle
    mock_embedding_list = [0.11] * 768
    mock_event_data = [
        {
            "id": uuid.uuid4(),
            "timestamp": datetime.now(timezone.utc),
            "content": json.dumps({"msg": "Vector Match 1"}),
            "metadata": json.dumps({"source": "vector_test"}),
            # Provide the embedding as a list, like the raw DB record would have
            # (after potential parsing if DB stores as string, but from_db_record handles this)
            # EventModel.from_db_record expects the raw format (string or list)
            # and calls _format_embedding_for_db internally if needed. 
            # Let's assume the raw record has it as a string for this mock.
            "embedding": str(mock_embedding_list), # Simulate DB string format
            "similarity_score": 0.05 # Added directly as it comes from the query
        }
    ]
    # This will now correctly call _parse_embedding_from_db internally
    mock_event_models = [EventModel.from_db_record(rec) for rec in mock_event_data]

    # Configure the mock for event_repository.search_vector
    # It should return a tuple: (list_of_events, total_count)
    mock_event_repo.search_vector.return_value = (mock_event_models, len(mock_event_models))

    # Exécution de la méthode à tester
    results, total_hits = await search_service.search_by_vector(
        vector=test_embedding, 
        limit=5, 
        offset=0
    )

    # Vérifications
    mock_event_repo.search_vector.assert_awaited_once()
    call_args = mock_event_repo.search_vector.call_args[1]
    assert call_args["vector"] == test_embedding
    assert call_args["limit"] == 5
    assert call_args["offset"] == 0
    assert call_args["metadata"] is None # Check default metadata is None
    assert call_args["ts_start"] is None
    assert call_args["ts_end"] is None

    assert len(results) == 1
    assert isinstance(results[0], Memory) # Check if conversion happened
    assert results[0].id == mock_event_models[0].id
    # Check similarity score propagation
    assert results[0].similarity_score == mock_event_models[0].similarity_score 
    assert total_hits == 1 # Check total hits count


@pytest.mark.anyio
async def test_search_hybrid(
    search_service: MemorySearchService,
    mock_event_repo: AsyncMock,
    mock_embedding_service: AsyncMock,
    mock_memory_repo: AsyncMock # Keep memory repo mock for potential other calls
):
    """Teste la recherche hybride nominale."""
    query = "test query"
    metadata_filter = {"tag": "test"}
    embedding = [0.1] * 768 # Correct dimension
    mock_embedding_service.generate_embedding.return_value = embedding
    
    # Configure mock_event_repo.search_vector to return some mock events
    mock_event1 = MagicMock(spec=EventModel)
    mock_event1.id = uuid.uuid4()
    mock_event1.timestamp = datetime.now(timezone.utc)
    # Configure search_vector to return a tuple (list_of_events, total_count)
    mock_event_repo.search_vector.return_value = ([mock_event1], 1)

    results, total_hits = await search_service.search_hybrid(
        query=query,
        metadata_filter=metadata_filter,
        limit=5,
        offset=0
    )

    mock_embedding_service.generate_embedding.assert_awaited_once_with(query)
    # Assert that event_repository.search_vector was called
    mock_event_repo.search_vector.assert_awaited_once()
    # Check the arguments passed to search_vector
    call_args = mock_event_repo.search_vector.call_args
    assert call_args[1]['vector'] == embedding
    assert call_args[1]['metadata'] == metadata_filter
    assert call_args[1]['limit'] == 5
    assert call_args[1]['offset'] == 0
    
    # Ensure memory_repo methods were NOT called by search_hybrid
    mock_memory_repo.search_by_embedding.assert_not_called()
    mock_memory_repo.list_memories.assert_not_called()

    assert len(results) == 1
    assert results[0] == mock_event1 # Check if the correct event model is returned
    assert total_hits == 1 


@pytest.mark.anyio
async def test_search_hybrid_with_empty_results(
    search_service: MemorySearchService, 
    mock_event_repo: AsyncMock, 
    mock_embedding_service: AsyncMock,
    mock_memory_repo: AsyncMock
):
    """Teste la recherche hybride retournant des résultats vides."""
    query = "no results query"
    embedding = [0.9] * 768 # Correct dimension
    mock_embedding_service.generate_embedding.return_value = embedding
    mock_event_repo.search_vector.return_value = ([], 0) # Simulate no results found (empty list, 0 count)

    results, total_hits = await search_service.search_hybrid(query=query)

    mock_embedding_service.generate_embedding.assert_awaited_once_with(query)
    mock_event_repo.search_vector.assert_awaited_once()
    # Ensure memory_repo methods were NOT called
    mock_memory_repo.search_by_embedding.assert_not_called()
    mock_memory_repo.list_memories.assert_not_called()
    
    assert results == []
    assert total_hits == 0

@pytest.mark.anyio
async def test_search_hybrid_with_none_query(
    search_service: MemorySearchService, 
    mock_event_repo: AsyncMock, 
    mock_embedding_service: AsyncMock,
    mock_memory_repo: AsyncMock
):
    """Teste la recherche hybride avec seulement un filtre metadata (pas de query textuelle)."""
    metadata_filter = {"tag": "metadata_only"}
    # Mock should still return a tuple, even if vector=None was passed
    mock_event_repo.search_vector.return_value = ([], 0)
    
    results, total_hits = await search_service.search_hybrid(query="", metadata_filter=metadata_filter)

    # generate_embedding should NOT be called if query is empty
    mock_embedding_service.generate_embedding.assert_not_called()
    # event_repository.search_vector should be called with vector=None
    mock_event_repo.search_vector.assert_awaited_once()
    call_args = mock_event_repo.search_vector.call_args
    assert call_args[1]['vector'] is None
    assert call_args[1]['metadata'] == metadata_filter

    # Ensure memory_repo methods were NOT called
    mock_memory_repo.search_by_embedding.assert_not_called()
    mock_memory_repo.list_memories.assert_not_called()
    
    assert results == []
    assert total_hits == 0

@pytest.mark.anyio
async def test_search_hybrid_with_none_metadata(
    search_service: MemorySearchService, 
    mock_event_repo: AsyncMock, 
    mock_embedding_service: AsyncMock,
    mock_memory_repo: AsyncMock
):
    """Teste la recherche hybride avec seulement une query textuelle (pas de filtre metadata)."""
    query = "vector only query"
    embedding = [0.3] * 768 # Correct dimension
    mock_embedding_service.generate_embedding.return_value = embedding
    mock_event_repo.search_vector.return_value = ([], 0) # Simulate no results found

    results, total_hits = await search_service.search_hybrid(query=query)

    mock_embedding_service.generate_embedding.assert_awaited_once_with(query)
    # event_repository.search_vector should be called with metadata=None
    mock_event_repo.search_vector.assert_awaited_once()
    call_args = mock_event_repo.search_vector.call_args
    assert call_args[1]['vector'] == embedding
    assert call_args[1]['metadata'] is None

    # Ensure memory_repo methods were NOT called
    mock_memory_repo.search_by_embedding.assert_not_called()
    mock_memory_repo.list_memories.assert_not_called()
    
    assert results == []
    assert total_hits == 0
