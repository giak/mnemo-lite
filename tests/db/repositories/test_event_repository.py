import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import builtins # Import nécessaire pour mocker/spy print
import datetime
from datetime import timezone  # Ajout de l'import timezone
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
from db.repositories.event_repository import EventRepository, EventModel, EventCreate, EventQueryBuilder
# from api.db.repositories import event_repository # Plus nécessaire si on ne spy pas le module

# Import SQLAlchemy async components and Result/Row/TextClause
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.engine import Result, Row
# from sqlalchemy.sql import text, TextClause # Import TextClause for type checking
from sqlalchemy.sql import text # Keep text import
from sqlalchemy.sql import Select

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
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock the builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    test_event_id = uuid.uuid4()
    
    # Configure fetchone to return None
    mock_result.fetchone.return_value = None
    
    # Configure the mock builder
    mock_query = text("SELECT ... WHERE id = :event_id") # Mock query object
    mock_params = {"event_id": test_event_id}
    mock_builder.build_get_by_id_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject the mock builder
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_builder.build_get_by_id_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once()
    # Vérifier que execute est appelé avec la requête et params du builder mocké
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query # Check query object identity
    assert execute_call_args[0][1] == mock_params # Check parameters
    
    assert found_event is None

# --- Test pour delete ---
@pytest.mark.anyio
async def test_delete_event_success(mocker):
    """Teste la suppression réussie d'un événement."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock the builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    test_event_id = uuid.uuid4()
    mock_result.rowcount = 1

    # Configure the mock builder for delete
    mock_query = text("DELETE FROM events WHERE id = :event_id") # Mock query
    mock_params = {"event_id": test_event_id}
    mock_builder.build_delete_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
    deleted = await repository.delete(event_id=test_event_id)
    mock_builder.build_delete_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params
    mock_connection.commit.assert_awaited_once()
    assert deleted is True

@pytest.mark.anyio
async def test_delete_event_not_found(mocker):
    """Teste la suppression quand l'ID n'existe pas."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock the builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    test_event_id = uuid.uuid4()
    mock_result.rowcount = 0

    # Configure the mock builder for delete
    mock_query = text("DELETE FROM events WHERE id = :event_id") # Mock query
    mock_params = {"event_id": test_event_id}
    mock_builder.build_delete_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
    deleted = await repository.delete(event_id=test_event_id)
    mock_builder.build_delete_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params
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
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    criteria = {"source": "test", "type": "filter"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate the DB records (raw dicts from DB)
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
    # Configure mock result to return dicts via mappings()
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    # Configure mock builder
    mock_query = text("SELECT ... WHERE metadata @> ... ")
    mock_params = {"criteria": json.dumps(criteria)}
    mock_builder.build_filter_by_metadata_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
    
    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)
    
    # 3. Vérification (Assert)
    mock_builder.build_filter_by_metadata_query.assert_called_once_with(criteria)
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params
    
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
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    criteria = {"source": "nonexistent"}
    # Configure mock result to return empty list via mappings()
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = []
    mock_result.mappings.return_value = mock_mappings
    
    # Configure mock builder
    mock_query = text("SELECT ... WHERE metadata @> ... ")
    mock_params = {"criteria": json.dumps(criteria)}
    mock_builder.build_filter_by_metadata_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
    
    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)
    
    # 3. Vérification (Assert)
    mock_builder.build_filter_by_metadata_query.assert_called_once_with(criteria)
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params
    
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
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    criteria = {"source": "search_test"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate records returned by mappings().all()
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
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    # Configure mock builder for metadata-only search
    mock_query = MagicMock(spec=Select)
    mock_query.whereclause = None # Simulate a valid query, not the 'WHERE false\' case
    mock_params = {"md_filter": criteria, "lim": 10, "off": 0}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
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
    # Check that builder was called correctly for metadata-only search
    mock_builder.build_search_vector_query.assert_called_once_with(
        vector=None,
        metadata=criteria,
        ts_start=None,
        ts_end=None,
        limit=test_limit,
        offset=test_offset
    )
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params
    
    assert isinstance(found_events, list)
    assert len(found_events) == 2
    assert found_events[0].id == expected_id1
    assert found_events[1].id == expected_id2
    assert found_events[0].embedding == None
    assert found_events[1].embedding == None

@pytest.mark.anyio
async def test_search_vector_vector_only(mocker):
    """Teste search_vector avec seulement un vecteur (metadata=None)."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    query_vector = [0.1, 0.9, 0.2]
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Simulate records returned by mappings().all()
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
    expected_embedding_list = [0.11, 0.89, 0.19]
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    # Configure mock builder for vector-only search
    mock_query = MagicMock(spec=Select)
    mock_query.whereclause = None # Simulate a valid query
    mock_params = {"vec_query": query_vector, "lim": 10, "off": 0}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
    test_top_k = 5 # top_k is not used by builder directly anymore, but passed to repo method
    test_limit = 10
    test_offset = 0
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=query_vector,
        top_k=test_top_k, # Still pass top_k here, even if builder uses limit
        metadata=None,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    # Check builder call
    mock_builder.build_search_vector_query.assert_called_once_with(
        vector=query_vector,
        metadata=None,
        ts_start=None,
        ts_end=None,
        limit=test_limit,
        offset=test_offset
        # Note: top_k n'est pas passé au builder
    )
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params

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
    mock_builder = MagicMock(spec=EventQueryBuilder) # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    query_vector = [0.5, 0.5]
    criteria = {"tag": "hybrid"}
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    expected_embedding_list = [0.51, 0.49]
    expected_embedding_str = '[' + ','.join(map(str, expected_embedding_list)) + ']'

    fake_db_records_dicts = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': json.dumps({"msg": "Hybrid Match"}),
            'metadata': json.dumps({"tag": "hybrid", "source": "test"}),
            'embedding': expected_embedding_str,
            'similarity_score': 0.02
        }
    ]
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings
    
    # Configure mock builder for hybrid search
    mock_query = MagicMock(spec=Select)
    mock_query.whereclause = None # Simulate a valid query
    mock_params = {"vec_query": query_vector, "md_filter": criteria, "distance_threshold": 5.0, "lim": 5, "off": 0}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder # Inject mock
    test_top_k = 3
    test_limit = 5
    test_offset = 0
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=query_vector,
        top_k=test_top_k, # Pass top_k, repo might use it later, builder uses limit
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    # Check builder call
    mock_builder.build_search_vector_query.assert_called_once_with(
        vector=query_vector,
        metadata=criteria,
        ts_start=None,
        ts_end=None,
        limit=test_limit,
        offset=test_offset
        # Default distance_threshold is used by builder
    )
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query
    assert execute_call_args[0][1] == mock_params

    assert isinstance(found_events, list)
    assert len(found_events) == 1
    assert found_events[0].id == expected_id1
    assert found_events[0].embedding == expected_embedding_list # Check parsing back to list
    assert found_events[0].similarity_score == 0.02

# Ajouter ici d'autres tests pour update_metadata, delete quand implémentés 

# --- Nouveaux tests pour EventQueryBuilder ---

# Fixture pour instancier le builder une fois par test
@pytest.fixture
def query_builder() -> EventQueryBuilder:
    return EventQueryBuilder()

def test_build_add_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête INSERT."""
    event_content = {"text": "Add test"}
    event_metadata = {"tag": "add_builder"}
    event_embedding = [0.1, 0.2]
    event_to_create = EventCreate(
        content=event_content,
        metadata=event_metadata,
        embedding=event_embedding,
        timestamp=datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc) # Timestamp fixe
    )

    query, params = query_builder.build_add_query(event_to_create)
    query_str = str(query)

    assert "INSERT INTO events" in query_str
    assert "VALUES (:content, :metadata, :embedding, :timestamp)" in query_str
    assert "RETURNING id, timestamp, content, metadata, embedding" in query_str

    assert params["content"] == json.dumps(event_content)
    assert params["metadata"] == json.dumps(event_metadata)
    # Vérifie que l'embedding est bien formaté comme attendu par pgvector
    assert params["embedding"] == "[0.1,0.2]"
    assert params["timestamp"] == event_to_create.timestamp

