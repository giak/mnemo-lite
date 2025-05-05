import pytest
from unittest.mock import AsyncMock, patch
import numpy as np
from typing import List, Dict, Any

from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, APIRouter, Body

from interfaces.services import EmbeddingServiceProtocol
from models.embedding_models import EmbeddingRequest, EmbeddingResponse, SimilarityRequest, SimilarityResponse

from main import app

# Créer un router pour les endpoints de test
test_router = APIRouter(prefix="/test", tags=["test"])

# Fonction pour récupérer le service mocké
def get_test_embedding_service() -> EmbeddingServiceProtocol:
    """Retourne le mock du service d'embedding pour les tests."""
    return app.state.mock_embedding_service

@test_router.post("/embedding", response_model=EmbeddingResponse)
async def test_generate_embedding(
    request: EmbeddingRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_test_embedding_service)
):
    embedding = await embedding_service.generate_embedding(request.text)
    return EmbeddingResponse(
        embedding=embedding,
        dimension=len(embedding),
        model="test-model"
    )

@test_router.post("/similarity", response_model=SimilarityResponse)
async def endpoint_compute_similarity(
    request: SimilarityRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_test_embedding_service)
):
    """
    Endpoint de test pour calculer la similarité entre deux textes.
    Simule un endpoint réel utilisant le protocole de service pour les tests.
    """
    embedding1 = await embedding_service.generate_embedding(request.text1)
    embedding2 = await embedding_service.generate_embedding(request.text2)
    similarity = await embedding_service.compute_similarity(embedding1, embedding2)
    
    return SimilarityResponse(
        similarity=similarity,
        model="test-model"
    )

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
    response = client.post(
        "/test/embedding",
        json={"text": test_text}
    )
    
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
    response = client.post(
        "/test/similarity",
        json={"text1": text1, "text2": text2}
    )
    
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