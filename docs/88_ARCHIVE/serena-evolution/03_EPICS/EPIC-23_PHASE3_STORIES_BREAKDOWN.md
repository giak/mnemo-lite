# EPIC-23 Phase 3: Ultra-Detailed Breakdown

**Stories**: 23.7, 23.8, 23.9, 23.11, 23.12
**Total**: 6 pts → 12 sub-stories → ~20h
**Focus**: Configuration, HTTP Transport, Documentation, Elicitation, MCP Inspector

---

## Story 23.7: Configuration & Utilities (1 pt → 2 sub-stories, 4h)

### Sub-Story 23.7.1: Project Switcher Tool + List Projects Resource (0.5 pt)

**Objectif**: Permettre à l'utilisateur de changer de projet et lister les projets indexés.

**Fichiers**:
- `api/mcp/tools/config_tools.py` (nouveau, ~120 lignes)
- `api/mcp/resources/config_resources.py` (nouveau, ~80 lignes)
- `tests/mcp/test_config_tools.py` (nouveau, ~100 lignes)

**Dépendances**:
- 23.1.1 (structure MCP)
- 23.1.2 (BaseMCPComponent)
- 23.3.1 (table memories avec project_id)

**Contenu**:

```python
# api/mcp/tools/config_tools.py
from mcp import Context
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
import structlog

from api.mcp.base import BaseMCPComponent, MCPBaseResponse

logger = structlog.get_logger()

class SwitchProjectRequest(BaseModel):
    """Request to switch active project."""
    project_id: UUID
    confirm: bool = False

class SwitchProjectResponse(MCPBaseResponse):
    """Response from switch_project tool."""
    project_id: UUID
    project_name: str
    indexed_files: int
    last_indexed: Optional[str] = None

class SwitchProjectTool(BaseMCPComponent):
    """Tool to switch the active project context."""

    def get_name(self) -> str:
        return "switch_project"

    async def execute(
        self,
        ctx: Context,
        request: SwitchProjectRequest
    ) -> SwitchProjectResponse:
        """
        Switch the active project for code search and indexing.

        Args:
            ctx: MCP context
            request: Switch project request with project_id

        Returns:
            SwitchProjectResponse with project details

        Raises:
            ValueError: If project_id not found
        """
        logger.info("switch_project.start", project_id=str(request.project_id))

        # Elicitation si pas de confirmation explicite
        if not request.confirm:
            await ctx.request_elicitation(
                title="Confirm Project Switch",
                prompt=f"Switch to project {request.project_id}? This will change the context for all searches.",
                options=["Yes", "Cancel"]
            )

        # Récupérer les infos du projet depuis DB
        db = self._services["db"]
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id,
                    name,
                    COUNT(DISTINCT c.id) as indexed_files,
                    MAX(c.indexed_at) as last_indexed
                FROM projects p
                LEFT JOIN code_chunks c ON c.project_id = p.id
                WHERE p.id = $1
                GROUP BY p.id, p.name
                """,
                request.project_id
            )

            if not row:
                raise ValueError(f"Project {request.project_id} not found")

            # Stocker dans le contexte MCP (session-level state)
            ctx.session.set("current_project_id", str(request.project_id))

            logger.info(
                "switch_project.success",
                project_id=str(request.project_id),
                project_name=row["name"]
            )

            return SwitchProjectResponse(
                success=True,
                message=f"Switched to project: {row['name']}",
                project_id=request.project_id,
                project_name=row["name"],
                indexed_files=row["indexed_files"],
                last_indexed=row["last_indexed"].isoformat() if row["last_indexed"] else None
            )


# api/mcp/resources/config_resources.py
from mcp import Context
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import structlog

from api.mcp.base import BaseMCPComponent

logger = structlog.get_logger()

class ProjectInfo(BaseModel):
    """Information about a single project."""
    id: UUID
    name: str
    indexed_files: int
    total_chunks: int
    last_indexed: Optional[datetime] = None
    languages: List[str] = Field(default_factory=list)
    is_active: bool = False

class ProjectsListResponse(BaseModel):
    """List of all projects."""
    projects: List[ProjectInfo]
    total: int
    active_project_id: Optional[UUID] = None

class ListProjectsResource(BaseMCPComponent):
    """Resource to list all indexed projects."""

    def get_name(self) -> str:
        return "projects://list"

    async def get(self, ctx: Context) -> ProjectsListResponse:
        """
        List all projects with indexing status.

        Returns:
            ProjectsListResponse with project details
        """
        logger.info("list_projects.start")

        # Récupérer current_project_id du contexte
        active_project_id = ctx.session.get("current_project_id")

        db = self._services["db"]
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    p.id,
                    p.name,
                    COUNT(DISTINCT c.id) as indexed_files,
                    COUNT(c.id) as total_chunks,
                    MAX(c.indexed_at) as last_indexed,
                    ARRAY_AGG(DISTINCT c.language) FILTER (WHERE c.language IS NOT NULL) as languages
                FROM projects p
                LEFT JOIN code_chunks c ON c.project_id = p.id
                GROUP BY p.id, p.name
                ORDER BY p.name
                """
            )

            projects = [
                ProjectInfo(
                    id=row["id"],
                    name=row["name"],
                    indexed_files=row["indexed_files"],
                    total_chunks=row["total_chunks"],
                    last_indexed=row["last_indexed"],
                    languages=row["languages"] or [],
                    is_active=(str(row["id"]) == active_project_id)
                )
                for row in rows
            ]

            logger.info("list_projects.success", total=len(projects))

            return ProjectsListResponse(
                projects=projects,
                total=len(projects),
                active_project_id=UUID(active_project_id) if active_project_id else None
            )
```

**Tests**:

```python
# tests/mcp/test_config_tools.py
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_switch_project_success():
    """Test switching to existing project."""
    tool = SwitchProjectTool()
    project_id = uuid4()

    # Mock DB
    mock_db = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": project_id,
        "name": "test-project",
        "indexed_files": 42,
        "last_indexed": datetime.utcnow()
    }
    mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

    tool.inject_services({"db": mock_db})

    # Mock context
    ctx = MagicMock()
    ctx.session.set = MagicMock()

    response = await tool.execute(
        ctx,
        SwitchProjectRequest(project_id=project_id, confirm=True)
    )

    assert response.success
    assert response.project_id == project_id
    assert response.project_name == "test-project"
    ctx.session.set.assert_called_once_with("current_project_id", str(project_id))

@pytest.mark.asyncio
async def test_list_projects():
    """Test listing all projects."""
    resource = ListProjectsResource()

    # Mock DB
    mock_db = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": uuid4(),
            "name": "project-1",
            "indexed_files": 10,
            "total_chunks": 100,
            "last_indexed": datetime.utcnow(),
            "languages": ["python", "javascript"]
        }
    ]
    mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

    resource.inject_services({"db": mock_db})

    ctx = MagicMock()
    ctx.session.get.return_value = None

    response = await resource.get(ctx)

    assert response.total == 1
    assert len(response.projects) == 1
    assert response.projects[0].name == "project-1"
```

**Validation MCP Inspector**:

1. Tester `switch_project`:
   ```json
   {
     "project_id": "UUID-existant",
     "confirm": true
   }
   ```
   - Vérifier session state updated
   - Vérifier response avec project details

2. Tester `projects://list`:
   - Ouvrir resource dans Inspector
   - Vérifier liste complète
   - Vérifier `is_active` pour projet actif

**Pièges**:
- ⚠️ **Session state**: MCP Context.session est thread-local, vérifier persistance
- ⚠️ **Project not found**: Retourner erreur claire vs crash
- ⚠️ **Elicitation**: Ne pas bloquer si confirm=True déjà fourni

**Temps**: 2h (dev) + 0.5h (tests) = **2.5h**

---

### Sub-Story 23.7.2: Supported Languages Resource (0.5 pt)

**Objectif**: Exposer la liste des langages supportés par Tree-sitter.

**Fichiers**:
- `api/mcp/resources/config_resources.py` (extension, +60 lignes)
- `tests/mcp/test_config_resources.py` (nouveau, ~50 lignes)

**Dépendances**:
- 23.1.1 (structure MCP)
- 23.1.2 (BaseMCPComponent)

**Contenu**:

