# EPIC-25: Technical Stack Analysis - Vue.js 3 Modern Ecosystem

**Date**: 2025-11-01
**Purpose**: Comprehensive analysis of modern Vue.js 3 stack for MnemoLite UI/UX refonte
**Research**: Web Search + Context7 Documentation + Industry Best Practices 2025

---

## 📋 Executive Summary

**Recommended Stack**:
```
Frontend: Vue.js 3 + Composition API (<script setup>)
Build Tool: Vite v7.0.0
Package Manager: PNPM
Runtime: Node.js (production) | Bun (development/optional)
Linter/Formatter: Biome.js
State Management: Pinia
UI Components: Shadcn-Vue + TailwindCSS
Charts: Chart.js
Graph: Cytoscape.js
Testing: Vitest
```

**Rationale**: Modern, performant, monorepo-friendly, production-proven stack with excellent DX.

---

## 🔍 Component Analysis

### 1. Vue.js 3 + Composition API + Script Setup

#### Overview
Vue.js 3 with Composition API and `<script setup>` syntax is the modern standard for Vue development in 2025.

#### Key Features (from Context7 docs)

**1. Script Setup Syntax** (Recommended):
```vue
<script setup>
import { ref, onMounted } from 'vue'

// Reactive state
const count = ref(0)

// Functions that mutate state and trigger updates
function increment() {
  count.value++
}

// Lifecycle hooks
onMounted(() => {
  console.log(`The initial count is ${count.value}.`)
})
</script>

<template>
  <button @click="increment">Count is: {{ count }}</button>
</template>
```

**2. Props Declaration** (Type-Based):
```vue
<script setup lang="ts">
// Type-based declaration (concise, TypeScript)
const props = defineProps<{
  foo: string
  bar?: number
}>()

// Or runtime declaration
const props = defineProps({
  foo: { type: String, required: true },
  bar: Number
})
</script>
```

**3. Provide/Inject** (Dependency Injection):
```vue
<script setup>
import { ref, provide, inject } from 'vue'

// Provider (parent)
const count = ref(0)
provide('count', count)

// Consumer (child)
const count = inject('count')
</script>
```

#### Best Practices (Web Research 2025)

**1. Composables for Reusability**:
Extract business logic into `useXyz()` functions:
```typescript
// composables/useSearch.ts
import { ref, computed } from 'vue'

export function useSearch() {
  const query = ref('')
  const isSearching = ref(false)

  const search = async () => {
    isSearching.value = true
    // ... search logic
    isSearching.value = false
  }

  return { query, isSearching, search }
}

// Component usage
<script setup>
import { useSearch } from '@/composables/useSearch'
const { query, isSearching, search } = useSearch()
</script>
```

**2. Organize by Feature, Not File Type**:
```
src/
├── features/
│   ├── dashboard/
│   │   ├── components/
│   │   ├── composables/
│   │   ├── stores/
│   │   └── Dashboard.vue
│   ├── search/
│   │   ├── components/
│   │   ├── composables/
│   │   ├── stores/
│   │   └── Search.vue
│   └── monitoring/
└── shared/
```

**3. Ref vs Reactive**:
- `ref()` for primitives (string, number, boolean)
- `reactive()` for objects and arrays
- Avoid mixing unnecessarily

**4. State Management with Pinia**:
```typescript
// stores/dashboard.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useDashboardStore = defineStore('dashboard', () => {
  // State
  const metrics = ref({ cpu: 0, ram: 0 })

  // Getters
  const isHealthy = computed(() => metrics.value.cpu < 80)

  // Actions
  async function fetchMetrics() {
    // SSE or HTTP call
  }

  return { metrics, isHealthy, fetchMetrics }
})
```

**5. TypeScript + Script Setup**:
```vue
<script setup lang="ts">
import { ref, Ref } from 'vue'

interface Metric {
  name: string
  value: number
}

const metrics: Ref<Metric[]> = ref([])
</script>
```

#### Vue.js 3 Advantages for MnemoLite

