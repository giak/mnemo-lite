"""
Tests for SymbolPathService (EPIC-11 Story 11.1).

Tests cover:
- Fix #1: Parent context ordering (outermost → innermost)
- Fix #3: Strict containment checks
- Basic name_path generation
- Multi-language support
"""

import pytest
from pathlib import Path
from typing import List
from services.symbol_path_service import SymbolPathService


# Mock CodeChunk class for testing
class MockCodeChunk:
    """Mock code chunk for testing parent context extraction."""

    def __init__(
        self,
        name: str,
        chunk_type: str,
        start_line: int,
        end_line: int
    ):
        self.name = name
        self.chunk_type = chunk_type
        self.start_line = start_line
        self.end_line = end_line


class TestSymbolPathServiceBasics:
    """Test basic name_path generation functionality."""

    @pytest.fixture
    def service(self):
        return SymbolPathService()

    def test_simple_function_name_path(self, service):
        """Test name_path generation for simple function (no parent)."""
        name_path = service.generate_name_path(
            chunk_name="calculate_total",
            file_path="/home/user/project/api/utils/calculator.py",
            repository_root="/home/user/project",
            parent_context=None,
            language="python"
        )

        assert name_path == "utils.calculator.calculate_total"

    def test_method_with_parent_class(self, service):
        """Test name_path generation for method with parent class."""
        name_path = service.generate_name_path(
            chunk_name="validate",
            file_path="/home/user/project/api/models/user.py",
            repository_root="/home/user/project",
            parent_context=["User"],
            language="python"
        )

        assert name_path == "models.user.User.validate"

    def test_nested_method_with_multiple_parents(self, service):
        """Test name_path generation for nested method with multiple parents."""
        name_path = service.generate_name_path(
            chunk_name="connect",
            file_path="/home/user/project/api/services/cache.py",
            repository_root="/home/user/project",
            parent_context=["CacheManager", "RedisCache"],
            language="python"
        )

        assert name_path == "services.cache.CacheManager.RedisCache.connect"


class TestFileToModulePath:
    """Test _file_to_module_path conversion for different languages."""

    @pytest.fixture
    def service(self):
        return SymbolPathService()

    def test_python_file_path_conversion(self, service):
        """Test Python file path to module path conversion."""
        module_path = service._file_to_module_path(
            file_path="/home/user/project/api/routes/auth.py",
            repository_root="/home/user/project",
            language="python"
        )

        assert module_path == "routes.auth"

    def test_python_nested_file_path(self, service):
        """Test nested Python file path conversion."""
        module_path = service._file_to_module_path(
            file_path="/home/user/project/api/services/caches/redis_cache.py",
            repository_root="/home/user/project",
            language="python"
        )

        assert module_path == "services.caches.redis_cache"

    def test_python_init_file_removal(self, service):
        """Test __init__.py is removed from module path."""
        module_path = service._file_to_module_path(
            file_path="/home/user/project/api/models/__init__.py",
            repository_root="/home/user/project",
            language="python"
        )

        assert module_path == "models"

    def test_javascript_file_path_conversion(self, service):
        """Test JavaScript file path conversion."""
        module_path = service._file_to_module_path(
            file_path="/home/user/project/src/components/Button.jsx",
            repository_root="/home/user/project",
            language="javascript"
        )

        assert module_path == "components.Button"

    def test_typescript_file_path_conversion(self, service):
        """Test TypeScript file path conversion."""
        module_path = service._file_to_module_path(
            file_path="/home/user/project/src/components/Button.tsx",
            repository_root="/home/user/project",
            language="typescript"
        )

        assert module_path == "components.Button"

    def test_go_file_path_conversion(self, service):
        """Test Go file path conversion."""
        module_path = service._file_to_module_path(
            file_path="/home/user/project/pkg/models/user.go",
            repository_root="/home/user/project",
            language="go"
        )

        assert module_path == "models.user"


