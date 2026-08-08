/**
 * Brain Composable
 * Fetches ALL MnemoLite data for the Brain page
 */

import { api, apiV1 } from '@/api/client'
import { ref, onMounted, onUnmounted } from 'vue'

export interface BrainData {
  // Counts
  totalRows: number
  memoriesCount: number
  chunksCount: number
  alertsCount: number
  metricsCount: number
  nodesCount: number
  edgesCount: number
  computedMetricsCount: number

  // Μ+Λ+Φ: Memory
  memories: any[]
  chunks: any[]

  // Ξ: System
  alerts: any[]
  latency: any[]
  cacheStats: any | null
  batchStatus: any | null

  // Ω: Intelligence
  graphNodes: any[]
  graphEdges: any[]
  computedMetrics: any[]
}

export function useBrain(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options

  const data = ref<BrainData>({
    totalRows: 0,
    memoriesCount: 0,
    chunksCount: 0,
    alertsCount: 0,
    metricsCount: 0,
    nodesCount: 0,
    edgesCount: 0,
    computedMetricsCount: 0,
    memories: [],
    chunks: [],
    alerts: [],
    latency: [],
    cacheStats: null,
    batchStatus: null,
    graphNodes: [],
    graphEdges: [],
    computedMetrics: []
  })

  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  // Compteur d'échecs par cycle de refresh (peuple `error`)
  let fetchStats: { total: number; failed: number; failedEndpoints: string[] } = {
    total: 0,
    failed: 0,
    failedEndpoints: []
  }

  async function safeFetch(request: Promise<Response>, fallback: any = null, label = 'unknown'): Promise<any> {
    fetchStats.total += 1
    try {
      const resp = await request
      if (!resp.ok) {
        fetchStats.failed += 1
        fetchStats.failedEndpoints.push(`${label} (HTTP ${resp.status})`)
        return fallback
      }
      return await resp.json()
    } catch {
      fetchStats.failed += 1
      fetchStats.failedEndpoints.push(label)
      return fallback
    }
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    fetchStats = { total: 0, failed: 0, failedEndpoints: [] }

    const results = await Promise.all([
      // Μ+Λ+Φ
      safeFetch(api('/memories/recent?limit=50'), [], '/memories/recent'),
      safeFetch(api('/memories/code-chunks/recent?limit=30'), { recent_chunks: [] }, '/memories/code-chunks/recent'),

      // Ξ
      safeFetch(api('/alerts/recent?limit=20'), { data: [] }, '/alerts/recent'),
      safeFetch(api('/monitoring/latency?hours=24'), { data: [] }, '/monitoring/latency'),
      safeFetch(apiV1('/cache/stats'), null, '/cache/stats'),

      // Ω
      safeFetch(apiV1('/code/graph/repositories'), [], '/code/graph/repositories'),
    ])

    const [
      memories,
      chunksResp,
      alertsResp,
      latencyResp,
      cacheStats,
      repos,
    ] = results

    // Process memories
    const memoriesList = Array.isArray(memories) ? memories : (memories?.results || [])
    const chunksList = chunksResp?.recent_chunks || []

    // Process alerts
    const alertsList = alertsResp?.data || []

    // Process latency
    const latencyList = latencyResp?.data || []

    // Get graph data for first repo
    let graphNodes: any[] = []
    let graphEdges: any[] = []
    let computedMetricsList: any[] = []

    let batchStatus: any = null

    if (repos && repos.length > 0) {
      const repo = repos[0]?.repository || repos[0]?.name || 'expanse'
      const [graphResp, metricsResp, batchResp] = await Promise.all([
        safeFetch(apiV1(`/code/graph/data/${repo}?limit=50`), null, `/code/graph/data/${repo}`),
        safeFetch(apiV1(`/code/graph/metrics/${repo}`), null, `/code/graph/metrics/${repo}`),
        safeFetch(api(`/indexing/batch/status/${repo}`), null, `/indexing/batch/status/${repo}`),
      ])

      if (graphResp) {
        graphNodes = graphResp.nodes || []
        graphEdges = graphResp.edges || []
      }
      if (metricsResp) {
        computedMetricsList = metricsResp.nodes || metricsResp.metrics || []
      }
      if (batchResp && batchResp.status !== 'not_found') {
        batchStatus = batchResp
      }
    }

    // Calculate counts
    const memoriesCount = memoriesList.length
    const chunksCount = chunksList.length
    const alertsCount = alertsList.length
    const metricsCount = latencyList.reduce((s: number, d: any) => s + (d.count || 0), 0)
    const nodesCount = graphNodes.length
    const edgesCount = graphEdges.length
    const computedMetricsCount = computedMetricsList.length

    data.value = {
      totalRows: memoriesCount + chunksCount + alertsCount + metricsCount + nodesCount + edgesCount,
      memoriesCount,
      chunksCount,
      alertsCount,
      metricsCount,
      nodesCount,
      edgesCount,
      computedMetricsCount,
      memories: memoriesList,
      chunks: chunksList,
      alerts: alertsList,
      latency: latencyList,
      cacheStats,
      batchStatus,
      graphNodes,
      graphEdges,
      computedMetrics: computedMetricsList
    }

    // Peupler `error` : null si tout va bien, message sinon (partiel ou total)
    if (fetchStats.failed === 0) {
      error.value = null
    } else if (fetchStats.failed === fetchStats.total) {
      error.value = `Backend inaccessible : ${fetchStats.total} endpoints en échec`
    } else {
      error.value = `${fetchStats.failed}/${fetchStats.total} endpoints en échec : ${fetchStats.failedEndpoints.join(', ')}`
    }

    loading.value = false
    lastUpdated.value = new Date()
  }

  onMounted(() => {
    fetchAll()
    intervalId = window.setInterval(fetchAll, refreshInterval)
  })

  onUnmounted(() => {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  })

  return { data, loading, error, lastUpdated, refresh: fetchAll }
}