✅ **Performance**: Virtual DOM optimizations, smaller bundle size vs Vue 2
✅ **Composition API**: Better code organization and reusability
✅ **TypeScript**: First-class support, better DX
✅ **SSR-Ready**: Vite + Vue 3 have excellent SSR support
✅ **Ecosystem**: Mature in 2025, extensive libraries (VueUse, Pinia, etc.)

---

### 2. Vite v7.0.0 (Latest)

#### Overview
Vite is the next-generation build tool with instant server start and lightning-fast HMR.

#### Key Features (from Context7 docs)

**1. SSR Configuration**:
```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ command, mode, isSsrBuild }) => {
  return {
    plugins: [vue()],

    // SSR-specific config
    ssr: {
      target: 'node', // or 'webworker'
      noExternal: [], // Force transform dependencies
      external: [],   // Externalize dependencies
    },

    // Build config
    build: {
      ssr: false, // true for SSR build
      ssrManifest: true, // Generate SSR manifest
      ssrEmitAssets: false,
      minify: 'esbuild', // or 'terser' or false
      reportCompressedSize: true,
    }
  }
})
```

**2. TypeScript Performance Optimization**:
```json
// tsconfig.json
{
  "compilerOptions": {
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true
  }
}
```
This enables direct `.ts`/`.tsx` imports without extensions, reducing filesystem checks.

**3. Build Scripts** (SSR-ready):
```json
{
  "scripts": {
    "dev": "vite",
    "build:client": "vite build --outDir dist/client --ssrManifest",
    "build:server": "vite build --outDir dist/server --ssr src/entry-server.ts",
    "build": "pnpm build:client && pnpm build:server",
    "preview": "NODE_ENV=production node server.js"
  }
}
```

#### Vite v7.0.0 New Features (2025)

**Environment API** (Game-changer):
- Standardizes how JS runs across client/server/edge environments
- Better control over multiple rendering contexts
- Improved SSR support

**Automatic Optimizations**:
- CSS Code Splitting (automatic extraction from async chunks)
- Preload Directives Generation (`<link rel="modulepreload">`)
- Tree-shaking optimizations

#### Vite Performance (Web Research 2025)

- **Dev Server**: Instant start (no bundling)
- **HMR**: Lightning-fast (<50ms updates)
- **Build**: Rollup-based, optimized production bundles
- **TypeScript**: esbuild transformation (20-30x faster than `tsc`)

#### Vite Advantages for MnemoLite

✅ **Speed**: Instant dev server, fast HMR critical for large UI
✅ **SSE Support**: Native EventSource support, perfect for monitoring
✅ **SSR-Ready**: If we need server-side rendering later
✅ **Plugin Ecosystem**: Rich plugins (Vue, TypeScript, PWA, etc.)
✅ **Production-Proven**: Next.js, Nuxt, Astro all migrated to Vite

---

### 3. PNPM vs NPM (Package Manager)

#### Performance Comparison (Web Research 2025)

| Metric | NPM | PNPM | Improvement |
|--------|-----|------|-------------|
| **Install Time (cold)** | ~120s | ~40s | **3x faster** |
| **Install Time (cached)** | ~60s | ~12s | **5x faster** |
| **Disk Space** | ~1.2 GB | ~300 MB | **75% reduction** |
| **node_modules Structure** | Flat, duplicates | Hard-links, symlinks | Efficient |
| **Monorepo Support** | Basic | Native, excellent | Built-in workspace |

#### PNPM Key Features

**1. Content-Addressable Storage**:
```
~/.pnpm-store/
  v3/
    files/
      00/abcd1234... (hard-linked to all projects)

project1/node_modules/
  .pnpm/
  lodash -> symlink to ~/.pnpm-store/.../lodash
```
- All packages stored once globally
- Projects hard-link to global store
- **Result**: 75% disk space savings

**2. Monorepo Workspace** (`pnpm-workspace.yaml`):
```yaml
packages:
  - 'api'
  - 'frontend'
  - 'shared'
```

**3. Strict Dependencies**:
- Prevents phantom dependencies (using unlisted packages)
- Flat structure causes bugs, PNPM prevents this

**4. Filtering & Scoped Commands**:
```bash
pnpm --filter frontend build
pnpm --filter api test
pnpm -r build  # Run build in all packages
```

#### Industry Adoption (2025)

