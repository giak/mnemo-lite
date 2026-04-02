# EPIC-16 Story 16.2 Analysis: TypeExtractorService Extension

**Story ID**: EPIC-16 Story 16.2
**Story Points**: 5 pts
**Status**: 📝 **READY FOR IMPLEMENTATION**
**Depends On**:
- EPIC-16 Story 16.1 (TypeScriptLSPClient)
- EPIC-13 Story 13.2 (TypeExtractorService foundation)
**Reference**: EPIC-13 Story 13.2 (Python type extraction)
**Created**: 2025-10-23

---

## 🎯 User Story

**As a** type extractor
**I want** to use TypeScript LSP for type resolution
**So that** TypeScript metadata is 95%+ accurate (vs 70% heuristic)

---

## 📋 Acceptance Criteria

- [ ] **AC1**: Add `typescript_lsp` parameter to TypeExtractorService
- [ ] **AC2**: Implement `_extract_typescript_types()` method for LSP-based extraction
- [ ] **AC3**: Parse LSP hover responses → structured metadata
- [ ] **AC4**: Extract parameter types with full type info
- [ ] **AC5**: Extract return types with generic resolution
- [ ] **AC6**: Resolve generic types (e.g., Promise<T> → Promise<User>)
- [ ] **AC7**: Track imports (symbol → file location)
- [ ] **AC8**: Cache LSP responses in Redis (L2 cache)
- [ ] **AC9**: Integration tests: 5+ test cases covering TypeScript type extraction

---

## 🔍 Current State Analysis

### Existing TypeExtractorService (EPIC-13)

**File**: `api/services/type_extractor_service.py`

**Current Capabilities**:
- ✅ Python type extraction via Pyright LSP
- ✅ Caching in Redis (L2)
- ✅ Graceful degradation (LSP → heuristic)
- ✅ Circuit breaker integration

**Current Architecture**:
```python
class TypeExtractorService:
    def __init__(
        self,
        pyright_lsp: PyrightLSPClient,
        redis_client: Redis,
        cache_ttl: int = 3600
    ):
        self.pyright_lsp = pyright_lsp
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl

    async def extract_types(
        self,
        chunk: CodeChunk,
        language: str
    ) -> Dict[str, Any]:
        """Extract type information for a code chunk."""

        if language == "python":
            return await self._extract_python_types(chunk)

        # Fallback for other languages
        return {}
```

**Gap**: No TypeScript support → Need to add `typescript_lsp` and `_extract_typescript_types()`

---

## 🎯 Target State

### Extended TypeExtractorService (Post EPIC-16)

**Target Architecture**:
```python
class TypeExtractorService:
    def __init__(
        self,
        pyright_lsp: PyrightLSPClient,
        typescript_lsp: TypeScriptLSPClient,  # ← NEW
        redis_client: Redis,
        cache_ttl: int = 3600
    ):
        self.pyright_lsp = pyright_lsp
        self.typescript_lsp = typescript_lsp  # ← NEW
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl

    async def extract_types(
        self,
        chunk: CodeChunk,
        language: str
    ) -> Dict[str, Any]:
        """Extract type information for a code chunk."""

        if language == "python":
            return await self._extract_python_types(chunk)

        elif language in ("typescript", "javascript", "tsx"):  # ← NEW
            return await self._extract_typescript_types(chunk)

        # Fallback for other languages
        return {}
```

---

## 💻 Code Changes

### 1. Update Constructor (DI)

**File**: `api/services/type_extractor_service.py`

```python
from api.services.typescript_lsp_client import TypeScriptLSPClient

class TypeExtractorService:
    def __init__(
        self,
        pyright_lsp: PyrightLSPClient,
        typescript_lsp: TypeScriptLSPClient,  # ← NEW
        redis_client: Redis,
        cache_ttl: int = 3600
    ):
        """Initialize type extractor with LSP clients.

        Args:
            pyright_lsp: Python LSP client
            typescript_lsp: TypeScript LSP client (NEW)
            redis_client: Redis for L2 caching
            cache_ttl: Cache TTL in seconds
        """
        self.pyright_lsp = pyright_lsp
        self.typescript_lsp = typescript_lsp  # ← NEW
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)
```

---

### 2. Implement `_extract_typescript_types()`

