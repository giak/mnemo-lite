# Canvas Resize Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor canvas resize to use G6 native `autoResize` instead of custom composable with timing logic.

**Architecture:** Remove the 3-layer custom resize system (composable + setTimeout + manual calculations) and replace with G6's built-in `autoResize: true` option. This eliminates race conditions and reduces code by ~150 lines.

**Tech Stack:** Vue 3 Composition API, G6 graph library, TypeScript

---

## Task 1: Refactor OrgchartGraph.vue to use G6 autoResize

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:1-850`

**Step 1: Remove composable import and usage**

Remove these lines:
```typescript
// Line 14 - Remove import
import { useFullscreenResize } from '@/composables/useFullscreenResize'

// Lines 43-49 - Remove composable usage
const { calculateSize } = useFullscreenResize(containerRef, (width, height) => {
  if (graph) {
    graph.setSize(width, height)
    graph.render()
  }
})
```

**Step 2: Add autoResize to Graph config**

In the `initGraph()` function, find the `new Graph({...})` call (around line 412) and add `autoResize: true`:

```typescript
graph = new Graph({
  container: containerRef.value,
  autoResize: true,  // ← Add this line
  width: containerRef.value.offsetWidth,
  height: containerRef.value.offsetHeight,
  layout: {
    // ... rest of config
  }
})
```

**Step 3: Remove manual resize logic from view mode change**

In the watch callback (around line 645-654), remove the manual resize call:

```typescript
if ((onlyViewModeChanged || onlyZoomChanged) && graph) {
  try {
    console.log('[Orgchart] ViewMode or Zoom changed, updating styles with animation...')

    // ← REMOVE THESE LINES (650-654):
    // const size = calculateSize()
    // if (size) {
    //   console.log('[Orgchart] Resizing canvas for view change:', size)
    //   graph.setSize(size.width, size.height)
    // }

    const nodeMap = new Map(props.nodes.map(n => [n.id, n]))
    // ... rest of animation logic
```

**Step 4: Simplify onMounted - remove delays**

Replace the delayed init (lines 792-798) with immediate call:

```typescript
// Initialize on mount - G6 autoResize handles resize events
onMounted(() => {
  initGraph()
})
```

**Step 5: Remove setTimeout from watch**

In the watch callback for data changes (around lines 786-790), replace delayed init:

```typescript
// OLD (lines 786-790):
// await nextTick()
// setTimeout(() => {
//   initGraph()
// }, 100)

// NEW:
await nextTick()
initGraph()
```

**Step 6: Verify compilation**

Run: `cd frontend && pnpm dev`
Expected: No TypeScript errors, HMR update successful

**Step 7: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "refactor(orgchart): use G6 autoResize instead of custom resize logic"
```

---

## Task 2: Refactor ForceDirectedGraph.vue to use G6 autoResize

**Files:**
- Modify: `frontend/src/components/ForceDirectedGraph.vue:1-320`

**Step 1: Remove composable import and usage**

Remove these lines:
```typescript
// Line 5 - Remove import
import { useFullscreenResize } from '@/composables/useFullscreenResize'

// Lines 15-20 - Remove composable usage
const { calculateSize } = useFullscreenResize(containerRef, (width, height) => {
  if (graphInstance) {
    graphInstance.changeSize(width, height)
  }
})
```

**Step 2: Add autoResize to Graph config**

In the `initGraph()` function (around line 123), add `autoResize: true`:

```typescript
graphInstance = new Graph({
  container: containerRef.value,
  autoResize: true,  // ← Add this line
  width: containerRef.value.offsetWidth,
  height: containerRef.value.offsetHeight,
  layout: {
    // ... rest of config
  }
})
```

**Step 3: Remove manual size calculation**

Remove the size calculation at the start of `initGraph()` (around lines 111-118):

```typescript
// OLD (remove these lines):
// const size = calculateSize()
// if (!size) {
//   console.error('[ForceDirectedGraph] Failed to calculate size')
//   return
// }
// console.log('[ForceDirectedGraph] Initializing with dimensions:', size)

// NEW (use container dimensions directly):
const width = containerRef.value.offsetWidth
const height = containerRef.value.offsetHeight

graphInstance = new Graph({
  container: containerRef.value,
  autoResize: true,
  width,
  height,
  // ...
})
```

**Step 4: Simplify onMounted - remove delays**

Replace the delayed init (lines 194-200) with immediate call:

```typescript
// Initialize on mount - G6 autoResize handles resize events
onMounted(() => {
  initGraph()
})
```

**Step 5: Remove setTimeout from watch**

Replace the watch with delayed init (lines 209-215) with immediate call:

```typescript
watch(() => [props.nodes, props.edges], async () => {
  await nextTick()
  initGraph()
}, { deep: true })
```

**Step 6: Verify compilation**

Run: `cd frontend && pnpm dev`
Expected: No TypeScript errors, HMR update successful

**Step 7: Commit**

```bash
git add frontend/src/components/ForceDirectedGraph.vue
git commit -m "refactor(force-graph): use G6 autoResize instead of custom resize logic"
```

---

## Task 3: Delete useFullscreenResize composable

**Files:**
- Delete: `frontend/src/composables/useFullscreenResize.ts`

**Step 1: Verify no other files import it**

Run: `cd frontend && grep -r "useFullscreenResize" src/`
Expected: No matches (both OrgchartGraph and ForceDirectedGraph already updated)

**Step 2: Delete the file**

Run: `rm frontend/src/composables/useFullscreenResize.ts`

**Step 3: Verify compilation**

Run: `cd frontend && pnpm dev`
Expected: No errors, successful compilation

**Step 4: Commit**

```bash
git add frontend/src/composables/useFullscreenResize.ts
git commit -m "refactor: remove useFullscreenResize composable (replaced by G6 autoResize)"
```

---

## Task 4: Manual Testing

**Files:**
- Test: `http://localhost:3000/orgchart`

**Step 1: Test normal window resize**

1. Open `http://localhost:3000/orgchart`
2. Resize browser window
3. Expected: Canvas resizes smoothly to fill available space

**Step 2: Test fullscreen toggle**

1. Click fullscreen button (⛶)
2. Expected: Canvas fills entire screen
3. Press ESC or click exit fullscreen (🗗)
4. Expected: Canvas returns to normal size

**Step 3: Test view changes**

1. Start on "Complexité" view
2. Click "Hiérarchie"
3. Expected: Canvas fills available space (not compressed)
4. Click "Hubs"
5. Expected: Canvas fills available space
6. Click "Architecture"
7. Expected: Canvas fills available space
8. Click "Matrice"
9. Expected: Matrix view renders correctly

**Step 4: Test zoom changes**

1. On any orgchart view (Hiérarchie/Complexité/Hubs)
2. Adjust zoom slider
3. Expected: Canvas maintains correct size while nodes filter

**Step 5: Document testing results**

If all tests pass, no action needed.

If any test fails, add a ResizeObserver fallback for that specific case (minimal implementation).

---

## Verification Checklist

- [ ] No TypeScript compilation errors
- [ ] No console errors when changing views
- [ ] Canvas fills available space in normal mode
- [ ] Canvas fills screen in fullscreen mode
- [ ] All 5 views work correctly (Hiérarchie, Complexité, Hubs, Architecture, Matrice)
- [ ] Window resize works smoothly
- [ ] Zoom slider works without resize issues
- [ ] Code reduced by ~150 lines
- [ ] No more `setTimeout` delays
- [ ] No more manual dimension calculations

---

## Rollback Plan

If `autoResize` doesn't work correctly:

1. Restore `useFullscreenResize.ts` from git
2. Re-add composable imports to both components
3. Create GitHub issue documenting which scenario failed
4. Consider hybrid approach: `autoResize: true` + minimal ResizeObserver for edge cases

---

## Success Criteria

✅ Canvas resize works consistently across all views
✅ No race conditions or timing issues
✅ Code is simpler and more maintainable
✅ Behavior is predictable (single source of truth: G6)
