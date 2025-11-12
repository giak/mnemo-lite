#!/bin/bash
# Centralized hook service for ALL Claude Code projects
# Called by stub hooks in each project
# Version: 1.0.0 - Centralized architecture

set -euo pipefail

# ============================================================================
# 1. PARSE ARGUMENTS
# ============================================================================
TRANSCRIPT_PATH="${1:-}"
SESSION_ID="${2:-unknown}"
HOOK_TYPE="${3:-stop}"  # "stop" or "auto"

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo "ERROR: Invalid transcript path: $TRANSCRIPT_PATH" >&2
  exit 1
fi

# ============================================================================
# 2. DETECT PROJECT NAME
# ============================================================================

# Extract project path from transcript directory structure
# Handle SESSION:xxx subdirectories (transcripts can be nested in session folders)
TRANSCRIPT_DIR=$(dirname "$TRANSCRIPT_PATH")
TRANSCRIPT_PARENT=$(basename "$TRANSCRIPT_DIR")

if [[ "$TRANSCRIPT_PARENT" =~ ^SESSION: ]] || [[ "$TRANSCRIPT_PARENT" =~ ^agent- ]]; then
  # Transcript is in .../SESSION:xxx/transcript.jsonl or .../agent-xxx.jsonl parent
  # Go up one more level to get the actual project directory
  PROJECT_DIR=$(basename "$(dirname "$TRANSCRIPT_DIR")")
else
  # Transcript is directly in project directory
  PROJECT_DIR="$TRANSCRIPT_PARENT"
fi

# Reconstruct absolute path using regex to preserve hyphens in project names
PROJECT_PATH=""
if [[ "$PROJECT_DIR" =~ ^-home-([^-]+)-projects-(.+)$ ]]; then
  PROJECT_PATH="/home/${BASH_REMATCH[1]}/projects/${BASH_REMATCH[2]}"
elif [[ "$PROJECT_DIR" =~ ^-home-([^-]+)-Work-(.+)$ ]]; then
  PROJECT_PATH="/home/${BASH_REMATCH[1]}/Work/${BASH_REMATCH[2]}"
fi

# Detect project name using centralized script (uses Git if available)
SCRIPT_PATH="/home/giak/Work/MnemoLite/scripts/get-project-name.sh"
PROJECT_NAME=""

if [ -n "$PROJECT_PATH" ] && [ -d "$PROJECT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
  PROJECT_NAME=$(bash "$SCRIPT_PATH" "$PROJECT_PATH" 2>/dev/null || echo "")
fi

# Fallback: extract from PROJECT_PATH or PROJECT_DIR
if [ -z "$PROJECT_NAME" ]; then
  if [ -n "$PROJECT_PATH" ]; then
    PROJECT_NAME=$(basename "$PROJECT_PATH" | tr '[:upper:]' '[:lower:]')
  else
    # Extract last segment from PROJECT_DIR
    PROJECT_NAME=$(echo "$PROJECT_DIR" | sed -E 's/^-home-[^-]+-projects-//; s/^-home-[^-]+-Work-//; s/^-//')
    PROJECT_NAME=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]')
  fi
fi

# ============================================================================
# 3. EXTRACT MESSAGES (based on hook type)
# ============================================================================

