# Cleanup Dual Auto-Save System - Design Document

**Date:** 2025-11-13
**Status:** Ready for Implementation
**Related:** EPIC-24 Auto-Save Reliability System

---

## Problem Statement

Currently, MnemoLite has **two parallel auto-save systems** running simultaneously:

1. **Real-time Hooks** (Active & Preferred)
   - `.claude/hooks/Stop/auto-save.sh` and `.claude/hooks/UserPromptSubmit/auto-save-previous.sh`
   - Calls `scripts/save-conversation-from-hook.sh`
   - Pushes to Redis Queue via `/v1/conversations/queue`
   - Saves in real-time after each exchange

2. **Auto-Import Daemon** (Running but Redundant)
   - `conversation-auto-import.sh` runs in background (started in docker-compose)
   - Calls `/v1/conversations/import` every 30 seconds
   - Scans all transcripts and imports new ones

**Issues:**
- Potential duplications between systems
- Confusion about which system is active
- Daemon logs clutter (repeated imports)
- Unnecessary resource usage

---

## Solution Overview - Approach A (Minimal Cleanup)

**Decision:** Keep real-time hooks as primary system, disable daemon by default, preserve manual import capability.

**Changes:**
1. Disable auto-import daemon in `docker-compose.yml` (add environment flag)
2. Remove obsolete hook backups (`.claude/hooks.backup.*`)
3. Document the active system and manual import process
4. Simplify healthcheck (remove daemon check)

**Benefits:**
- Single active system (hooks)
- Cleaner logs
- No duplications
- Manual import still available for historical data

---

## Detailed Design

### 1. Docker Compose Changes

**File:** `docker-compose.yml`

**Current Command (Lines 119-124):**
```yaml
command:
  - sh
  - -c
  - |
    nohup bash /app/scripts/conversation-auto-import.sh > /tmp/daemon.log 2>&1 &
    exec uvicorn main:app --host 0.0.0.0 --port 8000
```

**Proposed Command:**
```yaml
command:
  - sh
  - -c
  - |
    if [ "${ENABLE_AUTO_IMPORT:-false}" = "true" ]; then
      nohup bash /app/scripts/conversation-auto-import.sh > /tmp/daemon.log 2>&1 &
    fi
    exec uvicorn main:app --host 0.0.0.0 --port 8000
```

**Add Environment Variable (Line 88):**
```yaml
ENABLE_AUTO_IMPORT: ${ENABLE_AUTO_IMPORT:-false}
```

**Current Healthcheck (Lines 126-131):**
```yaml
healthcheck:
  test: ["CMD", "sh", "-c", "curl -f http://localhost:8000/health && curl -f http://localhost:8000/v1/autosave/health"]
  interval: 60s
  timeout: 10s
  retries: 3
  start_period: 120s
```

**Proposed Healthcheck:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 60s
  timeout: 10s
  retries: 3
  start_period: 120s
```

### 2. Environment Configuration

**File:** `.env`

**Add:**
```bash
# Auto-Import Daemon (disabled by default, use hooks instead)
ENABLE_AUTO_IMPORT=false
```

### 3. File Cleanup

**Files to DELETE:**
```
.claude/hooks.backup.20251112_132219/
.claude/hooks.backup.20251112_171418/
.claude/hooks.obsolete/
```

**Files to KEEP:**
```
✅ scripts/save-conversation-from-hook.sh (used by hooks)
✅ scripts/get-project-name.sh (used by hooks)
✅ scripts/import-historical-conversations.py (manual import tool)
✅ scripts/conversation-auto-import.sh (reference, can be re-enabled)
✅ .claude/hooks/Stop/auto-save.sh (active)
✅ .claude/hooks/UserPromptSubmit/auto-save-previous.sh (active)
✅ API endpoint /v1/conversations/import (marked DEPRECATED)
```

### 4. Documentation Updates

**Add to README.md or QUICKSTART.md:**

```markdown
## 🔄 Auto-Save des Conversations Claude Code

MnemoLite sauvegarde automatiquement toutes vos conversations via des hooks temps réel.

### Système Actif : Hooks Temps Réel

**Architecture :**
```
Claude Code → Hook Stop/UserPromptSubmit → save-conversation-from-hook.sh
           → API /queue → Redis Streams → Worker → PostgreSQL
```

**Hooks installés :**
- `.claude/hooks/Stop/auto-save.sh` : Sauvegarde à la fin de chaque conversation
- `.claude/hooks/UserPromptSubmit/auto-save-previous.sh` : Sauvegarde l'échange précédent

**Aucune configuration requise** - Les hooks sont automatiquement actifs.

### Import Historique (Manuel)

Pour importer les conversations passées d'un nouveau projet :

