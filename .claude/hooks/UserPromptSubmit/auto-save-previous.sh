#!/bin/bash
# Auto-save PREVIOUS conversation (transparent)
# Hook: UserPromptSubmit (before each user question)
# Saves the LAST complete exchange (previous user + assistant)
# Version: 1.0.1 - DEBUG

set -euo pipefail

# DEBUG: Log que le hook est appelé
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Hook UserPromptSubmit called - VERSION 2.0" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 1. READ HOOK DATA
# ============================================================================
HOOK_DATA=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_DATA" | jq -r '.transcript_path // ""')
SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // "unknown"')

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Transcript: $TRANSCRIPT_PATH, Session: $SESSION_ID" >> /tmp/hook-autosave-debug.log

# Validate transcript exists
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 2. EXTRACT PREVIOUS EXCHANGE (before current user input)
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

# Need at least 1 previous exchange (so minimum 2 user messages total)
if [ "$USER_COUNT" -lt 2 ]; then
  echo '{"continue": true}'
  exit 0
fi

# Extract SECOND-TO-LAST REAL user message (Claude Code format, exclude tool_result)
PREV_USER=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '
  [.[] |
   select(.message.role == "user") |
   select(
     (.message.content | type) == "string" or
     ((.message.content | type) == "array" and
      (.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] |
  if length >= 2 then .[-2].message else null end |
  if . == null then ""
  elif (.content | type) == "array" then
    [.content[] | select(.type == "text") | .text] | join("\n")
  else
    .content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Extract COMPLETE assistant response BETWEEN user N-2 and user N-1
# Includes: assistant text + tool results (Bash, Read, etc.)
PREV_ASSISTANT=$(tail -2000 "$TRANSCRIPT_PATH" | jq -rs '
  # Add array indices to all messages
  . as $all |
  ($all | to_entries) as $indexed |

  # Get indices of real user messages (excluding tool_result)
  [$indexed[] |
   select(.value.message.role == "user") |
   select(
     (.value.message.content | type) == "string" or
     ((.value.message.content | type) == "array" and
      (.value.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] as $user_entries |

  # If less than 2 users, return empty
  if ($user_entries | length) < 2 then ""
  else
    # Get indices of user N-2 and N-1
    ($user_entries[-2].key) as $user_n2_idx |
    ($user_entries[-1].key) as $user_n1_idx |

    # Extract ALL messages between these indices (assistant text + tool_result)
    [$indexed[] |
     select(.key > $user_n2_idx and .key < $user_n1_idx) |

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
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

# Skip if empty (minimum 1 char to avoid truly empty messages)
if [ -z "$PREV_USER" ] || [ ${#PREV_USER} -lt 1 ]; then
  echo "DEBUG: PREV_USER empty or too short (${#PREV_USER} chars)" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

if [ -z "$PREV_ASSISTANT" ] || [ ${#PREV_ASSISTANT} -lt 1 ]; then
  echo "DEBUG: PREV_ASSISTANT empty or too short (${#PREV_ASSISTANT} chars)" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

echo "DEBUG: Extracted USER=${#PREV_USER} chars, ASSISTANT=${#PREV_ASSISTANT} chars" >> /tmp/hook-autosave-debug.log

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

# ============================================================================
# 4. DEDUPLICATION CHECK (hash-based)
# ============================================================================

# Compute hash of the exchange
EXCHANGE_HASH=$(echo -n "$PREV_USER$PREV_ASSISTANT" | md5sum | cut -d' ' -f1 | cut -c1-16)
HASH_FILE="/tmp/mnemo-saved-exchanges.txt"

# Check if already saved
if grep -q "^${EXCHANGE_HASH}$" "$HASH_FILE" 2>/dev/null; then
  echo "DEBUG: Hash $EXCHANGE_HASH already exists, skipping" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

echo "DEBUG: Hash $EXCHANGE_HASH not found, proceeding to save..." >> /tmp/hook-autosave-debug.log

# ============================================================================
# 5. SAVE TO MNEMOLITE (via write_memory MCP tool)
# ============================================================================

# Call Python script inside Docker that uses write_memory tool
# Must be executed from MnemoLite directory
SAVE_OUTPUT=$(cd /home/giak/Work/MnemoLite && docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "$PREV_USER" \
  "$PREV_ASSISTANT" \
  "${SESSION_ID}_auto" \
  "$PROJECT_NAME" \
  2>&1)

echo "DEBUG: Save output: $SAVE_OUTPUT" >> /tmp/hook-autosave-debug.log

# Mark as saved
echo "$EXCHANGE_HASH" >> "$HASH_FILE"
echo "DEBUG: Hash $EXCHANGE_HASH added to dedup file" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 6. RETURN SUCCESS (non-blocking)
# ============================================================================
echo '{"continue": true}'
exit 0
