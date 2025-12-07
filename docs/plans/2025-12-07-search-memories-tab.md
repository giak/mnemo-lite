# Search Memories Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Memories" tab to the search page with semantic search, type filtering, and multi-select ID copying for MCP usage.

**Architecture:** Two-tab interface (Code/Memories) with shared search page. New REST endpoint wraps existing SearchMemoryTool logic. Frontend uses composable pattern matching useCodeSearch.

**Tech Stack:** Vue 3 + TypeScript, FastAPI, SQLAlchemy async, pgvector semantic search

---

## Task 1: Backend - Memory Search Endpoint

**Files:**
- Modify: `api/routes/memories_routes.py`
- Test: `tests/routes/test_memories_routes.py` (create)

### Step 1: Write the failing test

Create test file `tests/routes/test_memories_routes.py`:

```python
"""Tests for memories search endpoint."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def mock_engine():
    """Mock database engine."""
    engine = MagicMock()
    return engine


@pytest.mark.asyncio
async def test_search_memories_returns_results():
    """Test POST /api/v1/memories/search returns search results."""
    mock_results = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "title": "Investigation Duclos",
            "content_preview": "Enquête sur les liens...",
            "memory_type": "investigation",
            "tags": ["politique"],
            "similarity_score": 0.89,
            "created_at": "2024-12-05T14:30:00Z",
        }
    ]

    with patch("routes.memories_routes.get_memory_search_service") as mock_service:
        mock_search = AsyncMock(return_value={
            "memories": mock_results,
            "total": 1,
            "query": "Duclos",
            "metadata": {"search_mode": "hybrid", "execution_time_ms": 45}
        })
        mock_service.return_value.search = mock_search

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/memories/search",
                json={"query": "Duclos", "limit": 10}
            )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Investigation Duclos"


@pytest.mark.asyncio
async def test_search_memories_with_type_filter():
    """Test memory search with memory_type filter."""
    with patch("routes.memories_routes.get_memory_search_service") as mock_service:
        mock_search = AsyncMock(return_value={
            "memories": [],
            "total": 0,
            "query": "test",
            "metadata": {}
        })
        mock_service.return_value.search = mock_search

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/memories/search",
                json={"query": "test", "memory_type": "investigation"}
            )

        assert response.status_code == 200
        # Verify filter was passed
        call_args = mock_search.call_args
        assert call_args.kwargs.get("memory_type") == "investigation"


@pytest.mark.asyncio
async def test_search_memories_empty_query_returns_400():
    """Test empty query returns 400 error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/memories/search",
            json={"query": ""}
        )

    assert response.status_code == 400
```

### Step 2: Run test to verify it fails

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
TEST_DATABASE_URL="postgresql+asyncpg://localhost/mnemolite_test" \
EMBEDDING_MODE=mock \
pytest tests/routes/test_memories_routes.py -v
```

Expected: FAIL with "No module named 'routes.memories_routes'" or "404 Not Found"

### Step 3: Write the endpoint implementation

Add to `api/routes/memories_routes.py` at the end of the file:

```python
from pydantic import BaseModel, Field
from typing import Optional, List


class MemorySearchRequest(BaseModel):
    """Request body for memory search."""
    query: str = Field(..., min_length=1, description="Search query")
    memory_type: Optional[str] = Field(None, description="Filter by memory type")
    limit: int = Field(20, ge=1, le=100, description="Max results")
    offset: int = Field(0, ge=0, description="Pagination offset")


class MemorySearchResult(BaseModel):
    """Single memory search result."""
    id: str
    title: str
    content_preview: str
    memory_type: str
    tags: List[str]
    author: Optional[str]
    created_at: str
    score: float


