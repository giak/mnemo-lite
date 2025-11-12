# Python Indexing Support (EPIC-29) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Python language support to MnemoLite code indexing with AST parsing, metadata extraction, embeddings, and call graph construction.

**Architecture:** Extend existing Protocol-based metadata extraction architecture by implementing PythonMetadataExtractor that follows the same pattern as TypeScriptMetadataExtractor. Use tree-sitter for AST parsing with Python-specific queries for imports, calls, decorators, type hints, and async patterns.

**Tech Stack:** tree-sitter-python (via tree-sitter-language-pack), Protocol-based DIP pattern, pytest for TDD

**Validation:** Dog-fooding - index MnemoLite's 170 Python files and validate MCP search can find key functions/classes

---

## Task 1: Create PythonMetadataExtractor with Basic Imports (Story 29.1 Part 1)

**Files:**
- Create: `api/services/metadata_extractors/python_extractor.py`
- Create: `tests/services/metadata_extractors/test_python_extractor.py`

### Step 1: Write failing test for basic imports

**File:** `tests/services/metadata_extractors/test_python_extractor.py`

```python
"""
Tests for Python metadata extractor.
"""

import pytest
from tree_sitter_language_pack import get_parser
from services.metadata_extractors.python_extractor import PythonMetadataExtractor


@pytest.fixture
def python_extractor():
    """Create a PythonMetadataExtractor instance."""
    return PythonMetadataExtractor()


@pytest.fixture
def python_parser():
    """Create a tree-sitter Python parser."""
    return get_parser("python")


@pytest.mark.asyncio
async def test_extract_basic_import(python_extractor, python_parser):
    """Test extraction of basic import statement."""
    source_code = "import os"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["os"]


@pytest.mark.asyncio
async def test_extract_from_import(python_extractor, python_parser):
    """Test extraction of from...import statement."""
    source_code = "from pathlib import Path"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["pathlib.Path"]


@pytest.mark.asyncio
async def test_extract_from_import_multiple(python_extractor, python_parser):
    """Test extraction of from...import with multiple names."""
    source_code = "from typing import List, Dict, Optional"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["typing.List", "typing.Dict", "typing.Optional"]


@pytest.mark.asyncio
async def test_extract_from_import_alias(python_extractor, python_parser):
    """Test extraction of import with alias."""
    source_code = "from datetime import datetime as dt"
    tree = python_parser.parse(bytes(source_code, "utf8"))

    imports = await python_extractor.extract_imports(tree, source_code)

    assert imports == ["datetime.datetime"]
```

### Step 2: Run tests to verify they fail

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py -v
```

**Expected:** FAIL with "ModuleNotFoundError: No module named 'services.metadata_extractors.python_extractor'"

### Step 3: Create PythonMetadataExtractor skeleton

**File:** `api/services/metadata_extractors/python_extractor.py`

```python
"""
Python metadata extractor using tree-sitter.

EPIC-29 Story 29.1: Python import extraction.
EPIC-29 Story 29.1: Python call extraction.
"""

import logging
from typing import Any
from tree_sitter import Node, Tree, Query, QueryCursor
from tree_sitter_language_pack import get_language


logger = logging.getLogger(__name__)


class PythonMetadataExtractor:
    """
    Extract metadata from Python using tree-sitter queries.

    Supports:
    - Import statements (import X, from X import Y)
    - Function calls
    - Decorators
    - Type hints
    - Async/await patterns
    """

    def __init__(self):
        """Initialize Python language and queries."""
        self.language = get_language("python")
        self.language_name = "python"
        self.logger = logging.getLogger(__name__)

        # Import extraction queries
        self.basic_import_query = Query(
            self.language,
            "(import_statement name: (dotted_name) @import_name)"
        )

        self.from_import_query = Query(
            self.language,
            "(import_from_statement module_name: (dotted_name) @module_name name: (dotted_name) @import_name)"
        )

        self.from_import_alias_query = Query(
            self.language,
            "(import_from_statement module_name: (dotted_name) @module_name name: (aliased_import name: (dotted_name) @import_name))"
        )

    async def extract_imports(self, tree: Tree, source_code: str) -> list[str]:
        """
        Extract import statements from Python code.

        Args:
            tree: tree-sitter AST tree
            source_code: Full source code (for byte range extraction)

        Returns:
            List of import references (e.g., ['os', 'pathlib.Path'])
        """
        imports = []
        source_bytes = bytes(source_code, "utf8")
        cursor = QueryCursor()

        # Extract basic imports (import X)
        for match in cursor.matches(self.basic_import_query, tree.root_node):
            for capture_name, node in match[1].items():
                if capture_name == "import_name":
                    import_text = source_bytes[node.start_byte:node.end_byte].decode("utf8")
                    imports.append(import_text)

        # Extract from imports (from X import Y)
        module_imports = {}
        for match in cursor.matches(self.from_import_query, tree.root_node):
            module_name = None
            import_name = None
            for capture_name, node in match[1].items():
                text = source_bytes[node.start_byte:node.end_byte].decode("utf8")
                if capture_name == "module_name":
                    module_name = text
                elif capture_name == "import_name":
                    import_name = text

            if module_name and import_name:
                imports.append(f"{module_name}.{import_name}")

        # Extract from imports with aliases (from X import Y as Z)
        for match in cursor.matches(self.from_import_alias_query, tree.root_node):
            module_name = None
            import_name = None
            for capture_name, node in match[1].items():
                text = source_bytes[node.start_byte:node.end_byte].decode("utf8")
                if capture_name == "module_name":
                    module_name = text
                elif capture_name == "import_name":
                    import_name = text

            if module_name and import_name:
                imports.append(f"{module_name}.{import_name}")

        return imports

    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function/method calls from a code node.

        Args:
            node: tree-sitter AST node (function, class, method)
            source_code: Full source code (for byte range extraction)

        Returns:
            List of call references (e.g., ['calculate_total', 'service.fetch_data'])
        """
        # TODO: Implement in next step
        return []

    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata (imports + calls + other) from a code node.

        Args:
            source_code: Full source code
            node: tree-sitter AST node
            tree: Full AST tree

        Returns:
            Metadata dict with: {"imports": [...], "calls": [...]}
        """
        imports = await self.extract_imports(tree, source_code)
        calls = await self.extract_calls(node, source_code)

        return {
            "imports": imports,
            "calls": calls
        }
```

### Step 4: Run tests to verify they pass

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_basic_import -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_from_import -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_from_import_multiple -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_from_import_alias -v
```

**Expected:** All tests PASS

### Step 5: Commit

