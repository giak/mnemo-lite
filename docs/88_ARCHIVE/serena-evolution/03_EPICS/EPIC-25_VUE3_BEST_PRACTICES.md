# EPIC-25: Vue.js 3 Best Practices - Composables & Separation of Concerns

**Date**: 2025-11-01
**Purpose**: Guide des bonnes pratiques Vue.js 3 pour MnemoLite UI/UX
**Principe**: Séparer le traitement (composables) de l'affichage (components)

---

## 🎯 Principe Fondamental

### Composition API Pattern

```
┌─────────────────────────────────────────┐
│         PRESENTATION LAYER              │
│  (Components - Dumb/Presentational)     │
│  - Vue template                         │
│  - Props/emits                          │
│  - Visual logic only                    │
└──────────────────┬──────────────────────┘
                   │ uses
┌──────────────────▼──────────────────────┐
│          BUSINESS LOGIC LAYER           │
│     (Composables - Smart/Container)     │
│  - Data fetching                        │
│  - State management                     │
│  - Business rules                       │
│  - Side effects (API calls, SSE, etc.)  │
└─────────────────────────────────────────┘
```

**Avantages** :
- ✅ Testabilité (logic testable sans DOM)
- ✅ Réutilisabilité (1 composable → N components)
- ✅ Lisibilité (component = simple, clear intent)
- ✅ Maintenabilité (change logic sans toucher UI)

---

## 📚 Pattern: Composables

### Structure Standard

```typescript
// composables/useXyz.ts
import { ref, computed, onMounted } from 'vue'

export function useXyz() {
  // 1. State (reactive)
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // 2. Computed (derived state)
  const hasData = computed(() => data.value !== null)

  // 3. Methods (actions)
  async function fetchData() {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/xyz')
      data.value = await response.json()
    } catch (e) {
      error.value = e
    } finally {
      loading.value = false
    }
  }

  // 4. Lifecycle hooks (if needed)
  onMounted(() => {
    fetchData()
  })

  // 5. Return API (what component needs)
  return {
    // State
    data,
    loading,
    error,
    // Computed
    hasData,
    // Methods
    fetchData,
  }
}
```

### Naming Convention

```
useXyz          # Generic pattern
useFeature      # Feature-based (useSearch, useDashboard)
useResource     # Resource-based (useEmbeddings, useLogs)
useApi          # API-based (useApiClient, useSSE)
```

---

## 🏗️ Architecture MnemoLite

### Folder Structure

```
frontend/src/
├── composables/              # 🧠 BUSINESS LOGIC
│   ├── useDashboard.ts       # Dashboard data & logic
│   ├── useEmbeddings.ts      # Embeddings stats
│   ├── useHealth.ts          # Services health check
│   ├── useSearch.ts          # Search functionality
│   ├── useGraph.ts           # Graph data & controls
│   ├── useLogs.ts            # Logs fetching & filtering
│   └── useApi.ts             # API client wrapper
│
├── components/               # 🎨 PRESENTATION LAYER
│   ├── Navbar.vue            # Simple, no logic
│   ├── EmbeddingCard.vue     # Props-based, dumb
│   ├── HealthBadge.vue       # Props-based, dumb
│   ├── SearchResults.vue     # Props-based, dumb
│   └── LogsTable.vue         # Props-based, dumb
│
├── pages/                    # 📄 SMART COMPONENTS
│   ├── Dashboard.vue         # Uses composables
│   ├── Search.vue            # Uses composables
│   ├── Graph.vue             # Uses composables
│   └── Logs.vue              # Uses composables
│
└── utils/
    └── api.ts                # Shared API utils
```

**Règle d'or** :
- **`composables/`** = Toute la logique métier
- **`components/`** = Composants réutilisables, props-based, NO logic
- **`pages/`** = Orchestration (use composables + components)

---

## 💡 Exemples Concrets pour EPIC-25

### 1. Dashboard Page (Smart Component)

