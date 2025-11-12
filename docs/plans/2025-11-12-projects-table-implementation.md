# Projects Table Implementation Plan

**Date:** 2025-11-12
**Status:** Ready for Execution
**Depends On:** [2025-11-12-project-name-detection-design.md](./2025-11-12-project-name-detection-design.md)
**Problem:** UUID validation blocks project name strings ("mnemolite" → UUID error)

---

## Overview

This plan implements a complete Projects table architecture to resolve the UUID vs string mismatch discovered during integration testing. The solution enables proper project management while maintaining the project name detection system already implemented.

**Architecture Decisions (from brainstorming):**
- **Q1:** Option B - Architecture for multiple projects
- **Q2:** Option C - Complete schema (name, display_name, description, repository_path, project_type, status)
- **Q3:** Option D - Soft delete with status field (never actually delete)
- **Q4:** Option C - Hybrid resolution with auto_create flag and logging

**Key Insight:** Project names ("mnemolite") → UUID resolution layer enables backward compatibility while adding proper referential integrity.

---

## Prerequisites

- PostgreSQL 18 database running
- API accessible at http://localhost:8000
- Detection script from previous tasks working
- All migrations up to v8 applied

---

## Task 1: Create Projects Table Migration

**File:** `/home/giak/Work/MnemoLite/db/migrations/v8_to_v9_create_projects_table.sql`

**Action:** Create SQL migration file

**Complete Migration:**

```sql
-- Migration: v8 → v9 - Create Projects Table
-- Date: 2025-11-12
-- Purpose: Add proper project management with soft delete and referential integrity

BEGIN;

-- ============================================================================
-- 1. CREATE PROJECTS TABLE
-- ============================================================================

CREATE TABLE projects (
  -- Primary Key
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Core Fields
  name TEXT UNIQUE NOT NULL,                    -- Technical name: "mnemolite" (lowercase)
  display_name TEXT NOT NULL,                   -- Display name: "MnemoLite" (with capitals)
  description TEXT,                             -- Project description for UI

  -- Metadata
  repository_path TEXT,                         -- "/home/giak/Work/MnemoLite"
  project_type TEXT DEFAULT 'application',      -- 'application', 'library', 'tool', etc.

  -- Soft Delete
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived')),

  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 2. CREATE INDEXES
-- ============================================================================

CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_name_status ON projects(name, status);  -- Composite for lookups

-- ============================================================================
-- 3. ADD FOREIGN KEY TO MEMORIES
-- ============================================================================

-- Add FK constraint (memories.project_id already exists as UUID)
-- No ON DELETE because we use soft delete (status='archived')
ALTER TABLE memories
  ADD CONSTRAINT fk_memories_project
  FOREIGN KEY (project_id) REFERENCES projects(id);

-- Add index for FK lookups
CREATE INDEX idx_memories_project_id ON memories(project_id);

-- ============================================================================
-- 4. INSERT INITIAL PROJECTS
-- ============================================================================

-- Insert MnemoLite project (primary project)
INSERT INTO projects (name, display_name, description, repository_path, project_type, status)
VALUES (
  'mnemolite',
  'MnemoLite',
  'PostgreSQL 18 Cognitive Memory + Code Intelligence System',
  '/home/giak/Work/MnemoLite',
  'application',
  'active'
)
ON CONFLICT (name) DO NOTHING;

-- Add other known projects here as needed
-- Example:
-- INSERT INTO projects (name, display_name, repository_path, project_type)
-- VALUES ('serena', 'Serena', '/home/giak/Work/Serena', 'application');

-- ============================================================================
-- 5. UPDATE SCHEMA VERSION
-- ============================================================================

-- Update schema version tracking (if you have a versions table)
-- INSERT INTO schema_versions (version, applied_at) VALUES (9, NOW());

COMMIT;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

-- To rollback this migration:
-- BEGIN;
-- ALTER TABLE memories DROP CONSTRAINT IF EXISTS fk_memories_project;
-- DROP INDEX IF EXISTS idx_memories_project_id;
-- DROP INDEX IF EXISTS idx_projects_name_status;
-- DROP INDEX IF EXISTS idx_projects_status;
-- DROP INDEX IF EXISTS idx_projects_name;
-- DROP TABLE IF EXISTS projects CASCADE;
-- COMMIT;
```

