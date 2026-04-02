<script setup lang="ts">
/**
 * EPIC-30 Story 30.1: Alert Rule Editor — SCADA Style
 * CRUD interface for managing alert rules.
 */
import { ref, onMounted } from 'vue'
import { API } from '@/config/api'

interface AlertRule {
  id: string
  name: string
  alert_type: string
  threshold: number
  severity: string
  cooldown_seconds: number
  enabled: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

const rules = ref<AlertRule[]>([])
const loading = ref(false)
const editingRule = ref<AlertRule | null>(null)
const showForm = ref(false)

const severityLed: Record<string, string> = {
  critical: 'scada-led-red',
  warning: 'scada-led-yellow',
  info: 'scada-led-green'
}

const severityBadge: Record<string, string> = {
  critical: 'bg-red-900/50 border-red-600 text-red-300',
  warning: 'bg-yellow-900/50 border-yellow-600 text-yellow-300',
  info: 'bg-green-900/50 border-green-600 text-green-300'
}

const ALERT_TYPES = [
  'cache_hit_rate_low', 'memory_high', 'slow_queries',
  'error_rate_high', 'evictions_high', 'cpu_high',
  'disk_high', 'connections_high'
]

const SEVERITIES = ['info', 'warning', 'critical']

const emptyRule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at'> = {
  name: '',
  alert_type: 'cache_hit_rate_low',
  threshold: 0.8,
  severity: 'warning',
  cooldown_seconds: 300,
  enabled: true,
  metadata: {}
}

const newRule = ref({ ...emptyRule })

