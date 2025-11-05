/**
 * EPIC-27: Projects Management Composable
 * Centralized state and API calls for projects management
 */
import { ref, computed } from 'vue'
import type {
  Project,
  ProjectsResponse,
  ActiveProjectResponse,
  SetActiveProjectResponse,
  ReindexProjectResponse,
  DeleteProjectResponse
} from '@/types/projects'

const API_BASE = 'http://localhost:8001/api/v1'

// Global state for active project
const activeProject = ref<string>('default')
const projects = ref<Project[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

export function useProjects() {
  // Load active project from localStorage on init
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('activeProject')
    if (stored) {
      activeProject.value = stored
    }
  }

  /**
   * Fetch list of all projects
   */
  async function fetchProjects(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects`)

      if (!response.ok) {
        throw new Error(`Failed to fetch projects: ${response.statusText}`)
      }

      const data: ProjectsResponse = await response.json()
      projects.value = data.projects
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch projects:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Get currently active project
   */
  async function fetchActiveProject(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/projects/active`)

      if (!response.ok) {
        throw new Error(`Failed to fetch active project: ${response.statusText}`)
      }

      const data: ActiveProjectResponse = await response.json()
      activeProject.value = data.repository

      // Persist to localStorage
      localStorage.setItem('activeProject', data.repository)
    } catch (err) {
      console.error('Failed to fetch active project:', err)
    }
  }

  /**
   * Switch active project
   */
  async function setActiveProject(repository: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects/active`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ repository })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to set active project')
      }

      const data: SetActiveProjectResponse = await response.json()
      activeProject.value = data.repository

      // Persist to localStorage
      localStorage.setItem('activeProject', data.repository)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Trigger project reindexing
   */
  async function reindexProject(repository: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects/${repository}/reindex`, {
        method: 'POST'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to reindex project')
      }

      const data: ReindexProjectResponse = await response.json()

      // Refresh projects list to show new status
      await fetchProjects()

      return data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete project and all its data
   */
  async function deleteProject(repository: string): Promise<DeleteProjectResponse> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/projects/${repository}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to delete project')
      }

      const data: DeleteProjectResponse = await response.json()

      // Refresh projects list
      await fetchProjects()

      // If deleted project was active, switch to default
      if (activeProject.value === repository) {
        if (projects.value.length > 0) {
          await setActiveProject(projects.value[0].repository)
        } else {
          activeProject.value = 'default'
        }
      }

      return data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Computed
  const activeProjectData = computed(() => {
    return projects.value.find(p => p.repository === activeProject.value) || null
  })

  const projectsCount = computed(() => projects.value.length)

  const healthyProjects = computed(() => {
    return projects.value.filter(p => p.status === 'healthy').length
  })

  return {
    // State
    projects,
    activeProject,
    loading,
    error,

    // Computed
    activeProjectData,
    projectsCount,
    healthyProjects,

    // Methods
    fetchProjects,
    fetchActiveProject,
    setActiveProject,
    reindexProject,
    deleteProject
  }
}
