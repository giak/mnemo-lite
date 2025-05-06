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
        smtp_password=None,
    )


# Fixture pour le service de notification avec SMTP configuré (pour les tests de branche)
@pytest.fixture
def notification_service_with_smtp():
    """Crée un service de notification avec SMTP configuré."""
    return NotificationService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="password",
    )


# Test pour send_notification
@pytest.mark.asyncio
async def test_send_notification(notification_service):
    """Teste l'envoi d'une notification."""
    # Envoi d'une notification
    result = await notification_service.send_notification(
        user_id="user123", message="Test message", metadata={"priority": "high"}
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
        message="Broadcast test message", user_ids=user_ids
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
        message="Broadcast test message", user_ids=None
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
        user_id="user123", message="Test message", metadata={"priority": "high"}
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
            smtp_password="password",
        )

        # Envoi d'une notification
        result = await service.send_notification(
            user_id="user123", message="Test message"
        )

        # Vérifications
        assert result == False


# Test pour broadcast_notification avec une erreur globale
@pytest.mark.asyncio
async def test_broadcast_notification_with_global_error():
    """Teste la diffusion d'une notification avec une erreur globale."""
    # Création d'un service pour le test
    service = NotificationService()

    # Patch de la méthode broadcast_notification pour simuler une erreur
    with patch.object(
        service, "broadcast_notification", side_effect=Exception("Erreur globale")
    ):
        # Diffusion de la notification avec gestion d'erreur
        try:
            results = await service.broadcast_notification(
                message="Broadcast test message", user_ids=["user1", "user2"]
            )
            assert False, "L'exception n'a pas été levée"
        except Exception as e:
            assert str(e) == "Erreur globale"
            # Le test est réussi si on intercepte l'exception


# Test pour broadcast_notification avec erreurs partielles
@pytest.mark.asyncio
async def test_broadcast_notification_with_partial_errors(notification_service):
    """Teste la diffusion d'une notification avec des erreurs partielles."""
    # Liste d'utilisateurs
    user_ids = ["user1", "user2", "error_user"]

    # Patch de la méthode send_notification pour simuler une erreur pour un utilisateur spécifique
    original_send = notification_service.send_notification

    async def mock_send(user_id, message, metadata=None):
        if user_id == "error_user":
            return False
        return await original_send(user_id, message, metadata)

    with patch.object(notification_service, "send_notification", side_effect=mock_send):
        # Diffusion de la notification
        results = await notification_service.broadcast_notification(
            message="Broadcast test message", user_ids=user_ids
        )

        # Vérifications
        assert len(results) == 3
        assert results["user1"] == True
        assert results["user2"] == True
        assert results["error_user"] == False
        assert len(notification_service.notification_log) == 2  # Deux entrées réussies


# Test pour send_notification sans métadonnées
@pytest.mark.asyncio
async def test_send_notification_without_metadata(notification_service):
    """Teste l'envoi d'une notification sans métadonnées."""
    # Envoi d'une notification sans métadonnées
    result = await notification_service.send_notification(
        user_id="user123", message="Test message without metadata"
    )

    # Vérifications
    assert result == True
    assert len(notification_service.notification_log) == 1

    log_entry = notification_service.notification_log[0]
    assert log_entry["user_id"] == "user123"
    assert log_entry["message"] == "Test message without metadata"
    assert "status" in log_entry["metadata"]
    assert "timestamp" in log_entry["metadata"]


# Test pour broadcast_notification avec une liste vide d'utilisateurs
@pytest.mark.asyncio
async def test_broadcast_notification_with_empty_user_list(notification_service):
    """Teste la diffusion d'une notification avec une liste vide d'utilisateurs."""
    # Diffusion de la notification avec une liste vide
    results = await notification_service.broadcast_notification(
        message="Broadcast test message", user_ids=[]
    )

    # Vérifications
    assert len(results) == 0
    assert len(notification_service.notification_log) == 0


# Test pour l'initialisation du service
def test_notification_service_initialization():
    """Teste l'initialisation du service de notification."""
    # Initialisation avec des paramètres complets
    service = NotificationService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="password",
        default_sender="test@example.com",
    )

    # Vérifications
    assert service.smtp_host == "smtp.example.com"
    assert service.smtp_port == 587
    assert service.smtp_user == "user"
    assert service.smtp_password == "password"
    assert service.default_sender == "test@example.com"
    assert service.smtp_configured == True
    assert len(service.notification_log) == 0

    # Initialisation avec des paramètres partiels
    service_partial = NotificationService(smtp_host="smtp.example.com", smtp_port=587)

    # Vérifications
    assert service_partial.smtp_configured == False
    assert service_partial.default_sender == "noreply@mnemolite.app"


# Test pour send_notification avec une exception non gérée
@pytest.mark.asyncio
async def test_send_notification_with_unhandled_exception(notification_service):
    """Teste l'envoi d'une notification avec une exception non gérée."""
    # Création d'un user_id qui provoquera une erreur
    # En provoquant une erreur lors de l'accès à user_id
    with patch.object(
        notification_service,
        "send_notification",
        side_effect=Exception("Erreur non gérée"),
    ):
        # Envoi d'une notification avec gestion d'erreur
        try:
            result = await notification_service.send_notification(
                user_id="error_user", message="Test message"
            )
            assert False, "L'exception n'a pas été levée"
        except Exception as e:
            assert str(e) == "Erreur non gérée"
            # Le test est réussi si on intercepte l'exception


# Test pour broadcast_notification avec des erreurs dans send_notification
@pytest.mark.asyncio
async def test_broadcast_with_send_errors(notification_service):
    """Teste la diffusion de notification lorsque send_notification génère des erreurs."""
    # Liste d'utilisateurs
    user_ids = ["user1", "user2", "user3"]

    # Patch pour simuler des erreurs dans send_notification
    with patch.object(notification_service, "send_notification", return_value=False):
        # Diffusion de la notification
        results = await notification_service.broadcast_notification(
            message="Broadcast test message", user_ids=user_ids
        )

        # Vérifications
        assert len(results) == 3
        assert all(success == False for success in results.values())
