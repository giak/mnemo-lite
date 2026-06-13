# Automatisation Complète Setup MnemoLite — Ultra-Thinking

**Date**: 2025-11-08 10:05
**Contexte**: Automatiser l'installation MnemoLite dans nouveaux projets
**Méthodologie**: Brainstorming profond + analyse architecturale multi-niveaux

---

## 🎯 PROBLÈME À RÉSOUDRE

### Workflow Manuel Actuel (Truth Engine)

**Étapes nécessaires** (15-20 minutes) :
1. Copier `.claude/hooks/` depuis MnemoLite
2. Éditer `.claude/settings.local.json` → ajouter section `hooks`
3. Créer `.mcp.json` avec config MnemoLite
4. Ajouter permissions Docker dans `settings.local.json`
5. Ajuster paths dans scripts hooks (cd /home/giak/Work/MnemoLite)
6. Rendre scripts exécutables (chmod +x)
7. Recharger VSCode
8. Tester hook (poser question)
9. Vérifier logs debug

**Points de friction** :
- ❌ Répétitif pour chaque nouveau projet
- ❌ Risque d'oubli (permissions, chmod, etc.)
- ❌ Édition manuelle JSON (erreurs syntaxe)
- ❌ Ajustement paths projet-spécifiques
- ❌ Pas de validation automatique
- ❌ Documentation manuelle requise

**Coût cognitif** :
- Developer: 15-20 min × nombre de projets
- Erreurs potentielles: 30% (json, paths, permissions)
- Re-setup après corruption: 10 min

---

## 🧠 ULTRA-THINKING : NIVEAUX D'AUTOMATISATION

### Niveau 0 : Naïf (État Actuel)

**Approche**: Documentation README + copier-coller manuel

**Workflow**:
```bash
# Utilisateur fait manuellement
cp -r /path/to/template/.claude/hooks ~/.new-project/.claude/
# ... éditer JSON manuellement
```

**Avantages**:
- ✅ Simplicité (aucun outil)
- ✅ Contrôle total

**Inconvénients**:
- ❌ Répétitif
- ❌ Erreur-prone
- ❌ Pas scalable
- ❌ Friction cognitive

**Score**: 2/10

---

### Niveau 1 : Script Bash Basique

**Approche**: Script shell simple qui copie templates

**Implémentation**:
```bash
#!/bin/bash
# /home/giak/Work/MnemoLite/scripts/setup-new-project.sh

set -euo pipefail

PROJECT_PATH="${1:-.}"
MNEMOLITE_PATH="/home/giak/Work/MnemoLite"

echo "🚀 Setting up MnemoLite for project: $PROJECT_PATH"

# 1. Copy hooks
echo "📂 Copying hooks..."
mkdir -p "$PROJECT_PATH/.claude/hooks"
cp -r "$MNEMOLITE_PATH/.claude/hooks"/* "$PROJECT_PATH/.claude/hooks/"
chmod +x "$PROJECT_PATH/.claude/hooks"/**/*.sh

# 2. Create/update settings.local.json
echo "⚙️  Configuring settings.local.json..."
cat > "$PROJECT_PATH/.claude/settings.local.json" <<EOF
{
  "permissions": {
    "allow": [
      "Bash(docker compose:*)",
      "Bash(curl:*)",
      "Bash(jq:*)"
    ],
    "deny": [],
    "ask": []
  },
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["mnemolite"],
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash .claude/hooks/UserPromptSubmit/auto-save-previous.sh",
        "timeout": 5
      }]
    }]
  },
  "disableAllHooks": false
}
EOF

# 3. Create .mcp.json
echo "🔧 Creating .mcp.json..."
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

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Reload VSCode (Cmd+Shift+P → 'Developer: Reload Window')"
echo "2. Ask a question to trigger hook"
echo "3. Check logs: tail -f /tmp/hook-autosave-debug.log"
```

