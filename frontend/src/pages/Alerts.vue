<script setup lang="ts">
/**
 * EPIC-30 Story 30.2: Alerts Dashboard — SCADA Style
 * Real-time alert timeline with filters, ACK, and export.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { API } from '@/config/api'

interface Alert {
  id: string
  alert_type: string
  severity: string
  message: string
  created_at: string
  value: number
  threshold: number
  acknowledged: boolean
  acknowledged_at?: string
}

const alerts = ref<Alert[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const lastUpdated = ref<Date | null>(null)

// Filters
const filterSeverity = ref<string>('all')
const filterStatus = ref<string>('all') // all, active, acknowledged

// Pagination
const currentPage = ref(1)
const pageSize = 20
const totalAlerts = ref(0)

const severityLed: Record<string, string> = {
  critical: 'scada-led-red',
  warning: 'scada-led-yellow',
  info: 'scada-led-green'
}

const severityBadge: Record<string, string> = {
  critical: 'bg-red-900/50 border-red-600 text-red-300',
  warning: 'bg-yellow-900/50 border-yellow-600 text-yellow-300',
  info: 'bg-green-900/50 border-green-600 text-green-300'
}

const activeAlertCount = computed(() =>
  alerts.value.filter(a => !a.acknowledged).length
)

const filteredAlerts = computed(() => {
  let result = alerts.value
  if (filterSeverity.value !== 'all') {
    result = result.filter(a => a.severity === filterSeverity.value)
  }
  if (filterStatus.value === 'active') {
    result = result.filter(a => !a.acknowledged)
  } else if (filterStatus.value === 'acknowledged') {
    result = result.filter(a => a.acknowledged)
  }
  return result
})

const paginatedAlerts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredAlerts.value.slice(start, start + pageSize)
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredAlerts.value.length / pageSize))
)

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).toUpperCase()
}

function formatAlertType(type: string): string {
  return type.replace(/_/g, ' ').toUpperCase()
}

async function fetchAlerts() {
  loading.value = true
  try {
    const resp = await fetch(`${API}/alerts/recent?limit=100`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    alerts.value = data.data || []
    totalAlerts.value = alerts.value.length
    lastUpdated.value = new Date()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch alerts'
  } finally {
    loading.value = false
  }
}

async function ackAlert(id: string) {
  try {
    const resp = await fetch(`${API}/alerts/${id}/ack`, { method: 'POST' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await fetchAlerts()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to ack alert'
  }
}

function exportCSV() {
  const headers = ['ID', 'Type', 'Severity', 'Message', 'Created', 'Value', 'Threshold', 'Acknowledged']
  const rows = filteredAlerts.value.map(a => [
    a.id,
    a.alert_type,
    a.severity,
    `"${a.message.replace(/"/g, '""')}"`,
    a.created_at,
    a.value,
    a.threshold,
    a.acknowledged ? 'Yes' : 'No'
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `alerts-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function resetFilters() {
  filterSeverity.value = 'all'
  filterStatus.value = 'all'
  currentPage.value = 1
}

onMounted(() => {
  fetchAlerts()
})

const refreshInterval = setInterval(fetchAlerts, 15000)
onUnmounted(() => clearInterval(refreshInterval))
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header SCADA -->
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
          <span class="scada-led" :class="activeAlertCount > 0 ? 'scada-led-red' : 'scada-led-green'"></span>
          <div>
            <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Alerts</h1>
            <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
              Real-time Alert Dashboard
            </p>
          </div>
        </div>
        <div class="text-right flex items-center gap-3">
          <button
            @click="exportCSV"
            class="scada-btn scada-btn-ghost text-xs"
            title="Export CSV"
          >
            EXPORT CSV
          </button>
          <button
            @click="fetchAlerts"
            :disabled="loading"
            class="scada-btn scada-btn-primary"
          >
            {{ loading ? 'REFRESHING...' : 'REFRESH' }}
          </button>
          <p class="mt-2 text-xs text-gray-500 font-mono uppercase">
            {{ activeAlertCount }} ACTIVE / {{ totalAlerts }} TOTAL
          </p>
        </div>
      </div>

      <!-- Error Banner -->
      <div v-if="error" class="mb-6 bg-red-950/50 border-l-4 border-red-500 p-4">
        <div class="flex items-center gap-2">
          <span class="scada-led scada-led-red"></span>
          <span class="text-sm text-red-400 font-mono">{{ error }}</span>
        </div>
      </div>

      <!-- Filters -->
      <div class="scada-panel mb-6">
        <div class="flex items-center gap-4 flex-wrap">
          <span class="scada-label text-cyan-400">Filters:</span>
          <select
            v-model="filterSeverity"
            @change="currentPage = 1"
            class="bg-slate-800 border border-slate-600 text-slate-300 text-xs font-mono px-3 py-1.5 rounded focus:border-cyan-500 focus:outline-none"
          >
            <option value="all">ALL SEVERITIES</option>
            <option value="critical">CRITICAL</option>
            <option value="warning">WARNING</option>
            <option value="info">INFO</option>
          </select>
          <select
            v-model="filterStatus"
            @change="currentPage = 1"
            class="bg-slate-800 border border-slate-600 text-slate-300 text-xs font-mono px-3 py-1.5 rounded focus:border-cyan-500 focus:outline-none"
          >
            <option value="all">ALL STATUS</option>
            <option value="active">ACTIVE ONLY</option>
            <option value="acknowledged">ACKNOWLEDGED ONLY</option>
          </select>
          <button
            @click="resetFilters"
            class="scada-btn scada-btn-ghost text-xs"
          >
            RESET
          </button>
          <span class="ml-auto text-xs font-mono text-slate-500">
            {{ filteredAlerts.length }} RESULTS
          </span>
        </div>
      </div>

      <!-- Alert Timeline -->
      <div class="scada-panel">
        <div class="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
          <div
            v-for="alert in paginatedAlerts"
            :key="alert.id"
            class="border rounded px-4 py-3 transition-colors"
            :class="alert.acknowledged
              ? 'bg-slate-800/30 border-slate-700 opacity-60'
              : 'bg-slate-800/70 border-slate-600 hover:border-cyan-600'"
          >
            <div class="flex items-center gap-3 mb-2">
              <span class="scada-led" :class="severityLed[alert.severity] || 'scada-led-yellow'"></span>
              <span class="font-mono text-xs font-bold uppercase px-2 py-0.5 rounded border"
                :class="severityBadge[alert.severity] || severityBadge.warning">
                {{ alert.severity }}
              </span>
              <span class="font-mono text-sm text-cyan-400 uppercase">{{ formatAlertType(alert.alert_type) }}</span>
              <span class="ml-auto text-xs font-mono text-slate-500">{{ formatDate(alert.created_at) }}</span>
            </div>
            <div class="flex items-center gap-3 ml-6">
              <span class="font-mono text-xs text-slate-300">{{ alert.message }}</span>
              <div class="ml-auto flex items-center gap-3 text-xs font-mono text-slate-500">
                <span>Value: <span class="text-slate-300">{{ alert.value }}</span></span>
                <span>Threshold: <span class="text-slate-300">{{ alert.threshold }}</span></span>
                <span v-if="alert.acknowledged && alert.acknowledged_at" class="text-green-500">
                  ACK: {{ formatDate(alert.acknowledged_at) }}
                </span>
              </div>
              <button
                v-if="!alert.acknowledged"
                @click="ackAlert(alert.id)"
                class="scada-btn scada-btn-ghost text-xs px-3 py-1"
                title="Acknowledge this alert"
              >
                ACK
              </button>
            </div>
          </div>

          <div v-if="filteredAlerts.length === 0" class="text-center py-12">
            <span class="scada-led scada-led-green"></span>
            <p class="text-lg text-gray-400 font-mono mt-4">NO ALERTS MATCHING FILTERS</p>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between mt-4 pt-4 border-t border-slate-700">
          <button
            @click="currentPage = Math.max(1, currentPage - 1)"
            :disabled="currentPage === 1"
            class="scada-btn scada-btn-ghost text-xs"
          >
            ← PREV
          </button>
          <span class="text-xs font-mono text-slate-400">
            Page {{ currentPage }} / {{ totalPages }}
          </span>
          <button
            @click="currentPage = Math.min(totalPages, currentPage + 1)"
            :disabled="currentPage === totalPages"
            class="scada-btn scada-btn-ghost text-xs"
          >
            NEXT →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
