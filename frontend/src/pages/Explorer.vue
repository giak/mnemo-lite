<script setup lang="ts">
/**
 * Explorer.vue — EPIC-78 Knowledge Explorer
 *
 * Onglets : Socle (T2) / Explorer (T3) / Relations (T4).
 * T2 : vue « Socle » — distribution par type, top sujets cliquables,
 * couverture factuelle (status:CONFIRME) et timeline des investigations,
 * branchée sur GET /api/v1/memories/explorer/stats.
 */
import { ref, computed, onMounted } from 'vue'
import { getExplorerStats } from '@/api/explorer'
import type { ExplorerStats } from '@/types/explorer'

// --- États
type Tab = 'socle' | 'explorer' | 'relations'
const activeTab = ref<Tab>('socle')
const selectedSubject = ref<string | null>(null)

const data = ref<ExplorerStats | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const lastUpdated = ref<Date | null>(null)

async function refresh(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    data.value = await getExplorerStats()
    lastUpdated.value = new Date()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load explorer stats'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

/** Clic sur un sujet -> onglet Explorer (l'arborescence arrive en T3) */
function selectSubject(tag: string): void {
  selectedSubject.value = tag
  activeTab.value = 'explorer'
}

// --- Helpers de rendu
const TYPE_META: Record<string, { icon: string; bar: string }> = {
  investigation: { icon: '🔬', bar: 'bg-cyan-500' },
  note: { icon: '📝', bar: 'bg-slate-500' },
  quintessence: { icon: '🧬', bar: 'bg-amber-500' },
  reference: { icon: '📚', bar: 'bg-purple-500' },
  article: { icon: '📰', bar: 'bg-blue-500' },
  decision: { icon: '📋', bar: 'bg-emerald-500' },
  task: { icon: '✅', bar: 'bg-pink-500' },
  conversation: { icon: '💬', bar: 'bg-slate-600' }
}

const typeMeta = (type: string) =>
  TYPE_META[type] ?? { icon: '📄', bar: 'bg-slate-400' }

const typeRows = computed(() => {
  if (!data.value) return []
  const entries = Object.entries(data.value.by_type)
  const max = Math.max(...entries.map(([, n]) => n), 1)
  return entries
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => ({
      type,
      count,
      pct: Math.round((count / max) * 100)
    }))
})

const confirmedPct = computed(() => {
  if (!data.value || data.value.status.total === 0) return 0
  return Math.round((data.value.status.confirmed / data.value.status.total) * 100)
})

const factCheckedPct = computed(() => {
  if (!data.value || data.value.status.total === 0) return 0
  return Math.round((data.value.status.fact_checked / data.value.status.total) * 100)
})

const maxSubjectCount = computed(() => {
  if (!data.value || data.value.top_subjects.length === 0) return 1
  return Math.max(...data.value.top_subjects.map((s) => s.count))
})

const timelineBars = computed(() => {
  if (!data.value) return []
  const items = [...data.value.timeline].sort((a, b) => a.month.localeCompare(b.month))
  const max = Math.max(...items.map((i) => i.count), 1)
  return items.map((i) => ({
    month: i.month,
    short: i.month.slice(2), // YYYY-MM -> YY-MM
    count: i.count,
    pct: Math.round((i.count / max) * 100)
  }))
})

const formatMonth = (ym: string) => {
  const [y, m = '01'] = ym.split('-')
  const months = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
  const mi = parseInt(m, 10) - 1
  return mi >= 0 && mi < 12 ? `${months[mi]} ${y}` : ym
}

