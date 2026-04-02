# EPIC-23 Story 23.7 ULTRATHINK: Configuration & Utilities

**Date**: 2025-10-28
**Story**: 23.7 - Configuration & Utilities (1 pt, ~4h)
**Phase**: Phase 3 - Production & Polish
**Status**: 🔍 **BRAINSTORMING & DESIGN**

---

## Table of Contents

1. [Context Analysis](#context-analysis)
2. [Requirements Analysis](#requirements-analysis)
3. [Architecture Analysis](#architecture-analysis)
4. [Implementation Strategy](#implementation-strategy)
5. [Testing Strategy](#testing-strategy)
6. [Risk Analysis](#risk-analysis)
7. [Decision Log](#decision-log)
8. [Implementation Plan](#implementation-plan)

---

## 1. Context Analysis

### 1.1 Current State (Before Story 23.7)

**Completed Stories** (7/12, 74%):
- ✅ Story 23.1: Project Structure & FastMCP Setup (3 pts)
- ✅ Story 23.2: Code Search Tool (3 pts)
- ✅ Story 23.3: Memory Tools & Resources (2 pts)
- ✅ Story 23.4: Code Graph Resources (3 pts)
- ✅ Story 23.5: Project Indexing Tools (2 pts)
- ✅ Story 23.6: Analytics & Observability (2 pts)
- ✅ Story 23.10: Prompts Library (2 pts)

**Total**: 17/23 story points (Phase 1 + Phase 2 complete)

**Current Capabilities**:
- 8 Tools implemented (ping, write/update/delete_memory, index_project, reindex_file, clear_cache)
- 13 Resources implemented (health, search, memories, graph, indexing status, analytics)
- 6 Prompts implemented (analyze_codebase, refactor_suggestions, find_bugs, generate_tests, explain_code, security_audit)
- PostgreSQL 18 + Redis connectivity
- Service injection pattern working
- 200 tests passing (100% success rate)

### 1.2 What Story 23.7 Adds

**New MCP Components** (2 sub-stories):
1. **Sub-Story 23.7.1**: Project Switcher + List Projects
   - `switch_project` tool (write operation)
   - `projects://list` resource (read operation)

2. **Sub-Story 23.7.2**: Supported Languages
   - `config://languages` resource (read operation)

**Purpose**:
- Allow users to manage multiple projects in MnemoLite
- Switch between projects dynamically (session state)
- List all indexed projects with statistics
- Expose supported programming languages for documentation

**Why This Matters**:
- Multi-project workflows (e.g., compare authentication logic across projects)
- Project discovery (find indexed projects)
- Language discoverability (what can MnemoLite index?)

---

## 2. Requirements Analysis

### 2.1 Sub-Story 23.7.1: Project Switcher Tool + List Projects Resource

#### 2.1.1 Functional Requirements

**FR-23.7.1-1: `switch_project` Tool**
- **Input**: `project_id` (UUID), `confirm` (bool, optional)
- **Output**: `SwitchProjectResponse` (success, project_name, indexed_files, last_indexed)
- **Behavior**:
  - Validate project_id exists in database
  - Store current_project_id in MCP session state (`ctx.session.set()`)
  - Return project details (name, files, chunks, last_indexed)
  - **Elicitation**: Ask confirmation if not bypassed with `confirm=True`

**FR-23.7.1-2: `projects://list` Resource**
- **Input**: None (or Context from session)
- **Output**: `ProjectsListResponse` (list of ProjectInfo, total, active_project_id)
- **Behavior**:
  - Query database for all projects with statistics
  - Aggregate data: indexed_files, total_chunks, languages, last_indexed
  - Mark active project (from session state)
  - Return sorted list (by project name)

**FR-23.7.1-3: Session State Management**
- **Storage**: MCP Context session (`ctx.session.set/get()`)
- **Key**: `"current_project_id"` (string UUID)
- **Scope**: Per-client session (thread-local or connection-specific)
- **Lifetime**: Until session ends or project switched

#### 2.1.2 Non-Functional Requirements

**NFR-23.7.1-1: Performance**
- `switch_project`: <50ms (single DB query + session write)
- `projects://list`: <200ms (single aggregated query)

**NFR-23.7.1-2: Data Consistency**
- Project statistics must reflect current DB state
- Active project marker accurate across tools/resources

**NFR-23.7.1-3: UX**
- Elicitation for switch_project (confirm action)
- Clear messaging on project not found
- `is_active` flag obvious in list

### 2.2 Sub-Story 23.7.2: Supported Languages Resource

#### 2.2.1 Functional Requirements

**FR-23.7.2-1: `config://languages` Resource**
- **Input**: None
- **Output**: `SupportedLanguagesResponse` (list of LanguageInfo, total)
- **Behavior**:
  - Return static list of supported languages
  - Include extensions, tree-sitter grammar, embedding model
  - Languages: Python, JavaScript, TypeScript, Go, Rust, Java, C#, Ruby, PHP, etc.

**FR-23.7.2-2: Language Metadata**
- **LanguageInfo fields**:
  - `name`: Display name (e.g., "Python")
  - `extensions`: File extensions (e.g., [".py", ".pyi"])
  - `tree_sitter_grammar`: Grammar name (e.g., "tree-sitter-python")
  - `embedding_model`: Model used (e.g., "all-MiniLM-L6-v2" or "nomic-embed-text-v1.5")

#### 2.2.2 Non-Functional Requirements

**NFR-23.7.2-1: Completeness**
- Cover 15+ mainstream languages
- Match actual Tree-sitter support in MnemoLite

**NFR-23.7.2-2: Maintainability**
- Easy to add new languages
- Centralized configuration (no hardcoded lists scattered)

---

## 3. Architecture Analysis

### 3.1 Database Schema Analysis

#### 3.1.1 Existing Tables

**`code_chunks` table** (from EPIC-06, migration v1):
```sql
CREATE TABLE code_chunks (
    id UUID PRIMARY KEY,
    file_path TEXT NOT NULL,
    repository TEXT,  -- Project name/identifier
    start_line INTEGER,
    end_line INTEGER,
    content TEXT,
    language TEXT,
    chunk_type TEXT,
    qualified_name TEXT,
    embedding vector(384),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**⚠️ CRITICAL FINDING**:
- **NO `projects` table exists!**
- `repository` field in `code_chunks` is TEXT (project name string)
- **NO `project_id` UUID foreign key!**

**Implication**:
- Cannot query "SELECT * FROM projects" - table doesn't exist
- Must aggregate projects from `code_chunks.repository` DISTINCT values
- Need to handle multiple projects via `repository` string matching

#### 3.1.2 Database Migration Decision

**Option A**: Create `projects` table (recommended)
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    last_indexed TIMESTAMP
);

ALTER TABLE code_chunks
    ADD COLUMN project_id UUID REFERENCES projects(id);

CREATE INDEX idx_code_chunks_project_id ON code_chunks(project_id);
```

**Benefits**:
- Proper relational modeling
- Foreign key constraints
- Can store project metadata (description, settings)
- Future-proof for multi-project features

**Drawbacks**:
- Requires migration v8→v9
- Must migrate existing `repository` TEXT → `project_id` UUID
- ~30-60 min implementation + testing

**Option B**: Use `repository` TEXT as pseudo-project ID (pragmatic)
```python
# No migration needed
# Treat `repository` string as project identifier
# Aggregate stats from code_chunks WHERE repository = ?
```

**Benefits**:
- No migration needed
- Works with existing data
- Fast to implement (<2h)

**Drawbacks**:
- Not normalized (repository name duplication)
- String matching issues (case sensitivity, typos)
- Cannot store project metadata
- Harder to enforce uniqueness

**DECISION**: **Option B (pragmatic approach)** - Use `repository` TEXT
- **Rationale**: Story 23.7 is 1 pt (~4h), creating migration would consume 50% of time
- **Future**: Add `projects` table in EPIC-24 (multi-project refactor)
- **Compromise**: Document limitation in code comments

### 3.2 Session State Architecture

#### 3.2.1 MCP Context Session API

**FastMCP Session Storage** (from MCP 2025-06-18 spec):
```python
# Set session variable
ctx.session.set(key: str, value: Any) -> None

# Get session variable
ctx.session.get(key: str, default: Any = None) -> Any

# Storage: Thread-local or connection-specific
# Lifetime: Until MCP connection closes
```

**Storage Location**:
- **stdio transport** (Claude Desktop): In-memory, per-process
- **HTTP transport** (future Story 23.8): Session token or cookie-based

**Persistence**:
- ❌ Not persisted across restarts
- ❌ Not shared across multiple MCP clients
- ✅ Per-client isolation

**Implication**:
- Each Claude Desktop session has independent `current_project_id`
- Restarting MCP server resets session (back to no active project)
- Multiple clients can have different active projects

#### 3.2.2 Session State Design

**Key**: `"current_project_id"`
**Value**: `str(UUID)` (string representation of project UUID)
**Alternatives**:
- ❌ Integer ID: Not available (no `projects.id`)
- ✅ Repository name (TEXT): Use this for Option B

**Revised Design for Option B**:
- **Key**: `"current_repository"`
- **Value**: `str` (repository name, e.g., "mnemolite")
- **Fallback**: `None` or `"default"` if not set

### 3.3 Reusability Analysis

#### 3.3.1 Services to Inject

**Needed Services**:
1. **SQLAlchemy Engine**: Database queries (aggregation)
2. **Redis** (optional): Not needed for this story
3. **CodeIndexingService** (optional): For language detection logic

**Service Injection Pattern** (from Story 23.1):
```python
class SwitchProjectTool(BaseMCPComponent):
    def inject_services(self, services: dict):
        self._services = services

    @property
    def engine(self):
        return self._services.get("sqlalchemy_engine")
```

#### 3.3.2 Existing Code Reuse

**From EPIC-06 (CodeIndexingService)**:
```python
# api/services/code_indexing_service.py
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    # ... 15+ languages
}
```

**Reuse Strategy**:
- Extract `SUPPORTED_EXTENSIONS` into shared config
- Create `Language` config class in `api/config/languages.py`
- Import in both CodeIndexingService and SupportedLanguagesResource

---

## 4. Implementation Strategy

### 4.1 Sub-Story 23.7.1 Implementation

#### 4.1.1 Pydantic Models

**File**: `api/mnemo_mcp/models/config_models.py` (new file, ~150 lines)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Tool Models
class SwitchProjectRequest(BaseModel):
    """Request to switch active project."""
    repository: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Repository/project name to switch to"
    )
    confirm: bool = Field(
        default=False,
        description="Skip confirmation elicitation if True"
    )

class SwitchProjectResponse(MCPBaseResponse):
    """Response from switch_project tool."""
    repository: str = Field(description="Active repository name")
    indexed_files: int = Field(description="Number of indexed files")
    total_chunks: int = Field(description="Total code chunks")
    languages: List[str] = Field(description="Programming languages found")
    last_indexed: Optional[str] = Field(
        default=None,
        description="Last indexing timestamp (ISO 8601)"
    )

# Resource Models
class ProjectInfo(BaseModel):
    """Information about a single project."""
    repository: str = Field(description="Repository/project name")
    indexed_files: int = Field(description="Number of indexed files")
    total_chunks: int = Field(description="Total code chunks")
    last_indexed: Optional[datetime] = Field(
        default=None,
        description="Last indexing timestamp"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages found"
    )
    is_active: bool = Field(
        default=False,
        description="Whether this is the currently active project"
    )

class ProjectsListResponse(BaseModel):
    """List of all indexed projects."""
    projects: List[ProjectInfo] = Field(description="List of projects")
    total: int = Field(description="Total number of projects")
    active_repository: Optional[str] = Field(
        default=None,
        description="Currently active repository name"
    )
```

#### 4.1.2 `switch_project` Tool

**File**: `api/mnemo_mcp/tools/config_tools.py` (new file, ~200 lines)

```python
from mcp import Context
import structlog
from sqlalchemy import text

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.config_models import (
    SwitchProjectRequest,
    SwitchProjectResponse
)

logger = structlog.get_logger()

class SwitchProjectTool(BaseMCPComponent):
    """Tool to switch the active project context."""

    def get_name(self) -> str:
        return "switch_project"

    def get_description(self) -> str:
        return (
            "Switch the active project/repository for code search and indexing. "
            "Changes the context for all subsequent operations."
        )

    async def execute(
        self,
        ctx: Context,
        request: SwitchProjectRequest
    ) -> SwitchProjectResponse:
        """
        Switch active project.

        Args:
            ctx: MCP context
            request: Switch project request

        Returns:
            SwitchProjectResponse with project details

        Raises:
            ValueError: If repository not found
        """
        logger.info("switch_project.start", repository=request.repository)

        # Elicitation if no explicit confirmation
        if not request.confirm:
            logger.info("switch_project.elicit", repository=request.repository)

            # TODO: Implement elicitation helper (Story 23.11)
            # For now, proceed without elicitation
            pass

        # Query database for project statistics
        engine = self.engine
        if not engine:
            raise ValueError("Database engine not available")

        async with engine.connect() as conn:
            # Aggregate statistics for this repository
            query = text("""
                SELECT
                    repository,
                    COUNT(DISTINCT file_path) as indexed_files,
                    COUNT(*) as total_chunks,
                    MAX(created_at) as last_indexed,
                    ARRAY_AGG(DISTINCT language) FILTER (WHERE language IS NOT NULL) as languages
                FROM code_chunks
                WHERE repository = :repository
                GROUP BY repository
            """)

            result = await conn.execute(query, {"repository": request.repository})
            row = result.fetchone()

            if not row:
                logger.warning(
                    "switch_project.not_found",
                    repository=request.repository
                )
                raise ValueError(
                    f"Repository '{request.repository}' not found or not indexed. "
                    f"Use index_project tool to index it first."
                )

            # Store in session state
            ctx.session.set("current_repository", request.repository)

            logger.info(
                "switch_project.success",
                repository=request.repository,
                indexed_files=row.indexed_files,
                total_chunks=row.total_chunks
            )

            return SwitchProjectResponse(
                success=True,
                message=f"Switched to repository: {request.repository}",
                repository=row.repository,
                indexed_files=row.indexed_files,
                total_chunks=row.total_chunks,
                languages=row.languages or [],
                last_indexed=row.last_indexed.isoformat() if row.last_indexed else None
            )


# Singleton instance for registration
switch_project_tool = SwitchProjectTool()
```

#### 4.1.3 `projects://list` Resource

**File**: `api/mnemo_mcp/resources/config_resources.py` (new file, ~180 lines)

```python
from mcp import Context
import structlog
from sqlalchemy import text

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.config_models import (
    ProjectInfo,
    ProjectsListResponse
)

logger = structlog.get_logger()

class ListProjectsResource(BaseMCPComponent):
    """Resource to list all indexed projects."""

    def get_name(self) -> str:
        return "projects://list"

    def get_description(self) -> str:
        return (
            "List all indexed projects with statistics "
            "(files, chunks, languages, last indexed)."
        )

    async def get(self, ctx: Context) -> ProjectsListResponse:
        """
        List all projects.

        Args:
            ctx: MCP context

        Returns:
            ProjectsListResponse with project list
        """
        logger.info("list_projects.start")

        # Get active repository from session
        active_repository = ctx.session.get("current_repository")
        logger.debug("list_projects.active", repository=active_repository)

        # Query database
        engine = self.engine
        if not engine:
            logger.error("list_projects.no_engine")
            return ProjectsListResponse(
                projects=[],
                total=0,
                active_repository=active_repository
            )

        async with engine.connect() as conn:
            query = text("""
                SELECT
                    repository,
                    COUNT(DISTINCT file_path) as indexed_files,
                    COUNT(*) as total_chunks,
                    MAX(created_at) as last_indexed,
                    ARRAY_AGG(DISTINCT language) FILTER (WHERE language IS NOT NULL) as languages
                FROM code_chunks
                GROUP BY repository
                ORDER BY repository ASC
            """)

            result = await conn.execute(query)
            rows = result.fetchall()

            projects = [
                ProjectInfo(
                    repository=row.repository,
                    indexed_files=row.indexed_files,
                    total_chunks=row.total_chunks,
                    last_indexed=row.last_indexed,
                    languages=row.languages or [],
                    is_active=(row.repository == active_repository)
                )
                for row in rows
            ]

            logger.info("list_projects.success", total=len(projects))

            return ProjectsListResponse(
                projects=projects,
                total=len(projects),
                active_repository=active_repository
            )


# Singleton instance for registration
list_projects_resource = ListProjectsResource()
```

### 4.2 Sub-Story 23.7.2 Implementation

#### 4.2.1 Shared Language Configuration

**File**: `api/config/languages.py` (new file, ~250 lines)

```python
from dataclasses import dataclass
from typing import List

@dataclass
class LanguageConfig:
    """Configuration for a supported programming language."""
    name: str
    extensions: List[str]
    tree_sitter_grammar: str
    embedding_model: str = "nomic-embed-text-v1.5"  # Default

# Supported languages configuration
SUPPORTED_LANGUAGES = [
    LanguageConfig(
        name="Python",
        extensions=[".py", ".pyi"],
        tree_sitter_grammar="tree-sitter-python",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="JavaScript",
        extensions=[".js", ".jsx", ".mjs", ".cjs"],
        tree_sitter_grammar="tree-sitter-javascript",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="TypeScript",
        extensions=[".ts", ".tsx", ".d.ts"],
        tree_sitter_grammar="tree-sitter-typescript",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Go",
        extensions=[".go"],
        tree_sitter_grammar="tree-sitter-go",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Rust",
        extensions=[".rs"],
        tree_sitter_grammar="tree-sitter-rust",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Java",
        extensions=[".java"],
        tree_sitter_grammar="tree-sitter-java",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="C#",
        extensions=[".cs", ".csx"],
        tree_sitter_grammar="tree-sitter-c-sharp",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Ruby",
        extensions=[".rb", ".rake"],
        tree_sitter_grammar="tree-sitter-ruby",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="PHP",
        extensions=[".php", ".php5", ".phtml"],
        tree_sitter_grammar="tree-sitter-php",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="C",
        extensions=[".c", ".h"],
        tree_sitter_grammar="tree-sitter-c",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="C++",
        extensions=[".cpp", ".hpp", ".cc", ".hh", ".cxx"],
        tree_sitter_grammar="tree-sitter-cpp",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Swift",
        extensions=[".swift"],
        tree_sitter_grammar="tree-sitter-swift",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Kotlin",
        extensions=[".kt", ".kts"],
        tree_sitter_grammar="tree-sitter-kotlin",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Scala",
        extensions=[".scala", ".sc"],
        tree_sitter_grammar="tree-sitter-scala",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Bash",
        extensions=[".sh", ".bash"],
        tree_sitter_grammar="tree-sitter-bash",
        embedding_model="nomic-embed-text-v1.5"
    ),
]

# Extension to language mapping (for quick lookup)
EXTENSION_TO_LANGUAGE = {
    ext: lang.name
    for lang in SUPPORTED_LANGUAGES
    for ext in lang.extensions
}
```

#### 4.2.2 `config://languages` Resource

**File**: `api/mnemo_mcp/resources/config_resources.py` (add to existing file)

```python
from mnemo_mcp.models.config_models import (
    LanguageInfo,
    SupportedLanguagesResponse
)
from config.languages import SUPPORTED_LANGUAGES

class SupportedLanguagesResource(BaseMCPComponent):
    """Resource exposing supported programming languages."""

    def get_name(self) -> str:
        return "config://languages"

    def get_description(self) -> str:
        return (
            "Get list of programming languages supported by MnemoLite, "
            "including file extensions and Tree-sitter grammars."
        )

    async def get(self, ctx: Context) -> SupportedLanguagesResponse:
        """
        Get supported languages.

        Args:
            ctx: MCP context

        Returns:
            SupportedLanguagesResponse with language list
        """
        logger.info("supported_languages.start")

        languages = [
            LanguageInfo(
                name=lang.name,
                extensions=lang.extensions,
                tree_sitter_grammar=lang.tree_sitter_grammar,
                embedding_model=lang.embedding_model
            )
            for lang in SUPPORTED_LANGUAGES
        ]

        logger.info("supported_languages.success", total=len(languages))

        return SupportedLanguagesResponse(
            languages=languages,
            total=len(languages)
        )


# Singleton instance
supported_languages_resource = SupportedLanguagesResource()
```

#### 4.2.3 Pydantic Models for Languages

**File**: `api/mnemo_mcp/models/config_models.py` (add to existing file)

```python
class LanguageInfo(BaseModel):
    """Information about a supported programming language."""
    name: str = Field(description="Language display name")
    extensions: List[str] = Field(description="File extensions (e.g., ['.py', '.pyi'])")
    tree_sitter_grammar: str = Field(description="Tree-sitter grammar name")
    embedding_model: str = Field(
        default="nomic-embed-text-v1.5",
        description="Embedding model used for this language"
    )

class SupportedLanguagesResponse(BaseModel):
    """List of supported programming languages."""
    languages: List[LanguageInfo] = Field(description="List of languages")
    total: int = Field(description="Total number of supported languages")
```

### 4.3 Server Registration

**File**: `api/mnemo_mcp/server.py` (modifications)

```python
# Add imports
from mnemo_mcp.tools.config_tools import switch_project_tool
from mnemo_mcp.resources.config_resources import (
    list_projects_resource,
    supported_languages_resource
)

# In setup_mcp_server() function
def setup_mcp_server(mcp: FastMCP) -> FastMCP:
    """Setup MCP server with all components."""

    # ... existing tool/resource registrations ...

    # Story 23.7: Configuration & Utilities
    mcp.tool()(switch_project_tool.execute)
    mcp.resource(list_projects_resource.get_name())(list_projects_resource.get)
    mcp.resource(supported_languages_resource.get_name())(supported_languages_resource.get)

    logger.info("mcp.server.registered",
                tools=["switch_project"],
                resources=["projects://list", "config://languages"])

    return mcp
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

#### 5.1.1 Test `switch_project` Tool

**File**: `tests/mnemo_mcp/test_config_tools.py` (new file, ~250 lines)

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from mnemo_mcp.tools.config_tools import SwitchProjectTool
from mnemo_mcp.models.config_models import SwitchProjectRequest

@pytest.mark.asyncio
async def test_switch_project_success():
    """Test switching to existing project."""
    tool = SwitchProjectTool()

    # Mock engine
    mock_engine = MagicMock()
    mock_conn = AsyncMock()

    # Mock fetchone() result
    mock_row = MagicMock()
    mock_row.repository = "test-repo"
    mock_row.indexed_files = 42
    mock_row.total_chunks = 234
    mock_row.languages = ["python", "javascript"]
    mock_row.last_indexed = datetime(2025, 1, 15, 12, 0, 0)

    mock_result = AsyncMock()
    mock_result.fetchone.return_value = mock_row

    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    tool.inject_services({"sqlalchemy_engine": mock_engine})

    # Mock context
    ctx = MagicMock()
    ctx.session.set = MagicMock()

    # Execute
    response = await tool.execute(
        ctx,
        SwitchProjectRequest(repository="test-repo", confirm=True)
    )

    # Assertions
    assert response.success is True
    assert response.repository == "test-repo"
    assert response.indexed_files == 42
    assert response.total_chunks == 234
    assert "python" in response.languages

    # Verify session updated
    ctx.session.set.assert_called_once_with("current_repository", "test-repo")

@pytest.mark.asyncio
async def test_switch_project_not_found():
    """Test switching to non-existent project raises error."""
    tool = SwitchProjectTool()

    # Mock engine returning no results
    mock_engine = MagicMock()
    mock_conn = AsyncMock()

    mock_result = AsyncMock()
    mock_result.fetchone.return_value = None  # Not found

    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    tool.inject_services({"sqlalchemy_engine": mock_engine})

    ctx = MagicMock()

    # Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        await tool.execute(
            ctx,
            SwitchProjectRequest(repository="nonexistent", confirm=True)
        )

    assert "not found" in str(exc_info.value).lower()
```

#### 5.1.2 Test `projects://list` Resource

**File**: `tests/mnemo_mcp/test_config_resources.py` (new file, ~200 lines)

```python
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from mnemo_mcp.resources.config_resources import ListProjectsResource

@pytest.mark.asyncio
async def test_list_projects():
    """Test listing all projects."""
    resource = ListProjectsResource()

    # Mock engine
    mock_engine = MagicMock()
    mock_conn = AsyncMock()

    # Mock fetchall() results
    mock_row1 = MagicMock()
    mock_row1.repository = "project-a"
    mock_row1.indexed_files = 10
    mock_row1.total_chunks = 100
    mock_row1.languages = ["python"]
    mock_row1.last_indexed = datetime(2025, 1, 15, 10, 0, 0)

    mock_row2 = MagicMock()
    mock_row2.repository = "project-b"
    mock_row2.indexed_files = 20
    mock_row2.total_chunks = 200
    mock_row2.languages = ["javascript", "typescript"]
    mock_row2.last_indexed = datetime(2025, 1, 16, 12, 0, 0)

    mock_result = AsyncMock()
    mock_result.fetchall.return_value = [mock_row1, mock_row2]

    mock_conn.execute = AsyncMock(return_value=mock_result)
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    resource.inject_services({"sqlalchemy_engine": mock_engine})

    # Mock context
    ctx = MagicMock()
    ctx.session.get.return_value = "project-a"  # Active project

    # Execute
    response = await resource.get(ctx)

    # Assertions
    assert response.total == 2
    assert len(response.projects) == 2

    # Check project details
    project_a = next(p for p in response.projects if p.repository == "project-a")
    assert project_a.indexed_files == 10
    assert project_a.is_active is True

    project_b = next(p for p in response.projects if p.repository == "project-b")
    assert project_b.indexed_files == 20
    assert project_b.is_active is False

    # Check active repository
    assert response.active_repository == "project-a"
```

#### 5.1.3 Test `config://languages` Resource

**File**: `tests/mnemo_mcp/test_config_resources.py` (add to existing)

```python
@pytest.mark.asyncio
async def test_supported_languages():
    """Test getting supported languages."""
    resource = SupportedLanguagesResource()
    resource.inject_services({})  # No services needed

    ctx = MagicMock()
    response = await resource.get(ctx)

    # Assertions
    assert response.total > 10  # At least 10 languages
    assert len(response.languages) == response.total

    # Check Python is present
    python = next((l for l in response.languages if l.name == "Python"), None)
    assert python is not None
    assert ".py" in python.extensions
    assert python.tree_sitter_grammar == "tree-sitter-python"
    assert python.embedding_model == "nomic-embed-text-v1.5"

    # Check JavaScript
    javascript = next((l for l in response.languages if l.name == "JavaScript"), None)
    assert javascript is not None
    assert ".js" in javascript.extensions
```

### 5.2 Integration Tests

**File**: `tests/mnemo_mcp/integration/test_config_integration.py` (new file)

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_switch_project_and_list(test_db, mcp_server):
    """Test switching project and listing projects end-to-end."""
    # 1. List projects (initially none or existing)
    list_response = await mcp_server.call_resource("projects://list")
    initial_count = list_response["total"]

    # 2. Index a test project (creates repository in DB)
    await mcp_server.call_tool(
        "index_project",
        {"project_path": "/tmp/test-project", "repository": "test-repo-integration"}
    )

    # 3. List projects again (should have +1)
    list_response = await mcp_server.call_resource("projects://list")
    assert list_response["total"] == initial_count + 1

    # 4. Switch to test project
    switch_response = await mcp_server.call_tool(
        "switch_project",
        {"repository": "test-repo-integration", "confirm": True}
    )
    assert switch_response["success"] is True

    # 5. List projects (test-repo should be active)
    list_response = await mcp_server.call_resource("projects://list")
    active_project = next(
        p for p in list_response["projects"]
        if p["repository"] == "test-repo-integration"
    )
    assert active_project["is_active"] is True
```

### 5.3 Test Coverage Target

**Target**: >80% line coverage
- Unit tests: 100% of logic paths
- Integration tests: End-to-end workflows
- Edge cases: Empty DB, invalid repository, no session

---

## 6. Risk Analysis

### 6.1 Technical Risks

**RISK-23.7-1: Session State Persistence** (HIGH)
- **Issue**: MCP session state not persisted across restarts
- **Impact**: Users lose active project on server restart
- **Mitigation**:
  - Document limitation in user guide
  - Consider Redis-backed session in Story 23.8 (HTTP transport)
  - Default to last-used project on startup (optional)

**RISK-23.7-2: No `projects` Table** (MEDIUM)
- **Issue**: Using `repository` TEXT instead of normalized `projects` table
- **Impact**:
  - Cannot store project metadata (description, settings)
  - String matching issues (case sensitivity, typos)
- **Mitigation**:
  - Document limitation in code comments
  - Add TODO for EPIC-24 (multi-project refactor)
  - Use TRIM() and LOWER() for case-insensitive matching

**RISK-23.7-3: Thread Safety** (LOW)
- **Issue**: `ctx.session.set()` thread-local behavior unclear
- **Impact**: Concurrent requests might have race conditions
- **Mitigation**:
  - FastMCP SDK handles thread safety (trusted)
  - Add logging to detect race conditions in production

### 6.2 UX Risks

**RISK-23.7-4: Elicitation Bypass** (LOW)
- **Issue**: `switch_project` should ask confirmation (Story 23.7.1), but elicitation helpers not implemented until Story 23.11
- **Impact**: Users might switch projects accidentally
- **Mitigation**:
  - Skip elicitation for Story 23.7 (accept risk)
  - Add TODO comment to implement in Story 23.11
  - Document `confirm=True` bypass in API reference

**RISK-23.7-5: Language List Completeness** (LOW)
- **Issue**: Hardcoded 15 languages, might miss new grammars
- **Impact**: Users assume MnemoLite doesn't support their language
- **Mitigation**:
  - Review Tree-sitter grammars list (https://tree-sitter.github.io/tree-sitter/)
  - Add comment to update list when adding new languages
  - Version SUPPORTED_LANGUAGES config

---

## 7. Decision Log

### Decision 7.1: Use `repository` TEXT Instead of `projects` Table

**Context**: Database schema doesn't have `projects` table, only `repository` TEXT in `code_chunks`.

**Options**:
1. Create `projects` table (normalized, ~1-2h migration)
2. Use `repository` TEXT as pseudo-project ID (pragmatic, no migration)

**Decision**: **Option 2 - Use `repository` TEXT**

**Rationale**:
- Story 23.7 is only 1 pt (~4h total)
- Creating migration + testing would consume 50% of time
- Existing codebase already uses `repository` TEXT
- Can refactor to proper table in EPIC-24

**Trade-offs**:
- ❌ Not normalized (duplication)
- ❌ Cannot store project metadata
- ✅ Fast to implement
- ✅ Works with existing data
- ✅ No migration risk

**Documentation**: Add TODO comments in code

### Decision 7.2: Skip Elicitation for Now

**Context**: Story 23.7.1 specifies elicitation for `switch_project`, but elicitation helpers are Story 23.11.

**Options**:
1. Implement basic elicitation now (duplicate code)
2. Skip elicitation until Story 23.11 (accept UX gap)
3. Block Story 23.7 on Story 23.11 (delays progress)

**Decision**: **Option 2 - Skip elicitation for now**

**Rationale**:
- Elicitation is non-critical for MVP
- Adding `confirm=True` parameter allows bypass
- Story 23.11 will add helpers (~2h)
- Can refactor in Story 23.11 with proper patterns

**Trade-offs**:
- ❌ Users might switch accidentally (low risk)
- ✅ Faster implementation
- ✅ Cleaner code with proper helpers later

**Documentation**: Add TODO comment + issue

### Decision 7.3: Centralize Language Configuration

**Context**: Language list scattered across CodeIndexingService, need single source of truth.

**Options**:
1. Keep in CodeIndexingService (status quo)
2. Create `api/config/languages.py` (centralized)
3. Load from database (over-engineered)

**Decision**: **Option 2 - Create `api/config/languages.py`**

**Rationale**:
- Single source of truth
- Easy to maintain and extend
- Reusable across services
- Type-safe with dataclass

**Trade-offs**:
- ✅ Centralized configuration
- ✅ Easy to add languages
- ⚠️ Need to refactor CodeIndexingService (separate commit)

**Implementation**: Create `config/languages.py` with `SUPPORTED_LANGUAGES` list

---

## 8. Implementation Plan

### 8.1 Task Breakdown

**Sub-Story 23.7.1: Project Switcher + List Projects** (2.5h)

1. **Create Pydantic Models** (30 min)
   - `config_models.py`: SwitchProjectRequest, SwitchProjectResponse, ProjectInfo, ProjectsListResponse
   - Add to `models/__init__.py` exports

2. **Implement `switch_project` Tool** (60 min)
   - `config_tools.py`: SwitchProjectTool class
   - Database query for project statistics
   - Session state management (`ctx.session.set()`)
   - Error handling (repository not found)

3. **Implement `projects://list` Resource** (45 min)
   - `config_resources.py`: ListProjectsResource class
   - Database aggregation query
   - Mark active project (from session)
   - Sort by repository name

4. **Unit Tests** (45 min)
   - `test_config_tools.py`: 5 tests (success, not found, session state, no engine, empty DB)
   - `test_config_resources.py`: 4 tests (list projects, active marker, no session, no engine)

**Sub-Story 23.7.2: Supported Languages** (1.5h)

5. **Create Language Configuration** (30 min)
   - `config/languages.py`: LanguageConfig dataclass, SUPPORTED_LANGUAGES list (15 languages)
   - Extension to language mapping

6. **Implement `config://languages` Resource** (30 min)
   - `config_resources.py`: SupportedLanguagesResource class
   - Convert SUPPORTED_LANGUAGES to LanguageInfo Pydantic models
   - Return structured response

7. **Unit Tests** (30 min)
   - `test_config_resources.py`: 3 tests (supported languages, Python present, metadata correct)

**Integration & Registration** (30 min)

8. **Server Registration** (15 min)
   - `server.py`: Register switch_project tool, projects://list resource, config://languages resource
   - Update lifespan to inject services

9. **Integration Test** (15 min)
   - `test_config_integration.py`: End-to-end test (switch + list)

### 8.2 Timeline

**Total Estimate**: 4h (matches story points: 1 pt = ~4h)

**Day 1 Session 1** (2h):
- Sub-Story 23.7.1 complete (models + tools + tests)

**Day 1 Session 2** (2h):
- Sub-Story 23.7.2 complete (languages + tests)
- Integration + registration

### 8.3 Validation Checklist

- [ ] `switch_project` tool registered in MCP server
- [ ] `projects://list` resource registered
- [ ] `config://languages` resource registered
- [ ] Session state persists across tool/resource calls (same session)
- [ ] Active project marked correctly in list
- [ ] All 12+ unit tests passing
- [ ] Integration test passing
- [ ] Manual test in MCP Inspector

---

## 9. Future Enhancements (Out of Scope)

**EPIC-24: Multi-Project Features**
- Create `projects` table (normalized schema)
- Migrate `repository` TEXT → `project_id` UUID foreign key
- Add project metadata (description, settings, created_at)
- Default active project on server startup (last-used or config)

**Story 23.11: Elicitation Helpers**
- Implement `request_confirmation()` helper
- Add elicitation to `switch_project` tool
- Document elicitation patterns

**Story 23.8: HTTP Transport**
- Redis-backed session state (cross-client persistence)
- Session token authentication
- SSE progress stream for long operations

---

## 10. Summary

**Story 23.7** adds multi-project management to MnemoLite MCP:

**Key Deliverables**:
- ✅ `switch_project` tool (change active project context)
- ✅ `projects://list` resource (discover indexed projects)
- ✅ `config://languages` resource (supported languages documentation)
- ✅ Session state management (per-client active project)
- ✅ Centralized language configuration

**Pragmatic Decisions**:
- Use `repository` TEXT instead of `projects` table (faster, refactor later)
- Skip elicitation for now (Story 23.11 will add helpers)
- Centralize language config in `config/languages.py`

**Testing**:
- 12+ unit tests (tools + resources)
- 1 integration test (end-to-end workflow)
- Target: >80% coverage

**Timeline**: 4 hours (1 story point)

**Next Story**: 23.8 - HTTP Transport Support (2 pts, ~8h)

---

**Document Version**: 1.0.0
**Status**: ✅ **READY FOR IMPLEMENTATION**
**Approval**: Awaiting user confirmation to proceed
