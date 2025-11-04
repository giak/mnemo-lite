# Memories Monitor Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a read-only monitoring dashboard at `/memories` to view saved conversations, code chunks, and embedding health status.

**Architecture:**
- Frontend: New Vue 3 page with 3-column dashboard layout (conversations | code | embeddings)
- Backend: New REST API endpoints in `/api/v1/memories/` for stats and recent items
- Data flow: Frontend polls backend every 30s, displays with auto-refresh indicator
- No editing/deletion - pure observability for debugging and analytics

**Tech Stack:** Vue 3 Composition API, TypeScript, FastAPI (Python), PostgreSQL, Tailwind CSS

---

## Task 1: Create Backend API Endpoints

**Files:**
- Create: `api/routes/memories_routes.py`
- Modify: `api/main.py` (register new router)

### Step 1: Create memories_routes.py with stats endpoint

**File:** `api/routes/memories_routes.py`

```python
"""
EPIC-26: Memories Monitor Backend API
Endpoints for Memories Monitor page displaying conversations, code, embeddings.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


@router.get("/stats")
async def get_memories_stats(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get overall memories statistics for dashboard.

    Returns:
        - total: Total memories count
        - today: Memories added today
        - embedding_rate: Percentage with embeddings
        - last_activity: Most recent memory timestamp
    """
    try:
        async with engine.begin() as conn:
            # Total memories
            result = await conn.execute(
                text("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL")
            )
            total = result.scalar() or 0

            # Today's count (last 24 hours)
            result = await conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM memories
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    AND deleted_at IS NULL
                """)
            )
            today = result.scalar() or 0

            # Embedding success rate
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_emb,
                        COUNT(*) as total
                    FROM memories
                    WHERE deleted_at IS NULL
                """)
            )
            row = result.fetchone()
            embedding_rate = (row.with_emb / row.total * 100) if row.total > 0 else 0

            # Last activity
            result = await conn.execute(
                text("SELECT MAX(created_at) FROM memories WHERE deleted_at IS NULL")
            )
            last_activity = result.scalar()

        return {
            "total": total,
            "today": today,
            "embedding_rate": round(embedding_rate, 1),
            "last_activity": last_activity.isoformat() if last_activity else None
        }
    except Exception as e:
        logger.error(f"Failed to get memories stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get memories stats: {str(e)}"
        )


@router.get("/recent")
async def get_recent_memories(
    limit: int = Query(default=10, ge=1, le=100),
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """
    Get recent memories (conversations) for timeline display.

    Args:
        limit: Number of recent items to return (1-100, default 10)

    Returns:
        List of memory objects with: id, title, created_at, memory_type, tags, has_embedding
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        id,
                        title,
                        created_at,
                        memory_type,
                        tags,
                        (embedding IS NOT NULL) as has_embedding,
                        author
                    FROM memories
                    WHERE deleted_at IS NULL
                    AND memory_type = 'conversation'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.fetchall()

            memories = []
            for row in rows:
                memories.append({
                    "id": str(row.id),
                    "title": row.title,
                    "created_at": row.created_at.isoformat(),
                    "memory_type": row.memory_type,
                    "tags": row.tags or [],
                    "has_embedding": row.has_embedding,
                    "author": row.author
                })

            return memories
    except Exception as e:
        logger.error(f"Failed to get recent memories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recent memories: {str(e)}"
        )


@router.get("/code-chunks/recent")
async def get_recent_code_chunks(
    limit: int = Query(default=10, ge=1, le=100),
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Get recent code chunk indexing activity.

    Args:
        limit: Number of recent items to return (1-100, default 10)

    Returns:
        Dictionary with indexing_stats (today's activity) and recent_chunks list
    """
    try:
        async with engine.begin() as conn:
            # Today's indexing stats
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) as chunks_today,
                        COUNT(DISTINCT file_path) as files_today
                    FROM code_chunks
                    WHERE indexed_at >= NOW() - INTERVAL '24 hours'
                """)
            )
            stats = result.fetchone()

            # Recent chunks
            result = await conn.execute(
                text("""
                    SELECT
                        id,
                        file_path,
                        chunk_type,
                        repository,
                        language,
                        indexed_at,
                        content
                    FROM code_chunks
                    ORDER BY indexed_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.fetchall()

            recent_chunks = []
            for row in rows:
                # Extract chunk name from content (first line, max 50 chars)
                content_preview = row.content[:50].split('\n')[0] if row.content else ""

                recent_chunks.append({
                    "id": str(row.id),
                    "file_path": row.file_path,
                    "chunk_type": row.chunk_type,
                    "repository": row.repository,
                    "language": row.language,
                    "indexed_at": row.indexed_at.isoformat(),
                    "content_preview": content_preview
                })

            return {
                "indexing_stats": {
                    "chunks_today": stats.chunks_today or 0,
                    "files_today": stats.files_today or 0
                },
                "recent_chunks": recent_chunks
            }
    except Exception as e:
        logger.error(f"Failed to get recent code chunks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recent code chunks: {str(e)}"
        )


@router.get("/embeddings/health")
async def get_embeddings_health(engine: AsyncEngine = Depends(get_db_engine)) -> Dict[str, Any]:
    """
    Get embedding health alerts and status.

    Returns:
        - text_embeddings: count, success_rate, model
        - code_embeddings: count, model
        - alerts: list of issues (e.g., memories without embeddings)
    """
    try:
        async with engine.begin() as conn:
            # Text embeddings health
            result = await conn.execute(
                text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_emb
                    FROM memories
                    WHERE deleted_at IS NULL
                """)
            )
            text_stats = result.fetchone()
            text_success_rate = (text_stats.with_emb / text_stats.total * 100) if text_stats.total > 0 else 0

            # Code embeddings (all code_chunks have embeddings by design)
            result = await conn.execute(
                text("SELECT COUNT(*) FROM code_chunks")
            )
            code_count = result.scalar() or 0

            # Alerts
            alerts = []
            memories_without_embeddings = text_stats.total - text_stats.with_emb
            if memories_without_embeddings > 0:
                alerts.append({
                    "type": "warning",
                    "message": f"{memories_without_embeddings} memories without embeddings"
                })

        return {
            "text_embeddings": {
                "total": text_stats.total,
                "with_embeddings": text_stats.with_emb,
                "success_rate": round(text_success_rate, 1),
                "model": "nomic-ai/nomic-embed-text-v1.5"
            },
            "code_embeddings": {
                "total": code_count,
                "model": "jinaai/jina-embeddings-v2-base-code"
            },
            "alerts": alerts,
            "status": "healthy" if text_success_rate > 90 else "degraded"
        }
    except Exception as e:
        logger.error(f"Failed to get embeddings health: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get embeddings health: {str(e)}"
        )
```

