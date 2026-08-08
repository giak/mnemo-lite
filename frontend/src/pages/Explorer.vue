<script setup lang="ts">
/**
 * Explorer.vue — EPIC-78 Knowledge Explorer
 *
 * Onglets : Socle (T2) / Explorer (T3) / Relations (T4) / Recherche (T6).
 * T2 : vue « Socle » — distribution par type, top sujets cliquables,
 *      couverture factuelle (status:CONFIRME) et timeline des investigations.
 * T3 : vue « Explorer » — arborescence sujet -> enquêtes -> faits vérifiés ->
 *      autres, branchée sur GET /api/v1/memories/explorer/tree.
 * T4 : vue « Relations » — graphe G6 des mémoires liées par tags partagés.
 * T6 : vue « Recherche » — recherche avancée (type + statut + tags + période).
 */
import { ref, computed, watch, onMounted } from 'vue'
import {
  getExplorerStats,
  getExplorerTree,
  getRelatedByTags,
  searchSourceMemories,
  searchMemories
} from '@/api/explorer'
import type {
  ExplorerStats,
  ExplorerTree,
  ExplorerTreeItem,
  RelatedItem,
  SearchResultItem
} from '@/types/explorer'
import TreeItemRow from '@/components/TreeItemRow.vue'
import G6Graph from '@/components/G6Graph.vue'
import MemoryDetailPanel from '@/components/MemoryDetailPanel.vue'

// --- États
type Tab = 'socle' | 'explorer' | 'relations' | 'recherche'
const activeTab = ref<Tab>('socle')
const selectedSubject = ref<string | null>(null)
const subjectQuery = ref('')

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

// --- Arborescence (T3)
const tree = ref<ExplorerTree | null>(null)
const treeLoading = ref(false)
const treeError = ref<string | null>(null)
const selectedItem = ref<ExplorerTreeItem | null>(null)

async function loadTree(subject: string): Promise<void> {
  treeLoading.value = true
  treeError.value = null
  selectedItem.value = null
  try {
    tree.value = await getExplorerTree(subject)
  } catch (err) {
    treeError.value = err instanceof Error ? err.message : 'Failed to load tree'
  } finally {
    treeLoading.value = false
  }
}

/** Sélection d'un sujet (depuis le Socle ou le sélecteur) -> charge l'arborescence */
function selectSubject(tag: string): void {
  selectedSubject.value = tag
  activeTab.value = 'explorer'
  loadTree(tag)
}

function exploreFromInput(): void {
  const q = subjectQuery.value.trim()
  if (q) selectSubject(q)
}

// Si on revient sur l'onglet Explorer avec un sujet déjà choisi mais jamais chargé
watch(activeTab, (tab) => {
  // La fiche mémoire est scopée à l'onglet : on la ferme en quittant l'onglet
  // (évite une fiche périmée d'un autre onglet)
  selectedItem.value = null
  if (tab === 'explorer' && selectedSubject.value && !tree.value && !treeLoading.value) {
    loadTree(selectedSubject.value)
  }
})

// --- Relations (T4)
const sourceQuery = ref('')
const sourceResults = ref<ExplorerTreeItem[]>([])
const sourceSearching = ref(false)
const sourceError = ref<string | null>(null)

const sourceMemory = ref<ExplorerTreeItem | null>(null)
const related = ref<RelatedItem[]>([])
const relatedTotal = ref(0)
const relatedLoading = ref(false)
const relatedError = ref<string | null>(null)
const minShared = ref(1)
const relatedLimit = ref(20)

async function searchSources(): Promise<void> {
  const q = sourceQuery.value.trim()
  if (!q) return
  sourceSearching.value = true
  sourceError.value = null
  try {
    sourceResults.value = await searchSourceMemories(q)
  } catch (err) {
    sourceError.value = err instanceof Error ? err.message : 'Recherche impossible'
  } finally {
    sourceSearching.value = false
  }
}

/** Une relation choisie dans la fiche remplace l'élément sélectionné (re-centrage) */
function handleSelectMemory(item: {
  id: string
  title: string
  memory_type: string
  tags: string[]
  created_at: string | null
}): void {
  selectedItem.value = { ...item }
}

// Séquence anti-course : seule la dernière requête fait foi (changements rapides de source)
let relatedSeq = 0