**Execution:**
```bash
# Apply migration
docker compose exec postgres psql -U postgres -d mnemolite -f /tmp/v8_to_v9_create_projects_table.sql

# Or copy to container first:
docker compose cp db/migrations/v8_to_v9_create_projects_table.sql postgres:/tmp/
docker compose exec postgres psql -U postgres -d mnemolite -f /tmp/v8_to_v9_create_projects_table.sql
```

**Verification:**
```bash
# Check table exists
docker compose exec postgres psql -U postgres -d mnemolite -c "\d projects"

# Check indexes
docker compose exec postgres psql -U postgres -d mnemolite -c "\di projects*"

# Check FK constraint
docker compose exec postgres psql -U postgres -d mnemolite -c "\d memories" | grep -A 5 "Foreign-key"

# Verify initial project
docker compose exec postgres psql -U postgres -d mnemolite -c "SELECT * FROM projects;"
```

---

## Task 2: Create Project Resolution Function

**File:** `/home/giak/Work/MnemoLite/api/mnemo_mcp/tools/project_tools.py` (new file)

**Action:** Create Python module for project resolution

**Complete Code:**

```python
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
```

**Tests to Add (Optional):**
```python
# tests/unit/tools/test_project_tools.py

async def test_resolve_project_existing():
    """Test resolving existing project returns UUID"""
    # Setup: Insert test project
    # Test: resolve_project_id("test-project")
    # Assert: Returns correct UUID

async def test_resolve_project_auto_create():
    """Test auto-creation of missing project"""
    # Test: resolve_project_id("new-project", auto_create=True)
    # Assert: Project created, UUID returned

async def test_resolve_project_strict_mode_fails():
    """Test strict mode raises error for missing project"""
    # Test: resolve_project_id("missing", auto_create=False)
    # Assert: Raises ValueError
```

---

## Task 3: Modify write_memory() to Accept Name or UUID

**File:** `/home/giak/Work/MnemoLite/api/mnemo_mcp/tools/memory_tools.py`

**Current Problematic Code (line 112):**
```python
if project_id:
    project_uuid = uuid.UUID(project_id)  # ❌ Fails with "mnemolite"
```

**Action:** Modify to accept both UUID strings and project names

**Complete Modification:**

```python
# Add import at top of file
from .project_tools import resolve_project_id

# Find the write_memory function (around line 50-120)
# Locate the project_id validation section (around line 112)

# BEFORE (lines 112-115):
if project_id:
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise ValueError(f"Invalid project_id UUID: {project_id}")

# AFTER:
if project_id:
    try:
        # Try to parse as UUID first (for backward compatibility)
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        # Not a UUID - treat as project name and resolve
        logger.debug(f"Resolving project name '{project_id}' to UUID")
        project_uuid = await resolve_project_id(
            name=project_id,
            conn=conn,
            auto_create=True  # Auto-create projects as needed
        )
        logger.info(f"Resolved project '{project_id}' to UUID {project_uuid}")
```