```vue
<!-- pages/Dashboard.vue -->
<script setup lang="ts">
import { useDashboard } from '@/composables/useDashboard'
import { useEmbeddings } from '@/composables/useEmbeddings'
import { useHealth } from '@/composables/useHealth'

import EmbeddingCard from '@/components/EmbeddingCard.vue'
import HealthBadge from '@/components/HealthBadge.vue'

// Use composables (business logic)
const { refresh, loading } = useDashboard()
const { textEmbeddings, codeEmbeddings } = useEmbeddings()
const { services, refreshHealth } = useHealth()

// Component orchestrates composables + UI
const handleRefresh = async () => {
  await Promise.all([refresh(), refreshHealth()])
}
</script>

<template>
  <div class="dashboard">
    <header class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">Dashboard</h1>
      <button
        @click="handleRefresh"
        :disabled="loading"
        class="btn-primary"
      >
        Refresh
      </button>
    </header>

    <!-- Embeddings Cards (dumb components) -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <EmbeddingCard
        title="TEXT Embeddings"
        :model="textEmbeddings.model"
        :count="textEmbeddings.count"
        :lastIndexed="textEmbeddings.lastIndexed"
      />
      <EmbeddingCard
        title="CODE Embeddings"
        :model="codeEmbeddings.model"
        :count="codeEmbeddings.count"
        :lastIndexed="codeEmbeddings.lastIndexed"
      />
    </div>

    <!-- Services Health (dumb components) -->
    <div class="grid grid-cols-3 gap-4">
      <HealthBadge
        v-for="service in services"
        :key="service.name"
        :name="service.name"
        :status="service.status"
      />
    </div>
  </div>
</template>
```

**Analyse** :
- ✅ Page = orchestration (smart)
- ✅ 3 composables = logic séparée
- ✅ Components = dumb, props-based
- ✅ Clear, testable, maintainable

---

### 2. useDashboard Composable (Business Logic)

```typescript
// composables/useDashboard.ts
import { ref } from 'vue'

export function useDashboard() {
  const loading = ref(false)
  const lastRefresh = ref<Date | null>(null)

  async function refresh() {
    loading.value = true
    try {
      // Trigger all dashboard data refresh
      // (autres composables gèrent leur propre state)
      lastRefresh.value = new Date()
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    lastRefresh,
    refresh,
  }
}
```

---

### 3. useEmbeddings Composable (Business Logic)

```typescript
// composables/useEmbeddings.ts
import { ref, onMounted } from 'vue'
import { api } from '@/utils/api'

interface EmbeddingStats {
  model: string
  count: number
  lastIndexed: string
}

export function useEmbeddings() {
  const textEmbeddings = ref<EmbeddingStats>({
    model: '',
    count: 0,
    lastIndexed: '',
  })

  const codeEmbeddings = ref<EmbeddingStats>({
    model: '',
    count: 0,
    lastIndexed: '',
  })

  const loading = ref(false)
  const error = ref<Error | null>(null)

  async function fetchEmbeddings() {
    loading.value = true
    error.value = null

    try {
      // Parallel fetch (faster)
      const [textData, codeData] = await Promise.all([
        api.get('/api/v1/dashboard/embeddings/text'),
        api.get('/api/v1/dashboard/embeddings/code'),
      ])

      textEmbeddings.value = textData
      codeEmbeddings.value = codeData
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  // Auto-fetch on mount
  onMounted(() => {
    fetchEmbeddings()
  })

  return {
    textEmbeddings,
    codeEmbeddings,
    loading,
    error,
    fetchEmbeddings,
  }
}
```

