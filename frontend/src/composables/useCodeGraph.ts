/**
 * EPIC-25 Story 25.5: Code Graph Composable
 *
 * Composable for fetching code graph statistics and data.
 */

import { ref } from 'vue'

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
  id: string
  source: string
  target: string
  type: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_returned: number
  limit: number
}

export interface RepositoryMetrics {
  total_functions: number
  avg_complexity: number
  max_complexity: number
  most_complex_function: string
  avg_coupling: number
  top_pagerank: Array<{ name: string; score: number }>
}

interface UseCodeGraphReturn {
  stats: ReturnType<typeof ref<GraphStats | null>>
  graphData: ReturnType<typeof ref<GraphData | null>>
  loading: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string | null>>
  building: ReturnType<typeof ref<boolean>>
  buildError: ReturnType<typeof ref<string | null>>
  repositories: ReturnType<typeof ref<string[]>>
  metrics: ReturnType<typeof ref<RepositoryMetrics | null>>
  fetchStats: (repository: string) => Promise<void>
  fetchGraphData: (repository: string, limit?: number) => Promise<void>
  buildGraph: (repository: string, language?: string) => Promise<void>
  fetchRepositories: () => Promise<void>
  fetchMetrics: (repository: string) => Promise<void>
}

export function useCodeGraph(): UseCodeGraphReturn {
  const stats = ref<GraphStats | null>(null)
  const graphData = ref<GraphData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const building = ref(false)
  const buildError = ref<string | null>(null)
  const repositories = ref<string[]>([])
  const metrics = ref<RepositoryMetrics | null>(null)

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

  const buildGraph = async (repository: string = 'MnemoLite', language: string = 'python') => {
    building.value = true
    buildError.value = null

    try {
      const response = await fetch('http://localhost:8001/v1/code/graph/build', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repository,
          language,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(errorData.detail || `Failed to build graph: ${response.status}`)
      }

      const data = await response.json()
      stats.value = data

      // Refresh stats after build
      await fetchStats(repository)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      buildError.value = errorMessage
      console.error('Graph build error:', err)
    } finally {
      building.value = false
    }
  }

  const fetchGraphData = async (repository: string = 'MnemoLite', limit: number = 500) => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(
        `http://localhost:8001/v1/code/graph/data/${repository}?limit=${limit}`
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch graph data: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      graphData.value = data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Graph data error:', err)
      graphData.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchRepositories = async () => {
    try {
      const response = await fetch('http://localhost:8001/v1/code/graph/repositories')

      if (!response.ok) {
        throw new Error(`Failed to fetch repositories: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      repositories.value = data
    } catch (err) {
      console.error('Failed to fetch repositories:', err)
      repositories.value = []
    }
  }

  const fetchMetrics = async (repository: string = 'MnemoLite') => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`http://localhost:8001/v1/code/graph/metrics/${repository}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      metrics.value = data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      error.value = errorMessage
      console.error('Metrics error:', err)
      metrics.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    graphData,
    loading,
    error,
    building,
    buildError,
    repositories,
    metrics,
    fetchStats,
    fetchGraphData,
    buildGraph,
    fetchRepositories,
    fetchMetrics,
  }
}
