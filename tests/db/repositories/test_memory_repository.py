import os
import uuid
import pytest
import pytest_asyncio # Ensure pytest-asyncio is installed
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.sql import text
from typing import AsyncGenerator, Dict, Any, List
import datetime
import json
import asyncio

# Import the class to test and supporting models
from db.repositories.memory_repository import MemoryRepository
from models.memory_models import MemoryCreate, MemoryUpdate, Memory

# --- Configuration ---
# Use the same TEST_DATABASE_URL used in Makefile/environment
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://mnemo:mnemopass@localhost:5433/mnemolite_test")
# Ensure this matches the table name used in the repository
TABLE_NAME = "events"


# --- Fixtures ---

@pytest.fixture(scope="session")
def event_loop():
    """Creates an instance of the default event loop for the session." Gère le warning pytest."""
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provides a SQLAlchemy AsyncEngine connected to the test database for the session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False) # Set echo=True for debugging SQL
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="function") # Use function scope to ensure clean state per test
async def clean_db_table(db_engine: AsyncEngine):
    """Fixture to clean the test table before each test runs."""
    async with db_engine.connect() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {TABLE_NAME} RESTART IDENTITY CASCADE;"))
        await conn.commit()
    yield # Test runs here
    # Optional: add cleanup after test if needed, but TRUNCATE before should suffice

@pytest_asyncio.fixture(scope="function")
async def memory_repo(db_engine: AsyncEngine, clean_db_table: None) -> MemoryRepository:
    """Provides a MemoryRepository instance initialized with the test DB engine.
    Depends on clean_db_table to ensure the table is empty before the test.
    """
    # The clean_db_table fixture runs automatically due to dependency
    return MemoryRepository(engine=db_engine)

# --- Helper Functions ---
async def get_record_by_id(db_engine: AsyncEngine, record_id: uuid.UUID) -> Dict[str, Any] | None:
    """Helper to fetch a raw record directly from the DB for verification."""
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT id, timestamp, content, metadata FROM {TABLE_NAME} WHERE id = :id"),
            {"id": record_id}
        )
        record = result.mappings().first() # Use mappings() for dict-like access
        return dict(record) if record else None

# --- Sample Test Data ---
@pytest.fixture
def sample_memory_create_data() -> MemoryCreate:
    return MemoryCreate(
        memory_type="episodic",
        event_type="test_event",
        role_id=123,
        content={"message": "This is a test memory content."},
        metadata={"source": "pytest", "extra_info": "sample_data"},
        expiration=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    )

@pytest.fixture
def sample_memory_update_data() -> MemoryUpdate:
    return MemoryUpdate(
        memory_type="semantic", # Change type
        content={"message": "Updated test content", "new_field": True}, # Update content
        metadata={"source": "pytest_update"}, # Overwrite metadata
        expiration=None # Remove expiration
    )

# --- Test Cases Start Here ---

# TODO: Add tests for _map_record_to_memory

# --- Tests for add() ---
@pytest.mark.asyncio
async def test_add_memory_success(
    memory_repo: MemoryRepository,
    db_engine: AsyncEngine, # Needed for direct DB check
    sample_memory_create_data: MemoryCreate
):
    """Test successfully adding a new memory."""
    # Arrange
    input_data = sample_memory_create_data

    # Act
    created_memory = await memory_repo.add(input_data)

    # Assert: Check returned object
    assert created_memory is not None
    assert isinstance(created_memory.id, uuid.UUID)
    assert isinstance(created_memory.timestamp, datetime.datetime)
    assert created_memory.memory_type == input_data.memory_type
    assert created_memory.event_type == input_data.event_type
    assert created_memory.role_id == input_data.role_id
    assert created_memory.content == input_data.content
    # Specific metadata fields are extracted, check remaining metadata
    assert created_memory.metadata == input_data.metadata # {'source': 'pytest', 'extra_info': 'sample_data'}
    assert created_memory.expiration is not None
    # Compare expiration dates carefully (potential precision differences)
    assert abs(created_memory.expiration - input_data.expiration) < datetime.timedelta(seconds=1)

    # Assert: Check directly in the database
    db_record = await get_record_by_id(db_engine, created_memory.id)
    assert db_record is not None
    assert db_record["id"] == created_memory.id
    assert db_record["content"] == input_data.content # Stored as JSON
    
    # Verify how metadata is stored (combined structure)
    expected_metadata_in_db = input_data.metadata.copy()
    expected_metadata_in_db["memory_type"] = input_data.memory_type
    expected_metadata_in_db["event_type"] = input_data.event_type
    expected_metadata_in_db["role_id"] = input_data.role_id
    expected_metadata_in_db["expiration"] = input_data.expiration.isoformat() # Stored as ISO string
    assert db_record["metadata"] == expected_metadata_in_db


