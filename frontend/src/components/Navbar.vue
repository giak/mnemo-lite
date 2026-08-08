<script setup lang="ts">
/**
 * EPIC-27: Navbar Component - SCADA Industrial Style
 * EPIC-74 : navigation générée depuis le router (meta.navLabel / meta.navGroup).
 * Toute route portant meta.navLabel apparaît automatiquement — plus de liens codés en dur.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

interface NavItem {
  name: string
  path: string
}

interface NavGroup {
  group: string
  items: NavItem[]
}

const navGroups = computed<NavGroup[]>(() => {
  const groups = new Map<string, NavItem[]>()
  for (const r of router.options.routes) {
    const label = r.meta?.navLabel as string | undefined
    if (!label) continue
    const group = (r.meta?.navGroup as string | undefined) || 'Other'
    const items = groups.get(group) || []
    items.push({ name: label, path: r.path })
    groups.set(group, items)
  }
  return Array.from(groups.entries()).map(([group, items]) => ({ group, items }))
})

const isActive = (path: string) => route.path === path
</script>

<template>
  <nav class="nav-bar">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex space-x-8">
          <!-- Logo avec LED SCADA -->
          <div class="flex-shrink-0 flex items-center gap-3">
            <span class="scada-led scada-led-cyan" />
            <h1 class="text-xl font-bold font-mono text-cyan-400 uppercase tracking-wider">
              MnemoLite
            </h1>
          </div>

          <!-- Navigation Links (générés depuis le router) -->
          <div class="flex items-center">
            <template
              v-for="(group, gi) in navGroups"
              :key="group.group"
            >
              <!-- Group separator -->
              <div
                v-if="gi > 0"
                class="w-px h-6 bg-slate-700 mx-3"
              />

              <router-link
                v-for="link in group.items"
                :key="link.name"
                :to="link.path"
                :class="[
                  isActive(link.path) ? 'nav-link-active' : 'nav-link',
                  'font-mono text-xs tracking-wide flex items-center gap-1.5 px-2 py-1 rounded transition-colors'
                ]"
              >
                {{ link.name }}
              </router-link>
            </template>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>
