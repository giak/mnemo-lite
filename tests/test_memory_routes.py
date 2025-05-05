import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
import uuid
import datetime
import json
import sys
from pathlib import Path

# Ajout du chemin racine du projet pour permettre les importations relatives
sys.path.append(str(Path(__file__).parent.parent))

# Import de l'application FastAPI
from main import app 
# Import des dépendances et modèles
from models.memory_models import Memory, MemoryCreate, MemoryUpdate
from api.dependencies import get_memory_repository

# --- Fixtures ---

@pytest.fixture
def client():
    """Crée un TestClient FastAPI standard."""
    with TestClient(app) as test_client:
        yield test_client

# Fixture pour mocker directement le repository
@pytest.fixture
def mock_memory_repo():
    """Crée un mock pour MemoryRepositoryProtocol."""
    mock_repo = AsyncMock()
    
    # Configuration automatique des méthodes les plus courantes
    mock_repo.get_by_id.return_value = None  # Par défaut, aucune mémoire trouvée
    mock_repo.add.return_value = None  # Configurer dans chaque test
    mock_repo.update.return_value = None  # Configurer dans chaque test
    mock_repo.delete.return_value = True  # Par défaut, suppression réussie
    mock_repo.list_memories.return_value = ([], 0)  # Par défaut, aucun résultat et count=0
    
    return mock_repo

@pytest.fixture
def app_with_mock_repo(mock_memory_repo):
    """Remplace le repository dans l'app par le mock."""
    
    # Remplacer la dépendance dans l'application
    app.dependency_overrides[get_memory_repository] = lambda: mock_memory_repo
    
    yield app
    
    # Nettoyer après le test
    app.dependency_overrides.clear()

@pytest.fixture
def client_with_mock_repo(app_with_mock_repo):
    """Client de test avec repository mocké."""
    with TestClient(app_with_mock_repo) as test_client:
        yield test_client, app_with_mock_repo

# --- Tests des routes utilisant les fixtures avec mocks ---

