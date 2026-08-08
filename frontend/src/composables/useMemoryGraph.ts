import { ref } from 'vue'
import type { MemoryGraphData } from '../types/memory-graph'
import { API } from '../config/api'

export function useMemoryGraph() {
  const graphData = ref<MemoryGraphData>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 })
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchGraph(minScore = 0.3, limit = 100) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${API}/memories/graph?min_score=${minScore}&limit=${limit}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      graphData.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { graphData, loading, error, fetchGraph }
}