async function loadRelated(): Promise<void> {
  if (!sourceMemory.value) return
  const seq = ++relatedSeq
  relatedLoading.value = true
  relatedError.value = null
  try {
    const resp = await getRelatedByTags(sourceMemory.value.id, relatedLimit.value, minShared.value)
    if (seq !== relatedSeq) return // réponse obsolète : une plus récente est en vol
    related.value = resp.related
    relatedTotal.value = resp.total
  } catch (err) {
    if (seq !== relatedSeq) return
    relatedError.value = err instanceof Error ? err.message : 'Chargement des relations impossible'
  } finally {
    if (seq === relatedSeq) relatedLoading.value = false
  }
}

function selectSource(item: ExplorerTreeItem): void {
  sourceMemory.value = item
  sourceQuery.value = ''
  sourceResults.value = []
  loadRelated()
}

function clearSource(): void {
  sourceMemory.value = null
  related.value = []
  relatedTotal.value = 0
}

/** Re-centrage : une relation devient la nouvelle source (saute de puce) */
function selectRelated(r: RelatedItem): void {
  selectSource({
    id: r.id,
    title: r.title,
    memory_type: r.memory_type,
    tags: r.shared_tags,
    created_at: null
  })
}

// Chips rapides : éléments du tree courant (si un sujet a été exploré)
const treeQuickSources = computed<ExplorerTreeItem[]>(() => {
  if (!tree.value) return []
  return [...tree.value.investigations, ...tree.value.facts, ...tree.value.others].slice(0, 8)
})

// Graphe G6 : nœud central = source, satellites = relations
const graphNodes = computed(() => {
  if (!sourceMemory.value) return []
  const nodes: Array<{ id: string; label: string; type: string }> = [
    {
      id: sourceMemory.value.id,
      label: sourceMemory.value.title,
      type: sourceMemory.value.memory_type
    }
  ]
  for (const r of related.value) {
    nodes.push({ id: r.id, label: r.title, type: r.memory_type })
  }
  return nodes
})

const graphEdges = computed(() => {
  if (!sourceMemory.value) return []
  return related.value.map((r) => ({
    id: `${sourceMemory.value!.id}->${r.id}`,
    source: sourceMemory.value!.id,
    target: r.id,
    type: 'related'
  }))
})

// Recharger les relations quand les filtres changent
watch([minShared, relatedLimit], () => {
  if (sourceMemory.value) loadRelated()
})

// --- Recherche avancée (T6)
const searchQuery = ref('')
const searchType = ref('')
const searchStatus = ref('')
const searchTags = ref('')
const searchFrom = ref('')
const searchTo = ref('')
const searchResults = ref<SearchResultItem[]>([])
const searchTotal = ref(0)
const searchRunning = ref(false)
const searchError = ref<string | null>(null)
const searchHasRun = ref(false)

const SEARCH_TYPES = [
  { value: 'investigation', label: 'Enquêtes' },
  { value: 'article', label: 'Articles' },
  { value: 'quintessence', label: 'Fiches internes' },
  { value: 'reference', label: 'Références' },
  { value: 'note', label: 'Notes' },
  { value: 'decision', label: 'Décisions' },
  { value: 'task', label: 'Tâches' },
  { value: 'conversation', label: 'Conversations' }
]

const SEARCH_STATUSES = [
  { value: 'status:CONFIRME', label: 'status:CONFIRME' },
  { value: 'fact-check', label: 'fact-check' }
]

async function runSearch(): Promise<void> {
  const q = searchQuery.value.trim()
  if (!q) {
    searchError.value = 'Saisissez un texte de recherche.'
    return
  }
  searchRunning.value = true
  searchError.value = null
  try {
    const resp = await searchMemories({
      query: q,
      memory_type: searchType.value || undefined,
      status: searchStatus.value || undefined,
      tags: searchTags.value
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      created_from: searchFrom.value || undefined,
      created_to: searchTo.value || undefined,
      limit: 50
    })
    searchResults.value = resp.results
    searchTotal.value = resp.total
    searchHasRun.value = true
  } catch (err) {
    searchError.value = err instanceof Error ? err.message : 'Recherche impossible'
  } finally {
    searchRunning.value = false
  }
}

function resetSearch(): void {
  searchQuery.value = ''
  searchType.value = ''
  searchStatus.value = ''
  searchTags.value = ''
  searchFrom.value = ''
  searchTo.value = ''
  searchResults.value = []
  searchTotal.value = 0
  searchError.value = null
  searchHasRun.value = false
  selectedItem.value = null
}

