<script setup lang="ts">
/**
 * EPIC-26: Memories Monitor Stats Bar
 * Top stats bar showing: Total | Embedding Rate | Today | Last Activity
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
  if (!isoString) return 'Never'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}min ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

// Embedding rate status color
const embeddingRateColor = computed(() => {
  if (!props.stats) return 'text-gray-400'
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
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
    <div class="grid grid-cols-4 gap-4">
      <!-- Total Memories -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Total Memories</div>
        <div class="text-2xl font-bold text-cyan-400">
          {{ stats?.total.toLocaleString() || '—' }}
        </div>
      </div>

      <!-- Embedding Rate -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Embeddings</div>
        <div class="text-2xl font-bold" :class="embeddingRateColor">
          {{ stats ? `${stats.embedding_rate}%` : '—' }}
          <span v-if="stats && stats.embedding_rate >= 95" class="text-sm">✅</span>
          <span v-else-if="stats && stats.embedding_rate >= 85" class="text-sm">⚠️</span>
          <span v-else-if="stats" class="text-sm">❌</span>
        </div>
      </div>

      <!-- Today's Count -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Added Today</div>
        <div class="text-2xl font-bold text-purple-400">
          +{{ stats?.today || 0 }}
        </div>
      </div>

      <!-- Last Activity -->
      <div class="text-center">
        <div class="text-sm text-gray-400 mb-1">Last Activity</div>
        <div class="text-2xl font-bold text-emerald-400">
          {{ formatRelativeTime(stats?.last_activity || null) }}
        </div>
      </div>
    </div>

    <!-- Last Updated Indicator -->
    <div v-if="lastUpdated" class="text-xs text-gray-500 text-center mt-3">
      Last updated: {{ lastUpdatedText }}
    </div>
  </div>
</template>
