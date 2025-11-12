# Project Name Detection - Implementation Plan

**Date:** 2025-11-12
**Design Doc:** [2025-11-12-project-name-detection-design.md](./2025-11-12-project-name-detection-design.md)
**Status:** Ready for Execution
**Estimated Time:** 45-60 minutes

---

## Overview

This plan implements robust project name detection for MnemoLite using a centralized bash script approach. The system will automatically detect project names from Git repository roots with basename fallback, eliminating hardcoded project names.

**Architecture:**
```
scripts/get-project-name.sh (centralized detection logic)
    ↓ called by
├── .claude/hooks/UserPromptSubmit/auto-save-previous.sh
├── api/routes/conversations_routes.py (via subprocess)
└── Future: MCP tools, indexing scripts
```

---

## Prerequisites

- Docker services running (`docker compose up -d`)
- API accessible at http://localhost:8000
- Frontend dev server running at http://localhost:3000
- Git repository initialized in MnemoLite directory
- Write access to `/home/giak/Work/MnemoLite/`

---

## Task 1: Create Detection Script

**File:** `/home/giak/Work/MnemoLite/scripts/get-project-name.sh`

**Action:** Create new file with project detection logic

**Complete Code:**
```bash
#!/bin/bash
# Detect project name with fallback strategy
# Usage: bash scripts/get-project-name.sh [optional_working_directory]
# Output: project name in lowercase (e.g., "mnemolite")
# Exit codes: 0 = success (always succeeds via fallback)

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

**Post-Creation Steps:**
```bash
# Make script executable
chmod +x /home/giak/Work/MnemoLite/scripts/get-project-name.sh

# Test from MnemoLite directory
cd /home/giak/Work/MnemoLite
bash scripts/get-project-name.sh
# Expected output: "mnemolite"

# Test with explicit path
bash scripts/get-project-name.sh /home/giak/Work/MnemoLite
# Expected output: "mnemolite"

# Test from subdirectory (should still return Git root)
cd /home/giak/Work/MnemoLite/api
bash ../scripts/get-project-name.sh
# Expected output: "mnemolite"
```

**Verification:**
- Script exists at correct path
- Script is executable (`ls -la scripts/get-project-name.sh` shows `x` permissions)
- Test from Git repo returns lowercase directory name
- Test from subdirectory returns Git root basename (not subdirectory name)
- Script never fails (always has fallback)

---

## Task 2: Update Hook for Auto-Save

**File:** `/home/giak/Work/MnemoLite/.claude/hooks/UserPromptSubmit/auto-save-previous.sh`

**Current Location to Modify:** After conversation extraction (around line 60-70), before the curl API call

**Action:** Add project name detection section

**Code to Add:**
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

**Then Modify the curl API Call:**

**Find this section (around line 100-120):**
```bash
curl -s -X POST "$API_URL/api/v1/memories" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "title": "Conv: ${PREV_USER:0:60}...",
  "content": "$CONTENT_ESCAPED",
  "memory_type": "conversation",
  "tags": [TAGS],
  "author": "AutoSave",
  "project_id": null
}
EOF
```

**Replace `"project_id": null` with:**
```bash
  "project_id": "$PROJECT_NAME"
```

**Complete Modified curl Call:**
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

**Verification:**
- Read the hook file to confirm changes
- Check `/tmp/hook-autosave-debug.log` after next user prompt to see "Detected project: mnemolite"
- Create a test conversation and verify project_id is populated in database

---

## Task 3: Add Python Detection Function

**File:** `/home/giak/Work/MnemoLite/api/routes/conversations_routes.py`

**Current Problematic Code (Line ~306):**
```python
await write_tool.execute(
    ctx=ctx,
    title=title,
    content=content,
    memory_type="conversation",
    tags=tags,
    author="AutoImport",
    project_id="mnemolite"  # HARDCODED - TO BE REPLACED
)
```

**Action 1: Add imports at top of file**

**Find the import section (lines 1-20) and add:**
```python
import subprocess
import os
from pathlib import Path
```

**Verification Point:** Imports should be with other stdlib imports, grouped logically

---

**Action 2: Add helper function**

**Location:** After imports, before route definitions (around line 30-40)

**Code to Add:**
```python
def get_project_name(working_dir: str = None) -> str:
    """
    Detect project name using centralized bash script.

    Falls back through multiple strategies:
    1. Execute get-project-name.sh from various locations
    2. Use basename of working directory

    Args:
        working_dir: Working directory to detect from (default: current dir)

    Returns:
        Project name in lowercase (always succeeds)

    Examples:
        >>> get_project_name("/home/user/MnemoLite")
        "mnemolite"
        >>> get_project_name()  # From /home/user/MyProject
        "myproject"
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
                # Log silently, continue to fallback
                pass

    # Fallback: use basename of working directory
    return Path(working_dir).name.lower()
```

**Verification Point:** Function is defined before any route handlers

---

**Action 3: Update parse_claude_transcripts() function**

**Find this line (around line 240-260 in parse_claude_transcripts function):**
```python
project_name = session_id.rsplit('-', 1)[0] if '-' in session_id else session_id
```

**Replace with:**
```python
project_name = get_project_name(str(transcripts_path.parent))
```

**Context - The full section should look like:**
```python
async def parse_claude_transcripts(transcripts_path: Path) -> list[dict]:
    """Parse Claude Code transcript files and extract conversation exchanges."""
    memories = []

    # ... existing code ...

    for file_path in transcript_files:
        session_id = file_path.stem

        # Detect project name from directory context
        project_name = get_project_name(str(transcripts_path.parent))

        # ... rest of function ...
```

**Verification Point:** Old filename-based extraction is completely removed

---

**Action 4: Update write_tool.execute() call**

**Find the hardcoded project_id (around line 306):**
```python
project_id="mnemolite"
```

**Replace with:**
```python
project_id=project_name
```

**Complete Context:**
```python
await write_tool.execute(
    ctx=ctx,
    title=title,
    content=content,
    memory_type="conversation",
    tags=tags,
    author="AutoImport",
    project_id=project_name  # Now using detected project name
)
```

**Verification Point:** No hardcoded "mnemolite" string remains in file

---

**Full Verification for Task 3:**
```bash
# Restart API to load changes
docker compose restart api

# Check logs for errors
docker compose logs api | tail -20

# Test the endpoint
curl -X POST http://localhost:8000/v1/conversations/import

# Verify in UI: http://localhost:3000/memories
# Should show "MNEMOLITE" project badge on conversation cards
```

---

## Task 4: Create Test Suite

**File:** `/home/giak/Work/MnemoLite/tests/test-get-project-name.sh`

**Action:** Create new test file

**Complete Code:**
```bash
#!/bin/bash
# Test suite for get-project-name.sh
# Tests various scenarios: Git repos, non-Git dirs, explicit paths

set -e

SCRIPT_PATH="/home/giak/Work/MnemoLite/scripts/get-project-name.sh"
PASSED=0
FAILED=0

echo "========================================"
echo "Testing: get-project-name.sh"
echo "========================================"

# Test 1: From Git repository root
echo -n "Test 1: Git repository root... "
cd /home/giak/Work/MnemoLite
RESULT=$(bash "$SCRIPT_PATH")
if [ "$RESULT" = "mnemolite" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: mnemolite, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi

# Test 2: From Git subdirectory (should return root)
echo -n "Test 2: Git subdirectory... "
cd /home/giak/Work/MnemoLite/api
RESULT=$(bash "$SCRIPT_PATH")
if [ "$RESULT" = "mnemolite" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: mnemolite, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi

# Test 3: With explicit path argument
echo -n "Test 3: Explicit path argument... "
RESULT=$(bash "$SCRIPT_PATH" /home/giak/Work/MnemoLite)
if [ "$RESULT" = "mnemolite" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: mnemolite, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi

# Test 4: Non-Git directory (fallback to basename)
echo -n "Test 4: Non-Git directory fallback... "
mkdir -p /tmp/TestProject123
RESULT=$(bash "$SCRIPT_PATH" /tmp/TestProject123)
if [ "$RESULT" = "testproject123" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: testproject123, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi
rm -rf /tmp/TestProject123

# Test 5: Uppercase directory name (should lowercase)
echo -n "Test 5: Uppercase normalization... "
mkdir -p /tmp/UPPERCASE_DIR
RESULT=$(bash "$SCRIPT_PATH" /tmp/UPPERCASE_DIR)
if [ "$RESULT" = "uppercase_dir" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: uppercase_dir, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi
rm -rf /tmp/UPPERCASE_DIR

# Summary
echo "========================================"
echo "Results: $PASSED passed, $FAILED failed"
echo "========================================"

if [ $FAILED -eq 0 ]; then
  echo "✅ All tests passed!"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi
```

**Execution:**
```bash
# Make test executable
chmod +x /home/giak/Work/MnemoLite/tests/test-get-project-name.sh

# Run tests
bash /home/giak/Work/MnemoLite/tests/test-get-project-name.sh
```

**Expected Output:**
```
========================================
Testing: get-project-name.sh
========================================
Test 1: Git repository root... ✅ PASS (got: mnemolite)
Test 2: Git subdirectory... ✅ PASS (got: mnemolite)
Test 3: Explicit path argument... ✅ PASS (got: mnemolite)
Test 4: Non-Git directory fallback... ✅ PASS (got: testproject123)
Test 5: Uppercase normalization... ✅ PASS (got: uppercase_dir)
========================================
Results: 5 passed, 0 failed
========================================
✅ All tests passed!
```

---

## Task 5: Integration Testing

**Scenario 1: New Conversation in MnemoLite**

**Steps:**
```bash
# 1. Clear previous test data (optional)
docker compose exec postgres psql -U postgres -d mnemolite -c "DELETE FROM memories WHERE tags @> ARRAY['test-integration'];"

# 2. Trigger hook by creating a test conversation in Claude Code
# Type a message, wait for response, check hook logs

# 3. Check hook logs
tail -f /tmp/hook-autosave-debug.log
# Should see: "Detected project: mnemolite"

# 4. Verify in database
docker compose exec postgres psql -U postgres -d mnemolite -c "SELECT project_id, title FROM memories WHERE memory_type='conversation' ORDER BY created_at DESC LIMIT 5;"
# Should see: project_id = "mnemolite"

# 5. Check UI at http://localhost:3000/memories
# Should see: 📁 MNEMOLITE badge on conversation cards
```

**Expected Results:**
- Hook log shows detected project name
- Database shows project_id populated
- UI displays project badge

---

**Scenario 2: Auto-Import Existing Transcripts**

**Steps:**
```bash
# 1. Ensure transcript files exist
ls -la ~/.config/claude-code/transcripts/*.jsonl

# 2. Trigger import
curl -X POST http://localhost:8000/v1/conversations/import

# 3. Check response
# {"imported": N, "skipped": M, "failed": 0}

# 4. Verify project_id in database
docker compose exec postgres psql -U postgres -d mnemolite -c "SELECT DISTINCT project_id, COUNT(*) FROM memories WHERE author='AutoImport' GROUP BY project_id;"
# Should show: mnemolite | <count>

# 5. Check UI
# All auto-imported conversations should show 📁 MNEMOLITE
```

**Expected Results:**
- All imported conversations have project_id = "mnemolite"
- No NULL project_id values for new imports
- UI shows project badge consistently

---

**Scenario 3: Test from Subdirectory**

**Steps:**
```bash
# 1. Navigate to subdirectory
cd /home/giak/Work/MnemoLite/frontend

# 2. Call script
bash ../scripts/get-project-name.sh

# 3. Expected output
# "mnemolite" (Git root, not "frontend")
```

**Expected Results:**
- Script returns Git root name, not subdirectory name

---

## Task 6: Optional Data Migration

**File:** SQL migration script (execute manually if needed)

**Purpose:** Update existing conversations that have NULL project_id

**SQL Script:**
```sql
-- Migration: Populate NULL project_ids for MnemoLite conversations
-- Date: 2025-11-12
-- CAUTION: Only run once, review results before committing

BEGIN;

-- Preview affected rows
SELECT id, title, author, tags, project_id
FROM memories
WHERE project_id IS NULL
  AND memory_type = 'conversation'
  AND author IN ('AutoSave', 'AutoImport')
  AND tags @> ARRAY['claude-code'];

-- Update to set project_id = 'mnemolite'
UPDATE memories
SET project_id = 'mnemolite'
WHERE project_id IS NULL
  AND memory_type = 'conversation'
  AND author IN ('AutoSave', 'AutoImport')
  AND tags @> ARRAY['claude-code'];

-- Verify results
SELECT project_id, COUNT(*)
FROM memories
WHERE memory_type = 'conversation'
GROUP BY project_id;

-- Commit if results look good
COMMIT;
-- or ROLLBACK; if something looks wrong
```

**Execution:**
```bash
docker compose exec postgres psql -U postgres -d mnemolite

# Then paste the SQL script above
# Review the preview results
# If satisfied, let it COMMIT
```

**Warning:** This is optional and only affects historical data. New conversations will have project_id automatically populated.

---

## Task 7: Final Verification

**Checklist:**

```bash
# 1. Script exists and is executable
ls -la /home/giak/Work/MnemoLite/scripts/get-project-name.sh
# Should show: -rwxr-xr-x

# 2. Script works independently
bash /home/giak/Work/MnemoLite/scripts/get-project-name.sh
# Output: mnemolite

# 3. Tests pass
bash /home/giak/Work/MnemoLite/tests/test-get-project-name.sh
# Output: ✅ All tests passed!

# 4. API restart successful
docker compose restart api
docker compose logs api | tail -20
# Should show: "Application startup complete"

# 5. No errors on import
curl -X POST http://localhost:8000/v1/conversations/import
# Should return: {"imported": N, ...} without errors

# 6. Database check
docker compose exec postgres psql -U postgres -d mnemolite -c "SELECT project_id, COUNT(*) FROM memories WHERE memory_type='conversation' AND created_at > NOW() - INTERVAL '1 hour' GROUP BY project_id;"
# Should show: mnemolite | N (for recent conversations)

# 7. UI verification
# Open: http://localhost:3000/memories
# Check: Conversation cards show 📁 MNEMOLITE badge
# Check: No date:XXXXX tags visible (filtered out)

# 8. Hook verification
tail /tmp/hook-autosave-debug.log
# Should show: "Detected project: mnemolite" for recent conversations
```

**Success Criteria:**
- ✅ All 5 unit tests pass
- ✅ Script detected from Git repository
- ✅ Fallback works for non-Git directories
- ✅ Hook logs show detected project name
- ✅ API imports use detected project name
- ✅ Database shows populated project_id for new conversations
- ✅ UI displays project badges correctly
- ✅ No hardcoded "mnemolite" strings remain in code

---

## Rollback Plan

If something goes wrong:

```bash
# 1. Revert Git changes
cd /home/giak/Work/MnemoLite
git diff HEAD  # Review changes
git checkout HEAD -- .claude/hooks/UserPromptSubmit/auto-save-previous.sh
git checkout HEAD -- api/routes/conversations_routes.py

# 2. Remove new files
rm -f scripts/get-project-name.sh
rm -f tests/test-get-project-name.sh

# 3. Restart API
docker compose restart api

# 4. Verify rollback
curl http://localhost:8000/health
```

---

## Post-Implementation

**Commit Message Template:**
```
feat(core): Add robust project name detection with Git-based fallback

- Create centralized get-project-name.sh script with cascade logic
- Modify auto-save hook to detect project from Git root
- Update conversations_routes.py to use dynamic project detection
- Add comprehensive test suite with 5 test scenarios
- Remove hardcoded "mnemolite" project_id

Resolves: Project name detection not portable across different projects
Design: docs/plans/2025-11-12-project-name-detection-design.md

BREAKING: Conversations now require project context from directory
```

**Documentation Updates:**
- Update QUICKSTART.md to mention project auto-detection
- Add troubleshooting section for project name issues

---

## Time Estimates

- Task 1 (Script): 5 minutes
- Task 2 (Hook): 10 minutes
- Task 3 (Python): 15 minutes
- Task 4 (Tests): 10 minutes
- Task 5 (Integration): 10 minutes
- Task 6 (Migration): 5 minutes (optional)
- Task 7 (Verification): 5 minutes

**Total: ~50 minutes** (60 minutes with migration)

---

## Notes

- **No hardcoded fallbacks:** The script always succeeds via basename fallback
- **Timeout protection:** Python subprocess has 2-second timeout
- **Portable:** Works when MnemoLite is used as MCP server in other projects
- **Testable:** Script can be tested independently without running full system
- **Logged:** Hook logs detected project for debugging
- **Extensible:** Future components can reuse the same detection script

**Design Principle:** Single source of truth (DRY) with defense in depth (multiple fallbacks)
