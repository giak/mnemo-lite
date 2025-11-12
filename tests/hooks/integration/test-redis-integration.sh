#!/bin/bash
# Test Redis Streams integration

set -euo pipefail

echo "========================================="
echo "Test: Redis Streams Integration"
echo "========================================="

# Helper function to run redis-cli via Docker
redis_cli() {
  docker compose -f /home/giak/Work/MnemoLite/docker-compose.yml exec -T redis redis-cli "$@"
}

# Prerequisites
echo "Checking prerequisites..."
docker compose -f /home/giak/Work/MnemoLite/docker-compose.yml exec -T redis redis-cli ping >/dev/null || { echo "✗ Redis not running"; exit 1; }
echo "✓ Prerequisites OK"

# Test 1: Service pushes to Redis
echo ""
echo "Test 1: Service pushes message to Redis"
BEFORE_COUNT=$(redis_cli XLEN conversations:autosave)
echo "  Before: $BEFORE_COUNT messages"

# Create test transcript with valid JSON format
TEST_TRANSCRIPT="/tmp/test-transcript-$(date +%s).jsonl"
cat > "$TEST_TRANSCRIPT" << 'EOF'
{"message":{"role":"user","content":"Test user message"}}
{"message":{"role":"assistant","content":[{"type":"text","text":"Test assistant response"}]}}
EOF

# Call service with test data
bash /home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh \
  "$TEST_TRANSCRIPT" \
  "test-redis-$(date +%s)" \
  "stop" || true

AFTER_COUNT=$(redis_cli XLEN conversations:autosave)
echo "  After: $AFTER_COUNT messages"

if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
  echo "  ✓ Message added to stream"
else
  echo "  ✗ No message added"
  rm -f "$TEST_TRANSCRIPT"
  exit 1
fi

# Test 2: Read message from stream
echo ""
echo "Test 2: Read last message from stream"
LAST_MSG=$(redis_cli XREVRANGE conversations:autosave + - COUNT 1)
echo "$LAST_MSG" | grep -q "project_name" && echo "  ✓ Message contains project_name" || { echo "  ✗ Invalid message"; rm -f "$TEST_TRANSCRIPT"; exit 1; }

# Cleanup
rm -f "$TEST_TRANSCRIPT"

echo ""
echo "========================================="
echo "✅ ALL TESTS PASSED"
echo "========================================="
