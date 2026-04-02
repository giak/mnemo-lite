# EPIC-23 MCP Integration - ULTRA-DÉCOUPAGE STORIES

**Date**: 2025-10-24
**Objectif**: Découpage granulaire maximum pour faciliter implémentation
**Principe**: 1 story = multiple sub-stories de 0.5 pt chacune

---

## 📐 Méthodologie de Découpage

### Critères de Granularité
- ✅ **1 sub-story = 1-3 heures max** de développement
- ✅ **1 sub-story = 1-3 fichiers** max touchés
- ✅ **1 sub-story = testable indépendamment**
- ✅ **Dépendances explicites** entre sub-stories
- ✅ **Checkpoints de validation** après chaque sub-story

### Format Sub-Story
```
Story X.Y: Nom Court (0.5 pt)
├── Objectif: 1 phrase claire
├── Fichiers: Liste exacte
├── Dépendances: Stories précédentes requises
├── Inputs: Ce qui doit exister avant
├── Outputs: Ce qui sera créé
├── Tests: Comment valider
├── Pièges: Points d'attention
└── Temps estimé: X heures
```

---

## 🎯 PHASE 1: FOUNDATION (8 pts → 16 sub-stories)

### STORY 23.1: MCP Server Bootstrap (3 pts → 6 sub-stories)

#### Sub-Story 23.1.1: Projet Structure & Dependencies (0.5 pt)

**Objectif**: Créer structure `api/mcp/` et installer dépendances

**Fichiers à créer**:
```
api/mcp/
├── __init__.py           # Module initialization
├── server.py             # FastMCP server (placeholder)
├── cli.py                # CLI entrypoint (placeholder)
├── models.py             # Pydantic models base (placeholder)
├── context.py            # MCP context (placeholder)
└── tools/
    ├── __init__.py
    └── base.py           # BaseMCPTool class
```

**Dépendances pyproject.toml**:
```toml
# Ajouter à api/pyproject.toml (ou créer nouveau)
[project]
dependencies = [
    # Existing deps...
    "mcp[cli]==1.12.3",           # MCP SDK + FastMCP + Inspector
    "docstring-parser>=0.16",      # Parse docstrings
    "pydantic>=2.10.6",            # Structured output (déjà présent?)
]

[project.scripts]
mnemolite-mcp-server = "mcp.cli:start_mcp_server"
```

**Tests**:
```bash
# Vérifier imports
cd api/mcp && python3 -c "from mcp.server.fastmcp import FastMCP; print('OK')"

# Vérifier structure
tree api/mcp/
```

**Pièges**:
- ⚠️ Conflit versions Pydantic avec existant (vérifier requirements.txt)
- ⚠️ MCP SDK nécessite Python >=3.11 (vérifier version projet)
- ⚠️ FastMCP inclus dans `mcp[cli]` (pas package séparé)

**Temps estimé**: 1h

---

#### Sub-Story 23.1.2: BaseMCPTool & Base Models (0.5 pt)

**Objectif**: Créer classes de base réutilisables

**Fichier**: `api/mcp/tools/base.py`

**Contenu**:
```python
"""
Base classes for MnemoLite MCP tools, resources, and prompts.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field
from mcp.server.fastmcp import Context


# ========== Base Response Models ==========

class MCPBaseResponse(BaseModel):
    """Base response model for all MCP interactions."""
    success: bool = True
    message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MCPErrorResponse(MCPBaseResponse):
    """Error response model."""
    success: bool = False
    error_code: Optional[str] = None
    error_details: Optional[dict] = None


# ========== Markers (Serena-inspired) ==========

class MCPToolMarker:
    """Base marker for MCP interactions."""
    pass


class MCPWriteOperation(MCPToolMarker):
    """Marker for write operations (Tools)."""
    pass


class MCPReadOperation(MCPToolMarker):
    """Marker for read operations (Resources)."""
    pass


class MCPUserTemplate(MCPToolMarker):
    """Marker for user templates (Prompts)."""
    pass


# ========== Base Component ==========

class BaseMCPComponent(ABC):
    """
    Base class for all MCP components (tools, resources, prompts).
    Provides access to MnemoLite services.
    """

    def __init__(self):
        """Initialize component."""
        self._services = None  # Will be injected

    def inject_services(self, services: dict[str, Any]) -> None:
        """
        Inject MnemoLite services (dependency injection).

        Args:
            services: Dict with keys like 'search_service', 'db_engine', etc.
        """
        self._services = services

    @property
    def services(self) -> dict[str, Any]:
        """Get injected services."""
        if self._services is None:
            raise RuntimeError("Services not injected. Call inject_services() first.")
        return self._services

    @abstractmethod
    def get_name(self) -> str:
        """Get component name (for registration)."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get component description (for LLM)."""
        pass


# ========== Utility Functions ==========

def validate_context(ctx: Optional[Context]) -> Context:
    """Validate MCP context is provided."""
    if ctx is None:
        raise ValueError("MCP Context required but not provided")
    return ctx


def create_error_response(
    message: str,
    error_code: Optional[str] = None,
    error_details: Optional[dict] = None
) -> MCPErrorResponse:
    """Create standardized error response."""
    return MCPErrorResponse(
        message=message,
        error_code=error_code or "UNKNOWN_ERROR",
        error_details=error_details or {}
    )
```

