# Canvas Resize Refactor Design

**Date:** 2025-11-08
**Approach:** Use G6 native `autoResize` (KISS/YAGNI)

## Problem

The current canvas resize system has inconsistent behavior across view changes:
- Uses 3 layers: composable + watch with delays + manual calculations
- Race conditions with `setTimeout(100ms)` delays
- Manual dimension calculations that can fail
- ~150 lines of complex resize logic

## Solution: Delegate to G6 `autoResize`

### Principle

Let G6 handle all resize logic natively with its built-in `autoResize: true` option. Remove all custom timing, calculations, and observers.

### Architecture Changes

1. **Remove completely:**
   - `/frontend/src/composables/useFullscreenResize.ts` (entire file)
   - All `setTimeout` delays in graph components
   - All manual dimension calculations (`calculateSize()`)
   - Custom `ResizeObserver` instances
   - `fullscreenchange` event listeners

2. **Add to G6 config:**
   ```typescript
   const graph = new Graph({
     container: containerRef.value,
     autoResize: true,  // G6 handles everything
     // ... rest of config
   })
   ```

3. **Keep:**
   - Fullscreen button and `toggleFullscreen()` in `Orgchart.vue`
   - No need to listen to resize events - `autoResize` detects them automatically

### Files to Modify

1. **DELETE:** `frontend/src/composables/useFullscreenResize.ts`
2. **MODIFY:** `frontend/src/components/OrgchartGraph.vue`
   - Remove composable import and usage
   - Add `autoResize: true` to Graph config
   - Remove `watch` with `setTimeout`
   - Simplify `onMounted` (no delays)
3. **MODIFY:** `frontend/src/components/ForceDirectedGraph.vue`
   - Same changes as OrgchartGraph

### Benefits

- **KISS:** One option instead of 3-layer system
- **YAGNI:** Remove unused complexity
- **DRY:** No duplicated resize logic
- **Reliable:** G6-maintained, no race conditions
- **Lines removed:** ~150 lines

### Testing Plan

1. Test window resize in normal mode
2. Test fullscreen toggle (⛶ button)
3. Test view changes (Hiérarchie → Complexité → Hubs → Architecture → Matrice)
4. Test zoom changes
5. Verify canvas fills available space in all scenarios

### Rollback Plan

If `autoResize` doesn't work for fullscreen:
- Add minimal `ResizeObserver` only for fullscreen edge case
- Keep it separate from G6 config
- Still simpler than current 3-layer system

## Implementation Steps

See implementation plan: `2025-11-08-canvas-resize-refactor-plan.md`
