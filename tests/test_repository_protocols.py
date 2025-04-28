import pytest
from unittest.mock import AsyncMock, patch
import uuid
import datetime
from typing import Dict, List, Any, Optional
from fastapi.testclient import TestClient
from pydantic import BaseModel

from main import app
from interfaces.repositories import EventRepositoryProtocol
from models.event_models import EventModel, EventCreate

# Mock du repository basé sur le protocole
class MockEventRepository:
    """Implémentation fictive du EventRepositoryProtocol pour les tests."""
    
    def __init__(self):
        self.events = {}
        self.add_mock = AsyncMock()
        self.get_by_id_mock = AsyncMock()
        self.update_metadata_mock = AsyncMock()
        self.delete_mock = AsyncMock()
        self.search_by_embedding_mock = AsyncMock()
        self.filter_by_metadata_mock = AsyncMock()
    
    async def add(self, event: EventCreate) -> EventModel:
        """Version mockée de la méthode add."""
        return await self.add_mock(event)
    
    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Version mockée de la méthode get_by_id."""
        return await self.get_by_id_mock(event_id)
    
    async def update_metadata(self, event_id: uuid.UUID, metadata: Dict[str, Any]) -> Optional[EventModel]:
        """Version mockée de la méthode update_metadata."""
        return await self.update_metadata_mock(event_id, metadata)
    
    async def delete(self, event_id: uuid.UUID) -> bool:
        """Version mockée de la méthode delete."""
        return await self.delete_mock(event_id)
    
    async def search_by_embedding(self, embedding: List[float], limit: int = 5) -> List[EventModel]:
        """Version mockée de la méthode search_by_embedding."""
        return await self.search_by_embedding_mock(embedding, limit)
    
    async def filter_by_metadata(self, metadata_filter: Dict[str, Any], limit: int = 10, offset: int = 0) -> List[EventModel]:
        """Version mockée de la méthode filter_by_metadata."""
        return await self.filter_by_metadata_mock(metadata_filter, limit, offset)

# Fixture pour le client FastAPI avec un mock du repository
@pytest.fixture
def client_with_mock_repo():
    """Client avec un repository mocké injecté."""
    mock_repo = MockEventRepository()
    
    # Patch la fonction get_event_repository pour qu'elle retourne notre mock
    with patch("dependencies.get_event_repository", return_value=mock_repo):
        with TestClient(app) as test_client:
            yield test_client, mock_repo

# Tests utilisant le mock basé sur le protocole
def test_get_event_success_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'un événement avec succès en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    expected_event = EventModel(
        id=test_event_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content={"message": "Test event"},
        metadata={"type": "test"},
        embedding=[0.1, 0.2, 0.3]
    )
    
    # Configurer le comportement du mock
    mock_repo.get_by_id_mock.return_value = expected_event
    
    # 2. Action
    response = client.get(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.get_by_id_mock.assert_called_once_with(test_event_id)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_event_id)
    assert response_data["content"] == expected_event.content
    assert response_data["metadata"] == expected_event.metadata

def test_get_event_not_found_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'un événement inexistant en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    
    # Configurer le comportement du mock
    mock_repo.get_by_id_mock.return_value = None
    
    # 2. Action
    response = client.get(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.get_by_id_mock.assert_called_once_with(test_event_id)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Événement avec ID {test_event_id} non trouvé"}

def test_create_event_with_protocol_mock(client_with_mock_repo):
    """Teste la création d'un événement en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    event_data = {
        "content": {"message": "New test event"},
        "metadata": {"type": "creation_test"}
    }
    expected_event = EventModel(
        id=uuid.uuid4(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content=event_data["content"],
        metadata=event_data["metadata"],
        embedding=None
    )
    
    # Configurer le comportement du mock
    mock_repo.add_mock.return_value = expected_event
    
    # 2. Action
    response = client.post("/v1/events/", json=event_data)
    
    # 3. Vérification
    assert mock_repo.add_mock.called
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["content"] == event_data["content"]
    assert response_data["metadata"] == event_data["metadata"]

def test_update_event_metadata_with_protocol_mock(client_with_mock_repo):
    """Teste la mise à jour des métadonnées d'un événement en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    metadata_update = {"updated": True, "timestamp": "2023-01-01"}
    updated_event = EventModel(
        id=test_event_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content={"message": "Original content"},
        metadata={"original": "value", **metadata_update},
        embedding=None
    )
    
    # Configurer le comportement du mock
    mock_repo.update_metadata_mock.return_value = updated_event
    
    # 2. Action
    response = client.patch(f"/v1/events/{test_event_id}/metadata", json=metadata_update)
    
    # 3. Vérification
    mock_repo.update_metadata_mock.assert_called_once_with(test_event_id, metadata_update)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["metadata"]["updated"] == metadata_update["updated"]
    assert response_data["metadata"]["timestamp"] == metadata_update["timestamp"]

def test_delete_event_with_protocol_mock(client_with_mock_repo):
    """Teste la suppression d'un événement en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    
    # Configurer le comportement du mock
    mock_repo.delete_mock.return_value = True
    
    # 2. Action
    response = client.delete(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.delete_mock.assert_called_once_with(test_event_id)
    assert response.status_code == 204
    assert response.content == b''  # No content 