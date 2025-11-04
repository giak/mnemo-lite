<script setup lang="ts">
/**
 * EPIC-26: Code Chunks Widget
 * Displays indexing activity stats + recent code chunks
 */
import { computed } from 'vue'
import type { CodeChunksResponse } from '@/types/memories'

interface Props {
  data: CodeChunksResponse | null
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

// Extract filename from path
function getFilename(path: string): string {
  return path.split('/').pop() || path
}

// Get language color badge
function getLanguageColor(language: string): string {
  const colors: Record<string, string> = {
    python: 'bg-blue-600',
    javascript: 'bg-yellow-600',
    typescript: 'bg-blue-500',
    go: 'bg-cyan-600',
    rust: 'bg-orange-600',
    java: 'bg-red-600'
  }
  return colors[language.toLowerCase()] || 'bg-gray-600'
}
</script>

<template>
  <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 h-full">
    <h2 class="text-lg font-semibold text-cyan-400 mb-4">
      💻 Code Indexing Activity
    </h2>

    <!-- Stats Box -->
    <div v-if="data" class="bg-slate-700 border border-slate-600 rounded-lg p-3 mb-4">
      <div class="text-sm text-gray-400 mb-2">📊 Today's Activity</div>
      <div class="grid grid-cols-2 gap-2 text-center">
        <div>
          <div class="text-xl font-bold text-purple-400">
            +{{ data.indexing_stats.chunks_today }}
          </div>
          <div class="text-xs text-gray-400">chunks</div>
        </div>
        <div>
          <div class="text-xl font-bold text-emerald-400">
            {{ data.indexing_stats.files_today }}
          </div>
          <div class="text-xs text-gray-400">files</div>
        </div>
      </div>
    </div>

    <!-- Recent Chunks List -->
    <div class="text-sm text-gray-400 mb-2">Latest Chunks:</div>

    <div v-if="!data || data.recent_chunks.length === 0" class="text-gray-400 text-sm text-center py-8">
      No code chunks found
    </div>

    <div v-else class="space-y-2 overflow-y-auto max-h-[450px]">
      <div
        v-for="chunk in data.recent_chunks"
        :key="chunk.id"
        class="border border-slate-600 rounded-lg p-2 hover:bg-slate-700 transition-colors"
      >
        <!-- File + Language -->
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs text-gray-300 truncate flex-1">
            {{ getFilename(chunk.file_path) }}
          </span>
          <span
            class="text-xs px-2 py-0.5 rounded text-white ml-2"
            :class="getLanguageColor(chunk.language)"
          >
            {{ chunk.language }}
          </span>
        </div>

        <!-- Chunk Type + Preview -->
        <div class="text-xs text-gray-400 mb-1">
          <span class="text-cyan-400">{{ chunk.chunk_type }}</span>
          <span v-if="chunk.content_preview"> - {{ chunk.content_preview }}</span>
        </div>

        <!-- Repo + Time -->
        <div class="flex items-center justify-between text-xs text-gray-500">
          <span>{{ chunk.repository }}</span>
          <span>{{ formatRelativeTime(chunk.indexed_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