const typeLabel = (type: string) => type.charAt(0).toUpperCase() + type.slice(1)
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-4">
          <span class="scada-led scada-led-cyan"></span>
          <div>
            <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Explorer</h1>
            <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
              Socle de connaissances — faits, enquêtes, articles, relations
            </p>
          </div>
        </div>
        <div class="text-right">
          <button @click="refresh" :disabled="loading" class="scada-btn scada-btn-primary">
            {{ loading ? 'REFRESHING...' : 'REFRESH' }}
          </button>
          <p class="mt-2 text-xs text-gray-500 font-mono uppercase">
            Last Updated:
            {{ lastUpdated ? lastUpdated.toLocaleTimeString() : 'NEVER' }}
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="mb-6 border-b border-slate-700">
        <nav class="flex gap-4">
          <button
            v-for="t in (['socle', 'explorer', 'relations'] as Tab[])"
            :key="t"
            @click="activeTab = t"
            :class="[
              'px-4 py-2 font-mono text-sm uppercase tracking-wide border-b-2 transition-colors',
              activeTab === t
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            ]"
          >
            {{ t }}
          </button>
        </nav>
      </div>

      <!-- Error -->
      <div v-if="error" class="alert-error">
        <span class="text-sm font-mono">{{ error }}</span>
      </div>

      <!-- Loading -->
      <div v-if="loading && !data" class="animate-pulse space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div v-for="i in 4" :key="i" class="h-28 bg-slate-800/60 border-2 border-slate-700"></div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="h-64 bg-slate-800/60 border-2 border-slate-700"></div>
          <div class="h-64 bg-slate-800/60 border-2 border-slate-700"></div>
        </div>
      </div>

      <template v-else-if="data">
        <!-- ============ SOCLE TAB ============ -->
        <div v-if="activeTab === 'socle'" class="space-y-6">
          <!-- Stat cards -->
          <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div class="scada-panel">
              <div class="flex items-center gap-2 mb-3">
                <span class="scada-led scada-led-cyan"></span>
                <span class="scada-label">Total socle</span>
              </div>
              <p class="scada-data text-3xl">{{ data.status.total.toLocaleString() }}</p>
              <p class="text-xs text-gray-500 mt-1">conversations exclues</p>
            </div>
            <div class="scada-panel">
              <div class="flex items-center gap-2 mb-3">
                <span class="scada-led scada-led-cyan"></span>
                <span class="scada-label">Enquêtes</span>
              </div>
              <p class="scada-data text-3xl">{{ (data.by_type.investigation ?? 0).toLocaleString() }}</p>
              <p class="text-xs text-gray-500 mt-1">investigations</p>
            </div>
            <div class="scada-panel">
              <div class="flex items-center gap-2 mb-3">
                <span class="scada-led scada-led-yellow"></span>
                <span class="scada-label">Fiches internes</span>
              </div>
              <p class="scada-data text-3xl text-amber-400">{{ (data.by_type.quintessence ?? 0).toLocaleString() }}</p>
              <p class="text-xs text-gray-500 mt-1">quintessences</p>
            </div>
            <div class="scada-panel">
              <div class="flex items-center gap-2 mb-3">
                <span class="scada-led scada-led-green"></span>
                <span class="scada-label">Articles publiés</span>
              </div>
              <p class="scada-data text-3xl text-emerald-400">{{ (data.by_type.article ?? 0).toLocaleString() }}</p>
              <p class="text-xs text-gray-500 mt-1">articles</p>
            </div>
          </div>

          <!-- Distribution + Couverture -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="scada-panel">
              <h2 class="scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
                Distribution par type
              </h2>
              <div class="space-y-3">
                <div v-for="row in typeRows" :key="row.type" class="flex items-center gap-3">
                  <span class="w-6 text-center text-sm">{{ typeMeta(row.type).icon }}</span>
                  <span class="w-28 text-xs text-gray-300 font-mono uppercase truncate">{{ typeLabel(row.type) }}</span>
                  <div class="flex-1 h-3 bg-slate-800 border border-slate-700 overflow-hidden">
                    <div
                      class="h-full transition-all duration-500"
                      :class="typeMeta(row.type).bar"
                      :style="{ width: `${row.pct}%` }"
                    ></div>
                  </div>
                  <span class="w-16 text-right scada-data text-sm">{{ row.count.toLocaleString() }}</span>
                </div>
              </div>
            </div>

            <div class="scada-panel">
              <h2 class="scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
                Couverture factuelle
              </h2>
              <div class="space-y-5">
                <div>
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs text-gray-300 font-mono uppercase">
                      <span class="scada-led scada-led-green mr-2"></span>Faits vérifiés
                      <span class="text-gray-500">(status:CONFIRME)</span>
                    </span>
                    <span class="scada-data text-sm">
                      {{ data.status.confirmed.toLocaleString() }} <span class="text-gray-500">/ {{ data.status.total.toLocaleString() }}</span>
                    </span>
                  </div>
                  <div class="h-4 bg-slate-800 border border-slate-700 overflow-hidden">
                    <div
                      class="h-full bg-emerald-500 transition-all duration-500"
                      :style="{ width: `${confirmedPct}%` }"
                    ></div>
                  </div>
                  <p class="text-xs text-gray-500 mt-1 text-right">{{ confirmedPct }} % du socle</p>
                </div>
                <div>
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs text-gray-300 font-mono uppercase">
                      <span class="scada-led scada-led-cyan mr-2"></span>Fact-checkés
                      <span class="text-gray-500">(fact-check)</span>
                    </span>
                    <span class="scada-data text-sm">
                      {{ data.status.fact_checked.toLocaleString() }} <span class="text-gray-500">/ {{ data.status.total.toLocaleString() }}</span>
                    </span>
                  </div>
                  <div class="h-4 bg-slate-800 border border-slate-700 overflow-hidden">
                    <div
                      class="h-full bg-cyan-500 transition-all duration-500"
                      :style="{ width: `${factCheckedPct}%` }"
                    ></div>
                  </div>
                  <p class="text-xs text-gray-500 mt-1 text-right">{{ factCheckedPct }} % du socle</p>
                </div>
                <div class="pt-3 border-t border-slate-700">
                  <p class="text-xs text-gray-500 leading-relaxed">
                    Les faits vérifiés portent le tag <span class="text-emerald-400 font-mono">status:CONFIRME</span> :
                    la couverture du socle par la vérification forensique (KERNEL) se mesure ici.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Top sujets + Timeline -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="scada-panel">
              <h2 class="scada-label text-cyan-400 mb-1 pb-3 border-b-2 border-slate-700">
                Top sujets
              </h2>
              <p class="text-xs text-gray-500 mb-4 -mt-2">Cliquer un sujet pour explorer son arborescence (T3)</p>
              <div v-if="data.top_subjects.length > 0" class="space-y-1">
                <button
                  v-for="s in data.top_subjects"
                  :key="s.tag"
                  @click="selectSubject(s.tag)"
                  class="w-full flex items-center gap-3 px-2 py-1.5 rounded transition-colors hover:bg-slate-800/70 group text-left"
                >
                  <span class="w-4 h-4 flex-shrink-0 border-2 border-cyan-500 text-cyan-400 text-[10px] flex items-center justify-center group-hover:bg-cyan-500 group-hover:text-slate-950 transition-colors">
                    ›
                  </span>
                  <span class="flex-1 text-xs text-gray-300 font-mono truncate">{{ s.tag }}</span>
                  <div class="w-24 h-2 bg-slate-800 border border-slate-700 overflow-hidden">
                    <div
                      class="h-full bg-cyan-600/70 group-hover:bg-cyan-400 transition-colors"
                      :style="{ width: `${Math.round((s.count / maxSubjectCount) * 100)}%` }"
                    ></div>
                  </div>
                  <span class="w-12 text-right scada-data text-sm">{{ s.count.toLocaleString() }}</span>
                </button>
              </div>
              <div v-else class="text-sm text-gray-500 py-6 text-center">
                Aucun sujet — le socle n'est pas encore taggé.
              </div>
            </div>

            <div class="scada-panel">
              <h2 class="scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
                Timeline des investigations
              </h2>
              <div v-if="timelineBars.length > 0" class="flex items-end gap-1 h-40">
                <div
                  v-for="b in timelineBars"
                  :key="b.month"
                  class="flex-1 flex flex-col items-center justify-end h-full group min-w-0"
                  :title="`${formatMonth(b.month)} : ${b.count.toLocaleString()}`"
                >
                  <span class="text-[9px] text-gray-500 font-mono mb-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    {{ b.count }}
                  </span>
                  <div
                    class="w-full bg-cyan-600/60 group-hover:bg-cyan-400 transition-colors rounded-t-sm"
                    :style="{ height: `${Math.max(b.pct, 3)}%` }"
                  ></div>
                  <span class="text-[9px] text-gray-500 font-mono mt-1 rotate-0">{{ b.short }}</span>
                </div>
              </div>
              <div v-else class="text-sm text-gray-500 py-6 text-center">
                Aucune investigation datée.
              </div>
            </div>
          </div>
        </div>

        <!-- ============ EXPLORER TAB (T3) ============ -->
        <div v-else-if="activeTab === 'explorer'" class="scada-panel text-center py-16">
          <div v-if="selectedSubject" class="space-y-4">
            <p class="text-sm text-gray-400 font-mono uppercase tracking-wide">Sujet sélectionné</p>
            <p class="scada-data text-2xl">{{ selectedSubject }}</p>
            <p class="text-sm text-gray-500">L'arborescence sujet → enquêtes → faits vérifiés → sources arrive en T3.</p>
          </div>
          <div v-else class="space-y-3">
            <span class="text-4xl">🧭</span>
            <h3 class="text-lg font-medium text-gray-300 uppercase">Explorer un sujet</h3>
            <p class="text-sm text-gray-500 max-w-md mx-auto">
              Cliquez un sujet dans l'onglet Socle pour voir son arborescence.
              L'arborescence sujet → enquêtes → faits vérifiés → sources arrive en T3.
            </p>
          </div>
        </div>

        <!-- ============ RELATIONS TAB (T4) ============ -->
        <div v-else class="scada-panel text-center py-16 space-y-3">
          <span class="text-4xl">🕸️</span>
          <h3 class="text-lg font-medium text-gray-300 uppercase">Graphe de relations</h3>
          <p class="text-sm text-gray-500 max-w-md mx-auto">
            Le graphe des liens entre mémoires (proxy par tags partagés) arrive en T4.
            Le backend <span class="text-cyan-400 font-mono">/related-by-tags</span> est déjà opérationnel.
          </p>
        </div>
      </template>

      <!-- Empty -->
      <div v-else-if="!loading" class="scada-panel text-center py-16">
        <h3 class="text-lg font-medium text-gray-300 uppercase">Aucune donnée</h3>
        <p class="mt-2 text-sm text-gray-500">Le socle est vide — le backend /explorer/stats n'a rien retourné.</p>
      </div>
    </div>
  </div>
</template>
