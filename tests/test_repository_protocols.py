import pytest
from unittest.mock import AsyncMock, patch
import uuid
import datetime
from typing import Dict, List, Any, Optional, Union
from fastapi.testclient import TestClient
from fastapi import APIRouter, Depends, HTTPException, status
import json

from main import app
from interfaces.repositories import EventRepositoryProtocol
from models.event_models import EventModel, EventCreate

# Créer un router pour les endpoints de test
test_router = APIRouter(prefix="/test", tags=["test"])

# Fonction pour récupérer le repository mocké


def get_test_event_repo() -> EventRepositoryProtocol:
    """Retourne le mock du repository d'événements pour les tests."""
    return app.state.mock_event_repo


@test_router.post("/events/create", response_model=EventModel)
async def endpoint_create_event(
    event: EventCreate,
    event_repo: EventRepositoryProtocol = Depends(get_test_event_repo),
):
    """
    Endpoint de test pour créer un événement.
    Simule un endpoint réel utilisant le protocole de repository pour les tests.
    """
    return await event_repo.add(event)


@test_router.get("/events/{event_id}", response_model=EventModel)
async def endpoint_get_event(
    event_id: uuid.UUID,
    event_repo: EventRepositoryProtocol = Depends(get_test_event_repo),
):
    """
    Endpoint de test pour récupérer un événement par ID.
    Simule un endpoint réel utilisant le protocole de repository pour les tests.
    """
    event = await event_repo.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@test_router.get("/events", response_model=List[EventModel])
async def endpoint_filter_events(
    metadata_filter: Optional[str] = None,
    event_repo: EventRepositoryProtocol = Depends(get_test_event_repo),
):
    """
    Endpoint de test pour filtrer les événements par metadata.
    Simule un endpoint réel utilisant le protocole de repository pour les tests.
    """
    # Parse the metadata_filter if it's a string
    filter_dict = {}
    if metadata_filter:
        try:
            filter_dict = json.loads(metadata_filter)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata_filter JSON")

    return await event_repo.filter_by_metadata(filter_dict)


@test_router.patch("/events/{event_id}/metadata", response_model=EventModel)
async def endpoint_update_event_metadata(
    event_id: uuid.UUID,
    metadata: Dict[str, Any],
    event_repo: EventRepositoryProtocol = Depends(get_test_event_repo),
):
    """
    Endpoint de test pour mettre à jour les métadonnées d'un événement.
    Simule un endpoint réel utilisant le protocole de repository pour les tests.
    """
    return await event_repo.update_metadata(event_id, metadata)


@test_router.delete("/events/{event_id}", status_code=204)
async def endpoint_delete_event(
    event_id: uuid.UUID,
    event_repo: EventRepositoryProtocol = Depends(get_test_event_repo),
):
    """
    Endpoint de test pour supprimer un événement par ID.
    Simule un endpoint réel utilisant le protocole de repository pour les tests.
    """
    success = await event_repo.delete(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return None


class MockEventRepository:
    """Implémentation fictive du EventRepositoryProtocol pour les tests.

    Phase 3.3: Removed search_by_embedding as it's no longer in EventRepositoryProtocol.
    """

    def __init__(self):
        self.events = {}
        self.add = AsyncMock()
        self.get_by_id = AsyncMock()
        self.update_metadata = AsyncMock()
        self.delete = AsyncMock()
        self.filter_by_metadata = AsyncMock()


# Fixture pour le client FastAPI avec un mock du repository


@pytest.fixture
def client_with_mock_repo():
    """Client avec un repository mocké injecté."""
    mock_repo = MockEventRepository()

    # Ajouter le router de test à l'application
    app.include_router(test_router)

    # Stocker le mock dans l'état de l'app
    app.state.mock_event_repo = mock_repo

    with TestClient(app) as test_client:
        yield test_client, mock_repo


def test_create_event_with_protocol_mock(client_with_mock_repo):
    """Teste la création d'un événement en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    event_data = {
        "content": {"text": "Test event content"},
        "metadata": {"type": "test", "priority": "high"},
    }
    expected_event = EventModel(
        id=uuid.uuid4(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content={"text": "Test event content"},
        metadata={"type": "test", "priority": "high"},
        embedding=None,
    )

    # Configurer le comportement du mock
    mock_repo.add.return_value = expected_event

    # 2. Action
    response = client.post("/test/events/create", json=event_data)

    # 3. Vérification (Assert)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["content"] == event_data["content"]
    assert response_data["metadata"] == event_data["metadata"]

    # Vérifier que le mock a été appelé correctement
    # Le premier argument du premier appel au mock
    call_args = mock_repo.add.call_args[0][0]

    # Vérifier que les données d'événement sont correctes
    assert call_args.content == event_data["content"]
    assert call_args.metadata == event_data["metadata"]


def test_get_event_success_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'un événement avec succès en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    test_event_id = uuid.uuid4()
    expected_event = EventModel(
        id=test_event_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content={"text": "Event retrieved successfully"},
        metadata={"retrieved": True},
        embedding=None,
    )

    # Configurer le comportement du mock
    mock_repo.get_by_id.return_value = expected_event

    # 2. Action
    response = client.get(f"/test/events/{test_event_id}")

    # 3. Vérification (Assert)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_event_id)
    assert response_data["content"] == expected_event.content

    # Vérifier que le mock a été appelé correctement
    mock_repo.get_by_id.assert_called_once_with(test_event_id)


def test_get_event_not_found_with_protocol_mock(client_with_mock_repo):
    """Teste la récupération d'un événement inexistant en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    test_event_id = uuid.uuid4()

    # Configurer le comportement du mock pour simuler un événement non trouvé
    mock_repo.get_by_id.return_value = None

    # 2. Action
    response = client.get(f"/test/events/{test_event_id}")

    # 3. Vérification (Assert)
    assert response.status_code == 404

    # Vérifier que le mock a été appelé correctement
    mock_repo.get_by_id.assert_called_once_with(test_event_id)


def test_filter_events_with_protocol_mock(client_with_mock_repo):
    """Teste le filtrage d'événements par metadata en utilisant un mock basé sur le protocole."""
    client, mock_repo = client_with_mock_repo

    # 1. Préparation
    metadata_filter = {"type": "test"}
    expected_events = [
        EventModel(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            content={"text": f"Event {i}"},
            metadata={"type": "test", "index": i},
            embedding=None,
        )
        for i in range(3)
    ]

    # Configurer le comportement du mock
    mock_repo.filter_by_metadata.return_value = expected_events

    # 2. Action
    response = client.get(
        "/test/events", params={"metadata_filter": json.dumps(metadata_filter)}
    )

    # 3. Vérification (Assert)
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == len(expected_events)

    # Vérifier que le mock a été appelé correctement
    mock_repo.filter_by_metadata.assert_called_once_with(metadata_filter)


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
        embedding=None,
    )

    # Configurer le comportement du mock
    mock_repo.update_metadata.return_value = updated_event

    # 2. Action
    response = client.patch(
        f"/test/events/{test_event_id}/metadata", json=metadata_update
    )

    # 3. Vérification
    mock_repo.update_metadata.assert_called_once_with(test_event_id, metadata_update)
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
    mock_repo.delete.return_value = True

    # 2. Action
    response = client.delete(f"/test/events/{test_event_id}")

    # 3. Vérification
    mock_repo.delete.assert_called_once_with(test_event_id)
    assert response.status_code == 204
    assert response.content == b""  # No content