# TODO: Add test for add() with database errors (needs mocking or specific DB setup)
# TODO: Add test for add() with JSON serialization errors (if input data allows invalid JSON)

# --- Tests for get_by_id() ---
@pytest.mark.asyncio
async def test_get_memory_by_id_success(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate
):
    """Test retrieving an existing memory by its ID."""
    # Arrange: Add a memory first
    added_memory = await memory_repo.add(sample_memory_create_data)
    assert added_memory is not None

    # Act
    retrieved_memory = await memory_repo.get_by_id(added_memory.id)

    # Assert
    assert retrieved_memory is not None
    assert retrieved_memory.id == added_memory.id
    assert retrieved_memory.memory_type == added_memory.memory_type
    assert retrieved_memory.event_type == added_memory.event_type
    assert retrieved_memory.role_id == added_memory.role_id
    assert retrieved_memory.content == added_memory.content
    assert retrieved_memory.metadata == added_memory.metadata
    assert abs(retrieved_memory.timestamp - added_memory.timestamp) < datetime.timedelta(seconds=1)
    assert abs(retrieved_memory.expiration - added_memory.expiration) < datetime.timedelta(seconds=1)

@pytest.mark.asyncio
async def test_get_memory_by_id_not_found(
    memory_repo: MemoryRepository
):
    """Test retrieving a non-existent memory by ID returns None."""
    # Arrange
    non_existent_id = uuid.uuid4()

    # Act
    retrieved_memory = await memory_repo.get_by_id(non_existent_id)

    # Assert
    assert retrieved_memory is None


# --- Tests for update() ---
@pytest.mark.asyncio
async def test_update_memory_success(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate,
    sample_memory_update_data: MemoryUpdate,
    db_engine: AsyncEngine
):
    """Test successfully updating an existing memory."""
    # Arrange: Add initial memory
    initial_memory = await memory_repo.add(sample_memory_create_data)
    update_data = sample_memory_update_data

    # Act
    updated_memory = await memory_repo.update(initial_memory.id, update_data)

    # Assert: Check returned object
    assert updated_memory is not None
    assert updated_memory.id == initial_memory.id
    assert updated_memory.memory_type == update_data.memory_type # Updated
    assert updated_memory.event_type == sample_memory_create_data.event_type # Should be merged from existing
    assert updated_memory.role_id == sample_memory_create_data.role_id # Should be merged from existing
    # Content should be merged
    expected_content = sample_memory_create_data.content.copy()
    expected_content.update(update_data.content)
    assert updated_memory.content == expected_content
    # Metadata should be merged
    expected_metadata = sample_memory_create_data.metadata.copy()
    expected_metadata.update(update_data.metadata)
    assert updated_memory.metadata == expected_metadata
    assert updated_memory.expiration is None # Updated to None

    # Assert: Check directly in DB
    db_record = await get_record_by_id(db_engine, initial_memory.id)
    assert db_record is not None
    assert db_record["content"] == expected_content
    # Check merged metadata in DB (includes specific fields)
    db_metadata = db_record["metadata"]
    assert db_metadata["memory_type"] == update_data.memory_type
    assert db_metadata["event_type"] == sample_memory_create_data.event_type
    assert db_metadata["role_id"] == sample_memory_create_data.role_id
    assert db_metadata["source"] == update_data.metadata["source"]
    assert db_metadata["extra_info"] == sample_memory_create_data.metadata["extra_info"]
    assert db_metadata.get("expiration") is None # Check expiration removed

