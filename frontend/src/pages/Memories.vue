<script setup lang="ts">
/**
 * EPIC-27: Memories Monitor Page - SCADA Industrial Style
 * Main dashboard for monitoring conversations, code chunks, and embeddings with LED indicators
 */
import { ref } from 'vue'
import { useMemories } from '@/composables/useMemories'
import MemoriesStatsBar from '@/components/MemoriesStatsBar.vue'
import ConversationsWidget from '@/components/ConversationsWidget.vue'
import CodeChunksWidget from '@/components/CodeChunksWidget.vue'
import EmbeddingsWidget from '@/components/EmbeddingsWidget.vue'
import ConversationDetailModal from '@/components/ConversationDetailModal.vue'

// Use memories composable with 30-second refresh
const { data, loading, errors, lastUpdated, refresh } = useMemories({
  refreshInterval: 30000
})

// Modal state
const selectedMemoryId = ref<string | null>(null)
const isModalOpen = ref(false)

// Handle view detail - open modal
function handleViewDetail(memoryId: string) {
  selectedMemoryId.value = memoryId
  isModalOpen.value = true
}

// Handle modal close
function handleCloseModal() {
  isModalOpen.value = false
  // Clear selected memory after animation completes
  setTimeout(() => {
    selectedMemoryId.value = null
  }, 300)
}
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header avec LED SCADA -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <span class="scada-led scada-led-cyan"></span>
        <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Memories Monitor</h1>
      </div>

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

    <!-- Error Display avec LED -->
    <div v-if="errors.length > 0" class="mb-4 space-y-2">
      <div
        v-for="error in errors"
        :key="error.timestamp"
        class="bg-red-900/50 border-2 border-red-600 text-red-300 px-4 py-3 rounded flex items-start gap-3"
      >
        <span class="scada-led scada-led-red"></span>
        <span class="text-sm font-mono">
          <span class="scada-status-danger">{{ error.endpoint }}</span>: {{ error.message }}
        </span>
      </div>
    </div>

    <!-- Stats Bar -->
    <MemoriesStatsBar :stats="data.stats" :last-updated="lastUpdated" />

    <!-- 3-Column Dashboard -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 max-h-[calc(100vh-280px)]">
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

    <!-- Conversation Detail Modal -->
    <ConversationDetailModal
      :memory-id="selectedMemoryId"
      :is-open="isModalOpen"
      @close="handleCloseModal"
    />
  </div>
</template>
