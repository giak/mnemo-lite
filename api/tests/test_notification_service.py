"""
Tests pour le service de notification.
"""
import pytest
import json
from datetime import datetime
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from services.notification_service import NotificationService

# Fixture pour le service de notification en mode test
@pytest.fixture
def notification_service():
    """Crée un service de notification en mode test."""
    return NotificationService(
        smtp_host=None,  # Mode test sans serveur SMTP
        smtp_port=None,
        smtp_user=None,
        smtp_password=None
    )

# Fixture pour le service de notification avec SMTP configuré (pour les tests de branche)
@pytest.fixture
def notification_service_with_smtp():
    """Crée un service de notification avec SMTP configuré."""
    return NotificationService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="password"
    )

# Test pour send_notification
@pytest.mark.asyncio
async def test_send_notification(notification_service):
    """Teste l'envoi d'une notification."""
    # Envoi d'une notification
    result = await notification_service.send_notification(
        user_id="user123",
        message="Test message",
        metadata={"priority": "high"}
    )
    
    # Vérifications
    assert result == True
    assert len(notification_service.notification_log) == 1
    
    log_entry = notification_service.notification_log[0]
    assert log_entry["user_id"] == "user123"
    assert log_entry["message"] == "Test message"
    assert log_entry["metadata"]["priority"] == "high"
    assert log_entry["metadata"]["status"] == "logged_only"
    assert "timestamp" in log_entry["metadata"]

# Test pour broadcast_notification
@pytest.mark.asyncio
async def test_broadcast_notification(notification_service):
    """Teste la diffusion d'une notification à plusieurs utilisateurs."""
    # Liste d'utilisateurs
    user_ids = ["user1", "user2", "user3"]
    
    # Diffusion de la notification
    results = await notification_service.broadcast_notification(
        message="Broadcast test message",
        user_ids=user_ids
    )
    
    # Vérifications
    assert len(results) == 3
    assert all(success == True for success in results.values())
    assert len(notification_service.notification_log) == 3
    
    # Vérification des métadonnées communes
    for log_entry in notification_service.notification_log:
        assert log_entry["message"] == "Broadcast test message"
        assert log_entry["metadata"]["type"] == "broadcast"
        assert log_entry["metadata"]["broadcast_size"] == 3
        assert "broadcast_id" in log_entry["metadata"]

# Test pour broadcast_notification sans destinataires
@pytest.mark.asyncio
async def test_broadcast_notification_without_recipients(notification_service):
    """Teste la diffusion d'une notification sans destinataires."""
    # Diffusion de la notification sans destinataires
    results = await notification_service.broadcast_notification(
        message="Broadcast test message",
        user_ids=None
    )
    
    # Vérifications
    assert len(results) == 0
    assert len(notification_service.notification_log) == 0

# Test pour send_notification avec SMTP configuré
@pytest.mark.asyncio
async def test_send_notification_with_smtp(notification_service_with_smtp):
    """Teste l'envoi d'une notification avec SMTP configuré."""
    # Envoi d'une notification
    result = await notification_service_with_smtp.send_notification(
        user_id="user123",
        message="Test message",
        metadata={"priority": "high"}
    )
    
    # Vérifications
    assert result == True
    assert len(notification_service_with_smtp.notification_log) == 1
    
    log_entry = notification_service_with_smtp.notification_log[0]
    assert log_entry["metadata"]["status"] == "sent"

# Test pour send_notification avec une erreur
@pytest.mark.asyncio
async def test_send_notification_with_error():
    """Teste l'envoi d'une notification avec une erreur."""
    # Création d'un service qui génère une erreur
    with patch("asyncio.sleep", side_effect=Exception("Test error")):
        service = NotificationService(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="password"
        )
        
        # Envoi d'une notification
        result = await service.send_notification(
            user_id="user123",
            message="Test message"
        )
        
        # Vérifications
        assert result == False 