### Step 2: Register router in main.py

**File:** `api/main.py`

Find the section where routers are registered (search for `app.include_router`), and add:

```python
from routes import memories_routes

# ... existing routers ...

# EPIC-26: Memories Monitor
app.include_router(memories_routes.router)
```

### Step 3: Test backend endpoints

Run backend and test with curl:

```bash
# Start API (if not running)
docker compose up -d

# Wait for startup
sleep 5

# Test stats endpoint
curl http://localhost:8001/api/v1/memories/stats | jq .

# Test recent memories
curl http://localhost:8001/api/v1/memories/recent?limit=5 | jq .

# Test code chunks
curl 'http://localhost:8001/api/v1/memories/code-chunks/recent?limit=5' | jq .

# Test embeddings health
curl http://localhost:8001/api/v1/memories/embeddings/health | jq .
```

**Expected output:**
- All endpoints return 200 OK
- Stats shows total > 0 (25,083 from earlier)
- Recent memories returns array of conversations
- Code chunks returns indexing_stats + recent_chunks
- Embeddings health shows success_rate ~98.5%

### Step 4: Commit backend endpoints

```bash
git add api/routes/memories_routes.py api/main.py
git commit -m "feat(api): add memories monitor endpoints

- GET /api/v1/memories/stats - overall statistics
- GET /api/v1/memories/recent - recent conversations
- GET /api/v1/memories/code-chunks/recent - code indexing activity
- GET /api/v1/memories/embeddings/health - embedding health alerts

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Create Frontend TypeScript Types

**Files:**
- Create: `frontend/src/types/memories.ts`

### Step 1: Create memories types file

**File:** `frontend/src/types/memories.ts`

```typescript
/**
 * EPIC-26: Memories Monitor Types
 * TypeScript interfaces for memories monitor page
 */

