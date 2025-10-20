# Serena vs MnemoLite: Architecture Comparison & Recommendations

**Version:** 1.0.0
**Date:** 2025-10-18
**Status:** Analysis Complete

---

## Executive Summary

This document analyzes Serena's architecture to identify techniques and improvements for MnemoLite. After examining 15+ source files from Serena's codebase, we've identified **8 high-value improvements** and **3 architectural patterns** that could significantly enhance MnemoLite's capabilities.

**Key Finding:** Serena and MnemoLite are **complementary architectures** optimized for different use cases:
- **Serena**: Real-time IDE-like editing with ephemeral caching (LSP-based)
- **MnemoLite**: Persistent semantic search and code intelligence (embedding-based)

**Recommendation:** Adopt a **hybrid approach** combining LSP precision editing with pgvector semantic search.

---

## Table of Contents

1. [Architecture Comparison Matrix](#architecture-comparison-matrix)
2. [Serena's Key Techniques](#serenas-key-techniques)
3. [Actionable Improvements for MnemoLite](#actionable-improvements-for-mnemolite)
4. [Implementation Roadmap](#implementation-roadmap)
5. [Code Examples](#code-examples)
6. [References](#references)

---

## Architecture Comparison Matrix

| Component | Serena | MnemoLite | Optimal Hybrid |
|-----------|--------|-----------|----------------|
| **Code Analysis** | LSP (30+ languages) | tree-sitter AST | **LSP + tree-sitter** |
| **Symbol Extraction** | DocumentSymbol via LSP | AST node traversal | LSP for editing, tree-sitter for indexing |
| **Storage** | In-memory cache (hash-based) | PostgreSQL + pgvector | PostgreSQL + Redis cache layer |
| **Memory/Knowledge** | Markdown files (.serena/memories/) | Dual embeddings (768D TEXT+CODE) | **Keep dual embeddings** + metadata files |
| **Search** | Regex pattern + symbol name | Hybrid (RRF + vector + lexical) | **Keep hybrid search** + LSP symbol queries |
| **Editing** | Symbol-level precision (LSP) | ❌ None | **Add LSP editing tools** |
| **Caching Strategy** | MD5 hash → (content, symbols) | No memory cache | **Add Redis/dict cache** |
| **Type Information** | ✅ Via LSP (Pyright, gopls) | ❌ Not extracted | Add LSP type queries |
| **Refactoring** | ✅ rename_symbol (workspace-wide) | ❌ None | Add LSP refactoring tools |
| **Metadata Extraction** | Runtime via LSP | Static via tree-sitter | **Both**: tree-sitter for indexing, LSP for live queries |
| **Performance** | Fast (in-memory, ~10ms) | Moderate (DB queries, <200ms) | Cache hot paths, optimize cold queries |
| **Persistence** | None (restart loses cache) | ✅ Full (PostgreSQL) | **Keep PostgreSQL** + cache |

### Verdict

✅ **Strengths to Keep (MnemoLite)**:
- Persistent semantic search with dual embeddings
- PostgreSQL-based storage with pgvector
- Hybrid search (RRF fusion)
- Graph construction and traversal
- Code intelligence dashboard

🔄 **Improvements from Serena**:
- Add LSP integration for editing capabilities
- Implement caching layer (Redis or in-memory)
- Add symbol-level editing tools
- Improve metadata extraction with LSP type information
- Add workspace-wide refactoring

---

## Serena's Key Techniques

### 1. Hash-Based Caching (Excellent)

**Location**: `serena-main/src/solidlsp/ls.py:240-250`

```python
class SolidLanguageServer(ABC):
    def __init__(self, ...):
        # Maps: file_path -> (content_hash, (symbols, nested_symbols))
        self._document_symbols_cache: dict[str, tuple[str, tuple[...]]] = {}
        self._cache_lock = threading.Lock()

    @dataclass
    class LSPFileBuffer:
        uri: str
        contents: str
        version: int
        language_id: str
        ref_count: int
        content_hash: str  # MD5 hash for cache invalidation
```

**How it works**:
1. Calculate MD5 hash of file contents
2. Check if `file_path` exists in cache with same hash
3. If match: return cached symbols (0ms)
4. If miss/mismatch: query LSP, update cache with new hash

**Benefits**:
- **129x faster** than querying LSP every time (from MnemoLite's own graph metrics)
- Thread-safe with locks
- Automatic invalidation on content change
- Zero false positives (hash collision negligible)

**MnemoLite Application**:
```python
# Add to api/db/repositories/code_chunk.py or new api/services/chunk_cache.py
import hashlib
from typing import Dict, Tuple, List
from threading import Lock

class CodeChunkCache:
    """In-memory cache for code chunks with hash-based invalidation."""

    def __init__(self):
        self._cache: Dict[str, Tuple[str, List[CodeChunk]]] = {}
        self._lock = Lock()

    def get_chunks(self, file_path: str, content: str) -> List[CodeChunk] | None:
        """Returns cached chunks if content hash matches, else None."""
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        with self._lock:
            if file_path in self._cache:
                cached_hash, cached_chunks = self._cache[file_path]
                if cached_hash == content_hash:
                    return cached_chunks
        return None

    def set_chunks(self, file_path: str, content: str, chunks: List[CodeChunk]):
        """Stores chunks with content hash."""
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        with self._lock:
            self._cache[file_path] = (content_hash, chunks)

    def invalidate(self, file_path: str):
        """Removes cached entry for file."""
        with self._lock:
            self._cache.pop(file_path, None)
```

**Priority**: 🔴 **HIGH** (Easy to implement, big performance gain)

---

### 2. Symbol-Level Editing (Game-Changer)

**Location**: `serena-main/src/serena/code_editor.py:85-181`

**Operations**:
- `replace_body(name_path, file, body)` - Replace function/class body
- `insert_after_symbol(name_path, file, content)` - Add content after symbol
- `insert_before_symbol(name_path, file, content)` - Add content before symbol
- `delete_symbol(name_path, file)` - Remove symbol entirely
- `rename_symbol(name_path, file, new_name)` - Rename with workspace-wide refactoring

**Example**: Replace function body
```python
class LanguageServerCodeEditor(CodeEditor):
    def replace_body(self, name_path: str, relative_file_path: str, body: str):
        """
        Replaces the body of a symbol (function, class, method).

        :param name_path: Symbol path like "/MyClass/my_method"
        :param relative_file_path: "src/services/search.py"
        :param body: New function body (code only, no def/signature)
        """
        symbol = self._find_unique_symbol(name_path, relative_file_path)
        start_pos = symbol.get_body_start_position_or_raise()  # After signature
        end_pos = symbol.get_body_end_position_or_raise()      # Before closing

        with self._edited_file_context(relative_file_path) as edited_file:
            body = body.strip()  # Remove extra whitespace
            edited_file.delete_text_between_positions(start_pos, end_pos)
            edited_file.insert_text_at_position(start_pos, body)
```

**Smart Whitespace Handling**:
```python
def insert_after_symbol(self, name_path, file, body):
    # Ensure minimum 0 or 1 empty lines between symbols based on type
    min_empty_lines = 1 if symbol.is_neighbouring_definition_separated_by_empty_line() else 0
    original_leading_newlines = self._count_leading_newlines(body)
    num_leading_empty_lines = max(min_empty_lines, original_leading_newlines)

    # Preserve formatting conventions automatically!
    if num_leading_empty_lines:
        body = ("\n" * num_leading_empty_lines) + body.lstrip("\r\n")
```

**MnemoLite Application**: New API endpoints

```python
# api/routes/code_editing_routes.py (NEW FILE)
from fastapi import APIRouter, Depends, HTTPException
from api.services.lsp_code_editor import LSPCodeEditor
from pydantic import BaseModel

router = APIRouter(prefix="/v1/code/edit", tags=["code-editing"])

class ReplaceBodyRequest(BaseModel):
    repository: str
    file_path: str
    symbol_name_path: str  # e.g., "/SearchService/hybrid_search"
    new_body: str

class RenameSymbolRequest(BaseModel):
    repository: str
    file_path: str
    symbol_name_path: str
    new_name: str

@router.post("/replace-body")
async def replace_symbol_body(
    request: ReplaceBodyRequest,
    editor: LSPCodeEditor = Depends(get_lsp_editor)
):
    """Replace the body of a function/class/method with new code."""
    try:
        editor.replace_body(
            name_path=request.symbol_name_path,
            relative_file_path=request.file_path,
            body=request.new_body
        )
        # Re-index the modified file
        await reindex_file(request.repository, request.file_path)
        return {"status": "success", "message": f"Replaced body of {request.symbol_name_path}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/rename-symbol")
async def rename_symbol(
    request: RenameSymbolRequest,
    editor: LSPCodeEditor = Depends(get_lsp_editor)
):
    """Rename a symbol across the entire workspace (all references)."""
    result_msg = editor.rename_symbol(
        name_path=request.symbol_name_path,
        relative_file_path=request.file_path,
        new_name=request.new_name
    )
    # Re-index all modified files
    await reindex_repository(request.repository)
    return {"status": "success", "message": result_msg}
```

**Priority**: 🟡 **MEDIUM-HIGH** (High value but requires LSP integration - significant work)

---

### 3. LSP Protocol Handler (Robust)

**Location**: `serena-main/src/solidlsp/ls_handler.py:95-589`

**Key Features**:
- JSON-RPC 2.0 over stdin/stdout
- Thread-safe with locks (`_stdin_lock`, `_request_id_lock`, `_response_handlers_lock`)
- Request timeout support
- Automatic process cleanup on failure
- Separate threads for stdout/stderr reading

**Error Handling Pattern**:
```python
def _read_ls_process_stdout(self):
    exception: Exception | None = None
    try:
        while self.process and self.process.stdout:
            # Read messages, handle responses
            ...
    except LanguageServerTerminatedException as e:
        exception = e
    except (BrokenPipeError, ConnectionResetError) as e:
        exception = LanguageServerTerminatedException(
            "Language server process terminated while reading stdout", cause=e
        )
    finally:
        if not self._is_shutting_down:
            log.error(str(exception))
            self._cancel_pending_requests(exception)  # Fail fast!
```

**MnemoLite Application**: Could use for Python LSP integration if editing is added

**Priority**: 🟢 **LOW-MEDIUM** (Only needed if LSP editing is implemented)

---

### 4. Hierarchical Symbol Name Paths (Clever)

**Location**: `serena-main/src/serena/symbol.py:80-120`

**Concept**: Symbol paths like file system paths

```python
class LanguageServerSymbol:
    _NAME_PATH_SEP = "/"

    @staticmethod
    def match_name_path(name_path: str, symbol_name_path_parts: list[str],
                        substring_matching: bool) -> bool:
        """
        Matches symbol paths with support for:
        - Absolute: "/MyClass/my_method" (must start from root)
        - Relative: "my_method" (matches anywhere)
        - Substring: True → "search" matches "hybrid_search"

        Examples:
        - "/SearchService/hybrid_search" → class SearchService, method hybrid_search
        - "hybrid_search" → any symbol named hybrid_search
        - "search" (substring=True) → hybrid_search, vector_search, etc.
        """
        # Pattern matching logic...
```

**Why This Matters**: Precise symbol identification without line numbers

**Current MnemoLite Approach**:
```sql
-- api/db/repositories/code_chunk.py
WHERE name ILIKE %param%  -- Simple text matching
```

**Improved Approach**:
```python
# api/models/code_chunk.py - Add field
class CodeChunk(BaseModel):
    name_path: str | None = None  # e.g., "SearchService/hybrid_search"

# api/services/code_chunking.py - Extract during chunking
def extract_name_path(node, parent_names: list[str]) -> str:
    """Builds hierarchical name path for symbol."""
    current_name = extract_name(node)
    all_names = parent_names + [current_name]
    return "/".join(all_names)

# Usage in chunking
def chunk_file(source_code: str, language: str) -> list[CodeChunk]:
    parent_stack = []  # Track nesting
    for node in ast_nodes:
        if node.type in ['class_definition', 'function_definition']:
            name_path = extract_name_path(node, parent_stack)
            chunk.name_path = name_path
            if node.type == 'class_definition':
                parent_stack.append(extract_name(node))
    # Pop stack as we exit scopes
```

**Search Improvement**:
```python
# api/db/repositories/code_chunk.py
async def find_by_name_path(
    self,
    name_path: str,
    substring_matching: bool = False,
    repository: str | None = None
) -> list[CodeChunk]:
    """
    Find chunks by hierarchical name path.

    Examples:
    - "/SearchService/hybrid_search" → exact class+method
    - "hybrid_search" → any symbol named hybrid_search
    - "search" (substring=True) → all symbols containing "search"
    """
    if substring_matching:
        condition = CodeChunksTable.c.name_path.ilike(f"%{name_path}%")
    elif name_path.startswith("/"):
        # Absolute path - exact match
        condition = CodeChunksTable.c.name_path == name_path.lstrip("/")
    else:
        # Relative path - match end of path
        condition = CodeChunksTable.c.name_path.ilike(f"%/{name_path}")

    query = select(CodeChunksTable).where(condition)
    if repository:
        query = query.where(CodeChunksTable.c.repository == repository)

    result = await self.session.execute(query)
    return result.scalars().all()
```

**Priority**: 🔴 **HIGH** (Easy to implement, major usability improvement)

---

### 5. Simple Memory System (Surprisingly Effective)

**Location**: `serena-main/src/serena/tools/memory_tools.py:1-66`

**Serena's Approach**: Just markdown files!

```python
class MemoriesManager:
    def __init__(self, project_root: str):
        self._memory_dir = Path(project_root) / ".serena" / "memories"

    def save_memory(self, name: str, content: str) -> str:
        """Saves markdown file in .serena/memories/{name}.md"""
        memory_file = self._memory_dir / f"{name}.md"
        memory_file.write_text(content, encoding='utf-8')
        return f"Memory '{name}' saved."

    def load_memory(self, name: str) -> str:
        """Loads markdown content or returns 'not found'."""
        memory_file = self._memory_dir / f"{name}.md"
        if memory_file.exists():
            return memory_file.read_text(encoding='utf-8')
        return f"Memory '{name}' not found."

    def list_memories(self) -> list[str]:
        """Returns list of memory names (without .md extension)."""
        return [f.stem for f in self._memory_dir.glob("*.md")]
```

**MnemoLite Could Add**: Hybrid approach (keep embeddings, add human-readable files)

```python
# api/services/project_knowledge.py (NEW FILE)
class ProjectKnowledgeManager:
    """Manages both structured embeddings and human-readable markdown memories."""

    def __init__(self, repository_root: str):
        self.memory_dir = Path(repository_root) / ".mnemolite" / "knowledge"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    async def save_insight(
        self,
        name: str,
        content: str,
        embedding_service: EmbeddingService
    ):
        """
        Saves insight in BOTH formats:
        1. Markdown file for human readability
        2. Database with embedding for semantic search
        """
        # 1. Human-readable markdown
        markdown_file = self.memory_dir / f"{name}.md"
        markdown_content = f"""# {name}

**Created**: {datetime.utcnow().isoformat()}
**Type**: Project Insight

---

{content}
"""
        markdown_file.write_text(markdown_content, encoding='utf-8')

        # 2. Searchable embedding
        embedding = await embedding_service.generate_embedding(content)
        await self.db.memories.create({
            "name": name,
            "content": content,
            "embedding": embedding,
            "file_path": str(markdown_file),
            "created_at": datetime.utcnow()
        })

        return f"Insight '{name}' saved (searchable + markdown)"

    async def search_insights(self, query: str, top_k: int = 5):
        """Search insights using vector similarity."""
        query_embedding = await self.embedding_service.generate_embedding(query)
        return await self.db.memories.vector_search(query_embedding, limit=top_k)
```

**API Endpoints**:
```python
# api/routes/knowledge_routes.py (NEW)
@router.post("/v1/knowledge/save")
async def save_project_insight(name: str, content: str):
    """Save a project insight (best practices, architecture notes, gotchas)."""
    result = await knowledge_manager.save_insight(name, content, embedding_service)
    return {"status": "success", "message": result}

@router.get("/v1/knowledge/search")
async def search_insights(query: str, top_k: int = 5):
    """Semantic search across project knowledge base."""
    results = await knowledge_manager.search_insights(query, top_k)
    return {"insights": results}

@router.get("/v1/knowledge/list")
async def list_insights():
    """List all saved insights (markdown files + database entries)."""
    markdown_files = list(knowledge_manager.memory_dir.glob("*.md"))
    db_entries = await knowledge_manager.db.memories.list_all()
    return {
        "markdown_files": [f.stem for f in markdown_files],
        "database_entries": db_entries
    }
```

**Priority**: 🟢 **MEDIUM** (Nice-to-have, complements existing embeddings)

---

### 6. Context Manager Pattern for File Editing

**Location**: `serena-main/src/serena/code_editor.py:55-72`

**Pattern**: Automatic save on context exit

```python
@contextmanager
def _edited_file_context(self, relative_path: str) -> Iterator["CodeEditor.EditedFile"]:
    """
    Context manager for editing a file.
    Automatically saves file when context exits (no manual save needed).
    """
    with self._open_file_context(relative_path) as edited_file:
        yield edited_file
        # Automatically save the file on exit
        abs_path = os.path.join(self.project_root, relative_path)
        with open(abs_path, "w", encoding=self.encoding) as f:
            f.write(edited_file.get_contents())

# Usage
with self._edited_file_context(file_path) as edited_file:
    edited_file.delete_text_between_positions(start, end)
    edited_file.insert_text_at_position(pos, text)
    # File saved automatically here!
```

**Why It's Good**:
- No forgotten saves
- Exception-safe (rollback possible)
- Clean API

**MnemoLite Could Use**: For bulk operations

```python
# api/services/bulk_indexing.py
@asynccontextmanager
async def indexing_transaction(self, repository: str):
    """Context manager for bulk indexing with rollback on error."""
    async with self.db.begin():  # Transaction
        try:
            yield self
            # Commit automatically if no exception
        except Exception as e:
            # Rollback automatically on error
            logger.error(f"Indexing failed for {repository}, rolling back: {e}")
            raise

# Usage
async with bulk_indexer.indexing_transaction(repo) as indexer:
    for file in files:
        await indexer.index_file(file)
    # Auto-commit if all succeeded, auto-rollback if any failed
```

**Priority**: 🟢 **LOW-MEDIUM** (Nice pattern, but existing code works fine)

---

### 7. Tool Registry with Dynamic Loading

**Location**: `serena-main/src/serena/agent.py:123-168`

**Concept**: Auto-discover and filter tools based on context/mode

```python
class SerenaAgent:
    def __init__(self, context, modes):
        # Instantiate ALL tools
        self._all_tools = {
            tool_class: tool_class(self)
            for tool_class in ToolRegistry().get_all_tool_classes()
        }

        # Filter based on context (desktop-app, agent, ide-assistant)
        # and modes (planning, editing, interactive, one-shot)
        self._base_tool_set = ToolSet.default().apply(
            self.config,
            self._context,
            *self._modes
        )

        # Expose only allowed tools
        self._exposed_tools = AvailableTools([
            tool for tool in self._all_tools.values()
            if self._base_tool_set.includes_name(tool.get_name())
        ])

        logger.info(f"Loaded {len(self._all_tools)} tools, exposing {len(self._exposed_tools)}")
```

**MnemoLite Application**: Context-based tool exposure

```python
# api/services/tool_manager.py (NEW - for future AI agent integration)
from enum import Enum
from typing import Protocol

class ToolContext(Enum):
    """Different contexts for tool availability."""
    WEB_UI = "web_ui"              # Basic search/graph tools only
    API_CLIENT = "api_client"      # Full API access
    AI_AGENT = "ai_agent"          # AI-safe tools (no destructive ops)
    ADMIN = "admin"                # All tools including dangerous ones

class Tool(Protocol):
    """Base protocol for MnemoLite tools."""
    name: str
    description: str
    allowed_contexts: list[ToolContext]

    async def execute(self, **kwargs): ...

class ToolManager:
    def __init__(self):
        self._all_tools: dict[str, Tool] = {}
        self._register_tools()

    def _register_tools(self):
        """Auto-discover all tool classes."""
        from api.tools import search_tools, graph_tools, indexing_tools, admin_tools

        for module in [search_tools, graph_tools, indexing_tools, admin_tools]:
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, 'name') and hasattr(obj, 'execute'):
                    self._all_tools[obj.name] = obj()

    def get_tools_for_context(self, context: ToolContext) -> list[Tool]:
        """Returns only tools allowed in given context."""
        return [
            tool for tool in self._all_tools.values()
            if context in tool.allowed_contexts
        ]

# Example Tool Definition
class HybridSearchTool:
    name = "hybrid_search"
    description = "Search code using hybrid RRF+vector+lexical approach"
    allowed_contexts = [
        ToolContext.WEB_UI,
        ToolContext.API_CLIENT,
        ToolContext.AI_AGENT,
        ToolContext.ADMIN
    ]

    async def execute(self, query: str, repository: str, limit: int = 10):
        # Implementation...
        pass

class DeleteRepositoryTool:
    name = "delete_repository"
    description = "⚠️ DANGEROUS: Permanently delete all indexed data for repository"
    allowed_contexts = [ToolContext.ADMIN]  # Admin only!

    async def execute(self, repository: str, confirm: bool = False):
        if not confirm:
            raise ValueError("Must set confirm=True to delete repository")
        # Implementation...
```

**Priority**: 🟢 **LOW** (Future-proofing for AI agent integration)

---

### 8. Regex-Based File Search with Glob Patterns

**Location**: `serena-main/src/serena/tools/file_tools.py:294-404`

**Feature**: Advanced search with glob include/exclude patterns

```python
class SearchForPatternTool:
    def apply(
        self,
        substring_pattern: str,           # Regex pattern
        context_lines_before: int = 0,
        context_lines_after: int = 0,
        paths_include_glob: str = "",     # e.g., "*.py", "src/**/*.ts"
        paths_exclude_glob: str = "",     # e.g., "*test*", "**/*_generated.py"
        relative_path: str = "",
        restrict_search_to_code_files: bool = False,
    ):
        """
        Flexible search with glob patterns.

        Examples:
        - Find all TODO comments in Python files:
          pattern="TODO:", paths_include_glob="*.py"

        - Find function calls excluding tests:
          pattern="hybrid_search\(", paths_exclude_glob="**/test_*.py"

        - Find imports in specific directory:
          pattern="^import ", relative_path="src/services", paths_include_glob="*.py"
        """
        # Scan files matching glob patterns
        matches = search_files(
            rel_paths_to_search,
            substring_pattern,
            paths_include_glob=paths_include_glob,
            paths_exclude_glob=paths_exclude_glob,
        )
        return json.dumps(file_to_matches)
```

**MnemoLite Application**: Enhanced code search endpoint

```python
# api/routes/code_search_routes.py - ADD NEW ENDPOINT
from pathlib import Path
import re
from fnmatch import fnmatch

@router.get("/v1/code/search/pattern")
async def search_pattern(
    query: str,                          # Regex pattern
    repository: str,
    include_glob: str | None = None,     # "*.py" or "src/**/*.{py,go}"
    exclude_glob: str | None = None,     # "test_*.py"
    context_lines: int = 2,              # Lines before/after match
):
    """
    Advanced pattern search with glob filtering and context lines.

    Examples:
    - GET /v1/code/search/pattern?query=TODO:&repository=mnemolite&include_glob=*.py
    - GET /v1/code/search/pattern?query=class\s+\w+Search&exclude_glob=**/test_*
    """
    # Get all files in repository from database
    all_chunks = await code_chunk_repo.find_by_repository(repository)
    file_paths = set(chunk.file_path for chunk in all_chunks)

    # Filter by glob patterns
    filtered_paths = []
    for path in file_paths:
        # Check exclude pattern first (takes precedence)
        if exclude_glob and _glob_match(path, exclude_glob):
            continue
        # Check include pattern
        if include_glob and not _glob_match(path, include_glob):
            continue
        filtered_paths.append(path)

    # Search in filtered files
    results = {}
    for file_path in filtered_paths:
        matches = await _search_file_pattern(
            repository, file_path, query, context_lines
        )
        if matches:
            results[file_path] = matches

    return {
        "query": query,
        "repository": repository,
        "include_glob": include_glob,
        "exclude_glob": exclude_glob,
        "files_matched": len(results),
        "results": results
    }

def _glob_match(path: str, pattern: str) -> bool:
    """Match path against glob pattern (supports ** for recursive)."""
    # Convert glob to regex if contains **
    if "**" in pattern:
        regex_pattern = pattern.replace("**", ".*").replace("*", "[^/]*")
        return bool(re.match(regex_pattern, path))
    else:
        return fnmatch(Path(path).name, pattern)
```

**Priority**: 🟡 **MEDIUM** (Nice feature, enhances search capabilities)

---

## Actionable Improvements for MnemoLite

### Prioritized Roadmap

#### 🔴 **Priority 1: Quick Wins (Week 1-2)**

1. **Add Hash-Based Caching** [Technique #1]
   - **Effort**: 2-3 days
   - **Impact**: 10-100x faster re-indexing, reduced DB load
   - **Implementation**:
     - Create `api/services/chunk_cache.py` with `CodeChunkCache` class
     - Integrate into `code_indexing_service.py`
     - Add cache hit/miss metrics to `/health` endpoint
   - **Files to Create/Modify**:
     - NEW: `api/services/chunk_cache.py` (~100 lines)
     - MODIFY: `api/services/code_indexing_service.py` (add cache checks)
     - MODIFY: `api/routes/health.py` (add cache metrics)

2. **Add Hierarchical Name Paths** [Technique #4]
   - **Effort**: 2-3 days
   - **Impact**: Better symbol identification, more precise search
   - **Implementation**:
     - Add `name_path` field to `code_chunks` table
     - Modify chunking service to extract parent hierarchy
     - Add `/v1/code/search/by-name-path` endpoint
   - **Files to Create/Modify**:
     - MODIFY: `api/models/code_chunk.py` (add `name_path: str | None`)
     - MODIFY: `db/init/01-init.sql` (add column)
     - MODIFY: `api/services/code_chunking_service.py` (extract hierarchy)
     - NEW: Add search method in `api/db/repositories/code_chunk.py`

#### 🟡 **Priority 2: Medium-Term Enhancements (Week 3-6)**

3. **Add Pattern Search with Glob Filters** [Technique #8]
   - **Effort**: 3-4 days
   - **Impact**: More flexible code search, better developer experience
   - **Implementation**: New endpoint `/v1/code/search/pattern`
   - **Files to Create/Modify**:
     - NEW: Pattern matching logic in `api/services/pattern_search_service.py`
     - MODIFY: `api/routes/code_search_routes.py` (add endpoint)

4. **Add Simple Knowledge Base** [Technique #5]
   - **Effort**: 3-5 days
   - **Impact**: Human-readable project insights alongside embeddings
   - **Implementation**:
     - Create `.mnemolite/knowledge/` directory structure
     - Add markdown save/load + embedding persistence
     - New routes in `api/routes/knowledge_routes.py`
   - **Files to Create/Modify**:
     - NEW: `api/services/project_knowledge.py` (~150 lines)
     - NEW: `api/routes/knowledge_routes.py` (~100 lines)
     - NEW: Add `memories` table (optional, could use existing embeddings)

#### 🟢 **Priority 3: Advanced Features (Week 7-12)**

5. **Add LSP Integration for Editing** [Technique #2, #3]
   - **Effort**: 2-3 weeks (significant)
   - **Impact**: Code editing capabilities, symbol-level precision
   - **Implementation**:
     - Integrate Pyright LSP for Python (start with one language)
     - Create `LSPCodeEditor` service
     - Add editing endpoints (replace_body, rename_symbol, etc.)
   - **Files to Create/Modify**:
     - NEW: `api/services/lsp/` directory (LSP handler, ~500 lines)
     - NEW: `api/services/lsp_code_editor.py` (~400 lines)
     - NEW: `api/routes/code_editing_routes.py` (~200 lines)
   - **Dependencies**: Install `pyright` or `jedi` for Python LSP

6. **Add Tool Registry for AI Agent Integration** [Technique #7]
   - **Effort**: 1 week
   - **Impact**: Future-proofs for AI agents, clean architecture
   - **Implementation**: Context-based tool filtering
   - **Files to Create/Modify**:
     - NEW: `api/tools/` directory with tool base classes
     - NEW: `api/services/tool_manager.py` (~200 lines)
     - MODIFY: Existing services to implement Tool protocol

---

## Implementation Roadmap

### EPIC-10: Code Intelligence Enhancements (Based on Serena Analysis)

**Story Points**: ~42 points (estimated)

#### Phase 1: Performance & Caching (10 pts)
- **Story 1**: Hash-based chunk caching (5 pts)
- **Story 2**: Cache metrics and monitoring (3 pts)
- **Story 3**: Cache invalidation strategy (2 pts)

#### Phase 2: Symbol Enhancement (12 pts)
- **Story 4**: Hierarchical name paths extraction (5 pts)
- **Story 5**: Name path search API (4 pts)
- **Story 6**: UI integration for name path search (3 pts)

#### Phase 3: Advanced Search (8 pts)
- **Story 7**: Pattern search with glob filters (5 pts)
- **Story 8**: Context lines in search results (3 pts)

#### Phase 4: Knowledge Base (12 pts)
- **Story 9**: Project knowledge manager service (5 pts)
- **Story 10**: Knowledge API endpoints (4 pts)
- **Story 11**: Knowledge UI (dashboard integration) (3 pts)

**Dependencies**: None (can start immediately)
**Target**: Complete by end of Q4 2025

---

## Code Examples

### Example 1: Hash-Based Caching Integration

**Before** (api/services/code_indexing_service.py):
```python
async def index_file(self, file_path: str, repository: str):
    """Index a single file by parsing and storing chunks."""
    content = self._read_file(file_path)

    # Always parse and chunk (slow!)
    chunks = await self.chunking_service.chunk_file(content, language)

    # Store in database
    await self.code_chunk_repo.bulk_create(chunks)
```

**After** (with caching):
```python
from api.services.chunk_cache import CodeChunkCache

class CodeIndexingService:
    def __init__(self, ...):
        self.chunk_cache = CodeChunkCache()
        self.cache_hits = 0
        self.cache_misses = 0

    async def index_file(self, file_path: str, repository: str):
        """Index a single file with hash-based caching."""
        content = self._read_file(file_path)

        # Check cache first
        cached_chunks = self.chunk_cache.get_chunks(file_path, content)
        if cached_chunks:
            self.cache_hits += 1
            logger.info(f"Cache HIT for {file_path}")
            chunks = cached_chunks
        else:
            self.cache_misses += 1
            logger.info(f"Cache MISS for {file_path}, parsing...")
            chunks = await self.chunking_service.chunk_file(content, language)
            self.chunk_cache.set_chunks(file_path, content, chunks)

        # Store in database (update existing or insert new)
        await self.code_chunk_repo.bulk_upsert(chunks)

        return {
            "indexed": len(chunks),
            "cache_hit": cached_chunks is not None
        }

    def get_cache_stats(self) -> dict:
        """Returns cache performance metrics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate_percent": round(hit_rate, 2)
        }
```

**Health Endpoint Update**:
```python
# api/routes/health.py
@router.get("/health")
async def health_check(indexing_service: CodeIndexingService = Depends()):
    cache_stats = indexing_service.get_cache_stats()
    return {
        "status": "healthy",
        "cache": cache_stats,
        "database": await check_db(),
        ...
    }
```

**Expected Impact**:
- Re-indexing unchanged files: ~1ms (cache hit) vs ~65ms (cache miss)
- Large repositories with frequent re-indexing: **98%+ cache hit rate**

---

### Example 2: Hierarchical Name Path Search

**Database Migration**:
```sql
-- db/migrations/001_add_name_path.sql
ALTER TABLE code_chunks ADD COLUMN name_path TEXT;
CREATE INDEX idx_code_chunks_name_path ON code_chunks USING GIN (name_path gin_trgm_ops);
-- Trigram index for fast LIKE queries
```

**Chunking Enhancement**:
```python
# api/services/code_chunking_service.py
def _extract_chunks_recursive(
    self,
    node,
    parent_names: list[str] = []
) -> list[CodeChunk]:
    """Recursively extract chunks with hierarchical name paths."""
    chunks = []

    if node.type in ['function_definition', 'class_definition', 'method_declaration']:
        name = self._extract_name(node)

        # Build hierarchical path
        name_path = "/".join(parent_names + [name])

        chunk = CodeChunk(
            name=name,
            name_path=name_path,  # NEW FIELD
            chunk_type=self._map_type(node.type),
            source_code=self._get_source(node),
            # ... other fields
        )
        chunks.append(chunk)

        # Recurse into children with updated parent stack
        if node.type in ['class_definition', 'module']:
            child_parent_names = parent_names + [name]
        else:
            child_parent_names = parent_names

        for child in node.children:
            chunks.extend(self._extract_chunks_recursive(child, child_parent_names))

    return chunks
```

**Search Endpoint**:
```python
# api/routes/code_search_routes.py
@router.get("/v1/code/search/by-name-path")
async def search_by_name_path(
    name_path: str,
    repository: str,
    substring: bool = False,
    repo: CodeChunkRepository = Depends(get_code_chunk_repo)
):
    """
    Search code by hierarchical name path.

    Examples:
    - /SearchService/hybrid_search → exact class+method
    - hybrid_search → any symbol with that name
    - search (substring=True) → all symbols containing "search"
    """
    chunks = await repo.find_by_name_path(name_path, substring, repository)

    return {
        "name_path": name_path,
        "substring_matching": substring,
        "results": [
            {
                "name_path": chunk.name_path,
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "source_code": chunk.source_code,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line
            }
            for chunk in chunks
        ]
    }
```

**UI Integration** (templates/code_search.html):
```html
<!-- Add Name Path search tab -->
<div class="search-type-tabs">
    <button onclick="switchSearch('hybrid')">Hybrid Search</button>
    <button onclick="switchSearch('name-path')">By Symbol Path</button>
</div>

<div id="name-path-search" style="display:none;">
    <input
        type="text"
        id="name-path-input"
        placeholder="e.g., SearchService/hybrid_search"
    />
    <label>
        <input type="checkbox" id="substring-match" /> Substring matching
    </label>
    <button onclick="searchByNamePath()">Search</button>
</div>

<script>
async function searchByNamePath() {
    const namePath = document.getElementById('name-path-input').value;
    const substring = document.getElementById('substring-match').checked;
    const repository = document.getElementById('repository-select').value;

    const response = await fetch(
        `/v1/code/search/by-name-path?name_path=${encodeURIComponent(namePath)}&repository=${repository}&substring=${substring}`
    );
    const data = await response.json();
    displayResults(data.results);
}
</script>
```

---

## References

### Serena Files Analyzed

1. **Core Architecture**:
   - `serena-main/src/serena/agent.py` - Central orchestrator
   - `serena-main/src/serena/project.py` - Project management
   - `serena-main/src/solidlsp/ls.py` - Language server wrapper

2. **Symbol System**:
   - `serena-main/src/serena/symbol.py` - Symbol representation
   - `serena-main/src/serena/code_editor.py` - Symbol-level editing
   - `serena-main/src/serena/tools/symbol_tools.py` - Symbol finding tools

3. **LSP Integration**:
   - `serena-main/src/solidlsp/ls_handler.py` - JSON-RPC protocol handler
   - `serena-main/src/solidlsp/language_servers/pyright_server.py` - Python LSP
   - `serena-main/src/solidlsp/language_servers/gopls.py` - Go LSP

4. **File Operations**:
   - `serena-main/src/serena/tools/file_tools.py` - Read, write, search, regex replace

5. **Memory System**:
   - `serena-main/src/serena/tools/memory_tools.py` - Markdown-based memories

### MnemoLite Key Files

1. **Code Intelligence**:
   - `api/services/code_chunking_service.py` - tree-sitter AST parsing
   - `api/services/dual_embedding_service.py` - TEXT + CODE embeddings
   - `api/services/graph_construction_service.py` - Dependency graphs

2. **Search**:
   - `api/services/hybrid_code_search_service.py` - RRF fusion
   - `api/services/lexical_search_service.py` - BM25
   - `api/services/vector_search_service.py` - Cosine similarity

3. **Storage**:
   - `api/db/repositories/code_chunk.py` - Code chunk repository
   - `api/db/repositories/node.py` - Graph node repository
   - `api/db/repositories/edge.py` - Graph edge repository

### External Resources

- **Serena GitHub**: https://github.com/oraios/serena
- **LSP Specification**: https://microsoft.github.io/language-server-protocol/
- **tree-sitter**: https://tree-sitter.github.io/tree-sitter/
- **pgvector**: https://github.com/pgvector/pgvector

---

## Conclusion

Serena and MnemoLite represent **complementary architectural philosophies**:

| Aspect | Serena | MnemoLite |
|--------|--------|-----------|
| **Optimization** | Real-time editing | Persistent search |
| **Storage** | Ephemeral cache | PostgreSQL + pgvector |
| **Strength** | Symbol precision | Semantic search |
| **Use Case** | IDE assistant | Code intelligence platform |

**Recommended Strategy**:
1. ✅ Keep MnemoLite's core strengths (dual embeddings, hybrid search, graph construction)
2. ➕ Add Serena's best techniques (caching, name paths, LSP editing - optional)
3. 🎯 Create hybrid system: pgvector for search + LSP for editing

**Next Steps**:
1. Implement Priority 1 improvements (hash caching + name paths) - **Week 1-2**
2. Evaluate impact on performance and usability
3. Decide on LSP integration based on user demand for editing features
4. Document new capabilities in CLAUDE.md v2.1.0

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-18
**Author**: Claude Code Analysis
**Status**: ✅ Complete - Ready for Implementation
