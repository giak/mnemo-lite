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
    ) -> Dict[str, Any]:
        """
        Create a new persistent memory.

        Args:
            ctx: MCP context
            title: Short memory title (1-200 chars)
            content: Full memory content
            memory_type: Classification (note, decision, task, reference, conversation)
            tags: User-defined tags for filtering (optional)
            author: Optional author attribution (e.g., "Claude", "User")
            project_id: Project UUID or project name (e.g., "mnemolite")
                       If name provided, will be resolved to UUID (auto-creates if missing)
            related_chunks: Array of code chunk UUIDs to link (optional)
            resource_links: MCP resource links [{"uri": "...", "type": "..."}] (optional)

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
            )

            # Generate embedding (graceful degradation on failure)
            embedding = None
            embedding_generated = False

            if self.embedding_service:
                try:
                    # Combine title + content for embedding
                    embedding_text = f"{title}\n\n{content}"
                    embedding = await self.embedding_service.generate_embedding(embedding_text)
                    embedding_generated = True
                    logger.info(
                        "Embedding generated for memory",
                        title=title,
                        embedding_dim=len(embedding) if embedding else 0
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
            )

            # Determine if embedding needs regeneration
            needs_embedding_regeneration = (title is not None and title != existing_memory.title) or \
                                           (content is not None and content != existing_memory.content)

            new_embedding = None
            embedding_regenerated = False

            if needs_embedding_regeneration and self.embedding_service:
                try:
                    # Use new values if provided, else keep existing
                    new_title = title if title is not None else existing_memory.title
                    new_content = content if content is not None else existing_memory.content

                    embedding_text = f"{new_title}\n\n{new_content}"
                    new_embedding = await self.embedding_service.generate_embedding(embedding_text)
                    embedding_regenerated = True

                    logger.info(
                        "Embedding regenerated for updated memory",
                        memory_id=id,
                        embedding_dim=len(new_embedding) if new_embedding else 0
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


# Singleton instances for registration
write_memory_tool = WriteMemoryTool()
update_memory_tool = UpdateMemoryTool()
delete_memory_tool = DeleteMemoryTool()
