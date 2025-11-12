#!/bin/bash
# Stub hook for UserPromptSubmit - calls centralized MnemoLite service
# Version: 1.0.0 - Stub architecture
# Deploy this to: <project>/.claude/hooks/UserPromptSubmit/auto-save-previous.sh

set -euo pipefail

# Read hook data
HOOK_DATA=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_DATA" | jq -r '.transcript_path // ""')
SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // "unknown"')

# Validate
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo '{"continue": true}'
  exit 0
fi

# Call centralized service
# Detect MnemoLite location dynamically
MNEMOLITE_ROOT="${MNEMOLITE_HOME:-}"

if [ -z "$MNEMOLITE_ROOT" ]; then
  # Fallback: Search common locations
  for candidate in "$HOME/Work/MnemoLite" "$HOME/projects/MnemoLite" "$HOME/MnemoLite"; do
    if [ -f "$candidate/scripts/save-conversation-from-hook.sh" ]; then
      MNEMOLITE_ROOT="$candidate"
      break
    fi
  done
fi

if [ -z "$MNEMOLITE_ROOT" ] || [ ! -f "$MNEMOLITE_ROOT/scripts/save-conversation-from-hook.sh" ]; then
  # Service not found - fail silently
  echo '{"continue": true}'
  exit 0
fi

bash "$MNEMOLITE_ROOT/scripts/save-conversation-from-hook.sh" \
  "$TRANSCRIPT_PATH" \
  "$SESSION_ID" \
  "auto" \
  2>&1 > /dev/null || true

# Always continue
echo '{"continue": true}'
exit 0
