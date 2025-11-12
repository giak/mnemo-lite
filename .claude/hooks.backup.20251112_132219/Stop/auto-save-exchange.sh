#!/bin/bash
# Auto-save CURRENT conversation (after Claude finishes)
# Hook: Stop (after Claude completes response)
# Saves the CURRENT complete exchange (user + assistant)
# Version: 3.0 - POC Option A

set -euo pipefail

# DEBUG: Log que le hook est appelé
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Hook Stop called - VERSION 3.0 POC-A" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 1. READ HOOK DATA
# ============================================================================
HOOK_DATA=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_DATA" | jq -r '.transcript_path // ""')
SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // "unknown"')

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stop Hook - Transcript: $TRANSCRIPT_PATH, Session: $SESSION_ID" >> /tmp/hook-autosave-debug.log

# Validate transcript exists
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo "DEBUG: Stop Hook - Transcript not found, exiting" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 2. EXTRACT CURRENT EXCHANGE (last user + assistant response)
# ============================================================================

# Count total REAL user messages (Claude Code format: .message.role, exclude tool_result)
USER_COUNT=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '
  [.[] |
   select(.message.role == "user") |
   select(
     (.message.content | type) == "string" or
     ((.message.content | type) == "array" and
      (.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] | length
' 2>/dev/null || echo "0")

# Need at least 1 exchange
if [ "$USER_COUNT" -lt 1 ]; then
  echo "DEBUG: Stop Hook - No user messages found (USER_COUNT=$USER_COUNT)" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

# Extract LAST REAL user message (Claude Code format, exclude tool_result)
LAST_USER=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '
  [.[] |
   select(.message.role == "user") |
   select(
     (.message.content | type) == "string" or
     ((.message.content | type) == "array" and
      (.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] |
  if length >= 1 then .[-1].message else null end |
  if . == null then ""
  elif (.content | type) == "array" then
    [.content[] | select(.type == "text") | .text] | join("\n")
  else
    .content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Extract COMPLETE assistant response AFTER last user
# Includes: assistant text + tool results (Bash, Read, etc.)
LAST_ASSISTANT=$(tail -2000 "$TRANSCRIPT_PATH" | jq -rs '
  # Add array indices to all messages
  . as $all |
  ($all | to_entries) as $indexed |

  # Get index of last real user message (excluding tool_result)
  ([$indexed[] |
   select(.value.message.role == "user") |
   select(
     (.value.message.content | type) == "string" or
     ((.value.message.content | type) == "array" and
      (.value.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] | .[-1].key) as $last_user_idx |

  # Extract ALL messages AFTER last user (assistant text + tool_result)
  [$indexed[] |
   select(.key > $last_user_idx) |

   # Extract content based on message type
   if .value.message.role == "assistant" then
     # Assistant text
     if (.value.message.content | type) == "array" then
       ([.value.message.content[] | select(.type == "text") | .text] | join("\n"))
     else
       ""
     end
   elif .value.message.role == "user" then
     # Tool results (output of Bash, Read, etc)
     if (.value.message.content | type) == "array" then
       ([.value.message.content[] |
        select(.type == "tool_result") |
        .content // ""
       ] | join("\n---\n"))
     else
       ""
     end
   else
     ""
   end
  ] | map(select(length > 0)) | join("\n\n")
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Skip if empty (minimum 1 char to avoid truly empty messages)
if [ -z "$LAST_USER" ] || [ ${#LAST_USER} -lt 1 ]; then
  echo "DEBUG: Stop Hook - LAST_USER empty or too short (${#LAST_USER} chars)" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

if [ -z "$LAST_ASSISTANT" ] || [ ${#LAST_ASSISTANT} -lt 1 ]; then
  echo "DEBUG: Stop Hook - LAST_ASSISTANT empty or too short (${#LAST_ASSISTANT} chars)" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

echo "DEBUG: Stop Hook - Extracted USER=${#LAST_USER} chars, ASSISTANT=${#LAST_ASSISTANT} chars" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 3. DEDUPLICATION CHECK (hash-based)
# ============================================================================

# Compute hash of the exchange
EXCHANGE_HASH=$(echo -n "$LAST_USER$LAST_ASSISTANT" | md5sum | cut -d' ' -f1 | cut -c1-16)
HASH_FILE="/tmp/mnemo-saved-exchanges.txt"

# Check if already saved
if grep -q "^${EXCHANGE_HASH}$" "$HASH_FILE" 2>/dev/null; then
  echo "DEBUG: Stop Hook - Hash $EXCHANGE_HASH already exists, skipping" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

echo "DEBUG: Stop Hook - Hash $EXCHANGE_HASH not found, proceeding to save..." >> /tmp/hook-autosave-debug.log

# ============================================================================
# 4. SAVE TO MNEMOLITE (via write_memory MCP tool)
# ============================================================================

# Call Python script inside Docker that uses write_memory tool
# Must be executed from MnemoLite directory
SAVE_OUTPUT=$(cd /home/giak/Work/MnemoLite && docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "$LAST_USER" \
  "$LAST_ASSISTANT" \
  "${SESSION_ID}_stop" \
  2>&1)

echo "DEBUG: Stop Hook - Save output: $SAVE_OUTPUT" >> /tmp/hook-autosave-debug.log

# Mark as saved
echo "$EXCHANGE_HASH" >> "$HASH_FILE"
echo "DEBUG: Stop Hook - Hash $EXCHANGE_HASH added to dedup file" >> /tmp/hook-autosave-debug.log
echo "✓ Stop Hook - Saved exchange immediately after response" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 5. RETURN SUCCESS (non-blocking)
# ============================================================================
echo '{"continue": true}'
exit 0