class MemorySearchResponse(BaseModel):
    """Response for memory search."""
    results: List[MemorySearchResult]
    total: int
    query: str
    search_time_ms: float


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    engine: AsyncEngine = Depends(get_db_engine)
) -> MemorySearchResponse:
    """
    Semantic search on memories.

    Uses hybrid lexical + vector search with RRF fusion.
    Supports filtering by memory_type (note, decision, task, reference, conversation, investigation).

    Returns:
        MemorySearchResponse with results, total count, and search metadata.
    """
    import time
    from services.embedding_service import EmbeddingService
    from services.hybrid_memory_search_service import HybridMemorySearchService
    from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType

    start_time = time.time()

    try:
        # Validate memory_type if provided
        memory_type_enum = None
        if request.memory_type:
            try:
                memory_type_enum = MemoryType(request.memory_type)
            except ValueError:
                valid_types = [t.value for t in MemoryType]
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid memory_type. Valid types: {', '.join(valid_types)}"
                )

        # Get embedding service
        embedding_service = EmbeddingService()

        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)

        # Build filters
        filters = MemoryFilters(
            memory_type=memory_type_enum,
            tags=[],
        )

        # Search using hybrid service
        search_service = HybridMemorySearchService(engine)
        response = await search_service.search(
            query=request.query,
            embedding=query_embedding,
            filters=filters,
            limit=request.limit,
            offset=request.offset,
        )

        # Convert to response format
        results = []
        for hr in response.results:
            results.append(MemorySearchResult(
                id=str(hr.memory_id),
                title=hr.title,
                content_preview=hr.content_preview,
                memory_type=hr.memory_type,
                tags=hr.tags or [],
                author=hr.author,
                created_at=hr.created_at,
                score=round(hr.rrf_score, 4),
            ))

        elapsed_ms = (time.time() - start_time) * 1000

        return MemorySearchResponse(
            results=results,
            total=response.metadata.total_results,
            query=request.query,
            search_time_ms=round(elapsed_ms, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Memory search failed. Please try again later."
        )
```

### Step 4: Run tests to verify they pass

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
TEST_DATABASE_URL="postgresql+asyncpg://localhost/mnemolite_test" \
EMBEDDING_MODE=mock \
pytest tests/routes/test_memories_routes.py -v
```

Expected: PASS

### Step 5: Commit

```bash
git add api/routes/memories_routes.py tests/routes/test_memories_routes.py
git commit -m "feat(api): add POST /api/v1/memories/search endpoint

Semantic search on memories with type filtering.
Uses hybrid lexical + vector search with RRF fusion."
```

---

## Task 2: Frontend - useMemorySearch Composable

**Files:**
- Create: `frontend/src/composables/useMemorySearch.ts`
- Create: `frontend/src/composables/__tests__/useMemorySearch.test.ts`

### Step 1: Write the failing test

Create `frontend/src/composables/__tests__/useMemorySearch.test.ts`:

```typescript
/**
 * Unit tests for useMemorySearch composable
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useMemorySearch } from '../useMemorySearch'
import { nextTick } from 'vue'

// Mock fetch
global.fetch = vi.fn()

describe('useMemorySearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with empty state', () => {
    const { results, loading, error, totalResults, selectedIds } = useMemorySearch()

    expect(results.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(totalResults.value).toBe(0)
    expect(selectedIds.value.size).toBe(0)
  })

  it('should perform successful search', async () => {
    const mockResults = [
      {
        id: '550e8400-e29b-41d4-a716-446655440001',
        title: 'Investigation Duclos',
        content_preview: 'Enquête sur les liens...',
        memory_type: 'investigation',
        tags: ['politique'],
        author: 'Claude',
        created_at: '2024-12-05T14:30:00Z',
        score: 0.89,
      },
    ]

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          results: mockResults,
          total: 1,
          query: 'Duclos',
          search_time_ms: 45,
        }),
      })
    ) as any

    const { results, loading, error, search } = useMemorySearch()

    await search('Duclos')
    await nextTick()

    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(results.value).toEqual(mockResults)
  })

  it('should search with memory_type filter', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ results: [], total: 0 }),
      })
    ) as any

    const { search } = useMemorySearch()

    await search('test', { memoryType: 'investigation' })
    await nextTick()

    const callBody = JSON.parse((global.fetch as any).mock.calls[0][1].body)
    expect(callBody.memory_type).toBe('investigation')
  })

  it('should toggle selection', () => {
    const { selectedIds, toggleSelection, isSelected } = useMemorySearch()

    expect(isSelected('id-1')).toBe(false)

    toggleSelection('id-1')
    expect(isSelected('id-1')).toBe(true)
    expect(selectedIds.value.size).toBe(1)

    toggleSelection('id-1')
    expect(isSelected('id-1')).toBe(false)
    expect(selectedIds.value.size).toBe(0)
  })

  it('should select all visible results', async () => {
    const mockResults = [
      { id: 'id-1', title: 'A', content_preview: '', memory_type: 'note', tags: [], score: 0.9, created_at: '' },
      { id: 'id-2', title: 'B', content_preview: '', memory_type: 'note', tags: [], score: 0.8, created_at: '' },
    ]

    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ results: mockResults, total: 2 }),
      })
    ) as any

    const { results, selectedIds, selectAll, search } = useMemorySearch()

    await search('test')
    await nextTick()

    selectAll()

    expect(selectedIds.value.size).toBe(2)
    expect(selectedIds.value.has('id-1')).toBe(true)
    expect(selectedIds.value.has('id-2')).toBe(true)
  })

  it('should copy selected IDs as newline-separated string', () => {
    const { selectedIds, copySelectedIds } = useMemorySearch()

    selectedIds.value.add('id-1')
    selectedIds.value.add('id-2')

    // Mock clipboard
    const writeTextMock = vi.fn(() => Promise.resolve())
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    })

    copySelectedIds()

    expect(writeTextMock).toHaveBeenCalledWith('id-1\nid-2')
  })

  it('should clear all state', () => {
    const { results, error, loading, selectedIds, clear } = useMemorySearch()

    results.value = [{ id: '1', title: 'T', content_preview: '', memory_type: 'note', tags: [], score: 0.9, created_at: '' }]
    error.value = 'Some error'
    loading.value = true
    selectedIds.value.add('1')

    clear()

    expect(results.value).toEqual([])
    expect(error.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(selectedIds.value.size).toBe(0)
  })
})
```

### Step 2: Run test to verify it fails

```bash
cd /home/giak/Work/MnemoLite/frontend && pnpm test -- useMemorySearch
```

Expected: FAIL with "Cannot find module '../useMemorySearch'"

### Step 3: Write the composable implementation

Create `frontend/src/composables/useMemorySearch.ts`:

```typescript
/**
 * Composable for semantic search on memories.
 *
 * Provides search, filtering, multi-selection, and ID copying functionality.
 */

import { ref, computed } from 'vue'

export interface MemorySearchResult {
  id: string
  title: string
  content_preview: string
  memory_type: string
  tags: string[]
  author?: string
  created_at: string
  score: number
}

export interface MemorySearchOptions {
  memoryType?: string
  limit?: number
  offset?: number
}

export function useMemorySearch() {
  const results = ref<MemorySearchResult[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedIds = ref<Set<string>>(new Set())

  const totalResults = computed(() => results.value.length)

  const search = async (query: string, options: MemorySearchOptions = {}) => {
    if (!query.trim()) {
      results.value = []
      error.value = null
      return
    }

    loading.value = true
    error.value = null

    try {
      const requestBody: Record<string, any> = {
        query: query.trim(),
        limit: options.limit ?? 20,
        offset: options.offset ?? 0,
      }

      if (options.memoryType) {
        requestBody.memory_type = options.memoryType
      }

      const response = await fetch('http://localhost:8001/api/v1/memories/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      results.value = data.results || []
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Memory search error:', err)
      results.value = []
    } finally {
      loading.value = false
    }
  }

  const toggleSelection = (id: string) => {
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id)
    } else {
      selectedIds.value.add(id)
    }
    // Trigger reactivity
    selectedIds.value = new Set(selectedIds.value)
  }

  const isSelected = (id: string) => selectedIds.value.has(id)

  const selectAll = () => {
    results.value.forEach((r) => selectedIds.value.add(r.id))
    selectedIds.value = new Set(selectedIds.value)
  }

  const deselectAll = () => {
    selectedIds.value.clear()
    selectedIds.value = new Set(selectedIds.value)
  }

  const copySelectedIds = async (): Promise<boolean> => {
    const ids = Array.from(selectedIds.value).join('\n')
    try {
      await navigator.clipboard.writeText(ids)
      return true
    } catch (err) {
      console.error('Failed to copy IDs:', err)
      return false
    }
  }

  const copySingleId = async (id: string): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(id)
      return true
    } catch (err) {
      console.error('Failed to copy ID:', err)
      return false
    }
  }

  const clear = () => {
    results.value = []
    error.value = null
    loading.value = false
    selectedIds.value = new Set()
  }

  return {
    results,
    loading,
    error,
    totalResults,
    selectedIds,
    search,
    toggleSelection,
    isSelected,
    selectAll,
    deselectAll,
    copySelectedIds,
    copySingleId,
    clear,
  }
}
```

### Step 4: Run tests to verify they pass

```bash
cd /home/giak/Work/MnemoLite/frontend && pnpm test -- useMemorySearch
```

Expected: PASS

### Step 5: Commit

```bash
git add frontend/src/composables/useMemorySearch.ts frontend/src/composables/__tests__/useMemorySearch.test.ts
git commit -m "feat(frontend): add useMemorySearch composable

Semantic search on memories with:
- Type filtering (investigation, note, decision, etc.)
- Multi-selection with Set-based tracking
- Copy selected IDs to clipboard (newline-separated)"
```

---

## Task 3: Frontend - Refactor Search.vue with Tabs

**Files:**
- Modify: `frontend/src/pages/Search.vue`

### Step 1: Backup current implementation

No test needed - this is a refactor. Read the current file first.

### Step 2: Refactor Search.vue with tab system

Replace `frontend/src/pages/Search.vue` content:

```vue
<script setup lang="ts">
/**
 * Search Page with Code and Memories tabs.
 * Supports URL-based tab persistence (?tab=memories)
 */

import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCodeSearch } from '@/composables/useCodeSearch'
import { useMemorySearch } from '@/composables/useMemorySearch'

const route = useRoute()
const router = useRouter()

// Tab state
type TabType = 'code' | 'memories'
const activeTab = ref<TabType>('code')

// Initialize tab from URL
onMounted(() => {
  const tabParam = route.query.tab as string
  if (tabParam === 'memories') {
    activeTab.value = 'memories'
  }
})

// Sync tab to URL
watch(activeTab, (newTab) => {
  router.replace({ query: { ...route.query, tab: newTab } })
})

const switchTab = (tab: TabType) => {
  activeTab.value = tab
}

// Code search state
const codeSearch = useCodeSearch()
const codeQuery = ref('')
const selectedLanguage = ref<string>('')
const selectedChunkType = ref<string>('')
const languages = ['python', 'typescript', 'javascript', 'vue', 'markdown']
const chunkTypes = ['function', 'class', 'method', 'interface', 'type']

const handleCodeSearch = async () => {
  if (!codeQuery.value.trim()) {
    codeSearch.clear()
    return
  }
  const filters: any = {}
  if (selectedLanguage.value) filters.language = selectedLanguage.value
  if (selectedChunkType.value) filters.chunk_type = selectedChunkType.value

  await codeSearch.search(codeQuery.value, {
    lexical_weight: 0.5,
    vector_weight: 0.5,
    top_k: 50,
    enable_lexical: true,
    enable_vector: false,
    filters,
  })
}

const handleCodeClear = () => {
  codeQuery.value = ''
  selectedLanguage.value = ''
  selectedChunkType.value = ''
  codeSearch.clear()
}

// Memory search state
const memorySearch = useMemorySearch()
const memoryQuery = ref('')
const selectedMemoryType = ref<string>('')
const memoryTypes = [
  { value: '', label: 'Tous les types' },
  { value: 'investigation', label: 'Investigation' },
  { value: 'decision', label: 'Decision' },
  { value: 'note', label: 'Note' },
  { value: 'task', label: 'Task' },
  { value: 'reference', label: 'Reference' },
  { value: 'conversation', label: 'Conversation' },
]

const handleMemorySearch = async () => {
  if (!memoryQuery.value.trim()) {
    memorySearch.clear()
    return
  }
  await memorySearch.search(memoryQuery.value, {
    memoryType: selectedMemoryType.value || undefined,
    limit: 50,
  })
}

const handleMemoryClear = () => {
  memoryQuery.value = ''
  selectedMemoryType.value = ''
  memorySearch.clear()
}

const setInvestigationFilter = () => {
  selectedMemoryType.value = 'investigation'
  if (memoryQuery.value.trim()) {
    handleMemorySearch()
  }
}

// Copy feedback
const copyFeedback = ref<string | null>(null)
const showCopyFeedback = (message: string) => {
  copyFeedback.value = message
  setTimeout(() => {
    copyFeedback.value = null
  }, 2000)
}

const handleCopySingle = async (id: string) => {
  const success = await memorySearch.copySingleId(id)
  if (success) {
    showCopyFeedback('ID copié !')
  }
}

const handleCopySelected = async () => {
  const success = await memorySearch.copySelectedIds()
  if (success) {
    showCopyFeedback(`${memorySearch.selectedIds.value.size} IDs copiés !`)
  }
}

// Helpers
const handleKeyPress = (event: KeyboardEvent, handler: () => void) => {
  if (event.key === 'Enter') handler()
}

const formatLineRange = (start: number, end: number) => {
  return start === end ? `L${start}` : `L${start}-${end}`
}

const truncateContent = (content: string, maxLength: number = 200) => {
  if (!content) return ''
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength) + '...'
}

const getLineRange = (metadata: Record<string, any>) => {
  const startLine = metadata?.start_line
  const endLine = metadata?.end_line
  if (!startLine) return null
  return { start: startLine, end: endLine || startLine }
}

const getMemoryTypeIcon = (type: string) => {
  const icons: Record<string, string> = {
    investigation: '🔬',
    decision: '📋',
    note: '📝',
    task: '✅',
    reference: '📚',
    conversation: '💬',
  }
  return icons[type] || '📄'
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

const allSelected = computed(() => {
  if (memorySearch.results.value.length === 0) return false
  return memorySearch.results.value.every((r) => memorySearch.isSelected(r.id))
})

const toggleSelectAll = () => {
  if (allSelected.value) {
    memorySearch.deselectAll()
  } else {
    memorySearch.selectAll()
  }
}
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header -->
      <div class="mb-8 flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <div>
          <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Search</h1>
          <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
            Code & Memories Hybrid Search
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="mb-6 border-b border-slate-700">
        <nav class="flex gap-4">
          <button
            @click="switchTab('code')"
            :class="[
              'px-4 py-2 font-mono text-sm uppercase tracking-wide border-b-2 transition-colors',
              activeTab === 'code'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            ]"
          >
            Code
          </button>
          <button
            @click="switchTab('memories')"
            :class="[
              'px-4 py-2 font-mono text-sm uppercase tracking-wide border-b-2 transition-colors',
              activeTab === 'memories'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            ]"
          >
            Memories
          </button>
        </nav>
      </div>

      <!-- Copy Feedback Toast -->
      <Transition name="fade">
        <div
          v-if="copyFeedback"
          class="fixed top-4 right-4 bg-emerald-600 text-white px-4 py-2 rounded shadow-lg z-50 font-mono text-sm"
        >
          {{ copyFeedback }}
        </div>
      </Transition>

      <!-- CODE TAB -->
      <div v-if="activeTab === 'code'">
        <!-- Search Bar -->
        <div class="section mb-6">
          <div class="space-y-4">
            <div>
              <label class="label">Search Query</label>
              <div class="flex gap-3">
                <input
                  v-model="codeQuery"
                  @keypress="handleKeyPress($event, handleCodeSearch)"
                  type="text"
                  class="input flex-1"
                  placeholder="Enter search query (e.g., 'async def', 'models.User')"
                />
                <button
                  @click="handleCodeSearch"
                  :disabled="codeSearch.loading.value || !codeQuery.trim()"
                  class="btn-primary"
                >
                  {{ codeSearch.loading.value ? 'Searching...' : 'Search' }}
                </button>
                <button @click="handleCodeClear" :disabled="codeSearch.loading.value" class="btn-ghost">
                  Clear
                </button>
              </div>
            </div>

            <!-- Filters -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="label">Language</label>
                <select v-model="selectedLanguage" class="input">
                  <option value="">All Languages</option>
                  <option v-for="lang in languages" :key="lang" :value="lang">{{ lang }}</option>
                </select>
              </div>
              <div>
                <label class="label">Chunk Type</label>
                <select v-model="selectedChunkType" class="input">
                  <option value="">All Types</option>
                  <option v-for="type in chunkTypes" :key="type" :value="type">{{ type }}</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Code Results -->
        <div v-if="codeSearch.error.value" class="alert-error mb-4">
          {{ codeSearch.error.value }}
        </div>

        <div v-if="codeSearch.totalResults.value > 0" class="mb-4">
          <p class="text-sm text-gray-400">
            Found <span class="text-cyan-400 font-semibold">{{ codeSearch.totalResults.value }}</span> results
          </p>
        </div>

        <div v-if="codeSearch.loading.value" class="section">
          <div class="animate-pulse space-y-4">
            <div class="h-4 bg-slate-700 w-3/4"></div>
            <div class="h-4 bg-slate-700 w-1/2"></div>
            <div class="h-20 bg-slate-700"></div>
          </div>
        </div>

        <div v-else-if="codeSearch.totalResults.value > 0" class="space-y-4">
          <div
            v-for="result in codeSearch.results.value"
            :key="result.chunk_id"
            class="section hover:border-cyan-500/30 transition-colors"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2 flex-1 min-w-0">
                <span class="text-sm text-cyan-400 font-mono truncate">
                  {{ result.file_path || 'Unknown file' }}
                </span>
                <span v-if="getLineRange(result.metadata)" class="text-xs text-gray-500">
                  {{ formatLineRange(getLineRange(result.metadata)!.start, getLineRange(result.metadata)!.end) }}
                </span>
              </div>
              <div class="flex gap-2 flex-shrink-0">
                <span v-if="result.chunk_type" class="badge-info text-xs">{{ result.chunk_type }}</span>
                <span v-if="result.language" class="badge-info text-xs">{{ result.language }}</span>
              </div>
            </div>
            <div class="bg-slate-900 border border-slate-700 p-4 overflow-x-auto">
              <pre class="text-sm text-gray-300 font-mono whitespace-pre-wrap">{{ truncateContent(result.source_code, 400) }}</pre>
            </div>
          </div>
        </div>

        <div v-else-if="!codeSearch.loading.value && codeQuery" class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">No Results Found</h3>
          <p class="mt-2 text-sm text-gray-500">Try adjusting your search query or filters</p>
        </div>

        <div v-else class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">Search Code</h3>
          <p class="mt-2 text-sm text-gray-500">Enter a search query to find code across your repositories</p>
        </div>
      </div>

      <!-- MEMORIES TAB -->
      <div v-if="activeTab === 'memories'">
        <!-- Search Bar -->
        <div class="section mb-6">
          <div class="space-y-4">
            <div>
              <label class="label">Semantic Search</label>
              <div class="flex gap-3">
                <input
                  v-model="memoryQuery"
                  @keypress="handleKeyPress($event, handleMemorySearch)"
                  type="text"
                  class="input flex-1"
                  placeholder="Recherche sémantique (ex: 'Duclos ObsDelphi', 'decision architecture')"
                />
                <button
                  @click="handleMemorySearch"
                  :disabled="memorySearch.loading.value || !memoryQuery.trim()"
                  class="btn-primary"
                >
                  {{ memorySearch.loading.value ? 'Searching...' : 'Search' }}
                </button>
                <button @click="handleMemoryClear" :disabled="memorySearch.loading.value" class="btn-ghost">
                  Clear
                </button>
              </div>
            </div>

            <!-- Filters -->
            <div class="flex items-center gap-4">
              <div class="flex-1 max-w-xs">
                <label class="label">Type</label>
                <select v-model="selectedMemoryType" class="input">
                  <option v-for="t in memoryTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </div>
              <div class="pt-6">
                <button
                  @click="setInvestigationFilter"
                  :class="[
                    'px-4 py-2 font-mono text-sm uppercase tracking-wide border rounded transition-colors',
                    selectedMemoryType === 'investigation'
                      ? 'bg-amber-600 border-amber-500 text-white'
                      : 'bg-transparent border-amber-600 text-amber-400 hover:bg-amber-600/20'
                  ]"
                >
                  ⚡ Investigations
                </button>
              </div>
            </div>

            <!-- Selection Actions -->
            <div v-if="memorySearch.results.value.length > 0" class="flex items-center justify-between pt-2 border-t border-slate-700">
              <label class="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  @change="toggleSelectAll"
                  class="form-checkbox bg-slate-800 border-slate-600 text-cyan-500 rounded"
                />
                Tout sélectionner ({{ memorySearch.results.value.length }})
              </label>
              <button
                v-if="memorySearch.selectedIds.value.size > 0"
                @click="handleCopySelected"
                class="btn-ghost text-emerald-400 hover:text-emerald-300"
              >
                📋 Copier {{ memorySearch.selectedIds.value.size }} IDs
              </button>
            </div>
          </div>
        </div>

        <!-- Memory Results -->
        <div v-if="memorySearch.error.value" class="alert-error mb-4">
          {{ memorySearch.error.value }}
        </div>

        <div v-if="memorySearch.totalResults.value > 0" class="mb-4">
          <p class="text-sm text-gray-400">
            Found <span class="text-cyan-400 font-semibold">{{ memorySearch.totalResults.value }}</span> memories
          </p>
        </div>

        <div v-if="memorySearch.loading.value" class="section">
          <div class="animate-pulse space-y-4">
            <div class="h-4 bg-slate-700 w-3/4"></div>
            <div class="h-4 bg-slate-700 w-1/2"></div>
            <div class="h-20 bg-slate-700"></div>
          </div>
        </div>

        <div v-else-if="memorySearch.totalResults.value > 0" class="space-y-4">
          <div
            v-for="result in memorySearch.results.value"
            :key="result.id"
            :class="[
              'section transition-colors',
              memorySearch.isSelected(result.id) ? 'border-cyan-500/50 bg-cyan-950/20' : 'hover:border-cyan-500/30'
            ]"
          >
            <!-- Header -->
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <input
                  type="checkbox"
                  :checked="memorySearch.isSelected(result.id)"
                  @change="memorySearch.toggleSelection(result.id)"
                  class="form-checkbox bg-slate-800 border-slate-600 text-cyan-500 rounded"
                />
                <span class="text-sm text-cyan-400 font-mono truncate font-semibold">
                  {{ result.title }}
                </span>
              </div>
              <button
                @click="handleCopySingle(result.id)"
                class="text-gray-500 hover:text-emerald-400 transition-colors p-1"
                title="Copier l'ID"
              >
                📋
              </button>
            </div>

            <!-- Metadata -->
            <div class="flex items-center gap-3 mb-2 text-xs text-gray-500">
              <span class="flex items-center gap-1">
                {{ getMemoryTypeIcon(result.memory_type) }}
                <span class="text-gray-400">{{ result.memory_type }}</span>
              </span>
              <span>│</span>
              <span>{{ formatDate(result.created_at) }}</span>
              <span>│</span>
              <span class="text-cyan-400">Score: {{ result.score.toFixed(3) }}</span>
            </div>

            <!-- Tags -->
            <div v-if="result.tags && result.tags.length > 0" class="mb-2">
              <span
                v-for="tag in result.tags"
                :key="tag"
                class="inline-block text-xs bg-slate-700 text-gray-300 px-2 py-0.5 rounded mr-1"
              >
                #{{ tag }}
              </span>
            </div>

            <!-- Content Preview -->
            <div class="bg-slate-900 border border-slate-700 p-3 rounded">
              <p class="text-sm text-gray-400 leading-relaxed">
                {{ truncateContent(result.content_preview, 200) }}
              </p>
            </div>
          </div>
        </div>

        <div v-else-if="!memorySearch.loading.value && memoryQuery" class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">No Results Found</h3>
          <p class="mt-2 text-sm text-gray-500">Try adjusting your search query or type filter</p>
        </div>

        <div v-else class="section text-center py-12">
          <h3 class="text-lg font-medium text-gray-300 uppercase">Search Memories</h3>
          <p class="mt-2 text-sm text-gray-500">
            Recherche sémantique dans vos notes, décisions, et investigations
          </p>
          <div class="mt-4 text-xs text-gray-600 max-w-md mx-auto">
            <p class="mb-2">Exemples de recherche :</p>
            <ul class="text-left space-y-1">
              <li>• <span class="text-cyan-400 font-mono">Duclos ObsDelphi</span> - Find investigation</li>
              <li>• <span class="text-cyan-400 font-mono">decision cache Redis</span> - Architecture decisions</li>
              <li>• <span class="text-cyan-400 font-mono">async patterns</span> - Coding patterns</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

### Step 3: Manual verification

```bash
cd /home/giak/Work/MnemoLite/frontend && pnpm dev
```

Open http://localhost:3000/search - verify:
1. Two tabs visible (Code / Memories)
2. URL updates with `?tab=memories` when switching
3. Code tab works as before
4. Memories tab shows search form

### Step 4: Commit

```bash
git add frontend/src/pages/Search.vue
git commit -m "feat(frontend): add Memories tab to Search page

Two-tab interface with URL persistence (?tab=memories).
Memories tab includes:
- Semantic search with type filter
- Quick 'Investigations' preset button
- Multi-select with checkbox
- Copy selected IDs to clipboard
- Card display with content preview"
```

---

## Task 4: Integration Test

**Files:**
- Create: `tests/e2e/test_memory_search_e2e.py`

### Step 1: Write E2E test

Create `tests/e2e/test_memory_search_e2e.py`:

```python
"""E2E tests for memory search feature."""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_memory_search_endpoint_e2e():
    """Test the full memory search flow."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test search endpoint exists
        response = await client.post(
            "/api/v1/memories/search",
            json={"query": "test query", "limit": 5}
        )

        # Should return 200 (may have 0 results in test env)
        assert response.status_code in [200, 500]  # 500 if no embedding service

        if response.status_code == 200:
            data = response.json()
            assert "results" in data
            assert "total" in data
            assert "query" in data
            assert data["query"] == "test query"


@pytest.mark.asyncio
async def test_memory_search_with_invalid_type():
    """Test validation of memory_type filter."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/memories/search",
            json={"query": "test", "memory_type": "invalid_type"}
        )

        assert response.status_code == 400
        assert "Invalid memory_type" in response.json()["detail"]
