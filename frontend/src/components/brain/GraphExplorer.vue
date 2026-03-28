<script setup lang="ts">
defineProps<{ data: any }>()
const emit = defineEmits<{ select: [item: any] }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-purple"></span>
      <h2 class="scada-label text-purple-400">GRAPH</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ (data.graphNodes || []).length }} nodes · {{ (data.graphEdges || []).length }} edges</span>
    </div>
    <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <div
        v-for="node in data.graphNodes || []"
        :key="node.id"
        class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 cursor-pointer hover:border-purple-600"
        @click="emit('select', node)"
      >
        <div class="flex items-center gap-2">
          <span class="scada-led scada-led-purple" style="width:6px;height:6px"></span>
          <span class="font-mono text-xs text-slate-300 truncate">{{ node.label || node.name || node.id }}</span>
          <span class="text-xs text-slate-600 ml-auto font-mono">{{ node.type || '' }}</span>
        </div>
        <div class="mt-1 font-mono text-xs text-slate-500">
          {{ (data.graphEdges || []).filter((e: any) => e.source === node.id || e.from === node.id).length }} edges
        </div>
      </div>
      <div v-if="(data.graphNodes || []).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
