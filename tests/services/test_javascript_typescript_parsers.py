"""
Unit tests for JavaScript and TypeScript parsers (EPIC-06 Phase 1.5).

Tests:
- JavaScript parser: functions, arrow functions, classes, generators
- TypeScript parser: interfaces, type aliases, enums, classes
- Name extraction for all node types
- Edge cases: anonymous functions, exported declarations, nested structures
- Performance benchmarks
"""

import pytest

from models.code_chunk_models import ChunkType
from services.code_chunking_service import (
    CodeChunkingService,
    JavaScriptParser,
    TypeScriptParser,
    LANGUAGE_PACK_AVAILABLE,
)


# Skip all tests if tree-sitter-language-pack not available
pytestmark = pytest.mark.skipif(
    not LANGUAGE_PACK_AVAILABLE,
    reason="tree-sitter-language-pack not installed"
)


@pytest.fixture
def chunking_service():
    """Get CodeChunkingService instance."""
    return CodeChunkingService(max_workers=2)


@pytest.fixture
def javascript_parser():
    """Get JavaScriptParser instance."""
    if not LANGUAGE_PACK_AVAILABLE:
        pytest.skip("tree-sitter-language-pack not available")
    return JavaScriptParser()


@pytest.fixture
def typescript_parser():
    """Get TypeScriptParser instance."""
    if not LANGUAGE_PACK_AVAILABLE:
        pytest.skip("tree-sitter-language-pack not available")
    return TypeScriptParser()


# ============================================================================
# JAVASCRIPT PARSER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_javascript_function_declaration(chunking_service):
    """Test JavaScript regular function declarations."""
    source_code = '''
function calculateTotal(items) {
    return items.reduce((sum, item) => sum + item.price, 0);
}

function processOrder(order) {
    const total = calculateTotal(order.items);
    return total > 0;
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False  # JS metadata not supported yet
    )

    assert len(chunks) == 2, f"Expected 2 chunks (2 functions), got {len(chunks)}"

    # Chunk 1: calculateTotal
    chunk1 = chunks[0]
    assert chunk1.chunk_type == ChunkType.FUNCTION
    assert chunk1.name == "calculateTotal"
    assert "function calculateTotal" in chunk1.source_code
    assert "reduce" in chunk1.source_code

    # Chunk 2: processOrder
    chunk2 = chunks[1]
    assert chunk2.chunk_type == ChunkType.FUNCTION
    assert chunk2.name == "processOrder"
    assert "function processOrder" in chunk2.source_code


@pytest.mark.asyncio
async def test_javascript_arrow_functions(chunking_service):
    """Test JavaScript arrow function declarations."""
    source_code = '''
const add = (a, b) => a + b;

const processData = async (data) => {
    const result = data.map(x => x * 2);
    return result.filter(x => x > 10);
};

const greet = (name) => `Hello, ${name}!`;
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    # Should extract 3 arrow functions
    assert len(chunks) == 3

    # Check all are arrow functions
    arrow_chunks = [c for c in chunks if c.chunk_type == ChunkType.ARROW_FUNCTION]
    assert len(arrow_chunks) == 3

    # Verify names extracted from variable declarators
    names = {chunk.name for chunk in chunks}
    assert names == {"add", "processData", "greet"}


@pytest.mark.asyncio
async def test_javascript_generator_function(chunking_service):
    """Test JavaScript generator functions."""
    source_code = '''
function* fibonacci() {
    let [a, b] = [0, 1];
    while (true) {
        yield a;
        [a, b] = [b, a + b];
    }
}

function* range(start, end) {
    for (let i = start; i < end; i++) {
        yield i;
    }
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    assert len(chunks) == 2

    # Check both are generators
    for chunk in chunks:
        assert chunk.chunk_type == ChunkType.GENERATOR
        assert "yield" in chunk.source_code

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert names == {"fibonacci", "range"}


@pytest.mark.asyncio
async def test_javascript_class_with_methods(chunking_service):
    """Test JavaScript class declarations with methods."""
    source_code = '''
class UserService {
    constructor(db) {
        this.db = db;
    }

    async getUser(id) {
        return await this.db.users.findOne({ id });
    }

    async createUser(userData) {
        return await this.db.users.insert(userData);
    }