export interface MemoriesStats {
  total: number
  today: number
  embedding_rate: number
  last_activity: string | null
}

export interface Memory {
  id: string
  title: string
  created_at: string
  memory_type: string
  tags: string[]
  has_embedding: boolean
  author: string | null
}

export interface CodeChunk {
  id: string
  file_path: string
  chunk_type: string
  repository: string
  language: string
  indexed_at: string
  content_preview: string
}

export interface IndexingStats {
  chunks_today: number
  files_today: number
}

export interface CodeChunksResponse {
  indexing_stats: IndexingStats
  recent_chunks: CodeChunk[]
}

export interface EmbeddingsHealth {
  text_embeddings: {
    total: number
    with_embeddings: number
    success_rate: number
    model: string
  }
  code_embeddings: {
    total: number
    model: string
  }
  alerts: Array<{
    type: 'warning' | 'error' | 'info'
    message: string
  }>
  status: 'healthy' | 'degraded' | 'critical'
}

export interface MemoriesData {
  stats: MemoriesStats | null
  recentMemories: Memory[]
  codeChunks: CodeChunksResponse | null
  embeddingsHealth: EmbeddingsHealth | null
}

export interface MemoriesError {
  endpoint: string
  message: string
  timestamp: string
}
```

### Step 2: Commit types

```bash
git add frontend/src/types/memories.ts
git commit -m "feat(types): add memories monitor TypeScript types

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Create Memories Composable

**Files:**
- Create: `frontend/src/composables/useMemories.ts`

### Step 1: Create useMemories composable

**File:** `frontend/src/composables/useMemories.ts`