**Tests**:
```python
# tests/mcp/test_base.py
def test_base_response_creation():
    resp = MCPBaseResponse(success=True, message="Test")
    assert resp.success is True

def test_error_response():
    err = create_error_response("Test error", "TEST_ERR")
    assert err.success is False
    assert err.error_code == "TEST_ERR"

def test_component_requires_services():
    comp = BaseMCPComponent()
    with pytest.raises(RuntimeError):
        _ = comp.services  # Should fail before injection
```

**Pièges**:
- ⚠️ Services injection doit être thread-safe (asyncio)
- ⚠️ Pydantic v2 syntax (Field, BaseModel)
- ⚠️ Context peut être None (gérer gracieusement)

**Temps estimé**: 2h

---

#### Sub-Story 23.1.3: FastMCP Server Initialization (0.5 pt)

**Objectif**: Créer serveur FastMCP minimal fonctionnel

**Fichier**: `api/mcp/server.py`

**Contenu**:
```python
"""
MnemoLite MCP Server using FastMCP.
"""
import os
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP, Context
import structlog

from api.mcp.context import MCPServerContext

logger = structlog.get_logger(__name__)


# ========== Server Configuration ==========

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8002"))
MCP_NAME = "mnemolite"
MCP_VERSION = "0.1.0"


# ========== Lifespan Management ==========

@asynccontextmanager
async def mcp_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """
    Manage MCP server startup and shutdown.

    Startup:
    - Initialize database connections
    - Load services (search, embeddings, etc.)
    - Register tools/resources/prompts

    Shutdown:
    - Close database connections
    - Cleanup resources
    """
    logger.info("🚀 MnemoLite MCP Server starting...",
                name=MCP_NAME, version=MCP_VERSION)

    # TODO: Initialize MnemoLite services
    # server_context = MCPServerContext()
    # await server_context.initialize()

    logger.info("✅ MnemoLite MCP Server ready")

    try:
        yield  # Server runs here
    finally:
        logger.info("🛑 MnemoLite MCP Server shutting down...")

        # TODO: Cleanup
        # await server_context.cleanup()

        logger.info("✅ MnemoLite MCP Server stopped")


# ========== Server Instance ==========

def create_mcp_server() -> FastMCP:
    """
    Create and configure FastMCP server instance.

    Returns:
        Configured FastMCP server
    """

    instructions = """
MnemoLite MCP Server - Code Intelligence & Memory

Provides semantic code search, project memory, and code graph navigation.

Available interactions:
- Tools: Write operations (index, write memory, etc.)
- Resources: Read operations (search, get status, etc.)
- Prompts: User templates (analyze, refactor, etc.)

Use 'list tools', 'list resources', 'list prompts' to explore.
    """.strip()

    mcp = FastMCP(
        name=MCP_NAME,
        version=MCP_VERSION,
        lifespan=mcp_lifespan,
        host=MCP_HOST,
        port=MCP_PORT,
        instructions=instructions
    )

    # TODO: Register tools/resources/prompts
    # register_tools(mcp)
    # register_resources(mcp)
    # register_prompts(mcp)

    return mcp


# ========== Main Entry Point ==========

def start_server(host: str = MCP_HOST, port: int = MCP_PORT) -> None:
    """
    Start MnemoLite MCP server (blocking).

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    mcp = create_mcp_server()

    logger.info("Starting MCP server", host=host, port=port, name=MCP_NAME)

    # FastMCP handles asyncio event loop
    mcp.run(transport="stdio")  # Default: stdio for Claude Desktop


if __name__ == "__main__":
    start_server()
```

**Tests**:
```python
# tests/mcp/test_server.py
def test_create_mcp_server():
    """Test server creation."""
    mcp = create_mcp_server()
    assert mcp.name == "mnemolite"
    assert mcp.version == "0.1.0"

async def test_lifespan_startup_shutdown():
    """Test lifespan hooks."""
    mcp = create_mcp_server()
    async with mcp_lifespan(mcp):
        # Server running
        pass
    # Server stopped (should not crash)
```

**Pièges**:
- ⚠️ `mcp.run()` bloque le thread (gère son propre event loop)
- ⚠️ stdio transport pour Claude Desktop (pas HTTP par défaut)
- ⚠️ Lifespan doit être async context manager
- ⚠️ Ne pas initialiser services lourds dans `__init__` (faire dans lifespan)

**Temps estimé**: 2h

---

#### Sub-Story 23.1.4: CLI Entrypoint (0.5 pt)

**Objectif**: Créer CLI pour lancer le serveur MCP

**Fichier**: `api/mcp/cli.py`

