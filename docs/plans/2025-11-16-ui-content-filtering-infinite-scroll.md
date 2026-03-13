# MnemoLite UI Content Filtering & Infinite Scroll Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean conversation titles from system pollution (`<ide_opened_file>`, `<system-reminder>`) and add infinite scroll to UI for better conversation monitoring.

**Architecture:** Two-layer approach: (1) Backend filters user messages at save time to extract first real text for clean titles, (2) Frontend implements infinite scroll with offset-based pagination.

**Tech Stack:** Bash/jq (backend filtering), Vue 3 Composition API (frontend), TypeScript, Tailwind CSS

---

## Task 1: Backend - Add Message Cleaning Function

**Context:** The script `/home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh` currently extracts raw user messages that contain pollution like `<ide_opened_file>`, `<system-reminder>`, `<command-message>`, etc. This pollutes conversation titles in the UI.

**Files:**
- Modify: `/home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh`

**Step 1: Write test helper script**

Create a test script to validate cleaning function before integrating.

```bash
# Create: /home/giak/Work/MnemoLite/tests/test-clean-user-message.sh
#!/bin/bash

# Test cases for clean_user_message function
source /home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh

# Test 1: Remove <ide_opened_file> pollution
INPUT1='<ide_opened_file>The user opened /path/to/file</ide_opened_file>
test_fix_2025'
EXPECTED1='test_fix_2025'
RESULT1=$(clean_user_message "$INPUT1")
echo "Test 1: ${RESULT1}"
[[ "$RESULT1" == "$EXPECTED1" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT1)"

# Test 2: Remove <system-reminder>
INPUT2='<system-reminder>Some system message</system-reminder>
bozo'
EXPECTED2='bozo'
RESULT2=$(clean_user_message "$INPUT2")
echo "Test 2: ${RESULT2}"
[[ "$RESULT2" == "$EXPECTED2" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT2)"

# Test 3: Remove multiple tags
INPUT3='<ide_opened_file>...</ide_opened_file>
<system-reminder>...</system-reminder>
recherche "test_fix_2025"'
EXPECTED3='recherche "test_fix_2025"'
RESULT3=$(clean_user_message "$INPUT3")
echo "Test 3: ${RESULT3}"
[[ "$RESULT3" == "$EXPECTED3" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT3)"

# Test 4: Keep regular text unchanged
INPUT4='This is a normal user message'
EXPECTED4='This is a normal user message'
RESULT4=$(clean_user_message "$INPUT4")
echo "Test 4: ${RESULT4}"
[[ "$RESULT4" == "$EXPECTED4" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT4)"
```

**Step 2: Run test to verify it fails**

```bash
chmod +x /home/giak/Work/MnemoLite/tests/test-clean-user-message.sh
bash /home/giak/Work/MnemoLite/tests/test-clean-user-message.sh
```

**Expected:** FAIL with "clean_user_message: command not found"

**Step 3: Implement clean_user_message function**

Add this function after line 201 in `/home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh`:

```bash
# ============================================================================
# 3.5. CLEAN USER MESSAGE (extract first real text)
# ============================================================================

# Function: Extract first real user text, removing XML-like system tags
# Input: Raw user message (may contain <ide_opened_file>, <system-reminder>, etc.)
# Output: First non-empty line without XML tags, max 100 chars
clean_user_message() {
  local raw_msg="$1"

  # Remove all XML-like tags and their content (greedy multi-line)
  # Handles: <ide_opened_file>...</ide_opened_file>, <system-reminder>...</system-reminder>, etc.
  local cleaned=$(echo "$raw_msg" | sed -E '
    # Remove opening + content + closing tags (multi-line, greedy)
    :a
    s|<[^>]+>.*</[^>]+>||g
    # Remove orphan opening tags
    s|<[^>]+>||g
    # Remove orphan closing tags
    s|</[^>]+>||g
    ta
  ')

  # Extract first non-empty line
  local first_line=$(echo "$cleaned" | grep -v '^[[:space:]]*$' | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')

  # Limit to 100 chars for title
  echo "$first_line" | head -c 100
}

# Clean USER_MSG for title generation
USER_MSG_CLEAN=$(clean_user_message "$USER_MSG")

# Use cleaned message for title, keep raw for content
if [ -z "$USER_MSG_CLEAN" ]; then
  # Fallback: if cleaning resulted in empty, use first 100 chars of raw
  USER_MSG_CLEAN=$(echo "$USER_MSG" | head -c 100)
fi
```

