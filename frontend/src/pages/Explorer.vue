<script setup lang="ts">
/**
 * Explorer.vue — EPIC-78 Knowledge Explorer
 *
 * Onglets : Socle (T2) / Explorer (T3) / Relations (T4).
 * T2 : vue « Socle » — distribution par type, top sujets cliquables,
 *      couverture factuelle (status:CONFIRME) et timeline des investigations.
 * T3 : vue « Explorer » — arborescence sujet -> enquêtes -> faits vérifiés ->
 *      autres, branchée sur GET /api/v1/memories/explorer/tree.
 */
import { ref, computed, watch, onMounted } from 'vue'
import { getExplorerStats, getExplorerTree } from '@/api/explorer'
import type { ExplorerStats, ExplorerTree, ExplorerTreeItem } from '@/types/explorer'
import TreeItemRow from '@/components/TreeItemRow.vue'

// --- États
type Tab = 'socle' | 'explorer' | 'relations'
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
  if (tab === 'explorer' && selectedSubject.value && !tree.value && !treeLoading.value) {
    loadTree(selectedSubject.value)
  }
})

const copyFeedback = ref<string | null>(null)
async function copyId(id: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(id)
    copyFeedback.value = 'ID copié !'
  } catch {
    copyFeedback.value = 'Copie impossible'
  }
  setTimeout(() => {
    copyFeedback.value = null
  }, 2000)
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

      <!-- Copy feedback toast -->
      <Transition name="fade">
        <div
          v-if="copyFeedback"
          class="fixed top-4 right-4 bg-emerald-600 text-white px-4 py-2 rounded shadow-lg z-50 font-mono text-sm"
        >
          {{ copyFeedback }}
        </div>
      </Transition>

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

          <!-- Détail de l'élément sélectionné (préfiguration T5) -->
          <div v-if="selectedItem" class="scada-panel">
            <div class="flex items-center justify-between mb-3">
              <h3 class="scada-label text-cyan-400">Détail</h3>
              <button
                @click="selectedItem = null"
                class="text-xs font-mono text-gray-500 hover:text-gray-300 transition-colors uppercase"
              >
                Fermer ✕
              </button>
            </div>
            <p class="text-base text-gray-100 font-mono">{{ selectedItem.title }}</p>
            <div class="flex flex-wrap items-center gap-2 mt-3">
              <span class="badge-info text-xs">{{ selectedItem.memory_type }}</span>
              <span class="text-xs text-gray-500 font-mono">
                {{ formatDate(selectedItem.created_at) }}
              </span>
              <button
                @click="copyId(selectedItem.id)"
                class="ml-auto text-xs font-mono text-gray-500 hover:text-emerald-400 transition-colors uppercase"
                title="Copier l'ID"
              >
                📋 copier l'id
              </button>
            </div>
            <div v-if="selectedItem.tags.length > 0" class="mt-3 flex flex-wrap gap-1.5">
              <span
                v-for="tag in selectedItem.tags"
                :key="tag"
                class="inline-block text-xs bg-slate-700 text-gray-300 px-2 py-0.5 rounded"
              >
                #{{ tag }}
              </span>
            </div>
            <p class="text-xs text-gray-600 mt-4">La fiche enrichie (contenu, entités, liens) arrive en T5.</p>
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

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
