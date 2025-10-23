# EPIC-15 Story 15.1: Implement TypeScriptParser - Analysis

**Story ID**: EPIC-15.1
**Story Points**: 8 pts
**Status**: 📝 **READY FOR IMPLEMENTATION**
**Priority**: P0 (Critical - Foundation for all TypeScript support)
**Dependencies**: None
**Related**: Story 15.2 (JavaScriptParser will inherit from this)
**Created**: 2025-10-23
**Last Updated**: 2025-10-23

---

## 📝 User Story

**As a** code indexer
**I want to** parse TypeScript files using tree-sitter AST
**So that** functions, classes, interfaces, and methods are semantically chunked

---

## 🎯 Acceptance Criteria

1. **TypeScriptParser Class** (2 pts)
   - [ ] Create `TypeScriptParser` class inheriting from `LanguageParser`
   - [ ] Initialize with tree-sitter language name `"typescript"`
   - [ ] Implement all required methods from LanguageParser protocol

2. **Function Node Extraction** (1.5 pts)
   - [ ] `get_function_nodes()` extracts `function_declaration` nodes
   - [ ] `get_function_nodes()` extracts `arrow_function` nodes
   - [ ] Tree-sitter query handles both function types correctly

3. **Class Node Extraction** (1 pt)
   - [ ] `get_class_nodes()` extracts `class_declaration` nodes
   - [ ] Works with exported classes (`export class Foo`)

4. **Interface Node Extraction** (1 pt)
   - [ ] `get_interface_nodes()` extracts `interface_declaration` nodes
   - [ ] New method specific to TypeScript (not in PythonParser)

5. **Method Node Extraction** (1 pt)
   - [ ] `get_method_nodes()` extracts `method_definition` nodes from class bodies
   - [ ] Handles public/private/protected modifiers

6. **Node to CodeUnit Conversion** (1 pt)
   - [ ] `node_to_code_unit()` converts TypeScript nodes to CodeUnit
   - [ ] Extracts name from `identifier` or `type_identifier`
   - [ ] Maps TypeScript node types to ChunkType enum
   - [ ] Calculates correct line numbers and source code

7. **ChunkType Enum Update** (0.5 pts)
   - [ ] Add `ChunkType.INTERFACE` to `api/models/code_chunk_models.py`
   - [ ] Optional: Add `ChunkType.TYPE_ALIAS` for future use

8. **Unit Tests** (1 pt)
   - [ ] Test function extraction (regular functions + arrow functions)
   - [ ] Test class extraction
   - [ ] Test interface extraction
   - [ ] Test method extraction
   - [ ] Test node_to_code_unit conversion
   - [ ] Test with exported symbols (`export class`, `export function`)
   - [ ] Test with async functions
   - [ ] Test with generic types
   - [ ] Minimum 20 test cases
   - [ ] 100% code coverage for TypeScriptParser

---

## 🔍 Technical Analysis

### Tree-sitter TypeScript AST Structure

**Verified Available**: Tree-sitter supports `typescript` language out-of-the-box.

**Key Node Types**:

| TypeScript Node Type | Python Equivalent | Description |
|---------------------|-------------------|-------------|
| `function_declaration` | `function_definition` | Named functions |
| `arrow_function` | N/A | Arrow functions (ES6) |
| `class_declaration` | `class_definition` | Classes |
| `method_definition` | Same (in class_body) | Methods in classes |
| `interface_declaration` | N/A | TypeScript interfaces |
| `type_alias_declaration` | N/A | Type aliases |
| `lexical_declaration` | N/A | const/let/var declarations |

**Example TypeScript Code**:
```typescript
export class ExportFormat {
  constructor(private readonly id: string) {}

  public getId(): string {
    return this.id;
  }
}

export interface StorageRepository {
  save(key: string, data: unknown): Promise<void>
}

export function formatData(data: any): string {
  return JSON.stringify(data);
}

const arrowFunc = (x: number): number => x * 2;
```

