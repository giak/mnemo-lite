"""
MCP Memory Resources

Resources for reading memories: get by ID, list, and semantic search.

EPIC-23 Story 23.3: Persistent memory storage read operations.
Provides read-only access to memories via MCP Resources.
"""

import time
import json
import hashlib
from typing import Optional, Dict, Any
from urllib.parse import unquote, parse_qs, urlparse
import uuid

from mcp.server.fastmcp import Context
import structlog
from datetime import datetime

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.memory_models import (
    Memory,
    MemoryListResponse,
    MemorySearchResponse,
    PaginationMetadata,
    MemoryFilters,
    MemoryType,
)
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import EmbeddingServiceInterface

logger = structlog.get_logger()


class GetMemoryResource(BaseMCPComponent):
    """
    Resource for retrieving a single memory by UUID.

    URI: memories://get/{id}

    Usage in Claude Desktop:
        Access "memories://get/abc-123-..." to retrieve memory with ID

    Returns:
        Complete Memory object with all fields (including embedding)

    Performance:
        - No caching (always fresh data)
        - ~10-20ms P95
    """

    def get_name(self) -> str:
        return "memories://get"

    async def get(self, ctx: Context, uri: str) -> Dict[str, Any]:
        """
        Get a single memory by UUID.

        Args:
            ctx: MCP context (unused for resources)
            uri: Resource URI (e.g., "memories://get/abc-123")

        Returns:
            Memory object as dict, or error dict if not found

        Raises:
            ValueError: Invalid UUID format
            RuntimeError: Memory not found
        """
        start_time = time.time()

        try:
            # Extract ID from URI: "memories://get/{id}"
            parts = uri.split("/")
            if len(parts) < 4:
                raise ValueError(f"Invalid URI format: {uri}. Expected memories://get/{{id}}")

            memory_id_str = parts[-1]

            # Validate UUID
            try:
                memory_uuid = uuid.UUID(memory_id_str)
            except ValueError:
                raise ValueError(f"Invalid memory UUID: {memory_id_str}")

            # Fetch from database
            memory = await self.memory_repository.get_by_id(str(memory_uuid))

            if not memory:
                raise RuntimeError(f"Memory {memory_id_str} not found or deleted")

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory retrieved",
                memory_id=memory_id_str,
                title=memory.title,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            return memory.model_dump(mode='json')

        except (ValueError, RuntimeError) as e:
            logger.error("Failed to get memory", error=str(e), uri=uri)
            raise

        except Exception as e:
            logger.error("Unexpected error in get_memory", error=str(e), uri=uri)
            raise RuntimeError(f"Failed to get memory: {e}") from e


class ListMemoriesResource(BaseMCPComponent):
    """
    Resource for listing memories with filters and pagination.

    URI: memories://list?project_id={uuid}&memory_type={type}&tags={tag1,tag2}&limit={n}&offset={n}

    Query Parameters:
        - project_id: UUID (optional, filter by project)
        - memory_type: note|decision|task|reference|conversation (optional)
        - tags: comma-separated (optional, e.g., "python,async")
        - author: string (optional)
        - limit: 1-100 (default 10)
        - offset: pagination offset (default 0)
        - include_deleted: true|false (default false)

    Usage in Claude Desktop:
        Access "memories://list?tags=python&limit=5" to list Python-tagged memories

    Returns:
        MemoryListResponse with memories list and pagination metadata
        (Embeddings excluded for bandwidth savings)

    Caching:
        - Redis L2 cache, 1-minute TTL
        - Cache key includes all query parameters

    Performance:
        - Cached: <5ms P95
        - Uncached: ~20-50ms P95
    """

    def get_name(self) -> str:
        return "memories://list"

    async def get(self, ctx: Context, uri: str) -> Dict[str, Any]:
        """
        List memories with optional filters.

        Args:
            ctx: MCP context (unused for resources)
            uri: Resource URI with query params

        Returns:
            MemoryListResponse as dict

        Raises:
            ValueError: Invalid query parameters
        """
        start_time = time.time()

        try:
            # Check cache first
            cache_key = f"memory_list:{hashlib.sha256(uri.encode()).hexdigest()}"

            if self.redis_client:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.info("Memory list cache hit", uri=uri)
                    return json.loads(cached)

            # Parse query parameters
            params = self._parse_query_params(uri)

            # Build filters
            filters = MemoryFilters(
                project_id=uuid.UUID(params["project_id"]) if params.get("project_id") else None,
                memory_type=MemoryType(params["memory_type"]) if params.get("memory_type") else None,
                tags=params.get("tags", "").split(",") if params.get("tags") else [],
                author=params.get("author"),
                include_deleted=params.get("include_deleted", "false").lower() == "true"
            )

            limit = min(int(params.get("limit", 10)), 100)
            offset = int(params.get("offset", 0))

            # Query database
            memories, total_count = await self.memory_repository.list_memories(
                filters=filters,
                limit=limit,
                offset=offset
            )

            # Build response
            response = MemoryListResponse(
                memories=memories,
                pagination=PaginationMetadata(
                    limit=limit,
                    offset=offset,
                    total=total_count,
                    has_more=offset + len(memories) < total_count
                )
            )

            result = response.model_dump(mode='json')

            # Cache result (1 min TTL)
            if self.redis_client:
                await self.redis_client.set(cache_key, json.dumps(result), ex=60)

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memories listed",
                count=len(memories),
                total=total_count,
                limit=limit,
                offset=offset,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            return result

        except ValueError as e:
            logger.error("Invalid parameters in list_memories", error=str(e), uri=uri)
            raise

        except Exception as e:
            logger.error("Failed to list memories", error=str(e), uri=uri)
            raise RuntimeError(f"Failed to list memories: {e}") from e


