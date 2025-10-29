#!/bin/bash
# Auto-save PREVIOUS conversation (transparent)
# Hook: UserPromptSubmit (before each user question)
# Saves the LAST complete exchange (previous user + assistant)
# Version: 1.0.1 - DEBUG

set -euo pipefail

# DEBUG: Log que le hook est appelé
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Hook UserPromptSubmit called" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 1. READ HOOK DATA
# ============================================================================
HOOK_DATA=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_DATA" | jq -r '.transcript_path // ""')
SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // "unknown"')

# Validate transcript exists
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 2. EXTRACT PREVIOUS EXCHANGE (before current user input)
# ============================================================================

# Count total user messages
USER_COUNT=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '[.[] | select(.role == "user")] | length' 2>/dev/null || echo "0")

# Need at least 1 previous exchange (so minimum 2 user messages total)
if [ "$USER_COUNT" -lt 2 ]; then
  echo '{"continue": true}'
  exit 0
fi

# Extract SECOND-TO-LAST user message
PREV_USER=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '
  [.[] | select(.role == "user")] |
  if length >= 2 then .[-2] else null end |
  if . == null then ""
  elif (.content | type) == "array" then
    [.content[] | select(.type == "text") | .text] | join("\n")
  else
    .content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Extract LAST assistant message (response to that user message)
PREV_ASSISTANT=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '
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
if [ -z "$PREV_USER" ] || [ ${#PREV_USER} -lt 5 ]; then
  echo '{"continue": true}'
  exit 0
fi

if [ -z "$PREV_ASSISTANT" ] || [ ${#PREV_ASSISTANT} -lt 5 ]; then
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 3. DEDUPLICATION CHECK (hash-based)
# ============================================================================

# Compute hash of the exchange
EXCHANGE_HASH=$(echo -n "$PREV_USER$PREV_ASSISTANT" | md5sum | cut -d' ' -f1 | cut -c1-16)
HASH_FILE="/tmp/mnemo-saved-exchanges.txt"

# Check if already saved
if grep -q "^${EXCHANGE_HASH}$" "$HASH_FILE" 2>/dev/null; then
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 4. SAVE TO MNEMOLITE (via write_memory MCP tool)
# ============================================================================

# Call Python script inside Docker that uses write_memory tool
docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "$PREV_USER" \
  "$PREV_ASSISTANT" \
  "${SESSION_ID}_auto" \
  2>&1 | grep -E "^[✓✗]" || true

# Mark as saved
echo "$EXCHANGE_HASH" >> "$HASH_FILE"

# ============================================================================
# 5. RETURN SUCCESS (non-blocking)
# ============================================================================
echo '{"continue": true}'
exit 0
