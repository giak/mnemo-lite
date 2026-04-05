"""
MCP Memory Tools

Tools for persistent memory storage: create, update, delete, search,
and consolidate memories.

EPIC-23 Story 23.3: Persistent memory storage for LLM interactions.
Provides CRUD operations with semantic embeddings and project scoping.

Consolidation (Expanse Apex §V):
    When too many memories accumulate (e.g., sys:history > 20),
    the agent summarizes older ones into a single consolidated memory
    and soft-deletes the originals.
"""

import time
import json
from typing import Optional, List, Dict, Any, Union
import uuid
from datetime import datetime, timezone

from mcp.server.fastmcp import Context
import structlog

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.elicitation import request_confirmation
from mnemo_mcp.models.memory_models import (
    MemoryType,
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    DeleteMemoryResponse,
)
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import EmbeddingServiceInterface
from mnemo_mcp.tools.project_tools import resolve_project_id

logger = structlog.get_logger()


class WriteMemoryTool(BaseMCPComponent):
    """
    Tool for creating new persistent memories.

    Creates a memory with semantic embedding for later retrieval.
    Supports project scoping, tags, and links to code chunks.

    Usage in Claude Desktop:
        "Remember that the user prefers async/await over callbacks"
        → Tool call: write_memory(
            title="User prefers async/await",
            content="User mentioned preferring async/await over callbacks...",
            memory_type="note",
            tags=["preferences", "python"]
        )

    Performance:
        - With embedding generation: ~80-120ms P95
        - Embedding failure (graceful degradation): ~30ms P95
    """

    def get_name(self) -> str:
        return "write_memory"

    async def execute(
        self,
        ctx: Context,
        title: str,
        content: str,
        memory_type: str = "note",
        tags: List[str] = None,
        author: Optional[str] = None,
        project_id: Optional[str] = None,
        related_chunks: List[str] = None,
        resource_links: List[Dict[str, str]] = None,
        embedding_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new persistent memory.

        Args:
            ctx: MCP context
            title: Short memory title (1-200 chars)
            content: Full memory content
            memory_type: Classification (note, decision, task, reference, conversation, investigation)
            tags: User-defined tags for filtering (optional)
            author: Optional author attribution (e.g., "Claude", "User")
            project_id: Project UUID or project name (e.g., "mnemolite")
                       If name provided, will be resolved to UUID (auto-creates if missing)
            related_chunks: Array of code chunk UUIDs to link (optional)
            resource_links: MCP resource links [{"uri": "...", "type": "..."}] (optional)
            embedding_source: Optional focused text for embedding computation (EPIC-24).
                             If provided, embedding is computed on this instead of title+content.
                             Recommended: 200-400 word structured summary with subject, themes, entities.

        Returns:
            Dict with id, title, memory_type, created_at, updated_at, embedding_generated

        Raises:
            ValueError: Invalid input parameters
        """
        start_time = time.time()

        try:
            # Validate input
            if not title or len(title) > 200:
                raise ValueError("Title must be 1-200 characters")

            if not content:
                raise ValueError("Content cannot be empty")

            # Parse memory_type enum
            try:
                memory_type_enum = MemoryType(memory_type)
            except ValueError:
                valid_types = [t.value for t in MemoryType]
                raise ValueError(
                    f"Invalid memory_type '{memory_type}'. Valid types: {', '.join(valid_types)}"
                )

            # Parse project_id UUID if provided
            project_uuid = None
            if project_id:
                try:
                    # Try to parse as UUID first (for backward compatibility)
                    project_uuid = uuid.UUID(project_id)
                except ValueError:
                    # Not a UUID - treat as project name and resolve
                    logger.debug(f"Resolving project name '{project_id}' to UUID")

                    # Get database connection from memory_repository's engine
                    async with self.memory_repository.engine.begin() as conn:
                        project_uuid = await resolve_project_id(
                            name=project_id,
                            conn=conn,
                            auto_create=True  # Auto-create projects as needed
                        )

                    logger.info(f"Resolved project '{project_id}' to UUID {project_uuid}")

            # Parse related_chunks UUIDs
            related_chunks_uuids = []
            if related_chunks:
                try:
                    related_chunks_uuids = [uuid.UUID(c) for c in related_chunks]
                except ValueError as e:
                    raise ValueError(f"Invalid related_chunks UUID: {e}")

            # Create MemoryCreate object
            memory_create = MemoryCreate(
                title=title,
                content=content,
                memory_type=memory_type_enum,
                tags=tags or [],
                author=author,
                project_id=project_uuid,
                related_chunks=related_chunks_uuids,
                resource_links=resource_links or [],
                embedding_source=embedding_source,
            )

            # Generate embedding (graceful degradation on failure)
            # OPTIMIZATION: Skip embedding for write_memory to avoid 10s cold start.
            # The embedding will be generated asynchronously by the worker.
            embedding = None
            embedding_generated = False

            if self.embedding_service:
                try:
                    # EPIC-24: Use embedding_source if provided, otherwise title+content
                    if embedding_source:
                        embedding_text = embedding_source
                    else:
                        embedding_text = f"{title}\n\n{content}"

                    embedding_raw = await self.embedding_service.generate_embedding(embedding_text)
                    # DualEmbeddingService returns {"text": [...], "code": [...]} — extract TEXT
                    embedding = embedding_raw.get("text") if isinstance(embedding_raw, dict) else embedding_raw
                    embedding_generated = True
                except Exception as e:
                    logger.warning(
                        "Embedding generation failed, proceeding without embedding",
                        error=str(e),
                        title=title
                    )
            else:
                logger.warning("No embedding service available, memory will have no embedding")

            # Save to database
            memory = await self.memory_repository.create(memory_create, embedding)

            # EPIC-28: Trigger async entity extraction (non-blocking)
            self._trigger_entity_extraction(memory)

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory created successfully",
                memory_id=str(memory.id),
                title=memory.title,
                memory_type=memory.memory_type.value,
                embedding_generated=embedding_generated,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            # Return lightweight response
            response = MemoryResponse(
                id=memory.id,
                title=memory.title,
                memory_type=memory.memory_type,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
                embedding_generated=embedding_generated,
                tags=memory.tags,
                author=memory.author,
                content_preview=memory.content[:200] if memory.content else None,
            )

            return response.model_dump(mode='json')

        except ValueError as e:
            logger.error("Validation error in write_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to create memory", error=str(e), title=title)
            raise RuntimeError(f"Failed to create memory: {e}") from e

    def _trigger_entity_extraction(self, memory: Any) -> None:
        """
        Push entity extraction request to Redis Stream for worker processing.
        
        Non-blocking: the worker handles extraction asynchronously.
        """
        try:
            import json as _json
            redis = self._services.get("redis")
            if redis is None:
                return

            payload = _json.dumps({
                "memory_id": str(memory.id),
                "title": memory.title,
                "content": memory.content,
                "memory_type": memory.memory_type.value if hasattr(memory.memory_type, "value") else str(memory.memory_type),
                "tags": memory.tags or [],
            })

            redis.xadd("entity:extraction", {"payload": payload})
        except Exception as e:
            logger.debug("entity_extraction_trigger_failed", error=str(e))


class UpdateMemoryTool(BaseMCPComponent):
    """
    Tool for updating existing memories (partial update).

    Updates one or more fields of an existing memory.
    Regenerates embedding if title or content changes.

    Usage in Claude Desktop:
        "Update that memory to add 'javascript' tag"
        → Tool call: update_memory(
            id="abc-123-...",
            tags=["preferences", "python", "javascript"]
        )

    Performance:
        - Without embedding regeneration: ~20-40ms P95
        - With embedding regeneration: ~80-120ms P95
    """

    def get_name(self) -> str:
        return "update_memory"

    async def execute(
        self,
        ctx: Context,
        id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
        related_chunks: Optional[List[str]] = None,
        resource_links: Optional[List[Dict[str, str]]] = None,
        embedding_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing memory (partial update).

        Args:
            ctx: MCP context
            id: Memory UUID to update
            title: Update title (optional)
            content: Update content (optional)
            memory_type: Update classification (optional)
            tags: Update tags - replaces existing (optional)
            author: Update author (optional)
            related_chunks: Update related code chunks - replaces existing (optional)
            resource_links: Update resource links - replaces existing (optional)
            embedding_source: Update focused text for embedding - triggers embedding regeneration (optional)

        Returns:
            Dict with id, updated_at, embedding_regenerated

        Raises:
            ValueError: Invalid input parameters
            RuntimeError: Memory not found or update failed
        """
        start_time = time.time()

        try:
            # Validate memory ID
            try:
                memory_uuid = uuid.UUID(id)
            except ValueError:
                raise ValueError(f"Invalid memory UUID: {id}")

            # Fetch existing memory first
            existing_memory = await self.memory_repository.get_by_id(str(memory_uuid))
            if not existing_memory:
                raise RuntimeError(f"Memory {id} not found or already deleted")

            # Parse memory_type if provided
            memory_type_enum = None
            if memory_type:
                try:
                    memory_type_enum = MemoryType(memory_type)
                except ValueError:
                    valid_types = [t.value for t in MemoryType]
                    raise ValueError(
                        f"Invalid memory_type '{memory_type}'. Valid types: {', '.join(valid_types)}"
                    )

            # Parse related_chunks UUIDs if provided
            related_chunks_uuids = None
            if related_chunks is not None:
                try:
                    related_chunks_uuids = [uuid.UUID(c) for c in related_chunks]
                except ValueError as e:
                    raise ValueError(f"Invalid related_chunks UUID: {e}")

            # Create MemoryUpdate object
            memory_update = MemoryUpdate(
                title=title,
                content=content,
                memory_type=memory_type_enum,
                tags=tags,
                author=author,
                related_chunks=related_chunks_uuids,
                resource_links=resource_links,
                embedding_source=embedding_source,
            )

            # Determine if embedding needs regeneration
            # EPIC-24: Also regenerate if embedding_source is explicitly provided
            needs_embedding_regeneration = (
                (title is not None and title != existing_memory.title) or
                (content is not None and content != existing_memory.content) or
                (embedding_source is not None)  # Always regenerate if new embedding_source provided
            )

            new_embedding = None
            embedding_regenerated = False

            if needs_embedding_regeneration and self.embedding_service:
                try:
                    # EPIC-24: Prioritize embedding_source for embedding generation
                    if embedding_source:
                        embedding_text = embedding_source
                        logger.info(
                            "Using new embedding_source for embedding regeneration",
                            memory_id=id,
                            embedding_source_len=len(embedding_source)
                        )
                    elif hasattr(existing_memory, 'embedding_source') and existing_memory.embedding_source:
                        # Use existing embedding_source if available
                        embedding_text = existing_memory.embedding_source
                        logger.info(
                            "Using existing embedding_source for embedding regeneration",
                            memory_id=id
                        )
                    else:
                        # Fall back to title+content
                        new_title = title if title is not None else existing_memory.title
                        new_content = content if content is not None else existing_memory.content
                        embedding_text = f"{new_title}\n\n{new_content}"
                        logger.info(
                            "Using title+content for embedding regeneration (no embedding_source)",
                            memory_id=id
                        )

                    new_embedding_raw = await self.embedding_service.generate_embedding(embedding_text)
                    # DualEmbeddingService returns {"text": [...], "code": [...]} — extract TEXT
                    new_embedding = new_embedding_raw.get("text") if isinstance(new_embedding_raw, dict) else new_embedding_raw
                    embedding_regenerated = True

                    logger.info(
                        "Embedding regenerated for updated memory",
                        memory_id=id,
                        embedding_dim=len(new_embedding) if new_embedding else 0,
                        used_embedding_source=embedding_source is not None
                    )
                except Exception as e:
                    logger.warning(
                        "Embedding regeneration failed, keeping old embedding",
                        error=str(e),
                        memory_id=id
                    )

            # Update in database
            updated_memory = await self.memory_repository.update(
                str(memory_uuid),
                memory_update,
                regenerate_embedding=embedding_regenerated,
                new_embedding=new_embedding
            )

            if not updated_memory:
                raise RuntimeError(f"Memory {id} not found or already deleted")

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory updated successfully",
                memory_id=id,
                embedding_regenerated=embedding_regenerated,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            return {
                "id": str(updated_memory.id),
                "title": updated_memory.title,
                "updated_at": updated_memory.updated_at.isoformat(),
                "embedding_regenerated": embedding_regenerated,
            }

        except ValueError as e:
            logger.error("Validation error in update_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to update memory", error=str(e), memory_id=id)
            raise RuntimeError(f"Failed to update memory: {e}") from e


class DeleteMemoryTool(BaseMCPComponent):
    """
    Tool for deleting memories (soft delete by default, hard delete with elicitation).

    Soft delete: Sets deleted_at timestamp (can be restored).
    Hard delete: Permanently removes from database (requires elicitation).

    ⚠️ ELICITATION FLOW:
        1. User calls delete_memory(id="abc-123") → Soft delete (reversible)
        2. User calls delete_memory(id="abc-123", permanent=True) → Triggers elicitation
        3. User confirms → Hard delete (irreversible)

    Usage in Claude Desktop:
        "Delete that memory about async patterns"
        → Tool call: delete_memory(id="abc-123")
        → Soft deleted (can be restored)

        "Delete that memory permanently"
        → Tool call: delete_memory(id="abc-123", permanent=True)
        → Elicitation: "⚠️ Permanently delete memory 'User prefers async/await'?"
        → User confirms → Hard deleted

    Performance:
        - Soft delete: ~15-30ms P95
        - Hard delete: ~20-40ms P95
    """

    def get_name(self) -> str:
        return "delete_memory"

    async def execute(
        self,
        ctx: Context,
        id: str,
        permanent: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete a memory (soft delete by default).

        Args:
            ctx: MCP context
            id: Memory UUID to delete
            permanent: If True, triggers elicitation for hard delete confirmation

        Returns:
            Dict with id, deleted_at, permanent, can_restore

        Raises:
            ValueError: Invalid UUID
            RuntimeError: Memory not found or deletion failed
        """
        start_time = time.time()

        try:
            # Validate memory ID
            try:
                memory_uuid = uuid.UUID(id)
            except ValueError:
                raise ValueError(f"Invalid memory UUID: {id}")

            # Fetch existing memory
            existing_memory = await self.memory_repository.get_by_id(str(memory_uuid))
            if not existing_memory:
                raise RuntimeError(f"Memory {id} not found")

            # Soft delete (default)
            if not permanent:
                success = await self.memory_repository.soft_delete(str(memory_uuid))

                if not success:
                    raise RuntimeError(f"Failed to soft delete memory {id}")

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory soft deleted",
                memory_id=id,
                title=existing_memory.title,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            response = DeleteMemoryResponse(
                id=memory_uuid,
                deleted_at=datetime.now(timezone.utc),
                permanent=False,
                can_restore=True,
            )

            return response.model_dump(mode='json')

            # Hard delete (requires elicitation - EPIC-23 Story 23.11)

            # Request user confirmation before permanent deletion
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
                logger.info(
                    "permanent_deletion_cancelled",
                    memory_id=id,
                    title=existing_memory.title
                )
                return DeleteMemoryResponse(
                    id=memory_uuid,
                    deleted_at=existing_memory.deleted_at,
                    permanent=False,
                    can_restore=True,
                    success=False,
                    message="Permanent deletion cancelled by user"
                ).model_dump(mode='json')

            # Verify memory is already soft deleted
            if existing_memory.deleted_at is None:
                raise ValueError(
                    "Memory must be soft deleted before permanent deletion. "
                    "Call delete_memory(id) first, then delete_memory(id, permanent=True)."
                )

            # Perform hard delete
            success = await self.memory_repository.delete_permanently(str(memory_uuid))

            if not success:
                raise RuntimeError(f"Failed to permanently delete memory {id}")

            elapsed_ms = (time.time() - start_time) * 1000

            logger.warning(
                "Memory permanently deleted",
                memory_id=id,
                title=existing_memory.title,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            response = DeleteMemoryResponse(
                id=memory_uuid,
                deleted_at=datetime.now(timezone.utc),
                permanent=True,
                can_restore=False,
            )

            return response.model_dump(mode='json')

        except ValueError as e:
            logger.error("Validation error in delete_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to delete memory", error=str(e), memory_id=id)
            raise RuntimeError(f"Failed to delete memory: {e}") from e


class SearchMemoryTool(BaseMCPComponent):
    """
    Tool for semantic search on memories.

    Searches memories using hybrid lexical + vector search.
    Returns ranked results with similarity scores.

    Usage:
        search_memory(query="Duclos ObsDelphi investigation")
        → Returns memories matching the query semantically
    """

    def get_name(self) -> str:
        return "search_memory"

    async def execute(
        self,
        ctx: Context,
        query: Optional[str] = None,
        memory_type: Optional[str] = None,
        tags: Optional[Union[str, List[str]]] = None,
        consumed: Optional[bool] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Semantic search on memories.

        Args:
            ctx: MCP context
            query: Search query (natural language). Optional if tags provided.
            memory_type: Filter by type (note, decision, task, reference, conversation, investigation)
            tags: Filter by tags — accepts string "sys:history" or list ["sys:history", "v15"]
            consumed: Filter by consumption status (None=all, True=consumed, False=fresh)
            lifecycle_state: Filter by lifecycle (None=all, "sealed", "candidate", "doubt", "summary")
            limit: Max results (1-50, default: 10)
            offset: Pagination offset (default: 0)

        Returns:
            Dict with memories list, pagination, and search metadata
        """
        # Normalize tags: accept string or list (tolerant to agent errors)
        if isinstance(tags, str):
            tags = [tags]
        if tags is not None:
            tags = [t.strip() for t in tags if t.strip()]

        start_time = time.time()

        logger.info(
            "search_memory.execute.start",
            query=query,
            limit=limit,
            offset=offset,
            memory_type=memory_type,
            tags=tags,
            has_services=self._services is not None,
            has_embedding_service=self.embedding_service is not None,
            has_hybrid_search=self.hybrid_memory_search_service is not None,
            has_memory_repo=self.memory_repository is not None,
        )

        try:
            # Validate inputs: query required UNLESS tags are provided (tag-only listing mode)
            query_stripped = (query or "").strip()
            if not query_stripped and not tags:
                raise ValueError("Query or tags is required — provide at least one")

            limit = max(1, min(50, limit))
            offset = max(0, offset)

            # Parse memory_type if provided
            memory_type_enum = None
            if memory_type:
                try:
                    memory_type_enum = MemoryType(memory_type)
                except ValueError:
                    valid_types = [t.value for t in MemoryType]
                    raise ValueError(
                        f"Invalid memory_type '{memory_type}'. Valid: {', '.join(valid_types)}"
                    )

            # Generate query embedding (graceful degradation if unavailable)
            # OPTIMIZATION: Skip embedding for tag-only searches — use lexical search only.
            # A query is considered "tag-only" if:
            #   1. It starts with "sys:" or "trace:" and is short (<50 chars), OR
            #   2. Tags filter is explicitly provided
            # This avoids 8-10s model load for simple tag lookups like "sys:protocol".
            query_embedding = None
            is_tag_query = query_stripped.startswith(('sys:', 'trace:')) and len(query_stripped) < 50
            is_tag_only = is_tag_query or bool(tags)

            # EPIC-32 Story 32.2: Check Redis cache for memory search
            redis = self._services.get("redis") if self._services else None
            if redis:
                try:
                    import hashlib as _hashlib
                    cache_params = {
                        "q": query_stripped,
                        "t": memory_type,
                        "tags": sorted(tags) if tags else [],
                        "c": consumed,
                        "ls": lifecycle_state,
                        "l": limit,
                        "o": offset,
                    }
                    cache_key = f"memsearch:{_hashlib.sha256(json.dumps(cache_params, sort_keys=True).encode()).hexdigest()[:16]}"
                    cached = await redis.get(cache_key)
                    if cached:
                        logger.info("search_memory.cache_hit", cache_key=cache_key)
                        return json.loads(cached)
                except Exception as e:
                    logger.warning(f"Memory search cache read failed: {e}")

            if not is_tag_only and self.embedding_service:
                try:
                    query_embedding_raw = await self.embedding_service.generate_embedding(query)
                    # DualEmbeddingService returns {"text": [...], "code": [...]} — extract TEXT
                    query_embedding = query_embedding_raw.get("text") if isinstance(query_embedding_raw, dict) else query_embedding_raw
                except Exception as e:
                    logger.warning(f"Embedding generation failed, falling back to tag-only search: {e}")

            embedding_ms = (time.time() - start_time) * 1000

            # Try hybrid search if available AND embedding exists
            if hasattr(self, 'hybrid_memory_search_service') and self.hybrid_memory_search_service and query_embedding:
                from mnemo_mcp.models.memory_models import MemoryFilters

                filters = MemoryFilters(
                    memory_type=memory_type_enum if memory_type_enum else None,
                    tags=tags or [],
                    consumed=consumed,
                    lifecycle_state=lifecycle_state,
                )

                # EPIC-32: Extract HL/LL keywords (deterministic, no LLM)
                keywords = None
                query_understanding = self._services.get("query_understanding_service")
                if query_understanding:
                    keywords = query_understanding.extract_keywords(query)

                response = await self.hybrid_memory_search_service.search(
                    query=query,
                    embedding=query_embedding,
                    keywords=keywords,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                )

                # Convert HybridResult to memory format
                memories = []
                from services.highlight_service import highlight_matches
                for m in response.results:
                    content_text = getattr(m, 'content', m.content_preview)
                    content_preview = content_text[:300] + "..." if len(content_text) > 300 else content_text
                    # EPIC-35 Story 35.1: Add highlighting snippets
                    highlights = highlight_matches(content_text, query, max_snippets=2) if query else []
                    memories.append({
                        "id": str(m.memory_id),
                        "title": m.title,
                        "content_preview": content_preview,
                        "highlights": highlights,
                        "memory_type": m.memory_type,
                        "tags": m.tags or [],
                        "similarity_score": m.rrf_score,
                        "created_at": m.created_at,
                    })

                result = {
                    "query": query,
                    "memories": memories,
                    "total": response.metadata.total_results,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(memories) < response.metadata.total_results,
                    "metadata": {
                        "search_mode": "hybrid",
                        "embedding_time_ms": round(embedding_ms, 2),
                        "execution_time_ms": round(response.metadata.execution_time_ms, 2),
                    }
                }
            else:
                # Fallback: tag-only or repository search (no hybrid service)
                from mnemo_mcp.models.memory_models import MemoryFilters
                effective_tags = tags if tags else ([query_stripped] if is_tag_query else [])
                fallback_filters = MemoryFilters(
                    memory_type=memory_type_enum,
                    tags=effective_tags,
                    consumed=consumed,
                    lifecycle_state=lifecycle_state,
                )

                if query_embedding:
                    memories_list, total_count = await self.memory_repository.search_by_vector(
                        vector=query_embedding,
                        filters=fallback_filters,
                        limit=limit,
                        offset=offset,
                        distance_threshold=0.7,
                    )
                    search_mode = "vector_only"
                else:
                    memories_list, total_count = await self.memory_repository.search_by_tags(
                        filters=fallback_filters,
                        limit=limit,
                        offset=offset,
                    )
                    search_mode = "tag_only"

                memories = []
                from services.highlight_service import highlight_matches
                for m in memories_list:
                    content_text = m.content[:300] + "..." if len(m.content) > 300 else m.content
                    highlights = highlight_matches(content_text, query, max_snippets=2) if query else []
                    memories.append({
                        "id": str(m.id),
                        "title": m.title,
                        "content_preview": content_text,
                        "highlights": highlights,
                        "memory_type": m.memory_type.value if hasattr(m.memory_type, 'value') else m.memory_type,
                        "tags": m.tags or [],
                        "similarity_score": getattr(m, 'similarity_score', None),
                        "created_at": m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
                    })

                result = {
                    "query": query,
                    "memories": memories,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(memories) < total_count,
                    "metadata": {
                        "search_mode": search_mode,
                        "embedding_time_ms": round(embedding_ms, 2),
                    }
                }

            elapsed_ms = (time.time() - start_time) * 1000

            # EPIC-32 Story 32.2: Write to Redis cache
            if redis:
                try:
                    # TTL depends on query type: tag-only=5min, natural=1min
                    ttl = 300 if is_tag_only else 60
                    await redis.setex(cache_key, ttl, json.dumps(result))
                    logger.debug(
                        "search_memory.cache_write",
                        cache_key=cache_key,
                        ttl=ttl,
                        is_tag_only=is_tag_only,
                    )
                except Exception as e:
                    logger.warning(f"Memory search cache write failed: {e}")

            logger.info(
                "search_memory.complete",
                query=query,
                count=len(result["memories"]),
                total=result["total"],
                elapsed_ms=round(elapsed_ms, 2),
                search_mode=result["metadata"].get("search_mode", "unknown"),
                is_tag_only=is_tag_only,
                cache_hit=cache_key is not None and redis is not None,
                tags=tags,
                memory_type=memory_type,
            )

            return result

        except ValueError as e:
            logger.error("Validation error in search_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to search memories", error=str(e), query=query)
            raise RuntimeError(f"Failed to search memories: {e}") from e


class ReadMemoryTool(BaseMCPComponent):
    """
    Tool for reading the complete content of a specific memory by ID.

    Usage in Claude Desktop:
        "Read the full content of memory abc-123"
        → Tool call: read_memory(id="abc-123-...")
        → Returns full memory details including complete content
    """

    def get_name(self) -> str:
        return "read_memory"

    async def execute(
        self,
        ctx: Context,
        id: str,
    ) -> Dict[str, Any]:
        """
        Read full content of a memory.

        Args:
            ctx: MCP context
            id: Memory UUID to read

        Returns:
            Dict with complete memory details including full content
        """
        start_time = time.time()

        try:
            # Validate memory ID
            try:
                memory_uuid = uuid.UUID(id)
            except ValueError:
                raise ValueError(f"Invalid memory UUID: {id}")

            # Fetch memory
            memory = await self.memory_repository.get_by_id(str(memory_uuid))
            
            if not memory:
                raise RuntimeError(f"Memory {id} not found or deleted")

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory read successfully",
                memory_id=id,
                title=memory.title,
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            response = MemoryResponse(
                id=memory.id,
                title=memory.title,
                memory_type=memory.memory_type,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
                embedding_generated=memory.embedding is not None,
                tags=memory.tags,
                author=memory.author,
                content_preview=memory.content,  # Return full content here too for backward compat
            )
            
            # Need to explicitly include full content as it's not in the base Response model
            result = response.model_dump(mode='json')
            result['content'] = memory.content
            
            return result

        except ValueError as e:
            logger.error("Validation error in read_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to read memory", error=str(e), memory_id=id)
            raise RuntimeError(f"Failed to read memory: {e}") from e


class ConsolidateMemoryTool(BaseMCPComponent):
    """
    Tool for consolidating multiple memories into a single summary.

    Used by agents (like Expanse) to compress accumulating history:
    - When sys:history count > 20, summarize oldest 10 into 1 consolidated
    - Creates new memory with summary content
    - Soft-deletes source memories
    - Tags consolidated memory with :summary suffix

    Workflow (2-step for LLM integration):
    1. Agent calls search_memory to find memories to consolidate
    2. Agent generates summary from the results
    3. Agent calls consolidate_memory with summary + source IDs
    """

    def get_name(self) -> str:
        return "consolidate_memory"

    async def execute(self, ctx: Context, **params) -> dict:
        """
        Consolidate multiple memories into a single summary memory.

        Args:
            title: Title for the consolidated memory
            summary: The consolidated content (LLM-generated summary)
            source_ids: List of memory UUIDs to consolidate (will be soft-deleted)
            tags: Tags for the consolidated memory (auto-adds :summary suffix to first tag)
            memory_type: Type for consolidated memory (default: note)
            author: Optional author attribution

        Returns:
            Dict with consolidated_memory (id, title), deleted_count, source_ids
        """
        title = params.get("title")
        summary = params.get("summary")
        source_ids = params.get("source_ids", [])
        tags = params.get("tags", [])
        memory_type = params.get("memory_type", "note")
        author = params.get("author")

        # Validation
        if not title or not title.strip():
            raise ValueError("title is required")
        if not summary or not summary.strip():
            raise ValueError("summary is required")
        if not source_ids or len(source_ids) < 2:
            raise ValueError("source_ids must contain at least 2 memory IDs to consolidate")

        try:
            repo = self.memory_repository
            embedding_svc = self.embedding_service

            if not repo:
                raise RuntimeError("MemoryRepository not available")

            # Auto-tag with :summary suffix on first tag
            consolidated_tags = list(tags)
            if consolidated_tags:
                base_tag = consolidated_tags[0]
                if not base_tag.endswith(":summary"):
                    consolidated_tags[0] = f"{base_tag}:summary"
            consolidated_tags.append("sys:consolidated")

            # Generate embedding for the summary
            embedding_text = f"{title}\n\n{summary}"
            embedding = None
            if embedding_svc:
                try:
                    embedding_raw = await embedding_svc.generate_embedding(embedding_text)
                    # P0-2 FIX: DualEmbeddingService returns dict, extract TEXT
                    embedding = embedding_raw.get("text") if isinstance(embedding_raw, dict) else embedding_raw
                except Exception as e:
                    logger.warning("Embedding generation failed for consolidation", error=str(e))

            # Create the consolidated memory
            memory_create = MemoryCreate(
                title=title,
                content=summary,
                memory_type=MemoryType(memory_type),
                tags=consolidated_tags,
                author=author or "consolidation",
            )

            consolidated = await repo.create(memory_create, embedding=embedding)

            # Soft-delete source memories
            deleted_count = 0
            for source_id in source_ids:
                try:
                    # Parse UUID
                    memory_uuid = uuid.UUID(source_id) if isinstance(source_id, str) else source_id
                    success = await repo.soft_delete(memory_uuid)
                    if success:
                        deleted_count += 1
                except (ValueError, Exception) as e:
                    logger.warning(
                        "Failed to soft-delete source memory during consolidation",
                        source_id=str(source_id),
                        error=str(e)
                    )

            result = {
                "consolidated_memory": {
                    "id": str(consolidated.id),
                    "title": consolidated.title,
                    "memory_type": consolidated.memory_type,
                    "tags": consolidated.tags,
                    "created_at": consolidated.created_at.isoformat(),
                },
                "deleted_count": deleted_count,
                "total_source_ids": len(source_ids),
                "source_ids": [str(sid) for sid in source_ids],
            }

            logger.info(
                "Memory consolidation completed",
                consolidated_id=str(consolidated.id),
                deleted=deleted_count,
                total=len(source_ids),
            )

            return result

        except ValueError as e:
            logger.error("Validation error in consolidate_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to consolidate memories", error=str(e))
            raise RuntimeError(f"Failed to consolidate memories: {e}") from e


class MarkConsumedTool(BaseMCPComponent):
    """
    Tool for marking memories as consumed by an agent process.

    Used by agents (like Expanse Dream) to mark memories as processed.
    Prevents re-processing and enables queries for fresh/unconsumed memories.

    Idempotent: re-marking an already consumed memory has no effect.

    Usage:
        # Dream Passe 1: process drifts, then mark them consumed
        drifts = search_memory(tags=["sys:drift"], consumed=False)
        ... process drifts ...
        mark_consumed(memory_ids=[d.id for d in drifts], consumed_by="dream_passe1")

        # Later: only get fresh drifts
        fresh = search_memory(tags=["sys:drift"], consumed=False)
    """

    def get_name(self) -> str:
        return "mark_consumed"

    async def execute(self, ctx: Context, **params) -> dict:
        """
        Mark memories as consumed.

        Args:
            memory_ids: List of memory UUIDs to mark as consumed
            consumed_by: Who consumed them (e.g., "dream_passe1", "boot", "manual")

        Returns:
            Dict with: marked (count), already_consumed (count), total_requested
        """
        memory_ids = params.get("memory_ids", [])
        consumed_by = params.get("consumed_by", "unknown")

        if not memory_ids:
            return {"marked": 0, "already_consumed": 0, "total_requested": 0}

        if not consumed_by or not consumed_by.strip():
            raise ValueError("consumed_by is required")

        try:
            engine = self._services.get("engine")
            if not engine:
                raise RuntimeError("Database engine not available")

            from sqlalchemy import text

            # Idempotent: only update memories that are NOT already consumed
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("""
                        UPDATE memories
                        SET consumed_at = NOW(), consumed_by = :consumed_by
                        WHERE id = ANY(:ids)
                          AND consumed_at IS NULL
                          AND deleted_at IS NULL
                    """),
                    {"consumed_by": consumed_by.strip(), "ids": memory_ids}
                )
                marked = result.rowcount

            already_consumed = len(memory_ids) - marked

            logger.info(
                "memories.mark_consumed",
                marked=marked,
                already_consumed=already_consumed,
                consumed_by=consumed_by,
            )

            return {
                "marked": marked,
                "already_consumed": already_consumed,
                "total_requested": len(memory_ids),
                "consumed_by": consumed_by,
            }

        except Exception as e:
            logger.error("Failed to mark memories consumed", error=str(e))
            raise RuntimeError(f"Failed to mark memories consumed: {e}") from e


class SystemSnapshotTool(BaseMCPComponent):
    """
    Tool for getting a system snapshot in a single call.

    Replaces 4 sequential boot queries with parallel fetches.
    Returns context groups + health metrics for agent boot.

    Usage (Expanse boot):
        snapshot = get_system_snapshot(repository="expanse")
        → Returns: core, patterns, extensions, profile, project
                    + health (drifts, traces, candidates, history_count)
    """

    def get_name(self) -> str:
        return "get_system_snapshot"

    async def execute(self, ctx: Context, **params) -> dict:
        """
        Get system snapshot in parallel queries.

        Args:
            repository: Repository/project name (default: "expanse")
            context_budget: Max tokens for context (default: 500)

        Returns:
            Dict with: core, patterns, extensions, profile, project, health
        """
        repository = params.get("repository", "expanse")
        context_budget = params.get("context_budget", 500)

        try:
            engine = self._services.get("engine")
            if not engine:
                raise RuntimeError("Database engine not available")

            import asyncio
            from sqlalchemy import text

            # P2-2 FIX: Each task creates its own connection for true parallelism
            # SQLAlchemy serializes queries on a shared connection
            async def fetch_group(engine, query_tag, limit):
                """Fetch memories matching a tag group (own connection)."""
                try:
                    async with engine.connect() as conn:
                        result = await conn.execute(
                            text("""
                                SELECT id::text, title, memory_type, tags, created_at::text
                                FROM memories
                                WHERE (:tag = ANY(tags) OR :tag2 = ANY(tags))
                                  AND deleted_at IS NULL
                                ORDER BY created_at DESC
                                LIMIT :limit
                            """),
                            {"tag": query_tag, "tag2": query_tag, "limit": limit}
                        )
                        rows = result.fetchall()
                        return [
                        {"id": r[0], "title": r[1], "type": r[2], "tags": r[3], "created_at": r[4]}
                        for r in rows
                    ]
                except Exception:
                    return []

            async def fetch_health(engine):
                """Fetch health metrics in one query (own connection)."""
                try:
                    async with engine.connect() as conn:
                        result = await conn.execute(text("""
                        SELECT
                            (SELECT COUNT(*) FROM memories WHERE 'sys:history' = ANY(tags) AND deleted_at IS NULL) as history_count,
                            (SELECT COUNT(*) FROM memories WHERE 'sys:drift' = ANY(tags) AND consumed_at IS NULL AND deleted_at IS NULL) as fresh_drifts,
                            (SELECT COUNT(*) FROM memories WHERE tags @> ARRAY['trace:fresh'] AND consumed_at IS NULL AND deleted_at IS NULL) as fresh_traces,
                            (SELECT COUNT(*) FROM memories WHERE 'sys:pattern:candidate' = ANY(tags) AND consumed_at IS NULL AND deleted_at IS NULL) as candidates_pending,
                            (SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL) as total_memories,
                            (SELECT COUNT(*) FROM memories WHERE 'sys:protocol' = ANY(tags) AND deleted_at IS NULL) as protocol_count,
                            (SELECT COUNT(*) FROM memories WHERE 'sys:trace' = ANY(tags) AND deleted_at IS NULL) as trace_count
                    """))
                    row = result.fetchone()
                    if row:
                        return {
                            "history_count": row[0],
                            "needs_consolidation": row[0] > 20,
                            "fresh_drifts": row[1],
                            "fresh_traces": row[2],
                            "candidates_pending": row[3],
                            "total_memories": row[4],
                            "protocol_count": row[5],
                            "trace_count": row[6],
                        }
                    return {"history_count": 0, "needs_consolidation": False, "fresh_drifts": 0, "fresh_traces": 0, "candidates_pending": 0, "total_memories": 0, "protocol_count": 0, "trace_count": 0}
                except Exception as e:
                    return {"error": str(e)}

            # Run all queries in parallel (each on its own connection)
            core_task = fetch_group(engine, "sys:core", 20)
            anchor_task = fetch_group(engine, "sys:anchor", 20)
            pattern_task = fetch_group(engine, "sys:pattern", 20)
            extension_task = fetch_group(engine, "sys:extension", 10)
            profile_task = fetch_group(engine, "sys:user:profile", 5)
            project_task = fetch_group(engine, f"sys:project:{repository}", 1)
            protocol_task = fetch_group(engine, "sys:protocol", 10)
            trace_task = fetch_group(engine, "sys:trace", 10)
            health_task = fetch_health(engine)

            core, anchors, patterns, extensions, profile, project, protocols, traces, health = await asyncio.gather(
                core_task, anchor_task, pattern_task, extension_task,
                profile_task, project_task, protocol_task, trace_task, health_task
            )

            # Merge core + anchors (deduplicate)
            seen_ids = set()
            merged_core = []
            for m in core + anchors:
                if m["id"] not in seen_ids:
                    seen_ids.add(m["id"])
                    merged_core.append(m)

            # Filter patterns to exclude candidates (sealed only)
            sealed_patterns = [p for p in patterns if "sys:pattern:candidate" not in (p.get("tags") or [])]
            candidates = [p for p in patterns if "sys:pattern:candidate" in (p.get("tags") or [])]

            result = {
                "core": merged_core,
                "patterns": sealed_patterns[:20],
                "candidates": candidates[:5],
                "extensions": extensions,
                "protocols": protocols,
                "traces": traces,
                "profile": profile,
                "project": project,
                "health": health,
                "budget": {
                    "allocated": context_budget,
                    "items_returned": len(merged_core) + len(sealed_patterns) + len(extensions) + len(protocols) + len(traces) + len(profile),
                }
            }

            logger.info(
                "system.snapshot",
                repository=repository,
                core=len(merged_core),
                patterns=len(sealed_patterns),
                extensions=len(extensions),
                protocols=len(protocols),
                traces=len(traces),
                drifts=health.get("fresh_drifts", 0),
                fresh_traces=health.get("fresh_traces", 0),
            )

            return result

        except Exception as e:
            logger.error("Failed to get system snapshot", error=str(e))
            raise RuntimeError(f"Failed to get system snapshot: {e}") from e



# Singleton instances for registration
write_memory_tool = WriteMemoryTool()
update_memory_tool = UpdateMemoryTool()
delete_memory_tool = DeleteMemoryTool()
search_memory_tool = SearchMemoryTool()
read_memory_tool = ReadMemoryTool()
consolidate_memory_tool = ConsolidateMemoryTool()
mark_consumed_tool = MarkConsumedTool()
# system_snapshot_tool defined after ConfigureDecayTool (line 1325)



class ConfigureDecayTool(BaseMCPComponent):
    """
    Tool for configuring tag-based decay rules.

    Replaces hardcoded DECAY_PRESETS with configurable per-tag rules.
    Supports auto-consolidation thresholds and priority boosts.

    Usage:
        configure_decay(tag_pattern="sys:history", decay_rate=0.05, auto_consolidate_threshold=20)
        configure_decay(tag_pattern="sys:core", decay_rate=0.0)  # No decay
    """

    def get_name(self) -> str:
        return "configure_decay"

    async def execute(self, ctx: Context, **params) -> dict:
        """Configure decay for a tag pattern."""
        tag_pattern = params.get("tag_pattern")
        decay_rate = params.get("decay_rate")
        auto_consolidate_threshold = params.get("auto_consolidate_threshold")
        priority_boost = params.get("priority_boost", 0.0)

        if not tag_pattern:
            raise ValueError("tag_pattern is required")
        if decay_rate is None:
            raise ValueError("decay_rate is required")
        if decay_rate < 0:
            raise ValueError("decay_rate must be >= 0")

        import math
        half_life = math.log(2) / decay_rate if decay_rate > 0 else None

        try:
            engine = self._services.get("engine")
            if not engine:
                raise RuntimeError("Database engine not available")

            from sqlalchemy import text

            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                        INSERT INTO memory_decay_config (tag_pattern, decay_rate, half_life_days, auto_consolidate_threshold, priority_boost, updated_at)
                        VALUES (:tag, :rate, :hl, :threshold, :boost, NOW())
                        ON CONFLICT (tag_pattern) DO UPDATE SET
                            decay_rate = EXCLUDED.decay_rate,
                            half_life_days = EXCLUDED.half_life_days,
                            auto_consolidate_threshold = EXCLUDED.auto_consolidate_threshold,
                            priority_boost = EXCLUDED.priority_boost,
                            updated_at = NOW()
                    """),
                    {
                        "tag": tag_pattern,
                        "rate": decay_rate,
                        "hl": int(half_life) if half_life else None,
                        "threshold": auto_consolidate_threshold,
                        "boost": priority_boost,
                    }
                )

            logger.info("decay.configured", tag=tag_pattern, rate=decay_rate, threshold=auto_consolidate_threshold)

            return {
                "tag_pattern": tag_pattern,
                "decay_rate": decay_rate,
                "half_life_days": int(half_life) if half_life else None,
                "auto_consolidate_threshold": auto_consolidate_threshold,
                "priority_boost": priority_boost,
            }

        except Exception as e:
            logger.error("Failed to configure decay", error=str(e))
            raise RuntimeError(f"Failed to configure decay: {e}") from e


system_snapshot_tool = SystemSnapshotTool()
configure_decay_tool = ConfigureDecayTool()
