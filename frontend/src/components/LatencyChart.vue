<script setup lang="ts">
/**
 * Latency Chart — Chart.js line chart showing API latency over time
 */
import { ref, watch, onUnmounted } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

Chart.register(
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface LatencyPoint {
  hour: string
  avg: number
  p95: number
  max: number
  count: number
}

const props = defineProps<{
  data: LatencyPoint[]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart | null = null

function createChart() {
  if (!canvasRef.value) return
  if (chartInstance) chartInstance.destroy()

  const labels = props.data.map(d => {
    const date = new Date(d.hour)
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })
  })

  chartInstance = new Chart(canvasRef.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Avg (ms)',
          data: props.data.map(d => d.avg),
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34, 211, 238, 0.1)',
          fill: true,
          tension: 0.3,
          pointRadius: 2,
          borderWidth: 2
        },
        {
          label: 'P95 (ms)',
          data: props.data.map(d => d.p95),
          borderColor: '#f59e0b',
          backgroundColor: 'transparent',
          fill: false,
          tension: 0.3,
          pointRadius: 1,
          borderWidth: 1.5,
          borderDash: [5, 5]
        },
        {
          label: 'Max (ms)',
          data: props.data.map(d => d.max),
          borderColor: '#ef4444',
          backgroundColor: 'transparent',
          fill: false,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: {
        legend: {
          labels: {
            color: '#94a3b8',
            font: { family: "'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace", size: 11 },
            usePointStyle: true,
            pointStyle: 'line'
          }
        },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#22d3ee',
          bodyColor: '#e2e8f0',
          borderColor: '#334155',
          borderWidth: 1,
          titleFont: { family: 'monospace' },
          bodyFont: { family: 'monospace' },
          callbacks: {
            label: (ctx) => `  ${ctx.dataset.label}: ${Math.round(ctx.parsed.y)}ms`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { family: 'monospace', size: 10 }, maxRotation: 45 },
          grid: { color: 'rgba(51, 65, 85, 0.5)' }
        },
        y: {
          ticks: {
            color: '#64748b',
            font: { family: 'monospace', size: 10 },
            callback: (val) => `${val}ms`
          },
          grid: { color: 'rgba(51, 65, 85, 0.5)' }
        }
      }
    }
  })
}

watch(() => props.data, () => {
  if (props.data.length > 0) createChart()
}, { immediate: true })

onUnmounted(() => {
  if (chartInstance) chartInstance.destroy()
})
</script>

<template>
  <div class="relative h-64">
    <canvas ref="canvasRef"></canvas>
    <div v-if="data.length === 0" class="absolute inset-0 flex items-center justify-center text-slate-600 font-mono text-sm">
      NO DATA
    </div>
  </div>
</template>