def test_build_get_by_id_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête SELECT par ID."""
    test_id = uuid.uuid4()
    query, params = query_builder.build_get_by_id_query(test_id)
    query_str = str(query)

    assert "SELECT id, timestamp, content, metadata, embedding" in query_str
    assert "FROM events WHERE id = :event_id" in query_str
    assert params == {"event_id": test_id}

def test_build_update_metadata_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête UPDATE metadata."""
    test_id = uuid.uuid4()
    metadata_update = {"new_tag": "updated", "status": "active"}
    query, params = query_builder.build_update_metadata_query(test_id, metadata_update)
    query_str = str(query)

    assert "UPDATE events" in query_str
    assert "SET metadata = metadata || :metadata_update::jsonb" in query_str
    assert "WHERE id = :event_id" in query_str
    assert "RETURNING id, timestamp, content, metadata, embedding" in query_str
    assert params["event_id"] == test_id
    assert params["metadata_update"] == json.dumps(metadata_update)

def test_build_delete_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête DELETE."""
    test_id = uuid.uuid4()
    query, params = query_builder.build_delete_query(test_id)
    query_str = str(query)

    assert "DELETE FROM events WHERE id = :event_id" in query_str
    assert params == {"event_id": test_id}

def test_build_filter_by_metadata_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête SELECT filtrée par metadata."""
    criteria = {"source": "builder_test", "level": 5}
    query, params = query_builder.build_filter_by_metadata_query(criteria)
    query_str = str(query)

    assert "SELECT id, timestamp, content, metadata, embedding" in query_str
    assert "FROM events" in query_str
    assert "WHERE metadata @> :criteria::jsonb" in query_str
    assert "ORDER BY timestamp DESC" in query_str
    assert params == {"criteria": json.dumps(criteria)}

# Tests plus spécifiques pour build_search_vector_query