class TestParentContextOrdering:
    """
    FIX #1: Test parent context ordering (outermost → innermost).

    Critical test: Ensures reverse=True is applied correctly.
    Without reverse=True, ordering would be reversed.
    """

    @pytest.fixture
    def service(self):
        return SymbolPathService()

    def test_single_parent_class(self, service):
        """Test single parent class extraction."""
        # Setup: Method inside a class
        method = MockCodeChunk(
            name="validate",
            chunk_type="method",
            start_line=10,
            end_line=15
        )

        parent_class = MockCodeChunk(
            name="User",
            chunk_type="class",
            start_line=5,
            end_line=20
        )

        all_chunks = [method, parent_class]

        parent_context = service.extract_parent_context(method, all_chunks)

        assert parent_context == ["User"]

    def test_nested_classes_ordering(self, service):
        """
        FIX #1: Test nested classes are returned in outermost → innermost order.

        Structure:
            class Outer:           # Lines 1-30 (range: 29)
                class Middle:      # Lines 5-25 (range: 20)
                    class Inner:   # Lines 10-20 (range: 10)
                        def method():  # Lines 15-17 (range: 2)

        Expected parent_context: ["Outer", "Middle", "Inner"]
        Wrong (without reverse=True): ["Inner", "Middle", "Outer"]
        """
        method = MockCodeChunk(
            name="method",
            chunk_type="method",
            start_line=15,
            end_line=17
        )

        inner_class = MockCodeChunk(
            name="Inner",
            chunk_type="class",
            start_line=10,
            end_line=20
        )

        middle_class = MockCodeChunk(
            name="Middle",
            chunk_type="class",
            start_line=5,
            end_line=25
        )

        outer_class = MockCodeChunk(
            name="Outer",
            chunk_type="class",
            start_line=1,
            end_line=30
        )

        all_chunks = [method, inner_class, middle_class, outer_class]

        parent_context = service.extract_parent_context(method, all_chunks)

        # CRITICAL: Must be outermost → innermost
        assert parent_context == ["Outer", "Middle", "Inner"]
        # This would FAIL without reverse=True in symbol_path_service.py:222

    def test_deeply_nested_classes(self, service):
        """Test deeply nested classes (4 levels)."""
        method = MockCodeChunk(
            name="execute",
            chunk_type="method",
            start_line=25,
            end_line=27
        )

        level4 = MockCodeChunk(
            name="Level4",
            chunk_type="class",
            start_line=20,
            end_line=30
        )

        level3 = MockCodeChunk(
            name="Level3",
            chunk_type="class",
            start_line=15,
            end_line=35
        )

        level2 = MockCodeChunk(
            name="Level2",
            chunk_type="class",
            start_line=10,
            end_line=40
        )

        level1 = MockCodeChunk(
            name="Level1",
            chunk_type="class",
            start_line=5,
            end_line=45
        )

        all_chunks = [method, level4, level3, level2, level1]

        parent_context = service.extract_parent_context(method, all_chunks)

        assert parent_context == ["Level1", "Level2", "Level3", "Level4"]

    def test_sibling_classes_not_included(self, service):
        """Test sibling classes are not included as parents."""
        method = MockCodeChunk(
            name="validate",
            chunk_type="method",
            start_line=15,
            end_line=18
        )

        parent_class = MockCodeChunk(
            name="User",
            chunk_type="class",
            start_line=10,
            end_line=20
        )

        sibling_class = MockCodeChunk(
            name="Admin",
            chunk_type="class",
            start_line=25,
            end_line=35
        )

        all_chunks = [method, parent_class, sibling_class]

        parent_context = service.extract_parent_context(method, all_chunks)

        # Only parent, not sibling
        assert parent_context == ["User"]