@pytest.mark.asyncio
async def test_update_memory_partial(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate
):
    """Test partially updating a memory (only one field)."""
    # Arrange
    initial_memory = await memory_repo.add(sample_memory_create_data)
    partial_update = MemoryUpdate(event_type="updated_event_only")

    # Act
    updated_memory = await memory_repo.update(initial_memory.id, partial_update)

    # Assert
    assert updated_memory is not None
    assert updated_memory.id == initial_memory.id
    assert updated_memory.memory_type == initial_memory.memory_type # Unchanged
    assert updated_memory.event_type == partial_update.event_type # Updated
    assert updated_memory.role_id == initial_memory.role_id # Unchanged
    assert updated_memory.content == initial_memory.content # Unchanged
    assert updated_memory.metadata == initial_memory.metadata # Unchanged (apart from event_type handled separately)
    assert updated_memory.expiration == initial_memory.expiration # Unchanged

@pytest.mark.asyncio
async def test_update_memory_not_found(
    memory_repo: MemoryRepository,
    sample_memory_update_data: MemoryUpdate
):
    """Test updating a non-existent memory returns None."""
    # Arrange
    non_existent_id = uuid.uuid4()
    update_data = sample_memory_update_data

    # Act
    updated_memory = await memory_repo.update(non_existent_id, update_data)

    # Assert
    assert updated_memory is None

@pytest.mark.asyncio
async def test_update_memory_empty_data(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate
):
    """Test that calling update with no actual data doesn't change the memory."""
    # Arrange
    initial_memory = await memory_repo.add(sample_memory_create_data)
    empty_update = MemoryUpdate() # No fields set

    # Act
    # The method should internally call get_by_id in this case
    updated_memory = await memory_repo.update(initial_memory.id, empty_update)

    # Assert
    assert updated_memory is not None
    assert updated_memory.id == initial_memory.id
    assert updated_memory.memory_type == initial_memory.memory_type
    assert updated_memory.event_type == initial_memory.event_type
    assert updated_memory.role_id == initial_memory.role_id
    assert updated_memory.content == initial_memory.content
    assert updated_memory.metadata == initial_memory.metadata
    assert updated_memory.expiration == initial_memory.expiration

@pytest.mark.asyncio
async def test_update_memory_merge_only_content(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate
):
    """Test that updating only content merges correctly."""
    # Arrange
    initial_memory = await memory_repo.add(sample_memory_create_data)
    content_update = MemoryUpdate(content={"new_field": "only_content"})

    # Act
    updated_memory = await memory_repo.update(initial_memory.id, content_update)

    # Assert
    assert updated_memory is not None
    expected_content = initial_memory.content.copy()
    expected_content.update(content_update.content)
    assert updated_memory.content == expected_content
    # Other fields should remain unchanged (check a few)
    assert updated_memory.memory_type == initial_memory.memory_type
    assert updated_memory.metadata == initial_memory.metadata

@pytest.mark.asyncio
async def test_update_memory_merge_only_metadata(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate
):
    """Test that updating only metadata merges correctly."""
    # Arrange
    initial_memory = await memory_repo.add(sample_memory_create_data)
    metadata_update = MemoryUpdate(metadata={"new_meta": "only_metadata"})

    # Act
    updated_memory = await memory_repo.update(initial_memory.id, metadata_update)

    # Assert
    assert updated_memory is not None
    expected_metadata = initial_memory.metadata.copy()
    expected_metadata.update(metadata_update.metadata)
    assert updated_memory.metadata == expected_metadata
    # Other fields should remain unchanged (check a few)
    assert updated_memory.memory_type == initial_memory.memory_type
    assert updated_memory.content == initial_memory.content

@pytest.mark.asyncio
async def test_update_memory_overwrite_content_key(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate # Has content: {"message": ...}
):
    """Test that updating content overwrites existing keys."""
    # Arrange
    initial_memory = await memory_repo.add(sample_memory_create_data)
    # Update with the *same* key but different value
    content_update = MemoryUpdate(content={"message": "overwritten"})

    # Act
    updated_memory = await memory_repo.update(initial_memory.id, content_update)

    # Assert
    assert updated_memory is not None
    # Check that the original key was overwritten, not merged deeper
    assert updated_memory.content == {"message": "overwritten"}

@pytest.mark.asyncio
async def test_update_memory_overwrite_metadata_key(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate # Has metadata: {"source": "pytest", "extra_info": ...}
):
    """Test that updating metadata overwrites existing keys."""
    # Arrange
    initial_memory = await memory_repo.add(sample_memory_create_data)
    # Update with the *same* key but different value
    metadata_update = MemoryUpdate(metadata={"source": "overwritten"})

    # Act
    updated_memory = await memory_repo.update(initial_memory.id, metadata_update)

    # Assert
    assert updated_memory is not None
    # Check that the original key was overwritten
    expected_metadata = initial_memory.metadata.copy()
    expected_metadata["source"] = "overwritten" # Overwrite the specific key
    assert updated_memory.metadata == expected_metadata


