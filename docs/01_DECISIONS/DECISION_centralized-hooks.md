# Centralized Hooks Architecture

**Status:** ✅ IMPLEMENTED
**Version:** 1.0.0
**Date:** 2025-11-12

---

## Problem Statement

**Original Issue:** Each Claude Code project has its own copy of `.claude/hooks/`. When hooks are updated in one project (e.g., MnemoLite), other projects (e.g., truth-engine) continue using outdated/broken versions.

**Impact:**
- Bug fixes don't propagate to other projects
- Must manually sync hook code across all projects
- High maintenance burden
- Risk of version drift and inconsistent behavior

---

## Solution: Centralized Service Architecture

**Principle:** Code lives in ONE place (MnemoLite), all projects call the centralized service.

```
┌─────────────────────────────────────────────────────────────┐
│                   MnemoLite (Central Hub)                    │
│                                                              │
│  scripts/save-conversation-from-hook.sh (ALL LOGIC)          │
│    ├─ Message extraction (Stop vs UserPromptSubmit)         │
│    ├─ Project detection (Git-based)                         │
│    ├─ Deduplication (hash-based)                            │
│    └─ Save via MCP write_memory                             │
│                                                              │
│  scripts/stub-hooks/ (Templates for other projects)         │
│    ├─ Stop/auto-save.sh (30 lines)                          │
│    └─ UserPromptSubmit/auto-save-previous.sh (30 lines)     │
└─────────────────────────────────────────────────────────────┘
                           ▲ ▲ ▲
                           │ │ │
        ┌──────────────────┘ │ └──────────────────┐
        │                    │                    │
┌───────┴────────┐  ┌────────┴───────┐  ┌────────┴───────┐
│  truth-engine  │  │   my-project   │  │  other-project │
│                │  │                │  │                │
│  .claude/hooks/│  │  .claude/hooks/│  │  .claude/hooks/│
│  (stubs only)  │  │  (stubs only)  │  │  (stubs only)  │
└────────────────┘  └────────────────┘  └────────────────┘
```

---

## Architecture Components

### 1. Central Service (MnemoLite)

**File:** [`scripts/save-conversation-from-hook.sh`](../../scripts/save-conversation-from-hook.sh)

**Responsibilities:**
- Parse arguments (transcript_path, session_id, hook_type)
- Detect project name from transcript path (Git-based)
- Extract messages based on hook type (stop vs auto)
- Deduplicate using hash
- Save to MnemoLite via Docker + write_memory MCP tool

**Parameters:**
```bash
save-conversation-from-hook.sh \
  <transcript_path> \
  <session_id> \
  <hook_type: "stop" | "auto">
```

**Dependencies:**
- MnemoLite Docker containers running (`docker compose up`)
- Access to `/home/giak/Work/MnemoLite/`
- `jq` for JSON parsing

### 2. Stub Hooks (Other Projects)

**Files:**
- [`scripts/stub-hooks/Stop/auto-save.sh`](../../scripts/stub-hooks/Stop/auto-save.sh) (708 bytes)
- [`scripts/stub-hooks/UserPromptSubmit/auto-save-previous.sh`](../../scripts/stub-hooks/UserPromptSubmit/auto-save-previous.sh) (741 bytes)

**Responsibilities:**
- Read hook data (transcript_path, session_id)
- Call central service with appropriate hook_type
- Return success

**Size comparison:**
- **Old hooks:** 4833 bytes (complex logic, duplicated)
- **New stubs:** 708 bytes (86% smaller, minimal logic)

---

## Deployment Instructions

### For New Projects

1. **Create hook directories:**
   ```bash
   mkdir -p /path/to/project/.claude/hooks/Stop
   mkdir -p /path/to/project/.claude/hooks/UserPromptSubmit
   ```