**Step 4: Run test to verify it passes**

```bash
bash /home/giak/Work/MnemoLite/tests/test-clean-user-message.sh
```

**Expected:** All tests PASS with "✓ PASS"

**Step 5: Integrate cleaned message into API call**

Modify lines 226-234 to send both cleaned and raw messages:

```bash
# Try queuing to Redis via API endpoint (reliable path)
QUEUE_RESPONSE=$(curl -s -X POST http://localhost:8001/v1/conversations/queue \
  -H "Content-Type: application/json" \
  -d "{
    \"user_message\": $USER_MSG_ESCAPED,
    \"user_message_clean\": $(echo "$USER_MSG_CLEAN" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))"),
    \"assistant_message\": $ASSISTANT_MSG_ESCAPED,
    \"project_name\": \"$PROJECT_NAME\",
    \"session_id\": \"$SESSION_TAG\",
    \"timestamp\": \"$TIMESTAMP\"
  }" 2>&1)
```

**Step 6: Test with real conversation**

```bash
# Create new Claude Code session and type: "test_clean_title_2025"
# Wait 5 seconds for hook to fire
# Check logs
tail -20 /tmp/hook-stop-output.log
```

**Expected:** Log shows "✓ Queued: <message_id>" without errors

**Step 7: Commit backend changes**

```bash
cd /home/giak/Work/MnemoLite
git add scripts/save-conversation-from-hook.sh tests/test-clean-user-message.sh
git commit -m "feat(backend): Add user message cleaning to remove system tag pollution

- Add clean_user_message() function using sed regex
- Remove <ide_opened_file>, <system-reminder>, <command-message> tags
- Extract first real text line (max 100 chars) for clean titles
- Keep raw message for full content preservation
- Add test suite with 4 test cases (all passing)

Fixes conversation title pollution in UI (e.g., 'test_fix_2025' instead of '<ide_opened_file>...')
"
```

---

## Task 2: API - Handle user_message_clean Field

**Context:** The API endpoint `/v1/conversations/queue` and `/v1/conversations/save` need to accept the new `user_message_clean` field and use it for title generation.

**Files:**
- Modify: `/home/giak/Work/MnemoLite/api/routes/conversations_routes.py`

**Step 1: Add user_message_clean parameter to queue endpoint**

Modify the `/queue` endpoint (around line 310):

```python
@router.post("/queue")
async def queue_conversation(
    user_message: str = Body(...),
    user_message_clean: str = Body(default=""),  # ← NEW: Cleaned message for title
    assistant_message: str = Body(...),
    project_name: str = Body(...),
    session_id: str = Body(...),
    timestamp: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """
    Queue a conversation to Redis Streams for async processing by worker.
    """
    try:
        import redis

        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=False)

        ts = timestamp or datetime.now().isoformat()

        # Use cleaned message for title, fallback to raw if empty
        clean_msg = user_message_clean.strip() if user_message_clean else user_message[:100]

        stream_name = "conversations:autosave"
        message_id = r.xadd(
            stream_name,
            {
                b"user_message": user_message.encode('utf-8'),
                b"user_message_clean": clean_msg.encode('utf-8'),  # ← NEW
                b"assistant_message": assistant_message.encode('utf-8'),
                b"project_name": project_name.encode('utf-8'),
                b"session_id": session_id.encode('utf-8'),
                b"timestamp": ts.encode('utf-8')
            }
        )

        return {
            "success": True,
            "message_id": message_id.decode(),
            "queued": True,
            "project_name": project_name
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis queue unavailable: {str(e)}")
```

**Step 2: Add user_message_clean parameter to save endpoint**

Modify the `/save` endpoint (around line 389):

