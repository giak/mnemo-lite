<script setup lang="ts">
defineProps<{ data: any }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-green"></span>
      <h2 class="scada-label text-green-400">LATENCY METRICS</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ (data.latency || []).length }}</span>
    </div>
    <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <div
        v-for="(metric, idx) in data.latency || []"
        :key="idx"
        class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="font-mono text-xs text-slate-300">{{ metric.label || metric.name || ('Metric ' + (idx + 1)) }}</span>
          <span class="text-xs font-mono ml-auto" :class="metric.p99 > 200 ? 'text-red-400' : 'text-green-400'">{{ metric.p99 ?? metric.value ?? '–' }}ms</span>
        </div>
        <div class="flex items-end gap-px h-4">
          <div
            v-for="(v, i) in (metric.sparkline || metric.history || [])"
            :key="i"
            class="flex-1 rounded-t"
            :style="{
              height: Math.max(2, (v / (metric.max || Math.max(...(metric.sparkline || metric.history || [1])))) * 16) + 'px',
              backgroundColor: v > (metric.threshold || 200) ? '#f87171' : '#34d399'
            }"
          ></div>
        </div>
      </div>
      <div v-if="(data.latency || []).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