def test_get_memory_success_with_mock(client_with_mock_repo):
    """Teste la récupération réussie d'une mémoire en utilisant un mock repository."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    test_content = {"data": "test memory content"}
    test_metadata = {"tag": "test"}
    test_memory_type = "episodic"
    test_event_type = "user_input"
    test_role_id = 1
    test_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Configurer le mock pour retourner une mémoire
    mock_memory = Memory(
        id=test_memory_id,
        timestamp=test_timestamp,
        memory_type=test_memory_type,
        event_type=test_event_type,
        role_id=test_role_id,
        content=test_content,
        metadata=test_metadata
    )
    mock_repo.get_by_id.return_value = mock_memory
    
    # 2. Action
    response = client.get(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.get_by_id.assert_called_once_with(test_memory_id)
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_memory_id)
    assert response_data["content"] == test_content
    assert response_data["metadata"] == test_metadata
    assert response_data["memory_type"] == test_memory_type
    assert response_data["event_type"] == test_event_type
    assert response_data["role_id"] == test_role_id

def test_get_memory_not_found_with_mock(client_with_mock_repo):
    """Teste la récupération d'une mémoire inexistante en utilisant un mock repository."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = None
    
    # 2. Action
    response = client.get(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.get_by_id.assert_called_once_with(test_memory_id)
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_create_memory_success(client_with_mock_repo):
    """Teste la création réussie d'une mémoire."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    test_content = {"message": "Test memory content"}
    test_metadata = {"source": "test", "importance": "high"}
    test_memory_type = "episodic"
    test_event_type = "user_input"
    test_role_id = 1
    test_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Préparer la mémoire à créer
    memory_data = {
        "memory_type": test_memory_type,
        "event_type": test_event_type,
        "role_id": test_role_id,
        "content": test_content,
        "metadata": test_metadata
    }
    
    # Configurer la réponse du mock
    mock_memory = Memory(
        id=test_memory_id,
        timestamp=test_timestamp,
        memory_type=test_memory_type,
        event_type=test_event_type,
        role_id=test_role_id,
        content=test_content,
        metadata=test_metadata
    )
    mock_repo.add.return_value = mock_memory
    
    # 2. Action
    response = client.post("/v0/memories/", json=memory_data)
    
    # 3. Vérification
    assert mock_repo.add.called
    
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["id"] == str(test_memory_id)
    assert response_data["content"] == test_content
    assert response_data["metadata"] == test_metadata
    assert response_data["memory_type"] == test_memory_type
    assert response_data["event_type"] == test_event_type
    assert response_data["role_id"] == test_role_id

def test_update_memory_success(client_with_mock_repo):
    """Teste la mise à jour réussie d'une mémoire."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    original_content = {"message": "Original memory content"}
    original_metadata = {"source": "test", "status": "pending"}
    original_memory_type = "episodic"
    original_event_type = "user_input"
    original_role_id = 1
    
    # Mise à jour à appliquer
    update_data = {
        "content": {"message": "Updated memory content"},
        "metadata": {"status": "completed", "updated_at": "2023-06-15T12:00:00Z"},
        "memory_type": "semantic"
    }
    
    # Résultat attendu après la mise à jour
    expected_content = update_data["content"]
    expected_metadata = {"status": "completed", "updated_at": "2023-06-15T12:00:00Z"}
    expected_memory_type = "semantic"
    
    # Configurer la réponse du mock
    mock_memory = Memory(
        id=test_memory_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        memory_type=expected_memory_type,
        event_type=original_event_type,
        role_id=original_role_id,
        content=expected_content,
        metadata=expected_metadata
    )
    mock_repo.update.return_value = mock_memory
    
    # 2. Action
    response = client.put(f"/v0/memories/{test_memory_id}", json=update_data)
    
    # 3. Vérification
    mock_repo.update.assert_called_once()
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(test_memory_id)
    assert response_data["content"] == expected_content
    assert response_data["metadata"] == expected_metadata
    assert response_data["memory_type"] == expected_memory_type
    assert response_data["event_type"] == original_event_type
    assert response_data["role_id"] == original_role_id

def test_update_memory_not_found(client_with_mock_repo):
    """Teste la mise à jour d'une mémoire inexistante."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    update_data = {
        "content": {"message": "Updated content"}
    }
    
    # Configurer le mock pour simuler une mémoire non trouvée
    mock_repo.update.return_value = None
    
    # 2. Action
    response = client.put(f"/v0/memories/{test_memory_id}", json=update_data)
    
    # 3. Vérification
    mock_repo.update.assert_called_once()
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_delete_memory_success(client_with_mock_repo):
    """Teste la suppression réussie d'une mémoire."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    mock_repo.delete.return_value = True
    
    # 2. Action
    response = client.delete(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.delete.assert_called_once_with(test_memory_id)
    
    assert response.status_code == 204
    assert response.content == b''  # Pas de contenu pour une réponse 204

def test_delete_memory_not_found(client_with_mock_repo):
    """Teste la suppression d'une mémoire inexistante."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memory_id = uuid.uuid4()
    mock_repo.delete.return_value = False
    
    # 2. Action
    response = client.delete(f"/v0/memories/{test_memory_id}")
    
    # 3. Vérification
    mock_repo.delete.assert_called_once_with(test_memory_id)
    
    assert response.status_code == 404
    assert "detail" in response.json()

def test_list_memories(client_with_mock_repo):
    """Teste la liste des mémoires avec filtrage."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memories = [
        Memory(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            memory_type="episodic",
            event_type="user_input",
            role_id=1,
            content={"message": f"Memory {i}"},
            metadata={"type": "type1" if i % 2 == 0 else "type2"}
        )
        for i in range(3)
    ]
    
    # Configurer le mock pour retourner nos mémoires de test
    mock_repo.list_memories.return_value = (test_memories, len(test_memories))
    
    # 2. Action - Récupérer toutes les mémoires
    response = client.get("/v0/memories/")
    
    # 3. Vérification
    assert mock_repo.list_memories.called
    
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 3
    
    # Vérifier que les paramètres sont bien passés au repository
    mock_repo.list_memories.reset_mock()
    
    # 4. Action - Filtrage par type de mémoire
    response = client.get("/v0/memories/?memory_type=episodic&limit=5&offset=2")
    
    # 5. Vérification des paramètres
    mock_repo.list_memories.assert_called_once()
    call_kwargs = mock_repo.list_memories.call_args[1]
    assert call_kwargs["memory_type"] == "episodic"
    assert call_kwargs["limit"] == 5
    assert call_kwargs["offset"] == 2

def test_list_memories_empty_result(client_with_mock_repo):
    """Teste la liste des mémoires quand le résultat est vide."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation - Liste vide
    mock_repo.list_memories.return_value = ([], 0)
    
    # 2. Action
    response = client.get("/v0/memories/")
    
    # 3. Vérification
    assert mock_repo.list_memories.called
    
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 0
    assert isinstance(response_data, list)

def test_list_memories_with_filters(client_with_mock_repo):
    """Teste la liste des mémoires avec différents filtres."""
    client, app = client_with_mock_repo
    mock_repo = app.dependency_overrides[get_memory_repository]()
    
    # 1. Préparation
    test_memories = [
        Memory(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            memory_type="episodic",
            event_type="user_input",
            role_id=1,
            content={"message": "Memory with specific filters"},
            metadata={"session_id": "test-session"}
        )
    ]
    
    # Configurer le mock
    mock_repo.list_memories.return_value = (test_memories, len(test_memories))
    
    # 2. Action - Filtrage par plusieurs critères
    response = client.get("/v0/memories/?memory_type=episodic&event_type=user_input&role_id=1&session_id=test-session")
    
    # 3. Vérification des paramètres transmis au repository
    assert mock_repo.list_memories.called
    call_kwargs = mock_repo.list_memories.call_args[1]
    assert call_kwargs["memory_type"] == "episodic"
    assert call_kwargs["event_type"] == "user_input"
    assert call_kwargs["role_id"] == 1
    assert call_kwargs["session_id"] == "test-session"
    
    # Vérification de la réponse
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1 