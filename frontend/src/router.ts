import { createRouter, createWebHistory } from 'vue-router'

// NB: l'ordre des groupes dans la navbar suit l'ordre de déclaration des routes
// (Data, Cognitive, Ops, Tools). Insérer une route en tête réordonne la nav.
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/pages/Dashboard.vue'),
      meta: { navLabel: 'Dashboard', navGroup: 'Data' }
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/pages/Search.vue'),
      meta: { navLabel: 'Search', navGroup: 'Data' }
    },
    {
      path: '/memories',
      name: 'memories',
      component: () => import('@/pages/Memories.vue'),
      meta: { navLabel: 'Memories', navGroup: 'Data' }
    },
    {
      path: '/brain',
      name: 'brain',
      component: () => import('@/pages/Brain.vue'),
      meta: { navLabel: 'Brain', navGroup: 'Cognitive' }
    },
    {
      path: '/monitoring',
      name: 'monitoring',
      component: () => import('@/pages/Monitoring.vue'),
      meta: { navLabel: 'Monitoring', navGroup: 'Ops' }
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('@/pages/Projects.vue'),
      meta: { navLabel: 'Projects', navGroup: 'Ops' }
    },
    {
      path: '/graph',
      name: 'graph',
      component: () => import('@/pages/Graph.vue'),
      meta: { navLabel: 'Graph', navGroup: 'Tools' }
    },
    {
      // EPIC-74 : URL inconnue ou ancienne page supprimée -> redirection propre
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard'
    }
  ]
})

export default router