**File**: `api/services/type_extractor_service.py`

```python
async def _extract_typescript_types(
    self,
    chunk: CodeChunk
) -> Dict[str, Any]:
    """Extract TypeScript types using LSP.

    Args:
        chunk: Code chunk to extract types from

    Returns:
        Dictionary with structured type metadata:
        {
            "parameters": [
                {
                    "name": "id",
                    "type": "string",
                    "type_info": {"kind": "string", "primitive": true}
                }
            ],
            "return_type": {
                "type": "Promise<User>",
                "resolved_type": "Promise<{ id: string; name: string }>",
                "generic_args": ["User"],
                "definition": {"file": "types.ts", "line": 1}
            },
            "imports": [
                {
                    "symbol": "User",
                    "from": "./types",
                    "resolved_path": "/project/types.ts"
                }
            ],
            "type_errors": [],
            "inferred_types": {}
        }
    """
    # Check cache first (L2)
    cache_key = f"ts-types:{chunk.id}"
    cached = await self._get_from_cache(cache_key)
    if cached:
        return cached

    try:
        # Create temporary workspace with TypeScript file
        workspace_dir = await self._create_typescript_workspace(chunk)

        # Get hover info for function/method signature
        hover = await self.typescript_lsp.get_hover(
            file_path=workspace_dir / "temp.ts",
            line=0,  # Assuming chunk starts at line 0 in temp file
            character=0
        )

        if not hover:
            self.logger.warning(f"No hover info for chunk {chunk.id}, using heuristic")
            return await self._extract_typescript_heuristic(chunk)

        # Parse hover response → structured metadata
        metadata = self._parse_typescript_hover(hover, chunk)

        # Extract imports
        metadata["imports"] = self._extract_typescript_imports(chunk.source_code)

        # Cache result (L2)
        await self._set_in_cache(cache_key, metadata)

        return metadata

    except Exception as e:
        self.logger.error(f"TypeScript LSP extraction failed: {e}")
        # Fallback to heuristic
        return await self._extract_typescript_heuristic(chunk)
```

---

### 3. Parse LSP Hover Response