```python
@router.post("/save")
async def save_conversation(
    user_message: str = Body(...),
    user_message_clean: str = Body(default=""),  # ← NEW
    assistant_message: str = Body(...),
    project_name: str = Body(...),
    session_id: str = Body(...),
    timestamp: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """
    Save a single conversation from hook (NOT auto-import).
    Called by worker after dequeuing from Redis.
    """
    # ... existing code ...

    # Use cleaned message for title
    clean_msg = user_message_clean.strip() if user_message_clean else user_message[:100]
    title = f"Conv: {clean_msg[:100]}"

    # ... rest of save logic ...
```

**Step 3: Update worker to pass user_message_clean**

Modify `/home/giak/Work/MnemoLite/workers/conversation_worker.py` process_message method (around line 230):

```python
response = await self._http_client.post(
    f"{self.api_url}/v1/conversations/save",
    json={
        "user_message": message.user_message,
        "user_message_clean": message.user_message_clean,  # ← NEW: Pass through
        "assistant_message": message.assistant_message,
        "project_name": message.project_name,
        "session_id": message.session_id,
        "timestamp": message.timestamp
    }
)
```

**Step 4: Update ConversationMessage dataclass**

Modify `/home/giak/Work/MnemoLite/workers/conversation_worker.py` dataclass (around line 45):

```python
@dataclass
class ConversationMessage:
    """Message consumed from Redis Stream."""
    user_message: str
    user_message_clean: str  # ← NEW: Cleaned message for title
    assistant_message: str
    project_name: str
    session_id: str
    timestamp: str
    stream_id: str
```

**Step 5: Update message parsing in worker**

Modify the `_parse_redis_message` method (around line 120):

```python
def _parse_redis_message(self, redis_msg: Dict[bytes, bytes], stream_id: str) -> ConversationMessage:
    """Parse Redis Stream message into ConversationMessage."""
    return ConversationMessage(
        user_message=redis_msg[b'user_message'].decode('utf-8'),
        user_message_clean=redis_msg.get(b'user_message_clean', b'').decode('utf-8'),  # ← NEW
        assistant_message=redis_msg[b'assistant_message'].decode('utf-8'),
        project_name=redis_msg[b'project_name'].decode('utf-8'),
        session_id=redis_msg[b'session_id'].decode('utf-8'),
        timestamp=redis_msg[b'timestamp'].decode('utf-8'),
        stream_id=stream_id
    )
```

**Step 6: Test API endpoint directly**

```bash
# Test queue endpoint with cleaned message
curl -X POST http://localhost:8001/v1/conversations/queue \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "<ide_opened_file>test</ide_opened_file>\ntest_api_clean_2025",
    "user_message_clean": "test_api_clean_2025",
    "assistant_message": "Response to test",
    "project_name": "truth-engine",
    "session_id": "test-session",
    "timestamp": "2025-11-16T12:00:00"
  }'
```

**Expected:** JSON response with `"success": true, "queued": true, "message_id": "..."`

**Step 7: Verify in database**

```bash
docker compose -f /home/giak/Work/MnemoLite/docker-compose.yml exec -T db psql -U mnemo -d mnemolite -c "SELECT title, LEFT(content, 100) FROM memories WHERE content LIKE '%test_api_clean_2025%' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Title shows "Conv: test_api_clean_2025" (without `<ide_opened_file>`)

**Step 8: Restart worker to pick up new field**

```bash
cd /home/giak/Work/MnemoLite
docker compose restart worker
docker compose logs -f worker --tail=20
```

**Expected:** Worker restarts cleanly, logs show "Worker started, polling interval: 1.0s"

**Step 9: Commit API changes**

```bash
cd /home/giak/Work/MnemoLite
git add api/routes/conversations_routes.py workers/conversation_worker.py
git commit -m "feat(api): Accept user_message_clean field for title generation

- Add user_message_clean parameter to /queue and /save endpoints
- Update ConversationMessage dataclass with new field
- Update worker to pass cleaned message through pipeline
- Use cleaned message for title, fallback to raw[:100] if empty

Works with backend cleaning function to produce clean titles in UI
"
```

---

## Task 3: Frontend - Add Infinite Scroll to Composable

**Context:** The `useMemories.ts` composable currently fetches only 10 conversations (hardcoded). For monitoring passive use, users need to scroll through hundreds of conversations without pagination clicks.

**Files:**
- Modify: `/home/giak/Work/MnemoLite/frontend/src/composables/useMemories.ts`

**Step 1: Add infinite scroll state variables**

Modify the composable (after line 27):

```typescript
// State
const data = ref<MemoriesData>({
  stats: null,
  recentMemories: [],
  codeChunks: null,
  embeddingsHealth: null
})

