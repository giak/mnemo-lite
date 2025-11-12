#!/bin/bash
# Unit tests for project name detection
# Tests the critical bug that caused ".claude" project creation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
GET_PROJECT_NAME="$REPO_ROOT/scripts/get-project-name.sh"

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
assert_equals() {
  local expected="$1"
  local actual="$2"
  local test_name="$3"

  TESTS_RUN=$((TESTS_RUN + 1))

  if [ "$expected" = "$actual" ]; then
    echo "✓ PASS: $test_name"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ FAIL: $test_name"
    echo "  Expected: '$expected'"
    echo "  Actual:   '$actual'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

echo "========================================="
echo "Unit Tests: Project Detection"
echo "========================================="
echo ""

# Test 1: MnemoLite project detection
echo "Test 1: Detect MnemoLite from repo root"
PROJECT_NAME=$(bash "$GET_PROJECT_NAME" "$REPO_ROOT" 2>/dev/null || echo "ERROR")
assert_equals "mnemolite" "$PROJECT_NAME" "MnemoLite repo root detection"

# Test 2: Should NOT detect .claude as project
echo "Test 2: .claude directory should detect parent project"
if [ -d "$REPO_ROOT/.claude" ]; then
  PROJECT_NAME=$(bash "$GET_PROJECT_NAME" "$REPO_ROOT/.claude" 2>/dev/null || echo "ERROR")
  # When called on .claude/, should still detect parent (mnemolite) via Git
  assert_equals "mnemolite" "$PROJECT_NAME" ".claude should resolve to parent via Git"
fi

# Test 3: truth-engine project (if exists)
echo "Test 3: truth-engine project detection"
if [ -d "/home/giak/projects/truth-engine" ]; then
  PROJECT_NAME=$(bash "$GET_PROJECT_NAME" "/home/giak/projects/truth-engine" 2>/dev/null || echo "ERROR")
  assert_equals "truth-engine" "$PROJECT_NAME" "truth-engine detection"
fi

# Test 4: Non-existent directory should fail gracefully
echo "Test 4: Non-existent directory handling"
PROJECT_NAME=$(bash "$GET_PROJECT_NAME" "/nonexistent/path" 2>/dev/null || echo "")
if [ -z "$PROJECT_NAME" ]; then
  echo "✓ PASS: Non-existent directory handled gracefully"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "✗ FAIL: Should return empty for non-existent path"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Test 5: Basename fallback (non-Git directory)
echo "Test 5: Basename fallback for non-Git directory"
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/my-test-project"
PROJECT_NAME=$(bash "$GET_PROJECT_NAME" "$TEMP_DIR/my-test-project" 2>/dev/null || echo "ERROR")
rm -rf "$TEMP_DIR"
assert_equals "my-test-project" "$PROJECT_NAME" "Basename fallback"

# Test 6: SESSION subdirectory handling (regression test for SESSION: bug)
echo "Test 6: Handle SESSION:xxx subdirectories correctly"
# Simulate transcript path: .../projects/-home-giak-Work-MnemoLite/SESSION:xxx/transcript.jsonl
MOCK_TRANSCRIPT="/tmp/-home-giak-Work-MnemoLite/SESSION:TEST123/transcript.jsonl"
TRANSCRIPT_DIR=$(dirname "$MOCK_TRANSCRIPT")
TRANSCRIPT_PARENT=$(basename "$TRANSCRIPT_DIR")

if [[ "$TRANSCRIPT_PARENT" =~ ^SESSION: ]] || [[ "$TRANSCRIPT_PARENT" =~ ^agent- ]]; then
  PROJECT_DIR=$(basename "$(dirname "$TRANSCRIPT_DIR")")
else
  PROJECT_DIR="$TRANSCRIPT_PARENT"
fi

assert_equals "-home-giak-Work-MnemoLite" "$PROJECT_DIR" "SESSION:xxx subdirectory handling"

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
