import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
import datetime
import json

# Import de l'application FastAPI
from main import app 
# Import des dépendances et modèles
from db.repositories.event_repository import EventRepository, EventModel, EventCreate
from dependencies import get_event_repository

# --- Fixtures ---

@pytest.fixture
def client():
    """Crée un TestClient FastAPI standard."""
    with TestClient(app) as test_client:
        yield test_client

# Fixture pour mocker directement le repository
@pytest.fixture
def mock_event_repo():
    """Crée un mock pour EventRepositoryProtocol."""
    mock_repo = AsyncMock()
    
    # Configuration automatique des méthodes les plus courantes
    mock_repo.get_by_id.return_value = None  # Par défaut, aucun événement trouvé
    mock_repo.add.return_value = None  # Configurer dans chaque test
    mock_repo.update_metadata.return_value = None  # Configurer dans chaque test
    mock_repo.delete.return_value = True  # Par défaut, suppression réussie
    mock_repo.filter_by_metadata.return_value = []  # Par défaut, aucun résultat
    mock_repo.search_by_embedding.return_value = []  # Par défaut, aucun résultat
    
    return mock_repo

@pytest.fixture
def app_with_mock_repo(mock_event_repo):
    """Remplace le repository dans l'app par le mock."""
    
    # Remplacer la dépendance dans l'application
    app.dependency_overrides[get_event_repository] = lambda: mock_event_repo
    
    yield app
    
    # Nettoyer après le test
    app.dependency_overrides.clear()

@pytest.fixture
def client_with_mock_repo(app_with_mock_repo):
    """Client de test avec repository mocké."""
    with TestClient(app_with_mock_repo) as test_client:
        yield test_client, app_with_mock_repo

# --- Tests des routes utilisant les fixtures avec mocks ---

def test_get_event_success_with_mock(client_with_mock_repo):
    """Teste la récupération réussie d'un événement en utilisant un mock repository."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    expected_content = {"data": "test content"}
    expected_metadata = {"test": True}
    expected_embedding = [0.1, 0.2, 0.3]
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Configurer le mock pour retourner un événement
    mock_event = EventModel(
        id=test_event_id,
        timestamp=expected_timestamp,
        content=expected_content,
        metadata=expected_metadata,
        embedding=expected_embedding
    )
    mock_repo.get_by_id.return_value = mock_event
    
    # 2. Action
    response = client.get(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.get_by_id.assert_called_once_with(test_event_id)
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_event_id)
    assert response_data["content"] == expected_content
    assert response_data["metadata"] == expected_metadata
    assert response_data["embedding"] == expected_embedding

def test_get_event_not_found_with_mock(client_with_mock_repo):
    """Teste la récupération d'un événement inexistant en utilisant un mock repository."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = None
    
    # 2. Action
    response = client.get(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.get_by_id.assert_called_once_with(test_event_id)
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_create_event_success(client_with_mock_repo):
    """Teste la création réussie d'un événement."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    test_content = {"message": "Test event"}
    test_metadata = {"source": "test", "importance": "high"}
    test_embedding = [0.1, 0.2, 0.3, 0.4]
    test_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Préparer l'événement à créer
    event_data = {
        "content": test_content,
        "metadata": test_metadata,
        "embedding": test_embedding,
        "timestamp": test_timestamp.isoformat()
    }
    
    # Configurer la réponse du mock
    mock_event = EventModel(
        id=test_event_id,
        timestamp=test_timestamp,
        content=test_content,
        metadata=test_metadata,
        embedding=test_embedding
    )
    mock_repo.add.return_value = mock_event
    
    # 2. Action
    response = client.post("/v1/events/", json=event_data)
    
    # 3. Vérification
    assert mock_repo.add.called
    
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["id"] == str(test_event_id)
    assert response_data["content"] == test_content
    assert response_data["metadata"] == test_metadata
    assert response_data["embedding"] == test_embedding

def test_update_event_metadata_success(client_with_mock_repo):
    """Teste la mise à jour réussie des métadonnées d'un événement."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    original_content = {"message": "Original content"}
    original_metadata = {"source": "test", "status": "pending"}
    metadata_update = {"status": "completed", "updated_at": "2023-06-15T12:00:00Z"}
    
    # Métadonnées attendues après la mise à jour (fusion des deux)
    expected_metadata = {**original_metadata, **metadata_update}
    
    # Configurer la réponse du mock
    mock_event = EventModel(
        id=test_event_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        content=original_content,
        metadata=expected_metadata,
        embedding=None
    )
    mock_repo.update_metadata.return_value = mock_event
    
    # 2. Action
    response = client.patch(f"/v1/events/{test_event_id}/metadata", json=metadata_update)
    
    # 3. Vérification
    mock_repo.update_metadata.assert_called_once_with(test_event_id, metadata_update)
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_event_id)
    assert response_data["content"] == original_content
    assert response_data["metadata"] == expected_metadata

