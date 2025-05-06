import pytest
from unittest.mock import AsyncMock, patch
import uuid
from uuid import UUID
import datetime
from typing import Dict, List, Any, Optional, Union
from fastapi.testclient import TestClient
from fastapi import APIRouter, Depends, HTTPException, status
import json

from main import app
from interfaces.repositories import MemoryRepositoryProtocol
from models.memory_models import Memory, MemoryCreate, MemoryUpdate

# Créer un router pour les endpoints de test
test_router = APIRouter(prefix="/test", tags=["test"])

# Fonction pour récupérer le repository mocké


def get_test_memory_repo() -> MemoryRepositoryProtocol:
    """Retourne le repository mocké pour les tests."""
    return app.state.mock_memory_repo


# Définir les endpoints de test - Préfixer avec 'endpoint_' pour éviter
# que pytest ne les collecte comme des tests


@test_router.post("/memories/create", response_model=Memory)
async def endpoint_create_memory(
    memory: MemoryCreate,
    memory_repo: MemoryRepositoryProtocol = Depends(get_test_memory_repo),
):
    """Endpoint de test pour créer une mémoire."""
    return await memory_repo.add(memory)


@test_router.get("/memories/{memory_id}", response_model=Memory)
async def endpoint_get_memory(
    memory_id: uuid.UUID,
    memory_repo: MemoryRepositoryProtocol = Depends(get_test_memory_repo),
):
    """Endpoint de test pour récupérer une mémoire par ID."""
    memory = await memory_repo.get_by_id(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@test_router.put("/memories/{memory_id}", response_model=Memory)
async def endpoint_update_memory(
    memory_id: uuid.UUID,
    memory_update: MemoryUpdate,
    memory_repo: MemoryRepositoryProtocol = Depends(get_test_memory_repo),
):
    """Endpoint de test pour mettre à jour une mémoire."""
    return await memory_repo.update(memory_id, memory_update)


@test_router.delete("/memories/{memory_id}", response_model=bool)
async def endpoint_delete_memory(
    memory_id: uuid.UUID,
    memory_repo: MemoryRepositoryProtocol = Depends(get_test_memory_repo),
):
    """Endpoint de test pour supprimer une mémoire."""
    return await memory_repo.delete(memory_id)


@test_router.get("/memories", response_model=List[Memory])
async def endpoint_list_memories(
    limit: int = 10,
    offset: int = 0,
    memory_type: Optional[str] = None,
    event_type: Optional[str] = None,
    role_id: Optional[int] = None,
    session_id: Optional[str] = None,
    metadata_filter: Optional[str] = None,
    ts_start: Optional[Any] = None,
    ts_end: Optional[Any] = None,
    skip: Optional[int] = None,
    memory_repo: MemoryRepositoryProtocol = Depends(get_test_memory_repo),
):
    """Endpoint de test pour récupérer une liste de mémoires."""
    # Parse the metadata_filter if it's a string
    filter_dict = None
    if metadata_filter:
        try:
            filter_dict = json.loads(metadata_filter)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata_filter JSON")

    memories, total = await memory_repo.list_memories(
        limit=limit,
        offset=offset,
        memory_type=memory_type,
        event_type=event_type,
        role_id=role_id,
        session_id=session_id,
        metadata_filter=filter_dict,
        ts_start=ts_start,
        ts_end=ts_end,
        skip=skip,
    )
    return memories


# Mock du repository basé sur le protocole


class MockMemoryRepository:
    """Implémentation fictive du MemoryRepositoryProtocol pour les tests."""

    def __init__(self):
        self.memories = {}
        # Créer les mocks correctement comme attributs d'instance
        self.add = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update = AsyncMock()
        self.delete = AsyncMock()
        self.list_memories = AsyncMock()

    # Les méthodes ci-dessous ne sont plus nécessaires car les mocks sont directement
    # utilisés comme attributs de la classe


# Fixture pour le client FastAPI avec un mock du repository


@pytest.fixture
def client_with_mock_repo():
    """Client avec un repository mocké injecté."""
    mock_repo = MockMemoryRepository()

    # Ajout plus simple du router - pas besoin de vérifier s'il existe déjà
    # pytest crée une nouvelle instance d'app pour chaque test donc l'ajout
    # multiple n'est pas un problème
    app.include_router(test_router)

    # Stocker le mock dans l'état de l'app
    app.state.mock_memory_repo = mock_repo

    with TestClient(app) as test_client:
        yield test_client, mock_repo


# Définir l'ancien test comme un test skip pour éviter toute confusion


@pytest.mark.skip(reason="Remplacé par test_create_memory_with_protocol_mock")
async def test_list_memories():
    """Test à ignorer."""
    pass


# Tests utilisant le mock basé sur le protocole


def test_create_memory_with_protocol_mock(client_with_mock_repo):
    """Teste la création d'une mémoire en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    memory_data = {
        "memory_type": "episodic",
        "event_type": "conversation",
        "role_id": 1,
        "content": {"text": "Test memory content"},
        "metadata": {"type": "test", "priority": "high"},
    }
    expected_memory = Memory(
        id=uuid.uuid4(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        memory_type="episodic",
        event_type="conversation",
        role_id=1,
        content={"text": "Test memory content"},
        metadata={"type": "test", "priority": "high"},
    )

    # Configurer le comportement du mock
    mock_repo.add.return_value = expected_memory

    # 2. Action
    response = client.post("/test/memories/create", json=memory_data)

    # 3. Vérification
    assert response.status_code == 200
    response_data = response.json()
    assert UUID(response_data["id"])
    mock_repo.add.assert_called_once()


def test_get_memory_success_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'une mémoire avec succès en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    test_memory_id = uuid.uuid4()
    expected_memory = Memory(
        id=test_memory_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        memory_type="semantic",
        event_type="note",
        role_id=2,
        content={"text": "Memory retrieved successfully"},
        metadata={"retrieved": True},
    )

    # Configurer le comportement du mock
    mock_repo.get_by_id.return_value = expected_memory

    # 2. Action
    response = client.get(f"/test/memories/{test_memory_id}")

    # 3. Vérification
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_memory_id)
    mock_repo.get_by_id.assert_called_once()


def test_get_memory_not_found_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'une mémoire inexistante en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    test_memory_id = uuid.uuid4()

    # Configurer le comportement du mock
    mock_repo.get_by_id.return_value = None

    # 2. Action
    response = client.get(f"/test/memories/{test_memory_id}")

    # 3. Vérification
    assert response.status_code == 404
    mock_repo.get_by_id.assert_called_once()


def test_update_memory_with_protocol_mock(client_with_mock_repo):
    """Teste la mise à jour d'une mémoire en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    test_memory_id = uuid.uuid4()
    memory_update = {
        "content": {"text": "Updated memory content"},
        "metadata": {"updated": True},
    }
    updated_memory = Memory(
        id=test_memory_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        memory_type="semantic",
        event_type="note",
        role_id=2,
        content={"text": "Updated memory content"},
        metadata={"updated": True},
    )

    # Configurer le comportement du mock
    mock_repo.update.return_value = updated_memory

    # 2. Action
    response = client.put(f"/test/memories/{test_memory_id}", json=memory_update)

    # 3. Vérification
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_memory_id)
    mock_repo.update.assert_called_once()


