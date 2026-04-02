#!/bin/bash
# Auto-save TOUS les échanges dans MnemoLite
# Hook: Stop (after each Claude response)
# Version: 1.0.0 Production

set -euo pipefail

# ============================================================================
# 1. READ HOOK DATA
# ============================================================================
HOOK_DATA=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_DATA" | jq -r '.transcript_path // ""')
SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // "unknown"')
STOP_HOOK_ACTIVE=$(echo "$HOOK_DATA" | jq -r '.stop_hook_active // false')

# Prevent infinite loops
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  echo '{"continue": true}' >&2
  exit 0
fi

# Validate transcript exists
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo '{"continue": true}' >&2
  exit 0
fi

# ============================================================================
# 2. PARSE TRANSCRIPT (JSONL Format)
# ============================================================================

# Extract last user message
LAST_USER=$(tail -50 "$TRANSCRIPT_PATH" | jq -s '
  [.[] | select(.role == "user")] |
  last |
  if . == null then ""
  elif (.content | type) == "array" then
    [.content[] | select(.type == "text") | .text] | join("\n")
  else
    .content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Extract last assistant message
LAST_ASSISTANT=$(tail -50 "$TRANSCRIPT_PATH" | jq -s '
  [.[] | select(.role == "assistant")] |
  last |
  if . == null then ""
  elif (.content | type) == "array" then
    [.content[] | select(.type == "text") | .text] | join("\n")
  else
    .content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Skip if empty
if [ -z "$LAST_USER" ] || [ ${#LAST_USER} -lt 5 ]; then
  echo '{"continue": true}' >&2
  exit 0
fi

if [ -z "$LAST_ASSISTANT" ] || [ ${#LAST_ASSISTANT} -lt 5 ]; then
  echo '{"continue": true}' >&2
  exit 0
fi

# ============================================================================
# 3. SAVE TO MNEMOLITE (via write_memory MCP tool with embeddings)
# ============================================================================

# Call Python script inside Docker that uses write_memory tool
# This generates embeddings for semantic search!
docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "$LAST_USER" \
  "$LAST_ASSISTANT" \
  "$SESSION_ID" \
  2>&1 | grep -E "^[✓✗]" || true

# ============================================================================
# 4. RETURN SUCCESS (non-blocking)
# ============================================================================
echo '{"continue": true}'
exit 0