```python
# api/mcp/resources/config_resources.py (ajout)

class LanguageInfo(BaseModel):
    """Information about a supported language."""
    name: str
    extensions: List[str]
    tree_sitter_grammar: str
    embedding_model: str = "all-MiniLM-L6-v2"  # Default CODE model

class SupportedLanguagesResponse(BaseModel):
    """List of supported programming languages."""
    languages: List[LanguageInfo]
    total: int

class SupportedLanguagesResource(BaseMCPComponent):
    """Resource exposing supported languages."""

    def get_name(self) -> str:
        return "config://languages"

    async def get(self, ctx: Context) -> SupportedLanguagesResponse:
        """
        Get all languages supported by Tree-sitter parsers.

        Returns:
            SupportedLanguagesResponse with language details
        """
        logger.info("supported_languages.start")

        # Récupérer depuis services
        indexing_service = self._services.get("indexing_service")

        languages = [
            LanguageInfo(
                name="Python",
                extensions=[".py", ".pyi"],
                tree_sitter_grammar="tree-sitter-python",
                embedding_model="all-MiniLM-L6-v2"
            ),
            LanguageInfo(
                name="JavaScript",
                extensions=[".js", ".jsx", ".mjs"],
                tree_sitter_grammar="tree-sitter-javascript",
                embedding_model="all-MiniLM-L6-v2"
            ),
            LanguageInfo(
                name="TypeScript",
                extensions=[".ts", ".tsx"],
                tree_sitter_grammar="tree-sitter-typescript",
                embedding_model="all-MiniLM-L6-v2"
            ),
            LanguageInfo(
                name="Go",
                extensions=[".go"],
                tree_sitter_grammar="tree-sitter-go",
                embedding_model="all-MiniLM-L6-v2"
            ),
            LanguageInfo(
                name="Rust",
                extensions=[".rs"],
                tree_sitter_grammar="tree-sitter-rust",
                embedding_model="all-MiniLM-L6-v2"
            ),
            # Ajouter autres langages...
        ]

        logger.info("supported_languages.success", total=len(languages))

        return SupportedLanguagesResponse(
            languages=languages,
            total=len(languages)
        )
```

**Tests**:

```python
# tests/mcp/test_config_resources.py
@pytest.mark.asyncio
async def test_supported_languages():
    """Test getting supported languages."""
    resource = SupportedLanguagesResource()
    resource.inject_services({})

    ctx = MagicMock()
    response = await resource.get(ctx)

    assert response.total > 0
    assert len(response.languages) == response.total

    # Vérifier Python présent
    python = next((l for l in response.languages if l.name == "Python"), None)
    assert python is not None
    assert ".py" in python.extensions
    assert python.tree_sitter_grammar == "tree-sitter-python"
```

**Validation MCP Inspector**:
- Ouvrir `config://languages`
- Vérifier liste complète avec extensions
- Vérifier format JSON structuré

**Pièges**:
- ⚠️ **Hardcoded languages**: Idéalement charger depuis config dynamique
- ⚠️ **Extension conflicts**: `.ts` peut être TypeScript ou autre

**Temps**: 1h (dev) + 0.5h (tests) = **1.5h**

---

## Story 23.8: HTTP Transport Support (2 pts → 4 sub-stories, 8h)

### Sub-Story 23.8.1: HTTP Server Setup avec SSE (0.5 pt)

**Objectif**: Créer serveur HTTP FastMCP avec Server-Sent Events pour streaming.

**Fichiers**:
- `api/mcp/transport/http_server.py` (nouveau, ~150 lignes)
- `api/mcp/transport/__init__.py` (nouveau, ~20 lignes)
- `tests/mcp/transport/test_http_server.py` (nouveau, ~80 lignes)

**Dépendances**:
- 23.1.3 (FastMCP server initialization)
- 23.1.4 (lifespan management)

**Contenu**:

```python
# api/mcp/transport/http_server.py
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator
import json
import structlog

logger = structlog.get_logger()

class MCPHTTPTransport:
    """HTTP transport layer for MCP server with SSE support."""

    def __init__(self, mcp_server: FastMCP, host: str = "0.0.0.0", port: int = 8002):
        """
        Initialize HTTP transport.

        Args:
            mcp_server: Configured FastMCP server instance
            host: Bind host (default: 0.0.0.0)
            port: Bind port (default: 8002, different from FastAPI main app on 8001)
        """
        self.mcp = mcp_server
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="MnemoLite MCP Server (HTTP Transport)",
            version="1.0.0"
        )

        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes for MCP protocol."""

        @self.app.post("/mcp/v1/tools/call")
        async def call_tool(request: Request):
            """Call MCP tool via HTTP POST."""
            body = await request.json()
            tool_name = body.get("tool")
            arguments = body.get("arguments", {})

            logger.info("http.tool.call", tool=tool_name)

            # Appeler le tool MCP
            result = await self.mcp.call_tool(tool_name, arguments)

            return result

        @self.app.get("/mcp/v1/resources/{resource_uri:path}")
        async def get_resource(resource_uri: str):
            """Get MCP resource via HTTP GET."""
            logger.info("http.resource.get", uri=resource_uri)

            result = await self.mcp.get_resource(resource_uri)

            return result

        @self.app.get("/mcp/v1/stream/progress")
        async def stream_progress(request: Request):
            """
            Stream progress updates via Server-Sent Events.

            Used for long-running operations like indexing.
            """
            async def event_generator() -> AsyncGenerator[str, None]:
                # Subscribe to MCP progress events
                async for event in self.mcp.progress_events():
                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "operation": event.operation,
                            "progress": event.progress,
                            "message": event.message
                        })
                    }

            return EventSourceResponse(event_generator())

        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy", "transport": "http"}

    async def start(self):
        """Start HTTP server."""
        import uvicorn

        logger.info("mcp.http.start", host=self.host, port=self.port)

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
```

**Tests**:

```python
# tests/mcp/transport/test_http_server.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_http_tool_call():
    """Test calling MCP tool via HTTP."""
    # Setup mock MCP server
    mcp = MockFastMCP()
    transport = MCPHTTPTransport(mcp, port=8003)

    async with AsyncClient(app=transport.app, base_url="http://test") as client:
        response = await client.post(
            "/mcp/v1/tools/call",
            json={
                "tool": "ping",
                "arguments": {}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

@pytest.mark.asyncio
async def test_http_resource_get():
    """Test getting MCP resource via HTTP."""
    mcp = MockFastMCP()
    transport = MCPHTTPTransport(mcp, port=8003)

    async with AsyncClient(app=transport.app, base_url="http://test") as client:
        response = await client.get("/mcp/v1/resources/health://status")

        assert response.status_code == 200
```

**Validation MCP Inspector**:
- Tester avec curl:
  ```bash
  curl -X POST http://localhost:8002/mcp/v1/tools/call \
    -H "Content-Type: application/json" \
    -d '{"tool": "ping", "arguments": {}}'
  ```
- Vérifier SSE stream:
  ```bash
  curl -N http://localhost:8002/mcp/v1/stream/progress
  ```

**Pièges**:
- ⚠️ **Port conflicts**: MCP HTTP (8002) ≠ FastAPI main (8001)
- ⚠️ **CORS**: Ajouter CORS middleware pour web clients
- ⚠️ **SSE buffering**: Désactiver buffering nginx/reverse proxy

**Temps**: 1.5h (dev) + 0.5h (tests) = **2h**

---

### Sub-Story 23.8.2: OAuth 2.0 + PKCE Authentication (0.5 pt)

**Objectif**: Implémenter OAuth 2.0 avec PKCE flow pour sécuriser HTTP transport.

**Fichiers**:
- `api/mcp/transport/auth.py` (nouveau, ~200 lignes)
- `api/mcp/transport/http_server.py` (modification, +40 lignes)
- `tests/mcp/transport/test_auth.py` (nouveau, ~120 lignes)

**Dépendances**:
- 23.8.1 (HTTP server)

**Contenu**:

```python
# api/mcp/transport/auth.py
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import hashlib
import secrets
import jwt
import structlog

logger = structlog.get_logger()

security = HTTPBearer()

class OAuth2PKCEAuth:
    """OAuth 2.0 with PKCE authentication for MCP HTTP transport."""

    def __init__(self, secret_key: str):
        """
        Initialize OAuth 2.0 PKCE authentication.

        Args:
            secret_key: JWT signing secret
        """
        self.secret_key = secret_key
        self.code_verifiers = {}  # code_challenge -> code_verifier
        self.access_tokens = {}   # token -> user_id

    def generate_pkce_challenge(self) -> tuple[str, str]:
        """
        Generate PKCE code_verifier and code_challenge.

        Returns:
            (code_verifier, code_challenge) tuple
        """
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = hashlib.sha256(code_verifier.encode()).hexdigest()

        return code_verifier, code_challenge

    async def authorize(self, code_challenge: str, client_id: str) -> str:
        """
        Step 1: Authorization - return authorization code.

        Args:
            code_challenge: SHA256 hash of code_verifier
            client_id: Client identifier

        Returns:
            Authorization code
        """
        logger.info("oauth.authorize", client_id=client_id)

        # Générer authorization code
        auth_code = secrets.token_urlsafe(16)

        # Stocker code_challenge pour validation ultérieure
        self.code_verifiers[auth_code] = code_challenge

        return auth_code

    async def exchange_token(
        self,
        auth_code: str,
        code_verifier: str
    ) -> dict:
        """
        Step 2: Token exchange - validate code_verifier and return access token.

        Args:
            auth_code: Authorization code from step 1
            code_verifier: Original code_verifier (proves client identity)

        Returns:
            Token response with access_token and expires_in

        Raises:
            HTTPException: If code_verifier invalid
        """
        logger.info("oauth.exchange", auth_code=auth_code[:8])

        # Vérifier que auth_code existe
        if auth_code not in self.code_verifiers:
            raise HTTPException(status_code=401, detail="Invalid authorization code")

        # Valider code_verifier via PKCE
        expected_challenge = hashlib.sha256(code_verifier.encode()).hexdigest()
        actual_challenge = self.code_verifiers[auth_code]

        if expected_challenge != actual_challenge:
            raise HTTPException(status_code=401, detail="Invalid code_verifier (PKCE failed)")

        # Générer access token JWT
        payload = {
            "sub": "mcp-client",  # user_id
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow()
        }
        access_token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        # Nettoyer code_verifier (one-time use)
        del self.code_verifiers[auth_code]

        logger.info("oauth.success", token=access_token[:16])

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400  # 24h
        }

    async def verify_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> dict:
        """
        Verify JWT access token.

        Args:
            credentials: HTTP Authorization header

        Returns:
            Decoded JWT payload

        Raises:
            HTTPException: If token invalid/expired
        """
        try:
            payload = jwt.decode(
                credentials.credentials,
                self.secret_key,
                algorithms=["HS256"]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")


# Intégration dans HTTP server
# api/mcp/transport/http_server.py (modification)

class MCPHTTPTransport:
    def __init__(self, mcp_server: FastMCP, auth: OAuth2PKCEAuth = None, ...):
        self.auth = auth
        # ...

    def _setup_routes(self):
        # Routes OAuth 2.0
        @self.app.post("/oauth/authorize")
        async def oauth_authorize(code_challenge: str, client_id: str):
            """OAuth 2.0 authorization endpoint."""
            auth_code = await self.auth.authorize(code_challenge, client_id)
            return {"code": auth_code}

        @self.app.post("/oauth/token")
        async def oauth_token(code: str, code_verifier: str):
            """OAuth 2.0 token exchange endpoint."""
            return await self.auth.exchange_token(code, code_verifier)

        # Routes protégées
        @self.app.post("/mcp/v1/tools/call")
        async def call_tool(
            request: Request,
            user: dict = Depends(self.auth.verify_token)  # Protection
        ):
            # ... existing code
```

**Tests**:

```python
# tests/mcp/transport/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_oauth_pkce_flow():
    """Test complete OAuth 2.0 PKCE flow."""
    auth = OAuth2PKCEAuth(secret_key="test-secret")

    # Step 1: Generate PKCE challenge
    code_verifier, code_challenge = auth.generate_pkce_challenge()

    # Step 2: Authorize
    auth_code = await auth.authorize(code_challenge, client_id="test-client")
    assert auth_code is not None

    # Step 3: Exchange token
    token_response = await auth.exchange_token(auth_code, code_verifier)
    assert "access_token" in token_response
    assert token_response["token_type"] == "Bearer"

    # Step 4: Verify token
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token_response["access_token"]
    )
    payload = await auth.verify_token(credentials)
    assert payload["sub"] == "mcp-client"

@pytest.mark.asyncio
async def test_oauth_invalid_verifier():
    """Test PKCE validation rejects wrong code_verifier."""
    auth = OAuth2PKCEAuth(secret_key="test-secret")

    _, code_challenge = auth.generate_pkce_challenge()
    auth_code = await auth.authorize(code_challenge, "test-client")

    # Try with wrong verifier
    with pytest.raises(HTTPException) as exc:
        await auth.exchange_token(auth_code, "wrong-verifier")

    assert exc.value.status_code == 401
    assert "PKCE failed" in exc.value.detail
```

**Validation**:
```bash
# Test PKCE flow avec curl
CODE_VERIFIER=$(openssl rand -base64 32)
CODE_CHALLENGE=$(echo -n $CODE_VERIFIER | sha256sum | awk '{print $1}')

# Step 1: Authorize
AUTH_CODE=$(curl -X POST http://localhost:8002/oauth/authorize \
  -d "code_challenge=$CODE_CHALLENGE&client_id=test" | jq -r '.code')

# Step 2: Exchange token
ACCESS_TOKEN=$(curl -X POST http://localhost:8002/oauth/token \
  -d "code=$AUTH_CODE&code_verifier=$CODE_VERIFIER" | jq -r '.access_token')

# Step 3: Call protected endpoint
curl -X POST http://localhost:8002/mcp/v1/tools/call \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool": "ping", "arguments": {}}'
```

**Pièges**:
- ⚠️ **PKCE hash**: SHA256 en hex, pas base64
- ⚠️ **One-time codes**: Authorization code valide 1 seule fois
- ⚠️ **Token expiry**: Vérifier `exp` claim JWT

**Temps**: 2h (dev) + 1h (tests) = **3h**

---

### Sub-Story 23.8.3: CORS Configuration (0.5 pt)

**Objectif**: Configurer CORS pour permettre accès web au MCP HTTP.

**Fichiers**:
- `api/mcp/transport/http_server.py` (modification, +30 lignes)
- `api/mcp/config.py` (modification, +15 lignes)
- `tests/mcp/transport/test_cors.py` (nouveau, ~60 lignes)

**Dépendances**:
- 23.8.1 (HTTP server)

**Contenu**:

```python
# api/mcp/config.py (ajout)
from pydantic_settings import BaseSettings

class MCPConfig(BaseSettings):
    """MCP server configuration."""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "https://app.example.com"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "OPTIONS"]
    cors_allow_headers: list[str] = ["Authorization", "Content-Type"]

    class Config:
        env_prefix = "MCP_"


# api/mcp/transport/http_server.py (modification)
from fastapi.middleware.cors import CORSMiddleware

class MCPHTTPTransport:
    def __init__(self, mcp_server: FastMCP, config: MCPConfig, ...):
        self.config = config
        # ...
        self._setup_cors()

    def _setup_cors(self):
        """Setup CORS middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=self.config.cors_allow_credentials,
            allow_methods=self.config.cors_allow_methods,
            allow_headers=self.config.cors_allow_headers,
            expose_headers=["X-Request-ID"]  # Pour tracing
        )

        logger.info("cors.configured", origins=self.config.cors_origins)
```

**Tests**:

```python
# tests/mcp/transport/test_cors.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_cors_preflight():
    """Test CORS preflight OPTIONS request."""
    config = MCPConfig(cors_origins=["http://localhost:3000"])
    transport = MCPHTTPTransport(mcp, config=config)

    async with AsyncClient(app=transport.app, base_url="http://test") as client:
        response = await client.options(
            "/mcp/v1/tools/call",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

@pytest.mark.asyncio
async def test_cors_blocked_origin():
    """Test CORS blocks unauthorized origin."""
    config = MCPConfig(cors_origins=["http://localhost:3000"])
    transport = MCPHTTPTransport(mcp, config=config)

    async with AsyncClient(app=transport.app, base_url="http://test") as client:
        response = await client.post(
            "/mcp/v1/tools/call",
            headers={"Origin": "http://evil.com"},
            json={"tool": "ping", "arguments": {}}
        )

        # FastAPI returns response but without CORS headers
        assert "access-control-allow-origin" not in response.headers
```

**Validation**:
```bash
# Test CORS avec curl
curl -X OPTIONS http://localhost:8002/mcp/v1/tools/call \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -v  # Check headers
```

**Pièges**:
- ⚠️ **Wildcard origins**: `["*"]` incompatible avec `allow_credentials=True`
- ⚠️ **SSE CORS**: Vérifier `/mcp/v1/stream/progress` CORS aussi

**Temps**: 1h (dev) + 0.5h (tests) = **1.5h**

---

### Sub-Story 23.8.4: API Key Authentication (Dev Mode) (0.5 pt)

**Objectif**: Implémenter simple API key auth pour développement (alternative à OAuth).

**Fichiers**:
- `api/mcp/transport/auth.py` (modification, +80 lignes)
- `tests/mcp/transport/test_auth.py` (modification, +50 lignes)

**Dépendances**:
- 23.8.1 (HTTP server)

**Contenu**:

