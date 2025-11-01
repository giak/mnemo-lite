<script setup lang="ts">
/**
 * EPIC-25 Story 25.3: Dashboard Card Component
 * Reusable card component for displaying dashboard statistics - Dark Theme Design System
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

const cardClasses = {
  success: 'card-success',
  warning: 'card-warning',
  error: 'card-error',
  info: 'card-info',
}

const statusTextClasses = {
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  error: 'text-red-400',
  info: 'text-cyan-400',
}

const statusValueClasses = {
  success: 'text-emerald-300',
  warning: 'text-amber-300',
  error: 'text-red-300',
  info: 'text-cyan-200',
}
</script>

<template>
  <div :class="cardClasses[props.status]">
    <h3
      class="text-subheading"
      :class="statusTextClasses[props.status]"
    >
      {{ props.title }}
    </h3>

    <div v-if="props.loading" class="mt-4">
      <div class="animate-pulse">
        <div class="h-8 bg-slate-700 w-24"></div>
        <div class="h-4 bg-slate-800 w-32 mt-2"></div>
      </div>
    </div>

    <div v-else class="mt-4">
      <p
        class="text-4xl font-bold"
        :class="statusValueClasses[props.status]"
      >
        {{ props.value ?? '-' }}
      </p>
      <p
        v-if="props.subtitle"
        class="mt-2 text-sm text-gray-400"
      >
        {{ props.subtitle }}
      </p>
    </div>
  </div>
</template>
