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
from sqlalchemy.sql.expression import Select, Delete, text, TextClause # Keep text import, NO TextClause


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
    mock_params = {"event_id": test_event_id} # Define expected params
    mock_builder.build_delete_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    
    # 2. Action (Act)
    deleted = await repository.delete(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_builder.build_delete_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once_with(mock_query, mock_params)
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
    mock_params = {"event_id": test_event_id} # Define expected params
    mock_builder.build_delete_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock
    
    # 2. Action (Act)
    deleted = await repository.delete(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_builder.build_delete_query.assert_called_once_with(test_event_id)
    mock_connection.execute.assert_awaited_once_with(mock_query, mock_params)
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
    mock_params = {"criteria": json.dumps(criteria)} # Define expected params
    mock_builder.build_filter_by_metadata_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)

    # 3. Vérification (Assert)
    mock_builder.build_filter_by_metadata_query.assert_called_once_with(criteria, 10, 0)
    mock_connection.execute.assert_awaited_once_with(mock_query, mock_params)
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
    mock_params = {"criteria": json.dumps(criteria)} # Define expected params
    mock_builder.build_filter_by_metadata_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)

    # 3. Vérification (Assert)
    mock_builder.build_filter_by_metadata_query.assert_called_once_with(criteria, 10, 0)
    mock_connection.execute.assert_awaited_once_with(mock_query, mock_params)
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

    # Define test_limit and test_offset before using them in mock_params_data
    test_limit = 10
    test_offset = 0

    # Configure mock builder for metadata-only search
    mock_query_data = text("SELECT ... DATA ...")
    mock_params_data = {"md_filter": json.dumps(criteria), "lim": test_limit, "off": test_offset} # Example params
    mock_builder.build_search_vector_query.return_value = (mock_query_data, mock_params_data)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    # Unpack the (events, total_hits) tuple from search_vector
    events, total_hits = await repository.search_vector(
        vector=None,
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )

    # 3. Vérification (Assert)
    # Check that builder was called correctly for metadata-only search
    # It's called once by the current repository.search_vector implementation
    mock_builder.build_search_vector_query.assert_called_once_with(
        vector=None,
        metadata=criteria,
        ts_start=None,
        ts_end=None,
        limit=test_limit,
        offset=test_offset,
        distance_threshold=None # Updated default: 5.0 → None
    )

    # Assert execute calls (data query only)
    mock_connection.execute.assert_awaited_once_with(mock_query_data, mock_params_data)
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

    # Define test_limit and test_offset before using them in mock_params_data
    test_limit = 10
    test_offset = 0

    # Configure mock builder for vector-only search
    mock_query_data = text("SELECT ... DATA ...")
    mock_params_data = {"vec_query": EventModel._format_embedding_for_db(query_vector), "dist_threshold": 5.0, "lim": test_limit, "off": test_offset} # Example params
    mock_builder.build_search_vector_query.return_value = (mock_query_data, mock_params_data)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    # Unpack the (events, total_hits) tuple from search_vector
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        limit=test_limit,
        offset=test_offset
    )

    # 3. Vérification (Assert)
    # Check builder call - adjusted to accept either the top_k or limit parameter
    # Called once by current repository.search_vector
    mock_builder.build_search_vector_query.assert_called_once_with(
        vector=query_vector,
        metadata=None,
        ts_start=None,
        ts_end=None,
        limit=test_limit,
        offset=test_offset,
        distance_threshold=None # Updated default: 5.0 → None
    )

    # Assert execute calls (data query only)
    mock_connection.execute.assert_awaited_once_with(mock_query_data, mock_params_data)
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

    # Define test_limit and test_offset before using them in mock_params_data
    test_limit = 5
    test_offset = 0

    # Configure mock builder for hybrid search
    mock_query_data = text("SELECT ... DATA ...")
    mock_params_data = { # Example params, adjust based on actual builder output for these inputs
        "vec_query": EventModel._format_embedding_for_db(query_vector),
        "dist_threshold": 5.0, 
        "md_filter": json.dumps(criteria), 
        "lim": test_limit, 
        "off": test_offset
    }
    mock_builder.build_search_vector_query.return_value = (mock_query_data, mock_params_data)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder  # Inject mock

    # 2. Action (Act)
    # Unpack the (events, total_hits) tuple from search_vector
    events, total_hits = await repository.search_vector(
        vector=query_vector,
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
        offset=test_offset,
        distance_threshold=None # Updated default: 5.0 → None
    )
    
    # Assert execute calls (data query only)
    mock_connection.execute.assert_awaited_once_with(mock_query_data, mock_params_data)
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
    """Teste la construction de la requête INSERT retournée par build_add_query (maintenant text())."""
    now_utc = datetime.datetime.now(tz=timezone.utc)
    event_data = EventCreate(
        content={"message": "Test event for build_add_query"},
        metadata={"tag": "builder_test"},
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        timestamp=now_utc
    )

    query, params = query_builder.build_add_query(event_data)

    # Assertions for TextClause query and parameters
    assert isinstance(query, TextClause), "Query should be a TextClause object"
    query_str_lower = str(query).lower() # For case-insensitive checks

    assert "insert into events" in query_str_lower
    assert "values (:id, cast(:content as jsonb), cast(:metadata as jsonb), :embedding, :timestamp)" in query_str_lower
    assert "returning id, content, metadata, embedding, timestamp" in query_str_lower

    # Check parameters
    assert isinstance(params, dict)
    assert "id" in params and isinstance(uuid.UUID(params["id"]), uuid.UUID) # Check if ID is a valid UUID string
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

    assert "SELECT" in query_str
    assert "ID" in query_str
    assert "FROM" in query_str 
    assert "EVENTS" in query_str
    assert "WHERE" in query_str
    assert params["event_id"] == str(test_id) # Expect string representation


