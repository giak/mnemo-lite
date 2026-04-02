# MnemoLite + Claude Code — Quickstart

**5 minutes setup** pour utiliser MnemoLite avec Claude Code.

---

## 1. Démarrer MnemoLite (30 secondes)

```bash
cd /home/giak/Work/MnemoLite
docker compose up -d

# Vérifier
docker compose ps
# Expected: api, db, redis all "Up (healthy)"

curl http://localhost:8001/health
# Expected: {"status":"healthy",...}
```

---

## 2. Configurer MCP (30 secondes)

**Dans votre projet**, créer `.mcp.json` :

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "bash",
      "args": ["/home/giak/Work/MnemoLite/scripts/mcp_server.sh"],
      "env": {
        "DOCKER_COMPOSE_PROJECT": "mnemolite"
      }
    }
  }
}
```

---

## 3. Installer Auto-Save (2 minutes)

```bash
# Copier hooks depuis MnemoLite master
cp -r /home/giak/Work/MnemoLite/.claude/hooks /path/to/your/project/.claude/

# OU créer manuellement
mkdir -p /path/to/your/project/.claude/hooks/{SessionStart,Stop,UserPromptSubmit}
```

**Configurer `settings.local.json`** :

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{"type": "command", "command": "bash .claude/hooks/SessionStart/check-autosave-setup.sh", "timeout": 5}]
    }],
    "Stop": [{
      "matcher": "*",
      "hooks": [{"type": "command", "command": "bash .claude/hooks/Stop/auto-save-exchange.sh", "timeout": 5}]
    }],
    "UserPromptSubmit": [{
      "matcher": "*",
      "hooks": [{"type": "command", "command": "bash .claude/hooks/UserPromptSubmit/auto-save-previous.sh", "timeout": 5}]
    }]
  }
}
```

---

## 4. Démarrer Claude Code (10 secondes)

```bash
cd /path/to/your/project
claude-code
```

**Vous devriez voir** :

```
═══════════════════════════════════════════════════════════
  ✅ AUTO-SAVE SYSTEM: ACTIVE & HEALTHY
═══════════════════════════════════════════════════════════
  MnemoLite:     Running
  Hook Stop:     Installed & Configured
  API Health:    OK
═══════════════════════════════════════════════════════════
```

---

## 5. Premier Test (30 secondes)

```
user> Test MCP ping
```

**Expected** : Claude utilise automatiquement l'outil `ping` de MnemoLite.

```
user> Indexe le projet /path/to/your/project avec repository="my-project"
```

**Expected** : Progression en temps réel → "Indexing complete: X files, Y chunks"

```
user> Cherche toutes les fonctions qui gèrent les erreurs
```

**Expected** : Claude utilise `search_code` et trouve les fonctions pertinentes.

---

## 6. Sauvegarde Mémoire (30 secondes)

```
user> Sauvegarde cette note : le projet utilise FastAPI + PostgreSQL + Redis. Tags: tech-stack, architecture
```

**Expected** : Mémoire sauvegardée avec embedding sémantique.

```
user> Rappelle-moi quelle est notre tech stack ?
```

**Expected** : Claude retrouve la mémoire via recherche sémantique.

---

## ✅ C'est Tout !

Vous avez maintenant :
- ✅ MnemoLite MCP actif
- ✅ Recherche sémantique de code
- ✅ Mémoire persistante
- ✅ Auto-save conversations

**Prochaines étapes** :

1. Lire [CLAUDE_CODE_INTEGRATION.md](CLAUDE_CODE_INTEGRATION.md) pour documentation complète
2. Explorer les 9 MCP tools disponibles
3. Utiliser multi-repository workflow
4. Créer des ADR (Architecture Decision Records)

---

## Troubleshooting Rapide

**MCP tools not available ?**
```bash
# Vérifier Docker up
cd /home/giak/Work/MnemoLite && docker compose ps

# Vérifier .mcp.json existe
cat /path/to/your/project/.mcp.json
```

**Auto-save alert au démarrage ?**
```bash
# Vérifier health endpoint
curl http://localhost:8001/api/v1/autosave/health

# Vérifier logs
tail -20 /tmp/hook-autosave-debug.log
```

---

**Version** : 1.0
**Date** : 2025-11-08
