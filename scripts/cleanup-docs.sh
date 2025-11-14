#!/bin/bash
# MnemoLite Documentation Cleanup Script
# Follows document-lifecycle skill principles
# Version: 1.0
# Date: 2025-11-13

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$PROJECT_ROOT/docs/88_ARCHIVE/backups/cleanup_${TIMESTAMP}"
LOG_FILE="$PROJECT_ROOT/cleanup_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_ROOT"

log "=========================================="
log "MnemoLite Documentation Cleanup"
log "=========================================="
log "Project root: $PROJECT_ROOT"
log "Backup dir: $BACKUP_DIR"
log "Log file: $LOG_FILE"
log ""

# Create backup directory
log "Creating backup directory..."
mkdir -p "$BACKUP_DIR"

# ==========================================
# PHASE 1: Critical Cleanup (api/code_test + obsolete files)
# ==========================================

log ""
log "=========================================="
log "PHASE 1: Critical Cleanup"
log "=========================================="

# 1.1 Backup and remove api/code_test/ (80MB)
if [ -d "api/code_test" ]; then
    log "Backing up api/code_test/ (80MB)..."
    tar -czf "$BACKUP_DIR/api_code_test.tar.gz" api/code_test/ 2>/dev/null || warn "Failed to backup api/code_test"

    log "Removing api/code_test/..."
    rm -rf api/code_test/
    info "✅ Freed ~80MB disk space"
else
    warn "api/code_test/ not found, skipping"
fi

# 1.2 Archive obsolete root markdown files
log ""
log "Archiving obsolete root markdown files..."
mkdir -p "docs/88_ARCHIVE/2025-10_obsolete_v2_docs"

if [ -f "SYNTHESE_MNEMOLITE_V2.md" ]; then
    cp "SYNTHESE_MNEMOLITE_V2.md" "$BACKUP_DIR/"
    mv "SYNTHESE_MNEMOLITE_V2.md" "docs/88_ARCHIVE/2025-10_obsolete_v2_docs/"
    info "✅ Archived SYNTHESE_MNEMOLITE_V2.md"
fi

if [ -f "GUIDE_DEMARRAGE.md" ]; then
    cp "GUIDE_DEMARRAGE.md" "$BACKUP_DIR/"
    mv "GUIDE_DEMARRAGE.md" "docs/88_ARCHIVE/2025-10_obsolete_v2_docs/"
    info "✅ Archived GUIDE_DEMARRAGE.md"
fi

if [ -f "NEXT_STEPS.md" ]; then
    cp "NEXT_STEPS.md" "$BACKUP_DIR/"
    # NEXT_STEPS is actually EPIC-27 completion report
    mv "NEXT_STEPS.md" "docs/agile/serena-evolution/03_EPICS/EPIC-27_PHASE1_COMPLETION_REPORT.md"
    info "✅ Moved NEXT_STEPS.md to EPIC-27 completion report"
fi

# 1.3 Rename README_SETUP.md to SETUP.md
if [ -f "README_SETUP.md" ]; then
    cp "README_SETUP.md" "$BACKUP_DIR/"
    mv "README_SETUP.md" "SETUP.md"
    info "✅ Renamed README_SETUP.md → SETUP.md"
fi

# ==========================================
# PHASE 2: Create Lifecycle Directory Structure
# ==========================================

log ""
log "=========================================="
log "PHASE 2: Create Lifecycle Structure"
log "=========================================="

mkdir -p docs/00_CONTROL
mkdir -p docs/01_DECISIONS
mkdir -p docs/02_RESEARCH
mkdir -p docs/88_ARCHIVE
mkdir -p docs/99_TEMP

info "✅ Created lifecycle directories: 00_CONTROL, 01_DECISIONS, 02_RESEARCH, 88_ARCHIVE, 99_TEMP"

# ==========================================
# PHASE 3: Move and Rename Files with Prefixes
# ==========================================

log ""
log "=========================================="
log "PHASE 3: Reorganize Documentation"
log "=========================================="

# 3.1 Move inventory to CONTROL
if [ -f "docs/test_inventory.md" ]; then
    cp "docs/test_inventory.md" "$BACKUP_DIR/"
    mv "docs/test_inventory.md" "docs/00_CONTROL/CONTROL_test_inventory.md"
    info "✅ Moved test_inventory.md → 00_CONTROL/CONTROL_test_inventory.md"