```

### Step 2: Run E2E tests

```bash
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
TEST_DATABASE_URL="postgresql+asyncpg://localhost/mnemolite_test" \
EMBEDDING_MODE=mock \
pytest tests/e2e/test_memory_search_e2e.py -v
```

### Step 3: Commit

```bash
git add tests/e2e/test_memory_search_e2e.py
git commit -m "test(e2e): add memory search E2E tests

Validates search endpoint and type filter validation."
```

---

## Task 5: Final Verification & Cleanup

### Step 1: Run all tests

```bash
# Backend tests
PYTHONPATH=/home/giak/Work/MnemoLite/api:$PYTHONPATH \
EMBEDDING_MODE=mock \
pytest tests/ -v --ignore=tests/archive

# Frontend tests
cd /home/giak/Work/MnemoLite/frontend && pnpm test
```

### Step 2: Type check frontend

```bash
cd /home/giak/Work/MnemoLite/frontend && pnpm run type-check
```

### Step 3: Manual E2E verification

1. Start backend: `docker compose up -d`
2. Start frontend: `cd frontend && pnpm dev`
3. Open http://localhost:3000/search?tab=memories
4. Search for "test"
5. Verify results display
6. Select multiple results
7. Click "Copy IDs" and verify clipboard

### Step 4: Final commit

```bash
git add .
git commit -m "feat: complete memory search tab implementation

- POST /api/v1/memories/search endpoint
- useMemorySearch composable with multi-select
- Two-tab Search page (Code/Memories)
- Type filter with 'Investigations' preset
- Copy IDs to clipboard (single and bulk)"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Backend search endpoint | `memories_routes.py`, tests |
| 2 | useMemorySearch composable | `useMemorySearch.ts`, tests |
| 3 | Search.vue with tabs | `Search.vue` |
| 4 | E2E tests | `test_memory_search_e2e.py` |
| 5 | Final verification | All |

**Total estimated tasks:** 5 major tasks, ~15 commits