**Corresponding AST** (simplified):
```
program
  ├─ export_statement
  │   └─ class_declaration (ExportFormat)        ← get_class_nodes()
  │       └─ class_body
  │           └─ method_definition (getId)       ← get_method_nodes()
  │
  ├─ export_statement
  │   └─ interface_declaration (StorageRepository) ← get_interface_nodes()
  │       └─ interface_body
  │           └─ method_signature (save)
  │
  ├─ export_statement
  │   └─ function_declaration (formatData)       ← get_function_nodes()
  │
  └─ lexical_declaration (const)
      └─ variable_declarator
          └─ arrow_function                      ← get_function_nodes()
```

### Tree-sitter Query Examples

**Function Declarations + Arrow Functions**:
```scheme
(function_declaration) @function

(lexical_declaration
  (variable_declarator
    value: (arrow_function) @arrow_function))
```

**Class Declarations**:
```scheme
(class_declaration) @class
```

**Interface Declarations**:
```scheme
(interface_declaration) @interface
```

**Method Definitions**:
```python
# In get_method_nodes(node):
for child in node.children:
    if child.type == "class_body":
        for subchild in child.children:
            if subchild.type == "method_definition":
                methods.append(subchild)
```

### Implementation Pattern (Follow PythonParser)

**PythonParser Structure** (reference):
```python
class PythonParser(LanguageParser):
    def __init__(self):
        super().__init__("python")

    def get_function_nodes(self, tree: Tree) -> list[Node]:
        # Query for function_definition
        pass

    def get_class_nodes(self, tree: Tree) -> list[Node]:
        # Query for class_definition
        pass

    def get_method_nodes(self, node: Node) -> list[Node]:
        # Extract decorated_definition from class body
        pass

    def node_to_code_unit(self, node: Node, source_code: str) -> CodeUnit:
        # Convert node to CodeUnit
        pass
```

**TypeScriptParser Structure** (to implement):
```python
class TypeScriptParser(LanguageParser):
    def __init__(self):
        super().__init__("typescript")

    def get_function_nodes(self, tree: Tree) -> list[Node]:
        # Query for function_declaration + arrow_function
        pass

    def get_class_nodes(self, tree: Tree) -> list[Node]:
        # Query for class_declaration
        pass

    def get_interface_nodes(self, tree: Tree) -> list[Node]:
        # Query for interface_declaration (NEW - TypeScript-specific)
        pass

    def get_method_nodes(self, node: Node) -> list[Node]:
        # Extract method_definition from class_body
        pass

    def node_to_code_unit(self, node: Node, source_code: str) -> CodeUnit:
        # Convert TypeScript node to CodeUnit
        # Handle: identifier, type_identifier, async, etc.
        pass
```

---

## 💻 Implementation Details

### File Locations

**Main Implementation**:
- `api/services/code_chunking_service.py` - Add `TypeScriptParser` class (~100-150 lines)

**Model Updates**:
- `api/models/code_chunk_models.py` - Add `ChunkType.INTERFACE` enum value

**Tests**:
- `tests/services/test_code_chunking_service.py` - Add TypeScript test suite (~200 lines)

### Code Skeleton

