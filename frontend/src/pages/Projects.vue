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

function getStatusIcon(status: string): string {
  switch (status) {
    case 'healthy':
      return '✅'
    case 'needs_reindex':
      return '⏰'
    case 'poor_coverage':
      return '⚠️'
    case 'error':
      return '❌'
    default:
      return '❓'
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
        class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {{ loading ? '⏳ Loading...' : '🔄 Refresh' }}
      </button>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mb-4 bg-red-900/50 border border-red-600 text-red-300 px-4 py-3 rounded-lg">
      ⚠️ {{ error }}
    </div>

    <!-- Active Project Card -->
    <div v-if="activeProject" class="mb-6 bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-600 rounded-lg p-4">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-sm text-gray-400">Active Project</span>
          <h2 class="text-2xl font-bold text-cyan-400">{{ activeProject }}</h2>
        </div>
        <div class="text-4xl">🎯</div>
      </div>
    </div>

    <!-- Projects Table -->
    <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
      <table class="w-full">
        <thead class="bg-slate-700">
          <tr>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Repository</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Files</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Chunks</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">LOC</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Languages</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Coverage</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Last Indexed</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-gray-300">Status</th>
            <th class="px-4 py-3 text-center text-sm font-semibold text-gray-300">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700">
          <tr
            v-for="project in projects"
            :key="project.repository"
            class="hover:bg-slate-700/50 transition-colors"
            :class="{ 'bg-cyan-900/20': project.repository === activeProject }"
          >
            <!-- Repository -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span v-if="project.repository === activeProject" class="text-cyan-400">🎯</span>
                <span class="font-medium text-white">{{ project.repository }}</span>
              </div>
            </td>

            <!-- Files -->
            <td class="px-4 py-3 text-gray-300">
              {{ formatNumber(project.files_count) }}
            </td>

            <!-- Chunks -->
            <td class="px-4 py-3 text-gray-300">
              {{ formatNumber(project.chunks_count) }}
            </td>

            <!-- LOC -->
            <td class="px-4 py-3 text-gray-300">
              {{ formatNumber(project.total_loc) }}
            </td>

            <!-- Languages -->
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="lang in project.languages.slice(0, 3)"
                  :key="lang"
                  class="px-2 py-0.5 text-xs rounded bg-slate-600 text-gray-300"
                >
                  {{ lang }}
                </span>
                <span
                  v-if="project.languages.length > 3"
                  class="px-2 py-0.5 text-xs rounded bg-slate-600 text-gray-400"
                >
                  +{{ project.languages.length - 3 }}
                </span>
              </div>
            </td>

            <!-- Coverage -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <div class="w-12 h-2 bg-slate-700 rounded-full overflow-hidden">
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
                <span class="text-sm text-gray-400">{{ Math.round(project.graph_coverage * 100) }}%</span>
              </div>
            </td>

            <!-- Last Indexed -->
            <td class="px-4 py-3 text-sm text-gray-400">
              {{ formatDate(project.last_indexed) }}
            </td>

            <!-- Status -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-1">
                <span>{{ getStatusIcon(project.status) }}</span>
                <span :class="getStatusColor(project.status)" class="text-sm">
                  {{ project.status }}
                </span>
              </div>
            </td>

            <!-- Actions -->
            <td class="px-4 py-3">
              <div class="flex items-center justify-center gap-2">
                <button
                  v-if="project.repository !== activeProject"
                  @click="handleSetActive(project.repository)"
                  class="px-3 py-1 text-sm bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
                  title="Set as active project"
                >
                  Set Active
                </button>
                <button
                  @click="handleReindex(project.repository)"
                  class="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
                  title="Reindex project"
                >
                  Reindex
                </button>
                <button
                  @click="handleDeleteClick(project.repository)"
                  class="px-3 py-1 text-sm bg-red-600 hover:bg-red-500 text-white rounded transition-colors"
                  title="Delete project"
                >
                  Delete
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
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      @click="handleDeleteCancel"
    >
      <div
        class="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-6"
        @click.stop
      >
        <h3 class="text-xl font-bold text-red-400 mb-4">⚠️ Delete Project</h3>
        <p class="text-gray-300 mb-4">
          Are you sure you want to delete <strong class="text-white">{{ confirmDeleteProject }}</strong>?
        </p>
        <p class="text-sm text-gray-400 mb-6">
          This will permanently delete all code chunks, nodes, and edges. This action cannot be undone.
        </p>
        <div class="flex gap-3 justify-end">
          <button
            @click="handleDeleteCancel"
            class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors"
          >
            Cancel
          </button>
          <button
            @click="handleDeleteConfirm"
            class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