2. **Copy stub hooks:**
   ```bash
   cp /home/giak/Work/MnemoLite/scripts/stub-hooks/Stop/auto-save.sh \
      /path/to/project/.claude/hooks/Stop/auto-save.sh

   cp /home/giak/Work/MnemoLite/scripts/stub-hooks/UserPromptSubmit/auto-save-previous.sh \
      /path/to/project/.claude/hooks/UserPromptSubmit/auto-save-previous.sh
   ```

3. **Make executable:**
   ```bash
   chmod +x /path/to/project/.claude/hooks/Stop/auto-save.sh
   chmod +x /path/to/project/.claude/hooks/UserPromptSubmit/auto-save-previous.sh
   ```

4. **Verify:**
   ```bash
   head -3 /path/to/project/.claude/hooks/Stop/auto-save.sh
   # Should show: "Version: 1.0.0 - Stub architecture"
   ```

### For Existing Projects (Migration)

1. **Backup old hooks:**
   ```bash
   mkdir -p /path/to/project/.claude/hooks.backup
   cp -r /path/to/project/.claude/hooks/* \
         /path/to/project/.claude/hooks.backup/
   ```

2. **Follow "For New Projects" steps above**

3. **Test:**
   ```bash
   # Simulate hook call
   cat <<EOF | bash /path/to/project/.claude/hooks/Stop/auto-save.sh
   {
     "transcript_path": "/home/user/.claude/projects/-home-user-projects-myproject/session.jsonl",
     "session_id": "test-session-id"
   }
   EOF
   ```

---

## How It Works

### Flow Diagram

```
User works in truth-engine project
  ↓
Claude Code triggers Stop hook
  ↓
truth-engine/.claude/hooks/Stop/auto-save.sh (stub)
  ├─ Reads: transcript_path, session_id
  └─ Calls: MnemoLite central service
      ↓
MnemoLite/scripts/save-conversation-from-hook.sh
  ├─ Detects project: "truth-engine" (from transcript path)
  ├─ Extracts last user + assistant message
  ├─ Checks deduplication hash
  └─ Saves via: docker compose exec → save-direct.py → write_memory
      ↓
PostgreSQL (memories table)
  ├─ project_id: <truth-engine UUID>
  └─ Ready for API/UI display
```

### Message Extraction Logic

**Stop Hook (hook_type="stop"):**
- Extracts **LAST** user message (excluding tool_result)
- Extracts **LAST** assistant message
- Use case: Save conversation when user stops/closes session

**UserPromptSubmit Hook (hook_type="auto"):**
- Extracts **SECOND-TO-LAST** user message
- Extracts **COMPLETE** assistant response between N-2 and N-1
- Use case: Auto-save previous exchange before processing new input

---

## Advantages

### ✅ Maintainability
- **One source of truth:** All logic in MnemoLite
- **Bug fixes propagate instantly:** Update central service → all projects fixed
- **Version control:** Single codebase to track/test

### ✅ Simplicity
- **Minimal project setup:** Copy 2 tiny stub files
- **No project-specific code:** Stubs are identical for all projects
- **Clear separation:** Stubs = entry points, Service = business logic

### ✅ Consistency
- **Same behavior everywhere:** All projects use same extraction/detection logic
- **No version drift:** Can't have outdated hooks in some projects
- **Easier debugging:** One place to add logging/instrumentation

---

## Constraints

### 🔴 MnemoLite Must Be Running
- Central service requires `docker compose up` in MnemoLite
- If MnemoLite is down, conversations won't be saved
- **Mitigation:** MnemoLite runs persistently on development machine

### 🔴 Hardcoded Path
- Stubs reference `/home/giak/Work/MnemoLite/scripts/...`
- Won't work if MnemoLite is moved or on different machine
- **Mitigation:** Environment variable or config file (future enhancement)

### 🔴 No Multi-User Support (Yet)
- Assumes single user (`/home/giak/`)
- Would need path discovery for multi-user setups
- **Mitigation:** Fine for single-developer setup, can enhance later

---

## Testing

### Manual Test

