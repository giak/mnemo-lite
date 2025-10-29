# Auto-Save Conversations - Quick Start Guide

**Status**: ✅ WORKING - Implemented & Tested
**Date**: 2025-10-29
**EPIC**: EPIC-24

---

## 🎯 What It Does

**Automatically saves ALL your Claude Code conversations to MnemoLite PostgreSQL database.**

- ✅ **Automatic** - No manual action required
- ✅ **Transparent** - Runs in background
- ✅ **Real-time** - Saves within 30 seconds
- ✅ **Self-contained** - Everything in Docker
- ✅ **Zero external dependencies**

---

## 🚀 Quick Start (3 Steps)

### Step 1: Auto-detect Your Projects Directory

```bash
cd /path/to/MnemoLite
./scripts/setup-env.sh
```

This creates `.env` with the correct `CLAUDE_PROJECTS_DIR`.

### Step 2: Start MnemoLite

```bash
docker compose up
```

That's it! The daemon starts automatically.

### Step 3: Verify It's Working

```bash
# Check daemon logs
docker compose logs api | grep DAEMON

# Check saved conversations
docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT COUNT(*) FROM memories
  WHERE author = 'AutoSave';
"
```

---

## 📊 What Gets Saved

- **User question** + **Claude response** = 1 conversation
- **Metadata**: Session ID, timestamp, tags
- **Embeddings**: 768D vector for semantic search
- **Deduplication**: Hash-based, no duplicates

**Storage**: PostgreSQL `memories` table with author = `'AutoSave'`

---

## ⚙️ Configuration (Optional)

### Import Historical Conversations

By default, the daemon only captures **new** conversations (from now on).

To import **all historical conversations**:

```bash
IMPORT_HISTORICAL=true docker compose up
```

**Warning**: This will import ALL past conversations from transcripts. For large history (1000+ exchanges), this may take 5-10 minutes on first start.

### Adjust Poll Interval

Default: 30 seconds

To change (example: 10 seconds):

```bash
POLL_INTERVAL=10 docker compose up
```

### Custom Projects Directory

If auto-detection fails:

```bash
# Find your Claude projects directory
ls ~/.claude/projects/

# Set manually
export CLAUDE_PROJECTS_DIR=~/.claude/projects/-your-project-name
docker compose up
```

---

## 🔍 Monitoring

### Check Daemon Status

```bash
docker compose logs -f api | grep DAEMON
```

**Expected output**:
```
[DAEMON] 2025-10-29 09:21:54 | INFO  | MnemoLite Conversation Auto-Save Daemon Starting
[DAEMON] 2025-10-29 09:21:54 | INFO  | Projects directory: /home/user/.claude/projects
[DAEMON] 2025-10-29 09:21:54 | INFO  | Found 29 transcript file(s)
[DAEMON] 2025-10-29 09:21:54 | DEBUG | No new exchanges found
```

### List Saved Conversations

```bash
docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT
    LEFT(title, 60) as title,
    created_at,
    tags
  FROM memories
  WHERE author = 'AutoSave'
  ORDER BY created_at DESC
  LIMIT 10;
"
```

### Count Conversations Today

```bash
docker compose exec -T db psql -U mnemo -d mnemolite -c "
  SELECT COUNT(*) as today
  FROM memories
  WHERE author = 'AutoSave'
    AND DATE(created_at) = CURRENT_DATE;
"
```

---

## 🐛 Troubleshooting

### Daemon Not Starting

**Check logs**:
```bash
docker compose logs api | grep -E "DAEMON|Error"
```

**Common issues**:
1. `.env` file missing → Run `./scripts/setup-env.sh`
2. Projects directory not found → Check `CLAUDE_PROJECTS_DIR` in `.env`
3. DB connection failed → Wait 30s, daemon will retry

### No Conversations Saved

**Check if daemon is running**:
```bash
docker compose logs api | grep DAEMON | tail -5
```

**Should see**: `DEBUG | No new exchanges found` (means daemon is working, just no new conversations yet)

**Test with a new conversation**:
1. Start Claude Code in this workspace
2. Have a conversation
3. Wait 30-60 seconds
4. Check DB again

### Projects Directory Not Found

**Auto-detect again**:
```bash
./scripts/setup-env.sh
```

**Manual detection**:
```bash
# Find all Claude projects
ls -la ~/.claude/projects/

# Your project should match your workspace path
# Example: -home-giak-Work-MnemoLite for /home/giak/Work/MnemoLite
```

---

## 📈 Performance

**Resource Usage** (typical):
- CPU: < 1% (idle), ~5% during save
- Memory: ~20MB
- Disk I/O: Minimal (read-only transcripts)

**Latency**:
- Conversation → Saved: < 60 seconds (30s poll + processing time)
- Database write: ~50ms per conversation
- No impact on Claude Code performance

---

## 🎓 How It Works

```
Claude Code Session
        ↓
Writes to ~/.claude/projects/[session-id].jsonl
        ↓
Daemon polls every 30s
        ↓
Detects new exchanges (incremental parsing)
        ↓
Hash-based deduplication check
        ↓
Save via WriteMemoryTool
        ↓
PostgreSQL + embeddings (768D)
        ↓
Ready for semantic search!
```

**State Management**:
- `/tmp/conversation-daemon-state.json` tracks processed exchanges
- State persisted across restarts
- No re-processing of old conversations

---

## 🔧 Advanced Usage

### Stop Auto-Save Temporarily

```bash
# Stop daemon (API keeps running)
docker compose exec api pkill -f conversation-daemon

# Daemon auto-restarts in 5 seconds (via restart loop)
```

### Clear State (Force Re-scan)

```bash
docker compose exec api rm /tmp/conversation-daemon-state.json
docker compose restart api
```

### View Daemon State

```bash
docker compose exec api cat /tmp/conversation-daemon-state.json | jq .
```

---

## 📚 Related Docs

- **Architecture**: [EPIC-24_ARCHITECTURE_DAEMON_PROPOSAL.md](agile/serena-evolution/03_EPICS/EPIC-24_ARCHITECTURE_DAEMON_PROPOSAL.md)
- **Simulation**: [EPIC-24_SIMULATION_DEEP_ANALYSIS.md](agile/serena-evolution/03_EPICS/EPIC-24_SIMULATION_DEEP_ANALYSIS.md)
- **Solutions Comparison**: [EPIC-24_SOLUTIONS_COMPARISON_ULTRATHINK.md](agile/serena-evolution/03_EPICS/EPIC-24_SOLUTIONS_COMPARISON_ULTRATHINK.md)

---

## ✅ Success Checklist

- [ ] `.env` file created with correct `CLAUDE_PROJECTS_DIR`
- [ ] `docker compose up` starts without errors
- [ ] Daemon logs visible: `docker compose logs api | grep DAEMON`
- [ ] Transcripts found: `Found X transcript file(s)`
- [ ] New conversations automatically saved within 60 seconds

---

**Version**: 1.0.0
**Status**: Production Ready
**Tested**: 2025-10-29
**Maintainer**: MnemoLite Team
