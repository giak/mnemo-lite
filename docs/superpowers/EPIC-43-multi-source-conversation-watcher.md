# 🔍 EPIC-43: Multi-Source Conversation Watcher

> **Statut** : ✅ Implémenté (v1 MVP)
> **Priorité** : 🔴 Haute (Core Feature — auto-import conversations)
> **Inspiration** : EPIC-24 auto-save daemon (bash) → refonte Python multi-sources
> **Effort estimé v1** : ~12h (daemon + 4 parsers + Docker integration + 54 tests)
> **Date** : Juin 2025
> **Dernière validation** : 54/54 tests passent, Docker Compose validé, dry-run OK
> **Philosophie** : KISS, polling-based, zero system deps, Docker-native

---

## Table des Matières

1. [Contexte & Problème](#1-contexte--problème)
2. [Architecture v1](#2-architecture-v1)
3. [Sources supportées (4)](#3-sources-supportées-4)
4. [Déploiement Docker](#4-déploiement-docker)
5. [Stories v1](#5-stories-v1)
6. [Guide de maintenance](#6-guide-de-maintenance)
7. [Guide d'évolution — ajouter une source](#7-guide-dévolution--ajouter-une-source)
8. [Référence technique : formats de données](#8-référence-technique--formats-de-données)
9. [Stratégie de test](#9-stratégie-de-test)
10. [Configuration](#10-configuration)
11. [Robustesse & Modes de défaillance](#11-robustesse--modes-de-défaillance)
12. [Questions décidées](#12-questions-décidées)
13. [Annexes v2+ (backlog)](#13-annexes-v2-backlog)

---

## 1. Contexte & Problème

### Le problème original

MnemoLite avait un système d'auto-import de conversations **mono-source** (Claude Code uniquement) via un script bash (`scripts/conversation-auto-import.sh`), activé par `ENABLE_AUTO_IMPORT=true`. Ce système présentait des limites majeures :

| Limite | Détail |
|--------|--------|
| **Mono-source** | Seul Claude Code était supporté |
| **Bash fragil** | Script shell difficile à tester et maintenir |
| **Pas de state persistant** | Re-importait tout à chaque redémarrage |
| **Pas de déduplication** | Conversations en double fréquentes |
| **Pas de logs structurés** | Debugging impossible |
| **Hook système requis** | Nécessitait un hook ou un cron pour tourner en continu |

### L'écosystème des AI coding tools

Les développeurs utilisent aujourd'hui **plusieurs** AI coding tools en parallèle :

| Outil | Stockage local | Format | Fréquence d'update |
|-------|---------------|--------|-------------------|
| **Claude Code** | `~/.claude/projects/` | JSONL (1 msg/ligne) | Temps réel (append) |
| **Codebuff** | `~/.config/manicode/projects/` | JSON (`chat-messages.json`) | Par session |
| **OpenCode** | `~/.local/share/opencode/opencode.db` | SQLite | Temps réel |
| **KiloCode/RooCode** | `~/.vscode/globalStorage/kilocode.kilo-code/tasks/` | JSON | Par task |

Chaque outil a un format, un schéma, et un cycle de vie différent. Le watcher doit comprendre chacun d'eux.

### La solution v1

Un daemon Python **multi-sources** qui :
1. **Poll** chaque source à intervalle régulier (pas de watchdog/inotify)
2. **Parse** les conversations en paires user/assistant
3. **Déduplique** via content hash (SHA-256)
4. **Poste** au MnemoLite API (`/v1/conversations/save`)
5. **Persiste** son state en JSON pour reprise après crash
6. **Se lance** comme subprocess Docker (zéro intervention système)

---

## 2. Architecture v1

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container (api)                    │
│                                                              │
│  ┌──────────┐  nohup   ┌──────────────────────────────────┐ │
│  │  FastAPI  │◄─────────│  multi-watcher-daemon.py         │ │
│  │  :8000    │  POST    │                                  │ │
│  └──────────┘ /save     │  ┌─────────────┐ ┌───────────┐  │ │
│                         │  │ClaudeCodeSrc│ │CodebuffSrc│  │ │
│                         │  └─────────────┘ └───────────┘  │ │
│                         │  ┌─────────────┐ ┌───────────┐  │ │
│                         │  │ OpenCodeSrc │ │KiloCodeSrc│  │ │
│                         │  └─────────────┘ └───────────┘  │ │
│                         │         │                        │ │
│                         │  ┌──────▼──────┐                 │ │
│                         │  │WatcherState │ ← JSON file     │ │
│                         │  │ (dedup+cursor)│  (Docker vol) │ │
│                         │  └─────────────┘                 │ │
│                         └──────────────────────────────────┘ │
│                                                              │
│  Volume mounts (ro):                                        │
│    /host/.claude/projects/                                   │
│    /host/.config/manicode/projects/                          │
│    /host/.local/share/opencode/                              │
└─────────────────────────────────────────────────────────────┘
```

### Data model interne

```python
@dataclass
class ConversationPair:
    user_message: str       # Texte brut de l'utilisateur
    assistant_message: str  # Texte brut de l'assistant (peut être multi-tour)
    project_name: str       # lowercase, ex: "mnemolite"
    session_id: str         # identifiant de session (source-spécifique)
    timestamp: str          # ISO 8601 ou vide
    source_tag: str         # "claude-code" | "codebuff" | "opencode" | "kilocode"

    @property
    def content_hash(self) -> str:
        # SHA-256 des 2 messages, tronqué à 16 chars → déduplication
        return hashlib.sha256(
            (self.user_message + self.assistant_message).encode()
        ).hexdigest()[:16]
```

### State management

```python
class WatcherState:
    """Persiste l'état d'import dans ~/.local/share/mnemo/multi-watcher-state.json"""
    state: Dict = {
        "sources": {           # Per-source cursor data
            "claude-code": {"file:path": last_size},
            "codebuff": {"file:path": last_mtime},
            "opencode": {"last_message_id": "abc123"},
            "kilocode": {"file:path": last_mtime},
        },
        "saved_hashes": [],   # Content hashes (dedup, max 10000)
        "stats": {}           # Runtime stats
    }
```

### State management — caveat `mark_saved`

> ⚠️ **`mark_saved` append sans vérifier les doublons.** La liste `saved_hashes` dans le JSON
> peut contenir des hashes en double. La lookup reste correcte car `is_saved` utilise un set
> caché (`_hash_set`) pour des lookups O(1). Au `save()`, la liste est tronquée aux 10000 plus
> récents. Ce n'est pas un bug, mais un piège de maintenance : un dev futur pourrait s'étonner
> de voir des doublons dans le JSON. Ne PAS "corriger" en ajoutant un check de doublon dans
> `mark_saved` — cela ralentirait l'append pour aucun bénéfice (le set gère déjà la dédup).

### Logging

Le daemon utilise **structlog** pour du logging structuré cohérent avec le reste du projet (API, services).

```python
# Configuration (module-level)
import structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),     # ou JSONRenderer via WATCHER_LOG_FORMAT=json
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger("watcher")
```

**Fallback** : Si structlog n'est pas installé (run local hors Docker), un `_PrintLogger` stub
mimique l'API structlog via `print()` avec timestamps :
```
[INFO] 2025-06-01 10:00:00 watcher_starting mode=single_poll sources=['claude-code', 'codebuff']
```

**JSON mode** : `WATCHER_LOG_FORMAT=json` active `JSONRenderer` pour ingestion OpenObserve
en Docker (cohérent avec les logs de l'API).

**Convention d'événements** : Noms structurés + key-value pairs :
```python
logger.info("new_pairs_found", source=source.name, count=len(pairs))
logger.warning("parse_error", source="claude-code", file=transcript_file.name, error=str(e))
logger.error("api_error_status", status=resp.status, body_preview=body[:200])
logger.info("source_skip", source="codebuff", reason="directory_not_found", path=str(s.projects_dir))
```

### Filtrage projet

Le daemon supporte un **filtre projet** pour éviter la pollution inter-projets dans la DB.

Sans filtre, le daemon importe les conversations de **tous** les projets trouvés dans les répertoires
sources (ex: `expanse`, `forge`, `test-dsl`...). Avec `--project-filter mnemolite` ou
`ACTIVE_PROJECT=mnemolite`, seules les conversations du projet MnemoLite sont importées.

**Optimisations par source** :
- **Codebuff** : skip le répertoire projet entier si le nom ne matche pas
- **Claude Code** : skip le transcript entier après décodage du nom de projet
- **OpenCode** : skip la session SQLite entière si le projet ne matche pas
- **KiloCode** : filtrage dans `save_pair()` (pas d'optimisation possible au niveau fichier)

```python
# Dans BaseSourceWatcher.save_pair()
if self.project_filter and pair.project_name != self.project_filter:
    logger.debug("project_filtered", source=pair.source_tag,
                 project=pair.project_name, filter=self.project_filter)
    return False
```

### Flux de sauvegarde

```
poll() → List[ConversationPair]
  │
  ├── project_filter: pair.project_name != filter?
  │     └── yes → skip (logger.debug "project_filtered")
  │
  ├── dedup: state.is_saved(pair.content_hash)?
  │     └── yes → skip
  │
  ├── dry_run? → logger.info("dry_run_save", ...) + state.mark_saved()
  │
  └── POST /v1/conversations/save
        │
        ├── 200 OK → state.mark_saved(hash) → return True
        └── error → logger.error("api_error_...", ...) + return False
```

### API endpoint appelé

```
POST /v1/conversations/save
Body: {
    "user_message": str,           # Required
    "user_message_clean": str,     # Optional (first 100 chars)
    "assistant_message": str,      # Required
    "project_name": str,           # Optional (from path)
    "session_id": str,             # Optional
    "timestamp": str,              # Optional (ISO 8601)
    "source": str                  # Optional ("claude-code"|"codebuff"|"opencode"|"kilocode")
}
```

---

## 3. Sources supportées (4)

### 3.1 Claude Code (`ClaudeCodeSource`)

**Emplacement** : `~/.claude/projects/` (ou `CLAUDE_PROJECTS_DIR` / `--claude-dir`)

**Structure de répertoire** :
```
~/.claude/projects/
  └── -home-giak-Work-MnemoLite/     # Nom encodé (dirs → tirets)
      ├── 0fd7901f-...jsonl           # Transcript de session (UUID.jsonl)
      └── agent-abc123-...jsonl       # Sub-agent (IGNORÉ)
```

**Format JSONL** (1 message par ligne) :
```jsonl
{"type":"summary","summary":"...","leafRole":"user","uuid":"..."}
{"type":"message","message":{"role":"user","content":"Explique ce code","timestamp":"2025-06-01T10:00:00"}}
{"type":"message","message":{"role":"assistant","content":[{"type":"text","text":"Ce code fait..."},{"type":"thinking","thinking":"Je dois..."}]}}
{"type":"message","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"...","content":"..."}]}}
```

**Parsing** :
- Skip les fichiers `agent-*` (sous-agents internes)
- Cooldown 60s : skip fichiers modifiés il y a moins de 60s (encore en écriture)
- Suivi incrémental par taille de fichier (`last_size`)
- Exclusion des `tool_result` (réponses d'outils, pas du user)
- Support des timestamps entiers (epoch) et chaînes (ISO)
- Consecutive assistant messages sont concaténés avec `\n`
- Contenu `thinking` tronqué à 200 chars

**Déduction du projet** :
```
-home-giak-Work-MnemoLite → /home/giak/Work/MnemoLite → "mnemolite"
-home-giak-projects-MyApp → /home/giak/projects/MyApp → "myapp"
```
Regex : `^-home-([^-]+)-Work-(.+)$` ou `^-home-([^-]+)-projects-(.+)$`

**Poll interval** : 30s

**Env vars** :
- `CLAUDE_PROJECTS_DIR` — surcharge le chemin par défaut

---

### 3.2 Codebuff (`CodebuffSource`)

**Emplacement** : `~/.config/manicode/projects/` (ou `CODEBUFF_PROJECTS_DIR` / `--codebuff-dir`)

**Structure de répertoire** :
```
~/.config/manicode/projects/
  └── MnemoLite/                     # Nom lisible du projet
      └── chats/
          └── 2026-07-01T11-00-00.000Z/   # ISO timestamp du chat
              └── chat-messages.json       # Messages de la session
```

**Format JSON** (`chat-messages.json`) :
```json
[
  {"variant": "user", "content": "What is the output?", "timestamp": "11:00 AM"},
  {
    "variant": "ai",
    "blocks": [
      {"type": "text", "content": "The output is 42."},
      {"type": "tool", "name": "run_command", "content": "..."}
    ]
  },
  {"variant": "ai", "content": "Direct content without blocks."}
]
```

**Parsing** :
- Suivi incrémental par mtime du fichier (`last_mtime`)
- Date extraite du nom du répertoire parent (premiers 10 chars : `2026-07-01`)
- Timestamp user : format `"HH:MM AM/PM"` combiné avec la date du répertoire
- Fallback : `content` direct si pas de `blocks` (AI messages)
- Tool blocks : `[Tool: tool_name]` (inclus mais synthétique)
- Consecutive AI messages sont concaténés

**Poll interval** : 30s

**Env vars** :
- `CODEBUFF_PROJECTS_DIR` — surcharge le chemin par défaut (dans le daemon)
- `CODEBUFF_DIR` — chemin côté host (dans docker-compose / `.env`)

> ⚠️ **Note : deux couches de config.** Le daemon utilise `CODEBUFF_PROJECTS_DIR` pour son chemin interne,
> tandis que docker-compose utilise `CODEBUFF_DIR` pour le chemin host qui sera monté dans le container.
> En mode Docker, les CLI args (`--codebuff-dir /host/...`) prévalent sur les env vars du daemon.

---

### 3.3 OpenCode (`OpenCodeSource`)

**Emplacement** : `~/.local/share/opencode/opencode.db` (ou `OPENCODE_DB_PATH` / `--opencode-db`)

**Schéma SQLite** :
```sql
-- Sessions (conversations)
session (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES project(id)
)

-- Projects
project (
    id TEXT PRIMARY KEY,
    path TEXT               -- ex: "/home/giak/Work/MnemoLite"
)

-- Messages
message (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    time_created TIMESTAMPTZ,
    data JSON               -- {"role": "user"|"assistant", "time": {"created": 1719800000000}}
)

-- Parts (text content of messages)
part (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    time_created TIMESTAMPTZ,
    data JSON               -- {"type": "text", "text": "content here"}
)
```

**Parsing** :
- **Cursor-based** : `last_message_id` → ne fetch que les messages nouveaux
- Rôle extrait via `json_extract(data, '$.role')` dans la DB
- Texte extrait via la table `part` avec `json_extract(data, '$.type') = 'text'`
- Batch IN clauses (500 max, compatibilité SQLite < 3.38)
- Timestamp depuis `data.time.created` (millisecondes epoch)
- Fallback `project_path` si JOIN `session↔project` échoue (schéma ancien)
- Limite initiale : 500 messages max au premier poll (anti-OOM)

**Poll interval** : 15s (requêtes SQLite très rapides)

**Env vars** :
- `OPENCODE_DB_PATH` — surcharge le chemin par défaut (dans le daemon)
- `OPENCODE_DIR` — chemin côté host du répertoire parent (dans docker-compose / `.env`)

> ⚠️ **Note : deux couches de config.** Le daemon utilise `OPENCODE_DB_PATH` pour pointer directement
> sur le fichier DB, tandis que docker-compose monte le répertoire parent via `OPENCODE_DIR`.
> En mode Docker, le CLI arg `--opencode-db /host/.local/share/opencode/opencode.db` prévaut.

---

### 3.4 KiloCode / RooCode (`KiloCodeSource`)

**Emplacement** : `~/.vscode/globalStorage/kilocode.kilo-code/` (ou `--kilocode-dir`)

**Chemins détectés automatiquement** (par ordre de priorité) :
1. `~/.vscode/globalStorage/kilocode.kilo-code/`
2. `~/.vscode-server/data/User/globalStorage/kilocode.kilo-code/`
3. `~/.vscode/globalStorage/roocode.roo-code/` (RooCode fork)
4. `~/.vscode-server/data/User/globalStorage/roocode.roo-code/`

**Structure de répertoire** :
```
kilocode.kilo-code/
  └── tasks/
      └── task-abc123/
          ├── api_conversation_history.json   # Messages de la conversation
          └── task.json                       # Metadata (cwd, workspace, etc.)
```

**Format JSON** (`api_conversation_history.json`) :
```json
[
  {
    "role": "user",
    "content": [
      {"type": "text", "text": "Refactor this module"},
      {"type": "tool_use", "name": "read_file", "input": {...}}
    ],
    "ts": "2025-06-01T10:00:00Z"
  },
  {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "I'll refactor..."},
      {"type": "tool_use", "name": "apply_diff", "input": {...}}
    ]
  }
]
```

**Parsing** :
- Suivi incrémental par mtime du fichier (`last_mtime`)
- XML metadata filtering : les blocs XML injectés par RooCode/KiloCode sont exclus :
  - `<environment_details>`, `<task>`, `<feedback>`, `<attempt_completion>`
  - `<ask_followup_question>`, `<new_task_created>`, `<task_completed>`
- Tool use blocks : `[Tool: tool_name]`
- Project name déduit de `task.json` (champs : `cwd`, `workspace`, `projectPath`, `rootPath`)
- Fallback : scan des autres fichiers JSON dans le répertoire de la task

**Poll interval** : 30s

**Env vars** :
- Aucune (auto-détection des chemins VS Code)

---

## 4. Déploiement Docker

### Principe

Le daemon se lance comme **subprocess** du container API via `nohup` dans le `command` du docker-compose. Aucune intervention système n'est requise (pas de systemd, crontab, ou hook).

### docker-compose.yml

```yaml
services:
  api:
    environment:
      CONVERSATION_WATCHER_ENABLED: ${CONVERSATION_WATCHER_ENABLED:-false}
    volumes:
      # Source data (read-only mounts from host)
      - ${CLAUDE_PROJECTS_DIR:-~/.claude/projects}:/host/.claude/projects:ro
      - ${CODEBUFF_DIR:-~/.config/manicode/projects}:/host/.config/manicode/projects:ro
      - ${OPENCODE_DIR:-~/.local/share/opencode}:/host/.local/share/opencode:ro
      # Persistent state (named volume — survives container restarts)
      - mnemo_watcher_state:/root/.local/share/mnemo
    command:
      - sh
      - -c
      - |
        if [ "${CONVERSATION_WATCHER_ENABLED:-false}" = "true" ]; then
          pip install -q aiohttp 2>/dev/null || true
          nohup python3 /app/scripts/multi-watcher-daemon.py \
            --api-url http://localhost:8000 \
            --project-filter ${ACTIVE_PROJECT:-mnemolite} \
            --claude-dir /host/.claude/projects \
            --codebuff-dir /host/.config/manicode/projects \
            --opencode-db /host/.local/share/opencode/opencode.db \
            > /tmp/multi-watcher.log 2>&1 &
        elif [ "${ENABLE_AUTO_IMPORT:-false}" = "true" ]; then
          nohup bash /app/scripts/conversation-auto-import.sh > /tmp/daemon.log 2>&1 &
        fi
        uvicorn main:app --host 0.0.0.0 --port 8000

volumes:
  mnemo_watcher_state:  # Persistent state for watcher dedup/cursor
```

### Points clés

| Aspect | Détail |
|--------|--------|
| **Activation** | `CONVERSATION_WATCHER_ENABLED=true` dans `.env` |
| **Sécurité** | Tous les mounts source sont `:ro` (lecture seule) |
| **Filtrage projet** | `ACTIVE_PROJECT=mnemolite` — n'importe que les conversations du projet actif |
| **Persistance** | Volume nommé `mnemo_watcher_state` pour le state JSON |
| **Fallback** | `ENABLE_AUTO_IMPORT` encore supporté si watcher désactivé |
| **Safety pip** | `pip install -q aiohttp` en cas d'image non rebuild |
| **Logs** | `/tmp/multi-watcher.log` dans le container |

### .env

```bash
# Multi-source conversation watcher (Claude Code + Codebuff + OpenCode)
# Set to false to disable auto-import of conversations from AI tools
CONVERSATION_WATCHER_ENABLED=true
CODEBUFF_DIR=/home/giak/.config/manicode/projects
OPENCODE_DIR=/home/giak/.local/share/opencode
# Active project filter — only import conversations for this project
ACTIVE_PROJECT=mnemolite
```

---

## 5. Stories v1

### 📝 Story 43.1 : Core Daemon & Data Model

**En tant qu'** architecte système,
**Je veux** un daemon Python multi-sources avec polling et déduplication,
**Afin que** les conversations de tous mes AI tools soient importées automatiquement.

#### Critères d'Acceptation

- [x] Créer `scripts/multi-watcher-daemon.py` (monolithe, ~1200 lignes)
- [x] Dataclass `ConversationPair` avec content hash SHA-256
- [x] `WatcherState` avec persistance JSON, déduplication par hash, cursors par source
- [x] `BaseSourceWatcher` abstrait avec `poll()`, `save_pair()`, session aiohttp
- [x] `MultiSourceWatcher` orchestrateur avec run concurrent + graceful shutdown
- [x] CLI argparse : `--source`, `--api-url`, `--dry-run`, `--once`, `--state-file`
- [x] CLI par source : `--claude-dir`, `--codebuff-dir`, `--opencode-db`, `--kilocode-dir`
- [x] Signal handlers SIGINT/SIGTERM

#### Effort : ~4h

---

### 📝 Story 43.2 : 4 Source Parsers

**En tant qu'** utilisateur multi-outils,
**Je veux** que le daemon supporte Claude Code, Codebuff, OpenCode et KiloCode,
**Afin que** toutes mes conversations soient capturées.

#### Critères d'Acceptation

- [x] `ClaudeCodeSource` : JSONL parsing, agent-* skip, cooldown 60s, incremental size
- [x] `CodebuffSource` : JSON parsing, blocks+content fallback, date from dir name
- [x] `OpenCodeSource` : SQLite cursor-based, batch IN, JOIN session↔project
- [x] `KiloCodeSource` : JSON parsing, XML metadata filter, task.json project detection
- [x] Auto-détection : source ignorée si répertoire/DB inexistant (avec log `[SKIP]`)
- [x] Filtrage : messages < 5 chars ignorés, tool_result exclus

#### Effort : ~4h

---

### 📝 Story 43.3 : Docker Integration

**En tant qu'** opérateur DevOps,
**Je veux** que le watcher démarre automatiquement avec l'API,
**Afin que** je n'aie aucune intervention système à faire.

#### Critères d'Acceptation

- [x] `docker-compose.yml` : volume mounts ro pour les 3 sources principales
- [x] Volume nommé `mnemo_watcher_state` pour la persistance du state
- [x] Env var `CONVERSATION_WATCHER_ENABLED` (défaut: `false` dans compose, `true` dans `.env`)
- [x] Command block : `nohup python3 multi-watcher-daemon.py ... &`
- [x] Fallback `ENABLE_AUTO_IMPORT` conservé
- [x] Safety `pip install -q aiohttp` dans le command block
- [x] `.env` mis à jour avec les variables du watcher

#### Effort : ~2h

---

### 📝 Story 43.4 : Tests Unitaires (54 tests)

**En tant que** développeur,
**Je veux** une suite de tests complète pour chaque source,
**Afin que** les parsers restent corrects quand les formats évoluent.

#### Critères d'Acceptation

- [x] `tests/scripts/test_multi_watcher_daemon.py` — 54 tests
- [x] `tests/scripts/conftest.py` — Local conftest override (pas de DB requise)
- [x] `tests/conftest.py` — Guard `try/except` sur sqlalchemy import
- [x] Tests par source : ClaudeCodeSource (8), CodebuffSource (7), OpenCodeSource (7), KiloCodeSource (10)
- [x] Tests WatcherState (7), ConversationPair (2), BaseSourceWatcher (3)
- [x] Edge cases : integer timestamps, list user content, AI sans blocks, tool_result skip, XML filter
- [x] Import via `importlib.util` (nom de fichier avec tirets)

#### Effort : ~2h

---

## 6. Guide de maintenance

### 6.1 Fichiers clés

| Fichier | Rôle | Lignes |
|---------|------|--------|
| `scripts/multi-watcher-daemon.py` | Daemon complet (monolithe) | ~1200 |
| `tests/scripts/test_multi_watcher_daemon.py` | 54 tests unitaires | ~600 |
| `tests/scripts/conftest.py` | Conftest local (stub DB fixtures) | ~50 |
| `docker-compose.yml` | Configuration Docker | — |
| `.env` | Variables d'activation | — |

### 6.2 Logs & debugging

Le daemon utilise **structlog** (ConsoleRenderer par défaut, JSONRenderer via `WATCHER_LOG_FORMAT=json`).

**Dans le container** :
```bash
# Voir les logs du watcher (format structuré)
docker compose exec api tail -f /tmp/multi-watcher.log

# Voir les logs en JSON (pour ingestion OpenObserve)
# Ajouter WATCHER_LOG_FORMAT=json dans docker-compose.yml environment

# Voir le state actuel
docker compose exec api cat /root/.local/share/mnemo/multi-watcher-state.json

# Vérifier que le process tourne
docker compose exec api ps aux | grep multi-watcher

# Chercher une erreur spécifique dans les logs structurés
docker compose exec api grep '"error"' /tmp/multi-watcher.log
docker compose exec api grep 'api_error_status' /tmp/multi-watcher.log
```

**En local (hors Docker)** :
```bash
# Dry-run single poll (preview sans sauvegarder)
python3 scripts/multi-watcher-daemon.py --dry-run --once --api-url http://localhost:8001

# Une seule source
python3 scripts/multi-watcher-daemon.py --source codebuff --dry-run --once

# Changer l'API URL
python3 scripts/multi-watcher-daemon.py --api-url http://localhost:8000 --once

# Activer les logs JSON (si structlog est installé localement)
WATCHER_LOG_FORMAT=json python3 scripts/multi-watcher-daemon.py --dry-run --once
```

### 6.3 Problèmes courants

| Problème | Cause | Solution |
|----------|-------|----------|
| `source_skip` — directory not found | Mount manquant ou chemin erroné | Vérifier `CLAUDE_PROJECTS_DIR` dans `.env` + mount dans docker-compose |
| `api_error_status` — status 422 | Format de payload invalide | Vérifier le schéma de `/v1/conversations/save` |
| Conversations en double | State file perdu (container recréé) | Vérifier que `mnemo_watcher_state` est un volume nommé |
| `api_call_failed` — No module named 'aiohttp' | Image non rebuild | `make build` ou le safety `pip install` dans le command block |
| Watcher ne démarre pas | `CONVERSATION_WATCHER_ENABLED!=true` | Vérifier `.env` et les defaults docker-compose |
| File pas encore lu (cooldown) | Fichier modifié < 60s ago | Normal — le cooldown évite les lectures partielles |
| `parse_error` dans les logs | JSON/JSONL malformé dans une source | Vérifier le fichier concerné (champ `file=` dans le log) |

### 6.4 Reset du state

Pour forcer un re-import de toutes les conversations :
```bash
# Supprimer le state file (prochain démarrage = tout ré-importer)
docker compose exec api rm /root/.local/share/mnemo/multi-watcher-state.json
docker compose restart api
```

---

## 7. Guide d'évolution — ajouter une source

### Processus pas-à-pas

Pour ajouter un nouvel AI coding tool (ex: **Cursor**, **Windsurf**, **Aider**), suivre ce template :

#### Étape 1 : Comprendre le format de stockage

```bash
# Explorer les répertoires de l'outil
find ~ -path "*cursor*" -name "*.json" 2>/dev/null | head -20
find ~ -path "*windsurf*" -name "*.json" 2>/dev/null | head -20

# Analyser le schéma
cat ~/.cursor/.../conversations/...json | python3 -m json.tool | head -50
```

Documenter dans la section [8](#8-référence-technique--formats-de-données) :
- Chemin de stockage
- Format (JSONL, JSON, SQLite, autre)
- Schéma des messages (rôles, contenu, timestamps)
- Spécificités (tool calls, thinking, metadata)

#### Étape 2 : Implémenter le parser

Créer une classe héritant de `BaseSourceWatcher` dans `multi-watcher-daemon.py` :

```python
class CursorSource(BaseSourceWatcher):
    """Watches ~/.cursor/... for conversations."""

    POLL_INTERVAL = 30

    def __init__(self, state: WatcherState, api_url: str, dry_run: bool = False,
                 storage_dir: str = None):
        super().__init__(state, api_url, dry_run)
        self.storage_dir = Path(
            storage_dir or os.getenv("CURSOR_STORAGE_DIR",
                                      str(Path.home() / ".cursor" / "conversations"))
        )

    async def poll(self) -> List[ConversationPair]:
        if not self.storage_dir.exists():
            return []
        # ... parser logic ...
```

**Règles de parsing communes** :
- Retourner `List[ConversationPair]`
- Filtrer les messages < 5 chars
- Exclure les tool_result / feedback automatique
- Concaténer les assistant messages consécutifs
- Utiliser `self.state.get_source_state("cursor")` pour le cursor
- Appeler `self.state.is_saved(pair.content_hash)` avant d'ajouter un pair

#### Étape 3 : Enregistrer dans `build_sources()`

```python
def build_sources(args, state: WatcherState) -> List[BaseSourceWatcher]:
    # ... existing sources ...

    # Cursor
    if not source_filter or source_filter == "cursor":
        s = CursorSource(state, api_url, dry_run, args.cursor_dir)
        if s.storage_dir.exists():
            sources.append(s)
        else:
            print(f"[SKIP] Cursor: directory not found ({s.storage_dir})")
```

#### Étape 4 : Ajouter le CLI arg

```python
parser.add_argument("--cursor-dir", type=str, default=None,
                    help="Custom Cursor storage directory")
```

#### Étape 5 : Docker integration

```yaml
# docker-compose.yml
environment:
  CURSOR_DIR: ${CURSOR_DIR:-/home/giak/.cursor/conversations}
volumes:
  - ${CURSOR_DIR:-/home/giak/.cursor/conversations}:/host/.cursor/conversations:ro
```

Dans le command block :
```bash
--cursor-dir /host/.cursor/conversations \
```

#### Étape 6 : Écrire les tests

Suivre le pattern de `test_multi_watcher_daemon.py` :

```python
class TestCursorSource:
    @pytest.fixture
    def source(self, state, api_url):
        return CursorSource(state, api_url)

    def test_poll_empty_dir(self, tmp_path, state, api_url):
        source = CursorSource(state, api_url, storage_dir=str(tmp_path))
        pairs = asyncio.get_event_loop().run_until_complete(source.poll())
        assert pairs == []

    @pytest.mark.asyncio
    async def test_poll_finds_pairs(self, tmp_path, state, api_url):
        # ... setup test data ...
        pairs = await source.poll()
        assert len(pairs) >= 1
```

#### Étape 7 : Documenter

Ajouter une section dans [3. Sources supportées](#3-sources-supportées-4) et dans [8. Référence technique](#8-référence-technique--formats-de-données).

---

## 8. Référence technique : formats de données

### 8.1 Claude Code — JSONL Transcript

**Chemin** : `~/.claude/projects/<encoded-dir>/<uuid>.jsonl`

**Ligne type** :
```json
{"type":"message","message":{"role":"user","content":"...","timestamp":"..."}}
```

**Variantes de `content`** :

| Type | Exemple | Traitement |
|------|---------|------------|
| `str` | `"Hello"` | Direct |
| `list[dict]` avec `type=text` | `[{"type":"text","text":"..."}]` | Extraire `.text` |
| `list[dict]` avec `type=thinking` | `[{"type":"thinking","thinking":"..."}]` | Tronquer 200 chars |
| `list[dict]` avec `type=tool_result` | `[{"type":"tool_result",...}]` | **Ignorer** (pas du user) |

**Variantes de `timestamp`** :

| Type | Exemple | Traitement |
|------|---------|------------|
| `str` ISO | `"2025-06-01T10:00:00"` | Direct |
| `int/float` epoch | `1735689600` | `datetime.fromtimestamp()` |

**Noms de répertoires encodés** :

| Encoded | Décodé | Regex |
|---------|--------|-------|
| `-home-giak-Work-MnemoLite` | `/home/giak/Work/MnemoLite` | `^-home-([^-]+)-Work-(.+)$` |
| `-home-giak-projects-MyApp` | `/home/giak/projects/MyApp` | `^-home-([^-]+)-projects-(.+)$` |

### 8.2 Codebuff — JSON Chat

**Chemin** : `~/.config/manicode/projects/<project>/chats/<iso-timestamp>/chat-messages.json`

**Message type** :

| Variant | `variant` | Contenu | Traitement |
|---------|-----------|---------|------------|
| User | `"user"` | `content: str` | Direct |
| AI avec blocks | `"ai"` | `blocks: [{type, content/name}]` | Extraire text blocks, tool → `[Tool: name]` |
| AI sans blocks | `"ai"` | `content: str` | Direct (fallback) |

**Timestamps** : Format `"HH:MM AM/PM"` dans le message, date ISO dans le nom du répertoire parent.

### 8.3 OpenCode — SQLite

**Chemin** : `~/.local/share/opencode/opencode.db`

**Tables clés** :

| Table | Colonnes clés | Usage |
|-------|---------------|-------|
| `session` | `id`, `project_id` | Lier conversation → projet |
| `project` | `id`, `path` | Chemin du projet |
| `message` | `id`, `session_id`, `time_created`, `data` (JSON) | Messages |
| `part` | `id`, `message_id`, `time_created`, `data` (JSON) | Contenu textuel |

**JSON dans `data`** :
```json
// message.data
{"role": "user", "time": {"created": 1719800000000}}

// part.data
{"type": "text", "text": "actual content"}
```

**Requêtes clés** :

```sql
-- Rôle du message
SELECT json_extract(data, '$.role') as role FROM message WHERE id = ?;

-- Texte des parts
SELECT message_id, data FROM part
WHERE message_id IN (...)
AND json_extract(data, '$.type') = 'text'
ORDER BY time_created ASC;

-- Project path
SELECT s.id, p.path FROM session s LEFT JOIN project p ON s.project_id = p.id;
```

### 8.4 KiloCode / RooCode — JSON Task History

**Chemin** : `~/.vscode/globalStorage/kilocode.kilo-code/tasks/<task-id>/api_conversation_history.json`

**Message type** :

| Rôle | `content` type | Traitement |
|------|----------------|------------|
| `user` | `list[dict]` avec `type=text` | Extraire `.text`, filtrer XML |
| `user` | `list[dict]` avec `type=tool_use` | `[Tool: name]` |
| `assistant` | Identique | Identique |

**XML metadata à filtrer** (injecté par RooCode/KiloCode, pas du contenu utilisateur) :
```
<environment_details>, <task>, <feedback>,
<attempt_completion>, <ask_followup_question>,
<new_task_created>, <task_completed>
```

**Project detection** (`task.json`) :
```json
{"cwd": "/home/giak/Work/MnemoLite"}  → "mnemolite"
```
Champs testés : `cwd`, `workspace`, `projectPath`, `rootPath`

---

## 9. Stratégie de test

### Structure

```
tests/
  conftest.py                          # Guard sqlalchemy import
  scripts/
    conftest.py                         # Stub DB fixtures (no Docker/PG needed)
    test_multi_watcher_daemon.py       # 54 unit tests
```

### Import du daemon

Le fichier utilise des tirets (`multi-watcher-daemon.py`), pas un identifiant Python valide. L'import se fait via `importlib.util` :

```python
import importlib.util

_mod_path = os.path.join(_project_root, "scripts", "multi-watcher-daemon.py")
_spec = importlib.util.spec_from_file_location("multi_watcher_daemon", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["multi_watcher_daemon"] = _mod
_spec.loader.exec_module(_mod)

ConversationPair = _mod.ConversationPair
WatcherState = _mod.WatcherState
# ... etc
```

**Note** : Le daemon a un `sys.exit(1)` si `aiohttp` n'est pas installé. Les tests mockent `aiohttp` avant l'import :
```python
if "aiohttp" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["aiohttp"] = MagicMock()
```

### Conftest local

`tests/scripts/conftest.py` override les fixtures DB du root conftest pour permettre l'exécution sans PostgreSQL :

```python
@pytest.fixture(scope="session")
def test_db_url():
    pytest.skip("TEST_DATABASE_URL not set — script tests don't need a DB")

@pytest.fixture(scope="session", autouse=True)
def _clean_test_db_at_session_start():
    yield  # no-op
```

### Coverage par source

| Source | Tests | Edge cases couverts |
|--------|-------|---------------------|
| `ConversationPair` | 2 | Hash déterminisme, unicité |
| `WatcherState` | 7 | mark_saved, is_saved, persist/reload, parent dir creation, hash set caching, idempotent lookup |
| `BaseSourceWatcher` | 3 | Project name extraction, Claude dir decode |
| `ClaudeCodeSource` | 8 | Poll finds pairs, tool_result skip, short msg skip, unchanged skip, list user content (text blocks), integer timestamp, agent-* skip, _extract_text |
| `CodebuffSource` | 7 | Poll finds pairs, multiple AI blocks, short msg skip, already-seen skip, AI content without blocks, date from dir name, invalid JSON |
| `OpenCodeSource` | 7 | DB not found, finds pairs, short msg skip, cursor incremental, multiple assistants, no-project fallback, cursor prevents rereading |
| `KiloCodeSource` | 10 | No storage dir, finds pairs, project from task.json, default project, XML filter, short msg skip, already-seen, extract_blocks, invalid history, multiple assistants |

### Exécution

```bash
# Tous les tests du watcher
pytest tests/scripts/test_multi_watcher_daemon.py -v

# Une seule classe
pytest tests/scripts/test_multi_watcher_daemon.py::TestClaudeCodeSource -v

# Un seul test
pytest tests/scripts/test_multi_watcher_daemon.py::TestClaudeCodeSource::test_poll_handles_integer_timestamp -v
```

---

## 10. Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `CONVERSATION_WATCHER_ENABLED` | `false` | Activer le watcher dans Docker |
| `ACTIVE_PROJECT` | `mnemolite` | Projet actif — seules les conversations de ce projet sont importées |
| `CLAUDE_PROJECTS_DIR` | `~/.claude/projects` | Répertoire Claude Code (host) |
| `CODEBUFF_DIR` | `~/.config/manicode/projects` | Répertoire Codebuff (host) |
| `OPENCODE_DIR` | `~/.local/share/opencode` | Répertoire OpenCode (host) |
| `WATCHER_LOG_FORMAT` | `""` (console) | `"json"` pour JSON logs (OpenObserve) |
| `MNEMO_WATCHER_STATE` | `~/.local/share/mnemo/multi-watcher-state.json` | State file path |

### CLI arguments

| Arg | Défaut | Description |
|-----|--------|-------------|
| `--source` | all | Filtrer à une source : `claude-code`, `codebuff`, `opencode`, `kilocode` |
| `--project-filter` | none | N'importer que les conversations de ce projet (ex: `mnemolite`). Fallback : `ACTIVE_PROJECT` env var |
| `--api-url` | `http://localhost:8001` | URL de l'API MnemoLite |
| `--dry-run` | false | Preview sans sauvegarder |
| `--once` | false | Single poll cycle + exit |
| `--state-file` | default | Chemin du state file |
| `--claude-dir` | default | Surcharge chemin Claude Code |
| `--codebuff-dir` | default | Surcharge chemin Codebuff |
| `--opencode-db` | default | Surcharge chemin OpenCode DB |
| `--kilocode-dir` | default | Surcharge chemin KiloCode |

### Dépendances

| Package | Version | Pourquoi |
|---------|---------|----------|
| `aiohttp` | >=3.9.0 | HTTP client pour POST `/save` |
| Python stdlib | 3.10+ | `sqlite3`, `json`, `hashlib`, `asyncio`, `argparse` |

---

## 11. Robustesse & Modes de défaillance

### Défaillances gérées

| Scénario | Comportement | Impact |
|----------|-------------|--------|
| **API down** (502/503/timeout) | `save_pair` log l'erreur, return False. Prochain poll réessaie | Perte temporaire, auto-récupération au cycle suivant |
| **State file corrompu** | `_load()` catch l'exception, retourne un state vierge | ⚠️ Re-import de toutes les conversations (dédup par hash côté API) |
| **State file effacé** | Idem — state vierge, re-import complet | Même impact, les hashes déjà sauvés seront skip côté daemon |
| **Fichier en écriture** (Claude Code) | Cooldown 60s : skip fichiers modifiés < 60s ago | Pas de lecture partielle |
| **aiohttp pas installé** | `sys.exit(1)` au démarrage du daemon | Docker safety pip install comme fallback |
| **Données source illisibles** (JSON malformé) | `try/except` dans chaque parser, message `[WARN]` | Fichier ignoré, les autres continuent |
| **Container restart** | State persisté dans volume nommé `mnemo_watcher_state` | Pas de perte de state, reprise au curseur |
| **Outil non installé** | Source `[SKIP]` avec log, pas d'erreur | Les autres sources fonctionnent normalement |

### Vie privée des conversations

> ⚠️ Le daemon poste les messages **bruts** au endpoint `/v1/conversations/save`.
> Il n'applique PAS le `PrivacyService` (EPIC-42) sur le contenu avant l'envoi.
> Le PrivacyService est appliqué côté API dans `write_memory` / `update_memory`, mais le
> endpoint `/save` n'est actuellement pas couvert.
>
> **Action v2** : Intégrer PrivacyService dans le flux de sauvegarde des conversations
> (Story 43.5 v2 — voir Annexe C).

### Améliorations robustesse v2+

| Amélioration | Description | Effort |
|-------------|-------------|--------|
| **Retry avec backoff** | Exponential backoff sur erreurs API 5xx | ~1h |
| **State file backup** | Garder `.bak` du state précédent | ~30min |
| **PrivacyService integration** | Sanitizer les conversations avant POST | ~2h |
| **Heartbeat file** | Écrire un heartbeat timestamp pour monitoring | ~30min |
| **State validation** | Checksum ou version dans le state JSON | ~1h |

---

## 12. Questions décidées

| # | Question | Décision | Raison |
|---|----------|----------|--------|
| Q1 | Polling vs inotify/watchdog ? | **Polling** | Simplicité, pas de deps, fonctionne sur NFS/Docker mounts |
| Q2 | Monolithe vs modules séparés ? | **Monolithe** (~1200 lignes) | Facile à déployer (1 fichier), pas d'import hell. Refactor si > 2000 lignes |
| Q3 | State : JSON vs SQLite ? | **JSON** | Suffisant pour 10K hashes, lisible, debuggable |
| Q4 | Dédup : hash complet vs tronqué ? | **Tronqué 16 chars** | Collision négligeable à cette échelle, plus compact |
| Q5 | Subprocess vs background task FastAPI ? | **Subprocess** | Isolation crash, pas de coupling avec le lifespan, redémarrage indépendant |
| Q6 | Docker mounts : ro ou rw ? | **ro** (lecture seule) | Le watcher ne modifie jamais les données source |
| Q7 | Default `CONVERSATION_WATCHER_ENABLED` ? | **`false`** dans compose | Breaking change si `true` par défaut. `.env` override pour ce setup |
| Q8 | Cooldown fichier (Claude Code) ? | **60s** | Évite les lectures partielles pendant l'écriture active |
| Q9 | Seuil minimum message ? | **5 chars** | Filtre les acks, tool results courts, erreurs vides |
| Q10 | Max saved_hashes ? | **10000** | Limite mémoire, les plus anciens sont tronqués au save |
| Q11 | OpenCode : premier poll limit ? | **500 messages** | Anti-OOM sur grosses DB historiques |
| Q12 | Logging : print() vs structlog ? | **structlog + fallback** | Cohérent avec l'API, fallback `_PrintLogger` pour runs locaux. JSON mode via `WATCHER_LOG_FORMAT=json` |
| Q13 | Log format par défaut dans Docker ? | **ConsoleRenderer** | Plus lisible pour `docker compose logs`. JSON mode opt-in pour OpenObserve |
| Q14 | Filtrage projet : whitelist ou tout importer ? | **`ACTIVE_PROJECT` whitelist** | Un seul projet actif par instance MnemoLite. Sans filtre, tous les projets sont importés (risque de pollution DB). `--project-filter` CLI arg + `ACTIVE_PROJECT` env var. Optimisations par source pour skip early. |

---

## 13. Annexes v2+ (backlog)

### Annexe A : Nouvelles sources potentielles

> Voir aussi le [Guide d'évolution — ajouter une source](#7-guide-dévolution--ajouter-une-source) pour le processus pas-à-pas.

| Outil | Stockage | Format | Complexité | Priorité |
|-------|----------|--------|------------|----------|
| **Cursor** | `~/.cursor/` | JSON (conversations DB) | Moyenne | Haute (populaire) |
| **Windsurf** | `~/.windsurf/` | JSON | Moyenne | Moyenne |
| **Aider** | `.aider.chat.history.md` | Markdown | Basse | Basse |
| **Continue** | `~/.continue/` | JSON | Moyenne | Moyenne |
| **Cline** | `~/.vscode/extensions/saoudrissa.cline/` | JSON | Basse | Basse |

### Annexe B : Améliorations architecture

| Feature | Description | Effort |
|---------|-------------|--------|
| **Refactor en modules** | `watcher/base.py`, `watcher/claude_code.py`, etc. | ~2h |
| **OTel instrumentation** | Spans pour chaque poll + save | ~2h |
| **Health endpoint** | Le daemon expose un `/health` sur un port secondaire | ~2h |
| **Graceful restart** | SIGHUP pour forcer un re-scan complet | ~1h |
| **Config hot-reload** | Recharger les chemins sans redémarrer | ~2h |

### Annexe C : Améliorations parsing

### Annexe C-1 : Story 43.5 v2 — PrivacyService Integration

Actuellement, le daemon poste les messages bruts au endpoint `/save`. Le PrivacyService
(EPIC-42) n'est pas appliqué. Pour fermer cette faille :

```
Conversation Pair
  → PrivacyService.sanitize(user_message)     ← NOUVEAU
  → PrivacyService.sanitize(assistant_message) ← NOUVEAU
  → POST /v1/conversations/save (contenu sanitisé)
```

Options d'implémentation :
1. **Côté daemon** : Importer `PrivacyService` dans le daemon (ajout dépendance au module `api/services/`)
2. **Côté API** : Appliquer PrivacyService dans le endpoint `/save` (comme pour `write_memory`)
3. **Hybride** : Côté API (recommandé — une seule place de truth)

Effort estimé : ~2h

### Annexe C-2 : Améliorations parsing (suite)

| Feature | Description | Effort |
|---------|-------------|--------|
| **Streaming JSONL** | Lire les nouvelles lignes sans recharger tout le fichier (seek) | ~2h |
| **Rich tool calls** | Inclure les inputs/outputs d'outils (optionnel, configurable) | ~3h |
| **Multi-user content** | Supporter les conversations avec plusieurs participants | ~2h |
| **Image/file attachments** | Détecter et référencer les pièces jointes | ~3h |
| **Thinking full** | Inclure le thinking complet (pas tronqué) via config | ~1h |

### Annexe D : Améliorations ops

| Feature | Description | Effort |
|---------|-------------|--------|
| **Prometheus metrics** | Counter saved/skipped/errors par source | ~2h |
| **Alerting** | Alerte si 0 conversations importées depuis N heures | ~1h |
| **Backfill historique** | `--backfill` mode pour importer tout l'historique | ~2h |
| **Rate limiting API** | Backoff exponentiel si API retourne 429/5xx | ~1h |
| **Parallel saves** | `asyncio.gather()` pour les POST parallèles | ~1h |
| **State compression** | Rotate les saved_hashes quand la liste dépasse 10K | ~1h |

### Annexe E : Comparaison avec l'ancien système (EPIC-24)

| Aspect | EPIC-24 (bash) | EPIC-43 (Python) |
|--------|----------------|-------------------|
| Sources | Claude Code only | 4 sources |
| Langage | Bash | Python 3.10+ |
| State | Aucun | JSON persistant + dédup |
| Tests | 0 | 54 |
| Structured logs | ❌ print() | ✅ structlog (ConsoleRenderer / JSONRenderer) |
| Docker integration | `ENABLE_AUTO_IMPORT` | `CONVERSATION_WATCHER_ENABLED` |
| Project filtering | ❌ (all projects) | ✅ `--project-filter` / `ACTIVE_PROJECT` |
| Incremental read | ❌ (tout re-lire) | ✅ (size/mtime/cursor) |
| Graceful shutdown | ❌ | ✅ (SIGINT/SIGTERM) |
| Dry-run | ❌ | ✅ (`--dry-run --once`) |
| Multi-source | ❌ | ✅ (concurrent asyncio) |

---

*EPIC-43 v1 MVP — ✅ Implémenté — 54/54 tests passent — Juin 2025*
