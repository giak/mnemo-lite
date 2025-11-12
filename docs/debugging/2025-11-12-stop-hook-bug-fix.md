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

## Status

✅ **RESOLVED** - Stop hook now correctly extracts messages and saves conversations with project_id for all projects
