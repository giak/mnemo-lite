<script setup lang="ts">
/**
 * EPIC-26: Memories Monitor Page
 * Main dashboard for monitoring conversations, code chunks, and embeddings
 */
import { useMemories } from '@/composables/useMemories'
import MemoriesStatsBar from '@/components/MemoriesStatsBar.vue'
import ConversationsWidget from '@/components/ConversationsWidget.vue'
import CodeChunksWidget from '@/components/CodeChunksWidget.vue'
import EmbeddingsWidget from '@/components/EmbeddingsWidget.vue'

// Use memories composable with 30-second refresh
const { data, loading, errors, lastUpdated, refresh } = useMemories({
  refreshInterval: 30000
})

// Handle view detail (future: open modal)
function handleViewDetail(memoryId: string) {
  console.log('View memory detail:', memoryId)
  // TODO: Implement modal in future iteration
  alert(`Memory detail modal coming soon!\nID: ${memoryId}`)
}
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold text-cyan-400">🧠 Memories Monitor</h1>

      <button
        @click="refresh"
        :disabled="loading"
        class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
      >
        <span v-if="loading">⏳</span>
        <span v-else>🔄</span>
        Refresh
      </button>
    </div>

    <!-- Error Display -->
    <div v-if="errors.length > 0" class="mb-4 space-y-2">
      <div
        v-for="error in errors"
        :key="error.timestamp"
        class="bg-red-900/50 border border-red-600 text-red-300 px-4 py-2 rounded-lg text-sm"
      >
        ⚠️ {{ error.endpoint }}: {{ error.message }}
      </div>
    </div>

    <!-- Stats Bar -->
    <MemoriesStatsBar :stats="data.stats" :last-updated="lastUpdated" />

    <!-- 3-Column Dashboard -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left: Conversations -->
      <div>
        <ConversationsWidget
          :memories="data.recentMemories"
          @view-detail="handleViewDetail"
        />
      </div>

      <!-- Center: Code Chunks -->
      <div>
        <CodeChunksWidget :data="data.codeChunks" />
      </div>

      <!-- Right: Embeddings -->
      <div>
        <EmbeddingsWidget :health="data.embeddingsHealth" />
      </div>
    </div>
  </div>
</template>
