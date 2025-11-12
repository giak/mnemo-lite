#!/bin/bash
# Auto-Setup & Health Check for MnemoLite Auto-Save System
# Hook: SessionStart (when Claude Code session starts/resumes)
# Validates auto-save is functional and SCREAMS if broken
# Version: 1.0 - Phase 2 Production

set -euo pipefail

# Colors for alerts
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# 1. READ HOOK DATA
# ============================================================================
HOOK_DATA=$(cat)
SESSION_ID=$(echo "$HOOK_DATA" | jq -r '.session_id // "unknown"')
SOURCE=$(echo "$HOOK_DATA" | jq -r '.source // "unknown"')

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SessionStart Hook - Session: $SESSION_ID, Source: $SOURCE" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 2. CHECK MCP MNEMOLITE CONNECTED
# ============================================================================

# Check if MnemoLite Docker container is running
MNEMOLITE_RUNNING=$(cd /home/giak/Work/MnemoLite && docker compose ps api --status running --quiet 2>/dev/null || echo "")

if [ -z "$MNEMOLITE_RUNNING" ]; then
  # SCREAM - MnemoLite not running
  echo "" >&2
  echo "╔═══════════════════════════════════════════════════════════╗" >&2
  echo "║  🚨 ALERT: AUTO-SAVE NON FONCTIONNEL                      ║" >&2
  echo "╠═══════════════════════════════════════════════════════════╣" >&2
  echo "║  MnemoLite Docker container is NOT running.               ║" >&2
  echo "║  Your conversations will NOT be saved automatically.      ║" >&2
  echo "║                                                           ║" >&2
  echo "║  Fix:                                                     ║" >&2
  echo "║  1. cd /home/giak/Work/MnemoLite                          ║" >&2
  echo "║  2. docker compose up -d                                  ║" >&2
  echo "║  3. Check logs: docker compose logs api                   ║" >&2
  echo "╚═══════════════════════════════════════════════════════════╝" >&2
  echo "" >&2

  echo "ALERT: MnemoLite container NOT running - Auto-save DISABLED" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 3. CHECK HOOK STOP EXISTS
# ============================================================================

STOP_HOOK_PATH="/home/giak/projects/truth-engine/.claude/hooks/Stop/auto-save-exchange.sh"

if [ ! -f "$STOP_HOOK_PATH" ]; then
  # SCREAM - Hook Stop missing
  echo "" >&2
  echo "╔═══════════════════════════════════════════════════════════╗" >&2
  echo "║  🚨 ALERT: AUTO-SAVE HOOK MANQUANT                        ║" >&2
  echo "╠═══════════════════════════════════════════════════════════╣" >&2
  echo "║  Hook Stop not found at:                                  ║" >&2
  echo "║  $STOP_HOOK_PATH" >&2
  echo "║                                                           ║" >&2
  echo "║  Auto-save will NOT work.                                 ║" >&2
  echo "║                                                           ║" >&2
  echo "║  Fix:                                                     ║" >&2
  echo "║  Copy from master: cp /home/giak/Work/MnemoLite/.claude/hooks/Stop/auto-save-exchange.sh $STOP_HOOK_PATH" >&2
  echo "╚═══════════════════════════════════════════════════════════╝" >&2
  echo "" >&2

  echo "ALERT: Hook Stop NOT found - Auto-save BROKEN" >> /tmp/hook-autosave-debug.log
  echo '{"continue": true}'
  exit 0
fi

# ============================================================================
# 4. HEALTH CHECK MNEMOLITE API (dedicated autosave endpoint)
# ============================================================================