```python
# api/mcp/transport/auth.py (ajout)

class APIKeyAuth:
    """Simple API key authentication for development."""

    def __init__(self, api_keys: dict[str, str]):
        """
        Initialize API key auth.

        Args:
            api_keys: Mapping of api_key -> user_id
        """
        self.api_keys = api_keys

    async def verify_api_key(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> dict:
        """
        Verify API key from Authorization: Bearer header.

        Args:
            credentials: HTTP Authorization header

        Returns:
            User info dict

        Raises:
            HTTPException: If API key invalid
        """
        api_key = credentials.credentials

        if api_key not in self.api_keys:
            raise HTTPException(status_code=401, detail="Invalid API key")

        user_id = self.api_keys[api_key]

        logger.info("api_key.verified", user_id=user_id)

        return {
            "sub": user_id,
            "auth_method": "api_key"
        }


# Intégration dans HTTP server
# api/mcp/transport/http_server.py (modification)

class MCPHTTPTransport:
    def __init__(
        self,
        mcp_server: FastMCP,
        auth_mode: str = "oauth",  # "oauth" | "api_key" | "none"
        ...
    ):
        self.auth_mode = auth_mode

        if auth_mode == "oauth":
            self.auth = OAuth2PKCEAuth(secret_key=...)
        elif auth_mode == "api_key":
            self.auth = APIKeyAuth(api_keys={
                "dev-key-12345": "developer",
                "test-key-67890": "tester"
            })
        else:
            self.auth = None  # No auth (dev only)

    def _setup_routes(self):
        @self.app.post("/mcp/v1/tools/call")
        async def call_tool(
            request: Request,
            user: dict = Depends(self._get_auth_dependency())
        ):
            # ...

    def _get_auth_dependency(self):
        """Get appropriate auth dependency based on mode."""
        if self.auth_mode == "oauth":
            return self.auth.verify_token
        elif self.auth_mode == "api_key":
            return self.auth.verify_api_key
        else:
            return lambda: {"sub": "anonymous"}  # No auth
```

**Tests**:

```python
# tests/mcp/transport/test_auth.py (ajout)
@pytest.mark.asyncio
async def test_api_key_auth_success():
    """Test API key authentication success."""
    auth = APIKeyAuth(api_keys={"test-key": "test-user"})

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-key"
    )

    user = await auth.verify_api_key(credentials)
    assert user["sub"] == "test-user"

@pytest.mark.asyncio
async def test_api_key_auth_invalid():
    """Test API key authentication rejects invalid key."""
    auth = APIKeyAuth(api_keys={"valid-key": "user"})

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-key"
    )

    with pytest.raises(HTTPException) as exc:
        await auth.verify_api_key(credentials)

    assert exc.value.status_code == 401
```

**Validation**:
```bash
# Test API key
curl -X POST http://localhost:8002/mcp/v1/tools/call \
  -H "Authorization: Bearer dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"tool": "ping", "arguments": {}}'
```

**Pièges**:
- ⚠️ **Production usage**: Ne JAMAIS utiliser en production (OAuth obligatoire)
- ⚠️ **Key rotation**: Pas de mécanisme rotation, OK pour dev seulement

**Temps**: 1h (dev) + 0.5h (tests) = **1.5h**

---

## Story 23.9: Documentation & Examples (1 pt → 2 sub-stories, 4h)

### Sub-Story 23.9.1: User Guide & API Reference (0.5 pt)

**Objectif**: Documenter toutes les Tools/Resources/Prompts pour utilisateurs.

**Fichiers**:
- `docs/mcp/USER_GUIDE.md` (nouveau, ~3000 mots)
- `docs/mcp/API_REFERENCE.md` (nouveau, ~4000 mots)
- `docs/mcp/EXAMPLES.md` (nouveau, ~2000 mots)

**Dépendances**:
- 23.1.* à 23.10.* (toutes les fonctionnalités)

**Contenu**:

```markdown
# docs/mcp/USER_GUIDE.md

# MnemoLite MCP Server - User Guide

## Introduction

MnemoLite MCP Server transforms your codebase into a **queryable cognitive memory** accessible by LLMs like Claude.

**Key Features**:
- **Semantic Code Search**: Vector-based search using embeddings
- **Code Graph Navigation**: Explore function calls, imports, inheritance
- **Persistent Memories**: Store and retrieve project-specific notes
- **29 MCP Interactions**: 8 Tools + 15 Resources + 6 Prompts

---

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install mcp==1.12.3 fastmcp

# Setup MnemoLite MCP module
cd /home/giak/Work/MnemoLite
python -m api.mcp.server
```

### 2. Configure Claude Desktop

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "python",
      "args": ["-m", "api.mcp.server"],
      "cwd": "/home/giak/Work/MnemoLite",
      "env": {
        "TEST_DATABASE_URL": "postgresql://...",
        "EMBEDDING_MODE": "mock"
      }
    }
  }
}
```

### 3. First Search

In Claude Desktop:

```
User: Use mnemolite to search for "authentication logic"

Claude: [Uses code://search resource]
Found 12 relevant code chunks:
1. api/auth/login.py:45 - JWT token generation
2. api/middleware/auth.py:23 - Authentication middleware
...
```

---

## Tools (Write Operations)

### 1. `index_project`

**Purpose**: Index a project directory for semantic search.

**Arguments**:
- `project_path` (string, required): Absolute path to project
- `languages` (array, optional): Filter languages (e.g., ["python", "javascript"])
- `max_workers` (int, optional): Parallel workers (default: 4)

**Example**:

```json
{
  "project_path": "/home/user/my-project",
  "languages": ["python"],
  "max_workers": 4
}
```

**Response**:

```json
{
  "success": true,
  "message": "Indexed 1,234 files in 45.2s",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "files_indexed": 1234,
  "chunks_created": 8765,
  "duration_seconds": 45.2
}
```

**Elicitation**: Asks confirmation if project > 10,000 files.

---

### 2. `write_memory`

**Purpose**: Store a persistent memory (note, decision, bug report).

**Arguments**:
- `name` (string, required): Unique memory name
- `content` (string, required): Memory content (supports markdown)
- `memory_type` (string, optional): Type (note|decision|bug|feature)
- `tags` (array, optional): Tags for categorization

**Example**:

```json
{
  "name": "auth-refactor-decision",
  "content": "## Decision: Migrate to JWT\n\nRationale: Better scalability...",
  "memory_type": "decision",
  "tags": ["auth", "architecture"]
}
```

---

## Resources (Read Operations)

### 1. `code://search/{query}`

**Purpose**: Semantic search across indexed code.

**Parameters**:
- `query` (string): Search query (natural language or keywords)
- `limit` (int, optional): Max results (default: 10)
- `language` (string, optional): Filter by language

**Example**:

```
code://search/authentication%20middleware?limit=5&language=python
```

**Response**:

```json
{
  "chunks": [
    {
      "id": "uuid-1",
      "file_path": "api/middleware/auth.py",
      "start_line": 23,
      "end_line": 45,
      "content": "class AuthMiddleware:...",
      "score": 0.89
    }
  ],
  "total": 5
}
```

---

### 2. `graph://nodes/{chunk_id}`

**Purpose**: Get code graph for a specific chunk (functions called, imports).

**Example**:

```
graph://nodes/550e8400-e29b-41d4-a716-446655440000
```

**Response**:

```json
{
  "nodes": [
    {
      "id": "uuid-1",
      "name": "authenticate_user",
      "qualified_name": "api.auth.authenticate_user",
      "chunk_type": "function"
    }
  ],
  "edges": [
    {
      "source_id": "uuid-1",
      "target_id": "uuid-2",
      "relation_type": "calls"
    }
  ]
}
```

---

## Prompts (User Templates)

### 1. `analyze_codebase`

**Purpose**: Generate analysis prompt for codebase architecture.

**Parameters**:
- `language` (string): Target language (default: "all")
- `focus` (string): Focus area (architecture|patterns|security)

**Example in Claude Desktop**:

```
User: /analyze_codebase language=python focus=security

Claude: [Prompt auto-expanded]
Analyze the python codebase with focus on security.

Please provide:
1. Security vulnerabilities
2. Authentication/authorization patterns
...

[Claude then uses code://search to explore]
```

---

## Advanced Usage

### Multi-Project Workflow

```python
# Switch to project A
await switch_project(project_id="uuid-a", confirm=True)

# Search in project A
results_a = await search_code(query="authentication")

# Switch to project B
await switch_project(project_id="uuid-b", confirm=True)

# Search in project B (different results)
results_b = await search_code(query="authentication")
```

### Progress Tracking (HTTP Transport)

```javascript
// Subscribe to SSE progress stream
const eventSource = new EventSource('http://localhost:8002/mcp/v1/stream/progress');

eventSource.addEventListener('progress', (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.operation}: ${data.progress * 100}% - ${data.message}`);
});

