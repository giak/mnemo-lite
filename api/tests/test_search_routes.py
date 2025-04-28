"""
Tests pour les routes de recherche.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from routes.search_routes import router as search_router
from models.memory_models import Memory
from dependencies import get_memory_search_service

# Fixtures
@pytest.fixture
def app():
    """Fixture pour créer une application FastAPI de test."""
    app = FastAPI()
    app.include_router(search_router)
    return app

@pytest.fixture
def client(app):
    """Fixture pour créer un client de test."""
    return TestClient(app)

@pytest.fixture
def mock_memory_search_service():
    """Fixture pour créer un mock du service de recherche de mémoires."""
    mock_service = AsyncMock()
    return mock_service

@pytest.fixture
def app_with_mock_service(app, mock_memory_search_service):
    """Fixture pour créer une application FastAPI avec un service de recherche mocké."""
    app.dependency_overrides[get_memory_search_service] = lambda: mock_memory_search_service
    return app

@pytest.fixture
def client_with_mock_service(app_with_mock_service):
    """Fixture pour créer un client de test avec un service de recherche mocké."""
    return TestClient(app_with_mock_service)

# Helper pour créer des mémoires de test
def create_test_memories():
    """Crée des mémoires de test."""
    return [
        Memory(
            id="1",
            content={"text": "Test memory 1"},
            metadata={"tag": "test", "priority": "high"},
            timestamp=datetime.now(tz=timezone.utc)
        ),
        Memory(
            id="2",
            content={"text": "Test memory 2"},
            metadata={"tag": "test", "priority": "medium"},
            timestamp=datetime.now(tz=timezone.utc)
        )
    ]

# Tests
def test_search_by_content(client_with_mock_service, mock_memory_search_service):
    """Test de la route de recherche par contenu."""
    # Configuration du mock
    test_memories = create_test_memories()
    mock_memory_search_service.search_by_content.return_value = test_memories
    
    # Requête de test
    response = client_with_mock_service.post(
        "/search/content",
        json={"query": "Test query", "limit": 5}
    )
    
    # Vérifications
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    assert data["query"] == "Test query"
    
    # Vérification du mock
    mock_memory_search_service.search_by_content.assert_called_once_with("Test query", 5)

def test_search_by_similarity(client_with_mock_service, mock_memory_search_service):
    """Test de la route de recherche par similarité."""
    # Configuration du mock
    test_memories = create_test_memories()
    mock_memory_search_service.search_by_similarity.return_value = test_memories
    
    # Requête de test
    response = client_with_mock_service.post(
        "/search/similarity",
        json={"query": "Test query", "limit": 5}
    )
    
    # Vérifications
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    assert data["query"] == "Test query"
    
    # Vérification du mock
    mock_memory_search_service.search_by_similarity.assert_called_once_with("Test query", 5)

def test_search_by_metadata(client_with_mock_service, mock_memory_search_service):
    """Test de la route de recherche par métadonnées."""
    # Configuration du mock
    test_memories = create_test_memories()
    mock_memory_search_service.search_by_metadata.return_value = test_memories
    
    # Requête de test
    metadata_filter = {"tag": "test", "priority": "high"}
    response = client_with_mock_service.get(
        f"/search/metadata?metadata_filter={json.dumps(metadata_filter)}&limit=10"
    )
    
    # Vérifications
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    
    # Vérification du mock
    mock_memory_search_service.search_by_metadata.assert_called_once_with(metadata_filter, 10)

def test_search_by_metadata_invalid_json(client_with_mock_service):
    """Test de la route de recherche par métadonnées avec un JSON invalide."""
    # Requête de test avec un JSON invalide
    response = client_with_mock_service.get(
        "/search/metadata?metadata_filter=invalid_json&limit=10"
    )
    
    # Vérifications
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "JSON invalide" in data["detail"] 