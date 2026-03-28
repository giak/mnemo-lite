<script setup lang="ts">
defineProps<{ data: any }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="scada-label text-cyan-400">BATCH INDEXING</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ data.batchStatus?.status || 'idle' }}</span>
    </div>
    <div class="bg-slate-800/50 border border-slate-700 rounded px-3 py-3 space-y-2">
      <template v-if="data.batchStatus">
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Status</span>
          <span class="scada-data" :class="data.batchStatus.status === 'running' ? 'text-green-400' : 'text-slate-300'">{{ data.batchStatus.status || '–' }}</span>
        </div>
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Progress</span>
          <span class="scada-data text-slate-200">{{ data.batchStatus.processed ?? '–' }} / {{ data.batchStatus.total ?? '–' }}</span>
        </div>
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Errors</span>
          <span class="scada-data" :class="(data.batchStatus.errors || 0) > 0 ? 'text-red-400' : 'text-slate-500'">{{ data.batchStatus.errors ?? 0 }}</span>
        </div>
        <div v-if="data.batchStatus.progress != null" class="w-full bg-slate-700 rounded-full h-1.5 mt-1">
          <div class="bg-cyan-500 h-1.5 rounded-full transition-all" :style="{ width: data.batchStatus.progress + '%' }"></div>
        </div>
      </template>
      <div v-if="!data.batchStatus" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