# --- Tests for delete() ---
@pytest.mark.asyncio
async def test_delete_memory_success(
    memory_repo: MemoryRepository,
    sample_memory_create_data: MemoryCreate
):
    """Test successfully deleting an existing memory."""
    # Arrange: Add a memory
    added_memory = await memory_repo.add(sample_memory_create_data)
    assert added_memory is not None
    memory_id_to_delete = added_memory.id

    # Act: Delete the memory
    delete_result = await memory_repo.delete(memory_id_to_delete)

    # Assert: delete returned True and memory is gone
    assert delete_result is True
    retrieved_memory = await memory_repo.get_by_id(memory_id_to_delete)
    assert retrieved_memory is None

@pytest.mark.asyncio
async def test_delete_memory_not_found(
    memory_repo: MemoryRepository
):
    """Test deleting a non-existent memory returns False."""
    # Arrange
    non_existent_id = uuid.uuid4()

    # Act
    delete_result = await memory_repo.delete(non_existent_id)

    # Assert
    assert delete_result is False


# --- Tests for list_memories() ---

# Helper fixture to add multiple diverse memories
@pytest_asyncio.fixture(scope="function")
async def populate_multiple_memories(memory_repo: MemoryRepository):
    memories_data = [
        # Memory 1: Episodic, Event A, Role 1, Session 101
        MemoryCreate(memory_type="episodic", event_type="event_A", role_id=1, content={"data": "memory 1"}, metadata={"session_id": "101", "custom": "val1"}),
        # Memory 2: Semantic, Event B, Role 2, Session 102
        MemoryCreate(memory_type="semantic", event_type="event_B", role_id=2, content={"data": "memory 2"}, metadata={"session_id": "102"}),
        # Memory 3: Episodic, Event B, Role 1, Session 101
        MemoryCreate(memory_type="episodic", event_type="event_B", role_id=1, content={"data": "memory 3"}, metadata={"session_id": "101"}),
        # Memory 4: Episodic, Event C, Role 3, No Session
        MemoryCreate(memory_type="episodic", event_type="event_C", role_id=3, content={"data": "memory 4"}),
        # Memory 5: Semantic, Event A, Role 2, Session 102
        MemoryCreate(memory_type="semantic", event_type="event_A", role_id=2, content={"data": "memory 5"}, metadata={"session_id": "102"}),
    ]
    added_memories = []
    for data in memories_data:
        # Introduce a small delay to ensure distinct timestamps for ordering tests
        await asyncio.sleep(0.01)
        added = await memory_repo.add(data)
        added_memories.append(added)
    return added_memories # Return the added memories (already mapped)