```bash
git add api/services/metadata_extractors/python_extractor.py tests/services/metadata_extractors/test_python_extractor.py
git commit -m "feat(EPIC-29): Add PythonMetadataExtractor with basic import extraction

Story 29.1 Part 1: Implement Protocol methods with Python import support
- Basic imports (import X)
- From imports (from X import Y)
- Multiple imports (from X import A, B, C)
- Aliased imports (from X import Y as Z)

Tests: 4/4 passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Add Call Extraction with Basic Patterns (Story 29.1 Part 2)

**Files:**
- Modify: `api/services/metadata_extractors/python_extractor.py`
- Modify: `tests/services/metadata_extractors/test_python_extractor.py`

### Step 1: Write failing tests for call extraction

**File:** `tests/services/metadata_extractors/test_python_extractor.py` (append)

```python
@pytest.mark.asyncio
async def test_extract_basic_call(python_extractor, python_parser):
    """Test extraction of basic function call."""
    source_code = """
def my_function():
    result = calculate_total()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]  # function_definition

    calls = await python_extractor.extract_calls(function_node, source_code)

    assert "calculate_total" in calls


@pytest.mark.asyncio
async def test_extract_method_call(python_extractor, python_parser):
    """Test extraction of method call."""
    source_code = """
def my_function():
    result = service.fetch_data()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(function_node, source_code)

    assert "service.fetch_data" in calls


@pytest.mark.asyncio
async def test_extract_chained_call(python_extractor, python_parser):
    """Test extraction of chained method calls."""
    source_code = """
def my_function():
    result = database.session.query(User).all()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(function_node, source_code)

    assert "database.session.query" in calls
```

### Step 2: Run tests to verify they fail

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_basic_call -v
```

**Expected:** FAIL with assertion error (empty list)

### Step 3: Implement call extraction

**File:** `api/services/metadata_extractors/python_extractor.py` (modify __init__ and extract_calls)

Update `__init__` to add call query:

```python
    def __init__(self):
        """Initialize Python language and queries."""
        self.language = get_language("python")
        self.language_name = "python"
        self.logger = logging.getLogger(__name__)

        # Import extraction queries
        self.basic_import_query = Query(
            self.language,
            "(import_statement name: (dotted_name) @import_name)"
        )

        self.from_import_query = Query(
            self.language,
            "(import_from_statement module_name: (dotted_name) @module_name name: (dotted_name) @import_name)"
        )

        self.from_import_alias_query = Query(
            self.language,
            "(import_from_statement module_name: (dotted_name) @module_name name: (aliased_import name: (dotted_name) @import_name))"
        )

        # Call extraction query
        self.call_query = Query(
            self.language,
            "(call function: (_) @call_function)"
        )
```

Update `extract_calls`:

```python
    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function/method calls from a code node.

        Args:
            node: tree-sitter AST node (function, class, method)
            source_code: Full source code (for byte range extraction)

        Returns:
            List of call references (e.g., ['calculate_total', 'service.fetch_data'])
        """
        calls = []
        source_bytes = bytes(source_code, "utf8")
        cursor = QueryCursor()

        # Extract all calls within the node
        for match in cursor.matches(self.call_query, node):
            for capture_name, call_node in match[1].items():
                if capture_name == "call_function":
                    call_text = self._extract_call_name(call_node, source_bytes)
                    if call_text:
                        calls.append(call_text)

        return list(set(calls))  # Deduplicate

    def _extract_call_name(self, node: Node, source_bytes: bytes) -> str:
        """
        Extract the full call name from a call node.

        Handles:
        - Simple calls: function()
        - Method calls: object.method()
        - Chained calls: obj.a.b.method()
        """
        if node.type == "identifier":
            return source_bytes[node.start_byte:node.end_byte].decode("utf8")

        elif node.type == "attribute":
            # For attribute access (obj.method), build full path
            parts = []
            current = node
            while current and current.type == "attribute":
                # Get the attribute name (rightmost part)
                attr_node = current.child_by_field_name("attribute")
                if attr_node:
                    parts.insert(0, source_bytes[attr_node.start_byte:attr_node.end_byte].decode("utf8"))

                # Move to the object (left side)
                current = current.child_by_field_name("object")

            # Get the base object name
            if current and current.type == "identifier":
                parts.insert(0, source_bytes[current.start_byte:current.end_byte].decode("utf8"))

            return ".".join(parts) if parts else ""

        return ""
```

### Step 4: Run tests to verify they pass

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_basic_call -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_method_call -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_chained_call -v
```

**Expected:** All 3 tests PASS

### Step 5: Commit

```bash
git add api/services/metadata_extractors/python_extractor.py tests/services/metadata_extractors/test_python_extractor.py
git commit -m "feat(EPIC-29): Add Python call extraction support

Story 29.1 Part 2: Implement call extraction with tree-sitter queries
- Basic calls (function())
- Method calls (object.method())
- Chained calls (obj.a.b.method())

Tests: 7/7 passing (4 imports + 3 calls)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Add Decorator Detection (Story 29.2 Part 1)

**Files:**
- Modify: `api/services/metadata_extractors/python_extractor.py`
- Modify: `tests/services/metadata_extractors/test_python_extractor.py`

### Step 1: Write failing tests for decorators

**File:** `tests/services/metadata_extractors/test_python_extractor.py` (append)

```python
@pytest.mark.asyncio
async def test_extract_metadata_with_decorator(python_extractor, python_parser):
    """Test metadata extraction includes decorator information."""
    source_code = """
@dataclass
class User:
    name: str
    age: int
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]  # decorated_definition

    metadata = await python_extractor.extract_metadata(source_code, class_node, tree)

    assert "decorators" in metadata
    assert "dataclass" in metadata["decorators"]


@pytest.mark.asyncio
async def test_extract_metadata_with_property_decorator(python_extractor, python_parser):
    """Test extraction of @property decorator."""
    source_code = """
class MyClass:
    @property
    def value(self):
        return self._value
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, class_node, tree)

    assert "decorators" in metadata
    assert "property" in metadata["decorators"]


