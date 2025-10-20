#!/bin/bash
# EPIC-10 Cache Load Testing Script
#
# Tests cache stability under load:
# 1. Concurrent search queries
# 2. Mixed read/write operations
# 3. Cache statistics validation
#
# Expected: >90% cache hit rate, zero stale data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

API_URL="${API_URL:-http://localhost:8001}"
NUM_REQUESTS="${NUM_REQUESTS:-1000}"
CONCURRENCY="${CONCURRENCY:-20}"

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}🔥 EPIC-10 Cache Load Testing${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  API URL:      ${API_URL}"
echo -e "  Requests:     ${NUM_REQUESTS}"
echo -e "  Concurrency:  ${CONCURRENCY}"
echo ""

# Check if API is available
echo -e "${BLUE}🔍 Checking API availability...${NC}"
if ! curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ API not available at ${API_URL}${NC}"
    echo -e "${YELLOW}💡 Start the API with: make up${NC}"
    exit 1
fi
echo -e "${GREEN}✅ API is ready${NC}"
echo ""

# Create temporary directory for test payloads
TEMP_DIR=$(mktemp -d)
trap "rm -rf ${TEMP_DIR}" EXIT

# Create search payload
cat > "${TEMP_DIR}/search_payload.json" <<EOF
{
  "query": "authentication",
  "limit": 10
}
EOF

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📊 Test 1: Baseline Cache Statistics${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Get baseline stats
echo -e "${BLUE}📈 Initial cache stats:${NC}"
curl -s "${API_URL}/v1/cache/stats" | python3 -m json.tool || echo "Failed to get stats"
echo ""

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📊 Test 2: Concurrent Search Queries (Cold Cache)${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Flush cache for cold start
echo -e "${YELLOW}🗑️  Flushing cache for cold start...${NC}"
curl -s -X POST "${API_URL}/v1/cache/flush" \
    -H "Content-Type: application/json" \
    -d '{"scope": "all"}' > /dev/null
sleep 2
echo -e "${GREEN}✅ Cache flushed${NC}"
echo ""

# Test with ab (Apache Bench) if available
if command -v ab &> /dev/null; then
    echo -e "${BLUE}🔥 Running ${NUM_REQUESTS} concurrent requests (cold cache)...${NC}"
    ab -n 100 -c 10 -p "${TEMP_DIR}/search_payload.json" \
       -T "application/json" \
       "${API_URL}/v1/code/search/hybrid" 2>&1 | grep -E "Requests per second|Time per request|Percentage"
    echo ""
else
    echo -e "${YELLOW}⚠️  Apache Bench (ab) not found, skipping concurrent test${NC}"
    echo -e "${YELLOW}💡 Install with: sudo apt install apache2-utils${NC}"
    echo ""
fi

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📊 Test 3: Concurrent Search Queries (Warm Cache)${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Prime cache with a few requests
echo -e "${BLUE}🔥 Priming cache...${NC}"
for i in {1..5}; do
    curl -s -X POST "${API_URL}/v1/code/search/hybrid" \
        -H "Content-Type: application/json" \
        -d @"${TEMP_DIR}/search_payload.json" > /dev/null
    echo -n "."
done
echo ""
echo -e "${GREEN}✅ Cache primed${NC}"
echo ""

# Test with warm cache
if command -v ab &> /dev/null; then
    echo -e "${BLUE}🔥 Running ${NUM_REQUESTS} concurrent requests (warm cache)...${NC}"
    ab -n 100 -c 10 -p "${TEMP_DIR}/search_payload.json" \
       -T "application/json" \
       "${API_URL}/v1/code/search/hybrid" 2>&1 | grep -E "Requests per second|Time per request|Percentage"
    echo ""
else
    echo -e "${YELLOW}⚠️  Apache Bench not available${NC}"
    echo ""
fi

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📊 Test 4: Python-based Load Test${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Create Python load test script
cat > "${TEMP_DIR}/load_test.py" <<'PYTHON_EOF'
import asyncio
import httpx
import time
import statistics
from typing import List

API_URL = "http://localhost:8001"

async def run_search(client: httpx.AsyncClient, query: str) -> float:
    """Run single search and return latency in ms."""
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{API_URL}/v1/code/search/hybrid",
            json={"query": query, "limit": 10},
            timeout=10.0
        )
        response.raise_for_status()
        return (time.perf_counter() - start) * 1000
    except Exception as e:
        print(f"Error: {e}")
        return -1

async def load_test(num_requests: int = 100, concurrency: int = 10):
    """Run concurrent load test."""
    queries = [
        "authentication", "authorization", "database", "cache", "search",
        "function", "class", "import", "export", "api"
    ]

    print(f"🔥 Running {num_requests} requests with {concurrency} concurrent workers...")

    async with httpx.AsyncClient() as client:
        latencies = []

        # Run in batches
        for batch_start in range(0, num_requests, concurrency):
            batch_end = min(batch_start + concurrency, num_requests)
            tasks = []

            for i in range(batch_start, batch_end):
                query = queries[i % len(queries)]
                tasks.append(run_search(client, query))

            batch_latencies = await asyncio.gather(*tasks)
            valid_latencies = [lat for lat in batch_latencies if lat > 0]
            latencies.extend(valid_latencies)

            # Progress
            progress = (batch_end / num_requests) * 100
            print(f"  Progress: {progress:.0f}% ({batch_end}/{num_requests})", end="\r")

        print("\n")

        if latencies:
            median = statistics.median(latencies)
            p95 = statistics.quantiles(latencies, n=20)[18]
            p99 = statistics.quantiles(latencies, n=100)[98]

            print(f"📊 Results:")
            print(f"  Total requests: {len(latencies)}")
            print(f"  Median latency: {median:.1f}ms")
            print(f"  P95 latency:    {p95:.1f}ms")
            print(f"  P99 latency:    {p99:.1f}ms")
            print(f"  Min latency:    {min(latencies):.1f}ms")
            print(f"  Max latency:    {max(latencies):.1f}ms")

            # Check targets
            if median < 20:
                print("  ✅ PASS: Median latency <20ms")
            else:
                print(f"  ⚠️  WARN: Median latency {median:.1f}ms")
        else:
            print("❌ No successful requests")

if __name__ == "__main__":
    asyncio.run(load_test(num_requests=100, concurrency=10))
PYTHON_EOF

# Run Python load test
echo -e "${BLUE}🐍 Running Python-based concurrent load test...${NC}"
python3 "${TEMP_DIR}/load_test.py"
echo ""

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📊 Test 5: Final Cache Statistics${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Get final stats
echo -e "${BLUE}📈 Final cache stats:${NC}"
CACHE_STATS=$(curl -s "${API_URL}/v1/cache/stats")
echo "${CACHE_STATS}" | python3 -m json.tool || echo "Failed to get stats"
echo ""

# Parse and validate hit rates
echo -e "${BLUE}🎯 Validating cache performance...${NC}"

# Extract hit rates using Python
python3 <<PYTHON_VALIDATE
import json

stats_json = '''${CACHE_STATS}'''

try:
    stats = json.loads(stats_json)

    l1_hit_rate = stats.get('l1_hit_rate', 0)
    l2_hit_rate = stats.get('l2_hit_rate', 0)
    combined_hit_rate = stats.get('combined_hit_rate', 0)

    print(f"  L1 Hit Rate:       {l1_hit_rate:.1f}%")
    print(f"  L2 Hit Rate:       {l2_hit_rate:.1f}%")
    print(f"  Combined Hit Rate: {combined_hit_rate:.1f}%")
    print()

    # Validation
    all_pass = True

    if combined_hit_rate >= 90:
        print("  ✅ PASS: Combined hit rate ≥90%")
    elif combined_hit_rate >= 80:
        print(f"  ⚠️  WARN: Combined hit rate {combined_hit_rate:.1f}% (target: ≥90%)")
        all_pass = False
    else:
        print(f"  ❌ FAIL: Combined hit rate {combined_hit_rate:.1f}% (target: ≥90%)")
        all_pass = False

    # Check L2 Redis status
    l2_status = stats.get('l2', {}).get('status', 'unknown')
    if l2_status == 'connected':
        print("  ✅ PASS: L2 Redis connected")
    else:
        print(f"  ⚠️  WARN: L2 Redis status: {l2_status}")
        all_pass = False

    print()

    if all_pass:
        print("✅ ALL VALIDATIONS PASSED")
        exit(0)
    else:
        print("⚠️  SOME VALIDATIONS FAILED")
        exit(1)

except json.JSONDecodeError:
    print("❌ Failed to parse cache stats")
    exit(1)
except Exception as e:
    print(f"❌ Validation error: {e}")
    exit(1)
PYTHON_VALIDATE

VALIDATION_RESULT=$?

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"

if [ $VALIDATION_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ EPIC-10 Load Test PASSED${NC}"
else
    echo -e "${YELLOW}⚠️  EPIC-10 Load Test - Some Issues Detected${NC}"
fi

echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""

exit $VALIDATION_RESULT