fi

# 3.2 Move specifications to DECISIONS
if [ -f "docs/Specification_API.md" ]; then
    cp "docs/Specification_API.md" "$BACKUP_DIR/"
    mv "docs/Specification_API.md" "docs/01_DECISIONS/DECISION_api_specification.md"
    info "✅ Moved Specification_API.md → 01_DECISIONS/DECISION_api_specification.md"
fi

if [ -f "docs/bdd_schema.md" ]; then
    cp "docs/bdd_schema.md" "$BACKUP_DIR/"
    mv "docs/bdd_schema.md" "docs/01_DECISIONS/DECISION_database_schema.md"
    info "✅ Moved bdd_schema.md → 01_DECISIONS/DECISION_database_schema.md"
fi

if [ -f "docs/architecture_diagrams.md" ]; then
    cp "docs/architecture_diagrams.md" "$BACKUP_DIR/"
    mv "docs/architecture_diagrams.md" "docs/01_DECISIONS/DECISION_architecture_diagrams.md"
    info "✅ Moved architecture_diagrams.md → 01_DECISIONS/DECISION_architecture_diagrams.md"
fi

if [ -f "docs/docker_setup.md" ]; then
    cp "docs/docker_setup.md" "$BACKUP_DIR/"
    mv "docs/docker_setup.md" "docs/01_DECISIONS/DECISION_docker_setup.md"
    info "✅ Moved docker_setup.md → 01_DECISIONS/DECISION_docker_setup.md"
fi

# 3.3 Archive Docker analysis files
log ""
log "Archiving Docker analysis files..."
mkdir -p "docs/88_ARCHIVE/2025-10_docker_analysis"

for file in docs/DOCKER_*.md; do
    if [ -f "$file" ]; then
        basename=$(basename "$file")
        cp "$file" "$BACKUP_DIR/"
        mv "$file" "docs/88_ARCHIVE/2025-10_docker_analysis/ARCHIVE_${basename}"
        info "✅ Archived $basename → 88_ARCHIVE/2025-10_docker_analysis/"
    fi
done