@pytest.mark.asyncio
async def test_extract_metadata_with_async_decorator(python_extractor, python_parser):
    """Test extraction of custom async decorator."""
    source_code = """
@async_cached
async def fetch_data():
    return await database.query()
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, function_node, tree)

    assert "decorators" in metadata
    assert "async_cached" in metadata["decorators"]
    assert metadata.get("is_async") is True
```

### Step 2: Run tests to verify they fail

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_metadata_with_decorator -v
```

**Expected:** FAIL with KeyError: 'decorators'

### Step 3: Implement decorator extraction

**File:** `api/services/metadata_extractors/python_extractor.py`

Add to `__init__`:

```python
        # Decorator extraction query
        self.decorator_query = Query(
            self.language,
            """
            (decorated_definition
              (decorator) @decorator)
            """
        )
```

Add new method `extract_decorators`:

```python
    async def extract_decorators(self, node: Node, source_code: str) -> list[str]:
        """
        Extract decorator names from a node.

        Args:
            node: tree-sitter AST node
            source_code: Full source code

        Returns:
            List of decorator names (e.g., ['dataclass', 'property'])
        """
        decorators = []
        source_bytes = bytes(source_code, "utf8")
        cursor = QueryCursor()

        # Check if this is a decorated definition
        if node.type == "decorated_definition":
            for match in cursor.matches(self.decorator_query, node):
                for capture_name, decorator_node in match[1].items():
                    if capture_name == "decorator":
                        # Decorator node includes '@', get the name after it
                        decorator_text = source_bytes[decorator_node.start_byte:decorator_node.end_byte].decode("utf8")
                        # Remove '@' and get just the name (handle @decorator and @decorator())
                        decorator_name = decorator_text.lstrip("@").split("(")[0].strip()
                        decorators.append(decorator_name)

        return decorators

    def _is_async_function(self, node: Node) -> bool:
        """
        Check if a function node is async.

        Args:
            node: tree-sitter AST node

        Returns:
            True if function is async, False otherwise
        """
        # Check decorated_definition wrapping async function
        if node.type == "decorated_definition":
            definition = node.child_by_field_name("definition")
            if definition and definition.type == "function_definition":
                # Check if 'async' keyword is present
                for child in definition.children:
                    if child.type == "async":
                        return True

        # Check direct function_definition
        elif node.type == "function_definition":
            for child in node.children:
                if child.type == "async":
                    return True

        return False
```

Update `extract_metadata`:

```python
    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata (imports + calls + decorators + async) from a code node.

        Args:
            source_code: Full source code
            node: tree-sitter AST node
            tree: Full AST tree

        Returns:
            Metadata dict with: {"imports": [...], "calls": [...], "decorators": [...], "is_async": bool}
        """
        imports = await self.extract_imports(tree, source_code)
        calls = await self.extract_calls(node, source_code)
        decorators = await self.extract_decorators(node, source_code)
        is_async = self._is_async_function(node)

        return {
            "imports": imports,
            "calls": calls,
            "decorators": decorators,
            "is_async": is_async
        }
```

### Step 4: Run tests to verify they pass

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_metadata_with_decorator -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_metadata_with_property_decorator -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_metadata_with_async_decorator -v
```

**Expected:** All 3 tests PASS

### Step 5: Commit

```bash
git add api/services/metadata_extractors/python_extractor.py tests/services/metadata_extractors/test_python_extractor.py
git commit -m "feat(EPIC-29): Add Python decorator and async detection

Story 29.2 Part 1: Extract decorators and detect async functions
- Decorator extraction (@dataclass, @property, custom)
- Async function detection (async def)
- Enhanced metadata dict with decorators and is_async fields

Tests: 10/10 passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Add Type Hints Extraction (Story 29.2 Part 2)

**Files:**
- Modify: `api/services/metadata_extractors/python_extractor.py`
- Modify: `tests/services/metadata_extractors/test_python_extractor.py`

### Step 1: Write failing tests for type hints

**File:** `tests/services/metadata_extractors/test_python_extractor.py` (append)

```python
@pytest.mark.asyncio
async def test_extract_type_hints_from_function(python_extractor, python_parser):
    """Test extraction of function parameter type hints."""
    source_code = """
def process_data(items: List[str], count: int) -> Dict[str, int]:
    return {}
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, function_node, tree)

    assert "type_hints" in metadata
    type_hints = metadata["type_hints"]
    assert "parameters" in type_hints
    assert "return_type" in type_hints
    assert type_hints["return_type"] == "Dict[str, int]"


@pytest.mark.asyncio
async def test_extract_optional_type_hint(python_extractor, python_parser):
    """Test extraction of Optional type hint."""
    source_code = """
def get_user(user_id: int) -> Optional[User]:
    return None
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, function_node, tree)

    assert metadata["type_hints"]["return_type"] == "Optional[User]"


@pytest.mark.asyncio
async def test_extract_class_attribute_type_hints(python_extractor, python_parser):
    """Test extraction of class attribute type hints."""
    source_code = """
class User:
    name: str
    age: int
    email: Optional[str] = None
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]

    metadata = await python_extractor.extract_metadata(source_code, class_node, tree)

    assert "type_hints" in metadata
    assert "attributes" in metadata["type_hints"]
```

### Step 2: Run tests to verify they fail

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_type_hints_from_function -v
```

**Expected:** FAIL with KeyError: 'type_hints'

### Step 3: Implement type hints extraction

**File:** `api/services/metadata_extractors/python_extractor.py`

Add to `__init__`:

```python
        # Type hint extraction queries
        self.function_type_query = Query(
            self.language,
            """
            (function_definition
              parameters: (parameters
                (typed_parameter
                  type: (_) @param_type))
              return_type: (type) @return_type)
            """
        )

        self.class_attribute_type_query = Query(
            self.language,
            """
            (class_definition
              body: (block
                (expression_statement
                  (assignment
                    left: (identifier) @attr_name
                    type: (type) @attr_type))))
            """
        )
```

Add new method `extract_type_hints`:

```python
    async def extract_type_hints(self, node: Node, source_code: str) -> dict[str, Any]:
        """
        Extract type hints from function signatures or class attributes.

        Args:
            node: tree-sitter AST node
            source_code: Full source code

        Returns:
            Dict with type hint information:
            - For functions: {"parameters": [...], "return_type": "..."}
            - For classes: {"attributes": {"name": "type", ...}}
        """
        type_hints = {}
        source_bytes = bytes(source_code, "utf8")
        cursor = QueryCursor()

        # Extract function type hints
        if node.type == "function_definition" or (node.type == "decorated_definition" and
           node.child_by_field_name("definition") and
           node.child_by_field_name("definition").type == "function_definition"):

            func_node = node if node.type == "function_definition" else node.child_by_field_name("definition")

            # Get return type
            return_type_node = func_node.child_by_field_name("return_type")
            if return_type_node:
                return_type_text = source_bytes[return_type_node.start_byte:return_type_node.end_byte].decode("utf8")
                type_hints["return_type"] = return_type_text.strip()

            # Get parameter types
            parameters_node = func_node.child_by_field_name("parameters")
            if parameters_node:
                param_types = []
                for child in parameters_node.children:
                    if child.type == "typed_parameter":
                        param_name_node = child.child_by_field_name("name")
                        param_type_node = child.child_by_field_name("type")
                        if param_name_node and param_type_node:
                            param_name = source_bytes[param_name_node.start_byte:param_name_node.end_byte].decode("utf8")
                            param_type = source_bytes[param_type_node.start_byte:param_type_node.end_byte].decode("utf8")
                            param_types.append({"name": param_name, "type": param_type})

                if param_types:
                    type_hints["parameters"] = param_types

        # Extract class attribute type hints
        elif node.type == "class_definition" or (node.type == "decorated_definition" and
             node.child_by_field_name("definition") and
             node.child_by_field_name("definition").type == "class_definition"):

            class_node = node if node.type == "class_definition" else node.child_by_field_name("definition")
            body_node = class_node.child_by_field_name("body")

            if body_node:
                attributes = {}
                for child in body_node.children:
                    # Look for annotated assignments (name: type = value)
                    if child.type == "expression_statement":
                        for expr_child in child.children:
                            if expr_child.type == "assignment":
                                # Get attribute name and type
                                left_node = expr_child.child_by_field_name("left")
                                type_node = expr_child.child_by_field_name("type")

                                if left_node and type_node:
                                    attr_name = source_bytes[left_node.start_byte:left_node.end_byte].decode("utf8")
                                    attr_type = source_bytes[type_node.start_byte:type_node.end_byte].decode("utf8")
                                    attributes[attr_name] = attr_type

                if attributes:
                    type_hints["attributes"] = attributes

        return type_hints
```

Update `extract_metadata`:

```python
    async def extract_metadata(
        self,
        source_code: str,
        node: Node,
        tree: Tree
    ) -> dict[str, Any]:
        """
        Extract all metadata from a code node.

        Returns:
            Metadata dict with: imports, calls, decorators, is_async, type_hints
        """
        imports = await self.extract_imports(tree, source_code)
        calls = await self.extract_calls(node, source_code)
        decorators = await self.extract_decorators(node, source_code)
        is_async = self._is_async_function(node)
        type_hints = await self.extract_type_hints(node, source_code)

        return {
            "imports": imports,
            "calls": calls,
            "decorators": decorators,
            "is_async": is_async,
            "type_hints": type_hints
        }
```

### Step 4: Run tests to verify they pass

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_type_hints_from_function -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_optional_type_hint -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_extract_class_attribute_type_hints -v
```

**Expected:** All 3 tests PASS

### Step 5: Commit

```bash
git add api/services/metadata_extractors/python_extractor.py tests/services/metadata_extractors/test_python_extractor.py
git commit -m "feat(EPIC-29): Add Python type hints extraction

Story 29.2 Part 2: Extract type hints from functions and classes
- Function parameter types (items: List[str])
- Function return types (-> Dict[str, int])
- Class attribute types (name: str)
- Support for Optional, List, Dict, Union types

Tests: 13/13 passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Add Framework Blacklist for Pytest/Unittest (Story 29.3)

**Files:**
- Modify: `api/services/metadata_extractors/python_extractor.py`
- Modify: `tests/services/metadata_extractors/test_python_extractor.py`

### Step 1: Write failing tests for framework blacklist

**File:** `tests/services/metadata_extractors/test_python_extractor.py` (append)

```python
@pytest.mark.asyncio
async def test_framework_blacklist_pytest(python_extractor, python_parser):
    """Test that pytest framework functions are filtered out."""
    source_code = """