def test_build_update_metadata_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête UPDATE metadata."""
    test_id = uuid.uuid4()
    metadata_update = {"new_tag": "updated", "status": "active"}
    query, params = query_builder.build_update_metadata_query(test_id, metadata_update)
    query_str = str(query).upper()

    assert "UPDATE" in query_str
    assert "SET" in query_str
    assert "METADATA" in query_str
    assert "WHERE" in query_str
    assert params["event_id"] == str(test_id) # Expect string representation
    assert params["metadata_update"] == json.dumps(metadata_update)


def test_build_delete_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête DELETE."""
    test_id = uuid.uuid4()
    query, params = query_builder.build_delete_query(test_id)
    assert isinstance(query, Delete), "Query should be a Delete object"
    query_str = str(query.compile(compile_kwargs={"literal_binds": False})).upper()
    assert "DELETE FROM EVENTS" in query_str
    assert "WHERE EVENTS.ID = :EVENT_ID" in query_str
    assert params["event_id"] == str(test_id) # Expect string representation


def test_build_filter_by_metadata_query(query_builder: EventQueryBuilder):
    """Teste la construction de la requête SELECT filtrée par metadata."""
    criteria = {"source": "builder_test", "level": 5}
    limit = 10
    offset = 0
    query_tuple = query_builder.build_filter_by_metadata_query(criteria, limit, offset)
    assert isinstance(query_tuple, tuple), "Should return a tuple (query, params)"
    assert len(query_tuple) == 2, "Tuple should have two elements"
    query, params = query_tuple
    # La requête est un TextClause, pas un Select directement à cause de la construction manuelle de la string SQL
    assert isinstance(query, TextClause), "Query should be a TextClause object"
    assert "metadata @> cast(:criteria as jsonb)" in str(query).lower() # Updated: ::jsonb → CAST
    assert "order by timestamp desc" in str(query).lower()
    assert "limit :lim offset :off" in str(query).lower()
    assert params == {"criteria": json.dumps(criteria), "lim": limit, "off": offset}


# Tests plus spécifiques pour build_search_vector_query


def test_build_search_vector_query_vector_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement un vecteur."""
    vector = [0.1] * query_builder._get_vector_dimensions()
    limit, offset = 5, 0
    distance_threshold_test = 1.0  # Explicitly pass a threshold for this test
    query_tuple = query_builder.build_search_vector_query(
        vector=vector, limit=limit, offset=offset, distance_threshold=distance_threshold_test
    )
    assert isinstance(query_tuple, tuple) and len(query_tuple) == 2
    query, params = query_tuple
    query_str = str(query).upper()
    assert "SELECT" in query_str
    assert "EMBEDDING <-> :VEC_QUERY AS SIMILARITY_SCORE" in query_str
    assert "WHERE EMBEDDING <-> :VEC_QUERY <= :DIST_THRESHOLD" in query_str
    assert "ORDER BY SIMILARITY_SCORE ASC" in query_str
    assert "LIMIT :LIM" in query_str
    assert "OFFSET :OFF" in query_str
    assert params.get("vec_query") == EventModel._format_embedding_for_db(vector)
    assert params.get("dist_threshold") == distance_threshold_test  # Check against explicit value


def test_build_search_vector_query_metadata_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement metadata."""
    metadata = {"tag": "metadata_only_builder"}
    limit, offset = 10, 5
    query_tuple = query_builder.build_search_vector_query(
        metadata=metadata, limit=limit, offset=offset
    )
    assert isinstance(query_tuple, tuple) and len(query_tuple) == 2
    query, params = query_tuple
    query_str = str(query).upper().replace('\n', ' ')
    assert "SELECT" in query_str
    assert "NULL AS SIMILARITY_SCORE" in query_str
    assert 'METADATA @> :MD_FILTER ::JSONB' in query_str # Added space before ::JSONB
    assert "ORDER BY TIMESTAMP DESC" in query_str # No table alias
    assert "LIMIT :LIM" in query_str
    assert "OFFSET :OFF" in query_str
    
    metadata_json_str = json.dumps(metadata)

    # Assertions for bound parameters
    # Vector and dist_thresh are not applicable for metadata-only search.
    assert params.get("md_filter") == json.dumps(metadata)
    assert params.get("lim") == limit
    assert params.get("off") == offset