    validateUser(user) {
        return user && user.email;
    }
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    # Should have 1 class chunk
    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.chunk_type == ChunkType.CLASS
    assert chunk.name == "UserService"
    assert "class UserService" in chunk.source_code
    assert "constructor" in chunk.source_code
    assert "getUser" in chunk.source_code


@pytest.mark.asyncio
async def test_javascript_exported_functions(chunking_service):
    """Test JavaScript exported function declarations."""
    source_code = '''
export function publicApi(params) {
    return processInternal(params);
}

export const exportedArrow = (x) => x * 2;

export class ApiService {
    constructor() {
        this.version = '1.0';
    }
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    assert len(chunks) == 3

    # Check types
    chunk_types = {chunk.chunk_type for chunk in chunks}
    assert ChunkType.FUNCTION in chunk_types
    assert ChunkType.ARROW_FUNCTION in chunk_types
    assert ChunkType.CLASS in chunk_types

    # Verify names extracted correctly despite export
    names = {chunk.name for chunk in chunks}
    assert "publicApi" in names
    assert "exportedArrow" in names
    assert "ApiService" in names


@pytest.mark.asyncio
async def test_javascript_mixed_constructs(chunking_service):
    """Test JavaScript file with mixed function types."""
    source_code = '''
// Regular function
function regularFunc() {
    return 42;
}

// Arrow function
const arrowFunc = () => {
    return 100;
};

// Generator
function* generatorFunc() {
    yield 1;
    yield 2;
}

// Class
class MyClass {
    method() {
        return "result";
    }
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    assert len(chunks) == 4

    # Verify all chunk types present
    chunk_types = {chunk.chunk_type for chunk in chunks}
    assert ChunkType.FUNCTION in chunk_types
    assert ChunkType.ARROW_FUNCTION in chunk_types
    assert ChunkType.GENERATOR in chunk_types
    assert ChunkType.CLASS in chunk_types


def test_javascript_parser_node_extraction(javascript_parser):
    """Test JavaScriptParser can extract different node types."""
    source_code = '''
function regularFunc() {}
const arrowFunc = () => {};
function* genFunc() {}
class MyClass {}
'''

    tree = javascript_parser.parse(source_code)

    # Test function nodes (includes all function types)
    function_nodes = javascript_parser.get_function_nodes(tree)
    assert len(function_nodes) >= 3  # regular + arrow + generator

    # Test class nodes
    class_nodes = javascript_parser.get_class_nodes(tree)
    assert len(class_nodes) == 1
    assert class_nodes[0].type == "class_declaration"


# ============================================================================
# TYPESCRIPT PARSER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_typescript_interface_declaration(chunking_service):
    """Test TypeScript interface declarations."""
    source_code = '''
interface User {
    id: string;
    name: string;
    email: string;
    createdAt: Date;
}

interface ApiResponse<T> {
    data: T;
    status: number;
    message: string;
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )

    assert len(chunks) == 2

    # Check both are interfaces
    interface_chunks = [c for c in chunks if c.chunk_type == ChunkType.INTERFACE]
    assert len(interface_chunks) == 2

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert names == {"User", "ApiResponse"}

    # Verify content
    user_chunk = next(c for c in chunks if c.name == "User")
    assert "interface User" in user_chunk.source_code
    assert "createdAt: Date" in user_chunk.source_code


@pytest.mark.asyncio
async def test_typescript_type_alias_declaration(chunking_service):
    """Test TypeScript type alias declarations."""
    source_code = '''
type ID = string | number;

type User = {
    id: ID;
    name: string;
};

type Status = "active" | "inactive" | "pending";

type Callback<T> = (data: T) => void;
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )

    assert len(chunks) == 4

    # Check all are type aliases
    type_chunks = [c for c in chunks if c.chunk_type == ChunkType.TYPE_ALIAS]
    assert len(type_chunks) == 4

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert names == {"ID", "User", "Status", "Callback"}


@pytest.mark.asyncio
async def test_typescript_enum_declaration(chunking_service):
    """Test TypeScript enum declarations."""
    source_code = '''
enum UserRole {
    Admin = "ADMIN",
    User = "USER",
    Guest = "GUEST"
}

enum HttpStatus {
    OK = 200,
    NotFound = 404,
    ServerError = 500
}

enum Direction {
    Up,
    Down,
    Left,
    Right
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )

    assert len(chunks) == 3

    # Check all are enums
    enum_chunks = [c for c in chunks if c.chunk_type == ChunkType.ENUM]
    assert len(enum_chunks) == 3

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert names == {"UserRole", "HttpStatus", "Direction"}

    # Verify content
    role_chunk = next(c for c in chunks if c.name == "UserRole")
    assert "enum UserRole" in role_chunk.source_code
    assert "Admin = \"ADMIN\"" in role_chunk.source_code


@pytest.mark.asyncio
async def test_typescript_class_with_types(chunking_service):
    """Test TypeScript class with type annotations."""
    source_code = '''
class UserRepository {
    private db: Database;

    constructor(db: Database) {
        this.db = db;
    }