if [ "$HOOK_TYPE" = "stop" ]; then
  # Stop hook: Extract LAST exchange (current conversation ending)

  # Extract LAST REAL user message (Claude Code format: .message.role, exclude tool_result)
  USER_MSG=$(tail -100 "$TRANSCRIPT_PATH" | jq -s '
    [.[] |
     select(.message.role == "user") |
     select(
       (.message.content | type) == "string" or
       ((.message.content | type) == "array" and
        (.message.content | map(select(.type == "tool_result")) | length) == 0)
     )
    ] |
    last |
    if . == null then ""
    elif (.message.content | type) == "array" then
      [.message.content[] | select(.type == "text") | .text] | join("\n")
    else
      .message.content
    end
  ' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

  # Extract LAST assistant message WITH TEXT (Claude Code format: .message.role)
  # Filter to only messages that contain text (not just tool_use)
  ASSISTANT_MSG=$(tail -500 "$TRANSCRIPT_PATH" | jq -s '
    [.[] |
     select(.message.role == "assistant") |
     select(
       (.message.content | type) == "array" and
       (.message.content | map(select(.type == "text")) | length) > 0
     )
    ] |
    last |
    if . == null then ""
    elif (.message.content | type) == "array" then
      [.message.content[] | select(.type == "text") | .text] | join("\n")
    else
      .message.content
    end
  ' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

elif [ "$HOOK_TYPE" = "auto" ]; then
  # UserPromptSubmit hook: Extract PREVIOUS exchange (second-to-last)

  # Count total REAL user messages
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

  # Need at least 2 user messages
  if [ "$USER_COUNT" -lt 2 ]; then
    exit 0
  fi

  # Extract SECOND-TO-LAST user message
  USER_MSG=$(tail -200 "$TRANSCRIPT_PATH" | jq -s '
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
  ASSISTANT_MSG=$(tail -2000 "$TRANSCRIPT_PATH" | jq -rs '
    . as $all |
    ($all | to_entries) as $indexed |

    [$indexed[] |
     select(.value.message.role == "user") |
     select(
       (.value.message.content | type) == "string" or
       ((.value.message.content | type) == "array" and
        (.value.message.content | map(select(.type == "tool_result")) | length) == 0)
     )
    ] as $user_entries |

    if ($user_entries | length) < 2 then ""
    else
      ($user_entries[-2].key) as $user_n2_idx |
      ($user_entries[-1].key) as $user_n1_idx |

      [$indexed[] |
       select(.key > $user_n2_idx and .key < $user_n1_idx) |

       if .value.message.role == "assistant" then
         if (.value.message.content | type) == "array" then
           ([.value.message.content[] | select(.type == "text") | .text] | join("\n"))
         else
           ""
         end
       elif .value.message.role == "user" then
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
fi

# Skip if empty
if [ -z "$USER_MSG" ] || [ ${#USER_MSG} -lt 1 ]; then
  exit 0
fi

if [ -z "$ASSISTANT_MSG" ] || [ ${#ASSISTANT_MSG} -lt 1 ]; then
  exit 0
fi

# ============================================================================
# 4. DEDUPLICATION CHECK
# ============================================================================
EXCHANGE_HASH=$(echo -n "$USER_MSG$ASSISTANT_MSG" | md5sum | cut -d' ' -f1 | cut -c1-16)
HASH_FILE="/tmp/mnemo-saved-exchanges.txt"

if grep -q "^${EXCHANGE_HASH}$" "$HASH_FILE" 2>/dev/null; then
  exit 0
fi

# ============================================================================
# 5. SAVE TO MNEMOLITE
# ============================================================================

# Build session tag based on hook type
SESSION_TAG="${SESSION_ID}_${HOOK_TYPE}"

# Call API endpoint /v1/conversations/save (NEW - replaces save-direct.py)
# Escape JSON strings properly (keep quotes for JSON syntax)
USER_MSG_ESCAPED=$(echo "$USER_MSG" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")
ASSISTANT_MSG_ESCAPED=$(echo "$ASSISTANT_MSG" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")
TIMESTAMP=$(date -Iseconds)

# Change to MnemoLite directory for docker compose
cd /home/giak/Work/MnemoLite

# Call modern API endpoint
curl -s -X POST http://localhost:8001/v1/conversations/save \
  -H "Content-Type: application/json" \
  -d "{
    \"user_message\": $USER_MSG_ESCAPED,
    \"assistant_message\": $ASSISTANT_MSG_ESCAPED,
    \"project_name\": \"$PROJECT_NAME\",
    \"session_id\": \"$SESSION_TAG\",
    \"timestamp\": \"$TIMESTAMP\"
  }" \
  2>&1 | grep -qE "success.*true" && echo "✓ Saved" || echo "✗ Failed"

# Mark as saved
echo "$EXCHANGE_HASH" >> "$HASH_FILE"
exit 0