**Full Context (lines 100-125 after modification):**
```python
async def write_memory(
    ctx: RequestContext,
    title: str,
    content: str,
    memory_type: str = "note",
    tags: list[str] = None,
    author: str = None,
    project_id: str = None,
    related_chunks: list[str] = None,
    resource_links: list[dict] = None
) -> dict:
    """
    Write a memory to the database with optional embedding generation.

    Args:
        ctx: Request context with session and database
        title: Memory title (1-200 chars)
        content: Memory content
        memory_type: Type classification (note, decision, task, reference, conversation)
        tags: Optional list of tags
        author: Optional author attribution
        project_id: Project UUID or project name (e.g., "mnemolite")
                   If name provided, will be resolved to UUID (auto-creates if missing)
        related_chunks: Optional list of code chunk UUIDs
        resource_links: Optional list of MCP resource links

    Returns:
        Dict with id, title, memory_type, created_at, has_embedding
    """
    # ... existing validation code ...

    # Project ID validation and resolution
    project_uuid = None
    if project_id:
        try:
            # Try to parse as UUID first (backward compatibility)
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            # Not a UUID - treat as project name and resolve
            logger.debug(f"Resolving project name '{project_id}' to UUID")
            project_uuid = await resolve_project_id(
                name=project_id,
                conn=conn,
                auto_create=True
            )
            logger.info(f"Resolved project '{project_id}' to UUID {project_uuid}")

    # ... rest of function remains unchanged ...
```

**Verification Points:**
- Import added: `from .project_tools import resolve_project_id`
- UUID parsing wrapped in try/except
- ValueError triggers name resolution
- Auto-create enabled for convenience
- Logging added for debugging

---

## Task 4: Modify Memories API to Include display_name

**File:** `/home/giak/Work/MnemoLite/api/routes/memories_routes.py`

**Current Query (line 115-130):**
```sql
SELECT
    id, title, created_at, memory_type, tags,
    (embedding IS NOT NULL) as has_embedding,
    author, project_id
FROM memories
WHERE deleted_at IS NULL AND memory_type = 'conversation'
ORDER BY created_at DESC
LIMIT :limit
```

**Action:** Join projects table to include display_name

**Modified Query:**
```sql
SELECT
    m.id, m.title, m.created_at, m.memory_type, m.tags,
    (m.embedding IS NOT NULL) as has_embedding,
    m.author, m.project_id,
    p.display_name as project_name  -- NEW: Join for display name
FROM memories m
LEFT JOIN projects p ON m.project_id = p.id  -- NEW: Join projects
WHERE m.deleted_at IS NULL AND m.memory_type = 'conversation'
ORDER BY m.created_at DESC
LIMIT :limit
```

**Full Modified Endpoint (lines 100-145):**
```python
@router.get("/recent", response_model=RecentMemoriesResponse)
async def get_recent_memories(
    limit: int = Query(default=10, ge=1, le=100),
    ctx: RequestContext = Depends(get_context)
) -> RecentMemoriesResponse:
    """
    Get recent conversation memories with project display names.

    Args:
        limit: Maximum number of memories to return (1-100)
        ctx: Request context

    Returns:
        RecentMemoriesResponse with memories list
    """
    async with ctx.db.begin() as conn:
        # Query with LEFT JOIN to get project display_name
        result = await conn.execute(
            text("""
                SELECT
                    m.id,
                    m.title,
                    m.created_at,
                    m.memory_type,
                    m.tags,
                    (m.embedding IS NOT NULL) as has_embedding,
                    m.author,
                    m.project_id,
                    p.display_name as project_name
                FROM memories m
                LEFT JOIN projects p ON m.project_id = p.id
                WHERE m.deleted_at IS NULL
                  AND m.memory_type = 'conversation'
                ORDER BY m.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )

        memories = []
        for row in result:
            memories.append({
                "id": str(row.id),
                "title": row.title,
                "created_at": row.created_at.isoformat(),
                "memory_type": row.memory_type,
                "tags": row.tags or [],
                "has_embedding": row.has_embedding,
                "author": row.author,
                "project_id": str(row.project_id) if row.project_id else None,
                "project_name": row.project_name  # NEW: Include display name
            })

        return RecentMemoriesResponse(memories=memories)
```

**Verification:**
```bash
# Test endpoint
curl http://localhost:8000/api/v1/memories/recent | jq '.memories[0]'

# Should include:
# {
#   "project_id": "uuid-here",
#   "project_name": "MnemoLite"  <-- NEW FIELD
# }
```

