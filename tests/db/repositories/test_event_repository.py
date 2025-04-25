import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import asyncpg
import builtins # Import nécessaire pour mocker/spy print

# Import de la classe à tester (adapter le chemin si nécessaire)
# Assumons que le PYTHONPATH est configuré pour que 'api' soit accessible
from api.db.repositories.event_repository import EventRepository
# from api.db.repositories import event_repository # Plus nécessaire si on ne spy pas le module

@pytest.mark.asyncio # Nécessaire pour les tests async avec pytest-asyncio
async def test_event_repository_instantiation():
    """Teste si EventRepository peut être instancié avec un pool mocké."""
    # Crée un mock asynchrone pour simuler le pool de connexions asyncpg
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    
    # Instancie le repository avec le mock
    repository = EventRepository(pool=mock_pool)
    
    # Vérifie que l'instance a bien été créée et que le pool est assigné
    assert isinstance(repository, EventRepository)
    assert repository.pool is mock_pool

@pytest.mark.asyncio
async def test_add_event_placeholder(mocker): # mocker est une fixture pytest
    """Teste la méthode add (placeholder actuel)."""
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    repository = EventRepository(pool=mock_pool)
    
    # Crée des données d'événement factices (ajuster selon EventCreate)
    fake_event_data = MagicMock() # Utilise MagicMock pour simuler EventCreate
    
    # Espionne la fonction built-in print
    spy_print = mocker.spy(builtins, 'print')
    
    # Appelle la méthode add
    result = await repository.add(event_data=fake_event_data)
    
    # Vérifie que print a été appelé avec le bon message
    spy_print.assert_called_once_with(f"Placeholder: Adding event with data: {fake_event_data}")
    
    # Vérifie que le résultat est du type attendu (placeholder EventModel)
    # Il faudra importer/définir EventModel correctement
    # assert isinstance(result, EventModel) # Commenté car EventModel est vide

# Ajouter ici d'autres tests pour get_by_id, update_metadata, delete quand implémentés
# Exemple:
# @pytest.mark.asyncio
# async def test_get_by_id_not_found():
#     mock_pool = AsyncMock(spec=asyncpg.Pool)
#     # Configure le mock pour retourner None quand fetchrow est appelé
#     mock_connection = AsyncMock()
#     mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
#     mock_connection.fetchrow.return_value = None 
#     repository = EventRepository(pool=mock_pool)
#     
#     result = await repository.get_by_id(uuid.uuid4())
#     assert result is None 