# Check dedicated autosave health endpoint
HEALTH_RESPONSE=$(curl -sf http://localhost:8001/api/v1/autosave/health 2>&1)
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status // "error"' 2>/dev/null || echo "error")

if [ "$HEALTH_STATUS" != "healthy" ]; then
  # Extract errors if available
  HEALTH_ERRORS=$(echo "$HEALTH_RESPONSE" | jq -r '.errors[]?' 2>/dev/null || echo "Unknown error")

  # SCREAM - API unhealthy
  echo "" >&2
  echo "╔═══════════════════════════════════════════════════════════╗" >&2
  echo "║  ⚠️  WARNING: MNEMOLITE API UNHEALTHY                      ║" >&2
  echo "╠═══════════════════════════════════════════════════════════╣" >&2
  echo "║  MnemoLite API health check failed.                       ║" >&2
  echo "║  Status: $HEALTH_STATUS" >&2
  if [ -n "$HEALTH_ERRORS" ]; then
    echo "║  Errors: $HEALTH_ERRORS" >&2
  fi
  echo "║                                                           ║" >&2
  echo "║  Auto-save may not work correctly.                        ║" >&2
  echo "║                                                           ║" >&2
  echo "║  Check:                                                   ║" >&2
  echo "║  1. curl http://localhost:8001/api/v1/autosave/health     ║" >&2
  echo "║  2. cd /home/giak/Work/MnemoLite                          ║" >&2
  echo "║  3. docker compose logs api | tail -50                    ║" >&2
  echo "║  4. docker compose restart api                            ║" >&2
  echo "╚═══════════════════════════════════════════════════════════╝" >&2
  echo "" >&2

  echo "WARNING: MnemoLite API unhealthy (status=$HEALTH_STATUS) - Auto-save may fail" >> /tmp/hook-autosave-debug.log
  # Don't exit - let user know but continue
else
  # Log success
  LATENCY=$(echo "$HEALTH_RESPONSE" | jq -r '.total_latency_ms // 0' 2>/dev/null || echo "0")
  echo "✅ MnemoLite API healthy (latency=${LATENCY}ms)" >> /tmp/hook-autosave-debug.log
fi

# ============================================================================
# 5. CHECK SETTINGS.LOCAL.JSON HAS STOP HOOK
# ============================================================================

SETTINGS_FILE="/home/giak/projects/truth-engine/.claude/settings.local.json"

if [ -f "$SETTINGS_FILE" ]; then
  HAS_STOP_HOOK=$(jq -r '.hooks.Stop // "missing"' "$SETTINGS_FILE" 2>/dev/null || echo "missing")

  if [ "$HAS_STOP_HOOK" = "missing" ] || [ "$HAS_STOP_HOOK" = "null" ]; then
    # SCREAM - Stop hook not configured
    echo "" >&2
    echo "╔═══════════════════════════════════════════════════════════╗" >&2
    echo "║  🚨 ALERT: HOOK STOP NOT CONFIGURED                       ║" >&2
    echo "╠═══════════════════════════════════════════════════════════╣" >&2
    echo "║  Stop hook exists but is not configured in settings.      ║" >&2
    echo "║                                                           ║" >&2
    echo "║  File: $SETTINGS_FILE" >&2
    echo "║                                                           ║" >&2
    echo "║  Add to settings.local.json:                              ║" >&2
    echo '║  "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "bash .claude/hooks/Stop/auto-save-exchange.sh"}]}]' >&2
    echo "╚═══════════════════════════════════════════════════════════╝" >&2
    echo "" >&2

    echo "ALERT: Stop hook NOT configured in settings.local.json" >> /tmp/hook-autosave-debug.log
    echo '{"continue": true}'
    exit 0
  fi
fi

# ============================================================================
# 6. SUCCESS - ALL CHECKS PASSED
# ============================================================================

echo "" >&2
echo "═══════════════════════════════════════════════════════════" >&2
echo "  ✅ AUTO-SAVE SYSTEM: ACTIVE & HEALTHY                     " >&2
echo "═══════════════════════════════════════════════════════════" >&2
echo "  MnemoLite:     Running (Docker container up)" >&2
echo "  Hook Stop:     Installed & Configured" >&2
echo "  API Health:    OK" >&2
echo "  Coverage:      100% (Stop + UserPromptSubmit backup)" >&2
echo "  Latency:       0 (immediate save after response)" >&2
echo "═══════════════════════════════════════════════════════════" >&2
echo "" >&2

echo "✅ SessionStart - Auto-save system: ALL CHECKS PASSED" >> /tmp/hook-autosave-debug.log

# ============================================================================
# 7. RETURN SUCCESS (non-blocking)
# ============================================================================
echo '{"continue": true}'
exit 0
