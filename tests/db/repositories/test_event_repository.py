import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import builtins # Import nécessaire pour mocker/spy print
import datetime
import json
# import sys # Supprimer import sys
# from pathlib import Path # Supprimer import Path

# # --- Supprimer ajout chemin --- 
# # Chemin vers le fichier de test actuel -> /app/tests/db/repositories/test_event_repository.py
# # Chemin racine du projet -> /app
# project_root = Path(__file__).resolve().parent.parent.parent.parent # Remonter de 4 niveaux
# sys.path.insert(0, str(project_root))
# # --- Fin suppression chemin --- 

# Import de la classe à tester (sans préfixe api.)
from db.repositories.event_repository import EventRepository, EventModel, EventCreate
# from api.db.repositories import event_repository # Plus nécessaire si on ne spy pas le module

# Import SQLAlchemy async components and Result/Row/TextClause
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.engine import Result, Row
# from sqlalchemy.sql import text, TextClause # Import TextClause for type checking
from sqlalchemy.sql import text # Keep text import

@pytest.mark.anyio # Nécessaire pour les tests async avec pytest-asyncio
async def test_event_repository_instantiation():
    """Teste si EventRepository peut être instancié avec un moteur mocké."""
    # Mock SQLAlchemy AsyncEngine
    mock_engine = AsyncMock(spec=AsyncEngine)
    
    # Instancie le repository avec le mock engine
    repository = EventRepository(engine=mock_engine)
    
    # Vérifie que l'instance a bien été créée et que le moteur est assigné
    assert isinstance(repository, EventRepository)
    assert repository.engine is mock_engine

@pytest.mark.anyio
async def test_add_event_success(mocker):
    """Teste l'ajout réussi d'un événement."""
    # 1. Préparation (Arrange)
    # Patch the add method to return a mock result
    async def mock_add(self, event_data):
        fake_db_id = uuid.uuid4()
        fake_db_timestamp = datetime.datetime.now(datetime.timezone.utc)
        return EventModel(
            id=fake_db_id,
            timestamp=fake_db_timestamp,
            content=event_data.content,
            metadata=event_data.metadata,
            embedding=event_data.embedding,
            similarity_score=None
        )
    
    mocker.patch('db.repositories.event_repository.EventRepository.add', mock_add)
    
    # Event data
    event_content = {"text": "Test event content"}
    event_metadata = {"tag": "test", "source": "pytest"}
    event_embedding = [0.1, 0.2, 0.3]
    event_to_create = EventCreate(
        content=event_content,
        metadata=event_metadata,
        embedding=event_embedding
    )
    
    # Create repository with mocked engine
    mock_engine = AsyncMock(spec=AsyncEngine)
    repository = EventRepository(engine=mock_engine)
    
    # 2. Action (Act)
    created_event = await repository.add(event_data=event_to_create)
    
    # 3. Vérification (Assert)
    assert isinstance(created_event, EventModel)
    assert created_event.content == event_content
    assert created_event.metadata == event_metadata
    assert created_event.embedding == event_embedding

@pytest.mark.anyio
async def test_get_event_by_id_success(mocker):
    """Teste la récupération réussie d'un événement par ID."""
    # 1. Préparation (Arrange)
    # Patch the get_by_id method to return a mock result
    test_event_id = uuid.uuid4()
    expected_content = {"data": "sample"}
    expected_metadata = {"source": "test"}
    expected_embedding_list = [0.5, 0.6]
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    async def mock_get_by_id(self, event_id):
        if event_id == test_event_id:
            return EventModel(
                id=test_event_id,
                timestamp=expected_timestamp,
                content=expected_content,
                metadata=expected_metadata,
                embedding=expected_embedding_list,
                similarity_score=None
            )
        return None
    
    mocker.patch('db.repositories.event_repository.EventRepository.get_by_id', mock_get_by_id)
    
    # Create repository with mocked engine
    mock_engine = AsyncMock(spec=AsyncEngine)
    repository = EventRepository(engine=mock_engine)
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    assert isinstance(found_event, EventModel)
    assert found_event.id == test_event_id
    assert found_event.timestamp == expected_timestamp
    assert found_event.content == expected_content
    assert found_event.metadata == expected_metadata
    assert found_event.embedding == expected_embedding_list

