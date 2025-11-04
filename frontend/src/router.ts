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
    }
  ]
})

export default router
