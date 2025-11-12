#!/bin/bash
# Run all hook tests
# Usage: ./run-all-tests.sh [--verbose]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERBOSE=false

if [ "${1:-}" = "--verbose" ]; then
  VERBOSE=true
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0

run_test_suite() {
  local test_file="$1"
  local test_name=$(basename "$test_file" .sh)

  TOTAL_SUITES=$((TOTAL_SUITES + 1))

  echo ""
  echo "========================================="
  echo "Running: $test_name"
  echo "========================================="

  if [ "$VERBOSE" = true ]; then
    bash "$test_file"
    exit_code=$?
  else
    OUTPUT=$(bash "$test_file" 2>&1)
    exit_code=$?
    # Show only summary line
    echo "$OUTPUT" | grep -E "(Results:|Status:)" || echo "$OUTPUT"
  fi

  if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC}: $test_name"
    PASSED_SUITES=$((PASSED_SUITES + 1))
  else
    echo -e "${RED}✗ FAILED${NC}: $test_name"
    FAILED_SUITES=$((FAILED_SUITES + 1))
    if [ "$VERBOSE" = false ]; then
      echo ""
      echo "Full output:"
      echo "$OUTPUT"
    fi
  fi
}

echo "========================================="
echo "MnemoLite Hook Test Suite"
echo "========================================="
echo "Location: $SCRIPT_DIR"
echo "Mode: $([ "$VERBOSE" = true ] && echo "VERBOSE" || echo "SUMMARY")"
echo ""

# Run unit tests
echo ">>> UNIT TESTS"
if [ -d "$SCRIPT_DIR/unit" ]; then
  for test in "$SCRIPT_DIR/unit"/test-*.sh; do
    if [ -f "$test" ]; then
      run_test_suite "$test"
    fi
  done
else
  echo "No unit tests found"
fi

# Run integration tests (skip for now as they may need Docker)
echo ""
echo ">>> INTEGRATION TESTS (skipped - require Docker)"
echo "Run manually: bash $SCRIPT_DIR/integration/test-centralized-service.sh"

# Final summary
echo ""
echo "========================================="
echo "FINAL SUMMARY"
echo "========================================="
echo "Test Suites: $TOTAL_SUITES"
echo -e "Passed:      ${GREEN}$PASSED_SUITES${NC}"
if [ $FAILED_SUITES -gt 0 ]; then
  echo -e "Failed:      ${RED}$FAILED_SUITES${NC}"
else
  echo "Failed:      0"
fi

echo ""
if [ $FAILED_SUITES -eq 0 ]; then
  echo -e "${GREEN}✅ ALL TEST SUITES PASSED${NC}"
  exit 0
else
  echo -e "${RED}❌ SOME TESTS FAILED${NC}"
  echo ""
  echo "To see full output, run with --verbose:"
  echo "  bash $0 --verbose"
  exit 1
fi
