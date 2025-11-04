<script setup lang="ts">
/**
 * EPIC-26: Conversations Widget
 * Displays recent conversations in timeline format
 */
import { computed } from 'vue'
import type { Memory } from '@/types/memories'

interface Props {
  memories: Memory[]
}

const props = defineProps<Props>()

// Format relative time
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}min ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

// Extract session ID from tags (format: session:abc123...)
function extractSessionId(tags: string[]): string {
  const sessionTag = tags.find(tag => tag.startsWith('session:'))
  if (!sessionTag) return 'Unknown'
  return sessionTag.replace('session:', '').substring(0, 8)
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 h-full">
    <h2 class="text-lg font-semibold text-cyan-400 mb-4">
      📝 Recent Conversations
    </h2>

    <div v-if="memories.length === 0" class="text-gray-400 text-sm text-center py-8">
      No conversations found
    </div>

    <div v-else class="space-y-3 overflow-y-auto max-h-[600px]">
      <div
        v-for="memory in memories"
        :key="memory.id"
        class="border border-slate-600 rounded-lg p-3 hover:bg-slate-700 transition-colors"
      >
        <!-- Time + Session -->
        <div class="flex items-center justify-between text-xs text-gray-400 mb-2">
          <span>🕐 {{ formatRelativeTime(memory.created_at) }}</span>
          <span>Session: {{ extractSessionId(memory.tags) }}</span>
        </div>

        <!-- Title -->
        <div class="text-sm text-gray-200 mb-2 font-medium truncate">
          {{ memory.title }}
        </div>

        <!-- Tags -->
        <div class="flex flex-wrap gap-1 mb-2">
          <span
            v-for="tag in memory.tags.slice(0, 3)"
            :key="tag"
            class="text-xs px-2 py-0.5 bg-slate-600 text-gray-300 rounded"
          >
            {{ tag }}
          </span>
          <span
            v-if="memory.tags.length > 3"
            class="text-xs px-2 py-0.5 text-gray-400"
          >
            +{{ memory.tags.length - 3 }}
          </span>
        </div>

        <!-- Embedding Status + View Button -->
        <div class="flex items-center justify-between">
          <span class="text-xs" :class="memory.has_embedding ? 'text-green-400' : 'text-yellow-400'">
            {{ memory.has_embedding ? '✅ Embedded' : '⚠️ No embedding' }}
          </span>
          <button
            class="text-xs px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
            @click="$emit('view-detail', memory.id)"
          >
            👁️ View
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