class SearchMemoriesResource(BaseMCPComponent):
    """
    Resource for hybrid search of memories (lexical + vector + RRF fusion).

    EPIC-24 P0: Combines pg_trgm trigram similarity and pgvector embeddings
    using Reciprocal Rank Fusion (RRF) for optimal retrieval.

    URI: memories://search/{query}?limit={n}&offset={n}&project_id={uuid}&...

    Path Parameter:
        - query: Search text (URL-encoded)

    Query Parameters:
        - limit: 1-50 (default 5, smaller than code search)
        - offset: pagination offset (default 0)
        - project_id: UUID (optional, filter by project)
        - memory_type: filter by type (optional)
        - tags: comma-separated tags (optional)
        - enable_lexical: true|false (default true) - enable trigram search
        - enable_vector: true|false (default true) - enable vector search
        - lexical_weight: 0.0-1.0 (default 0.4) - weight for lexical in RRF
        - vector_weight: 0.0-1.0 (default 0.6) - weight for vector in RRF

    Usage in Claude Desktop:
        Access "memories://search/Bardella?limit=5" for hybrid search
        Access "memories://search/Bardella?enable_vector=false" for lexical-only

    Returns:
        MemorySearchResponse with ranked memories + RRF scores

    Caching:
        - Redis L2 cache, 5-minute TTL
        - Cache key includes query + all parameters

    Performance:
        - Cached: <10ms P95
        - Uncached: ~100-200ms P95 (parallel lexical + vector)
        - Lexical catches exact matches (proper nouns like "Bardella")
        - Vector catches semantic similarity (synonyms, paraphrases)
    """

    def get_name(self) -> str:
        return "memories://search"

    async def get(self, ctx: Context, uri: str) -> Dict[str, Any]:
        """
        Search memories using hybrid search (lexical + vector + RRF).

        Args:
            ctx: MCP context (unused for resources)
            uri: Resource URI with query in path and params in query string

        Returns:
            MemorySearchResponse as dict with ranked memories

        Raises:
            ValueError: Invalid query parameters
            RuntimeError: Search failed
        """
        start_time = time.time()

        try:
            # Check cache first
            cache_key = f"memory_search:{hashlib.sha256(uri.encode()).hexdigest()}"

            if self.redis_client:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.info("Memory search cache hit", uri=uri)
                    return json.loads(cached)

            # Extract query from URI: "memories://search/{query}?..."
            parts = uri.split("?")
            path = parts[0]
            query_text = unquote(path.split("/")[-1])

            if not query_text or len(query_text) > 500:
                raise ValueError("Query must be 1-500 characters")

            # Parse query parameters
            params = self._parse_query_params(uri)

            # Build filters
            filters = MemoryFilters(
                project_id=uuid.UUID(params["project_id"]) if params.get("project_id") else None,
                memory_type=MemoryType(params["memory_type"]) if params.get("memory_type") else None,
                tags=params.get("tags", "").split(",") if params.get("tags") else []
            )

            limit = min(int(params.get("limit", 5)), 50)
            offset = int(params.get("offset", 0))

            # EPIC-24: Hybrid search parameters
            enable_lexical = params.get("enable_lexical", "true").lower() == "true"
            enable_vector = params.get("enable_vector", "true").lower() == "true"
            lexical_weight = float(params.get("lexical_weight", 0.4))
            vector_weight = float(params.get("vector_weight", 0.6))

            # Validate weights
            if not (0.0 <= lexical_weight <= 1.0):
                raise ValueError("lexical_weight must be between 0.0 and 1.0")
            if not (0.0 <= vector_weight <= 1.0):
                raise ValueError("vector_weight must be between 0.0 and 1.0")

            # Generate query embedding for vector search
            # EPIC-24 P1: Use text_type=QUERY for v2 model compatibility
            query_embedding = None
            embedding_ms = 0.0

            if enable_vector and self.embedding_service:
                embedding_start = time.time()
                # Use embed_query for search queries (important for v2 models)
                if hasattr(self.embedding_service, 'embed_query'):
                    query_embedding = await self.embedding_service.embed_query(query_text)
                else:
                    query_embedding = await self.embedding_service.generate_embedding(query_text)
                embedding_ms = (time.time() - embedding_start) * 1000

            # Use hybrid search service if available
            if self.hybrid_memory_search_service:
                response = await self.hybrid_memory_search_service.search(
                    query=query_text,
                    embedding=query_embedding,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                    enable_lexical=enable_lexical,
                    enable_vector=enable_vector and query_embedding is not None,
                    lexical_weight=lexical_weight,
                    vector_weight=vector_weight,
                )

                # Convert hybrid results to Memory objects for response
                memories = []
                for hr in response.results:
                    # Parse datetime string from PostgreSQL (format: '2025-11-26 07:08:52.399567+00')
                    # PostgreSQL ::text cast produces +00 instead of +00:00, so we fix it
                    created_at_str = hr.created_at
                    if isinstance(created_at_str, str):
                        # Fix timezone format: +00 -> +00:00
                        if created_at_str.endswith('+00'):
                            created_at_str = created_at_str + ':00'
                        elif created_at_str.endswith('-00'):
                            created_at_str = created_at_str + ':00'
                        created_at_dt = datetime.fromisoformat(created_at_str)
                    else:
                        created_at_dt = created_at_str

                    # Build Memory object from hybrid result
                    memory = Memory(
                        id=uuid.UUID(hr.memory_id),
                        title=hr.title,
                        content=hr.content_preview,  # Preview only for search results
                        memory_type=MemoryType(hr.memory_type),
                        tags=hr.tags,
                        created_at=created_at_dt,
                        updated_at=created_at_dt,  # Use created_at as fallback for search results
                        author=hr.author,
                        similarity_score=hr.rrf_score,  # Use RRF score as similarity
                    )
                    memories.append(memory)

                # Build response with hybrid metadata
                result_response = MemorySearchResponse(
                    query=query_text,
                    memories=memories,
                    pagination=PaginationMetadata(
                        limit=limit,
                        offset=offset,
                        total=response.metadata.total_results,
                        has_more=offset + len(memories) < response.metadata.total_results
                    ),
                    metadata={
                        "search_mode": "hybrid",
                        "embedding_model": "nomic-embed-text-v1.5",
                        "embedding_time_ms": f"{embedding_ms:.2f}",
                        "lexical_enabled": response.metadata.lexical_enabled,
                        "vector_enabled": response.metadata.vector_enabled,
                        "lexical_weight": response.metadata.lexical_weight,
                        "vector_weight": response.metadata.vector_weight,
                        "lexical_count": response.metadata.lexical_count,
                        "vector_count": response.metadata.vector_count,
                        "execution_time_ms": f"{response.metadata.execution_time_ms:.2f}",
                    }
                )

            else:
                # Fallback to vector-only search (original behavior)
                if not self.embedding_service or not query_embedding:
                    raise RuntimeError("Embedding service not available")

                memories, total_count = await self.memory_repository.search_by_vector(
                    vector=query_embedding,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                    distance_threshold=0.7  # Legacy threshold
                )

                result_response = MemorySearchResponse(
                    query=query_text,
                    memories=memories,
                    pagination=PaginationMetadata(
                        limit=limit,
                        offset=offset,
                        total=total_count,
                        has_more=offset + len(memories) < total_count
                    ),
                    metadata={
                        "search_mode": "vector_only",
                        "embedding_model": "nomic-embed-text-v1.5",
                        "embedding_time_ms": f"{embedding_ms:.2f}",
                        "fallback_reason": "hybrid_service_unavailable"
                    }
                )

            result = result_response.model_dump(mode='json')

            # Cache result (5 min TTL)
            if self.redis_client:
                await self.redis_client.set(cache_key, json.dumps(result), ex=300)

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory search completed",
                query=query_text,
                count=len(result_response.memories),
                search_mode=result_response.metadata.get("search_mode", "unknown"),
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            return result

        except ValueError as e:
            logger.error("Invalid parameters in search_memories", error=str(e), uri=uri)
            raise

        except Exception as e:
            logger.error("Failed to search memories", error=str(e), uri=uri)
            raise RuntimeError(f"Failed to search memories: {e}") from e


# Singleton instances for registration
get_memory_resource = GetMemoryResource()
list_memories_resource = ListMemoriesResource()
search_memories_resource = SearchMemoriesResource()