const loading = ref(false)
const errors = ref<MemoriesError[]>([])
const lastUpdated = ref<Date | null>(null)

// ← NEW: Infinite scroll state
const loadingMore = ref(false)
const hasMore = ref(true)
const offset = ref(0)
const pageSize = 20  // Load 20 at a time
```

**Step 2: Modify fetchRecentMemories to support offset**

Replace the existing `fetchRecentMemories` function (lines 50-67):

```typescript
// Fetch recent memories (with offset for infinite scroll)
async function fetchRecentMemories(limit: number = pageSize, append: boolean = false): Promise<void> {
  try {
    const currentOffset = append ? offset.value : 0
    const response = await fetch(`${API_BASE_URL}/recent?limit=${limit}&offset=${currentOffset}`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    const newMemories = await response.json()

    if (append) {
      // Append to existing list (infinite scroll)
      data.value.recentMemories.push(...newMemories)
      offset.value += newMemories.length
    } else {
      // Replace list (initial load or refresh)
      data.value.recentMemories = newMemories
      offset.value = newMemories.length
    }

    // Check if we have more to load
    hasMore.value = newMemories.length === limit
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Unknown error'
    errors.value.push({
      endpoint: 'recent',
      message: errorMsg,
      timestamp: new Date().toISOString()
    })
    console.error('Failed to fetch recent memories:', error)
  }
}
```

**Step 3: Add loadMore function**

Add this function after `fetchRecentMemories`:

```typescript
// Load more memories for infinite scroll
async function loadMore(): Promise<void> {
  if (loadingMore.value || !hasMore.value) return

  loadingMore.value = true
  await fetchRecentMemories(pageSize, true)  // append = true
  loadingMore.value = false
}
```

**Step 4: Modify refresh to reset offset**

Update the `refresh` function (around line 108):

```typescript
async function refresh(): Promise<void> {
  loading.value = true
  errors.value = [] // Clear previous errors
  offset.value = 0  // ← NEW: Reset offset on manual refresh
  hasMore.value = true  // ← NEW: Reset hasMore flag

  // Fetch all endpoints in parallel
  await Promise.all([
    fetchStats(),
    fetchRecentMemories(pageSize, false),  // ← Changed: append = false
    fetchCodeChunks(),
    fetchEmbeddingsHealth()
  ])

  loading.value = false
  lastUpdated.value = new Date()
}
```

**Step 5: Export new functions and state**

Update the return statement (around line 147):

```typescript
return {
  data,
  loading,
  loadingMore,  // ← NEW
  hasMore,      // ← NEW
  errors,
  lastUpdated,
  refresh,
  loadMore      // ← NEW
}
```

**Step 6: Test composable logic manually**

Create a test file to verify logic:

```typescript
// Create: /home/giak/Work/MnemoLite/frontend/src/composables/__tests__/useMemories.test.ts
import { describe, it, expect, vi } from 'vitest'
import { useMemories } from '../useMemories'

describe('useMemories infinite scroll', () => {
  it('should load initial 20 memories', async () => {
    // Mock fetch to return 20 memories
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(Array(20).fill({ id: 'test' }))
      })
    ) as any

    const { data, refresh } = useMemories()
    await refresh()

    expect(data.value.recentMemories.length).toBe(20)
  })

  it('should append more memories on loadMore', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(Array(20).fill({ id: 'test' }))
      })
    ) as any

    const { data, loadMore, refresh } = useMemories()
    await refresh()
    await loadMore()

    expect(data.value.recentMemories.length).toBe(40)
  })

  it('should set hasMore to false when fewer than pageSize returned', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(Array(5).fill({ id: 'test' }))  // Only 5 returned
      })
    ) as any

    const { hasMore, refresh } = useMemories()
    await refresh()

    expect(hasMore.value).toBe(false)
  })
})
```

**Step 7: Run tests**

```bash
cd /home/giak/Work/MnemoLite/frontend
npm run test useMemories.test.ts
```

**Expected:** All 3 tests PASS

**Step 8: Commit composable changes**

```bash
cd /home/giak/Work/MnemoLite
git add frontend/src/composables/useMemories.ts frontend/src/composables/__tests__/useMemories.test.ts
git commit -m "feat(frontend): Add infinite scroll support to useMemories composable