Companies/Projects migrated to PNPM:
- ✅ **Next.js** (Vercel)
- ✅ **Vite** (Evan You)
- ✅ **Nuxt** (Nuxt team)
- ✅ **Astro** (Astro team)
- ✅ **Prisma** (Prisma team)

**Consensus**: PNPM is the sweet spot for 2025 - fast, space-efficient, monorepo-friendly.

#### PNPM for MnemoLite

✅ **Speed**: 3-5x faster installs (critical for CI/CD)
✅ **Disk Space**: 75% reduction (helpful for local dev)
✅ **Monorepo**: If we split `api` + `frontend` in future
✅ **Strict Mode**: Prevents dependency bugs early
✅ **Zero Config**: Drop-in replacement for NPM

**Migration**:
```bash
# Remove node_modules & package-lock.json
rm -rf node_modules package-lock.json

# Install PNPM
npm install -g pnpm

# Install dependencies
pnpm install
```

---

### 4. Bun Runtime (Optional Development Tool)

#### Overview (Web Research 2025)

Bun is an all-in-one JavaScript runtime built on Zig + JavaScriptCore.

**Key Stats**:
- Released: Bun 1.0 (September 2023)
- Latest: Bun v1.3.1 (October 28, 2025)
- Downloads: 5M+ monthly
- Performance: 3-4x faster than Node.js

#### Performance Benchmarks

| Task | Node.js | Bun | Improvement |
|------|---------|-----|-------------|
| **Cold Start** | 3.4s | 1.7s | **2x faster** |
| **HTTP Server** | Baseline | 3-4x faster | **3-4x** |
| **Package Install** | Baseline | 2-3x faster | **2-3x** |
| **Startup Time** | Baseline | 4x faster | **4x** |
| **Idle CPU** | Baseline | 100x reduction | **100x** |
| **Idle Memory** | Baseline | 40% reduction | **40%** |

#### Production Readiness (2025)

**Ready for**:
- ✅ Experiments, side projects
- ✅ Development environments
- ✅ Some production use cases (with caveats)

**Notable Users**:
- ✅ **Anthropic**: Uses Bun for Claude Code CLI

**Cautions**:
- ⚠️ Ecosystem still evolving (some native modules fail)
- ⚠️ Vue.js support: **Partially available, still evolving**
- ⚠️ Full migration not advised without extensive testing

**Quote from research**:
> "React is supported out of the box. Hot reloading just works. Plugins for Svelte and Vue are coming soon."
> - Bun roadmap (February 2025)

#### Vue.js Compatibility

**Current Status**:
- React: ✅ Full support
- Svelte: 🚧 Plugin in development
- Vue: 🚧 Plugin in development

**Workarounds**:
- Bun can run `vite dev` and `vite build` (no problem)
- Bun as task runner + package manager (not runtime)

#### Bun for MnemoLite (Recommendation)

**Recommended Approach**:
```json
// package.json
{
  "scripts": {
    "dev": "bun vite",              // Use Bun to run Vite
    "build": "bun vite build",      // Use Bun to run Vite build
    "preview": "bun vite preview",
    "test": "bun vitest"
  }
}
```

**Use Cases**:
- ✅ **Task runner**: Run scripts 2-4x faster
- ✅ **Package installer**: `bun install` instead of `pnpm install`
- ✅ **Test runner**: `bun vitest` faster than `node vitest`
- ❌ **Production runtime**: Stick with Node.js for now

**Migration Path**:
1. **Phase 1** (Now): Use Bun for dev scripts (`bun vite`)
2. **Phase 2** (Q1 2026): Use Bun for testing (`bun vitest`)
3. **Phase 3** (Q2 2026+): Evaluate Bun production runtime when Vue plugin is stable

---

### 5. Biome.js (Linter + Formatter)

#### Overview (Web Research 2025)

Biome is a modern toolchain written in Rust, replacing ESLint + Prettier with a single tool.

**Key Stats**:
- Released: 2023
- Latest: Biome v2.0 (June 2025)
- Performance: 15-25x faster than ESLint + Prettier
- Compatibility: 97% Prettier, 80%+ ESLint

#### Performance Comparison

