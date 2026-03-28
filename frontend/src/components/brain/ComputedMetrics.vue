<script setup lang="ts">
defineProps<{ data: any }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="scada-label text-cyan-400">COMPUTED METRICS</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ Object.keys(data.computedMetrics || {}).length }}</span>
    </div>
    <div class="bg-slate-800/50 border border-slate-700 rounded px-3 py-3 space-y-2">
      <template v-if="data.computedMetrics">
        <div
          v-for="(value, key) in data.computedMetrics"
          :key="key"
          class="flex items-center justify-between font-mono text-xs"
        >
          <span class="text-slate-400">{{ key }}</span>
          <span class="scada-data text-slate-200">{{ typeof value === 'number' ? value.toLocaleString() : value }}</span>
        </div>
      </template>
      <div v-if="!data.computedMetrics || Object.keys(data.computedMetrics).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
