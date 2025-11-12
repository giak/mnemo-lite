# Project Name Detection - Design Document

**Date:** 2025-11-12
**Status:** Validated
**Problem:** MnemoLite hardcodes project names when saving conversations, not scalable for multi-project usage

---

## Problem Statement

Current implementation extracts project name from Claude Code transcript filenames (e.g., `MnemoLite-abc123.jsonl`). This approach fails when MnemoLite is used as an MCP server or via hooks in different projects, because:

1. **Not robust:** Relies on filename format that may change
2. **Not portable:** Doesn't detect project context when run from client projects
3. **Hardcoded fallback:** Uses literal "mnemolite" string as fallback
4. **Not scalable:** Cannot distinguish between different client projects

---

## Solution Overview: Centralized Detection Script

**Architecture:** Script-based detection with cascade fallbacks, called by all components

```
scripts/get-project-name.sh (centralized logic)
    ↓ called by
├── .claude/hooks/UserPromptSubmit/auto-save.sh
├── api/routes/conversations_routes.py (via subprocess)
└── Future: MCP tools, indexing scripts, etc.
```

**Detection Strategy:**
1. **Primary:** Git root directory name (`git rev-parse --show-toplevel`)
2. **Fallback:** Current directory basename (`basename $PWD`)
3. **Normalization:** Convert to lowercase for consistency

---

## Component 1: Detection Script

### File: `scripts/get-project-name.sh`

**Responsibility:** Detect project name from any working directory with robust fallbacks.

**Implementation:**

```bash
#!/bin/bash
# Detect project name with fallback strategy
# Usage: bash scripts/get-project-name.sh [optional_working_directory]
# Output: project name in lowercase (e.g., "mnemolite")

set -euo pipefail

# Use provided directory or current directory
WORK_DIR="${1:-$(pwd)}"
cd "$WORK_DIR" 2>/dev/null || WORK_DIR="$(pwd)"

# Strategy A: Git root directory name (most reliable)
if command -v git >/dev/null 2>&1; then
  GIT_ROOT=$(git -C "$WORK_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
  if [ -n "$GIT_ROOT" ]; then
    basename "$GIT_ROOT" | tr '[:upper:]' '[:lower:]'
    exit 0
  fi
fi

# Strategy B: Current directory basename (fallback)
basename "$WORK_DIR" | tr '[:upper:]' '[:lower:]'
```

**Features:**
- Accepts optional working directory argument
- Always succeeds (fallback guaranteed)
- Portable (works without Git)
- Output: lowercase project name on stdout

---

## Component 2: Hook Integration

### File: `.claude/hooks/UserPromptSubmit/auto-save-previous.sh`

**Modification:** Add project name detection before API call

**Code Addition (after conversation extraction, before API call):**

```bash
# ============================================================================
# 3. DETECT PROJECT NAME
# ============================================================================

# Detect project name using centralized script
# Try multiple locations (portable across projects)
SCRIPT_PATHS=(
  "$PWD/scripts/get-project-name.sh"
  "$PWD/.claude/scripts/get-project-name.sh"
  "$(dirname "$TRANSCRIPT_PATH")/../../scripts/get-project-name.sh"
)

PROJECT_NAME=""
for SCRIPT_PATH in "${SCRIPT_PATHS[@]}"; do
  if [ -f "$SCRIPT_PATH" ]; then
    PROJECT_NAME=$(bash "$SCRIPT_PATH" "$PWD" 2>/dev/null || echo "")
    if [ -n "$PROJECT_NAME" ]; then
      break
    fi
  fi
done

# Fallback if script not found
if [ -z "$PROJECT_NAME" ]; then
  PROJECT_NAME=$(basename "$PWD" | tr '[:upper:]' '[:lower:]')
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Detected project: $PROJECT_NAME" >> /tmp/hook-autosave-debug.log
```

**Modified API Call:**

```bash
curl -s -X POST "$API_URL/api/v1/memories" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "title": "Conv: ${PREV_USER:0:60}...",
  "content": "$CONTENT_ESCAPED",
  "memory_type": "conversation",
  "tags": ["auto-saved", "claude-code", "session:$SESSION_ID"],
  "author": "AutoSave",
  "project_id": "$PROJECT_NAME"
}
EOF
```

