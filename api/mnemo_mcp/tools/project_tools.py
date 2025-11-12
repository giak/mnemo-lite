"""
Project resolution utilities for MnemoLite.

Provides functions to resolve project names to UUIDs with optional auto-creation,
enabling transparent project management across the system.
"""

import uuid
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def resolve_project_id(
    name: str,
    conn: AsyncConnection,
    auto_create: bool = True
) -> uuid.UUID:
    """
    Resolve project name to UUID with optional auto-creation.

    This function enables transparent project resolution throughout the system.
    When a project name (e.g., "mnemolite") is provided, it's automatically
    resolved to the corresponding UUID from the projects table.

    Args:
        name: Project name (e.g., "mnemolite", "Serena")
              Case-insensitive, will be normalized to lowercase
        conn: Database connection (must support transactions)
        auto_create: If True, create project if not found (default: True)
                    If False, raise ValueError if project not found

    Returns:
        UUID: Project UUID from projects table

    Raises:
        ValueError: If project not found and auto_create=False

    Examples:
        >>> # Auto-create enabled (default)
        >>> project_id = await resolve_project_id("mnemolite", conn)
        >>> # Returns UUID, creates project if missing

        >>> # Strict mode (no auto-create)
        >>> project_id = await resolve_project_id("mnemolite", conn, auto_create=False)
        >>> # Returns UUID or raises ValueError

    Notes:
        - Project names are normalized to lowercase for consistency
        - Only active projects (status='active') are returned
        - Auto-created projects use name.title() as display_name
        - All auto-creations are logged at WARNING level for visibility
    """
    name_lower = name.lower().strip()

    if not name_lower:
        raise ValueError("Project name cannot be empty")

    # Try to find existing active project
    result = await conn.execute(
        text("""
            SELECT id FROM projects
            WHERE name = :name AND status = 'active'
        """),
        {"name": name_lower}
    )
    row = result.fetchone()

    if row:
        logger.debug(f"Resolved project '{name_lower}' to UUID {row.id}")
        return row.id

    # Auto-create if enabled
    if auto_create:
        logger.warning(
            f"Auto-creating project: {name_lower} "
            f"(This is normal for first use, but check for typos)"
        )

        project_id = uuid.uuid4()

        # Infer display_name from name (capitalize each word)
        # "mnemolite" → "Mnemolite"
        # "my-project" → "My-Project"
        display_name = name_lower.replace('-', ' ').replace('_', ' ').title()

        await conn.execute(
            text("""
                INSERT INTO projects (id, name, display_name, status)
                VALUES (:id, :name, :display_name, 'active')
            """),
            {
                "id": project_id,
                "name": name_lower,
                "display_name": display_name
            }
        )
        # Note: Caller must commit transaction

        logger.info(f"Created project: {name_lower} (UUID: {project_id})")
        return project_id

    # Strict mode: fail if not found
    raise ValueError(
        f"Project '{name_lower}' not found in database. "
        f"Create it manually or enable auto_create=True"
    )


async def get_project_by_name(
    name: str,
    conn: AsyncConnection,
    include_archived: bool = False
) -> Optional[dict]:
    """
    Get full project details by name.

    Args:
        name: Project name (case-insensitive)
        conn: Database connection
        include_archived: If True, include archived projects (default: False)

    Returns:
        Dict with project fields, or None if not found

    Example:
        >>> project = await get_project_by_name("mnemolite", conn)
        >>> print(project['display_name'])  # "MnemoLite"
    """
    name_lower = name.lower().strip()

    status_filter = "AND status = 'active'" if not include_archived else ""

    result = await conn.execute(
        text(f"""
            SELECT
                id, name, display_name, description,
                repository_path, project_type, status,
                created_at, updated_at
            FROM projects
            WHERE name = :name {status_filter}
        """),
        {"name": name_lower}
    )
    row = result.fetchone()

    if not row:
        return None

    return {
        "id": str(row.id),
        "name": row.name,
        "display_name": row.display_name,
        "description": row.description,
        "repository_path": row.repository_path,
        "project_type": row.project_type,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None
    }


async def get_project_by_id(
    project_id: uuid.UUID,
    conn: AsyncConnection
) -> Optional[dict]:
    """
    Get full project details by UUID.

    Args:
        project_id: Project UUID
        conn: Database connection

    Returns:
        Dict with project fields, or None if not found
    """
    result = await conn.execute(
        text("""
            SELECT
                id, name, display_name, description,
                repository_path, project_type, status,
                created_at, updated_at
            FROM projects
            WHERE id = :id
        """),
        {"id": project_id}
    )
    row = result.fetchone()

    if not row:
        return None

    return {
        "id": str(row.id),
        "name": row.name,
        "display_name": row.display_name,
        "description": row.description,
        "repository_path": row.repository_path,
        "project_type": row.project_type,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None
    }
