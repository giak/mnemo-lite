/**
 * Composable for semantic search on memories.
 *
 * Provides search, filtering, multi-selection, and ID copying functionality.
 */

import { ref, computed } from 'vue'

const API_BASE_URL = 'http://localhost:8001/api/v1/memories'

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
  const total = ref(0)

  const totalResults = computed(() => total.value)

  const search = async (query: string, options: MemorySearchOptions = {}) => {
    if (!query.trim()) {
      results.value = []
      error.value = null
      total.value = 0
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

      const response = await fetch(`${API_BASE_URL}/search`, {
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
      total.value = data.total || 0
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Memory search error:', err)
      results.value = []
      total.value = 0
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
    total.value = 0
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
