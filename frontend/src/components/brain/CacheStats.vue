<script setup lang="ts">
defineProps<{ data: any }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-blue"></span>
      <h2 class="scada-label text-blue-400">CACHE STATS</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ Object.keys(data.cacheStats || {}).length }} keys</span>
    </div>
    <div class="bg-slate-800/50 border border-slate-700 rounded px-3 py-3 space-y-2">
      <template v-if="data.cacheStats">
        <div
          v-for="(value, key) in data.cacheStats"
          :key="key"
          class="flex items-center justify-between font-mono text-xs"
        >
          <span class="text-slate-400">{{ key }}</span>
          <span class="scada-data text-slate-200">{{ typeof value === 'number' ? value.toLocaleString() : value }}</span>
        </div>
      </template>
      <div v-if="!data.cacheStats || Object.keys(data.cacheStats).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