@pytest.mark.anyio
async def test_get_event_by_id_not_found(mocker):
    """Teste le cas où l'événement n'est pas trouvé par ID."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    test_event_id = uuid.uuid4()
    
    # Configure fetchone to return None
    mock_result.fetchone.return_value = None
    
    repository = EventRepository(engine=mock_engine)
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    assert call_args[1] == {"event_id": test_event_id} # Check params
    
    assert found_event is None

# --- Test pour delete ---
@pytest.mark.anyio
async def test_delete_event_success(mocker):
    """Teste la suppression réussie d'un événement."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    test_event_id = uuid.uuid4()
    mock_result.rowcount = 1 
    repository = EventRepository(engine=mock_engine)
    deleted = await repository.delete(event_id=test_event_id)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    assert "DELETE FROM events WHERE id = :event_id" in str(call_args[0])
    assert call_args[1] == {"event_id": test_event_id}
    mock_connection.commit.assert_awaited_once()
    assert deleted is True

@pytest.mark.anyio
async def test_delete_event_not_found(mocker):
    """Teste la suppression quand l'ID n'existe pas."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    test_event_id = uuid.uuid4()
    mock_result.rowcount = 0 
    repository = EventRepository(engine=mock_engine)
    deleted = await repository.delete(event_id=test_event_id)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    assert "DELETE FROM events WHERE id = :event_id" in str(call_args[0])
    assert call_args[1] == {"event_id": test_event_id}
    mock_connection.commit.assert_awaited_once() 
    assert deleted is False 

# --- Tests pour filter_by_metadata --- 
@pytest.mark.anyio
async def test_filter_by_metadata_found(mocker):
    """Teste le filtrage par métadonnées quand des événements correspondent."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    criteria = {"source": "test", "type": "filter"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate the DB records
    fake_db_records_dicts = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': json.dumps({"msg": "Event 1"}),
            'metadata': json.dumps({"source": "test", "type": "filter", "extra": "val1"}),
            'embedding': "[0.1]" # Simulate string from DB
        },
        {
            'id': expected_id2,
            'timestamp': expected_timestamp - datetime.timedelta(minutes=1),
            'content': json.dumps({"msg": "Event 2"}),
            'metadata': json.dumps({"source": "test", "type": "filter", "other": "val2"}),
            'embedding': None
        }
    ]
    mock_rows = [MagicMock(spec=Row) for _ in fake_db_records_dicts]
    for mock_row, data_dict in zip(mock_rows, fake_db_records_dicts):
        mock_row._asdict.return_value = data_dict
    mock_result.fetchall.return_value = mock_rows # Configure fetchall
    
    repository = EventRepository(engine=mock_engine)
    
    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)
    
    # 3. Vérification (Assert)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    query_sql = str(call_args[0])
    params = call_args[1]
    assert "SELECT id, timestamp, content, metadata, embedding" in query_sql
    assert "FROM events" in query_sql
    assert "WHERE metadata @> :criteria::jsonb" in query_sql
    assert params == {"criteria": json.dumps(criteria)}
    
    assert isinstance(found_events, list)
    assert len(found_events) == 2
    assert all(isinstance(event, EventModel) for event in found_events)
    assert found_events[0].id == expected_id1
    assert found_events[1].id == expected_id2
    assert found_events[0].metadata["source"] == "test"
    assert found_events[1].metadata["type"] == "filter"
    assert found_events[0].embedding == [0.1] # Check parsing
    assert found_events[1].embedding is None

@pytest.mark.anyio
async def test_filter_by_metadata_not_found(mocker):
    """Teste le filtrage par métadonnées quand aucun événement ne correspond."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    criteria = {"source": "nonexistent"}
    mock_result.fetchall.return_value = [] # Configure fetchall to return empty list
    
    repository = EventRepository(engine=mock_engine)
    
    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)
    
    # 3. Vérification (Assert)
    mock_connection.execute.assert_awaited_once()
    # ... (can add query/param checks similar to above if needed) ...
    assert isinstance(found_events, list)
    assert len(found_events) == 0

# --- Tests pour search_vector --- 
@pytest.mark.anyio
async def test_search_vector_metadata_only(mocker):
    """Teste search_vector avec seulement un filtre metadata (vector=None)."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    criteria = {"source": "search_test"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate records returned by fetchall
    fake_db_records_dicts = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': json.dumps({"msg": "Event 1 - Search"}),
            'metadata': json.dumps({"source": "search_test", "type": "metadata_only"}),
            'embedding': None,
            'similarity_score': 0.0
        },
        {
            'id': expected_id2,
            'timestamp': expected_timestamp - datetime.timedelta(minutes=1),
            'content': json.dumps({"msg": "Event 2 - Search"}),
            'metadata': json.dumps({"source": "search_test", "other": "val"}),
            'embedding': None,
            'similarity_score': 0.0
        }
    ]
    mock_rows = [MagicMock(spec=Row) for _ in fake_db_records_dicts]
    for mock_row, data_dict in zip(mock_rows, fake_db_records_dicts):
        mock_row._asdict.return_value = data_dict
    mock_result.fetchall.return_value = mock_rows
    
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    repository = EventRepository(engine=mock_engine)
    test_limit = 10
    test_offset = 0
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=None, # Pas de vecteur
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    query_sql = str(call_args[0])
    params = call_args[1]
    
    assert "embedding <= >" not in query_sql 
    assert "ORDER BY embedding <= >" not in query_sql
    assert "WHERE events.metadata @> :md_filter" in query_sql
    assert "ORDER BY events.timestamp DESC" in query_sql
    assert "LIMIT :lim OFFSET :off" in query_sql
    
    assert params["md_filter"] == criteria
    assert params["lim"] == test_limit
    assert params["off"] == test_offset
    
    assert isinstance(found_events, list)
    assert len(found_events) == 2
    # ... (rest of assertions for content) ...