---

## Task 5: Update Frontend Types and Components

**File 1:** `/home/giak/Work/MnemoLite/frontend/src/types/memories.ts`

**Action:** Add project_name field to Memory interface

**Current (line 13-22):**
```typescript
export interface Memory {
  id: string
  title: string
  created_at: string
  memory_type: string
  tags: string[]
  has_embedding: boolean
  author: string | null
  project_id: string | null
}
```

**Modified:**
```typescript
export interface Memory {
  id: string
  title: string
  created_at: string
  memory_type: string
  tags: string[]
  has_embedding: boolean
  author: string | null
  project_id: string | null
  project_name: string | null  // NEW: Display name from projects table
}
```

---

**File 2:** `/home/giak/Work/MnemoLite/frontend/src/components/ConversationsWidget.vue`

**Action:** Display project_name instead of project_id

**Current (lines 75-79):**
```vue
<!-- Project (conditional) -->
<div v-if="memory.project_id" class="text-xs text-cyan-400 mb-2 flex items-center gap-1">
  <span>📁</span>
  <span class="uppercase font-mono">{{ memory.project_id }}</span>  <!-- Shows UUID -->
</div>
```

**Modified:**
```vue
<!-- Project (conditional) -->
<div v-if="memory.project_name || memory.project_id" class="text-xs text-cyan-400 mb-2 flex items-center gap-1">
  <span>📁</span>
  <span class="uppercase font-mono">{{ memory.project_name || memory.project_id }}</span>
</div>
```

**Better Alternative (with fallback):**
```vue
<!-- Project (conditional) -->
<div v-if="memory.project_name || memory.project_id" class="text-xs text-cyan-400 mb-2 flex items-center gap-1">
  <span>📁</span>
  <span class="uppercase font-mono">
    {{ memory.project_name || 'Unknown Project' }}
  </span>
  <!-- Show UUID on hover for debugging -->
  <span v-if="memory.project_id" class="text-xxs text-gray-500" :title="memory.project_id">
    ⓘ
  </span>
</div>
```

---

## Task 6: Integration Testing

**Scenario 1: Auto-Import with Project Resolution**

```bash
# 1. Trigger auto-import
curl -X POST http://localhost:8000/v1/conversations/import

# 2. Check database - should have project_id populated
docker compose exec postgres psql -U postgres -d mnemolite -c \
  "SELECT m.title, p.name, p.display_name
   FROM memories m
   LEFT JOIN projects p ON m.project_id = p.id
   WHERE m.memory_type='conversation'
   ORDER BY m.created_at DESC LIMIT 5;"

# Expected output:
#        title         |   name    | display_name
# ---------------------+-----------+-------------
#  Conv: test message  | mnemolite | MnemoLite
```

**Scenario 2: Hook with Project Name**

```bash
# The hook will call save-direct.py with PROJECT_NAME="mnemolite"
# write_memory() will resolve "mnemolite" → UUID
# Check logs for resolution messages

docker compose logs api | grep -i "resolving project"
# Expected: "Resolving project name 'mnemolite' to UUID"
```

**Scenario 3: UI Display**

```bash
# Open UI: http://localhost:3000/memories
# Check conversation cards show:
# 📁 MNEMOLITE (not UUID)
```

**Scenario 4: Manual Project Creation**

```sql
-- Test creating a new project manually
INSERT INTO projects (name, display_name, description, repository_path, project_type)
VALUES (
  'serena',
  'Serena',
  'AI Orchestration Platform',
  '/home/giak/Work/Serena',
  'application'
);

-- Trigger auto-import from Serena project
-- Should auto-resolve to this UUID
```

---

## Task 7: Data Migration for Existing Memories

**Purpose:** Update existing NULL project_id values to reference "mnemolite" project

**File:** `/home/giak/Work/MnemoLite/db/migrations/v9_migrate_existing_memories.sql`

**Complete Migration:**