**Contenu**:
```python
"""
CLI entrypoint for MnemoLite MCP Server.
"""
import os
import sys
import click
import structlog

from api.mcp.server import start_server, MCP_HOST, MCP_PORT

logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="mnemolite-mcp-server")
def cli():
    """MnemoLite MCP Server - Code Intelligence via Model Context Protocol."""
    pass


@cli.command()
@click.option("--host", default=MCP_HOST, help="Host to bind to")
@click.option("--port", default=MCP_PORT, type=int, help="Port to bind to")
@click.option("--transport", type=click.Choice(["stdio", "http"]), default="stdio",
              help="Transport layer (stdio for Claude Desktop, http for web)")
@click.option("--project", type=click.Path(exists=True),
              help="Project directory to index")
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
              default="INFO", help="Log level")
def start(host: str, port: int, transport: str, project: str | None, log_level: str):
    """
    Start MnemoLite MCP server.

    Examples:
        # Start for Claude Desktop (stdio)
        $ mnemolite-mcp-server start --project /path/to/project

        # Start HTTP server
        $ mnemolite-mcp-server start --transport http --port 8002
    """

    # Configure logging
    log_level_int = getattr(structlog, log_level)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int)
    )

    logger.info("Starting MnemoLite MCP Server",
                transport=transport, host=host, port=port, project=project)

    # Set environment variables (for server.py)
    if project:
        os.environ["MNEMOLITE_PROJECT_PATH"] = project
    os.environ["MCP_TRANSPORT"] = transport

    try:
        start_server(host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error("Server crashed", error=str(e), exc_info=True)
        sys.exit(1)


@cli.command()
def dev():
    """
    Start MCP server in development mode with Inspector.

    Launches MCP Inspector web UI at http://127.0.0.1:6274
    """
    import subprocess

    logger.info("Starting MCP server in development mode with Inspector...")

    try:
        # Use mcp CLI to launch with Inspector
        subprocess.run([
            "uv", "run", "mcp", "dev", "api/mcp/server.py"
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to start dev mode", error=str(e))
        sys.exit(1)


@cli.command()
def install():
    """
    Install MnemoLite MCP server to Claude Desktop.

    Updates ~/.config/claude/claude_desktop_config.json
    """
    import json
    from pathlib import Path

    config_path = Path.home() / ".config" / "claude" / "claude_desktop_config.json"

    if not config_path.parent.exists():
        logger.error("Claude Desktop not found. Install Claude Desktop first.")
        sys.exit(1)

    # Read existing config
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {"mcpServers": {}}

    # Add mnemolite server
    config.setdefault("mcpServers", {})
    config["mcpServers"]["mnemolite"] = {
        "command": "uv",
        "args": ["run", "mnemolite-mcp-server", "start", "--project", str(Path.cwd())]
    }

    # Write updated config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    logger.info("✅ MnemoLite MCP server installed to Claude Desktop",
                config=str(config_path))
    logger.info("Restart Claude Desktop to activate.")


def start_mcp_server():
    """Entry point for pyproject.toml script."""
    cli()


if __name__ == "__main__":
    cli()
```

**Tests**:
```bash
# Test CLI help
mnemolite-mcp-server --help

# Test start command (should fail gracefully sans DB)
mnemolite-mcp-server start --help

# Test dev command
mnemolite-mcp-server dev

# Test install (dry-run)
mnemolite-mcp-server install
```

**Pièges**:
- ⚠️ Click options vs environment variables (ordre précédence)
- ⚠️ `uv run` nécessite pyproject.toml configuré
- ⚠️ Install command modifie config utilisateur (demander confirmation?)
- ⚠️ Paths absolus dans claude_desktop_config.json

**Temps estimé**: 2h

---

#### Sub-Story 23.1.5: Test Tool "ping" + Health Resource (0.5 pt)

**Objectif**: Premier tool + resource fonctionnels pour validation

**Fichier**: `api/mcp/tools/test_tools.py`

