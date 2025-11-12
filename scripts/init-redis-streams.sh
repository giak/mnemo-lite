#!/bin/bash
# Initialize Redis Streams for MnemoLite Auto-Save
# Creates consumer group if doesn't exist

set -euo pipefail

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
STREAM_NAME="conversations:autosave"
GROUP_NAME="workers"

echo "Initializing Redis Streams..."
echo "  Stream: $STREAM_NAME"
echo "  Group: $GROUP_NAME"

# Wait for Redis to be ready
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; do
  echo "Waiting for Redis..."
  sleep 1
done

# Create consumer group (ignore error if already exists)
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
  XGROUP CREATE "$STREAM_NAME" "$GROUP_NAME" 0 MKSTREAM \
  2>&1 | grep -v "BUSYGROUP" || true

echo "✓ Redis Streams initialized"
echo "  Stream: $STREAM_NAME"
echo "  Group: $GROUP_NAME"

# Show stream info
echo ""
echo "Stream info:"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" XINFO STREAM "$STREAM_NAME" || echo "  (empty stream)"
