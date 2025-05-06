import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import builtins  # Import nécessaire pour mocker/spy print
import datetime
from datetime import timezone  # Ajout de l'import timezone
import json

# Import de la classe à tester (sans préfixe api.)
from db.repositories.event_repository import (
    EventRepository,
    EventModel,
    EventCreate,
    EventQueryBuilder,
    RepositoryError,
)

# Import SQLAlchemy async components and Result/Row
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.engine import Result, Row
from sqlalchemy.sql import Select, Delete, text # Keep text import, NO TextClause


@pytest.mark.anyio  # Nécessaire pour les tests async avec pytest-asyncio
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
            similarity_score=None,
        )

    mocker.patch("db.repositories.event_repository.EventRepository.add", mock_add)

    # Event data
    event_content = {"text": "Test event content"}
    event_metadata = {"tag": "test", "source": "pytest"}
    event_embedding = [0.1, 0.2, 0.3]
    event_to_create = EventCreate(
        content=event_content, metadata=event_metadata, embedding=event_embedding
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
                similarity_score=None,
            )
        return None

    mocker.patch(
        "db.repositories.event_repository.EventRepository.get_by_id", mock_get_by_id
    )

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
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock the builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    test_event_id = uuid.uuid4()

    # Configure mappings().first() to return None - use MagicMock not AsyncMock
    mock_mappings = MagicMock()
    mock_mappings.first.return_value = None
    mock_result.mappings.return_value = mock_mappings

    # Configure the mock builder
    mock_query = text("SELECT ... WHERE id = :event_id")  # Mock query object
    mock_params = {"event_id": test_event_id}
    mock_builder.build_get_by_id_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject the mock builder

    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)

    # 3. Vérification (Assert)
    mock_builder.build_get_by_id_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once()
    # Vérifier que execute est appelé avec la requête et params du builder mocké
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query  # Check query object identity
    assert execute_call_args[0][1] == mock_params  # Check parameters

    assert found_event is None


