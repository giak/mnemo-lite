<script setup lang="ts">
import Navbar from '@/components/Navbar.vue'
</script>

<template>
  <div class="h-screen bg-slate-950 overflow-hidden flex flex-col">
    <!-- Navbar -->
    <Navbar class="flex-shrink-0" />

    <!-- Main Content Area -->
    <main class="flex-1 min-h-0 overflow-y-auto">
      <slot />
    </main>
  </div>
</template>