| Task | ESLint + Prettier | Biome | Improvement |
|------|-------------------|-------|-------------|
| **Linting (10k lines)** | 3-5s | ~200ms | **15x faster** |
| **Formatting (1k files)** | 1-2s | ~50ms | **25x faster** |
| **Configuration** | 2 tools | 1 tool | Unified |
| **Dependencies** | Many plugins | Zero | Self-contained |

#### Key Features

**1. All-in-One**:
```bash
# Replace:
npm install -D eslint prettier eslint-config-prettier eslint-plugin-vue

# With:
npm install -D @biomejs/biome
```

**2. Single Configuration** (`biome.json`):
```json
{
  "$schema": "https://biomejs.dev/schemas/2.0.0/schema.json",
  "organizeImports": {
    "enabled": true
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "suspicious": {
        "noExplicitAny": "error"
      }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  }
}
```

**3. Fast CLI**:
```bash
# Format
biome format --write ./src

# Lint
biome lint ./src

# Format + Lint + Organize Imports
biome check --write ./src
```

**4. Type Inference** (Biome 2.0+):
- Can catch type-related issues without running TypeScript compiler
- ~85% coverage of `typescript-eslint`

#### Biome vs ESLint + Prettier

**Biome Advantages**:
- ✅ **Speed**: 15-25x faster
- ✅ **Zero Config**: Works out of the box
- ✅ **Single Tool**: No coordination between linter/formatter
- ✅ **97% Prettier Compatible**: Easy migration
- ✅ **Rust-Based**: Memory-safe, parallel processing

**Biome Limitations**:
- ⚠️ Younger ecosystem (not all ESLint plugins supported)
- ⚠️ JSON-only config (vs JavaScript for dynamic setups)
- ⚠️ Vue support: **Less optimal** (better for React, TypeScript, JSON, CSS)

**Quote from research**:
> "Switching to Biome may result in less than optimal support for certain file types such as Vue, Markdown, YAML, and others."

#### Recommendation for MnemoLite

**Option A: Biome (Recommended for TypeScript/JSON/CSS)**:
```bash
pnpm add -D @biomejs/biome
```

**Option B: ESLint + Prettier (If Vue-specific rules needed)**:
```bash
pnpm add -D eslint prettier eslint-plugin-vue @vue/eslint-config-typescript
```

**Hybrid Approach** (Best of Both):
- **Biome**: For TypeScript files, shared utilities, JSON, CSS
- **ESLint**: For Vue SFC files only

```json
// biome.json
{
  "files": {
    "ignore": ["**/*.vue"] // Let ESLint handle Vue files
  }
}
```

---

## 🏗️ Recommended Architecture for EPIC-25

### Frontend Structure (Vue.js 3 + Vite)

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/          # Static assets (images, fonts)
│   ├── components/      # Shared UI components
│   │   ├── ui/          # Shadcn-Vue components
│   │   ├── charts/      # Chart.js wrappers
│   │   └── common/      # Buttons, Cards, etc.
│   ├── composables/     # Shared composables
│   │   ├── useSSE.ts
│   │   ├── useSearch.ts
│   │   └── useMetrics.ts
│   ├── features/        # Feature modules
│   │   ├── dashboard/
│   │   │   ├── components/
│   │   │   ├── composables/
│   │   │   ├── stores/
│   │   │   └── Dashboard.vue
│   │   ├── search/
│   │   ├── graph/
│   │   ├── monitoring/
│   │   └── settings/
│   ├── layouts/
│   │   ├── DefaultLayout.vue
│   │   └── NavBar.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/          # Pinia stores
│   │   ├── dashboard.ts
│   │   ├── search.ts
│   │   └── monitoring.ts
│   ├── types/           # TypeScript types
│   │   └── api.ts
│   ├── utils/
│   │   ├── api.ts       # Axios/Fetch wrapper
│   │   └── formatters.ts
│   ├── App.vue
│   └── main.ts
├── biome.json           # Biome config
├── index.html
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```

### Package.json (Recommended)

```json
{
  "name": "mnemolite-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "lint": "biome check ./src",
    "format": "biome format --write ./src",
    "test": "vitest",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "pinia": "^2.3.0",
    "@vueuse/core": "^11.5.0",
    "chart.js": "^4.5.0",
    "vue-chartjs": "^5.4.0",
    "cytoscape": "^3.32.0",
    "axios": "^1.8.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "vite": "^7.0.0",
    "typescript": "^5.7.3",
    "vue-tsc": "^2.2.0",
    "vitest": "^3.0.4",
    "@vitest/ui": "^3.0.4",
    "@biomejs/biome": "^1.9.4",
    "tailwindcss": "^3.4.17",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49"
  }
}
```

### Vite Config (Optimized)

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },

  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  },

  build: {
    target: 'esnext',
    minify: 'esbuild',
    reportCompressedSize: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'charts': ['chart.js', 'vue-chartjs'],
          'graph': ['cytoscape']
        }
      }
    }
  },

  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', '@vueuse/core']
  }
})
```