---

## Component 3: Auto-Import Integration

### File: `api/routes/conversations_routes.py`

**New Function:** Python wrapper to call bash script

```python
import subprocess
from pathlib import Path
import os

def get_project_name(working_dir: str = None) -> str:
    """
    Detect project name using centralized bash script.

    Args:
        working_dir: Working directory to detect from (default: current dir)

    Returns:
        Project name in lowercase
    """
    if working_dir is None:
        working_dir = os.getcwd()

    # Try to find and execute the detection script
    script_paths = [
        Path(__file__).parent.parent / "scripts" / "get-project-name.sh",
        Path(working_dir) / "scripts" / "get-project-name.sh",
    ]

    for script_path in script_paths:
        if script_path.exists():
            try:
                result = subprocess.run(
                    ["bash", str(script_path), working_dir],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().lower()
            except Exception:
                pass

    # Fallback: use basename of working directory
    return Path(working_dir).name.lower()
```

**Modified `parse_claude_transcripts()`:**

Replace:
```python
project_name = session_id.rsplit('-', 1)[0] if '-' in session_id else session_id
```

With:
```python
project_name = get_project_name(str(transcripts_path.parent))
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test-get-project-name.sh`

```bash
#!/bin/bash
# Test 1: From Git repository
cd /tmp/test-repo && git init
result=$(bash scripts/get-project-name.sh)
[ "$result" = "test-repo" ] && echo "✅ Test 1 passed" || echo "❌ Test 1 failed"

# Test 2: From non-Git directory
cd /tmp/standalone-project
result=$(bash scripts/get-project-name.sh)
[ "$result" = "standalone-project" ] && echo "✅ Test 2 passed" || echo "❌ Test 2 failed"

# Test 3: With explicit path argument
result=$(bash scripts/get-project-name.sh /home/user/MyApp)
[ "$result" = "myapp" ] && echo "✅ Test 3 passed" || echo "❌ Test 3 failed"
```

### Integration Tests

1. Create conversation in MnemoLite project → Verify `project_id = "mnemolite"`
2. Create conversation in another project → Verify correct project name
3. Run from subdirectory → Verify Git root is used (not subdirectory name)

---

## Migration Plan

### Existing Data

**Optional SQL migration** for conversations with `project_id = null`:

```sql
UPDATE memories
SET project_id = 'mnemolite'
WHERE project_id IS NULL
  AND author IN ('AutoSave', 'AutoImport')
  AND tags @> ARRAY['claude-code'];
```

---

## Deployment Checklist

1. ✅ Create `scripts/get-project-name.sh` with `chmod +x`
2. ✅ Test script independently: `bash scripts/get-project-name.sh`
3. ✅ Modify `.claude/hooks/UserPromptSubmit/auto-save-previous.sh`
4. ✅ Add `get_project_name()` to `api/routes/conversations_routes.py`
5. ✅ Modify `parse_claude_transcripts()` to use new function
6. ✅ Restart API: `docker compose restart api`
7. ✅ Test: Create new conversation and verify project name in UI
8. ✅ Verify in Memories page: http://localhost:3000/memories
9. ⚠️ (Optional) Run SQL migration for existing data

---

## Success Criteria

- ✅ Script works from any directory (Git or non-Git)
- ✅ Hooks detect project name automatically
- ✅ Auto-import uses correct project name
- ✅ UI displays project name in conversation cards
- ✅ Works when MnemoLite used as MCP server in other projects
- ✅ No hardcoded project names anywhere
- ✅ Graceful fallback if script missing (uses basename)

---

## Advantages of This Approach

1. **DRY:** Single source of truth for project detection logic
2. **Portable:** Works from any project using MnemoLite
3. **Robust:** Git-based detection with fallback
4. **Simple:** Pure bash script, no dependencies
5. **Testable:** Script can be tested independently
6. **Transparent:** Logs detected project for debugging
7. **Extensible:** Future components can reuse the same script

---

## Future Enhancements

- Support for `.claude/project.txt` override file
- Environment variable `MNEMOLITE_PROJECT` for manual override
- Auto-detection from `package.json` or `pyproject.toml` names
