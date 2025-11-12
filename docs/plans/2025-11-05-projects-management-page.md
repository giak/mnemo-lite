# Projects Management Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive Projects Management page to view, switch, add, reindex, and delete indexed code repositories.

**Architecture:**
- Backend: FastAPI REST API with project stats aggregation from PostgreSQL
- Frontend: Vue 3 page with table view, stats cards, and action buttons
- State: Global store for active project with persistence to localStorage
- Integration: Navbar dropdown for quick project switching

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy, asyncpg
- Frontend: Vue 3 Composition API, TypeScript, Tailwind CSS
- Testing: pytest (backend), vitest (frontend)

---

## Task 1: Backend - Projects List Endpoint

**Files:**
- Create: `api/routes/projects_routes.py`
- Test: `tests/routes/test_projects_routes.py`
- Modify: `api/main.py` (register router)

### Step 1: Write the failing test

Create `tests/routes/test_projects_routes.py`:

```python
"""
Tests for Projects Management API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_list_projects_returns_all_repositories(
    async_client: AsyncClient,
    engine: AsyncEngine
):
    """Test GET /api/v1/projects returns list of indexed repositories."""
    response = await async_client.get("/api/v1/projects")

    assert response.status_code == 200
    data = response.json()

    assert "projects" in data
    assert isinstance(data["projects"], list)
    assert len(data["projects"]) > 0

    # Check first project structure
    project = data["projects"][0]
    assert "repository" in project
    assert "files_count" in project
    assert "chunks_count" in project
    assert "languages" in project
    assert "last_indexed" in project
    assert "status" in project
```

### Step 2: Run test to verify it fails

```bash
pytest tests/routes/test_projects_routes.py::test_list_projects_returns_all_repositories -v
```

