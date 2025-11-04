/**
 * EPIC-26: Memories Monitor Composable
 * Vue 3 composable for fetching and managing memories data
 */

import { ref, onMounted, onUnmounted } from 'vue'
import type {
  MemoriesData,
  MemoriesError
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
