<script setup lang="ts">
defineProps<{ data: any }>()
const emit = defineEmits<{ select: [item: any] }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="scada-label text-cyan-400">CODE CHUNKS</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ (data.chunks || []).length }}</span>
    </div>
    <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <div
        v-for="chunk in data.chunks || []"
        :key="chunk.id"
        class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 cursor-pointer hover:border-cyan-600"
        @click="emit('select', chunk)"
      >
        <div class="flex items-center gap-2">
          <span class="scada-led scada-led-green" style="width:6px;height:6px"></span>
          <span class="font-mono text-xs text-slate-300 truncate">{{ chunk.file || chunk.path || 'unknown' }}</span>
          <span class="text-xs text-slate-600 ml-auto font-mono">L{{ chunk.lineStart || '?' }}–L{{ chunk.lineEnd || '?' }}</span>
        </div>
        <div class="mt-1 font-mono text-xs text-slate-500 truncate">{{ chunk.symbol || chunk.name || '' }}</div>
      </div>
      <div v-if="(data.chunks || []).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
