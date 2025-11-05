<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjects } from '@/composables/useProjects'

const route = useRoute()

// Add projects state
const {
  projects,
  activeProject,
  fetchProjects,
  setActiveProject
} = useProjects()

// Fetch projects on mount
onMounted(() => {
  fetchProjects()
})

// Project switcher state
const projectMenuOpen = ref(false)

const toggleProjectMenu = () => {
  projectMenuOpen.value = !projectMenuOpen.value
}

const closeProjectMenu = () => {
  projectMenuOpen.value = false
}

async function handleProjectSwitch(repository: string) {
  await setActiveProject(repository)
  closeProjectMenu()
}

interface MenuItem {
  name: string
  path?: string
  children?: MenuItem[]
}

const links: MenuItem[] = [
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'Search', path: '/search' },
  { name: 'Memories', path: '/memories' },
  {
    name: 'Graph',
    children: [
      { name: 'Code Graph', path: '/graph' },
      { name: 'Organigramme', path: '/orgchart' }
    ]
  },
  { name: 'Logs', path: '/logs' }
]

const openSubmenu = ref<string | null>(null)

const isActive = (path: string) => route.path === path

const toggleSubmenu = (name: string) => {
  openSubmenu.value = openSubmenu.value === name ? null : name
}

const closeSubmenu = () => {
  openSubmenu.value = null
}

const isSubmenuActive = (children?: MenuItem[]) => {
  if (!children) return false
  return children.some(child => child.path && isActive(child.path))
}
</script>

<template>
  <nav class="nav-bar">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex space-x-8">
          <div class="flex-shrink-0 flex items-center">
            <h1 class="text-xl text-heading">MnemoLite</h1>
          </div>

          <!-- Project Switcher -->
          <div class="relative ml-4">
            <button
              @click="toggleProjectMenu"
              class="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
            >
              <span class="text-cyan-400">📦</span>
              <span class="text-sm text-gray-300">{{ activeProject }}</span>
              <svg
                class="w-4 h-4 text-gray-400 transition-transform"
                :class="{ 'rotate-180': projectMenuOpen }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <!-- Dropdown -->
            <div
              v-if="projectMenuOpen"
              @click="closeProjectMenu"
              class="absolute left-0 mt-2 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto"
            >
              <div class="p-2">
                <div class="px-3 py-2 text-xs font-semibold text-gray-400 uppercase">
                  Switch Project
                </div>
                <router-link
                  v-for="project in projects"
                  :key="project.repository"
                  :to="`/projects`"
                  @click="handleProjectSwitch(project.repository)"
                  class="flex items-center justify-between px-3 py-2 text-sm hover:bg-slate-700 transition-colors rounded"
                  :class="{ 'bg-slate-700 text-cyan-400': project.repository === activeProject }"
                >
                  <span class="flex items-center gap-2">
                    <span v-if="project.repository === activeProject">🎯</span>
                    <span>{{ project.repository }}</span>
                  </span>
                  <span class="text-xs text-gray-500">{{ project.chunks_count }} chunks</span>
                </router-link>

                <div v-if="projects.length === 0" class="px-3 py-4 text-center text-sm text-gray-500">
                  No projects indexed
                </div>

                <div class="border-t border-slate-700 mt-2 pt-2">
                  <router-link
                    to="/projects"
                    class="flex items-center gap-2 px-3 py-2 text-sm text-cyan-400 hover:bg-slate-700 transition-colors rounded"
                  >
                    <span>⚙️</span>
                    <span>Manage Projects</span>
                  </router-link>
                </div>
              </div>
            </div>
          </div>

          <div class="flex space-x-4 items-center">
            <!-- Regular links without children -->
            <template v-for="link in links" :key="link.name">
              <router-link
                v-if="!link.children"
                :to="link.path!"
                :class="isActive(link.path!) ? 'nav-link-active' : 'nav-link'"
              >
                {{ link.name }}
              </router-link>

              <!-- Links with submenu -->
              <div v-else class="relative">
                <button
                  @click="toggleSubmenu(link.name)"
                  :class="[
                    'flex items-center gap-1',
                    isSubmenuActive(link.children) ? 'nav-link-active' : 'nav-link'
                  ]"
                >
                  {{ link.name }}
                  <svg
                    class="w-4 h-4 transition-transform"
                    :class="{ 'rotate-180': openSubmenu === link.name }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                <!-- Submenu dropdown -->
                <div
                  v-if="openSubmenu === link.name"
                  @click="closeSubmenu"
                  class="absolute left-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-50"
                >
                  <router-link
                    v-for="child in link.children"
                    :key="child.path"
                    :to="child.path!"
                    :class="[
                      'block px-4 py-2 text-sm hover:bg-slate-700 transition-colors',
                      isActive(child.path!) ? 'text-cyan-400 bg-slate-700' : 'text-gray-300'
                    ]"
                  >
                    {{ child.name }}
                  </router-link>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>
