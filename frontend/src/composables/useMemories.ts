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

  // Infinite scroll state
  const loadingMore = ref(false)
  const hasMore = ref(true)
  const offset = ref(0)
  const pageSize = 20  // Load 20 at a time

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

  // Fetch recent memories (with offset for infinite scroll)
  async function fetchRecentMemories(limit: number = pageSize, append: boolean = false): Promise<void> {
    try {
      const currentOffset = append ? offset.value : 0
      const response = await fetch(`${API_BASE_URL}/recent?limit=${limit}&offset=${currentOffset}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const newMemories = await response.json()

      if (append) {
        // Append to existing list (infinite scroll)
        data.value.recentMemories.push(...newMemories)
        offset.value += newMemories.length
      } else {
        // Replace list (initial load or refresh)
        data.value.recentMemories = newMemories
        offset.value = newMemories.length
      }

      // Check if we have more to load
      hasMore.value = newMemories.length === limit
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

  // Load more memories for infinite scroll
  async function loadMore(): Promise<void> {
    if (loadingMore.value || !hasMore.value) return

    loadingMore.value = true
    await fetchRecentMemories(pageSize, true)  // append = true
    loadingMore.value = false
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
    offset.value = 0  // Reset offset on manual refresh
    hasMore.value = true  // Reset hasMore flag

    // Fetch all endpoints in parallel
    await Promise.all([
      fetchStats(),
      fetchRecentMemories(pageSize, false),  // append = false
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
    loadingMore,  // NEW
    hasMore,      // NEW
    errors,
    lastUpdated,
    refresh,
    loadMore      // NEW
  }
}
