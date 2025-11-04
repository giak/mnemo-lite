<script setup lang="ts">
/**
 * EPIC-26: Embeddings Widget
 * Displays text/code embedding stats + health alerts
 */
import { computed } from 'vue'
import type { EmbeddingsHealth } from '@/types/memories'

interface Props {
  health: EmbeddingsHealth | null
}

const props = defineProps<Props>()

// Status color
const statusColor = computed(() => {
  if (!props.health) return 'text-gray-400'
  switch (props.health.status) {
    case 'healthy': return 'text-green-400'
    case 'degraded': return 'text-yellow-400'
    case 'critical': return 'text-red-400'
    default: return 'text-gray-400'
  }
})

// Alert icon
function getAlertIcon(type: string): string {
  switch (type) {
    case 'error': return '❌'
    case 'warning': return '⚠️'
    case 'info': return 'ℹ️'
    default: return '•'
  }
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 h-full">
    <h2 class="text-lg font-semibold text-cyan-400 mb-4">
      🧠 Embeddings Status
    </h2>

    <!-- Text Embeddings Widget -->
    <div class="bg-slate-700 border border-slate-600 rounded-lg p-3 mb-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold text-purple-400">📝 Text Embeddings</span>
        <span
          class="text-xs px-2 py-0.5 rounded"
          :class="health && health.text_embeddings.success_rate >= 95 ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'"
        >
          {{ health ? `${health.text_embeddings.success_rate}%` : '—' }}
        </span>
      </div>

      <div class="text-xs text-gray-400 space-y-1">
        <div>Total: <span class="text-gray-200">{{ health?.text_embeddings.total.toLocaleString() || '—' }}</span></div>
        <div>With embeddings: <span class="text-gray-200">{{ health?.text_embeddings.with_embeddings.toLocaleString() || '—' }}</span></div>
        <div class="truncate">Model: <span class="text-gray-200 text-xs">{{ health?.text_embeddings.model || '—' }}</span></div>
      </div>
    </div>

    <!-- Code Embeddings Widget -->
    <div class="bg-slate-700 border border-slate-600 rounded-lg p-3 mb-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold text-emerald-400">💻 Code Embeddings</span>
        <span class="text-xs px-2 py-0.5 bg-green-600 text-white rounded">
          100%
        </span>
      </div>

      <div class="text-xs text-gray-400 space-y-1">
        <div>Total: <span class="text-gray-200">{{ health?.code_embeddings.total.toLocaleString() || '—' }}</span></div>
        <div class="truncate">Model: <span class="text-gray-200 text-xs">{{ health?.code_embeddings.model || '—' }}</span></div>
      </div>
    </div>

    <!-- Health Alerts -->
    <div class="bg-slate-700 border border-slate-600 rounded-lg p-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-semibold text-cyan-400">🚨 Alerts</span>
        <span class="text-xs px-2 py-0.5 rounded" :class="statusColor">
          {{ health?.status.toUpperCase() || 'UNKNOWN' }}
        </span>
      </div>

      <div v-if="!health || health.alerts.length === 0" class="text-xs text-green-400">
        ✅ No issues detected
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="(alert, index) in health.alerts"
          :key="index"
          class="text-xs p-2 rounded"
          :class="{
            'bg-red-900/50 text-red-300': alert.type === 'error',
            'bg-yellow-900/50 text-yellow-300': alert.type === 'warning',
            'bg-blue-900/50 text-blue-300': alert.type === 'info'
          }"
        >
          <span>{{ getAlertIcon(alert.type) }} {{ alert.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