```python
def _parse_typescript_hover(
    self,
    hover: Dict[str, Any],
    chunk: CodeChunk
) -> Dict[str, Any]:
    """Parse LSP hover response into structured metadata.

    Args:
        hover: LSP hover result from get_hover()
        chunk: Original code chunk

    Returns:
        Structured type metadata
    """
    contents = hover.get("contents", "")

    # Example hover content:
    # "async getUser(id: string): Promise<User>"

    metadata = {
        "parameters": [],
        "return_type": None,
        "imports": [],
        "type_errors": [],
        "inferred_types": {}
    }

    # Extract signature (handle different formats)
    if "function " in contents or "method " in contents:
        signature = self._extract_signature_from_hover(contents)

        # Parse parameters
        metadata["parameters"] = self._parse_typescript_parameters(signature)

        # Parse return type
        metadata["return_type"] = self._parse_typescript_return_type(signature)

    elif "interface " in contents or "class " in contents:
        # For interfaces/classes, extract structure
        metadata["structure"] = self._parse_typescript_structure(contents)

    return metadata


def _extract_signature_from_hover(self, contents: str) -> str:
    """Extract function/method signature from hover content.

    Args:
        contents: Hover markdown content

    Returns:
        Cleaned signature string

    Example:
        Input: "(method) UserService.getUser(id: string): Promise<User>"
        Output: "getUser(id: string): Promise<User>"
    """
    # Remove markdown formatting
    signature = contents.strip()

    # Remove prefixes like "(method)", "(function)", etc.
    if ")" in signature:
        parts = signature.split(")", 1)
        if len(parts) > 1:
            signature = parts[1].strip()

    # Remove class prefixes (e.g., "UserService.")
    if "." in signature:
        parts = signature.split(".")
        signature = parts[-1]

    return signature


def _parse_typescript_parameters(
    self,
    signature: str
) -> List[Dict[str, Any]]:
    """Parse TypeScript parameters from signature.

    Args:
        signature: Function signature

    Returns:
        List of parameter metadata

    Example:
        Input: "getUser(id: string, options?: UserOptions): Promise<User>"
        Output: [
            {
                "name": "id",
                "type": "string",
                "optional": false,
                "type_info": {"kind": "string", "primitive": true}
            },
            {
                "name": "options",
                "type": "UserOptions",
                "optional": true,
                "type_info": {"kind": "UserOptions", "primitive": false}
            }
        ]
    """
    parameters = []

    # Extract parameter list (between parentheses)
    if "(" not in signature or ")" not in signature:
        return parameters

    param_str = signature.split("(", 1)[1].split(")", 1)[0]

    # Split by comma (handle nested generics)
    param_parts = self._split_parameters(param_str)

    for param in param_parts:
        param = param.strip()
        if not param:
            continue

        # Parse: "id: string" or "options?: UserOptions"
        optional = "?" in param
        name, type_str = self._parse_parameter_declaration(param)

        parameters.append({
            "name": name,
            "type": type_str,
            "optional": optional,
            "type_info": self._get_type_info(type_str)
        })

    return parameters


def _parse_typescript_return_type(
    self,
    signature: str
) -> Optional[Dict[str, Any]]:
    """Parse TypeScript return type from signature.

    Args:
        signature: Function signature

    Returns:
        Return type metadata or None

    Example:
        Input: "getUser(id: string): Promise<User>"
        Output: {
            "type": "Promise<User>",
            "generic_args": ["User"],
            "type_info": {"kind": "Promise", "generic": true}
        }
    """
    # Extract return type (after ":")
    if ":" not in signature:
        return None

    parts = signature.split(":")
    if len(parts) < 2:
        return None

    return_type = parts[-1].strip()

    # Parse generics (e.g., Promise<User>)
    generic_args = self._extract_generic_args(return_type)

    return {
        "type": return_type,
        "generic_args": generic_args,
        "type_info": self._get_type_info(return_type)
    }


def _extract_generic_args(self, type_str: str) -> List[str]:
    """Extract generic type arguments.

    Args:
        type_str: Type string (e.g., "Promise<User>")

    Returns:
        List of generic arguments

    Example:
        Input: "Promise<User>"
        Output: ["User"]

        Input: "Map<string, User[]>"
        Output: ["string", "User[]"]
    """
    if "<" not in type_str or ">" not in type_str:
        return []

    # Extract content between < and >
    start = type_str.index("<")
    end = type_str.rindex(">")
    args_str = type_str[start + 1:end]

    # Split by comma (handle nested generics)
    return [arg.strip() for arg in self._split_generic_args(args_str)]


def _get_type_info(self, type_str: str) -> Dict[str, Any]:
    """Get type classification info.

    Args:
        type_str: Type string

    Returns:
        Type classification

    Example:
        Input: "string"
        Output: {"kind": "string", "primitive": true}

        Input: "Promise<User>"
        Output: {"kind": "Promise", "generic": true, "primitive": false}
    """
    # Check for primitives
    primitives = {"string", "number", "boolean", "null", "undefined", "void", "any"}
    base_type = type_str.split("<")[0].strip()

    is_primitive = base_type in primitives
    is_generic = "<" in type_str and ">" in type_str
    is_array = "[]" in type_str

    return {
        "kind": base_type,
        "primitive": is_primitive,
        "generic": is_generic,
        "array": is_array
    }
```

---

### 4. Extract Imports

```python
def _extract_typescript_imports(self, source_code: str) -> List[Dict[str, Any]]:
    """Extract import statements from TypeScript code.

    Args:
        source_code: TypeScript source code

    Returns:
        List of import metadata

    Example:
        Input:
        ```
        import { User } from './types';
        import * as api from './api';
        ```

        Output:
        [
            {"symbol": "User", "from": "./types", "type": "named"},
            {"symbol": "*", "from": "./api", "alias": "api", "type": "namespace"}
        ]
    """
    imports = []

    # Parse import lines
    import_lines = [
        line.strip()
        for line in source_code.split("\n")
        if line.strip().startswith("import ")
    ]

    for line in import_lines:
        # Parse: import { User } from './types';
        if " from " in line:
            import_part = line.split(" from ")[0].replace("import ", "").strip()
            from_part = line.split(" from ")[1].strip().strip("';\"")

            # Named imports: { User, Post }
            if "{" in import_part:
                symbols = import_part.strip("{}").split(",")
                for symbol in symbols:
                    imports.append({
                        "symbol": symbol.strip(),
                        "from": from_part,
                        "type": "named"
                    })

            # Namespace import: * as api
            elif "*" in import_part:
                alias = import_part.split(" as ")[1].strip()
                imports.append({
                    "symbol": "*",
                    "from": from_part,
                    "alias": alias,
                    "type": "namespace"
                })

            # Default import: User
            else:
                imports.append({
                    "symbol": import_part.strip(),
                    "from": from_part,
                    "type": "default"
                })

    return imports
```

