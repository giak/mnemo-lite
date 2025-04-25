import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import asyncpg
import builtins # Import nécessaire pour mocker/spy print
import datetime
import json

# Import de la classe à tester (adapter le chemin si nécessaire)
# Assumons que le PYTHONPATH est configuré pour que 'api' soit accessible
from api.db.repositories.event_repository import EventRepository, EventModel, EventCreate
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
async def test_add_event_success(mocker):
    """Teste l'ajout réussi d'un événement."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    # Simule l'entrée dans le contexte `async with pool.acquire()`
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    # Données d'événement à créer
    event_content = {"text": "Test event content"}
    event_metadata = {"tag": "test", "source": "pytest"}
    event_embedding = [0.1, 0.2, 0.3]
    event_to_create = EventCreate(
        content=event_content,
        metadata=event_metadata,
        embedding=event_embedding
    )
    
    # Données simulées retournées par fetchrow
    fake_db_id = uuid.uuid4()
    fake_db_timestamp = datetime.datetime.now(datetime.timezone.utc)
    # Simule la sortie pgvector comme une chaîne (cas courant)
    fake_db_embedding_str = json.dumps(event_embedding) 
    
    # Données simulées retournées par fetchrow (maintenant un Dict)
    fake_db_return = {
        'id': fake_db_id,
        'timestamp': fake_db_timestamp,
        'content': event_content,
        'metadata': event_metadata,
        'embedding': fake_db_embedding_str # Simule la sortie str de pgvector
    }
    
    # Configurer fetchrow pour retourner le dictionnaire
    mock_connection.fetchrow.return_value = fake_db_return
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    created_event = await repository.add(event_data=event_to_create)
    
    # 3. Vérification (Assert)
    # Vérifie que fetchrow a été appelé avec les bons arguments
    mock_connection.fetchrow.assert_awaited_once()
    call_args = mock_connection.fetchrow.call_args[0]
    assert call_args[0].strip().startswith("INSERT INTO events")
    assert call_args[1] == json.dumps(event_content)
    assert call_args[2] == json.dumps(event_metadata)
    assert call_args[3] == json.dumps(event_embedding)
    
    # Vérifie que le résultat est du bon type et contient les bonnes données
    assert isinstance(created_event, EventModel)
    assert created_event.id == fake_db_id
    assert created_event.timestamp == fake_db_timestamp
    assert created_event.content == event_content
    assert created_event.metadata == event_metadata
    assert created_event.embedding == event_embedding

@pytest.mark.asyncio
async def test_get_event_by_id_success(mocker):
    """Teste la récupération réussie d'un événement par ID."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    test_event_id = uuid.uuid4()
    expected_content = {"data": "sample"}
    expected_metadata = {"source": "test"}
    expected_embedding = [0.5, 0.6]
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simuler l'enregistrement retourné par la base de données
    fake_db_record = {
        'id': test_event_id,
        'timestamp': expected_timestamp,
        'content': expected_content, # Simule déjà parsé par asyncpg
        'metadata': expected_metadata,
        'embedding': json.dumps(expected_embedding) # Simule str retourné par DB
    }
    
    mock_connection.fetchrow.return_value = fake_db_record
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_connection.fetchrow.assert_awaited_once_with(
        mocker.ANY, # La requête SQL
        test_event_id
    )
    # Vérifier la requête SQL plus précisément si nécessaire
    query_arg = mock_connection.fetchrow.call_args[0][0]
    assert "SELECT id, timestamp, content, metadata, embedding" in query_arg
    assert "FROM events WHERE id = $1" in query_arg
    
    assert isinstance(found_event, EventModel)
    assert found_event.id == test_event_id
    assert found_event.timestamp == expected_timestamp
    assert found_event.content == expected_content
    assert found_event.metadata == expected_metadata
    assert found_event.embedding == expected_embedding

@pytest.mark.asyncio
async def test_get_event_by_id_not_found(mocker):
    """Teste le cas où l'événement n'est pas trouvé par ID."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    test_event_id = uuid.uuid4()
    
    # Configurer fetchrow pour retourner None
    mock_connection.fetchrow.return_value = None
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_connection.fetchrow.assert_awaited_once_with(
        mocker.ANY, # La requête SQL
        test_event_id
    )
    assert found_event is None

# Ajouter ici d'autres tests pour get_by_id, update_metadata, delete quand implémentés
# Exemple:
# @pytest.mark.asyncio
# async def test_get_by_id_not_found():
#     mock_pool = AsyncMock(spec=asyncpg.Pool)
#     # Configure le mock pour retourner None quand fetchrow est appelé
#     mock_connection = AsyncMock()
#     mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
#     mock_connection.fetchrow.return_value = None 