- Add offset, hasMore, loadingMore state
- Modify fetchRecentMemories to support append mode
- Add loadMore() function for infinite scroll
- Reset offset on manual refresh
- Change default page size from 10 to 20
- Add unit tests for infinite scroll logic

Enables ConversationsWidget to load more on scroll
"
```

---

## Task 4: Frontend - Implement Scroll Detection in Widget

**Context:** The `ConversationsWidget.vue` component needs to detect when the user scrolls near the bottom of the conversations list and trigger `loadMore()`.

**Files:**
- Modify: `/home/giak/Work/MnemoLite/frontend/src/components/ConversationsWidget.vue`

**Step 1: Add scroll event listener**

Modify the `<script setup>` section (after line 65):

```typescript
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Memory } from '@/types/memories'

interface Props {
  memories: Memory[]
  loadingMore?: boolean  // ← NEW: Loading state for infinite scroll
  hasMore?: boolean      // ← NEW: Whether more memories available
}

const props = defineProps<Props>()

// Emit events
const emit = defineEmits<{
  'view-detail': [id: string]
  'load-more': []  // ← NEW: Emitted when user scrolls near bottom
}>()

// ← NEW: Ref to scrollable container
const scrollContainer = ref<HTMLElement | null>(null)

// ← NEW: Scroll handler for infinite scroll
function handleScroll() {
  if (!scrollContainer.value || !props.hasMore || props.loadingMore) return

  const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value

  // Trigger loadMore when 200px from bottom
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  if (distanceFromBottom < 200) {
    emit('load-more')
  }
}

// ← NEW: Lifecycle - attach/detach scroll listener
onMounted(() => {
  if (scrollContainer.value) {
    scrollContainer.value.addEventListener('scroll', handleScroll)
  }
})

onUnmounted(() => {
  if (scrollContainer.value) {
    scrollContainer.value.removeEventListener('scroll', handleScroll)
  }
})
```

**Step 2: Update template to attach ref and display loading state**

Modify the template section (lines 82-143):

```vue
<template>
  <div class="scada-panel h-full">
    <!-- Header avec LED -->
    <div class="flex items-center gap-3 mb-4 pb-3 border-b-2 border-slate-700">
      <span class="scada-led scada-led-cyan"></span>
      <h2 class="text-lg scada-label text-cyan-400">
        Recent Conversations
      </h2>
    </div>

    <!-- Empty State -->
    <div v-if="memories.length === 0" class="text-gray-400 text-sm text-center py-8 font-mono uppercase">
      No Conversations Found
    </div>

    <!-- Conversations List (scrollable with ref) -->
    <div
      v-else
      ref="scrollContainer"
      class="space-y-3 overflow-y-auto h-full"
    >
      <div
        v-for="memory in memories"
        :key="memory.id"
        class="border-2 border-slate-600 rounded p-3 hover:bg-slate-700 transition-colors"
      >
        <!-- Existing conversation card content (unchanged) -->
        <div class="flex items-center justify-between text-xs text-gray-400 mb-2 font-mono">
          <span>{{ formatFullDate(memory.created_at) }}</span>
          <span class="uppercase">{{ memory.author || 'Unknown' }}</span>
        </div>

        <div class="text-sm text-gray-200 mb-2 font-medium line-clamp-2">
          <span class="text-cyan-400">{{ getMemoryTypeLabel(memory.memory_type) }}</span>
          {{ memory.title }}
        </div>

        <div v-if="memory.project_name || memory.project_id" class="text-xs text-cyan-400 mb-2 flex items-center gap-1">
          <span>📁</span>
          <span class="uppercase font-mono">{{ memory.project_name || memory.project_id }}</span>
        </div>

        <div class="flex flex-wrap gap-1 mb-2">
          <span
            v-for="tag in memory.tags.filter(t => !t.startsWith('session:') && !t.startsWith('date:')).slice(0, 3)"
            :key="tag"
            class="text-xs px-2 py-0.5 bg-slate-600 text-gray-300 rounded border border-slate-500 font-mono"
          >
            {{ tag }}
          </span>
          <span
            v-if="memory.tags.filter(t => !t.startsWith('session:') && !t.startsWith('date:')).length > 3"
            class="text-xs px-2 py-0.5 text-gray-400 font-mono"
          >
            +{{ memory.tags.filter(t => !t.startsWith('session:') && !t.startsWith('date:')).length - 3 }}
          </span>
          <span class="text-xs px-2 py-0.5 bg-slate-700 text-cyan-400 rounded border border-cyan-700 font-mono uppercase">
            session:{{ extractSessionId(memory.tags) }}
          </span>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="scada-led" :class="memory.has_embedding ? 'scada-led-green' : 'scada-led-yellow'"></span>
            <span class="text-xs font-mono uppercase" :class="memory.has_embedding ? 'scada-status-healthy' : 'scada-status-warning'">
              {{ memory.has_embedding ? 'Embedded' : 'No Embedding' }}
            </span>
          </div>
          <button
            class="scada-btn scada-btn-primary text-xs px-3 py-1"
            @click="emit('view-detail', memory.id)"
          >
            View
          </button>
        </div>
      </div>

      <!-- ← NEW: Loading indicator at bottom -->
      <div v-if="loadingMore" class="text-center py-4">
        <span class="scada-led scada-led-yellow animate-pulse"></span>
        <span class="text-sm font-mono text-cyan-400 ml-2">LOADING MORE...</span>
      </div>

      <!-- ← NEW: End of list indicator -->
      <div v-else-if="!hasMore && memories.length > 0" class="text-center py-4">
        <span class="text-xs font-mono text-gray-500 uppercase">— End of Conversations —</span>
      </div>
    </div>
  </div>
</template>
```

**Step 3: Update parent page to pass props and handle event**

Modify `/home/giak/Work/MnemoLite/frontend/src/pages/Memories.vue` (around line 80):

```vue
<ConversationsWidget
  :memories="data.recentMemories"
  :loading-more="loadingMore"
  :has-more="hasMore"
  @view-detail="handleViewDetail"
  @load-more="loadMore"
/>
```

**Step 4: Update parent page script to import loadMore**

Modify the script section (around line 15):

```typescript
// Use memories composable with 30-second refresh
const { data, loading, loadingMore, hasMore, errors, lastUpdated, refresh, loadMore } = useMemories({
  refreshInterval: 30000
})
```

**Step 5: Test scroll behavior manually**

```bash
# Start dev server
cd /home/giak/Work/MnemoLite/frontend
npm run dev

# Open http://localhost:3000/memories
# Scroll down in ConversationsWidget
# Expected: "LOADING MORE..." appears when 200px from bottom
# Expected: New conversations append to list
```

**Step 6: Verify network requests**

Open browser DevTools Network tab:
- Initial load: `GET /api/v1/memories/recent?limit=20&offset=0`
- After scroll: `GET /api/v1/memories/recent?limit=20&offset=20`
- After scroll again: `GET /api/v1/memories/recent?limit=20&offset=40`

**Step 7: Commit widget changes**

```bash
cd /home/giak/Work/MnemoLite
git add frontend/src/components/ConversationsWidget.vue frontend/src/pages/Memories.vue
git commit -m "feat(frontend): Implement infinite scroll in ConversationsWidget

- Add scroll event listener to detect bottom proximity (200px threshold)
- Emit 'load-more' event when user scrolls near bottom
- Display 'LOADING MORE...' indicator during fetch
- Display 'End of Conversations' when hasMore=false
- Connect to useMemories loadMore() function
- Pass loadingMore and hasMore props from parent page

UX: Users can now scroll through hundreds of conversations without pagination
"
```

---

## Task 5: API - Add Offset Parameter to /recent Endpoint

**Context:** The frontend now sends `offset` parameter, but the API `/api/v1/memories/recent` endpoint doesn't support it yet.

**Files:**
- Modify: `/home/giak/Work/MnemoLite/api/routes/memories_routes.py`

**Step 1: Find the /recent endpoint**

```bash
grep -n "def.*recent" /home/giak/Work/MnemoLite/api/routes/memories_routes.py
```

**Expected:** Shows line number of the function (e.g., line 150)

**Step 2: Add offset parameter**

Modify the endpoint signature and query:

```python
@router.get("/recent")
async def get_recent_memories(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),  # ← NEW: Offset for pagination
    session: AsyncSession = Depends(get_session)
) -> List[MemoryResponse]:
    """
    Get recent memories ordered by creation date.

    Args:
        limit: Maximum number of memories to return (1-100)
        offset: Number of memories to skip (for infinite scroll)
        session: Database session

    Returns:
        List of recent memories
    """
    query = (
        select(Memory)
        .where(Memory.deleted_at.is_(None))
        .order_by(Memory.created_at.desc())
        .limit(limit)
        .offset(offset)  # ← NEW: Apply offset
    )

    result = await session.execute(query)
    memories = result.scalars().all()

    return [MemoryResponse.from_orm(m) for m in memories]
```

**Step 3: Test offset parameter**

```bash
# Test offset=0 (first page)
curl -s "http://localhost:8001/api/v1/memories/recent?limit=5&offset=0" | jq -r '.[].created_at'

# Test offset=5 (second page)
curl -s "http://localhost:8001/api/v1/memories/recent?limit=5&offset=5" | jq -r '.[].created_at'

# Test offset=10 (third page)
curl -s "http://localhost:8001/api/v1/memories/recent?limit=5&offset=10" | jq -r '.[].created_at'
```

**Expected:** Each request returns different timestamps in descending order

**Step 4: Verify no duplicates across pages**

```bash
# Fetch 2 pages and check for duplicates
PAGE1=$(curl -s "http://localhost:8001/api/v1/memories/recent?limit=10&offset=0" | jq -r '.[].id')
PAGE2=$(curl -s "http://localhost:8001/api/v1/memories/recent?limit=10&offset=10" | jq -r '.[].id')

# Check if any IDs appear in both pages
comm -12 <(echo "$PAGE1" | sort) <(echo "$PAGE2" | sort)
```

**Expected:** Empty output (no duplicates)

**Step 5: Commit API changes**

```bash
cd /home/giak/Work/MnemoLite
git add api/routes/memories_routes.py
git commit -m "feat(api): Add offset parameter to /recent endpoint for pagination

- Add offset query parameter (default 0, min 0)
- Apply offset to SQL query for infinite scroll support
- Update docstring with offset description

Works with frontend infinite scroll implementation
"
```

---

## Task 6: Integration Testing - End-to-End Validation

**Context:** All components are now integrated. Validate the complete flow: backend cleaning → API → worker → DB → frontend infinite scroll.

**Files:**
- No file changes, testing only

**Step 1: Create test conversation with pollution**

```bash
# In a new Claude Code session in truth-engine project, type:
# "<ide_opened_file>...</ide_opened_file>
# test_e2e_clean_scroll_2025"
# Wait 5 seconds, then close session
```

**Step 2: Verify hook executed**

```bash
tail -5 /tmp/hook-stop-output.log
```

**Expected:** Shows "✓ Queued: <message_id>"

**Step 3: Verify worker processed**

```bash
cd /home/giak/Work/MnemoLite
docker compose logs worker --tail=20
```

**Expected:** Shows `"msg_id": "...", "project": "truth-engine", "event": "message_processed"`

**Step 4: Verify DB has clean title**

```bash
docker compose exec -T db psql -U mnemo -d mnemolite -c "SELECT title FROM memories WHERE content LIKE '%test_e2e_clean_scroll_2025%' ORDER BY created_at DESC LIMIT 1;"
```

**Expected:** Title shows "Conv: test_e2e_clean_scroll_2025" (without `<ide_opened_file>`)

**Step 5: Verify API returns clean title**

```bash
MEMORY_ID=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "SELECT id FROM memories WHERE content LIKE '%test_e2e_clean_scroll_2025%' ORDER BY created_at DESC LIMIT 1;" | xargs)
curl -s "http://localhost:8001/api/v1/memories/$MEMORY_ID" | jq -r '.title'
```

**Expected:** "Conv: test_e2e_clean_scroll_2025"

**Step 6: Test infinite scroll in UI**

```bash
# Open http://localhost:3000/memories in browser
# Open DevTools Network tab
# Scroll down in ConversationsWidget
# Observe network requests
```

**Expected:**
- Initial load: `GET /recent?limit=20&offset=0` → 20 memories
- Scroll to bottom: `GET /recent?limit=20&offset=20` → Next 20 memories
- List shows "LOADING MORE..." during fetch
- New memories append smoothly
- Find "test_e2e_clean_scroll_2025" with clean title

**Step 7: Verify no regressions**

Test existing functionality:
- Click "View" on conversation → Modal opens with full content
- Click "REFRESH" button → List resets to top 20
- Auto-refresh every 30s → New conversations appear at top

**Expected:** All existing features work unchanged

**Step 8: Performance check**

```bash
# Check DB query performance with offset
docker compose exec -T db psql -U mnemo -d mnemolite -c "EXPLAIN ANALYZE SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 20 OFFSET 100;"
```

**Expected:** Query executes in <10ms (index on `created_at` exists)

**Step 9: Create test report**

```markdown
# Create: /home/giak/Work/MnemoLite/docs/plans/2025-11-16-ui-content-filtering-test-report.md

