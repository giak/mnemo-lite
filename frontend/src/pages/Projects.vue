<script setup lang="ts">
/**
 * EPIC-27: Projects Management Page
 * Manage indexed code repositories
 */
import { onMounted, ref, computed } from 'vue'
import { useProjects } from '@/composables/useProjects'
import type { Project } from '@/types/projects'

const {
  projects,
  activeProject,
  loading,
  error,
  fetchProjects,
  setActiveProject,
  reindexProject,
  deleteProject
} = useProjects()

const confirmDeleteProject = ref<string | null>(null)

onMounted(() => {
  fetchProjects()
})

function getStatusColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-500'
    case 'needs_reindex':
      return 'bg-yellow-500'
    case 'poor_coverage':
      return 'bg-orange-500'
    case 'error':
      return 'bg-red-500'
    default:
      return 'bg-gray-500'
  }
}

function getStatusTextColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'text-green-400'
    case 'needs_reindex':
      return 'text-yellow-400'
    case 'poor_coverage':
      return 'text-orange-400'
    case 'error':
      return 'text-red-400'
    default:
      return 'text-gray-400'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'healthy':
      return 'HEALTHY'
    case 'needs_reindex':
      return 'REINDEX'
    case 'poor_coverage':
      return 'LOW COV'
    case 'error':
      return 'ERROR'
    default:
      return 'UNKNOWN'
  }
}

