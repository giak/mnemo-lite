<script setup lang="ts">
/**
 * EPIC-27: Dashboard Card Component - SCADA Industrial Style
 * Reusable card component with LED indicators and monospace data
 */

interface Props {
  title: string
  value?: string | number
  subtitle?: string
  status?: 'success' | 'warning' | 'error' | 'info'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  status: 'info',
  loading: false,
})

// LED indicator classes
const ledClasses = {
  success: 'scada-led scada-led-green',
  warning: 'scada-led scada-led-yellow',
  error: 'scada-led scada-led-red',
  info: 'scada-led scada-led-cyan',
}

// SCADA status text classes
const statusClasses = {
  success: 'scada-status-healthy',
  warning: 'scada-status-warning',
  error: 'scada-status-danger',
  info: 'scada-status-info',
}
</script>

<template>
  <div class="scada-panel">
    <!-- Header avec LED et titre -->
    <div class="flex items-center gap-3 mb-4">
      <!-- LED Status Indicator -->
      <span :class="ledClasses[props.status]"></span>
      <h3 class="scada-label" :class="statusClasses[props.status]">
        {{ props.title }}
      </h3>
    </div>

    <div v-if="props.loading" class="mt-4">
      <div class="animate-pulse">
        <div class="h-8 bg-slate-700 w-24 rounded"></div>
        <div class="h-4 bg-slate-800 w-32 mt-2 rounded"></div>
      </div>
    </div>

    <div v-else class="mt-4">
      <!-- Valeur principale avec style SCADA monospace -->
      <p class="text-4xl scada-data">
        {{ props.value ?? '-' }}
      </p>

      <!-- Subtitle avec font monospace -->
      <p
        v-if="props.subtitle"
        class="mt-2 text-sm text-gray-400 font-mono"
      >
        {{ props.subtitle }}
      </p>
    </div>
  </div>
</template>