**Usage**:
```bash
# Dans nouveau projet
cd /path/to/new-project
bash /home/giak/Work/MnemoLite/scripts/setup-new-project.sh .

# Ou avec alias
alias mnemolite-setup='/home/giak/Work/MnemoLite/scripts/setup-new-project.sh'
mnemolite-setup .
```

**Avantages**:
- ✅ Automatise 90% du workflow
- ✅ Pas de dépendances (bash natif)
- ✅ Idempotent (peut relancer sans casser)
- ✅ Fast (< 1 seconde)

**Inconvénients**:
- ❌ Pas de validation config existante (écrase)
- ❌ Hardcoded paths
- ❌ Pas de rollback
- ❌ Utilisateur doit connaître le script

**Score**: 6/10

---

### Niveau 2 : Template Generator avec Validation

**Approche**: Script intelligent qui merge config existante

**Implémentation**:
```bash
#!/bin/bash
# /home/giak/Work/MnemoLite/scripts/mnemolite-init.sh

set -euo pipefail

PROJECT_PATH="${1:-.}"
MNEMOLITE_PATH="/home/giak/Work/MnemoLite"

echo "🔍 Analyzing project: $PROJECT_PATH"

# Validation: Check if already configured
if [ -f "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" ]; then
    echo "⚠️  MnemoLite hooks already installed."
    read -p "Overwrite? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Check if settings.local.json exists
SETTINGS_FILE="$PROJECT_PATH/.claude/settings.local.json"
BACKUP_FILE="$PROJECT_PATH/.claude/settings.local.json.backup.$(date +%s)"

if [ -f "$SETTINGS_FILE" ]; then
    echo "📦 Backing up existing settings to: $BACKUP_FILE"
    cp "$SETTINGS_FILE" "$BACKUP_FILE"

    # Merge with existing (using jq)
    echo "🔀 Merging with existing configuration..."

    # Extract existing permissions
    EXISTING_ALLOW=$(jq -r '.permissions.allow // []' "$SETTINGS_FILE")

    # Create merged config
    jq -s '.[0] * .[1]' "$SETTINGS_FILE" <(cat <<EOF
{
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["mnemolite"],
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash .claude/hooks/UserPromptSubmit/auto-save-previous.sh",
        "timeout": 5
      }]
    }]
  },
  "disableAllHooks": false
}
EOF
) > "$SETTINGS_FILE.tmp"

    mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
else
    # Create from scratch (same as Level 1)
    echo "📝 Creating new settings.local.json..."
    # ... (same as Level 1)
fi

# Copy hooks with validation
echo "📂 Installing hooks..."
mkdir -p "$PROJECT_PATH/.claude/hooks/UserPromptSubmit"
mkdir -p "$PROJECT_PATH/.claude/hooks/Stop"

cp "$MNEMOLITE_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" \
   "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/"
cp "$MNEMOLITE_PATH/.claude/hooks/Stop/"*.{sh,py} \
   "$PROJECT_PATH/.claude/hooks/Stop/"

# Make executable
chmod +x "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh"
chmod +x "$PROJECT_PATH/.claude/hooks/Stop/"*.sh

# Validation: Check syntax
echo "✓ Validating configuration..."
if ! jq empty "$SETTINGS_FILE" 2>/dev/null; then
    echo "❌ Invalid JSON in settings.local.json!"
    echo "Restoring backup..."
    mv "$BACKUP_FILE" "$SETTINGS_FILE"
    exit 1
fi

# Test: Check hook is executable
if ! bash "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" <<< '{"transcript_path":"/dev/null","session_id":"test"}' &>/dev/null; then
    echo "⚠️  Hook test failed (expected for missing transcript)"
fi

echo ""
echo "✅ MnemoLite setup complete!"
echo ""
echo "📋 Summary:"
echo "  - Hooks: ✅ Installed"
echo "  - Settings: ✅ Configured"
echo "  - Backup: $BACKUP_FILE"
echo ""
echo "🔄 Next: Reload VSCode"
```

