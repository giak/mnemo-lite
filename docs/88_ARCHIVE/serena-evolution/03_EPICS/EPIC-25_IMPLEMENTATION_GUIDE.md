# EPIC-25: Implementation Guide - Quick Start

**Date**: 2025-11-01
**Purpose**: Step-by-step guide pour démarrer l'implémentation de l'EPIC-25
**Target**: Dev solo, 6-9 semaines

---

## 🚀 Quick Start (Day 1-2)

### Step 1: Setup Project Structure

```bash
# Navigate to MnemoLite root
cd /home/giak/Work/MnemoLite

# Create frontend directory
mkdir -p frontend
cd frontend

# Initialize Vite + Vue.js 3 + TypeScript
pnpm create vite@latest . --template vue-ts

# Install core dependencies
pnpm install

# Add routing, state, graph
pnpm add vue-router@4 pinia cytoscape

# Add dev dependencies
pnpm add -D @types/node tailwindcss autoprefixer postcss vitest @vue/test-utils eslint prettier

# Initialize TailwindCSS
npx tailwindcss init -p
```

### Step 2: Configure TailwindCSS

```javascript
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

```css
/* src/style.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### Step 3: Configure Vite

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
  }
})
```

### Step 4: Configure TypeScript

```json
// tsconfig.json
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

### Step 5: Configure ESLint + Prettier

```javascript
// .eslintrc.cjs
module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier'
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    ecmaVersion: 'latest',
    parser: '@typescript-eslint/parser',
    sourceType: 'module'
  },
  rules: {
    'vue/multi-word-component-names': 'off',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }]
  }
}
```

```json
// .prettierrc
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "es5",
  "tabWidth": 2,
  "printWidth": 100
}
```

### Step 6: Setup Project Structure

```bash
cd src

# Create folders
mkdir -p composables components pages utils

# Remove default files
rm -rf components/HelloWorld.vue assets/vue.svg

# Create base files
touch composables/.gitkeep
touch components/.gitkeep
touch pages/.gitkeep
touch utils/api.ts
```

### Step 7: Update package.json Scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:ci": "vitest run",
    "lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --fix",
    "format": "prettier --write src/"
  }
}
```

---

## 📁 Final Structure (Day 2)

```
frontend/
├── public/
├── src/
│   ├── composables/        # Business logic
│   │   └── .gitkeep
│   ├── components/         # Presentation components
│   │   └── .gitkeep
│   ├── pages/              # Main views
│   │   └── .gitkeep
│   ├── utils/
│   │   └── api.ts          # API client
│   ├── App.vue
│   ├── main.ts
│   └── style.css
├── .eslintrc.cjs
├── .prettierrc
├── index.html
├── package.json
├── pnpm-lock.yaml
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

---

## 🏗️ Phase 1: Story 25.1 - Navbar + Routing

### Create Router

```typescript
// src/router.ts
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
      path: '/logs',
      name: 'logs',
      component: () => import('@/pages/Logs.vue')
    }
  ]
})

export default router
```

### Create Navbar Component

```vue
<!-- src/components/Navbar.vue -->
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
  <nav class="bg-white shadow-sm sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex space-x-8">
          <div class="flex-shrink-0 flex items-center">
            <h1 class="text-xl font-bold text-gray-900">MnemoLite</h1>
          </div>

          <div class="flex space-x-4 items-center">
            <router-link
              v-for="link in links"
              :key="link.path"
              :to="link.path"
              class="px-3 py-2 rounded-md text-sm font-medium transition-colors"
              :class="
                isActive(link.path)
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              "
            >
              {{ link.name }}
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>
```

### Create Placeholder Pages

```vue
<!-- src/pages/Dashboard.vue -->
<script setup lang="ts">
// Will implement in Story 25.3
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-3xl font-bold text-gray-900">Dashboard</h1>
    <p class="mt-4 text-gray-600">Dashboard will be implemented here.</p>
  </div>
</template>
```

```vue
<!-- src/pages/Search.vue -->
<script setup lang="ts">
// Will implement in Story 25.4
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-3xl font-bold text-gray-900">Search</h1>
    <p class="mt-4 text-gray-600">Search will be implemented here.</p>
  </div>
</template>
```

```vue
<!-- src/pages/Graph.vue -->
<script setup lang="ts">
// Will implement in Story 25.5
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-3xl font-bold text-gray-900">Graph</h1>
    <p class="mt-4 text-gray-600">Graph will be implemented here.</p>
  </div>
</template>
```

```vue
<!-- src/pages/Logs.vue -->
<script setup lang="ts">
// Will implement in Story 25.6
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-3xl font-bold text-gray-900">Logs</h1>
    <p class="mt-4 text-gray-600">Logs will be implemented here.</p>
  </div>
</template>
```

### Update App.vue

```vue
<!-- src/App.vue -->
<script setup lang="ts">
import Navbar from '@/components/Navbar.vue'
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <Navbar />
    <main>
      <router-view />
    </main>
  </div>
</template>
```

### Update main.ts

```typescript
// src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```

---

## 🧪 Test Story 25.1

```bash
# Start dev server
pnpm dev

# Open browser
# http://localhost:3000

# Test:
# ✅ Navbar affichée
# ✅ 4 liens (Dashboard, Search, Graph, Logs)
# ✅ Navigation fonctionne
# ✅ Active state (blue background on current page)
# ✅ Sticky navbar (scroll down)
```

**Acceptance**: Navigation works, navbar sticky, active state functional

---

## 📋 Next Steps After Story 25.1

### Story 25.2: Dashboard Backend API

Backend implementation:

```python
# api/routes/dashboard_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.db.session import get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/health")
async def get_health(db: AsyncSession = Depends(get_db)):
    """Get services health status"""
    return {
        "api": True,
        "database": await check_db_health(db),
        "redis": await check_redis_health()
    }

@router.get("/embeddings/text")
async def get_text_embeddings(db: AsyncSession = Depends(get_db)):
    """Get TEXT embeddings stats"""
    count = await db.scalar(
        select(func.count()).select_from(Conversation)
    )
    return {
        "model": "nomic-ai/nomic-embed-text-v1.5",
        "count": count,
        "dimension": 768,
        "lastIndexed": datetime.now().isoformat()
    }

@router.get("/embeddings/code")
async def get_code_embeddings(db: AsyncSession = Depends(get_db)):
    """Get CODE embeddings stats"""
    count = await db.scalar(
        select(func.count()).select_from(CodeChunk)
    )
    return {
        "model": "jinaai/jina-embeddings-v2-base-code",
        "count": count,
        "dimension": 768,
        "lastIndexed": datetime.now().isoformat()
    }
```

### Story 25.3: Dashboard Page

Create composables and components (see EPIC-25_VUE3_BEST_PRACTICES.md)

---

## 📊 Development Workflow

### Daily Workflow

```bash
# Morning: Pull latest, run tests
git pull
pnpm test:ci

# Development
pnpm dev             # Start dev server
# Code, save, hot-reload automatic

# Before commit: lint, test
pnpm lint
pnpm test:ci
pnpm build           # Check build works

# Commit
git add .
git commit -m "feat(story-25.1): implement navbar and routing"
```

### Testing Strategy

```bash
# Unit tests (composables)
pnpm test composables/

# Component tests
pnpm test components/

# E2E (later)
pnpm test:e2e
```

---

## 🎯 Definition of Done (per Story)

**Code**:
- [ ] Implementation complete
- [ ] TypeScript no errors
- [ ] ESLint passing
- [ ] Tests written (>70% coverage)

**Quality**:
- [ ] Loading states implemented
- [ ] Error handling implemented
- [ ] Responsive (desktop-first)
- [ ] Accessible (semantic HTML, keyboard nav)

**Documentation**:
- [ ] JSDoc comments on composables
- [ ] Component props documented
- [ ] Story acceptance criteria met

**Review**:
- [ ] Self-review (code quality, KISS, YAGNI)
- [ ] Manual testing (happy path + edge cases)
- [ ] Build successful
- [ ] Ready for production

---

## 📚 Resources

### Official Docs
- Vue.js 3: https://vuejs.org/guide/introduction.html
- Vue Router: https://router.vuejs.org/
- Pinia: https://pinia.vuejs.org/
- Vite: https://vitejs.dev/guide/
- TailwindCSS: https://tailwindcss.com/docs

### Project Docs
- EPIC-25_README.md - Main guide
- EPIC-25_VUE3_BEST_PRACTICES.md - Composables pattern
- EPIC-25_CRITICAL_REVIEW.md - KISS/YAGNI analysis

---

## 🚨 Common Pitfalls

### 1. Over-Engineering
- ❌ Adding features not in stories
- ✅ Stick to acceptance criteria

### 2. Not Using Composables
- ❌ Business logic in components
- ✅ Logic in composables, components dumb

### 3. Skipping Tests
- ❌ "I'll test later"
- ✅ Write tests as you code

### 4. Not Handling Errors
- ❌ Assume API always works
- ✅ try/catch, show errors to user

### 5. Ignoring TypeScript
- ❌ Using `any` everywhere
- ✅ Proper types, interfaces

---

## ✅ Checklist - Ready to Start

- [ ] PNPM installed globally (`npm install -g pnpm`)
- [ ] Node.js 18+ installed
- [ ] Backend API running (`http://localhost:8001`)
- [ ] Git configured
- [ ] IDE configured (VSCode + Volar extension recommended)
- [ ] EPIC-25_README.md read and understood
- [ ] EPIC-25_VUE3_BEST_PRACTICES.md read

**If all checked**: Ready to run setup commands! 🚀

---

**Status**: ✅ IMPLEMENTATION GUIDE READY
**Next Action**: Run Day 1-2 setup commands
**Timeline**: Setup (2 days) → Story 25.1 (2-3 days) → Phase 1 complete (2 weeks)

**Last Updated**: 2025-11-01
