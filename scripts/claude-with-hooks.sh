#!/bin/bash
# Wrapper script pour Claude Code - Active les hooks automatiquement
# Workaround pour bug Claude Code #10401
#
# Bug: Claude Code v2.0.27+ ne déclenche AUCUN hook sans le flag --debug hooks
# Issue: https://github.com/anthropics/claude-code/issues/10401
# Status: OPEN (en attente de fix upstream)
#
# Installation:
#   1. chmod +x scripts/claude-with-hooks.sh
#   2. echo 'alias claude="$HOME/Work/MnemoLite/scripts/claude-with-hooks.sh"' >> ~/.bashrc
#   3. source ~/.bashrc
#
# Usage:
#   claude                  → Lance avec --debug hooks automatiquement
#   claude --resume        → Reprend session avec hooks activés
#   claude --debug hooks   → Passe directement (pas de double --debug)
#
# Auteur: Claude Code Assistant
# Date: 2025-10-29
# EPIC: EPIC-24 (Auto-save conversations)

set -euo pipefail

# Colors pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Trouver l'exécutable claude
CLAUDE_BIN=$(which claude 2>/dev/null || echo "")

if [ -z "$CLAUDE_BIN" ]; then
  echo -e "${RED}❌ Error: Claude Code not found in PATH${NC}" >&2
  echo "   Install with: npm install -g @anthropic-ai/claude-code" >&2
  exit 1
fi

# Si --debug déjà dans les arguments, passer directement
if [[ "$*" =~ --debug ]]; then
  exec "$CLAUDE_BIN" "$@"
fi

# Sinon, forcer --debug hooks pour activer les hooks
echo -e "${YELLOW}🔧 Workaround Bug #10401: Activating hooks with --debug${NC}" >&2
exec "$CLAUDE_BIN" --debug hooks "$@"
