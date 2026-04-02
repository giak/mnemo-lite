# EPIC-24: Auto-Save Daemon - Architecture Proposal

**Date**: 2025-10-29
**Version**: 1.0.0
**Status**: ⏳ PENDING VALIDATION

---

## 🎯 Objectif

**Sauvegarder automatiquement et de manière transparente TOUTES les conversations Claude Code dans MnemoLite PostgreSQL.**

**Contraintes:**
- ✅ Automatique (aucune action user)
- ✅ Transparent (user ne voit rien)
- ✅ Self-contained (tout dans Docker)
- ✅ Zéro config externe
- ✅ Pas d'impact système OS

---

## 📐 Architecture Globale

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HOST SYSTEM                                  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ User's Home Directory                                          │ │
│  │  ~/.claude/projects/-home-giak-Work-MnemoLite/                │ │
│  │    ├── 5906b2a1-cbd9-4d97-bc2b-81445d816ebe.jsonl (session 1)│ │
│  │    ├── 0eb566c8-0e8d-4f56-9b6b-7ad909bdb630.jsonl (session 2)│ │
│  │    └── [autres sessions...]                                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                             ↑ (read-only mount)                      │
└─────────────────────────────┼────────────────────────────────────────┘
                              │
┌─────────────────────────────┼────────────────────────────────────────┐
│                    DOCKER COMPOSE STACK                              │
│                             │                                         │
│  ┌──────────────────────────▼──────────────────────────────────────┐ │
│  │                   API CONTAINER                                 │ │
│  │                                                                  │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │ Process 1: Uvicorn API Server                              │ │ │
│  │  │  - FastAPI app (port 8000)                                 │ │ │
│  │  │  - MCP Server                                              │ │ │
│  │  │  - Routes, endpoints                                       │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  │                             ┃                                    │ │
│  │                             ┃ (running in parallel)              │ │
│  │                             ┃                                    │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │ Process 2: Conversation Auto-Save Daemon                   │ │ │
│  │  │                                                            │ │ │
│  │  │  while True:                                               │ │ │
│  │  │    ├─> 1. Scan ~/.claude/projects/*.jsonl                 │ │ │
│  │  │    ├─> 2. Parse new exchanges (user+assistant pairs)      │ │ │
│  │  │    ├─> 3. Compute hash (deduplication)                    │ │ │
│  │  │    ├─> 4. Save via WriteMemoryTool                        │ │ │
│  │  │    │      ├─> MemoryRepository (PostgreSQL)               │ │ │
│  │  │    │      └─> EmbeddingService (768D vectors)             │ │ │
│  │  │    └─> 5. sleep(30)  # Poll every 30 seconds              │ │ │
│  │  │                                                            │ │ │
│  │  │  Logs: /tmp/conversation-daemon.log                       │ │ │
│  │  │  State: /tmp/conversation-daemon-state.json               │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  │                             │                                    │ │
│  │                             └─────────────────┐                  │ │
│  └───────────────────────────────────────────────┼──────────────────┘ │
│                                                   │                    │
│  ┌────────────────────────────────────────────────▼─────────────────┐ │
│  │                  POSTGRES CONTAINER (DB)                         │ │
│  │                                                                   │ │
│  │  PostgreSQL 18.1 + pgvector                                      │ │
│  │    ├─> memories table                                            │ │
│  │    │     ├─> id (UUID)                                           │ │
│  │    │     ├─> title (text)                                        │ │
│  │    │     ├─> content (text)                                      │ │
│  │    │     ├─> memory_type ('conversation')                        │ │
│  │    │     ├─> author ('AutoSave')                                 │ │
│  │    │     ├─> embedding (vector(768))                             │ │
│  │    │     ├─> tags (text[])                                       │ │
│  │    │     ├─> created_at (timestamp)                              │ │
│  │    │     └─> deleted_at (timestamp, nullable)                    │ │
│  │    └─> Vector search index (HNSW)                                │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flow d'Exécution Détaillé

### 1. Démarrage Système

```
User exécute:
    $ docker compose up

Docker Compose:
    ├─> Start DB container (PostgreSQL)
    └─> Start API container
            ├─> Launch Process 1: uvicorn api.main:app
            └─> Launch Process 2: python3 /app/scripts/conversation-daemon.py
                    │
                    └─> Daemon initialized
                            ├─> Load state from /tmp/conversation-daemon-state.json
                            ├─> Connect to PostgreSQL
                            ├─> Initialize MnemoLite services
                            └─> Enter polling loop
```

### 2. Polling Loop (Every 30 seconds)

```
┌─────────────────── ITERATION N ───────────────────┐
│                                                    │
│ 1. SCAN TRANSCRIPTS                               │
│    ├─> Find all *.jsonl in ~/.claude/projects/   │
│    ├─> Exclude agent-*.jsonl                      │
│    └─> Sort by modification time (newest first)   │
│                                                    │
│ 2. FOR EACH TRANSCRIPT                            │
│    ├─> Load state: last_processed_position        │
│    ├─> Seek to last position                      │
│    ├─> Read new lines only                        │
│    └─> Parse JSONL messages                       │
│                                                    │
│ 3. EXTRACT EXCHANGES                              │
│    ├─> Find user messages                         │
│    ├─> Find following assistant messages          │
│    └─> Create pairs: [(user, assistant), ...]     │
│                                                    │
│ 4. FOR EACH EXCHANGE                              │
│    ├─> Compute hash: SHA256(user + assistant)    │
│    ├─> Check if hash in saved_hashes set         │
│    ├─> IF NOT SAVED:                             │
│    │   ├─> Create title (first 60 chars)         │
│    │   ├─> Create content (formatted markdown)   │
│    │   ├─> Generate embedding (768D)             │
│    │   ├─> Save to PostgreSQL                    │
│    │   └─> Add hash to saved_hashes              │
│    └─> ELSE: skip (already saved)                │
│                                                    │
│ 5. UPDATE STATE                                   │
│    ├─> Save last_processed_position per file     │
│    ├─> Save saved_hashes (last 10,000)           │
│    └─> Write to state file                       │
│                                                    │
│ 6. LOG METRICS                                    │
│    ├─> Count: conversations saved this iteration │
│    ├─> Total: cumulative count                   │
│    └─> Timestamp: last successful run            │
│                                                    │
│ 7. SLEEP                                          │
│    └─> await asyncio.sleep(30)                   │
│                                                    │
└────────────────────────────────────────────────────┘
         │
         └─> ITERATION N+1 (30 seconds later)
```

### 3. Error Handling

```
IF ERROR OCCURS:
    ├─> Log error to /tmp/conversation-daemon.log
    ├─> Log to stdout (visible in docker logs)
    ├─> Continue to next iteration (don't crash)
    └─> Retry on next iteration (30s later)

TYPES OF ERRORS:
    ├─> FileNotFoundError → Skip transcript, continue
    ├─> JSONDecodeError → Log warning, skip line
    ├─> DatabaseError → Retry 3 times, then skip
    └─> Exception → Log stack trace, continue
```

---

## 🧩 Composants

### Component 1: Daemon Script

**Fichier**: `scripts/conversation-daemon.py`

**Responsabilités**:
- Poll transcripts directory every 30s
- Parse JSONL incrementally (only new lines)
- Dedup by hash (SHA256)
- Save via MnemoLite WriteMemoryTool
- Maintain state (persisted to disk)
- Log activity

**Taille estimée**: ~150 lignes Python

**Dépendances**:
- asyncio (stdlib)
- json (stdlib)
- hashlib (stdlib)
- pathlib (stdlib)
- MnemoLite services (déjà dans le projet)

**Key Functions**:
```python
async def poll_loop():
    """Main polling loop"""

async def scan_transcripts() -> List[Path]:
    """Find all transcript files"""

async def parse_transcript_incremental(path: Path) -> List[Tuple]:
    """Parse only new exchanges since last run"""

async def save_conversation(user: str, assistant: str, session_id: str):
    """Save to MnemoLite via WriteMemoryTool"""

def load_state() -> Dict:
    """Load daemon state from disk"""

def save_state(state: Dict):
    """Persist daemon state to disk"""
```

---

### Component 2: Docker Compose Configuration

**Fichier**: `docker-compose.yml`

**Modification Required**:

```yaml
services:
  api:
    volumes:
      # Existing volumes...
      - ~/.claude/projects:/home/user/.claude/projects:ro  # READ-ONLY mount

    command: >
      sh -c "
        python3 /app/scripts/conversation-daemon.py &
        uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
      "
```

**Explications**:
1. **Volume mount**: `~/.claude/projects` monté en **read-only** (`:ro`)
   - Daemon peut lire transcripts
   - Ne peut PAS modifier (sécurité)

2. **Command**: Lance 2 processus en parallèle
   - `python3 /app/scripts/conversation-daemon.py &` → Background (daemon)
   - `uvicorn api.main:app ...` → Foreground (API server)

3. **Logs**: Les deux processus écrivent vers stdout
   - Visible via `docker compose logs api`
   - Daemon préfixe ses logs avec `[DAEMON]`

---

### Component 3: State File

**Fichier**: `/tmp/conversation-daemon-state.json` (dans conteneur)

**Structure**:
```json
{
  "version": "1.0.0",
  "last_run": "2025-10-29T09:30:45Z",
  "transcripts": {
    "5906b2a1-cbd9-4d97-bc2b-81445d816ebe.jsonl": {
      "last_position": 5113542,
      "last_saved_hash": "a3f4d89e2c1b5f6a",
      "exchange_count": 123,
      "last_processed": "2025-10-29T09:30:45Z"
    },
    "0eb566c8-0e8d-4f56-9b6b-7ad909bdb630.jsonl": {
      "last_position": 48203,
      "last_saved_hash": "b2e8c71f9d3a4e5c",
      "exchange_count": 12,
      "last_processed": "2025-10-29T09:30:45Z"
    }
  },
  "saved_hashes": [
    "a3f4d89e2c1b5f6a",
    "b2e8c71f9d3a4e5c",
    "... (last 10,000 hashes)"
  ],
  "stats": {
    "total_saved": 152,
    "total_errors": 0,
    "uptime_seconds": 3600
  }
}
```

**Persistence**:
- Sauvegardé après chaque iteration
- Permet de reprendre après restart
- Évite re-processing de vieux échanges

---

## 📊 User Experience

### Scenario 1: Première Utilisation

```bash
User: cd /home/giak/Work/MnemoLite
User: docker compose up

[API] Starting MnemoLite API server...
[API] Uvicorn running on http://0.0.0.0:8000
[DAEMON] Conversation Auto-Save Daemon started
[DAEMON] Watching: /home/user/.claude/projects
[DAEMON] Found 45 transcript files
[DAEMON] Processing transcripts...
[DAEMON] ✓ Saved 152 conversations
[DAEMON] Polling every 30 seconds...
```

**User ne fait RIEN de plus. C'est automatique.**

---

### Scenario 2: Session Claude Code Active

```bash
Terminal 1:
User: claude
Claude: [working on code...]

Terminal 2:
User: docker compose logs -f api | grep DAEMON

[DAEMON] Poll iteration 1...
[DAEMON] Found 0 new exchanges
[DAEMON] Poll iteration 2...
[DAEMON] Found 1 new exchange in 5906b2a1-cbd9...
[DAEMON] ✓ Saved: Conv: "Brainstorm deeper et ultrathink..."
[DAEMON] Poll iteration 3...
[DAEMON] Found 0 new exchanges
```

**User peut voir l'activité (optionnel) mais n'a rien à faire.**

---

### Scenario 3: Vérification DB

```bash
User: docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT COUNT(*) FROM memories
  WHERE author = 'AutoSave'
  AND DATE(created_at) = CURRENT_DATE;
"

 count
-------
   47
(1 row)
```

**47 conversations sauvegardées aujourd'hui automatiquement.**

---

## ⚖️ Avantages / Inconvénients

### ✅ Avantages

1. **Automatique** - Aucune action user requise
2. **Transparent** - User ne voit rien (ou peut voir logs si veut)
3. **Self-contained** - Tout dans Docker
4. **Zéro config** - `docker compose up` suffit
5. **Pas d'impact OS** - Rien installé sur host
6. **Fiable** - Polling simple, pas de dépendance sur hooks
7. **Resumable** - State persisté, reprend après restart
8. **Dedup** - Hash-based, pas de doublons

### ⚠️ Inconvénients / Risques

1. **Latency** - Délai max 30s avant sauvegarde
   - **Mitigation**: Acceptable pour use case
   - **Alternative**: Réduire à 10s si nécessaire

2. **Volume mount path** - Dépend du chemin user
   - **Mitigation**: Utiliser variable env `CLAUDE_PROJECTS_DIR`
   - **Default**: `~/.claude/projects/-home-giak-Work-MnemoLite`

3. **Process management** - 2 processus dans 1 conteneur
   - **Risk**: Si daemon crash, pas de restart automatique
   - **Mitigation**: Error handling robuste + retry logic
   - **Monitoring**: Logs accessibles via `docker compose logs`

4. **Performance** - Overhead daemon
   - CPU: ~0.5% (poll 30s)
   - Memory: ~20MB
   - **Mitigation**: Négligeable

5. **Crash API** - Si API crash, daemon crash aussi
   - **Mitigation**: Docker restart policy
   - **Alternative**: Separate container (overkill)

---

## 🔍 Alternatives Considérées

### Alternative 1: Container Séparé

```yaml
services:
  daemon:
    build: .
    command: python3 /app/scripts/conversation-daemon.py
    depends_on:
      - db
```

**Avantages**: Isolation complète
**Inconvénients**: Plus complexe, 3 conteneurs au lieu de 2

**Verdict**: ❌ Overkill pour ce use case

---

### Alternative 2: Supervisord

```yaml
services:
  api:
    command: supervisord -c /app/supervisord.conf
```

**Avantages**: Process management robuste
**Inconvénients**: Dépendance externe (supervisord)

**Verdict**: ❌ Viole contrainte "pas de dépendances"

---

### Alternative 3: Systemd (inside container)

**Avantages**: Standard Linux
**Inconvénients**: Complexe, anti-pattern Docker

**Verdict**: ❌ Bad practice

---

## 🧪 Plan de Test

### Test 1: Daemon Starts

```bash
docker compose up -d
docker compose logs api | grep DAEMON | head -5

# Expected:
# [DAEMON] Conversation Auto-Save Daemon started
# [DAEMON] Watching: /home/user/.claude/projects
# [DAEMON] Found X transcript files
```

**Pass criteria**: Daemon logs visible

---

### Test 2: Initial Import

```bash
# Before
docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT COUNT(*) FROM memories WHERE author = 'AutoSave';
"
# → 6

# Wait 60s (2 iterations)

# After
docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT COUNT(*) FROM memories WHERE author = 'AutoSave';
"
# → 158 (all historical conversations imported)
```

**Pass criteria**: All historical conversations imported on first run

---

### Test 3: Real-Time Save

```bash
# Terminal 1: Watch daemon logs
docker compose logs -f api | grep DAEMON

# Terminal 2: Create new Claude Code conversation
claude
# Have 2-3 exchanges with Claude

# Expected in Terminal 1 (within 30-60s):
# [DAEMON] Found 2 new exchanges in [session-id]
# [DAEMON] ✓ Saved: Conv: "First question..."
# [DAEMON] ✓ Saved: Conv: "Second question..."
```

**Pass criteria**: New conversations saved within 60s

---

### Test 4: Deduplication

```bash
# Restart daemon (should re-scan files)
docker compose restart api

# Wait 60s

# Check DB count - should NOT increase
docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT COUNT(*) FROM memories WHERE author = 'AutoSave';
"
# → Same count as before
```

**Pass criteria**: No duplicates created on restart

---

### Test 5: Error Recovery

```bash
# Stop DB
docker compose stop db

# Daemon should log errors but not crash

# Restart DB
docker compose start db

# Wait 60s - daemon should recover and continue
```

**Pass criteria**: Daemon continues after DB temporary unavailability

---

## 📈 Metrics & Monitoring

### Logs Structure

```
[DAEMON] 2025-10-29 09:30:45 | INFO | Daemon started
[DAEMON] 2025-10-29 09:30:45 | INFO | Watching /home/user/.claude/projects
[DAEMON] 2025-10-29 09:30:45 | INFO | Found 45 transcripts
[DAEMON] 2025-10-29 09:30:47 | INFO | ✓ Saved 152 conversations (initial import)
[DAEMON] 2025-10-29 09:31:17 | INFO | Poll iteration 1 - 0 new exchanges
[DAEMON] 2025-10-29 09:31:47 | INFO | Poll iteration 2 - 2 new exchanges
[DAEMON] 2025-10-29 09:31:48 | INFO | ✓ Saved: Conv: "Brainstorm deeper..."
[DAEMON] 2025-10-29 09:31:49 | INFO | ✓ Saved: Conv: "créer un schéma..."
[DAEMON] 2025-10-29 09:32:17 | ERROR | Failed to connect to DB: Connection refused
[DAEMON] 2025-10-29 09:32:17 | INFO | Retrying in 30s...
```

### Health Check (Optional)

```bash
# User can check daemon health anytime
docker compose exec api cat /tmp/conversation-daemon-state.json | jq '.stats'

{
  "total_saved": 152,
  "total_errors": 0,
  "uptime_seconds": 3600,
  "last_run": "2025-10-29T09:30:45Z"
}
```

---

## 🎯 Décision Required

**Questions for Validation:**

1. ✅ **Volume mount path OK?**
   - Default: `~/.claude/projects/-home-giak-Work-MnemoLite`
   - User peut override avec env var si besoin?

2. ✅ **Polling interval OK?**
   - Default: 30 secondes
   - Acceptable latency?

3. ✅ **Process management OK?**
   - 2 processus dans 1 conteneur (daemon + API)
   - Ou préfères-tu conteneur séparé?

4. ✅ **Logs OK?**
   - Logs daemon mélangés avec logs API
   - Préfixe `[DAEMON]` pour distinguer
   - Ou fichier log séparé?

5. ✅ **State persistence OK?**
   - State dans `/tmp/` du conteneur (perdu si volume supprimé)
   - Ou monter volume pour persister state?

---

## 🚀 Next Steps (if approved)

1. **Implementation** (1h)
   - Create `scripts/conversation-daemon.py`
   - Modify `docker-compose.yml`
   - Test locally

2. **Testing** (30min)
   - Run all 5 test scenarios
   - Verify DB content
   - Check logs

3. **Documentation** (30min)
   - Update README
   - Add troubleshooting guide
   - Document env vars

**Total ETA: 2h**

---

**Attends validation avant de commencer l'implémentation.**

**Version**: 1.0.0
**Date**: 2025-10-29
**Author**: Claude Code Assistant
**EPIC**: EPIC-24 (Auto-Save Conversations)
**Status**: ⏳ PENDING USER VALIDATION