# E2E Test Report - UI Content Filtering & Infinite Scroll

**Date:** 2025-11-16
**Tested By:** Claude Code
**Features:** Clean titles, Infinite scroll

## Test Results

### ✅ Backend Cleaning
- [x] `<ide_opened_file>` removed from titles
- [x] `<system-reminder>` removed from titles
- [x] First real text extracted correctly
- [x] 100 char limit enforced

### ✅ API Integration
- [x] `/queue` accepts `user_message_clean`
- [x] `/save` uses cleaned message for title
- [x] Worker passes cleaned message through
- [x] `/recent` supports offset parameter

### ✅ Frontend Infinite Scroll
- [x] Initial load: 20 conversations
- [x] Scroll detection: 200px threshold works
- [x] Load more: Appends next 20
- [x] Loading indicator appears during fetch
- [x] "End of Conversations" shows when hasMore=false
- [x] No duplicate conversations across pages

### ✅ Performance
- [x] Query time: <10ms with offset=100
- [x] UI smooth scroll (no jank)
- [x] Worker processing: ~60ms per message

### 🎯 Manual Test Case: "test_e2e_clean_scroll_2025"
- Input: `<ide_opened_file>...</ide_opened_file>\ntest_e2e_clean_scroll_2025`
- Expected title: "Conv: test_e2e_clean_scroll_2025"
- Actual title: "Conv: test_e2e_clean_scroll_2025"
- Result: ✅ PASS

## Conclusion
All features working as designed. Ready for production.
```

**Step 10: Final commit**

```bash
cd /home/giak/Work/MnemoLite
git add docs/plans/2025-11-16-ui-content-filtering-test-report.md
git commit -m "test: E2E validation for UI content filtering & infinite scroll

- Validated backend cleaning removes system tags
- Verified API accepts and uses user_message_clean field
- Confirmed worker processes cleaned messages
- Tested frontend infinite scroll (20 per page, smooth append)
- Performance check: DB queries <10ms at offset=100
- Manual test case 'test_e2e_clean_scroll_2025' passed

All features working as designed, no regressions
"
```

---

## Summary

**Total Tasks:** 6
**Estimated Time:** 90-120 minutes
**Files Modified:** 7
**Tests Added:** 2 (bash script + vitest)

**Key Changes:**
1. Backend: `clean_user_message()` function removes XML tags, extracts first real text
2. API: New `user_message_clean` field in queue/save endpoints
3. Worker: Updated dataclass and parsing to handle cleaned messages
4. Frontend Composable: Infinite scroll with offset/hasMore/loadMore
5. Frontend Widget: Scroll detection, loading states, event emission
6. API Endpoint: `/recent` now supports offset parameter

**Quality Gates:**
- ✅ All tests pass (bash + vitest)
- ✅ E2E validation successful
- ✅ No regressions in existing features
- ✅ Performance verified (<10ms queries)

**DRY/YAGNI Compliance:**
- Cleaning logic centralized in single bash function
- No over-engineering (simple sed regex, not full XML parser)
- Infinite scroll uses standard offset pagination (no complex cursor logic)
- Reused existing API patterns and composable structure

**Ready for Production:** Yes, after all tests pass.
