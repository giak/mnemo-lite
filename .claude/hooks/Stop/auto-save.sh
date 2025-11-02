#!/bin/bash
# Auto-save CURRENT conversation on Stop
# Hook: Stop (at end of conversation)
# Version: 1.0.0

set -euo pipefail

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
# 2. EXTRACT LAST EXCHANGE
# ============================================================================

# Extract LAST user message
LAST_USER=$(tail -100 "$TRANSCRIPT_PATH" | jq -s '
  [.[] | select(.role == "user")] |
  last |
  if . == null then ""
  elif (.content | type) == "array" then
    [.content[] | select(.type == "text") | .text] | join("\n")
  else
    .content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Extract LAST assistant message
LAST_ASSISTANT=$(tail -100 "$TRANSCRIPT_PATH" | jq -s '
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
  echo '{"continue": true}'
  exit 0
fi

if [ -z "$LAST_ASSISTANT" ] || [ ${#LAST_ASSISTANT} -lt 5 ]; then
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 3. DEDUPLICATION CHECK
# ============================================================================
EXCHANGE_HASH=$(echo -n "$LAST_USER$LAST_ASSISTANT" | md5sum | cut -d' ' -f1 | cut -c1-16)
HASH_FILE="/tmp/mnemo-saved-exchanges.txt"

if grep -q "^${EXCHANGE_HASH}$" "$HASH_FILE" 2>/dev/null; then
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 4. SAVE TO MNEMOLITE
# ============================================================================
docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "$LAST_USER" \
  "$LAST_ASSISTANT" \
  "${SESSION_ID}_stop" \
  2>&1 | grep -E "^[✓✗]" || true

echo "$EXCHANGE_HASH" >> "$HASH_FILE"

# ============================================================================
# 5. RETURN SUCCESS
# ============================================================================
echo '{"continue": true}'
exit 0
