#!/bin/bash
# Deploy centralized stub hooks to a project
# Usage: ./deploy-hooks-to-project.sh <project-path>
# Example: ./deploy-hooks-to-project.sh /home/giak/projects/truth-engine

set -euo pipefail

PROJECT_PATH="${1:-}"

if [ -z "$PROJECT_PATH" ]; then
  echo "Usage: $0 <project-path>"
  echo "Example: $0 /home/giak/projects/truth-engine"
  exit 1
fi

if [ ! -d "$PROJECT_PATH" ]; then
  echo "ERROR: Project directory does not exist: $PROJECT_PATH"
  exit 1
fi

PROJECT_NAME=$(basename "$PROJECT_PATH")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MNEMOLITE_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "Deploy Centralized Hooks"
echo "========================================="
echo "Project: $PROJECT_NAME"
echo "Path: $PROJECT_PATH"
echo "MnemoLite: $MNEMOLITE_ROOT"
echo ""

# 1. Backup existing hooks (if any)
if [ -d "$PROJECT_PATH/.claude/hooks" ]; then
  echo "[1/5] Backing up existing hooks..."
  BACKUP_DIR="$PROJECT_PATH/.claude/hooks.backup.$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  cp -r "$PROJECT_PATH/.claude/hooks/"* "$BACKUP_DIR/" 2>/dev/null || true
  echo "  ✓ Backup created: $BACKUP_DIR"
else
  echo "[1/5] No existing hooks to backup"
fi

# 2. Create hook directories
echo "[2/5] Creating hook directories..."
mkdir -p "$PROJECT_PATH/.claude/hooks/Stop"
mkdir -p "$PROJECT_PATH/.claude/hooks/UserPromptSubmit"
echo "  ✓ Directories created"

# 3. Copy stub hooks
echo "[3/5] Copying stub hooks..."
cp "$MNEMOLITE_ROOT/scripts/stub-hooks/Stop/auto-save.sh" \
   "$PROJECT_PATH/.claude/hooks/Stop/auto-save.sh"
cp "$MNEMOLITE_ROOT/scripts/stub-hooks/UserPromptSubmit/auto-save-previous.sh" \
   "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh"
echo "  ✓ Stubs copied"

# 3.5. Clean up obsolete files
echo "[3.5/5] Cleaning obsolete hooks..."
OBSOLETE_FILES=(
  "$PROJECT_PATH/.claude/hooks/Stop/auto-save-exchange.sh"
  "$PROJECT_PATH/.claude/hooks/Stop/save-direct.py"
  "$PROJECT_PATH/.claude/hooks/SessionStart/check-autosave-setup.sh"
)

CLEANED_COUNT=0
for file in "${OBSOLETE_FILES[@]}"; do
  if [ -f "$file" ]; then
    OBSOLETE_DIR="$PROJECT_PATH/.claude/hooks.obsolete"
    mkdir -p "$OBSOLETE_DIR"
    mv "$file" "$OBSOLETE_DIR/" 2>/dev/null && CLEANED_COUNT=$((CLEANED_COUNT + 1))
  fi
done

# Remove empty SessionStart directory
rmdir "$PROJECT_PATH/.claude/hooks/SessionStart" 2>/dev/null && CLEANED_COUNT=$((CLEANED_COUNT + 1)) || true

if [ $CLEANED_COUNT -gt 0 ]; then
  echo "  ✓ Removed $CLEANED_COUNT obsolete file(s) → hooks.obsolete/"
else
  echo "  ✓ No obsolete files found"
fi

# 4. Make executable
echo "[4/5] Setting permissions..."
chmod +x "$PROJECT_PATH/.claude/hooks/Stop/auto-save.sh"
chmod +x "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh"
echo "  ✓ Hooks are executable"

# 5. Verify
echo "[5/5] Verifying deployment..."
STOP_VERSION=$(head -3 "$PROJECT_PATH/.claude/hooks/Stop/auto-save.sh" | grep "Version:" || echo "NOT FOUND")
PROMPT_VERSION=$(head -3 "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" | grep "Version:" || echo "NOT FOUND")

if [[ "$STOP_VERSION" == *"Stub architecture"* ]] && [[ "$PROMPT_VERSION" == *"Stub architecture"* ]]; then
  echo "  ✓ Deployment verified"
else
  echo "  ✗ WARNING: Unexpected hook versions"
  echo "    Stop: $STOP_VERSION"
  echo "    Prompt: $PROMPT_VERSION"
fi

echo ""
echo "========================================="
echo "✓ Deployment Complete!"
echo "========================================="
echo ""
echo "Hook sizes:"
ls -lh "$PROJECT_PATH/.claude/hooks/Stop/auto-save.sh"
ls -lh "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh"
echo ""
echo "Next steps:"
echo "  1. Work in $PROJECT_NAME"
echo "  2. Have conversations with Claude Code"
echo "  3. Conversations will auto-save to MnemoLite with correct project_id"
echo ""
echo "Verify in database:"
echo "  docker compose exec -T db psql -U mnemo -d mnemolite -c \\"
echo "    \"SELECT title, p.display_name FROM memories m"
echo "     JOIN projects p ON m.project_id = p.id"
echo "     WHERE p.name = '$PROJECT_NAME'"
echo "     ORDER BY m.created_at DESC LIMIT 5;\""