```sql
-- Migration: Populate NULL project_ids for existing MnemoLite conversations
-- Date: 2025-11-12
-- CAUTION: Review preview before committing

BEGIN;

-- ============================================================================
-- 1. PREVIEW AFFECTED ROWS
-- ============================================================================

SELECT
  COUNT(*) as total_to_update,
  COUNT(DISTINCT author) as unique_authors,
  MIN(created_at) as oldest_memory,
  MAX(created_at) as newest_memory
FROM memories
WHERE project_id IS NULL
  AND memory_type = 'conversation'
  AND (author IN ('AutoSave', 'AutoImport') OR tags @> ARRAY['claude-code']);

-- ============================================================================
-- 2. GET MNEMOLITE PROJECT UUID
-- ============================================================================

-- Store mnemolite UUID in variable
DO $$
DECLARE
  mnemolite_uuid UUID;
BEGIN
  -- Get mnemolite project UUID
  SELECT id INTO mnemolite_uuid
  FROM projects
  WHERE name = 'mnemolite' AND status = 'active';

  IF mnemolite_uuid IS NULL THEN
    RAISE EXCEPTION 'MnemoLite project not found in projects table. Run v8_to_v9 migration first.';
  END IF;

  RAISE NOTICE 'MnemoLite project UUID: %', mnemolite_uuid;

  -- Update memories with NULL project_id
  UPDATE memories
  SET project_id = mnemolite_uuid
  WHERE project_id IS NULL
    AND memory_type = 'conversation'
    AND (author IN ('AutoSave', 'AutoImport') OR tags @> ARRAY['claude-code']);

  RAISE NOTICE 'Updated % memories', FOUND;
END $$;

-- ============================================================================
-- 3. VERIFY RESULTS
-- ============================================================================

SELECT
  p.name,
  p.display_name,
  COUNT(*) as memory_count
FROM memories m
LEFT JOIN projects p ON m.project_id = p.id
WHERE m.memory_type = 'conversation'
GROUP BY p.name, p.display_name
ORDER BY memory_count DESC;

-- ============================================================================
-- 4. COMMIT OR ROLLBACK
-- ============================================================================

-- Review the verification results above
-- If correct, COMMIT
-- If incorrect, ROLLBACK

COMMIT;
-- or: ROLLBACK;
```

**Execution:**
```bash
# Copy to container
docker compose cp db/migrations/v9_migrate_existing_memories.sql postgres:/tmp/

# Execute with review
docker compose exec postgres psql -U postgres -d mnemolite -f /tmp/v9_migrate_existing_memories.sql

# Manually review output, then decide to commit or rollback
```

---

## Task 8: Final Verification Checklist

**Database Checks:**

```bash
# 1. Projects table exists with initial data
docker compose exec postgres psql -U postgres -d mnemolite -c \
  "SELECT name, display_name, status FROM projects;"
# Expected: mnemolite | MnemoLite | active

# 2. FK constraint exists
docker compose exec postgres psql -U postgres -d mnemolite -c \
  "\d memories" | grep -A 3 "Foreign-key"
# Expected: fk_memories_project FOREIGN KEY (project_id) REFERENCES projects(id)

# 3. Memories have project_id populated
docker compose exec postgres psql -U postgres -d mnemolite -c \
  "SELECT COUNT(*), COUNT(project_id) FROM memories WHERE memory_type='conversation';"
# Expected: Both counts should be equal (or close)

# 4. Join query works
docker compose exec postgres psql -U postgres -d mnemolite -c \
  "SELECT m.title, p.display_name FROM memories m LEFT JOIN projects p ON m.project_id = p.id LIMIT 5;"
# Expected: Shows conversation titles with "MnemoLite"
```

**API Checks:**

