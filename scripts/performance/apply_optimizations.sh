#!/bin/bash
# Apply performance optimizations to MnemoLite
# Usage: ./apply_optimizations.sh [test|apply]

set -e

MODE=${1:-test}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 MnemoLite Performance Optimization Script"
echo "============================================="

# Function to test current performance
test_performance() {
    echo -e "\n${YELLOW}Testing current performance...${NC}"

    # Quick health check
    echo -n "Health endpoint: "
    time curl -s http://localhost:8001/health -o /dev/null

    # Test event creation
    echo -n "Create event: "
    time curl -X POST http://localhost:8001/v1/events/ \
        -H "Content-Type: application/json" \
        -d '{"content": {"text": "Performance test"}}' \
        -s -o /dev/null

    # Test search
    echo -n "Search: "
    time curl -X POST http://localhost:8001/v1/search/ \
        -H "Content-Type: application/json" \
        -d '{"limit": 5}' \
        -s -o /dev/null

    echo ""
}

# Function to apply optimizations
apply_optimizations() {
    echo -e "\n${BLUE}Applying optimizations...${NC}"

    # 1. Update main.py with optimized configuration
    echo -e "${GREEN}✓${NC} Updating database pool configuration..."

    # Backup original
    cp api/main.py api/main.py.backup

    # Apply optimized settings based on environment
    if grep -q "pool_size=3" api/main.py; then
        sed -i 's/pool_size=3/pool_size=20/g' api/main.py
        sed -i 's/max_overflow=1/max_overflow=10/g' api/main.py
        echo -e "${GREEN}✓${NC} Pool size increased: 3 → 20"
    fi

    # 2. Add cache endpoints to event routes
    if [ ! -f "api/routes/event_routes_original.py" ]; then
        cp api/routes/event_routes.py api/routes/event_routes_original.py
    fi

    # 3. Import and initialize cache in event routes
    if ! grep -q "simple_memory_cache" api/routes/event_routes.py; then
        cat >> api/routes/event_routes.py << 'EOF'

# Performance optimization: Add caching
try:
    from services.simple_memory_cache import get_event_cache, get_all_cache_stats
    _event_cache = get_event_cache()

    @router.get("/cache/stats")
    async def get_cache_stats():
        """Get cache statistics."""
        return await get_all_cache_stats()

    logger.info("Cache optimization enabled for event routes")
except ImportError:
    logger.warning("Cache module not found, running without cache optimization")
EOF
        echo -e "${GREEN}✓${NC} Cache added to event routes"
    fi

    # 4. Restart API container to apply changes
    echo -e "${YELLOW}Restarting API container...${NC}"
    docker-compose restart api

    # Wait for API to be ready
    echo -n "Waiting for API to be ready"
    for i in {1..30}; do
        if curl -s http://localhost:8001/health > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            break
        fi
        echo -n "."
        sleep 1
    done
}

# Function to benchmark after optimization
benchmark() {
    echo -e "\n${YELLOW}Running benchmark...${NC}"

    # Simple load test
    echo "Sending 100 requests to test performance..."

    START=$(date +%s)

    for i in {1..100}; do
        curl -s http://localhost:8001/health -o /dev/null &
        if [ $((i % 10)) -eq 0 ]; then
            echo -n "."
        fi
    done
    wait

    END=$(date +%s)
    DURATION=$((END - START))

    echo -e "\n${GREEN}Benchmark complete!${NC}"
    echo "Time for 100 requests: ${DURATION} seconds"
    echo "Average: $((100 / DURATION)) req/s"
}

# Function to show cache statistics
show_cache_stats() {
    echo -e "\n${BLUE}Cache Statistics:${NC}"
    curl -s http://localhost:8001/v1/events/cache/stats 2>/dev/null | jq . || echo "Cache stats not available yet"
}

# Main execution
case $MODE in
    test)
        echo -e "${YELLOW}Mode: TEST - Testing current performance${NC}"
        test_performance
        ;;

    apply)
        echo -e "${BLUE}Mode: APPLY - Applying optimizations${NC}"

        # Test before
        echo -e "\n${YELLOW}=== BEFORE OPTIMIZATION ===${NC}"
        test_performance

        # Apply optimizations
        apply_optimizations

        # Wait for restart
        sleep 5

        # Test after
        echo -e "\n${YELLOW}=== AFTER OPTIMIZATION ===${NC}"
        test_performance

        # Show improvement
        echo -e "\n${GREEN}✅ Optimizations applied successfully!${NC}"
        show_cache_stats
        ;;

    benchmark)
        echo -e "${YELLOW}Mode: BENCHMARK - Running performance benchmark${NC}"
        benchmark
        show_cache_stats
        ;;

    rollback)
        echo -e "${RED}Mode: ROLLBACK - Reverting optimizations${NC}"

        # Restore backups
        if [ -f "api/main.py.backup" ]; then
            mv api/main.py.backup api/main.py
            echo -e "${GREEN}✓${NC} main.py restored"
        fi

        if [ -f "api/routes/event_routes_original.py" ]; then
            mv api/routes/event_routes_original.py api/routes/event_routes.py
            echo -e "${GREEN}✓${NC} event_routes.py restored"
        fi

        docker-compose restart api
        echo -e "${GREEN}✓${NC} Rollback complete"
        ;;

    *)
        echo "Usage: $0 [test|apply|benchmark|rollback]"
        echo ""
        echo "  test      - Test current performance"
        echo "  apply     - Apply optimizations"
        echo "  benchmark - Run performance benchmark"
        echo "  rollback  - Revert optimizations"
        exit 1
        ;;
esac

echo -e "\n${BLUE}=============================================${NC}"
echo "Done!"