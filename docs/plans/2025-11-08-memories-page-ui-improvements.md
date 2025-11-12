# Memories Page UI Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the Memories page UI with full-height columns and detailed conversation information display.

**Architecture:** Modify the layout to use CSS max-height for full viewport usage with individual column scrolling. Enhance the ConversationsWidget to display complete date (French format), memory type, project, and author information while maintaining the SCADA industrial style.

**Tech Stack:** Vue 3 Composition API, TypeScript, Tailwind CSS, existing SCADA styling

---

## Task 1: Add Full-Height Layout to Memories Page

**Goal:** Make the 3-column grid use maximum available height with flexible max-height approach.

**Files:**
- Modify: `frontend/src/pages/Memories.vue:76-95`

### Step 1: Read current Memories.vue layout

```bash
cat frontend/src/pages/Memories.vue | grep -A 20 "3-Column Dashboard"
```

Expected: See current grid layout without height constraints

### Step 2: Modify grid container to add max-height

In `frontend/src/pages/Memories.vue` at line 77, change:

```vue
<!-- BEFORE -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

<!-- AFTER -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 max-h-[calc(100vh-280px)]">
```

**Explanation:**
- `max-h-[calc(100vh-280px)]` = viewport height - navbar (64px) - header (80px) - stats bar (100px) - padding (36px)
- Columns will grow up to this height, then scroll individually

### Step 3: Verify the change in browser

```bash
# Vite HMR should auto-reload
# Check browser console for no errors
```

Expected: No compilation errors, page loads normally

### Step 4: Commit the layout change

```bash
git add frontend/src/pages/Memories.vue
git commit -m "feat(memories): add max-height to 3-column grid for full viewport usage

- Columns now use max-h-[calc(100vh-280px)]
- Enables better vertical space utilization
- Individual column scrolling will be added in widget components"
```

---

## Task 2: Add Date Formatting Functions to ConversationsWidget

**Goal:** Add helper functions for French date formatting and memory type labels.

**Files:**
- Modify: `frontend/src/components/ConversationsWidget.vue:1-38`

### Step 1: Read current ConversationsWidget script section

```bash
head -40 frontend/src/components/ConversationsWidget.vue
```

Expected: See existing `formatRelativeTime()` and `extractSessionId()` functions

### Step 2: Add formatFullDate function after extractSessionId

In `frontend/src/components/ConversationsWidget.vue` after line 38 (after `extractSessionId` function), add:

```typescript
// Format full date in French: "8 novembre 2025 07:18:03"
function formatFullDate(isoString: string): string {
  const date = new Date(isoString)
  const months = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
  ]
  const day = date.getDate()
  const month = months[date.getMonth()]
  const year = date.getFullYear()
  const time = date.toLocaleTimeString('fr-FR')
  return `${day} ${month} ${year} ${time}`
}
```

### Step 3: Add getMemoryTypeLabel function after formatFullDate

In `frontend/src/components/ConversationsWidget.vue` after the `formatFullDate` function, add:

```typescript
// Get short label for memory type
function getMemoryTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    conversation: 'Conv:',
    note: 'Note:',
    decision: 'Dec:',
    task: 'Task:',
    reference: 'Ref:'
  }
  return labels[type] || 'Conv:'
}
```

### Step 4: Verify TypeScript compilation

```bash
cd frontend && npx vue-tsc --noEmit | grep -i "ConversationsWidget"
```

Expected: No TypeScript errors for ConversationsWidget.vue

### Step 5: Commit the helper functions

```bash
git add frontend/src/components/ConversationsWidget.vue
git commit -m "feat(memories): add French date formatting and type label helpers

- Add formatFullDate(): formats ISO date to French format
- Add getMemoryTypeLabel(): converts memory type to short prefix
- Preparation for detailed conversation cards"
```

---

## Task 3: Update ConversationsWidget Template

**Goal:** Replace the conversation card template with detailed layout showing date, type, project, and author.

**Files:**
- Modify: `frontend/src/components/ConversationsWidget.vue:41-109`

### Step 1: Read current template structure

```bash
grep -A 50 "<!-- Conversations List -->" frontend/src/components/ConversationsWidget.vue
```

Expected: See current card template with time, title, tags, and status

### Step 2: Add overflow-y-auto to conversations list container

In `frontend/src/components/ConversationsWidget.vue` at line 57, change:

```vue
<!-- BEFORE -->
<div v-else class="space-y-3 overflow-y-auto max-h-[600px]">

<!-- AFTER -->
<div v-else class="space-y-3 overflow-y-auto h-full">
```

**Explanation:** Remove fixed max-h-[600px], let it fill parent container height

### Step 3: Replace conversation card template

In `frontend/src/components/ConversationsWidget.vue` replace lines 58-106 with:

```vue
      <div
        v-for="memory in memories"
        :key="memory.id"
        class="border-2 border-slate-600 rounded p-3 hover:bg-slate-700 transition-colors"
      >
        <!-- Header: Full Date + Author -->
        <div class="flex items-center justify-between text-xs text-gray-400 mb-2 font-mono">
          <span>{{ formatFullDate(memory.created_at) }}</span>
          <span class="uppercase">{{ memory.author || 'Unknown' }}</span>
        </div>

        <!-- Title with Type Prefix -->
        <div class="text-sm text-gray-200 mb-2 font-medium line-clamp-2">
          <span class="text-cyan-400">{{ getMemoryTypeLabel(memory.memory_type) }}</span>
          {{ memory.title }}
        </div>

        <!-- Project (conditional) -->
        <div v-if="memory.project_id" class="text-xs text-cyan-400 mb-2 flex items-center gap-1">
          <span>📁</span>
          <span class="uppercase font-mono">{{ memory.project_id }}</span>
        </div>

        <!-- Tags + Session -->
        <div class="flex flex-wrap gap-1 mb-2">
          <span
            v-for="tag in memory.tags.filter(t => !t.startsWith('session:')).slice(0, 3)"
            :key="tag"
            class="text-xs px-2 py-0.5 bg-slate-600 text-gray-300 rounded border border-slate-500 font-mono"
          >
            {{ tag }}
          </span>
          <span
            v-if="memory.tags.filter(t => !t.startsWith('session:')).length > 3"
            class="text-xs px-2 py-0.5 text-gray-400 font-mono"
          >
            +{{ memory.tags.filter(t => !t.startsWith('session:')).length - 3 }}
          </span>
          <span class="text-xs px-2 py-0.5 bg-slate-700 text-cyan-400 rounded border border-cyan-700 font-mono uppercase">
            session:{{ extractSessionId(memory.tags) }}
          </span>
        </div>

        <!-- Footer: Embedding Status + View Button -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="scada-led" :class="memory.has_embedding ? 'scada-led-green' : 'scada-led-yellow'"></span>
            <span class="text-xs font-mono uppercase" :class="memory.has_embedding ? 'scada-status-healthy' : 'scada-status-warning'">
              {{ memory.has_embedding ? 'Embedded' : 'No Embedding' }}
            </span>
          </div>
          <button
            class="scada-btn scada-btn-primary text-xs px-3 py-1"
            @click="$emit('view-detail', memory.id)"
          >
            View
          </button>
        </div>
      </div>
```

**Key changes:**
- Header: Full French date + Author (line 64-67)
- Title: Type prefix + title with line-clamp-2 (line 70-73)
- Project: Conditional display with 📁 icon (line 76-80)
- Tags: Filter out session tags, show first 3 + counter (line 83-98)
- Session: Separate badge with cyan styling (line 99-102)
- Footer: Unchanged (line 105-117)

### Step 4: Verify compilation

```bash
cd frontend && npx vue-tsc --noEmit | grep -i "ConversationsWidget"
```

Expected: No TypeScript errors

### Step 5: Test in browser

Open http://localhost:3000/memories and verify:
- ✅ Conversations show full French date
- ✅ Type prefixes visible (Conv:, Note:, etc.)
- ✅ Project shown when available
- ✅ Author displayed (or "Unknown")
- ✅ Tags filtered correctly (no session: tags in main list)
- ✅ Session ID shown in separate cyan badge
- ✅ Scroll works in conversation column

### Step 6: Commit the template update

```bash
git add frontend/src/components/ConversationsWidget.vue
git commit -m "feat(memories): redesign conversation cards with detailed info

New card layout:
- Header: Full French date + author
- Title: Memory type prefix (Conv:, Note:, etc.) + title
- Project: Conditional display with folder icon
- Tags: Filtered (exclude session:) with session badge separate
- Footer: Unchanged (embedding status + VIEW button)

Improvements:
- Changed container to h-full for parent-based height
- Added line-clamp-2 for title truncation
- Enhanced readability with clear information hierarchy
- Maintained SCADA industrial styling"
```

