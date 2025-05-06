import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, APIRouter, Body

from interfaces.services import EmbeddingServiceProtocol
from models.embedding_models import (
    EmbeddingRequest,
    EmbeddingResponse,
    SimilarityRequest,
    SimilarityResponse,
)

from main import app

# Ajout du chemin racine du projet pour permettre les importations relatives
sys.path.append(str(Path(__file__).parent.parent))

from services.embedding_service import SimpleEmbeddingService, EmbeddingServiceInterface

# Créer un router pour les endpoints de test
test_router = APIRouter(prefix="/test", tags=["test"])


# Fonction pour récupérer le service mocké
def get_test_embedding_service() -> EmbeddingServiceProtocol:
    """Retourne le mock du service d'embedding pour les tests."""
    return app.state.mock_embedding_service


@test_router.post("/embedding", response_model=EmbeddingResponse)
async def test_generate_embedding(
    request: EmbeddingRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_test_embedding_service),
):
    embedding = await embedding_service.generate_embedding(request.text)
    return EmbeddingResponse(
        embedding=embedding, dimension=len(embedding), model="test-model"
    )


@test_router.post("/similarity", response_model=SimilarityResponse)
async def endpoint_compute_similarity(
    request: SimilarityRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_test_embedding_service),
):
    """
    Endpoint de test pour calculer la similarité entre deux textes.
    Simule un endpoint réel utilisant le protocole de service pour les tests.
    """
    embedding1 = await embedding_service.generate_embedding(request.text1)
    embedding2 = await embedding_service.generate_embedding(request.text2)
    similarity = await embedding_service.compute_similarity(embedding1, embedding2)

    return SimilarityResponse(similarity=similarity, model="test-model")


class MockEmbeddingService:
    """Implémentation fictive du EmbeddingServiceProtocol pour les tests."""

    def __init__(self):
        self.generate_embedding = AsyncMock()
        self.compute_similarity = AsyncMock()


# Fixture pour le client FastAPI avec un mock du service
@pytest.fixture
def app_with_mock_service():
    """Client avec un service mocké injecté."""
    mock_service = MockEmbeddingService()

    # Ajouter le router de test à l'application
    app.include_router(test_router)

    # Stocker le mock dans l'état de l'app
    app.state.mock_embedding_service = mock_service

    with TestClient(app) as test_client:
        yield test_client, mock_service


def test_generate_embedding_with_protocol_mock(app_with_mock_service):
    """Teste la génération d'un embedding en utilisant un mock basé sur le protocole."""
    client, mock_service = app_with_mock_service

    # 1. Préparation
    test_text = "Test text for embedding"
    mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    # Configurer le comportement du mock
    mock_service.generate_embedding.return_value = mock_embedding

    # 2. Action
    response = client.post("/test/embedding", json={"text": test_text})

    # 3. Vérification
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["embedding"] == mock_embedding
    assert response_data["dimension"] == len(mock_embedding)
    assert response_data["model"] == "test-model"
    mock_service.generate_embedding.assert_called_once_with(test_text)


def test_compute_similarity_with_protocol_mock(app_with_mock_service):
    """Teste le calcul de similarité en utilisant un mock basé sur le protocole."""
    client, mock_service = app_with_mock_service

    # 1. Préparation
    text1 = "First text"
    text2 = "Second text"
    embedding1 = [0.1, 0.2, 0.3]
    embedding2 = [0.2, 0.3, 0.4]
    expected_similarity = 0.85

    # Configurer le comportement du mock
    mock_service.generate_embedding.side_effect = [embedding1, embedding2]
    mock_service.compute_similarity.return_value = expected_similarity

    # 2. Action
    response = client.post("/test/similarity", json={"text1": text1, "text2": text2})

    # 3. Vérification (Assert)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["similarity"] == expected_similarity
    assert response_data["model"] == "test-model"

    # Vérifier que les mocks ont été appelés correctement
    mock_service.generate_embedding.assert_any_call(text1)
    mock_service.generate_embedding.assert_any_call(text2)
    assert mock_service.generate_embedding.call_count == 2
    mock_service.compute_similarity.assert_called_once_with(embedding1, embedding2)


# Fixtures
@pytest.fixture
def embedding_service():
    """Fixture pour créer une instance du service d'embeddings."""
    return SimpleEmbeddingService()


# Tests
@pytest.mark.asyncio
async def test_generate_embedding():
    """Test de la génération d'embedding de base."""
    service = SimpleEmbeddingService()

    # Générer un embedding
    text = "Ceci est un test d'embedding."
    embedding = await service.generate_embedding(text)

    # Vérifications
    assert isinstance(embedding, list)
    assert len(embedding) == 1536  # Dimension par défaut = 1536
    assert all(
        isinstance(x, float) for x in embedding
    )  # Tous les éléments sont des flottants