**Contenu**:
```python
"""
Test tools and resources for MCP server validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from mcp.server.fastmcp import Context
from api.mcp.tools.base import BaseMCPComponent, MCPBaseResponse, MCPWriteOperation, MCPReadOperation


# ========== Response Models ==========

class PingResponse(MCPBaseResponse):
    """Response from ping tool."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = "pong"
    latency_ms: float = 0.0


class HealthStatus(MCPBaseResponse):
    """Health status resource."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: dict[str, bool] = Field(default_factory=dict)
    version: str = "0.1.0"


# ========== Tool: ping ==========

class PingTool(BaseMCPComponent, MCPWriteOperation):
    """Test tool to verify MCP server is responsive."""

    def get_name(self) -> str:
        return "ping"

    def get_description(self) -> str:
        return "Test MCP server connectivity. Returns 'pong' with timestamp."

    async def execute(self, ctx: Optional[Context] = None) -> PingResponse:
        """
        Ping the MCP server.

        Args:
            ctx: MCP context (optional for this tool)

        Returns:
            PingResponse with timestamp
        """
        import time
        start = time.time()

        # Simulate minimal work
        await asyncio.sleep(0.001)

        latency_ms = (time.time() - start) * 1000

        return PingResponse(
            message="pong",
            latency_ms=round(latency_ms, 2)
        )


# ========== Resource: health status ==========

class HealthResource(BaseMCPComponent, MCPReadOperation):
    """Health status resource (read-only)."""

    def get_name(self) -> str:
        return "health://status"

    def get_description(self) -> str:
        return "Get MCP server health status and service availability."

    async def get(self, ctx: Optional[Context] = None) -> HealthStatus:
        """
        Get health status.

        Returns:
            HealthStatus with service states
        """
        services = {
            "mcp_server": True,
            "database": False,  # TODO: check actual DB
            "redis": False,     # TODO: check actual Redis
            "embeddings": False # TODO: check actual service
        }

        all_healthy = all(services.values())
        status = "healthy" if all_healthy else "degraded"

        return HealthStatus(
            status=status,
            services=services
        )


# ========== Registration Helper ==========

def register_test_interactions(mcp: "FastMCP") -> None:
    """
    Register test tool and resource to MCP server.

    Args:
        mcp: FastMCP server instance
    """
    # Tool: ping
    ping_tool = PingTool()

    @mcp.tool()
    async def ping(ctx: Context) -> PingResponse:
        """Test MCP server connectivity."""
        return await ping_tool.execute(ctx)

    # Resource: health status
    health_resource = HealthResource()

    @mcp.resource("health://status")
    async def get_health_status(ctx: Context) -> HealthStatus:
        """Get server health status."""
        return await health_resource.get(ctx)
```

**Modifier `api/mcp/server.py`**:
```python
# Dans create_mcp_server()
from api.mcp.tools.test_tools import register_test_interactions

def create_mcp_server() -> FastMCP:
    mcp = FastMCP(...)

    # Register test interactions
    register_test_interactions(mcp)

    return mcp
```

**Tests**:
```python
# tests/mcp/test_tools.py
async def test_ping_tool():
    """Test ping tool returns pong."""
    tool = PingTool()
    response = await tool.execute()

    assert response.success is True
    assert response.message == "pong"
    assert response.latency_ms >= 0

async def test_health_resource():
    """Test health resource returns status."""
    resource = HealthResource()
    status = await resource.get()

    assert status.status in ["healthy", "degraded"]
    assert "mcp_server" in status.services
```

**Validation Manuelle**:
```bash
# Start server
mnemolite-mcp-server dev

# Dans MCP Inspector (http://127.0.0.1:6274):
# 1. Tools tab → ping → Execute → Should return "pong"
# 2. Resources tab → health://status → Get → Should return status
```

**Pièges**:
- ⚠️ Async/await requis (FastMCP est async-first)
- ⚠️ Pydantic Field default_factory pour datetime
- ⚠️ Context peut être None (tools simples)
- ⚠️ Registration via decorators @mcp.tool() et @mcp.resource()

**Temps estimé**: 2h

---

#### Sub-Story 23.1.6: MCP Inspector Integration & Validation (0.5 pt)

**Objectif**: Documenter workflow MCP Inspector + validation complète

**Fichier**: `docs/mcp/01_MCP_INSPECTOR_GUIDE.md`

**Contenu**:
```markdown
# MCP Inspector Guide - MnemoLite

## What is MCP Inspector?

MCP Inspector is a web-based debugging tool for MCP servers. It provides:
- Interactive testing of tools, resources, and prompts
- Schema validation
- Message inspection
- Connection testing

## Starting Inspector

### Method 1: Development Mode (Recommended)
```bash
# Starts server + Inspector automatically
mnemolite-mcp-server dev
```

Inspector opens at: `http://127.0.0.1:6274`

### Method 2: Standalone
```bash
# Terminal 1: Start MCP server
mnemolite-mcp-server start

# Terminal 2: Start Inspector
mcp-inspector
```

## Using Inspector

### 1. Tools Tab
Test write operations:
1. Select tool from dropdown (e.g., "ping")
2. Fill parameters (if any)
3. Click "Execute"
4. View response + execution time

### 2. Resources Tab
Test read operations:
1. Enter resource URI (e.g., "health://status")
2. Click "Get"
3. View returned data

### 3. Prompts Tab
Test user templates:
1. Select prompt from dropdown
2. Fill parameters
3. View generated template

### 4. Messages Tab
View raw MCP protocol messages:
- JSON-RPC requests/responses
- Error messages
- Connection logs

## Validation Checklist

### Bootstrap (Story 23.1)
- [ ] Server starts without errors
- [ ] Inspector connects successfully
- [ ] Tool "ping" returns "pong"
- [ ] Resource "health://status" returns status
- [ ] No error messages in Messages tab

### Search Tools (Story 23.2)
- [ ] Resource "code://search/test" returns results
- [ ] Structured output validates (Pydantic)
- [ ] Cache-Control headers present
- [ ] Pagination works (offset/limit)

### Memory System (Story 23.3)
- [ ] Tool "write_project_memory" creates memory
- [ ] Resource "memories://list" shows created memory
- [ ] Resource "memories://search/test" finds memory
- [ ] Elicitation prompt appears for delete