### TypeScript Config (Performance)

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ESNext", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.tsx", "src/**/*.vue"],
  "exclude": ["node_modules", "dist"]
}
```

---

## 🎯 Tech Stack Decision Matrix

### Comparison: Vue.js 3 vs React

| Criterion | Vue.js 3 | React | Winner |
|-----------|----------|-------|--------|
| **Learning Curve** | Gentle, intuitive | Steeper (JSX, hooks) | Vue ✅ |
| **Performance** | Excellent (Virtual DOM) | Excellent (Virtual DOM) | Tie |
| **Bundle Size** | 34KB (gzipped) | 42KB (gzipped) | Vue ✅ |
| **TypeScript** | First-class support | First-class support | Tie |
| **SSE Support** | Native EventSource | Native EventSource | Tie |
| **Ecosystem** | Rich, mature (2025) | Richer, more mature | React |
| **State Mgmt** | Pinia (simple) | Redux/Zustand (complex) | Vue ✅ |
| **SSR** | Excellent (Nuxt/Vite) | Excellent (Next.js) | Tie |
| **Developer Preference** | User chose Vue! | - | Vue ✅ |

**Decision**: **Vue.js 3** (user preference + excellent fit for MnemoLite)

### Comparison: Vite vs Webpack

| Criterion | Vite | Webpack | Winner |
|-----------|------|---------|--------|
| **Dev Server Start** | Instant (<1s) | Slow (10-30s) | Vite ✅ |
| **HMR Speed** | <50ms | 1-3s | Vite ✅ |
| **Build Speed** | Fast (Rollup) | Slower | Vite ✅ |
| **Config Complexity** | Simple | Complex | Vite ✅ |
| **Ecosystem** | Growing | Mature | Webpack |
| **Production Ready** | Yes (2025) | Yes | Tie |

**Decision**: **Vite** (clear winner for modern development)

### Comparison: PNPM vs NPM vs Bun

| Criterion | PNPM | NPM | Bun | Winner |
|-----------|------|-----|-----|--------|
| **Install Speed** | 3x faster | Baseline | 5x faster | Bun ✅ |
| **Disk Space** | 75% savings | Baseline | Similar to PNPM | PNPM ✅ |
| **Monorepo** | Native, excellent | Basic | Good | PNPM ✅ |
| **Stability** | Proven (2025) | Rock solid | Evolving | PNPM/NPM |
| **Ecosystem** | Compatible | 100% | 95%+ | NPM/PNPM |
| **Production Ready** | Yes | Yes | Partial (Vue) | PNPM ✅ |

**Decision**: **PNPM** (primary) + **Bun** (optional dev scripts)

### Comparison: Biome vs ESLint + Prettier

| Criterion | Biome | ESLint + Prettier | Winner |
|-----------|-------|-------------------|--------|
| **Speed** | 15-25x faster | Baseline | Biome ✅ |
| **Configuration** | Single tool | Two tools | Biome ✅ |
| **Vue Support** | Less optimal | Excellent | ESLint ✅ |
| **TypeScript** | Excellent | Good | Biome ✅ |
| **Ecosystem** | Growing | Mature | ESLint |
| **Learning Curve** | Gentle | Moderate | Biome ✅ |

**Decision**: **Hybrid** (Biome for TS/JSON/CSS, ESLint for Vue SFC)

---

## 📊 Performance Projections for MnemoLite

### Build Times (Estimated)

| Phase | Webpack + NPM | Vite + PNPM | Vite + Bun | Improvement |
|-------|---------------|-------------|------------|-------------|
| **Initial Install** | ~120s | ~40s | ~25s | **79% faster** |
| **Dev Server Start** | ~15s | <1s | <1s | **93% faster** |
| **HMR Update** | 2-3s | <50ms | <50ms | **98% faster** |
| **Production Build** | ~60s | ~25s | ~20s | **67% faster** |
| **Linting** | ~5s | ~500ms | ~500ms | **90% faster** |

**Total Time Saved** (per dev cycle): **~85% reduction**

### Bundle Size (Estimated)

| Library | Size (gzipped) |
|---------|----------------|
| Vue 3 + Router + Pinia | ~50 KB |
| Chart.js | ~60 KB |
| Cytoscape.js | ~80 KB |
| TailwindCSS (purged) | ~10 KB |
| **Total Base** | **~200 KB** |
| **+ Components** | ~100 KB |
| **Grand Total** | **~300 KB** ✅ |

**Target**: <500 KB (excellent for rich dashboard)

---

## ✅ Final Recommendation

### Phase 1: MVP1 (Navigation + Dashboard)

**Stack**:
```yaml
Frontend:
  - Vue.js 3.5+ with Composition API (<script setup>)
  - Vite 7.0.0
  - TypeScript 5.7+
  - PNPM (package manager)

