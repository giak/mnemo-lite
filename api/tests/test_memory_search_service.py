"""
Tests pour le service de recherche de mémoires.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from services.memory_search_service import MemorySearchService
from models.memory_models import Memory
from models.event_models import EventModel

# Fixtures
@pytest.fixture
def mock_event_repository():
    """Fixture pour créer un mock du repository d'événements."""
    mock_repo = AsyncMock()
    return mock_repo

@pytest.fixture
def mock_memory_repository():
    """Fixture pour créer un mock du repository de mémoires."""
    mock_repo = AsyncMock()
    return mock_repo

@pytest.fixture
def mock_embedding_service():
    """Fixture pour créer un mock du service d'embeddings."""
    mock_service = AsyncMock()
    # Configuration du mock pour renvoyer un embedding de test
    mock_service.generate_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
    return mock_service

@pytest.fixture
def memory_search_service(mock_event_repository, mock_memory_repository, mock_embedding_service):
    """Fixture pour créer une instance du service de recherche de mémoires."""
    return MemorySearchService(
        event_repository=mock_event_repository,
        memory_repository=mock_memory_repository,
        embedding_service=mock_embedding_service
    )

# Tests
@pytest.mark.asyncio
async def test_search_by_content(memory_search_service, mock_embedding_service):
    """Test de la recherche par contenu."""
    # Configuration du mock
    mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    # Appel de la méthode à tester avec espionnage (spy)
    with patch.object(memory_search_service, 'search_by_similarity', AsyncMock()) as mock_search_similarity:
        mock_memories = [
            Memory(id="1", content={"text": "Test 1"}, metadata={"tag": "test"}, timestamp=datetime.now(tz=timezone.utc))
        ]
        mock_search_similarity.return_value = mock_memories
        
        # Exécution de la méthode à tester
        result = await memory_search_service.search_by_content("Test query", 5)
        
        # Vérifications
        mock_search_similarity.assert_called_once_with("Test query", 5)
        assert result == mock_memories

@pytest.mark.asyncio
async def test_search_by_metadata(memory_search_service, mock_memory_repository):
    """Test de la recherche par métadonnées."""
    # Configuration du mock
    mock_memories = [
        Memory(id="1", content={"text": "Test 1"}, metadata={"tag": "test"}, timestamp=datetime.now(tz=timezone.utc))
    ]
    mock_memory_repository.list_memories.return_value = mock_memories
    
    # Exécution de la méthode à tester
    result = await memory_search_service.search_by_metadata({"tag": "test"}, 10)
    
    # Vérifications
    mock_memory_repository.list_memories.assert_called_once_with(
        metadata_filter={"tag": "test"},
        limit=10
    )
    assert result == mock_memories

@pytest.mark.asyncio
async def test_search_by_similarity(memory_search_service, mock_event_repository, mock_embedding_service):
    """Test de la recherche par similarité."""
    # Configuration des mocks
    test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    mock_embedding_service.generate_embedding.return_value = test_embedding
    
    # Création d'événements de test
    test_events = [
        EventModel(
            id="1",
            content={"text": "Test event 1"},
            metadata={"tag": "test"},
            timestamp=datetime.now(tz=timezone.utc),
            embedding=None
        )
    ]
    mock_event_repository.search_by_embedding.return_value = test_events
    
    # Exécution de la méthode à tester
    result = await memory_search_service.search_by_similarity("Test query", 5)
    
    # Vérifications
    mock_embedding_service.generate_embedding.assert_called_once_with("Test query")
    mock_event_repository.search_by_embedding.assert_called_once_with(
        embedding=test_embedding,
        limit=5
    )
    
    # Vérification que les résultats ont été convertis en mémoires
    assert len(result) == 1
    assert isinstance(result[0], Memory)
    assert result[0].id == "1"
    assert result[0].content == {"text": "Test event 1"}
    assert result[0].metadata == {"tag": "test"} 