## Troubleshooting

### Inspector won't connect
```bash
# Check server is running
ps aux | grep mnemolite-mcp-server

# Check port 6274 is free
lsof -i :6274

# Restart with verbose logging
mnemolite-mcp-server start --log-level DEBUG
```

### Tools return errors
1. Check Messages tab for error details
2. Verify parameters match schema
3. Check server logs (stderr)
4. Test with simpler parameters

### Resources return 404
1. Verify resource URI format (e.g., "health://status")
2. Check Resources tab dropdown for registered resources
3. Test with ping tool first (simpler)

## Next Steps

After validating with Inspector:
1. Test with Claude Desktop (install command)
2. Try in production (HTTP transport)
3. Monitor with EPIC-22 observability

## References

- MCP Inspector Docs: https://github.com/modelcontextprotocol/inspector
- FastMCP Debugging: https://github.com/jlowin/fastmcp
- MnemoLite MCP Architecture: `99_TEMP/EPIC-23_MCP_VALIDATION_CORRECTIONS.md`
```

**Tests**:
```bash
# Validation automatique (ajouter à tests/mcp/test_inspector.py)
def test_inspector_is_running():
    """Test Inspector web UI is accessible."""
    import requests
    response = requests.get("http://127.0.0.1:6274")
    assert response.status_code == 200

