"""
Tests pour les routes de mémoires avec remplacement de dépendances.
Ce fichier illustre l'utilisation du système d'injection de dépendances
pour faciliter les tests en remplaçant les dépendances réelles par des mocks.
"""
import json
import pytest
from uuid import UUID, uuid4
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from api.models.memory_models import Memory, MemoryCreate, MemoryUpdate
from api.interfaces.repositories import MemoryRepositoryProtocol
from api.dependencies import get_memory_repository
from api.routes.memory_routes import router as memory_router

# Classe de mock pour le repository de mémoires
class MockMemoryRepository:
    """Implémentation mock du repository de mémoires pour les tests."""
    
    def __init__(self):
        """Initialise le repository mock avec quelques données de test."""
        self.memories = {}
    
    async def add(self, memory: MemoryCreate) -> Memory:
        """Ajoute une mémoire mock."""
        memory_id = uuid4()
        memory_dict = memory.dict()
        memory_obj = Memory(
            id=memory_id,
            timestamp="2023-01-01T12:00:00Z",
            **memory_dict
        )
        self.memories[str(memory_id)] = memory_obj
        return memory_obj
    
    async def get_by_id(self, memory_id: UUID) -> Optional[Memory]:
        """Récupère une mémoire mock par son ID."""
        return self.memories.get(str(memory_id))
    
    async def update(self, memory_id: UUID, memory_update: MemoryUpdate) -> Optional[Memory]:
        """Met à jour une mémoire mock."""
        memory = self.memories.get(str(memory_id))
        if not memory:
            return None
        
        update_data = memory_update.dict(exclude_unset=True)
        updated_memory = memory.copy(update=update_data)
        self.memories[str(memory_id)] = updated_memory
        return updated_memory
    
    async def delete(self, memory_id: UUID) -> bool:
        """Supprime une mémoire mock."""
        if str(memory_id) in self.memories:
            del self.memories[str(memory_id)]
            return True
        return False
    
    async def list_memories(
        self, 
        limit: int = 10, 
        offset: int = 0,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Memory]:
        """Liste les mémoires mock avec filtrage optionnel."""
        memories = list(self.memories.values())
        
        # Appliquer le filtrage si nécessaire
        if metadata_filter:
            filtered_memories = []
            for memory in memories:
                metadata = memory.metadata or {}
                match = True
                for key, value in metadata_filter.items():
                    if key not in metadata or metadata[key] != value:
                        match = False
                        break
                if match:
                    filtered_memories.append(memory)
            memories = filtered_memories
        
        # Appliquer pagination
        return memories[offset:offset + limit]


# Fixture pour l'application FastAPI avec dépendances remplacées
@pytest.fixture
def app():
    """Crée une instance de FastAPI pour les tests avec des dépendances mockées."""
    app = FastAPI()
    app.include_router(memory_router)
    
    # Créer une instance de notre mock repository
    mock_repo = MockMemoryRepository()
    
    # Remplacer la dépendance avec notre mock
    app.dependency_overrides[get_memory_repository] = lambda: mock_repo
    
    return app, mock_repo


@pytest.fixture
def client(app):
    """Crée un client de test pour l'application FastAPI."""
    app_instance, _ = app
    return TestClient(app_instance)


# Tests pour les routes de mémoires
def test_create_memory(client, app):
    """Teste la création d'une mémoire."""
    _, mock_repo = app
    
    memory_data = {
        "content": "Test memory content",
        "metadata": {"type": "test", "tag": "unittest"}
    }
    
    response = client.post("/v1/memories/", json=memory_data)
    
    assert response.status_code == 201
    assert "id" in response.json()
    assert response.json()["content"] == memory_data["content"]
    assert response.json()["metadata"] == memory_data["metadata"]
    
    # Vérifier que la mémoire a bien été ajoutée au repository mock
    assert len(mock_repo.memories) == 1


def test_get_memory(client, app):
    """Teste la récupération d'une mémoire par son ID."""
    _, mock_repo = app
    
    # Créer d'abord une mémoire
    memory_data = {
        "content": "Test memory content",
        "metadata": {"type": "test", "tag": "unittest"}
    }
    
    create_response = client.post("/v1/memories/", json=memory_data)
    memory_id = create_response.json()["id"]
    
    # Récupérer la mémoire
    get_response = client.get(f"/v1/memories/{memory_id}")
    
    assert get_response.status_code == 200
    assert get_response.json()["id"] == memory_id
    assert get_response.json()["content"] == memory_data["content"]


def test_update_memory(client, app):
    """Teste la mise à jour d'une mémoire."""
    _, mock_repo = app
    
    # Créer d'abord une mémoire
    memory_data = {
        "content": "Test memory content",
        "metadata": {"type": "test", "tag": "unittest"}
    }
    
    create_response = client.post("/v1/memories/", json=memory_data)
    memory_id = create_response.json()["id"]
    
    # Mettre à jour la mémoire
    update_data = {
        "content": "Updated memory content",
        "metadata": {"type": "test", "tag": "updated"}
    }
    
    update_response = client.put(f"/v1/memories/{memory_id}", json=update_data)
    
    assert update_response.status_code == 200
    assert update_response.json()["id"] == memory_id
    assert update_response.json()["content"] == update_data["content"]
    assert update_response.json()["metadata"] == update_data["metadata"]


def test_delete_memory(client, app):
    """Teste la suppression d'une mémoire."""
    _, mock_repo = app
    
    # Créer d'abord une mémoire
    memory_data = {
        "content": "Test memory content",
        "metadata": {"type": "test", "tag": "unittest"}
    }
    
    create_response = client.post("/v1/memories/", json=memory_data)
    memory_id = create_response.json()["id"]
    
    # Vérifier que la mémoire existe
    get_response = client.get(f"/v1/memories/{memory_id}")
    assert get_response.status_code == 200
    
    # Supprimer la mémoire
    delete_response = client.delete(f"/v1/memories/{memory_id}")
    assert delete_response.status_code == 204
    
    # Vérifier que la mémoire n'existe plus
    get_response_after = client.get(f"/v1/memories/{memory_id}")
    assert get_response_after.status_code == 404


def test_list_memories(client, app):
    """Teste la liste des mémoires avec filtrage."""
    _, mock_repo = app
    
    # Créer plusieurs mémoires
    client.post("/v1/memories/", json={"content": "Memory 1", "metadata": {"type": "type1"}})
    client.post("/v1/memories/", json={"content": "Memory 2", "metadata": {"type": "type1"}})
    client.post("/v1/memories/", json={"content": "Memory 3", "metadata": {"type": "type2"}})
    
    # Récupérer toutes les mémoires
    response = client.get("/v1/memories/")
    assert response.status_code == 200
    assert len(response.json()) == 3
    
    # Filtrer par type
    response = client.get("/v1/memories/?memory_type=type1")
    assert response.status_code == 200
    assert len(response.json()) == 2
    
    # Tester la pagination
    response = client.get("/v1/memories/?limit=1&offset=1")
    assert response.status_code == 200
    assert len(response.json()) == 1 