<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { ConsolidationGroup } from '../../types/memory-graph'
import { api } from '@/api/client'

const suggestions = ref<ConsolidationGroup[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const consolidating = ref<string | null>(null)
const showConsolidateModal = ref(false)
const selectedGroup = ref<ConsolidationGroup | null>(null)
const summaryText = ref('')

async function fetchSuggestions() {
  loading.value = true
  error.value = null
  try {
    const res = await api('/memories/consolidation/suggestions?min_shared_entities=0&min_shared_concepts=0&similarity_threshold=0.01&min_group_size=2')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    suggestions.value = data.groups
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function openConsolidateModal(group: ConsolidationGroup) {
  selectedGroup.value = group
  summaryText.value = `Consolidated from ${group.titles.length} memories about ${group.shared_entities.join(', ')}. ${group.suggested_summary_hint}`
  showConsolidateModal.value = true
}

async function consolidate() {
  if (!selectedGroup.value) return
  consolidating.value = selectedGroup.value.source_ids[0] ?? null
  try {
    const res = await api('/memories/consolidate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: selectedGroup.value.suggested_title,
        summary: summaryText.value,
        source_ids: selectedGroup.value.source_ids,
        tags: selectedGroup.value.suggested_tags,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    await res.json()
    showConsolidateModal.value = false
    selectedGroup.value = null
    await fetchSuggestions()
  } catch (e: any) {
    error.value = e.message
  } finally {
    consolidating.value = null
  }
}

function similarityColor(score: number) {
  if (score >= 0.6) return 'badge-green'
  if (score >= 0.4) return 'badge-yellow'
  return 'badge-red'
}

onMounted(fetchSuggestions)
</script>

<template>
  <div class="scada-panel p-4">
    <div class="flex items-center justify-between mb-4">
      <h2 class="scada-label text-lg">
        Consolidation Suggestions
      </h2>
      <button
        class="scada-btn scada-btn-ghost text-xs"
        :disabled="loading"
        @click="fetchSuggestions"
      >
        {{ loading ? '...' : '↻ Refresh' }}
      </button>
    </div>

    <div
      v-if="error"
      class="alert-error p-2 mb-4 text-sm"
    >
      {{ error }}
    </div>
    <div
      v-else-if="suggestions.length === 0"
      class="alert-info p-2 mb-4 text-sm"
    >
      No consolidation suggestions. Memories may not have enough shared entities yet.
    </div>

    <div class="space-y-4">
      <div
        v-for="(group, i) in suggestions"
        :key="i"
        class="scada-panel p-3"
      >
        <div class="flex items-center justify-between mb-2">
          <h3 class="scada-data text-sm">
            {{ group.suggested_title }}
          </h3>
          <span :class="['badge', similarityColor(group.avg_similarity)]">{{ (group.avg_similarity * 100).toFixed(0) }}%</span>
        </div>

        <div class="flex flex-wrap gap-1 mb-2">
          <span
            v-for="e in group.shared_entities"
            :key="e"
            class="badge-cyan px-1 py-0.5 text-[10px]"
          >{{ e }}</span>
          <span
            v-for="c in group.shared_concepts"
            :key="c"
            class="badge-purple px-1 py-0.5 text-[10px]"
          >{{ c }}</span>
        </div>

        <div class="space-y-1 mb-3">
          <div
            v-for="(title, j) in group.titles"
            :key="j"
            class="text-xs"
          >
            <span class="scada-label">{{ j + 1 }}.</span>
            <span class="scada-data">{{ title }}</span>
            <span class="text-gray-500 ml-1 truncate max-w-[200px] inline-block">{{ group.content_previews[j] }}</span>
          </div>
        </div>

        <div class="text-[10px] text-gray-400 mb-2">
          {{ group.suggested_summary_hint }}
        </div>

        <button
          class="scada-btn scada-btn-primary text-xs"
          :disabled="consolidating === group.source_ids[0]"
          @click="openConsolidateModal(group)"
        >
          {{ consolidating === group.source_ids[0] ? 'Consolidating...' : 'Consolidate' }}
        </button>
      </div>
    </div>

    <!-- Consolidate Modal -->
    <div
      v-if="showConsolidateModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    >
      <div class="scada-panel p-6 max-w-lg w-full mx-4">
        <h3 class="scada-label text-lg mb-4">
          Confirm Consolidation
        </h3>
        <div class="space-y-3">
          <div>
            <label class="scada-label text-xs">Title</label>
            <div class="scada-data text-sm">
              {{ selectedGroup?.suggested_title }}
            </div>
          </div>
          <div>
            <label class="scada-label text-xs">Summary</label>
            <textarea
              v-model="summaryText"
              class="input w-full h-32 text-xs font-mono"
            />
          </div>
          <div class="flex gap-2 justify-end">
            <button
              class="scada-btn scada-btn-ghost text-xs"
              @click="showConsolidateModal = false"
            >
              Cancel
            </button>
            <button
              class="scada-btn scada-btn-primary text-xs"
              :disabled="Boolean(consolidating)"
              @click="consolidate"
            >
              {{ consolidating ? 'Consolidating...' : 'Consolidate' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