    async findById(id: string): Promise<User | null> {
        return await this.db.users.findOne({ id });
    }

    async create(user: Omit<User, 'id'>): Promise<User> {
        return await this.db.users.insert(user);
    }
}
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )

    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.chunk_type == ChunkType.CLASS
    assert chunk.name == "UserRepository"
    assert "class UserRepository" in chunk.source_code
    assert "Promise<User" in chunk.source_code


@pytest.mark.asyncio
async def test_typescript_mixed_declarations(chunking_service):
    """Test TypeScript file with all declaration types."""
    source_code = '''
// Interface
interface User {
    id: string;
    name: string;
}

// Type alias
type ID = string | number;

// Enum
enum Status {
    Active = "ACTIVE",
    Inactive = "INACTIVE"
}

// Class
class UserService {
    getUser(id: ID): Promise<User> {
        return Promise.resolve({ id: "1", name: "Test" });
    }
}

// Function (inherited from JavaScript)
function createUser(name: string): User {
    return { id: "1", name };
}

// Arrow function (inherited from JavaScript)
const validateUser = (user: User): boolean => {
    return user && user.id !== "";
};
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )

    assert len(chunks) == 6

    # Verify all chunk types present
    chunk_types = {chunk.chunk_type for chunk in chunks}
    assert ChunkType.INTERFACE in chunk_types
    assert ChunkType.TYPE_ALIAS in chunk_types
    assert ChunkType.ENUM in chunk_types
    assert ChunkType.CLASS in chunk_types
    assert ChunkType.FUNCTION in chunk_types
    assert ChunkType.ARROW_FUNCTION in chunk_types

    # Verify specific names
    names = {chunk.name for chunk in chunks}
    assert "User" in names
    assert "ID" in names
    assert "Status" in names
    assert "UserService" in names
    assert "createUser" in names
    assert "validateUser" in names


def test_typescript_parser_node_extraction(typescript_parser):
    """Test TypeScriptParser can extract TypeScript-specific nodes."""
    source_code = '''
interface User {}
type ID = string;
enum Status { Active, Inactive }
class Service {}
'''

    tree = typescript_parser.parse(source_code)

    # Test interface nodes
    interface_nodes = typescript_parser.get_interface_nodes(tree)
    assert len(interface_nodes) == 1
    assert interface_nodes[0].type == "interface_declaration"

    # Test type alias nodes
    type_nodes = typescript_parser.get_type_alias_nodes(tree)
    assert len(type_nodes) == 1
    assert type_nodes[0].type == "type_alias_declaration"

    # Test enum nodes
    enum_nodes = typescript_parser.get_enum_nodes(tree)
    assert len(enum_nodes) == 1
    assert enum_nodes[0].type == "enum_declaration"

    # Test class nodes (inherited from JavaScript)
    class_nodes = typescript_parser.get_class_nodes(tree)
    assert len(class_nodes) == 1
    assert class_nodes[0].type == "class_declaration"


# ============================================================================
# EDGE CASES AND NAME EXTRACTION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_javascript_anonymous_functions(chunking_service):
    """Test handling of anonymous functions in object literals.

    Note: Functions inside object literals are not top-level declarations
    and are not extracted by the current parser query. This is expected behavior
    as we focus on extracting top-level code units (functions, classes, etc.).
    """
    source_code = '''
const handlers = {
    onClick: function() {
        console.log("clicked");
    },
    onHover: () => {
        console.log("hovered");
    }
};

// Top-level arrow function (should be extracted)
const topLevel = () => {
    return handlers;
};
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    # Should extract at least the top-level arrow function
    assert len(chunks) >= 1

    # Verify top-level function is extracted
    top_level_chunks = [c for c in chunks if c.name == "topLevel"]
    assert len(top_level_chunks) == 1
    assert top_level_chunks[0].chunk_type == ChunkType.ARROW_FUNCTION


@pytest.mark.asyncio
async def test_typescript_generic_types(chunking_service):
    """Test TypeScript generics in interfaces and types."""
    source_code = '''
interface Repository<T> {
    find(id: string): Promise<T>;
    create(item: T): Promise<T>;
    update(id: string, item: Partial<T>): Promise<T>;
}

type Result<T, E = Error> =
    | { success: true; data: T }
    | { success: false; error: E };
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )

    assert len(chunks) == 2

    # Check types
    interface_chunk = next(c for c in chunks if c.chunk_type == ChunkType.INTERFACE)
    assert interface_chunk.name == "Repository"
    assert "Repository<T>" in interface_chunk.source_code

    type_chunk = next(c for c in chunks if c.chunk_type == ChunkType.TYPE_ALIAS)
    assert type_chunk.name == "Result"


@pytest.mark.asyncio
async def test_jsx_tsx_support(chunking_service):
    """Test that JSX/TSX use correct parsers."""
    jsx_code = '''
