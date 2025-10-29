#!/bin/bash
# Auto-import Claude Code conversations via API
# EPIC-24: Simple daemon that calls /v1/conversations/import

set -uo pipefail  # Removed -e to prevent exit on curl failures

API_URL="${API_URL:-http://localhost:8000}"
POLL_INTERVAL="${POLL_INTERVAL:-30}"
HEARTBEAT_FILE="/tmp/daemon-heartbeat.txt"
METRICS_FILE="/tmp/daemon-metrics.json"

CONSECUTIVE_FAILURES=0
TOTAL_IMPORTED=0
START_TIME=$(date +%s)

echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | MnemoLite Conversation Auto-Save Daemon Starting"
echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | API endpoint: $API_URL/v1/conversations/import"
echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | Poll interval: ${POLL_INTERVAL}s"
echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | Heartbeat: $HEARTBEAT_FILE"

# Wait for API to be ready
echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
        echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | API is ready!"
        break
    fi
    sleep 2
done

# Function to update heartbeat
update_heartbeat() {
    echo "$(date +%s)" > "$HEARTBEAT_FILE"
}

# Function to update metrics
update_metrics() {
    local status=$1
    local last_import_count=$2

    NOW=$(date +%s)
    UPTIME=$((NOW - START_TIME))

    cat > "$METRICS_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$status",
  "last_poll": "$(date -Iseconds)",
  "consecutive_failures": $CONSECUTIVE_FAILURES,
  "total_imported": $TOTAL_IMPORTED,
  "last_import_count": $last_import_count,
  "uptime_seconds": $UPTIME,
  "pid": $$
}
EOF
}

while true; do
    # Update heartbeat at start of loop
    update_heartbeat

    # Call import endpoint
    RESPONSE=$(curl -s -X POST "$API_URL/v1/conversations/import" -H "Content-Type: application/json" 2>&1)

    # Simple check if imported > 0 (without jq)
    if echo "$RESPONSE" | grep -q '"imported"'; then
        # Extract imported count (simple grep, no jq needed)
        IMPORTED=$(echo "$RESPONSE" | grep -o '"imported":[0-9]*' | grep -o '[0-9]*')

        if [ "$IMPORTED" -gt 0 ] 2>/dev/null; then
            echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | INFO  | ✓ Imported $IMPORTED new conversation(s)"
            TOTAL_IMPORTED=$((TOTAL_IMPORTED + IMPORTED))
            CONSECUTIVE_FAILURES=0
            update_metrics "healthy" "$IMPORTED"
        else
            echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | DEBUG | No new conversations found"
            CONSECUTIVE_FAILURES=0
            update_metrics "healthy" 0
        fi
    else
        echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | ERROR | API call failed: $RESPONSE"
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        update_metrics "degraded" 0

        # Alert if too many consecutive failures
        if [ "$CONSECUTIVE_FAILURES" -ge 5 ]; then
            echo "[DAEMON] $(date '+%Y-%m-%d %H:%M:%S') | CRITICAL | ${CONSECUTIVE_FAILURES} consecutive failures!"
            update_metrics "critical" 0
        fi
    fi

    # Sleep
    sleep "$POLL_INTERVAL"
done