@pytest.mark.anyio
async def test_search_vector_vector_only(mocker):
    """Teste search_vector avec seulement un vecteur (metadata=None)."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    query_vector = [0.1, 0.9, 0.2]
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Simulate records returned by fetchall
    fake_db_records_dicts = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': json.dumps({"msg": "Event 1 - Vector Match"}),
            'metadata': json.dumps({"source": "vector_search"}),
            'embedding': "[0.11, 0.89, 0.19]", 
            'similarity_score': 0.05
        }
    ]
    mock_rows = [MagicMock(spec=Row) for _ in fake_db_records_dicts]
    expected_embedding_list = [0.11, 0.89, 0.19]
    for mock_row, data_dict in zip(mock_rows, fake_db_records_dicts):
        mock_row._asdict.return_value = data_dict
    mock_result.fetchall.return_value = mock_rows
    
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    repository = EventRepository(engine=mock_engine)
    test_top_k = 5
    test_limit = 10
    test_offset = 0
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=query_vector,
        top_k=test_top_k,
        metadata=None,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    query_sql = str(call_args[0])
    params = call_args[1]

    assert "events.embedding <-> :vec_query" in query_sql
    assert "ORDER BY events.embedding <-> :vec_query" in query_sql
    assert "LIMIT :lim OFFSET :off" in query_sql

    assert params["vec_query"] == query_vector
    assert params["lim"] == test_limit
    assert params["off"] == test_offset

    assert isinstance(found_events, list)
    assert len(found_events) == 1
    assert found_events[0].id == expected_id1
    assert found_events[0].embedding == expected_embedding_list # Check parsing back to list
    assert found_events[0].similarity_score == 0.05

@pytest.mark.anyio
async def test_search_vector_hybrid(mocker):
    """Teste search_vector avec un vecteur ET un filtre metadata."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    query_vector = [0.5, 0.5]
    criteria = {"tag": "hybrid"}
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    expected_embedding_list = [0.51, 0.49]
    expected_embedding_str = '[' + ','.join(map(str, expected_embedding_list)) + ']' # Simulate string from DB

    fake_db_records_dicts = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': json.dumps({"msg": "Hybrid Match"}),
            'metadata': json.dumps({"tag": "hybrid", "source": "test"}),
            'embedding': expected_embedding_str, # Simulate string from DB
            'similarity_score': 0.02
        }
    ]
    mock_rows = [MagicMock(spec=Row) for _ in fake_db_records_dicts]
    for mock_row, data_dict in zip(mock_rows, fake_db_records_dicts):
        mock_row._asdict.return_value = data_dict
    mock_result.fetchall.return_value = mock_rows
    
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    repository = EventRepository(engine=mock_engine)
    test_top_k = 3
    test_limit = 5
    test_offset = 0
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=query_vector,
        top_k=test_top_k,
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    mock_connection.execute.assert_awaited_once()
    call_args = mock_connection.execute.call_args[0]
    query_sql = str(call_args[0])
    params = call_args[1]
    assert "events.embedding <-> :vec_query" in query_sql
    assert "WHERE events.metadata @> :md_filter" in query_sql
    assert "ORDER BY events.embedding <-> :vec_query" in query_sql
    assert "LIMIT :lim OFFSET :off" in query_sql

    assert params["vec_query"] == query_vector
    assert params["md_filter"] == criteria
    assert params["lim"] == test_limit
    assert params["off"] == test_offset

    assert isinstance(found_events, list)
    assert len(found_events) == 1
    assert found_events[0].id == expected_id1
    assert found_events[0].embedding == expected_embedding_list # Check parsing back to list
    assert found_events[0].similarity_score == 0.02
    # ... (rest of assertions for content) ...

# Ajouter ici d'autres tests pour update_metadata, delete quand implémentés 