**Avantages**:
- ✅ Merge config existante (safe)
- ✅ Backup automatique
- ✅ Validation JSON
- ✅ Test basic du hook
- ✅ Rollback possible

**Inconvénients**:
- ❌ Dépendance jq
- ❌ Complexité accrue
- ❌ Toujours utilisateur-initié

**Score**: 7.5/10

---

### Niveau 3 : Global Hooks (Shared)

**Approche**: Installer hooks au niveau global (~/.claude/hooks), tous projets en bénéficient

**Architecture**:
```
~/.claude/
├── global-hooks/
│   ├── UserPromptSubmit/
│   │   └── mnemolite-auto-save.sh    # Global hook
│   └── Stop/
│       └── save-direct.py
└── hooks-config.json                  # Whitelist projects
```

**Implémentation**:

`.claude-code` config globale:
```json
{
  "globalHooks": {
    "UserPromptSubmit": [
      {
        "matcher": "*",  // Tous projets
        "hooks": [{
          "type": "command",
          "command": "bash ~/.claude/global-hooks/UserPromptSubmit/mnemolite-auto-save.sh",
          "timeout": 5
        }]
      }
    ]
  }
}
```

Script global adaptatif:
```bash
#!/bin/bash
# ~/.claude/global-hooks/UserPromptSubmit/mnemolite-auto-save.sh

HOOK_DATA=$(cat)
PROJECT_PATH=$(echo "$HOOK_DATA" | jq -r '.project_path // ""')

# Check if project wants MnemoLite
if [ -f "$PROJECT_PATH/.mnemolite-enabled" ]; then
    # Run standard hook logic
    # ... (same as Level 1/2)
else
    # Skip silently
    echo '{"continue": true}'
    exit 0
fi
```

**Opt-in per projet**:
```bash
# Dans nouveau projet
touch .mnemolite-enabled

# Ou avec metadata
echo '{"repository": "my-project", "tags": ["python", "research"]}' > .mnemolite-enabled
```

**Avantages**:
- ✅ Setup ultra-minimal par projet (1 fichier)
- ✅ Maintenance centralisée (update 1× → all projects)
- ✅ Pas de copie hooks (DRY)
- ✅ Consistent behavior

**Inconvénients**:
- ❌ Requiert support "globalHooks" dans Claude Code (pas encore implémenté?)
- ❌ Moins de flexibilité par projet
- ❌ Debugging plus complexe (où est le hook?)
- ❌ Race condition si plusieurs projets ouverts simultanément

**Score**: 8/10 (si Claude Code supporte globalHooks)

---

### Niveau 4 : MCP Tool `setup_project`

**Approche**: Créer un outil MCP qui setup projet depuis l'intérieur

**Implémentation MnemoLite**:

`api/mnemo_mcp/tools/setup_tools.py`:
```python
from mcp.server.fastmcp import Context
from pathlib import Path
import json
import shutil

async def setup_project_tool(
    ctx: Context,
    project_path: str,
    features: list[str] = ["hooks", "mcp-config", "permissions"]
) -> dict:
    """
    Setup MnemoLite for a new project.

    Automatically installs:
    - Auto-save hooks (UserPromptSubmit)
    - .mcp.json configuration
    - settings.local.json permissions

    Args:
        project_path: Absolute path to project root
        features: List of features to install (default: all)

    Returns:
        SetupResult with installed_files, backup_created, next_steps
    """
    project = Path(project_path)
    mnemolite = Path("/home/giak/Work/MnemoLite")

    result = {
        "installed_files": [],
        "backup_created": [],
        "errors": []
    }

    # 1. Install hooks
    if "hooks" in features:
        hooks_src = mnemolite / ".claude/hooks"
        hooks_dst = project / ".claude/hooks"

        if hooks_dst.exists():
            backup = project / f".claude/hooks.backup.{int(time.time())}"
            shutil.move(hooks_dst, backup)
            result["backup_created"].append(str(backup))

        shutil.copytree(hooks_src, hooks_dst)
        result["installed_files"].append(".claude/hooks/")

        # Make executable
        for script in hooks_dst.rglob("*.sh"):
            script.chmod(0o755)

    # 2. Create .mcp.json
    if "mcp-config" in features:
        mcp_config = {
            "mcpServers": {
                "mnemolite": {
                    "command": "bash",
                    "args": [str(mnemolite / "scripts/mcp_server.sh")],
                    "env": {"DOCKER_COMPOSE_PROJECT": "mnemolite"}
                }
            }
        }

        mcp_file = project / ".mcp.json"
        mcp_file.write_text(json.dumps(mcp_config, indent=2))
        result["installed_files"].append(".mcp.json")

    # 3. Update settings.local.json
    if "permissions" in features:
        settings_file = project / ".claude/settings.local.json"

        if settings_file.exists():
            # Merge
            existing = json.loads(settings_file.read_text())
        else:
            existing = {}

        existing.update({
            "enableAllProjectMcpServers": True,
            "enabledMcpjsonServers": ["mnemolite"],
            "hooks": {
                "UserPromptSubmit": [{
                    "matcher": "*",
                    "hooks": [{
                        "type": "command",
                        "command": "bash .claude/hooks/UserPromptSubmit/auto-save-previous.sh",
                        "timeout": 5
                    }]
                }]
            },
            "disableAllHooks": False
        })

        settings_file.write_text(json.dumps(existing, indent=2))
        result["installed_files"].append(".claude/settings.local.json")

    return {
        "success": True,
        "project_path": str(project),
        "installed_files": result["installed_files"],
        "backup_created": result["backup_created"],
        "next_steps": [
            "Reload VSCode (Cmd+Shift+P → 'Developer: Reload Window')",
            "Ask a question to trigger hook",
            "Check logs: tail -f /tmp/hook-autosave-debug.log"
        ]
    }
```

**Registration**:
```python
@mcp.tool()
async def setup_project(
    ctx: Context,
    project_path: str,
    features: list[str] = ["hooks", "mcp-config", "permissions"]
) -> dict:
    """Setup MnemoLite for a new project."""
    return await setup_project_tool(ctx, project_path, features)
```