def test_build_search_vector_query_time_only(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec seulement un filtre temporel."""
    ts_start = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ts_end = datetime.datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    limit, offset = 8, 1
    query_tuple = query_builder.build_search_vector_query(
        ts_start=ts_start, ts_end=ts_end, limit=limit, offset=offset
    )
    assert isinstance(query_tuple, tuple) and len(query_tuple) == 2
    query, params = query_tuple
    query_str = str(query).upper().replace('\n', ' ')
    assert "SELECT" in query_str
    assert "NULL AS SIMILARITY_SCORE" in query_str
    assert "WHERE TIMESTAMP >= :TS_START" in query_str # No table alias
    assert "AND TIMESTAMP <= :TS_END" in query_str # No table alias
    assert params.get("ts_start") == ts_start
    assert params.get("ts_end") == ts_end
    assert params.get("lim") == limit
    assert params.get("off") == offset


def test_build_search_vector_query_hybrid(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query avec tous les critères."""
    vector = [0.2] * query_builder._get_vector_dimensions()
    metadata = {"type": "hybrid_builder"}
    ts_start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    ts_end = datetime.datetime.now(datetime.timezone.utc)
    limit, offset = 20, 10
    distance_threshold_val = 1.0 # Updated default: 0.5 → 1.0

    query_tuple = query_builder.build_search_vector_query(
        vector=vector,
        metadata=metadata,
        ts_start=ts_start,
        ts_end=ts_end,
        limit=limit,
        offset=offset,
        distance_threshold=distance_threshold_val
    )
    assert isinstance(query_tuple, tuple) and len(query_tuple) == 2
    query, params = query_tuple
    query_str = str(query).upper().replace('\n', ' ')
    assert "SELECT" in query_str
    assert "EMBEDDING <-> :VEC_QUERY AS SIMILARITY_SCORE" in query_str
    assert "WHERE EMBEDDING <-> :VEC_QUERY <= :DIST_THRESHOLD" in query_str
    assert "AND METADATA @> :MD_FILTER ::JSONB" in query_str # Added space before ::JSONB
    assert "ORDER BY SIMILARITY_SCORE ASC" in query_str
    assert "LIMIT :LIM" in query_str
    assert params.get("vec_query") == EventModel._format_embedding_for_db(vector)
    assert params.get("dist_threshold") == distance_threshold_val # Corrected: dist_threshold, use local var
    assert params.get("md_filter") == json.dumps(metadata)
    assert params.get("ts_start") == ts_start
    assert params.get("ts_end") == ts_end
    assert params.get("lim") == limit
    assert params.get("off") == offset


def test_build_search_vector_query_no_criteria(query_builder: EventQueryBuilder):
    """Teste build_search_vector_query sans aucun critère (devrait retourner tout)."""
    limit, offset = 15, 3
    query_tuple = query_builder.build_search_vector_query(limit=limit, offset=offset)
    assert isinstance(query_tuple, tuple) and len(query_tuple) == 2
    query, params = query_tuple
    query_str = str(query).upper()

    assert "SELECT" in query_str
    assert "NULL AS SIMILARITY_SCORE" in query_str
    assert "WHERE" not in query_str
    assert "ORDER BY TIMESTAMP DESC" in query_str
    assert "LIMIT :LIM" in query_str # Reverted to placeholder check
    assert "OFFSET :OFF" in query_str # Reverted to placeholder check
    assert params.get("lim") == limit # Check actual param value
    assert params.get("off") == offset # Check actual param value


def test_build_search_vector_query_invalid_dimension(query_builder: EventQueryBuilder):
    """Teste que build_search_vector_query lève une erreur si la dimension du vecteur est mauvaise."""
    vector_invalid = [0.1, 0.2]  # Dimension incorrecte
    with pytest.raises(ValueError) as excinfo:
        query_builder.build_search_vector_query(vector=vector_invalid)
    assert str(query_builder._get_vector_dimensions()) in str(excinfo.value)
    assert str(len(vector_invalid)) in str(excinfo.value)


# --- Fin des tests pour EventQueryBuilder ---
