/**
 * EPIC-25 Story 25.3: Dashboard Composable
 * Vue 3 composable for fetching and managing dashboard data
 */

import { ref, onMounted, onUnmounted } from 'vue'
import type { DashboardData, DashboardError } from '@/types/dashboard'

const API_BASE_URL = 'http://localhost:8001/api/v1/dashboard'

export function useDashboard(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options // Default: 30 seconds

  // State
  const data = ref<DashboardData>({
    health: null,
    textEmbeddings: null,
    codeEmbeddings: null,
  })

  const loading = ref(false)
  const errors = ref<DashboardError[]>([])
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  // Fetch health status
  async function fetchHealth(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/health`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.health = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'health',
        message: errorMsg,
        timestamp: new Date().toISOString(),
      })
      console.error('Failed to fetch health status:', error)
    }
  }

  // Fetch text embeddings stats
  async function fetchTextEmbeddings(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/embeddings/text`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.textEmbeddings = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'embeddings/text',
        message: errorMsg,
        timestamp: new Date().toISOString(),
      })
      console.error('Failed to fetch text embeddings:', error)
    }
  }

  // Fetch code embeddings stats
  async function fetchCodeEmbeddings(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/embeddings/code`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      data.value.codeEmbeddings = await response.json()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      errors.value.push({
        endpoint: 'embeddings/code',
        message: errorMsg,
        timestamp: new Date().toISOString(),
      })
      console.error('Failed to fetch code embeddings:', error)
    }
  }

  // Fetch all dashboard data
  async function fetchDashboardData(): Promise<void> {
    loading.value = true
    errors.value = [] // Clear previous errors

    try {
      // Fetch all endpoints in parallel
      await Promise.all([
        fetchHealth(),
        fetchTextEmbeddings(),
        fetchCodeEmbeddings(),
      ])

      lastUpdated.value = new Date()
    } finally {
      loading.value = false
    }
  }

  // Start auto-refresh
  function startAutoRefresh(): void {
    if (intervalId !== null) {
      return // Already running
    }

    intervalId = window.setInterval(() => {
      fetchDashboardData()
    }, refreshInterval)
  }

  // Stop auto-refresh
  function stopAutoRefresh(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  // Manual refresh
  async function refresh(): Promise<void> {
    await fetchDashboardData()
  }

  // Lifecycle hooks
  onMounted(() => {
    fetchDashboardData()
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
    refresh,
    startAutoRefresh,
    stopAutoRefresh,
  }
}