---

### 5. Heuristic Fallback

```python
async def _extract_typescript_heuristic(
    self,
    chunk: CodeChunk
) -> Dict[str, Any]:
    """Fallback heuristic type extraction (without LSP).

    Args:
        chunk: Code chunk

    Returns:
        Basic type metadata (70% accuracy)

    Note:
        This is the fallback when LSP fails or times out.
        Uses regex-based parsing (same as EPIC-15).
    """
    metadata = {
        "parameters": [],
        "return_type": None,
        "imports": self._extract_typescript_imports(chunk.source_code),
        "extraction_method": "heuristic"  # Mark as heuristic
    }

    # Extract from chunk.metadata (populated by EPIC-15 parser)
    if chunk.metadata:
        if "parameters" in chunk.metadata:
            # Convert simple list to structured format
            metadata["parameters"] = [
                {"name": param, "type": "any"}
                for param in chunk.metadata["parameters"]
            ]

        if "return_type" in chunk.metadata:
            metadata["return_type"] = {
                "type": chunk.metadata["return_type"]
            }

    return metadata
```

---

### 6. Workspace Management

```python
async def _create_typescript_workspace(
    self,
    chunk: CodeChunk
) -> Path:
    """Create temporary TypeScript workspace for LSP.

    Args:
        chunk: Code chunk to create workspace for

    Returns:
        Path to workspace directory

    Note:
        Workspace contains:
        - temp.ts: The code chunk
        - tsconfig.json: Minimal TypeScript config
    """
    workspace_dir = Path(f"/tmp/ts-workspace-{chunk.id}")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Write chunk to temp.ts
    temp_file = workspace_dir / "temp.ts"
    temp_file.write_text(chunk.source_code)

    # Create minimal tsconfig.json
    tsconfig = {
        "compilerOptions": {
            "target": "ES2020",
            "module": "commonjs",
            "strict": false,
            "skipLibCheck": true
        }
    }

    tsconfig_file = workspace_dir / "tsconfig.json"
    tsconfig_file.write_text(json.dumps(tsconfig, indent=2))

    return workspace_dir
```

---

## 🧪 Testing Strategy

### Integration Tests

**File**: `tests/services/test_type_extractor_service.py`

**New Test Cases** (5+ tests):

