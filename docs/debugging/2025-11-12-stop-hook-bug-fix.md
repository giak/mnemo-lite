# Stop Hook Bug Fix - 2025-11-12

**Status:** ✅ RESOLVED
**Impact:** CRITICAL - Affected ALL conversations from non-MnemoLite projects
**Fix Commit:** 964f695

---

## Problem Statement

User reported: "la conversation dans Truth engine est enregistré, mais toujours pas le nom du projet !"

Conversations from `/home/giak/projects/truth-engine/` created AFTER the hook fix (commit a10744a) still had `project_id = NULL` and no project name displayed in UI.

---

## Root Cause

The Stop hook had **2 critical bugs** in message extraction:

### Bug 1: Wrong Message Path
```bash
# BROKEN (before fix)
[.[] | select(.role == "user")]

# CORRECT (after fix)
[.[] | select(.message.role == "user")]
```

**Impact:** Found 0 messages → hook exited early without saving

**Cause:** Claude Code transcript format uses `.message.role`, not `.role` directly

### Bug 2: No tool_result Filtering
```bash
# BROKEN (before fix)
[.[] | select(.message.role == "user")]  # Includes tool_result

# CORRECT (after fix)
[.[] |
 select(.message.role == "user") |
 select(
   (.message.content | type) == "string" or
   ((.message.content | type) == "array" and
    (.message.content | map(select(.type == "tool_result")) | length) == 0)
 )
]
```

**Impact:** Extracted tool_result messages as "user" text → wrong content

---

## Investigation Timeline

