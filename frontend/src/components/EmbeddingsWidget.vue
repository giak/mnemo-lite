<script setup lang="ts">
/**
 * EPIC-27: Embeddings Widget - SCADA Industrial Style
 * Displays text/code embedding stats + health alerts with LED indicators
 */
import { computed } from 'vue'
import type { EmbeddingsHealth } from '@/types/memories'

interface Props {
  health: EmbeddingsHealth | null
}

const props = defineProps<Props>()

// LED class based on status
const statusLedClass = computed(() => {
  if (!props.health) return 'scada-led-cyan'
  switch (props.health.status) {
    case 'healthy': return 'scada-led-green'
    case 'degraded': return 'scada-led-yellow'
    case 'critical': return 'scada-led-red'
    default: return 'scada-led-cyan'
  }
})

// Status text color
const statusTextClass = computed(() => {
  if (!props.health) return 'scada-status-info'
  switch (props.health.status) {
    case 'healthy': return 'scada-status-healthy'
    case 'degraded': return 'scada-status-warning'
    case 'critical': return 'scada-status-danger'
    default: return 'scada-status-info'
  }
})

// LED class for success rate badge
function getSuccessRateLed(rate: number): string {
  if (rate >= 95) return 'scada-led-green'
  if (rate >= 85) return 'scada-led-yellow'
  return 'scada-led-red'
}

// Alert LED color
function getAlertLedClass(type: string): string {
  switch (type) {
    case 'error': return 'scada-led-red'
    case 'warning': return 'scada-led-yellow'
    case 'info': return 'scada-led-cyan'
    default: return 'scada-led-cyan'
  }
}
</script>

<template>
  <div class="scada-panel h-full">
    <!-- Header avec LED status -->
    <div class="flex items-center gap-3 mb-4 pb-3 border-b-2 border-slate-700">
      <span class="scada-led" :class="statusLedClass"></span>
      <h2 class="text-lg scada-label text-cyan-400">
        Embeddings Status
      </h2>
    </div>

    <!-- Text Embeddings -->
    <div class="bg-slate-700/50 border-2 border-slate-600 rounded p-3 mb-3">
      <div class="flex items-center justify-between mb-3">
        <span class="scada-label text-purple-400">Text Embeddings</span>
        <div class="flex items-center gap-2">
          <span
            v-if="health"
            class="scada-led"
            :class="getSuccessRateLed(health.text_embeddings.success_rate)"
          ></span>
          <span class="text-xs font-mono font-bold text-gray-200">
            {{ health ? `${health.text_embeddings.success_rate}%` : '—' }}
          </span>
        </div>
      </div>

      <div class="text-xs text-gray-400 space-y-1 font-mono">
        <div class="flex justify-between border-b border-slate-600 pb-1">
          <span class="scada-label text-[10px]">Total:</span>
          <span class="text-cyan-400 font-bold">{{ health?.text_embeddings.total.toLocaleString() || '—' }}</span>
        </div>
        <div class="flex justify-between border-b border-slate-600 pb-1">
          <span class="scada-label text-[10px]">With Embeddings:</span>
          <span class="text-cyan-400 font-bold">{{ health?.text_embeddings.with_embeddings.toLocaleString() || '—' }}</span>
        </div>
        <div class="truncate pt-1">
          <span class="scada-label text-[10px]">Model:</span>
          <span class="text-gray-300 text-[10px] ml-1">{{ health?.text_embeddings.model || '—' }}</span>
        </div>
      </div>
    </div>

    <!-- Code Embeddings -->
    <div class="bg-slate-700/50 border-2 border-slate-600 rounded p-3 mb-3">
      <div class="flex items-center justify-between mb-3">
        <span class="scada-label text-emerald-400">Code Embeddings</span>
        <div class="flex items-center gap-2">
          <span class="scada-led scada-led-green"></span>
          <span class="text-xs font-mono font-bold text-green-400">
            100%
          </span>
        </div>
      </div>

      <div class="text-xs text-gray-400 space-y-1 font-mono">
        <div class="flex justify-between border-b border-slate-600 pb-1">
          <span class="scada-label text-[10px]">Total:</span>
          <span class="text-cyan-400 font-bold">{{ health?.code_embeddings.total.toLocaleString() || '—' }}</span>
        </div>
        <div class="truncate pt-1">
          <span class="scada-label text-[10px]">Model:</span>
          <span class="text-gray-300 text-[10px] ml-1">{{ health?.code_embeddings.model || '—' }}</span>
        </div>
      </div>
    </div>

    <!-- Health Alerts -->
    <div class="bg-slate-700/50 border-2 border-slate-600 rounded p-3">
      <div class="flex items-center justify-between mb-3">
        <span class="scada-label text-cyan-400">System Alerts</span>
        <span class="text-xs" :class="statusTextClass">
          {{ health?.status.toUpperCase() || 'UNKNOWN' }}
        </span>
      </div>

      <div v-if="!health || health.alerts.length === 0" class="flex items-center gap-2">
        <span class="scada-led scada-led-green"></span>
        <span class="text-xs scada-status-healthy">No Issues Detected</span>
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="(alert, index) in health.alerts"
          :key="index"
          class="flex items-start gap-2 p-2 border-2 rounded"
          :class="{
            'bg-red-900/30 border-red-600': alert.type === 'error',
            'bg-yellow-900/30 border-yellow-600': alert.type === 'warning',
            'bg-blue-900/30 border-blue-600': alert.type === 'info'
          }"
        >
          <span class="scada-led flex-shrink-0 mt-0.5" :class="getAlertLedClass(alert.type)"></span>
          <span class="text-xs font-mono" :class="{
            'text-red-300': alert.type === 'error',
            'text-yellow-300': alert.type === 'warning',
            'text-blue-300': alert.type === 'info'
          }">{{ alert.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
