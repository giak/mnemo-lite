<script setup lang="ts">
/**
 * EPIC-27: Conversations Widget - SCADA Industrial Style
 * Displays recent conversations with LED indicators and monospace formatting
 */
import { computed } from 'vue'
import type { Memory } from '@/types/memories'

interface Props {
  memories: Memory[]
}

const props = defineProps<Props>()

// Emit events
defineEmits<{
  'view-detail': [id: string]
}>()

// Format relative time in UPPERCASE abbreviated format
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}S AGO`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}MIN AGO`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}H AGO`
  return `${Math.floor(diffSec / 86400)}D AGO`
}

// Extract session ID from tags (format: session:abc123...)
function extractSessionId(tags: string[]): string {
  const sessionTag = tags.find(tag => tag.startsWith('session:'))
  if (!sessionTag) return 'UNKNOWN'
  return sessionTag.replace('session:', '').substring(0, 8).toUpperCase()
}

// Format full date in French: "8 novembre 2025 07:18:03"
function formatFullDate(isoString: string): string {
  const date = new Date(isoString)
  const months = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
  ]
  const day = date.getDate()
  const month = months[date.getMonth()]
  const year = date.getFullYear()
  const time = date.toLocaleTimeString('fr-FR')
  return `${day} ${month} ${year} ${time}`
}

// Get short label for memory type
function getMemoryTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    conversation: 'Conv:',
    note: 'Note:',
    decision: 'Dec:',
    task: 'Task:',
    reference: 'Ref:'
  }
  return labels[type] || 'Conv:'
}
</script>

<template>
  <div class="scada-panel h-full">
    <!-- Header avec LED -->
    <div class="flex items-center gap-3 mb-4 pb-3 border-b-2 border-slate-700">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="text-lg scada-label text-cyan-400">
        Recent Conversations
      </h2>
    </div>

    <!-- Empty State -->
    <div v-if="memories.length === 0" class="text-gray-400 text-sm text-center py-8 font-mono uppercase">
      No Conversations Found
    </div>

    <!-- Conversations List -->
    <div v-else class="space-y-3 overflow-y-auto h-full">
      <div
        v-for="memory in memories"
        :key="memory.id"
        class="border-2 border-slate-600 rounded p-3 hover:bg-slate-700 transition-colors"
      >
        <!-- Header: Full Date + Author -->
        <div class="flex items-center justify-between text-xs text-gray-400 mb-2 font-mono">
          <span>{{ formatFullDate(memory.created_at) }}</span>
          <span class="uppercase">{{ memory.author || 'Unknown' }}</span>
        </div>

        <!-- Title with Type Prefix -->
        <div class="text-sm text-gray-200 mb-2 font-medium line-clamp-2">
          <span class="text-cyan-400">{{ getMemoryTypeLabel(memory.memory_type) }}</span>
          {{ memory.title }}
        </div>

        <!-- Project (conditional) -->
        <div v-if="memory.project_id" class="text-xs text-cyan-400 mb-2 flex items-center gap-1">
          <span>📁</span>
          <span class="uppercase font-mono">{{ memory.project_id }}</span>
        </div>

        <!-- Tags + Session -->
        <div class="flex flex-wrap gap-1 mb-2">
          <span
            v-for="tag in memory.tags.filter(t => !t.startsWith('session:') && !t.startsWith('date:')).slice(0, 3)"
            :key="tag"
            class="text-xs px-2 py-0.5 bg-slate-600 text-gray-300 rounded border border-slate-500 font-mono"
          >
            {{ tag }}
          </span>
          <span
            v-if="memory.tags.filter(t => !t.startsWith('session:') && !t.startsWith('date:')).length > 3"
            class="text-xs px-2 py-0.5 text-gray-400 font-mono"
          >
            +{{ memory.tags.filter(t => !t.startsWith('session:') && !t.startsWith('date:')).length - 3 }}
          </span>
          <span class="text-xs px-2 py-0.5 bg-slate-700 text-cyan-400 rounded border border-cyan-700 font-mono uppercase">
            session:{{ extractSessionId(memory.tags) }}
          </span>
        </div>

        <!-- Footer: Embedding Status + View Button -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="scada-led" :class="memory.has_embedding ? 'scada-led-green' : 'scada-led-yellow'"></span>
            <span class="text-xs font-mono uppercase" :class="memory.has_embedding ? 'scada-status-healthy' : 'scada-status-warning'">
              {{ memory.has_embedding ? 'Embedded' : 'No Embedding' }}
            </span>
          </div>
          <button
            class="scada-btn scada-btn-primary text-xs px-3 py-1"
            @click="$emit('view-detail', memory.id)"
          >
            View
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
