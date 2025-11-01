/**
 * EPIC-25 Story 25.5: Code Graph Composable
 *
 * Composable for fetching code graph statistics and data.
 */

import { ref, computed } from 'vue'

export interface GraphStats {
  repository: string
  total_nodes: number
  total_edges: number
  nodes_by_type: Record<string, number>
  edges_by_type: Record<string, number>
}

export interface GraphNode {
  id: string
  label: string
  type: string
  file_path?: string
  metadata?: Record<string, any>
}

export interface GraphEdge {
  source: string
  target: string
  type: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

interface UseCodeGraphReturn {
  stats: ReturnType<typeof ref<GraphStats | null>>
  loading: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string | null>>
  fetchStats: (repository: string) => Promise<void>
}

export function useCodeGraph(): UseCodeGraphReturn {
  const stats = ref<GraphStats | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchStats = async (repository: string = 'MnemoLite') => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`http://localhost:8001/v1/code/graph/stats/${repository}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch graph stats: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      stats.value = data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Graph stats error:', err)
      stats.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    loading,
    error,
    fetchStats,
  }
}