```typescript
/**
 * EPIC-26: Memories Monitor Composable
 * Vue 3 composable for fetching and managing memories data
 */

import { ref, onMounted, onUnmounted } from 'vue'
import type {
  MemoriesData,
  MemoriesError,
  MemoriesStats,
  Memory,
  CodeChunksResponse,
  EmbeddingsHealth
} from '@/types/memories'

const API_BASE_URL = 'http://localhost:8001/api/v1/memories'

export function useMemories(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options // Default: 30 seconds

  // State
  const data = ref<MemoriesData>({
    stats: null,
    recentMemories: [],
    codeChunks: null,
    embeddingsHealth: null
  })

  const loading = ref(false)
  const errors = ref<MemoriesError[]>([])
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  // Fetch memories stats
  async function fetchStats(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.stats = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'stats',
        message: errorMsg,
        timestamp: new Date().toISOString()
      })
      console.error('Failed to fetch memories stats:', error)
    }
  }

  // Fetch recent memories
  async function fetchRecentMemories(limit: number = 10): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/recent?limit=${limit}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.recentMemories = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'recent',
        message: errorMsg,
        timestamp: new Date().toISOString()
      })
      console.error('Failed to fetch recent memories:', error)
    }
  }

  // Fetch code chunks
  async function fetchCodeChunks(limit: number = 10): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/code-chunks/recent?limit=${limit}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.codeChunks = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'code-chunks',
        message: errorMsg,
        timestamp: new Date().toISOString()
      })
      console.error('Failed to fetch code chunks:', error)
    }
  }

  // Fetch embeddings health
  async function fetchEmbeddingsHealth(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/embeddings/health`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.embeddingsHealth = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'embeddings-health',
        message: errorMsg,
        timestamp: new Date().toISOString()
      })
      console.error('Failed to fetch embeddings health:', error)
    }
  }

  // Fetch all data
  async function refresh(): Promise<void> {
    loading.value = true
    errors.value = [] // Clear previous errors

    // Fetch all endpoints in parallel
    await Promise.all([
      fetchStats(),
      fetchRecentMemories(),
      fetchCodeChunks(),
      fetchEmbeddingsHealth()
    ])

    loading.value = false
    lastUpdated.value = new Date()
  }

  // Setup auto-refresh
  function startAutoRefresh(): void {
    if (intervalId !== null) return
    intervalId = window.setInterval(refresh, refreshInterval)
  }

  function stopAutoRefresh(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  // Lifecycle
  onMounted(() => {
    refresh()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    data,
    loading,
    errors,
    lastUpdated,
    refresh
  }
}
```

### Step 2: Commit composable

```bash
git add frontend/src/composables/useMemories.ts
git commit -m "feat(composable): add useMemories composable

- Fetches stats, recent memories, code chunks, embeddings health
- Auto-refresh every 30s
- Parallel API calls for performance
- Error handling per endpoint

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Create StatsBar Component

**Files:**
- Create: `frontend/src/components/MemoriesStatsBar.vue`

### Step 1: Create MemoriesStatsBar component

**File:** `frontend/src/components/MemoriesStatsBar.vue`

```vue
<script setup lang="ts">
/**
 * EPIC-26: Memories Monitor Stats Bar
 * Top stats bar showing: Total | Embedding Rate | Today | Last Activity
 */
import { computed } from 'vue'
import type { MemoriesStats } from '@/types/memories'

interface Props {
  stats: MemoriesStats | null
  lastUpdated: Date | null
}

const props = defineProps<Props>()

// Format relative time (e.g., "5min ago")
function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return 'Never'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}min ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

// Embedding rate status color
const embeddingRateColor = computed(() => {
  if (!props.stats) return 'text-gray-400'
  if (props.stats.embedding_rate >= 95) return 'text-green-400'
  if (props.stats.embedding_rate >= 85) return 'text-yellow-400'
  return 'text-red-400'
})

// Format last updated
const lastUpdatedText = computed(() => {
  if (!props.lastUpdated) return ''
  return formatRelativeTime(props.lastUpdated.toISOString())
})
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
    <div class="grid grid-cols-4 gap-4">
      <!-- Total Memories -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Total Memories</div>
        <div class="text-2xl font-bold text-cyan-400">
          {{ stats?.total.toLocaleString() || '—' }}
        </div>
      </div>

      <!-- Embedding Rate -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Embeddings</div>
        <div class="text-2xl font-bold" :class="embeddingRateColor">
          {{ stats ? `${stats.embedding_rate}%` : '—' }}
          <span v-if="stats && stats.embedding_rate >= 95" class="text-sm">✅</span>
          <span v-else-if="stats && stats.embedding_rate >= 85" class="text-sm">⚠️</span>
          <span v-else-if="stats" class="text-sm">❌</span>
        </div>
      </div>

      <!-- Today's Count -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Added Today</div>
        <div class="text-2xl font-bold text-purple-400">
          +{{ stats?.today || 0 }}
        </div>
      </div>

      <!-- Last Activity -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Last Activity</div>
        <div class="text-2xl font-bold text-emerald-400">
          {{ formatRelativeTime(stats?.last_activity || null) }}
        </div>
      </div>
    </div>

    <!-- Last Updated Indicator -->
    <div v-if="lastUpdated" class="text-xs text-gray-500 text-center mt-3">
      Last updated: {{ lastUpdatedText }}
    </div>
  </div>
</template>
```

### Step 2: Commit component

```bash
git add frontend/src/components/MemoriesStatsBar.vue
git commit -m "feat(component): add MemoriesStatsBar component

- Displays total, embedding rate, today count, last activity
- Color-coded embedding rate (green/yellow/red)
- Relative time formatting (5min ago)
- Last updated indicator

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Create ConversationsWidget Component

**Files:**
- Create: `frontend/src/components/ConversationsWidget.vue`

### Step 1: Create ConversationsWidget component

**File:** `frontend/src/components/ConversationsWidget.vue`

```vue
<script setup lang="ts">
/**
 * EPIC-26: Conversations Widget
 * Displays recent conversations in timeline format
 */
import { computed } from 'vue'
import type { Memory } from '@/types/memories'

interface Props {
  memories: Memory[]
}

const props = defineProps<Props>()

// Format relative time
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}min ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