**Usage** (depuis n'importe quel projet avec MCP):
```
Claude, setup MnemoLite for current project:
Use MCP tool: setup_project(project_path="/home/giak/projects/new-project")
```

**Avantages**:
- ✅ **Workflow in-conversation** - pas de terminal
- ✅ Disponible partout (MCP global)
- ✅ Validation, backup, rollback intégrés
- ✅ Logging automatique
- ✅ Peut demander confirmation (elicitation)
- ✅ Extensible (features opt-in)

**Inconvénients**:
- ❌ Requiert MCP déjà configuré (chicken-egg)
- ❌ Développement dans MnemoLite requis
- ❌ Tests unitaires nécessaires

**Score**: 9/10

---

### Niveau 5 : Auto-Detection avec SessionStart Hook

**Approche**: Hook SessionStart détecte projet non-configuré et propose setup

**Architecture**:

Hook global `SessionStart`:
```bash
#!/bin/bash
# ~/.claude/global-hooks/SessionStart/mnemolite-auto-detect.sh

HOOK_DATA=$(cat)
PROJECT_PATH=$(echo "$HOOK_DATA" | jq -r '.project_path // ""')

# Check if MnemoLite hooks installed
if [ ! -f "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh" ]; then
    # Not configured - offer setup
    cat <<EOF
{
  "continue": true,
  "message": "🔍 MnemoLite auto-save not configured for this project.\\n\\nWould you like to enable it? Say 'yes' to auto-configure."
}
EOF
    exit 0
fi

# Already configured - silent
echo '{"continue": true}'
exit 0
```

**Flow conversationnel**:
```
Claude: "🔍 MnemoLite auto-save not configured for this project.
Would you like to enable it?"

User: "yes"

Claude: [Uses MCP setup_project tool]
"✅ MnemoLite configured! Reloading window..."
```

**Implémentation complète**:

1. **SessionStart hook** détecte absence config
2. **Offre setup** via message
3. **User accepte** → Claude appelle `setup_project` MCP tool
4. **Auto-reload** VSCode (si possible)
5. **Confirmation** setup réussi

**Avantages**:
- ✅ **Zero friction** - utilisateur fait rien
- ✅ Proactive discovery
- ✅ Opt-in conversationnel (pas forcé)
- ✅ Learn-by-doing (user voit le process)

**Inconvénients**:
- ❌ Requiert SessionStart hook support
- ❌ Peut être intrusif si non désiré
- ❌ Complexity accrue

**Score**: 9.5/10 (si SessionStart existe)

---

### Niveau 6 : Package Manager Style (Ultimate)

**Approche**: CLI dédié façon npm/poetry pour gérer MnemoLite projects

**Implementation**:
```bash
#!/usr/bin/env python3
# /home/giak/.local/bin/mnemo

import click
import json
from pathlib import Path

@click.group()
def cli():
    """MnemoLite Project Manager"""
    pass

@cli.command()
@click.argument('project_path', type=click.Path(), default='.')
@click.option('--features', '-f', multiple=True,
              default=['hooks', 'mcp-config', 'permissions'],
              help='Features to install')
def init(project_path, features):
    """Initialize MnemoLite for a project"""
    project = Path(project_path).resolve()
    click.echo(f"🚀 Initializing MnemoLite for {project.name}")

    # Run setup logic (same as Level 4)
    # ...

    click.echo("✅ Done!")
    click.echo("\nNext: mnemo status")

@cli.command()
@click.argument('project_path', type=click.Path(), default='.')
def status(project_path):
    """Check MnemoLite status for project"""
    project = Path(project_path).resolve()

    checks = {
        "Hooks installed": (project / ".claude/hooks/UserPromptSubmit/auto-save-previous.sh").exists(),
        "MCP configured": (project / ".mcp.json").exists(),
        "Settings configured": (project / ".claude/settings.local.json").exists(),
    }

    for check, status in checks.items():
        icon = "✅" if status else "❌"
        click.echo(f"{icon} {check}")

@cli.command()
@click.argument('project_path', type=click.Path(), default='.')
def validate(project_path):
    """Validate MnemoLite configuration"""
    project = Path(project_path).resolve()

    # Check JSON syntax
    settings = project / ".claude/settings.local.json"
    if settings.exists():
        try:
            json.loads(settings.read_text())
            click.echo("✅ settings.local.json valid")
        except json.JSONDecodeError as e:
            click.echo(f"❌ Invalid JSON: {e}")

    # Check hook executable
    hook = project / ".claude/hooks/UserPromptSubmit/auto-save-previous.sh"
    if hook.exists() and hook.stat().st_mode & 0o111:
        click.echo("✅ Hook executable")
    else:
        click.echo("❌ Hook not executable")

@cli.command()
@click.argument('project_path', type=click.Path(), default='.')
def test(project_path):
    """Test hook execution"""
    project = Path(project_path).resolve()
    hook = project / ".claude/hooks/UserPromptSubmit/auto-save-previous.sh"

    # Run with test data
    test_data = {
        "transcript_path": "/dev/null",
        "session_id": "test"
    }

    # Execute hook
    # ...

@cli.command()
@click.argument('project_path', type=click.Path(), default='.')
def remove(project_path):
    """Remove MnemoLite from project"""
    if not click.confirm("Remove MnemoLite configuration?"):
        return

    # Backup first
    # Remove hooks, configs
    # ...

if __name__ == '__main__':
    cli()
```

**Usage**:
```bash
# Initialize new project
cd /path/to/new-project
mnemo init

# Check status
mnemo status

# Validate config
mnemo validate

# Test hook
mnemo test

# Remove
mnemo remove
```

**Features avancées**:
```bash
# List all MnemoLite projects
mnemo list

# Update hooks to latest version
mnemo update

# Migrate old config to new format
mnemo migrate

# Generate project report
mnemo report --format markdown > MNEMOLITE.md
```

**Avantages**:
- ✅ **Professional UX** (like npm, poetry)
- ✅ Toutes features: init, status, validate, test, remove
- ✅ Extensible (plugins)
- ✅ Documentation intégrée (--help)
- ✅ Shell completion
- ✅ CI/CD integration possible

**Inconvénients**:
- ❌ Développement conséquent
- ❌ Maintenance long-term
- ❌ Dépendances Python (click, etc.)

**Score**: 10/10 (mais effort++)

---

## 📊 COMPARAISON GLOBALE

| Level | Approche | Effort Dev | Friction User | Maintainabilité | Score |
|-------|----------|------------|---------------|-----------------|-------|
| 0 | Manuel | 0h | 20min/projet | 3/10 | 2/10 |
| 1 | Script bash | 1h | 1min + terminal | 5/10 | 6/10 |
| 2 | Template + Validation | 3h | 1min + terminal | 7/10 | 7.5/10 |
| 3 | Global Hooks | 4h | 10sec (touch file) | 8/10 | 8/10 |
| 4 | MCP Tool | 6h | Conversational | 9/10 | 9/10 |
| 5 | Auto-Detection | 8h | Zero (proactive) | 9/10 | 9.5/10 |
| 6 | CLI Manager | 16h | 10sec (mnemo init) | 10/10 | 10/10 |

---

## 🎯 RECOMMANDATION PAR CONTEXTE

### Court Terme (1-2 projets) → **Level 1-2**

**Implémentation**:
```bash
# Créer script simple
cat > /home/giak/Work/MnemoLite/scripts/setup-new-project.sh <<'EOF'
#!/bin/bash
# (Level 1 script from above)
EOF

chmod +x /home/giak/Work/MnemoLite/scripts/setup-new-project.sh

# Alias global
echo 'alias mnemo-setup="/home/giak/Work/MnemoLite/scripts/setup-new-project.sh"' >> ~/.bashrc
```

**Usage**:
```bash
cd /path/to/new-project
mnemo-setup .
```

**ROI**: Excellent (1h dev → sauve 15min/projet)

---

### Moyen Terme (3-10 projets) → **Level 4**

**Implémentation**: MCP Tool `setup_project`

**Workflow**:
```
User: "Claude, enable MnemoLite for this project"
Claude: [Uses setup_project MCP tool]
        "✅ Done! Reload VSCode."
```

**ROI**: Très bon (6h dev → workflow conversationnel)

---

### Long Terme (10+ projets / équipe) → **Level 6**

**Implémentation**: CLI Manager complet

**Features critiques**:
- `mnemo init` - Setup projet
- `mnemo status` - Vérifier config
- `mnemo update` - Update hooks version
- `mnemo list` - Liste projets MnemoLite

**ROI**: Excellent si équipe (16h dev → économie temps × N developers)

---

## 🚀 ROADMAP PROGRESSIF

### Phase 1: Quick Win (Aujourd'hui, 1h)

**Action**: Créer script Level 1

```bash
cd /home/giak/Work/MnemoLite
mkdir -p scripts
cat > scripts/setup-new-project.sh <<'SCRIPT'
#!/bin/bash
# (Copy Level 1 implementation)
SCRIPT

chmod +x scripts/setup-new-project.sh

# Test sur projet dummy
mkdir -p /tmp/test-project
bash scripts/setup-new-project.sh /tmp/test-project
```

**Validation**:
```bash
# Check files created
ls -la /tmp/test-project/.claude/
cat /tmp/test-project/.claude/settings.local.json
```

---

### Phase 2: Validation (Semaine prochaine, 2h)

**Action**: Ajouter Level 2 features (backup, merge, validate)

**Améliorer**:
- Merge existing settings.local.json (pas écraser)
- Backup automatique
- Validation JSON syntax
- Test hook execution

---

### Phase 3: MCP Tool (Dans 2 semaines, 6h)

**Action**: Implémenter `setup_project` MCP tool

**Files**:
- `api/mnemo_mcp/tools/setup_tools.py`
- `tests/test_setup_tool.py`
- Documentation

**Test**:
```python
# Test unitaire
result = await setup_project_tool(
    ctx=mock_ctx,
    project_path="/tmp/test",
    features=["hooks", "mcp-config"]
)
assert result["success"] == True
assert len(result["installed_files"]) == 2
```

---

### Phase 4: Auto-Detection (Dans 1 mois, 8h)

**Action**: SessionStart hook avec detection

**Requires**:
- Claude Code support SessionStart hook
- UI pour confirmation user
- Integration avec MCP tool

---

### Phase 5: CLI Manager (Si équipe / long-term, 16h)

**Action**: CLI Python complet

**Stack**:
- Click (CLI framework)
- Rich (pretty output)
- Pytest (tests)

**Distribution**:
```bash
pip install mnemolite-cli
mnemo init .
```

---

## 💡 INSIGHTS ARCHITECTURAUX

### 1. Progression vs Big Bang

**Insight**: Commencer simple (Level 1), itérer selon besoins

**Raison**:
- Level 1 = 80% valeur, 20% effort
- Level 6 = 100% valeur, 100% effort
- Diminishing returns après Level 4

**Recommandation**: Ship Level 1 aujourd'hui, décider Phase 2 après usage

---

### 2. Conversational > Terminal

**Insight**: MCP Tool (Level 4) meilleur UX que script bash

**Raison**:
- User déjà dans conversation
- Pas de context switch (terminal)
- Confirmation naturelle
- Logs visibles immédiatement

**Trade-off**: Requiert MCP configuré (chicken-egg pour 1er projet)

---

### 3. Global vs Local

**Insight**: Hybrid approach optimal

**Architecture**:
```
Global:
  - Hooks code (DRY, centralized updates)
  - MCP tool (available everywhere)

Local:
  - .mnemolite-enabled (opt-in flag)
  - settings.local.json (project-specific permissions)
```

**Avantages**:
- Maintenance centralisée
- Flexibility per-project
- Pas de duplication code

---

### 4. Templates vs Generation

**Insight**: Generation > Templates pour configs dynamiques

**Exemple**:

**Template approach** (fragile):
```bash
cp template/settings.local.json $PROJECT/
# Problème: écrase existing, paths hardcoded
```

**Generation approach** (robust):
```python
def generate_settings(project_path, existing=None):
    config = existing or {}
    config.update({
        "enabledMcpjsonServers": ["mnemolite"],
        "hooks": generate_hooks_config(project_path)
    })
    return config
```

**Avantage**: Merge, validation, adaptation dynamique

---

### 5. Validation Layers

**Insight**: Multi-layer validation critique

**Layers**:
1. **Syntax** - JSON valid?
2. **Semantic** - Required fields present?
3. **Runtime** - Hook executable? MCP reachable?
4. **Integration** - End-to-end test (pose question → verify saved)

**Implementation**:
```bash
mnemo validate
# ✅ Syntax: JSON valid
# ✅ Semantic: All required fields present
# ⚠️  Runtime: MnemoLite Docker not running
# ⏭️  Integration: Skipped (fix runtime first)
```

---

## 🔧 IMPLEMENTATION IMMEDIATE (Level 1)

### Script Final Recommandé

```bash
#!/bin/bash
# /home/giak/Work/MnemoLite/scripts/setup-new-project.sh
# Version: 1.0.0
# Description: Setup MnemoLite auto-save for new project

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
PROJECT_PATH="${1:-.}"
MNEMOLITE_PATH="/home/giak/Work/MnemoLite"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}🚀 MnemoLite Project Setup${NC}"
echo "Project: $PROJECT_PATH"
echo ""

# Validate project path
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${RED}❌ Project path does not exist: $PROJECT_PATH${NC}"
    exit 1
fi

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
   "$PROJECT_PATH/.claude/hooks/Stop/"
cp "$MNEMOLITE_PATH/.claude/hooks/Stop/save-direct.py" \
   "$PROJECT_PATH/.claude/hooks/Stop/"

# Make executable
echo "🔧 Setting permissions..."
chmod +x "$PROJECT_PATH/.claude/hooks/UserPromptSubmit/auto-save-previous.sh"
chmod +x "$PROJECT_PATH/.claude/hooks/Stop/auto-save.sh"

# Create/update settings.local.json
SETTINGS_FILE="$PROJECT_PATH/.claude/settings.local.json"

if [ -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}⚠️  settings.local.json exists - backing up...${NC}"
    BACKUP="$SETTINGS_FILE.backup.$(date +%s)"
    cp "$SETTINGS_FILE" "$BACKUP"
    echo "Backup: $BACKUP"

    # TODO: Merge with jq (optional)
    echo -e "${YELLOW}Note: Manual merge may be needed${NC}"
fi

cat > "$SETTINGS_FILE" <<EOF
{
  "permissions": {
    "allow": [
      "Bash(docker compose:*)",
      "Bash(curl:*)",
      "Bash(jq:*)"
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
if ! docker compose -f "$MNEMOLITE_PATH/docker-compose.yml" ps | grep -q "Up"; then
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
echo "  1. Reload VSCode: Cmd+Shift+P → 'Developer: Reload Window'"
echo "  2. Ask a question to trigger hook"
echo "  3. Check logs: tail -f /tmp/hook-autosave-debug.log"
echo ""
echo "📚 Documentation:"
echo "  - Architecture: See RAPPORT_SAUVEGARDE_CONVERSATIONS.md"
echo "  - Troubleshooting: See MCP_STATUS.md"
```

**Install**:
```bash
chmod +x /home/giak/Work/MnemoLite/scripts/setup-new-project.sh

# Alias
echo 'alias mnemo-setup="/home/giak/Work/MnemoLite/scripts/setup-new-project.sh"' >> ~/.bashrc
source ~/.bashrc
```

**Usage**:
```bash
cd /path/to/new-project
mnemo-setup .
# Follow prompts
```

---

## 📝 CONCLUSION

### Recommandation Immédiate

**SHIP Level 1 aujourd'hui** (1h effort):
1. Créer script `setup-new-project.sh`
2. Ajouter alias bash
3. Tester sur projet dummy
4. Documenter dans MnemoLite README

**Bénéfices immédiats**:
- ✅ Setup 20min → 1min (95% réduction)
- ✅ Zéro erreurs (automated)
- ✅ Reproductible
- ✅ Documenté par le code

### Roadmap Suggérée

**Phase 1** (Aujourd'hui): Level 1 script
**Phase 2** (Si besoin, +2h): Level 2 validation
**Phase 3** (Si 5+ projets, +6h): Level 4 MCP tool
**Phase 4** (Si équipe, +16h): Level 6 CLI manager

### Métrique de Succès

**Mesurer**:
- Temps setup par projet (target: <2min)
- Taux d'erreur config (target: 0%)
- Projects adoptant MnemoLite (track)

---

**Rapport généré par**: Claude Code (Sonnet 4.5)
**Durée brainstorming**: Ultra-deep thinking
**Niveaux analysés**: 7 (0→6)
**Architectures explorées**: 7
**Scripts générés**: 3
**Insights**: 5 majeurs