def test_update_event_metadata_not_found(client_with_mock_repo):
    """Teste la mise à jour des métadonnées d'un événement inexistant."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    metadata_update = {"status": "completed"}
    
    # Configurer le mock pour simuler un événement non trouvé
    mock_repo.update_metadata.return_value = None
    
    # 2. Action
    response = client.patch(f"/v1/events/{test_event_id}/metadata", json=metadata_update)
    
    # 3. Vérification
    mock_repo.update_metadata.assert_called_once_with(test_event_id, metadata_update)
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_delete_event_success(client_with_mock_repo):
    """Teste la suppression réussie d'un événement."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    mock_repo.delete.return_value = True
    
    # 2. Action
    response = client.delete(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.delete.assert_called_once_with(test_event_id)
    
    assert response.status_code == 204
    assert response.content == b''  # Pas de contenu pour une réponse 204

def test_delete_event_not_found(client_with_mock_repo):
    """Teste la suppression d'un événement inexistant."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_event_id = uuid.uuid4()
    mock_repo.delete.return_value = False
    
    # 2. Action
    response = client.delete(f"/v1/events/{test_event_id}")
    
    # 3. Vérification
    mock_repo.delete.assert_called_once_with(test_event_id)
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_filter_events_by_metadata(client_with_mock_repo):
    """Teste le filtrage des événements par métadonnées."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_filter = {"source": "test", "status": "completed"}
    test_limit = 5
    test_offset = 2
    
    # Créer quelques événements fictifs pour la réponse
    events = [
        EventModel(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            content={"message": f"Test event {i}"},
            metadata={"source": "test", "status": "completed", "index": i},
            embedding=None
        )
        for i in range(3)
    ]
    
    mock_repo.filter_by_metadata.return_value = events
    
    # 2. Action - Utiliser POST avec le body JSON et les paramètres dans l'URL
    response = client.post(
        f"/v1/events/filter/metadata?limit={test_limit}&offset={test_offset}",
        json=test_filter
    )
    
    # 3. Vérification
    mock_repo.filter_by_metadata.assert_called_once_with(test_filter, test_limit, test_offset)
    
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == len(events)
    
    # Vérifier que les IDs correspondent
    response_ids = [item["id"] for item in response_data]
    expected_ids = [str(event.id) for event in events]
    assert set(response_ids) == set(expected_ids)

def test_search_events_by_embedding(client_with_mock_repo):
    """Teste la recherche d'événements par embedding."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_event_repository]()
    
    # 1. Préparation
    test_embedding = [0.1, 0.2, 0.3, 0.4]
    test_limit = 3
    
    # Créer quelques événements fictifs pour la réponse
    events = [
        EventModel(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            content={"message": f"Similar event {i}"},
            metadata={"similarity_index": i},
            embedding=test_embedding,
            similarity_score=0.9 - (i * 0.1)  # Scores décroissants
        )
        for i in range(2)
    ]
    
    mock_repo.search_by_embedding.return_value = events
    
    # 2. Action - Utiliser POST avec le body JSON
    response = client.post(
        f"/v1/events/search/embedding?limit={test_limit}",
        json=test_embedding
    )
    
    # 3. Vérification
    mock_repo.search_by_embedding.assert_called_once_with(test_embedding, test_limit)
    
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == len(events)
    
    # Vérifier que les IDs correspondent
    response_ids = [item["id"] for item in response_data]
    expected_ids = [str(event.id) for event in events]
    assert set(response_ids) == set(expected_ids)

# --- Tests utilisant patch (maintenus pour référence mais skippés) ---

@pytest.mark.skip(reason="Problème persistant de mocking/patch avec TestClient sur cette route")
def test_get_event_success_with_patch(client: TestClient):
    """Teste la récupération réussie en patchant EventRepository.get_by_id."""
    # 1. Préparation (Arrange)
    test_event_id = uuid.uuid4()
    expected_content = {"data": "patched success"}
    expected_metadata = {"patched": True}
    expected_embedding = [0.1, 0.2]
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Modèle attendu qui sera retourné par le mock patché
    mock_event_model = EventModel(
        id=test_event_id,
        timestamp=expected_timestamp,
        content=expected_content,
        metadata=expected_metadata,
        embedding=expected_embedding
    )

    # 2. Action (Act) - Utilise patch.object pour remplacer get_by_id
    #    'db.repositories.event_repository.EventRepository' -> chemin vers la CLASSE (sans api.)
    with patch('db.repositories.event_repository.EventRepository.get_by_id', new_callable=AsyncMock) as mock_get_by_id:
        # Configurer la valeur de retour du mock créé par patch
        mock_get_by_id.return_value = mock_event_model
        
        # Exécuter la requête API
        response = client.get(f"/v1/events/{test_event_id}")

        # 3. Vérification (Assert)
        # Vérifier que le mock créé par patch a été appelé
        mock_get_by_id.assert_called_once_with(event_id=test_event_id) 
        
        # Vérifier la réponse HTTP
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == str(test_event_id)
        assert response_data["content"] == expected_content
        assert response_data["metadata"] == expected_metadata
        assert response_data["embedding"] == expected_embedding
        assert datetime.datetime.fromisoformat(response_data["timestamp"].replace("Z", "+00:00")) == expected_timestamp

@pytest.mark.skip(reason="Problème persistant de mocking/patch avec TestClient sur cette route")
def test_get_event_not_found_with_patch(client: TestClient):
    """Teste le cas 404 en patchant EventRepository.get_by_id."""
    # 1. Préparation (Arrange)
    test_event_id = uuid.uuid4()

    # 2. Action (Act) - Utilise patch.object
    with patch('db.repositories.event_repository.EventRepository.get_by_id', new_callable=AsyncMock) as mock_get_by_id:
        # Configurer le mock pour retourner None
        mock_get_by_id.return_value = None
        
        # Exécuter la requête API
        response = client.get(f"/v1/events/{test_event_id}")

        # 3. Vérification (Assert)
        # Vérifier que le mock créé par patch a été appelé
        mock_get_by_id.assert_called_once_with(event_id=test_event_id)
        
        # Vérifier la réponse HTTP 404
        assert response.status_code == 404
        assert response.json() == {"detail": "Événement avec ID " + str(test_event_id) + " non trouvé"} 