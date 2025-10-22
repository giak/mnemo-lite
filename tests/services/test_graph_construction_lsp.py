"""
Tests for GraphConstructionService with LSP-enhanced call resolution (EPIC-13 Story 13.5).

Tests the enhanced call resolution using name_path from EPIC-11 and type metadata from Stories 13.1-13.4.
"""

import pytest
import uuid
from datetime import datetime, timezone

from services.graph_construction_service import GraphConstructionService
from models.code_chunk_models import CodeChunkModel


@pytest.mark.anyio
class TestEnhancedCallResolution:
    """Test EPIC-13 Story 13.5: Enhanced call resolution using name_path."""

    async def test_resolve_via_name_path_exact_match(self, test_engine):
        """Test resolution via name_path exact match (highest priority)."""
        service = GraphConstructionService(test_engine)

        # Caller chunk calling "get_user"
        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/routes/user_routes.py",
            language="python",
            chunk_type="function",
            name="list_users",
            name_path="api.routes.user_routes.list_users",
            source_code="def list_users():\n    return get_user(1)",
            start_line=10,
            end_line=11,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["get_user"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        # Target chunk with name_path (disambiguated)
        target_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/user_service.py",
            language="python",
            chunk_type="function",
            name="get_user",
            name_path="api.services.user_service.get_user",
            source_code="def get_user(user_id: int) -> User:\n    pass",
            start_line=20,
            end_line=21,
            embedding_text=None,
            embedding_code=None,
            metadata={"return_type": "User", "param_types": {"user_id": "int"}},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        # Ambiguous chunk (same name, different path)
        ambiguous_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="tests/test_user.py",
            language="python",
            chunk_type="function",
            name="get_user",
            name_path="tests.test_user.get_user",
            source_code="def get_user():\n    return {'id': 1, 'name': 'Test'}",
            start_line=5,
            end_line=6,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, target_chunk, ambiguous_chunk]

        # Resolve "get_user" - should use name_path to disambiguate
        result = await service._resolve_call_target("get_user", caller_chunk, all_chunks)

        # Should resolve to target_chunk (not ambiguous_chunk)
        # Because both match "get_user", but name_path provides precision
        assert result == target_chunk.id, "Should resolve to target via name_path"

    async def test_resolve_via_name_path_single_match(self, test_engine):
        """Test resolution when only one name_path match exists."""
        service = GraphConstructionService(test_engine)

        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/routes/order_routes.py",
            language="python",
            chunk_type="function",
            name="create_order",
            name_path="api.routes.order_routes.create_order",
            source_code="def create_order():\n    calculate_total(items)",
            start_line=10,
            end_line=11,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["calculate_total"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        target_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/pricing_service.py",
            language="python",
            chunk_type="function",
            name="calculate_total",
            name_path="api.services.pricing_service.calculate_total",
            source_code="def calculate_total(items: List[Item]) -> float:\n    pass",
            start_line=30,
            end_line=31,
            embedding_text=None,
            embedding_code=None,
            metadata={"return_type": "float"},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, target_chunk]

        result = await service._resolve_call_target("calculate_total", caller_chunk, all_chunks)

        assert result == target_chunk.id, "Should resolve to unique name_path match"

    async def test_resolve_via_name_path_disambiguation_same_file(self, test_engine):
        """Test disambiguation using file proximity when multiple name_path matches exist."""
        service = GraphConstructionService(test_engine)

        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/user_service.py",
            language="python",
            chunk_type="function",
            name="list_users",
            name_path="api.services.user_service.list_users",
            source_code="def list_users():\n    validate(user)",
            start_line=10,
            end_line=11,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["validate"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        # Target in same file (should be preferred)
        same_file_target = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/user_service.py",
            language="python",
            chunk_type="function",
            name="validate",
            name_path="api.services.user_service.validate",
            source_code="def validate(user: User) -> bool:\n    pass",
            start_line=20,
            end_line=21,
            embedding_text=None,
            embedding_code=None,
            metadata={"return_type": "bool"},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        # Target in different file (should not be chosen)
        different_file_target = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/validation_service.py",
            language="python",
            chunk_type="function",
            name="validate",
            name_path="api.services.validation_service.validate",
            source_code="def validate(data: dict) -> bool:\n    pass",
            start_line=5,
            end_line=6,
            embedding_text=None,
            embedding_code=None,
            metadata={"return_type": "bool"},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, same_file_target, different_file_target]

        result = await service._resolve_call_target("validate", caller_chunk, all_chunks)

        # Should prefer same_file_target due to file proximity
        assert result == same_file_target.id, "Should prefer same file when multiple name_path matches"

    async def test_resolve_via_name_path_partial_match(self, test_engine):
        """Test resolution when name_path ends with call_name (partial match)."""
        service = GraphConstructionService(test_engine)

        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/routes/user_routes.py",
            language="python",
            chunk_type="function",
            name="update_user",
            name_path="api.routes.user_routes.update_user",
            source_code="def update_user():\n    User.save()",
            start_line=10,
            end_line=11,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["save"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        # Method target with hierarchical name_path
        target_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="models/user.py",
            language="python",
            chunk_type="method",
            name="save",
            name_path="models.user.User.save",  # Ends with ".save"
            source_code="def save(self):\n    pass",
            start_line=50,
            end_line=51,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, target_chunk]

        result = await service._resolve_call_target("save", caller_chunk, all_chunks)

        # Should match because name_path ends with ".save"
        assert result == target_chunk.id, "Should match name_path ending with call_name"

    async def test_fallback_to_local_file_when_no_name_path(self, test_engine):
        """Test fallback to local file match when name_path is not available."""
        service = GraphConstructionService(test_engine)

        # Old chunk without name_path (backward compatibility)
        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="utils.py",
            language="python",
            chunk_type="function",
            name="caller",
            name_path=None,  # No name_path
            source_code="def caller():\n    helper()",
            start_line=1,
            end_line=2,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["helper"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        target_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="utils.py",
            language="python",
            chunk_type="function",
            name="helper",
            name_path=None,  # No name_path
            source_code="def helper():\n    pass",
            start_line=5,
            end_line=6,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, target_chunk]

        result = await service._resolve_call_target("helper", caller_chunk, all_chunks)

        # Should still resolve via local file fallback
        assert result == target_chunk.id, "Should fallback to local file match"

    async def test_fallback_to_imports_when_cross_file(self, test_engine):
        """Test fallback to import-based resolution for cross-file calls."""
        service = GraphConstructionService(test_engine)

        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/routes.py",
            language="python",
            chunk_type="function",
            name="handle_request",
            name_path=None,  # No name_path
            source_code="def handle_request():\n    calculate_total(items)",
            start_line=10,
            end_line=11,
            embedding_text=None,
            embedding_code=None,
            metadata={
                "calls": ["calculate_total"],
                "imports": ["utils.pricing.calculate_total"]
            },
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        target_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="utils/pricing.py",
            language="python",
            chunk_type="function",
            name="calculate_total",
            name_path=None,  # No name_path
            source_code="def calculate_total(items):\n    pass",
            start_line=5,
            end_line=6,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk, target_chunk]

        result = await service._resolve_call_target("calculate_total", caller_chunk, all_chunks)

        # Should resolve via imports (fallback)
        assert result == target_chunk.id, "Should resolve via imports when cross-file"

    async def test_no_resolution_for_unknown_call(self, test_engine):
        """Test that unknown calls return None (graceful degradation)."""
        service = GraphConstructionService(test_engine)

        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="test.py",
            language="python",
            chunk_type="function",
            name="test_func",
            name_path="test.test_func",
            source_code="def test_func():\n    unknown_function()",
            start_line=1,
            end_line=2,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["unknown_function"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk]

        result = await service._resolve_call_target("unknown_function", caller_chunk, all_chunks)

        # Should return None (not found)
        assert result is None, "Unknown function should return None"

    async def test_builtin_calls_still_skipped(self, test_engine):
        """Test that built-in calls are still skipped (no regression)."""
        service = GraphConstructionService(test_engine)

        caller_chunk = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="test.py",
            language="python",
            chunk_type="function",
            name="test_func",
            name_path="test.test_func",
            source_code="def test_func():\n    return len([1, 2, 3])",
            start_line=1,
            end_line=2,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["len"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )

        all_chunks = [caller_chunk]

        result = await service._resolve_call_target("len", caller_chunk, all_chunks)

        # Built-in should still return None
        assert result is None, "Built-in 'len' should return None"