@pytest.mark.asyncio
async def test_list_memories_no_filters_default_limit(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test listing memories with no filters and default limit (10)."""
    # Arrange
    # Data is populated by the fixture
    total_added = len(populate_multiple_memories)
    default_limit = 10

    # Act
    listed_memories = await memory_repo.list_memories()

    # Assert
    assert len(listed_memories) == total_added
    assert len(listed_memories) <= default_limit
    # Check descending order by timestamp (most recent first)
    assert listed_memories[0].timestamp > listed_memories[1].timestamp
    assert listed_memories[1].timestamp > listed_memories[2].timestamp
    # Spot check the last added memory is the first listed
    assert listed_memories[0].id == populate_multiple_memories[-1].id
    assert listed_memories[0].content == populate_multiple_memories[-1].content

@pytest.mark.asyncio
async def test_list_memories_custom_limit(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test listing memories with a custom limit."""
    # Arrange
    limit = 3

    # Act
    listed_memories = await memory_repo.list_memories(limit=limit)

    # Assert
    assert len(listed_memories) == limit
    # Check descending order
    assert listed_memories[0].timestamp > listed_memories[1].timestamp
    assert listed_memories[1].timestamp > listed_memories[2].timestamp
    # Check it got the *last* 3 added
    assert listed_memories[0].id == populate_multiple_memories[-1].id
    assert listed_memories[1].id == populate_multiple_memories[-2].id
    assert listed_memories[2].id == populate_multiple_memories[-3].id

@pytest.mark.asyncio
async def test_list_memories_offset(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test listing memories with an offset."""
    # Arrange
    offset = 2
    total_added = len(populate_multiple_memories)

    # Act
    listed_memories = await memory_repo.list_memories(offset=offset)

    # Assert
    assert len(listed_memories) == total_added - offset
    # Check the first item returned is the N-offset-th item added (0-indexed)
    assert listed_memories[0].id == populate_multiple_memories[-(offset + 1)].id

@pytest.mark.asyncio
async def test_list_memories_filter_memory_type(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test filtering by memory_type."""
    # Arrange
    memory_type_filter = "episodic"
    # Count expected results from fixture data
    expected_count = sum(1 for mem in populate_multiple_memories if mem.memory_type == memory_type_filter)

    # Act
    listed_memories = await memory_repo.list_memories(memory_type=memory_type_filter)

    # Assert
    assert len(listed_memories) == expected_count
    for mem in listed_memories:
        assert mem.memory_type == memory_type_filter

@pytest.mark.asyncio
async def test_list_memories_filter_event_type(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test filtering by event_type."""
    # Arrange
    event_type_filter = "event_B"
    expected_count = sum(1 for mem in populate_multiple_memories if mem.event_type == event_type_filter)

    # Act
    listed_memories = await memory_repo.list_memories(event_type=event_type_filter)

    # Assert
    assert len(listed_memories) == expected_count
    for mem in listed_memories:
        assert mem.event_type == event_type_filter

@pytest.mark.asyncio
async def test_list_memories_filter_role_id(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test filtering by role_id."""
    # Arrange
    role_id_filter = 1
    expected_count = sum(1 for mem in populate_multiple_memories if mem.role_id == role_id_filter)

    # Act
    listed_memories = await memory_repo.list_memories(role_id=role_id_filter)

    # Assert
    assert len(listed_memories) == expected_count
    for mem in listed_memories:
        assert mem.role_id == role_id_filter

@pytest.mark.asyncio
async def test_list_memories_filter_session_id(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test filtering by session_id (stored in metadata)."""
    # Arrange
    session_id_filter = "101"
    # Count expected results (check metadata directly for session_id)
    expected_count = sum(1 for mem in populate_multiple_memories if mem.metadata.get("session_id") == session_id_filter)

    # Act
    listed_memories = await memory_repo.list_memories(session_id=session_id_filter)

    # Assert
    assert len(listed_memories) == expected_count
    for mem in listed_memories:
        # Check metadata for session_id (it's not a top-level Memory field)
        assert mem.metadata.get("session_id") == session_id_filter

@pytest.mark.asyncio
async def test_list_memories_combined_filters_pagination(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test combining filters with limit and offset."""
    # Arrange - Filter for Episodic, Role 1 (should be 2 memories)
    memory_type_filter = "episodic"
    role_id_filter = 1
    limit = 1
    offset = 1

    # Act
    listed_memories = await memory_repo.list_memories(
        memory_type=memory_type_filter,
        role_id=role_id_filter,
        limit=limit,
        offset=offset
    )

    # Assert
    assert len(listed_memories) == limit
    # Check the specific memory returned (should be the *first* added that matches,
    # because offset=1 skips the most recent one matching the filter)
    # Find expected memory in original data
    matching_memories = sorted(
        [m for m in populate_multiple_memories if m.memory_type == memory_type_filter and m.role_id == role_id_filter],
        key=lambda m: m.timestamp,
        reverse=True # Same order as DB query
    )
    assert listed_memories[0].id == matching_memories[offset].id # Compare with the offset-th match
    assert listed_memories[0].memory_type == memory_type_filter
    assert listed_memories[0].role_id == role_id_filter

@pytest.mark.asyncio
async def test_list_memories_filter_no_results(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test filters that yield no results return an empty list."""
    # Arrange
    memory_type_filter = "non_existent_type"

    # Act
    listed_memories = await memory_repo.list_memories(memory_type=memory_type_filter)

    # Assert
    assert listed_memories == []

@pytest.mark.asyncio
async def test_list_memories_limit_zero(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test listing memories with limit=0 returns empty list."""
    # Act
    listed_memories = await memory_repo.list_memories(limit=0)
    # Assert
    assert listed_memories == []

@pytest.mark.asyncio
async def test_list_memories_offset_too_large(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test listing memories with offset >= total items returns empty list."""
    # Arrange
    offset = len(populate_multiple_memories)
    # Act
    listed_memories = await memory_repo.list_memories(offset=offset)
    # Assert
    assert listed_memories == []

@pytest.mark.asyncio
async def test_list_memories_three_filters(
    memory_repo: MemoryRepository,
    populate_multiple_memories: List[Memory]
):
    """Test combining three filters (memory_type, event_type, role_id)."""
    # Arrange: Filter for Episodic, Event B, Role 1 (should be 1 memory: memory 3)
    memory_type_filter = "episodic"
    event_type_filter = "event_B"
    role_id_filter = 1
    expected_content = {"data": "memory 3"} # From populate_multiple_memories

    # Act
    listed_memories = await memory_repo.list_memories(
        memory_type=memory_type_filter,
        event_type=event_type_filter,
        role_id=role_id_filter
    )

    # Assert
    assert len(listed_memories) == 1
    assert listed_memories[0].memory_type == memory_type_filter
    assert listed_memories[0].event_type == event_type_filter
    assert listed_memories[0].role_id == role_id_filter
    assert listed_memories[0].content == expected_content

# --- Tests for _map_record_to_memory (indirectly) ---
@pytest.mark.asyncio
async def test_get_memory_with_null_json_fields(
    memory_repo: MemoryRepository,
    db_engine: AsyncEngine # Needed for direct insertion
):
    """Test retrieving and mapping a record with NULL JSON fields."""
    # Arrange: Directly insert a record with NULL content/metadata
    test_id = uuid.uuid4()
    insert_query = text(
        f"INSERT INTO {TABLE_NAME} (id, timestamp, content, metadata) VALUES (:id, NOW() AT TIME ZONE 'utc', NULL, NULL)"
    )
    async with db_engine.connect() as conn:
        await conn.execute(insert_query, {"id": test_id})
        await conn.commit()

    # Act
    retrieved_memory = await memory_repo.get_by_id(test_id)

    # Assert: Check that mapping handled NULLs gracefully
    assert retrieved_memory is not None
    assert retrieved_memory.id == test_id
    # The mapper should return empty dicts for NULL json/jsonb fields
    assert retrieved_memory.content == {}
    assert retrieved_memory.metadata == {}
    # Specific fields extracted from metadata should have defaults
    assert retrieved_memory.memory_type == "unknown"
    assert retrieved_memory.event_type == "unknown"
    assert retrieved_memory.role_id == -1
    assert retrieved_memory.expiration is None

@pytest.mark.asyncio
async def test_get_memory_with_null_json_fields(
    memory_repo: MemoryRepository,
    db_engine: AsyncEngine # Needed for direct insertion
):
    """Test retrieving and mapping a record with empty but valid JSON fields."""
    # Arrange: Directly insert a record with empty JSON content/metadata
    test_id = uuid.uuid4()
    # Avoid f-string issue with literal braces by using standard string formatting
    sql = (
        f"INSERT INTO {TABLE_NAME} (id, timestamp, content, metadata) "
        f"VALUES (:id, NOW() AT TIME ZONE 'utc', '{{}}'::jsonb, '{{}}'::jsonb)"
    )
    insert_query = text(sql)
    async with db_engine.connect() as conn:
        await conn.execute(insert_query, {"id": test_id})
        await conn.commit()

    # Act
    retrieved_memory = await memory_repo.get_by_id(test_id)

    # Assert: Check that mapping handled empty JSONs gracefully
    assert retrieved_memory is not None
    assert retrieved_memory.id == test_id
    # The mapper should return empty dicts for empty json/jsonb fields
    assert retrieved_memory.content == {}
    assert retrieved_memory.metadata == {}
    # Specific fields extracted from metadata should have defaults
    assert retrieved_memory.memory_type == "unknown"
    assert retrieved_memory.event_type == "unknown"
    assert retrieved_memory.role_id == -1
    assert retrieved_memory.expiration is None

# Final cleanup of placeholder if still present
# @pytest.mark.asyncio
# async def test_dummy_placeholder():
#     """A dummy test to ensure the file is picked up by pytest."""
#     assert True 