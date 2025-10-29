"""
MCP Configuration Tools (EPIC-23 Story 23.7).

Tools for project management and configuration.
"""

import structlog
from mcp.server.fastmcp import Context
from sqlalchemy import text

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.elicitation import request_confirmation
from mnemo_mcp.models.config_models import (
    SwitchProjectRequest,
    SwitchProjectResponse,
)

logger = structlog.get_logger()


class SwitchProjectTool(BaseMCPComponent):
    """
    Tool to switch the active project/repository context.

    Changes the current project context for all subsequent MCP operations
    (search, indexing, graph queries). The active project is stored in
    MCP session state and persists for the duration of the session.

    NOTE: Uses `repository` TEXT field from code_chunks table as project identifier.
          No `projects` table exists yet (pragmatic decision for Story 23.7).
          Future: Normalize with `projects` table in EPIC-24.
    """

    def get_name(self) -> str:
        return "switch_project"

    def get_description(self) -> str:
        return (
            "Switch the active project/repository for code search and indexing. "
            "Changes the context for all subsequent operations. "
            "The project must be indexed first using index_project tool."
        )

    async def execute(
        self,
        ctx: Context,
        request: SwitchProjectRequest
    ) -> SwitchProjectResponse:
        """
        Switch active project.

        Args:
            ctx: MCP context (for session state)
            request: Switch project request with repository name

        Returns:
            SwitchProjectResponse with project statistics

        Raises:
            ValueError: If repository not found or database unavailable
        """
        logger.info("switch_project.start", repository=request.repository)

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
                logger.info(
                    "switch_project.cancelled",
                    repository=request.repository
                )
                return SwitchProjectResponse(
                    success=False,
                    message="Project switch cancelled by user",
                    repository=request.repository,
                    indexed_files=0,
                    total_chunks=0,
                    languages=[]
                )

        # Get database engine
        engine = self.engine
        if not engine:
            logger.error("switch_project.no_engine")
            raise ValueError("Database engine not available")

        # Query database for project statistics
        async with engine.connect() as conn:
            query = text("""
                SELECT
                    repository,
                    COUNT(DISTINCT file_path) as indexed_files,
                    COUNT(*) as total_chunks,
                    MAX(created_at) as last_indexed,
                    ARRAY_AGG(DISTINCT language) FILTER (WHERE language IS NOT NULL) as languages
                FROM code_chunks
                WHERE TRIM(LOWER(repository)) = TRIM(LOWER(:repository))
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

            # Store in MCP session state
            # Key: "current_repository" (string)
            # Scope: Per-client session (thread-local or connection-specific)
            # Lifetime: Until session ends or switched again
            ctx.session.set("current_repository", row.repository)

            logger.info(
                "switch_project.success",
                repository=row.repository,
                indexed_files=row.indexed_files,
                total_chunks=row.total_chunks
            )

            return SwitchProjectResponse(
                success=True,
                message=f"Switched to repository: {row.repository}",
                repository=row.repository,
                indexed_files=row.indexed_files,
                total_chunks=row.total_chunks,
                languages=row.languages or [],
                last_indexed=(
                    row.last_indexed.isoformat() if row.last_indexed else None
                )
            )


# Singleton instance for registration
switch_project_tool = SwitchProjectTool()