/** Un résultat de recherche devient la fiche affichée (le score est perdu, géré par la fiche) */
function openSearchResult(item: ExplorerTreeItem): void {
  selectedItem.value = item
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

const formatDate = (d: string | null) => {
  if (!d) return ''
  return new Date(d).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
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
            v-for="t in (['socle', 'explorer', 'relations', 'recherche'] as Tab[])"
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
              <p class="text-xs text-gray-500 mb-4 -mt-2">Cliquer un sujet pour explorer son arborescence</p>
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
        <div v-else-if="activeTab === 'explorer'" class="space-y-6">
          <!-- Sélecteur de sujet -->
          <div class="scada-panel">
            <h2 class="scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
              Sélectionner un sujet
            </h2>
            <div class="flex gap-3">
              <input
                v-model="subjectQuery"
                @keypress.enter="exploreFromInput"
                type="text"
                class="input flex-1"
                placeholder="Tag de sujet (ex: 14-juillet-2026, ingerences-russes, macron)"
              />
              <button
                @click="exploreFromInput"
                :disabled="!subjectQuery.trim() || treeLoading"
                class="scada-btn scada-btn-primary"
              >
                {{ treeLoading ? 'CHARGEMENT...' : 'EXPLORER' }}
              </button>
            </div>
            <div v-if="data.top_subjects.length > 0" class="mt-3 flex flex-wrap gap-2">
              <button
                v-for="s in data.top_subjects.slice(0, 12)"
                :key="s.tag"
                @click="selectSubject(s.tag)"
                class="px-2 py-1 text-xs font-mono border rounded transition-colors"
                :class="
                  selectedSubject === s.tag
                    ? 'border-cyan-400 text-cyan-400 bg-cyan-950/30'
                    : 'border-slate-600 text-gray-400 hover:border-cyan-500 hover:text-cyan-400'
                "
              >
                {{ s.tag }} <span class="text-gray-600">{{ s.count }}</span>
              </button>
            </div>
          </div>

          <!-- Erreur arborescence -->
          <div v-if="selectedSubject && treeError" class="alert-error">
            <span class="text-sm font-mono">{{ treeError }}</span>
          </div>

          <!-- Chargement arborescence -->
          <div v-if="selectedSubject && treeLoading" class="animate-pulse space-y-3">
            <div v-for="i in 6" :key="i" class="h-12 bg-slate-800/60 border-2 border-slate-700"></div>
          </div>

          <!-- Résultats -->
          <template v-else-if="selectedSubject && tree">
            <div v-if="tree.total > 0" class="space-y-6">
              <!-- Barre de synthèse -->
              <div class="flex flex-wrap items-center gap-3">
                <span class="scada-led scada-led-cyan"></span>
                <h2 class="text-lg font-mono text-cyan-400 uppercase tracking-wide">{{ tree.subject }}</h2>
                <span class="text-sm text-gray-500 font-mono">{{ tree.total }} éléments</span>
                <span class="text-xs text-gray-500 font-mono uppercase">(majuscules/minuscules ignorées)</span>
              </div>

              <!-- Enquêtes -->
              <section v-if="tree.investigations.length > 0">
                <h3 class="scada-label text-cyan-400 mb-3 pb-2 border-b border-slate-700">
                  🔬 Enquêtes <span class="text-gray-500">({{ tree.investigations.length }})</span>
                </h3>
                <div class="space-y-2">
                  <TreeItemRow
                    v-for="item in tree.investigations"
                    :key="item.id"
                    :item="item"
                    :active="selectedItem?.id === item.id"
                    @select="selectedItem = item"
                  />
                </div>
              </section>

              <!-- Faits vérifiés -->
              <section v-if="tree.facts.length > 0">
                <h3 class="scada-label text-amber-400 mb-3 pb-2 border-b border-slate-700">
                  🧬 Faits vérifiés <span class="text-gray-500">({{ tree.facts.length }})</span>
                </h3>
                <div class="space-y-2">
                  <TreeItemRow
                    v-for="item in tree.facts"
                    :key="item.id"
                    :item="item"
                    :active="selectedItem?.id === item.id"
                    @select="selectedItem = item"
                  />
                </div>
              </section>

              <!-- Autres -->
              <section v-if="tree.others.length > 0">
                <h3 class="scada-label text-gray-400 mb-3 pb-2 border-b border-slate-700">
                  📄 Autres <span class="text-gray-500">({{ tree.others.length }})</span>
                </h3>
                <div class="space-y-2">
                  <TreeItemRow
                    v-for="item in tree.others"
                    :key="item.id"
                    :item="item"
                    :active="selectedItem?.id === item.id"
                    @select="selectedItem = item"
                  />
                </div>
              </section>
            </div>

            <div v-else class="scada-panel text-center py-14 space-y-3">
              <span class="text-4xl">🔎</span>
              <h3 class="text-lg font-medium text-gray-300 uppercase">Aucun élément</h3>
              <p class="text-sm text-gray-500 max-w-md mx-auto">
                Le sujet <span class="text-cyan-400 font-mono">{{ tree.subject }}</span> ne correspond à
                aucune mémoire. Vérifiez le tag (il doit être présent sur au moins une mémoire du socle).
              </p>
            </div>
          </template>

          <!-- État initial / aucun sujet -->
          <div v-else class="scada-panel text-center py-16 space-y-3">
            <span class="text-4xl">🧭</span>
            <h3 class="text-lg font-medium text-gray-300 uppercase">Explorer un sujet</h3>
            <p class="text-sm text-gray-500 max-w-md mx-auto">
              Saisissez un tag de sujet ou cliquez sur un sujet ci-dessus (ou dans l'onglet Socle)
              pour voir son arborescence : enquêtes → faits vérifiés → sources.
            </p>
          </div>

          <!-- Fiche mémoire enrichie (T5) -->
          <MemoryDetailPanel
            v-if="selectedItem"
            :memory-id="selectedItem.id"
            :title="selectedItem.title"
            @close="selectedItem = null"
            @select-memory="handleSelectMemory"
          />
        </div>

        <!-- ============ RECHERCHE TAB (T6) ============ -->
        <div v-else-if="activeTab === 'recherche'" class="space-y-6">
          <!-- Filtres combinés -->
          <div class="scada-panel">
            <h2 class="scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
              Recherche avancée
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <div class="md:col-span-2 lg:col-span-3">
                <input
                  v-model="searchQuery"
                  @keypress.enter="runSearch"
                  type="text"
                  class="input w-full"
                  placeholder="Requête sémantique (ex: parrainages, ingérences russes, ARCOM)"
                />
              </div>
              <div>
                <label class="block text-[10px] text-gray-500 font-mono uppercase mb-1">Type</label>
                <select v-model="searchType" class="input w-full">
                  <option value="">Tous</option>
                  <option v-for="t in SEARCH_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[10px] text-gray-500 font-mono uppercase mb-1">Statut</label>
                <select v-model="searchStatus" class="input w-full">
                  <option value="">Tous</option>
                  <option v-for="s in SEARCH_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[10px] text-gray-500 font-mono uppercase mb-1">Tags (séparés par virgule)</label>
                <input
                  v-model="searchTags"
                  type="text"
                  class="input w-full"
                  placeholder="sujet:14-juillet-2026, piste:12"
                />
              </div>
              <div>
                <label class="block text-[10px] text-gray-500 font-mono uppercase mb-1">Créé après</label>
                <input v-model="searchFrom" type="date" class="input w-full" />
              </div>
              <div>
                <label class="block text-[10px] text-gray-500 font-mono uppercase mb-1">Créé avant</label>
                <input v-model="searchTo" type="date" class="input w-full" />
              </div>
              <div class="flex items-end gap-2">
                <button
                  @click="runSearch"
                  :disabled="!searchQuery.trim() || searchRunning"
                  class="scada-btn scada-btn-primary flex-1"
                >
                  {{ searchRunning ? 'RECHERCHE...' : 'RECHERCHER' }}
                </button>
                <button
                  @click="resetSearch"
                  class="scada-btn"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>

          <!-- Erreur -->
          <div v-if="searchError" class="alert-error">
            <span class="text-sm font-mono">{{ searchError }}</span>
          </div>

          <!-- Chargement -->
          <div v-if="searchRunning" class="animate-pulse space-y-3">
            <div v-for="i in 5" :key="i" class="h-12 bg-slate-800/60 border-2 border-slate-700"></div>
          </div>

          <!-- Résultats -->
          <template v-else>
            <div v-if="searchHasRun && searchResults.length > 0" class="space-y-3">
              <p class="text-xs text-gray-500 font-mono uppercase">
                {{ searchTotal }} résultat{{ searchTotal > 1 ? 's' : '' }} — cliquer une ligne pour ouvrir la fiche
              </p>
              <TreeItemRow
                v-for="item in searchResults"
                :key="item.id"
                :item="item"
                :score="item.score"
                :active="selectedItem?.id === item.id"
                @select="openSearchResult"
              />
            </div>

            <div
              v-else-if="searchHasRun"
              class="scada-panel text-center py-14 space-y-3"
            >
              <span class="text-4xl">🔎</span>
              <h3 class="text-lg font-medium text-gray-300 uppercase">Aucun résultat</h3>
              <p class="text-sm text-gray-500 max-w-md mx-auto">
                Aucune mémoire ne correspond aux filtres. Élargissez la requête ou retirez des filtres.
              </p>
            </div>
          </template>

          <!-- État initial -->
          <div
            v-if="!searchHasRun && !searchRunning"
            class="scada-panel text-center py-16 space-y-3"
          >
            <span class="text-4xl">🔍</span>
            <h3 class="text-lg font-medium text-gray-300 uppercase">Rechercher dans le socle</h3>
            <p class="text-sm text-gray-500 max-w-md mx-auto">
              Combinez une requête sémantique avec des filtres : type, statut (status:CONFIRME,
              fact-check), tags (AND) et période de création.
            </p>
          </div>

          <!-- Fiche mémoire enrichie (T5) -->
          <MemoryDetailPanel
            v-if="selectedItem"
            :memory-id="selectedItem.id"
            :title="selectedItem.title"
            @close="selectedItem = null"
            @select-memory="handleSelectMemory"
          />
        </div>

        <!-- ============ RELATIONS TAB (T4) ============ -->
        <div v-else class="space-y-6">
          <!-- Sélecteur de mémoire source -->
          <div class="scada-panel">
            <h2 class="scada-label text-cyan-400 mb-4 pb-3 border-b-2 border-slate-700">
              Mémoire source
            </h2>
            <div class="flex gap-3">
              <input
                v-model="sourceQuery"
                @keypress.enter="searchSources"
                type="text"
                class="input flex-1"
                placeholder="Rechercher une mémoire par titre (ex: parrainages, ARCOM)"
              />
              <button
                @click="searchSources"
                :disabled="!sourceQuery.trim() || sourceSearching"
                class="scada-btn scada-btn-primary"
              >
                {{ sourceSearching ? 'RECHERCHE...' : 'RECHERCHER' }}
              </button>
            </div>

            <!-- Résultats de recherche -->
            <div v-if="sourceResults.length > 0" class="mt-3 space-y-1">
              <button
                v-for="r in sourceResults"
                :key="r.id"
                @click="selectSource(r)"
                class="w-full flex items-center gap-3 px-3 py-2 border border-slate-700 bg-slate-900/50 hover:border-cyan-500/50 rounded transition-colors text-left"
              >
                <span class="flex-1 min-w-0">
                  <span class="block text-sm text-gray-200 font-mono truncate">{{ r.title }}</span>
                  <span class="block text-[10px] text-gray-500 font-mono uppercase mt-0.5">
                    {{ r.memory_type }} · {{ formatDate(r.created_at) }}
                  </span>
                </span>
                <span class="text-gray-600">›</span>
              </button>
            </div>
            <p v-else-if="sourceError" class="mt-3 text-xs text-red-400 font-mono">{{ sourceError }}</p>

            <!-- Chips rapides depuis le tree courant -->
            <div v-if="treeQuickSources.length > 0" class="mt-3 pt-3 border-t border-slate-700">
              <p class="text-[10px] text-gray-500 font-mono uppercase mb-2">
                Depuis le sujet « {{ tree?.subject }} »
              </p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="item in treeQuickSources"
                  :key="item.id"
                  @click="selectSource(item)"
                  class="px-2 py-1 text-xs font-mono border rounded transition-colors border-slate-600 text-gray-400 hover:border-cyan-500 hover:text-cyan-400 max-w-xs truncate"
                  :title="item.title"
                >
                  {{ item.title }}
                </button>
              </div>
            </div>
          </div>

          <!-- Source choisie -->
          <div v-if="sourceMemory" class="space-y-6">
            <!-- Barre source + filtres -->
            <div class="scada-panel">
              <div class="flex flex-wrap items-center gap-3">
                <span class="scada-led scada-led-cyan"></span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-100 font-mono truncate">{{ sourceMemory.title }}</p>
                  <p class="text-[10px] text-gray-500 font-mono uppercase">
                    {{ sourceMemory.memory_type }} · {{ formatDate(sourceMemory.created_at) }} ·
                    {{ relatedTotal }} relations affichées (limit {{ relatedLimit }})
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <label class="text-[10px] text-gray-500 font-mono uppercase">Tags min</label>
                  <select
                    v-model.number="minShared"
                    class="bg-slate-700 text-gray-200 border border-slate-600 rounded px-2 py-1 text-xs"
                  >
                    <option :value="1">1</option>
                    <option :value="2">2</option>
                    <option :value="3">3</option>
                  </select>
                  <label class="text-[10px] text-gray-500 font-mono uppercase ml-2">Max</label>
                  <select
                    v-model.number="relatedLimit"
                    class="bg-slate-700 text-gray-200 border border-slate-600 rounded px-2 py-1 text-xs"
                  >
                    <option :value="10">10</option>
                    <option :value="20">20</option>
                    <option :value="50">50</option>
                  </select>
                  <button
                    @click="clearSource"
                    class="ml-2 text-xs font-mono text-gray-500 hover:text-gray-300 uppercase"
                  >
                    ✕ changer
                  </button>
                </div>
              </div>
            </div>

            <!-- Erreur -->
            <div v-if="relatedError" class="alert-error">
              <span class="text-sm font-mono">{{ relatedError }}</span>
            </div>

            <!-- Chargement -->
            <div v-if="relatedLoading" class="animate-pulse space-y-3">
              <div v-for="i in 5" :key="i" class="h-12 bg-slate-800/60 border-2 border-slate-700"></div>
            </div>

            <!-- Contenu -->
            <template v-else>
              <div
                v-if="related.length === 0"
                class="scada-panel text-center py-14 space-y-3"
              >
                <span class="text-4xl">🕸️</span>
                <h3 class="text-lg font-medium text-gray-300 uppercase">Aucune relation</h3>
                <p class="text-sm text-gray-500 max-w-md mx-auto">
                  Aucune mémoire ne partage un tag avec la source au seuil choisi.
                  Réduisez « Tags min » ou changez de mémoire source.
                </p>
              </div>

              <div v-else class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6">
                <!-- Graphe G6 réutilisé -->
                <div class="scada-panel p-0 overflow-hidden">
                  <G6Graph :nodes="graphNodes" :edges="graphEdges" :loading="relatedLoading" />
                </div>

                <!-- Liste des relations -->
                <div class="scada-panel max-h-[850px] overflow-y-auto">
                  <h3 class="scada-label text-cyan-400 mb-3 pb-2 border-b-2 border-slate-700">
                    Relations ({{ related.length }})
                  </h3>
                  <div class="space-y-2">
                    <button
                      v-for="r in related"
                      :key="r.id"
                      @click="selectRelated(r)"
                      class="w-full text-left px-3 py-2 border rounded transition-colors border-slate-700 bg-slate-900/50 hover:border-cyan-500/50"
                    >
                      <div class="flex items-center gap-2">
                        <span class="flex-1 text-xs text-gray-200 font-mono truncate">{{ r.title }}</span>
                        <span
                          class="flex-shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded"
                          :class="r.score >= 4 ? 'bg-amber-600/30 text-amber-300' : 'bg-slate-700 text-gray-300'"
                        >
                          score {{ r.score }}
                        </span>
                      </div>
                      <p class="text-[10px] text-gray-500 font-mono uppercase mt-1">{{ r.memory_type }}</p>
                      <div v-if="r.shared_tags.length > 0" class="mt-1 flex flex-wrap gap-1">
                        <span
                          v-for="t in r.shared_tags.slice(0, 4)"
                          :key="t"
                          class="text-[10px] bg-slate-700 text-gray-300 px-1 rounded"
                        >
                          #{{ t }}
                        </span>
                        <span v-if="r.shared_tags.length > 4" class="text-[10px] text-gray-500">
                          +{{ r.shared_tags.length - 4 }}
                        </span>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <!-- Aucune source -->
          <div v-else class="scada-panel text-center py-16 space-y-3">
            <span class="text-4xl">🕸️</span>
            <h3 class="text-lg font-medium text-gray-300 uppercase">Graphe de relations</h3>
            <p class="text-sm text-gray-500 max-w-md mx-auto">
              Recherchez une mémoire source pour voir les mémoires liées par tags partagés.
              Cliquez une relation pour re-centrer le graphe sur elle (exploration en saut de puce).
            </p>
          </div>
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

