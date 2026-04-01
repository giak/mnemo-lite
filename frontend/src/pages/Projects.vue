<script setup lang="ts">
/**
 * EPIC-28 Story 28.2: Projects Management Page — SCADA Style
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
const actionLoading = ref<string | null>(null)

onMounted(() => {
  fetchProjects()
})

function getStatusLed(status: string): string {
  switch (status) {
    case 'healthy': return 'scada-led-green'
    case 'needs_reindex': return 'scada-led-yellow'
    case 'poor_coverage': return 'scada-led-orange'
    case 'error': return 'scada-led-red'
    default: return 'scada-led-gray'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'healthy': return 'HEALTHY'
    case 'needs_reindex': return 'REINDEX'
    case 'poor_coverage': return 'LOW COV'
    case 'error': return 'ERROR'
    default: return 'UNKNOWN'
  }
}

function formatDate(isoString: string | null): string {
  if (!isoString) return 'NEVER'
  const date = new Date(isoString)
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).toUpperCase()
}

function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

async function handleSetActive(repository: string) {
  try {
    actionLoading.value = `activate:${repository}`
    await setActiveProject(repository)
  } catch (err) {
    console.error('Failed to set active project:', err)
  } finally {
    actionLoading.value = null
  }
}

async function handleReindex(repository: string) {
  if (!confirm(`Reindex project "${repository}"?\n\nThis will re-scan all files and may take several minutes.`)) {
    return
  }

  try {
    actionLoading.value = `reindex:${repository}`
    await reindexProject(repository)
  } catch (err) {
    alert(`Failed to reindex: ${err instanceof Error ? err.message : 'Unknown error'}`)
  } finally {
    actionLoading.value = null
  }
}

function handleDeleteClick(repository: string) {
  confirmDeleteProject.value = repository
}

async function handleDeleteConfirm() {
  if (!confirmDeleteProject.value) return

  try {
    actionLoading.value = `delete:${confirmDeleteProject.value}`
    const result = await deleteProject(confirmDeleteProject.value)
    alert(`Deleted ${result.repository}: ${result.deleted_chunks} chunks, ${result.deleted_nodes} nodes`)
    confirmDeleteProject.value = null
  } catch (err) {
    alert(`Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`)
  } finally {
    actionLoading.value = null
  }
}

function handleDeleteCancel() {
  confirmDeleteProject.value = null
}

function isActionLoading(action: string, repository: string): boolean {
  return actionLoading.value === `${action}:${repository}`
}
</script>

<template>
  <div class="bg-slate-950">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header SCADA -->
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
          <span class="scada-led scada-led-cyan"></span>
          <div>
            <h1 class="text-3xl font-bold font-mono text-cyan-400 uppercase tracking-wider">Projects</h1>
            <p class="mt-2 text-sm text-gray-400 font-mono uppercase tracking-wide">
              Manage Indexed Code Repositories
            </p>
          </div>
        </div>
        <div class="text-right">
          <button
            @click="fetchProjects"
            :disabled="loading"
            class="scada-btn scada-btn-primary"
          >
            {{ loading ? 'REFRESHING...' : 'REFRESH' }}
          </button>
          <p class="mt-2 text-xs text-gray-500 font-mono uppercase">
            {{ projects.length }} PROJECT{{ projects.length !== 1 ? 'S' : '' }}
          </p>
        </div>
      </div>

      <!-- Error Banner -->
      <div v-if="error" class="mb-6 bg-red-950/50 border-l-4 border-red-500 p-4">
        <div class="flex">
          <div class="flex-shrink-0">
            <span class="scada-led scada-led-red"></span>
          </div>
          <div class="ml-3">
            <h3 class="text-sm scada-status-danger">Failed to Load Projects</h3>
            <p class="mt-1 text-sm text-red-400 font-mono">{{ error }}</p>
          </div>
        </div>
      </div>

      <!-- Active Project Card -->
      <div v-if="activeProject" class="mb-6 scada-panel scada-panel-info">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="scada-led scada-led-cyan animate-pulse"></span>
            <div>
              <span class="scada-label">Active Project</span>
              <h2 class="text-2xl font-bold text-cyan-400 font-mono">{{ activeProject }}</h2>
            </div>
          </div>
          <span class="scada-badge scada-badge-cyan">ACTIVE</span>
        </div>
      </div>

      <!-- Projects Table -->
      <div class="scada-panel">
        <div class="overflow-x-auto">
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
                    <span v-if="project.repository === activeProject" class="scada-led scada-led-cyan animate-pulse"></span>
                    <span class="font-mono font-semibold text-white">{{ project.repository }}</span>
                  </div>
                </td>

                <!-- Files -->
                <td class="px-4 py-3 scada-data border-r border-slate-700">
                  {{ formatNumber(project.files_count) }}
                </td>

                <!-- Chunks -->
                <td class="px-4 py-3 scada-data border-r border-slate-700">
                  {{ formatNumber(project.chunks_count) }}
                </td>

                <!-- LOC -->
                <td class="px-4 py-3 scada-data border-r border-slate-700">
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
                    <span :class="getStatusLed(project.status)" class="scada-led"></span>
                    <span class="text-xs font-mono font-bold uppercase text-gray-300">
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
                      :disabled="isActionLoading('activate', project.repository)"
                      class="scada-btn scada-btn-primary text-xs"
                      title="Set as active project"
                    >
                      {{ isActionLoading('activate', project.repository) ? '...' : 'ACTIVATE' }}
                    </button>
                    <button
                      @click="handleReindex(project.repository)"
                      :disabled="isActionLoading('reindex', project.repository)"
                      class="scada-btn scada-btn-ghost text-xs"
                      title="Reindex project"
                    >
                      {{ isActionLoading('reindex', project.repository) ? '...' : 'REINDEX' }}
                    </button>
                    <button
                      @click="handleDeleteClick(project.repository)"
                      :disabled="isActionLoading('delete', project.repository)"
                      class="scada-btn scada-btn-danger text-xs"
                      title="Delete project"
                    >
                      {{ isActionLoading('delete', project.repository) ? '...' : 'DELETE' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Empty State -->
          <div v-if="!loading && projects.length === 0" class="py-12 text-center">
            <span class="scada-led scada-led-gray"></span>
            <p class="text-lg text-gray-400 font-mono mt-4">NO PROJECTS INDEXED</p>
            <p class="text-sm text-gray-500 font-mono mt-2">Use the CLI to index your first project</p>
          </div>
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
            <span class="scada-led scada-led-red animate-pulse"></span>
            <h3 class="text-xl font-mono font-bold text-red-400 uppercase tracking-wider">Delete Project</h3>
          </div>
          <p class="text-gray-300 mb-4 font-mono text-sm">
            Confirm deletion of: <strong class="text-white bg-red-900/30 px-2 py-1">{{ confirmDeleteProject }}</strong>
          </p>
          <p class="text-xs font-mono text-gray-400 mb-6 bg-slate-800 border border-slate-700 p-3">
            This will permanently delete all code chunks, nodes, and edges. This action cannot be undone.
          </p>
          <div class="flex gap-2 justify-end">
            <button
              @click="handleDeleteCancel"
              class="scada-btn scada-btn-ghost"
            >
              CANCEL
            </button>
            <button
              @click="handleDeleteConfirm"
              :disabled="isActionLoading('delete', confirmDeleteProject)"
              class="scada-btn scada-btn-danger"
            >
              {{ isActionLoading('delete', confirmDeleteProject) ? 'DELETING...' : 'CONFIRM DELETE' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
