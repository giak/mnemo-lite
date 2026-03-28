/**
 * Brain Composable
 * Fetches ALL MnemoLite data for the Brain page
 */

import { ref, onMounted, onUnmounted } from 'vue'

const API = 'http://localhost:8001/api/v1'
const API_V1 = 'http://localhost:8001/v1'

export interface BrainData {
  // Counts
  totalRows: number
  memoriesCount: number
  chunksCount: number
  eventsCount: number
  alertsCount: number
  metricsCount: number
  nodesCount: number
  edgesCount: number
  computedMetricsCount: number
  edgeWeightsCount: number

  // Μ+Λ+Φ: Memory
  memories: any[]
  memoryStats: any | null
  chunks: any[]
  events: any[]
  vocabfWords: any[]

  // Ξ: System
  alerts: any[]
  alertSummary: any[]
  latency: any[]
  indexingErrors: any[]
  decayConfig: any[]
  cacheStats: any | null
  autosaveStats: any | null
  batchStatus: any | null

  // Ω: Intelligence
  graphNodes: any[]
  graphEdges: any[]
  graphStats: any | null
  computedMetrics: any[]
  edgeWeights: any[]
  searchResults: any[]
}

export function useBrain(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options

  const data = ref<BrainData>({
    totalRows: 0,
    memoriesCount: 0,
    chunksCount: 0,
    eventsCount: 0,
    alertsCount: 0,
    metricsCount: 0,
    nodesCount: 0,
    edgesCount: 0,
    computedMetricsCount: 0,
    edgeWeightsCount: 0,
    memories: [],
    memoryStats: null,
    chunks: [],
    events: [],
    vocabfWords: [],
    alerts: [],
    alertSummary: [],
    latency: [],
    indexingErrors: [],
    decayConfig: [],
    cacheStats: null,
    autosaveStats: null,
    batchStatus: null,
    graphNodes: [],
    graphEdges: [],
    graphStats: null,
    computedMetrics: [],
    edgeWeights: [],
    searchResults: []
  })

  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  async function safeFetch(url: string, fallback: any = null): Promise<any> {
    try {
      const resp = await fetch(url)
      if (!resp.ok) return fallback
      return await resp.json()
    } catch {
      return fallback
    }
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null

    const results = await Promise.all([
      // Μ+Λ+Φ
      safeFetch(`${API}/memories/recent?limit=50`, []),
      safeFetch(`${API}/memories/stats`, null),
      safeFetch(`${API}/memories/code-chunks/recent?limit=30`, { recent_chunks: [] }),
      safeFetch(`${API_V1}/events/cache/stats`, null),

      // Ξ
      safeFetch(`${API}/alerts/recent?limit=20`, { data: [] }),
      safeFetch(`${API}/alerts/summary`, { data: [] }),
      safeFetch(`${API}/monitoring/latency?hours=24`, { data: [] }),
      safeFetch(`${API}/memories/decay/config`, { data: [] }),
      safeFetch(`${API_V1}/cache/stats`, null),
      safeFetch(`${API_V1}/autosave/stats`, null),

      // Ω
      safeFetch(`${API_V1}/code/graph/repositories`, []),
      safeFetch(`${API_V1}/cache/stats`, null),
    ])

    const [
      memories,
      memoryStats,
      chunksResp,
      eventsStats,

      alertsResp,
      alertSummaryResp,
      latencyResp,
      decayConfigResp,
      cacheStats,
      autosaveStats,

      repos,
      _cacheStatsDup,
    ] = results

    // Process memories
    const memoriesList = Array.isArray(memories) ? memories : (memories?.results || [])
    const chunksList = chunksResp?.recent_chunks || []

    // Process alerts
    const alertsList = alertsResp?.data || []
    const alertSummaryList = alertSummaryResp?.data || []

    // Process latency
    const latencyList = latencyResp?.data || []

    // Process decay config
    const decayList = decayConfigResp?.data || []

    // Get graph data for first repo
    let graphNodes: any[] = []
    let graphEdges: any[] = []
    let graphStats: any = null
    let computedMetricsList: any[] = []
    let edgeWeightsList: any[] = []

    if (repos && repos.length > 0) {
      const repo = repos[0]?.repository || repos[0]?.name || 'expanse'
      const [graphResp, metricsResp] = await Promise.all([
        safeFetch(`${API_V1}/code/graph/data/${repo}?limit=50`, null),
        safeFetch(`${API_V1}/code/graph/metrics/${repo}`, null),
      ])

      if (graphResp) {
        graphNodes = graphResp.nodes || []
        graphEdges = graphResp.edges || []
        graphStats = graphResp.stats || null
      }
      if (metricsResp) {
        computedMetricsList = metricsResp.nodes || metricsResp.metrics || []
      }
    }

    // Calculate counts
    const memoriesCount = memoriesList.length
    const chunksCount = chunksList.length
    const eventsCount = eventsStats?.total || 0
    const alertsCount = alertsList.length
    const metricsCount = latencyList.reduce((s: number, d: any) => s + (d.count || 0), 0)
    const nodesCount = graphNodes.length
    const edgesCount = graphEdges.length
    const computedMetricsCount = computedMetricsList.length
    const edgeWeightsCount = edgeWeightsList.length

    data.value = {
      totalRows: memoriesCount + chunksCount + eventsCount + alertsCount + metricsCount + nodesCount + edgesCount,
      memoriesCount,
      chunksCount,
      eventsCount,
      alertsCount,
      metricsCount,
      nodesCount,
      edgesCount,
      computedMetricsCount,
      edgeWeightsCount,
      memories: memoriesList,
      memoryStats,
      chunks: chunksList,
      events: [],
      vocabfWords: [],
      alerts: alertsList,
      alertSummary: alertSummaryList,
      latency: latencyList,
      indexingErrors: [],
      decayConfig: decayList,
      cacheStats,
      autosaveStats,
      batchStatus: null,
      graphNodes,
      graphEdges,
      graphStats,
      computedMetrics: computedMetricsList,
      edgeWeights: edgeWeightsList,
      searchResults: []
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