```bash
# Test Stop hook with truth-engine transcript
cat <<'EOF' | bash /home/giak/projects/truth-engine/.claude/hooks/Stop/auto-save.sh
{
  "transcript_path": "/home/giak/.claude/projects/-home-giak-projects-truth-engine/session.jsonl",
  "session_id": "test-session-id"
}
EOF

# Verify in database
docker compose exec -T db psql -U mnemo -d mnemolite -c \
  "SELECT title, p.display_name FROM memories m
   JOIN projects p ON m.project_id = p.id
   WHERE m.created_at >= NOW() - INTERVAL '1 minute'
   ORDER BY m.created_at DESC LIMIT 5;"
```

### Expected Result
```
title               | display_name
--------------------+-------------
Conv: test message  | Truth Engine
```

---

## Troubleshooting

### Problem: Conversations Not Saved

**Symptoms:** No new conversations appear in database after hook triggers

**Diagnosis:**
1. Check MnemoLite is running:
   ```bash
   docker compose ps
   ```

2. Check central service exists:
   ```bash
   ls -l /home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh
   ```

3. Test service directly:
   ```bash
   bash /home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh \
     "/path/to/transcript.jsonl" "test-session" "stop"
   ```

4. Check logs:
   ```bash
   docker compose logs api | grep -i error
   ```

### Problem: Wrong Project Detected

**Symptoms:** Conversations saved with wrong project_name

**Diagnosis:**
1. Test project detection:
   ```bash
   bash /home/giak/Work/MnemoLite/scripts/get-project-name.sh \
     /home/giak/projects/truth-engine
   ```

2. Check Git repository:
   ```bash
   cd /home/giak/projects/truth-engine
   git rev-parse --show-toplevel
   ```

### Problem: Deduplication Issues

**Symptoms:** Conversations not saved (silently skipped)

**Diagnosis:**
1. Check hash file:
   ```bash
   tail -20 /tmp/mnemo-saved-exchanges.txt
   ```

2. Clear hash file (careful!):
   ```bash
   rm /tmp/mnemo-saved-exchanges.txt
   ```

---

## Future Enhancements

### Path Discovery
Replace hardcoded `/home/giak/Work/MnemoLite/` with:
```bash
MNEMOLITE_ROOT="${MNEMOLITE_ROOT:-/home/giak/Work/MnemoLite}"
```

### Multi-User Support
Detect home directory dynamically:
```bash
USER_HOME=$(eval echo ~$(whoami))
MNEMOLITE_ROOT="$USER_HOME/Work/MnemoLite"
```

### Async Processing
Instead of blocking hook execution:
```bash
# Queue save request
echo "$TRANSCRIPT_PATH|$SESSION_ID|$HOOK_TYPE" >> /tmp/mnemo-save-queue

# Background processor consumes queue
# (run via cron or systemd timer)
```

### Health Check
Add central service health endpoint:
```bash
bash /home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh --health
# Returns: OK (MnemoLite running) or ERROR
```

---

## Migration Status

| Project | Status | Date | Notes |
|---------|--------|------|-------|
| MnemoLite | ✅ Central service | 2025-11-12 | Original development |
| truth-engine | ✅ Stub hooks deployed | 2025-11-12 | First migration |
| Other projects | ⏳ Pending | - | Follow deployment instructions |

---

## Related Documentation

- [Stop Hook Bug Fix](../debugging/2025-11-12-stop-hook-bug-fix.md) - Original issue that motivated centralization
- [Truth Engine Workflow Test](../tests/2025-11-12-truth-engine-workflow-test.md) - Testing multi-project detection
- [Project Tools API](../../api/mnemo_mcp/tools/project_tools.py) - Project name resolution logic

---

## Changelog

### v1.0.0 - 2025-11-12
- Initial centralized architecture
- Central service: `save-conversation-from-hook.sh`
- Stub hooks for Stop and UserPromptSubmit
- Deployed to truth-engine project
- Documentation created