@pytest.mark.anyio
class TestResolutionAccuracyImprovement:
    """Test that resolution accuracy improves with name_path (70% → 95%+ target)."""

    async def test_resolution_accuracy_scenario(self, test_engine):
        """
        Test realistic scenario with multiple ambiguous names.

        Without name_path: Low accuracy (many ambiguous names)
        With name_path: High accuracy (qualified names disambiguate)
        """
        service = GraphConstructionService(test_engine)

        # Create realistic repository structure with common names
        chunks = []

        # Caller: api/routes/user_routes.py::create_user
        caller = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/routes/user_routes.py",
            language="python",
            chunk_type="function",
            name="create_user",
            name_path="api.routes.user_routes.create_user",
            source_code="def create_user():\n    validate(data)\n    save(user)\n    send_email(user)",
            start_line=10,
            end_line=13,
            embedding_text=None,
            embedding_code=None,
            metadata={"calls": ["validate", "save", "send_email"]},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )
        chunks.append(caller)

        # Target 1: api/services/validation_service.py::validate
        target1 = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/validation_service.py",
            language="python",
            chunk_type="function",
            name="validate",
            name_path="api.services.validation_service.validate",
            source_code="def validate(data: dict) -> bool:\n    pass",
            start_line=5,
            end_line=6,
            embedding_text=None,
            embedding_code=None,
            metadata={"return_type": "bool"},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )
        chunks.append(target1)

        # Ambiguous: tests/test_validation.py::validate (should NOT match)
        ambiguous1 = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="tests/test_validation.py",
            language="python",
            chunk_type="function",
            name="validate",
            name_path="tests.test_validation.validate",
            source_code="def validate():\n    pass",
            start_line=10,
            end_line=11,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )
        chunks.append(ambiguous1)

        # Target 2: models/user.py::User.save (method)
        target2 = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="models/user.py",
            language="python",
            chunk_type="method",
            name="save",
            name_path="models.user.User.save",
            source_code="def save(self):\n    pass",
            start_line=50,
            end_line=51,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )
        chunks.append(target2)

        # Ambiguous: utils/file_utils.py::save (should NOT match)
        ambiguous2 = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="utils/file_utils.py",
            language="python",
            chunk_type="function",
            name="save",
            name_path="utils.file_utils.save",
            source_code="def save(filename, data):\n    pass",
            start_line=20,
            end_line=21,
            embedding_text=None,
            embedding_code=None,
            metadata={},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )
        chunks.append(ambiguous2)

        # Target 3: api/services/notification_service.py::send_email
        target3 = CodeChunkModel(
            id=uuid.uuid4(),
            file_path="api/services/notification_service.py",
            language="python",
            chunk_type="function",
            name="send_email",
            name_path="api.services.notification_service.send_email",
            source_code="def send_email(user: User) -> None:\n    pass",
            start_line=30,
            end_line=31,
            embedding_text=None,
            embedding_code=None,
            metadata={"return_type": "None"},
            indexed_at=datetime.now(timezone.utc),
            last_modified=None,
            node_id=None,
            repository="test_repo",
            commit_hash=None
        )
        chunks.append(target3)

        # Test resolution for each call
        result1 = await service._resolve_call_target("validate", caller, chunks)
        result2 = await service._resolve_call_target("save", caller, chunks)
        result3 = await service._resolve_call_target("send_email", caller, chunks)

        # With name_path, should resolve correctly
        assert result1 == target1.id, "Should resolve 'validate' to validation_service (not tests)"
        assert result2 == target2.id, "Should resolve 'save' to User.save (not file_utils)"
        assert result3 == target3.id, "Should resolve 'send_email' to notification_service"

        # This demonstrates improved accuracy: 3/3 correct (100%)
        # Without name_path, would be ambiguous (likely <70% accuracy)