function formatDate(isoString: string | null): string {
  if (!isoString) return 'Never'
  const date = new Date(isoString)
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

async function handleSetActive(repository: string) {
  try {
    await setActiveProject(repository)
  } catch (err) {
    console.error('Failed to set active project:', err)
  }
}

async function handleReindex(repository: string) {
  if (!confirm(`Reindex project "${repository}"?\n\nThis will re-scan all files and may take several minutes.`)) {
    return
  }

  try {
    await reindexProject(repository)
    alert(`Reindexing started for ${repository}`)
  } catch (err) {
    alert(`Failed to reindex: ${err instanceof Error ? err.message : 'Unknown error'}`)
  }
}

function handleDeleteClick(repository: string) {
  confirmDeleteProject.value = repository
}

async function handleDeleteConfirm() {
  if (!confirmDeleteProject.value) return

  try {
    const result = await deleteProject(confirmDeleteProject.value)
    alert(`Deleted ${result.repository}: ${result.deleted_chunks} chunks, ${result.deleted_nodes} nodes`)
    confirmDeleteProject.value = null
  } catch (err) {
    alert(`Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`)
  }
}

function handleDeleteCancel() {
  confirmDeleteProject.value = null
}
</script>

<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold text-cyan-400">📦 Projects</h1>
        <p class="text-gray-400 mt-1">Manage indexed code repositories</p>
      </div>

      <button
        @click="fetchProjects"
        :disabled="loading"
        class="px-6 py-2 bg-cyan-600 hover:bg-cyan-700 text-white font-mono text-sm uppercase tracking-wider border-2 border-cyan-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
      >
        {{ loading ? '⏳ LOADING...' : '🔄 REFRESH' }}
      </button>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mb-4 bg-red-900/20 border-2 border-red-500 text-red-300 px-4 py-3 font-mono">
      <span class="inline-block w-3 h-3 bg-red-500 rounded-full mr-2 animate-pulse"></span>
      ERROR: {{ error }}
    </div>

    <!-- Active Project Card -->
    <div v-if="activeProject" class="mb-6 bg-cyan-900/20 border-2 border-cyan-500 p-4 shadow-lg shadow-cyan-500/20">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="inline-block w-3 h-3 bg-cyan-400 rounded-full animate-pulse"></span>
          <div>
            <span class="text-xs font-mono text-gray-400 uppercase tracking-wider">Active Project</span>
            <h2 class="text-2xl font-bold text-cyan-400 font-mono">{{ activeProject }}</h2>
          </div>
        </div>
        <div class="text-4xl">🎯</div>
      </div>
    </div>

    <!-- Projects Table -->
    <div class="bg-slate-900 border-2 border-slate-600 overflow-hidden shadow-xl">
      <table class="w-full border-collapse">
        <thead class="bg-slate-800 border-b-2 border-slate-600">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Repository</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Files</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Chunks</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">LOC</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Languages</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Coverage</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Last Indexed</th>
            <th class="px-4 py-3 text-left text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider border-r border-slate-700">Status</th>
            <th class="px-4 py-3 text-center text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y-2 divide-slate-700">
          <tr
            v-for="project in projects"
            :key="project.repository"
            class="hover:bg-slate-800/70 transition-colors border-b-2 border-slate-700"
            :class="{ 'bg-cyan-900/20 border-l-4 border-l-cyan-400': project.repository === activeProject }"
          >
            <!-- Repository -->
            <td class="px-4 py-3 border-r border-slate-700">
              <div class="flex items-center gap-2">
                <span v-if="project.repository === activeProject" class="inline-block w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></span>
                <span class="font-mono font-semibold text-white">{{ project.repository }}</span>
              </div>
            </td>

            <!-- Files -->
            <td class="px-4 py-3 font-mono text-gray-300 border-r border-slate-700">
              {{ formatNumber(project.files_count) }}
            </td>

            <!-- Chunks -->
            <td class="px-4 py-3 font-mono text-gray-300 border-r border-slate-700">
              {{ formatNumber(project.chunks_count) }}
            </td>

            <!-- LOC -->
            <td class="px-4 py-3 font-mono text-gray-300 border-r border-slate-700">
              {{ formatNumber(project.total_loc) }}
            </td>

            <!-- Languages -->
            <td class="px-4 py-3 border-r border-slate-700">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="lang in project.languages.slice(0, 3)"
                  :key="lang"
                  class="px-2 py-0.5 text-xs font-mono bg-slate-700 border border-slate-600 text-gray-300 uppercase"
                >
                  {{ lang }}
                </span>
                <span
                  v-if="project.languages.length > 3"
                  class="px-2 py-0.5 text-xs font-mono bg-slate-700 border border-slate-600 text-gray-400"
                >
                  +{{ project.languages.length - 3 }}
                </span>
              </div>
            </td>

            <!-- Coverage -->
            <td class="px-4 py-3 border-r border-slate-700">
              <div class="flex items-center gap-2">
                <div class="w-16 h-3 bg-slate-800 border border-slate-600 overflow-hidden">
                  <div
                    class="h-full transition-all"
                    :class="{
                      'bg-green-500': project.graph_coverage >= 0.7,
                      'bg-yellow-500': project.graph_coverage >= 0.4 && project.graph_coverage < 0.7,
                      'bg-red-500': project.graph_coverage < 0.4
                    }"
                    :style="{ width: `${project.graph_coverage * 100}%` }"
                  ></div>
                </div>
                <span class="text-xs font-mono text-gray-400 font-bold">{{ Math.round(project.graph_coverage * 100) }}%</span>
              </div>
            </td>

            <!-- Last Indexed -->
            <td class="px-4 py-3 text-xs font-mono text-gray-400 border-r border-slate-700">
              {{ formatDate(project.last_indexed) }}
            </td>

            <!-- Status -->
            <td class="px-4 py-3 border-r border-slate-700">
              <div class="flex items-center gap-2">
                <span :class="getStatusColor(project.status)" class="inline-block w-2 h-2 rounded-full"></span>
                <span :class="getStatusTextColor(project.status)" class="text-xs font-mono font-bold uppercase">
                  {{ getStatusLabel(project.status) }}
                </span>
              </div>
            </td>

            <!-- Actions -->
            <td class="px-4 py-3">
              <div class="flex items-center justify-center gap-1">
                <button
                  v-if="project.repository !== activeProject"
                  @click="handleSetActive(project.repository)"
                  class="px-3 py-1.5 text-xs font-mono font-bold bg-cyan-600 hover:bg-cyan-700 text-white border border-cyan-500 uppercase tracking-wider transition-all shadow-sm"
                  title="Set as active project"
                >
                  ACTIVATE
                </button>
                <button
                  @click="handleReindex(project.repository)"
                  class="px-3 py-1.5 text-xs font-mono font-bold bg-blue-600 hover:bg-blue-700 text-white border border-blue-500 uppercase tracking-wider transition-all shadow-sm"
                  title="Reindex project"
                >
                  REINDEX
                </button>
                <button
                  @click="handleDeleteClick(project.repository)"
                  class="px-3 py-1.5 text-xs font-mono font-bold bg-red-600 hover:bg-red-700 text-white border border-red-500 uppercase tracking-wider transition-all shadow-sm"
                  title="Delete project"
                >
                  DELETE
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty State -->
      <div v-if="!loading && projects.length === 0" class="py-12 text-center text-gray-400">
        <div class="text-6xl mb-4">📦</div>
        <p class="text-lg">No projects indexed yet</p>
        <p class="text-sm mt-2">Use the CLI to index your first project</p>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="confirmDeleteProject"
      class="fixed inset-0 bg-black bg-opacity-80 z-50 flex items-center justify-center p-4"
      @click="handleDeleteCancel"
    >
      <div
        class="bg-slate-900 border-2 border-red-500 shadow-2xl shadow-red-500/30 max-w-md w-full p-6"
        @click.stop
      >
        <div class="flex items-center gap-3 mb-4 border-b-2 border-red-500 pb-4">
          <span class="inline-block w-4 h-4 bg-red-500 rounded-full animate-pulse"></span>
          <h3 class="text-xl font-mono font-bold text-red-400 uppercase tracking-wider">⚠️ DELETE PROJECT</h3>
        </div>
        <p class="text-gray-300 mb-4 font-mono text-sm">
          Confirm deletion of: <strong class="text-white bg-red-900/30 px-2 py-1">{{ confirmDeleteProject }}</strong>
        </p>
        <p class="text-xs font-mono text-gray-400 mb-6 bg-slate-800 border border-slate-700 p-3">
          ⚠️ WARNING: This will permanently delete all code chunks, nodes, and edges. This action cannot be undone.
        </p>
        <div class="flex gap-2 justify-end">
          <button
            @click="handleDeleteCancel"
            class="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white border border-slate-600 font-mono text-sm uppercase tracking-wider transition-all"
          >
            CANCEL
          </button>
          <button
            @click="handleDeleteConfirm"
            class="px-6 py-2 bg-red-600 hover:bg-red-700 text-white border-2 border-red-500 font-mono text-sm uppercase tracking-wider transition-all shadow-lg"
          >
            CONFIRM DELETE
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