def test_user_creation():
    user = create_user("John")
    assert user.name == "John"
    mock.patch("database.save")
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(function_node, source_code)

    # Should include create_user but NOT assert, mock.patch
    assert "create_user" in calls
    assert "assert" not in calls
    assert "mock.patch" not in calls


@pytest.mark.asyncio
async def test_framework_blacklist_unittest(python_extractor, python_parser):
    """Test that unittest framework methods are filtered out."""
    source_code = """
class TestUser(unittest.TestCase):
    def setUp(self):
        self.user = User()

    def test_name(self):
        self.assertEqual(self.user.name, "John")
        self.assertTrue(self.user.is_active)
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    class_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(class_node, source_code)

    # Should NOT include assertEqual, assertTrue, setUp (blacklisted)
    assert "assertEqual" not in calls
    assert "assertTrue" not in calls
    assert "setUp" not in calls


@pytest.mark.asyncio
async def test_print_debug_blacklist(python_extractor, python_parser):
    """Test that print/debug statements are filtered out."""
    source_code = """
def process_data(items):
    print("Processing items")
    result = calculate(items)
    breakpoint()
    return result
"""
    tree = python_parser.parse(bytes(source_code, "utf8"))
    function_node = tree.root_node.children[0]

    calls = await python_extractor.extract_calls(function_node, source_code)

    # Should include calculate but NOT print, breakpoint
    assert "calculate" in calls
    assert "print" not in calls
    assert "breakpoint" not in calls
```

### Step 2: Run tests to verify they fail

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_framework_blacklist_pytest -v
```

**Expected:** FAIL with assertion error (blacklisted functions are included)

### Step 3: Add framework blacklist

**File:** `api/services/metadata_extractors/python_extractor.py`

Add class constant after class definition:

```python
class PythonMetadataExtractor:
    """
    Extract metadata from Python using tree-sitter queries.
    """

    # EPIC-29 Story 29.3: Framework function blacklist
    # Common test framework functions to filter out (reduce noise)
    FRAMEWORK_BLACKLIST = {
        # pytest
        "describe", "it", "test", "fixture", "mock", "patch", "monkeypatch",
        "parametrize", "mark", "raises", "warns", "approx", "capfd", "capsys",
        "tmpdir", "tmp_path",
        # pytest assertions (though these are statements, not calls)
        "assert",
        # unittest.TestCase methods
        "setUp", "tearDown", "setUpClass", "tearDownClass",
        "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
        "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
        "assertIn", "assertNotIn", "assertIsInstance", "assertNotIsInstance",
        "assertRaises", "assertRaisesRegex", "assertWarns", "assertWarnsRegex",
        "assertAlmostEqual", "assertNotAlmostEqual", "assertGreater",
        "assertGreaterEqual", "assertLess", "assertLessEqual",
        "assertRegex", "assertNotRegex", "assertCountEqual",
        "assertMultiLineEqual", "assertSequenceEqual", "assertListEqual",
        "assertTupleEqual", "assertSetEqual", "assertDictEqual",
        "fail", "skipTest", "subTest",
        # Mock/patch
        "MagicMock", "Mock", "create_autospec", "seal",
        # Common debugging
        "print", "breakpoint", "pdb", "set_trace",
        # Logging (too generic, creates noise)
        "debug", "info", "warning", "error", "critical",
    }

    def __init__(self):
        # ... existing code ...
```

Update `extract_calls` to filter blacklist:

```python
    async def extract_calls(self, node: Node, source_code: str) -> list[str]:
        """
        Extract function/method calls from a code node.

        Filters out framework functions from FRAMEWORK_BLACKLIST.

        Args:
            node: tree-sitter AST node (function, class, method)
            source_code: Full source code (for byte range extraction)

        Returns:
            List of call references (e.g., ['calculate_total', 'service.fetch_data'])
        """
        calls = []
        source_bytes = bytes(source_code, "utf8")
        cursor = QueryCursor()

        # Extract all calls within the node
        for match in cursor.matches(self.call_query, node):
            for capture_name, call_node in match[1].items():
                if capture_name == "call_function":
                    call_text = self._extract_call_name(call_node, source_bytes)
                    if call_text and not self._is_blacklisted(call_text):
                        calls.append(call_text)

        return list(set(calls))  # Deduplicate

    def _is_blacklisted(self, call_name: str) -> bool:
        """
        Check if a call name should be filtered out.

        Args:
            call_name: Full call name (e.g., 'mock.patch', 'assertEqual')

        Returns:
            True if blacklisted, False otherwise
        """
        # Check both full name and last part (for method calls)
        # e.g., "self.assertEqual" -> check "assertEqual"
        parts = call_name.split(".")
        last_part = parts[-1] if parts else call_name

        return (call_name in self.FRAMEWORK_BLACKLIST or
                last_part in self.FRAMEWORK_BLACKLIST)
```

### Step 4: Run tests to verify they pass

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_framework_blacklist_pytest -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_framework_blacklist_unittest -v
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py::test_print_debug_blacklist -v
```

**Expected:** All 3 tests PASS

### Step 5: Run full test suite to verify no regressions

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py -v
```

**Expected:** All 16 tests PASS

### Step 6: Commit

```bash
git add api/services/metadata_extractors/python_extractor.py tests/services/metadata_extractors/test_python_extractor.py
git commit -m "feat(EPIC-29): Add framework blacklist for Python

Story 29.3: Filter out test framework noise from call graph
- pytest: fixture, mock, patch, parametrize, raises
- unittest: assertEqual, assertTrue, setUp, tearDown
- Debug: print, breakpoint, pdb
- Logging: debug, info, warning, error

Reduces call graph noise, improves signal-to-noise ratio

Tests: 16/16 passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Integrate with Metadata Service (Story 29.4 Part 1)

**Files:**
- Modify: `api/services/metadata_extractors/__init__.py`
- Modify: `api/services/metadata_extractor_service.py`
- Create: `tests/integration/test_python_indexing.py`

### Step 1: Write failing integration test

**File:** `tests/integration/test_python_indexing.py`

```python
"""
Integration test for Python indexing pipeline.
"""

import pytest
from pathlib import Path
from services.code_chunking_service import CodeChunkingService
from services.metadata_extractor_service import MetadataExtractorService
from services.metadata_extractors.python_extractor import PythonMetadataExtractor


@pytest.mark.asyncio
async def test_python_file_chunking():
    """Test that Python files can be chunked and metadata extracted."""
    # Create a simple Python file content
    source_code = """
