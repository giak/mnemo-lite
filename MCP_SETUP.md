# MCP Setup — Truth Engine

**Status actuel**:
- ✅ `uvx` disponible (Python MCP)
- ✅ `@upstash/context7-mcp` installé (npm) - **ACTIF**
- ✅ `@modelcontextprotocol/server-web-search` - **ACTIF**
- ✅ MnemoLite MCP configuré - **PENDING RELOAD**
- ✅ Config MCP créée: `~/.config/Claude/mcp.json`

---

## 1. Vérifier MnemoLite MCP

```bash
# Check si MnemoLite server existe
uvx mcp-server-mnemolite --help

# Si pas installé, chercher package
pip search mnemolite 2>/dev/null || echo "À vérifier manuellement"

# Ou check GitHub/PyPI
# https://github.com/search?q=mnemolite+mcp
# https://pypi.org/search/?q=mnemolite
```

**Si MnemoLite est un projet local**:
```bash
# Chercher le repo
find ~/projects -name "*mnemolite*" -type d

# Vérifier si MCP server inclus
ls ~/projects/mnemolite*/mcp* 2>/dev/null
```

---

## 2. MCP Web Search (pour Truth Engine)

**Options recherche web**:

### A. Brave Search (recommandé - free 2K/mois)
```bash
npm install -g @modelcontextprotocol/server-brave-search
```

### B. DuckDuckGo (backup - unlimited free)
```bash
npm install -g mcp-server-duckduckgo
```

### C. Context7 (déjà installé - à tester)
```bash
# Déjà présent: @upstash/context7-mcp@1.0.17
# Vérifier capabilities
npx @upstash/context7-mcp --help
```

---

## 3. Config MCP Claude Desktop

Créer `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "uvx",
      "args": ["mcp-server-mnemolite", "--db-path", "/path/to/mnemolite.db"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "YOUR_KEY_HERE"
      }
    },
    "duckduckgo": {
      "command": "npx",
      "args": ["-y", "mcp-server-duckduckgo"]
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

---

## 4. Tests

### Test MnemoLite
```bash
# Index KB Truth Engine
uvx mcp-server-mnemolite index /home/giak/projects/truth-engine/kb/*.md

# Test query
uvx mcp-server-mnemolite search "EDI formula"
```

### Test Web Search
```bash
# Test Brave (si installé + API key)
npx @modelcontextprotocol/server-brave-search test "test query"

# Test DuckDuckGo
npx mcp-server-duckduckgo test "test query"

# Test Context7
npx @upstash/context7-mcp --version
```

---

## 5. Actions Immédiates

**Pour setup Truth Engine maintenant**:

1. **Localiser MnemoLite**:
   ```bash
   find ~/projects -name "*mnemolite*" -type d
   ```

2. **Installer web search** (choix minimal):
   ```bash
   npm install -g mcp-server-duckduckgo  # Free unlimited
   ```

3. **Créer config Claude Desktop**:
   ```bash
   mkdir -p ~/.config/Claude
   # Copier template ci-dessus dans ~/.config/Claude/claude_desktop_config.json
   ```

4. **Tester intégration**:
   ```bash
   # Dans Claude Desktop, vérifier MCP servers détectés
   # Ou via CLI si disponible:
   claude-code mcp list
   ```

---

## Debug

Si MCP server ne fonctionne pas:

```bash
# Vérifier commandes disponibles
which uvx
which npx
npm list -g

# Test direct server
uvx mcp-server-mnemolite --help
npx mcp-server-duckduckgo --help

# Check logs Claude Desktop
tail -f ~/.config/Claude/logs/*.log  # Si logs existent
```

---

**Next**: Une fois MCP configuré, test investigation Truth Engine avec recherches web illimitées.
