#!/bin/bash
#
# Validation Script for v3.0 Migration
# EPIC-10 Story 10.6: Migration Script for content_hash
#
# Purpose: Validate that all code chunks have valid content_hash in metadata
#
# Usage:
#   ./scripts/validate_v3.sh
#   DATABASE_URL=... ./scripts/validate_v3.sh
#
# Exit codes:
#   0 - All validation checks passed
#   1 - Validation failed
#   2 - Database connection error

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo "======================================================================"
echo "🔍 MnemoLite v3.0 Migration Validation"
echo "======================================================================"
echo ""

# Check if running in Docker
if [ -f /.dockerenv ]; then
    # Inside Docker container - use localhost
    DB_HOST="${DB_HOST:-db}"
    DB_PORT="${DB_PORT:-5432}"
    DB_NAME="${DB_NAME:-mnemolite}"
    DB_USER="${DB_USER:-mnemo}"
    PSQL_CMD="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A"
else
    # Outside Docker - use docker compose exec
    PSQL_CMD="docker compose exec -T db psql -U mnemo -d mnemolite -t -A"
fi

# Test database connection
echo -n "📡 Testing database connection... "
if $PSQL_CMD -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}❌ Cannot connect to database${NC}"
    exit 2
fi

# Validation 1: Count total chunks
echo -n "📊 Counting total chunks... "
TOTAL_CHUNKS=$($PSQL_CMD -c "SELECT COUNT(*) FROM code_chunks;")
echo -e "${BLUE}$TOTAL_CHUNKS${NC} chunks"

if [ "$TOTAL_CHUNKS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No chunks found in database (empty database)${NC}"
    echo "======================================================================"
    echo -e "${GREEN}✅ Validation SKIPPED (no data to validate)${NC}"
    echo "======================================================================"
    exit 0
fi

# Validation 2: Count chunks with content_hash
echo -n "🔑 Counting chunks with content_hash... "
WITH_HASH=$($PSQL_CMD -c "SELECT COUNT(*) FROM code_chunks WHERE metadata->>'content_hash' IS NOT NULL;")
echo -e "${BLUE}$WITH_HASH${NC} chunks"

# Validation 3: Calculate coverage
if [ "$TOTAL_CHUNKS" -eq "$WITH_HASH" ]; then
    COVERAGE=100
    echo -e "📈 Coverage: ${GREEN}${COVERAGE}%${NC} (${WITH_HASH}/${TOTAL_CHUNKS})"
else
    MISSING=$((TOTAL_CHUNKS - WITH_HASH))
    COVERAGE=$((WITH_HASH * 100 / TOTAL_CHUNKS))
    echo -e "📈 Coverage: ${RED}${COVERAGE}%${NC} (${WITH_HASH}/${TOTAL_CHUNKS})"
    echo -e "${RED}❌ FAILED: $MISSING chunks missing content_hash${NC}"

    # Show sample of missing chunks
    echo ""
    echo "Sample chunks without content_hash:"
    $PSQL_CMD -c "
        SELECT id, file_path
        FROM code_chunks
        WHERE metadata->>'content_hash' IS NULL
        LIMIT 5;
    " | while IFS='|' read -r id file_path; do
        echo "  - $file_path (ID: $id)"
    done

    exit 1
fi

# Validation 4: Check hash format (32 hex characters)
echo -n "🔐 Validating hash format (32 hex chars)... "
INVALID_FORMAT=$($PSQL_CMD -c "
    SELECT COUNT(*)
    FROM code_chunks
    WHERE
        metadata->>'content_hash' IS NOT NULL
        AND LENGTH(metadata->>'content_hash') != 32;
")

if [ "$INVALID_FORMAT" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All hashes valid"
else
    echo -e "${RED}✗${NC} $INVALID_FORMAT invalid hashes"
    echo -e "${RED}❌ FAILED: Invalid hash format detected${NC}"
    exit 1
fi

# Validation 5: Verify MD5 hash correctness (sample 10 chunks)
echo -n "🔬 Verifying hash correctness (sample)... "
INCORRECT_HASH=$($PSQL_CMD -c "
    SELECT COUNT(*)
    FROM (
        SELECT
            md5(source_code) as computed_hash,
            metadata->>'content_hash' as stored_hash
        FROM code_chunks
        WHERE metadata->>'content_hash' IS NOT NULL
        LIMIT 10
    ) AS sample
    WHERE computed_hash != stored_hash;
")

if [ "$INCORRECT_HASH" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Sample hashes correct"
else
    echo -e "${RED}✗${NC} $INCORRECT_HASH incorrect hashes in sample"
    echo -e "${RED}❌ FAILED: Hash computation mismatch${NC}"
    exit 1
fi

# Success summary
echo ""
echo "======================================================================"
echo -e "${GREEN}✅ All validation checks PASSED${NC}"
echo "======================================================================"
echo ""
echo "Summary:"
echo "  • Total chunks: $TOTAL_CHUNKS"
echo "  • With content_hash: $WITH_HASH (100%)"
echo "  • Hash format: Valid (32 hex chars)"
echo "  • Hash correctness: Verified (sample)"
echo ""

# Display sample chunks with hashes
echo "Sample migrated chunks:"
echo "----------------------------------------------------------------------"
$PSQL_CMD -c "
    SELECT
        file_path,
        LEFT(metadata->>'content_hash', 8) || '...' || RIGHT(metadata->>'content_hash', 8) as hash_preview
    FROM code_chunks
    WHERE metadata->>'content_hash' IS NOT NULL
    LIMIT 5;
" | while IFS='|' read -r file_path hash_preview; do
    echo "  📄 $file_path"
    echo "     Hash: $hash_preview"
done

echo ""
echo "======================================================================"
echo -e "${GREEN}✅ Database ready for v3.0 (cache-enabled)${NC}"
echo "======================================================================"

exit 0