```bash
# 1. Recent memories endpoint includes project_name
curl -s http://localhost:8000/api/v1/memories/recent | jq '.memories[0] | {title, project_name}'
# Expected: {"title": "Conv: ...", "project_name": "MnemoLite"}

# 2. Auto-import works with project resolution
curl -X POST http://localhost:8000/v1/conversations/import
# Expected: {"imported": N, ...} with no errors

# 3. Logs show project resolution
docker compose logs api --tail=100 | grep -i "project"
# Expected: "Resolving project name 'mnemolite' to UUID" (if new conversations created)
```

**UI Checks:**

```bash
# 1. Open Memories page
# URL: http://localhost:3000/memories

# 2. Check conversation cards
# Expected: 📁 MNEMOLITE badge visible (not UUID)

# 3. Check no UUID strings in UI
# Expected: Clean display names, no raw UUIDs visible
```

**Code Quality Checks:**

```bash
# 1. No hardcoded "mnemolite" in API (except initial migration)
grep -r "mnemolite" api/ --include="*.py" | grep -v migration | grep -v "test" | grep -v ".pyc"
# Expected: Only in comments/docstrings, not in code logic

# 2. Import statement added
grep "from .project_tools import" api/mnemo_mcp/tools/memory_tools.py
# Expected: from .project_tools import resolve_project_id

# 3. Type definitions updated
grep "project_name" frontend/src/types/memories.ts
# Expected: project_name: string | null
```

---

## Success Criteria

- ✅ Projects table created with indexes and FK constraint
- ✅ resolve_project_id() function implemented and tested
- ✅ write_memory() accepts both UUID and project name strings
- ✅ API endpoint returns project_name (display name, not UUID)
- ✅ UI displays "MnemoLite" instead of UUID
- ✅ Auto-import works with project name resolution
- ✅ Hook works with project name detection
- ✅ Existing memories migrated to reference projects
- ✅ All tests pass with no UUID validation errors
- ✅ Logs show project resolution messages when applicable

---

## Rollback Plan

If issues occur, rollback in reverse order:

```bash
# 1. Revert API code changes
git checkout HEAD -- api/mnemo_mcp/tools/memory_tools.py
git checkout HEAD -- api/mnemo_mcp/tools/project_tools.py
git checkout HEAD -- api/routes/memories_routes.py

# 2. Revert frontend changes
git checkout HEAD -- frontend/src/types/memories.ts
git checkout HEAD -- frontend/src/components/ConversationsWidget.vue

# 3. Rollback database migration
docker compose exec postgres psql -U postgres -d mnemolite <<EOF
BEGIN;
ALTER TABLE memories DROP CONSTRAINT IF EXISTS fk_memories_project;
DROP INDEX IF EXISTS idx_memories_project_id;
DROP TABLE IF EXISTS projects CASCADE;
COMMIT;
EOF

# 4. Restart services
docker compose restart api
```

---

## Time Estimates

- Task 1 (Migration): 15 minutes
- Task 2 (Resolution Function): 20 minutes
- Task 3 (Modify write_memory): 10 minutes
- Task 4 (API Endpoint): 15 minutes
- Task 5 (Frontend): 10 minutes
- Task 6 (Integration Tests): 15 minutes
- Task 7 (Data Migration): 10 minutes (optional)
- Task 8 (Final Verification): 10 minutes

**Total: ~2 hours** (1.5 hours without data migration)

---

## Notes

- **Auto-creation is intentional:** Projects are auto-created when first referenced to minimize friction
- **Logging is verbose:** WARNING level logs for auto-creation help detect typos
- **Soft delete everywhere:** Never actually delete projects or memories, just mark as archived
- **UUID backward compatibility:** Existing UUID-based calls continue to work
- **Display names are separate:** Technical name (lowercase) vs display name (capitalized)
- **FK constraint has no ON DELETE:** Soft delete means we never actually delete projects

---

## Future Enhancements

- Projects management UI (create, edit, archive projects via web interface)
- Project statistics page (memories count, disk usage, etc.)
- Project search and filtering in memories page
- Bulk project reassignment tool
- Project export/import functionality
- Project templates for common setups