import os
from pathlib import Path
from typing import List, Optional

class DataProcessor:
    def __init__(self, config: dict):
        self.config = config

    async def process_items(self, items: List[str]) -> Optional[dict]:
        result = self.validate(items)
        data = await self.fetch_data()
        return self.merge(result, data)

    def validate(self, items: List[str]) -> dict:
        return {"valid": True}

    async def fetch_data(self) -> dict:
        return {"data": []}

    def merge(self, a: dict, b: dict) -> dict:
        return {**a, **b}
"""

    # Create metadata service with Python extractor
    python_extractor = PythonMetadataExtractor()
    metadata_service = MetadataExtractorService(metadata_extractor=python_extractor)

    # Create chunking service
    chunking_service = CodeChunkingService(max_workers=1, metadata_service=metadata_service)

    # Parse and chunk
    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="test_processor.py",
        language="python"
    )

    # Assertions
    assert len(chunks) > 0, "Should create at least one chunk"

    # Find the process_items method chunk
    process_chunk = next((c for c in chunks if "process_items" in c.content), None)
    assert process_chunk is not None, "Should find process_items method chunk"

    # Check metadata
    metadata = process_chunk.metadata
    assert metadata is not None
    assert "imports" in metadata
    assert "calls" in metadata

    # Check imports extracted
    imports = metadata["imports"]
    assert any("pathlib.Path" in imp for imp in imports)
    assert any("typing.List" in imp for imp in imports)

    # Check calls extracted (should call validate, fetch_data, merge)
    calls = metadata["calls"]
    assert "self.validate" in calls or "validate" in calls
    assert "self.fetch_data" in calls or "fetch_data" in calls
    assert "self.merge" in calls or "merge" in calls

    # Check async detection
    assert metadata.get("is_async") is True

    # Check type hints
    assert "type_hints" in metadata
    type_hints = metadata["type_hints"]
    assert "return_type" in type_hints
    assert "Optional[dict]" in type_hints["return_type"]
```

### Step 2: Run test to verify it fails

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/integration/test_python_indexing.py -v
```

**Expected:** FAIL - MetadataExtractorService doesn't know about PythonMetadataExtractor

### Step 3: Update metadata extractors __init__.py

**File:** `api/services/metadata_extractors/__init__.py`

```python
"""
Metadata extractors package.