```python
# api/services/code_chunking_service.py

class TypeScriptParser(LanguageParser):
    """
    TypeScript/TSX AST parser using tree-sitter.

    Handles:
    - Function declarations (function)
    - Class declarations (class)
    - Method definitions (methods in classes)
    - Interface declarations (TypeScript)
    - Arrow functions (const x = () => {})
    - Async functions
    """

    def __init__(self):
        super().__init__("typescript")

    def get_function_nodes(self, tree: Tree) -> list[Node]:
        """Extract function declarations + arrow functions."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            """
            (function_declaration) @function
            (lexical_declaration
              (variable_declarator
                value: (arrow_function) @arrow_function))
            """
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('function', []))
            nodes.extend(captures_dict.get('arrow_function', []))
        return nodes

    def get_class_nodes(self, tree: Tree) -> list[Node]:
        """Extract class declarations."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            """
            (class_declaration) @class
            """
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('class', []))
        return nodes

    def get_interface_nodes(self, tree: Tree) -> list[Node]:
        """Extract interface declarations (TypeScript-specific)."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            """
            (interface_declaration) @interface
            """
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('interface', []))
        return nodes

    def get_method_nodes(self, node: Node) -> list[Node]:
        """Extract method definitions from class body."""
        methods = []
        for child in node.children:
            if child.type == "class_body":
                for subchild in child.children:
                    if subchild.type == "method_definition":
                        methods.append(subchild)
        return methods

    def node_to_code_unit(self, node: Node, source_code: str) -> CodeUnit:
        """
        Convert TypeScript tree-sitter node to CodeUnit.

        Handles:
        - type_identifier (class names, interface names)
        - identifier (function/method names)
        - Async functions (async keyword)
        """
        # Get name from identifier/type_identifier
        name = None
        for child in node.children:
            if child.type in ["identifier", "type_identifier"]:
                name = source_code[child.start_byte:child.end_byte]
                break

        if not name:
            name = f"anonymous_{node.type}"

        # Determine chunk type
        chunk_type_map = {
            "function_declaration": ChunkType.FUNCTION,
            "arrow_function": ChunkType.FUNCTION,
            "class_declaration": ChunkType.CLASS,
            "method_definition": ChunkType.METHOD,
            "interface_declaration": ChunkType.INTERFACE,  # NEW
        }
        chunk_type = chunk_type_map.get(node.type, ChunkType.FUNCTION)

        # Extract source code
        start_byte = node.start_byte
        end_byte = node.end_byte
        source_text = source_code[start_byte:end_byte]

        # Calculate line numbers
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        return CodeUnit(
            node_type=node.type,
            chunk_type=chunk_type,
            name=name,
            source_code=source_text,
            start_line=start_line,
            end_line=end_line,
            size=len(source_text)
        )
```

### ChunkType Enum Update

```python
# api/models/code_chunk_models.py

class ChunkType(str, Enum):
    """Type of code chunk."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    FALLBACK_FIXED = "fallback_fixed"
    INTERFACE = "interface"  # ← NEW (TypeScript)
    # TYPE_ALIAS = "type_alias"  # ← Optional (future use)
```

---

## 🧪 Testing Strategy

### Unit Tests (20+ test cases)

**Test Functions** (5 tests):
```python
@pytest.mark.asyncio
async def test_typescript_function_declaration():
    """Test extracting regular function declarations."""
    source_code = """
    export function formatData(data: any): string {
      return JSON.stringify(data);
    }
    """
    # Assert: 1 chunk, type=function, name=formatData

@pytest.mark.asyncio
async def test_typescript_arrow_function():
    """Test extracting arrow functions."""
    source_code = """
    const arrowFunc = (x: number): number => x * 2;
    """
    # Assert: 1 chunk, type=function, name=arrowFunc

@pytest.mark.asyncio
async def test_typescript_async_function():
    """Test extracting async functions."""
    source_code = """
    async function fetchData(): Promise<Data> {
      return await api.get('/data');
    }
    """
    # Assert: 1 chunk, type=function, name=fetchData

@pytest.mark.asyncio
async def test_typescript_generic_function():
    """Test extracting generic functions."""
    source_code = """
    function identity<T>(arg: T): T {
      return arg;
    }
    """
    # Assert: 1 chunk, type=function, name=identity

@pytest.mark.asyncio
async def test_typescript_exported_function():
    """Test extracting exported functions."""
    source_code = """
    export async function processData<T>(data: T[]): Promise<T[]> {
      return data.map(item => transform(item));
    }
    """
    # Assert: 1 chunk, type=function, name=processData
```

**Test Classes** (3 tests):
```python
@pytest.mark.asyncio
async def test_typescript_class_declaration():
    """Test extracting class declarations."""
    source_code = """
    export class ExportFormat {
      constructor(private readonly id: string) {}

      public getId(): string {
        return this.id;
      }
    }
    """
    # Assert: 1 class chunk (ExportFormat) + 1 method chunk (getId)

@pytest.mark.asyncio
async def test_typescript_class_with_generics():
    """Test extracting generic classes."""
    source_code = """
    class Container<T> {
      private items: T[] = [];

      add(item: T): void {
        this.items.push(item);
      }
    }
    """
    # Assert: 1 class chunk + 1 method chunk

@pytest.mark.asyncio
async def test_typescript_exported_class():
    """Test extracting exported classes."""
    source_code = """
    export default class DefaultExport {
      process(): void {}
    }
    """
    # Assert: 1 class chunk + 1 method chunk
```