// Start indexing (triggers progress events)
await fetch('http://localhost:8002/mcp/v1/tools/call', {
  method: 'POST',
  body: JSON.stringify({
    tool: 'index_project',
    arguments: { project_path: '/large/project' }
  })
});
```

---

## Troubleshooting

### "MCP server not responding"

1. Check server logs:
   ```bash
   tail -f /tmp/mnemolite-mcp.log
   ```

2. Verify database connection:
   ```bash
   psql $TEST_DATABASE_URL -c "SELECT COUNT(*) FROM code_chunks;"
   ```

3. Test with MCP Inspector:
   ```bash
   open http://127.0.0.1:6274
   ```

### "Search returns no results"

1. Verify project indexed:
   ```
   GET projects://list
   ```

2. Check index status:
   ```
   GET index://status/{project_id}
   ```

3. Re-index if needed:
   ```json
   {"tool": "index_project", "arguments": {"project_path": "..."}}
   ```

---

## Best Practices

1. **Index incrementally**: Use `reindex_file` for single file changes
2. **Use memories**: Store architectural decisions for context
3. **Tag memories**: Use consistent tags for better retrieval
4. **Monitor cache**: Check `cache://stats` regularly
5. **Elicitation**: Always confirm destructive operations
```

**API_REFERENCE.md** contiendrait:
- Spec complète de chaque Tool/Resource/Prompt
- Schémas Pydantic complets
- Codes d'erreur
- Rate limits (si applicable)

**EXAMPLES.md** contiendrait:
- Exemples Claude Desktop
- Exemples HTTP/curl
- Exemples Python SDK
- Use cases réels

**Temps**: 2.5h (rédaction) + 0.5h (révision) = **3h**

---

### Sub-Story 23.9.2: Developer Guide & Architecture Docs (0.5 pt)

**Objectif**: Documenter architecture interne pour contributeurs.

**Fichiers**:
- `docs/mcp/ARCHITECTURE.md` (nouveau, ~2500 mots)
- `docs/mcp/CONTRIBUTING.md` (nouveau, ~1500 mots)
- `docs/mcp/TROUBLESHOOTING.md` (nouveau, ~1000 mots)

**Dépendances**:
- 23.1.* à 23.10.* (architecture complète)

**Contenu**:

```markdown
# docs/mcp/ARCHITECTURE.md

# MnemoLite MCP Server - Architecture

## Overview

MnemoLite MCP Server is built on **FastMCP** (official MCP SDK) and follows a **layered architecture** with dependency injection.

```
┌─────────────────────────────────────────┐
│   MCP Protocol Layer (FastMCP)          │
│   - stdio transport (Claude Desktop)    │
│   - HTTP/SSE transport (Web clients)    │
└─────────────────────────────────────────┘
              │
┌─────────────────────────────────────────┐
│   MCP Components Layer                  │
│   - Tools (write ops)                   │
│   - Resources (read ops)                │
│   - Prompts (templates)                 │
└─────────────────────────────────────────┘
              │
┌─────────────────────────────────────────┐
│   Services Layer (MnemoLite)            │
│   - HybridCodeSearchService             │
│   - CodeGraphService                    │
│   - CodeIndexingService                 │
│   - MemoryService                       │
└─────────────────────────────────────────┘
              │
┌─────────────────────────────────────────┐
│   Data Layer                            │
│   - PostgreSQL 18 (pgvector)            │
│   - Redis (L2 cache)                    │
└─────────────────────────────────────────┘
```

---

## Design Patterns

### 1. Service Injection Pattern

All MCP components inherit from `BaseMCPComponent` and receive services via dependency injection.

```python
class BaseMCPComponent(ABC):
    def __init__(self):
        self._services = None

    def inject_services(self, services: dict[str, Any]) -> None:
        """Inject MnemoLite services."""
        self._services = services

# Usage in server lifespan
async def server_lifespan(mcp: FastMCP):
    services = {
        "db": DatabaseService(),
        "search_service": HybridCodeSearchService(),
        "graph_service": CodeGraphService(),
        ...
    }

    for component in all_components:
        component.inject_services(services)

    yield
```