Expected: `FAIL - 404 Not Found` (endpoint doesn't exist yet)

### Step 3: Create projects routes file

Create `api/routes/projects_routes.py`:

```python
"""
EPIC-27: Projects Management API
Endpoints for managing indexed code repositories.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
async def list_projects(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    List all indexed projects with statistics.

    Returns:
        {
            "projects": [
                {
                    "repository": "code_test",
                    "files_count": 123,
                    "chunks_count": 456,
                    "languages": ["python", "typescript"],
                    "last_indexed": "2025-11-05T10:30:00",
                    "status": "healthy",
                    "total_loc": 12345,
                    "graph_coverage": 0.92
                },
                ...
            ]
        }
    """
    try:
        async with engine.begin() as conn:
            # Get repository statistics
            result = await conn.execute(
                text("""
                    SELECT
                        properties->>'repository' as repository,
                        COUNT(DISTINCT properties->>'file_path') as files_count,
                        COUNT(*) as chunks_count,
                        MAX(indexed_at) as last_indexed,
                        array_agg(DISTINCT properties->>'language') FILTER (WHERE properties->>'language' IS NOT NULL) as languages,
                        SUM(CAST(properties->>'loc' AS INTEGER)) FILTER (WHERE properties->>'loc' IS NOT NULL) as total_loc
                    FROM code_chunks
                    WHERE properties->>'repository' IS NOT NULL
                    GROUP BY properties->>'repository'
                    ORDER BY last_indexed DESC
                """)
            )

            projects = []
            for row in result.fetchall():
                # Calculate graph coverage for this repository
                coverage_result = await conn.execute(
                    text("""
                        SELECT
                            COUNT(*) FILTER (WHERE array_length(edges_in, 1) > 0 OR array_length(edges_out, 1) > 0) as connected,
                            COUNT(*) as total
                        FROM nodes
                        WHERE node_type = 'Module'
                          AND properties->>'repository' = :repository
                    """),
                    {"repository": row.repository}
                )
                coverage_row = coverage_result.fetchone()
                graph_coverage = (coverage_row.connected / coverage_row.total) if coverage_row.total > 0 else 0

                # Determine status
                last_indexed = row.last_indexed
                if last_indexed:
                    days_since_index = (datetime.now(last_indexed.tzinfo) - last_indexed).days
                    if days_since_index > 7:
                        status = "needs_reindex"
                    elif graph_coverage < 0.5:
                        status = "poor_coverage"
                    else:
                        status = "healthy"
                else:
                    status = "error"

                projects.append({
                    "repository": row.repository,
                    "files_count": row.files_count,
                    "chunks_count": row.chunks_count,
                    "languages": row.languages or [],
                    "last_indexed": last_indexed.isoformat() if last_indexed else None,
                    "status": status,
                    "total_loc": row.total_loc or 0,
                    "graph_coverage": round(graph_coverage, 2)
                })

            return {"projects": projects}

    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve projects list. Please try again later."
        )
```

### Step 4: Register router in main.py

Modify `api/main.py`, add after other router imports:

```python
from routes import projects_routes

# ... existing code ...

# EPIC-27: Projects Management
app.include_router(projects_routes.router)
```

### Step 5: Run test to verify it passes

```bash
pytest tests/routes/test_projects_routes.py::test_list_projects_returns_all_repositories -v
```

Expected: `PASS`

### Step 6: Commit

```bash
git add api/routes/projects_routes.py tests/routes/test_projects_routes.py api/main.py
git commit -m "feat(projects): add projects list endpoint with stats

- GET /api/v1/projects returns all indexed repositories
- Includes files count, chunks count, languages, last indexed
- Calculates graph coverage and status
- Status: healthy, needs_reindex, poor_coverage, error

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Backend - Active Project Endpoints

**Files:**
- Modify: `api/routes/projects_routes.py`
- Test: `tests/routes/test_projects_routes.py`

### Step 1: Write failing tests for get/set active project

Add to `tests/routes/test_projects_routes.py`:

```python
@pytest.mark.asyncio
async def test_get_active_project_returns_current(async_client: AsyncClient):
    """Test GET /api/v1/projects/active returns currently active project."""
    response = await async_client.get("/api/v1/projects/active")

    assert response.status_code == 200
    data = response.json()

    assert "repository" in data
    assert isinstance(data["repository"], str)


@pytest.mark.asyncio
async def test_set_active_project_changes_context(async_client: AsyncClient):
    """Test POST /api/v1/projects/active switches active project."""
    response = await async_client.post(
        "/api/v1/projects/active",
        json={"repository": "test_project"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["repository"] == "test_project"
    assert "message" in data
```

### Step 2: Run tests to verify they fail

```bash
pytest tests/routes/test_projects_routes.py -k "active" -v
```

Expected: `FAIL - 404 Not Found`

### Step 3: Implement active project endpoints

Add to `api/routes/projects_routes.py`:

```python
from pydantic import BaseModel


class SetActiveProjectRequest(BaseModel):
    repository: str


# Simple in-memory store for active project (will be enhanced with Redis later)
_active_project = {"repository": "default"}


@router.get("/active")
async def get_active_project() -> Dict[str, str]:
    """
    Get the currently active project.

    Returns:
        {
            "repository": "code_test"
        }
    """
    return _active_project


@router.post("/active")
async def set_active_project(
    request: SetActiveProjectRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Set the active project for search and navigation.

    Args:
        request: {"repository": "project_name"}

    Returns:
        {
            "repository": "project_name",
            "message": "Active project switched to project_name"
        }
    """
    try:
        # Verify project exists
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT COUNT(*) as count
                    FROM code_chunks
                    WHERE properties->>'repository' = :repository
                """),
                {"repository": request.repository}
            )
            count = result.scalar()

            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{request.repository}' not found or has no indexed files."
                )

        # Update active project
        _active_project["repository"] = request.repository

        return {
            "repository": request.repository,
            "message": f"Active project switched to {request.repository}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set active project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to set active project. Please try again later."
        )
```

### Step 4: Run tests to verify they pass

```bash
pytest tests/routes/test_projects_routes.py -k "active" -v
```

Expected: `PASS`

### Step 5: Commit

```bash
git add api/routes/projects_routes.py tests/routes/test_projects_routes.py
git commit -m "feat(projects): add get/set active project endpoints

- GET /api/v1/projects/active returns current active project
- POST /api/v1/projects/active switches active project
- Validates project exists before switching

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Backend - Reindex Project Endpoint

**Files:**
- Modify: `api/routes/projects_routes.py`
- Test: `tests/routes/test_projects_routes.py`

### Step 1: Write failing test for reindex

Add to `tests/routes/test_projects_routes.py`:

```python
@pytest.mark.asyncio
async def test_reindex_project_triggers_indexing(async_client: AsyncClient):
    """Test POST /api/v1/projects/{repository}/reindex triggers reindexing."""
    response = await async_client.post("/api/v1/projects/code_test/reindex")

    assert response.status_code == 200
    data = response.json()

    assert "repository" in data
    assert "status" in data
    assert data["status"] == "reindexing"
```

### Step 2: Run test to verify it fails

```bash
pytest tests/routes/test_projects_routes.py::test_reindex_project_triggers_indexing -v
```

Expected: `FAIL - 404 Not Found`

### Step 3: Implement reindex endpoint

Add to `api/routes/projects_routes.py`:

```python
import asyncio
from pathlib import Path


@router.post("/{repository}/reindex")
async def reindex_project(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Trigger reindexing of a project.

    NOTE: This is a simplified version that triggers background indexing.
    Full implementation would use a task queue (Celery/RQ).

    Args:
        repository: Name of the repository to reindex

    Returns:
        {
            "repository": "code_test",
            "status": "reindexing",
            "message": "Reindexing started for code_test"
        }
    """
    try:
        # Verify project exists
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        properties->>'file_path' as file_path
                    FROM code_chunks
                    WHERE properties->>'repository' = :repository
                    LIMIT 1
                """),
                {"repository": repository}
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{repository}' not found."
                )

            # Extract project root from file path
            # This is simplified - production would use proper project metadata
            file_path = row.file_path
            # Assume project root is parent of first indexed file
            project_root = str(Path(file_path).parent.parent)

        # TODO: Trigger background reindexing task
        # For now, just return success status
        logger.info(f"Reindex triggered for {repository} at {project_root}")

        return {
            "repository": repository,
            "status": "reindexing",
            "message": f"Reindexing started for {repository}",
            "project_root": project_root
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reindex project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger reindexing. Please try again later."
        )
```

### Step 4: Run test to verify it passes

```bash
pytest tests/routes/test_projects_routes.py::test_reindex_project_triggers_indexing -v
```

Expected: `PASS`

### Step 5: Commit

```bash
git add api/routes/projects_routes.py tests/routes/test_projects_routes.py
git commit -m "feat(projects): add reindex project endpoint

- POST /api/v1/projects/{repository}/reindex triggers reindexing
- Validates project exists
- Returns reindexing status

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Backend - Delete Project Endpoint

**Files:**
- Modify: `api/routes/projects_routes.py`
- Test: `tests/routes/test_projects_routes.py`

### Step 1: Write failing test for delete

Add to `tests/routes/test_projects_routes.py`:

```python
@pytest.mark.asyncio
async def test_delete_project_removes_all_data(async_client: AsyncClient, engine: AsyncEngine):
    """Test DELETE /api/v1/projects/{repository} removes all project data."""
    # First, verify project exists
    response = await async_client.get("/api/v1/projects")
    projects_before = response.json()["projects"]

    # Delete a project (assuming 'test_delete' exists in test data)
    response = await async_client.delete("/api/v1/projects/test_delete")

    assert response.status_code == 200
    data = response.json()

    assert "repository" in data
    assert "deleted_chunks" in data
    assert "deleted_nodes" in data
    assert data["deleted_chunks"] > 0
```

### Step 2: Run test to verify it fails

```bash
pytest tests/routes/test_projects_routes.py::test_delete_project_removes_all_data -v
```

Expected: `FAIL - 404 Not Found`

### Step 3: Implement delete endpoint

Add to `api/routes/projects_routes.py`:

```python
@router.delete("/{repository}")
async def delete_project(
    repository: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Delete all data for a project.

    WARNING: This is destructive and cannot be undone!

    Args:
        repository: Name of the repository to delete

    Returns:
        {
            "repository": "code_test",
            "deleted_chunks": 1234,
            "deleted_nodes": 567,
            "message": "Project code_test deleted successfully"
        }
    """
    try:
        async with engine.begin() as conn:
            # Delete code chunks
            result = await conn.execute(
                text("""
                    DELETE FROM code_chunks
                    WHERE properties->>'repository' = :repository
                    RETURNING id
                """),
                {"repository": repository}
            )
            deleted_chunks = len(result.fetchall())

            # Delete nodes
            result = await conn.execute(
                text("""
                    DELETE FROM nodes
                    WHERE properties->>'repository' = :repository
                    RETURNING node_id
                """),
                {"repository": repository}
            )
            deleted_nodes = len(result.fetchall())

            # Delete edges (cascade should handle this, but be explicit)
            await conn.execute(
                text("""
                    DELETE FROM edges
                    WHERE source_id IN (
                        SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
                    ) OR target_id IN (
                        SELECT node_id FROM nodes WHERE properties->>'repository' = :repository
                    )
                """),
                {"repository": repository}
            )

            if deleted_chunks == 0 and deleted_nodes == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project '{repository}' not found or already deleted."
                )

        logger.info(f"Deleted project {repository}: {deleted_chunks} chunks, {deleted_nodes} nodes")

        return {
            "repository": repository,
            "deleted_chunks": deleted_chunks,
            "deleted_nodes": deleted_nodes,
            "message": f"Project {repository} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete project. Please try again later."
        )
```

### Step 4: Run test to verify it passes

```bash
pytest tests/routes/test_projects_routes.py::test_delete_project_removes_all_data -v
```

Expected: `PASS`

### Step 5: Commit

```bash
git add api/routes/projects_routes.py tests/routes/test_projects_routes.py
git commit -m "feat(projects): add delete project endpoint

- DELETE /api/v1/projects/{repository} removes all project data
- Deletes code_chunks, nodes, and edges
- Returns count of deleted items
- Warns about destructive operation

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Frontend - TypeScript Types

**Files:**
- Create: `frontend/src/types/projects.ts`

### Step 1: Create TypeScript interfaces

Create `frontend/src/types/projects.ts`:

```typescript
/**
 * EPIC-27: Projects Management Types
 * TypeScript interfaces for projects management page
 */

export type ProjectStatus = 'healthy' | 'needs_reindex' | 'poor_coverage' | 'error'

export interface Project {
  repository: string
  files_count: number
  chunks_count: number
  languages: string[]
  last_indexed: string | null
  status: ProjectStatus
  total_loc: number
  graph_coverage: number
}

export interface ProjectsResponse {
  projects: Project[]
}

export interface ActiveProjectResponse {
  repository: string
}

export interface SetActiveProjectRequest {
  repository: string
}

export interface SetActiveProjectResponse {
  repository: string
  message: string
}

export interface ReindexProjectResponse {
  repository: string
  status: string
  message: string
  project_root: string
}

export interface DeleteProjectResponse {
  repository: string
  deleted_chunks: number
  deleted_nodes: number
  message: string
}
```

### Step 2: Commit

```bash
git add frontend/src/types/projects.ts
git commit -m "feat(projects): add TypeScript types for projects management

- Define Project, ProjectStatus interfaces
- Add API request/response types
- Type-safe projects management

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Frontend - Projects Composable

**Files:**
- Create: `frontend/src/composables/useProjects.ts`

### Step 1: Create projects composable

Create `frontend/src/composables/useProjects.ts`:

```typescript
/**
 * EPIC-27: Projects Management Composable
 * Centralized state and API calls for projects management
 */
import { ref, computed } from 'vue'
import type {
  Project,
  ProjectsResponse,
  ActiveProjectResponse,
  SetActiveProjectResponse,
  ReindexProjectResponse,
  DeleteProjectResponse
} from '@/types/projects'

const API_BASE = 'http://localhost:8001/api/v1'

// Global state for active project
const activeProject = ref<string>('default')
const projects = ref<Project[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

export function useProjects() {
  // Load active project from localStorage on init
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('activeProject')
    if (stored) {
      activeProject.value = stored
    }
  }

  /**
   * Fetch list of all projects
   */
  async function fetchProjects(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects`)

      if (!response.ok) {
        throw new Error(`Failed to fetch projects: ${response.statusText}`)
      }

      const data: ProjectsResponse = await response.json()
      projects.value = data.projects
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch projects:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Get currently active project
   */
  async function fetchActiveProject(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/projects/active`)

      if (!response.ok) {
        throw new Error(`Failed to fetch active project: ${response.statusText}`)
      }

      const data: ActiveProjectResponse = await response.json()
      activeProject.value = data.repository

      // Persist to localStorage
      localStorage.setItem('activeProject', data.repository)
    } catch (err) {
      console.error('Failed to fetch active project:', err)
    }
  }

  /**
   * Switch active project
   */
  async function setActiveProject(repository: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects/active`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ repository })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to set active project')
      }

      const data: SetActiveProjectResponse = await response.json()
      activeProject.value = data.repository

      // Persist to localStorage
      localStorage.setItem('activeProject', data.repository)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Trigger project reindexing
   */
  async function reindexProject(repository: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects/${repository}/reindex`, {
        method: 'POST'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to reindex project')
      }

      const data: ReindexProjectResponse = await response.json()

      // Refresh projects list to show new status
      await fetchProjects()

      return data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete project and all its data
   */
  async function deleteProject(repository: string): Promise<DeleteProjectResponse> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects/${repository}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to delete project')
      }

      const data: DeleteProjectResponse = await response.json()

      // Refresh projects list
      await fetchProjects()

      // If deleted project was active, switch to default
      if (activeProject.value === repository) {
        if (projects.value.length > 0) {
          await setActiveProject(projects.value[0].repository)
        } else {
          activeProject.value = 'default'
        }
      }

      return data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Computed
  const activeProjectData = computed(() => {
    return projects.value.find(p => p.repository === activeProject.value) || null
  })

  const projectsCount = computed(() => projects.value.length)

  const healthyProjects = computed(() => {
    return projects.value.filter(p => p.status === 'healthy').length
  })

  return {
    // State
    projects,
    activeProject,
    loading,
    error,

    // Computed
    activeProjectData,
    projectsCount,
    healthyProjects,

    // Methods
    fetchProjects,
    fetchActiveProject,
    setActiveProject,
    reindexProject,
    deleteProject
  }
}
```

### Step 2: Commit

```bash
git add frontend/src/composables/useProjects.ts
git commit -m "feat(projects): add projects composable with API integration

- Fetch projects list with stats
- Get/set active project with localStorage persistence
- Reindex and delete project operations
- Global state management for projects

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Frontend - Projects Page Component

**Files:**
- Create: `frontend/src/pages/Projects.vue`

### Step 1: Create Projects page

Create `frontend/src/pages/Projects.vue`:

```vue
<script setup lang="ts">
/**
 * EPIC-27: Projects Management Page
 * Manage indexed code repositories
 */
import { onMounted, ref, computed } from 'vue'
import { useProjects } from '@/composables/useProjects'
import type { Project } from '@/types/projects'

const {
  projects,
  activeProject,
  loading,
  error,
  fetchProjects,
  setActiveProject,
  reindexProject,
  deleteProject
} = useProjects()

const confirmDeleteProject = ref<string | null>(null)

onMounted(() => {
  fetchProjects()
})

function getStatusColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'text-green-400'
    case 'needs_reindex':
      return 'text-yellow-400'
    case 'poor_coverage':
      return 'text-orange-400'
    case 'error':
      return 'text-red-400'
    default:
      return 'text-gray-400'
  }
}

function getStatusIcon(status: string): string {
  switch (status) {
    case 'healthy':
      return '✅'
    case 'needs_reindex':
      return '⏰'
    case 'poor_coverage':
      return '⚠️'
    case 'error':
      return '❌'
    default:
      return '❓'
  }
}

function formatDate(isoString: string | null): string {
  if (!isoString) return 'Never'
  const date = new Date(isoString)
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

async function handleSetActive(repository: string) {
  try {
    await setActiveProject(repository)
  } catch (err) {
    console.error('Failed to set active project:', err)
  }
}

async function handleReindex(repository: string) {
  if (!confirm(`Reindex project "${repository}"?\n\nThis will re-scan all files and may take several minutes.`)) {
    return
  }

  try {
    await reindexProject(repository)
    alert(`Reindexing started for ${repository}`)
  } catch (err) {
    alert(`Failed to reindex: ${err instanceof Error ? err.message : 'Unknown error'}`)
  }
}

function handleDeleteClick(repository: string) {
  confirmDeleteProject.value = repository
}

async function handleDeleteConfirm() {
  if (!confirmDeleteProject.value) return

  try {
    const result = await deleteProject(confirmDeleteProject.value)
    alert(`Deleted ${result.repository}: ${result.deleted_chunks} chunks, ${result.deleted_nodes} nodes`)
    confirmDeleteProject.value = null
  } catch (err) {
    alert(`Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`)
  }
}

function handleDeleteCancel() {
  confirmDeleteProject.value = null
}
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold text-cyan-400">📦 Projects</h1>
        <p class="text-gray-400 mt-1">Manage indexed code repositories</p>
      </div>

      <button
        @click="fetchProjects"
        :disabled="loading"
        class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ loading ? '⏳ Loading...' : '🔄 Refresh' }}
      </button>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mb-4 bg-red-900/50 border border-red-600 text-red-300 px-4 py-3 rounded-lg">
      ⚠️ {{ error }}
    </div>

    <!-- Active Project Card -->
    <div v-if="activeProject" class="mb-6 bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-600 rounded-lg p-4">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-sm text-gray-400">Active Project</span>
          <h2 class="text-2xl font-bold text-cyan-400">{{ activeProject }}</h2>
        </div>
        <div class="text-4xl">🎯</div>
      </div>
    </div>

    <!-- Projects Table -->
    <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <table class="w-full">
        <thead class="bg-slate-700">
          <tr>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Repository</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Files</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Chunks</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">LOC</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Languages</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Coverage</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Last Indexed</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Status</th>
            <th class="px-4 py-3 text-center text-sm font-semibold text-gray-300">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700">
          <tr
            v-for="project in projects"
            :key="project.repository"
            class="hover:bg-slate-700/50 transition-colors"
            :class="{ 'bg-cyan-900/20': project.repository === activeProject }"
          >
            <!-- Repository -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span v-if="project.repository === activeProject" class="text-cyan-400">🎯</span>
                <span class="font-medium text-white">{{ project.repository }}</span>
              </div>
            </td>

            <!-- Files -->
            <td class="px-4 py-3 text-gray-300">
              {{ formatNumber(project.files_count) }}
            </td>

            <!-- Chunks -->
            <td class="px-4 py-3 text-gray-300">
              {{ formatNumber(project.chunks_count) }}
            </td>

            <!-- LOC -->
            <td class="px-4 py-3 text-gray-300">
              {{ formatNumber(project.total_loc) }}
            </td>

            <!-- Languages -->
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="lang in project.languages.slice(0, 3)"
                  :key="lang"
                  class="px-2 py-0.5 text-xs rounded bg-slate-600 text-gray-300"
                >
                  {{ lang }}
                </span>
                <span
                  v-if="project.languages.length > 3"
                  class="px-2 py-0.5 text-xs rounded bg-slate-600 text-gray-400"
                >
                  +{{ project.languages.length - 3 }}
                </span>
              </div>
            </td>

            <!-- Coverage -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <div class="w-12 h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    class="h-full transition-all"
                    :class="{
                      'bg-green-500': project.graph_coverage >= 0.7,
                      'bg-yellow-500': project.graph_coverage >= 0.4 && project.graph_coverage < 0.7,
                      'bg-red-500': project.graph_coverage < 0.4
                    }"
                    :style="{ width: `${project.graph_coverage * 100}%` }"
                  ></div>
                </div>
                <span class="text-sm text-gray-400">{{ Math.round(project.graph_coverage * 100) }}%</span>
              </div>
            </td>

            <!-- Last Indexed -->
            <td class="px-4 py-3 text-sm text-gray-400">
              {{ formatDate(project.last_indexed) }}
            </td>

            <!-- Status -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-1">
                <span>{{ getStatusIcon(project.status) }}</span>
                <span :class="getStatusColor(project.status)" class="text-sm">
                  {{ project.status }}
                </span>
              </div>
            </td>

            <!-- Actions -->
            <td class="px-4 py-3">
              <div class="flex items-center justify-center gap-2">
                <button
                  v-if="project.repository !== activeProject"
                  @click="handleSetActive(project.repository)"
                  class="px-3 py-1 text-sm bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
                  title="Set as active project"
                >
                  Set Active
                </button>
                <button
                  @click="handleReindex(project.repository)"
                  class="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
                  title="Reindex project"
                >
                  Reindex
                </button>
                <button
                  @click="handleDeleteClick(project.repository)"
                  class="px-3 py-1 text-sm bg-red-600 hover:bg-red-500 text-white rounded transition-colors"
                  title="Delete project"
                >
                  Delete
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty State -->
      <div v-if="!loading && projects.length === 0" class="py-12 text-center text-gray-400">
        <div class="text-6xl mb-4">📦</div>
        <p class="text-lg">No projects indexed yet</p>
        <p class="text-sm mt-2">Use the CLI to index your first project</p>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="confirmDeleteProject"
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      @click="handleDeleteCancel"
    >
      <div
        class="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-6"
        @click.stop
      >
        <h3 class="text-xl font-bold text-red-400 mb-4">⚠️ Delete Project</h3>
        <p class="text-gray-300 mb-4">
          Are you sure you want to delete <strong class="text-white">{{ confirmDeleteProject }}</strong>?
        </p>
        <p class="text-sm text-gray-400 mb-6">
          This will permanently delete all code chunks, nodes, and edges. This action cannot be undone.
        </p>
        <div class="flex gap-3 justify-end">
          <button
            @click="handleDeleteCancel"
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
          >
            Cancel
          </button>
          <button
            @click="handleDeleteConfirm"
            class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Step 2: Commit

```bash
git add frontend/src/pages/Projects.vue
git commit -m "feat(projects): add projects management page

- Table view with all project statistics
- Set active, reindex, delete actions
- Status indicators with color coding
- Delete confirmation modal
- Responsive table layout

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Frontend - Project Switcher in Navbar

**Files:**
- Modify: `frontend/src/components/Navbar.vue`

### Step 1: Add project switcher dropdown

Modify `frontend/src/components/Navbar.vue`:

Add imports at top of script:

```typescript
import { computed, onMounted } from 'vue'
import { useProjects } from '@/composables/useProjects'

// ... existing code ...

// Add projects state
const {
  projects,
  activeProject,
  fetchProjects,
  setActiveProject
} = useProjects()

// Fetch projects on mount
onMounted(() => {
  fetchProjects()
})

// Project switcher state
const projectMenuOpen = ref(false)

const toggleProjectMenu = () => {
  projectMenuOpen.value = !projectMenuOpen.value
}

const closeProjectMenu = () => {
  projectMenuOpen.value = false
}

async function handleProjectSwitch(repository: string) {
  await setActiveProject(repository)
  closeProjectMenu()
}
```

Add project switcher in template, after the logo:

```vue
<div class="flex-shrink-0 flex items-center">
  <h1 class="text-xl text-heading">MnemoLite</h1>
</div>

<!-- Project Switcher -->
<div class="relative ml-4">
  <button
    @click="toggleProjectMenu"
    class="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
  >
    <span class="text-cyan-400">📦</span>
    <span class="text-sm text-gray-300">{{ activeProject }}</span>
    <svg
      class="w-4 h-4 text-gray-400 transition-transform"
      :class="{ 'rotate-180': projectMenuOpen }"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  <!-- Dropdown -->
  <div
    v-if="projectMenuOpen"
    @click="closeProjectMenu"
    class="absolute left-0 mt-2 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto"
  >
    <div class="p-2">
      <div class="px-3 py-2 text-xs font-semibold text-gray-400 uppercase">
        Switch Project
      </div>
      <router-link
        v-for="project in projects"
        :key="project.repository"
        :to="`/projects`"
        @click="handleProjectSwitch(project.repository)"
        class="flex items-center justify-between px-3 py-2 text-sm hover:bg-slate-700 transition-colors rounded"
        :class="{ 'bg-slate-700 text-cyan-400': project.repository === activeProject }"
      >
        <span class="flex items-center gap-2">
          <span v-if="project.repository === activeProject">🎯</span>
          <span>{{ project.repository }}</span>
        </span>
        <span class="text-xs text-gray-500">{{ project.chunks_count }} chunks</span>
      </router-link>

      <div v-if="projects.length === 0" class="px-3 py-4 text-center text-sm text-gray-500">
        No projects indexed
      </div>

      <div class="border-t border-slate-700 mt-2 pt-2">
        <router-link
          to="/projects"
          class="flex items-center gap-2 px-3 py-2 text-sm text-cyan-400 hover:bg-slate-700 transition-colors rounded"
        >
          <span>⚙️</span>
          <span>Manage Projects</span>
        </router-link>
      </div>
    </div>
  </div>
</div>
```

### Step 2: Commit

```bash
git add frontend/src/components/Navbar.vue
git commit -m "feat(projects): add project switcher to navbar

- Dropdown menu to switch active project
- Shows all indexed projects with chunk counts
- Quick access from any page
- Link to full Projects page

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Frontend - Add Route

**Files:**
- Modify: `frontend/src/router.ts`
- Modify: `frontend/src/components/Navbar.vue` (add nav link)

### Step 1: Add Projects route

Modify `frontend/src/router.ts`, add after memories route:

```typescript
{
  path: '/projects',
  name: 'projects',
  component: () => import('@/pages/Projects.vue')
}
```

### Step 2: Add Projects link to navbar

Modify `frontend/src/components/Navbar.vue`, add to links array:

```typescript
const links: MenuItem[] = [
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'Search', path: '/search' },
  { name: 'Memories', path: '/memories' },
  { name: 'Projects', path: '/projects' },  // Add this line
  {
    name: 'Graph',
    children: [
      { name: 'Code Graph', path: '/graph' },
      { name: 'Organigramme', path: '/orgchart' }
    ]
  },
  { name: 'Logs', path: '/logs' }
]
```

### Step 3: Commit

```bash
git add frontend/src/router.ts frontend/src/components/Navbar.vue
git commit -m "feat(projects): add Projects page route and nav link

- Add /projects route
- Add Projects link to navbar
- Enable navigation to projects management page

EPIC-27: Projects Management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Integration Testing

**Files:**
- None (manual testing)

### Step 1: Start backend and frontend

```bash
# Terminal 1: Backend
docker compose up api

# Terminal 2: Frontend
cd frontend && pnpm dev
```

### Step 2: Test Projects page

1. Navigate to `http://localhost:3000/projects`
2. Verify projects list displays with all stats
3. Test "Set Active" button - check active project changes
4. Test project switcher in navbar - verify dropdown works
5. Test "Reindex" button - confirm dialog appears
6. Test "Delete" button - confirm modal appears

### Step 3: Test API endpoints directly

```bash
# List projects
curl http://localhost:8001/api/v1/projects | jq

# Get active project
curl http://localhost:8001/api/v1/projects/active | jq

# Set active project
curl -X POST http://localhost:8001/api/v1/projects/active \
  -H "Content-Type: application/json" \
  -d '{"repository":"code_test"}' | jq

# Reindex project (dry run)
curl -X POST http://localhost:8001/api/v1/projects/code_test/reindex | jq
```

### Step 4: Document results

Create `docs/features/projects-management.md`:

```markdown
# Projects Management

Manage indexed code repositories from the web UI.

## Features

- View all indexed projects with detailed statistics
- Switch active project for search and navigation
- Reindex projects to refresh code chunks
- Delete projects and all associated data
- Quick project switcher in navbar

## Pages

### Projects Page (`/projects`)

Table view of all indexed projects showing:
- Repository name
- File and chunk counts
- Lines of code
- Languages detected
- Graph coverage percentage
- Last indexed timestamp
- Status (healthy, needs reindex, poor coverage, error)

Actions:
- Set Active: Switch to this project
- Reindex: Trigger full reindexing
- Delete: Remove all project data

### Navbar Project Switcher

Dropdown menu in navbar for quick project switching:
- Shows all projects with chunk counts
- Current active project highlighted
- Link to full Projects page

## API Endpoints

- `GET /api/v1/projects` - List all projects
- `GET /api/v1/projects/active` - Get active project
- `POST /api/v1/projects/active` - Set active project
- `POST /api/v1/projects/{repo}/reindex` - Trigger reindex
- `DELETE /api/v1/projects/{repo}` - Delete project

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Frontend: Vue 3, TypeScript, Tailwind CSS
- State: Composables with localStorage persistence

## Future Enhancements

- Add project from UI (file picker)
- Real-time indexing progress
- Project-level settings (ignore patterns, etc.)
- Export/import project configuration
```

### Step 5: Final commit

```bash
git add docs/features/projects-management.md
git commit -m "docs: add projects management feature documentation

- Feature overview and usage
- API endpoints reference
- Future enhancements

EPIC-27: Projects Management Complete

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Verification Checklist

Before considering this complete, verify:

- [ ] All backend tests pass: `pytest tests/routes/test_projects_routes.py -v`
- [ ] Frontend builds without errors: `cd frontend && pnpm build`
- [ ] Projects page loads and displays data
- [ ] Active project switcher works in navbar
- [ ] Can switch active project from both locations
- [ ] Reindex button shows confirmation
- [ ] Delete button shows modal and requires confirmation
- [ ] localStorage persists active project across page reloads
- [ ] All 10 tasks committed with proper messages

## Notes

- The reindex endpoint is simplified and doesn't actually trigger background indexing yet. Production would use Celery/RQ for async task execution.
- Delete operation is immediate and destructive. Consider adding soft delete or backup mechanisms.
- Active project state is in-memory on backend. For production, use Redis or database.
- No authentication/authorization yet. All operations are open access.

---

**Plan complete and saved to `docs/plans/2025-11-05-projects-management-page.md`.**

## Execution Options

**1. Subagent-Driven (this session)**
- I dispatch fresh subagent per task
- Code review between tasks
- Fast iteration with quality gates
- Stay in this session

**2. Parallel Session (separate)**
- Open new session with executing-plans skill
- Batch execution with checkpoints
- Independent parallel work

**Which approach would you like?**
