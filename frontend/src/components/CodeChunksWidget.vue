<script setup lang="ts">
/**
 * EPIC-27: Code Chunks Widget - SCADA Industrial Style
 * Displays indexing activity stats + recent code chunks with LED indicators
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

  if (diffSec < 60) return `${diffSec}S`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}MIN`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}H`
  return `${Math.floor(diffSec / 86400)}D`
}

// Extract filename from path
function getFilename(path: string): string {
  return path.split('/').pop() || path
}

// Get language color badge (using SCADA colors)
function getLanguageColor(language: string): string {
  const colors: Record<string, string> = {
    python: 'bg-blue-600 border-blue-500',
    javascript: 'bg-yellow-600 border-yellow-500',
    typescript: 'bg-blue-500 border-blue-400',
    go: 'bg-cyan-600 border-cyan-500',
    rust: 'bg-orange-600 border-orange-500',
    java: 'bg-red-600 border-red-500',
    vue: 'bg-emerald-600 border-emerald-500'
  }
  return colors[language.toLowerCase()] || 'bg-gray-600 border-gray-500'
}
</script>

<template>
  <div class="scada-panel h-full">
    <!-- Header avec LED -->
    <div class="flex items-center gap-3 mb-4 pb-3 border-b-2 border-slate-700">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="text-lg scada-label text-cyan-400">
        Code Indexing Activity
      </h2>
    </div>

    <!-- Stats Box -->
    <div v-if="data" class="bg-slate-700/50 border-2 border-slate-600 rounded p-3 mb-4">
      <div class="scada-label mb-3">Today's Activity</div>
      <div class="grid grid-cols-2 gap-4 text-center">
        <div class="border-r border-slate-600">
          <div class="text-xl scada-data text-purple-400">
            +{{ data.indexing_stats.chunks_today }}
          </div>
          <div class="scada-label text-[10px]">Chunks</div>
        </div>
        <div>
          <div class="text-xl scada-data text-emerald-400">
            {{ data.indexing_stats.files_today }}
          </div>
          <div class="scada-label text-[10px]">Files</div>
        </div>
      </div>
    </div>

    <!-- Recent Chunks List -->
    <div class="scada-label mb-2">Latest Chunks:</div>

    <div v-if="!data || data.recent_chunks.length === 0" class="text-gray-400 text-sm text-center py-8 font-mono uppercase">
      No Code Chunks Found
    </div>

    <div v-else class="space-y-2 overflow-y-auto max-h-[450px]">
      <div
        v-for="chunk in data.recent_chunks"
        :key="chunk.id"
        class="border-2 border-slate-600 rounded p-2 hover:bg-slate-700 transition-colors"
      >
        <!-- File + Language Badge -->
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs text-gray-300 truncate flex-1 font-mono">
            {{ getFilename(chunk.file_path) }}
          </span>
          <span
            class="text-xs px-2 py-0.5 rounded text-white ml-2 font-mono uppercase border"
            :class="getLanguageColor(chunk.language)"
          >
            {{ chunk.language }}
          </span>
        </div>

        <!-- Chunk Type + Preview -->
        <div class="text-xs text-gray-400 mb-1 font-mono">
          <span class="text-cyan-400 uppercase font-bold">{{ chunk.chunk_type }}</span>
          <span v-if="chunk.content_preview"> - {{ chunk.content_preview }}</span>
        </div>

        <!-- Repo + Time -->
        <div class="flex items-center justify-between text-xs text-gray-500 font-mono uppercase">
          <span>{{ chunk.repository }}</span>
          <span>{{ formatRelativeTime(chunk.indexed_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
