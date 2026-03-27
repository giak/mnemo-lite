/**
 * Monitoring Composable
 * Fetches metrics and alerts from the MnemoLite API
 */

import { ref, onMounted, onUnmounted } from 'vue'

const API_BASE_URL = '/api/v1'

export interface LatencyPoint {
  hour: string
  avg: number
  p95: number
  max: number
  count: number
}

export interface AlertSummary {
  alert_type: string
  severity: string
  unacked: number
  total: number
}

export interface Alert {
  id: string
  alert_type: string
  severity: string
  message: string
  created_at: string
  value: number
  threshold: number
  acknowledged: boolean
}

export function useMonitoring(options: { refreshInterval?: number } = {}) {
  const { refreshInterval = 30000 } = options

  const latency = ref<LatencyPoint[]>([])
  const alertSummary = ref<AlertSummary[]>([])
  const recentAlerts = ref<Alert[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)

  let intervalId: number | null = null

  async function fetchLatency(): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE_URL}/monitoring/latency?hours=24`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      latency.value = data.data || []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch latency'
    }
  }

  async function fetchAlertSummary(): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE_URL}/alerts/summary`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      alertSummary.value = data.data || []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch alert summary'
    }
  }

  async function fetchRecentAlerts(): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE_URL}/alerts/recent?limit=20`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      recentAlerts.value = data.data || []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch alerts'
    }
  }

  async function ackAlert(id: string): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE_URL}/alerts/${id}/ack`, { method: 'POST' })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      // Refresh alerts after ack
      await fetchAlertSummary()
      await fetchRecentAlerts()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to ack alert'
    }
  }

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    await Promise.all([
      fetchLatency(),
      fetchAlertSummary(),
      fetchRecentAlerts()
    ])
    loading.value = false
    lastUpdated.value = new Date()
  }

  onMounted(() => {
    refresh()
    intervalId = window.setInterval(refresh, refreshInterval)
  })

  onUnmounted(() => {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  })

  return {
    latency,
    alertSummary,
    recentAlerts,
    loading,
    error,
    lastUpdated,
    refresh,
    ackAlert
  }
}
