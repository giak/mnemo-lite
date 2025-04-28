"""
Tests pour le système d'injection de dépendances.
"""
import pytest
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine
from unittest.mock import AsyncMock, MagicMock, patch
import os
import json

from dependencies import (
    get_db_engine, 
    get_event_repository, 
    get_memory_repository,
    get_embedding_service,
    get_memory_search_service,
    get_event_processor,
    get_notification_service
)
from interfaces.repositories import EventRepositoryProtocol, MemoryRepositoryProtocol
from interfaces.services import (
    EmbeddingServiceProtocol, 
    MemorySearchServiceProtocol,
    EventProcessorProtocol,
    NotificationServiceProtocol
)
from services.embedding_service import SimpleEmbeddingService
from services.memory_search_service import MemorySearchService
from services.event_processor import EventProcessor
from services.notification_service import NotificationService

# Fixture pour une application FastAPI de test
@pytest.fixture
def app_with_engine():
    app = FastAPI()
    
    # Créer un moteur mock
    mock_engine = MagicMock(spec=AsyncEngine)
    
    # Configurer l'état de l'application
    app.state.db_engine = mock_engine
    app.state.settings = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": 587,
        "SMTP_USER": "user",
        "SMTP_PASSWORD": "password"
    }
    
    # Définir un endpoint de test pour chaque dépendance
    @app.get("/test-db-engine")
    async def test_db_engine(engine = Depends(get_db_engine)):
        return {"engine_available": engine is not None}
    
    @app.get("/test-event-repository")
    async def test_event_repository(repo = Depends(get_event_repository)):
        return {"repository_available": repo is not None, "type": type(repo).__name__}
    
    @app.get("/test-memory-repository")
    async def test_memory_repository(repo = Depends(get_memory_repository)):
        return {"repository_available": repo is not None, "type": type(repo).__name__}
    
    @app.get("/test-embedding-service")
    async def test_embedding_service(service = Depends(get_embedding_service)):
        return {"service_available": service is not None, "type": type(service).__name__}
    
    @app.get("/test-memory-search-service")
    async def test_memory_search_service(service = Depends(get_memory_search_service)):
        return {"service_available": service is not None, "type": type(service).__name__}
    
    @app.get("/test-event-processor")
    async def test_event_processor(service = Depends(get_event_processor)):
        return {"service_available": service is not None, "type": type(service).__name__}
    
    @app.get("/test-notification-service")
    async def test_notification_service(service = Depends(get_notification_service)):
        return {"service_available": service is not None, "type": type(service).__name__}
    
    return app

# Fixture pour une application FastAPI sans moteur
@pytest.fixture
def app_without_engine():
    app = FastAPI()
    
    # Pas de moteur configuré
    app.state.db_engine = None
    
    # Définir un endpoint de test pour get_db_engine
    @app.get("/test-db-engine")
    async def test_db_engine(engine = Depends(get_db_engine)):
        return {"engine_available": engine is not None}
    
    return app

# Test pour client avec moteur de base de données
@pytest.fixture
def client_with_engine(app_with_engine):
    return TestClient(app_with_engine)

# Test pour client sans moteur de base de données
@pytest.fixture
def client_without_engine(app_without_engine):
    return TestClient(app_without_engine)

# Tests pour l'injection du moteur de base de données
def test_db_engine_injection(client_with_engine):
    """Teste l'injection du moteur de base de données."""
    response = client_with_engine.get("/test-db-engine")
    assert response.status_code == 200
    assert response.json()["engine_available"] == True

# Test pour l'injection du repository d'événements
def test_event_repository_injection(client_with_engine):
    """Teste l'injection du repository d'événements."""
    response = client_with_engine.get("/test-event-repository")
    assert response.status_code == 200
    assert response.json()["repository_available"] == True
    assert response.json()["type"] == "EventRepository"

# Test pour l'injection du repository de mémoires
def test_memory_repository_injection(client_with_engine):
    """Teste l'injection du repository de mémoires."""
    response = client_with_engine.get("/test-memory-repository")
    assert response.status_code == 200
    assert response.json()["repository_available"] == True
    assert response.json()["type"] == "MemoryRepository"

# Test pour l'injection du service d'embedding
def test_embedding_service_injection(client_with_engine):
    """Teste l'injection du service d'embedding."""
    response = client_with_engine.get("/test-embedding-service")
    assert response.status_code == 200
    assert response.json()["service_available"] == True
    assert response.json()["type"] == "SimpleEmbeddingService"

# Test pour l'injection du service de recherche de mémoires
def test_memory_search_service_injection(client_with_engine):
    """Teste l'injection du service de recherche de mémoires."""
    response = client_with_engine.get("/test-memory-search-service")
    assert response.status_code == 200
    assert response.json()["service_available"] == True
    assert response.json()["type"] == "MemorySearchService"

# Test pour l'injection du processeur d'événements
def test_event_processor_injection(client_with_engine):
    """Teste l'injection du processeur d'événements."""
    response = client_with_engine.get("/test-event-processor")
    assert response.status_code == 200
    assert response.json()["service_available"] == True
    assert response.json()["type"] == "EventProcessor"

# Test pour l'injection du service de notification
def test_notification_service_injection(client_with_engine):
    """Teste l'injection du service de notification."""
    response = client_with_engine.get("/test-notification-service")
    assert response.status_code == 200
    assert response.json()["service_available"] == True
    assert response.json()["type"] == "NotificationService"

# Test pour la gestion des erreurs dans l'injection de dépendances
def test_dependency_error_handling(client_without_engine):
    """Teste la gestion des erreurs lors de l'injection de dépendances."""
    # Utiliser client_without_engine pour tester le cas où le moteur n'est pas disponible
    response = client_without_engine.get("/test-db-engine")
    assert response.status_code == 503
    assert "Database connection not available" in response.json()["detail"] 