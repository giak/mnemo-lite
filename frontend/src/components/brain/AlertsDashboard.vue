<script setup lang="ts">
defineProps<{ data: any }>()
const emit = defineEmits<{ select: [item: any] }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-red"></span>
      <h2 class="scada-label text-red-400">ALERTS</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ (data.alerts || []).length }}</span>
    </div>
    <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <div
        v-for="alert in data.alerts || []"
        :key="alert.id"
        class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 cursor-pointer hover:border-red-600"
        @click="emit('select', alert)"
      >
        <div class="flex items-center gap-2">
          <span class="scada-led" :class="alert.severity === 'critical' ? 'scada-led-red' : 'scada-led-amber'" style="width:6px;height:6px"></span>
          <span class="font-mono text-xs text-slate-300 truncate">{{ alert.title || alert.name || 'alert' }}</span>
          <span class="text-xs text-slate-600 ml-auto font-mono uppercase">{{ alert.severity || '' }}</span>
        </div>
        <div class="mt-1 font-mono text-xs text-slate-500 truncate">{{ alert.message || alert.description || '' }}</div>
      </div>
      <div v-if="(data.alerts || []).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