// Extract session ID from tags (format: session:abc123...)
function extractSessionId(tags: string[]): string {
  const sessionTag = tags.find(tag => tag.startsWith('session:'))
  if (!sessionTag) return 'Unknown'
  return sessionTag.replace('session:', '').substring(0, 8)
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 h-full">
    <h2 class="text-lg font-semibold text-cyan-400 mb-4">
      📝 Recent Conversations
    </h2>

    <div v-if="memories.length === 0" class="text-gray-400 text-sm text-center py-8">
      No conversations found
    </div>

    <div v-else class="space-y-3 overflow-y-auto max-h-[600px]">
      <div
        v-for="memory in memories"
        :key="memory.id"
        class="border border-slate-600 rounded-lg p-3 hover:bg-slate-700 transition-colors"
      >
        <!-- Time + Session -->
        <div class="flex items-center justify-between text-xs text-gray-400 mb-2">
          <span>🕐 {{ formatRelativeTime(memory.created_at) }}</span>
          <span>Session: {{ extractSessionId(memory.tags) }}</span>
        </div>

        <!-- Title -->
        <div class="text-sm text-gray-200 mb-2 font-medium truncate">
          {{ memory.title }}
        </div>

        <!-- Tags -->
        <div class="flex flex-wrap gap-1 mb-2">
          <span
            v-for="tag in memory.tags.slice(0, 3)"
            :key="tag"
            class="text-xs px-2 py-0.5 bg-slate-600 text-gray-300 rounded"
          >
            {{ tag }}
          </span>
          <span
            v-if="memory.tags.length > 3"
            class="text-xs px-2 py-0.5 text-gray-400"
          >
            +{{ memory.tags.length - 3 }}
          </span>
        </div>

        <!-- Embedding Status + View Button -->
        <div class="flex items-center justify-between">
          <span class="text-xs" :class="memory.has_embedding ? 'text-green-400' : 'text-yellow-400'">
            {{ memory.has_embedding ? '✅ Embedded' : '⚠️ No embedding' }}
          </span>
          <button
            class="text-xs px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
            @click="$emit('view-detail', memory.id)"
          >
            👁️ View
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Step 2: Commit component

```bash
git add frontend/src/components/ConversationsWidget.vue
git commit -m "feat(component): add ConversationsWidget component

- Timeline display of recent conversations
- Session ID extraction from tags
- Embedding status indicator
- View button (emits event for future modal)
- Scrollable list with max height

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Create CodeChunksWidget Component

**Files:**
- Create: `frontend/src/components/CodeChunksWidget.vue`

### Step 1: Create CodeChunksWidget component

**File:** `frontend/src/components/CodeChunksWidget.vue`

```vue
<script setup lang="ts">
/**
 * EPIC-26: Code Chunks Widget
 * Displays indexing activity stats + recent code chunks
 */
import { computed } from 'vue'
import type { CodeChunksResponse } from '@/types/memories'

interface Props {
  data: CodeChunksResponse | null
}

const props = defineProps<Props>()

// Format relative time
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}min ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

// Extract filename from path
function getFilename(path: string): string {
  return path.split('/').pop() || path
}