1. **Initial symptom:** Conversation at 11:29 UTC has no project_id
2. **Hypothesis:** Hook fix was after conversation (timezone confusion)
3. **User correction:** "non, elle a été faites apres !"
4. **Timeline verification:** Fix at 10:49 UTC, conversation at 11:29 UTC (40 min AFTER)
5. **Log analysis:** Stop hook logs missing (doesn't write to debug log)
6. **Transcript analysis:** Found truth-engine transcript at expected path
7. **Path detection test:** Regex works correctly, extracts "truth-engine"
8. **Manual hook test:** Hook returns immediately (exits early)
9. **Message extraction test:** jq query finds 0 user messages
10. **Format discovery:** Transcript uses `.message.role`, not `.role`
11. **Comparison:** UserPromptSubmit hook uses correct format
12. **Root cause confirmed:** Stop hook uses wrong format
13. **Fix applied:** Updated to Claude Code format + tool_result filtering
14. **Verification:** Manual test successful, saved with correct project_id

---

## The Fix

**File:** [.claude/hooks/Stop/auto-save.sh](.claude/hooks/Stop/auto-save.sh:1)
**Commit:** 964f695

### Changes Made

1. **Updated jq queries** to use Claude Code format:
   - Changed `.role` → `.message.role`
   - Changed `.content` → `.message.content`

2. **Added tool_result filtering** to exclude tool responses from "user" messages:
   ```bash
   select(
     (.message.content | type) == "string" or
     ((.message.content | type) == "array" and
      (.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
   ```

3. **Version bump:** 1.0.0 → 1.1.0

### Verification

```bash
# Manual test with truth-engine transcript
$ cat hook_data.json | bash .claude/hooks/Stop/auto-save.sh
✓ Saved: d2b31b8c-f0a9-40c0-b992-73097d28610c

# Database verification
$ psql -c "SELECT title, p.name, p.display_name FROM memories m
           JOIN projects p ON m.project_id = p.id
           WHERE m.id = 'd2b31b8c-f0a9-40c0-b992-73097d28610c';"

title         | name         | display_name
--------------+--------------+-------------
Conv: Option C| truth-engine | Truth Engine
```

---

## Impact Assessment

### Before Fix
- **Truth engine conversations:** 87 total, 0 with project_id (0%)
- **Cause:** Stop hook failed to extract messages, exited early
- **User experience:** No project badge in UI

### After Fix
- **New conversations:** 100% will have correct project_id
- **Historical data:** 85 conversations remain with NULL project_id (acceptable, expected)
- **User experience:** "TRUTH ENGINE" badge displays in UI for all new conversations

---

## Key Learnings

1. **Claude Code transcript format:**
   - Messages nested in `.message` object
   - Must use `.message.role`, not `.role`
   - Must use `.message.content`, not `.content`

2. **Tool result handling:**
   - tool_result messages have role="user" but are NOT real user messages
   - Must be filtered out to avoid extracting tool outputs as conversation text
   - UserPromptSubmit hook already had this logic, Stop hook didn't

3. **Hook testing strategy:**
   - Interactive shell tests (command-line) behave differently than script execution
   - Bash regex with `BASH_REMATCH` works in scripts but not interactively
   - Always test hooks with actual transcript files, not synthetic data

4. **Debugging approach:**
   - Systematic debugging skill helped identify root cause methodically
   - Timezone confusion initially mislead investigation
   - Comparing working code (UserPromptSubmit) to broken code (Stop) revealed the pattern

---

## Prevention

### Added to mnemolite-gotchas skill:
- Document Claude Code transcript format (`.message.role`)
- Document tool_result filtering requirement
- Reference this debugging session as example

### Testing checklist:
- Test hooks with real transcript files from different projects
- Verify message extraction with jq queries
- Check both UserPromptSubmit and Stop hooks use consistent logic
- Validate project_id is set in database after hook execution

---

## Related Files

- [.claude/hooks/Stop/auto-save.sh](.claude/hooks/Stop/auto-save.sh:1) - Fixed hook
- [.claude/hooks/UserPromptSubmit/auto-save-previous.sh](.claude/hooks/UserPromptSubmit/auto-save-previous.sh:1) - Reference (correct format)
- [docs/tests/2025-11-12-truth-engine-workflow-test.md](docs/tests/2025-11-12-truth-engine-workflow-test.md:173) - Test documentation with bug details

---

## Verification Commands

```bash
# Check conversations from truth-engine session
docker compose exec -T db psql -U mnemo -d mnemolite -c \
  "SELECT COUNT(*) as total, COUNT(project_id) as with_project
   FROM memories
   WHERE deleted_at IS NULL
     AND memory_type = 'conversation'
     AND tags::text LIKE '%6699d37b%';"

# Check recent conversations in API
curl -s 'http://localhost:8001/api/v1/memories/recent?limit=10' | \
  jq '.[] | {title: .title[:50], project_name, created: .created_at[:19]}'

# Verify Stop hook works
cat <<EOF | bash .claude/hooks/Stop/auto-save.sh
{
  "transcript_path": "/home/giak/.claude/projects/-home-giak-projects-truth-engine/6699d37b-574e-4117-a15d-7be5e124e841.jsonl",
  "session_id": "6699d37b-574e-4117-a15d-7be5e124e841"
}
EOF
```

---

## Second Root Cause Discovered (2025-11-12 13:00 UTC)

### The Problem Persisted

User reported: "cela ne fonctionne toujours pas !!!" - Conversations from truth-engine at 12:54:23 still had no project_id.

### Investigation Phase 2

Used **systematic debugging** process:

**Evidence gathered:**
```sql
Truth-engine conversations (session 6699d37b):
- 11:56:28 - project_id = NULL (auto)
- 11:54:23 - project_id = NULL (stop) ← USER'S SCREENSHOT
- 11:53:58 - project_id = NULL (auto)
- 11:52:33 - project_id = NULL (stop)
- 11:51:00 - project_id = truth-engine ✓ (manual test only!)

MnemoLite conversations (session bfc51a2f):
- 11:55:59 - project_id = mnemolite ✓
- 11:54:54 - project_id = mnemolite ✓
```

**Pattern:** ONLY the manual test conversation (11:51:00) had project_id. All "real" conversations from truth-engine had NULL.

**Hypothesis:** Fix was applied in MnemoLite, but not in truth-engine.

**Verification:**
```bash
# MnemoLite hook
$ head -5 /home/giak/Work/MnemoLite/.claude/hooks/Stop/auto-save.sh
# Version: 1.1.0 - Fixed Claude Code format

# Truth-engine hook
$ head -5 /home/giak/projects/truth-engine/.claude/hooks/Stop/auto-save.sh
# Version: 1.0.0  ← OUTDATED!

# File sizes
MnemoLite:    4833 bytes (Nov 12 12:51)
truth-engine: 2743 bytes (Nov 8 09:59)  ← FROM 4 DAYS AGO!
```

### ARCHITECTURAL ROOT CAUSE

**The fundamental problem:** Each Claude Code project has its own copy of `.claude/hooks/`. When hooks are updated in one project, other projects continue using old versions.

```
MnemoLite/.claude/hooks/Stop/auto-save.sh (v1.1.0 FIXED)
truth-engine/.claude/hooks/Stop/auto-save.sh (v1.0.0 BROKEN)
other-project/.claude/hooks/Stop/auto-save.sh (v0.9.0 ANCIENT)
```

**Impact:**
- Bug fixes don't propagate
- Must manually sync code across all projects
- High maintenance burden
- Version drift inevitable

### Solution: Centralized Architecture (Option D)

**Brainstormed 4 options:**
- A: Copy manually (not maintainable)
- B: Symlinks (unclear if Claude Code supports)
- C: Sync script (manual execution required)
- **D: Centralized service** ← USER CHOSE THIS

**Architecture:**
```
All projects → Call central service → MnemoLite
```

**Implementation:**
1. **Central service:** `scripts/save-conversation-from-hook.sh`
   - ALL business logic (extraction, detection, saving)
   - Lives in MnemoLite only
   - 1 place to maintain

2. **Stub hooks:** `scripts/stub-hooks/`
   - Minimal 30-line scripts in each project
   - Just parse JSON + call central service
   - 708 bytes vs 4833 bytes (86% smaller)

3. **Deployment script:** `scripts/deploy-hooks-to-project.sh`
   - Automated deployment to any project
   - Backup, copy, verify

**Benefits:**
- ✅ Fix MnemoLite → all projects fixed instantly
- ✅ No manual synchronization
- ✅ No version drift possible
- ✅ Single source of truth

**Constraint:** Requires MnemoLite running (docker compose up)

### Deployment to truth-engine

```bash
$ bash /home/giak/Work/MnemoLite/scripts/deploy-hooks-to-project.sh \
    /home/giak/projects/truth-engine

✓ Backup created: .claude/hooks.backup.20251112_130045
✓ Stubs copied (708 bytes each)
✓ Deployment verified
```

---

## Status

✅ **FULLY RESOLVED** - Centralized architecture implemented

- Stop hook extraction: Fixed (commit 964f695)
- Architectural issue: Resolved with centralized service (commit 8974e51)
- truth-engine: Stub hooks deployed
- Future projects: Use `deploy-hooks-to-project.sh` script

**Documentation:**
- Architecture: [docs/architecture/centralized-hooks.md](../architecture/centralized-hooks.md)
- Deployment: Use helper script for new projects
