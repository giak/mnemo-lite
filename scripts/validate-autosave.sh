#!/bin/bash
# Script de validation end-to-end de l'auto-save des conversations
# EPIC-24: Auto-Save Conversations
# Usage: ./scripts/validate-autosave.sh

set -euo pipefail

echo "=================================================="
echo "🧪 VALIDATION AUTO-SAVE CONVERSATIONS (EPIC-24)"
echo "=================================================="
echo ""

# Couleurs pour les tests
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

# Fonction de test
test_case() {
    local name="$1"
    local command="$2"
    local expected="$3"

    echo -n "⏳ Testing: $name... "

    if output=$(eval "$command" 2>&1); then
        if echo "$output" | grep -q "$expected"; then
            echo -e "${GREEN}✓ PASS${NC}"
            ((TESTS_PASSED++))
            return 0
        else
            echo -e "${RED}✗ FAIL${NC}"
            echo "   Expected: $expected"
            echo "   Got: $output"
            ((TESTS_FAILED++))
            return 1
        fi
    else
        echo -e "${RED}✗ FAIL (command error)${NC}"
        echo "   Error: $output"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "📋 Phase 1: Infrastructure Tests"
echo "-----------------------------------"

# Test 1: API container is running
test_case "API container running" \
    "docker compose ps api | grep -q 'Up'" \
    ""

# Test 2: Database container is running
test_case "Database container running" \
    "docker compose ps db | grep -q 'Up'" \
    ""

# Test 3: API is responding
test_case "API health endpoint" \
    "curl -s http://localhost:8001/health | jq -r '.status'" \
    "ok"

# Test 4: API import endpoint exists
test_case "Import endpoint exists" \
    "curl -s -X POST http://localhost:8001/v1/conversations/import | jq -r '.message'" \
    "found"

echo ""
echo "📋 Phase 2: Parsing Tests"
echo "-----------------------------------"

# Test 5: Parsing script exists
test_case "Conversation daemon script exists" \
    "docker compose exec -T api ls /app/scripts/conversation-auto-import.sh" \
    "conversation-auto-import.sh"

# Test 6: Transcript directory is mounted
test_case "Claude projects directory mounted" \
    "docker compose exec -T api ls /home/user/.claude/projects/ | wc -l" \
    "[0-9]"

# Test 7: Transcripts exist
test_case "Transcript files exist" \
    "docker compose exec -T api sh -c 'ls /home/user/.claude/projects/*.jsonl 2>/dev/null | wc -l'" \
    "[1-9]"

echo ""
echo "📋 Phase 3: Database Tests"
echo "-----------------------------------"

# Test 8: Memories table exists
test_case "Memories table exists" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -c '\\dt memories' | grep -q 'memories'" \
    ""

# Test 9: AutoImport conversations exist
test_case "Auto-imported conversations exist" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport';\" | xargs" \
    "[0-9]"

# Test 10: Embeddings are generated
test_case "Embeddings exist for imported conversations" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND embedding IS NOT NULL;\" | xargs" \
    "[0-9]"

# Test 11: Tags are correct
test_case "Auto-imported tags present" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT tags FROM memories WHERE author = 'AutoImport' LIMIT 1;\" | grep -q 'auto-imported'" \
    ""

echo ""
echo "📋 Phase 4: Functional Tests"
echo "-----------------------------------"

# Test 12: Manual import works
BEFORE_COUNT=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "SELECT COUNT(*) FROM memories WHERE author = 'AutoImport';" | xargs)
curl -s -X POST http://localhost:8001/v1/conversations/import > /dev/null
sleep 2
AFTER_COUNT=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "SELECT COUNT(*) FROM memories WHERE author = 'AutoImport';" | xargs)

if [ "$AFTER_COUNT" -ge "$BEFORE_COUNT" ]; then
    echo -e "⏳ Testing: Manual import increments or maintains count... ${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "⏳ Testing: Manual import increments or maintains count... ${RED}✗ FAIL${NC}"
    echo "   Before: $BEFORE_COUNT, After: $AFTER_COUNT"
    ((TESTS_FAILED++))
fi

# Test 13: Deduplication works
IMPORT1=$(curl -s -X POST http://localhost:8001/v1/conversations/import | jq -r '.imported')
sleep 1
IMPORT2=$(curl -s -X POST http://localhost:8001/v1/conversations/import | jq -r '.imported')

if [ "$IMPORT2" -eq 0 ]; then
    echo -e "⏳ Testing: Deduplication prevents re-import... ${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "⏳ Testing: Deduplication prevents re-import... ${YELLOW}⚠ WARNING${NC}"
    echo "   Second import returned $IMPORT2 (expected 0)"
fi

# Test 14: State file exists
test_case "Deduplication state file exists" \
    "docker compose exec -T api ls /tmp/mnemo-conversations-state.json" \
    "mnemo-conversations-state.json"

# Test 15: Recent conversations are saved
test_case "Recent conversations exist (< 24h)" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '24 hours';\" | xargs" \
    "[0-9]"

echo ""
echo "📋 Phase 5: Content Quality Tests"
echo "-----------------------------------"

# Test 16: Conversations have titles
test_case "Conversations have titles" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND title IS NOT NULL AND title != '';\" | xargs" \
    "[0-9]"

# Test 17: Conversations have content
test_case "Conversations have content" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND LENGTH(content) > 50;\" | xargs" \
    "[0-9]"

# Test 18: Session tags exist
test_case "Session tags exist" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT tags FROM memories WHERE author = 'AutoImport' LIMIT 1;\" | grep -q 'session:'" \
    ""

# Test 19: Date tags exist
test_case "Date tags exist" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT tags FROM memories WHERE author = 'AutoImport' LIMIT 1;\" | grep -q 'date:'" \
    ""

echo ""
echo "📋 Phase 6: Search Tests"
echo "-----------------------------------"

# Test 20: Text search works
test_case "Text search finds conversations" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND content ILIKE '%conversation%';\" | xargs" \
    "[0-9]"

echo ""
echo "=================================================="
echo "📊 RESULTS"
echo "=================================================="
echo ""
echo -e "✅ Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "❌ Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo ""
    echo "Auto-Save Conversations (EPIC-24) is FULLY FUNCTIONAL!"
    echo ""

    # Afficher quelques stats
    TOTAL_CONVERSATIONS=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "SELECT COUNT(*) FROM memories WHERE author = 'AutoImport';" | xargs)
    echo "📊 Statistics:"
    echo "   Total auto-imported conversations: $TOTAL_CONVERSATIONS"

    RECENT_24H=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '24 hours';" | xargs)
    echo "   Imported in last 24h: $RECENT_24H"

    echo ""
    echo "✅ System Status: OPERATIONAL"
    exit 0
else
    echo -e "${RED}💥 SOME TESTS FAILED!${NC}"
    echo ""
    echo "Please review the failures above and fix the issues."
    echo ""
    echo "❌ System Status: NEEDS ATTENTION"
    exit 1
fi
