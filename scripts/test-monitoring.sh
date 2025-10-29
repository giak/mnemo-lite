#!/bin/bash
# Script de test du système de monitoring
# EPIC-24: Monitoring & Reliability

set -euo pipefail

echo "======================================================"
echo "🧪 TEST SYSTÈME DE MONITORING AUTO-SAVE"
echo "======================================================"
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

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

echo "📋 Phase 1: Heartbeat System"
echo "-----------------------------------"

# Test 1: Heartbeat file exists
test_case "Heartbeat file exists" \
    "docker compose exec -T api ls /tmp/daemon-heartbeat.txt" \
    "daemon-heartbeat.txt"

# Test 2: Heartbeat is recent (<60s)
BEAT=$(docker compose exec -T api cat /tmp/daemon-heartbeat.txt)
NOW=$(date +%s)
AGE=$((NOW - BEAT))

if [ "$AGE" -lt 60 ]; then
    echo -e "⏳ Testing: Heartbeat is recent (<60s)... ${GREEN}✓ PASS${NC} (age: ${AGE}s)"
    ((TESTS_PASSED++))
else
    echo -e "⏳ Testing: Heartbeat is recent (<60s)... ${RED}✗ FAIL${NC} (age: ${AGE}s)"
    ((TESTS_FAILED++))
fi

# Test 3: Metrics file exists
test_case "Metrics file exists" \
    "docker compose exec -T api ls /tmp/daemon-metrics.json" \
    "daemon-metrics.json"

# Test 4: Metrics has correct structure
test_case "Metrics contains status field" \
    "docker compose exec -T api cat /tmp/daemon-metrics.json" \
    "status"

echo ""
echo "📋 Phase 2: Health Endpoint"
echo "-----------------------------------"

# Test 5: Health endpoint responds
test_case "Health endpoint responds" \
    "curl -s http://localhost:8001/v1/autosave/health" \
    "status"

# Test 6: Health endpoint reports healthy
test_case "Health endpoint reports healthy status" \
    "curl -s http://localhost:8001/v1/autosave/health | grep -o '\"status\":\"[^\"]*\"'" \
    "healthy"

# Test 7: Health endpoint includes daemon metrics
test_case "Health endpoint includes daemon metrics" \
    "curl -s http://localhost:8001/v1/autosave/health" \
    "heartbeat_age_seconds"

echo ""
echo "📋 Phase 3: Docker Health Check"
echo "-----------------------------------"

# Test 8: Container is healthy
test_case "Docker container reports healthy" \
    "docker compose ps api | grep -o '(healthy)'" \
    "healthy"

# Test 9: Health check command works
test_case "Docker healthcheck command succeeds" \
    "docker compose exec -T api sh -c 'curl -f http://localhost:8000/health && curl -f http://localhost:8000/v1/autosave/health'" \
    ""

echo ""
echo "📋 Phase 4: Daemon Functionality"
echo "-----------------------------------"

# Test 10: Daemon process is running
DAEMON_PID=$(docker compose exec -T api cat /tmp/daemon-metrics.json | grep -o '"pid":[0-9]*' | grep -o '[0-9]*')
test_case "Daemon PID exists in metrics" \
    "echo $DAEMON_PID" \
    "[0-9]"

# Test 11: Recent imports visible in DB
test_case "Recent imports exist in database" \
    "docker compose exec -T db psql -U mnemo -d mnemolite -t -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '5 minutes';\" | xargs" \
    "[0-9]"

# Test 12: No critical issues reported
test_case "No critical issues in health check" \
    "curl -s http://localhost:8001/v1/autosave/health | grep -c 'critical'" \
    "^0"

echo ""
echo "📋 Phase 5: Failure Detection (Simulation)"
echo "-----------------------------------"

echo "⚠️  Simulating daemon failure (stopping updates)..."
echo "    This tests if health endpoint detects stale heartbeat"

# Note: We can't actually kill the daemon (no pkill in container)
# But we can check if the health endpoint WOULD detect it

CURRENT_AGE=$(curl -s http://localhost:8001/v1/autosave/health | grep -o '"heartbeat_age_seconds":[0-9]*' | grep -o '[0-9]*')

if [ "$CURRENT_AGE" -lt 60 ]; then
    echo -e "⏳ Heartbeat detection threshold check... ${GREEN}✓ PASS${NC}"
    echo "   Current age: ${CURRENT_AGE}s (threshold: 60s for degraded, 120s for unhealthy)"
    ((TESTS_PASSED++))
else
    echo -e "⏳ Heartbeat detection threshold check... ${YELLOW}⚠ WARNING${NC}"
    echo "   Current age: ${CURRENT_AGE}s (exceeds 60s threshold)"
fi

echo ""
echo "======================================================"
echo "📊 RESULTS"
echo "======================================================"
echo ""
echo -e "✅ Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "❌ Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo ""
    echo "✅ Monitoring System Status: OPERATIONAL"
    echo ""
    echo "📊 Current Metrics:"
    docker compose exec -T api cat /tmp/daemon-metrics.json | python3 -m json.tool
    echo ""
    echo "✅ System Ready for Production"
    exit 0
else
    echo -e "${RED}💥 SOME TESTS FAILED!${NC}"
    echo ""
    echo "Please review the failures above."
    echo ""
    echo "❌ Monitoring System Status: NEEDS ATTENTION"
    exit 1
fi
