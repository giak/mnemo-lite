import { createRouter, createWebHistory } from 'vue-router'

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
      component: () => import('@/pages/Dashboard.vue')
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/pages/Search.vue')
    },
    {
      path: '/graph',
      name: 'graph',
      component: () => import('@/pages/Graph.vue')
    },
    {
      path: '/orgchart',
      name: 'orgchart',
      component: () => import('@/pages/Orgchart.vue')
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/pages/Logs.vue')
    },
    {
      path: '/memories',
      name: 'memories',
      component: () => import('@/pages/Memories.vue')
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('@/pages/Projects.vue')
    },
    {
      path: '/expanse',
      name: 'expanse',
      component: () => import('@/pages/Expanse.vue')
    },
    {
      path: '/monitoring',
      name: 'monitoring',
      component: () => import('@/pages/Monitoring.vue')
    },
    {
      path: '/brain',
      name: 'brain',
      component: () => import('@/pages/Brain.vue')
    },
    {
      path: '/expanse-memory',
      name: 'expanse-memory',
      component: () => import('@/pages/ExpanseMemory.vue')
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: () => import('@/pages/Alerts.vue')
    },
    {
      path: '/search-analytics',
      name: 'search-analytics',
      component: () => import('@/pages/SearchAnalytics.vue')
    }
  ]
})

export default router