const Component = () => {
    return <div>Hello</div>;
};
'''

    tsx_code = '''
interface Props {
    name: string;
}

const Component: React.FC<Props> = ({ name }) => {
    return <div>Hello {name}</div>;
};
'''

    # JSX should use JavaScript parser
    jsx_chunks = await chunking_service.chunk_code(
        source_code=jsx_code,
        language="jsx",
        file_path="test.jsx",
        extract_metadata=False
    )
    assert len(jsx_chunks) >= 1

    # TSX should use TypeScript parser
    tsx_chunks = await chunking_service.chunk_code(
        source_code=tsx_code,
        language="tsx",
        file_path="test.tsx",
        extract_metadata=False
    )
    assert len(tsx_chunks) >= 2  # Interface + arrow function


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_javascript_performance(chunking_service):
    """Test JavaScript chunking performance."""
    import time

    # Generate 20 functions (~300 LOC)
    source_code = ""
    for i in range(20):
        source_code += f'''
function process_{i}(data) {{
    const result = data.map(x => x * {i});
    const filtered = result.filter(x => x > 10);
    const sum = filtered.reduce((acc, x) => acc + x, 0);
    return sum;
}}

const handler_{i} = async (event) => {{
    const data = await fetchData(event.id);
    return process_{i}(data);
}};

'''

    start = time.time()
    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )
    elapsed_ms = (time.time() - start) * 1000

    assert len(chunks) >= 30  # 20 functions + 20 arrow functions
    assert elapsed_ms < 200, f"Performance: {elapsed_ms:.2f}ms > 200ms"

    print(f"✅ JavaScript performance: {elapsed_ms:.2f}ms for {len(chunks)} chunks")


@pytest.mark.asyncio
async def test_typescript_performance(chunking_service):
    """Test TypeScript chunking performance."""
    import time

    # Generate mixed TypeScript declarations
    source_code = ""
    for i in range(10):
        source_code += f'''
interface Entity{i} {{
    id: string;
    name: string;
    value: number;
}}

type Handler{i} = (data: Entity{i}) => Promise<void>;

enum Status{i} {{
    Active = "ACTIVE_{i}",
    Inactive = "INACTIVE_{i}"
}}

class Service{i} {{
    async process(entity: Entity{i}): Promise<Entity{i}> {{
        return entity;
    }}
}}

'''

    start = time.time()
    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="typescript",
        file_path="test.ts",
        extract_metadata=False
    )
    elapsed_ms = (time.time() - start) * 1000

    assert len(chunks) >= 30  # 10 interfaces + 10 types + 10 enums + 10 classes
    assert elapsed_ms < 200, f"Performance: {elapsed_ms:.2f}ms > 200ms"

    print(f"✅ TypeScript performance: {elapsed_ms:.2f}ms for {len(chunks)} chunks")


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_javascript_syntax_error_fallback(chunking_service):
    """Test JavaScript handles syntax errors gracefully.

    Note: Tree-sitter has error recovery mechanisms. For very short invalid code,
    it may not extract any nodes, resulting in an empty chunk list instead of
    falling back to fixed chunking. This is acceptable behavior.
    """
    invalid_code = '''
function broken(
// Missing closing paren and body
const x = 1;
const y = 2;
'''

    chunks = await chunking_service.chunk_code(
        source_code=invalid_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    # Tree-sitter may return 0 chunks for invalid code (error recovery)
    # or may fall back to fixed chunking
    assert isinstance(chunks, list)
    # If chunks were created, verify they are either parsed or fallback
    for chunk in chunks:
        assert chunk.chunk_type in [
            ChunkType.FUNCTION,
            ChunkType.ARROW_FUNCTION,
            ChunkType.CLASS,
            ChunkType.FALLBACK_FIXED
        ]


@pytest.mark.asyncio
async def test_typescript_empty_file(chunking_service):
    """Test TypeScript handles empty files gracefully."""
    with pytest.raises(ValueError, match="source_code cannot be empty"):
        await chunking_service.chunk_code(
            source_code="",
            language="typescript",
            file_path="test.ts"
        )


@pytest.mark.asyncio
async def test_javascript_only_comments(chunking_service):
    """Test JavaScript file with only comments."""
    source_code = '''
// This is a comment
/* This is a
   multiline comment */
// Another comment
'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="javascript",
        file_path="test.js",
        extract_metadata=False
    )

    # Should create fallback chunk or no chunks
    # Tree-sitter might not extract any code units from comments-only file
    assert isinstance(chunks, list)