```python
@pytest.mark.asyncio
async def test_extract_typescript_function_types():
    """Test TypeScript function type extraction."""
    # Arrange
    chunk = CodeChunk(
        id=uuid.uuid4(),
        file_path="test.ts",
        language="typescript",
        chunk_type=ChunkType.FUNCTION,
        source_code="""
        export async function getUser(id: string): Promise<User> {
            return await api.get(`/users/${id}`);
        }
        """,
        name="getUser",
        start_line=1,
        end_line=3,
        repository="test",
        commit_hash="abc123"
    )

    typescript_lsp = Mock()
    typescript_lsp.get_hover = AsyncMock(return_value={
        "contents": "(function) getUser(id: string): Promise<User>"
    })

    service = TypeExtractorService(
        pyright_lsp=Mock(),
        typescript_lsp=typescript_lsp,
        redis_client=Mock()
    )

    # Act
    result = await service.extract_types(chunk, language="typescript")

    # Assert
    assert result["parameters"][0]["name"] == "id"
    assert result["parameters"][0]["type"] == "string"
    assert result["return_type"]["type"] == "Promise<User>"
    assert "User" in result["return_type"]["generic_args"]


@pytest.mark.asyncio
async def test_extract_typescript_class_method_types():
    """Test TypeScript class method type extraction."""
    chunk = CodeChunk(
        id=uuid.uuid4(),
        file_path="test.ts",
        language="typescript",
        chunk_type=ChunkType.METHOD,
        source_code="""
        async getUser(id: string): Promise<User> {
            return await this.api.get(`/users/${id}`);
        }
        """,
        name="getUser",
        start_line=1,
        end_line=3,
        repository="test",
        commit_hash="abc123"
    )

    typescript_lsp = Mock()
    typescript_lsp.get_hover = AsyncMock(return_value={
        "contents": "(method) UserService.getUser(id: string): Promise<User>"
    })

    service = TypeExtractorService(
        pyright_lsp=Mock(),
        typescript_lsp=typescript_lsp,
        redis_client=Mock()
    )

    # Act
    result = await service.extract_types(chunk, language="typescript")

    # Assert
    assert len(result["parameters"]) == 1
    assert result["parameters"][0]["type"] == "string"
    assert result["return_type"]["generic_args"] == ["User"]


@pytest.mark.asyncio
async def test_extract_typescript_imports():
    """Test TypeScript import extraction."""
    chunk = CodeChunk(
        id=uuid.uuid4(),
        file_path="test.ts",
        language="typescript",
        chunk_type=ChunkType.CLASS,
        source_code="""
        import { User, Post } from './types';
        import * as api from './api';

        export class UserService {
            async getUser(id: string): Promise<User> {
                return await api.get(`/users/${id}`);
            }
        }
        """,
        name="UserService",
        start_line=1,
        end_line=8,
        repository="test",
        commit_hash="abc123"
    )

    service = TypeExtractorService(
        pyright_lsp=Mock(),
        typescript_lsp=Mock(),
        redis_client=Mock()
    )

    # Act
    result = await service.extract_types(chunk, language="typescript")

    # Assert
    assert len(result["imports"]) == 3
    assert result["imports"][0]["symbol"] == "User"
    assert result["imports"][0]["from"] == "./types"
    assert result["imports"][2]["type"] == "namespace"


@pytest.mark.asyncio
async def test_typescript_lsp_fallback_to_heuristic():
    """Test graceful degradation when LSP fails."""
    chunk = CodeChunk(
        id=uuid.uuid4(),
        file_path="test.ts",
        language="typescript",
        chunk_type=ChunkType.FUNCTION,
        source_code="export function test(x: number): string { return ''; }",
        name="test",
        metadata={"parameters": ["x"], "return_type": "string"},
        start_line=1,
        end_line=1,
        repository="test",
        commit_hash="abc123"
    )

    typescript_lsp = Mock()
    typescript_lsp.get_hover = AsyncMock(side_effect=TimeoutError("LSP timeout"))

    service = TypeExtractorService(
        pyright_lsp=Mock(),
        typescript_lsp=typescript_lsp,
        redis_client=Mock()
    )

    # Act
    result = await service.extract_types(chunk, language="typescript")

    # Assert
    assert result["extraction_method"] == "heuristic"  # Fallback used
    assert len(result["parameters"]) == 1


@pytest.mark.asyncio
async def test_typescript_generic_type_resolution():
    """Test generic type resolution (Promise<T>, Array<T>, etc.)."""
    chunk = CodeChunk(
        id=uuid.uuid4(),
        file_path="test.ts",
        language="typescript",
        chunk_type=ChunkType.FUNCTION,
        source_code="function getAll(): Promise<User[]> { return []; }",
        name="getAll",
        start_line=1,
        end_line=1,
        repository="test",
        commit_hash="abc123"
    )

    typescript_lsp = Mock()
    typescript_lsp.get_hover = AsyncMock(return_value={
        "contents": "(function) getAll(): Promise<User[]>"
    })

    service = TypeExtractorService(
        pyright_lsp=Mock(),
        typescript_lsp=typescript_lsp,
        redis_client=Mock()
    )

    # Act
    result = await service.extract_types(chunk, language="typescript")

    # Assert
    assert result["return_type"]["type"] == "Promise<User[]>"
    assert "User[]" in result["return_type"]["generic_args"]
    assert result["return_type"]["type_info"]["generic"] is True
```

---

## 📊 Performance Impact

### Before EPIC-16 (EPIC-15 only)

**Type Extraction Accuracy**: 70% (heuristic)

**Example Metadata**:
```json
{
  "parameters": ["id"],
  "return_type": "Promise<User>"
}
```