// Get language color badge
function getLanguageColor(language: string): string {
  const colors: Record<string, string> = {
    python: 'bg-blue-600',
    javascript: 'bg-yellow-600',
    typescript: 'bg-blue-500',
    go: 'bg-cyan-600',
    rust: 'bg-orange-600',
    java: 'bg-red-600'
  }
  return colors[language.toLowerCase()] || 'bg-gray-600'
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 h-full">
    <h2 class="text-lg font-semibold text-cyan-400 mb-4">
      💻 Code Indexing Activity
    </h2>

    <!-- Stats Box -->
    <div v-if="data" class="bg-slate-700 border border-slate-600 rounded-lg p-3 mb-4">
      <div class="text-sm text-gray-400 mb-2">📊 Today's Activity</div>
      <div class="grid grid-cols-2 gap-2 text-center">
        <div>
          <div class="text-xl font-bold text-purple-400">
            +{{ data.indexing_stats.chunks_today }}
          </div>
          <div class="text-xs text-gray-400">chunks</div>
        </div>
        <div>
          <div class="text-xl font-bold text-emerald-400">
            {{ data.indexing_stats.files_today }}
          </div>
          <div class="text-xs text-gray-400">files</div>
        </div>
      </div>
    </div>

    <!-- Recent Chunks List -->
    <div class="text-sm text-gray-400 mb-2">Latest Chunks:</div>

    <div v-if="!data || data.recent_chunks.length === 0" class="text-gray-400 text-sm text-center py-8">
      No code chunks found
    </div>

    <div v-else class="space-y-2 overflow-y-auto max-h-[450px]">
      <div
        v-for="chunk in data.recent_chunks"
        :key="chunk.id"
        class="border border-slate-600 rounded-lg p-2 hover:bg-slate-700 transition-colors"
      >
        <!-- File + Language -->
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs text-gray-300 truncate flex-1">
            {{ getFilename(chunk.file_path) }}
          </span>
          <span
            class="text-xs px-2 py-0.5 rounded text-white ml-2"
            :class="getLanguageColor(chunk.language)"
          >
            {{ chunk.language }}
          </span>
        </div>

        <!-- Chunk Type + Preview -->
        <div class="text-xs text-gray-400 mb-1">
          <span class="text-cyan-400">{{ chunk.chunk_type }}</span>
          <span v-if="chunk.content_preview"> - {{ chunk.content_preview }}</span>
        </div>

        <!-- Repo + Time -->
        <div class="flex items-center justify-between text-xs text-gray-500">
          <span>{{ chunk.repository }}</span>
          <span>{{ formatRelativeTime(chunk.indexed_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Step 2: Commit component

```bash
git add frontend/src/components/CodeChunksWidget.vue
git commit -m "feat(component): add CodeChunksWidget component

- Today's indexing stats (chunks + files)
- Recent chunks list with file, language, type
- Language color badges
- Scrollable list with max height

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Create EmbeddingsWidget Component

**Files:**
- Create: `frontend/src/components/EmbeddingsWidget.vue`

### Step 1: Create EmbeddingsWidget component

**File:** `frontend/src/components/EmbeddingsWidget.vue`

```vue
<script setup lang="ts">
/**
 * EPIC-26: Embeddings Widget
 * Displays text/code embedding stats + health alerts
 */
import { computed } from 'vue'
import type { EmbeddingsHealth } from '@/types/memories'

interface Props {
  health: EmbeddingsHealth | null
}

const props = defineProps<Props>()

// Status color
const statusColor = computed(() => {
  if (!props.health) return 'text-gray-400'
  switch (props.health.status) {
    case 'healthy': return 'text-green-400'
    case 'degraded': return 'text-yellow-400'
    case 'critical': return 'text-red-400'
    default: return 'text-gray-400'
  }
})

// Alert icon
function getAlertIcon(type: string): string {
  switch (type) {
    case 'error': return '❌'
    case 'warning': return '⚠️'
    case 'info': return 'ℹ️'
    default: return '•'
  }
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 h-full">
    <h2 class="text-lg font-semibold text-cyan-400 mb-4">
      🧠 Embeddings Status
    </h2>

    <!-- Text Embeddings Widget -->
    <div class="bg-slate-700 border border-slate-600 rounded-lg p-3 mb-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold text-purple-400">📝 Text Embeddings</span>
        <span
          class="text-xs px-2 py-0.5 rounded"
          :class="health && health.text_embeddings.success_rate >= 95 ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'"
        >
          {{ health ? `${health.text_embeddings.success_rate}%` : '—' }}
        </span>
      </div>

      <div class="text-xs text-gray-400 space-y-1">
        <div>Total: <span class="text-gray-200">{{ health?.text_embeddings.total.toLocaleString() || '—' }}</span></div>
        <div>With embeddings: <span class="text-gray-200">{{ health?.text_embeddings.with_embeddings.toLocaleString() || '—' }}</span></div>
        <div class="truncate">Model: <span class="text-gray-200 text-xs">{{ health?.text_embeddings.model || '—' }}</span></div>
      </div>
    </div>

    <!-- Code Embeddings Widget -->
    <div class="bg-slate-700 border border-slate-600 rounded-lg p-3 mb-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold text-emerald-400">💻 Code Embeddings</span>
        <span class="text-xs px-2 py-0.5 bg-green-600 text-white rounded">
          100%
        </span>
      </div>

      <div class="text-xs text-gray-400 space-y-1">
        <div>Total: <span class="text-gray-200">{{ health?.code_embeddings.total.toLocaleString() || '—' }}</span></div>
        <div class="truncate">Model: <span class="text-gray-200 text-xs">{{ health?.code_embeddings.model || '—' }}</span></div>
      </div>
    </div>

    <!-- Health Alerts -->
    <div class="bg-slate-700 border border-slate-600 rounded-lg p-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold text-cyan-400">🚨 Alerts</span>
        <span class="text-xs px-2 py-0.5 rounded" :class="statusColor">
          {{ health?.status.toUpperCase() || 'UNKNOWN' }}
        </span>
      </div>

      <div v-if="!health || health.alerts.length === 0" class="text-xs text-green-400">
        ✅ No issues detected
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="(alert, index) in health.alerts"
          :key="index"
          class="text-xs p-2 rounded"
          :class="{
            'bg-red-900/50 text-red-300': alert.type === 'error',
            'bg-yellow-900/50 text-yellow-300': alert.type === 'warning',
            'bg-blue-900/50 text-blue-300': alert.type === 'info'
          }"
        >
          <span>{{ getAlertIcon(alert.type) }} {{ alert.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Step 2: Commit component

```bash
git add frontend/src/components/EmbeddingsWidget.vue
git commit -m "feat(component): add EmbeddingsWidget component

- Text embeddings widget with success rate
- Code embeddings widget (always 100%)
- Health alerts section with color coding
- Model display for both embedding types

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Create Main Memories Page

**Files:**
- Create: `frontend/src/pages/Memories.vue`

### Step 1: Create Memories.vue page

**File:** `frontend/src/pages/Memories.vue`

```vue
<script setup lang="ts">
/**
 * EPIC-26: Memories Monitor Page
 * Main dashboard for monitoring conversations, code chunks, and embeddings
 */
import { computed } from 'vue'
import { useMemories } from '@/composables/useMemories'
import MemoriesStatsBar from '@/components/MemoriesStatsBar.vue'
import ConversationsWidget from '@/components/ConversationsWidget.vue'
import CodeChunksWidget from '@/components/CodeChunksWidget.vue'
import EmbeddingsWidget from '@/components/EmbeddingsWidget.vue'

// Use memories composable with 30-second refresh
const { data, loading, errors, lastUpdated, refresh } = useMemories({
  refreshInterval: 30000
})

// Handle view detail (future: open modal)
function handleViewDetail(memoryId: string) {
  console.log('View memory detail:', memoryId)
  // TODO: Implement modal in future iteration
  alert(`Memory detail modal coming soon!\nID: ${memoryId}`)
}
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-cyan-400">🧠 Memories Monitor</h1>

      <button
        @click="refresh"
        :disabled="loading"
        class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
      >
        <span v-if="loading">⏳</span>
        <span v-else>🔄</span>
        Refresh
      </button>
    </div>

    <!-- Error Display -->
    <div v-if="errors.length > 0" class="mb-4 space-y-2">
      <div
        v-for="error in errors"
        :key="error.timestamp"
        class="bg-red-900/50 border border-red-600 text-red-300 px-4 py-2 rounded-lg text-sm"
      >
        ⚠️ {{ error.endpoint }}: {{ error.message }}
      </div>
    </div>

    <!-- Stats Bar -->
    <MemoriesStatsBar :stats="data.stats" :last-updated="lastUpdated" />

    <!-- 3-Column Dashboard -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left: Conversations -->
      <div>
        <ConversationsWidget
          :memories="data.recentMemories"
          @view-detail="handleViewDetail"
        />
      </div>

      <!-- Center: Code Chunks -->
      <div>
        <CodeChunksWidget :data="data.codeChunks" />
      </div>

      <!-- Right: Embeddings -->
      <div>
        <EmbeddingsWidget :health="data.embeddingsHealth" />
      </div>
    </div>
  </div>
</template>
```

### Step 2: Commit page

```bash
git add frontend/src/pages/Memories.vue
git commit -m "feat(page): add Memories monitor page

- 3-column dashboard layout
- Stats bar at top
- Manual refresh button
- Error display
- Auto-refresh every 30s via composable

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Add Route and Navigation

**Files:**
- Modify: `frontend/src/router.ts`
- Modify: `frontend/src/components/Navbar.vue`

### Step 1: Add route to router.ts

**File:** `frontend/src/router.ts`

Add after existing routes (around line 34):

```typescript
    {
      path: '/memories',
      name: 'memories',
      component: () => import('@/pages/Memories.vue')
    }
```

### Step 2: Add to Navbar

**File:** `frontend/src/components/Navbar.vue`

In the `links` array (around line 13), add after 'Search':

```typescript
const links: MenuItem[] = [
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'Search', path: '/search' },
  { name: 'Memories', path: '/memories' },  // Add this line
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

### Step 3: Test frontend

```bash
# Start frontend dev server (if not running)
cd frontend
pnpm dev
```

Open browser to `http://localhost:5173/memories` and verify:
- Page loads without errors
- Stats bar displays (may show 0 if no data)
- 3 widgets render
- Refresh button works
- Navbar shows "Memories" link

### Step 4: Commit routing changes

```bash
git add frontend/src/router.ts frontend/src/components/Navbar.vue
git commit -m "feat(routing): add memories monitor route and nav

- Add /memories route to router
- Add Memories link to navbar
- Page accessible from navigation

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Integration Testing and Documentation

**Files:**
- Create: `docs/features/memories-monitor.md`

### Step 1: Manual integration test

Test complete user flow:

1. **Start services:**
   ```bash
   docker compose up -d
   cd frontend && pnpm dev
   ```

2. **Navigate to memories page:**
   - Open `http://localhost:5173/memories`
   - Verify stats bar shows total ~25,083
   - Verify embedding rate ~98.5%
   - Verify conversations list populated

3. **Test auto-refresh:**
   - Wait 30 seconds
   - Verify "Last updated" changes
   - Verify data refreshes automatically

4. **Test manual refresh:**
   - Click refresh button
   - Verify loading state (⏳)
   - Verify data updates

5. **Test responsive layout:**
   - Resize browser to mobile width
   - Verify columns stack vertically
   - Verify all widgets remain usable

### Step 2: Create documentation

**File:** `docs/features/memories-monitor.md`

```markdown
# Memories Monitor Feature

**Status:** ✅ Implemented
**Date:** 2025-11-04
**EPIC:** EPIC-26

## Overview

Read-only monitoring dashboard at `/memories` for viewing saved conversations, code chunks, and embedding health status.

## Features

### Stats Bar
- **Total Memories**: Current count (~25,083)
- **Embedding Rate**: Success percentage with color coding (green >95%, yellow >85%, red <85%)
- **Today's Count**: Memories added in last 24 hours
- **Last Activity**: Relative time since last memory created

### Conversations Widget
- Timeline of 10 most recent conversations
- Displays: time, session ID, title, tags, embedding status
- "View" button (future: modal detail view)

### Code Chunks Widget
- Today's indexing stats (chunks + files)
- List of 10 most recent indexed chunks
- Language badges with color coding
- File path, chunk type, repository

### Embeddings Widget
- **Text Embeddings**: Total, with embeddings, success rate, model
- **Code Embeddings**: Total, model (always 100%)
- **Health Alerts**: Warnings for memories without embeddings

## Auto-Refresh

- Automatic refresh every 30 seconds
- Manual refresh button
- "Last updated" indicator

## API Endpoints

- `GET /api/v1/memories/stats` - Overall statistics
- `GET /api/v1/memories/recent?limit=10` - Recent conversations
- `GET /api/v1/memories/code-chunks/recent?limit=10` - Code indexing activity
- `GET /api/v1/memories/embeddings/health` - Embedding health alerts

## Tech Stack

- **Frontend**: Vue 3, TypeScript, Tailwind CSS
- **Backend**: FastAPI, PostgreSQL
- **Composable**: `useMemories` with auto-refresh

## Future Enhancements

- Modal for viewing full conversation content
- Search/filter within conversations
- Export conversations to markdown
- Embedding visualization (t-SNE or UMAP)
- Time-series charts for activity
```

### Step 3: Commit documentation

```bash
git add docs/features/memories-monitor.md
git commit -m "docs: add memories monitor feature documentation

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Step 4: Final verification

Run full test suite:

```bash
# Backend tests (if any exist for memories routes)
cd api
pytest tests/ -k memories -v

# Frontend type check
cd frontend
pnpm vue-tsc --noEmit

# Frontend build
pnpm build
```

Expected: All checks pass, build succeeds.

---

## ✅ Implementation Complete

All tasks completed! The Memories Monitor page is now accessible at `/memories` with:

- ✅ Backend API endpoints for stats, conversations, code chunks, embeddings
- ✅ TypeScript types and interfaces
- ✅ Vue 3 composable with auto-refresh
- ✅ Stats bar component
- ✅ 3 widget components (Conversations, Code, Embeddings)
- ✅ Main page with 3-column layout
- ✅ Routing and navigation
- ✅ Documentation

**Final commit:**

```bash
git log --oneline -10
# Should show 10 commits from this implementation
```
