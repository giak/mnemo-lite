<script setup lang="ts">
/**
 * EPIC-27: Navbar Component - SCADA Industrial Style
 * Navigation with LED indicator, monospace UPPERCASE labels, and dropdown menu
 */
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

interface MenuItem {
  name: string
  path?: string
  children?: MenuItem[]
}

const links: MenuItem[] = [
  { name: 'DASHBOARD', path: '/dashboard' },
  { name: 'SEARCH', path: '/search' },
  { name: 'MEMORIES', path: '/memories' },
  { name: 'PROJECTS', path: '/projects' },
  {
    name: 'GRAPH',
    children: [
      { name: 'CODE GRAPH', path: '/graph' },
      { name: 'ORGANIGRAMME', path: '/orgchart' }
    ]
  },
  { name: 'LOGS', path: '/logs' }
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
          <!-- Logo avec LED SCADA -->
          <div class="flex-shrink-0 flex items-center gap-3">
            <span class="scada-led scada-led-cyan"></span>
            <h1 class="text-xl font-bold font-mono text-cyan-400 uppercase tracking-wider">
              MnemoLite
            </h1>
          </div>

          <!-- Navigation Links avec style industriel -->
          <div class="flex space-x-4 items-center">
            <template v-for="link in links" :key="link.name">
              <!-- Regular links without children -->
              <router-link
                v-if="!link.children"
                :to="link.path!"
                :class="[
                  isActive(link.path!) ? 'nav-link-active' : 'nav-link',
                  'font-mono text-xs tracking-wide'
                ]"
              >
                {{ link.name }}
              </router-link>

              <!-- Links with submenu -->
              <div v-else class="relative">
                <button
                  @click="toggleSubmenu(link.name)"
                  :class="[
                    'flex items-center gap-1 font-mono text-xs tracking-wide',
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

                <!-- Submenu dropdown avec border industriel -->
                <div
                  v-if="openSubmenu === link.name"
                  @click="closeSubmenu"
                  class="absolute left-0 mt-2 w-48 bg-slate-800 border-2 border-slate-600 rounded shadow-lg z-50"
                >
                  <router-link
                    v-for="child in link.children"
                    :key="child.path"
                    :to="child.path!"
                    :class="[
                      'block px-4 py-2 text-xs font-mono tracking-wide hover:bg-slate-700 transition-colors border-b border-slate-700 last:border-b-0',
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
