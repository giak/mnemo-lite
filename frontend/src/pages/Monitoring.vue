<script setup lang="ts">
/**
 * Monitoring Page — SCADA Industrial Style
 * API latency chart + Alerts summary + Recent alerts
 * With tooltips, legends, and help text for clarity
 */
import { computed, ref } from 'vue'
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

// Alert type descriptions
const alertDescriptions: Record<string, string> = {
  slow_queries: 'Requêtes DB dépassant 500ms — index manquant ou query mal optimisée',
  cache_hit_rate_low: 'Taux de cache < 70% — le cache n\'est pas efficace, trop de requêtes DB',
  error_rate_high: 'Taux d\'erreur API > 10% — beaucoup de requêtes échouent',
  memory_high: 'Utilisation RAM > 80% — risque de crash OOM',
  cpu_high: 'Utilisation CPU > 90% — serveur surchargé'
}

// Severity descriptions
const severityDescriptions: Record<string, string> = {
  critical: 'Alerte critique — nécessite une action immédiate',
  warning: 'Alerte warning — à surveiller, pas encore bloquant',
  info: 'Information — pas d\'action requise'
}

// Health status
const healthStatus = computed(() => {
  const critCount = alertSummary.value
    .filter(a => a.severity === 'critical')
    .reduce((s, a) => s + a.unacked, 0)
  const warnCount = alertSummary.value
    .filter(a => a.severity === 'warning')
    .reduce((s, a) => s + a.unacked, 0)

  if (critCount > 100) return { label: 'CRITICAL', color: 'red', led: 'scada-led-red' }
  if (critCount > 0) return { label: 'WARNING', color: 'amber', led: 'scada-led-yellow' }
  if (warnCount > 0) return { label: 'NOMINAL', color: 'yellow', led: 'scada-led-yellow' }
  return { label: 'HEALTHY', color: 'green', led: 'scada-led-green' }
})

// Show help toggle
const showHelp = ref(false)

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

function formatAlertType(type: string): string {
  return type.replace(/_/g, ' ').toUpperCase()
}

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

// Chart stats
const chartAvg = computed(() => {
  if (latency.value.length === 0) return 0
  return Math.round(latency.value.reduce((s, d) => s + d.avg, 0) / latency.value.length)
})
const chartMax = computed(() => {
  if (latency.value.length === 0) return 0
  return Math.round(Math.max(...latency.value.map(d => d.max)))
})
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <span class="scada-led" :class="healthStatus.led"></span>
        <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Monitoring</h1>
        <span
          class="scada-status uppercase text-sm font-bold"
          :class="`text-${healthStatus.color}-400`"
        >{{ healthStatus.label }}</span>
      </div>

      <div class="flex items-center gap-4">
        <button
          @click="showHelp = !showHelp"
          class="scada-btn scada-btn-ghost flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-700 hover:border-cyan-600 hover:text-cyan-400 transition-colors"
          :class="showHelp ? 'border-cyan-600 text-cyan-400 bg-slate-800' : ''"
          title="Afficher l'aide"
        >
          <span class="text-lg font-bold">?</span>
          <span class="text-xs hidden md:inline">AIDE</span>
        </button>
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

    <!-- Help Panel -->
    <Transition name="slide">
      <div v-if="showHelp" class="scada-panel mb-6 bg-slate-800/30">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-cyan"></span>
          <h2 class="scada-label text-cyan-400">Aide — Monitoring</h2>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm font-mono">
          <!-- Chart help -->
          <div>
            <div class="text-cyan-400 uppercase text-xs mb-2">Graphique Latence</div>
            <div class="space-y-1 text-slate-400">
              <div><span class="text-cyan-400">● Avg</span> — Temps de réponse moyen des requêtes API</div>
              <div><span class="text-amber-400">-- P95</span> — 95% des requêtes sont plus rapides que cette valeur</div>
              <div><span class="text-red-400">— Max</span> — Requête la plus lente de l'heure</div>
              <div class="text-slate-500 mt-2">Idéal: &lt;200ms avg. Attention: &gt;500ms. Critique: &gt;2s</div>
            </div>
          </div>
          <!-- Severity help -->
          <div>
            <div class="text-cyan-400 uppercase text-xs mb-2">LED Severity</div>
            <div class="space-y-1 text-slate-400">
              <div><span class="scada-led scada-led-red"></span> Critical — Action immédiate requise</div>
              <div><span class="scada-led scada-led-yellow"></span> Warning — À surveiller</div>
              <div><span class="scada-led scada-led-green"></span> Info — Tout va bien</div>
            </div>
          </div>
          <!-- Actions help -->
          <div>
            <div class="text-cyan-400 uppercase text-xs mb-2">Actions</div>
            <div class="space-y-1 text-slate-400">
              <div><span class="scada-btn text-[10px] px-2 py-0.5">ACK</span> — Acquitter une alerte (marquer comme vue)</div>
              <div>🔄 REFRESH — Recharger les données (auto: 30s)</div>
              <div>? — Afficher/masquer cette aide</div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

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
        <!-- Chart stats -->
        <div class="flex items-center gap-4 ml-auto">
          <div class="flex items-center gap-2" title="Temps de réponse moyen sur 24h">
            <span class="w-3 h-0.5 bg-cyan-400 inline-block"></span>
            <span class="text-xs font-mono text-slate-400">Avg: <span class="text-cyan-400">{{ chartAvg }}ms</span></span>
          </div>
          <div class="flex items-center gap-2" title="Requête la plus lente sur 24h">
            <span class="w-3 h-0.5 bg-red-400 inline-block"></span>
            <span class="text-xs font-mono text-slate-400">Max: <span class="text-red-400">{{ chartMax }}ms</span></span>
          </div>
          <div class="flex items-center gap-2" title="Nombre d'intervalles horaires avec des données">
            <span class="text-xs font-mono text-slate-500">{{ latency.length }}h</span>
          </div>
        </div>
      </div>
      <LatencyChart :data="latency" />
      <!-- Chart legend -->
      <div class="flex items-center gap-6 mt-3 text-xs font-mono text-slate-500">
        <div class="flex items-center gap-2">
          <span class="w-3 h-0.5 bg-cyan-400 inline-block"></span>
          <span>Avg — Temps moyen</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-3 h-0.5 bg-amber-400 inline-block border-dashed"></span>
          <span>P95 — 95e percentile (la plupart des requêtes sont plus rapides)</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-3 h-0.5 bg-red-400 inline-block"></span>
          <span>Max — Requête la plus lente de l'heure</span>
        </div>
      </div>
    </div>

    <!-- 2-Column: Alert Summary + Recent Alerts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- Col 1: Alert Summary -->
      <div class="scada-panel">
        <div class="flex items-center gap-3 mb-4">
          <span class="scada-led scada-led-yellow"></span>
          <h2 class="scada-label text-cyan-400">Alert Summary</h2>
          <span class="text-[10px] font-mono text-slate-600 ml-2" title="Nombre d'alertes non acquittées par type">
            (non-acknowledged)
          </span>
        </div>

        <div class="space-y-3">
          <div
            v-for="[type, info] in alertsByType"
            :key="type"
            class="bg-slate-800/50 border border-slate-700 rounded px-4 py-3"
          >
            <div class="flex items-center justify-between mb-1">
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
            <!-- Description -->
            <div class="text-[10px] font-mono text-slate-500 ml-6">
              {{ alertDescriptions[type] || 'Alerte système' }}
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
                title="Acquitter cette alerte (marquer comme vue)"
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

<style scoped>
.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