Exports all language-specific extractors.
"""

from services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
from services.metadata_extractors.python_extractor import PythonMetadataExtractor

__all__ = [
    "TypeScriptMetadataExtractor",
    "PythonMetadataExtractor",
]
```

### Step 4: Update metadata extractor service to support Python

**File:** `api/services/metadata_extractor_service.py`

Find the `__init__` method and update it to support Python:

```python
    def __init__(self, metadata_extractor=None):
        """
        Initialize MetadataExtractorService.

        Args:
            metadata_extractor: Optional specific extractor (for testing/DI)
        """
        self.typescript_extractor = TypeScriptMetadataExtractor(language="typescript")
        self.javascript_extractor = TypeScriptMetadataExtractor(language="javascript")
        self.python_extractor = PythonMetadataExtractor()

        # Allow dependency injection for testing
        self._injected_extractor = metadata_extractor
```

Find the method that selects extractor by language and update:

```python
    def _get_extractor(self, language: str):
        """Get the appropriate metadata extractor for a language."""
        if self._injected_extractor:
            return self._injected_extractor

        language_lower = language.lower()
        if language_lower == "typescript":
            return self.typescript_extractor
        elif language_lower == "javascript":
            return self.javascript_extractor
        elif language_lower == "python":
            return self.python_extractor
        else:
            # Default to TypeScript for unknown languages
            return self.typescript_extractor
```

### Step 5: Run integration test to verify it passes

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/integration/test_python_indexing.py -v
```

**Expected:** Test PASS

### Step 6: Commit

```bash
git add api/services/metadata_extractors/__init__.py api/services/metadata_extractor_service.py tests/integration/test_python_indexing.py
git commit -m "feat(EPIC-29): Integrate PythonMetadataExtractor into metadata service

Story 29.4 Part 1: Wire up Python extractor to chunking pipeline
- Export PythonMetadataExtractor from package
- Add Python extractor to MetadataExtractorService
- Add language routing for Python files
- Integration test validates full pipeline

Tests: 17/17 passing (16 unit + 1 integration)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Index MnemoLite Python Files (Story 29.4 Part 2)

**Files:**
- Modify: `scripts/index_directory.py` (to support Python)
- Test on live MnemoLite codebase

### Step 1: Check current language detection in index_directory.py

**Command:**
```bash
grep -n "language" /home/giak/Work/MnemoLite/scripts/index_directory.py | head -20
```

**Expected:** Find where language is detected/set

### Step 2: Update scan_files to include Python files

**File:** `scripts/index_directory.py`

Find the `scan_files` function and update to include `.py` files:

```python
def scan_files(directory: Path) -> list[Path]:
    """
    Recursively scan directory for TypeScript/JavaScript/Python files.

    Returns:
        List of file paths
    """
    extensions = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"}
    files = []

    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))

    # Filter out node_modules, .git, __pycache__, etc
    files = [
        f for f in files
        if not any(part.startswith(".") or part in ["node_modules", "dist", "build", "__pycache__", "venv", ".venv"]
                   for part in f.parts)
    ]

    return sorted(files)
```

Find where language is detected from file extension and update:

```python
def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    suffix = file_path.suffix.lower()

    if suffix in [".ts", ".tsx"]:
        return "typescript"
    elif suffix in [".js", ".jsx", ".mjs"]:
        return "javascript"
    elif suffix == ".py":
        return "python"
    else:
        return "typescript"  # default
```

### Step 3: Test indexing on small Python subset

**Command:**
```bash
# Test on just one Python file first
python /home/giak/Work/MnemoLite/scripts/index_directory.py \
  /home/giak/Work/MnemoLite/api/services/metadata_extractors \
  --repository test-python-extractor \
  --verbose
```

**Expected:** Successfully index Python files in metadata_extractors directory

### Step 4: Index full MnemoLite Python codebase

**Command:**
```bash
# Index all Python files in api/
python /home/giak/Work/MnemoLite/scripts/index_directory.py \
  /home/giak/Work/MnemoLite/api \
  --repository mnemolite-python \
  --verbose
```

**Expected:**
- ~170 Python files indexed
- Multiple chunks created
- Graph nodes/edges created
- No errors

### Step 5: Verify indexing results in database

**Command:**
```bash
# Check indexed stats
psql $DATABASE_URL -c "
SELECT
  COUNT(*) as chunks,
  COUNT(DISTINCT file_path) as files
FROM code_chunks
WHERE repository = 'mnemolite-python' AND language = 'python';
"

# Check graph stats
psql $DATABASE_URL -c "
SELECT
  COUNT(*) as nodes
FROM code_graph_nodes
WHERE repository = 'mnemolite-python';
"

psql $DATABASE_URL -c "
SELECT
  COUNT(*) as edges
FROM code_graph_edges
WHERE source_repository = 'mnemolite-python';
"
```

**Expected:**
- chunks > 500
- files ~= 170
- nodes > 300
- edges > 150
- edge ratio (edges/nodes) > 0.40

### Step 6: Commit

```bash
git add scripts/index_directory.py
git commit -m "feat(EPIC-29): Add Python language support to indexing script

Story 29.4 Part 2: Enable Python file indexing
- Add .py extension to scan_files()
- Add detect_language() support for Python
- Filter __pycache__, venv from scanning
- Successfully indexed MnemoLite Python codebase (170 files)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Dog-Fooding Validation with MCP (Story 29.4 Part 3)

**Files:**
- Manual MCP testing
- Document results

### Step 1: Test MCP search for async database functions

**Command (via Claude Code or MCP client):**
```python
mcp__mnemolite__search_code(
    query="async database transaction",
    filters={"language": "python", "repository": "mnemolite-python"},
    limit=10
)
```

**Expected:** Should find functions like:
- `execute_transaction`
- `begin_transaction`
- Database service methods with async

### Step 2: Test MCP search for embedding service

**Command:**
```python
mcp__mnemolite__search_code(
    query="embedding service generate embeddings",
    filters={"language": "python", "repository": "mnemolite-python"},
    limit=10
)
```

**Expected:** Should find:
- `EmbeddingService` class
- `generate_embedding` method
- Embedding-related functions

### Step 3: Test MCP search for hybrid search RRF

**Command:**
```python
mcp__mnemolite__search_code(
    query="hybrid search RRF fusion",
    filters={"language": "python", "repository": "mnemolite-python"},
    limit=10
)
```

**Expected:** Should find:
- `HybridSearchService`
- RRF fusion logic
- Reciprocal rank functions

### Step 4: Test MCP search for metadata extraction

**Command:**
```python
mcp__mnemolite__search_code(
    query="tree-sitter metadata extraction",
    filters={"language": "python", "repository": "mnemolite-python"},
    limit=10
)
```

**Expected:** Should find:
- `MetadataExtractor` classes
- `extract_imports`, `extract_calls` methods
- tree-sitter query code

### Step 5: Document validation results

**File:** `docs/agile/serena-evolution/03_EPICS/EPIC-29_VALIDATION.md`

```markdown
# EPIC-29 Python Indexing - Dog-Fooding Validation

**Date:** 2025-11-07
**Repository:** mnemolite-python (170 Python files)

## Indexing Stats

| Metric | Count |
|--------|-------|
| Files | [FILL] |
| Chunks | [FILL] |
| Nodes | [FILL] |
| Edges | [FILL] |
| Edge Ratio | [FILL]% |

## MCP Search Validation

### Query 1: "async database transaction"
**Top Results:**
1. [FILL] - [file:line]
2. [FILL] - [file:line]
3. [FILL] - [file:line]

**Accuracy:** ✅/⚠️/❌ [Comments]

### Query 2: "embedding service generate embeddings"
**Top Results:**
1. [FILL]
2. [FILL]
3. [FILL]

**Accuracy:** ✅/⚠️/❌

### Query 3: "hybrid search RRF fusion"
**Top Results:**
1. [FILL]
2. [FILL]
3. [FILL]

**Accuracy:** ✅/⚠️/❌

### Query 4: "tree-sitter metadata extraction"
**Top Results:**
1. [FILL]
2. [FILL]
3. [FILL]

**Accuracy:** ✅/⚠️/❌

## Overall Assessment

**Success Criteria:** [PASS/FAIL]
- ✅/❌ Edge ratio > 40%
- ✅/❌ At least 3/4 queries return relevant results
- ✅/❌ Can navigate MnemoLite codebase via MCP

**Conclusion:** [Summary of validation results]

**Next Steps:** [Any improvements needed]
```

### Step 6: Fill in validation document with actual results

Run the MCP queries above and fill in the EPIC-29_VALIDATION.md document with real results.

### Step 7: Commit validation results

```bash
git add docs/agile/serena-evolution/03_EPICS/EPIC-29_VALIDATION.md
git commit -m "docs(EPIC-29): Add dog-fooding validation results

Story 29.4 Part 3: MCP search validation on MnemoLite Python code
- 4 semantic queries tested
- Results documented with accuracy assessment
- Edge ratio and stats recorded

[FILL: ✅ Success / ⚠️ Needs improvement / ❌ Failed]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Update Documentation (Story 29.5 Part 1)

**Files:**
- Modify: `docs/STATUS_2025-11-05.md`
- Create: `docs/agile/serena-evolution/03_EPICS/EPIC-29_COMPLETION_REPORT.md`

### Step 1: Create EPIC-29 completion report

**File:** `docs/agile/serena-evolution/03_EPICS/EPIC-29_COMPLETION_REPORT.md`

```markdown
# EPIC-29: Python Indexing Support - Completion Report

**Status:** ✅ **COMPLETED**
**Date:** 2025-11-07
**Estimated:** 24-32 hours
**Actual:** [FILL] hours

---

## Executive Summary

Successfully implemented Python language support for MnemoLite code indexing, achieving feature parity with TypeScript/JavaScript extraction. Python files can now be indexed, searched semantically, and navigated via MCP with full metadata extraction including decorators, type hints, and async patterns.

---

## Implementation Summary

### Story 29.1: TDD Setup & Basic Queries ✅
**Time:** [FILL]h / 6-8h estimated

**Deliverables:**
- ✅ PythonMetadataExtractor class with Protocol implementation
- ✅ Import extraction (basic, from, aliases)
- ✅ Call extraction (functions, methods, chained)
- ✅ 7 unit tests passing

**Key Files:**
- `api/services/metadata_extractors/python_extractor.py`
- `tests/services/metadata_extractors/test_python_extractor.py`

### Story 29.2: Python Enhancements ✅
**Time:** [FILL]h / 8-10h estimated

**Deliverables:**
- ✅ Decorator detection (@dataclass, @property, custom)
- ✅ Async function detection (async def, await)
- ✅ Type hints extraction (parameters, return types, attributes)
- ✅ Support for Optional, List, Dict, Union types
- ✅ 6 additional unit tests passing

**Key Features:**
- Full decorator support with metadata enrichment
- Type hint parsing for better call graph precision
- Async/await pattern detection

### Story 29.3: Framework Blacklist ✅
**Time:** [FILL]h / 2-3h estimated

**Deliverables:**
- ✅ FRAMEWORK_BLACKLIST with 50+ entries
- ✅ pytest framework filtering (fixture, mock, patch, raises)
- ✅ unittest framework filtering (assertEqual, setUp, tearDown)
- ✅ Debug statement filtering (print, breakpoint, pdb)
- ✅ 3 blacklist unit tests passing

**Impact:**
- Reduced call graph noise by filtering test framework calls
- Improved signal-to-noise ratio for semantic search

### Story 29.4: Integration & Dog-fooding ✅
**Time:** [FILL]h / 4-6h estimated

**Deliverables:**
- ✅ Integration with MetadataExtractorService
- ✅ Updated index_directory.py for Python support
- ✅ Indexed MnemoLite Python codebase (170 files)
- ✅ MCP search validation (4 semantic queries)
- ✅ 1 integration test passing

**Validation Results:**
- Files indexed: [FILL]
- Chunks created: [FILL]
- Nodes: [FILL]
- Edges: [FILL]
- Edge ratio: [FILL]% (target: >40%)

**MCP Dog-fooding:**
- Query 1 (async database): [✅/⚠️/❌]
- Query 2 (embedding service): [✅/⚠️/❌]
- Query 3 (hybrid search RRF): [✅/⚠️/❌]
- Query 4 (metadata extraction): [✅/⚠️/❌]

### Story 29.5: Documentation & Cleanup ✅
**Time:** [FILL]h / 4-5h estimated

**Deliverables:**
- ✅ EPIC-29 completion report
- ✅ Updated STATUS.md
- ✅ Validation results documented
- ✅ Code cleanup and final review

---

## Technical Achievements

### Architecture
- ✅ Protocol-based design maintained (DIP pattern)
- ✅ Clean separation of concerns
- ✅ Reusable tree-sitter query pattern

### Testing
- ✅ TDD approach (tests written first)
- ✅ 16 unit tests + 1 integration test
- ✅ 100% test pass rate

### Features Implemented
- ✅ Import extraction (basic, from, aliases)
- ✅ Call extraction (functions, methods, chained)
- ✅ Decorator detection
- ✅ Type hints parsing
- ✅ Async/await detection
- ✅ Framework blacklist (50+ entries)
- ✅ Full pipeline integration

---

## Key Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Unit tests | 15+ | 16 | ✅ |
| Integration tests | 1+ | 1 | ✅ |
| Edge ratio | >40% | [FILL]% | [FILL] |
| Files indexed | 170 | [FILL] | [FILL] |
| Dog-fooding queries | 3/4 pass | [FILL]/4 | [FILL] |

---

## Lessons Learned

### What Went Well
- TDD approach caught bugs early
- tree-sitter queries more straightforward than expected for Python
- Protocol pattern made integration seamless
- Framework blacklist significantly improved signal-to-noise

### Challenges
- [FILL: Any challenges encountered]
- [FILL: How they were resolved]

### Future Improvements
- Consider adding docstring parsing (Google/NumPy style)
- Magic method detection could be more sophisticated
- Type hint analysis could be deeper (resolve imports)

---

## Impact

**Before EPIC-29:**
- ❌ Python files not indexed
- ❌ Cannot search MnemoLite's own Python code
- ❌ No metadata extraction for Python

**After EPIC-29:**
- ✅ Full Python indexing support
- ✅ Self-indexing: MnemoLite can index its own codebase
- ✅ Semantic search works on Python code
- ✅ Feature parity with TypeScript/JavaScript

---

## Commits

[List key commits with messages]

1. feat(EPIC-29): Add PythonMetadataExtractor with basic import extraction
2. feat(EPIC-29): Add Python call extraction support
3. feat(EPIC-29): Add Python decorator and async detection
4. feat(EPIC-29): Add Python type hints extraction
5. feat(EPIC-29): Add framework blacklist for Python
6. feat(EPIC-29): Integrate PythonMetadataExtractor into metadata service
7. feat(EPIC-29): Add Python language support to indexing script
8. docs(EPIC-29): Add dog-fooding validation results
9. docs(EPIC-29): Complete EPIC-29 documentation

---

## Conclusion

EPIC-29 successfully delivered Python indexing support with full feature parity to TypeScript/JavaScript. The implementation follows established patterns, maintains code quality through TDD, and validates functionality through dog-fooding on MnemoLite's own Python codebase.

**Status:** ✅ **PRODUCTION READY**

**Next Steps:**
- Monitor edge ratio and search quality in production
- Consider additional Python-specific enhancements (docstrings, magic methods)
- Extend to other languages (Go, Rust, etc) using same pattern
```

### Step 2: Update STATUS.md with EPIC-29

**File:** `docs/STATUS_2025-11-05.md`

Add under "## ✅ EPICs COMPLÉTÉS" section:

```markdown
### EPIC-29: Python Indexing Support ✅ **COMPLETE**
**Statut**: ✅ **COMPLETED** (Nov 7, 2025)
**Priorité**: HIGH
**Estimation**: 24-32 heures
**Temps réel**: [FILL] heures
**Impact**: Full Python language support, self-indexing capability

**Objectif atteint**:
- ✅ PythonMetadataExtractor with Protocol implementation
- ✅ Import/call extraction with tree-sitter queries
- ✅ Python-specific features: decorators, type hints, async detection
- ✅ Framework blacklist (pytest, unittest, debugging)
- ✅ Full pipeline integration + MCP dog-fooding validation

**Résultats**:

| Métrique | Valeur | Status |
|----------|--------|--------|
| Files indexed | [FILL] | ✅ |
| Chunks created | [FILL] | ✅ |
| Edge ratio | [FILL]% | [FILL: ✅ if >40%] |
| Unit tests | 16 | ✅ |
| Integration tests | 1 | ✅ |
| MCP queries passing | [FILL]/4 | [FILL] |

**Décision**: ✅ **PRODUCTION READY**
- Python files can be indexed alongside TypeScript/JavaScript
- MnemoLite can now index its own Python codebase
- Semantic search works on Python code with good accuracy

**Technical Highlights**:
- Protocol-based DIP pattern maintained
- TDD approach: tests written first, 100% pass rate
- tree-sitter queries for AST parsing
- 50+ framework blacklist entries reduce call graph noise

---
```

### Step 3: Update roadmap section

Find "## 🎯 Roadmap Court Terme" and update:

```markdown
### Sprint Immédiat: Finalisation & Documentation
1. ✅ **EPIC-28** (4h) - Byte offset fix **COMPLETED** → **53.7% edge ratio** ✅
2. ✅ **Story 28.4** (1h) - Unit tests **COMPLETED** (7/7 passing) ✅
3. ✅ **EPIC-26** (4h) - Parallel indexing testing & cleanup **ABANDONED**
4. ✅ **EPIC-29** ([FILL]h) - Python indexing support **COMPLETED** ✅
5. **EPIC-27 Phase 2** (16h optionnel) - Enhanced TS extraction

**Livrable**: Multi-language indexing (TypeScript + JavaScript + Python)
```

### Step 4: Update conclusion section

Find "**Conclusion**:" and update:

```markdown
**Conclusion**: MnemoLite est **95% complet** et **production-ready**. EPIC-28 (53.7% edge ratio) et EPIC-29 (Python indexing) résolus avec succès. Support multi-langage complet (TS/JS/Python). EPIC-26 (parallel indexing) abandonné après tests (2× slower). Features de sécurité réseau abandonnées (outil local).
```

### Step 5: Commit documentation updates

```bash
git add docs/STATUS_2025-11-05.md docs/agile/serena-evolution/03_EPICS/EPIC-29_COMPLETION_REPORT.md
git commit -m "docs(EPIC-29): Complete documentation and STATUS update

Story 29.5: Final documentation
- EPIC-29 completion report with full metrics
- STATUS.md updated with Python indexing completion
- Roadmap and conclusion updated
- Project now 95% complete with multi-language support

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Code Review & Final Cleanup (Story 29.5 Part 2)

**Files:**
- Review all EPIC-29 code
- Clean up any TODOs or debug code
- Run full test suite

### Step 1: Run complete test suite

**Command:**
```bash
# Run all Python extractor tests
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py -v

# Run integration tests
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/integration/test_python_indexing.py -v

# Run full test suite to check for regressions
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/ -v --tb=short
```

**Expected:** All tests pass, no regressions

### Step 2: Check for TODO comments

**Command:**
```bash
grep -rn "TODO" api/services/metadata_extractors/python_extractor.py
grep -rn "FIXME" api/services/metadata_extractors/python_extractor.py
grep -rn "XXX" api/services/metadata_extractors/python_extractor.py
```

**Expected:** No TODOs left (or document them as future work)

### Step 3: Check code quality

**Command:**
```bash
# Check for long lines, style issues
pylint api/services/metadata_extractors/python_extractor.py --max-line-length=120 || true

# Check type hints
mypy api/services/metadata_extractors/python_extractor.py --ignore-missing-imports || true
```

**Action:** Fix any critical issues found

### Step 4: Review test coverage

**Command:**
```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH pytest tests/services/metadata_extractors/test_python_extractor.py --cov=services.metadata_extractors.python_extractor --cov-report=term-missing
```

**Expected:** >80% coverage

### Step 5: Final cleanup commit (if needed)

```bash
# If any cleanup was done
git add api/services/metadata_extractors/python_extractor.py tests/services/metadata_extractors/test_python_extractor.py
git commit -m "refactor(EPIC-29): Final code cleanup and quality improvements

Story 29.5: Code review and cleanup
- Fixed style issues
- Removed debug code
- Improved type hints
- All tests passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Verification Checklist

Before marking EPIC-29 as complete, verify:

- [ ] All 16 unit tests pass
- [ ] Integration test passes
- [ ] MnemoLite Python files indexed successfully (170 files)
- [ ] Edge ratio > 40%
- [ ] MCP search works on Python code
- [ ] At least 3/4 dog-fooding queries return relevant results
- [ ] Documentation complete (STATUS.md + EPIC-29_COMPLETION_REPORT.md)
- [ ] No regressions in existing TypeScript/JavaScript indexing
- [ ] Code quality checks pass
- [ ] All commits follow message format

---

## Success Metrics

**Final Scorecard:**

| Category | Target | Actual | Status |
|----------|--------|--------|--------|
| **Testing** |
| Unit tests | 15+ | 16 | ✅ |
| Integration tests | 1+ | 1 | ✅ |
| Test pass rate | 100% | [FILL]% | [FILL] |
| **Indexing** |
| Files indexed | 170 | [FILL] | [FILL] |
| Chunks created | 500+ | [FILL] | [FILL] |
| Nodes created | 300+ | [FILL] | [FILL] |
| Edges created | 150+ | [FILL] | [FILL] |
| Edge ratio | >40% | [FILL]% | [FILL] |
| **Validation** |
| Dog-fooding queries | 3/4 pass | [FILL]/4 | [FILL] |
| MCP search works | Yes | [FILL] | [FILL] |
| **Quality** |
| Code coverage | >80% | [FILL]% | [FILL] |
| No regressions | Yes | [FILL] | [FILL] |

---

## Notes

- Uses @superpowers:test-driven-development for TDD approach
- Uses @superpowers:verification-before-completion before marking complete
- Follows CLAUDE.md principles: Test.First, EXTEND>REBUILD, Test.Public.Interface
- DRY: Reuses tree-sitter pattern from TypeScript extractor
- YAGNI: Implements only what's needed for MVP, documents future enhancements

**Related Skills:**
- @superpowers:test-driven-development
- @superpowers:verification-before-completion
- @mnemolite-architecture (Protocol-based DIP)

---

**End of Plan**
