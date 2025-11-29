"""
MCP Memory Tools

Tools for persistent memory storage: create, update, and delete memories.

EPIC-23 Story 23.3: Persistent memory storage for LLM interactions.
Provides CRUD operations with semantic embeddings and project scoping.
"""

import time
from typing import Optional, List, Dict, Any
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
            embedding = None
            embedding_generated = False

            if self.embedding_service:
                try:
                    # EPIC-24: Use embedding_source if provided, otherwise title+content
                    if embedding_source:
                        embedding_text = embedding_source
                        logger.info(
                            "Using embedding_source for embedding generation",
                            title=title,
                            embedding_source_len=len(embedding_source)
                        )
                    else:
                        embedding_text = f"{title}\n\n{content}"
                        logger.info(
                            "Using title+content for embedding generation (no embedding_source)",
                            title=title,
                            content_len=len(content)
                        )

                    embedding = await self.embedding_service.generate_embedding(embedding_text)
                    embedding_generated = True
                    logger.info(
                        "Embedding generated for memory",
                        title=title,
                        embedding_dim=len(embedding) if embedding else 0,
                        used_embedding_source=embedding_source is not None
                    )
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

                    new_embedding = await self.embedding_service.generate_embedding(embedding_text)
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
        query: str,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Semantic search on memories.

        Args:
            ctx: MCP context
            query: Search query (natural language)
            memory_type: Filter by type (note, decision, task, reference, conversation, investigation)
            tags: Filter by tags (optional)
            limit: Max results (1-50, default 10)
            offset: Pagination offset (default 0)

        Returns:
            Dict with memories list, pagination, and search metadata
        """
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
            # Validate inputs
            if not query or len(query.strip()) == 0:
                raise ValueError("Query cannot be empty")

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

            # Generate query embedding
            if not self.embedding_service:
                raise RuntimeError("Embedding service not available")

            query_embedding = await self.embedding_service.generate_embedding(query)

            embedding_ms = (time.time() - start_time) * 1000

            # Try hybrid search if available
            if hasattr(self, 'hybrid_memory_search_service') and self.hybrid_memory_search_service:
                from mnemo_mcp.models.memory_models import MemoryFilters

                filters = MemoryFilters(
                    memory_type=memory_type_enum if memory_type_enum else None,
                    tags=tags or [],
                )

                response = await self.hybrid_memory_search_service.search(
                    query=query,
                    embedding=query_embedding,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                )

                # Convert HybridResult to memory format
                memories = []
                for hr in response.results:
                    memories.append({
                        "id": str(hr.memory_id),
                        "title": hr.title,
                        "content_preview": hr.content_preview,
                        "memory_type": hr.memory_type,
                        "tags": hr.tags or [],
                        "similarity_score": hr.rrf_score,
                        "created_at": hr.created_at,
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
                # Fallback to vector-only search
                filters = {}
                if memory_type_enum:
                    filters["memory_type"] = memory_type_enum
                if tags:
                    filters["tags"] = tags

                memories_list, total_count = await self.memory_repository.search_by_vector(
                    vector=query_embedding,
                    filters=filters if filters else None,
                    limit=limit,
                    offset=offset,
                    distance_threshold=0.7
                )

                memories = []
                for m in memories_list:
                    memories.append({
                        "id": str(m.id),
                        "title": m.title,
                        "content_preview": m.content[:300] + "..." if len(m.content) > 300 else m.content,
                        "memory_type": m.memory_type.value if hasattr(m.memory_type, 'value') else m.memory_type,
                        "tags": m.tags or [],
                        "similarity_score": m.similarity_score if hasattr(m, 'similarity_score') else None,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    })

                result = {
                    "query": query,
                    "memories": memories,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(memories) < total_count,
                    "metadata": {
                        "search_mode": "vector_only",
                        "embedding_time_ms": round(embedding_ms, 2),
                    }
                }

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Memory search completed",
                query=query,
                count=len(result["memories"]),
                elapsed_ms=f"{elapsed_ms:.2f}"
            )

            return result

        except ValueError as e:
            logger.error("Validation error in search_memory", error=str(e))
            raise

        except Exception as e:
            logger.error("Failed to search memories", error=str(e), query=query)
            raise RuntimeError(f"Failed to search memories: {e}") from e


# Singleton instances for registration
write_memory_tool = WriteMemoryTool()
update_memory_tool = UpdateMemoryTool()
delete_memory_tool = DeleteMemoryTool()
search_memory_tool = SearchMemoryTool()
