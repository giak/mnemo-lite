<script setup lang="ts">
defineProps<{ data: any }>()
const emit = defineEmits<{ select: [item: any] }>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-3">
      <span class="scada-led scada-led-amber"></span>
      <h2 class="scada-label text-amber-400">EVENTS TIMELINE</h2>
      <span class="text-xs font-mono text-slate-500 ml-auto">{{ (data.events || []).length }}</span>
    </div>
    <div class="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <div
        v-for="event in data.events || []"
        :key="event.id"
        class="bg-slate-800/50 border border-slate-700 rounded px-3 py-2 cursor-pointer hover:border-amber-600"
        @click="emit('select', event)"
      >
        <div class="flex items-center gap-2">
          <span class="scada-led scada-led-amber" style="width:6px;height:6px"></span>
          <span class="font-mono text-xs text-slate-300 truncate">{{ event.type || event.kind || 'event' }}</span>
          <span class="text-xs text-slate-600 ml-auto font-mono">{{ event.timestamp || event.time || '' }}</span>
        </div>
        <div class="mt-1 font-mono text-xs text-slate-500 truncate">{{ event.summary || event.description || '' }}</div>
      </div>
      <div v-if="(data.events || []).length === 0" class="text-center text-slate-600 py-8 text-sm font-mono">NO DATA</div>
    </div>
  </div>
</template>