async function fetchRules() {
  loading.value = true
  try {
    const resp = await fetch(`${API}/monitoring/advanced/alert-rules`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    rules.value = data.data || []
  } catch (err) {
    console.error('Failed to fetch alert rules:', err)
  } finally {
    loading.value = false
  }
}

async function toggleRule(rule: AlertRule) {
  try {
    const resp = await fetch(`${API}/monitoring/advanced/alert-rules/${rule.id}/toggle`, { method: 'POST' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await fetchRules()
  } catch (err) {
    console.error('Failed to toggle rule:', err)
  }
}

async function deleteRule(rule: AlertRule) {
  if (!confirm(`Delete rule "${rule.name}"?`)) return
  try {
    const resp = await fetch(`${API}/monitoring/advanced/alert-rules/${rule.id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    await fetchRules()
  } catch (err) {
    console.error('Failed to delete rule:', err)
  }
}

function startEdit(rule: AlertRule) {
  editingRule.value = { ...rule }
  showForm.value = true
}

function startCreate() {
  newRule.value = { ...emptyRule }
  editingRule.value = null
  showForm.value = true
}

function cancelForm() {
  showForm.value = false
  editingRule.value = null
}

async function saveRule() {
  const rule = editingRule.value || newRule.value
  try {
    const url = editingRule.value
      ? `${API}/monitoring/advanced/alert-rules/${editingRule.value.id}`
      : `${API}/monitoring/advanced/alert-rules`
    const method = editingRule.value ? 'PUT' : 'POST'
    const resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule)
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    showForm.value = false
    editingRule.value = null
    await fetchRules()
  } catch (err) {
    console.error('Failed to save rule:', err)
  }
}

function formatType(type: string): string {
  return type.replace(/_/g, ' ').toUpperCase()
}

function formatCooldown(seconds: number): string {
  if (seconds >= 3600) return `${seconds / 3600}h`
  if (seconds >= 60) return `${seconds / 60}m`
  return `${seconds}s`
}

onMounted(() => {
  fetchRules()
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="scada-label text-cyan-400 text-lg">Alert Rules ({{ rules.length }})</h2>
      <button @click="startCreate" class="scada-btn scada-btn-primary text-xs">
        + NEW RULE
      </button>
    </div>

    <!-- Form Modal -->
    <div v-if="showForm" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" @click="cancelForm">
      <div class="bg-[#0d1424] border-2 border-cyan-700 rounded-lg w-full max-w-lg p-6" @click.stop>
        <h3 class="text-lg font-mono font-bold text-cyan-400 mb-4">
          {{ editingRule ? 'EDIT RULE' : 'NEW RULE' }}
        </h3>
        <div class="space-y-3">
          <div>
            <label class="scada-label text-xs">Name</label>
            <input v-model="editingRule ? editingRule.name : newRule.name"
              class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-sm font-mono px-3 py-2 rounded focus:border-cyan-500 focus:outline-none"
              placeholder="Rule name" />
          </div>
          <div>
            <label class="scada-label text-xs">Alert Type</label>
            <select v-model="editingRule ? editingRule.alert_type : newRule.alert_type"
              class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-sm font-mono px-3 py-2 rounded focus:border-cyan-500 focus:outline-none">
              <option v-for="t in ALERT_TYPES" :key="t" :value="t">{{ formatType(t) }}</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="scada-label text-xs">Threshold</label>
              <input v-model.number="editingRule ? editingRule.threshold : newRule.threshold"
                type="number" step="0.01"
                class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-sm font-mono px-3 py-2 rounded focus:border-cyan-500 focus:outline-none" />
            </div>
            <div>
              <label class="scada-label text-xs">Severity</label>
              <select v-model="editingRule ? editingRule.severity : newRule.severity"
                class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-sm font-mono px-3 py-2 rounded focus:border-cyan-500 focus:outline-none">
                <option v-for="s in SEVERITIES" :key="s" :value="s">{{ s.toUpperCase() }}</option>
              </select>
            </div>
          </div>
          <div>
            <label class="scada-label text-xs">Cooldown (seconds)</label>
            <input v-model.number="editingRule ? editingRule.cooldown_seconds : newRule.cooldown_seconds"
              type="number" step="60"
              class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-sm font-mono px-3 py-2 rounded focus:border-cyan-500 focus:outline-none" />
          </div>
        </div>
        <div class="flex gap-2 justify-end mt-6">
          <button @click="cancelForm" class="scada-btn scada-btn-ghost text-xs">CANCEL</button>
          <button @click="saveRule" class="scada-btn scada-btn-primary text-xs">SAVE</button>
        </div>
      </div>
    </div>

    <!-- Rules Table -->
    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead class="bg-slate-800 border-b-2 border-slate-600">
          <tr>
            <th class="px-3 py-2 text-left text-[10px] font-mono font-bold text-cyan-400 uppercase">Name</th>
            <th class="px-3 py-2 text-left text-[10px] font-mono font-bold text-cyan-400 uppercase">Type</th>
            <th class="px-3 py-2 text-left text-[10px] font-mono font-bold text-cyan-400 uppercase">Threshold</th>
            <th class="px-3 py-2 text-left text-[10px] font-mono font-bold text-cyan-400 uppercase">Severity</th>
            <th class="px-3 py-2 text-left text-[10px] font-mono font-bold text-cyan-400 uppercase">Cooldown</th>
            <th class="px-3 py-2 text-center text-[10px] font-mono font-bold text-cyan-400 uppercase">Enabled</th>
            <th class="px-3 py-2 text-center text-[10px] font-mono font-bold text-cyan-400 uppercase">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700">
          <tr v-for="rule in rules" :key="rule.id"
            class="hover:bg-slate-800/50 transition-colors"
            :class="{ 'opacity-50': !rule.enabled }">
            <td class="px-3 py-2 text-xs font-mono text-slate-300">{{ rule.name }}</td>
            <td class="px-3 py-2 text-[10px] font-mono text-slate-400">{{ formatType(rule.alert_type) }}</td>
            <td class="px-3 py-2 text-xs font-mono text-cyan-400">{{ rule.threshold }}</td>
            <td class="px-3 py-2">
              <span class="text-[10px] font-mono px-2 py-0.5 rounded border"
                :class="severityBadge[rule.severity] || severityBadge.warning">
                {{ rule.severity.toUpperCase() }}
              </span>
            </td>
            <td class="px-3 py-2 text-xs font-mono text-slate-400">{{ formatCooldown(rule.cooldown_seconds) }}</td>
            <td class="px-3 py-2 text-center">
              <button @click="toggleRule(rule)"
                class="scada-led transition-opacity"
                :class="rule.enabled ? 'scada-led-green' : 'scada-led-gray'"
                :title="rule.enabled ? 'Click to disable' : 'Click to enable'">
              </button>
            </td>
            <td class="px-3 py-2 text-center">
              <div class="flex items-center justify-center gap-1">
                <button @click="startEdit(rule)" class="scada-btn scada-btn-ghost text-[10px] px-2 py-0.5">EDIT</button>
                <button @click="deleteRule(rule)" class="scada-btn scada-btn-danger text-[10px] px-2 py-0.5">DEL</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loading && rules.length === 0" class="text-center py-8 text-slate-500 font-mono text-sm">
        NO ALERT RULES
      </div>
    </div>
  </div>
</template>
