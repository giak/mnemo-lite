"""
MCP Configuration Resources (EPIC-23 Story 23.7).

Resources for project listing and language configuration.
"""

import structlog
from typing import Optional
from mcp.server.fastmcp import Context
from sqlalchemy import text

from mnemo_mcp.base import BaseMCPComponent
from mnemo_mcp.models.config_models import (
    ProjectListItem,
    ProjectsListResponse,
    LanguageInfo,
    SupportedLanguagesResponse,
)
from config.languages import SUPPORTED_LANGUAGES

logger = structlog.get_logger()


class ListProjectsResource(BaseMCPComponent):
    """
    Resource to list all indexed projects with statistics.

    Returns aggregated statistics from code_chunks table grouped by repository.
    Marks the currently active project (from session state) with is_active=True.

    URI: projects://list

    NOTE: Uses `repository` TEXT field from code_chunks table as project identifier.
          No `projects` table exists yet (pragmatic decision for Story 23.7).
          Future: Normalize with `projects` table in EPIC-24.
    """

    def get_name(self) -> str:
        return "projects://list"

    def get_description(self) -> str:
        return (
            "List all indexed projects with statistics "
            "(files, chunks, languages, last indexed). "
            "Marks the currently active project."
        )

    async def get(self, ctx: Optional[Context] = None) -> ProjectsListResponse:
        """
        List all projects.

        Args:
            ctx: MCP context (for session state) - optional, None if unavailable

        Returns:
            ProjectsListResponse with project list and active marker
        """
        logger.info("list_projects.start")

        # Get active repository from session state (if context available)
        active_repository = None
        if ctx:
            active_repository = ctx.session.get("current_repository")
        logger.debug("list_projects.active_repository", repository=active_repository)

        # Get database engine
        engine = self.engine
        if not engine:
            logger.error("list_projects.no_engine")
            # Return empty list if no engine
            return ProjectsListResponse(
                projects=[],
                total=0,
                active_repository=active_repository
            )

        # Query database for all projects
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

            # Build project list with active marker
            projects = [
                ProjectListItem(
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


class SupportedLanguagesResource(BaseMCPComponent):
    """
    Resource exposing supported programming languages.

    Returns list of languages with file extensions, Tree-sitter grammars,
    and embedding models. Uses centralized configuration from config/languages.py.

    URI: config://languages

    This resource is useful for:
    - Documentation (what can MnemoLite index?)
    - Clients validating language support
    - Building language-specific UIs
    """

    def get_name(self) -> str:
        return "config://languages"

    def get_description(self) -> str:
        return (
            "Get list of programming languages supported by MnemoLite, "
            "including file extensions and Tree-sitter grammars."
        )

    async def get(self, ctx: Optional[Context] = None) -> SupportedLanguagesResponse:
        """
        Get supported languages.

        Args:
            ctx: MCP context (optional, not used by this resource)

        Returns:
            SupportedLanguagesResponse with language list
        """
        logger.info("supported_languages.start")

        # Convert LanguageConfig to LanguageInfo Pydantic models
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


# Singleton instance for registration
supported_languages_resource = SupportedLanguagesResource()
