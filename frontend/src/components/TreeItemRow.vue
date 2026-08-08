<script setup lang="ts">
/**
 * TreeItemRow.vue — EPIC-78 T3
 * Ligne d'un élément de l'arborescence Explorer (enquête / fait / autre).
 */
import type { ExplorerTreeItem } from '@/types/explorer'

defineProps<{ item: ExplorerTreeItem; active: boolean }>()
defineEmits<{ select: [item: ExplorerTreeItem] }>()

const TYPE_ICON: Record<string, string> = {
  investigation: '🔬',
  note: '📝',
  quintessence: '🧬',
  reference: '📚',
  article: '📰',
  decision: '📋',
  task: '✅',
  conversation: '💬'
}

const icon = (t: string) => TYPE_ICON[t] ?? '📄'

const formatDate = (d: string | null) => {
  if (!d) return ''
  return new Date(d).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}
</script>

<template>
  <button
    @click="$emit('select', item)"
    class="w-full flex items-center gap-3 px-3 py-2 border transition-colors text-left group"
    :class="
      active
        ? 'border-cyan-500 bg-cyan-950/30'
        : 'border-slate-700 bg-slate-900/50 hover:border-cyan-500/50'
    "
  >
    <span class="text-sm">{{ icon(item.memory_type) }}</span>
    <span class="flex-1 min-w-0">
      <span class="block text-sm text-gray-200 font-mono truncate">{{ item.title }}</span>
      <span class="block text-[10px] text-gray-500 font-mono uppercase mt-0.5">
        {{ item.memory_type }} · {{ formatDate(item.created_at) }}
      </span>
    </span>
    <span v-if="item.tags.length > 0" class="hidden md:flex gap-1 flex-shrink-0">
      <span
        v-for="tag in item.tags.slice(0, 3)"
        :key="tag"
        class="px-1.5 py-0.5 text-[10px] bg-slate-700 text-gray-300 rounded"
      >
        {{ tag }}
      </span>
    </span>
    <span class="text-gray-600 group-hover:text-cyan-400 transition-colors">›</span>
  </button>
</template>
