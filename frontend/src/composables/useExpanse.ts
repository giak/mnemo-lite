/**
 * EPIC-26: Expanse Data Composable
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

export interface ExpanseData {
  memories: ExpanseMemory[]
  codeChunks: { file: string; chunks: number }[]
  patternStats: Record<string, number>
}

export function useExpanse(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options

  const data = ref<ExpanseData>({
    memories: [],
    codeChunks: [],
    patternStats: {}
  })

  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  async function fetchMemories(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 50 })
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.memories = await response.json()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      error.value = `memories: ${msg}`
      console.error('Failed to fetch memories:', err)
    }
  }

  async function fetchCodeChunks(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/code-chunks/recent?limit=20`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.codeChunks = await response.json()
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
      data.value.patternStats = await response.json()
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
