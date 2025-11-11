"""
MnemoLite MCP Server

FastMCP-based Model Context Protocol server.
Exposes MnemoLite's code intelligence features to LLMs like Claude.

Usage:
    # stdio transport (Claude Desktop)
    python -m api.mcp.server

    # HTTP transport (Web clients)
    MCP_TRANSPORT=http python -m api.mcp.server
"""

import sys
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from mcp.server.fastmcp import FastMCP
import structlog

from mnemo_mcp.config import config
from mnemo_mcp.prompts import register_prompts

# Setup structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(structlog.stdlib.logging, config.log_level)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


# ============================================================================
# Server Lifespan Management
# ============================================================================

@asynccontextmanager
async def server_lifespan(mcp: FastMCP) -> AsyncGenerator[None, None]:
    """
    MCP server lifespan manager.

    Handles startup and shutdown:
    - Startup: Initialize database, Redis, services, inject dependencies
    - Shutdown: Cleanup connections, close pools

    Args:
        mcp: FastMCP server instance

    Yields:
        None (server is ready)
    """
    logger.info(
        "mcp.server.startup",
        name=config.server_name,
        version=config.server_version,
        transport=config.transport
    )

    # Services dict for dependency injection
    services = {}

    # --------------------------------------------------------------------
    # 1. Initialize Database Connection Pool
    # --------------------------------------------------------------------
    try:
        import asyncpg

        logger.info("mcp.db.connecting", url=config.database_url.split("@")[1])

        db_pool = await asyncpg.create_pool(
            config.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

        # Test connection
        async with db_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info("mcp.db.connected", postgres_version=version[:50])

        services["db"] = db_pool

    except Exception as e:
        logger.error("mcp.db.connection_failed", error=str(e))
        raise RuntimeError(f"Failed to connect to database: {e}")

    # --------------------------------------------------------------------
    # 2. Initialize Redis Client
    # --------------------------------------------------------------------
    try:
        import redis.asyncio as aioredis

        logger.info("mcp.redis.connecting", url=config.redis_url)

        redis_client = aioredis.from_url(
            config.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )

        # Test connection
        await redis_client.ping()
        logger.info("mcp.redis.connected")

        services["redis"] = redis_client

    except Exception as e:
        logger.warning("mcp.redis.connection_failed", error=str(e))
        # Redis is optional - graceful degradation
        services["redis"] = None

    # --------------------------------------------------------------------
    # 3. Initialize Services
    # --------------------------------------------------------------------

    # Story 23.2: Initialize EmbeddingService
    # Use MockEmbeddingService for fast startup (no 2-min model loading)
    # To use real embeddings: EMBEDDING_MODE=real (requires model download)
    try:
        embedding_mode = "mock"  # TODO: Read from env var if needed

        from services.embedding_service import MockEmbeddingService

        embedding_service = MockEmbeddingService(
            model_name="mock-model",
            dimension=768
        )

        services["embedding_service"] = embedding_service
        logger.info(
            "mcp.embedding_service.initialized",
            mode=embedding_mode,
            dimension=768
        )

    except Exception as e:
        logger.warning(
            "mcp.embedding_service.initialization_failed",
            error=str(e)
        )
        # Embedding service is optional - graceful degradation to lexical-only
        services["embedding_service"] = None

    # Create SQLAlchemy engine FIRST (needed by multiple services)
    sqlalchemy_engine = None
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        sqlalchemy_url = config.database_url.replace("postgresql://", "postgresql+asyncpg://")
        sqlalchemy_engine = create_async_engine(
            sqlalchemy_url,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )
        services["engine"] = sqlalchemy_engine
        logger.info("mcp.sqlalchemy_engine.initialized")
    except Exception as e:
        logger.warning("mcp.sqlalchemy_engine.initialization_failed", error=str(e))
        services["engine"] = None

    # Story 23.5: Initialize CodeIndexingService
    try:
        from services.code_indexing_service import CodeIndexingService
        from services.code_chunking_service import CodeChunkingService
        from services.metadata_extractor_service import MetadataExtractorService
        from services.graph_construction_service import GraphConstructionService
        from db.repositories.code_chunk_repository import CodeChunkRepository
        from services.caches.cascade_cache import CascadeCache
        from services.caches.code_chunk_cache import CodeChunkCache
        from services.caches.redis_cache import RedisCache

        # Create L1 cache (in-memory LRU)
        l1_cache = CodeChunkCache(max_size_mb=100)

        # Create L2 cache (Redis) if Redis is available
        l2_cache = None
        if services.get("redis"):
            l2_cache = RedisCache(redis_url=config.redis_url)
            # Connect the Redis cache
            await l2_cache.connect()

        # Create cascade cache with L1 and L2
        chunk_cache = CascadeCache(
            l1_cache=l1_cache,
            l2_cache=l2_cache
        )
        services["chunk_cache"] = chunk_cache

        # Initialize required dependencies for CodeIndexingService
        chunking_service = CodeChunkingService(max_workers=4)
        metadata_service = MetadataExtractorService()
        graph_service = GraphConstructionService(engine=sqlalchemy_engine)
        chunk_repository = CodeChunkRepository(engine=sqlalchemy_engine)

        # Initialize CodeIndexingService with all required dependencies
        code_indexing_service = CodeIndexingService(
            engine=sqlalchemy_engine,
            chunking_service=chunking_service,
            metadata_service=metadata_service,
            embedding_service=services.get("embedding_service"),
            graph_service=graph_service,
            chunk_repository=chunk_repository,
            chunk_cache=chunk_cache
        )
        services["code_indexing_service"] = code_indexing_service

        logger.info(
            "mcp.code_indexing_service.initialized",
            cache_enabled=services.get("redis") is not None
        )

    except Exception as e:
        logger.warning("mcp.code_indexing_service.initialization_failed", error=str(e))
        services["code_indexing_service"] = None
        # Note: Don't set chunk_cache to None - it was successfully initialized above

    # Story 23.6: Initialize MetricsCollector (EPIC-22)
    # Note: MetricsCollector initialization deferred to after sqlalchemy_engine creation
    # See after MemoryRepository initialization section

    logger.info(
        "mcp.services.initialized",
        services=list(services.keys())
    )

    # --------------------------------------------------------------------
    # 4. Inject Services into MCP Components
    # --------------------------------------------------------------------
    # Store services in mcp for access in registration functions
    mcp._services = services

    # Story 23.3: Initialize MemoryRepository (requires SQLAlchemy engine)
    try:
        from db.repositories.memory_repository import MemoryRepository

        # Use already-created SQLAlchemy engine
        if not sqlalchemy_engine:
            raise RuntimeError("SQLAlchemy engine not initialized")

        memory_repository = MemoryRepository(sqlalchemy_engine)
        services["memory_repository"] = memory_repository

        logger.info("mcp.memory_repository.initialized")

        # Story 23.6: Initialize MetricsCollector (uses same sqlalchemy_engine)
        from services.metrics_collector import MetricsCollector

        metrics_collector = MetricsCollector(
            db_engine=sqlalchemy_engine,
            redis_client=services.get("redis")  # Can be None for graceful degradation
        )
        services["metrics_collector"] = metrics_collector

        logger.info(
            "mcp.metrics_collector.initialized",
            redis_available=services.get("redis") is not None
        )

    except Exception as e:
        logger.warning("mcp.memory_repository.initialization_failed", error=str(e))
        services["memory_repository"] = None
        services["metrics_collector"] = None

    # Story 23.4: Initialize NodeRepository and GraphTraversalService
    try:
        from db.repositories.node_repository import NodeRepository
        from services.graph_traversal_service import GraphTraversalService

        # NodeRepository uses the same SQLAlchemy engine
        node_repository = NodeRepository(sqlalchemy_engine)
        services["node_repository"] = node_repository

        # GraphTraversalService uses NodeRepository and RedisCache
        graph_traversal_service = GraphTraversalService(
            engine=sqlalchemy_engine,
            redis_cache=services.get("redis")  # Can be None for graceful degradation
        )
        services["graph_traversal_service"] = graph_traversal_service

        logger.info(
            "mcp.graph_services.initialized",
            node_repository=True,
            graph_traversal_service=True,
            redis_cache=services.get("redis") is not None
        )

    except Exception as e:
        logger.warning("mcp.graph_services.initialization_failed", error=str(e))
        services["node_repository"] = None
        services["graph_traversal_service"] = None

    # Inject services into registered components
    from mnemo_mcp.tools.test_tool import ping_tool
    from mnemo_mcp.tools.search_tool import search_code_tool
    from mnemo_mcp.resources.health_resource import health_resource
    from mnemo_mcp.tools.memory_tools import (
        write_memory_tool,
        update_memory_tool,
        delete_memory_tool,
    )
    from mnemo_mcp.resources.memory_resources import (
        get_memory_resource,
        list_memories_resource,
        search_memories_resource,
    )
    from mnemo_mcp.resources.graph_resources import (
        graph_node_details_resource,
        find_callers_resource,
        find_callees_resource,
    )
    from mnemo_mcp.tools.indexing_tools import (
        index_project_tool,
        reindex_file_tool,
    )
    from mnemo_mcp.resources.indexing_resources import (
        index_status_resource,
    )
    from mnemo_mcp.tools.analytics_tools import (
        clear_cache_tool,
    )
    from mnemo_mcp.resources.analytics_resources import (
        cache_stats_resource,
        search_analytics_resource,
    )
    from mnemo_mcp.tools.config_tools import (
        switch_project_tool,
    )
    from mnemo_mcp.resources.config_resources import (
        list_projects_resource,
        supported_languages_resource,
    )

    ping_tool.inject_services(services)
    search_code_tool.inject_services(services)
    health_resource.inject_services(services)

    # Story 23.3: Inject services into memory components
    write_memory_tool.inject_services(services)
    update_memory_tool.inject_services(services)
    delete_memory_tool.inject_services(services)
    get_memory_resource.inject_services(services)
    list_memories_resource.inject_services(services)
    search_memories_resource.inject_services(services)

    # Story 23.4: Inject services into graph components
    graph_node_details_resource.inject_services(services)
    find_callers_resource.inject_services(services)
    find_callees_resource.inject_services(services)

    # Story 23.5: Inject services into indexing components
    index_project_tool.inject_services(services)
    reindex_file_tool.inject_services(services)
    index_status_resource.inject_services(services)

    # Story 23.6: Inject services into analytics components
    clear_cache_tool.inject_services(services)
    cache_stats_resource.inject_services(services)
    search_analytics_resource.inject_services(services)

    # Story 23.7: Inject services into config components
    switch_project_tool.inject_services(services)
    list_projects_resource.inject_services(services)
    supported_languages_resource.inject_services(services)

    logger.info(
        "mcp.components.services_injected",
        components=[
            "ping_tool", "search_code_tool", "health_resource",
            "write_memory_tool", "update_memory_tool", "delete_memory_tool",
            "get_memory_resource", "list_memories_resource", "search_memories_resource",
            "graph_node_details_resource", "find_callers_resource", "find_callees_resource",
            "index_project_tool", "reindex_file_tool", "index_status_resource",
            "clear_cache_tool", "cache_stats_resource", "search_analytics_resource",
            "switch_project_tool", "list_projects_resource", "supported_languages_resource"
        ]
    )

    try:
        yield
    finally:
        logger.info("mcp.server.shutdown")

        # --------------------------------------------------------------------
        # Cleanup: Close Connections
        # --------------------------------------------------------------------
        if services.get("redis"):
            try:
                await services["redis"].close()
                logger.info("mcp.redis.closed")
            except Exception as e:
                logger.error("mcp.redis.close_error", error=str(e))

        if services.get("db"):
            try:
                await services["db"].close()
                logger.info("mcp.db.closed")
            except Exception as e:
                logger.error("mcp.db.close_error", error=str(e))

        logger.info("mcp.shutdown.complete")


# ============================================================================
# FastMCP Server Initialization
# ============================================================================

def create_mcp_server() -> FastMCP:
    """
    Create and configure FastMCP server instance.

    Returns:
        Configured FastMCP server
    """
    logger.info("mcp.server.create", config=config.model_dump(exclude={"api_keys", "oauth_secret_key"}))

    # Create FastMCP server
    mcp = FastMCP(
        name=config.server_name,
        lifespan=server_lifespan,
    )

    logger.info(
        "mcp.server.created",
        name=mcp.name,
        version=config.server_version
    )

    # ========================================================================
    # Register MCP Components
    # ========================================================================

    # Story 23.1.5: Test tool and health resource
    register_test_components(mcp)

    # Story 23.2: Code search tool
    register_search_tool(mcp)

    # Story 23.3: Memory tools and resources
    register_memory_components(mcp)

    # Story 23.4: Code graph resources
    register_graph_components(mcp)

    # Story 23.5: Indexing tools and resources
    register_indexing_components(mcp)

    # Story 23.6: Analytics tools and resources
    register_analytics_components(mcp)

    # Story 23.7: Configuration tools and resources
    register_config_components(mcp)

    # Story 23.10: Prompts library
    register_prompts(mcp)

    return mcp


def register_test_components(mcp: FastMCP):
    """
    Register test tool and health resource (Story 23.1.5).

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.tools.test_tool import ping_tool
    from mnemo_mcp.resources.health_resource import health_resource

    from mcp.server.fastmcp import Context

    # Register ping tool
    @mcp.tool()
    async def ping(ctx: Context) -> dict:
        """
        Test MCP server connectivity.

        Returns:
            Pong response with timestamp
        """
        response = await ping_tool.execute(ctx)
        return response.model_dump()

    # Register health status resource
    @mcp.resource("health://status")
    async def get_health_status() -> dict:
        """
        Get MCP server health status.

        Returns:
            Health status with DB, Redis connectivity
        """
        # Note: Resources don't get Context in FastMCP,
        # we call the resource directly
        response = await health_resource.get(None)  # Pass None for now
        return response.model_dump()

    logger.info(
        "mcp.components.test.registered",
        tools=["ping"],
        resources=["health://status"]
    )


def register_search_tool(mcp: FastMCP):
    """
    Register code search tool (Story 23.2).

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.tools.search_tool import search_code_tool
    from mnemo_mcp.models.search_models import (
        CodeSearchQuery,
        CodeSearchFilters,
        CodeSearchResponse,
    )
    from mcp.server.fastmcp import Context

    # Register search_code tool with full parameter specification
    @mcp.tool()
    async def search_code(
        ctx: Context,
        query: str,
        filters: CodeSearchFilters | None = None,
        limit: int = 10,
        offset: int = 0,
        enable_lexical: bool = True,
        enable_vector: bool = True,
        lexical_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> dict:
        """
        Search code using hybrid lexical + vector search with RRF fusion.

        Combines keyword-based (pg_trgm) and semantic (embeddings) search
        for comprehensive code discovery. Results are ranked using Reciprocal
        Rank Fusion (RRF) with configurable weights.

        Args:
            query: Search query (keywords or natural language question)
            filters: Optional filters (language, chunk_type, repository, file_path, LSP types)
            limit: Maximum results to return (1-100, default: 10)
            offset: Pagination offset (0-1000, default: 0)
            enable_lexical: Enable lexical (trigram) search (default: True)
            enable_vector: Enable vector (semantic) search (default: True)
            lexical_weight: Weight for lexical results in RRF (0.0-1.0, default: 0.4)
            vector_weight: Weight for vector results in RRF (0.0-1.0, default: 0.6)

        Returns:
            CodeSearchResponse with results, metadata, and pagination info

        Examples:
            - "authentication function in Python"
            - "how to connect to database"
            - "redis cache implementation"
        """
        response: CodeSearchResponse = await search_code_tool.execute(
            ctx=ctx,
            query=query,
            filters=filters,
            limit=limit,
            offset=offset,
            enable_lexical=enable_lexical,
            enable_vector=enable_vector,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
        )
        return response.model_dump()

    logger.info(
        "mcp.components.search.registered",
        tools=["search_code"]
    )


def register_memory_components(mcp: FastMCP):
    """
    Register memory tools and resources (Story 23.3).

    Tools:
        - write_memory: Create new persistent memory
        - update_memory: Update existing memory (partial)
        - delete_memory: Soft delete (default) or hard delete (with elicitation)

    Resources:
        - memories://get/{id}: Get single memory by UUID
        - memories://list: List memories with filters and pagination
        - memories://search/{query}: Semantic search with embeddings

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.tools.memory_tools import (
        write_memory_tool,
        update_memory_tool,
        delete_memory_tool,
    )
    from mnemo_mcp.resources.memory_resources import (
        get_memory_resource,
        list_memories_resource,
        search_memories_resource,
    )
    from mnemo_mcp.models.memory_models import (
        MemoryType,
        MemoryResponse,
        DeleteMemoryResponse,
    )
    from mcp.server.fastmcp import Context
    from typing import Optional, List, Dict, Any

    # Register write_memory tool
    @mcp.tool()
    async def write_memory(
        ctx: Context,
        title: str,
        content: str,
        memory_type: str = "note",
        tags: List[str] | None = None,
        author: Optional[str] = None,
        project_id: Optional[str] = None,
        related_chunks: List[str] | None = None,
        resource_links: List[Dict[str, str]] | None = None,
    ) -> dict:
        """
        Create a new persistent memory with semantic embedding.

        Memories are stored with embeddings for later semantic retrieval.
        Supports project scoping, tags, and links to code chunks.

        Args:
            title: Short memory title (1-200 chars)
            content: Full memory content
            memory_type: Classification (note, decision, task, reference, conversation)
            tags: User-defined tags for filtering (optional)
            author: Optional author attribution (e.g., "Claude", "User")
            project_id: UUID for project scoping (null = global memory)
            related_chunks: Array of code chunk UUIDs to link (optional)
            resource_links: MCP resource links [{"uri": "...", "type": "..."}] (optional)

        Returns:
            MemoryResponse with id, title, memory_type, timestamps, embedding_generated

        Examples:
            - "User prefers async/await over callbacks"
            - "Decision: Chose Redis for L2 cache (see ADR-001)"
            - "TODO: Implement cursor-based pagination"
        """
        response = await write_memory_tool.execute(
            ctx=ctx,
            title=title,
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            author=author,
            project_id=project_id,
            related_chunks=related_chunks or [],
            resource_links=resource_links or [],
        )
        return response

    # Register update_memory tool
    @mcp.tool()
    async def update_memory(
        ctx: Context,
        id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
        related_chunks: Optional[List[str]] = None,
        resource_links: Optional[List[Dict[str, str]]] = None,
    ) -> dict:
        """
        Update an existing memory (partial update).

        Updates one or more fields of an existing memory.
        Regenerates embedding if title or content changes.

        Args:
            id: Memory UUID to update
            title: Update title (optional)
            content: Update content (optional)
            memory_type: Update classification (optional)
            tags: Update tags - replaces existing (optional)
            author: Update author (optional)
            related_chunks: Update related code chunks - replaces existing (optional)
            resource_links: Update resource links - replaces existing (optional)

        Returns:
            Dict with id, updated_at, embedding_regenerated

        Examples:
            - Update tags: update_memory(id="...", tags=["python", "async", "new-tag"])
            - Update content: update_memory(id="...", content="Updated content...")
        """
        response = await update_memory_tool.execute(
            ctx=ctx,
            id=id,
            title=title,
            content=content,
            memory_type=memory_type,
            tags=tags,
            author=author,
            related_chunks=related_chunks,
            resource_links=resource_links,
        )
        return response

    # Register delete_memory tool
    @mcp.tool()
    async def delete_memory(
        ctx: Context,
        id: str,
        permanent: bool = False,
    ) -> dict:
        """
        Delete a memory (soft delete by default, hard delete with elicitation).

        Soft delete: Sets deleted_at timestamp (can be restored).
        Hard delete: Permanently removes from database (requires elicitation).

        ⚠️ ELICITATION FLOW:
            1. delete_memory(id="...") → Soft delete (reversible)
            2. delete_memory(id="...", permanent=True) → Triggers elicitation
            3. User confirms → Hard delete (irreversible)

        Args:
            id: Memory UUID to delete
            permanent: If True, triggers elicitation for hard delete confirmation

        Returns:
            DeleteMemoryResponse with id, deleted_at, permanent, can_restore

        Examples:
            - Soft delete: delete_memory(id="...")
            - Hard delete: delete_memory(id="...", permanent=True)
        """
        response = await delete_memory_tool.execute(
            ctx=ctx,
            id=id,
            permanent=permanent,
        )
        return response

    # Register memories://get/{id} resource
    @mcp.resource("memories://get/{id}")
    async def get_memory(id: str) -> dict:
        """
        Get a single memory by UUID.

        URI: memories://get/{id}
        Returns: Complete Memory object with all fields

        Example:
            - memories://get/abc-123-def-456
        """
        uri = f"memories://get/{id}"
        response = await get_memory_resource.get(None, uri)
        return response

    # Register memories://list resource
    @mcp.resource("memories://list")
    async def list_memories() -> dict:
        """
        List memories with optional filters and pagination.

        URI: memories://list?project_id={uuid}&memory_type={type}&tags={tag1,tag2}&limit={n}&offset={n}

        Query Parameters:
            - project_id: UUID (optional, filter by project)
            - memory_type: note|decision|task|reference|conversation (optional)
            - tags: comma-separated (optional, e.g., "python,async")
            - author: string (optional)
            - limit: 1-100 (default 10)
            - offset: pagination offset (default 0)
            - include_deleted: true|false (default false)

        Returns:
            MemoryListResponse with memories list and pagination metadata

        Examples:
            - memories://list
            - memories://list?tags=python&limit=5
            - memories://list?memory_type=decision&project_id=xyz
        """
        # Use base URI without query parameters (resource will use defaults)
        uri = "memories://list"
        response = await list_memories_resource.get(None, uri)
        return response

    # Register memories://search/{query} resource
    @mcp.resource("memories://search/{query}")
    async def search_memories(query: str) -> dict:
        """
        Semantic search for memories using embeddings.

        URI: memories://search/{query}?limit={n}&threshold={0.0-1.0}

        Query Parameters:
            - limit: 1-50 (default 5)
            - offset: pagination offset (default 0)
            - project_id: UUID (optional, filter by project)
            - memory_type: filter by type (optional)
            - tags: comma-separated tags (optional)
            - threshold: similarity threshold 0.0-1.0 (default 0.7)

        Returns:
            MemorySearchResponse with ranked memories + similarity scores

        Examples:
            - memories://search/async%20patterns
            - memories://search/redis%20cache?limit=3&threshold=0.8
        """
        # Reconstruct URI from query parameter
        uri = f"memories://search/{query}"
        response = await search_memories_resource.get(None, uri)
        return response

    logger.info(
        "mcp.components.memory.registered",
        tools=["write_memory", "update_memory", "delete_memory"],
        resources=["memories://get/{id}", "memories://list", "memories://search/{query}"]
    )


def register_graph_components(mcp: FastMCP) -> None:
    """
    Register graph resources (EPIC-23 Story 23.4).

    Registers 3 MCP resources for code dependency graph navigation:
        - graph://nodes/{chunk_id}: Get node details with neighbors
        - graph://callers/{qualified_name}: Find all callers of a function
        - graph://callees/{qualified_name}: Find all callees of a function

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.resources.graph_resources import (
        graph_node_details_resource,
        find_callers_resource,
        find_callees_resource,
    )

    # Register graph://nodes/{chunk_id} resource
    @mcp.resource("graph://nodes/{chunk_id}")
    async def get_node_details(chunk_id: str) -> dict:
        """
        Get code graph node with neighbors.

        Returns a node (function, class, method, module) with:
        - Immediate callers (who calls this)
        - Immediate callees (what this calls)
        - Edges connecting node to neighbors
        - Resource links for navigation

        URI: graph://nodes/{chunk_id}

        Returns:
            GraphNodeDetailsResponse with node, neighbors, resource links

        Example:
            - graph://nodes/abc-123-def-456
        """
        response = await graph_node_details_resource.get(chunk_id=chunk_id)
        return response

    # Register graph://callers/{qualified_name} resource
    @mcp.resource("graph://callers/{qualified_name}")
    async def find_callers(qualified_name: str) -> dict:
        """
        Find all functions/methods that call the target function.

        Performs inbound graph traversal (dependents) up to max_depth hops.

        URI: graph://callers/{qualified_name}?max_depth={n}&limit={m}&offset={k}

        Query Parameters:
            - max_depth: 1-10 (default: 3)
            - relationship_type: calls, imports, etc. (default: calls)
            - limit: 1-500 (default: 50)
            - offset: 0-10000 (default: 0)

        Returns:
            CallerCalleeResponse with callers and pagination links

        Examples:
            - graph://callers/module.ClassName.method_name
            - graph://callers/utils.calculate_total?max_depth=2&limit=10
        """
        response = await find_callers_resource.get(
            qualified_name=qualified_name,
            max_depth=3,
            relationship_type="calls",
            limit=50,
            offset=0
        )
        return response

    # Register graph://callees/{qualified_name} resource
    @mcp.resource("graph://callees/{qualified_name}")
    async def find_callees(qualified_name: str) -> dict:
        """
        Find all functions/methods called by the target function.

        Performs outbound graph traversal (dependencies) up to max_depth hops.

        URI: graph://callees/{qualified_name}?max_depth={n}&limit={m}&offset={k}

        Query Parameters:
            - max_depth: 1-10 (default: 3)
            - relationship_type: calls, imports, etc. (default: calls)
            - limit: 1-500 (default: 50)
            - offset: 0-10000 (default: 0)

        Returns:
            CallerCalleeResponse with callees and pagination links

        Examples:
            - graph://callees/module.ClassName.method_name
            - graph://callees/services.process_data?max_depth=1&limit=20
        """
        response = await find_callees_resource.get(
            qualified_name=qualified_name,
            max_depth=3,
            relationship_type="calls",
            limit=50,
            offset=0
        )
        return response

    logger.info(
        "mcp.components.graph.registered",
        resources=[
            "graph://nodes/{chunk_id}",
            "graph://callers/{qualified_name}",
            "graph://callees/{qualified_name}"
        ]
    )


def register_indexing_components(mcp: FastMCP) -> None:
    """
    Register indexing tools and resources (EPIC-23 Story 23.5).

    Tools:
        - index_project: Index entire project directory with progress reporting
        - reindex_file: Reindex single file after modifications

    Resources:
        - index://status: Get indexing status for repository

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.tools.indexing_tools import (
        index_project_tool,
        reindex_file_tool,
    )
    from mnemo_mcp.resources.indexing_resources import (
        index_status_resource,
    )
    from mcp.server.fastmcp import Context
    from typing import Optional

    # Register index_project tool
    @mcp.tool()
    async def index_project(
        ctx: Context,
        project_path: str,
        repository: str = "default",
        include_gitignored: bool = False,
    ) -> dict:
        """
        Index an entire project directory.

        Scans project for code files, generates embeddings, builds dependency graph.
        Shows real-time progress with throttled updates. Uses distributed lock to
        prevent concurrent indexing. Respects .gitignore by default.

        Args:
            project_path: Path to project root directory
            repository: Repository name for organization (default: "default")
            include_gitignored: If True, index files even if gitignored (default: False)

        Returns:
            IndexResult with indexed_files, indexed_chunks, indexed_nodes, indexed_edges,
            failed_files, processing_time_ms, errors, message

        Elicitation:
            - Confirms with user if >100 files detected

        Examples:
            - index_project(project_path="/home/user/myproject")
            - index_project(project_path="/src", repository="frontend", include_gitignored=True)

        Progress Reporting:
            Uses ctx.report_progress() for real-time status updates (max 1/sec)

        Concurrency:
            Uses Redis distributed lock - only one indexing operation per repository
        """
        response = await index_project_tool.execute(
            project_path=project_path,
            repository=repository,
            include_gitignored=include_gitignored,
            ctx=ctx,
        )
        return response

    # Register reindex_file tool
    @mcp.tool()
    async def reindex_file(
        ctx: Context,
        file_path: str,
        repository: str = "default",
    ) -> dict:
        """
        Reindex a single file after modifications.

        Updates code chunks, regenerates embeddings, refreshes cache.
        Use after editing code to keep search index up to date.

        Args:
            file_path: Path to file to reindex
            repository: Repository name (default: "default")

        Returns:
            FileIndexResult with file_path, chunks_created, processing_time_ms, error

        Cache Behavior:
            - Invalidates L1/L2 cache before reindexing
            - Forces fresh parse and embedding generation

        Examples:
            - reindex_file(file_path="/home/user/myproject/src/main.py")
            - reindex_file(file_path="/src/utils.py", repository="backend")

        Performance:
            - Typical: <100ms per file
            - Depends on file size and embedding generation
        """
        response = await reindex_file_tool.execute(
            file_path=file_path,
            repository=repository,
            ctx=ctx,
        )
        return response

    # Register index://status resource
    @mcp.resource("index://status/{repository}")
    async def get_index_status(repository: str = "default") -> dict:
        """
        Get indexing status for repository.

        Combines Redis ephemeral state (in_progress) with PostgreSQL persistent data
        (completed, statistics). Returns current status with detailed statistics.

        URI: index://status/{repository}

        Returns:
            IndexStatus with:
                - status: not_indexed | in_progress | completed | failed | unknown
                - total_files: Number of indexed files
                - indexed_files: Progress (for in_progress status)
                - total_chunks: Total code chunks in database
                - languages: List of detected programming languages
                - last_indexed_at: Timestamp of last indexing
                - embedding_model: Model used for embeddings
                - cache_stats: L1/L2 cache hit rates
                - started_at: When indexing started (for in_progress)
                - completed_at: When indexing completed
                - error: Error message (for failed status)

        Status Determination:
            1. Redis status (if recent) - in_progress, failed
            2. DB data (if exists) - completed
            3. Otherwise - not_indexed

        Examples:
            - index://status/default
            - index://status/frontend
            - index://status/backend

        Use Cases:
            - Check if repository has been indexed
            - Monitor indexing progress
            - Get statistics (files, chunks, languages)
            - Debug indexing failures
        """
        response = await index_status_resource.get(repository=repository)
        return response

    logger.info(
        "mcp.components.indexing.registered",
        tools=["index_project", "reindex_file"],
        resources=["index://status/{repository}"]
    )


def register_analytics_components(mcp: FastMCP) -> None:
    """
    Register analytics tools and resources (EPIC-23 Story 23.6).

    Tools:
        - clear_cache: Clear cache layers (L1/L2/all) with elicitation confirmation

    Resources:
        - cache://stats: Get cache statistics (L1, L2, cascade)
        - analytics://search: Get search performance analytics

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.tools.analytics_tools import (
        clear_cache_tool,
    )
    from mnemo_mcp.resources.analytics_resources import (
        cache_stats_resource,
        search_analytics_resource,
    )
    from mcp.server.fastmcp import Context

    # Register clear_cache tool
    @mcp.tool()
    async def clear_cache(
        ctx: Context,
        layer: str = "all",
    ) -> dict:
        """
        Clear cache layers (admin operation).

        Clears L1 (in-memory), L2 (Redis), or all cache layers.
        Requires user confirmation via elicitation for destructive operation.
        Performance may temporarily degrade until cache is repopulated.

        Args:
            layer: Cache layer to clear - "L1", "L2", or "all" (default: "all")

        Returns:
            ClearCacheResponse with success, layer, entries_cleared, impact_warning

        Elicitation:
            Always confirms with user before clearing (destructive operation)

        Performance Impact:
            - L1: Low (single process)
            - L2: Medium (all processes)
            - all: High (all caches)

        Recovery Time:
            Typical recovery: 5-30 minutes depending on usage patterns

        Examples:
            - clear_cache(layer="L1")  # Clear in-memory cache only
            - clear_cache(layer="L2")  # Clear Redis cache only
            - clear_cache()            # Clear all cache layers (default)
        """
        response = await clear_cache_tool.execute(
            layer=layer,
            ctx=ctx,
        )
        return response

    # Register cache://stats resource
    @mcp.resource("cache://stats")
    async def get_cache_stats() -> dict:
        """
        Get cache statistics for all layers.

        Returns real-time statistics from L1 (in-memory), L2 (Redis), and cascade.
        Includes hit rates, memory usage, entries, evictions, and connection status.

        URI: cache://stats

        Returns:
            CacheStatsResponse with:
                - l1: L1 cache stats (hit_rate, size_mb, entries, evictions, utilization)
                - l2: L2 cache stats (hit_rate, memory_used_mb, connected, errors)
                - cascade: Combined metrics (combined_hit_rate, l1_to_l2_promotions)
                - overall_hit_rate: Combined hit rate across all layers (0-100)
                - timestamp: ISO 8601 timestamp

        L1 Stats (In-Memory LRU):
            - hit_rate_percent: Cache hit rate (0-100)
            - hits: Total cache hits
            - misses: Total cache misses
            - size_mb: Cache size in MB
            - entries: Number of cached entries
            - evictions: Number of evictions
            - utilization_percent: Cache utilization (0-100)

        L2 Stats (Redis):
            - hit_rate_percent: Cache hit rate (0-100)
            - hits: Total cache hits
            - misses: Total cache misses
            - memory_used_mb: Memory used in MB
            - memory_peak_mb: Peak memory used in MB
            - connected: Connection status (true/false)
            - errors: Number of errors

        Graceful Degradation:
            Works even when Redis (L2) is disconnected - shows L1 stats only

        Examples:
            - cache://stats
        """
        response = await cache_stats_resource.get(None)
        return response

    # Register analytics://search resource
    @mcp.resource("analytics://search")
    async def get_search_analytics() -> dict:
        """
        Get search performance analytics.

        Returns search analytics for specified time period (default: 24 hours).
        Integrates with EPIC-22 MetricsCollector to provide latency, throughput, error rates.

        URI: analytics://search?period_hours={n}

        Query Parameters:
            - period_hours: Analysis period in hours (1-168, default: 24)

        Returns:
            SearchAnalyticsResponse with:
                - period_hours: Analysis period
                - total_queries: Total search queries
                - avg_latency_ms: Average query latency
                - p50_latency_ms: P50 (median) latency
                - p95_latency_ms: P95 latency
                - p99_latency_ms: P99 latency
                - requests_per_second: Average queries per second
                - error_count: Number of failed queries
                - error_rate: Error rate percentage (0-100)
                - timestamp: ISO 8601 timestamp

        Dependencies:
            Requires EPIC-22 MetricsCollector service (graceful degradation if unavailable)

        Examples:
            - analytics://search                    # Last 24 hours (default)
            - analytics://search?period_hours=1     # Last 1 hour
            - analytics://search?period_hours=168   # Last 1 week (max)
        """
        # Default period_hours=24 (resource can parse from URI if needed)
        response = await search_analytics_resource.get(period_hours=24, ctx=None)
        return response

    logger.info(
        "mcp.components.analytics.registered",
        tools=["clear_cache"],
        resources=["cache://stats", "analytics://search"]
    )


def register_config_components(mcp: FastMCP) -> None:
    """
    Register configuration tools and resources (EPIC-23 Story 23.7).

    Tools:
        - switch_project: Switch active project/repository context

    Resources:
        - projects://list: List all indexed projects with statistics
        - config://languages: Get supported programming languages

    Args:
        mcp: FastMCP server instance
    """
    from mnemo_mcp.tools.config_tools import (
        switch_project_tool,
    )
    from mnemo_mcp.resources.config_resources import (
        list_projects_resource,
        supported_languages_resource,
    )
    from mnemo_mcp.models.config_models import (
        SwitchProjectRequest,
    )
    from mcp.server.fastmcp import Context

    # Register switch_project tool
    @mcp.tool()
    async def switch_project(
        ctx: Context,
        repository: str,
        confirm: bool = False,
    ) -> dict:
        """
        Switch the active project/repository for code search and indexing.

        Changes the context for all subsequent MCP operations. The active
        project is stored in MCP session state and persists for the session.

        Args:
            repository: Repository/project name to switch to
            confirm: Skip confirmation elicitation if True (for automation)

        Returns:
            SwitchProjectResponse with repository, indexed_files, total_chunks,
            languages, last_indexed

        Validation:
            - Repository must be indexed first using index_project tool
            - Case-insensitive matching (TEST_PROJECT matches test_project)

        Session State:
            Stores "current_repository" in MCP session for subsequent operations

        Examples:
            - switch_project(repository="backend")
            - switch_project(repository="frontend", confirm=True)

        Related:
            - Use projects://list to see all indexed projects
            - Use index_project to index a new project first
        """
        request = SwitchProjectRequest(
            repository=repository,
            confirm=confirm
        )
        response = await switch_project_tool.execute(ctx=ctx, request=request)
        return response.model_dump()

    # Register projects://list resource
    @mcp.resource("projects://list")
    async def list_projects() -> dict:
        """
        List all indexed projects with statistics.

        Returns aggregated statistics from code_chunks table grouped by repository.
        Marks the currently active project (from session state) with is_active=True.

        URI: projects://list

        Returns:
            ProjectsListResponse with:
                - projects: List of ProjectListItem (repository, indexed_files,
                  total_chunks, last_indexed, languages, is_active)
                - total: Total number of projects
                - active_repository: Currently active repository name (or null)

        Statistics Per Project:
            - indexed_files: Number of indexed files
            - total_chunks: Total code chunks
            - languages: Programming languages detected
            - last_indexed: Timestamp of last indexing
            - is_active: Whether this is the current active project

        Examples:
            - projects://list

        Use Cases:
            - Choose which project to switch to
            - View indexing statistics
            - Check which project is currently active
        """
        # Note: Resources don't get Context in FastMCP
        response = await list_projects_resource.get(ctx=None)
        return response.model_dump()

    # Register config://languages resource
    @mcp.resource("config://languages")
    async def supported_languages() -> dict:
        """
        Get list of programming languages supported by MnemoLite.

        Returns centralized language configuration with file extensions,
        Tree-sitter grammars, and embedding models.

        URI: config://languages

        Returns:
            SupportedLanguagesResponse with:
                - languages: List of LanguageInfo (name, extensions,
                  tree_sitter_grammar, embedding_model)
                - total: Total number of supported languages (15)

        Supported Languages (15):
            Python, JavaScript, TypeScript, Go, Rust, Java, C#, Ruby,
            PHP, C, C++, Swift, Kotlin, Scala, Bash

        Examples:
            - config://languages

        Use Cases:
            - Check if a language is supported before indexing
            - Get file extensions for a language
            - View Tree-sitter grammar configuration
            - Build language-specific UIs
        """
        # Note: Resources don't get Context in FastMCP
        response = await supported_languages_resource.get(ctx=None)
        return response.model_dump()

    logger.info(
        "mcp.components.config.registered",
        tools=["switch_project"],
        resources=["projects://list", "config://languages"]
    )


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """
    Main entry point for MCP server.

    Runs FastMCP server in stdio mode (default) or HTTP mode.
    """
    try:
        # Create server
        mcp = create_mcp_server()

        # Run server based on transport mode
        if config.transport == "stdio":
            logger.info("mcp.server.run.stdio")
            # FastMCP handles stdio transport automatically
            mcp.run()

        elif config.transport == "http":
            logger.info(
                "mcp.server.run.http",
                host=config.http_host,
                port=config.http_port
            )
            # TODO Story 23.8: HTTP transport implementation
            logger.error("HTTP transport not yet implemented (Story 23.8)")
            sys.exit(1)

        else:
            logger.error(f"Unknown transport mode: {config.transport}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("mcp.server.interrupted")
        sys.exit(0)

    except Exception as e:
        logger.exception("mcp.server.fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