def test_ping_via_inspector_api():
    """Test ping tool via Inspector API."""
    import requests
    response = requests.post("http://127.0.0.1:6274/api/tools/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "pong"
```

**Acceptance Criteria (Story 23.1 Complete)**:
- ✅ `mnemolite-mcp-server start` lance sans erreur
- ✅ `mnemolite-mcp-server dev` ouvre Inspector
- ✅ Tool "ping" retourne "pong" (< 50ms)
- ✅ Resource "health://status" retourne status
- ✅ Claude Desktop peut se connecter (après `install` command)
- ✅ Tous tests pytest passent
- ✅ Documentation Inspector complète

**Temps estimé**: 1.5h

---

### STORY 23.2: Core Search Tools (3 pts → 6 sub-stories)

#### Sub-Story 23.2.1: Pydantic Models for Search (0.5 pt)

**Objectif**: Créer tous les modèles Pydantic pour recherche

**Fichier**: `api/mcp/models.py` (compléter)

**Contenu**:
```python
"""
Pydantic models for MnemoLite MCP interactions.
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID


# ========== Code Chunk Models ==========

class CodeChunkResult(BaseModel):
    """Single code chunk search result."""

    # Identifiers
    id: UUID
    file_path: str
    line_start: int
    line_end: int

    # Content
    source_code: str
    chunk_type: str  # function, class, method, etc.
    language: str
    name: str
    name_path: Optional[str] = None  # Qualified name (EPIC-11)

    # Search metadata
    score: float = Field(ge=0.0, le=1.0, description="Relevance score")
    search_mode: Literal["semantic", "lexical", "hybrid"]

    # Additional metadata
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

    # MCP 2025-06-18: Resource links
    resource_links: List["ResourceLink"] = Field(default_factory=list)


class ResourceLink(BaseModel):
    """MCP 2025-06-18: Link to related resource."""
    uri: str = Field(description="Resource URI (e.g., 'graph://nodes/{chunk_id}')")
    name: str = Field(description="Human-readable name")
    description: Optional[str] = None


class SearchCodeResponse(BaseModel):
    """Response from code search resource."""

    chunks: List[CodeChunkResult]
    total_found: int
    query: str
    search_mode: Literal["semantic", "lexical", "hybrid"]

    # Performance metrics
    query_time_ms: float
    cache_hit: bool

    # Pagination
    offset: int = 0
    limit: int = 10
    has_more: bool = False

    # Metadata
    metadata: dict = Field(default_factory=dict)


class FindSimilarCodeResponse(BaseModel):
    """Response from find similar code resource."""

    similar_chunks: List[CodeChunkResult]
    query_snippet_hash: str  # SHA256 of query snippet
    threshold: float = Field(ge=0.0, le=1.0)
    total_found: int

    query_time_ms: float
    cache_hit: bool


class QualifiedNameSearchResponse(BaseModel):
    """Response from qualified name search."""

    matches: List[CodeChunkResult]
    query_name: str
    fuzzy_enabled: bool
    total_found: int

    query_time_ms: float


# ========== Cache Control ==========

class CacheControl(BaseModel):
    """Cache-Control headers for resources (MCP best practice)."""
    max_age: int = Field(ge=0, description="Cache TTL in seconds")
    stale_while_revalidate: int = Field(ge=0, description="Stale cache tolerance")
    must_revalidate: bool = False


# Forward refs
CodeChunkResult.model_rebuild()
SearchCodeResponse.model_rebuild()
```

**Tests**:
```python
# tests/mcp/test_models.py
def test_code_chunk_result_validation():
    """Test CodeChunkResult model."""
    chunk = CodeChunkResult(
        id=uuid4(),
        file_path="test.py",
        line_start=10,
        line_end=20,
        source_code="def test(): pass",
        chunk_type="function",
        language="python",
        name="test",
        score=0.95,
        search_mode="semantic",
        created_at=datetime.utcnow()
    )
    assert chunk.score == 0.95

def test_resource_link():
    """Test ResourceLink model."""
    link = ResourceLink(
        uri="graph://nodes/abc123",
        name="View Graph"
    )
    assert link.uri.startswith("graph://")

def test_search_response_pagination():
    """Test pagination fields."""
    resp = SearchCodeResponse(
        chunks=[],
        total_found=100,
        query="test",
        search_mode="hybrid",
        query_time_ms=45.2,
        cache_hit=False,
        limit=10,
        offset=0,
        has_more=True
    )
    assert resp.has_more is True
```

**Pièges**:
- ⚠️ UUID vs str (utiliser UUID type)
- ⚠️ datetime timezone-aware (use utcnow)
- ⚠️ Field constraints (ge, le pour scores)
- ⚠️ Forward refs (model_rebuild() pour circular refs)

**Temps estimé**: 1.5h

---

#### Sub-Story 23.2.2: Search Code Resource (0.5 pt)

**Objectif**: Resource "code://search/{query}" avec HybridCodeSearchService

**Fichier**: `api/mcp/tools/search_tools.py`

**Contenu**:
```python
"""
Search tools and resources for MnemoLite MCP.
"""
import time
import hashlib
from typing import Optional, Literal, List
from uuid import UUID

from mcp.server.fastmcp import Context
from api.mcp.tools.base import BaseMCPComponent, MCPReadOperation
from api.mcp.models import (
    SearchCodeResponse,
    CodeChunkResult,
    ResourceLink,
    CacheControl
)

# Import existing services
from api.services.hybrid_code_search_service import HybridCodeSearchService
from api.db.repositories.code_chunk_repository import CodeChunkRepository


class SearchCodeResource(BaseMCPComponent, MCPReadOperation):
    """
    Resource: code://search/{query}

    Search code semantically, lexically, or hybrid.
    """

    def get_name(self) -> str:
        return "code://search"

    def get_description(self) -> str:
        return """
        Search code using semantic, lexical, or hybrid search.

        Returns code chunks with relevance scores, file paths, and line numbers.
        Supports pagination (offset/limit).
        """.strip()

    async def get(
        self,
        query: str,
        mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
        language: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        min_score: float = 0.0,
        ctx: Optional[Context] = None
    ) -> SearchCodeResponse:
        """
        Search code.

        Args:
            query: Search query (natural language or code snippet)
            mode: Search mode (semantic, lexical, hybrid)
            language: Filter by language (e.g., "python", "javascript")
            limit: Max results to return
            offset: Pagination offset
            min_score: Minimum relevance score (0.0-1.0)
            ctx: MCP context

        Returns:
            SearchCodeResponse with matching code chunks
        """
        start_time = time.time()

        # Get services
        search_service: HybridCodeSearchService = self.services["search_service"]

        # Perform search
        try:
            results = await search_service.search(
                query=query,
                mode=mode,
                language=language,
                limit=limit + 1,  # +1 to check has_more
                offset=offset,
                min_score=min_score
            )

            # Check cache hit (from Redis L2)
            cache_hit = getattr(results, "_cache_hit", False)

            # Convert to MCP models
            chunks = []
            for result in results[:limit]:  # Trim to actual limit
                chunk = CodeChunkResult(
                    id=result.id,
                    file_path=result.file_path,
                    line_start=result.line_start,
                    line_end=result.line_end,
                    source_code=result.source_code,
                    chunk_type=result.chunk_type,
                    language=result.language,
                    name=result.name,
                    name_path=result.name_path,
                    score=result.score,
                    search_mode=mode,
                    metadata=result.metadata or {},
                    created_at=result.created_at,
                    resource_links=[
                        ResourceLink(
                            uri=f"code://chunk/{result.id}",
                            name="View Details"
                        ),
                        ResourceLink(
                            uri=f"graph://nodes/{result.id}",
                            name="View Graph"
                        )
                    ]
                )
                chunks.append(chunk)

            query_time_ms = (time.time() - start_time) * 1000
            has_more = len(results) > limit

            return SearchCodeResponse(
                chunks=chunks,
                total_found=len(results),  # TODO: get actual total from service
                query=query,
                search_mode=mode,
                query_time_ms=round(query_time_ms, 2),
                cache_hit=cache_hit,
                offset=offset,
                limit=limit,
                has_more=has_more,
                metadata={
                    "language_filter": language,
                    "min_score": min_score
                }
            )

        except Exception as e:
            # Log error
            if ctx:
                ctx.log.error("Search failed", query=query, error=str(e))

            # Return empty result (graceful degradation)
            return SearchCodeResponse(
                chunks=[],
                total_found=0,
                query=query,
                search_mode=mode,
                query_time_ms=0.0,
                cache_hit=False,
                metadata={"error": str(e)}
            )
```

**Modifier `api/mcp/server.py`** (dans lifespan):
```python
async def mcp_lifespan(server: FastMCP):
    # Initialize services
    from api.services.hybrid_code_search_service import HybridCodeSearchService
    from api.dependencies import get_db_engine, get_redis_cache

    db_engine = await get_db_engine()
    redis_cache = await get_redis_cache()

    search_service = HybridCodeSearchService(
        db_engine=db_engine,
        redis_cache=redis_cache
    )

    # Inject into components
    services = {
        "search_service": search_service,
        "db_engine": db_engine,
        "redis_cache": redis_cache
    }

    # Register search resource
    from api.mcp.tools.search_tools import SearchCodeResource
    search_resource = SearchCodeResource()
    search_resource.inject_services(services)

    @server.resource("code://search")
    async def search_code(
        query: str,
        mode: str = "hybrid",
        language: str = None,
        limit: int = 10,
        offset: int = 0,
        min_score: float = 0.0,
        ctx: Context = None
    ):
        """Search code using semantic/lexical/hybrid search."""
        return await search_resource.get(
            query=query,
            mode=mode,
            language=language,
            limit=limit,
            offset=offset,
            min_score=min_score,
            ctx=ctx
        )

    yield  # Server runs

    # Cleanup
    await db_engine.dispose()
```

**Tests**:
```python
# tests/mcp/test_search_tools.py
async def test_search_code_resource(test_db):
    """Test search code resource."""
    resource = SearchCodeResource()
    resource.inject_services(get_test_services())

    response = await resource.get(query="test function")

    assert isinstance(response, SearchCodeResponse)
    assert response.search_mode == "hybrid"
    assert response.query == "test function"
    assert len(response.chunks) <= 10

async def test_search_with_language_filter(test_db):
    """Test language filtering."""
    resource = SearchCodeResource()
    resource.inject_services(get_test_services())

    response = await resource.get(
        query="test",
        language="python"
    )

    for chunk in response.chunks:
        assert chunk.language == "python"
```

**Validation MCP Inspector**:
```
Resource URI: code://search/test%20function
Parameters:
  - mode: hybrid
  - limit: 5

Expected Response:
  - chunks: [array of CodeChunkResult]
  - query_time_ms: < 100ms (with cache)
  - cache_hit: true (après 2ème appel)
  - resource_links: present in each chunk
```

**Pièges**:
- ⚠️ Service injection doit être async-safe
- ⚠️ Pagination: limit+1 trick pour has_more
- ⚠️ Graceful degradation si search service fail
- ⚠️ Resource links URLs doivent être valides

**Temps estimé**: 2.5h

---

#### Sub-Story 23.2.3: Find Similar Code Resource (0.5 pt)

**Objectif**: Resource "code://similar/{snippet_hash}" pour détecter duplication

**Fichier**: `api/mcp/tools/search_tools.py` (ajouter classe)

**Contenu**:
```python
class FindSimilarCodeResource(BaseMCPComponent, MCPReadOperation):
    """
    Resource: code://similar/{snippet_hash}

    Find code similar to a given snippet (duplication detection).
    """

    def get_name(self) -> str:
        return "code://similar"

    def get_description(self) -> str:
        return """
        Find code similar to a given snippet using semantic embeddings.

        Useful for:
        - Detecting code duplication
        - Finding refactoring opportunities
        - Identifying similar patterns

        Returns code chunks sorted by similarity score.
        """.strip()

    async def get(
        self,
        code_snippet: str,
        threshold: float = 0.8,
        exclude_file: Optional[str] = None,
        limit: int = 5,
        ctx: Optional[Context] = None
    ) -> FindSimilarCodeResponse:
        """
        Find similar code.

        Args:
            code_snippet: Code to find similar matches for
            threshold: Minimum similarity (0.0-1.0)
            exclude_file: Exclude results from this file
            limit: Max results
            ctx: MCP context

        Returns:
            FindSimilarCodeResponse with similar code chunks
        """
        start_time = time.time()

        # Hash snippet for caching
        snippet_hash = hashlib.sha256(code_snippet.encode()).hexdigest()[:16]

        # Get embedding service
        embedding_service = self.services["embedding_service"]
        search_service = self.services["search_service"]

        try:
            # Generate embedding for snippet
            snippet_embedding = await embedding_service.embed_code(code_snippet)

            # Search for similar chunks
            results = await search_service.search_by_embedding(
                embedding=snippet_embedding,
                threshold=threshold,
                limit=limit,
                exclude_file=exclude_file
            )

            # Convert to MCP models
            similar_chunks = []
            for result in results:
                chunk = CodeChunkResult(
                    id=result.id,
                    file_path=result.file_path,
                    line_start=result.line_start,
                    line_end=result.line_end,
                    source_code=result.source_code,
                    chunk_type=result.chunk_type,
                    language=result.language,
                    name=result.name,
                    name_path=result.name_path,
                    score=result.similarity_score,
                    search_mode="semantic",
                    metadata=result.metadata or {},
                    created_at=result.created_at,
                    resource_links=[
                        ResourceLink(
                            uri=f"code://chunk/{result.id}",
                            name="View Original"
                        )
                    ]
                )
                similar_chunks.append(chunk)

            query_time_ms = (time.time() - start_time) * 1000

            return FindSimilarCodeResponse(
                similar_chunks=similar_chunks,
                query_snippet_hash=snippet_hash,
                threshold=threshold,
                total_found=len(similar_chunks),
                query_time_ms=round(query_time_ms, 2),
                cache_hit=False  # TODO: implement caching
            )

        except Exception as e:
            if ctx:
                ctx.log.error("Find similar failed", error=str(e))

            return FindSimilarCodeResponse(
                similar_chunks=[],
                query_snippet_hash=snippet_hash,
                threshold=threshold,
                total_found=0,
                query_time_ms=0.0,
                cache_hit=False
            )
```

**Registration dans server.py**:
```python
@server.resource("code://similar")
async def find_similar_code(
    code_snippet: str,
    threshold: float = 0.8,
    exclude_file: str = None,
    limit: int = 5,
    ctx: Context = None
):
    """Find code similar to given snippet."""
    similar_resource = FindSimilarCodeResource()
    similar_resource.inject_services(services)
    return await similar_resource.get(
        code_snippet=code_snippet,
        threshold=threshold,
        exclude_file=exclude_file,
        limit=limit,
        ctx=ctx
    )
```

**Tests**:
```python
async def test_find_similar_code():
    """Test find similar code resource."""
    resource = FindSimilarCodeResource()
    resource.inject_services(get_test_services())

    snippet = "def calculate_sum(a, b):\n    return a + b"
    response = await resource.get(code_snippet=snippet)

    assert isinstance(response, FindSimilarCodeResponse)
    assert len(response.similar_chunks) >= 0
    assert response.threshold == 0.8

async def test_exclude_file_works():
    """Test exclude_file parameter."""
    resource = FindSimilarCodeResource()
    resource.inject_services(get_test_services())

    snippet = "test code"
    response = await resource.get(
        code_snippet=snippet,
        exclude_file="test.py"
    )

    for chunk in response.similar_chunks:
        assert chunk.file_path != "test.py"
```

**Temps estimé**: 2h

---

**[CONTINUER avec Sub-Stories 23.2.4 à 23.2.6...]**

---

## 📊 RÉSUMÉ DÉCOUPAGE PHASE 1

### Story 23.1: Bootstrap (3 pts → 6 sub-stories)
- 23.1.1: Projet Structure (0.5 pt) - 1h
- 23.1.2: Base Classes (0.5 pt) - 2h
- 23.1.3: FastMCP Server (0.5 pt) - 2h
- 23.1.4: CLI Entrypoint (0.5 pt) - 2h
- 23.1.5: Test Tool+Resource (0.5 pt) - 2h
- 23.1.6: Inspector Integration (0.5 pt) - 1.5h
**Total: 10.5h estimées**

### Story 23.2: Core Search (3 pts → 6 sub-stories)
- 23.2.1: Pydantic Models (0.5 pt) - 1.5h
- 23.2.2: Search Resource (0.5 pt) - 2.5h
- 23.2.3: Similar Code Resource (0.5 pt) - 2h
- 23.2.4: Qualified Name Resource (0.5 pt) - 2h
- 23.2.5: Cache Control Headers (0.5 pt) - 1.5h
- 23.2.6: Pagination & Performance (0.5 pt) - 2h
**Total: 11.5h estimées**

### Story 23.3: Memory System (2 pts → 4 sub-stories)
- 23.3.1: SQL Migration (0.5 pt) - 2h
- 23.3.2: Write Memory Tool (0.5 pt) - 2h
- 23.3.3: Search Memories Resource (0.5 pt) - 2.5h
- 23.3.4: List Memories Resource (0.5 pt) - 1.5h
**Total: 8h estimées**

**PHASE 1 TOTAL: 30h estimées (vs 8 pts = ~24h théoriques)**

---

## 🎯 FORMAT POUR STORIES SUIVANTES

Chaque sub-story suivra ce format:
```
Story X.Y: Nom (0.5 pt)
├── Objectif: [1 phrase]
├── Fichiers: [Liste]
├── Dépendances: [Stories X.Y requises]
├── Contenu: [Code skeleton détaillé]
├── Tests: [pytest examples]
├── Validation: [Checklist MCP Inspector]
├── Pièges: [⚠️ Points attention]
└── Temps: [Xh]
```

---

## ⏭️ PROCHAINE ÉTAPE

Veux-tu que je continue le découpage pour:
1. **Phase 2** (Stories 23.4-23.6+23.10) ?
2. **Phase 3** (Stories 23.7-23.9+23.11-23.12) ?
3. Ou **valider Phase 1** d'abord puis continuer ?

---

**Status**: 📐 ULTRA-DÉCOUPAGE Phase 1 COMPLET
**Sub-stories créées**: 16 (6+6+4)
**Temps total estimé**: ~30h Phase 1
**Prêt pour**: Validation et continuation Phases 2-3