**Benefits**:
- Testable (mock services easily)
- Decoupled (MCP components don't instantiate services)
- Reusable (same services shared across components)

---

### 2. Structured Output with Pydantic

All MCP interactions use Pydantic models for **type safety** and **validation** (MCP 2025-06-18 requirement).

```python
class CodeSearchResponse(BaseModel):
    """Response from code search resource."""
    chunks: List[CodeChunk]
    total: int
    query: str
    cache_hit: bool = False

@mcp.resource("code://search/{query}")
async def search_code(ctx: Context, query: str) -> CodeSearchResponse:
    # Return type enforced by FastMCP
    return CodeSearchResponse(chunks=[...], total=10, query=query)
```

---

### 3. Progress Reporting for Long Operations

Use `ctx.report_progress()` for operations > 5 seconds.

```python
@mcp.tool()
async def index_project(ctx: Context, project_path: str) -> IndexResponse:
    files = discover_files(project_path)
    total = len(files)

    for i, file_path in enumerate(files):
        await index_file(file_path)

        # Report every 10%
        if i % (total // 10) == 0:
            progress = i / total
            await ctx.report_progress(
                progress=progress,
                message=f"{i}/{total} files indexed"
            )

    return IndexResponse(files_indexed=total)
```

---

## Module Structure

```
api/mcp/
├── __init__.py
├── server.py                  # FastMCP initialization, lifespan
├── base.py                    # BaseMCPComponent, MCPBaseResponse
├── models.py                  # Shared Pydantic models
├── config.py                  # MCPConfig (Pydantic Settings)
│
├── tools/                     # Write operations (8 tools)
│   ├── __init__.py
│   ├── search_tools.py        # (empty, search is read-only)
│   ├── memory_tools.py        # write_memory, update_memory, delete_memory
│   ├── graph_tools.py         # (empty, graph is read-only)
│   ├── indexing_tools.py      # index_project, reindex_file
│   ├── analytics_tools.py     # clear_cache
│   └── config_tools.py        # switch_project
│
├── resources/                 # Read operations (15 resources)
│   ├── __init__.py
│   ├── search_resources.py    # code://search, memories://search
│   ├── memory_resources.py    # memories://get, memories://list
│   ├── graph_resources.py     # graph://nodes, graph://callers, graph://callees
│   ├── indexing_resources.py  # index://status
│   ├── analytics_resources.py # cache://stats, analytics://search
│   └── config_resources.py    # projects://list, config://languages
│
├── prompts/                   # User templates (6 prompts)
│   ├── __init__.py
│   └── prompt_library.py      # analyze_codebase, refactor_suggestions, etc.
│
└── transport/                 # Transport layers
    ├── __init__.py
    ├── stdio_transport.py     # Default (Claude Desktop)
    ├── http_server.py         # HTTP/SSE transport
    └── auth.py                # OAuth 2.0, API key auth
```

---

## Cache Strategy

### L2 Redis Cache

Graph queries and search results are cached in Redis with TTL.

**Cache Key Pattern**:
```python
import hashlib
import json

def make_cache_key(prefix: str, params: dict) -> str:
    """Generate deterministic cache key."""
    params_json = json.dumps(params, sort_keys=True)
    hash_hex = hashlib.sha256(params_json.encode()).hexdigest()
    return f"{prefix}:{hash_hex[:16]}"

# Example
cache_key = make_cache_key("graph", {"chunk_id": "uuid-123", "depth": 2})
# => "graph:a1b2c3d4e5f6g7h8"
```

**TTL Strategy**:
- Code search: 300s (5 min) - data changes rarely
- Graph queries: 300s (5 min)
- Index status: 60s (1 min) - changes during indexing
- Cache stats: 10s - real-time monitoring

---

## Testing Strategy

### Unit Tests

Test each component in isolation with mocked services.

```python
# tests/mcp/test_search_resources.py
@pytest.mark.asyncio
async def test_search_code_resource():
    resource = SearchCodeResource()

    # Mock search service
    mock_service = AsyncMock()
    mock_service.hybrid_search.return_value = {
        "chunks": [...],
        "total": 5
    }

    resource.inject_services({"search_service": mock_service})

    ctx = MagicMock()
    response = await resource.get(ctx, query="test")

    assert response.total == 5
    mock_service.hybrid_search.assert_called_once()
```

### Integration Tests

Test via MCP Inspector API.

```python
# tests/mcp/integration/test_mcp_inspector.py
import requests

def test_tool_via_inspector():
    """Test tool execution via MCP Inspector HTTP API."""
    response = requests.post(
        "http://127.0.0.1:6274/api/tools/call",
        json={
            "server": "mnemolite",
            "tool": "ping",
            "arguments": {}
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

### End-to-End Tests

Test full workflow with real database (TEST_DATABASE_URL).

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_indexing_workflow(test_db):
    """Test complete indexing + search workflow."""
    # 1. Index project
    index_response = await mcp.call_tool(
        "index_project",
        {"project_path": "/tmp/test-project"}
    )
    assert index_response.success

    # 2. Search code
    search_response = await mcp.get_resource("code://search/function")
    assert search_response.total > 0

    # 3. Verify in database
    async with test_db.pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM code_chunks")
        assert count > 0
```

---

## Contributing

See `CONTRIBUTING.md` for:
- Code style guidelines (Black, Ruff)
- PR process
- Test coverage requirements (>80%)
- Documentation standards
```

**CONTRIBUTING.md** contiendrait:
- Setup développeur local
- Running tests (pytest, MCP Inspector)
- Code style (Black, Ruff, mypy)
- PR checklist
- Release process

**TROUBLESHOOTING.md** contiendrait:
- Common errors et solutions
- Debugging tips
- Performance tuning
- Database migration troubleshooting

**Temps**: 1h (rédaction) = **1h**

---

## Story 23.11: Elicitation Flows (1 pt → 2 sub-stories, 3h) ✅ **COMPLETE** (2025-10-28)

### ✅ Sub-Story 23.11.1: Elicitation Helpers & Patterns (0.5 pt) - COMPLETE

**Objectif**: ✅ Créer helpers réutilisables pour elicitation (human-in-the-loop).

**Fichiers Créés**:
- ✅ `api/mnemo_mcp/elicitation.py` (191 lignes)
- ✅ `tests/mnemo_mcp/test_elicitation.py` (246 lignes, 10 tests)

**Fichiers Modifiés**:
- ✅ `api/mnemo_mcp/tools/memory_tools.py` (ajout elicitation permanent delete, lines 449-479)
- ✅ `api/mnemo_mcp/tools/config_tools.py` (ajout elicitation project switch, lines 64-92)
- ✅ `tests/mnemo_mcp/test_config_tools.py` (ajout mock ctx.elicit)
- ✅ `tests/mnemo_mcp/test_memory_tools.py` (ajout mock ctx.elicit)

**Implémentation Réelle**:

```python
# api/mnemo_mcp/elicitation.py (RÉEL - 191 lignes)
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field
from typing import Optional, List
import structlog

logger = structlog.get_logger()

class ElicitationRequest(BaseModel):
    """Configuration for elicitation prompt."""
    title: str = Field(description="Title shown in UI")
    prompt: str = Field(description="Detailed prompt text")
    options: List[str] = Field(description="Available options")
    default: Optional[str] = Field(default=None, description="Default option")
    dangerous: bool = Field(default=False, description="Show warning UI")

class ElicitationResult(BaseModel):
    """Result from user elicitation."""
    confirmed: bool = Field(description="Whether user confirmed action")
    selected_option: Optional[str] = Field(default=None, description="Selected option")
    cancelled: bool = Field(default=False, description="Whether user cancelled")

async def request_confirmation(
    ctx: Context,
    action: str,
    details: str,
    dangerous: bool = False
) -> ElicitationResult:
    """
    Request user confirmation for an action (yes/no).

    Shows ⚠️ warning icon if dangerous=True for destructive operations.
    On error, returns cancelled=True (safe default).
    """
    logger.info("elicitation.confirm", action=action, dangerous=dangerous)

    title = f"⚠️ Confirm: {action}" if dangerous else f"Confirm: {action}"
    prompt_text = f"{details}\n\nProceed?"

    try:
        # Uses FastMCP ctx.elicit() API (MCP 2025-06-18)
        response = await ctx.elicit(
            prompt=f"{title}\n\n{prompt_text}",
            schema={"type": "string", "enum": ["yes", "no"]}
        )

        confirmed = response.value == "yes"

        logger.info("elicitation.result", action=action, confirmed=confirmed)

        return ElicitationResult(
            confirmed=confirmed,
            selected_option=response.value,
            cancelled=(response.value == "no")
        )
    except Exception as e:
        logger.error("elicitation.error", action=action, error=str(e))
        # Safe default: assume cancelled
        return ElicitationResult(confirmed=False, cancelled=True)

async def request_choice(
    ctx: Context,
    question: str,
    choices: List[str],
    default: Optional[str] = None
) -> str:
    """
    Request user to choose from multiple options.

    Automatically adds "Cancel" option.
    Raises ValueError if user cancels.
    """
    logger.info("elicitation.choice", question=question, choices=choices)

    all_options = choices + ["Cancel"]

    try:
        response = await ctx.elicit(
            prompt=f"{question}\n\nSelect one:",
            schema={"type": "string", "enum": all_options}
        )

        if response.value == "Cancel":
            raise ValueError("User cancelled operation")

        logger.info("elicitation.choice_selected", choice=response.value)
        return response.value
    except ValueError:
        raise
    except Exception as e:
        logger.error("elicitation.choice_error", question=question, error=str(e))
        raise ValueError("Elicitation failed or cancelled") from e
```

**Intégration dans memory_tools.py** (lines 449-479):
```python
# Hard delete (requires elicitation - EPIC-23 Story 23.11)
result = await request_confirmation(
    ctx,
    action="Permanently Delete Memory",
    details=(
        f"Memory '{existing_memory.title}' (ID: {id}) will be permanently deleted.\n"
        f"This action cannot be undone.\n\n"
        f"Memory details:\n"
        f"• Type: {existing_memory.memory_type}\n"
        f"• Created: {existing_memory.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"• Content length: {len(existing_memory.content)} characters"
    ),
    dangerous=True
)

if not result.confirmed:
    logger.info("permanent_deletion_cancelled", memory_id=id)
    return DeleteMemoryResponse(
        id=memory_uuid,
        deleted_at=existing_memory.deleted_at,
        permanent=False,
        can_restore=True,
        success=False,
        message="Permanent deletion cancelled by user"
    ).model_dump(mode='json')
```

**Intégration dans config_tools.py** (lines 64-92):
```python
# Request user confirmation before switching (EPIC-23 Story 23.11)
if not request.confirm:
    result = await request_confirmation(
        ctx,
        action="Switch Project",
        details=(
            f"Switch to repository '{request.repository}'?\n\n"
            f"This will change the active context for:\n"
            f"• All code searches\n"
            f"• Graph queries\n"
            f"• Memory searches\n\n"
            f"Current project will be deactivated."
        ),
        dangerous=False
    )

    if not result.confirmed:
        logger.info("switch_project.cancelled", repository=request.repository)
        return SwitchProjectResponse(
            success=False,
            message="Project switch cancelled by user",
            repository=request.repository,
            indexed_files=0,
            total_chunks=0,
            languages=[]
        )
```

**Tests**:

```python
# tests/mcp/test_elicitation.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_request_confirmation_confirmed():
    """Test user confirms action."""
    ctx = MagicMock()
    ctx.request_elicitation = AsyncMock(
        return_value=MagicMock(selected="Confirm")
    )

    result = await request_confirmation(
        ctx,
        action="Test Action",
        details="Test details"
    )

    assert result.confirmed is True
    assert result.cancelled is False

@pytest.mark.asyncio
async def test_request_confirmation_cancelled():
    """Test user cancels action."""
    ctx = MagicMock()
    ctx.request_elicitation = AsyncMock(
        return_value=MagicMock(selected="Cancel")
    )

    result = await request_confirmation(
        ctx,
        action="Test Action",
        details="Test details"
    )

    assert result.confirmed is False
    assert result.cancelled is True

@pytest.mark.asyncio
async def test_request_choice():
    """Test user chooses from options."""
    ctx = MagicMock()
    ctx.request_elicitation = AsyncMock(
        return_value=MagicMock(selected="Option B")
    )

    choice = await request_choice(
        ctx,
        question="Pick one:",
        choices=["Option A", "Option B", "Option C"]
    )

    assert choice == "Option B"
```

**Validation MCP Inspector**:
- Tester avec Inspector UI
- Vérifier modal/dialog UX
- Vérifier bouton "Cancel" fonctionne

**Tests Réels** (10 tests, 246 lignes):
```python
# tests/mnemo_mcp/test_elicitation.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_context_confirm():
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx

@pytest.mark.asyncio
async def test_request_confirmation_confirmed(mock_context_confirm):
    result = await request_confirmation(
        mock_context_confirm,
        action="Test Action",
        details="Test details"
    )
    assert result.confirmed is True
    assert result.cancelled is False
    assert result.selected_option == "yes"

# 9 autres tests...
```

**Résultats**:
- ✅ 10/10 tests unitaires passing
- ✅ 7 tests d'intégration mis à jour (mocks ctx.elicit ajoutés)
- ✅ 355/355 tests total passing (100%)

**Découverte Clé**:
- ❌ API initiale spécifiée: `ctx.request_elicitation()` (incorrect)
- ✅ API FastMCP réelle: `ctx.elicit()` (MCP 2025-06-18)
- Découverte via Story 23.6 (clear_cache déjà utilisait elicitation)

**Temps Réel**: 1.5h (dev) + 0.5h (tests) = **2h**

---

### ✅ Sub-Story 23.11.2: Elicitation UX Patterns (0.5 pt) - COMPLETE

**Objectif**: ✅ Documenter patterns UX pour elicitation dans docs.

**Fichiers Créés**:
- ✅ `api/docs/ELICITATION_PATTERNS.md` (5,200+ words, 13 sections)

**Contenu Réel**:

```markdown
# docs/mcp/ELICITATION_PATTERNS.md

# Elicitation UX Patterns

## Overview

**Elicitation** is MCP 2025-06-18's human-in-the-loop feature. Use it for:
- Destructive operations (delete, clear cache)
- Large operations (indexing >10k files)
- Ambiguous choices (multiple projects found)

---

## Pattern 1: Destructive Confirmation

**When**: Permanent data deletion, cache clearing

**UX**:
```python
await request_confirmation(
    ctx,
    action="Delete Memory",
    details=f"Memory '{memory_name}' will be permanently deleted. This cannot be undone.",
    dangerous=True  # Shows ⚠️ warning icon
)
```

**Claude Desktop UI**:
```
┌─────────────────────────────────────┐
│ ⚠️ Confirm: Delete Memory           │
│                                     │
│ Memory 'auth-decision' will be      │
│ permanently deleted. This cannot    │
│ be undone.                          │
│                                     │
│ Proceed?                            │
│                                     │
│ [ ⚠️ Yes, delete permanently ]      │
│ [ Cancel ]                          │
└─────────────────────────────────────┘
```

---

## Pattern 2: Large Operation Warning

**When**: Operation takes >30 seconds or affects >1000 items

**UX**:
```python
if file_count > 10000:
    result = await request_confirmation(
        ctx,
        action="Index Large Project",
        details=f"This project has {file_count:,} files. Indexing may take 10-20 minutes.",
        dangerous=False
    )
```

---

## Pattern 3: Ambiguous Choice

**When**: Multiple valid options, user must choose

**UX**:
```python
projects = await find_projects_by_name("my-app")

if len(projects) > 1:
    choices = [f"{p.name} ({p.id})" for p in projects]
    selected = await request_choice(
        ctx,
        question=f"Found {len(projects)} projects named 'my-app'. Which one?",
        choices=choices
    )
```

---

## Pattern 4: Bypass with `confirm` Flag

**When**: User wants to skip confirmation (automation, scripting)

**UX**:
```python
async def delete_memory(
    ctx: Context,
    memory_id: UUID,
    confirm: bool = False  # Allow bypass
):
    if not confirm:
        result = await request_confirmation(...)
        if not result.confirmed:
            return  # Abort

    # Proceed with deletion
```

**Usage**:
```json
{
  "tool": "delete_memory",
  "arguments": {
    "memory_id": "uuid-123",
    "confirm": true  // Skip elicitation
  }
}
```

---

## Best Practices

1. **Always dangerous=True for deletion**
2. **Show numbers**: "10,234 files" not "many files"
3. **Allow bypass**: Add `confirm: bool = False` parameter
4. **Test both paths**: Test confirmed AND cancelled in unit tests
5. **Timeout handling**: Gracefully handle elicitation timeout (60s default)

---

## Anti-Patterns

❌ **Don't** elicit for read operations
❌ **Don't** elicit for fast operations (<1s)
❌ **Don't** show technical UUIDs in prompts (use human names)
❌ **Don't** nest elicitations (confusing UX)
```

**Document Réel** (ELICITATION_PATTERNS.md - 5,200+ words):

**Sections** (13 sections):
1. Overview - Quand utiliser l'elicitation
2. API Reference - `request_confirmation()`, `request_choice()`, `ElicitationResult`
3. Usage Patterns - 3 patterns détaillés (destructive ops, context switch, multiple choice)
4. Bypass Flags - Support automation (confirm=True)
5. Testing Patterns - Unit & integration test examples
6. Logging & Audit Trail - Structured logging details
7. Error Handling - Safe defaults & ValueError pattern
8. FastMCP Integration - ctx.elicit() API details
9. Migration Guide - Before/after code examples
10. Examples in Production - 3 tools using elicitation
11. Best Practices - 7 Do's + 7 Don'ts
12. Future Enhancements - Post-EPIC-23 ideas
13. References - EPIC-23 docs, FastMCP SDK

**Highlights**:
- ✅ 15+ code examples
- ✅ API reference complète
- ✅ Testing patterns avec fixtures
- ✅ Migration guide (before/after)
- ✅ Production examples (delete_memory, switch_project, clear_cache)

**Temps Réel**: 1h (rédaction) = **1h**

---

## Story 23.11 - Résumé Final ✅

**Status**: ✅ **COMPLETE** (2025-10-28)
**Time**: 3h actual (3h estimé - estimation parfaite!)
**Tests**: 10 nouveaux + 7 mis à jour = 355/355 total passing ✅

**Livrables**:
- ✅ `api/mnemo_mcp/elicitation.py` (191 lignes)
- ✅ `tests/mnemo_mcp/test_elicitation.py` (246 lignes, 10 tests)
- ✅ `api/docs/ELICITATION_PATTERNS.md` (5,200+ words)
- ✅ Intégration memory_tools.py (permanent delete)
- ✅ Intégration config_tools.py (project switch)
- ✅ 7 integration tests updated (mocks ctx.elicit)

**Architecture Highlights**:
- FastMCP `ctx.elicit()` API (MCP 2025-06-18)
- Safe defaults (return cancelled on error)
- Bypass flags (`confirm=True` pour automation)
- Dangerous flag (⚠️ warning pour ops destructives)
- Structured logging (INFO/ERROR avec audit trail)

**Completion Report**: `EPIC-23_STORY_23.11_COMPLETION_REPORT.md` (comprehensive)
**ULTRATHINK**: `EPIC-23_STORY_23.11_ULTRATHINK.md` (~1400 lignes)

---

## Story 23.12: MCP Inspector Integration (1 pt → 2 sub-stories, 3h) ⭐NEW

### Sub-Story 23.12.1: Inspector Development Workflow (0.5 pt)

**Objectif**: Intégrer MCP Inspector dans workflow de développement.

**Fichiers**:
- `docs/mcp/MCP_INSPECTOR_GUIDE.md` (nouveau, ~2000 mots)
- `Makefile` (modification, +20 lignes)
- `.vscode/tasks.json` (nouveau, ~50 lignes)

**Dépendances**:
- 23.1.3 (FastMCP server)

**Contenu**:

```markdown
# docs/mcp/MCP_INSPECTOR_GUIDE.md

# MCP Inspector - Development Guide

## What is MCP Inspector?

**MCP Inspector** is a web-based debugging tool for MCP servers at `http://127.0.0.1:6274`.

**Features**:
- Interactive tool/resource testing
- Schema validation
- Request/response inspection
- Elicitation simulation
- Performance monitoring

---

## Installation

```bash
# Install MCP Inspector (included in mcp SDK)
pip install mcp==1.12.3

# Start Inspector (runs on port 6274)
mcp-inspector
```

---

## Development Workflow

### 1. Start MCP Server + Inspector

```bash
# Terminal 1: Start MnemoLite MCP Server
python -m api.mcp.server

# Terminal 2: Start MCP Inspector
mcp-inspector

# Terminal 3: Run tests
pytest tests/mcp/
```

### 2. Register MnemoLite Server in Inspector

Open `http://127.0.0.1:6274` and add:

```
Server Name: mnemolite
Command: python -m api.mcp.server
Working Directory: /home/giak/Work/MnemoLite
```

### 3. Test Tool Interactively

1. Select "mnemolite" server
2. Click "Tools" tab
3. Select "ping" tool
4. Click "Execute"
5. View response JSON

---

## Testing Checklist

### Phase 1 (Story 23.1-23.3)

- [ ] `ping` tool returns pong
- [ ] `health://status` resource shows DB connected
- [ ] `write_memory` creates memory in DB
- [ ] `memories://list` returns created memory
- [ ] `memories://get/{id}` returns memory details
- [ ] `memories://search/{query}` finds memories

### Phase 2 (Story 23.4-23.6)

- [ ] `code://search/{query}` returns code chunks
- [ ] `graph://nodes/{chunk_id}` returns graph
- [ ] `graph://callers/{name}` finds callers
- [ ] `index_project` indexes files (progress shown)
- [ ] `index://status/{project_id}` shows indexing status
- [ ] `cache://stats` shows cache hit rate

### Phase 3 (Story 23.7-23.12)

- [ ] `switch_project` changes context
- [ ] `projects://list` shows all projects
- [ ] HTTP transport works on port 8002
- [ ] OAuth 2.0 authentication succeeds
- [ ] Prompts appear in Claude Desktop UI
- [ ] Elicitation shows confirmation dialog

---

## Debugging Tips

### 1. View Raw JSON-RPC Messages

Inspector shows full request/response:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ping",
    "arguments": {}
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "success": true,
    "message": "pong",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

### 2. Schema Validation

Inspector validates against Pydantic schemas:

- ✅ Green checkmark: Valid schema
- ❌ Red X: Schema mismatch
- ⚠️ Warning: Deprecated fields

### 3. Performance Monitoring

Inspector shows latency for each call:

```
ping: 12ms
code://search/auth: 245ms (cached: 45ms)
index_project: 45.2s
```

---

## Automated Testing via Inspector API

Inspector exposes HTTP API for CI/CD:

```python
# tests/mcp/integration/test_mcp_inspector.py
import requests

def test_all_tools_via_inspector():
    """Test all tools are registered in Inspector."""
    response = requests.get("http://127.0.0.1:6274/api/servers/mnemolite/tools")

    tools = response.json()
    expected_tools = ["ping", "write_memory", "index_project", ...]

    for tool in expected_tools:
        assert tool in tools, f"Tool {tool} not registered"

def test_tool_execution():
    """Test tool execution via Inspector API."""
    response = requests.post(
        "http://127.0.0.1:6274/api/servers/mnemolite/tools/ping/execute",
        json={"arguments": {}}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

---

## Makefile Integration

```makefile
# Makefile (ajout)

.PHONY: mcp-inspector mcp-test

mcp-inspector:
    @echo "Starting MCP Inspector on http://127.0.0.1:6274"
    mcp-inspector

mcp-test:
    @echo "Testing MCP server with Inspector API"
    pytest tests/mcp/integration/ -v
```

Usage:
```bash
make mcp-inspector  # Start Inspector
make mcp-test       # Run integration tests
```

---

## VSCode Tasks

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "MCP: Start Server",
      "type": "shell",
      "command": "python -m api.mcp.server",
      "problemMatcher": [],
      "isBackground": true
    },
    {
      "label": "MCP: Start Inspector",
      "type": "shell",
      "command": "mcp-inspector",
      "problemMatcher": [],
      "isBackground": true
    },
    {
      "label": "MCP: Run Tests",
      "type": "shell",
      "command": "pytest tests/mcp/ -v",
      "problemMatcher": []
    }
  ]
}
```

Usage: `Ctrl+Shift+P` → "Tasks: Run Task" → "MCP: Start Inspector"
```

**Temps**: 1.5h (doc + setup) = **1.5h**

---

### Sub-Story 23.12.2: Inspector Test Automation (0.5 pt)

**Objectif**: Créer tests automatisés via Inspector HTTP API.

**Fichiers**:
- `tests/mcp/integration/test_inspector_api.py` (nouveau, ~200 lignes)
- `tests/mcp/integration/conftest.py` (nouveau, ~80 lignes)
- `scripts/mcp_inspector_check.sh` (nouveau, ~50 lignes)

**Dépendances**:
- 23.12.1 (Inspector workflow)
- 23.1.* à 23.10.* (toutes les fonctionnalités)

**Contenu**:

```python
# tests/mcp/integration/test_inspector_api.py
import pytest
import requests
import time
from typing import List

INSPECTOR_URL = "http://127.0.0.1:6274"
SERVER_NAME = "mnemolite"

@pytest.fixture(scope="module")
def inspector_client():
    """Ensure Inspector is running."""
    try:
        response = requests.get(f"{INSPECTOR_URL}/health", timeout=2)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        pytest.skip("MCP Inspector not running on port 6274")

    yield requests.Session()

def test_server_registered(inspector_client):
    """Test MnemoLite server is registered in Inspector."""
    response = inspector_client.get(f"{INSPECTOR_URL}/api/servers")
    servers = response.json()

    assert any(s["name"] == SERVER_NAME for s in servers), \
        f"Server '{SERVER_NAME}' not registered in Inspector"

def test_all_tools_registered(inspector_client):
    """Test all expected tools are registered."""
    response = inspector_client.get(f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/tools")
    tools = response.json()

    expected_tools = [
        "ping",
        "write_memory",
        "update_memory",
        "delete_memory",
        "index_project",
        "reindex_file",
        "clear_cache",
        "switch_project"
    ]

    tool_names = [t["name"] for t in tools]

    for expected in expected_tools:
        assert expected in tool_names, f"Tool '{expected}' not registered"

def test_all_resources_registered(inspector_client):
    """Test all expected resources are registered."""
    response = inspector_client.get(f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/resources")
    resources = response.json()

    expected_resources = [
        "health://status",
        "code://search",
        "memories://get",
        "memories://list",
        "memories://search",
        "graph://nodes",
        "graph://callers",
        "graph://callees",
        "index://status",
        "cache://stats",
        "analytics://search",
        "projects://list",
        "config://languages"
    ]

    resource_uris = [r["uri_template"] for r in resources]

    for expected in expected_resources:
        assert any(expected in uri for uri in resource_uris), \
            f"Resource '{expected}' not registered"

def test_ping_tool_execution(inspector_client):
    """Test ping tool execution via Inspector API."""
    response = inspector_client.post(
        f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/tools/ping/execute",
        json={"arguments": {}}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["message"] == "pong"
    assert "timestamp" in data

def test_health_resource_get(inspector_client):
    """Test health resource via Inspector API."""
    response = inspector_client.get(
        f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/resources/health%3A%2F%2Fstatus"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database_connected"] is True

def test_schema_validation(inspector_client):
    """Test all tools have valid Pydantic schemas."""
    response = inspector_client.get(f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/tools")
    tools = response.json()

    for tool in tools:
        # Inspector validates schemas automatically
        assert "schema" in tool, f"Tool '{tool['name']}' missing schema"

        schema = tool["schema"]
        assert "properties" in schema or "type" in schema, \
            f"Tool '{tool['name']}' has invalid schema"

def test_performance_monitoring(inspector_client):
    """Test Inspector tracks performance metrics."""
    # Execute ping tool multiple times
    for _ in range(10):
        inspector_client.post(
            f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/tools/ping/execute",
            json={"arguments": {}}
        )

    # Get metrics
    response = inspector_client.get(
        f"{INSPECTOR_URL}/api/servers/{SERVER_NAME}/metrics"
    )

    metrics = response.json()

    # Verify metrics tracked
    assert "total_calls" in metrics
    assert metrics["total_calls"] >= 10
    assert "average_latency_ms" in metrics
```

**Script bash pour CI/CD**:

```bash
# scripts/mcp_inspector_check.sh
#!/bin/bash
set -e

echo "=== MCP Inspector Integration Test ==="

# 1. Start MCP Inspector in background
echo "Starting MCP Inspector..."
mcp-inspector &
INSPECTOR_PID=$!
sleep 3  # Wait for startup

# 2. Start MnemoLite MCP Server in background
echo "Starting MnemoLite MCP Server..."
python -m api.mcp.server &
MCP_PID=$!
sleep 5  # Wait for registration

# 3. Run integration tests
echo "Running Inspector API tests..."
pytest tests/mcp/integration/test_inspector_api.py -v

# 4. Cleanup
echo "Cleaning up..."
kill $INSPECTOR_PID
kill $MCP_PID

echo "✅ All Inspector integration tests passed!"
```

**Tests**:

```python
# tests/mcp/integration/conftest.py
import pytest
import subprocess
import time

@pytest.fixture(scope="session", autouse=True)
def start_inspector():
    """Start MCP Inspector for integration tests."""
    proc = subprocess.Popen(
        ["mcp-inspector"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for startup
    time.sleep(3)

    yield

    # Cleanup
    proc.terminate()
    proc.wait(timeout=5)
```

**Validation**:
```bash
# Run integration tests
pytest tests/mcp/integration/ -v

# Or via script
bash scripts/mcp_inspector_check.sh
```

**Pièges**:
- ⚠️ **Port conflicts**: Vérifier port 6274 libre
- ⚠️ **Startup time**: Attendre 3-5s avant tests
- ⚠️ **CI/CD**: Ajouter timeout pour éviter hang

**Temps**: 1h (dev) + 0.5h (tests) = **1.5h**

---

## Phase 3 Summary

**Total**: 12 sub-stories, 6 story points, ~20h

| Story | Sub-Stories | Time |
|-------|------------|------|
| 23.7: Configuration | 2 | 4h |
| 23.8: HTTP Transport | 4 | 8h |
| 23.9: Documentation | 2 | 4h |
| 23.11: Elicitation | 2 | 3h |
| 23.12: Inspector | 2 | 3h |

**Dependencies**:
- 23.7 → 23.1.1, 23.1.2, 23.3.1
- 23.8 → 23.1.3, 23.1.4
- 23.9 → all (23.1.* to 23.10.*)
- 23.11 → 23.1.2
- 23.12 → 23.1.3 + all (for testing)

**Validation**:
- ✅ All tools/resources/prompts documented
- ✅ HTTP transport tested with curl
- ✅ OAuth 2.0 PKCE flow validated
- ✅ MCP Inspector integration tested
- ✅ Elicitation patterns documented

---

## Next Steps

1. **Create EPIC-23_README.md** consolidating all 3 phases
2. **Begin implementation** starting with Phase 1 (Story 23.1)
3. **Setup CI/CD** with Inspector integration tests
