#!/bin/bash
# Script de vérification: Claude Code avec hooks actifs
# EPIC-24: Auto-save Conversations

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VÉRIFICATION: Claude Code Hooks Actifs${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test 1: Vérifier que le wrapper existe
echo -e "${YELLOW}[1/6]${NC} Vérifier wrapper script..."
if [ -x ~/Work/MnemoLite/scripts/claude-with-hooks.sh ]; then
  echo -e "      ${GREEN}✓${NC} Wrapper existe et est exécutable"
else
  echo -e "      ${RED}✗${NC} Wrapper manquant ou non exécutable"
  exit 1
fi

# Test 2: Vérifier alias zsh
echo -e "${YELLOW}[2/6]${NC} Vérifier alias dans .zshrc..."
if grep -q "claude-with-hooks.sh" ~/.zshrc; then
  echo -e "      ${GREEN}✓${NC} Alias configuré dans .zshrc"
else
  echo -e "      ${RED}✗${NC} Alias manquant dans .zshrc"
  exit 1
fi

# Test 3: Vérifier que Claude Code tourne
echo -e "${YELLOW}[3/6]${NC} Vérifier processus Claude Code..."
CLAUDE_PROCS=$(pgrep -c claude || echo "0")
if [ "$CLAUDE_PROCS" -gt 0 ]; then
  echo -e "      ${GREEN}✓${NC} Claude Code en cours d'exécution ($CLAUDE_PROCS processus)"
else
  echo -e "      ${YELLOW}⚠${NC} Aucun processus Claude Code trouvé (normal si pas lancé)"
fi

# Test 4: Vérifier si Claude Code utilise --debug hooks
echo -e "${YELLOW}[4/6]${NC} Vérifier flag --debug hooks..."
if ps aux | grep -q "claude.*--debug.*hooks"; then
  echo -e "      ${GREEN}✓${NC} Claude Code tourne avec --debug hooks"
  DEBUG_ACTIVE=true
else
  echo -e "      ${RED}✗${NC} Claude Code tourne SANS --debug hooks"
  DEBUG_ACTIVE=false
fi

# Test 5: Vérifier hook log
echo -e "${YELLOW}[5/6]${NC} Vérifier log du hook Stop..."
if [ -f /tmp/mnemo-hook-stop.log ] && [ -s /tmp/mnemo-hook-stop.log ]; then
  LAST_LOG=$(tail -1 /tmp/mnemo-hook-stop.log)
  echo -e "      ${GREEN}✓${NC} Log existe avec contenu"
  echo -e "      ${BLUE}→${NC} Dernière ligne: ${LAST_LOG:0:80}..."
else
  echo -e "      ${YELLOW}⚠${NC} Log vide ou inexistant (hook pas encore appelé)"
fi

# Test 6: Vérifier conversations dans DB
echo -e "${YELLOW}[6/6]${NC} Vérifier conversations dans DB..."
DB_RESULT=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "
SELECT COUNT(*), MAX(created_at)
FROM memories
WHERE memory_type = 'conversation' AND author = 'AutoSave' AND deleted_at IS NULL;
" 2>/dev/null | xargs)

CONV_COUNT=$(echo "$DB_RESULT" | cut -d'|' -f1 | xargs)
LAST_SAVE=$(echo "$DB_RESULT" | cut -d'|' -f2 | xargs)

echo -e "      ${BLUE}→${NC} Conversations auto-sauvées: $CONV_COUNT"
echo -e "      ${BLUE}→${NC} Dernière sauvegarde: $LAST_SAVE"

# Résumé
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RÉSUMÉ${NC}"
echo -e "${BLUE}========================================${NC}"

if [ "$DEBUG_ACTIVE" = true ]; then
  echo -e "${GREEN}✓ HOOKS ACTIFS${NC} - Les conversations seront sauvegardées automatiquement"
  echo ""
  echo "Pour tester:"
  echo "  1. Poser une question simple dans Claude Code"
  echo "  2. Attendre la réponse complète"
  echo "  3. Re-lancer ce script"
  echo "  4. Le count devrait augmenter ($CONV_COUNT → $((CONV_COUNT+1)))"
else
  echo -e "${RED}✗ HOOKS INACTIFS${NC} - Action requise:"
  echo ""
  echo "  1. Fermer Claude Code actuel (exit ou Ctrl+D)"
  echo "  2. Ouvrir un NOUVEAU terminal"
  echo "  3. Lancer: cd ~/Work/MnemoLite && claude"
  echo "  4. Vérifier: ps aux | grep 'claude.*--debug'"
  echo "     → Doit afficher: --debug hooks"
fi

echo ""