**Analyse** :
- ✅ Toute la logique fetch/state
- ✅ Error handling
- ✅ Auto-fetch onMounted
- ✅ Testable sans component
- ✅ Réutilisable (plusieurs pages peuvent l'utiliser)

---

### 4. useHealth Composable (Business Logic)

```typescript
// composables/useHealth.ts
import { ref, computed } from 'vue'
import { api } from '@/utils/api'

interface ServiceStatus {
  name: string
  status: 'healthy' | 'unhealthy' | 'unknown'
  message?: string
}

export function useHealth() {
  const services = ref<ServiceStatus[]>([
    { name: 'API', status: 'unknown' },
    { name: 'PostgreSQL', status: 'unknown' },
    { name: 'Redis', status: 'unknown' },
  ])

  const loading = ref(false)

  const allHealthy = computed(() =>
    services.value.every(s => s.status === 'healthy')
  )

  async function refreshHealth() {
    loading.value = true

    try {
      const response = await api.get('/api/v1/health')

      services.value = [
        {
          name: 'API',
          status: response.api ? 'healthy' : 'unhealthy'
        },
        {
          name: 'PostgreSQL',
          status: response.database ? 'healthy' : 'unhealthy'
        },
        {
          name: 'Redis',
          status: response.redis ? 'healthy' : 'unhealthy'
        },
      ]
    } catch (e) {
      // Mark all as unhealthy on error
      services.value = services.value.map(s => ({
        ...s,
        status: 'unhealthy',
        message: 'Health check failed',
      }))
    } finally {
      loading.value = false
    }
  }

  return {
    services,
    loading,
    allHealthy,
    refreshHealth,
  }
}
```

---

### 5. EmbeddingCard Component (Dumb/Presentational)

```vue
<!-- components/EmbeddingCard.vue -->
<script setup lang="ts">
// Props only, NO business logic
defineProps<{
  title: string
  model: string
  count: number
  lastIndexed: string
}>()
</script>

<template>
  <div class="card bg-white p-6 rounded-lg shadow">
    <h3 class="text-lg font-semibold mb-4">{{ title }}</h3>

    <div class="space-y-2">
      <div class="flex justify-between">
        <span class="text-gray-600">Model:</span>
        <span class="font-mono text-sm">{{ model }}</span>
      </div>

      <div class="flex justify-between">
        <span class="text-gray-600">Count:</span>
        <span class="font-bold text-blue-600">{{ count.toLocaleString() }}</span>
      </div>

      <div class="flex justify-between">
        <span class="text-gray-600">Last Indexed:</span>
        <span class="text-sm">{{ lastIndexed }}</span>
      </div>
    </div>
  </div>
</template>
```

**Analyse** :
- ✅ Props-based (no state)
- ✅ NO business logic
- ✅ Pure presentation
- ✅ Réutilisable (text card, code card, future cards)
- ✅ Testable (just pass props)

---

### 6. HealthBadge Component (Dumb/Presentational)

```vue
<!-- components/HealthBadge.vue -->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  name: string
  status: 'healthy' | 'unhealthy' | 'unknown'
}>()

// Presentation logic only (colors, icons)
const statusColor = computed(() => {
  switch (props.status) {
    case 'healthy': return 'bg-green-100 text-green-800'
    case 'unhealthy': return 'bg-red-100 text-red-800'
    default: return 'bg-gray-100 text-gray-800'
  }
})

const statusIcon = computed(() => {
  switch (props.status) {
    case 'healthy': return '✓'
    case 'unhealthy': return '✗'
    default: return '?'
  }
})
</script>

<template>
  <div class="health-badge p-4 rounded-lg" :class="statusColor">
    <div class="flex items-center justify-between">
      <span class="font-semibold">{{ name }}</span>
      <span class="text-2xl">{{ statusIcon }}</span>
    </div>
  </div>
</template>
```

**Analyse** :
- ✅ Computed pour presentation logic (couleurs, icônes)
- ✅ NO business logic (fetch, state management)
- ✅ Props-based
- ✅ Réutilisable

---

## 🧪 Testabilité

### Test Composable (Business Logic)

```typescript
// composables/__tests__/useEmbeddings.test.ts
import { describe, it, expect, vi } from 'vitest'
import { useEmbeddings } from '../useEmbeddings'

describe('useEmbeddings', () => {
  it('fetches embeddings on mount', async () => {
    const { textEmbeddings, codeEmbeddings, loading } = useEmbeddings()

    // Initially loading
    expect(loading.value).toBe(true)

    // Wait for fetch
    await vi.waitFor(() => {
      expect(loading.value).toBe(false)
    })

    // Data populated
    expect(textEmbeddings.value.count).toBeGreaterThan(0)
    expect(codeEmbeddings.value.count).toBeGreaterThan(0)
  })

  it('handles fetch errors', async () => {
    // Mock API error
    vi.mock('@/utils/api', () => ({
      api: {
        get: vi.fn().mockRejectedValue(new Error('Network error'))
      }
    }))

    const { error, fetchEmbeddings } = useEmbeddings()

    await fetchEmbeddings()

    expect(error.value).toBeTruthy()
    expect(error.value?.message).toBe('Network error')
  })
})
```

**Avantage** : Test business logic **sans monter le DOM** (rapide!)

---

### Test Component (Presentation)

```typescript
// components/__tests__/EmbeddingCard.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmbeddingCard from '../EmbeddingCard.vue'

describe('EmbeddingCard', () => {
  it('displays embedding stats', () => {
    const wrapper = mount(EmbeddingCard, {
      props: {
        title: 'TEXT Embeddings',
        model: 'nomic-text-v1.5',
        count: 7972,
        lastIndexed: '2025-11-01',
      }
    })

    expect(wrapper.text()).toContain('TEXT Embeddings')
    expect(wrapper.text()).toContain('nomic-text-v1.5')
    expect(wrapper.text()).toContain('7,972')
    expect(wrapper.text()).toContain('2025-11-01')
  })

  it('formats count with thousand separators', () => {
    const wrapper = mount(EmbeddingCard, {
      props: {
        title: 'CODE',
        model: 'jina-code-v2',
        count: 125000,
        lastIndexed: '2025-11-01',
      }
    })

    expect(wrapper.text()).toContain('125,000')
  })
})
```

**Avantage** : Test presentation **indépendamment de la logique**

---

## 📋 Checklist Best Practices

### Composable Rules

- [ ] **Naming**: `useXyz` convention
- [ ] **Single Responsibility**: Un composable = une feature
- [ ] **Return Object**: Toujours return `{ state, computed, methods }`
- [ ] **Error Handling**: Toujours gérer erreurs (ref error)
- [ ] **Loading State**: Toujours exposer `loading` ref
- [ ] **Cleanup**: Use `onUnmounted` si nécessaire (listeners, timers)
- [ ] **TypeScript**: Typer tous les refs, methods, return

### Component Rules

- [ ] **Props-Based**: Dumb components = props only
- [ ] **No Direct API Calls**: Pages/composables gèrent ça
- [ ] **Emit Events**: Use `defineEmits` pour communication parent
- [ ] **Computed for Presentation**: OK pour couleurs, formatting
- [ ] **No Business Logic**: If, else, switch pour présentation OK, mais pas fetch/state
- [ ] **Reusable**: Component doit être réutilisable (pas de state global)

### Page Rules

- [ ] **Use Composables**: Toute logique via composables
- [ ] **Orchestration**: Page = glue entre composables + components
- [ ] **Handle Events**: Catch emits from components, call composable methods
- [ ] **Layout**: Page gère layout (grid, flex, spacing)
- [ ] **Error Display**: Show errors from composables

---

## 🎯 Application à EPIC-25

### Phase 1: Dashboard (Stories 25.1-25.3)

**Composables à créer**:
1. `useDashboard.ts` - Global dashboard state
2. `useEmbeddings.ts` - Embeddings stats (TEXT + CODE)
3. `useHealth.ts` - Services health check

**Components à créer**:
1. `Navbar.vue` - Navigation (dumb)
2. `EmbeddingCard.vue` - Stats card (dumb)
3. `HealthBadge.vue` - Service badge (dumb)

**Pages**:
1. `Dashboard.vue` - Uses 3 composables + 2 components

**Ratio**: 3 composables : 3 components : 1 page = Good balance

---

### Phase 2: Search (Story 25.4)

**Composables à créer**:
1. `useSearch.ts` - Search logic (call API, manage state)

**Components à créer**:
1. `SearchBar.vue` - Input + filters (dumb)
2. `SearchResults.vue` - Results list (dumb)
3. `SearchResult.vue` - Single result card (dumb)

**Pages**:
1. `Search.vue` - Uses useSearch + 3 components

---

### Phase 2: Graph (Story 25.5)

**Composables à créer**:
1. `useGraph.ts` - Graph data + Cytoscape instance

**Components à créer**:
1. `GraphCanvas.vue` - Cytoscape container (dumb, receives cy instance)
2. `GraphControls.vue` - Zoom, pan buttons (dumb, emits events)
3. `NodeDetailsPanel.vue` - Node info sidebar (dumb, props-based)

**Pages**:
1. `Graph.vue` - Uses useGraph + 3 components

---

### Phase 3: Logs (Story 25.6)

**Composables à créer**:
1. `useLogs.ts` - Fetch logs, filtering, pagination

**Components à créer**:
1. `LogsTable.vue` - Table display (dumb)
2. `LogsFilters.vue` - Filter controls (dumb, emits)

**Pages**:
1. `Logs.vue` - Uses useLogs + 2 components

---

## 📊 Summary: Separation of Concerns

| Layer | Responsibility | Files | Testable Sans DOM |
|-------|---------------|-------|-------------------|
| **Composables** | Business logic, API, state | `composables/*.ts` | ✅ Yes |
| **Components** | Presentation, props, emits | `components/*.vue` | ⚠️ Need mount |
| **Pages** | Orchestration, layout | `pages/*.vue` | ⚠️ Need mount |
| **Utils** | Shared helpers | `utils/*.ts` | ✅ Yes |

**KISS Principle** :
- Composable = all logic
- Component = all presentation
- Page = glue

**Benefits**:
- ✅ Clear separation
- ✅ Highly testable
- ✅ Reusable
- ✅ Maintainable
- ✅ Scalable

---

## ✅ Next Steps

1. **Setup Project Structure**:
   ```
   mkdir -p frontend/src/{composables,components,pages,utils}
   ```

2. **Create Base Composables** (Phase 1):
   - `useDashboard.ts`
   - `useEmbeddings.ts`
   - `useHealth.ts`

3. **Create Dumb Components**:
   - `EmbeddingCard.vue`
   - `HealthBadge.vue`

4. **Create Dashboard Page**:
   - `Dashboard.vue` (uses composables + components)

5. **Write Tests**:
   - Composables tests (fast, no DOM)
   - Components tests (mount, props)

---

**Status**: ✅ BEST PRACTICES DEFINED
**Principe**: Composables (logic) + Components (presentation) = Clean, Testable, Maintainable
**Next**: Apply to EPIC-25 Phase 1 implementation

**Last Updated**: 2025-11-01
