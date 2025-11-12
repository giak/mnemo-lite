#!/bin/bash
# Unit tests for message extraction from Claude Code transcripts
# Tests the critical bug: .role vs .message.role

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE_FILE="$SCRIPT_DIR/../fixtures/sample-transcript.jsonl"

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local test_name="$3"

  TESTS_RUN=$((TESTS_RUN + 1))

  if echo "$haystack" | grep -q "$needle"; then
    echo "✓ PASS: $test_name"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ FAIL: $test_name"
    echo "  Expected to contain: '$needle'"
    echo "  Actual output length: ${#haystack} chars"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

assert_not_empty() {
  local value="$1"
  local test_name="$2"

  TESTS_RUN=$((TESTS_RUN + 1))

  if [ -n "$value" ] && [ ${#value} -gt 10 ]; then
    echo "✓ PASS: $test_name (${#value} chars)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ FAIL: $test_name"
    echo "  Expected non-empty string, got: '$value'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

assert_empty() {
  local value="$1"
  local test_name="$2"

  TESTS_RUN=$((TESTS_RUN + 1))

  if [ -z "$value" ] || [ ${#value} -lt 5 ]; then
    echo "✓ PASS: $test_name"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ FAIL: $test_name"
    echo "  Expected empty, got: '$value' (${#value} chars)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

echo "========================================="
echo "Unit Tests: Message Extraction"
echo "========================================="
echo ""

# Test 1: Extract LAST user message (CORRECT format: .message.role)
echo "Test 1: Extract last user message (Claude Code format)"
LAST_USER=$(tail -100 "$FIXTURE_FILE" | jq -s '
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

assert_not_empty "$LAST_USER" "Extract last user message"
assert_contains "$LAST_USER" "Second user message" "Last user message content correct"

# Test 2: BROKEN format (.role instead of .message.role) should return NOTHING
echo ""
echo "Test 2: Verify broken format (.role) returns nothing"
BROKEN=$(tail -100 "$FIXTURE_FILE" | jq -s '
  [.[] | select(.role == "user")] |
  last |
  if . == null then "" else .content end
' 2>/dev/null | sed 's/^"//; s/"$//' || echo "")

assert_empty "$BROKEN" "Broken format (.role) should return empty"

# Test 3: Tool results should be filtered out
echo ""
echo "Test 3: Tool results should be excluded from user messages"
USER_MESSAGES=$(tail -100 "$FIXTURE_FILE" | jq -s '
  [.[] |
   select(.message.role == "user") |
   select(
     (.message.content | type) == "string" or
     ((.message.content | type) == "array" and
      (.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] | length
' 2>/dev/null || echo "0")

TESTS_RUN=$((TESTS_RUN + 1))
if [ "$USER_MESSAGES" -eq 2 ]; then
  echo "✓ PASS: Tool results excluded (found 2 real user messages)"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "✗ FAIL: Expected 2 user messages (excluding tool_result), got $USER_MESSAGES"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 4: Extract LAST assistant message
echo ""
echo "Test 4: Extract last assistant message"
LAST_ASSISTANT=$(tail -100 "$FIXTURE_FILE" | jq -s '
  [.[] | select(.message.role == "assistant")] |
  last |
  if . == null then ""
  elif (.message.content | type) == "array" then
    [.message.content[] | select(.type == "text") | .text] | join("\n")
  else
    .message.content
  end
' 2>/dev/null | sed 's/^"//; s/"$//' | sed 's/\\n/\n/g' || echo "")

assert_not_empty "$LAST_ASSISTANT" "Extract last assistant message"
assert_contains "$LAST_ASSISTANT" "Second assistant response" "Last assistant message content correct"

# Test 5: Count REAL user messages (for UserPromptSubmit logic)
echo ""
echo "Test 5: Count real user messages (excluding tool_result)"
USER_COUNT=$(tail -200 "$FIXTURE_FILE" | jq -s '
  [.[] |
   select(.message.role == "user") |
   select(
     (.message.content | type) == "string" or
     ((.message.content | type) == "array" and
      (.message.content | map(select(.type == "tool_result")) | length) == 0)
   )
  ] | length
' 2>/dev/null || echo "0")

TESTS_RUN=$((TESTS_RUN + 1))
if [ "$USER_COUNT" -ge 2 ]; then
  echo "✓ PASS: UserPromptSubmit would proceed (found $USER_COUNT user messages)"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "✗ FAIL: UserPromptSubmit needs ≥2 messages, got $USER_COUNT"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "========================================="
echo "Results: $TESTS_PASSED/$TESTS_RUN passed"
if [ $TESTS_FAILED -eq 0 ]; then
  echo "Status: ✅ ALL TESTS PASSED"
  exit 0
else
  echo "Status: ❌ $TESTS_FAILED TEST(S) FAILED"
  exit 1
fi
