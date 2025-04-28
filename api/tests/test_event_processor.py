"""
Tests pour le processeur d'événements.
"""
import pytest
import json
from datetime import datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from models.event_models import EventModel, EventCreate
from models.memory_models import Memory
from services.event_processor import EventProcessor
from interfaces.repositories import EventRepositoryProtocol
from interfaces.services import EmbeddingServiceProtocol

# Fixture pour un événement de test
@pytest.fixture
def event_model():
    """Crée un événement de test."""
    return EventModel(
        id=uuid.uuid4(),
        content="Ceci est un événement de test",
        metadata={"source": "test", "importance": "high"},
        timestamp=datetime.now(timezone.utc),
        embedding=None
    )

# Fixture pour les mocks
@pytest.fixture
def mocks():
    """Crée les mocks nécessaires pour les tests."""
    event_repo = AsyncMock(spec=EventRepositoryProtocol)
    embedding_service = AsyncMock(spec=EmbeddingServiceProtocol)
    
    # Configuration du mock pour generate_embedding
    embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3, 0.4]
    
    # Configuration du mock pour update_metadata
    event_repo.update_metadata.return_value = True
    
    return event_repo, embedding_service

# Fixture pour le processeur d'événements
@pytest.fixture
def processor(mocks):
    """Crée un processeur d'événements avec des mocks."""
    event_repo, embedding_service = mocks
    return EventProcessor(
        event_repository=event_repo,
        embedding_service=embedding_service
    )

# Test pour process_event
@pytest.mark.asyncio
async def test_process_event(processor, event_model, mocks):
    """Teste le traitement d'un événement."""
    event_repo, embedding_service = mocks
    
    # Traitement de l'événement
    result = await processor.process_event(event_model)
    
    # Vérifications
    assert isinstance(result, dict)
    assert "processed_at" in result
    assert "processor_version" in result
    assert result["source"] == "test"
    assert result["importance"] == "high"
    
    # Vérification que l'embedding a été généré
    embedding_service.generate_embedding.assert_called_once_with(event_model.content)
    
    # Vérification que les métadonnées ont été mises à jour
    event_repo.update_metadata.assert_called_once()
    call_args = event_repo.update_metadata.call_args[1]
    assert call_args["event_id"] == event_model.id
    assert "has_embedding" in call_args["metadata"]
    assert call_args["metadata"]["has_embedding"] == True

# Test pour generate_memory_from_event
@pytest.mark.asyncio
async def test_generate_memory_from_event(processor, event_model):
    """Teste la génération d'une mémoire à partir d'un événement."""
    # Génération de la mémoire
    memory = await processor.generate_memory_from_event(event_model)
    
    # Vérifications
    assert isinstance(memory, Memory)
    assert memory.content == event_model.content
    assert memory.id == str(event_model.id)
    assert memory.timestamp == event_model.timestamp
    assert "source_event_id" in memory.metadata
    assert memory.metadata["source_event_id"] == str(event_model.id)
    assert "memory_created_at" in memory.metadata
    assert "source" in memory.metadata
    assert memory.metadata["source"] == "test"

# Test pour process_event avec une erreur
@pytest.mark.asyncio
async def test_process_event_with_error(processor, event_model, mocks):
    """Teste le traitement d'un événement avec une erreur lors de la génération d'embedding."""
    event_repo, embedding_service = mocks
    
    # Configuration du mock pour générer une erreur
    embedding_service.generate_embedding.side_effect = ValueError("Erreur de test")
    
    # Traitement de l'événement
    result = await processor.process_event(event_model)
    
    # Vérifications
    assert isinstance(result, dict)
    assert "processed_at" in result
    assert "processor_version" in result
    assert result["source"] == "test"
    assert result["has_embedding"] == False
    assert "embedding_error" in result
    assert "Erreur de test" in result["embedding_error"] 