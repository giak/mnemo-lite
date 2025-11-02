# Scripts MnemoLite

## claude-with-hooks.sh

**Workaround pour Bug Claude Code #10401**

### Problème

Claude Code v2.0.27+ ne déclenche **AUCUN hook** (Stop, UserPromptSubmit, etc.) sans le flag `--debug hooks`.

**Impact**: Les conversations ne sont PAS sauvegardées automatiquement malgré la configuration correcte dans `.claude/settings.local.json`.

**Issue GitHub**: [#10401](https://github.com/anthropics/claude-code/issues/10401) - OPEN

### Solution

Ce wrapper script force automatiquement le flag `--debug hooks` à chaque lancement de Claude Code.

### Installation Rapide

```bash
# Option 1: Alias global (recommandé)
echo 'alias claude="$HOME/Work/MnemoLite/scripts/claude-with-hooks.sh"' >> ~/.bashrc
source ~/.bashrc

# Option 2: Copie dans ~/bin (si ~/bin est dans PATH)
cp scripts/claude-with-hooks.sh ~/bin/
chmod +x ~/bin/claude-with-hooks.sh
alias claude="$HOME/bin/claude-with-hooks.sh"

# Option 3: Lien symbolique
ln -s ~/Work/MnemoLite/scripts/claude-with-hooks.sh ~/bin/claude-hooks
alias claude='claude-hooks'
```

### Vérification

```bash
# 1. Tester l'alias
claude --version
# → Doit afficher: "🔧 Workaround Bug #10401: Activating hooks with --debug"

# 2. Vérifier que hooks s'exécutent
claude
# Poser une question, puis vérifier:
cat /tmp/mnemo-hook-stop.log
# → Doit contenir des entrées récentes

# 3. Vérifier conversations sauvegardées
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*), MAX(created_at)
FROM memories
WHERE memory_type = 'conversation' AND author = 'AutoSave';"
# → Count devrait augmenter après chaque conversation
```

### Usage

```bash
# Lancer nouvelle session (avec hooks activés)
claude

# Reprendre session précédente (avec hooks activés)
claude --resume

# Continue session spécifique (avec hooks activés)
claude --continue --session-id abc123

# Toutes les commandes Claude fonctionnent normalement
claude --help
```

### Désinstallation

Quand le bug sera corrigé en upstream:

```bash
# Supprimer l'alias
sed -i '/claude-with-hooks/d' ~/.bashrc
source ~/.bashrc

# Vérifier que claude original fonctionne avec hooks
ps aux | grep "claude.*--debug"
# → Si vide et hooks fonctionnent: bug corrigé, wrapper plus nécessaire
```

---

## mcp_server.sh

Script pour lancer le serveur MCP MnemoLite en standalone (pour debug).

**Usage**:
```bash
./scripts/mcp_server.sh
```

**Logs**: stdout/stderr

---

## periodic-conversation-scanner.py (À venir)

Background job pour parser périodiquement les transcripts Claude Code et sauvegarder les conversations manquées.

**Status**: Pas encore implémenté (Layer 3 de l'architecture multi-couches)

**Plan**:
- Parse `~/.claude/projects/` toutes les 5 minutes
- Détecte nouveaux échanges via hash deduplication
- Sauvegarde via `write_memory` MCP tool
- Coverage: +1.5% (rattrapage des hooks manqués)

---

## index_directory.py

Index entire TypeScript/JavaScript codebases into MnemoLite.

### Requirements

- Python 3.12+
- Docker (for running in container)
- tqdm: `pip install tqdm`

### Usage

**In Docker (recommended)**:
```bash
# Copy script to container
docker cp scripts/index_directory.py mnemo-api:/app/scripts/

# Run indexing
docker exec -i mnemo-api python3 /app/scripts/index_directory.py \
  /app/code_test \
  --repository code_test \
  --verbose
```

**On Host**:
```bash
# Ensure DATABASE_URL is set
export DATABASE_URL="postgresql+asyncpg://mnemo:mnemo@localhost:5432/mnemolite"

# Run indexing
python scripts/index_directory.py /path/to/code --repository myproject
```

### Options

- `directory` (required): Path to codebase
- `--repository` (optional): Repository name (default: directory name)
- `--verbose`: Enable detailed logging

### Pipeline

1. **Phase 1: Chunking** (~1 min)
   - Scans TypeScript/JavaScript files
   - Excludes tests, node_modules, declarations
   - AST parsing with tree-sitter

2. **Phase 2: Embeddings** (~3-5 min)
   - Generates CODE embeddings (768D)
   - Uses jinaai/jina-embeddings-v2-base-code
   - Stores in PostgreSQL

3. **Phase 3: Graph** (~10-20s)
   - Creates nodes (functions, classes)
   - Resolves call/import edges
   - EPIC-30: Filters anonymous functions

### Performance

- 100 files: ~2 minutes
- 500 files: ~8 minutes
- 1000 files: ~15 minutes

Bottleneck: Embedding generation (CPU-bound)

### Viewing Results

1. Open http://localhost:3002/
2. Select repository from dropdown
3. Explore graph visualization

---

**Dernière mise à jour**: 2025-11-02
**EPIC**: Directory Indexing (2025-11-02)
