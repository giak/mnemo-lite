/**
 * Expanse Data Composable
 * Vue 3 composable for fetching Expanse data from the MnemoLite API
 */

import { ref, onMounted, onUnmounted } from 'vue'

const API_BASE_URL = 'http://localhost:8001/api/v1/memories'

export interface ExpanseMemory {
  id: string
  title: string
  memory_type: string
  tags: string[]
  created_at: string
  score?: number
}

export interface CodeChunk {
  id: string
  file_path: string
  chunk_type: string
  repository: string
  language: string
}

export interface IndexingStats {
  chunks_today: number
  files_today: number
}

export interface MemoriesStats {
  total: number
  today: number
  embedding_rate: number
  last_activity: string
}

export interface ExpanseData {
  memories: ExpanseMemory[]
  codeChunks: CodeChunk[]
  indexingStats: IndexingStats
  stats: MemoriesStats | null
}

// Expanse-specific tags to track
const EXPANSE_TAGS = ['sys:pattern', 'sys:drift', 'sys:extension', 'sys:history', 'sys:anchor', 'trace:fresh', 'sys:core']

export function useExpanse(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options

  const data = ref<ExpanseData>({
    memories: [],
    codeChunks: [],
    indexingStats: { chunks_today: 0, files_today: 0 },
    stats: null
  })

  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  // Fetch memories tagged with Expanse tags
  async function fetchMemories(): Promise<void> {
    try {
      // Search for each Expanse tag and combine results
      const allMemories: ExpanseMemory[] = []
      const seen = new Set<string>()

      for (const tag of EXPANSE_TAGS) {
        const response = await fetch(`${API_BASE_URL}/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: tag, tags: [tag], limit: 10 })
        })
        if (!response.ok) continue
        const result = await response.json()
        for (const m of (result.results || [])) {
          if (!seen.has(m.id)) {
            seen.add(m.id)
            allMemories.push(m)
          }
        }
      }

      data.value.memories = allMemories.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      error.value = `memories: ${msg}`
      console.error('Failed to fetch memories:', err)
    }
  }

  async function fetchCodeChunks(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/code-chunks/recent?limit=50`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const result = await response.json()
      data.value.codeChunks = result.recent_chunks || []
      data.value.indexingStats = result.indexing_stats || { chunks_today: 0, files_today: 0 }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      error.value = `code-chunks: ${msg}`
      console.error('Failed to fetch code chunks:', err)
    }
  }

  async function fetchStats(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.stats = await response.json()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      error.value = `stats: ${msg}`
      console.error('Failed to fetch stats:', err)
    }
  }

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null

    await Promise.all([
      fetchMemories(),
      fetchCodeChunks(),
      fetchStats()
    ])

    loading.value = false
    lastUpdated.value = new Date()
  }

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
    error,
    lastUpdated,
    refresh
  }
}