def test_delete_memory_with_protocol_mock(client_with_mock_repo):
    """Teste la suppression d'une mémoire en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    test_memory_id = uuid.uuid4()

    # Configurer le comportement du mock
    mock_repo.delete.return_value = True

    # 2. Action
    response = client.delete(f"/test/memories/{test_memory_id}")

    # 3. Vérification
    assert response.status_code == 200
    mock_repo.delete.assert_called_once()


def test_list_memories_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération de la liste des mémoires en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    limit = 5
    offset = 0
    metadata_filter = {"type": "test"}

    expected_memories = [
        Memory(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            memory_type="semantic",
            event_type="note",
            role_id=1,
            content={"text": f"Memory {i}"},
            metadata={"type": "test", "index": i},
        )
        for i in range(limit)
    ]

    # Configurer le comportement du mock pour retourner un tuple (memories,
    # total)
    mock_repo.list_memories.return_value = (expected_memories, len(expected_memories))

    # 2. Action
    response = client.get(
        f"/test/memories?limit={limit}&offset={offset}&metadata_filter={
            json.dumps(metadata_filter)}"
    )

    # 3. Vérification
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == limit

    # Vérifier que le mock a été appelé correctement avec tous les paramètres
    # nécessaires
    mock_repo.list_memories.assert_called_once_with(
        limit=limit,
        offset=offset,
        memory_type=None,
        event_type=None,
        role_id=None,
        session_id=None,
        metadata_filter=metadata_filter,
        ts_start=None,
        ts_end=None,
        skip=None,
    )