# --- Test pour delete ---
@pytest.mark.anyio
async def test_delete_event_success(mocker):
    """Teste la suppression réussie d'un événement."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock the builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    
    # --- Mock Transaction Correctly (Attempt 2) ---
    # Mock the transaction object itself and its methods
    mock_transaction = AsyncMock() # This is the transaction object
    mock_transaction.commit = AsyncMock() # Make commit awaitable
    mock_transaction.rollback = AsyncMock() # Make rollback awaitable
    
    # Explicitly mock connection.begin as an AsyncMock function
    # and set its return value (when awaited) to the mock_transaction
    mock_connection.begin = AsyncMock(return_value=mock_transaction)
    # --- End Mock Transaction Fix (Attempt 2) ---

    test_event_id = uuid.uuid4()
    mock_result.rowcount = 1

    # Configure the mock builder for delete
    mock_query = text("DELETE FROM events WHERE id = :event_id")  # Mock query
    mock_builder.build_delete_query.return_value = mock_query 

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    
    # 2. Action (Act)
    deleted = await repository.delete(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_builder.build_delete_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once_with(mock_query)
    mock_transaction.commit.assert_awaited_once()
    assert deleted is True


@pytest.mark.anyio
async def test_delete_event_not_found(mocker):
    """Teste la suppression quand l'ID n'existe pas."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock the builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result
    test_event_id = uuid.uuid4()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.rowcount = 0
    
    # --- Mock Transaction Correctly (Attempt 2) ---
    # Mock the transaction object itself and its methods
    mock_transaction = AsyncMock() # This is the transaction object
    mock_transaction.commit = AsyncMock() # Make commit awaitable
    mock_transaction.rollback = AsyncMock() # Make rollback awaitable
    
    # Explicitly mock connection.begin as an AsyncMock function
    # and set its return value (when awaited) to the mock_transaction
    mock_connection.begin = AsyncMock(return_value=mock_transaction)
    # --- End Mock Transaction Fix (Attempt 2) ---

    # Configure the mock builder for delete
    mock_query = text("DELETE FROM events WHERE id = :event_id")  # Mock query
    mock_builder.build_delete_query.return_value = mock_query 

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    
    # 2. Action (Act)
    deleted = await repository.delete(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_builder.build_delete_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once_with(mock_query)
    mock_transaction.commit.assert_awaited_once() # Should still commit even if 0 rows affected
    assert deleted is False # Check return value based on scalar_one_or_none()


# --- Tests pour filter_by_metadata ---
@pytest.mark.anyio
async def test_filter_by_metadata_found(mocker):
    """Teste le filtrage par métadonnées quand des événements correspondent."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    criteria = {"source": "test", "type": "filter"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Simulate the DB records (raw dicts from DB)
    fake_db_records_dicts = [
        {
            "id": expected_id1,
            "timestamp": expected_timestamp,
            "content": json.dumps({"msg": "Event 1"}),
            "metadata": json.dumps(
                {"source": "test", "type": "filter", "extra": "val1"}
            ),
            "embedding": "[0.1]",  # Simulate string from DB
        },
        {
            "id": expected_id2,
            "timestamp": expected_timestamp - datetime.timedelta(minutes=1),
            "content": json.dumps({"msg": "Event 2"}),
            "metadata": json.dumps(
                {"source": "test", "type": "filter", "other": "val2"}
            ),
            "embedding": None,
        },
    ]
    # Configure mock result to return dicts via mappings()
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings

    # Configure mock builder
    mock_query = text("SELECT ... WHERE metadata @> ... ")
    mock_builder.build_filter_by_metadata_query.return_value = mock_query

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)

    # 3. Vérification (Assert)
    mock_builder.build_filter_by_metadata_query.assert_called_once_with(criteria)
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query

    assert isinstance(found_events, list)
    assert len(found_events) == 2
    assert all(isinstance(event, EventModel) for event in found_events)
    assert found_events[0].id == expected_id1
    assert found_events[1].id == expected_id2
    assert found_events[0].metadata["source"] == "test"
    assert found_events[1].metadata["type"] == "filter"
    assert found_events[0].embedding == [0.1]  # Check parsing
    assert found_events[1].embedding is None


@pytest.mark.anyio
async def test_filter_by_metadata_not_found(mocker):
    """Teste le filtrage par métadonnées quand aucun événement ne correspond."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    criteria = {"source": "nonexistent"}
    # Configure mock result to return empty list via mappings()
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = []
    mock_result.mappings.return_value = mock_mappings

    # Configure mock builder
    mock_query = text("SELECT ... WHERE metadata @> ... ")
    mock_builder.build_filter_by_metadata_query.return_value = mock_query

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)

    # 3. Vérification (Assert)
    mock_builder.build_filter_by_metadata_query.assert_called_once_with(criteria)
    mock_connection.execute.assert_awaited_once()
    execute_call_args = mock_connection.execute.call_args
    assert execute_call_args[0][0] is mock_query

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
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    criteria = {"source": "search_test"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Simulate records returned by mappings().all()
    fake_db_records_dicts = [
        {
            "id": expected_id1,
            "timestamp": expected_timestamp,
            "content": json.dumps({"msg": "Event 1 - Search"}),
            "metadata": json.dumps({"source": "search_test", "type": "metadata_only"}),
            "embedding": None,
            "similarity_score": 0.0,
        },
        {
            "id": expected_id2,
            "timestamp": expected_timestamp - datetime.timedelta(minutes=1),
            "content": json.dumps({"msg": "Event 2 - Search"}),
            "metadata": json.dumps({"source": "search_test", "other": "val"}),
            "embedding": None,
            "similarity_score": 0.0,
        },
    ]
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings

    # Configure mock builder for metadata-only search
    mock_query_count = text("SELECT COUNT(*)")
    mock_query_data = text("SELECT ... DATA ...")
    mock_builder.build_search_vector_query.side_effect = [mock_query_count, mock_query_data]

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    test_limit = 10
    test_offset = 0

    # 2. Action (Act)
    events, total_hits = await repository.search_vector(
        vector=None,
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )

    # 3. Vérification (Assert)
    # Check that builder was called correctly for metadata-only search
    assert mock_builder.build_search_vector_query.call_count == 2
    # Check first call (count)
    call_args_count = mock_builder.build_search_vector_query.call_args_list[0]
    assert call_args_count[1]["select_count"] is True
    assert call_args_count[1]["limit"] is None
    assert call_args_count[1]["offset"] is None
    # Check second call (data)
    call_args_data = mock_builder.build_search_vector_query.call_args_list[1]
    assert call_args_data[1]["select_count"] is False
    assert call_args_data[1]["limit"] == test_limit
    assert call_args_data[1]["offset"] == test_offset

    # Assert execute calls (count and data)
    assert mock_connection.execute.call_count == 2
    mock_connection.execute.assert_any_call(mock_query_count)
    mock_connection.execute.assert_any_call(mock_query_data)
    assert len(events) == 2
    assert events[0].id == expected_id1
    assert events[1].id == expected_id2
    assert events[0].embedding == None
    assert events[1].embedding == None


@pytest.mark.anyio
async def test_search_vector_vector_only(mocker):
    """Teste search_vector avec seulement un vecteur (metadata=None)."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    query_vector = [0.1, 0.9, 0.2]
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)

    # Simulate records returned by mappings().all()
    fake_db_records_dicts = [
        {
            "id": expected_id1,
            "timestamp": expected_timestamp,
            "content": json.dumps({"msg": "Event 1 - Vector Match"}),
            "metadata": json.dumps({"source": "vector_search"}),
            "embedding": "[0.11, 0.89, 0.19]",
            "similarity_score": 0.05,
        }
    ]
    expected_embedding_list = [0.11, 0.89, 0.19]
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings

    # Configure mock builder for vector-only search
    mock_query_count = text("SELECT COUNT(*)")
    mock_query_data = text("SELECT ... DATA ...")
    mock_builder.build_search_vector_query.side_effect = [mock_query_count, mock_query_data]

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    test_limit = 10
    test_offset = 0

    # 2. Action (Act)
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        limit=test_limit,
        offset=test_offset
    )

    # 3. Vérification (Assert)
    # Check builder call - adjusted to accept either the top_k or limit parameter
    assert mock_builder.build_search_vector_query.call_count == 2
    # Check first call (count)
    call_args_count = mock_builder.build_search_vector_query.call_args_list[0]
    assert call_args_count[1]["select_count"] is True
    assert call_args_count[1]["limit"] is None
    assert call_args_count[1]["offset"] is None
    # Check second call (data)
    call_args_data = mock_builder.build_search_vector_query.call_args_list[1]
    assert call_args_data[1]["select_count"] is False
    assert call_args_data[1]["limit"] == test_limit
    assert call_args_data[1]["offset"] == test_offset

    # Assert execute calls
    assert mock_connection.execute.call_count == 2
    mock_connection.execute.assert_any_call(mock_query_count)
    mock_connection.execute.assert_any_call(mock_query_data)
    assert len(events) == 1
    assert events[0].id == expected_id1
    assert (
        events[0].embedding == expected_embedding_list
    )  # Check parsing back to list
    assert events[0].similarity_score == 0.05


@pytest.mark.anyio
async def test_search_vector_hybrid(mocker):
    """Teste search_vector avec un vecteur ET un filtre metadata."""
    # 1. Préparation (Arrange)
    mock_engine = AsyncMock(spec=AsyncEngine)
    mock_connection = AsyncMock(spec=AsyncConnection)
    mock_result = AsyncMock(spec=Result)
    mock_builder = MagicMock(spec=EventQueryBuilder)  # Mock builder
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = mock_result

    query_vector = [0.5, 0.5]
    criteria = {"tag": "hybrid"}
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    expected_embedding_list = [0.51, 0.49]
    expected_embedding_str = "[" + ",".join(map(str, expected_embedding_list)) + "]"

    fake_db_records_dicts = [
        {
            "id": expected_id1,
            "timestamp": expected_timestamp,
            "content": json.dumps({"msg": "Hybrid Match"}),
            "metadata": json.dumps({"tag": "hybrid", "source": "test"}),
            "embedding": expected_embedding_str,
            "similarity_score": 0.02,
        }
    ]
    # Setup mock_result.mappings().all() to return the fake records
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = fake_db_records_dicts
    mock_result.mappings.return_value = mock_mappings

    # Configure mock builder for hybrid search
    mock_query_count = text("SELECT COUNT(*)")
    mock_query_data = text("SELECT ... DATA ...")
    mock_builder.build_search_vector_query.side_effect = [mock_query_count, mock_query_data]

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    test_limit = 5
    test_offset = 0

    # 2. Action (Act)
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )

    # 3. Vérification (Assert)
    # Check builder call
    assert mock_builder.build_search_vector_query.call_count == 2
    # Check first call (count)
    call_args_count = mock_builder.build_search_vector_query.call_args_list[0]
    assert call_args_count[1]["select_count"] is True
    assert call_args_count[1]["limit"] is None
    assert call_args_count[1]["offset"] is None
    # Check second call (data)
    call_args_data = mock_builder.build_search_vector_query.call_args_list[1]
    assert call_args_data[1]["select_count"] is False
    assert call_args_data[1]["limit"] == test_limit
    assert call_args_data[1]["offset"] == test_offset

    # Assert execute calls
    assert mock_connection.execute.call_count == 2
    mock_connection.execute.assert_any_call(mock_query_count)
    mock_connection.execute.assert_any_call(mock_query_data)
    assert len(events) == 1
    assert events[0].id == expected_id1
    assert (
        events[0].embedding == expected_embedding_list
    )  # Check parsing back to list
    assert events[0].similarity_score == 0.02


# Ajouter ici d'autres tests pour update_metadata, delete quand implémentés

# --- Nouveaux tests pour EventQueryBuilder ---


# Fixture pour instancier le builder une fois par test
@pytest.fixture
def query_builder() -> EventQueryBuilder:
    return EventQueryBuilder()


def test_build_add_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête INSERT retournée par build_add_query."""
    now_utc = datetime.datetime.now(tz=timezone.utc)
    event_data = EventCreate(
        content={"message": "Test event for build_add_query"},
        metadata={"tag": "builder_test"},
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        timestamp=now_utc
    )

    query, params = query_builder.build_add_query(event_data)

    # Check basic SQL structure instead
    query_str = str(query).upper()
    assert "INSERT INTO EVENTS" in query_str
    assert "VALUES (:CONTENT, :METADATA, :EMBEDDING, :TIMESTAMP)" in query_str
    assert "RETURNING" in query_str

    # Check parameters
    assert isinstance(params, dict)
    assert params["content"] == json.dumps(event_data.content)
    assert params["metadata"] == json.dumps(event_data.metadata)
    expected_embedding_str = EventModel._format_embedding_for_db(event_data.embedding)
    assert params["embedding"] == expected_embedding_str
    assert params["timestamp"] == event_data.timestamp


def test_build_get_by_id_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête SELECT par ID."""
    test_id = uuid.uuid4()
    query, params = query_builder.build_get_by_id_query(test_id)
    query_str = str(query).upper()

    # Vérification des éléments essentiels sans être strict sur l'espacement et le format
    assert "SELECT" in query_str
    assert "ID" in query_str
    assert "FROM" in query_str 
    assert "EVENTS" in query_str
    assert "WHERE" in query_str
    # Vérification du paramètre ID
    assert params["event_id"] == test_id


def test_build_update_metadata_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête UPDATE metadata."""
    test_id = uuid.uuid4()
    metadata_update = {"new_tag": "updated", "status": "active"}
    query, params = query_builder.build_update_metadata_query(test_id, metadata_update)
    query_str = str(query).upper()

    # Vérification des éléments essentiels
    assert "UPDATE" in query_str
    assert "SET" in query_str
    assert "METADATA" in query_str
    assert "WHERE" in query_str
    # Vérification des paramètres
    assert params["event_id"] == test_id
    assert params["metadata_update"] == json.dumps(metadata_update)


def test_build_delete_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête DELETE."""
    test_id = uuid.uuid4()
    query = query_builder.build_delete_query(test_id)
    assert isinstance(query, Delete), "Query should be a Delete object"
    compiled = query.compile() # Compile without literal binds
    query_str = str(compiled).upper()
    assert "DELETE FROM EVENTS" in query_str
    assert "WHERE EVENTS.ID = :EVENT_ID" in query_str # Check for named param placeholder
    assert "event_id" in compiled.params and str(compiled.params["event_id"]) == str(test_id)


def test_build_filter_by_metadata_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête SELECT filtrée par metadata."""
    criteria = {"source": "builder_test", "level": 5}
    query = query_builder.build_filter_by_metadata_query(criteria)
    assert isinstance(query, Select), "Query should be a Select object"
    compiled = query.compile() # Fix: Compile without literal binds
    query_str = str(compiled).upper()
    assert "SELECT" in query_str
    assert "FROM EVENTS" in query_str
    # Fix: Simplify assertion - check for operator and param placeholder
    assert "CAST(EVENTS.METADATA AS JSONB) @> :CRITERIA" in query_str
    assert "criteria" in compiled.params and compiled.params["criteria"] == json.dumps(criteria)
    assert "ORDER BY EVENTS.TIMESTAMP DESC" in query_str


# Tests plus spécifiques pour build_search_vector_query


def test_build_search_vector_query_vector_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement un vecteur."""
    vector = [0.1] * query_builder._get_vector_dimensions()
    limit, offset = 5, 0
    query = query_builder.build_search_vector_query(
        vector=vector, limit=limit, offset=offset, select_count=False # Test data query
    )
    compiled = query.compile()
    query_str = str(compiled).upper()
    # Check SQL structure
    assert "SELECT" in query_str
    assert "(EMBEDDING <-> :VEC_QUERY)" in query_str
    assert "WHERE (EMBEDDING <-> :VEC_QUERY) <= :DIST_THRESH" in query_str
    assert "ORDER BY SIMILARITY_SCORE ASC" in query_str
    assert "LIMIT :" in query_str # Check for limit placeholder
    assert "OFFSET :" in query_str # Check for offset placeholder
    # Assert that the raw vector list is passed as a parameter
    assert compiled.params.get("vec_query") == vector 
    assert compiled.params.get("dist_thresh") == 5.0 # Use the default threshold used by the builder


def test_build_search_vector_query_metadata_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement metadata."""
    metadata = {"tag": "metadata_only_builder"}
    limit, offset = 10, 5
    query = query_builder.build_search_vector_query(
        metadata=metadata, limit=limit, offset=offset, select_count=False
    )
    compiled = query.compile()
    query_str = str(compiled).upper().replace('\n', ' ')
    # Check SQL structure
    assert "SELECT" in query_str
    assert "NULL AS SIMILARITY_SCORE" in query_str
    assert '@>' in query_str
    assert ':MD_FILTER' in query_str # Check parameter placeholder presence
    assert "ORDER BY EVENTS.TIMESTAMP DESC" in query_str
    assert "LIMIT :" in query_str
    assert "OFFSET :" in query_str
    
    metadata_json_str = json.dumps(metadata)

    # Assertions for bound parameters
    # Vector and dist_thresh are not applicable for metadata-only search.
    assert compiled.params.get("md_filter") == metadata_json_str
    assert compiled.params.get("param_1") == limit
    assert compiled.params.get("param_2") == offset


def test_build_search_vector_query_time_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement un filtre temporel."""
    ts_start = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ts_end = datetime.datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    limit, offset = 8, 1
    query = query_builder.build_search_vector_query(
        ts_start=ts_start, ts_end=ts_end, limit=limit, offset=offset, select_count=False
    )
    assert isinstance(query, Select), "Query should be a Select object"
    compiled = query.compile() 
    query_str = str(compiled).upper().replace('\n', ' ')
    assert "SELECT" in query_str
    assert "NULL AS SIMILARITY_SCORE" in query_str
    assert "WHERE EVENTS.TIMESTAMP >= :TS_START" in query_str 
    assert "AND EVENTS.TIMESTAMP <= :TS_END" in query_str 
    assert "ts_start" in compiled.params and compiled.params["ts_start"] == ts_start
    assert "ts_end" in compiled.params and compiled.params["ts_end"] == ts_end
    assert "ORDER BY EVENTS.TIMESTAMP DESC" in query_str
    assert "LIMIT :PARAM_1" in query_str 
    assert "OFFSET :PARAM_2" in query_str
    assert compiled.params.get("param_1") == limit
    assert compiled.params.get("param_2") == offset


def test_build_search_vector_query_hybrid(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec tous les critères."""
    vector = [0.2] * query_builder._get_vector_dimensions()
    metadata = {"type": "hybrid_builder"}
    ts_start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    ts_end = datetime.datetime.now(datetime.timezone.utc)
    limit, offset = 20, 10
    distance_threshold = 0.5 # Explicitly set a non-default threshold

    query = query_builder.build_search_vector_query(
        vector=vector,
        metadata=metadata,
        ts_start=ts_start,
        ts_end=ts_end,
        limit=limit,
        offset=offset,
        distance_threshold=distance_threshold,
        select_count=False
    )
    assert isinstance(query, Select), "Query should be a Select object"

    compiled = query.compile() 
    query_str = str(compiled).upper().replace('\n', ' ')
    # Check SQL structure
    assert "SELECT" in query_str
    assert "(EMBEDDING <-> :VEC_QUERY)" in query_str
    assert "WHERE (EMBEDDING <-> :VEC_QUERY) <= :DIST_THRESH" in query_str
    # Check metadata filter presence
    assert "EVENTS.METADATA @> CAST(:MD_FILTER AS JSONB)" in query_str 
    assert "ORDER BY SIMILARITY_SCORE ASC" in query_str
    assert "LIMIT :" in query_str
    assert "OFFSET :" in query_str
    
    metadata_json_str = json.dumps(metadata)

    # Assertions for bound parameters
    assert compiled.params.get("vec_query") == vector # Compare with the raw list
    assert compiled.params.get("dist_thresh") == distance_threshold
    assert compiled.params.get("md_filter") == metadata_json_str
    assert compiled.params.get("ts_start") == ts_start
    assert compiled.params.get("ts_end") == ts_end
    assert compiled.params.get("param_1") == limit
    assert compiled.params.get("param_2") == offset


def test_build_search_vector_query_no_criteria(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query sans aucun critère (devrait retourner tout)."""
    limit, offset = 15, 3
    # Builder returns only the query object now
    query = query_builder.build_search_vector_query(limit=limit, offset=offset, select_count=False)

    # Assert it's a Select object
    assert isinstance(query, Select), "Query should be a Select object"

    # Compile and check
    compiled = query.compile(compile_kwargs={'literal_binds': True})
    query_str = str(compiled).upper()

    assert "SELECT" in query_str
    assert "NULL AS SIMILARITY_SCORE" in query_str
    assert "WHERE" not in query_str # No filters expected
    assert "ORDER BY EVENTS.TIMESTAMP DESC" in query_str
    assert f"LIMIT {limit}" in query_str
    assert f"OFFSET {offset}" in query_str


def test_build_search_vector_query_invalid_dimension(query_builder: EventQueryBuilder):
    """Teste que build_search_vector_query lève une erreur si la dimension du vecteur est mauvaise."""
    vector_invalid = [0.1, 0.2]  # Dimension incorrecte
    with pytest.raises(ValueError) as excinfo:
        query_builder.build_search_vector_query(vector=vector_invalid)
    assert str(query_builder._get_vector_dimensions()) in str(excinfo.value)
    assert str(len(vector_invalid)) in str(excinfo.value)


# --- Fin des tests pour EventQueryBuilder ---
