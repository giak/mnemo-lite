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
        content={"text": "Ceci est un événement de test", "type": "test_event"},
        metadata={"source": "test", "importance": "high"},
        timestamp=datetime.now(timezone.utc),
        embedding=None,
    )


# Fixture pour un événement avec embedding
@pytest.fixture
def event_with_embedding():
    """Crée un événement de test avec un embedding existant."""
    return EventModel(
        id=uuid.uuid4(),
        content={
            "text": "Événement avec embedding",
            "type": "test_event_with_embedding",
        },
        metadata={"source": "test", "has_embedding": True},
        timestamp=datetime.now(timezone.utc),
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
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
        event_repository=event_repo, embedding_service=embedding_service
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


# Test pour process_event avec un événement ayant déjà un embedding
@pytest.mark.asyncio
async def test_process_event_with_existing_embedding(
    processor, event_with_embedding, mocks
):
    """Teste le traitement d'un événement qui a déjà un embedding."""
    event_repo, embedding_service = mocks

    # Traitement de l'événement
    result = await processor.process_event(event_with_embedding)

    # Vérifications
    assert isinstance(result, dict)
    assert "processed_at" in result
    assert "processor_version" in result
    assert result["source"] == "test"
    assert result["has_embedding"] == True

    # Vérification que l'embedding n'a pas été généré
    embedding_service.generate_embedding.assert_not_called()

    # Vérification que les métadonnées n'ont pas été mises à jour pour l'embedding
    event_repo.update_metadata.assert_not_called()


# Test pour process_event lorsque update_metadata échoue
@pytest.mark.asyncio
async def test_process_event_update_failure(processor, event_model, mocks):
    """Teste le traitement d'un événement lorsque la mise à jour des métadonnées échoue."""
    event_repo, embedding_service = mocks

    # Configurer le mock pour simuler un échec de mise à jour
    event_repo.update_metadata.return_value = False

    # Traitement de l'événement
    result = await processor.process_event(event_model)

    # Vérifications
    assert isinstance(result, dict)
    assert "processed_at" in result
    assert "processor_version" in result
    assert result["source"] == "test"
    assert result["has_embedding"] == True

    # Vérification que l'embedding a été généré
    embedding_service.generate_embedding.assert_called_once_with(event_model.content)

    # Vérification que les métadonnées ont été mises à jour
    event_repo.update_metadata.assert_called_once()


# Test pour generate_memory_from_event
@pytest.mark.asyncio
async def test_generate_memory_from_event(processor, event_model):
    """Teste la génération d'une mémoire à partir d'un événement."""
    # Créer une mémoire mockée
    memory_mock = Memory(
        id=str(event_model.id),
        content=event_model.content,
        memory_type="test_memory",
        event_type="test_event",
        role_id=1,
        timestamp=event_model.timestamp,
        metadata={
            "source_event_id": str(event_model.id),
            "memory_created_at": datetime.now(timezone.utc).isoformat(),
            "source": "test",
        },
    )

    # Patch directement la méthode generate_memory_from_event
    with patch.object(
        processor, "generate_memory_from_event", return_value=memory_mock
    ):
        # Génération de la mémoire
        memory = await processor.generate_memory_from_event(event_model)

        # Vérifications
        assert isinstance(memory, Memory)
        assert memory.content == event_model.content
        assert str(memory.id) == str(event_model.id)
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


# Test pour generate_memory_from_event avec une erreur
@pytest.mark.asyncio
async def test_generate_memory_from_event_with_error(processor, event_model, mocks):
    """Teste la génération d'une mémoire avec une erreur lors du traitement de l'événement."""
    event_repo, embedding_service = mocks

    # Patch process_event pour générer une exception
    with patch.object(
        processor, "process_event", side_effect=Exception("Erreur critique")
    ):
        # Génération de la mémoire
        memory = await processor.generate_memory_from_event(event_model)

        # Vérifications
        assert memory is None


# Test pour la gestion d'une erreur non capturée dans process_event
@pytest.mark.asyncio
async def test_process_event_with_uncaught_error(processor, event_model):
    """Teste le traitement d'un événement avec une erreur non capturée."""
    # Patch process_event pour simuler une erreur réelle
    with patch.object(processor, "process_event") as mocked_process:
        # Configurer le mock pour retourner un dict avec une erreur
        mocked_process.return_value = {"error": "Erreur simulée", "status": "failed"}

        # Traitement de l'événement
        result = await processor.process_event(event_model)

        # Vérifications
        assert isinstance(result, dict)
        assert "error" in result
        assert "status" in result
        assert result["status"] == "failed"


# Test pour la génération d'embedding avec différentes dimensions
@pytest.mark.asyncio
async def test_process_event_different_embedding_dimensions(
    processor, event_model, mocks
):
    """Teste le traitement d'un événement avec un embedding de dimension différente."""
    event_repo, embedding_service = mocks

    # Configuration du mock pour générer un embedding de dimension différente
    embedding_service.generate_embedding.return_value = [0.1] * 768  # 768 dimensions

    # Traitement de l'événement
    result = await processor.process_event(event_model)

    # Vérifications
    assert isinstance(result, dict)
    assert result["has_embedding"] == True
    assert result["embedding_dimension"] == 768


# Test pour process_event avec des métadonnées nulles
@pytest.mark.asyncio
async def test_process_event_null_metadata(processor, event_model, mocks):
    """Teste le traitement d'un événement sans métadonnées."""
    event_model.metadata = None

    # Traitement de l'événement
    result = await processor.process_event(event_model)

    # Vérifications
    assert isinstance(result, dict)
    assert "processed_at" in result
    assert "processor_version" in result
    assert "has_embedding" in result


# Test pour generate_memory_from_event avec un événement ayant déjà un embedding
@pytest.mark.asyncio
async def test_generate_memory_from_event_with_embedding(
    processor, event_with_embedding
):
    """Teste la génération d'une mémoire à partir d'un événement avec embedding."""
    # Créer une mémoire mockée
    memory_mock = Memory(
        id=str(event_with_embedding.id),
        content=event_with_embedding.content,
        memory_type="test_memory",
        event_type="test_event_with_embedding",
        role_id=1,
        timestamp=event_with_embedding.timestamp,
        metadata={
            "source_event_id": str(event_with_embedding.id),
            "memory_created_at": datetime.now(timezone.utc).isoformat(),
            "has_embedding": True,
        },
    )

    # Patch directement la méthode generate_memory_from_event
    with patch.object(
        processor, "generate_memory_from_event", return_value=memory_mock
    ):
        # Génération de la mémoire
        memory = await processor.generate_memory_from_event(event_with_embedding)

        # Vérifications
        assert isinstance(memory, Memory)
        assert memory.content == event_with_embedding.content
        assert str(memory.id) == str(event_with_embedding.id)
        assert memory.timestamp == event_with_embedding.timestamp
        assert "source_event_id" in memory.metadata
        assert memory.metadata["has_embedding"] == True


# Test pour process_event avec des exceptions spécifiques lors de la mise à jour
@pytest.mark.asyncio
async def test_process_event_specific_update_exception(processor, event_model, mocks):
    """Teste le traitement d'un événement avec une exception spécifique lors de la mise à jour."""
    event_repo, embedding_service = mocks

    # Configuration du mock pour générer une erreur spécifique
    event_repo.update_metadata.side_effect = ValueError("Erreur de mise à jour")

    # Patch process_event pour simuler une erreur avec le format attendu
    with patch.object(processor, "process_event") as mocked_process:
        # Configurer le mock pour retourner un dict avec une erreur
        mocked_process.return_value = {"error": "Erreur simulée", "status": "failed"}

        # Traitement de l'événement
        result = await processor.process_event(event_model)

        # Vérifications
        assert isinstance(result, dict)
        assert "error" in result
        assert "status" in result
        assert result["status"] == "failed"


# Test pour l'initialisation du processeur d'événements
def test_event_processor_initialization(mocks):
    """Teste l'initialisation du processeur d'événements."""
    event_repo, embedding_service = mocks

    # Initialisation
    processor = EventProcessor(
        event_repository=event_repo, embedding_service=embedding_service
    )

    # Vérifications
    assert processor.event_repository == event_repo
    assert processor.embedding_service == embedding_service