UI/UX:
  - TailwindCSS 3.4+
  - Shadcn-Vue (component library)
  - Chart.js 4.5+ (activity chart)
  - Heroicons (icons)

State:
  - Pinia 2.3+ (stores)
  - VueUse 11.5+ (composables)

Testing:
  - Vitest 3.0+ (unit tests)
  - @vitest/ui (test UI)

Linting:
  - Biome 1.9+ (TS/JSON/CSS)
  - ESLint + eslint-plugin-vue (Vue SFC)

Optional:
  - Bun (dev scripts, faster task runner)
```

### Migration Path

**Week 1-2**:
1. Setup Vite + Vue 3 project
2. Configure PNPM workspace
3. Setup TailwindCSS + Shadcn-Vue
4. Create base layout + NavBar

**Week 3-4**:
1. Implement Dashboard skeleton
2. Create Pinia stores (dashboard, metrics)
3. Setup SSE composable (`useSSE.ts`)
4. Integrate Chart.js

**Week 5-6**:
1. Build 2 Embedding Cards (TEXT vs CODE)
2. Activity chart (live SSE data)
3. Quick actions buttons
4. Testing + polish

### Development Workflow

```bash
# Install dependencies
pnpm install

# Dev server (with Bun for speed, optional)
bun vite dev  # or: pnpm dev

# Linting
pnpm lint

# Build
pnpm build

# Test
pnpm test
```

---

## 🔗 Resources

### Official Documentation
- Vue.js 3: https://vuejs.org
- Vite: https://vite.dev
- PNPM: https://pnpm.io
- Bun: https://bun.com
- Biome: https://biomejs.dev

### Libraries
- Pinia: https://pinia.vuejs.org
- VueUse: https://vueuse.org
- Shadcn-Vue: https://www.shadcn-vue.com
- Chart.js: https://www.chartjs.org
- Cytoscape.js: https://js.cytoscape.org

### Learning Resources
- Vue School: https://vueschool.io
- Vue Mastery: https://www.vuemastery.com
- State of Vue 2025: https://www.monterail.com/stateofvue

---

## 📝 Next Steps

1. **Valida3te Stack**: User approval on Vue 3 + Vite + PNPM + Biome
2. **Setup Project**: Initialize Vite + Vue 3 project structure
3. **Create POC**: Small SSE dashboard POC (1-2 days)
4. **Update EPIC-25**: Update all stories with Vue 3 specifics
5. **Kick-off Phase 1**: Start Story 25.1 (Navbar + Routing)

---

**Status**: ✅ ANALYSIS COMPLETE - Ready for user validation
**Next Action**: User approval + Project setup
**Estimated Setup Time**: 1-2 days for base scaffolding

**Last Updated**: 2025-11-01
