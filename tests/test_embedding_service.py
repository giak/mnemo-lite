import pytest
from unittest.mock import AsyncMock, patch
import numpy as np
from typing import List, Dict, Any

from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, APIRouter, Body

from interfaces.services import EmbeddingServiceProtocol
from models.embedding_models import EmbeddingRequest, EmbeddingResponse, SimilarityRequest, SimilarityResponse

# Mock du service d'embedding basé sur le protocole
class MockEmbeddingService:
    """Implémentation fictive du EmbeddingServiceProtocol pour les tests."""
    
    def __init__(self):
        self.generate_embedding_mock = AsyncMock()
        self.compute_similarity_mock = AsyncMock()
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Version mockée de la méthode generate_embedding."""
        return await self.generate_embedding_mock(text)
    
    async def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Version mockée de la méthode compute_similarity."""
        return await self.compute_similarity_mock(embedding1, embedding2)

# Création d'un router simple pour tester l'injection
test_router = APIRouter()

# Fonction de dépendance pour injecter notre mock pendant les tests
async def get_test_embedding_service():
    return MockEmbeddingService()

@test_router.post("/test/embedding", response_model=EmbeddingResponse)
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

@test_router.post("/test/similarity", response_model=SimilarityResponse)
async def test_compute_similarity(
    request: SimilarityRequest,
    embedding_service: EmbeddingServiceProtocol = Depends(get_test_embedding_service)
):
    embedding1 = await embedding_service.generate_embedding(request.text1)
    embedding2 = await embedding_service.generate_embedding(request.text2)
    similarity = await embedding_service.compute_similarity(embedding1, embedding2)
    
    return SimilarityResponse(
        similarity=similarity,
        model="test-model",
        text1=request.text1,
        text2=request.text2,
        embedding1=embedding1,
        embedding2=embedding2
    )

# Fixture pour l'application FastAPI avec dépendances mockées
@pytest.fixture
def app_with_mock_service():
    """App avec un service d'embedding mocké injecté."""
    app = FastAPI()
    app.include_router(test_router)
    
    # Création du mock
    mock_service = MockEmbeddingService()
    
    # Remplacer la dépendance avec notre mock
    app.dependency_overrides[get_test_embedding_service] = lambda: mock_service
    
    # Retourner l'app et le mock pour les assertions
    with TestClient(app) as test_client:
        yield test_client, mock_service

# Tests unitaires
def test_generate_embedding_with_protocol_mock(app_with_mock_service):
    """Teste la génération d'un embedding en utilisant un mock basé sur le protocole."""
    client, mock_service = app_with_mock_service
    
    # 1. Préparation
    test_text = "Test text for embedding"
    mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    # Configurer le comportement du mock
    mock_service.generate_embedding_mock.return_value = mock_embedding
    
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
    mock_service.generate_embedding_mock.assert_called_once_with(test_text)

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
    mock_service.generate_embedding_mock.side_effect = [embedding1, embedding2]
    mock_service.compute_similarity_mock.return_value = expected_similarity
    
    # 2. Action
    response = client.post(
        "/test/similarity",
        json={"text1": text1, "text2": text2}
    )
    
    # 3. Vérification
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["similarity"] == expected_similarity
    assert response_data["embedding1"] == embedding1
    assert response_data["embedding2"] == embedding2
    mock_service.compute_similarity_mock.assert_called_once_with(embedding1, embedding2)