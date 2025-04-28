import pytest
from unittest.mock import AsyncMock, patch
import uuid
import datetime
from typing import Dict, List, Any, Optional, Union
from fastapi.testclient import TestClient

from main import app
from interfaces.repositories import MemoryRepositoryProtocol
from models.memory_models import Memory, MemoryCreate, MemoryUpdate

# Mock du repository basé sur le protocole
class MockMemoryRepository:
    """Implémentation fictive du MemoryRepositoryProtocol pour les tests."""
    
    def __init__(self):
        self.memories = {}
        self.add_mock = AsyncMock()
        self.get_by_id_mock = AsyncMock()
        self.update_mock = AsyncMock()
        self.delete_mock = AsyncMock()
        self.list_memories_mock = AsyncMock()
    
    async def add(self, memory: MemoryCreate) -> Memory:
        """Version mockée de la méthode add."""
        return await self.add_mock(memory)
    
    async def get_by_id(self, memory_id: Union[uuid.UUID, str]) -> Optional[Memory]:
        """Version mockée de la méthode get_by_id."""
        return await self.get_by_id_mock(memory_id)
    
    async def update(self, memory_id: Union[uuid.UUID, str], memory_update: MemoryUpdate) -> Optional[Memory]:
        """Version mockée de la méthode update."""
        return await self.update_mock(memory_id, memory_update)
    
    async def delete(self, memory_id: Union[uuid.UUID, str]) -> bool:
        """Version mockée de la méthode delete."""
        return await self.delete_mock(memory_id)
    
    async def list_memories(
        self, 
        limit: int = 10, 
        offset: int = 0,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Memory]:
        """Version mockée de la méthode list_memories."""
        return await self.list_memories_mock(limit, offset, metadata_filter)

# Fixture pour le client FastAPI avec un mock du repository
@pytest.fixture
def client_with_mock_repo():
    """Client avec un repository mocké injecté."""
    mock_repo = MockMemoryRepository()
    
    # Patch la fonction get_memory_repository pour qu'elle retourne notre mock
    with patch("dependencies.get_memory_repository", return_value=mock_repo):
        with TestClient(app) as test_client:
            yield test_client, mock_repo

# Tests utilisant le mock basé sur le protocole
def test_create_memory_with_protocol_mock(client_with_mock_repo):
    """Teste la création d'une mémoire en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    memory_data = {
        "content": "Test memory content",
        "metadata": {"type": "test", "priority": "high"}
    }
    expected_memory = Memory(
        id=uuid.uuid4(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content=memory_data["content"],
        metadata=memory_data["metadata"]
    )
    
    # Configurer le comportement du mock
    mock_repo.add_mock.return_value = expected_memory
    
    # 2. Action
    response = client.post("/v0/memories/", json=memory_data)
    
    # 3. Vérification
    assert mock_repo.add_mock.called
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["content"] == memory_data["content"]
    assert response_data["metadata"] == memory_data["metadata"]

def test_get_memory_success_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'une mémoire avec succès en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    expected_memory = Memory(
        id=test_memory_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content="Memory retrieved successfully",
        metadata={"retrieved": True}
    )
    
    # Configurer le comportement du mock
    mock_repo.get_by_id_mock.return_value = expected_memory
    
    # 2. Action
    response = client.get(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.get_by_id_mock.assert_called_once_with(test_memory_id)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_memory_id)
    assert response_data["content"] == expected_memory.content
    assert response_data["metadata"] == expected_memory.metadata

def test_get_memory_not_found_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'une mémoire inexistante en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    
    # Configurer le comportement du mock
    mock_repo.get_by_id_mock.return_value = None
    
    # 2. Action
    response = client.get(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.get_by_id_mock.assert_called_once_with(test_memory_id)
    assert response.status_code == 404
    assert "trouvée" in response.json()["detail"]  # Message en français

def test_update_memory_with_protocol_mock(client_with_mock_repo):
    """Teste la mise à jour d'une mémoire en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    memory_update = {
        "content": "Updated memory content",
        "metadata": {"updated": True, "timestamp": "2023-01-01"}
    }
    updated_memory = Memory(
        id=test_memory_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content=memory_update["content"],
        metadata=memory_update["metadata"]
    )
    
    # Configurer le comportement du mock
    mock_repo.update_mock.return_value = updated_memory
    
    # 2. Action
    response = client.put(f"/v0/memories/{test_memory_id}", json=memory_update)
    
    # 3. Vérification
    mock_repo.update_mock.assert_called_once()  # Vérifie l'appel sans vérifier les arguments exacts
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["content"] == memory_update["content"]
    assert response_data["metadata"] == memory_update["metadata"]

def test_delete_memory_with_protocol_mock(client_with_mock_repo):
    """Teste la suppression d'une mémoire en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    
    # Configurer le comportement du mock
    mock_repo.delete_mock.return_value = True
    
    # 2. Action
    response = client.delete(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.delete_mock.assert_called_once_with(test_memory_id)
    assert response.status_code == 204
    assert response.content == b''  # No content

def test_list_memories_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'une liste de mémoires en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo
    
    # 1. Préparation
    memory1 = Memory(
        id=uuid.uuid4(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content="Memory 1",
        metadata={"index": 1}
    )
    memory2 = Memory(
        id=uuid.uuid4(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content="Memory 2",
        metadata={"index": 2}
    )
    mock_memories = [memory1, memory2]
    
    # Configurer le comportement du mock
    mock_repo.list_memories_mock.return_value = mock_memories
    
    # 2. Action
    response = client.get("/v0/memories/?limit=10&offset=0&memory_type=test")
    
    # 3. Vérification
    # Vérification de l'appel avec metadata_filter contenant memory_type: test
    # Note: on ne peut pas vérifier exactement les arguments car ils sont transformés
    assert mock_repo.list_memories_mock.called
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["content"] == "Memory 1"
    assert response_data[1]["content"] == "Memory 2" 