#!/bin/bash
# MnemoLite Project Setup Script
# Version: 1.0.0
# Description: Setup MnemoLite auto-save hooks for new project

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
PROJECT_PATH="${1:-.}"
MNEMOLITE_PATH="/home/giak/Work/MnemoLite"

echo -e "${GREEN}🚀 MnemoLite Project Setup${NC}"
echo -e "${BLUE}Project: $PROJECT_PATH${NC}"
echo ""

# Validate project path
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${RED}❌ Project path does not exist: $PROJECT_PATH${NC}"
    exit 1
fi

# Resolve absolute path
PROJECT_PATH=$(cd "$PROJECT_PATH" && pwd)

# Check if already configured
if [ -f "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" ]; then
    echo -e "${YELLOW}⚠️  MnemoLite hooks already installed.${NC}"
    read -p "Overwrite? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Create .claude directory structure
echo "📁 Creating .claude directory structure..."
mkdir -p "$PROJECT_PATH/.claude/hooks/UserPromptSubmit"
mkdir -p "$PROJECT_PATH/.claude/hooks/Stop"

# Copy hooks
echo "📂 Copying hooks..."
cp "$MNEMOLITE_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" \
   "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/"
cp "$MNEMOLITE_PATH/.claude/hooks/Stop/auto-save.sh" \
   "$PROJECT_PATH/.claude/hooks/Stop/" 2>/dev/null || true
cp "$MNEMOLITE_PATH/.claude/hooks/Stop/save-direct.py" \
   "$PROJECT_PATH/.claude/hooks/Stop/"

# Make executable
echo "🔧 Setting permissions..."
chmod +x "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh"
chmod +x "$PROJECT_PATH/.claude/hooks/Stop/"*.sh 2>/dev/null || true

# Create/update settings.local.json
SETTINGS_FILE="$PROJECT_PATH/.claude/settings.local.json"

if [ -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}⚠️  settings.local.json exists - backing up...${NC}"
    BACKUP="$SETTINGS_FILE.backup.$(date +%s)"
    cp "$SETTINGS_FILE" "$BACKUP"
    echo "   Backup: $BACKUP"
fi

cat > "$SETTINGS_FILE" <<EOF
{
  "permissions": {
    "allow": [
      "Bash(docker compose:*)",
      "Bash(curl:*)",
      "Bash(jq:*)",
      "Bash(cat:*)",
      "Bash(tail:*)"
    ],
    "deny": [],
    "ask": []
  },
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": [
    "mnemolite"
  ],
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/UserPromptSubmit/auto-save-previous.sh",
            "timeout": 5
          }
        ]
      }
    ]
  },
  "disableAllHooks": false
}
EOF

echo "✅ settings.local.json configured"

# Create .mcp.json
cat > "$PROJECT_PATH/.mcp.json" <<EOF
{
  "mcpServers": {
    "mnemolite": {
      "command": "bash",
      "args": ["$MNEMOLITE_PATH/scripts/mcp_server.sh"],
      "env": {
        "DOCKER_COMPOSE_PROJECT": "mnemolite"
      }
    }
  }
}
EOF

echo "✅ .mcp.json created"

# Validation
echo ""
echo "🔍 Validating configuration..."

# Check JSON syntax
if command -v jq &> /dev/null; then
    if jq empty "$SETTINGS_FILE" 2>/dev/null; then
        echo "✅ settings.local.json: Valid JSON"
    else
        echo -e "${RED}❌ settings.local.json: Invalid JSON${NC}"
    fi

    if jq empty "$PROJECT_PATH/.mcp.json" 2>/dev/null; then
        echo "✅ .mcp.json: Valid JSON"
    else
        echo -e "${RED}❌ .mcp.json: Invalid JSON${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  jq not installed - skipping JSON validation${NC}"
fi

# Check MnemoLite running
echo ""
if docker compose -f "$MNEMOLITE_PATH/docker-compose.yml" ps 2>/dev/null | grep -q "Up"; then
    echo "✅ MnemoLite Docker services: Running"
else
    echo -e "${YELLOW}⚠️  MnemoLite Docker services not running${NC}"
    echo "   Start with: cd $MNEMOLITE_PATH && docker compose up -d"
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📋 Summary:"
echo "  - Hooks: ✅ Installed in .claude/hooks/"
echo "  - Settings: ✅ Configured in .claude/settings.local.json"
echo "  - MCP: ✅ Configured in .mcp.json"
echo ""
echo "🔄 Next steps:"
echo "  1. ${BLUE}Reload VSCode${NC}: Cmd+Shift+P → 'Developer: Reload Window'"
echo "  2. ${BLUE}Ask a question${NC} to trigger hook"
echo "  3. ${BLUE}Check logs${NC}: tail -f /tmp/hook-autosave-debug.log"
echo ""
echo "📊 Verify saved conversations:"
echo "   cd $MNEMOLITE_PATH && docker compose exec -T db psql -U mnemolite -d mnemolite -c \"SELECT COUNT(*) FROM memories WHERE author = 'AutoSave';\""
echo ""
echo "📚 Documentation:"
echo "   See ${PROJECT_PATH}/RAPPORT_SAUVEGARDE_CONVERSATIONS.md (if exists)"
