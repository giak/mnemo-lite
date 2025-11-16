#!/bin/bash

# Test cases for clean_user_message function
# Extract only the function definition (to avoid script execution)
SCRIPT_PATH="/home/giak/Work/MnemoLite/scripts/save-conversation-from-hook.sh"

# Try to source just the function (if it exists)
if grep -q "^clean_user_message()" "$SCRIPT_PATH" 2>/dev/null; then
  # Extract function definition
  eval "$(sed -n '/^clean_user_message()/,/^}/p' "$SCRIPT_PATH")"
else
  echo "ERROR: clean_user_message function not found"
  exit 1
fi

# Test 1: Remove <ide_opened_file> pollution
INPUT1='<ide_opened_file>The user opened /path/to/file</ide_opened_file>
test_fix_2025'
EXPECTED1='test_fix_2025'
RESULT1=$(clean_user_message "$INPUT1")
echo "Test 1: ${RESULT1}"
[[ "$RESULT1" == "$EXPECTED1" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT1)"

# Test 2: Remove <system-reminder>
INPUT2='<system-reminder>Some system message</system-reminder>
bozo'
EXPECTED2='bozo'
RESULT2=$(clean_user_message "$INPUT2")
echo "Test 2: ${RESULT2}"
[[ "$RESULT2" == "$EXPECTED2" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT2)"

# Test 3: Remove multiple tags
INPUT3='<ide_opened_file>...</ide_opened_file>
<system-reminder>...</system-reminder>
recherche "test_fix_2025"'
EXPECTED3='recherche "test_fix_2025"'
RESULT3=$(clean_user_message "$INPUT3")
echo "Test 3: ${RESULT3}"
[[ "$RESULT3" == "$EXPECTED3" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT3)"

# Test 4: Keep regular text unchanged
INPUT4='This is a normal user message'
EXPECTED4='This is a normal user message'
RESULT4=$(clean_user_message "$INPUT4")
echo "Test 4: ${RESULT4}"
[[ "$RESULT4" == "$EXPECTED4" ]] && echo "✓ PASS" || echo "✗ FAIL (got: $RESULT4)"
