<script setup lang="ts">
/**
 * MemoryDetailPanel.vue — EPIC-78 T5
 * Fiche mémoire enrichie : contenu markdown (useMarkdown), tags colorés par
 * rôle (status:/project:/article:/circuit:/piste:), entités/concepts, et
 * bloc « Liées » (relations par proxy de tags partagés, re-centrage possible).
 */
import { ref, computed, watch } from 'vue'
import { getMemoryDetail, getRelatedByTags } from '@/api/explorer'
import { useMarkdown } from '@/composables/useMarkdown'
import type { MemoryDetail, RelatedItem } from '@/types/explorer'

const props = defineProps<{
  memoryId: string
  title: string
}>()

const emit = defineEmits<{
  close: []
  'select-memory': [
    item: { id: string; title: string; memory_type: string; tags: string[]; created_at: string | null }
  ]
}>()

// --- Détail
const detail = ref<MemoryDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref<string | null>(null)

// --- Relations (Liées)
const related = ref<RelatedItem[]>([])
const relatedLoading = ref(false)
const relatedError = ref<string | null>(null)

// Séquence anti-course (changements rapides de mémoire)
let seq = 0

async function loadMemory(): Promise<void> {
  const current = ++seq
  detailLoading.value = true
  detailError.value = null
  detail.value = null
  related.value = []
  try {
    const d = await getMemoryDetail(props.memoryId)
    if (current !== seq) return
    detail.value = d
  } catch (err) {
    if (current !== seq) return
    detailError.value = err instanceof Error ? err.message : 'Chargement impossible'
  } finally {
    if (current === seq) detailLoading.value = false
  }

  relatedLoading.value = true
  relatedError.value = null
  try {
    const resp = await getRelatedByTags(props.memoryId, 8)
    if (current !== seq) return
    related.value = resp.related
  } catch (err) {
    if (current !== seq) return
    relatedError.value = err instanceof Error ? err.message : 'Chargement des relations impossible'
  } finally {
    if (current === seq) relatedLoading.value = false
  }
}

watch(() => props.memoryId, loadMemory, { immediate: true })

// --- Rendu
const contentRef = computed(() => detail.value?.content || '')
const { renderedContent } = useMarkdown(contentRef)

const copyFeedback = ref(false)
async function copyId(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.memoryId)
    copyFeedback.value = true
    setTimeout(() => {
      copyFeedback.value = false
    }, 2000)
  } catch {
    /* clipboard indisponible : silencieux */
  }
}

function formatDate(d: string | null | undefined): string {
  if (!d) return ''
  return new Date(d).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

/** Couleur et rôle d'un tag selon son préfixe (insensible à la casse : la base
 *  a des tags mixtes status:CONFIRME / status:confirme). */
function tagRole(tag: string): { cls: string } {
  const base = 'inline-block text-[10px] font-mono px-1.5 py-0.5 rounded border mr-1 mb-1'
  const t = tag.toLowerCase()
  if (t === 'status:confirme')
    return { cls: `${base} bg-emerald-600/30 text-emerald-300 border-emerald-600/50` }
  if (t.startsWith('status:'))
    return { cls: `${base} bg-amber-600/30 text-amber-300 border-amber-600/50` }
  if (t.startsWith('project:'))
    return { cls: `${base} bg-cyan-600/30 text-cyan-300 border-cyan-600/50` }
  if (t.startsWith('article:'))
    return { cls: `${base} bg-blue-600/30 text-blue-300 border-blue-600/50` }
  if (t.startsWith('circuit:'))
    return { cls: `${base} bg-orange-600/30 text-orange-300 border-orange-600/50` }
  if (t.startsWith('piste:'))
    return { cls: `${base} bg-purple-600/30 text-purple-300 border-purple-600/50` }
  if (t === 'fact-check')
    return { cls: `${base} bg-emerald-600/30 text-emerald-300 border-emerald-600/50` }
  if (t.startsWith('date:') || t.startsWith('session:') || t.startsWith('source-'))
    return { cls: `${base} bg-slate-700 text-gray-400 border-slate-600` }
  return { cls: `${base} bg-slate-700 text-gray-300 border-slate-600` }
}

function selectRelated(r: RelatedItem): void {
  emit('select-memory', {
    id: r.id,
    title: r.title,
    memory_type: r.memory_type,
    tags: r.shared_tags,
    created_at: null
  })
}

const hasEmbeddingLabel = computed(() => (detail.value?.has_embedding ? 'EMBEDDED' : 'NO EMBED'))
</script>

<template>
  <div class="scada-panel">
    <!-- Header -->
    <div class="flex items-start justify-between mb-3">
      <div class="flex items-center gap-2">
        <span class="scada-led scada-led-cyan"></span>
        <h3 class="scada-label text-cyan-400">Fiche mémoire</h3>
      </div>
      <button
        @click="emit('close')"
        class="text-xs font-mono text-gray-500 hover:text-gray-300 transition-colors uppercase"
      >
        Fermer ✕
      </button>
    </div>

    <!-- Erreur -->
    <div v-if="detailError" class="alert-error">
      <span class="text-sm font-mono">{{ detailError }}</span>
    </div>

    <!-- Chargement : le titre du nœud sert de placeholder en attendant le détail -->
    <div v-if="detailLoading" class="animate-pulse space-y-3">
      <p class="text-base text-gray-200 font-mono">{{ title }}</p>
      <div class="h-4 bg-slate-800/60 w-1/3"></div>
      <div class="h-24 bg-slate-800/60"></div>
    </div>

    <template v-else-if="detail">
      <!-- Titre -->
      <p class="text-base text-gray-100 font-mono">{{ detail.title }}</p>

      <!-- Meta -->
      <div class="flex flex-wrap items-center gap-2 mt-2 text-xs font-mono text-slate-400">
        <span class="px-1.5 py-0.5 bg-slate-700 rounded uppercase">{{ detail.memory_type }}</span>
        <span>{{ formatDate(detail.created_at) }}</span>
        <span v-if="detail.author">· {{ detail.author }}</span>
        <span
          class="px-1.5 py-0.5 rounded"
          :class="detail.has_embedding ? 'bg-emerald-900/40 text-emerald-400' : 'bg-slate-800 text-gray-500'"
        >
          {{ hasEmbeddingLabel }}
        </span>
        <button
          @click="copyId"
          class="ml-auto text-xs font-mono text-gray-500 hover:text-emerald-400 transition-colors uppercase"
          :title="copyFeedback ? 'ID copié !' : 'Copier l ID'"
        >
          {{ copyFeedback ? '✓ copié' : '📋 copier l id' }}
        </button>
      </div>

      <!-- Tags colorés par rôle -->
      <div v-if="detail.tags.length > 0" class="mt-3">
        <span
          v-for="tag in detail.tags"
          :key="tag"
          :class="tagRole(tag).cls"
        >
          #{{ tag }}
        </span>
      </div>

      <!-- Entités / concepts -->
      <div v-if="detail.entities.length > 0 || detail.concepts.length > 0" class="mt-4 pt-3 border-t-2 border-slate-700 space-y-3">
        <div v-if="detail.entities.length > 0">
          <h4 class="scada-label mb-2">Entités</h4>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="e in detail.entities"
              :key="e"
              class="text-xs font-mono px-2 py-0.5 bg-purple-600/20 text-purple-300 border border-purple-600/40 rounded"
            >
              {{ e }}
            </span>
          </div>
        </div>
        <div v-if="detail.concepts.length > 0">
          <h4 class="scada-label mb-2">Concepts</h4>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="c in detail.concepts"
              :key="c"
              class="text-xs font-mono px-2 py-0.5 bg-cyan-600/20 text-cyan-300 border border-cyan-600/40 rounded"
            >
              {{ c }}
            </span>
          </div>
        </div>
      </div>

      <!-- Contenu markdown -->
      <div class="mt-4 pt-3 border-t-2 border-slate-700">
        <h4 class="scada-label mb-3">Contenu</h4>
        <div
          v-if="renderedContent"
          class="scada-markdown text-sm"
          v-html="renderedContent"
        ></div>
        <p v-else class="text-sm text-gray-500">(contenu vide)</p>
      </div>

      <!-- Liées -->
      <div class="mt-4 pt-3 border-t-2 border-slate-700">
        <h4 class="scada-label mb-3">
          Liées
          <span v-if="relatedLoading" class="text-gray-500">(chargement…)</span>
          <span v-else class="text-gray-500">({{ related.length }})</span>
        </h4>
        <p v-if="relatedError" class="text-xs text-red-400 font-mono">{{ relatedError }}</p>
        <div v-else-if="related.length > 0" class="space-y-1.5">
          <button
            v-for="r in related"
            :key="r.id"
            @click="selectRelated(r)"
            class="w-full text-left px-3 py-2 border border-slate-700 bg-slate-900/50 hover:border-cyan-500/50 rounded transition-colors"
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
            <div class="mt-1 flex flex-wrap gap-1">
              <span
                v-for="t in r.shared_tags.slice(0, 3)"
                :key="t"
                class="text-[10px] bg-slate-700 text-gray-400 px-1 rounded"
              >
                #{{ t }}
              </span>
            </div>
          </button>
          <p class="text-[10px] text-gray-600 font-mono pt-1">
            Clic = ouvrir cette fiche · tags partagés pondérés (proxy)
          </p>
        </div>
        <p v-else-if="!relatedLoading" class="text-xs text-gray-500">Aucune mémoire liée par tags partagés.</p>
      </div>
    </template>
  </div>
</template>
