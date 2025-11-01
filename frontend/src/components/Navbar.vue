<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const links = [
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'Search', path: '/search' },
  { name: 'Graph', path: '/graph' },
  { name: 'Logs', path: '/logs' }
]

const isActive = (path: string) => route.path === path
</script>

<template>
  <nav class="nav-bar">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex space-x-8">
          <div class="flex-shrink-0 flex items-center">
            <h1 class="text-xl text-heading">MnemoLite</h1>
          </div>

          <div class="flex space-x-4 items-center">
            <router-link
              v-for="link in links"
              :key="link.path"
              :to="link.path"
              :class="isActive(link.path) ? 'nav-link-active' : 'nav-link'"
            >
              {{ link.name }}
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>
