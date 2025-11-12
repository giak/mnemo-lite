#!/bin/bash
# Stub hook for Stop - calls centralized MnemoLite service
# Version: 1.0.0 - Stub architecture
# Deploy this to: <project>/.claude/hooks/Stop/auto-save.sh

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
bash /home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh \
  "$TRANSCRIPT_PATH" \
  "$SESSION_ID" \
  "stop" \
  2>&1 > /dev/null || true

# Always continue
echo '{"continue": true}'
exit 0
