"""
Tests pour vérifier l'injection des nouveaux services.
"""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine
from unittest.mock import MagicMock

from dependencies import get_event_processor, get_notification_service
from services.event_processor import EventProcessor
from services.notification_service import NotificationService

# Fixture pour une application FastAPI de test
@pytest.fixture
def app_with_services():
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
    
    # Endpoints de test pour les nouveaux services
    @app.get("/test-event-processor")
    async def test_event_processor(service = Depends(get_event_processor)):
        return {
            "service_available": service is not None,
            "type": type(service).__name__
        }
    
    @app.get("/test-notification-service")
    async def test_notification_service(service = Depends(get_notification_service)):
        return {
            "service_available": service is not None,
            "type": type(service).__name__,
            "smtp_configured": service.smtp_configured
        }
    
    return app

# Client de test
@pytest.fixture
def client(app_with_services):
    return TestClient(app_with_services)

# Test pour l'injection du processeur d'événements
def test_event_processor_injection(client):
    """
    Teste que le processeur d'événements est correctement injecté.
    """
    response = client.get("/test-event-processor")
    assert response.status_code == 200
    assert response.json()["service_available"] == True
    assert response.json()["type"] == "EventProcessor"

# Test pour l'injection du service de notification
def test_notification_service_injection(client):
    """
    Teste que le service de notification est correctement injecté avec la configuration SMTP.
    """
    response = client.get("/test-notification-service")
    assert response.status_code == 200
    assert response.json()["service_available"] == True
    assert response.json()["type"] == "NotificationService"
    assert response.json()["smtp_configured"] == True 