<script setup lang="ts">
/**
 * EPIC-27: Memories Monitor Stats Bar - SCADA Industrial Style
 * Top stats bar with LED indicators and monospace data
 */
import { computed } from 'vue'
import type { MemoriesStats } from '@/types/memories'

interface Props {
  stats: MemoriesStats | null
  lastUpdated: Date | null
}

const props = defineProps<Props>()

// Format relative time (e.g., "5min ago")
function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return 'NEVER'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}S AGO`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}MIN AGO`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}H AGO`
  return `${Math.floor(diffSec / 86400)}D AGO`
}

// LED class based on embedding rate
const embeddingLedClass = computed(() => {
  if (!props.stats) return 'scada-led-cyan'
  if (props.stats.embedding_rate >= 95) return 'scada-led-green'
  if (props.stats.embedding_rate >= 85) return 'scada-led-yellow'
  return 'scada-led-red'
})

// Text color based on embedding rate
const embeddingColorClass = computed(() => {
  if (!props.stats) return 'text-cyan-400'
  if (props.stats.embedding_rate >= 95) return 'text-green-400'
  if (props.stats.embedding_rate >= 85) return 'text-yellow-400'
  return 'text-red-400'
})

// Format last updated
const lastUpdatedText = computed(() => {
  if (!props.lastUpdated) return ''
  return formatRelativeTime(props.lastUpdated.toISOString())
})
</script>

<template>
  <div class="scada-panel mb-6">
    <div class="grid grid-cols-4 gap-6">
      <!-- Total Memories -->
      <div class="text-center border-r border-slate-700 last:border-r-0">
        <div class="scada-label mb-2">Total Memories</div>
        <div class="text-2xl scada-data">
          {{ stats?.total.toLocaleString() || '—' }}
        </div>
      </div>

      <!-- Embedding Rate with LED -->
      <div class="text-center border-r border-slate-700 last:border-r-0">
        <div class="scada-label mb-2">Embeddings</div>
        <div class="flex items-center justify-center gap-2">
          <span class="scada-led" :class="embeddingLedClass"></span>
          <div class="text-2xl font-bold font-mono" :class="embeddingColorClass">
            {{ stats ? `${stats.embedding_rate}%` : '—' }}
          </div>
        </div>
      </div>

      <!-- Today's Count -->
      <div class="text-center border-r border-slate-700 last:border-r-0">
        <div class="scada-label mb-2">Added Today</div>
        <div class="text-2xl scada-data text-purple-400">
          +{{ stats?.today || 0 }}
        </div>
      </div>

      <!-- Last Activity -->
      <div class="text-center">
        <div class="scada-label mb-2">Last Activity</div>
        <div class="text-lg font-bold font-mono text-emerald-400 uppercase">
          {{ formatRelativeTime(stats?.last_activity || null) }}
        </div>
      </div>
    </div>

    <!-- Last Updated Indicator -->
    <div v-if="lastUpdated" class="text-xs text-gray-500 text-center mt-4 pt-3 border-t border-slate-700 font-mono">
      LAST UPDATED: {{ lastUpdatedText }}
    </div>
  </div>
</template>
