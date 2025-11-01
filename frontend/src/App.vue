<script setup lang="ts">
import Navbar from '@/components/Navbar.vue'
</script>

<template>
  <div id="app" class="min-h-screen bg-slate-950">
    <Navbar />
    <main>
      <router-view />
    </main>
  </div>
</template>