**Test Interfaces** (3 tests):
```python
@pytest.mark.asyncio
async def test_typescript_interface_declaration():
    """Test extracting interface declarations."""
    source_code = """
    export interface StorageRepository {
      save(key: string, data: unknown): Promise<void>
      load<T>(key: string): Promise<T | null>
    }
    """
    # Assert: 1 chunk, type=interface, name=StorageRepository

@pytest.mark.asyncio
async def test_typescript_interface_with_generics():
    """Test extracting generic interfaces."""
    source_code = """
    interface Repository<T> {
      findById(id: string): Promise<T | null>
      save(entity: T): Promise<void>
    }
    """
    # Assert: 1 chunk, type=interface, name=Repository

@pytest.mark.asyncio
async def test_typescript_exported_interface():
    """Test extracting exported interfaces."""
    source_code = """
    export interface Config {
      apiUrl: string;
      timeout: number;
    }
    """
    # Assert: 1 chunk, type=interface, name=Config
```

**Test Methods** (2 tests):
```python
@pytest.mark.asyncio
async def test_typescript_method_extraction():
    """Test extracting methods from classes."""
    source_code = """
    class Service {
      public async process(data: any): Promise<void> {}
      private validate(data: any): boolean { return true; }
      protected transform(data: any): any { return data; }
    }
    """
    # Assert: 1 class + 3 methods (public, private, protected)

@pytest.mark.asyncio
async def test_typescript_constructor():
    """Test extracting constructors."""
    source_code = """
    class User {
      constructor(private name: string, private age: number) {}
    }
    """
    # Assert: 1 class + 0 or 1 constructor (depending on implementation)
```

**Test Edge Cases** (7 tests):
```python
@pytest.mark.asyncio
async def test_typescript_empty_file():
    """Test handling empty TypeScript files."""
    # Assert: 0 chunks

@pytest.mark.asyncio
async def test_typescript_comments_only():
    """Test handling files with only comments."""
    # Assert: 0 chunks

@pytest.mark.asyncio
async def test_typescript_nested_functions():
    """Test handling nested functions."""
    # Assert: Extracts top-level function only (or all, depending on design)

@pytest.mark.asyncio
async def test_typescript_mixed_declarations():
    """Test file with mixed declarations."""
    source_code = """
    export class Foo {}
    export function bar() {}
    export interface Baz {}
    const qux = () => {};
    """
    # Assert: 4 chunks (class, function, interface, arrow function)

@pytest.mark.asyncio
async def test_typescript_tsx_support():
    """Test TypeScript React (TSX) files."""
    source_code = """
    export const Component: React.FC = () => {
      return <div>Hello</div>;
    };
    """
    # Assert: 1 chunk (arrow function component)

@pytest.mark.asyncio
async def test_typescript_namespace():
    """Test TypeScript namespaces."""
    source_code = """
    namespace Utils {
      export function helper(): void {}
    }
    """
    # Assert: Extracts helper function (or namespace, depending on design)

@pytest.mark.asyncio
async def test_typescript_enum():
    """Test TypeScript enums."""
    source_code = """
    enum Status {
      Active,
      Inactive
    }
    """
    # Assert: Handles gracefully (may not create chunks)
```

---

## 📊 Definition of Done

**Story 15.1 is complete when**:
1. ✅ TypeScriptParser class implemented in `code_chunking_service.py`
2. ✅ All 7 acceptance criteria met (100%)
3. ✅ ChunkType.INTERFACE added to enum
4. ✅ Minimum 20 unit tests implemented
5. ✅ All tests pass (100% success rate)
6. ✅ Code coverage >90% for TypeScriptParser
7. ✅ Code review approved
8. ✅ Merged to main branch

---

## 🔗 Related Documents

- [EPIC-15 README](EPIC-15_TYPESCRIPT_JAVASCRIPT_SUPPORT.md) - Epic overview
- [EPIC-15 ULTRATHINK](/tmp/EPIC-15_TYPESCRIPT_SUPPORT_ULTRATHINK.md) - Deep analysis
- [Story 15.2 Analysis](EPIC-15_STORY_15.2_ANALYSIS.md) - JavaScriptParser (inherits from this)

---

**Last Updated**: 2025-10-23
**Next Action**: Start implementation of TypeScriptParser class