---

## Task 4: Manual Testing and Verification

**Goal:** Verify all improvements work correctly across different scenarios.

**Test Checklist:**

### Step 1: Test full-height layout

Open http://localhost:3000/memories

**Verify:**
- [ ] All 3 columns visible side-by-side (desktop)
- [ ] Columns use maximum available height
- [ ] Each column has individual scroll when content exceeds height
- [ ] No global page scroll (only column scrolls)
- [ ] Responsive on smaller screens

### Step 2: Test conversation card display

**Verify:**
- [ ] Date shown in French format (e.g., "8 novembre 2025 07:18:03")
- [ ] Author shown (or "Unknown" if null)
- [ ] Memory type prefix visible (Conv:, Note:, Dec:, Task:, Ref:)
- [ ] Title truncated properly with line-clamp (max 2 lines)
- [ ] Project displayed when available (📁 + name)
- [ ] Project hidden when null/undefined
- [ ] Tags filtered (no "session:" tags in main list)
- [ ] Session ID shown in separate cyan badge
- [ ] Embedding status LED correct (green/yellow)
- [ ] VIEW button works (opens modal)

### Step 3: Test with different data

**Create test memories with:**
```bash
# Example: Create different memory types via MCP
curl -X POST http://localhost:8000/api/memories \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Note", "content": "Test content", "memory_type": "note"}'
```

**Verify all memory types display correctly:**
- [ ] conversation → "Conv:"
- [ ] note → "Note:"
- [ ] decision → "Dec:"
- [ ] task → "Task:"
- [ ] reference → "Ref:"

### Step 4: Test edge cases

**Verify handling of:**
- [ ] Memory with no tags → Tags section hidden or empty
- [ ] Memory with many tags (>3) → "+N" counter shown
- [ ] Memory with null author → "Unknown" displayed
- [ ] Memory with null project_id → Project line not shown
- [ ] Very long title → Truncated with ellipsis
- [ ] Empty conversation list → "No Conversations Found" shown

### Step 5: Test performance

**Verify:**
- [ ] Smooth scrolling in conversation column
- [ ] No lag when many conversations (20+)
- [ ] HMR updates work without page reload
- [ ] No console errors

### Step 6: Final verification commit

```bash
# If all tests pass, mark as verified
git commit --allow-empty -m "test(memories): verify UI improvements

Manual testing completed:
✅ Full-height layout with individual column scrolling
✅ French date format displayed correctly
✅ Memory type prefixes working
✅ Project display conditional logic
✅ Author handling (with fallback to Unknown)
✅ Tag filtering (session tags separate)
✅ All memory types tested
✅ Edge cases handled
✅ Performance acceptable
✅ SCADA styling maintained

Ready for review."
```

---

## Rollback Plan

If issues are found during testing:

```bash
# Rollback to before Task 1
git log --oneline -5  # Find commit SHA before Task 1
git reset --hard <SHA>

# Or rollback specific files
git checkout HEAD~3 -- frontend/src/pages/Memories.vue
git checkout HEAD~3 -- frontend/src/components/ConversationsWidget.vue
```

---

## Success Criteria

- ✅ Columns use full available height (max-h-[calc(100vh-280px)])
- ✅ Individual column scrolling works
- ✅ Conversation cards show complete information:
  - French date format
  - Memory type prefix
  - Project (when available)
  - Author (with fallback)
  - Filtered tags + session badge
- ✅ SCADA industrial styling maintained
- ✅ No TypeScript compilation errors
- ✅ Responsive design works
- ✅ Performance acceptable with many conversations

---

## Notes

- **DRY:** Reused existing SCADA styles (scada-led, scada-btn, etc.)
- **YAGNI:** No new dependencies, pure Vue 3 + Tailwind
- **TDD:** Manual testing steps documented (no unit tests for UI components)
- **Frequent commits:** 4 commits (layout, helpers, template, verification)

---

## Related Documentation

- Design doc: `docs/plans/2025-11-08-memories-page-ui-improvements-design.md`
- Memory types: `frontend/src/types/memories.ts`
- SCADA styles: Check existing scada-* classes in codebase