```bash
# Depuis le conteneur API
docker compose exec api python3 /app/scripts/import-historical-conversations.py

# Ou via l'API (DEPRECATED)
curl -X POST http://localhost:8001/v1/conversations/import \
  -H "Content-Type: application/json" \
  -d '{"projects_dir": "/host/.claude/projects"}'
```

⚠️ **Note :** L'import historique est un outil ponctuel, pas un daemon continu.

### Réactiver le Daemon (Si Nécessaire)

```bash
# Dans .env
ENABLE_AUTO_IMPORT=true

# Redémarrer
docker compose restart api
```
```

**Update:** `docs/plans/2025-11-12-autosave-reliability-queue.md`

Add note at top:

```markdown
## ⚠️ UPDATE 2025-11-13: Daemon Auto-Import Désactivé

Le daemon `conversation-auto-import.sh` est désormais **désactivé par défaut**.

**Raison :** Les hooks temps réel (Task 3) sont maintenant le système principal.
**Impact :** Aucun - Les hooks sauvegardent en temps réel via Redis Queue.
**Réactivation :** `ENABLE_AUTO_IMPORT=true` dans `.env` si nécessaire.

---
```

---

## Deployment Plan

### Step 1: Update docker-compose.yml
- Modify `command` to conditionally start daemon
- Add `ENABLE_AUTO_IMPORT` environment variable
- Simplify `healthcheck`

### Step 2: Update .env
```bash
echo "ENABLE_AUTO_IMPORT=false" >> .env
```

### Step 3: Cleanup Obsolete Files
```bash
rm -rf .claude/hooks.backup.* .claude/hooks.obsolete/
```

### Step 4: Restart API Container
```bash
docker compose restart api
```

### Step 5: Verification

**Check daemon is NOT running:**
```bash
docker compose exec api ps aux | grep conversation-auto-import
# Expected: No process found
```

**Check API is healthy:**
```bash
curl http://localhost:8001/health
# Expected: {"status": "healthy"}
```

**Check hooks work:**
- Create a new conversation in Claude Code
- Check worker logs: `docker compose logs worker --tail 20`
- Expected: `"event": "message_processed"`

**Test manual import:**
```bash
docker compose exec api python3 /app/scripts/import-historical-conversations.py
# Expected: Imports any missing conversations
```

**Verify no duplications:**
- Wait 5 minutes
- Query DB for duplicate titles
```bash
docker compose exec db psql -U mnemo -d mnemolite -c "
  SELECT title, COUNT(*) as count
  FROM memories
  WHERE memory_type = 'conversation'
    AND created_at > NOW() - INTERVAL '10 minutes'
  GROUP BY title
  HAVING COUNT(*) > 1;
"
# Expected: 0 rows (no duplicates)
```

---

## Testing Strategy

### Test 1: Real-Time Hooks Work
1. Create a new conversation in Claude Code
2. Check worker logs: Should see message processed
3. Query DB: Conversation should exist with author='AutoSave'

### Test 2: Manual Import Works
1. Run `import-historical-conversations.py`
2. Should import any missing historical conversations
3. Should skip duplicates

### Test 3: Daemon Stays Disabled
1. Wait 5 minutes after restart
2. Check process list: No auto-import daemon
3. Check logs: No repeated import calls

### Test 4: Re-Enable Daemon (Optional)
1. Set `ENABLE_AUTO_IMPORT=true` in `.env`
2. Restart API
3. Check process list: Daemon should be running
4. Set back to `false` and restart

---

## Rollback Plan

If issues occur:

```bash
# Revert docker-compose.yml changes
git checkout HEAD -- docker-compose.yml .env

# Restart API
docker compose restart api

# Or temporarily re-enable daemon
ENABLE_AUTO_IMPORT=true docker compose up -d api
```

---

## Success Criteria

- ✅ Daemon auto-import is disabled by default
- ✅ Real-time hooks continue to work
- ✅ Manual import script remains functional
- ✅ No duplicate conversations created
- ✅ Logs are cleaner (no repeated import calls)
- ✅ Documentation clearly explains the system
- ✅ Environment variable allows re-enabling daemon if needed

---

## Future Considerations

1. **Remove deprecated endpoint** - In v2.0, consider removing `/v1/conversations/import` entirely
2. **Archive daemon script** - Move `conversation-auto-import.sh` to `scripts/archive/` if never used
3. **Simplify worker** - Could remove import-related code if only queue-based saves are used

---

## Files Modified

- `docker-compose.yml` - Command, environment, healthcheck
- `.env` - Add ENABLE_AUTO_IMPORT flag
- README.md or QUICKSTART.md - Document active system
- `docs/plans/2025-11-12-autosave-reliability-queue.md` - Add update note

## Files Deleted

- `.claude/hooks.backup.20251112_132219/` (recursive)
- `.claude/hooks.backup.20251112_171418/` (recursive)
- `.claude/hooks.obsolete/` (recursive)

## Files Preserved

All active scripts and endpoints remain unchanged.