class TestStrictContainmentCheck:
    """
    FIX #3: Test strict containment checks (< and > instead of <= and >=).

    Edge cases that would fail with non-strict containment (<=, >=).
    """

    @pytest.fixture
    def service(self):
        return SymbolPathService()

    def test_same_start_line_not_parent(self, service):
        """
        FIX #3: Class starting at same line as method should NOT be parent.

        Structure:
            def outer(): class Inner:  # Line 10 (method and class both start here)

        This edge case would incorrectly detect Inner as parent with <= operator.
        """
        method = MockCodeChunk(
            name="outer",
            chunk_type="method",
            start_line=10,
            end_line=20
        )

        inner_class = MockCodeChunk(
            name="Inner",
            chunk_type="class",
            start_line=10,  # SAME as method start
            end_line=25
        )

        all_chunks = [method, inner_class]

        parent_context = service.extract_parent_context(method, all_chunks)

        # Must be empty (strict containment requires < not <=)
        assert parent_context == []

    def test_same_end_line_not_parent(self, service):
        """
        FIX #3: Class ending at same line as method should NOT be parent.

        Structure:
            class Outer: def method():  # Line 20 (both end here)

        This edge case would incorrectly detect Outer as parent with >= operator.
        """
        method = MockCodeChunk(
            name="method",
            chunk_type="method",
            start_line=15,
            end_line=20
        )

        outer_class = MockCodeChunk(
            name="Outer",
            chunk_type="class",
            start_line=10,
            end_line=20  # SAME as method end
        )

        all_chunks = [method, outer_class]

        parent_context = service.extract_parent_context(method, all_chunks)

        # Must be empty (strict containment requires > not >=)
        assert parent_context == []

    def test_exact_same_range_not_parent(self, service):
        """
        FIX #3: Chunk with exact same range should NOT be parent.

        This handles the case where two chunks have identical start and end lines.
        """
        chunk1 = MockCodeChunk(
            name="chunk1",
            chunk_type="method",
            start_line=10,
            end_line=20
        )

        chunk2 = MockCodeChunk(
            name="chunk2",
            chunk_type="class",
            start_line=10,
            end_line=20
        )

        all_chunks = [chunk1, chunk2]

        parent_context = service.extract_parent_context(chunk1, all_chunks)

        assert parent_context == []

    def test_valid_strict_containment(self, service):
        """
        FIX #3: Valid strict containment (parent starts BEFORE and ends AFTER).

        Structure:
            class Outer:     # Lines 10-30
                def method():  # Lines 15-20
        """
        method = MockCodeChunk(
            name="method",
            chunk_type="method",
            start_line=15,
            end_line=20
        )

        outer_class = MockCodeChunk(
            name="Outer",
            chunk_type="class",
            start_line=10,  # < 15 (BEFORE)
            end_line=30     # > 20 (AFTER)
        )

        all_chunks = [method, outer_class]

        parent_context = service.extract_parent_context(method, all_chunks)

        # Valid strict containment
        assert parent_context == ["Outer"]

    def test_adjacent_ranges_not_parent(self, service):
        """
        FIX #3: Adjacent ranges should NOT detect parent relationship.

        Structure:
            class A:  # Lines 10-20
            class B:  # Lines 21-30
        """
        class_b = MockCodeChunk(
            name="B",
            chunk_type="class",
            start_line=21,
            end_line=30
        )

        class_a = MockCodeChunk(
            name="A",
            chunk_type="class",
            start_line=10,
            end_line=20
        )

        all_chunks = [class_a, class_b]

        parent_context = service.extract_parent_context(class_b, all_chunks)

        # No parent (adjacent, not contained)
        assert parent_context == []


class TestIntegrationScenarios:
    """Integration tests combining all fixes."""

    @pytest.fixture
    def service(self):
        return SymbolPathService()

    def test_realistic_nested_class_scenario(self, service):
        """
        Test realistic scenario: nested classes with methods.

        Structure:
            class CacheManager:        # Lines 1-50
                class RedisCache:      # Lines 10-40
                    def connect():     # Lines 20-25
        """
        connect_method = MockCodeChunk(
            name="connect",
            chunk_type="method",
            start_line=20,
            end_line=25
        )

        redis_cache = MockCodeChunk(
            name="RedisCache",
            chunk_type="class",
            start_line=10,
            end_line=40
        )

        cache_manager = MockCodeChunk(
            name="CacheManager",
            chunk_type="class",
            start_line=1,
            end_line=50
        )

        all_chunks = [connect_method, redis_cache, cache_manager]

        # Extract parent context
        parent_context = service.extract_parent_context(connect_method, all_chunks)
        assert parent_context == ["CacheManager", "RedisCache"]

        # Generate full name_path
        name_path = service.generate_name_path(
            chunk_name="connect",
            file_path="/home/user/project/api/services/cache.py",
            repository_root="/home/user/project",
            parent_context=parent_context,
            language="python"
        )

        assert name_path == "services.cache.CacheManager.RedisCache.connect"

    def test_function_not_method_no_parent(self, service):
        """Test top-level function has no parent context."""
        function = MockCodeChunk(
            name="calculate_total",
            chunk_type="function",
            start_line=10,
            end_line=15
        )

        some_class = MockCodeChunk(
            name="SomeClass",
            chunk_type="class",
            start_line=20,
            end_line=30
        )

        all_chunks = [function, some_class]

        parent_context = service.extract_parent_context(function, all_chunks)

        # No parent (function is not contained in class)
        assert parent_context == []