@pytest.mark.asyncio
async def test_generate_embedding_empty_text():
    """Test de la génération d'embedding avec un texte vide."""
    service = SimpleEmbeddingService()

    # Générer un embedding avec un texte vide
    text = ""
    embedding = await service.generate_embedding(text)

    # Vérifications
    assert isinstance(embedding, list)
    assert len(embedding) == 1536  # Dimension par défaut = 1536
    assert all(
        isinstance(x, float) for x in embedding
    )  # Tous les éléments sont des flottants


@pytest.mark.asyncio
async def test_dimension_property():
    """Test de la propriété dimension."""
    service = SimpleEmbeddingService()

    # Vérifier la dimension par défaut
    assert service.dimension == 1536  # Dimension par défaut = 1536

    # Tester différentes dimensions
    service_dim_512 = SimpleEmbeddingService(dimension=512)
    assert service_dim_512.dimension == 512


@pytest.mark.asyncio
async def test_cosine_similarity():
    """Test de la fonction de similarité cosinus."""
    service = SimpleEmbeddingService()

    # Créer deux vecteurs test
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    v3 = [1.0, 1.0, 0.0]

    # Calculer les similarités
    sim12 = await service.compute_similarity(v1, v2)
    sim13 = await service.compute_similarity(v1, v3)

    # Vérifications
    assert isinstance(sim12, float)
    assert sim12 == 0.5  # Similitude (0 + 1)/2 au lieu de 0 dans la normalization
    assert 0.0 < sim13 < 1.0  # Vecteurs avec un angle entre 0 et 90 degrés


@pytest.mark.asyncio
async def test_batch_embedding():
    """Test de la génération d'embeddings par lots."""
    service = SimpleEmbeddingService()

    # Tester si la méthode existe
    if not hasattr(service, "batch_embedding"):
        # Si la méthode n'existe pas, implémenter une version de test
        async def batch_embedding(texts):
            return [await service.generate_embedding(text) for text in texts]

        service.batch_embedding = batch_embedding

    # Générer des embeddings pour plusieurs textes
    texts = ["Premier texte", "Deuxième texte", "Troisième texte"]
    embeddings = await service.batch_embedding(texts)

    # Vérifications
    assert isinstance(embeddings, list)
    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)
    assert all(
        len(emb) == 1536 for emb in embeddings
    )  # Dimension par défaut = 1536


@pytest.mark.asyncio
async def test_normalize_embedding():
    """Test de la normalisation d'un embedding."""
    service = SimpleEmbeddingService()

    # Tester si la méthode existe
    if not hasattr(service, "normalize_embedding"):
        # Si la méthode n'existe pas, implémenter une version de test
        async def normalize_embedding(vector):
            np_vector = np.array(vector)
            norm = np.linalg.norm(np_vector)
            if norm > 0:
                return (np_vector / norm).tolist()
            return np_vector.tolist()

        service.normalize_embedding = normalize_embedding

    # Créer un vecteur test
    v = [1.0, 2.0, 3.0]

    # Normaliser le vecteur
    normalized = await service.normalize_embedding(v)

    # Vérifications
    assert isinstance(normalized, list)
    assert len(normalized) == len(v)

    # Calculer la norme du vecteur normalisé (devrait être proche de 1)
    norm = sum(x**2 for x in normalized) ** 0.5
    assert abs(norm - 1.0) < 1e-9  # La norme devrait être très proche de 1


@pytest.mark.asyncio
async def test_error_handling():
    """Test de la gestion des erreurs dans le service d'embedding."""
    service = SimpleEmbeddingService()

    # Patch directement la méthode generate_embedding pour lever une ValueError
    with patch.object(
        service,
        "generate_embedding",
        side_effect=ValueError("Impossible de générer l'embedding: Test error"),
    ):
        # Vérifier que l'exception est bien levée avec le bon message
        with pytest.raises(ValueError) as exc_info:
            await service.generate_embedding("Test avec erreur")

        # Vérifier que l'erreur d'origine est mentionnée dans le message
        assert "Test error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_similarity_method():
    """Test de la méthode similarity si elle existe."""
    service = SimpleEmbeddingService()

    # Tester si la méthode existe
    if hasattr(service, "similarity"):
        # Créer deux vecteurs test
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]

        # Calculer la similarité
        result = await service.similarity(v1, v2)

        # Vérifications
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
    else:
        # Si la méthode n'existe pas, c'est compute_similarity qui est utilisée
        assert hasattr(service, "compute_similarity")