# 3.4 Archive SERENA and other deep analyses
for file in docs/SERENA_*.md docs/*_ULTRATHINK.md docs/*_AUDIT.md; do
    if [ -f "$file" ]; then
        basename=$(basename "$file")
        cp "$file" "$BACKUP_DIR/"

        # Determine archive directory based on content
        if [[ "$basename" == *"SERENA"* ]]; then
            mkdir -p "docs/88_ARCHIVE/2025-10_serena_analysis"
            mv "$file" "docs/88_ARCHIVE/2025-10_serena_analysis/ARCHIVE_${basename}"
        else
            mkdir -p "docs/88_ARCHIVE/2025-10_analysis"
            mv "$file" "docs/88_ARCHIVE/2025-10_analysis/ARCHIVE_${basename}"
        fi
        info "✅ Archived $basename"
    fi
done

# 3.5 Move temporary status files
if [ -f "docs/STATUS_2025-11-05.md" ]; then
    cp "docs/STATUS_2025-11-05.md" "$BACKUP_DIR/"
    mv "docs/STATUS_2025-11-05.md" "docs/99_TEMP/TEMP_2025-11-05_status.md"
    info "✅ Moved STATUS → 99_TEMP/TEMP_2025-11-05_status.md"
fi

# 3.6 Move UI design files to DECISIONS
for file in docs/ui_*.md; do
    if [ -f "$file" ]; then
        basename=$(basename "$file")
        name_part=$(echo "$basename" | sed 's/ui_//' | sed 's/.md//')
        cp "$file" "$BACKUP_DIR/"
        mv "$file" "docs/01_DECISIONS/DECISION_ui_${name_part}.md"
        info "✅ Moved $basename → 01_DECISIONS/DECISION_ui_${name_part}.md"
    fi
done

# 3.7 Move document architecture to DECISIONS
if [ -f "docs/Document Architecture.md" ]; then
    cp "docs/Document Architecture.md" "$BACKUP_DIR/"
    mv "docs/Document Architecture.md" "docs/01_DECISIONS/DECISION_document_architecture.md"
    info "✅ Moved Document Architecture.md → 01_DECISIONS/"
fi

# 3.8 Archive validation documents
for file in docs/*VALIDATION*.md docs/phase*.md; do
    if [ -f "$file" ]; then
        basename=$(basename "$file")
        cp "$file" "$BACKUP_DIR/"
        mkdir -p "docs/88_ARCHIVE/2025-10_validation"
        mv "$file" "docs/88_ARCHIVE/2025-10_validation/ARCHIVE_${basename}"
        info "✅ Archived $basename → 88_ARCHIVE/2025-10_validation/"
    fi
done

# 3.9 Archive Product/Project foundation docs
mkdir -p "docs/88_ARCHIVE/2025-10_foundation"

if [ -f "docs/Product Requirements Document.md" ]; then
    cp "docs/Product Requirements Document.md" "$BACKUP_DIR/"
    mv "docs/Product Requirements Document.md" "docs/88_ARCHIVE/2025-10_foundation/ARCHIVE_Product_Requirements_Document.md"
    info "✅ Archived Product Requirements Document"
fi

if [ -f "docs/Project Foundation Document.md" ]; then
    cp "docs/Project Foundation Document.md" "$BACKUP_DIR/"
    mv "docs/Project Foundation Document.md" "docs/88_ARCHIVE/2025-10_foundation/ARCHIVE_Project_Foundation_Document.md"
    info "✅ Archived Project Foundation Document"
fi

# ==========================================
# PHASE 4: Integrate Subdirectories
# ==========================================

log ""
log "=========================================="
log "PHASE 4: Integrate Subdirectories"
log "=========================================="

# 4.1 Integrate docs/agile/ into serena-evolution
if [ -d "docs/agile" ]; then
    for file in docs/agile/*.md; do
        if [ -f "$file" ]; then
            basename=$(basename "$file")
            cp "$file" "$BACKUP_DIR/"

            # Decide destination based on file type
            if [[ "$basename" == *"MIGRATION"* ]] || [[ "$basename" == *"ADR"* ]]; then
                mv "$file" "docs/agile/serena-evolution/01_ARCHITECTURE_DECISIONS/"
            elif [[ "$basename" == *"README"* ]]; then
                # Keep in agile/
                continue
            else
                mv "$file" "docs/agile/serena-evolution/02_RESEARCH/"
            fi
            info "✅ Integrated $basename into serena-evolution"
        fi
    done
fi

# 4.2 Integrate docs/architecture/
if [ -d "docs/architecture" ]; then
    for file in docs/architecture/*.md; do
        if [ -f "$file" ]; then
            basename=$(basename "$file")
            cp "$file" "$BACKUP_DIR/"
            mv "$file" "docs/01_DECISIONS/DECISION_${basename}"
            info "✅ Moved architecture/$basename → 01_DECISIONS/"
        fi
    done
    # Remove empty directory
    rmdir docs/architecture 2>/dev/null || warn "docs/architecture not empty or doesn't exist"
fi

# 4.3 Handle docs/debugging/
if [ -d "docs/debugging" ]; then
    # Keep debugging as-is, just ensure it's organized
    info "✅ Keeping docs/debugging/ as-is (recent debugging docs)"
fi

# 4.4 Archive AUTO-SAVE-QUICKSTART if obsolete
if [ -f "docs/AUTO-SAVE-QUICKSTART.md" ]; then
    cp "docs/AUTO-SAVE-QUICKSTART.md" "$BACKUP_DIR/"
    # Check if it's different from QUICKSTART.md
    if diff -q "docs/AUTO-SAVE-QUICKSTART.md" "QUICKSTART.md" >/dev/null 2>&1; then
        rm "docs/AUTO-SAVE-QUICKSTART.md"
        info "✅ Removed duplicate AUTO-SAVE-QUICKSTART.md"
    else
        mv "docs/AUTO-SAVE-QUICKSTART.md" "docs/88_ARCHIVE/2025-10_obsolete_v2_docs/"
        info "✅ Archived AUTO-SAVE-QUICKSTART.md"
    fi
fi

# 4.5 Archive MCP_INTEGRATION_GUIDE if superseded
if [ -f "docs/MCP_INTEGRATION_GUIDE.md" ]; then
    if [ -f "CLAUDE_CODE_INTEGRATION.md" ]; then
        cp "docs/MCP_INTEGRATION_GUIDE.md" "$BACKUP_DIR/"
        mv "docs/MCP_INTEGRATION_GUIDE.md" "docs/88_ARCHIVE/2025-10_obsolete_v2_docs/"
        info "✅ Archived MCP_INTEGRATION_GUIDE.md (superseded by CLAUDE_CODE_INTEGRATION.md)"
    fi
fi

# ==========================================
# PHASE 5: Create Archive READMEs
# ==========================================

log ""
log "=========================================="
log "PHASE 5: Create Archive READMEs"
log "=========================================="

# Create README for obsolete v2 docs archive
cat > "docs/88_ARCHIVE/2025-10_obsolete_v2_docs/README.md" <<'EOF'
# Archive: Obsolete v2.0.0 Documentation

**Archived**: 2025-11-13
**Status**: Superseded by v3.1.0 documentation

## Files

- `SYNTHESE_MNEMOLITE_V2.md` - v2.0.0 synthesis (outdated)
- `GUIDE_DEMARRAGE.md` - v2.0.0 startup guide (outdated)
- `AUTO-SAVE-QUICKSTART.md` - Superseded by root QUICKSTART.md
- `MCP_INTEGRATION_GUIDE.md` - Superseded by CLAUDE_CODE_INTEGRATION.md

## Why Archived

These documents were written for MnemoLite v2.0.0. The project is now at v3.1.0-dev with significant changes:
- New MCP tools (memory persistence)
- New architecture (hooks-based auto-save)
- PostgreSQL 18 migration complete
- Code Intelligence improvements

## Superseded By

- `README.md` (root) - Current v3.1.0-dev documentation
- `QUICKSTART.md` (root) - Current quick start guide
- `CLAUDE_CODE_INTEGRATION.md` (root) - Current MCP integration guide
EOF

info "✅ Created README for obsolete v2 docs archive"

# Create README for Docker analysis archive
cat > "docs/88_ARCHIVE/2025-10_docker_analysis/README.md" <<'EOF'
# Archive: Docker Analysis (October 2025)

**Archived**: 2025-11-13
**Status**: Historical analysis, superseded by current docker-compose.yml

## Files

- `DOCKER_OPTIMIZATIONS_SUMMARY.md` - Docker optimization analysis
- `DOCKER_ULTRATHINKING.md` - Deep Docker architecture thinking
- `DOCKER_VALIDATION_2025.md` - Docker validation report

## Key Findings

These analyses led to the current optimized docker-compose.yml:
- PostgreSQL 18 with optimized shared_buffers (1GB)
- Redis for L2 cache (7-alpine)
- Worker for async conversation processing
- OpenObserve for observability

## Current State

See `docker-compose.yml` and `SETUP.md` for current Docker setup.
EOF

info "✅ Created README for Docker analysis archive"

# ==========================================
# FINAL: Generate Statistics
# ==========================================

log ""
log "=========================================="
log "CLEANUP COMPLETE"
log "=========================================="

# Calculate statistics
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
DOCS_SIZE=$(du -sh docs/ | cut -f1)

log ""
log "Statistics:"
log "  - Backup created: $BACKUP_DIR ($BACKUP_SIZE)"
log "  - Current docs/ size: $DOCS_SIZE"
log "  - Freed space: ~80MB (api/code_test/)"
log "  - Lifecycle structure: ✅ Created"
log "  - Files reorganized: ✅ Complete"
log "  - Archives created: ✅ With READMEs"
log ""
log "Backup contents:"
ls -lh "$BACKUP_DIR/" | tee -a "$LOG_FILE"

log ""
log "✅ Cleanup complete! Backup preserved at:"
log "   $BACKUP_DIR"
log ""
log "📋 Full log saved to:"
log "   $LOG_FILE"
log ""
log "Next steps:"
log "  1. Review changes with: git status"
log "  2. Create CONTROL files (MISSION_CONTROL, DOCUMENT_INDEX)"
log "  3. Commit changes"

exit 0
