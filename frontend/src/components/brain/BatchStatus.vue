<script setup lang="ts">
defineProps<{ data: any }>()

// Mappe les statuts backend vers l'affichage SCADA
const STATUS_COLOR: Record<string, string> = {
  pending: 'text-yellow-400',
  processing: 'text-green-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  not_found: 'text-slate-300'
}

const STATUS_TEXT: Record<string, string> = {
  pending: 'pending',
  processing: 'running',
  completed: 'completed',
  failed: 'failed',
  not_found: 'idle'
}

function statusText(status: string): string {
  return STATUS_TEXT[status] || status || 'idle'
}

function statusColor(status: string): string {
  return STATUS_COLOR[status] || 'text-slate-300'
}
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="scada-label text-cyan-400">BATCH INDEXING</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ statusText(data.batchStatus?.status) }}</span>
    </div>
    <div class="bg-slate-800/50 border border-slate-700 rounded px-3 py-3 space-y-2">
      <template v-if="data.batchStatus">
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Status</span>
          <span class="scada-data" :class="statusColor(data.batchStatus.status)">{{ statusText(data.batchStatus.status) }}</span>
        </div>
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Progress</span>
          <span class="scada-data text-slate-200">{{ data.batchStatus.processed_files ?? '–' }} / {{ data.batchStatus.total_files ?? '–' }}</span>
        </div>
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Batch</span>
          <span class="scada-data text-slate-200">{{ data.batchStatus.current_batch ?? '–' }} / {{ data.batchStatus.total_batches ?? '–' }}</span>
        </div>
        <div class="flex items-center justify-between font-mono text-xs">
          <span class="text-slate-400">Errors</span>
          <span class="scada-data" :class="(data.batchStatus.failed_files || 0) > 0 ? 'text-red-400' : 'text-slate-500'">{{ data.batchStatus.failed_files ?? 0 }}</span>
        </div>
        <div v-if="data.batchStatus.progress_percent != null" class="w-full bg-slate-700 rounded-full h-1.5 mt-1">
          <div class="bg-cyan-500 h-1.5 rounded-full transition-all" :style="{ width: Math.min(100, Math.max(0, data.batchStatus.progress_percent)) + '%' }"></div>
        </div>
      </template>
      <div v-if="!data.batchStatus" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