**Problems**:
- Parameters only have names (no types)
- Return type is unresolved string
- No import tracking
- No generic resolution

---

### After EPIC-16

**Type Extraction Accuracy**: 95%+ (LSP-powered)

**Example Metadata**:
```json
{
  "parameters": [
    {
      "name": "id",
      "type": "string",
      "optional": false,
      "type_info": {"kind": "string", "primitive": true}
    }
  ],
  "return_type": {
    "type": "Promise<User>",
    "generic_args": ["User"],
    "type_info": {"kind": "Promise", "generic": true}
  },
  "imports": [
    {"symbol": "User", "from": "./types", "type": "named"}
  ],
  "extraction_method": "lsp"
}
```

**Improvements**:
- ✅ Parameters with full type info
- ✅ Return type with generic resolution
- ✅ Import tracking
- ✅ Type classification (primitive, generic, array)

**Improvement**: 70% → 95%+ accuracy (+35% improvement)

---

## 🔗 Dependencies

### 1. Dependency Injection (dependencies.py)

```python
from api.services.type_extractor_service import TypeExtractorService

def get_type_extractor_service(
    pyright_lsp: PyrightLSPClient = Depends(get_pyright_lsp_client),
    typescript_lsp: TypeScriptLSPClient = Depends(get_typescript_lsp_client),  # ← NEW
    redis_client: Redis = Depends(get_redis_client)
) -> TypeExtractorService:
    return TypeExtractorService(
        pyright_lsp=pyright_lsp,
        typescript_lsp=typescript_lsp,  # ← NEW
        redis_client=redis_client,
        cache_ttl=3600
    )
```

---

### 2. Code Indexing Pipeline

**Usage in CodeIndexingService**:
```python
# After chunking (EPIC-15)
chunks = await code_chunking_service.chunk_code(
    source_code=file_content,
    file_path=file_path,
    language=language,
    repository=repository,
    commit_hash=commit_hash
)

# Extract types (EPIC-16)
for chunk in chunks:
    type_metadata = await type_extractor_service.extract_types(
        chunk=chunk,
        language=language
    )

    # Merge type metadata into chunk.metadata
    chunk.metadata.update(type_metadata)

# Store chunks with enriched metadata
await code_chunk_repository.bulk_create(chunks)
```

---

## 📝 Implementation Checklist

- [ ] Update `TypeExtractorService.__init__()` with `typescript_lsp` parameter
- [ ] Implement `_extract_typescript_types()` method
- [ ] Implement `_parse_typescript_hover()` method
- [ ] Implement `_parse_typescript_parameters()` method
- [ ] Implement `_parse_typescript_return_type()` method
- [ ] Implement `_extract_generic_args()` method
- [ ] Implement `_get_type_info()` method
- [ ] Implement `_extract_typescript_imports()` method
- [ ] Implement `_extract_typescript_heuristic()` fallback
- [ ] Implement `_create_typescript_workspace()` method
- [ ] Update `extract_types()` to route TypeScript to LSP
- [ ] Update `dependencies.py` with new DI
- [ ] Create integration tests (5+ test cases)
- [ ] Test with real TypeScript files
- [ ] Validate 95%+ accuracy with test suite

---

## 🎯 Success Criteria

**Story 16.2 is complete when**:

1. ✅ TypeExtractorService extended with TypeScript LSP support (~120 lines added)
2. ✅ All TypeScript type extraction methods implemented
3. ✅ LSP hover response parsing working (parameters, return types, imports)
4. ✅ Generic type resolution working (Promise<T>, Array<T>, etc.)
5. ✅ Import extraction working (named, default, namespace)
6. ✅ Graceful degradation to heuristic on LSP failure
7. ✅ Redis caching integrated (L2)
8. ✅ Integration tests passing (5+ test cases, >90% coverage)
9. ✅ Type extraction accuracy: 95%+ (validated with tests)
10. ✅ Zero regressions in Python type extraction

---

**Last Updated**: 2025-10-23
**Status**: 📝 **READY FOR IMPLEMENTATION** (5 pts)
**Next Story**: [EPIC-16 Story 16.3: Integration & Performance](EPIC-16_STORY_16.3_ANALYSIS.md)
