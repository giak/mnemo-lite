#!/bin/bash
# Auto-detect Claude Code projects directory for current workspace
# Creates .env file with correct CLAUDE_PROJECTS_DIR

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Auto-detecting Claude Code projects directory..."
echo ""

# Get current workspace
WORKSPACE=$(pwd)
WORKSPACE_NAME=$(basename "$WORKSPACE")

echo "Current workspace: $WORKSPACE"
echo "Workspace name: $WORKSPACE_NAME"
echo ""

# Try to find Claude projects directory
CLAUDE_BASE="$HOME/.claude/projects"

if [ ! -d "$CLAUDE_BASE" ]; then
    echo -e "${RED}❌ Error: $CLAUDE_BASE not found${NC}"
    echo "   Claude Code has not created any projects yet."
    echo "   Please run Claude Code at least once in this workspace."
    exit 1
fi

echo "Searching in $CLAUDE_BASE..."
echo ""

# Find matching directory
# Claude Code creates directories like: -home-giak-Work-MnemoLite
WORKSPACE_SLUG=$(echo "$WORKSPACE" | sed 's/\//-/g')
PROJECT_DIR="$CLAUDE_BASE/$WORKSPACE_SLUG"

if [ -d "$PROJECT_DIR" ]; then
    echo -e "${GREEN}✓ Found: $PROJECT_DIR${NC}"
else
    # Try alternative matching (case-insensitive, partial match)
    MATCHES=$(find "$CLAUDE_BASE" -maxdepth 1 -type d -iname "*$WORKSPACE_NAME*" 2>/dev/null || true)

    if [ -z "$MATCHES" ]; then
        echo -e "${RED}❌ Error: No matching Claude projects directory found${NC}"
        echo ""
        echo "Available directories in $CLAUDE_BASE:"
        ls -1 "$CLAUDE_BASE" | grep -v "^agent-" | head -10 || echo "  (none)"
        echo ""
        echo "Please set manually:"
        echo "  export CLAUDE_PROJECTS_DIR=<path>"
        echo ""
        echo "Or create .env file:"
        echo "  CLAUDE_PROJECTS_DIR=<path>"
        exit 1
    fi

    # Use first match
    PROJECT_DIR=$(echo "$MATCHES" | head -1)
    echo -e "${YELLOW}⚠  Found similar: $PROJECT_DIR${NC}"
fi

# Count transcripts
TRANSCRIPT_COUNT=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.jsonl" ! -name "agent-*.jsonl" 2>/dev/null | wc -l)
echo ""
echo "Transcripts found: $TRANSCRIPT_COUNT"

# Create .env file
ENV_FILE="$WORKSPACE/.env"

if [ -f "$ENV_FILE" ]; then
    # Check if CLAUDE_PROJECTS_DIR already exists
    if grep -q "^CLAUDE_PROJECTS_DIR=" "$ENV_FILE"; then
        echo ""
        echo -e "${YELLOW}⚠  .env file already exists with CLAUDE_PROJECTS_DIR${NC}"
        echo "Current value:"
        grep "^CLAUDE_PROJECTS_DIR=" "$ENV_FILE"
        echo ""
        read -p "Overwrite? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 0
        fi
        # Remove old line
        sed -i "/^CLAUDE_PROJECTS_DIR=/d" "$ENV_FILE"
    fi
fi

# Append to .env
echo "CLAUDE_PROJECTS_DIR=$PROJECT_DIR" >> "$ENV_FILE"

echo ""
echo -e "${GREEN}✓ Created/updated $ENV_FILE${NC}"
echo ""
echo "Configuration:"
echo "  CLAUDE_PROJECTS_DIR=$PROJECT_DIR"
echo ""
echo "To start MnemoLite with auto-save:"
echo "  docker compose up"
echo ""
echo "To import historical conversations (first time):"
echo "  IMPORT_HISTORICAL=true docker compose up"
echo ""