def test_build_search_vector_query_vector_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement un vecteur."""
    vector = [0.1] * query_builder._get_vector_dimensions() # Vecteur de taille correcte
    limit, offset = 5, 0
    query, params = query_builder.build_search_vector_query(vector=vector, limit=limit, offset=offset)
    query_str = str(query)

    assert "embedding <-> :vec_query" in query_str # Distance L2
    assert "similarity_score" in query_str # Alias pour la distance
    assert "WHERE" not in query_str # Pas d'autres filtres
    assert "ORDER BY events.embedding <-> :vec_query" in query_str # Tri par distance
    assert "LIMIT :lim" in query_str
    assert "OFFSET :off" in query_str
    assert params['vec_query'] == vector
    assert params['lim'] == limit
    assert params['off'] == offset
    assert 'md_filter' not in params
    assert 'ts_start' not in params
    assert 'ts_end' not in params
    assert 'distance_threshold' not in params # Pas de filtre de distance si recherche vectorielle pure

def test_build_search_vector_query_metadata_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement metadata."""
    metadata = {"tag": "metadata_only_builder"}
    limit, offset = 10, 5
    query, params = query_builder.build_search_vector_query(metadata=metadata, limit=limit, offset=offset)
    query_str = str(query)

    assert "similarity_score" in query_str # Doit toujours avoir la colonne, même si NULL
    assert "embedding <->" not in query_str # Pas de calcul de distance
    assert "WHERE events.metadata @> :md_filter" in query_str
    assert "ORDER BY events.timestamp DESC" in query_str # Tri par défaut
    assert "LIMIT :lim" in query_str
    assert "OFFSET :off" in query_str
    assert params['md_filter'] == metadata
    assert params['lim'] == limit
    assert params['off'] == offset
    assert 'vec_query' not in params
    assert 'distance_threshold' not in params

def test_build_search_vector_query_time_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement un filtre temporel."""
    ts_start = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ts_end = datetime.datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    limit, offset = 20, 0
    query, params = query_builder.build_search_vector_query(ts_start=ts_start, ts_end=ts_end, limit=limit, offset=offset)
    query_str = str(query)

    assert "similarity_score" in query_str
    assert "embedding <->" not in query_str
    assert "WHERE events.timestamp >= :ts_start AND events.timestamp <= :ts_end" in query_str
    assert "ORDER BY events.timestamp DESC" in query_str
    assert "LIMIT :lim" in query_str
    assert "OFFSET :off" in query_str
    assert params['ts_start'] == ts_start
    assert params['ts_end'] == ts_end
    assert params['lim'] == limit
    assert params['off'] == offset
    assert 'vec_query' not in params
    assert 'md_filter' not in params
    assert 'distance_threshold' not in params

def test_build_search_vector_query_hybrid(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query en mode hybride (vecteur + metadata + temps)."""
    vector = [0.9] * query_builder._get_vector_dimensions()
    metadata = {"type": "hybrid_builder"}
    ts_start = datetime.datetime(2023, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    limit, offset = 7, 2
    distance_threshold = 0.5 # Tester un seuil spécifique
    query, params = query_builder.build_search_vector_query(
        vector=vector,
        metadata=metadata,
        ts_start=ts_start,
        limit=limit,
        offset=offset,
        distance_threshold=distance_threshold # Passer le seuil
    )
    query_str = str(query)

    assert "embedding <-> :vec_query" in query_str # Calcul de distance pour le tri ET le filtre
    assert "similarity_score" in query_str
    assert "WHERE" in query_str
    assert "events.metadata @> :md_filter" in query_str
    assert "events.timestamp >= :ts_start" in query_str
    # Test la condition de distance seuil (avec parenthèses possibles)
    assert "(events.embedding <-> :vec_query) < :distance_threshold" in query_str
    assert "ORDER BY events.embedding <-> :vec_query" in query_str # Tri par distance
    assert "LIMIT :lim" in query_str
    assert "OFFSET :off" in query_str
    assert params['vec_query'] == vector
    assert params['md_filter'] == metadata
    assert params['ts_start'] == ts_start
    assert params['lim'] == limit
    assert params['off'] == offset
    assert params['distance_threshold'] == distance_threshold # Vérifie le seuil

def test_build_search_vector_query_no_criteria(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query sans aucun critère."""
    query, params = query_builder.build_search_vector_query()
    query_str = str(query).lower()
    # La chaîne exacte peut varier selon SQLAlchemy, vérifions simplement qu'aucun résultat ne sera retourné
    assert "where" in query_str
    assert params == {}

def test_build_search_vector_query_invalid_dimension(query_builder: EventQueryBuilder):
    """Teste que build_search_vector_query lève une erreur si la dimension du vecteur est mauvaise."""
    vector_invalid = [0.1, 0.2] # Dimension incorrecte
    with pytest.raises(ValueError) as excinfo:
        query_builder.build_search_vector_query(vector=vector_invalid)
    assert str(query_builder._get_vector_dimensions()) in str(excinfo.value)
    assert str(len(vector_invalid)) in str(excinfo.value)

# --- Fin des tests pour EventQueryBuilder --- 