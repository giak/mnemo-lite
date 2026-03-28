<script setup lang="ts">
/**
 * BrainSidebar — Sidebar dynamique (détail du nœud sélectionné)
 */
import { computed } from 'vue'
import { useMarkdown } from '@/composables/useMarkdown'

const props = defineProps<{
  item: any
  type: string
  data: any
}>()

// Markdown rendering for memory content
const contentRef = computed(() => props.item?.content || props.item?.source_code || '')
const { renderedContent } = useMarkdown(contentRef)

function formatDate(iso: string): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('fr-FR', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false
  })
}
</script>

<template>
  <div>
    <!-- No selection -->
    <div v-if="!item" class="text-center text-slate-600 py-12">
      <div class="text-4xl mb-4">👁️</div>
      <div class="text-sm font-mono uppercase">Sélectionnez un élément</div>
      <div class="text-xs font-mono text-slate-700 mt-2">Cliquez sur un nœud dans le contenu central</div>
    </div>

    <!-- Memory detail -->
    <div v-else-if="type === 'memory'">
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led scada-led-green"></span>
        <h3 class="scada-label text-cyan-400 text-xs">Memory</h3>
      </div>
      <div class="space-y-3">
        <div class="text-sm font-mono text-cyan-400 font-bold">{{ item.title }}</div>
        <div class="flex items-center gap-2 text-xs font-mono text-slate-400">
          <span class="px-1.5 py-0.5 bg-slate-700 rounded uppercase">{{ item.memory_type }}</span>
          <span>{{ formatDate(item.created_at) }}</span>
        </div>
        <div class="flex gap-1 flex-wrap">
          <span
            v-for="tag in (item.tags || [])"
            :key="tag"
            class="text-[10px] font-mono px-1.5 py-0.5 bg-slate-700 text-slate-400 rounded"
          >{{ tag }}</span>
        </div>
        <div class="scada-markdown text-xs" v-html="renderedContent"></div>
      </div>
    </div>

    <!-- Code chunk detail -->
    <div v-else-if="type === 'chunk'">
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led scada-led-cyan"></span>
        <h3 class="scada-label text-cyan-400 text-xs">Code Chunk</h3>
      </div>
      <div class="space-y-3">
        <div class="text-sm font-mono text-cyan-400 font-bold">{{ item.name }}</div>
        <div class="text-xs font-mono text-slate-400">
          {{ item.file_path?.split('/').pop() }} ({{ item.language }})
        </div>
        <div class="text-[10px] font-mono text-slate-500">
          Lines {{ item.start_line }}–{{ item.end_line }} | {{ item.chunk_type }}
        </div>
        <pre class="bg-slate-900 border border-slate-700 rounded p-2 text-[10px] font-mono text-slate-300 overflow-x-auto">{{ item.source_code?.substring(0, 500) }}</pre>
      </div>
    </div>

    <!-- Alert detail -->
    <div v-else-if="type === 'alert'">
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led" :class="item.severity === 'critical' ? 'scada-led-red' : 'scada-led-yellow'"></span>
        <h3 class="scada-label text-cyan-400 text-xs">Alert</h3>
      </div>
      <div class="space-y-3">
        <div class="text-sm font-mono uppercase" :class="item.severity === 'critical' ? 'text-red-400' : 'text-amber-400'">
          {{ item.alert_type?.replace(/_/g, ' ') }}
        </div>
        <div class="text-xs font-mono text-slate-400">{{ item.message }}</div>
        <div class="text-[10px] font-mono text-slate-500">
          Value: {{ item.value }} | Threshold: {{ item.threshold }}
        </div>
        <div class="text-[10px] font-mono text-slate-500">{{ formatDate(item.created_at) }}</div>
      </div>
    </div>

    <!-- Node detail -->
    <div v-else-if="type === 'node'">
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led scada-led-green"></span>
        <h3 class="scada-label text-cyan-400 text-xs">Node</h3>
      </div>
      <div class="space-y-3">
        <div class="text-sm font-mono text-cyan-400 font-bold">{{ item.label || item.name }}</div>
        <div class="text-xs font-mono text-slate-400 uppercase">{{ item.node_type || item.type }}</div>
        <div v-if="item.properties" class="text-[10px] font-mono text-slate-500">
          <div v-for="(val, key) in item.properties" :key="key" class="flex justify-between">
            <span class="text-slate-600">{{ key }}:</span>
            <span class="text-slate-400">{{ val }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Event detail -->
    <div v-else-if="type === 'event'">
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led scada-led-cyan"></span>
        <h3 class="scada-label text-cyan-400 text-xs">Event</h3>
      </div>
      <div class="space-y-3">
        <div class="text-[10px] font-mono text-slate-500">{{ formatDate(item.timestamp) }}</div>
        <pre class="bg-slate-900 border border-slate-700 rounded p-2 text-[10px] font-mono text-slate-300 overflow-x-auto">{{ JSON.stringify(item.content || item, null, 2).substring(0, 500) }}</pre>
      </div>
    </div>

    <!-- Generic fallback -->
    <div v-else>
      <div class="flex items-center gap-2 mb-3">
        <span class="scada-led scada-led-cyan"></span>
        <h3 class="scada-label text-cyan-400 text-xs">{{ type }}</h3>
      </div>
      <pre class="bg-slate-900 border border-slate-700 rounded p-2 text-[10px] font-mono text-slate-300 overflow-x-auto">{{ JSON.stringify(item, null, 2).substring(0, 500) }}</pre>
    </div>
  </div>
</template>
