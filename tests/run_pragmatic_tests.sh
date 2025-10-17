#!/bin/bash
# Run pragmatic tests for MnemoLite
# Focus on fast feedback and real-world scenarios

set -e  # Exit on error

echo "🧪 MnemoLite Pragmatic Test Suite"
echo "================================="
echo ""

# Check if we're in test environment
if [ -z "$TEST_DATABASE_URL" ]; then
    echo "⚠️  TEST_DATABASE_URL not set. Using Docker environment..."
    export TEST_DATABASE_URL="postgresql+asyncpg://mnemo:mnemopass@localhost:5432/mnemolite_test"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run test category
run_test_category() {
    local category=$1
    local path=$2
    local markers=$3

    echo -e "${YELLOW}▶ Running $category tests...${NC}"

    if [ -n "$markers" ]; then
        pytest $path -v -m "$markers" --tb=short
    else
        pytest $path -v --tb=short
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $category tests passed${NC}\n"
    else
        echo -e "${RED}✗ $category tests failed${NC}\n"
        exit 1
    fi
}

# Parse arguments
MODE=${1:-"fast"}

case $MODE in
    "fast")
        echo "Mode: FAST (core tests only, ~10 seconds)"
        echo ""

        # Core CRUD tests
        run_test_category "CRUD" "tests/test_core/test_event_crud.py" ""

        # Basic search tests (skip slow ones)
        run_test_category "Search" "tests/test_core/test_vector_search.py" "not slow"

        echo -e "${GREEN}✅ Fast tests completed!${NC}"
        ;;

    "full")
        echo "Mode: FULL (all tests except real embeddings, ~30 seconds)"
        echo ""

        # Core tests
        run_test_category "CRUD" "tests/test_core/" ""

        # Integration tests (skip real embeddings)
        run_test_category "Integration" "tests/test_integration/" "not real_embeddings"

        echo -e "${GREEN}✅ Full tests completed!${NC}"
        ;;

    "integration")
        echo "Mode: INTEGRATION (API flow tests, ~20 seconds)"
        echo ""

        run_test_category "API Integration" "tests/test_integration/test_api_flow.py" "integration and not real_embeddings"

        echo -e "${GREEN}✅ Integration tests completed!${NC}"
        ;;

    "perf")
        echo "Mode: PERFORMANCE (benchmark tests, ~15 seconds)"
        echo ""

        run_test_category "Performance" "tests/" "performance"

        echo -e "${GREEN}✅ Performance tests completed!${NC}"
        ;;

    "coverage")
        echo "Mode: COVERAGE (with coverage report)"
        echo ""

        pytest tests/test_core tests/test_integration \
            -v \
            -m "not real_embeddings and not slow" \
            --cov=api/db/repositories \
            --cov=api/services \
            --cov-report=term-missing \
            --cov-report=html

        echo -e "${GREEN}✅ Coverage report generated in htmlcov/${NC}"
        ;;

    "single")
        # Run a single test for debugging
        TEST_NAME=${2:-"test_create_event"}
        echo "Mode: SINGLE (running $TEST_NAME)"
        echo ""

        pytest -vv -s -k "$TEST_NAME"
        ;;

    *)
        echo "Usage: $0 [fast|full|integration|perf|coverage|single [test_name]]"
        echo ""
        echo "Modes:"
        echo "  fast        - Core CRUD and search tests only (~10s)"
        echo "  full        - All tests except real embeddings (~30s)"
        echo "  integration - API integration tests (~20s)"
        echo "  perf        - Performance benchmarks (~15s)"
        echo "  coverage    - Run with coverage report"
        echo "  single      - Run a single test by name"
        echo ""
        echo "Examples:"
        echo "  $0              # Run fast tests (default)"
        echo "  $0 full         # Run all tests"
        echo "  $0 single test_create_event  # Debug single test"
        exit 1
        ;;
esac

echo ""
echo "📊 Test Summary:"
echo "==============="

# Count test files and tests
TEST_FILES=$(find tests/test_core tests/test_integration -name "test_*.py" 2>/dev/null | wc -l)
TEST_FUNCTIONS=$(grep -r "async def test_" tests/test_core tests/test_integration 2>/dev/null | wc -l)

echo "Test files: $TEST_FILES"
echo "Test functions: $TEST_FUNCTIONS"
echo ""

# Optional: Show test timing
if [ "$MODE" == "fast" ] || [ "$MODE" == "full" ]; then
    echo "Slowest tests:"
    pytest tests/ -v --durations=5 -q 2>/dev/null | grep "slowest" -A 5 || true
fi