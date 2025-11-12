#!/bin/bash
# Test suite for get-project-name.sh
# Tests various scenarios: Git repos, non-Git dirs, explicit paths

set -e

SCRIPT_PATH="/home/giak/Work/MnemoLite/scripts/get-project-name.sh"
PASSED=0
FAILED=0

echo "========================================"
echo "Testing: get-project-name.sh"
echo "========================================"

# Test 1: From Git repository root
echo -n "Test 1: Git repository root... "
cd /home/giak/Work/MnemoLite
RESULT=$(bash "$SCRIPT_PATH")
if [ "$RESULT" = "mnemolite" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: mnemolite, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi

# Test 2: From Git subdirectory (should return root)
echo -n "Test 2: Git subdirectory... "
cd /home/giak/Work/MnemoLite/api
RESULT=$(bash "$SCRIPT_PATH")
if [ "$RESULT" = "mnemolite" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: mnemolite, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi

# Test 3: With explicit path argument
echo -n "Test 3: Explicit path argument... "
RESULT=$(bash "$SCRIPT_PATH" /home/giak/Work/MnemoLite)
if [ "$RESULT" = "mnemolite" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: mnemolite, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi

# Test 4: Non-Git directory (fallback to basename)
echo -n "Test 4: Non-Git directory fallback... "
mkdir -p /tmp/TestProject123
RESULT=$(bash "$SCRIPT_PATH" /tmp/TestProject123)
if [ "$RESULT" = "testproject123" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: testproject123, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi
rm -rf /tmp/TestProject123

# Test 5: Uppercase directory name (should lowercase)
echo -n "Test 5: Uppercase normalization... "
mkdir -p /tmp/UPPERCASE_DIR
RESULT=$(bash "$SCRIPT_PATH" /tmp/UPPERCASE_DIR)
if [ "$RESULT" = "uppercase_dir" ]; then
  echo "✅ PASS (got: $RESULT)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAIL (expected: uppercase_dir, got: $RESULT)"
  FAILED=$((FAILED + 1))
fi
rm -rf /tmp/UPPERCASE_DIR

# Summary
echo "========================================"
echo "Results: $PASSED passed, $FAILED failed"
echo "========================================"

if [ $FAILED -eq 0 ]; then
  echo "✅ All tests passed!"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi
