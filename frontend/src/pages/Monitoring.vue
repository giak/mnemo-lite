<script setup lang="ts">
/**
 * Monitoring Page — SCADA Industrial Style
 * API latency chart + Alerts summary + Recent alerts
 */
import { computed } from 'vue'
import { useMonitoring } from '@/composables/useMonitoring'
import LatencyChart from '@/components/LatencyChart.vue'

const { latency, alertSummary, recentAlerts, loading, error, lastUpdated, refresh, ackAlert } = useMonitoring({
  refreshInterval: 30000
})

// LED color by severity
const severityLed: Record<string, string> = {
  critical: 'red',
  warning: 'yellow',
  info: 'green'
}

// Aggregate alerts by type
const alertsByType = computed(() => {
  const grouped: Record<string, { severity: string; unacked: number; total: number }> = {}
  for (const a of alertSummary.value) {
    const key = a.alert_type
    if (!grouped[key]) {
      grouped[key] = { severity: a.severity, unacked: 0, total: 0 }
    }
    grouped[key].unacked += a.unacked
    grouped[key].total += a.total
  }
  return Object.entries(grouped)
    .sort((a, b) => {
      if (a[1].severity === 'critical' && b[1].severity !== 'critical') return -1
      if (b[1].severity === 'critical' && a[1].severity !== 'critical') return 1
      return b[1].unacked - a[1].unacked
    })
})

// Format alert type for display
function formatAlertType(type: string): string {
  return type.replace(/_/g, ' ').toUpperCase()
}

// Format date
function formatDate(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

const formattedTime = computed(() => {
  if (!lastUpdated.value) return '--:--:--'
  return lastUpdated.value.toLocaleTimeString()
})
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Monitoring</h1>
      </div>

      <div class="flex items-center gap-4">
        <span class="scada-data text-slate-400 font-mono text-sm">
          LAST UPDATE: {{ formattedTime }}
        </span>
        <button
          @click="refresh"
          :disabled="loading"
          class="scada-btn scada-btn-primary flex items-center gap-2"
        >
          <span v-if="loading">⏳</span>
          <span v-else>🔄</span>
          {{ loading ? 'LOADING...' : 'REFRESH' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4">
      <div class="bg-red-900/50 border-2 border-red-600 text-red-300 px-4 py-3 rounded flex items-center gap-3">
        <span class="scada-led scada-led-red"></span>
        <span class="text-sm font-mono">{{ error }}</span>
      </div>
    </div>

    <!-- Latency Chart -->
    <div class="scada-panel mb-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="scada-led scada-led-cyan"></span>
        <h2 class="scada-label text-cyan-400">API Latency (24h)</h2>
        <span v-if="latency.length > 0" class="scada-data text-slate-400 text-sm ml-auto">
          {{ Math.round(latency.reduce((s, d) => s + d.avg, 0) / latency.length) }}ms avg
        </span>
      </div>
      <LatencyChart :data="latency" />
    </div>

    <!-- 2-Column: Alert Summary + Recent Alerts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- Col 1: Alert Summary -->
      <div class="scada-panel">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-yellow"></span>
          <h2 class="scada-label text-cyan-400">Alert Summary</h2>
        </div>

        <div class="space-y-3">
          <div
            v-for="[type, info] in alertsByType"
            :key="type"
            class="bg-slate-800/50 border border-slate-700 rounded px-4 py-3 flex items-center justify-between"
          >
            <div class="flex items-center gap-3">
              <span class="scada-led" :class="`scada-led-${severityLed[info.severity] || 'yellow'}`"></span>
              <span class="font-mono text-sm text-slate-300 uppercase">{{ formatAlertType(type) }}</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="scada-data text-sm font-mono" :class="info.unacked > 0 ? 'text-red-400' : 'text-slate-500'">
                {{ info.unacked.toLocaleString() }}
              </span>
              <span class="text-xs font-mono text-slate-600">unacked</span>
            </div>
          </div>

          <div v-if="alertsByType.length === 0" class="scada-data text-slate-500 text-center py-8">
            NO ALERTS
          </div>
        </div>
      </div>

      <!-- Col 2: Recent Alerts -->
      <div class="scada-panel">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-red"></span>
          <h2 class="scada-label text-cyan-400">Recent Alerts</h2>
          <span class="scada-data text-slate-400 text-sm ml-auto">{{ recentAlerts.length }}</span>
        </div>

        <div class="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
          <div
            v-for="alert in recentAlerts"
            :key="alert.id"
            class="bg-slate-800/50 border rounded px-3 py-2"
            :class="alert.acknowledged ? 'border-slate-700 opacity-50' : 'border-red-800/50'"
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="scada-led" :class="`scada-led-${severityLed[alert.severity] || 'yellow'}`"></span>
              <span class="font-mono text-xs text-slate-400">{{ formatDate(alert.created_at) }}</span>
              <span class="font-mono text-xs uppercase" :class="alert.severity === 'critical' ? 'text-red-400' : 'text-amber-400'">
                {{ alert.alert_type.replace(/_/g, ' ') }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span class="font-mono text-xs text-slate-500">{{ alert.message }}</span>
              <button
                v-if="!alert.acknowledged"
                @click="ackAlert(alert.id)"
                class="ml-auto text-[10px] font-mono px-2 py-0.5 rounded bg-slate-700 text-slate-400 hover:text-cyan-400 hover:border-cyan-600 border border-slate-600 transition-colors"
              >
                ACK
              </button>
            </div>
          </div>

          <div v-if="recentAlerts.length === 0" class="scada-data text-slate-500 text-center py-8">
            NO RECENT ALERTS
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
