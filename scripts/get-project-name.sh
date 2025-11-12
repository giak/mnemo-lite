#!/bin/bash
# Detect project name with fallback strategy
# Usage: bash scripts/get-project-name.sh [optional_working_directory]
# Output: project name in lowercase (e.g., "mnemolite")
# Exit codes: 0 = success (always succeeds via fallback)

set -euo pipefail

# Use provided directory or current directory
WORK_DIR="${1:-$(pwd)}"
cd "$WORK_DIR" 2>/dev/null || WORK_DIR="$(pwd)"

# Strategy A: Git root directory name (most reliable)
if command -v git >/dev/null 2>&1; then
  GIT_ROOT=$(git -C "$WORK_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
  if [ -n "$GIT_ROOT" ]; then
    basename "$GIT_ROOT" | tr '[:upper:]' '[:lower:]'
    exit 0
  fi
fi

# Strategy B: Current directory basename (fallback)
basename "$WORK_DIR" | tr '[:upper:]' '[:lower:]'
