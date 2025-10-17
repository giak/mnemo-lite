#!/bin/bash
# MnemoLite Complete Test Suite
# Usage: ./test_application.sh [quick|full|load]

# set -e  # Don't exit on error to see all results

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

MODE=${1:-quick}
BASE_URL="http://localhost:8001"

echo "🧪 MnemoLite Test Suite - Mode: $MODE"
echo "=================================="

# Function to test endpoint
test_endpoint() {
    local url=$1
    local expected=$2
    local method=${3:-GET}

    if [ "$method" = "GET" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    else
        status=$(curl -X "$method" -s -o /dev/null -w "%{http_code}" "$url")
    fi

    if [ "$status" = "$expected" ]; then
        echo -e "${GREEN}✓${NC} $url - Status: $status"
        return 0
    else
        echo -e "${RED}✗${NC} $url - Expected: $expected, Got: $status"
        return 1
    fi
}

# Quick tests
if [ "$MODE" = "quick" ] || [ "$MODE" = "full" ]; then
    echo -e "\n${YELLOW}1. Testing Core Endpoints${NC}"
    test_endpoint "$BASE_URL/health" "200"
    test_endpoint "$BASE_URL/docs" "200"
    test_endpoint "$BASE_URL/health/metrics" "200"

    echo -e "\n${YELLOW}2. Testing UI Pages${NC}"
    test_endpoint "$BASE_URL/ui/code/upload" "200"
    test_endpoint "$BASE_URL/ui/code/search" "200"
    test_endpoint "$BASE_URL/ui/code/graph" "200"
    test_endpoint "$BASE_URL/ui/code/dashboard" "200"
    test_endpoint "$BASE_URL/ui/code/repos" "200"

    echo -e "\n${YELLOW}3. Testing API Endpoints${NC}"
    test_endpoint "$BASE_URL/v1/events/" "405" "GET"  # Should be POST
    test_endpoint "$BASE_URL/v1/search/" "200" "GET"  # Accepts both GET and POST
    test_endpoint "$BASE_URL/v1/code/graph/stats" "200"
fi

# Full tests
if [ "$MODE" = "full" ]; then
    echo -e "\n${YELLOW}4. Running Python Tests${NC}"
    cd api
    python -m pytest tests/test_core -v --tb=short
    cd ..

    echo -e "\n${YELLOW}5. Testing Database Connection${NC}"
    docker exec mnemo-api python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_db():
    engine = create_async_engine('postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite')
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT COUNT(*) FROM events'))
        count = result.scalar()
        print(f'Events in DB: {count}')
    await engine.dispose()

asyncio.run(test_db())
"

    echo -e "\n${YELLOW}6. Testing Code Upload (Mock)${NC}"
    curl -X POST "$BASE_URL/v1/events/" \
        -H "Content-Type: application/json" \
        -d '{"content": {"text": "Test code upload", "type": "code"}}' \
        -s -o /dev/null -w "Upload test: %{http_code}\n"

    echo -e "\n${YELLOW}7. Testing Search${NC}"
    curl -X POST "$BASE_URL/v1/search/" \
        -H "Content-Type: application/json" \
        -d '{"query": "test", "limit": 5}' \
        -s | jq -r '.events | length' | xargs -I {} echo "Search returned {} results"
fi

# Load tests
if [ "$MODE" = "load" ]; then
    echo -e "\n${YELLOW}Starting Load Tests${NC}"

    # Check if locust is installed
    if ! command -v locust &> /dev/null; then
        echo "Installing Locust..."
        pip install locust
    fi

    echo "Starting Locust in headless mode..."
    echo "Simulating 10 users, spawn rate 2/s, for 30 seconds"

    locust -f /tmp/locust_load_test.py \
        --host "$BASE_URL" \
        --headless \
        --users 10 \
        --spawn-rate 2 \
        --run-time 30s \
        --only-summary
fi

echo -e "\n${GREEN}=================================="
echo "Test Suite Complete!"
echo "==================================${NC}"

# Summary
if [ "$MODE" = "quick" ]; then
    echo -e "\n📊 Quick test completed. Run './test_application.sh full' for comprehensive tests."
elif [ "$MODE" = "full" ]; then
    echo -e "\n📊 Full test completed. Run './test_application.sh load' for load testing."
elif [ "$MODE" = "load" ]; then
    echo -e "\n📊 Load test completed. Check results above for performance metrics."
fi